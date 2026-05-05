from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from zoneinfo import ZoneInfo

from .config import BASE_DIR, load_settings
from .storage import connect


APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="UN Internship Monitor")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str = Query("", description="Search keyword"),
    source: str = Query("all", description="Job source"),
    status: str = Query("active", description="active, deadline, today, all"),
) -> HTMLResponse:
    settings = load_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    tomorrow = today + timedelta(days=settings.lookahead_days)

    with connect(settings.database_path) as connection:
        stats = _stats(connection, today, tomorrow)
        sources = _sources(connection)
        jobs = _jobs(connection, q=q, source=source, status=status, today=today, tomorrow=tomorrow)
        last_updated = _last_updated(connection)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "jobs": jobs,
            "stats": stats,
            "sources": sources,
            "filters": {"q": q, "source": source, "status": status},
            "today": today,
            "tomorrow": tomorrow,
            "last_updated": last_updated,
        },
    )


@app.get("/api/jobs")
def jobs_api(
    q: str = "",
    source: str = "all",
    status: str = "active",
) -> dict[str, Any]:
    settings = load_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    tomorrow = today + timedelta(days=settings.lookahead_days)
    with connect(settings.database_path) as connection:
        jobs = _jobs(connection, q=q, source=source, status=status, today=today, tomorrow=tomorrow)
    return {"count": len(jobs), "jobs": jobs}


def _stats(connection: sqlite3.Connection, today: date, tomorrow: date) -> dict[str, int]:
    total = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    active = connection.execute(
        "SELECT COUNT(*) FROM jobs WHERE deadline_date IS NULL OR deadline_date >= ?",
        (today.isoformat(),),
    ).fetchone()[0]
    today_posted = connection.execute(
        "SELECT COUNT(*) FROM jobs WHERE posted_date = ?",
        (today.isoformat(),),
    ).fetchone()[0]
    deadline_tomorrow = connection.execute(
        "SELECT COUNT(*) FROM jobs WHERE deadline_date = ?",
        (tomorrow.isoformat(),),
    ).fetchone()[0]
    sources = connection.execute("SELECT COUNT(DISTINCT source) FROM jobs").fetchone()[0]
    return {
        "total": total,
        "active": active,
        "today_posted": today_posted,
        "deadline_tomorrow": deadline_tomorrow,
        "sources": sources,
    }


def _sources(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL AND source != '' ORDER BY source"
    ).fetchall()
    return [row[0] for row in rows]


def _last_updated(connection: sqlite3.Connection) -> str:
    value = connection.execute("SELECT MAX(last_seen_at) FROM jobs").fetchone()[0]
    if not value:
        return "No data yet"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def _jobs(
    connection: sqlite3.Connection,
    *,
    q: str,
    source: str,
    status: str,
    today: date,
    tomorrow: date,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[str] = []

    if q.strip():
        keyword = f"%{q.strip()}%"
        clauses.append("(title LIKE ? OR department LIKE ? OR location LIKE ? OR job_opening_id LIKE ?)")
        params.extend([keyword, keyword, keyword, keyword])

    if source != "all":
        clauses.append("source = ?")
        params.append(source)

    if status == "active":
        clauses.append("(deadline_date IS NULL OR deadline_date >= ?)")
        params.append(today.isoformat())
    elif status == "deadline":
        clauses.append("deadline_date = ?")
        params.append(tomorrow.isoformat())
    elif status == "today":
        clauses.append("posted_date = ?")
        params.append(today.isoformat())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""
        SELECT *
        FROM jobs
        {where}
        ORDER BY
            CASE WHEN deadline_date IS NULL THEN 1 ELSE 0 END,
            deadline_date ASC,
            source COLLATE NOCASE,
            title COLLATE NOCASE
        LIMIT 300
        """,
        params,
    ).fetchall()
    return [_row_dict(row, today) for row in rows]


def _row_dict(row: sqlite3.Row, today: date) -> dict[str, Any]:
    deadline = _parse_date(row["deadline_date"])
    posted = _parse_date(row["posted_date"])
    days_left = (deadline - today).days if deadline else None
    return {
        "job_opening_id": row["job_opening_id"],
        "title": row["title"],
        "department": row["department"],
        "location": row["location"],
        "posted_date": row["posted_date"] or "Unknown",
        "deadline_date": row["deadline_date"] or "Unknown",
        "apply_url": row["apply_url"],
        "source": row["source"],
        "first_seen_at": _pretty_dt(row["first_seen_at"]),
        "last_seen_at": _pretty_dt(row["last_seen_at"]),
        "days_left": days_left,
        "urgency": _urgency(days_left),
    }


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _pretty_dt(value: str | None) -> str:
    if not value:
        return "Unknown"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _urgency(days_left: int | None) -> str:
    if days_left is None:
        return "neutral"
    if days_left < 0:
        return "expired"
    if days_left <= 1:
        return "urgent"
    if days_left <= 7:
        return "soon"
    return "open"


def main() -> None:
    uvicorn.run("un_intern_monitor.web:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
