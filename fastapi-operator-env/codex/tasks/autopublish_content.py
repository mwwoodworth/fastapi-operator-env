"""Auto publish content to site, marketplaces, and newsletter."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

TASK_ID = "autopublish_content"
TASK_DESCRIPTION = "Publish a new article across all channels"
REQUIRED_FIELDS = ["title", "content"]

logger = logging.getLogger(__name__)


def _post_to_site(title: str, content: str) -> dict:
    """Publish to BrainStackStudio site API."""
    api_url = os.getenv("BRAINSTACK_API_URL")
    api_key = os.getenv("BRAINSTACK_API_KEY")
    if not api_url:
        return {"status": "disabled"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    try:  # pragma: no cover - external network
        resp = httpx.post(
            f"{api_url}/posts",
            json={"title": title, "content": content},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"status": "published", "id": data.get("id")}
    except Exception as exc:  # noqa: BLE001
        logger.error("Site publish failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _trigger_make(title: str, content: str) -> dict:
    """Send data to Make.com scenario for marketplace publishing."""
    url = os.getenv("MAKE_PUBLISH_WEBHOOK")
    if not url:
        return {"status": "disabled"}
    payload = {"title": title, "content": content}
    try:  # pragma: no cover - external network
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"status": "queued"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Make webhook failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _send_newsletter(title: str, content: str) -> dict:
    """Trigger newsletter send via API."""
    api_url = os.getenv("NEWSLETTER_API_URL")
    api_key = os.getenv("NEWSLETTER_API_KEY")
    if not api_url:
        return {"status": "disabled"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    try:  # pragma: no cover - external network
        resp = httpx.post(
            f"{api_url}/send",
            json={"subject": title, "body": content},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return {"status": "sent"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Newsletter send failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    title = context.get("title")
    content = context.get("content")
    if not title or not content:
        return {"error": "missing_fields"}
    result = {"site": _post_to_site(title, content)}
    result["marketplace"] = _trigger_make(title, content)
    if context.get("send_newsletter"):
        result["newsletter"] = _send_newsletter(title, content)
    return result
