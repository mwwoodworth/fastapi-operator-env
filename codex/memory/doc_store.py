from __future__ import annotations

"""Utility helpers for storing knowledge documents with embeddings."""

from typing import Any, Dict, List, Optional
import json

from pathlib import Path

from .memory_utils import chunk_text, embed_chunks

try:
    from supabase_client import supabase
except Exception:  # pragma: no cover - missing deps
    supabase = None

DOC_INDEX = Path("data/docs/doc_index.json")


def _load_index() -> List[Dict[str, Any]]:
    if not DOC_INDEX.exists():
        return []
    try:
        return json.loads(DOC_INDEX.read_text())
    except Exception:  # noqa: BLE001
        return []


def _save_index(data: List[Dict[str, Any]]) -> None:
    DOC_INDEX.parent.mkdir(parents=True, exist_ok=True)
    DOC_INDEX.write_text(json.dumps(data, indent=2))


def embed_and_store(content: str, metadata: Optional[Dict[str, Any]] = None) -> List[int]:
    """Embed the provided content and store chunks in the documents table.

    Returns a list of inserted row IDs when Supabase is available. Local fallback
    will append entries to ``doc_index.json`` and return sequential indices.
    """

    metadata = metadata or {}
    chunks = chunk_text(content)
    vectors = embed_chunks(chunks)
    inserted: List[int] = []

    if supabase:
        for chunk, vec in zip(chunks, vectors):
            try:  # pragma: no cover - network
                res = (
                    supabase.table("documents")
                    .insert({"content": chunk, "metadata": metadata, "embedding": vec})
                    .execute()
                )
                if res.data:
                    inserted.append(res.data[0].get("id"))
            except Exception:  # noqa: BLE001
                continue
    else:
        entries = _load_index()
        for chunk in chunks:
            entries.append({"path": f"local_{len(entries)}", "text": chunk})
            inserted.append(len(entries))
        _save_index(entries)

    return inserted
