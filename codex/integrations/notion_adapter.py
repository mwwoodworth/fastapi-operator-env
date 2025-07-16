from __future__ import annotations

"""Placeholder Notion adapter for knowledge search."""

from typing import List, Dict
import os
from loguru import logger

from . import notion


def search_notion_pages(query: str) -> List[Dict[str, str]]:
    """Search Notion for pages matching ``query`` and return snippets."""

    token = os.getenv("NOTION_API_KEY")
    if not token:
        logger.warning("No NOTION_API_KEY configured")
        return []

    pages = notion.search_notion_pages("", token, query)
    results: List[Dict[str, str]] = []
    for page in pages:
        snippet = notion.get_page_snippet("", token, page.get("id", ""))
        results.append(
            {
                "id": page.get("id", ""),
                "title": page.get("title", ""),
                "text": snippet,
                "tags": [],
                "source_url": f"https://www.notion.so/{page.get('id', '').replace('-', '')}",
            }
        )
    return results


def get_page_snippet(page_id: str) -> str:
    """Return a snippet of text from the given Notion page."""

    token = os.getenv("NOTION_API_KEY")
    if not token:
        logger.warning("No NOTION_API_KEY configured")
        return ""
    return notion.get_page_snippet("", token, page_id)


__all__ = ["search_notion_pages", "get_page_snippet"]
