from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.settings import Settings

from db.models import File as DBFile, Message, Task, Thread
from db.session import SessionLocal

settings = Settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
USERS = {}
if os.getenv("BASIC_AUTH_USERS"):
    try:
        USERS = json.loads(os.getenv("BASIC_AUTH_USERS", "{}"))
    except Exception:
        USERS = {}
AGENT_KEYS = {}
if os.getenv("AGENT_KEYS"):
    try:
        AGENT_KEYS = json.loads(os.getenv("AGENT_KEYS", "{}"))
    except Exception:
        AGENT_KEYS = {}


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_identity(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> str:
    """Authenticate via JWT bearer or agent key."""
    if not USERS and not AGENT_KEYS:
        return "anonymous"
    if USERS and token:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
            username = payload.get("sub")
            if username in USERS:
                return username
        except Exception:
            pass
    key = request.headers.get("X-Agent-Key")
    if AGENT_KEYS and key:
        for name, val in AGENT_KEYS.items():
            if val == key:
                return f"agent:{name}"
    raise HTTPException(status_code=401, detail="Unauthorized")


class ThreadCreate(BaseModel):
    title: Optional[str] = None
    participants: List[str] = []
    project_id: Optional[str] = None


class ThreadUpdate(BaseModel):
    title: Optional[str] = None
    add_participants: List[str] = []


@router.post("/threads")
def create_thread(payload: ThreadCreate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Create a new chat thread."""
    thread = Thread(title=payload.title, participants=payload.participants, project_id=payload.project_id)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return {"id": thread.id}


@router.get("/threads")
def list_threads(db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Return all threads."""
    threads = db.query(Thread).all()
    return threads


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Fetch a single thread by ID."""
    thread = db.query(Thread).get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="not found")
    return thread


@router.patch("/threads/{thread_id}")
def update_thread(thread_id: int, payload: ThreadUpdate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Update thread title or participants."""
    thread = db.query(Thread).get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="not found")
    if payload.title is not None:
        thread.title = payload.title
    if payload.add_participants:
        existing = thread.participants or []
        thread.participants = list(set(existing + payload.add_participants))
    db.commit()
    db.refresh(thread)
    return thread


class MessageCreate(BaseModel):
    thread_id: int
    sender: str
    content: str
    recipient: Optional[str] = None
    metadata: Optional[dict] = None
    attachments: Optional[dict] = None


class MessageUpdate(BaseModel):
    content: Optional[str] = None
    metadata: Optional[dict] = None
    attachments: Optional[dict] = None


@router.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Create a message in a thread."""
    msg = Message(
        thread_id=payload.thread_id,
        sender=payload.sender,
        recipient=payload.recipient,
        content=payload.content,
        meta=payload.metadata,
        attachments=payload.attachments,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id}


@router.get("/messages")
def list_messages(
    thread: int | None = None,
    sender: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_identity),
):
    """List messages filtered by thread or sender."""
    query = db.query(Message)
    if thread is not None:
        query = query.filter(Message.thread_id == thread)
    if sender is not None:
        query = query.filter(Message.sender == sender)
    return query.all()


@router.patch("/messages/{message_id}")
def edit_message(message_id: int, payload: MessageUpdate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Edit message content or metadata."""
    msg = db.query(Message).get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="not found")
    if payload.content is not None:
        msg.content = payload.content
    if payload.metadata is not None:
        msg.meta = payload.metadata
    if payload.attachments is not None:
        msg.attachments = payload.attachments
    db.commit()
    db.refresh(msg)
    return msg


@router.delete("/messages/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Delete a message."""
    msg = db.query(Message).get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(msg)
    db.commit()
    return {"status": "deleted"}


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "open"
    assigned_to: str
    created_by: str
    due_date: Optional[datetime] = None
    parent_task: Optional[int] = None
    thread_id: Optional[int] = None
    priority: Optional[int] = 0
    tags: List[str] = []


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    title: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None
    tags: Optional[List[str]] = None


@router.post("/tasks")
def create_task(payload: TaskCreate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Create a task."""
    task = Task(**payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id}


@router.get("/tasks")
def list_tasks(
    assigned_to: str | None = None,
    status: str | None = None,
    thread: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_identity),
):
    """List tasks filtered by assigned user, status or thread."""
    query = db.query(Task)
    if assigned_to is not None:
        query = query.filter(Task.assigned_to == assigned_to)
    if status is not None:
        query = query.filter(Task.status == status)
    if thread is not None:
        query = query.filter(Task.thread_id == thread)
    return query.all()


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Update task fields."""
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Delete a task."""
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(task)
    db.commit()
    return {"status": "deleted"}


class FileMeta(BaseModel):
    uploader: str
    thread_id: Optional[int] = None
    task_id: Optional[int] = None
    metadata: Optional[dict] = None


@router.post("/files")
async def upload_file(
    uploader: str = Form(...),
    thread_id: int | None = Form(None),
    task_id: int | None = Form(None),
    metadata: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(get_identity),
):
    """Upload a file and store metadata."""
    dest = Path("uploads")
    dest.mkdir(exist_ok=True)
    path = dest / file.filename
    with path.open("wb") as f:
        f.write(await file.read())
    db_file = DBFile(
        filename=file.filename,
        uploader=uploader,
        path=str(path),
        thread_id=thread_id,
        task_id=task_id,
        meta=json.loads(metadata) if metadata else {},
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return {"id": db_file.id}


@router.get("/files")
def list_files(
    thread: int | None = None,
    task: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_identity),
):
    """List uploaded files filtered by thread or task."""
    query = db.query(DBFile)
    if thread is not None:
        query = query.filter(DBFile.thread_id == thread)
    if task is not None:
        query = query.filter(DBFile.task_id == task)
    return query.all()


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), _: str = Depends(get_identity)):
    """Delete a stored file and remove from disk."""
    db_file = db.query(DBFile).get(file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="not found")
    path = Path(db_file.path)
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    db.delete(db_file)
    db.commit()
    return {"status": "deleted"}

