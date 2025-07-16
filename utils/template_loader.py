"""Load and render prompt templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_TEMPLATE_FILE = Path("codex/templates/prompt_templates.json")


def _load_templates() -> Dict[str, Dict[str, Any]]:
    if not _TEMPLATE_FILE.exists():
        return {}
    return json.loads(_TEMPLATE_FILE.read_text())


def render_template(key: str, fields: Dict[str, Any] | None = None) -> str:
    templates = _load_templates()
    data = templates.get(key)
    if not data:
        raise KeyError(f"Template not found: {key}")
    template = data.get("template", "")
    fields = fields or {}
    for name, value in fields.items():
        template = template.replace(f"{{{{{name}}}}}", str(value))
    return template
