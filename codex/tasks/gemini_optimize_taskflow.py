"""Optimize task workflow using Gemini."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import gemini_prompt

TASK_ID = "gemini_optimize_taskflow"
TASK_DESCRIPTION = "Propose optimized task flows based on history"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def _resolve_history(value: str | None, session_id: str | None = None) -> str:
    if value:
        return value
    return memory_store.load_recent(5, session_id)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    history = _resolve_history(context.get("history"), context.get("session_id"))
    prompt = (
        "Analyze the following task history and propose an optimized JSON workflo"
        "w. Respond only with JSON.\n"
        f"{history}"
    )
    result = gemini_prompt.run({"prompt": prompt})
    raw = result.get("completion", "")
    executed_by = result.get("executed_by", "gemini")
    try:
        optimized = json.loads(raw)
    except Exception:
        logger.error("Failed to parse optimization output")
        optimized = None
    return {"optimized": optimized, "raw": raw, "executed_by": executed_by}
