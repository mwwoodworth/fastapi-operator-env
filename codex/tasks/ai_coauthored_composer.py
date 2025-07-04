"""Compose a task plan co-authored by Claude and Gemini."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt, gemini_prompt

TASK_ID = "ai_coauthored_composer"
TASK_DESCRIPTION = "Compose task pipeline with Claude and Gemini"
REQUIRED_FIELDS = ["intent"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    if os.getenv("AI_COAUTHOR_MODE") != "enabled":
        return {"error": "disabled"}

    intent = context.get("intent")
    if not intent:
        return {"error": "missing_intent"}

    step1 = claude_prompt.run({"prompt": f"Draft a task skeleton for: {intent}. Respond in JSON."})
    skeleton = step1.get("completion", "")

    step2 = gemini_prompt.run({"prompt": f"Expand this skeleton with technical details. Respond in JSON.\n{skeleton}"})
    expanded = step2.get("completion", "")

    final = claude_prompt.run({"prompt": f"Finalize this plan for {intent}. Ensure logic is sound and goals clear. Respond in JSON.\n{expanded}"})
    final_raw = final.get("completion", "")
    executed_by = final.get("executed_by", "claude")

    try:
        plan = json.loads(final_raw)
    except Exception:
        plan = {"tasks": []}

    metadata = {"authors": ["claude", "gemini"], "version": "1.0"}
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": intent,
            "output": plan,
            "metadata": metadata,
            "tags": ["coauthored"],
        },
        origin={"model": executed_by},
    )

    return {"plan": plan, "metadata": metadata, "executed_by": executed_by}
