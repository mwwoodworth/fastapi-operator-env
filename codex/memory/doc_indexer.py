from __future__ import annotations

"""Simple document indexer for local markdown files."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DOC_DIR = Path(os.getenv("KNOWLEDGE_DOC_DIR", "data/docs"))
INDEX_FILE = DOC_DIR.parent / "doc_index.json"


def index_documents() -> List[Dict[str, Any]]:
    """Load markdown files and store a basic index."""
    docs: List[Dict[str, Any]] = []
    if not DOC_DIR.exists():
        return docs
    for path in DOC_DIR.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        docs.append({"path": str(path), "text": text})
    INDEX_FILE.write_text(json.dumps(docs, indent=2))
    return docs


def search(query: str) -> List[Dict[str, Any]]:
    """Return docs containing the query string."""
    if not INDEX_FILE.exists():
        index_documents()
    try:
        entries = json.loads(INDEX_FILE.read_text())
    except Exception:
        return []
    results: List[Dict[str, Any]] = []
    q = query.lower()
    for item in entries:
        text = item.get("text", "")
        if q in text.lower():
            results.append(
                {
                    "id": item.get("path"),
                    "title": Path(item.get("path")).stem,
                    "text": text[:500],
                    "tags": [],
                    "source_url": item.get("path"),
                }
            )
    return results


def list_sources() -> List[str]:
    if not INDEX_FILE.exists():
        return []
    try:
        entries = json.loads(INDEX_FILE.read_text())
        return [e.get("path") for e in entries]
    except Exception:
        return []
