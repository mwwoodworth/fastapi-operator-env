"""
SQLAlchemy ORM models for BrainOps database.

Defines the database schema for tasks, memory, agents, and system state.
These models map to tables in the Supabase PostgreSQL database.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text, Integer, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

# SQLAlchemy declarative base for all models
Base = declarative_base()


class TaskExecution(Base):
    """
    Model for tracking task executions in the system.
    
    Stores execution history, parameters, results, and status for all tasks
    triggered through various interfaces (webhooks, UI, scheduled).
    """
    __tablename__ = "task_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    parameters = Column(JSON, default={})
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Execution metadata
    triggered_by = Column(String(100))  # webhook, ui, schedule, agent
    trigger_source = Column(String(200))  # slack, clickup, make, etc.
    execution_time_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    agent_executions = relationship("AgentExecution", back_populates="task_execution")
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_task_status", "task_id", "status"),
        Index("idx_created_at", "created_at"),
    )


class AgentExecution(Base):
    """
    Model for tracking individual agent executions within tasks.
    
    Each task may involve multiple agent calls - this tracks each one
    for debugging, monitoring, and cost tracking.
    """
    __tablename__ = "agent_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_execution_id = Column(UUID(as_uuid=True), ForeignKey("task_executions.id"), nullable=False)
    agent_type = Column(String(50), nullable=False)  # claude, codex, gemini, search
    
    # Agent execution details
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    model_name = Column(String(100))  # e.g., claude-3-opus, gpt-4
    
    # Performance metrics
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Integer, nullable=True)
    cost_cents = Column(Integer, default=0)
    
    # Status tracking
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    task_execution = relationship("TaskExecution", back_populates="agent_executions")


class MemoryEntry(Base):
    """
    Model for the RAG memory system.
    
    Stores all types of memory: conversation history, document chunks,
    system knowledge, and user preferences.
    """
    __tablename__ = "memory_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_type = Column(String(50), nullable=False, index=True)  # conversation, document, knowledge, preference
    
    # Content and metadata
    content = Column(Text, nullable=False)
    meta_data = Column(JSON, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    embedding = Column(JSON, nullable=True)  # Store as JSON array for pgvector
    
    # Context and ownership
    user_id = Column(String(100), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    source = Column(String(200))  # slack, web, api, system
    
    # Timestamps and versioning
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    
    # Search and retrieval
    tags = Column(JSON, default=[])
    importance_score = Column(Integer, default=5)  # 1-10 scale
    
    # Indexes for efficient retrieval
    __table_args__ = (
        Index("idx_memory_type_user", "memory_type", "user_id"),
        Index("idx_session_id", "session_id"),
        Index("idx_importance", "importance_score"),
    )


class WebhookEvent(Base):
    """
    Model for tracking incoming webhook events.
    
    Stores raw webhook data for debugging, replay, and audit purposes.
    """
    __tablename__ = "webhook_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)  # slack, clickup, make, stripe
    event_type = Column(String(100), nullable=False)
    
    # Webhook data
    headers = Column(JSON, default={})
    payload = Column(JSON, nullable=False)
    signature = Column(String(500), nullable=True)
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)
    processing_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Related task execution if triggered
    task_execution_id = Column(UUID(as_uuid=True), ForeignKey("task_executions.id"), nullable=True)


class SystemConfig(Base):
    """
    Model for storing system configuration and feature flags.
    
    Key-value store for runtime configuration that can be updated
    without redeploying the application.
    """
    __tablename__ = "system_config"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    
    # Configuration metadata
    config_type = Column(String(50), default="general")  # general, feature_flag, integration
    is_secret = Column(Boolean, default=False)
    
    # Audit fields
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)