from __future__ import annotations

"""ClickUp API helpers for basic task operations."""

import logging
import os
from typing import Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.clickup.com/api/v2"
_TOKEN = os.getenv("CLICKUP_API_TOKEN")

_headers = {"Authorization": _TOKEN} if _TOKEN else {}


def create_task(title: str, description: str, list_id: str) -> Dict[str, Any]:
    """Create a task in ClickUp.

    Returns the API response JSON or ``{"error": "message"}`` on failure or when
    authentication is missing.
    """
    if not _TOKEN:
        return {"error": "not_configured"}
    payload = {"name": title, "description": description}
    try:  # pragma: no cover - external network
        resp = httpx.post(
            f"{_API_BASE}/list/{list_id}/task",
            json=payload,
            headers=_headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp create_task failed: %s", exc)
        return {"error": str(exc)}


def search_tasks(query: str) -> List[Dict[str, Any]]:
    """Search tasks in ClickUp matching ``query`` text."""
    if not _TOKEN:
        return []
    params = {"query": query}
    try:  # pragma: no cover - external network
        resp = httpx.get(f"{_API_BASE}/task", params=params, headers=_headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("tasks", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp search failed: %s", exc)
        return []
