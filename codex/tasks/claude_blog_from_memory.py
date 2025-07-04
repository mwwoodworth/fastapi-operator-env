"""Create a blog post from recent memory using Claude."""

from __future__ import annotations

import logging
from typing import Any, Dict

from codex.memory import memory_store
from utils.template_loader import render_template
from . import claude_prompt, tana_create

TASK_ID = "claude_blog_from_memory"
TASK_DESCRIPTION = "Generate a blog post from recent Claude memory"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    records = memory_store.fetch_all(limit=3)
    if not records:
        return {"error": "no_memory"}
    text = "\n\n".join(str(r.get("output") or r) for r in records)
    title = context.get("title", "AI Update")
    prompt = render_template("ai_blog_summary", {"title": title, "input": text})
    result = claude_prompt.run({"prompt": prompt})
    blog = result.get("completion", "")
    executed_by = result.get("executed_by", "claude")
    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": text,
            "output": blog,
            "user": context.get("user", "default"),
            "tags": ["blog"],
        },
        origin={"model": executed_by},
    )
    if context.get("tana"):
        try:
            tana_create.run({"content": blog, "metadata": {"tags": ["blog"]}})
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send blog to Tana")
    return {"blog": blog, "executed_by": executed_by}
