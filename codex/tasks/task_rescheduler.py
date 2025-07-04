"""Check delayed tasks and escalate, close, or re-run."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from codex.memory import agent_inbox, memory_store
from . import claude_prompt

TASK_ID = "task_rescheduler"
TASK_DESCRIPTION = "Handle delayed tasks and escalation"
REQUIRED_FIELDS: List[str] = []

_FILE = Path("delayed_tasks.json")


def _load() -> List[Dict[str, Any]]:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def _save(data: List[Dict[str, Any]]) -> None:
    _FILE.write_text(json.dumps(data, indent=2))


def record_delay(task_id: str, delay_until: str, note: str | None = None, fallback: str | None = None) -> None:
    tasks = _load()
    entry = {
        "task_id": task_id,
        "delay_until": delay_until,
        "note": note or "",
        "fallback": fallback or "notify",
        "handled": False,
    }
    tasks.append(entry)
    _save(tasks)
    agent_inbox.update_task(task_id, {"delay_until": delay_until, "note": note})


def run(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Check for expired delays and determine next action."""
    tasks = _load()
    now = datetime.utcnow()
    remaining: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    for t in tasks:
        if t.get("handled"):
            remaining.append(t)
            continue
        until = t.get("delay_until")
        if not until:
            remaining.append(t)
            continue
        try:
            dt = datetime.fromisoformat(until)
        except Exception:
            remaining.append(t)
            continue
        if now >= dt:
            prompt = (
                f"Task {t['task_id']} was delayed until {until}. "
                "Should we escalate, close, or re-run?"
            )
            ai = claude_prompt.run({"prompt": prompt})
            decision = ai.get("completion", "").lower()
            actions.append({"task_id": t["task_id"], "decision": decision})
            memory_store.save_memory(
                {
                    "task": TASK_ID,
                    "input": t,
                    "output": decision,
                    "tags": ["delay", "auto"],
                }
            )
            if "re-run" in decision:
                item = agent_inbox.get_task(t["task_id"]) or {}
                ctx = item.get("context", {})
                from codex import run_task

                run_task(t["task_id"], ctx)
                agent_inbox.mark_as_resolved(t["task_id"], "re-run", "auto")
            elif "close" in decision:
                agent_inbox.mark_as_resolved(t["task_id"], "closed", "auto")
            else:
                agent_inbox.update_task(t["task_id"], {"status": "escalate"})
            t["handled"] = True
        else:
            remaining.append(t)
    _save(remaining + [t for t in tasks if t.get("handled")])
    return {"actions": actions}
