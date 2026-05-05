from __future__ import annotations

import requests

from .models import Job


def build_daily_message(new_jobs: list[Job], deadline_jobs: list[Job]) -> tuple[str, str]:
    title = f"UN 实习岗位提醒：今日发布 {len(new_jobs)} 个，明天截止 {len(deadline_jobs)} 个"
    lines = [f"# {title}", ""]
    lines.append("## A. 今日发布岗位")
    lines.extend(_format_jobs(new_jobs))
    lines.append("")
    lines.append("## B. 明天截止岗位")
    lines.extend(_format_jobs(deadline_jobs))
    return title, "\n".join(lines)


def push_message(
    channel: str,
    title: str,
    body: str,
    *,
    serverchan_sendkey: str | None,
    wecom_webhook_url: str | None,
) -> None:
    if channel == "dry-run":
        print(body)
        return
    if channel == "serverchan":
        if not serverchan_sendkey:
            raise ValueError("PUSH_CHANNEL=serverchan 时必须设置 SERVERCHAN_SENDKEY")
        response = requests.post(
            f"https://sctapi.ftqq.com/{serverchan_sendkey}.send",
            data={"title": title, "desp": body},
            timeout=30,
        )
        response.raise_for_status()
        return
    if channel == "wecom":
        if not wecom_webhook_url:
            raise ValueError("PUSH_CHANNEL=wecom 时必须设置 WECOM_WEBHOOK_URL")
        response = requests.post(
            wecom_webhook_url,
            json={"msgtype": "markdown", "markdown": {"content": body}},
            timeout=30,
        )
        response.raise_for_status()
        return
    raise ValueError(f"不支持的 PUSH_CHANNEL: {channel}")


def _format_jobs(jobs: list[Job]) -> list[str]:
    if not jobs:
        return ["- 无"]

    lines: list[str] = []
    for index, job in enumerate(jobs, start=1):
        posted = job.posted_date.isoformat() if job.posted_date else "未知"
        deadline = job.deadline_date.isoformat() if job.deadline_date else "未知"
        department = job.department or "部门未知"
        location = job.location or "地点未知"
        lines.append(f"{index}. **{job.title}**")
        lines.append(f"   - 来源：{job.source}")
        lines.append(f"   - Job ID：{job.job_opening_id}")
        lines.append(f"   - 部门：{department}")
        lines.append(f"   - 地点：{location}")
        lines.append(f"   - 发布日期：{posted}")
        lines.append(f"   - 截止日期：{deadline}")
        lines.append(f"   - 链接：{job.apply_url}")
    return lines
