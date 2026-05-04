"""SQLite-backed job memory — prevents re-processing seen jobs."""

from __future__ import annotations

import os
import sqlite3
from datetime import date

_storage_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_storage_dir, "jobs.db")
TEST_DB_PATH = os.path.join(_storage_dir, "jobs_test.db")


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_db(db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                company    TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen  TEXT NOT NULL,
                decision   TEXT,
                email_sent INTEGER DEFAULT 0,
                score      INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def is_known_job(title: str, company: str, db_path: str = DB_PATH) -> bool:
    t = (title or "").strip()
    c = (company or "").strip()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE lower(title) = lower(?) AND lower(company) = lower(?)",
            (t, c),
        ).fetchone()
    return row is not None


def update_last_seen(title: str, company: str, db_path: str = DB_PATH) -> None:
    today = date.today().isoformat()
    t = (title or "").strip()
    c = (company or "").strip()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET last_seen = ? WHERE lower(title) = lower(?) AND lower(company) = lower(?)",
            (today, t, c),
        )
        conn.commit()


def record_job(job: dict, decision: str, score: int, email_sent: bool, db_path: str = DB_PATH) -> None:
    today = date.today().isoformat()
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (title, company, first_seen, last_seen, decision, email_sent, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, company, today, today, decision, int(email_sent), score),
        )
        conn.commit()
