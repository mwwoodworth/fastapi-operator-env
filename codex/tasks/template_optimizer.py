"""Optimize prompt templates using Gemini then Claude."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from . import gemini_prompt, claude_prompt

TASK_ID = "template_optimizer"
TASK_DESCRIPTION = "Evolve and optimize prompt templates"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)

_TEMPLATE_FILE = Path("codex/templates/prompt_templates.json")


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    if not _TEMPLATE_FILE.exists():
        return {"error": "template_file_missing"}

    data = json.loads(_TEMPLATE_FILE.read_text())
    for key, val in data.items():
        if not isinstance(val, dict) or "template" not in val:
            continue
        tmpl = val["template"]
        gem_res = gemini_prompt.run({"prompt": f"Improve this template for clarity and results:\n{tmpl}"})
        gem_out = gem_res.get("completion", tmpl)
        claude_res = claude_prompt.run({"prompt": f"Rewrite the following template to maximize engagement:\n{gem_out}"})
        val["template"] = claude_res.get("completion", gem_out)

    data["optimized_by"] = ["gemini", "claude"]
    _TEMPLATE_FILE.write_text(json.dumps(data, indent=2))

    return {"status": "optimized", "templates": len(data)}
