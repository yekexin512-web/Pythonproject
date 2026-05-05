from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .config import BASE_DIR
from .web import _jobs, _last_updated, _sources, _stats
from .config import load_settings
from .storage import connect


DOCS_DIR = BASE_DIR / "docs"


def build_static_site() -> Path:
    settings = load_settings()
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(settings.timezone)).date()
    tomorrow = today + timedelta(days=settings.lookahead_days)
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

    with connect(settings.database_path) as connection:
        context = {
            "request": _fake_request(),
            "jobs": _jobs(connection, q="", source="all", status="active", today=today, tomorrow=tomorrow),
            "stats": _stats(connection, today, tomorrow),
            "sources": _sources(connection),
            "filters": {"q": "", "source": "all", "status": "active"},
            "today": today,
            "tomorrow": tomorrow,
            "last_updated": _last_updated(connection),
            "static_mode": True,
        }

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    html = templates.get_template("dashboard.html").render(context)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(Path(__file__).resolve().parent / "static" / "dashboard.css", DOCS_DIR / "dashboard.css")
    return DOCS_DIR / "index.html"


def _fake_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("localhost", 80),
        "scheme": "https",
        "client": ("127.0.0.1", 0),
    }
    return Request(scope)


def main() -> None:
    output = build_static_site()
    print(f"Built {output}")


if __name__ == "__main__":
    main()
