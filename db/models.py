from __future__ import annotations

from datetime import datetime

try:
    from sqlalchemy import (
        JSON,
        Column,
        DateTime,
        ForeignKey,
        Integer,
        String,
        Text,
        Index,
    )
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy.orm import declarative_base, relationship
    SQLALCHEMY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    SQLALCHEMY_AVAILABLE = False

    class Dummy:
        def __init__(self, *args, **kwargs):
            pass

    JSON = DateTime = ForeignKey = Integer = String = Text = Index = Column = Dummy

    def declarative_base():  # type: ignore
        class Base:
            pass

        return Base

    def relationship(*args, **kwargs):  # type: ignore
        return None

    class ARRAY(list):
        pass

Base = declarative_base()

class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    participants = Column(ARRAY(String))
    project_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="thread")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.id"))
    sender = Column(String(50))
    recipient = Column(String(50), nullable=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)
    attachments = Column(JSON, nullable=True)

    thread = relationship("Thread", back_populates="messages")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    description = Column(Text)
    status = Column(String(50))
    assigned_to = Column(String(50))
    created_by = Column(String(50))
    due_date = Column(DateTime, nullable=True)
    parent_task = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    priority = Column(Integer)
    tags = Column(ARRAY(String))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("Task", remote_side=[id])
    thread = relationship("Thread")
    files = relationship("File", back_populates="task")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    uploader = Column(String(50))
    path = Column(String(255))
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)

    thread = relationship("Thread")
    task = relationship("Task", back_populates="files")


# Indexes
Index("ix_messages_thread_sender", Message.thread_id, Message.sender)
Index("ix_tasks_assigned_status", Task.assigned_to, Task.status)
