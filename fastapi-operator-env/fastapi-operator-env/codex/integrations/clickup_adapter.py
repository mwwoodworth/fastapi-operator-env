from __future__ import annotations

"""Simplified ClickUp adapter used by tasks."""

from typing import Any, Dict, List
from loguru import logger
import os

from . import clickup


def search_clickup_tasks(query: str) -> List[Dict[str, Any]]:
    """Search ClickUp for tasks matching ``query``."""
    token = os.getenv("CLICKUP_API_TOKEN")
    if not token:
        logger.warning("No CLICKUP_API_TOKEN configured")
        return []
    try:
        return clickup.search_tasks("", token, query)
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp search failed: %s", exc)
        return []


def create_clickup_task(task_data: Dict[str, Any]) -> Dict[str, Any] | None:
    """Create a ClickUp task from ``task_data``.

    Expected keys are ``title``, ``description`` and ``list_id``. An optional
    ``token`` overrides the default ``CLICKUP_API_TOKEN``.
    """
    list_id = task_data.get("list_id")
    if not list_id:
        logger.error("Missing list_id for ClickUp task creation")
        return None
    token = task_data.get("token") or os.getenv("CLICKUP_API_TOKEN")
    if not token:
        logger.error("No CLICKUP_API_TOKEN configured")
        return None
    title = task_data.get("title", "Untitled")
    description = task_data.get("description", "")
    try:
        return clickup.create_task("", token, list_id, title, description)
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp create failed: %s", exc)
        return {"error": str(exc)}


def update_clickup_task(task_id: str, fields: Dict[str, Any]) -> Dict[str, Any] | None:
    """Update a ClickUp task with ``fields``."""
    token = fields.pop("token", None) or os.getenv("CLICKUP_API_TOKEN")
    if not token:
        logger.error("No CLICKUP_API_TOKEN configured")
        return None
    try:
        return clickup.update_task("", token, task_id, fields)
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp update failed: %s", exc)
        return {"error": str(exc)}
