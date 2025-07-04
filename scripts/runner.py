"""Simple background runner to execute queued tasks."""

from __future__ import annotations

import asyncio
import logging

from codex import run_task
from codex.memory import memory_store

logger = logging.getLogger(__name__)
INTERVAL = 900  # 15 minutes


async def poll_and_run() -> None:
    while True:
        entries = memory_store.fetch_all()
        for entry in entries:
            if entry.get("auto_execute"):
                ctx = entry.get("context", {})
                try:
                    run_task(entry["task"], ctx)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Auto task failed: %s", exc)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(poll_and_run())
