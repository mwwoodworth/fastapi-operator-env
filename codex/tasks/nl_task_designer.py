"""Generate a multi-task plan from a natural language goal."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from utils.ai_router import get_ai_model
from utils.ai_logging import log_prompt
from . import claude_prompt, gemini_prompt, multi_task

TASK_ID = "nl_task_designer"
TASK_DESCRIPTION = "Design a task pipeline from a natural language goal"
REQUIRED_FIELDS = ["goal"]

logger = logging.getLogger(__name__)


def _load_recent(limit: int = 5) -> str:
    records = memory_store.fetch_all(limit=limit)
    return "\n\n".join(str(r.get("output") or r) for r in records)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    goal = context.get("goal")
    if not goal:
        return {"error": "missing_goal"}

    prefer_model = context.get("model")
    model = prefer_model or get_ai_model(task=TASK_ID)

    mem_text = _load_recent(5)
    prompt = (
        "You are an AI assistant that composes JSON task pipelines for the BrainOps Operator. "
        f"Goal: {goal}. Recent memory:\n{mem_text}\n"
        "Respond only with a JSON object containing a 'tasks' list."
    )

    ai_result = (
        claude_prompt.run({"prompt": prompt}) if model == "claude" else gemini_prompt.run({"prompt": prompt})
    )
    raw = ai_result.get("completion", "")
    log_prompt(model, TASK_ID, prompt, raw)

    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse NL designer output: %s", exc)
        return {"error": "parse_failed", "raw": raw}

    tasks = data.get("tasks") or []
    results = {}
    if tasks:
        results = multi_task.run({"tasks": tasks})

    return {"generated": tasks, "result": results}
