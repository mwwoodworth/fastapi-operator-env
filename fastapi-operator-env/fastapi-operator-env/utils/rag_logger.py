from __future__ import annotations

"""Logging utilities for knowledge retrieval queries."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LOG_FILE = Path("logs/rag_queries.json")


def log_query(entry: Dict[str, Any]) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    history: List[Dict[str, Any]] = []
    if LOG_FILE.exists():
        try:
            history = json.loads(LOG_FILE.read_text())
        except Exception:
            history = []
    history.append(entry)
    LOG_FILE.write_text(json.dumps(history[-200:], indent=2))


def load_logs(limit: int = 20) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text())
        return data[-limit:]
    except Exception:
        return []


def create_entry(query: str, sources: List[str], summary: str, model: str) -> Dict[str, Any]:
    return {
        "query": query,
        "sources_used": sources,
        "results_summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
    }
