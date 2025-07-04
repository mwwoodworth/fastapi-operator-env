"""Manage recurring tasks and queue due ones."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from codex.memory import agent_inbox

TASK_ID = "recurring_task_engine"
TASK_DESCRIPTION = "Check and enqueue recurring tasks"
REQUIRED_FIELDS: List[str] = []

_FILE = Path("recurring_tasks.json")


def _load() -> List[Dict[str, Any]]:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def _save(data: List[Dict[str, Any]]) -> None:
    _FILE.write_text(json.dumps(data, indent=2))


def get_recurring_tasks() -> List[Dict[str, Any]]:
    """Return all recurring task definitions."""
    return _load()


def add_recurring_task(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new recurring task entry."""
    tasks = _load()
    entry.setdefault("enabled", True)
    tasks.append(entry)
    _save(tasks)
    return entry


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Check for due recurring tasks and add them to inbox."""
    tasks = _load()
    now = datetime.utcnow()
    triggered: List[str] = []
    for t in tasks:
        if not t.get("enabled", True):
            continue
        freq = t.get("frequency")
        try:
            last_run = (
                datetime.fromisoformat(t["last_run"]) if t.get("last_run") else None
            )
        except Exception:
            last_run = None
        should_run = False
        if freq == "weekly":
            if now.strftime("%A") == t.get("day") and now.strftime("%H:%M") == t.get(
                "time"
            ):
                if not last_run or last_run.date() != now.date():
                    should_run = True
        elif freq == "daily":
            if now.strftime("%H:%M") == t.get("time"):
                if not last_run or last_run.date() != now.date():
                    should_run = True
        if should_run:
            entry = agent_inbox.add_to_inbox(
                t.get("task"), t.get("context", {}), "recurring"
            )
            t["last_run"] = now.isoformat()
            triggered.append(entry.get("task_id"))
    if triggered:
        _save(tasks)
    return {"triggered": triggered}
