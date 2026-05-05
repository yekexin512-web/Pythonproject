from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_opening_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    posted_date TEXT,
    deadline_date TEXT,
    apply_url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Internship',
    source TEXT NOT NULL DEFAULT 'UN Careers',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline_date ON jobs(deadline_date);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen_at ON jobs(first_seen_at);
"""


def _date_to_text(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _dt_to_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def upsert_jobs(connection: sqlite3.Connection, jobs: list[Job], now: datetime) -> list[Job]:
    new_jobs: list[Job] = []
    for job in jobs:
        existing = connection.execute(
            "SELECT job_opening_id FROM jobs WHERE job_opening_id = ?",
            (job.job_opening_id,),
        ).fetchone()
        if existing is None:
            new_jobs.append(job)
            connection.execute(
                """
                INSERT INTO jobs (
                    job_opening_id, title, department, location, posted_date,
                    deadline_date, apply_url, category, source, first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_opening_id,
                    job.title,
                    job.department,
                    job.location,
                    _date_to_text(job.posted_date),
                    _date_to_text(job.deadline_date),
                    job.apply_url,
                    job.category,
                    job.source,
                    _dt_to_text(now),
                    _dt_to_text(now),
                ),
            )
        else:
            connection.execute(
                """
                UPDATE jobs
                SET title = ?, department = ?, location = ?, posted_date = ?,
                    deadline_date = ?, apply_url = ?, category = ?, source = ?,
                    last_seen_at = ?
                WHERE job_opening_id = ?
                """,
                (
                    job.title,
                    job.department,
                    job.location,
                    _date_to_text(job.posted_date),
                    _date_to_text(job.deadline_date),
                    job.apply_url,
                    job.category,
                    job.source,
                    _dt_to_text(now),
                    job.job_opening_id,
                ),
            )
    connection.commit()
    return new_jobs


def jobs_deadline_on(connection: sqlite3.Connection, target_date: date) -> list[Job]:
    rows = connection.execute(
        """
        SELECT * FROM jobs
        WHERE deadline_date = ?
        ORDER BY title COLLATE NOCASE
        """,
        (target_date.isoformat(),),
    ).fetchall()
    return [_row_to_job(row) for row in rows]


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_opening_id=row["job_opening_id"],
        title=row["title"],
        department=row["department"],
        location=row["location"],
        posted_date=date.fromisoformat(row["posted_date"]) if row["posted_date"] else None,
        deadline_date=date.fromisoformat(row["deadline_date"]) if row["deadline_date"] else None,
        apply_url=row["apply_url"],
        category=row["category"],
        source=row["source"],
        first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
    )
