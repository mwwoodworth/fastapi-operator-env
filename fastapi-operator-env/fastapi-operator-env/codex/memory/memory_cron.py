"""Simple cron hooks for memory synchronization jobs."""

from __future__ import annotations

import schedule
import time
from typing import Callable

from codex.ai.claude_sync import sync_claude_logs


def start_scheduler(run_forever: bool = True) -> None:
    """Start scheduled sync jobs."""
    schedule.every(30).minutes.do(sync_claude_logs)
    if not run_forever:
        schedule.run_all()
        return
    while True:  # pragma: no cover - runtime loop
        schedule.run_pending()
        time.sleep(1)
