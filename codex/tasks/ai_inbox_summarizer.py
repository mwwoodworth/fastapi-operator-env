"""Summarize task context for inbox preview."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from utils.ai_logging import log_prompt
from . import claude_prompt, gemini_prompt

TASK_ID = "ai_inbox_summarizer"
TASK_DESCRIPTION = "Summarize task context for quick review"
REQUIRED_FIELDS = ["context"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    ctx = context.get("context") or {}
    model = context.get("model") or os.getenv("INBOX_SUMMARIZER_MODEL", "claude")
    if model not in {"claude", "gemini"}:
        return {
            "summary": str(ctx)[:200],
            "importance": "",
            "next_steps": "",
            "executed_by": model,
        }
    prompt = (
        "Provide a short JSON summary for the following task context. "
        "Return keys 'summary', 'importance', 'next_steps'.\n" + json.dumps(ctx)
    )
    ai_result = claude_prompt.run({"prompt": prompt}) if model == "claude" else gemini_prompt.run({"prompt": prompt})
    raw = ai_result.get("completion", "")
    log_prompt(model, TASK_ID, prompt, raw)
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        data = {"summary": raw, "importance": "", "next_steps": ""}
    data["executed_by"] = ai_result.get("executed_by", model)
    return data
