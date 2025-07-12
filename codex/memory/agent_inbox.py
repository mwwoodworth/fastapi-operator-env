"""Agent inbox queue stored in Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.settings import Settings
from codex.tasks import ai_inbox_summarizer
from codex.integrations import push_notify
from codex.tasks import claude_prompt

settings = Settings()

try:
    from supabase_client import supabase as _supabase
    SUPABASE_AVAILABLE = True
except Exception:  # noqa: BLE001
    SUPABASE_AVAILABLE = False

_SUPABASE_URL = settings.SUPABASE_URL
_SUPABASE_KEY = settings.SUPABASE_SERVICE_KEY
_TABLE = settings.INBOX_SUPABASE_TABLE

_client = _supabase if SUPABASE_AVAILABLE else None

_ALERT_THRESHOLD = settings.INBOX_ALERT_THRESHOLD
_last_alert_ts: datetime | None = None


def _maybe_send_alert() -> None:
    if _ALERT_THRESHOLD <= 0:
        return
    pending = len(get_pending_tasks(_ALERT_THRESHOLD + 1))
    if pending < _ALERT_THRESHOLD:
        return
    global _last_alert_ts
    if (
        _last_alert_ts
        and (datetime.now(timezone.utc) - _last_alert_ts).total_seconds() < 3600
    ):
        return
    items = get_pending_tasks(5)
    summaries = [i.get("summary", {}).get("summary") for i in items]
    prompt = "Summarize inbox: " + " ".join(summaries)
    res = claude_prompt.run({"prompt": prompt})
    msg = res.get("completion", "") or f"{pending} tasks pending"
    push_notify.send_push("Inbox Pending", msg.strip(), url="/agent/inbox")
    _last_alert_ts = datetime.now(timezone.utc)


def add_to_inbox(
    task_id: str, context: Dict[str, Any], origin: str, model: str | None = None
) -> Dict[str, Any]:
    """Queue a task for approval and store summary."""
    model = model or settings.INBOX_SUMMARIZER_MODEL
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
    if not _client:
        raise RuntimeError("Supabase client not configured")
    _client.table(_TABLE).insert(entry).execute()
    _maybe_send_alert()
    return entry


def get_pending_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    """Return pending inbox tasks."""
    if not _client:
        return []
    res = (
        _client.table(_TABLE)
        .select("*")
        .eq("status", "pending")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return list(res.data or [])


def mark_as_resolved(task_id: str, status: str, notes: str) -> None:
    """Update inbox item status with optional notes."""
    if not _client:
        raise RuntimeError("Supabase client not configured")
    _client.table(_TABLE).update({"status": status, "notes": notes}).eq(
        "task_id", task_id
    ).execute()


def update_task(task_id: str, fields: Dict[str, Any]) -> None:
    """Update fields on an inbox task."""
    if not _client:
        raise RuntimeError("Supabase client not configured")
    _client.table(_TABLE).update(fields).eq("task_id", task_id).execute()


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single inbox item."""
    if not _client:
        return None
    res = _client.table(_TABLE).select("*").eq("task_id", task_id).limit(1).execute()
    if res.data:
        return res.data[0]
    return None


def get_summary() -> Dict[str, Any]:
    """Return summary counts and last decision."""
    pending = 0
    approved = 0
    last_decision = None
    records: List[Dict[str, Any]] = []
    if _client:
        try:  # pragma: no cover - network
            all_items = (
                _client.table(_TABLE)
                .select("*")
                .order("timestamp", desc=True)
                .execute()
            )
            records = list(all_items.data or [])
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
