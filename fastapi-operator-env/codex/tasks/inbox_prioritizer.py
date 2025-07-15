from __future__ import annotations

"""Agent that scores inbox items for urgency and blocking status."""

from typing import Any, Dict, List

from codex.memory import agent_inbox
from . import claude_prompt

TASK_ID = "inbox_prioritizer"
TASK_DESCRIPTION = "Score inbox tasks by urgency"
REQUIRED_FIELDS: List[str] = []


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    items = agent_inbox.get_pending_tasks(20)
    if not items:
        return {"prioritized": []}

    desc = []
    for item in items:
        summary = item.get("summary", {}).get("summary") or str(item.get("context"))
        desc.append(f"- id:{item['task_id']} {summary}")
    prompt = (
        "Rate the following tasks from 0-10 urgency and indicate if they block other work. "
        "Return JSON list with fields 'task_id', 'urgency', 'blocking'.\n" + "\n".join(desc)
    )
    result = claude_prompt.run({"prompt": prompt})
    data = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")
    try:
        scores = eval(data, {"__builtins__": {}}) if isinstance(data, str) else data
    except Exception:  # noqa: BLE001
        scores = data
    return {"prioritized": scores, "executed_by": executed_by}
