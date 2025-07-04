"""AI model router to choose Claude or Gemini based on task type."""

from __future__ import annotations

import os


def get_ai_model(task: str | None = None) -> str:
    """Return 'claude' or 'gemini' based on the task name and env var."""
    mode = os.getenv("AI_ROUTER_MODE", "auto")
    if mode in {"claude", "gemini"}:
        return mode

    if not task:
        return "claude"

    name = task.lower()
    if any(k in name for k in ["summary", "write", "memory", "tana", "blog"]):
        return "claude"
    if any(k in name for k in ["code", "inspect", "data", "query", "rag"]):
        return "gemini"
    return "claude"
