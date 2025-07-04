from __future__ import annotations

"""Placeholder Tana adapter for knowledge search."""

from typing import List, Dict


def search_tana_nodes(query: str) -> List[Dict[str, str]]:
    """Search Tana for nodes matching the query.

    This demo implementation returns an empty list as network access may not be
    available during tests.
    """
    _ = query  # unused
    return []
