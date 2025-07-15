"""AI streaming endpoints with SSE and WebSocket support."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from core.security import get_current_user
from core.streaming import handle_sse_stream, handle_websocket_stream
from core.settings import Settings
from db.models import User, AISession
from db.session import get_db

settings = Settings()

router = APIRouter(prefix="/ai", tags=["AI Streaming"])


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., min_length=1, max_length=10000)
    model: str = Field(default="claude-3-opus", pattern="^(claude|gpt)")
    system_prompt: Optional[str] = Field(None, max_length=2000)
    context: Optional[Dict[str, Any]] = None
    stream: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Explain quantum computing in simple terms",
                "model": "claude-3-opus",
                "system_prompt": "You are a helpful AI assistant",
                "stream": True
            }
        }


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    session_id: str
    message: str
    model: str
    tokens: int
    cost: float


@router.post("/chat/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream AI chat response using Server-Sent Events (SSE).
    
    This endpoint returns a stream of events:
    - `session_start`: Contains session_id
    - `message`: Contains chunks of the AI response
    - `session_end`: Contains final statistics
    - `error`: If an error occurs
    
    Example client code:
    ```javascript
    const evtSource = new EventSource('/ai/chat/stream', {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer YOUR_TOKEN',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: 'Hello AI',
            model: 'claude-3-opus'
        })
    });
    
    evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data);
    };
    ```
    """
    return await handle_sse_stream(
        prompt=request.message,
        db=db,
        user_id=current_user.id,
        model=request.model,
        system_prompt=request.system_prompt,
        context=request.context
    )


@router.websocket("/chat/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for streaming AI chat.
    
    Connect with: `ws://localhost:8000/ai/chat/ws?token=YOUR_TOKEN`
    
    Message format:
    ```json
    {
        "type": "chat",
        "message": "Your message here",
        "model": "claude-3-opus",
        "system_prompt": "Optional system prompt",
        "context": {}
    }
    ```
    
    Response events:
    - `session_start`: New session started
    - `stream`: Streaming content chunks
    - `session_end`: Session completed with stats
    - `error`: Error occurred
    - `pong`: Response to ping
    """
    # Validate token and get user
    from jose import jwt
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        username = payload.get("sub")
        user_id = payload.get("user_id")
        
        if not username:
            await websocket.close(code=1008, reason="Invalid token")
            return
            
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            await websocket.close(code=1008, reason="User not found or inactive")
            return
            
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Generate client ID
    client_id = str(uuid.uuid4())
    
    # Handle WebSocket connection
    await handle_websocket_stream(
        websocket=websocket,
        db=db,
        user_id=user.id,
        client_id=client_id
    )


@router.get("/sessions", response_model=list[AISessionResponse])
async def list_sessions(
    limit: int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0),
    model: Optional[str] = None,
    purpose: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List AI chat sessions for the current user.
    
    - **limit**: Maximum number of sessions to return
    - **offset**: Number of sessions to skip
    - **model**: Filter by AI model
    - **purpose**: Filter by session purpose
    """
    query = db.query(AISession).filter(AISession.user_id == current_user.id)
    
    if model:
        query = query.filter(AISession.model == model)
    if purpose:
        query = query.filter(AISession.purpose == purpose)
    
    sessions = query.order_by(AISession.created_at.desc()).offset(offset).limit(limit).all()
    
    return [AISessionResponse.from_orm(session) for session in sessions]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    include_messages: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific AI session.
    
    - **session_id**: The session ID
    - **include_messages**: Include all messages in the response
    """
    session = db.query(AISession).filter(
        AISession.id == session_id,
        AISession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    response = {
        "id": session.id,
        "model": session.model,
        "purpose": session.purpose,
        "context": session.context,
        "token_count": session.token_count,
        "cost": session.cost,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "ended_at": session.ended_at
    }
    
    if include_messages:
        messages = []
        for msg in session.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "tokens": msg.tokens,
                "created_at": msg.created_at,
                "metadata": msg.metadata
            })
        response["messages"] = messages
    
    return response


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an AI session and all its messages.
    """
    session = db.query(AISession).filter(
        AISession.id == session_id,
        AISession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}


@router.get("/models")
async def list_available_models(
    current_user: User = Depends(get_current_user)
):
    """
    List available AI models and their capabilities.
    """
    return {
        "models": [
            {
                "id": "claude-3-opus",
                "name": "Claude 3 Opus",
                "provider": "Anthropic",
                "context_window": 200000,
                "capabilities": ["chat", "code", "analysis", "creative"],
                "pricing": {
                    "input": 15.0,  # per 1M tokens
                    "output": 75.0  # per 1M tokens
                }
            },
            {
                "id": "claude-3-sonnet",
                "name": "Claude 3 Sonnet",
                "provider": "Anthropic",
                "context_window": 200000,
                "capabilities": ["chat", "code", "analysis"],
                "pricing": {
                    "input": 3.0,
                    "output": 15.0
                }
            },
            {
                "id": "gpt-4-turbo",
                "name": "GPT-4 Turbo",
                "provider": "OpenAI",
                "context_window": 128000,
                "capabilities": ["chat", "code", "vision", "function_calling"],
                "pricing": {
                    "input": 10.0,
                    "output": 30.0
                }
            },
            {
                "id": "gpt-4",
                "name": "GPT-4",
                "provider": "OpenAI",
                "context_window": 8192,
                "capabilities": ["chat", "code", "function_calling"],
                "pricing": {
                    "input": 30.0,
                    "output": 60.0
                }
            }
        ]
    }


class AISessionResponse(BaseModel):
    """AI session response model."""
    id: str
    model: str
    purpose: str
    token_count: int
    cost: float
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime]
    
    class Config:
        from_attributes = True