"""Weekly review to re-rank inbox tasks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from codex.memory import agent_inbox, memory_store
from . import claude_prompt

TASK_ID = "weekly_priority_review"
TASK_DESCRIPTION = "Re-rank task priorities each week"
REQUIRED_FIELDS: List[str] = []

_LAST_FILE = Path("logs/last_priority_review.txt")


def get_last_review_time() -> str | None:
    if _LAST_FILE.exists():
        try:
            return _LAST_FILE.read_text().strip()
        except Exception:  # noqa: BLE001
            return None
    return None


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    items = agent_inbox.get_pending_tasks(50)
    summaries = [i.get("summary", {}).get("summary", "") for i in items]
    prompt = (
        "Review pending tasks and label each high_priority, defer, or close. "
        "Suggest 3 new tasks for next week in JSON.\n" + "\n".join(summaries)
    )
    ai = claude_prompt.run({"prompt": prompt})
    _LAST_FILE.parent.mkdir(exist_ok=True)
    _LAST_FILE.write_text(datetime.utcnow().isoformat())
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": summaries,
            "output": ai.get("completion", ""),
            "tags": ["weekly", "priority"],
        }
    )
    return {"review": ai.get("completion", ""), "executed_by": ai.get("executed_by", "claude")}
