"""Grade AI output using Claude."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from utils.ai_logging import log_prompt
from utils.ai_router import get_ai_model
from . import claude_prompt

TASK_ID = "claude_output_grader"
TASK_DESCRIPTION = "Evaluate output quality with Claude"
REQUIRED_FIELDS = ["output", "criteria"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    output = context.get("output")
    criteria = context.get("criteria")
    if not output or not criteria:
        return {"error": "missing_fields"}

    model = get_ai_model(task=TASK_ID)
    prompt = (
        "You are a strict grader. Score the following output on the criteria: "
        f"{criteria}. Provide a score 0-10 and suggestions for improvement.\n\n"
        f"OUTPUT:\n{output}"
    )
    result = claude_prompt.run({"prompt": prompt, "model": "claude-3-opus"})
    completion = result.get("completion", "")
    log_prompt("claude", TASK_ID, prompt, completion)

    try:
        data = json.loads(completion)
    except Exception:
        return {"raw": completion}

    return data
