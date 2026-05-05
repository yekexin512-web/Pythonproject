from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .date_utils import parse_date
from .models import Job
from .scraper import fetch_internship_jobs as fetch_un_careers_jobs


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    "Content-Type": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_all_internship_jobs(un_careers_url: str, *, headless: bool, today: date) -> list[Job]:
    jobs: list[Job] = []
    fetchers = [
        lambda: fetch_un_careers_jobs(un_careers_url, headless=headless),
        lambda: fetch_unhcr_jobs(today),
        lambda: fetch_undp_jobs(),
        lambda: fetch_unido_jobs(),
        lambda: fetch_wfp_jobs(today),
        lambda: fetch_unicef_jobs(),
    ]
    for fetcher in fetchers:
        try:
            jobs.extend(fetcher())
        except Exception as exc:
            print(f"Warning: skipped one source: {exc}")
    return _dedupe_jobs(jobs)


def fetch_unhcr_jobs(today: date) -> list[Job]:
    return _fetch_workday_jobs(
        source="UNHCR",
        api_base="https://unhcr.wd3.myworkdayjobs.com/wday/cxs/unhcr/External",
        public_base="https://unhcr.wd3.myworkdayjobs.com/External",
        payload={"limit": 20, "offset": 0, "searchText": "intern", "appliedFacets": {}},
        today=today,
    )


def fetch_wfp_jobs(today: date) -> list[Job]:
    return _fetch_workday_jobs(
        source="WFP",
        api_base="https://wd3.myworkdaysite.com/wday/cxs/wfp/job_openings",
        public_base="https://wd3.myworkdaysite.com/recruiting/wfp/job_openings",
        payload={
            "limit": 20,
            "offset": 0,
            "searchText": "",
            "appliedFacets": {"workerSubType": ["59387fe40123101e856f1834e09b0002"]},
        },
        today=today,
    )


def _fetch_workday_jobs(source: str, api_base: str, public_base: str, payload: dict, today: date) -> list[Job]:
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": HEADERS["Accept-Language"],
        "Origin": _origin(api_base),
        "Referer": _origin(api_base),
    }
    response = requests.post(f"{api_base}/jobs", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    jobs: list[Job] = []
    for item in response.json().get("jobPostings", []):
        title = item.get("title") or ""
        if not is_internship_text(title) and source != "WFP":
            continue
        external_path = item.get("externalPath") or ""
        raw_id = _first_bullet_id(item.get("bulletFields", [])) or _id_from_path(external_path)
        if not raw_id:
            continue
        detail = _workday_detail(api_base, external_path)
        jobs.append(
            Job(
                job_opening_id=f"{source}-{raw_id}",
                title=title,
                department=source,
                location=item.get("locationsText") or "",
                posted_date=_parse_workday_posted(item.get("postedOn"), today),
                deadline_date=_deadline_from_html(detail),
                apply_url=urljoin(public_base, external_path),
                source=source,
            )
        )
    return jobs


def _workday_detail(api_base: str, external_path: str) -> str:
    if not external_path:
        return ""
    response = requests.get(f"{api_base}{external_path}", headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json().get("jobPostingInfo", {}).get("jobDescription", "")


def fetch_unido_jobs() -> list[Job]:
    url = "https://careers.unido.org/search/?q=&q2=&alertId=&locationsearch=&title=&location=&department=&facility=intern&shifttype=#searchresults"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    jobs: list[Job] = []
    for row in soup.select("tr.data-row"):
        link = row.find("a", href=True)
        if not link:
            continue
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        href = urljoin(url, str(link["href"]))
        raw_id = _id_from_path(href)
        jobs.append(
            Job(
                job_opening_id=f"UNIDO-{raw_id}",
                title=link.get_text(" ", strip=True),
                department="UNIDO",
                location=_pick_cell(cells, 1),
                posted_date=None,
                deadline_date=parse_date(cells[-1] if cells else None),
                apply_url=href,
                source="UNIDO",
            )
        )
    return jobs


def fetch_unicef_jobs() -> list[Job]:
    url = "https://jobs.unicef.org/en-us/filter/?search-keyword=&pay-scale=internship"
    response = requests.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    jobs_by_id: dict[str, Job] = {}
    for link in soup.find_all("a", href=re.compile(r"/en-us/job/\d+")):
        title = link.get_text(" ", strip=True)
        href = urljoin(url, str(link["href"]))
        raw_id = _id_from_path(href)
        if not raw_id or f"UNICEF-{raw_id}" in jobs_by_id:
            continue
        container = link.find_parent(class_="row-content") or link.find_parent(class_="row-content--text") or link.parent
        text = container.get_text("\n", strip=True) if container else title
        jobs_by_id[f"UNICEF-{raw_id}"] = Job(
            job_opening_id=f"UNICEF-{raw_id}",
            title=title,
            department="UNICEF",
            location=_field_after_label(text, "Location"),
            posted_date=None,
            deadline_date=parse_date(_field_after_label(text, "Deadline")),
            apply_url=href,
            source="UNICEF",
        )
    return list(jobs_by_id.values())


def fetch_undp_jobs() -> list[Job]:
    url = "https://jobs.undp.org/cj_view_jobs.cfm"
    response = requests.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    jobs_by_id: dict[str, Job] = {}
    for link in soup.find_all("a", href=re.compile(r"/requisitions/job/\d+")):
        text = re.sub(r"\s+", " ", link.get_text(" ", strip=True))
        if not is_internship_text(text):
            continue
        raw_id = _id_from_path(str(link["href"]))
        if not raw_id:
            continue
        title = _between(text, "Job Title", "Post level") or text
        jobs_by_id[f"UNDP-{raw_id}"] = Job(
            job_opening_id=f"UNDP-{raw_id}",
            title=title.strip(),
            department=_between(text, "Agency", "Location") or "UNDP",
            location=_after(text, "Location"),
            posted_date=None,
            deadline_date=parse_date(_between(text, "Apply by", "Agency")),
            apply_url=str(link["href"]),
            source="UNDP",
        )
    return list(jobs_by_id.values())


def _dedupe_jobs(jobs: list[Job]) -> list[Job]:
    jobs_by_id = {job.job_opening_id: job for job in jobs}
    return sorted(jobs_by_id.values(), key=lambda job: (job.source, job.deadline_date or date.max, job.title))


def is_internship_text(text: str) -> bool:
    return bool(re.search(r"\b(intern|interns|internship|internships)\b", text, flags=re.IGNORECASE))


def _parse_workday_posted(value: str | None, today: date) -> date | None:
    if not value:
        return None
    text = value.strip().lower()
    if text == "posted today":
        return today
    if text == "posted yesterday":
        return today - timedelta(days=1)
    match = re.search(r"posted\s+(\d+)\s+days?\s+ago", text)
    if match:
        return today - timedelta(days=int(match.group(1)))
    return parse_date(value)


def _deadline_from_html(html: str) -> date | None:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    match = re.search(
        r"(?:Deadline for Applications|DEADLINE FOR APPLICATIONS|Deadline)\s*\n?\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}(?:-\d{1,2}:\d{2}[^\\n]*)?)",
        text,
        flags=re.IGNORECASE,
    )
    return parse_date(match.group(1)) if match else parse_date(text)


def _field_after_label(text: str, label: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if line.rstrip(":").lower() == label.lower():
            return lines[index + 1]
    return ""


def _first_bullet_id(values: list[str]) -> str:
    for value in values:
        if re.search(r"[A-Za-z]*\d{4,}", str(value)):
            return str(value)
    return ""


def _id_from_path(value: str) -> str:
    matches = re.findall(r"([A-Za-z]*\d{4,})", value)
    return matches[-1] if matches else ""


def _pick_cell(cells: list[str], index: int) -> str:
    return cells[index] if len(cells) > index else ""


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _between(text: str, start: str, end: str) -> str:
    match = re.search(rf"{re.escape(start)}\s*(.*?)\s*{re.escape(end)}", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _after(text: str, start: str) -> str:
    match = re.search(rf"{re.escape(start)}\s*(.*)$", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""
