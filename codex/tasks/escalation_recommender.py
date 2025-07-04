"""Recommend escalations for stale inbox tasks."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from codex.memory import agent_inbox

TASK_ID = "escalation_recommender"
TASK_DESCRIPTION = "Suggest follow-ups for idle tasks"
REQUIRED_FIELDS: List[str] = []

_IDLE_LIMIT = timedelta(days=2)


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tasks = agent_inbox.get_pending_tasks(50)
    now = datetime.utcnow()
    idle = []
    for t in tasks:
        ts = t.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if now - dt > _IDLE_LIMIT:
            idle.append(t)
    if len(idle) < 3:
        return {"escalation": []}
    suggestions = [f"Follow up on {i.get('task_id')}" for i in idle]
    return {"escalation": suggestions}
