"""Postgres-backed job memory — prevents re-processing seen jobs across users."""

from __future__ import annotations

import os
from datetime import date

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=os.environ["DATABASE_URL"],
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


def record_job(job: dict, decision: str, score: int, email_sent: bool, user_id: str) -> None:
    today = date.today()
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (user_id, title, company, first_seen, last_seen, decision, email_sent, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, title, company, today, today, decision, email_sent, score),
            )
        conn.commit()
    finally:
        _release(conn)
