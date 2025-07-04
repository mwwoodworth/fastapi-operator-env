"""Query multiple knowledge sources and summarize the results."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from codex.memory import memory_store
from codex.memory import doc_indexer
from codex.integrations.tana_adapter import search_tana_nodes
from codex.integrations.notion_adapter import search_notion_pages
from utils.context_builder import build_context
from utils import rag_logger
from . import rag_summary_writer

TASK_ID = "unified_rag_agent"
TASK_DESCRIPTION = "Unified knowledge retrieval agent"
REQUIRED_FIELDS = ["query"]

logger = logging.getLogger(__name__)


def _search_memory(query: str) -> List[str]:
    results: List[str] = []
    for entry in memory_store.fetch_all(limit=200):
        text = str(entry.get("output") or entry)
        if query.lower() in text.lower():
            results.append(text)
    return results


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    query = context.get("query", "")
    sources = context.get("sources", ["memory"]) or ["memory"]
    model = context.get("model", "claude")
    if not query:
        return {"error": "missing_query"}

    docs: List[str] = []
    sources_used: List[str] = []

    if "memory" in sources:
        mem = _search_memory(query)
        docs.extend(mem)
        sources_used.extend(["memory"] * len(mem))

    if "local_docs" in sources:
        local = doc_indexer.search(query)
        docs.extend([d["text"] for d in local])
        sources_used.extend([d["source_url"] for d in local])

    if "tana" in sources:
        tana = search_tana_nodes(query)
        docs.extend([t.get("text", "") for t in tana])
        sources_used.extend([t.get("source_url") for t in tana])

    if "notion" in sources:
        notion = search_notion_pages(query)
        docs.extend([n.get("text", "") for n in notion])
        sources_used.extend([n.get("source_url") for n in notion])

    context_block = build_context(docs)
    summary_res = rag_summary_writer.run({"query": query, "context": context_block, "model": model})
    summary = summary_res.get("summary", "")
    rag_logger.log_query(rag_logger.create_entry(query, sources_used, summary, model))

    return {"summary": summary, "sources": sources_used, "model": model}
