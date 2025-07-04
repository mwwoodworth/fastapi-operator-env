"""Convert chat messages into structured task prompts using Claude or Gemini."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from utils.ai_router import get_ai_model
from utils.ai_logging import log_prompt
from . import claude_prompt, gemini_prompt, multi_task

TASK_ID = "chat_to_prompt"
TASK_DESCRIPTION = "Convert a chat message into a JSON task list"
REQUIRED_FIELDS = ["message"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    message = context.get("message")
    if not message:
        return {"error": "missing_message"}

    limit = int(context.get("memory_scope", 5))
    mem_text = memory_store.load_recent(limit)

    model = context.get("model") or get_ai_model(task=TASK_ID)

    prompt = (
        "You are an AI assistant that converts user requests into JSON task lists. "
        f"User message: {message}\nRecent memory:\n{mem_text}\n"
        "Respond only with JSON like {\"tasks\": [{\"task\": ..., \"context\": {...}}]}"
    )

    ai_result = (
        claude_prompt.run({"prompt": prompt}) if model == "claude" else gemini_prompt.run({"prompt": prompt})
    )
    raw = ai_result.get("completion", "")
    executed_by = ai_result.get("executed_by", model)
    log_prompt(model, TASK_ID, prompt, raw)

    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse chat_to_prompt output: %s", exc)
        return {"error": "parse_failed", "raw": raw}

    if context.get("auto_run"):
        tasks = data.get("tasks") or []
        if tasks:
            run_result = multi_task.run({"tasks": tasks})
            data["run_result"] = run_result

    data["executed_by"] = executed_by
    return data
