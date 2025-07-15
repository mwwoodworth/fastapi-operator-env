from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class StatusResponse(BaseModel):
    """Generic status response."""

    status: str


class GenericResponse(BaseModel):
    """Flexible response model allowing arbitrary keys."""

    model_config = ConfigDict(extra="allow")


class ValueResponse(BaseModel):
    value: Any


class TanaNodeCreateResponse(StatusResponse):
    content: str


class TaskRunResponse(BaseModel):
    status: str
    result: Any


class CeleryTaskResponse(BaseModel):
    """Response when a task is queued for Celery execution."""

    task_id: str


class TaskStatusResponse(BaseModel):
    """Current status for an asynchronous task."""

    status: str
    result: Any | None = None


class ChatResponse(BaseModel):
    response: str
    model: str
    suggested_tasks: Optional[List[Dict[str, Any]]] = None
    memory_id: str


class VoiceUploadResponse(BaseModel):
    transcription: str
    tasks: List[Dict[str, Any]]
    id: str


class MemoryEntry(BaseModel):
    id: Optional[str] = None
    task: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    model: Optional[str] = None
    input: Any | None = None
    output: Any | None = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class MemoryEntriesResponse(BaseModel):
    entries: List[MemoryEntry]


class DocumentWriteResponse(BaseModel):
    document_id: str
    chunks: int


class DocumentUpdateResponse(BaseModel):
    status: str
    chunks: int


class QueryResultsResponse(BaseModel):
    results: List[Dict[str, Any]]


class VoiceHistoryEntry(BaseModel):
    id: str
    filename: str
    transcript: str
    timestamp: Optional[str] = None


class VoiceHistoryResponse(BaseModel):
    entries: List[VoiceHistoryEntry]


class VoiceTraceResponse(BaseModel):
    transcript: str
    tasks_triggered: List[str]
    memory_outputs: List[Dict[str, Any]]
    executed_by: Optional[str] = None


class VoiceStatusResponse(BaseModel):
    latest_transcript: str
    task_executed: bool
    memory_link: Optional[str]
    execution_status: str
    processed_by: Optional[str] = None


class MemoryTraceResponse(BaseModel):
    task: Optional[str] = None
    triggered_by: Optional[str] = None
    linked_transcript: Optional[str] = None
    linked_node: Optional[str] = None
    executed_by: Optional[str] = None
    output: Any | None = None


class KnowledgeDocUploadResponse(BaseModel):
    """Response for uploaded knowledge documents."""

    id: Optional[int] = None


class KnowledgeSearchResult(BaseModel):
    id: Optional[int] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    score: Optional[float] = None


class KnowledgeSearchResponse(BaseModel):
    results: List[KnowledgeSearchResult]

