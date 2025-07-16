"""
Memory and Knowledge Management Routes

This module provides endpoints for the RAG (Retrieval-Augmented Generation) system,
allowing storage, retrieval, and querying of business knowledge, task history,
and contextual information for AI agents.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from apps.backend.core.security import get_current_user
from apps.backend.memory.models import (
    User, MemoryEntry, DocumentChunk, QueryResult,
    MemoryType, DocumentMetadata
)
from apps.backend.memory.memory_store import (
    save_memory_entry,
    query_memories,
    get_memory_entry,
    update_memory_entry,
    delete_memory_entry
)
from apps.backend.memory.knowledge import (
    process_document,
    semantic_search,
    hybrid_search,
    get_relevant_context
)
from apps.backend.memory.backend_memory_vector_utils import generate_embedding


router = APIRouter()


@router.post("/write")
async def write_memory(
    content: str,
    memory_type: MemoryType,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Write a new memory entry to the knowledge base.
    
    Stores contextual information, decisions, insights, or any business
    knowledge that should be retained for future AI agent operations.
    """
    # Generate embedding for semantic search capability
    embedding = await generate_embedding(content)
    
    # Create memory entry with rich metadata
    memory_entry = MemoryEntry(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        content=content,
        title=title or f"{memory_type.value} - {datetime.utcnow().strftime('%Y-%m-%d')}",
        memory_type=memory_type,
        tags=tags or [],
        metadata=metadata or {},
        embedding=embedding,
        created_at=datetime.utcnow()
    )
    
    # Persist to vector database with full-text search indexing
    saved_entry = await save_memory_entry(memory_entry)
    
    return {
        "memory_id": saved_entry.id,
        "title": saved_entry.title,
        "type": saved_entry.memory_type.value,
        "created_at": saved_entry.created_at.isoformat(),
        "message": "Memory successfully stored"
    }


@router.post("/query")
async def query_memory(
    query: str,
    memory_types: Optional[List[MemoryType]] = None,
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    use_hybrid: bool = False,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Query memories using semantic search with optional filters.
    
    Retrieves relevant memories based on semantic similarity to the query,
    with support for filtering by memory type and hybrid search modes.
    """
    # Perform semantic or hybrid search based on parameters
    if use_hybrid:
        results = await hybrid_search(
            query=query,
            user_id=current_user.id,
            memory_types=memory_types,
            limit=limit,
            similarity_threshold=threshold
        )
    else:
        results = await semantic_search(
            query=query,
            user_id=current_user.id,
            memory_types=memory_types,
            limit=limit,
            similarity_threshold=threshold
        )
    
    # Format results with relevance scores and metadata
    formatted_results = [
        {
            "memory_id": result.id,
            "title": result.title,
            "content": result.content,
            "type": result.memory_type.value,
            "relevance_score": result.similarity_score,
            "created_at": result.created_at.isoformat(),
            "tags": result.tags,
            "metadata": result.metadata
        }
        for result in results
    ]
    
    return {
        "query": query,
        "results": formatted_results,
        "count": len(formatted_results),
        "search_type": "hybrid" if use_hybrid else "semantic"
    }


@router.post("/context")
async def get_agent_context(
    task_type: str,
    parameters: Dict[str, Any],
    max_tokens: int = Query(2000, ge=100, le=8000),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retrieve relevant context for AI agent operations.
    
    Assembles contextual information from memories, documents, and task history
    to provide comprehensive background for AI task execution.
    """
    # Build context query from task parameters
    context_query = f"Task: {task_type}\n"
    for key, value in parameters.items():
        context_query += f"{key}: {value}\n"
    
    # Retrieve relevant memories, documents, and historical context
    context_data = await get_relevant_context(
        query=context_query,
        user_id=current_user.id,
        task_type=task_type,
        max_tokens=max_tokens
    )
    
    return {
        "task_type": task_type,
        "context": {
            "memories": context_data.memories,
            "documents": context_data.documents,
            "task_history": context_data.task_history,
            "total_tokens": context_data.token_count
        },
        "assembled_at": datetime.utcnow().isoformat()
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Upload and process a document for knowledge extraction.
    
    Chunks documents intelligently and creates searchable embeddings
    for each chunk to enable granular retrieval.
    """
    # Validate file type and size
    allowed_types = [".pdf", ".txt", ".md", ".docx", ".json"]
    file_ext = file.filename.lower().split('.')[-1]
    
    if f".{file_ext}" not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: {', '.join(allowed_types)}"
        )
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 10MB limit"
        )
    
    # Read file content
    content = await file.read()
    
    # Process document into chunks with embeddings
    document_metadata = DocumentMetadata(
        filename=file.filename,
        title=title or file.filename,
        file_type=file_ext,
        size_bytes=file.size,
        tags=tags or [],
        user_id=current_user.id,
        uploaded_at=datetime.utcnow()
    )
    
    chunks = await process_document(
        content=content,
        metadata=document_metadata,
        chunk_size=1000,
        chunk_overlap=200
    )
    
    return {
        "document_id": document_metadata.id,
        "filename": file.filename,
        "chunks_created": len(chunks),
        "total_tokens": sum(chunk.token_count for chunk in chunks),
        "message": "Document successfully processed and indexed"
    }


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retrieve a specific memory entry by ID.
    
    Returns full memory content with all metadata and relationships.
    """
    memory = await get_memory_entry(memory_id, current_user.id)
    
    if not memory:
        raise HTTPException(404, "Memory entry not found")
    
    return {
        "memory_id": memory.id,
        "title": memory.title,
        "content": memory.content,
        "type": memory.memory_type.value,
        "tags": memory.tags,
        "metadata": memory.metadata,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None
    }


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    content: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update an existing memory entry.
    
    Allows partial updates while maintaining version history and
    regenerating embeddings if content changes.
    """
    # Get existing memory
    existing_memory = await get_memory_entry(memory_id, current_user.id)
    
    if not existing_memory:
        raise HTTPException(404, "Memory entry not found")
    
    # Build update data
    update_data = {}
    if content is not None:
        update_data["content"] = content
        # Regenerate embedding for new content
        update_data["embedding"] = await generate_embedding(content)
    
    if title is not None:
        update_data["title"] = title
    
    if tags is not None:
        update_data["tags"] = tags
    
    if metadata is not None:
        update_data["metadata"] = {**existing_memory.metadata, **metadata}
    
    # Apply updates with timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    updated_memory = await update_memory_entry(memory_id, update_data)
    
    return {
        "memory_id": updated_memory.id,
        "message": "Memory successfully updated",
        "updated_fields": list(update_data.keys())
    }


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Delete a memory entry.
    
    Performs soft delete to maintain referential integrity while
    removing from active searches.
    """
    success = await delete_memory_entry(memory_id, current_user.id)
    
    if not success:
        raise HTTPException(404, "Memory entry not found")
    
    return {"message": "Memory successfully deleted"}
