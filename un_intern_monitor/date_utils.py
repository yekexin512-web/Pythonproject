from __future__ import annotations

import re
from datetime import date, datetime


DATE_PATTERNS = (
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%b-%d-%y",
    "%b-%d-%Y",
)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    text = re.sub(r"(\d{4})-\d{1,2}:\d{2}.*$", r"\1", text)
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text, flags=re.IGNORECASE)
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    match = re.search(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|[A-Za-z]{3,9}-\d{1,2}-\d{2,4})",
        text,
    )
    if match:
        return parse_date(match.group(1))
    return None


def parse_job_opening_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(?:Job\s*Opening\s*ID|JobOpeningId|ID)\D*(\d{4,})", value, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{4,})\b", value)
    return match.group(1) if match else None
