"""Notify Make.com of a new sale for onboarding and CRM sync."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

TASK_ID = "sync_sale"
TASK_DESCRIPTION = "Send sale details to Make scenario"
REQUIRED_FIELDS = ["email", "product"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    url = os.getenv("MAKE_SALE_WEBHOOK")
    if not url:
        return {"error": "no_webhook_configured"}
    payload = {
        "email": context.get("email"),
        "product": context.get("product"),
        "amount": context.get("amount"),
        "metadata": context.get("metadata"),
    }
    try:  # pragma: no cover - external network
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"status": "sent"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Sale sync failed: %s", exc)
        return {"status": "error", "error": str(exc)}
