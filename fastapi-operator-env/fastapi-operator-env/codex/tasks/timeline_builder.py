"""Build a rolling 7-day task timeline."""

from __future__ import annotations

from typing import Any, Dict, List

from codex.memory import agent_inbox

TASK_ID = "timeline_builder"
TASK_DESCRIPTION = "Create timeline view of upcoming tasks"
REQUIRED_FIELDS: List[str] = []


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    pending = agent_inbox.get_pending_tasks(20)
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    schedule: Dict[str, List[str]] = {day: [] for day in days}
    for idx, item in enumerate(pending):
        day = days[idx % 7]
        schedule[day].append(item.get("task_id"))
    return {"timeline": schedule}
