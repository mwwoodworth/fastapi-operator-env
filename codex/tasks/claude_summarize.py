"""Summarize previous memory logs using Claude."""

from __future__ import annotations

import logging
from typing import Dict, Any

from codex.memory import memory_store
from . import claude_prompt

TASK_ID = "claude_summarize"
TASK_DESCRIPTION = "Summarize previous memory logs using Claude"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    records = memory_store.fetch_all(limit=3)
    if not records:
        return {"error": "no_memory"}
    text = "\n\n".join(str(r.get("output")) for r in records)
    prompt = f"Summarize the following information:\n{text}"
    result = claude_prompt.run({"prompt": prompt})
    summary = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": text,
            "output": summary,
            "user": context.get("user", "default"),
            "tags": ["summary"],
        },
        origin={"model": executed_by},
    )
    return {"summary": summary, "executed_by": executed_by}
