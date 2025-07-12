"""Persistent memory store using Supabase."""

from __future__ import annotations

from core.settings import Settings
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from supabase_client import supabase as _supabase
    SUPABASE_AVAILABLE = True
except Exception:  # noqa: BLE001
    SUPABASE_AVAILABLE = False

settings = Settings()
_client = _supabase if SUPABASE_AVAILABLE else None


def save_memory(memory: Dict[str, Any], origin: Dict[str, Any] | None = None) -> None:
    """Persist a memory entry with optional origin metadata."""
    entry = memory.copy()
    entry.setdefault("id", str(uuid.uuid4()))
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    if origin:
        meta = entry.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta.update(origin)
        else:
            entry["metadata"] = origin
        if origin.get("tags"):
            entry.setdefault("tags", [])
            if isinstance(entry["tags"], list):
                entry["tags"] = list(set(entry["tags"] + origin["tags"]))
    if not _client:
        raise RuntimeError("Supabase client not configured")
    _client.table("memory").insert(entry).execute()


def fetch_all(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent memory entries."""
    if not _client:
        return []
    res = (
        _client.table("memory")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return list(res.data or [])


def fetch_one(entry_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single memory entry by ID."""
    if not _client:
        return None
    res = _client.table("memory").select("*").eq("id", entry_id).limit(1).execute()
    if res.data:
        return res.data[0]
    return None


def count_entries() -> int:
    """Return total number of memory records."""
    if not _client:
        return 0
    res = _client.table("memory").select("id", count="exact").execute()
    return int(res.count or 0)


def query(tags: List[str] | None = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Query memory entries by tags."""
    tags = tags or []
    if not _client:
        return []
    qry = _client.table("memory").select("*").order("timestamp", desc=True).limit(limit)
    if tags:
        qry = qry.contains("tags", tags)
    res = qry.execute()
    return list(res.data or [])


def load_recent(limit: int = 5, session_id: str | None = None) -> str:
    """Return recent memory entries concatenated as text."""
    records = fetch_all(limit=1000)
    if session_id:
        records = [r for r in records if r.get("session_id") == session_id]
    records = records[-limit:]
    return "\n\n".join(str(r.get("output") or r) for r in records)


def search(
    query: str = "",
    tags: List[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    user: str | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search memory entries with optional fuzzy query and filters."""
    tags = tags or []
    records = fetch_all(limit=1000)
    if tags:
        records = [r for r in records if set(tags).issubset(set(r.get("tags") or []))]
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            records = [
                r
                for r in records
                if r.get("timestamp")
                and datetime.fromisoformat(r["timestamp"]) >= start_dt
            ]
        except Exception:  # noqa: BLE001
            pass
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            records = [
                r
                for r in records
                if r.get("timestamp")
                and datetime.fromisoformat(r["timestamp"]) <= end_dt
            ]
        except Exception:  # noqa: BLE001
            pass
    if user:
        records = [r for r in records if r.get("user") == user]
    if query:
        q_lower = query.lower()
        records = [
            r
            for r in records
            if q_lower in str(r.get("input", "")).lower()
            or q_lower in str(r.get("output", "")).lower()
            or q_lower in str(r.get("task", "")).lower()
        ]
    return records[-limit:]
