from __future__ import annotations

from datetime import date

import requests

from .models import Job


NOTION_API_BASE = "https://api.notion.com/v1"


def sync_daily_jobs_to_notion(
    *,
    token: str | None,
    database_id: str | None,
    notion_version: str,
    today_jobs: list[Job],
    deadline_jobs: list[Job],
    run_date: date,
) -> None:
    if not token or not database_id:
        return

    client = _NotionClient(token, database_id, notion_version)
    for job in today_jobs:
        client.create_job_if_missing(job, "今日发布", run_date)
    for job in deadline_jobs:
        client.create_job_if_missing(job, "明天截止", run_date)


class _NotionClient:
    def __init__(self, token: str, database_id: str, notion_version: str) -> None:
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json",
        }
        self.title_property = "Name"
        self._ensure_schema()

    def create_job_if_missing(self, job: Job, alert_type: str, run_date: date) -> None:
        if self._job_exists(job.job_opening_id):
            return

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                self.title_property: {"title": [{"text": {"content": job.title}}]},
                "Job ID": {"rich_text": [{"text": {"content": job.job_opening_id}}]},
                "Alert Type": {"select": {"name": alert_type}},
                "Department": {"rich_text": [{"text": {"content": job.department or ""}}]},
                "Location": {"rich_text": [{"text": {"content": job.location or ""}}]},
                "Posted Date": _date_property(job.posted_date),
                "Deadline Date": _date_property(job.deadline_date),
                "URL": {"url": job.apply_url},
                "Sync Date": _date_property(run_date),
            },
        }
        response = requests.post(
            f"{NOTION_API_BASE}/pages",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def _ensure_schema(self) -> None:
        response = requests.get(
            f"{NOTION_API_BASE}/databases/{self.database_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        properties = response.json().get("properties", {})
        for name, schema in properties.items():
            if schema.get("type") == "title":
                self.title_property = name
                break

        desired = {
            "Job ID": {"rich_text": {}},
            "Alert Type": {
                "select": {
                    "options": [
                        {"name": "今日发布", "color": "green"},
                        {"name": "明天截止", "color": "red"},
                    ]
                }
            },
            "Department": {"rich_text": {}},
            "Location": {"rich_text": {}},
            "Posted Date": {"date": {}},
            "Deadline Date": {"date": {}},
            "URL": {"url": {}},
            "Sync Date": {"date": {}},
        }
        missing = {name: schema for name, schema in desired.items() if name not in properties}
        if not missing:
            return

        response = requests.patch(
            f"{NOTION_API_BASE}/databases/{self.database_id}",
            headers=self.headers,
            json={"properties": missing},
            timeout=30,
        )
        response.raise_for_status()

    def _job_exists(self, job_id: str) -> bool:
        payload = {
            "filter": {"property": "Job ID", "rich_text": {"equals": job_id}},
            "page_size": 1,
        }
        response = requests.post(
            f"{NOTION_API_BASE}/databases/{self.database_id}/query",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return bool(response.json().get("results"))


def _date_property(value: date | None) -> dict:
    if value is None:
        return {"date": None}
    return {"date": {"start": value.isoformat()}}
