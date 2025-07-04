from __future__ import annotations

"""Placeholder Notion adapter for knowledge search."""

from typing import List, Dict


def search_notion_pages(query: str) -> List[Dict[str, str]]:
    """Search Notion for pages matching the query.

    Returns an empty list during tests or when API keys are missing.
    """
    _ = query
    return []
