from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import BASE_DIR
from .main import run_once
from .static_site import build_static_site


LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "run_monitor.log"


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    _log(f"==== {datetime.now():%Y-%m-%d %H:%M:%S} scheduled start ====")
    try:
        run_once(push=True)
        output = build_static_site()
        _log(f"Built {output}")
        _commit_and_push()
    except Exception as exc:
        exit_code = 1
        _log(f"ERROR: {type(exc).__name__}: {exc}")
    _log(f"==== {datetime.now():%Y-%m-%d %H:%M:%S} scheduled exit {exit_code} ====")
    raise SystemExit(exit_code)


def _commit_and_push() -> None:
    _run(["git", "add", "docs/index.html", "docs/dashboard.css"])
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
    if diff.returncode == 0:
        _log("No GitHub Pages changes to commit.")
        return

    message = f"Update dashboard {datetime.now():%Y-%m-%d}"
    _run(["git", "commit", "-m", message])
    _run(["git", "push", "origin", "main"])


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command,
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout.strip():
        _log(result.stdout.strip())
    if result.stderr.strip():
        _log(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")


def _log(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


if __name__ == "__main__":
    main()
