"""Validate a multi-task plan using Claude and Gemini."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from . import claude_prompt, gemini_prompt

TASK_ID = "task_validator"
TASK_DESCRIPTION = "Validate task plan with Claude and Gemini"
REQUIRED_FIELDS = ["plan"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    plan = context.get("plan")
    if not plan:
        return {"error": "missing_plan"}

    plan_json = json.dumps(plan)
    prompt = (
        "Evaluate the following task plan for likelihood of success and suggest i"
        "mprovements if needed. Respond briefly.\n"
        f"{plan_json}"
    )
    claude = claude_prompt.run({"prompt": prompt})
    gemini = gemini_prompt.run({"prompt": prompt})
    return {
        "claude": claude.get("completion"),
        "gemini": gemini.get("completion"),
        "executed_by": [claude.get("executed_by", "claude"), gemini.get("executed_by", "gemini")],
    }
