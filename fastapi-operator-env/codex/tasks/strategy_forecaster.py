"""Generate a 7-day strategic task forecast."""

from __future__ import annotations

from typing import Any, Dict, List

from codex.memory import agent_inbox, memory_store
from utils.route_planner import assign_routes

TASK_ID = "strategy_forecaster"
TASK_DESCRIPTION = "Create a 7-day forecast schedule"
REQUIRED_FIELDS = ["goal"]


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    goal = context.get("goal", "")
    model = context.get("model", "claude")
    _ = context.get("inputs", [])

    pending = agent_inbox.get_pending_tasks(7)
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    schedule: Dict[str, List[str]] = {}
    for i, day in enumerate(days):
        item = pending[i] if i < len(pending) else None
        schedule[day] = [item.get("task_id")] if item else []

    tasks_meta = [
        {"task": t.get("task_id"), "urgency": "medium"} for t in pending
    ]
    route_map = assign_routes(tasks_meta)
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": context,
            "output": {"schedule_by_day": schedule, "route_map": route_map},
            "tags": ["forecast"],
        },
        origin={"model": model},
    )
    return {
        "schedule_by_day": schedule,
        "tasks": tasks_meta,
        "route_map": route_map,
        "executed_by": model,
    }
