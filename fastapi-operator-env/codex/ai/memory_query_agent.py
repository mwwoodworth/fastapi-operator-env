"""Simple helper to query memory records."""

from __future__ import annotations

from typing import List

from codex.memory import memory_store


def query_memory(query: str, top_k: int = 5) -> List[dict]:
    """Return memory search results."""
    return memory_store.search(query, [], limit=top_k)
