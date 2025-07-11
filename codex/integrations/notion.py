from __future__ import annotations

"""Notion API helpers for search and snippet retrieval."""

import logging
import os
from typing import List, Dict

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.notion.com/v1"
_VERSION = "2022-06-28"

_TOKEN = os.getenv("NOTION_API_KEY")


def _headers() -> dict:
    if not _TOKEN:
        return {}
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Notion-Version": _VERSION,
    }


def search_notion_pages(query: str) -> List[Dict[str, str]]:
    """Search Notion workspace pages by text query.

    Returns a list of page ``{"id": str, "title": str}`` dictionaries. If the
    token is missing or the request fails, an empty list is returned.
    """
    if not _TOKEN:
        return []
    payload = {"query": query, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
    try:  # pragma: no cover - external network
        resp = httpx.post(f"{_API_BASE}/search", json=payload, headers=_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
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


def get_page_snippet(page_id: str) -> str:
    """Return a short text snippet from the top of a Notion page."""
    if not _TOKEN:
        return ""
    try:  # pragma: no cover - external network
        resp = httpx.get(
            f"{_API_BASE}/blocks/{page_id}/children",
            params={"page_size": 5},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Notion snippet failed: %s", exc)
        return ""

    texts: List[str] = []
    for block in data.get("results", []):
        btype = block.get("type")
        if btype == "paragraph":
            texts.append(
                "".join(t.get("plain_text", "") for t in block.get("paragraph", {}).get("text", []))
            )
        if len(" ".join(texts)) > 200:
            break
    snippet = " ".join(texts).strip()
    return snippet[:200]
