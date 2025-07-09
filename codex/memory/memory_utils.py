from __future__ import annotations

"""Helper utilities for memory management and embeddings."""

import json
import os
import uuid
import hashlib
from pathlib import Path
from typing import List, Dict

try:
    from supabase import create_client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    _client = (
        create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        if SUPABASE_URL and SUPABASE_SERVICE_KEY
        else None
    )
except Exception:  # pragma: no cover - missing dependency
    _client = None

_PROJECT_FILE = Path("logs/projects.json")
_AGENT_FILE = Path("logs/agents.json")
_DOCUMENT_FILE = Path("logs/documents.json")


def _load(path: Path) -> List[Dict[str, str]]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def _save(path: Path, data: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def get_or_create_project(name: str) -> str:
    """Return an existing project id or create a new one."""
    if not name:
        raise ValueError("project name required")
    if _client:
        try:  # pragma: no cover - network
            res = _client.table("projects").select("id").eq("name", name).execute()
            if res.data:
                return res.data[0]["id"]
            new_id = str(uuid.uuid4())
            _client.table("projects").insert({"id": new_id, "name": name}).execute()
            return new_id
        except Exception:  # noqa: BLE001
            pass
    records = _load(_PROJECT_FILE)
    for item in records:
        if item.get("name") == name:
            return item["id"]
    new_id = str(uuid.uuid4())
    records.append({"id": new_id, "name": name})
    _save(_PROJECT_FILE, records)
    return new_id


def get_or_create_agent(name: str, type_: str = "human") -> str:
    """Return existing agent id or create one."""
    if not name:
        raise ValueError("agent name required")
    if _client:
        try:  # pragma: no cover - network
            res = _client.table("agents").select("id").eq("name", name).execute()
            if res.data:
                return res.data[0]["id"]
            new_id = str(uuid.uuid4())
            _client.table("agents").insert({"id": new_id, "name": name, "type": type_}).execute()
            return new_id
        except Exception:  # noqa: BLE001
            pass
    records = _load(_AGENT_FILE)
    for item in records:
        if item.get("name") == name:
            return item["id"]
    new_id = str(uuid.uuid4())
    records.append({"id": new_id, "name": name, "type": type_})
    _save(_AGENT_FILE, records)
    return new_id


def save_document(doc_id: str, project_id: str, title: str, content: str, author_id: str) -> None:
    """Persist basic document metadata."""
    records = _load(_DOCUMENT_FILE)
    records.append(
        {
            "id": doc_id,
            "project_id": project_id,
            "title": title,
            "content": content,
            "author_id": author_id,
        }
    )
    _save(_DOCUMENT_FILE, records)


def update_document(doc_id: str, content: str) -> None:
    records = _load(_DOCUMENT_FILE)
    for item in records:
        if item.get("id") == doc_id:
            item["content"] = content
            break
    _save(_DOCUMENT_FILE, records)


def chunk_text(content: str, size: int = 200) -> List[str]:
    """Split text content into roughly ``size`` word chunks."""
    if not content:
        return []
    words = content.split()
    chunks: List[str] = []
    current: List[str] = []
    for w in words:
        current.append(w)
        if len(current) >= size:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """Return embedding vectors for the provided chunks."""
    vectors: List[List[float]] = []
    try:
        import openai

        if os.getenv("OPENAI_API_KEY"):
            openai.api_key = os.getenv("OPENAI_API_KEY")
            res = openai.Embedding.create(model="text-embedding-ada-002", input=chunks)
            for item in res["data"]:
                vectors.append(item["embedding"])
            return vectors
    except Exception:  # noqa: BLE001
        pass
    for c in chunks:
        digest = hashlib.sha256(c.encode()).digest()[:8]
        vectors.append([float(b) for b in digest])
    return vectors
