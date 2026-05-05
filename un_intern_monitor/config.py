from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_URL = (
    "https://careers.un.org/jobopening?language=en&"
    "data=%257B%2522jle%2522:%255B%255D,%2522jc%2522:%255B%2522INT%2522%255D%257D"
)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    search_url: str
    timezone: str
    lookahead_days: int
    playwright_headless: bool
    push_channel: str
    serverchan_sendkey: str | None
    wecom_webhook_url: str | None
    notion_token: str | None
    notion_database_id: str | None
    notion_version: str


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "un_internships.sqlite")),
        search_url=os.getenv("UN_CAREERS_SEARCH_URL", DEFAULT_SEARCH_URL),
        timezone=os.getenv("MONITOR_TIMEZONE", "Asia/Shanghai"),
        lookahead_days=int(os.getenv("DEADLINE_LOOKAHEAD_DAYS", "1")),
        playwright_headless=_bool_env("PLAYWRIGHT_HEADLESS", True),
        push_channel=os.getenv("PUSH_CHANNEL", "dry-run").strip().lower(),
        serverchan_sendkey=os.getenv("SERVERCHAN_SENDKEY"),
        wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL"),
        notion_token=os.getenv("NOTION_TOKEN"),
        notion_database_id=os.getenv("NOTION_DATABASE_ID"),
        notion_version=os.getenv("NOTION_VERSION", "2022-06-28"),
    )
