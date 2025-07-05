from __future__ import annotations

"""Agent inbox queue stored in Supabase or fallback JSON file."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except Exception:  # noqa: BLE001
    SUPABASE_AVAILABLE = False

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
_TABLE = os.getenv("INBOX_SUPABASE_TABLE", "agent_inbox")

_client = None
if SUPABASE_AVAILABLE and _SUPABASE_URL and _SUPABASE_KEY:
    try:  # pragma: no cover - network
        _client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    except Exception:  # noqa: BLE001
        _client = None

_LOG_FILE = Path("logs/inbox.json")

from codex.tasks import ai_inbox_summarizer
from codex.integrations import push_notify
from codex.tasks import claude_prompt

_ALERT_THRESHOLD = int(os.getenv("INBOX_ALERT_THRESHOLD", "3"))
_LAST_ALERT_FILE = Path("logs/last_inbox_alert.txt")


def _maybe_send_alert() -> None:
    if _ALERT_THRESHOLD <= 0:
        return
    pending = len(get_pending_tasks(_ALERT_THRESHOLD + 1))
    if pending < _ALERT_THRESHOLD:
        return
    last_ts = None
    if _LAST_ALERT_FILE.exists():
        try:
            last_ts = datetime.fromisoformat(_LAST_ALERT_FILE.read_text().strip())
        except Exception:
            last_ts = None
    if last_ts and (datetime.now(timezone.utc) - last_ts).total_seconds() < 3600:
        return
    items = get_pending_tasks(5)
    summaries = [i.get("summary", {}).get("summary") for i in items]
    prompt = "Summarize inbox: " + " ".join(summaries)
    res = claude_prompt.run({"prompt": prompt})
    msg = res.get("completion", "") or f"{pending} tasks pending"
    push_notify.send_push("Inbox Pending", msg.strip(), url="/agent/inbox")
    _LAST_ALERT_FILE.write_text(datetime.now(timezone.utc).isoformat())


def _append_file(entry: Dict[str, Any]) -> None:
    _LOG_FILE.parent.mkdir(exist_ok=True)
    history: List[Dict[str, Any]] = []
    if _LOG_FILE.exists():
        try:
            history = json.loads(_LOG_FILE.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    _LOG_FILE.write_text(json.dumps(history[-200:], indent=2))


def add_to_inbox(task_id: str, context: Dict[str, Any], origin: str, model: str | None = None) -> Dict[str, Any]:
    """Queue a task for approval and store summary."""
    model = model or os.getenv("INBOX_SUMMARIZER_MODEL", "claude")
    summary = ai_inbox_summarizer.run({"context": context, "model": model})
    entry = {
        "task_id": task_id,
        "origin": origin,
        "model": model,
        "context": context,
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    if _client:
        try:  # pragma: no cover - network
            _client.table(_TABLE).insert(entry).execute()
        except Exception:  # noqa: BLE001
            _append_file(entry)
    else:
        _append_file(entry)
    _maybe_send_alert()
    return entry


def get_pending_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    """Return pending inbox tasks."""
    if _client:
        try:  # pragma: no cover - network
            res = (
                _client.table(_TABLE)
                .select("*")
                .eq("status", "pending")
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            return list(res.data or [])
        except Exception:  # noqa: BLE001
            pass
    if _LOG_FILE.exists():
        try:
            data = json.loads(_LOG_FILE.read_text())
            return [d for d in data if d.get("status") == "pending"][-limit:]
        except Exception:  # noqa: BLE001
            return []
    return []


def _update_file(task_id: str, status: str, notes: str) -> None:
    if not _LOG_FILE.exists():
        return
    try:
        data = json.loads(_LOG_FILE.read_text())
    except Exception:  # noqa: BLE001
        return
    for item in data:
        if item.get("task_id") == task_id:
            item["status"] = status
            item["notes"] = notes
            item["updated"] = datetime.now(timezone.utc).isoformat()
            break
    _LOG_FILE.write_text(json.dumps(data, indent=2))


def mark_as_resolved(task_id: str, status: str, notes: str) -> None:
    """Update inbox item status with optional notes."""
    if _client:
        try:  # pragma: no cover - network
            _client.table(_TABLE).update({"status": status, "notes": notes}).eq("task_id", task_id).execute()
        except Exception:  # noqa: BLE001
            _update_file(task_id, status, notes)
    else:
        _update_file(task_id, status, notes)


def update_task(task_id: str, fields: Dict[str, Any]) -> None:
    """Update fields on an inbox task."""
    if _client:
        try:  # pragma: no cover - network
            _client.table(_TABLE).update(fields).eq("task_id", task_id).execute()
            return
        except Exception:  # noqa: BLE001
            pass
    if not _LOG_FILE.exists():
        return
    try:
        data = json.loads(_LOG_FILE.read_text())
    except Exception:  # noqa: BLE001
        return
    for item in data:
        if item.get("task_id") == task_id:
            item.update(fields)
            item["updated"] = datetime.now(timezone.utc).isoformat()
            break
    _LOG_FILE.write_text(json.dumps(data, indent=2))


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single inbox item."""
    if _client:
        try:  # pragma: no cover - network
            res = _client.table(_TABLE).select("*").eq("task_id", task_id).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception:  # noqa: BLE001
            pass
    if _LOG_FILE.exists():
        try:
            data = json.loads(_LOG_FILE.read_text())
            for item in data:
                if item.get("task_id") == task_id:
                    return item
        except Exception:  # noqa: BLE001
            return None
    return None


def get_summary() -> Dict[str, Any]:
    """Return summary counts and last decision."""
    pending = 0
    approved = 0
    last_decision = None
    records: List[Dict[str, Any]] = []
    if _client:
        try:  # pragma: no cover - network
            all_items = _client.table(_TABLE).select("*").order("timestamp", desc=True).execute()
            records = list(all_items.data or [])
        except Exception:  # noqa: BLE001
            records = []
    elif _LOG_FILE.exists():
        try:
            records = json.loads(_LOG_FILE.read_text())
        except Exception:  # noqa: BLE001
            records = []
    for item in records:
        status = item.get("status")
        if status == "pending":
            pending += 1
        if status == "approved":
            approved += 1
    if records:
        for item in reversed(records):
            if item.get("status") != "pending":
                last_decision = item.get("notes")
                break
    return {"pending": pending, "approved": approved, "last_decision": last_decision}
