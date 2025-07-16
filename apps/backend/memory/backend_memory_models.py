"""
Memory System Data Models

Pydantic models defining the schema for memory records, documents, 
knowledge entries, and retrieval sessions in the BrainOps system.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4


class MemoryType(str, Enum):
    """Types of memory entries in the system."""
    TASK_EXECUTION = "task_execution"
    PRODUCT_DOCUMENTATION = "product_documentation"
    CUSTOMER_INTERACTION = "customer_interaction"
    SYSTEM_LEARNING = "system_learning"
    BUSINESS_CONTEXT = "business_context"
    ESTIMATE_RECORD = "estimate_record"
    INTEGRATION_EVENT = "integration_event"


class KnowledgeCategory(str, Enum):
    """Categories for organizing knowledge base entries."""
    ROOFING = "roofing"
    PROJECT_MANAGEMENT = "project_management"
    AUTOMATION = "automation"
    PASSIVE_INCOME = "passive_income"
    TECHNICAL_SPECS = "technical_specs"
    BEST_PRACTICES = "best_practices"
    TEMPLATES = "templates"
    MARKET_DATA = "market_data"


class MemoryRecord(BaseModel):
    """
    Base model for all memory entries stored in the system.
    Represents atomic units of knowledge or experience.
    """
    
    id: UUID = Field(default_factory=uuid4)
    type: MemoryType
    category: Optional[KnowledgeCategory] = None
    
    # Content and metadata
    title: str
    content: str
    summary: Optional[str] = None
    
    # Embedding for vector search
    embedding: Optional[List[float]] = None
    embedding_model: str = "text-embedding-ada-002"
    
    # Contextual information
    context: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Relationships
    related_records: List[UUID] = Field(default_factory=list)
    parent_id: Optional[UUID] = None
    
    # Timestamps and versioning
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    
    # Access and importance
    access_count: int = 0
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @validator('summary', always=True)
    def generate_summary(cls, v, values):
        """Auto-generate summary if not provided."""
        if v is None and 'content' in values:
            # Take first 200 characters as summary
            content = values['content']
            return content[:200] + "..." if len(content) > 200 else content
        return v


class DocumentChunk(BaseModel):
    """
    Represents a chunk of a larger document for RAG processing.
    Used for breaking down large documents into searchable segments.
    """
    
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    
    # Content
    text: str
    start_char: int
    end_char: int
    
    # Metadata from parent document
    document_title: str
    document_type: str
    document_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Embedding for similarity search
    embedding: Optional[List[float]] = None
    
    # Chunk metadata
    tokens: Optional[int] = None
    overlap_prev: int = 0
    overlap_next: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeEntry(BaseModel):
    """
    Structured knowledge base entry with enhanced metadata.
    Used for storing curated, validated knowledge.
    """
    
    id: UUID = Field(default_factory=uuid4)
    category: KnowledgeCategory
    
    # Knowledge content
    title: str
    description: str
    body: str
    
    # Structured data (varies by category)
    structured_data: Optional[Dict[str, Any]] = None
    
    # Examples and references
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    
    # Validation and quality
    validated: bool = False
    validation_date: Optional[datetime] = None
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Usage tracking
    usage_count: int = 0
    last_accessed: Optional[datetime] = None
    
    # Versioning
    version: str = "1.0.0"
    previous_versions: List[UUID] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalSession(BaseModel):
    """
    Tracks a memory retrieval session for analytics and optimization.
    """
    
    id: UUID = Field(default_factory=uuid4)
    user_id: Optional[str] = None
    task_id: Optional[str] = None
    
    # Query information
    query: str
    query_embedding: Optional[List[float]] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Results
    retrieved_records: List[UUID] = Field(default_factory=list)
    relevance_scores: List[float] = Field(default_factory=list)
    
    # Performance metrics
    retrieval_time_ms: Optional[int] = None
    reranking_applied: bool = False
    
    # User feedback
    selected_records: List[UUID] = Field(default_factory=list)
    feedback_score: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EstimateRecord(BaseModel):
    """
    Specialized memory record for roofing estimates.
    """
    
    id: UUID = Field(default_factory=uuid4)
    project_name: str
    
    # Project details
    building_type: str
    roof_area_sf: float
    roof_type: str
    system_type: str
    
    # Financial data
    material_cost: float
    labor_cost: float
    total_cost: float
    cost_per_sf: float
    margin_percentage: float
    
    # Scope and specifications
    scope_items: List[str]
    special_conditions: List[str] = Field(default_factory=list)
    warranty_years: int
    
    # Metadata
    location: str
    estimate_date: datetime
    valid_until: datetime
    
    # Status tracking
    status: str = "draft"  # draft, sent, approved, rejected, expired
    won_project: Optional[bool] = None
    actual_cost: Optional[float] = None
    
    # Embedding for similarity search
    embedding: Optional[List[float]] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MemorySearchQuery(BaseModel):
    """
    Query model for searching memory records.
    """
    
    query: str
    memory_types: Optional[List[MemoryType]] = None
    categories: Optional[List[KnowledgeCategory]] = None
    
    # Time filters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Relevance and ranking
    min_relevance_score: float = 0.7
    max_results: int = 10
    
    # Advanced filters
    tags: Optional[List[str]] = None
    importance_threshold: Optional[float] = None
    
    # Search options
    include_embeddings: bool = False
    rerank_results: bool = True


class MemoryUpdate(BaseModel):
    """
    Model for updating existing memory records.
    """
    
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    
    # Metadata updates
    tags: Optional[List[str]] = None
    importance_score: Optional[float] = None
    
    # Context updates
    additional_context: Optional[Dict[str, Any]] = None
    
    # Relationship updates
    add_related_records: Optional[List[UUID]] = None
    remove_related_records: Optional[List[UUID]] = None
    
    # Trigger re-embedding
    regenerate_embedding: bool = False