"""Use Claude or Gemini to craft a useful prompt based on memory."""

from __future__ import annotations

import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt, gemini_prompt

TASK_ID = "ai_prompt_writer"
TASK_DESCRIPTION = "Generate a custom AI prompt"
REQUIRED_FIELDS = ["purpose", "input"]

logger = logging.getLogger(__name__)


def _resolve_input(val: str) -> str:
    if val.startswith("{{") and val.endswith("}}"):
        token = val[2:-2]
        if token.startswith("memory:"):
            arg = token.split(":", 1)[1]
            try:
                limit = 1 if arg == "recent" else int(arg)
            except Exception:  # noqa: BLE001
                limit = 1
            mem = memory_store.fetch_all(limit=limit)
            return "\n".join(str(m.get("output") or m) for m in mem)
    return val


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    purpose = context.get("purpose")
    raw_input = context.get("input", "")
    audience = context.get("audience", "general")
    model = context.get("model", "claude")

    if not purpose or not raw_input:
        return {"error": "missing_fields"}

    input_text = _resolve_input(str(raw_input))

    prompt = (
        "Craft a concise prompt for another AI system. "
        f"Purpose: {purpose}. Audience: {audience}. "
        f"Here is the input content:\n{input_text}"
    )

    if model == "gemini":
        result = gemini_prompt.run({"prompt": prompt})
    else:
        result = claude_prompt.run({"prompt": prompt})

    final_prompt = result.get("completion", "")
    executed_by = result.get("executed_by", model)
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": context,
            "output": final_prompt,
            "tags": ["prompt"],
        },
        origin={"model": executed_by},
    )
    return {"prompt": final_prompt, "executed_by": executed_by}
