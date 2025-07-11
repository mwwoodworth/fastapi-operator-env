"""Persistent memory store with Supabase fallback."""

from __future__ import annotations

import json
from core.settings import Settings
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client

    SUPABASE_AVAILABLE = True
except Exception:  # noqa: BLE001
    SUPABASE_AVAILABLE = False

settings = Settings()
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY

_client = None
if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception:  # noqa: BLE001
        _client = None

_LOG_FILE = Path("logs/memory_log.json")


def _append_file(entry: Dict[str, Any]) -> None:
    _LOG_FILE.parent.mkdir(exist_ok=True)
    history: List[Dict[str, Any]] = []
    if _LOG_FILE.exists():
        try:
            history = json.loads(_LOG_FILE.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    _LOG_FILE.write_text(json.dumps(history[-100:], indent=2))


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
    if _client:
        try:
            _client.table("memory").insert(entry).execute()
            return
        except Exception:  # noqa: BLE001
            # fall back to file
            pass
    _append_file(entry)


def fetch_all(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent memory entries."""
    if _client:
        try:
            res = (
                _client.table("memory")
                .select("*")
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
            return data[-limit:]
        except Exception:  # noqa: BLE001
            return []
    return []


def fetch_one(entry_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single memory entry by ID."""
    if _client:
        try:
            res = (
                _client.table("memory")
                .select("*")
                .eq("id", entry_id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:  # noqa: BLE001
            pass
    if _LOG_FILE.exists():
        try:
            data = json.loads(_LOG_FILE.read_text())
            for item in data:
                if item.get("id") == entry_id:
                    return item
        except Exception:  # noqa: BLE001
            return None
    return None


def count_entries() -> int:
    """Return total number of memory records."""
    if _client:
        try:
            res = _client.table("memory").select("id", count="exact").execute()
            return int(res.count or 0)
        except Exception:  # noqa: BLE001
            pass
    if _LOG_FILE.exists():
        try:
            return len(json.loads(_LOG_FILE.read_text()))
        except Exception:  # noqa: BLE001
            return 0
    return 0


def query(tags: List[str] | None = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Query memory entries by tags."""
    tags = tags or []
    if _client:
        try:
            qry = (
                _client.table("memory")
                .select("*")
                .order("timestamp", desc=True)
                .limit(limit)
            )
            if tags:
                qry = qry.contains("tags", tags)
            res = qry.execute()
            return list(res.data or [])
        except Exception:  # noqa: BLE001
            pass
    records = fetch_all(limit=1000)
    if tags:
        records = [r for r in records if set(tags).issubset(set(r.get("tags") or []))]
    return records[-limit:]


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
