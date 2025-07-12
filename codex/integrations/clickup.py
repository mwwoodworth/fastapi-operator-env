from __future__ import annotations

"""ClickUp API helpers for basic task operations."""

import logging
import os
import time
from typing import Dict, Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.clickup.com/api/v2"
_TOKEN = os.getenv("CLICKUP_API_TOKEN")

_headers = {"Authorization": _TOKEN} if _TOKEN else {}


def _request(
    method: str,
    url: str,
    token: str,
    idempotency_key: str | None = None,
    **kwargs: Any,
) -> dict:
    """HTTP request with exponential backoff."""
    headers = kwargs.pop("headers", {})
    if token:
        headers.setdefault("Authorization", token)
    if idempotency_key:
        headers.setdefault("Idempotency-Key", idempotency_key)

    backoff = 1.0
    for attempt in range(3):
        try:  # pragma: no cover - network
            resp = httpx.request(method, url, headers=headers, timeout=10, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                logger.error("ClickUp request failed: %s", exc)
                raise
            time.sleep(backoff)
            backoff *= 2


def create_task(
    workspace: str,
    token: str,
    list_id: str,
    title: str,
    description: str,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Create a task in ClickUp."""

    url = f"{_API_BASE}/list/{list_id}/task"
    payload = {"name": title, "description": description}
    return _request("POST", url, token, idempotency_key, json=payload)


def get_task(workspace: str, token: str, task_id: str) -> Dict[str, Any]:
    """Fetch a single task."""

    url = f"{_API_BASE}/task/{task_id}"
    return _request("GET", url, token)


def update_task(
    workspace: str,
    token: str,
    task_id: str,
    data: Dict[str, Any],
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Update a ClickUp task."""

    url = f"{_API_BASE}/task/{task_id}"
    return _request("PUT", url, token, idempotency_key, json=data)


def delete_task(workspace: str, token: str, task_id: str) -> Dict[str, Any]:
    """Delete a task."""

    url = f"{_API_BASE}/task/{task_id}"
    return _request("DELETE", url, token)


def search_tasks(workspace: str, token: str, query: str) -> List[Dict[str, Any]]:
    """Search tasks in ClickUp matching ``query`` text."""

    params = {"query": query}
    try:  # pragma: no cover - network
        data = _request("GET", f"{_API_BASE}/task", token, params=params)
        return data.get("tasks", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickUp search failed: %s", exc)
        return []


def handle_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process ClickUp webhook payload."""

    logger.info("Received ClickUp webhook: %s", event)
    return {"status": "received"}


router = APIRouter(prefix="/clickup")


class TaskPayload(BaseModel):
    list_id: str
    title: str
    description: str
    token: str
    workspace: str
    idempotency_key: Optional[str] = None


@router.post("/tasks")
def api_create_task(payload: TaskPayload) -> Dict[str, Any]:
    return create_task(
        payload.workspace,
        payload.token,
        payload.list_id,
        payload.title,
        payload.description,
        payload.idempotency_key,
    )


@router.get("/tasks/{task_id}")
def api_get_task(task_id: str, token: str, workspace: str) -> Dict[str, Any]:
    return get_task(workspace, token, task_id)


class UpdatePayload(BaseModel):
    token: str
    workspace: str
    fields: Dict[str, Any]
    idempotency_key: Optional[str] = None


@router.put("/tasks/{task_id}")
def api_update_task(task_id: str, payload: UpdatePayload) -> Dict[str, Any]:
    return update_task(
        payload.workspace,
        payload.token,
        task_id,
        payload.fields,
        payload.idempotency_key,
    )


@router.delete("/tasks/{task_id}")
def api_delete_task(task_id: str, token: str, workspace: str) -> Dict[str, Any]:
    return delete_task(workspace, token, task_id)


@router.get("/tasks/search")
def api_search_tasks(token: str, workspace: str, query: str) -> List[Dict[str, Any]]:
    return search_tasks(workspace, token, query)


@router.post("/webhook")
def api_webhook(event: Dict[str, Any]):
    return handle_webhook(event)
