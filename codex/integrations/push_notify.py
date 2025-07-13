from __future__ import annotations

"""Simple push notification helper via webhook."""

import os
import httpx
from loguru import logger


def send_push(title: str, body: str, url: str = "") -> dict:
    """Send a push notification using a webhook.

    Environment variables ``PUSH_WEBHOOK_URL`` and ``PUSH_DEVICE_ID`` configure
    the target service. If ``PUSH_WEBHOOK_URL`` is not provided, this function
    performs no action and returns ``{"status": "disabled"}``.
    """
    webhook = os.getenv("PUSH_WEBHOOK_URL")
    if not webhook:
        return {"status": "disabled"}

    payload = {"title": title, "body": body}
    device = os.getenv("PUSH_DEVICE_ID")
    if device:
        payload["device"] = device
    if url:
        payload["url"] = url

    try:  # pragma: no cover - external network
        resp = httpx.post(webhook, json=payload, timeout=10)
        resp.raise_for_status()
        return {"status": "sent", "response": resp.text}
    except Exception as exc:  # noqa: BLE001
        logger.error("Push notification failed: %s", exc)
        return {"status": "error", "error": str(exc)}
