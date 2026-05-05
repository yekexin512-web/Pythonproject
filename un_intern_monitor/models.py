from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Job:
    job_opening_id: str
    title: str
    department: str
    location: str
    posted_date: date | None
    deadline_date: date | None
    apply_url: str
    category: str = "Internship"
    source: str = "UN Careers"
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
