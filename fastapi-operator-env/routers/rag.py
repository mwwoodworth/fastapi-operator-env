"""RAG (Retrieval-Augmented Generation) endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.security import get_current_user
from core.rag import RAGEngine, chunk_text, extract_metadata_from_content
from db.models import User, Document
from db.session import get_db

router = APIRouter(prefix="/rag", tags=["RAG System"])


class DocumentCreate(BaseModel):
    """Document creation model."""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source: str = Field(default="manual", max_length=255)
    source_url: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(default="general", max_length=100)
    tags: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Roofing Best Practices Guide",
                "content": "This guide covers essential roofing techniques...",
                "source": "manual",
                "category": "roofing",
                "tags": ["guide", "best-practices"]
            }
        }


class DocumentResponse(BaseModel):
    """Document response model."""
    id: int
    title: str
    content: str
    source: str
    source_url: Optional[str]
    category: str
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    category: Optional[str] = None
    search_type: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    include_content: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How to install metal roofing?",
                "limit": 10,
                "category": "roofing",
                "search_type": "hybrid"
            }
        }


class SearchResult(BaseModel):
    """Search result model."""
    id: int
    title: str
    content: Optional[str]
    source: str
    source_url: Optional[str]
    category: str
    tags: List[str]
    similarity: Optional[float]
    score: Optional[float]
    snippet: Optional[str]


class RAGContextRequest(BaseModel):
    """RAG context generation request."""
    query: str = Field(..., min_length=1, max_length=1000)
    max_context_length: int = Field(default=4000, ge=100, le=10000)
    include_metadata: bool = True


@router.post("/documents", response_model=DocumentResponse)
async def create_document(
    document: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new document in the RAG system.
    
    The document will be automatically embedded for semantic search.
    """
    rag = RAGEngine(db, current_user.id)
    
    # Extract additional metadata
    auto_metadata = extract_metadata_from_content(document.content)
    combined_metadata = {**auto_metadata, **document.metadata}
    
    # Create document
    doc = await rag.add_document(
        title=document.title,
        content=document.content,
        source=document.source,
        source_url=document.source_url,
        category=document.category,
        tags=document.tags,
        metadata=combined_metadata
    )
    
    return DocumentResponse.from_orm(doc)


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("general"),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a document file to the RAG system.
    
    Supported formats: .txt, .md, .pdf
    """
    # Validate file type
    allowed_types = {".txt", ".md", ".pdf"}
    file_ext = "." + file.filename.split(".")[-1].lower()
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Read file content
    content = await file.read()
    text_content = content.decode("utf-8")
    
    # Use filename as title if not provided
    if not title:
        title = file.filename
    
    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
    
    # Create document
    rag = RAGEngine(db, current_user.id)
    doc = await rag.add_document(
        title=title,
        content=text_content,
        source="upload",
        source_url=f"file://{file.filename}",
        category=category,
        tags=tag_list,
        metadata={"filename": file.filename, "size": len(content)}
    )
    
    return DocumentResponse.from_orm(doc)


@router.post("/documents/batch", response_model=List[DocumentResponse])
async def create_documents_batch(
    documents: List[DocumentCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create multiple documents in batch.
    
    Maximum 50 documents per batch.
    """
    if len(documents) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 documents per batch"
        )
    
    rag = RAGEngine(db, current_user.id)
    
    # Prepare documents
    doc_data = []
    for doc in documents:
        auto_metadata = extract_metadata_from_content(doc.content)
        combined_metadata = {**auto_metadata, **doc.metadata}
        
        doc_data.append({
            "title": doc.title,
            "content": doc.content,
            "source": doc.source,
            "source_url": doc.source_url,
            "category": doc.category,
            "tags": doc.tags,
            "metadata": combined_metadata
        })
    
    # Batch create
    results = await rag.batch_add_documents(doc_data)
    
    # Filter out errors and return successful documents
    successful_docs = [r for r in results if not isinstance(r, Exception)]
    
    if len(successful_docs) < len(documents):
        # Some documents failed
        failed_count = len(documents) - len(successful_docs)
        raise HTTPException(
            status_code=207,  # Multi-Status
            detail=f"{failed_count} documents failed to create",
            headers={"X-Failed-Count": str(failed_count)}
        )
    
    return [DocumentResponse.from_orm(doc) for doc in successful_docs]


@router.post("/search", response_model=List[SearchResult])
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search documents using semantic, keyword, or hybrid search.
    
    - **semantic**: Uses vector similarity search
    - **keyword**: Uses PostgreSQL full-text search
    - **hybrid**: Combines both methods with weighted scores
    """
    rag = RAGEngine(db, current_user.id)
    
    if request.search_type == "semantic":
        results = await rag.search_documents(
            query=request.query,
            limit=request.limit,
            category=request.category,
            similarity_threshold=request.similarity_threshold
        )
    elif request.search_type == "hybrid":
        results = await rag.hybrid_search(
            query=request.query,
            limit=request.limit
        )
    else:
        # Keyword search - implement separately
        raise HTTPException(
            status_code=501,
            detail="Pure keyword search not yet implemented"
        )
    
    # Format results
    search_results = []
    for result in results:
        # Create snippet if content included
        snippet = None
        if request.include_content and result["content"]:
            # Find relevant snippet around query terms
            content_lower = result["content"].lower()
            query_lower = request.query.lower()
            query_words = query_lower.split()
            
            # Find first occurrence of any query word
            best_pos = len(content_lower)
            for word in query_words:
                pos = content_lower.find(word)
                if pos != -1 and pos < best_pos:
                    best_pos = pos
            
            # Extract snippet around position
            if best_pos < len(content_lower):
                start = max(0, best_pos - 100)
                end = min(len(result["content"]), best_pos + 200)
                snippet = "..." + result["content"][start:end] + "..."
        
        search_results.append(SearchResult(
            id=result["id"],
            title=result["title"],
            content=result["content"] if request.include_content else None,
            source=result["source"],
            source_url=result["source_url"],
            category=result["category"],
            tags=result["tags"],
            similarity=result.get("similarity"),
            score=result.get("combined_score"),
            snippet=snippet
        ))
    
    return search_results


@router.post("/context")
async def generate_context(
    request: RAGContextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate context for a prompt using RAG.
    
    This endpoint searches for relevant documents and formats them
    as context for use with AI models.
    """
    rag = RAGEngine(db, current_user.id)
    
    context = await rag.get_context_for_prompt(
        query=request.query,
        max_context_length=request.max_context_length,
        include_metadata=request.include_metadata
    )
    
    return {
        "query": request.query,
        "context": context,
        "context_length": len(context)
    }


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = None,
    source: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List documents in the RAG system.
    """
    query = db.query(Document).filter(Document.user_id == current_user.id)
    
    if category:
        query = query.filter(Document.category == category)
    if source:
        query = query.filter(Document.source == source)
    
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    
    return [DocumentResponse.from_orm(doc) for doc in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific document.
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse.from_orm(document)


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    update: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a document and regenerate its embedding.
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Update fields
    document.title = update.title
    document.content = update.content
    document.source = update.source
    document.source_url = update.source_url
    document.category = update.category
    document.tags = update.tags
    
    # Update metadata
    auto_metadata = extract_metadata_from_content(update.content)
    document.metadata = {**auto_metadata, **update.metadata}
    
    document.updated_at = datetime.utcnow()
    
    # Regenerate embedding
    rag = RAGEngine(db, current_user.id)
    await rag.update_document_embedding(document_id)
    
    db.commit()
    db.refresh(document)
    
    return DocumentResponse.from_orm(document)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document from the RAG system.
    """
    rag = RAGEngine(db, current_user.id)
    await rag.delete_document(document_id)
    
    return {"message": "Document deleted successfully"}


@router.get("/stats")
async def get_rag_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about documents in the RAG system.
    """
    rag = RAGEngine(db, current_user.id)
    stats = await rag.get_document_stats()
    
    return stats