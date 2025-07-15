from __future__ import annotations

"""Daily planner agent that considers inbox tasks and today's calendar."""

import os
from typing import Any, Dict, List

from codex.memory import agent_inbox
from codex.integrations import push_notify
from codex.tasks import claude_prompt

try:
    from mock import calendar as mock_calendar
except Exception:  # noqa: BLE001
    mock_calendar = None

TASK_ID = "claude_calendar_planner"
TASK_DESCRIPTION = "Suggest top actions for the day based on calendar"
REQUIRED_FIELDS: List[str] = []


def _load_calendar() -> List[Dict[str, Any]]:
    if mock_calendar and hasattr(mock_calendar, "get_today_events"):
        try:
            return mock_calendar.get_today_events()
        except Exception:  # noqa: BLE001
            return []
    return []


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    pending = agent_inbox.get_pending_tasks(20)
    events = _load_calendar()
    prompt = (
        "You are a planning assistant. Based on the following pending tasks and "
        "today's calendar events, suggest the top 3 next actions with reasons.\n"
        f"Pending: {pending}\nCalendar: {events}\nReturn JSON with key 'actions'."
    )
    result = claude_prompt.run({"prompt": prompt})
    plan = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")

    if os.getenv("PUSH_WEBHOOK_URL"):
        push_notify.send_push("Daily plan", "Check your daily recommendations", url="/agent/inbox")

    return {"plan": plan, "executed_by": executed_by}
