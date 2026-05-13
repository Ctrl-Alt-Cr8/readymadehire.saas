"""Postgres-backed job memory and user config — all DB access lives here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool


@dataclass
class UserConfig:
    user_id: str
    name: str
    target_roles: list
    location_pref: str
    keywords: list
    summary: str
    constraints: str
    recipient_email: str
    interview_answers: str = ""
    min_salary_k: int = 0
    years_experience: int = 0
    job_type: str = ""

    def as_profile(self) -> dict:
        """Return profile dict shape expected by Claude prompts."""
        profile: dict = {
            "name": self.name,
            "roles": self.target_roles,
            "location": self.location_pref,
            "constraints": self.constraints,
            "summary": self.summary,
        }
        if self.min_salary_k:
            profile["min_salary_k"] = self.min_salary_k
            profile["salary_note"] = f"Minimum ${self.min_salary_k}k/year — score down jobs that pay less"
        if self.years_experience:
            profile["years_experience"] = self.years_experience
        if self.job_type and self.job_type.lower() != "any":
            profile["job_type"] = self.job_type
        return profile

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        import urllib.parse
        dsn = os.environ["DATABASE_URL"]
        parsed = urllib.parse.urlparse(dsn)
        host = parsed.hostname or ""
        # Cloud Run passes the socket path as a query param: ?host=/cloudsql/...
        query = urllib.parse.parse_qs(parsed.query)
        socket_host = (query.get("host") or [""])[0]
        unix_socket = host.startswith("/") or socket_host.startswith("/")
        # For TCP, force IPv4 — macOS DNS64 translates IPv4 to IPv6 which Cloud SQL rejects.
        # Unix socket connections (Cloud Run + Cloud SQL Auth Proxy) need no hostaddr.
        extra = {} if unix_socket else {"hostaddr": host}
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn,
            **extra,
        )
    return _pool


def _connect():
    return _get_pool().getconn()


def _release(conn) -> None:
    _get_pool().putconn(conn)


def init_db() -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            # Advisory lock prevents concurrent gunicorn workers from deadlocking
            # on ALTER TABLE during simultaneous startup
            cur.execute("SELECT pg_advisory_lock(987654321)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id         TEXT PRIMARY KEY,
                    email      TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_configs (
                    user_id         TEXT PRIMARY KEY REFERENCES users(id),
                    name            TEXT NOT NULL,
                    target_roles    TEXT[],
                    location_pref   TEXT,
                    keywords        TEXT[],
                    summary         TEXT,
                    constraints     TEXT,
                    recipient_email TEXT,
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id         SERIAL PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    title      TEXT NOT NULL,
                    company    TEXT NOT NULL,
                    first_seen DATE NOT NULL,
                    last_seen  DATE NOT NULL,
                    decision   TEXT,
                    email_sent BOOLEAN DEFAULT FALSE,
                    score      INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_user_title_company
                ON jobs (user_id, lower(title), lower(company))
            """)
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS url TEXT")
            cur.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS interview_answers TEXT")
            cur.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS min_salary_k INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS years_experience INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS job_type TEXT DEFAULT ''")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS run_logs (
                    id             SERIAL PRIMARY KEY,
                    user_id        TEXT NOT NULL REFERENCES users(id),
                    run_at         TIMESTAMPTZ DEFAULT NOW(),
                    jobs_fetched   INTEGER,
                    jobs_apply     INTEGER,
                    jobs_review    INTEGER,
                    jobs_skip      INTEGER,
                    haiku_tokens   INTEGER,
                    sonnet_tokens  INTEGER,
                    estimated_cost NUMERIC(8, 4)
                )
            """)
            cur.execute("SELECT pg_advisory_unlock(987654321)")
        conn.commit()
    finally:
        _release(conn)


def _local_fallback_config(user_id: str) -> UserConfig:
    """Fallback when DATABASE_URL is not set (local CLI testing without DB)."""
    from app.config import PROFILE, KEYWORDS  # noqa: PLC0415
    return UserConfig(
        user_id=user_id,
        name=PROFILE["name"],
        target_roles=PROFILE["roles"],
        location_pref=PROFILE["location"],
        keywords=KEYWORDS,
        summary=PROFILE["summary"],
        constraints=PROFILE["constraints"],
        recipient_email=os.getenv("RECIPIENT_EMAIL", ""),
    )


def get_user_config(user_id: str) -> UserConfig:
    """Load per-user pipeline config. Falls back to local config.py if no DATABASE_URL."""
    if not os.getenv("DATABASE_URL"):
        return _local_fallback_config(user_id)

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM user_configs WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        _release(conn)

    if row is None:
        raise ValueError(f"No config found for user {user_id!r} — complete onboarding first.")

    return UserConfig(
        user_id=user_id,
        name=row["name"],
        target_roles=list(row["target_roles"] or []),
        location_pref=row["location_pref"] or "",
        keywords=list(row["keywords"] or []),
        summary=row["summary"] or "",
        constraints=row["constraints"] or "",
        recipient_email=row["recipient_email"] or "",
        interview_answers=row.get("interview_answers") or "",
        min_salary_k=int(row.get("min_salary_k") or 0),
        years_experience=int(row.get("years_experience") or 0),
        job_type=row.get("job_type") or "",
    )


def get_runs_with_jobs(user_id: str) -> list:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, run_at, jobs_fetched, jobs_apply, jobs_review, jobs_skip, estimated_cost
                FROM run_logs
                WHERE user_id = %s
                ORDER BY run_at DESC
                LIMIT 30
                """,
                (user_id,),
            )
            runs = [dict(r) for r in cur.fetchall()]

            for run in runs:
                run_date = run["run_at"].date()
                cur.execute(
                    """
                    SELECT id, title, company, decision, score, url
                    FROM jobs
                    WHERE user_id = %s AND first_seen = %s
                    ORDER BY
                        CASE decision WHEN 'APPLY' THEN 1 WHEN 'REVIEW' THEN 2 ELSE 3 END,
                        score DESC
                    """,
                    (user_id, run_date),
                )
                run["jobs"] = [dict(j) for j in cur.fetchall()]
                run["run_at"] = run["run_at"].isoformat()
                run["estimated_cost"] = float(run["estimated_cost"] or 0)
    finally:
        _release(conn)
    return runs


def save_user(user_id: str, email: str) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                (user_id, email),
            )
        conn.commit()
    finally:
        _release(conn)


def save_user_config(
    user_id: str,
    name: str,
    target_roles: list,
    location_pref: str,
    keywords: list,
    summary: str,
    constraints: str,
    recipient_email: str,
    interview_answers: str = "",
    min_salary_k: int = 0,
    years_experience: int = 0,
    job_type: str = "",
) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_configs
                    (user_id, name, target_roles, location_pref, keywords, summary, constraints,
                     recipient_email, interview_answers, min_salary_k, years_experience, job_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    name              = EXCLUDED.name,
                    target_roles      = EXCLUDED.target_roles,
                    location_pref     = EXCLUDED.location_pref,
                    keywords          = EXCLUDED.keywords,
                    summary           = EXCLUDED.summary,
                    constraints       = EXCLUDED.constraints,
                    recipient_email   = EXCLUDED.recipient_email,
                    interview_answers = EXCLUDED.interview_answers,
                    min_salary_k      = EXCLUDED.min_salary_k,
                    years_experience  = EXCLUDED.years_experience,
                    job_type          = EXCLUDED.job_type,
                    updated_at        = NOW()
                """,
                (user_id, name, target_roles, location_pref, keywords, summary, constraints,
                 recipient_email, interview_answers, min_salary_k, years_experience, job_type),
            )
        conn.commit()
    finally:
        _release(conn)


def is_known_job(title: str, company: str, user_id: str) -> bool:
    t = (title or "").strip()
    c = (company or "").strip()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM jobs WHERE user_id = %s AND lower(title) = lower(%s) AND lower(company) = lower(%s)",
                (user_id, t, c),
            )
            return cur.fetchone() is not None
    finally:
        _release(conn)


def update_last_seen(title: str, company: str, user_id: str) -> None:
    today = date.today()
    t = (title or "").strip()
    c = (company or "").strip()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET last_seen = %s WHERE user_id = %s AND lower(title) = lower(%s) AND lower(company) = lower(%s)",
                (today, user_id, t, c),
            )
        conn.commit()
    finally:
        _release(conn)


def record_run_log(
    user_id: str,
    jobs_fetched: int,
    jobs_apply: int,
    jobs_review: int,
    jobs_skip: int,
    haiku_tokens: int,
    sonnet_tokens: int,
    estimated_cost: float,
) -> None:
    if not os.getenv("DATABASE_URL"):
        return
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO run_logs
                    (user_id, jobs_fetched, jobs_apply, jobs_review, jobs_skip,
                     haiku_tokens, sonnet_tokens, estimated_cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, jobs_fetched, jobs_apply, jobs_review, jobs_skip,
                 haiku_tokens, sonnet_tokens, estimated_cost),
            )
        conn.commit()
    finally:
        _release(conn)


def record_job(job: dict, decision: str, score: int, email_sent: bool, user_id: str) -> None:
    today = date.today()
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    url = (job.get("url") or "").strip()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (user_id, title, company, first_seen, last_seen, decision, email_sent, score, url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, title, company, today, today, decision, email_sent, score, url),
            )
        conn.commit()
    finally:
        _release(conn)
