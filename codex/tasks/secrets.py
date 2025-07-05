"""Manage encrypted secrets stored in Supabase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from utils.crypto import encrypt, decrypt
from supabase_client import supabase


TASK_ID = "secrets"
TASK_DESCRIPTION = "Store, retrieve and delete encrypted secrets"
REQUIRED_FIELDS: list[str] = []

_AUDIT_FILE = Path("logs/secrets_audit.json")


def _log_audit(name: str, action: str) -> None:
    _AUDIT_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "action": action,
    }
    history: list[dict] = []
    if _AUDIT_FILE.exists():
        try:
            history = json.loads(_AUDIT_FILE.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    _AUDIT_FILE.write_text(json.dumps(history[-200:], indent=2))


def store_secret(name: str, value: str) -> None:
    encrypted = encrypt(value)
    supabase.table("secrets").insert({"name": name, "value": encrypted}).execute()
    _log_audit(name, "store")


def retrieve_secret(name: str) -> str | None:
    row = (
        supabase.table("secrets")
        .select("*")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    if row.data:
        value = decrypt(row.data[0]["value"])
        _log_audit(name, "retrieve")
        return value
    return None


def delete_secret(name: str) -> None:
    supabase.table("secrets").delete().eq("name", name).execute()
    _log_audit(name, "delete")


def list_secrets() -> list[str]:
    res = supabase.table("secrets").select("name").execute()
    names = [item["name"] for item in res.data or []]
    _log_audit("*", "list")
    return names


def expire_old(days: int = 90) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    res = (
        supabase.table("secrets")
        .select("id", "created_at")
        .lt("created_at", cutoff.isoformat())
        .execute()
    )
    for item in res.data or []:
        supabase.table("secrets").delete().eq("id", item["id"]).execute()
        _log_audit(item.get("id", ""), "expire")


def run(context: dict) -> dict:
    """Placeholder to satisfy task loader."""
    action = context.get("action")
    if action == "store":
        store_secret(context["name"], context["value"])
        return {"status": "stored"}
    if action == "retrieve":
        val = retrieve_secret(context["name"])
        return {"value": val}
    if action == "delete":
        delete_secret(context["name"])
        return {"status": "deleted"}
    if action == "list":
        return {"secrets": list_secrets()}
    return {"status": "no_action"}
