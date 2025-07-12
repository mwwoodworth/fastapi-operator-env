"""AI model router to choose Claude or Gemini based on task type."""

from __future__ import annotations

from typing import AsyncGenerator

from core.settings import Settings
from claude_utils import run_claude, stream_claude
from gpt_utils import run_gpt, stream_gpt

settings = Settings()


def get_ai_model(task: str | None = None) -> str:
    """Return 'claude', 'gemini', or 'chain' based on task name and env var."""
    mode = settings.AI_ROUTER_MODE
    if mode in {"claude", "gemini", "chain"}:
        return mode

    if not task:
        return "claude"

    name = task.lower()
    if any(k in name for k in ["summary", "write", "memory", "tana", "blog"]):
        return "claude"
    if any(k in name for k in ["code", "inspect", "data", "query", "rag"]):
        return "gemini"
    return "claude"


async def stream_completion(prompt: str, model: str) -> AsyncGenerator[str, None]:
    """Stream completion tokens for the selected model."""
    if model == "gemini":
        async for token in stream_gpt(prompt):
            yield token
    else:
        async for token in stream_claude(prompt):
            yield token


async def run_completion(prompt: str, model: str) -> str:
    """Return full completion string for the selected model."""
    if model == "gemini":
        return await run_gpt(prompt)
    return await run_claude(prompt)
