"""Synchronize recent memory entries between Claude and Gemini."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from codex.memory import memory_store
from . import claude_prompt, gemini_prompt

TASK_ID = "memory_sync_agent"
TASK_DESCRIPTION = "Sync recent Claude and Gemini summaries"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def _collect(task_name: str, limit: int) -> List[Dict[str, Any]]:
    records = memory_store.fetch_all(limit=50)
    selected = [r for r in records if r.get("task") == task_name]
    return selected[-limit:]


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    if os.getenv("MEMORY_SYNC_AGENT") != "true":
        return {"error": "disabled"}

    claude_logs = _collect("claude_memory_agent", 5)
    gem_opt_logs = _collect("gemini_optimize_taskflow", 5)

    claude_text = "\n".join(str(r.get("output") or r) for r in claude_logs)
    gem_text = "\n".join(str(r.get("output") or r) for r in gem_opt_logs)

    prompt = (
        "Compare the following Claude summaries and Gemini optimizations and "
        "summarize any differences or confirmations in brief:\n"
        f"Claude summaries:\n{claude_text}\nGemini optimizations:\n{gem_text}"
    )

    ai_result = claude_prompt.run({"prompt": prompt})
    summary = ai_result.get("completion", "")
    executed_by = ai_result.get("executed_by", "claude")

    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": {"claude": claude_text, "gemini": gem_text},
            "output": summary,
            "metadata": {"synced_by": "gemini", "synced_from": "claude"},
            "tags": ["sync"],
        },
        origin={"model": executed_by},
    )

    return {"summary": summary, "executed_by": executed_by}
