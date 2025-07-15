"""Assistant API endpoints for chat and AI interactions."""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from core.config import settings
from core.auth import get_current_user
from services.assistant import AssistantService
from services.voice_interface import VoiceInterface, VoiceWebSocketHandler
from models.db import User
from utils.audit import AuditLogger

router = APIRouter(prefix="/assistant", tags=["assistant"])
security = HTTPBearer()
audit_logger = AuditLogger()

# Initialize services
assistant_service = AssistantService()
voice_interface = VoiceInterface()
voice_websocket_handler = VoiceWebSocketHandler(voice_interface)


class ChatMessage(BaseModel):
    """Chat message model."""
    message: str = Field(..., description="The message content")
    message_type: str = Field(default="chat", description="Type of message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    actions: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    suggestions: List[str] = []


class SessionCreate(BaseModel):
    """Session creation model."""
    context: Optional[Dict[str, Any]] = Field(default=None, description="Initial context")


class ActionConfirmation(BaseModel):
    """Action confirmation model."""
    confirmed: bool = Field(..., description="Whether the action is confirmed")


class VoiceSessionCreate(BaseModel):
    """Voice session creation model."""
    config: Optional[Dict[str, Any]] = Field(default=None, description="Voice configuration")


class VoiceSettings(BaseModel):
    """Voice settings model."""
    voice_id: Optional[str] = Field(default=None, description="Voice ID for synthesis")
    stability: Optional[float] = Field(default=0.5, description="Voice stability")
    similarity_boost: Optional[float] = Field(default=0.8, description="Similarity boost")
    style: Optional[float] = Field(default=0.2, description="Voice style")
    use_speaker_boost: Optional[bool] = Field(default=True, description="Use speaker boost")


@router.post("/sessions", response_model=Dict[str, str])
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new assistant session."""
    try:
        session_id = await assistant_service.create_session(current_user.id)
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="assistant_session_created",
            resource_type="session",
            resource_id=session_id
        )
        
        return {"session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: str,
    message: ChatMessage,
    current_user: User = Depends(get_current_user)
):
    """Send a chat message to the assistant."""
    try:
        result = await assistant_service.process_message(
            session_id=session_id,
            message=message.message,
            message_type=message.message_type,
            context=message.context
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="assistant_message_sent",
            resource_type="message",
            resource_id=session_id,
            details={
                "message_type": message.message_type,
                "message_length": len(message.message)
            }
        )
        
        return ChatResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/stream")
async def stream_chat(
    session_id: str,
    message: str,
    current_user: User = Depends(get_current_user)
):
    """Stream a chat response from the assistant."""
    try:
        async def generate():
            async for chunk in assistant_service.stream_response(session_id, message):
                yield f"data: {chunk}\n\n"
        
        return EventSourceResponse(generate())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm/{pending_id}")
async def confirm_action(
    session_id: str,
    pending_id: str,
    confirmation: ActionConfirmation,
    current_user: User = Depends(get_current_user)
):
    """Confirm or reject a pending action."""
    try:
        result = await assistant_service.confirm_action(
            session_id=session_id,
            pending_id=pending_id,
            confirmed=confirmation.confirmed
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="action_confirmed" if confirmation.confirmed else "action_rejected",
            resource_type="action",
            resource_id=pending_id,
            details={"session_id": session_id}
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get session message history."""
    try:
        history = await assistant_service.get_session_history(session_id, limit)
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "message_type": msg.message_type,
                    "actions": [
                        {
                            "type": action.type.value,
                            "status": action.status,
                            "timestamp": action.timestamp.isoformat()
                        }
                        for action in (msg.actions or [])
                    ]
                }
                for msg in history
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = "json",
    current_user: User = Depends(get_current_user)
):
    """Export session data."""
    try:
        export_data = await assistant_service.export_session(session_id, format)
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="session_exported",
            resource_type="session",
            resource_id=session_id,
            details={"format": format}
        )
        
        return export_data
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/search")
async def search_history(
    query: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Search through user's conversation history."""
    try:
        results = await assistant_service.search_history(
            user_id=current_user.id,
            query=query,
            limit=limit
        )
        
        return {
            "query": query,
            "results": results,
            "total": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Voice interface endpoints
@router.post("/voice/sessions", response_model=Dict[str, str])
async def create_voice_session(
    session_data: VoiceSessionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new voice session."""
    try:
        session_id = await voice_interface.create_voice_session(
            user_id=current_user.id,
            session_config=session_data.config
        )
        
        return {"session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/sessions/{session_id}/settings")
async def set_voice_settings(
    session_id: str,
    settings: VoiceSettings,
    current_user: User = Depends(get_current_user)
):
    """Set voice synthesis settings."""
    try:
        result = await voice_interface.set_voice_settings(
            session_id=session_id,
            voice_settings=settings.dict(exclude_none=True)
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice/sessions/{session_id}/status")
async def get_voice_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get voice session status."""
    try:
        status = await voice_interface.get_session_status(session_id)
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/sessions/{session_id}/hotword/enable")
async def enable_hotword_detection(
    session_id: str,
    hotwords: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user)
):
    """Enable hotword detection."""
    try:
        result = await voice_interface.enable_hotword_detection(
            session_id=session_id,
            hotwords=hotwords
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/sessions/{session_id}/hotword/disable")
async def disable_hotword_detection(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Disable hotword detection."""
    try:
        result = await voice_interface.disable_hotword_detection(session_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/voice/sessions/{session_id}")
async def end_voice_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """End a voice session."""
    try:
        result = await voice_interface.end_voice_session(session_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time voice
@router.websocket("/voice/sessions/{session_id}/ws")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice communication."""
    await websocket.accept()
    
    try:
        await voice_websocket_handler.handle_connection(websocket, session_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1000, reason=str(e))


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for assistant service."""
    try:
        # Check service health
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "assistant": "healthy",
                "voice_interface": "healthy"
            }
        }
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))