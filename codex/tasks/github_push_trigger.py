"""Trigger tasks on GitHub push events."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict

from codex.brainops_operator import run_task

TASK_ID = "github_push_trigger"
TASK_DESCRIPTION = "Run a task when a GitHub push to main occurs"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)

GITHUB_SECRET = os.getenv("GITHUB_SECRET")
DEFAULT_TASK = os.getenv("GITHUB_TRIGGER_TASK", "site_audit")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    if not GITHUB_SECRET or not signature:
        return True
    digest = hmac.new(GITHUB_SECRET.encode(), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    payload = context.get("payload") or {}
    signature = context.get("signature")
    raw = context.get("raw_body", b"")
    if not _verify_signature(raw, signature):
        logger.warning("Invalid GitHub signature")
        return {"error": "invalid_signature"}
    if payload.get("ref") != "refs/heads/main":
        return {"status": "ignored"}
    task = context.get("task", DEFAULT_TASK)
    try:
        result = run_task(task, context.get("context", {}))
        return {"status": "triggered", "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.error("Triggered task failed: %s", exc)
        return {"error": str(exc)}
