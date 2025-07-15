"""Summarize retrieved context and suggest next steps."""

from __future__ import annotations

from typing import Any, Dict

from utils.context_builder import build_context
from . import claude_prompt, gemini_prompt

TASK_ID = "rag_summary_writer"
TASK_DESCRIPTION = "Generate summary from RAG context"
REQUIRED_FIELDS = ["query", "context"]


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    query = context.get("query", "")
    docs = context.get("context", "")
    model = context.get("model", "claude")
    prompt = (
        f"{docs}\n\nQuestion: {query}\n"
        "Provide a short executive summary and key next steps."
    )
    res = (
        claude_prompt.run({"prompt": prompt})
        if model == "claude"
        else gemini_prompt.run({"prompt": prompt})
    )
    return {"summary": res.get("completion", ""), "executed_by": res.get("executed_by", model)}
