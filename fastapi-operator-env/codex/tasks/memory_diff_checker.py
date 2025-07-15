"""Check for discrepancies between Claude and Gemini memory entries for a task."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from codex.memory import memory_store

TASK_ID = "memory_diff_checker"
TASK_DESCRIPTION = "Detect differences between Claude and Gemini memory logs"
REQUIRED_FIELDS = ["task_id"]

logger = logging.getLogger(__name__)


def _find_record(task: str, model: str) -> Optional[Dict[str, Any]]:
    for entry in reversed(memory_store.fetch_all(limit=100)):
        meta = entry.get("metadata") or {}
        if entry.get("task") == task and meta.get("model") == model:
            return entry
    return None


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    task_id = context.get("task_id")
    if not task_id:
        return {"error": "missing_task_id"}

    claude_entry = _find_record(task_id, "claude")
    gemini_entry = _find_record(task_id, "gemini")

    differ = False
    if claude_entry and gemini_entry:
        differ = claude_entry.get("output") != gemini_entry.get("output")

    result = {
        "claude": bool(claude_entry),
        "gemini": bool(gemini_entry),
        "discrepancy": differ,
    }
    if differ:
        result["claude_output"] = claude_entry.get("output") if claude_entry else None
        result["gemini_output"] = gemini_entry.get("output") if gemini_entry else None
    return result
