"""Summarize recent memory logs tagged as summary candidates using Claude."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt, tana_create

TASK_ID = "claude_memory_agent"
TASK_DESCRIPTION = "Summarize memory logs with Claude"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)

SUMMARY_TAG = os.getenv("SUMMARY_TAG", "summary_candidate")


def _collect(limit: int) -> str:
    records = memory_store.fetch_all(limit=50)
    selected = [r for r in records if SUMMARY_TAG in (r.get("tags") or [])]
    selected = selected[-limit:]
    return "\n\n".join(str(r.get("output") or r) for r in selected)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(context.get("limit", 5))
    text = _collect(limit)
    if not text:
        return {"error": "no_memory"}

    summary_type = context.get("summary_type", "brief")
    prompt = (
        f"Provide a {summary_type} summary of the following logs:\n{text}"
    )
    result = claude_prompt.run({"prompt": prompt})
    summary = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": text,
            "output": summary,
            "tags": ["summary"],
            "metadata": {"summary_of": SUMMARY_TAG},
        },
        origin={"model": executed_by},
    )
    try:
        tana_create.run({"content": summary, "metadata": {"tags": ["summary"]}})
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send summary to Tana")
    return {"summary": summary, "executed_by": executed_by}
