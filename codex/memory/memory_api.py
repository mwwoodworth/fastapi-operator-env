from __future__ import annotations

"""REST API for memory operations."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from core.settings import Settings
import uuid

from . import memory_store
from .memory_utils import (
    get_or_create_project,
    get_or_create_agent,
    chunk_text,
    embed_chunks,
    save_document,
    update_document,
)

router = APIRouter()

settings = Settings()
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_SERVICE_KEY

try:
    from supabase import create_client

    supabase = (
        create_client(SUPABASE_URL, SUPABASE_KEY)
        if SUPABASE_URL and SUPABASE_KEY
        else None
    )
except Exception:  # noqa: BLE001
    supabase = None


class QueryInput(BaseModel):
    query: str
    project_id: Optional[str] = None
    top_k: int = 5


class WriteInput(BaseModel):
    project_id: str
    title: str
    content: str
    author_id: str


class UpdateInput(BaseModel):
    document_id: str
    content: str


class RelayInput(BaseModel):
    type: str
    payload: dict


class GeminiRowInput(BaseModel):
    values: List[str]


@router.post("/memory/query")
async def query_memory(payload: QueryInput) -> dict:
    """Vector search fallback to keyword match."""
    results: List[dict] = []
    if supabase:
        try:  # pragma: no cover - network
            params = {
                "query_text": payload.query,
                "match_count": payload.top_k,
            }
            if payload.project_id:
                params["project_id"] = payload.project_id
            res = supabase.rpc("match_documents", params).execute()
            results = list(res.data or [])
        except Exception:  # noqa: BLE001
            results = []
    if not results:
        results = memory_store.search(payload.query, limit=payload.top_k)
    return {"results": results}


@router.post("/memory/write")
async def write_memory(payload: WriteInput) -> dict:
    """Create project/agent if needed and store document chunks."""
    project_id = get_or_create_project(payload.project_id)
    agent_id = get_or_create_agent(payload.author_id, "user")
    doc_id = str(uuid.uuid4())
    chunks = chunk_text(payload.content)
    vectors = embed_chunks(chunks)
    save_document(doc_id, project_id, payload.title, payload.content, agent_id)
    for idx, chunk in enumerate(chunks):
        memory_store.save_memory(
            {
                "task": "memory_chunk",
                "project_id": project_id,
                "agent_id": agent_id,
                "document_id": doc_id,
                "chunk_index": idx,
                "output": chunk,
                "embedding": vectors[idx],
                "title": payload.title,
            }
        )
    return {"document_id": doc_id, "chunks": len(chunks)}


@router.post("/memory/update")
async def update_memory(payload: UpdateInput) -> dict:
    """Replace document content and re-embed."""
    update_document(payload.document_id, payload.content)
    chunks = chunk_text(payload.content)
    vectors = embed_chunks(chunks)
    for idx, chunk in enumerate(chunks):
        memory_store.save_memory(
            {
                "task": "memory_chunk_update",
                "document_id": payload.document_id,
                "chunk_index": idx,
                "output": chunk,
                "embedding": vectors[idx],
            }
        )
    return {"status": "updated", "chunks": len(chunks)}


@router.post("/memory/relay")
async def relay_handler(payload: RelayInput) -> dict:
    """Generic relay endpoint for external sources."""
    entry = {"task": payload.type, "payload": payload.payload}
    memory_store.save_memory(entry)
    return {"status": "logged"}


@router.post("/memory/gemini-sync")
async def gemini_sync(payload: GeminiRowInput) -> dict:
    """Handle Google Sheets webhook rows from Gemini."""
    title = payload.values[0] if payload.values else "gemini"
    content = "\n".join(payload.values)
    data = WriteInput(
        project_id="gemini_sheet",
        title=title,
        content=content,
        author_id="gemini",
    )
    await write_memory(data)
    return {"status": "synced"}
