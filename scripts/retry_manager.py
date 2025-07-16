"""Retry failed tasks based on log history."""

from __future__ import annotations

import json
import os
from pathlib import Path

from codex import run_task
from codex.memory import memory_store

LOG_FILE = Path("logs/task_log.json")
RETRY_LIMIT = int(os.getenv("RETRY_FAILURE_LIMIT", "3"))


def process_failures() -> None:
    if not LOG_FILE.exists():
        return
    try:
        history = json.loads(LOG_FILE.read_text())
    except Exception:  # noqa: BLE001
        return
    for item in history:
        result = item.get("result")
        if isinstance(result, dict) and result.get("error"):
            retry = int(item.get("retry", 0))
            if retry >= RETRY_LIMIT:
                continue
            ctx = item.get("context") or {}
            task = item.get("task")
            ctx["retry"] = retry + 1
            res = run_task(task, ctx)
            memory_store.save_memory(
                {
                    "task": "retry_manager",
                    "input": item,
                    "output": res,
                    "tags": ["retry"],
                }
            )


if __name__ == "__main__":
    process_failures()
