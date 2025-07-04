"""Utilities for logging AI prompts and completions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .text_helpers import truncate


def log_prompt(model: str, task_id: str, prompt: str, output: str) -> None:
    """Append prompt/response pair to JSON log."""
    path = Path(f"logs/ai_prompts_{model}.json")
    path.parent.mkdir(exist_ok=True)
    entry = {
        "task_id": task_id,
        "model": model,
        "prompt": truncate(prompt, 2000),
        "output": truncate(output, 2000),
        "timestamp": datetime.utcnow().isoformat(),
    }
    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            history = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    path.write_text(json.dumps(history[-200:], indent=2))
