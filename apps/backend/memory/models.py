# Re-added by Claude for import fix
"""Memory models stub."""

from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class User(BaseModel):
    """User model stub."""
    id: str = "test-user"
    email: str = "test@example.com"
    username: Optional[str] = None
    is_active: bool = True
    created_at: datetime = datetime.now()

class TaskStatus(Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskRecord(BaseModel):
    """Task record model stub."""
    id: str
    status: TaskStatus
    user_id: str
    created_at: datetime

class UserCreate(BaseModel):
    """User create model stub."""
    email: str
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    """User login model stub."""
    email: str
    password: str

class TokenResponse(BaseModel):
    """Token response model stub."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

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
    """Memory entry model stub."""
    id: str
    content: str
    type: str
    created_at: datetime

class DocumentChunk(BaseModel):
    """Document chunk model stub."""
    id: str
    content: str
    metadata: Dict[str, Any]

class QueryResult(BaseModel):
    """Query result model stub."""
    chunks: List[DocumentChunk]
    score: float

class MemoryType(Enum):
    """Memory type enum."""
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    TASK = "task"

class DocumentMetadata(BaseModel):
    """Document metadata model stub."""
    filename: str
    size: int
    created_at: datetime

class AgentStatus(BaseModel):
    """Agent status model stub."""
    agent_id: str
    status: str
    last_active: datetime

class ApprovalRequest(BaseModel):
    """Approval request model stub."""
    id: str
    agent_id: str
    action: str
    created_at: datetime

class PipelineConfig(BaseModel):
    """Pipeline config model stub."""
    id: str
    name: str
    steps: List[Dict[str, Any]]
