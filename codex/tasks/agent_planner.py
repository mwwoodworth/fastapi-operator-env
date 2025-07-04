"""Generate a short task plan with Claude or Gemini and execute it."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt, gemini_prompt, multi_task

TASK_ID = "agent_planner"
TASK_DESCRIPTION = "Generate a task plan and run it"
REQUIRED_FIELDS = ["goal"]

logger = logging.getLogger(__name__)


def _load_recent(limit: int = 5) -> str:
    records = memory_store.fetch_all(limit=limit)
    return "\n\n".join(str(r.get("output") or r) for r in records)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    goal = context.get("goal")
    if not goal:
        return {"error": "missing_goal"}

    max_steps = int(context.get("max_steps", 3))
    model = context.get("model", "claude")

    mem_text = _load_recent(5)

    prompt = (
        "You are an AI assistant that creates JSON task plans. "
        f"Goal: {goal}. Use at most {max_steps} steps. "
        f"Recent memory:\n{mem_text}\n"
        "Respond with a JSON object: {\"tasks\": [ ... ]}."
    )

    if model == "gemini":
        ai_result = gemini_prompt.run({"prompt": prompt})
    else:
        ai_result = claude_prompt.run({"prompt": prompt})
    raw = ai_result.get("completion", "")

    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse agent output: %s", exc)
        return {"error": "parse_failed", "raw": raw}

    tasks = data.get("tasks") or []
    results = {}
    if tasks:
        results = multi_task.run({"tasks": tasks})

    return {"generated": tasks, "result": results}
