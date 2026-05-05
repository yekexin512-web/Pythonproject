from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import load_settings
from .multi_scraper import fetch_all_internship_jobs, is_internship_text
from .notifier import build_daily_message, push_message
from .notion_sync import sync_daily_jobs_to_notion
from .storage import connect, jobs_deadline_on, upsert_jobs


def run_once(push: bool = True) -> None:
    settings = load_settings()
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)

    jobs = fetch_all_internship_jobs(settings.search_url, headless=settings.playwright_headless, today=now.date())
    with connect(settings.database_path) as connection:
        new_jobs = upsert_jobs(connection, jobs, now)
        deadline_date = (now + timedelta(days=settings.lookahead_days)).date()
        deadline_jobs = [
            job
            for job in jobs_deadline_on(connection, deadline_date)
            if job.source == "UN Careers" or is_internship_text(job.title)
        ]

    new_job_ids = {job.job_opening_id for job in new_jobs}
    today_jobs = [
        job
        for job in jobs
        if job.posted_date == now.date() or (job.posted_date is None and job.job_opening_id in new_job_ids)
    ]
    title, body = build_daily_message(today_jobs, deadline_jobs)
    sync_daily_jobs_to_notion(
        token=settings.notion_token,
        database_id=settings.notion_database_id,
        notion_version=settings.notion_version,
        today_jobs=today_jobs,
        deadline_jobs=deadline_jobs,
        run_date=now.date(),
    )
    if push:
        push_message(
            settings.push_channel,
            title,
            body,
            serverchan_sendkey=settings.serverchan_sendkey,
            wecom_webhook_url=settings.wecom_webhook_url,
        )
    else:
        print(body)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Monitor UN Careers internship openings.")
    parser.add_argument("--no-push", action="store_true", help="只抓取并输出摘要，不发送微信推送")
    args = parser.parse_args()
    run_once(push=not args.no_push)


if __name__ == "__main__":
    main()
