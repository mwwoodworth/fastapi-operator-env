"""Generate and run tasks using Claude based on recent memory."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt, multi_task

TASK_ID = "claude_agent"
TASK_DESCRIPTION = "Generate a workflow with Claude and execute it"
REQUIRED_FIELDS = ["goal"]

logger = logging.getLogger(__name__)


def _load_memory(scope: str | int) -> str:
    if isinstance(scope, str) and scope.startswith("last_"):
        try:
            num = int(scope.split("_")[1])
        except Exception:  # noqa: BLE001
            num = 3
    else:
        try:
            num = int(scope)
        except Exception:  # noqa: BLE001
            num = 3
    records = memory_store.fetch_all(limit=num)
    return "\n\n".join(str(r.get("output") or r) for r in records)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    goal = context.get("goal")
    if not goal:
        return {"error": "missing_goal"}
    memory_scope = context.get("memory_scope", "last_3")
    mem_text = _load_memory(memory_scope)

    prompt = (
        "You are an AI assistant that generates JSON task lists. "
        "Return only valid JSON. Goal: "
        f"{goal}. Recent memory:\n{mem_text}\n"
        "Respond with a JSON object containing a 'tasks' list."
    )
    result = claude_prompt.run({"prompt": prompt})
    raw = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")
    try:
        task_data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse Claude output: %s", exc)
        return {"error": "parse_failed", "raw": raw}

    tasks = task_data.get("tasks") or []
    multi_result = {}
    if tasks:
        multi_result = multi_task.run({"tasks": tasks, "task_generated_by": TASK_ID})
    return {"generated": tasks, "result": multi_result, "executed_by": executed_by}
