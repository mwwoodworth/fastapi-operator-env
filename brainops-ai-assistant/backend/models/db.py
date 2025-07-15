"""Database models for BrainOps AI Assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    sessions = relationship("AssistantSessionDB", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    tasks = relationship("TaskDB", back_populates="created_by_user")
    workflows = relationship("WorkflowDB", back_populates="created_by_user")
    knowledge_entries = relationship("KnowledgeEntryDB", back_populates="created_by_user")


class AssistantSessionDB(Base):
    """Assistant session model."""
    __tablename__ = "assistant_sessions"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = Column(DateTime)
    context = Column(JSON, default=dict)
    active = Column(Boolean, default=True)
    mode = Column(String(20), default="chat")  # chat, voice, api
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("AssistantMessageDB", back_populates="session")


class AssistantMessageDB(Base):
    """Assistant message model with vector search support."""
    __tablename__ = "assistant_messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("assistant_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_type = Column(String(20), default="chat")  # chat, command, voice, action
    attachments = Column(JSON, default=list)
    meta_data = Column(JSON, default=dict)
    context = Column(JSON, default=dict)
    embedding = Column(Vector(1536))  # OpenAI embedding dimension for semantic search
    
    # Relationships
    session = relationship("AssistantSessionDB", back_populates="messages")
    actions = relationship("AssistantActionDB", back_populates="message")

    __table_args__ = (
        Index("ix_assistant_messages_embedding", "embedding", postgresql_using="ivfflat"),
        Index("ix_assistant_messages_timestamp", "timestamp"),
        Index("ix_assistant_messages_session_timestamp", "session_id", "timestamp"),
    )


class AssistantActionDB(Base):
    """Assistant action model."""
    __tablename__ = "assistant_actions"
    
    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), ForeignKey("assistant_messages.id"), nullable=False)
    type = Column(String(50), nullable=False)  # ActionType enum values
    status = Column(String(20), nullable=False)  # pending, completed, failed, blocked
    details = Column(JSON, default=dict)
    result = Column(JSON)
    error = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confirmation_required = Column(Boolean, default=False)
    confirmed_by = Column(Integer, ForeignKey("users.id"))
    confirmed_at = Column(DateTime)
    
    # Relationships
    message = relationship("AssistantMessageDB", back_populates="actions")


class TaskDB(Base):
    """Task model."""
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")  # pending, in_progress, completed, cancelled
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    assigned_to = Column(String(100))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = Column(DateTime)
    completed_at = Column(DateTime)
    tags = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)  # Task IDs
    subtasks = Column(JSON, default=list)  # Task IDs
    attachments = Column(JSON, default=list)
    meta_data = Column(JSON, default=dict)
    
    # Relationships
    created_by_user = relationship("User", back_populates="tasks")


class WorkflowDB(Base):
    """Workflow model."""
    __tablename__ = "workflows"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    trigger = Column(JSON, nullable=False)  # webhook, schedule, event, manual
    steps = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run = Column(DateTime)
    run_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    meta_data = Column(JSON, default=dict)
    
    # Relationships
    created_by_user = relationship("User", back_populates="workflows")
    runs = relationship("WorkflowRunDB", back_populates="workflow")


class WorkflowRunDB(Base):
    """Workflow run model."""
    __tablename__ = "workflow_runs"
    
    id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False)
    triggered_by = Column(String(100))
    trigger_data = Column(JSON, default=dict)
    status = Column(String(20), default="running")  # running, completed, failed, cancelled
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    step_results = Column(JSON, default=list)
    error = Column(Text)
    meta_data = Column(JSON, default=dict)
    
    # Relationships
    workflow = relationship("WorkflowDB", back_populates="runs")


class KnowledgeEntryDB(Base):
    """Knowledge base entry model with vector search support."""
    __tablename__ = "knowledge_entries"
    
    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # document, code, procedure, reference
    category = Column(String(100), nullable=False)
    tags = Column(JSON, default=list)
    source = Column(String(255))
    embedding = Column(Vector(1536))  # OpenAI embedding dimension
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime)
    meta_data = Column(JSON, default=dict)
    
    # Relationships
    created_by_user = relationship("User", back_populates="knowledge_entries")

    __table_args__ = (
        Index("ix_knowledge_entries_embedding", "embedding", postgresql_using="ivfflat"),
    )


class AuditLog(Base):
    """Audit log model."""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(255))
    details = Column(JSON, default=dict)
    success = Column(Boolean, default=True)
    error = Column(Text)
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class VoiceCommandDB(Base):
    """Voice command model."""
    __tablename__ = "voice_commands"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transcript = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    intent = Column(String(100))
    entities = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)
    audio_file = Column(String(255))
    duration_seconds = Column(Float)
    processed_at = Column(DateTime)
    processing_time_ms = Column(Float)
    
    # Relationships
    user = relationship("User")


class ApiKeyDB(Base):
    """API key model for service access."""
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    scopes = Column(JSON, default=list)  # List of allowed scopes
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)
    usage_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User")


class SystemConfigDB(Base):
    """System configuration model."""
    __tablename__ = "system_config"
    
    id = Column(String(36), primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    updated_by_user = relationship("User")


class NotificationDB(Base):
    """Notification model."""
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # info, warning, error, success
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    meta_data = Column(JSON, default=dict)
    
    # Relationships
    user = relationship("User")


class FileMetadataDB(Base):
    """File metadata model for tracking file operations."""
    __tablename__ = "file_metadata"
    
    id = Column(String(36), primary_key=True)
    path = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    checksum = Column(String(64))  # SHA-256 hash
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = Column(DateTime)
    access_count = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    meta_data = Column(JSON, default=dict)
    
    # Ownership
    created_by = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User")


class BackupDB(Base):
    """Backup tracking model."""
    __tablename__ = "backups"
    
    id = Column(String(36), primary_key=True)
    type = Column(String(50), nullable=False)  # full, incremental, files, database
    status = Column(String(20), nullable=False)  # running, completed, failed
    path = Column(String(500))
    size_bytes = Column(Integer)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    files_count = Column(Integer)
    error = Column(Text)
    meta_data = Column(JSON, default=dict)
    
    # Triggered by
    triggered_by = Column(Integer, ForeignKey("users.id"))
    trigger_user = relationship("User")