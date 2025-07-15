from __future__ import annotations

"""Notion API helpers for search and snippet retrieval."""

from loguru import logger
import os
import time
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import httpx


_API_BASE = "https://api.notion.com/v1"
_VERSION = "2022-06-28"

_TOKEN = os.getenv("NOTION_API_KEY")


def _request(
    method: str,
    url: str,
    token: str,
    idempotency_key: str | None = None,
    **kwargs: Any,
) -> dict:
    headers = kwargs.pop("headers", {})
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    headers.setdefault("Notion-Version", _VERSION)
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
                logger.error("Notion request failed: %s", exc)
                raise
            time.sleep(backoff)
            backoff *= 2


def _headers() -> dict:
    if not _TOKEN:
        return {}
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Notion-Version": _VERSION,
    }


def search_notion_pages(workspace: str, token: str, query: str) -> List[Dict[str, str]]:
    """Search Notion workspace pages by text query.

    Returns a list of page ``{"id": str, "title": str}`` dictionaries. If the
    token is missing or the request fails, an empty list is returned.
    """
    payload = {
        "query": query,
        "sort": {"direction": "descending", "timestamp": "last_edited_time"},
    }
    try:  # pragma: no cover - network
        data = _request("POST", f"{_API_BASE}/search", token, json=payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("Notion search failed: %s", exc)
        return []

    results: List[Dict[str, str]] = []
    for item in data.get("results", []):
        if item.get("object") != "page":
            continue
        title = ""
        for prop in item.get("properties", {}).values():
            if prop.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                break
        results.append({"id": item.get("id", ""), "title": title})
    return results


def create_page(
    workspace: str,
    token: str,
    parent_id: str,
    title: str,
    properties: Dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    payload = {
        "parent": {"page_id": parent_id},
        "properties": properties or {"title": [{"text": {"content": title}}]},
    }
    return _request("POST", f"{_API_BASE}/pages", token, idempotency_key, json=payload)


def get_page(workspace: str, token: str, page_id: str) -> Dict[str, Any]:
    return _request("GET", f"{_API_BASE}/pages/{page_id}", token)


def update_page(
    workspace: str,
    token: str,
    page_id: str,
    properties: Dict[str, Any],
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    payload = {"properties": properties}
    return _request(
        "PATCH", f"{_API_BASE}/pages/{page_id}", token, idempotency_key, json=payload
    )


def delete_page(workspace: str, token: str, page_id: str) -> Dict[str, Any]:
    payload = {"archived": True}
    return _request("PATCH", f"{_API_BASE}/pages/{page_id}", token, json=payload)


def handle_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process Notion webhook payload."""

    logger.info("Received Notion webhook: %s", event)
    return {"status": "received"}


router = APIRouter(prefix="/notion")


class PageCreatePayload(BaseModel):
    parent_id: str
    title: str
    token: str
    workspace: str
    properties: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


@router.post("/pages")
def api_create_page(payload: PageCreatePayload) -> Dict[str, Any]:
    return create_page(
        payload.workspace,
        payload.token,
        payload.parent_id,
        payload.title,
        payload.properties,
        payload.idempotency_key,
    )


@router.get("/pages/{page_id}")
def api_get_page(page_id: str, token: str, workspace: str) -> Dict[str, Any]:
    return get_page(workspace, token, page_id)


class PageUpdatePayload(BaseModel):
    token: str
    workspace: str
    properties: Dict[str, Any]
    idempotency_key: Optional[str] = None


@router.patch("/pages/{page_id}")
def api_update_page(page_id: str, payload: PageUpdatePayload) -> Dict[str, Any]:
    return update_page(
        payload.workspace,
        payload.token,
        page_id,
        payload.properties,
        payload.idempotency_key,
    )


@router.delete("/pages/{page_id}")
def api_delete_page(page_id: str, token: str, workspace: str) -> Dict[str, Any]:
    return delete_page(workspace, token, page_id)


@router.get("/pages/search")
def api_search_pages(token: str, workspace: str, query: str) -> List[Dict[str, str]]:
    return search_notion_pages(workspace, token, query)


@router.get("/pages/{page_id}/snippet")
def api_page_snippet(page_id: str, token: str, workspace: str) -> str:
    return get_page_snippet(workspace, token, page_id)


@router.post("/webhook")
def api_webhook(event: Dict[str, Any]):
    return handle_webhook(event)


def get_page_snippet(workspace: str, token: str, page_id: str) -> str:
    """Return a short text snippet from the top of a Notion page."""
    try:  # pragma: no cover - network
        data = _request(
            "GET",
            f"{_API_BASE}/blocks/{page_id}/children",
            token,
            params={"page_size": 5},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Notion snippet failed: %s", exc)
        return ""

    texts: List[str] = []
    for block in data.get("results", []):
        btype = block.get("type")
        if btype == "paragraph":
            texts.append(
                "".join(
                    t.get("plain_text", "")
                    for t in block.get("paragraph", {}).get("text", [])
                )
            )
        if len(" ".join(texts)) > 200:
            break
    snippet = " ".join(texts).strip()
    return snippet[:200]
