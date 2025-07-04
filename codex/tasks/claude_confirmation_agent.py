"""Use Claude to confirm whether to repeat or adjust recent tasks."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt

TASK_ID = "claude_confirmation_agent"
TASK_DESCRIPTION = "Ask Claude if recent task should be repeated or updated"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def _recent_history(limit: int = 5) -> str:
    records = memory_store.fetch_all(limit=limit)
    return "\n\n".join(str(r.get("output") or r) for r in records)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    history = _recent_history(3)
    prompt = (
        "You are a decision assistant. Recent task results:\n"
        f"{history}\n\nShould this be repeated or updated based on results? "
        "Respond in JSON with keys 'decision' (yes|no|adjust), 'reason', and "
        "optional 'follow_up'."
    )
    result = claude_prompt.run({"prompt": prompt})
    raw = result.get("completion", "")
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        decision = "adjust" if "adjust" in raw.lower() else ("no" if "no" in raw.lower() else "yes")
        data = {"decision": decision, "reason": raw}
    return data
