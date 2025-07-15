"""Assistant data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions the assistant can perform."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_CREATE = "file_create"
    COMMAND_EXECUTE = "command_execute"
    TASK_CREATE = "task_create"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    WORKFLOW_RUN = "workflow_run"
    WORKFLOW_CREATE = "workflow_create"
    AI_QUERY = "ai_query"
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_ADD = "knowledge_add"
    CODE_REVIEW = "code_review"
    TEST_RUN = "test_run"
    DEPLOY = "deploy"
    BACKUP = "backup"
    RESTORE = "restore"


class AssistantAction(BaseModel):
    """An action performed by the assistant."""
    type: ActionType
    status: str  # pending, completed, failed, blocked
    details: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confirmation_required: bool = False
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None


class AssistantMessage(BaseModel):
    """A message in the assistant conversation."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: str = "chat"  # chat, command, voice, action
    actions: Optional[List[AssistantAction]] = None
    attachments: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class AssistantSession(BaseModel):
    """An assistant interaction session."""
    id: str
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    messages: List[AssistantMessage] = []
    context: Dict[str, Any] = {}
    active: bool = True
    mode: str = "chat"  # chat, voice, api
    
    def add_message(self, message: AssistantMessage):
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def end_session(self):
        """End the session."""
        self.active = False
        self.ended_at = datetime.utcnow()


class Task(BaseModel):
    """A task managed by the assistant."""
    id: str
    title: str
    description: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, cancelled
    priority: str = "medium"  # low, medium, high, urgent
    assigned_to: Optional[str] = None
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: List[str] = []
    dependencies: List[str] = []  # Task IDs
    subtasks: List[str] = []  # Task IDs
    attachments: List[str] = []
    metadata: Dict[str, Any] = {}


class Workflow(BaseModel):
    """A workflow automation."""
    id: str
    name: str
    description: Optional[str] = None
    trigger: Dict[str, Any]  # webhook, schedule, event, manual
    steps: List[Dict[str, Any]]
    enabled: bool = True
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = {}


class KnowledgeEntry(BaseModel):
    """An entry in the knowledge base."""
    id: str
    title: str
    content: str
    type: str  # document, code, procedure, reference
    category: str
    tags: List[str] = []
    source: Optional[str] = None
    embedding: Optional[List[float]] = None
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class WorkflowRun(BaseModel):
    """A workflow run instance."""
    id: str
    workflow_id: str
    triggered_by: str
    trigger_data: Dict[str, Any] = {}
    status: str  # pending, running, completed, failed, cancelled
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    step_results: List[Dict[str, Any]] = []
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AuditLog(BaseModel):
    """An audit log entry."""
    id: str
    user_id: int
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    success: bool = True
    error: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VoiceCommand(BaseModel):
    """A voice command."""
    id: str
    user_id: int
    transcript: str
    confidence: float
    intent: Optional[str] = None
    entities: Dict[str, Any] = {}
    action_taken: Optional[AssistantAction] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    audio_file: Optional[str] = None
    duration_seconds: Optional[float] = None