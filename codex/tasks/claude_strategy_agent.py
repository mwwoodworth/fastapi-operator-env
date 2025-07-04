"""Weekly strategy agent that proposes goals for the next week."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from codex.memory import memory_store

TASK_ID = "claude_strategy_agent"
TASK_DESCRIPTION = "Review memory and suggest weekly strategy goals"
REQUIRED_FIELDS: List[str] = []


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    now = datetime.utcnow()
    records = memory_store.fetch_all(limit=50)
    recent = []
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if (now - dt).days <= 7:
            recent.append(r)
    goals = [f"Goal {i}" for i in range(1, 4)]
    tasks = [
        {"task": f"task_{i}", "context": {}} for i in range(1, 4)
    ]
    output = {"goals": goals, "recommended_tasks": tasks}
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": recent,
            "output": output,
            "tags": ["weekly-strategy"],
        }
    )
    return output
