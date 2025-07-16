"""
Pydantic models for BrainOps memory system.

Defines data structures for memory entries, knowledge documents, and
retrieval operations. Built to ensure type safety and data validation
across the memory subsystem.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, validator, constr


# Type definitions for clarity
EmbeddingVector = List[float]
ContentType = Literal["document", "conversation", "note", "task_result", "web_content"]
DocumentType = Literal["sop", "template", "guide", "reference", "analysis", "report"]


# Re-added by Codex for import fix
class MemoryType(str, Enum):
    TASK_EXECUTION = "task_execution"
    PRODUCT_DOCUMENTATION = "product_documentation"
    BUSINESS_CONTEXT = "business_context"
    ESTIMATE_RECORD = "estimate_record"


# Re-added by Codex for import fix
class KnowledgeCategory(str, Enum):
    ROOFING = "roofing"
    PROJECT_MANAGEMENT = "project_management"
    AUTOMATION = "automation"


class MemoryEntry(BaseModel):
    """
    Core memory entry for RAG system.
    
    Represents a single piece of retrievable knowledge with
    semantic embedding for similarity search.
    """
    id: Optional[UUID] = None
    user_id: UUID
    content: constr(min_length=1, max_length=10000) = Field(
        ...,
        description="The actual content to be stored and retrieved"
    )
    content_type: ContentType = Field(
        "note",
        description="Type of content for filtering and processing"
    )
    embedding: Optional[EmbeddingVector] = Field(
        None,
        description="Vector embedding for semantic search"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata for filtering and context"
    )
    source_url: Optional[str] = Field(
        None,
        description="Original source URL if applicable"
    )
    is_active: bool = Field(
        True,
        description="Whether this entry should be included in searches"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator("embedding")
    def validate_embedding_dimension(cls, v):
        """Ensure embedding matches expected dimension."""
        if v is not None and len(v) != 1536:  # OpenAI text-embedding-3-small
            raise ValueError(f"Embedding must be 1536 dimensions, got {len(v)}")
        return v
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class KnowledgeDocument(BaseModel):
    """
    Structured document for knowledge base.
    
    Represents larger documents that get chunked for retrieval,
    maintaining document-level metadata and relationships.
    """
    id: Optional[UUID] = None
    user_id: UUID
    title: constr(min_length=1, max_length=500) = Field(
        ...,
        description="Document title for identification"
    )
    content: constr(min_length=1) = Field(
        ...,
        description="Full document content"
    )
    document_type: DocumentType = Field(
        ...,
        description="Category of document for organization"
    )
    file_path: Optional[str] = Field(
        None,
        description="Original file path if uploaded"
    )
    file_hash: Optional[str] = Field(
        None,
        description="SHA256 hash for deduplication"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level metadata"
    )
    is_published: bool = Field(
        False,
        description="Whether document is ready for use"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator("file_hash")
    def validate_hash_format(cls, v):
        """Ensure hash is valid SHA256 format."""
        if v and len(v) != 64:
            raise ValueError("File hash must be 64 characters (SHA256)")
        return v


class DocumentChunk(BaseModel):
    """
    Chunked segment of a knowledge document.
    
    Represents a searchable portion of a larger document,
    optimized for embedding and retrieval operations.
    """
    id: Optional[UUID] = None
    document_id: UUID
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Sequential index within document"
    )
    content: constr(min_length=1, max_length=5000) = Field(
        ...,
        description="Chunk text content"
    )
    embedding: Optional[EmbeddingVector] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chunk-specific metadata"
    )
    created_at: Optional[datetime] = None
    
    @validator("embedding")
    def validate_embedding_dimension(cls, v):
        """Ensure embedding matches expected dimension."""
        if v is not None and len(v) != 1536:
            raise ValueError(f"Embedding must be 1536 dimensions, got {len(v)}")
        return v


class MemorySearchQuery(BaseModel):
    """
    Search query for memory retrieval.
    
    Defines parameters for semantic search operations with
    filtering and relevance controls.
    """
    query: constr(min_length=1, max_length=1000) = Field(
        ...,
        description="Natural language search query"
    )
    user_id: Optional[UUID] = Field(
        None,
        description="Filter by user (None for global search)"
    )
    content_types: Optional[List[ContentType]] = Field(
        None,
        description="Filter by content types"
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum results to return"
    )
    similarity_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score"
    )
    include_metadata: bool = Field(
        True,
        description="Whether to include metadata in results"
    )
    date_from: Optional[datetime] = Field(
        None,
        description="Filter results after this date"
    )
    date_to: Optional[datetime] = Field(
        None,
        description="Filter results before this date"
    )


# Re-added by Codex for import fix
class MemoryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# Re-added by Codex for import fix
class QueryResult(BaseModel):
    id: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Re-added by Codex for import fix
class DocumentMetadata(BaseModel):
    source: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# Re-added by Codex for import fix
class RetrievalSession(BaseModel):
    session_id: str
    user_id: str


class MemorySearchResult(BaseModel):
    """
    Single search result from memory retrieval.
    
    Provides matched content with relevance scoring and
    context for result interpretation.
    """
    entry_id: UUID
    content: str
    content_type: ContentType
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity to query"
    )
    metadata: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None
    created_at: datetime
    
    # Additional context for knowledge documents
    document_id: Optional[UUID] = None
    document_title: Optional[str] = None
    chunk_index: Optional[int] = None


class MemoryWriteRequest(BaseModel):
    """
    Request to write new memory entry.
    
    Validates content before storage and embedding generation,
    ensuring data quality in the memory system.
    """
    content: constr(min_length=10, max_length=10000) = Field(
        ...,
        description="Content to store in memory"
    )
    content_type: ContentType = Field(
        "note",
        description="Type of content being stored"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context and tags"
    )
    source_url: Optional[str] = Field(
        None,
        description="Source reference if applicable"
    )
    
    @validator("metadata")
    def validate_metadata_size(cls, v):
        """Ensure metadata doesn't exceed reasonable size."""
        import json
        if len(json.dumps(v)) > 5000:
            raise ValueError("Metadata too large (max 5KB)")
        return v


class MemoryUpdateRequest(BaseModel):
    """
    Request to update existing memory entry.
    
    Allows partial updates while maintaining data integrity
    and triggering re-embedding when content changes.
    """
    entry_id: UUID
    content: Optional[str] = Field(
        None,
        min_length=10,
        max_length=10000,
        description="New content (triggers re-embedding)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata updates (merged with existing)"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Enable/disable entry in searches"
    )


class MemorySession(BaseModel):
    """
    Represents a memory interaction session.
    
    Groups related memory operations for context tracking
    and conversation continuity.
    """
    session_id: constr(min_length=1, max_length=100)
    user_id: UUID
    started_at: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session context and state"
    )
    interaction_count: int = Field(
        0,
        ge=0,
        description="Number of interactions in session"
    )
    
    def increment_interaction(self):
        """Track interaction within session."""
        self.interaction_count += 1


class DocumentIngestionRequest(BaseModel):
    """
    Request to ingest document into knowledge base.
    
    Validates document before chunking and embedding,
    ensuring quality knowledge ingestion.
    """
    title: constr(min_length=1, max_length=500)
    content: constr(min_length=100) = Field(
        ...,
        description="Document content (min 100 chars)"
    )
    document_type: DocumentType
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata and tags"
    )
    file_path: Optional[str] = None
    auto_publish: bool = Field(
        True,
        description="Automatically publish after ingestion"
    )
    
    @validator("content")
    def validate_content_quality(cls, v):
        """Basic content quality checks."""
        # Check for minimum word count
        word_count = len(v.split())
        if word_count < 20:
            raise ValueError(f"Content too short: {word_count} words (minimum 20)")
        
        # Check for excessive repetition (possible corruption)
        words = v.lower().split()
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:
            raise ValueError("Content appears corrupted (too repetitive)")
        
        return v


class KnowledgeSearchQuery(BaseModel):
    """
    Specialized search query for knowledge documents.
    
    Extends basic search with document-specific filters
    and multi-chunk context retrieval.
    """
    query: constr(min_length=1, max_length=1000)
    user_id: Optional[UUID] = None
    document_types: Optional[List[DocumentType]] = None
    limit: int = Field(10, ge=1, le=50)
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)
    include_context: bool = Field(
        False,
        description="Include surrounding chunks for context"
    )
    context_window: int = Field(
        2,
        ge=0,
        le=5,
        description="Chunks before/after match to include"
    )


# Aggregated models for API responses
class MemoryStatsResponse(BaseModel):
    """Memory system statistics for monitoring."""
    total_entries: int
    total_documents: int
    total_chunks: int
    storage_size_mb: float
    active_sessions: int
    recent_searches: int
    avg_similarity_score: float


class MemoryHealthResponse(BaseModel):
    """Health check response for memory system."""
    status: Literal["healthy", "degraded", "unhealthy"]
    database_connected: bool
    embedding_service_available: bool
    avg_search_latency_ms: float
    issues: List[str] = Field(default_factory=list)


# Re-added by Codex for import fix
class User(BaseModel):
    id: str
    email: str
    hashed_password: Optional[str] = None


# Re-added by Codex for import fix
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Re-added by Codex for import fix
class TaskRecord(BaseModel):
    id: str
    user_id: str
    task_type: str
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# Re-added by Codex for import fix
class UserCreate(BaseModel):
    email: str
    password: str


# Re-added by Codex for import fix
class UserLogin(BaseModel):
    email: str
    password: str


# Re-added by Codex for import fix
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 3600



