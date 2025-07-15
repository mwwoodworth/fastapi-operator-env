from __future__ import annotations

"""Build context blocks for Claude or Gemini."""

from typing import List

from .text_helpers import truncate


def build_context(documents: List[str], max_tokens: int = 8000) -> str:
    """Combine documents and trim to desired length."""
    joined = "\n\n---\n\n".join(documents)
    text = truncate(joined, max_tokens)
    return "Here is what we know:\n" + text
