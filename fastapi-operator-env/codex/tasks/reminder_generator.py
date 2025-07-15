from __future__ import annotations

"""Generate nightly reminders for unresolved tasks."""

from typing import Any, Dict, List

from codex.memory import agent_inbox
from . import claude_prompt

TASK_ID = "reminder_generator"
TASK_DESCRIPTION = "Suggest which tasks to defer or escalate"
REQUIRED_FIELDS: List[str] = []


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    items = agent_inbox.get_pending_tasks(20)
    if not items:
        return {"reminders": []}

    summaries = [i.get("summary", {}).get("summary") for i in items]
    prompt = (
        "Review the following pending tasks and propose which to defer, escalate, or close before tomorrow. "
        "Return a short JSON summary.\n" + "\n".join(summaries)
    )
    result = claude_prompt.run({"prompt": prompt})
    executed_by = result.get("executed_by", "claude")
    reminders = result.get("completion", "")
    return {"reminders": reminders, "executed_by": executed_by}
