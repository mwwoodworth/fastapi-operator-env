"""Enhanced streaming AI responses with SSE and WebSocket support."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional, Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from claude_utils import stream_claude
from gpt_utils import stream_gpt
from core.settings import Settings
from db.models import AISession, AIMessage
from utils.metrics import AI_STREAMING_DURATION, AI_STREAMING_TOKENS

settings = Settings()


class StreamingAIHandler:
    """Handle streaming AI responses with session tracking."""
    
    def __init__(self, db: Session, user_id: int, model: str = "claude-3-opus"):
        self.db = db
        self.user_id = user_id
        self.model = model
        self.session: Optional[AISession] = None
        self.start_time = None
        self.total_tokens = 0
        
    async def create_session(self, purpose: str = "chat", context: Dict = None) -> AISession:
        """Create a new AI session."""
        self.session = AISession(
            user_id=self.user_id,
            model=self.model,
            purpose=purpose,
            context=context or {}
        )
        self.db.add(self.session)
        self.db.commit()
        self.db.refresh(self.session)
        return self.session
    
    async def add_message(self, role: str, content: str, tokens: int = 0, metadata: Dict = None):
        """Add a message to the session."""
        if not self.session:
            raise ValueError("No active session")
            
        message = AIMessage(
            session_id=self.session.id,
            role=role,
            content=content,
            tokens=tokens,
            metadata=metadata or {}
        )
        self.db.add(message)
        
        # Update session token count
        self.session.token_count += tokens
        self.total_tokens += tokens
        
        self.db.commit()
        
    async def stream_response(self, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Stream AI response with token tracking."""
        self.start_time = time.time()
        
        # Add user message
        await self.add_message("user", prompt, tokens=len(prompt.split()) * 2)  # Rough estimate
        
        # Add system prompt if provided
        if system_prompt:
            await self.add_message("system", system_prompt, tokens=len(system_prompt.split()) * 2)
        
        # Stream response based on model
        response_content = ""
        token_count = 0
        
        try:
            if self.model.startswith("claude"):
                async for chunk in stream_claude(prompt):
                    response_content += chunk
                    token_count += 1
                    yield chunk
            elif self.model.startswith("gpt"):
                async for chunk in stream_gpt(prompt):
                    response_content += chunk
                    token_count += 1
                    yield chunk
            else:
                raise ValueError(f"Unsupported model: {self.model}")
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"\n\nError: {str(e)}"
            
        finally:
            # Add assistant message
            await self.add_message("assistant", response_content, tokens=token_count)
            
            # Update metrics
            duration = time.time() - self.start_time
            AI_STREAMING_DURATION.labels(model=self.model).observe(duration)
            AI_STREAMING_TOKENS.labels(model=self.model).inc(token_count)
            
            # Update session
            self.session.updated_at = datetime.now(timezone.utc)
            self.db.commit()
    
    async def end_session(self):
        """End the AI session."""
        if self.session:
            self.session.ended_at = datetime.now(timezone.utc)
            
            # Calculate approximate cost
            if self.model == "claude-3-opus":
                # Claude pricing: $15/1M input tokens, $75/1M output tokens
                self.session.cost = (self.total_tokens / 1_000_000) * 45  # Average
            elif self.model == "gpt-4":
                # GPT-4 pricing: $30/1M input tokens, $60/1M output tokens
                self.session.cost = (self.total_tokens / 1_000_000) * 45  # Average
                
            self.db.commit()


async def handle_sse_stream(
    prompt: str,
    db: Session,
    user_id: int,
    model: str = "claude-3-opus",
    system_prompt: str = None,
    context: Dict = None
) -> EventSourceResponse:
    """Handle Server-Sent Events streaming."""
    
    async def event_generator():
        handler = StreamingAIHandler(db, user_id, model)
        
        try:
            # Create session
            session = await handler.create_session(purpose="sse_chat", context=context)
            yield {
                "event": "session_start",
                "data": json.dumps({"session_id": session.id})
            }
            
            # Stream response
            async for chunk in handler.stream_response(prompt, system_prompt):
                yield {
                    "event": "message",
                    "data": json.dumps({"content": chunk})
                }
                
            # End session
            await handler.end_session()
            yield {
                "event": "session_end",
                "data": json.dumps({
                    "session_id": session.id,
                    "total_tokens": handler.total_tokens,
                    "cost": session.cost
                })
            }
            
        except Exception as e:
            logger.error(f"SSE streaming error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())


class WebSocketManager:
    """Manage WebSocket connections for streaming."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")
        
    def disconnect(self, client_id: str):
        """Remove WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")
            
    async def send_json(self, client_id: str, data: Dict):
        """Send JSON data to specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)
            
    async def broadcast_json(self, data: Dict):
        """Broadcast JSON data to all connected clients."""
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")


# Global WebSocket manager
ws_manager = WebSocketManager()


async def handle_websocket_stream(
    websocket: WebSocket,
    db: Session,
    user_id: int,
    client_id: str
):
    """Handle WebSocket streaming connection."""
    await ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            if data.get("type") == "chat":
                prompt = data.get("message", "")
                model = data.get("model", "claude-3-opus")
                system_prompt = data.get("system_prompt")
                context = data.get("context", {})
                
                # Create handler
                handler = StreamingAIHandler(db, user_id, model)
                
                # Create session
                session = await handler.create_session(purpose="ws_chat", context=context)
                await websocket.send_json({
                    "type": "session_start",
                    "session_id": session.id
                })
                
                # Stream response
                async for chunk in handler.stream_response(prompt, system_prompt):
                    await websocket.send_json({
                        "type": "stream",
                        "content": chunk
                    })
                    
                # End session
                await handler.end_session()
                await websocket.send_json({
                    "type": "session_end",
                    "session_id": session.id,
                    "total_tokens": handler.total_tokens,
                    "cost": session.cost
                })
                
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
        ws_manager.disconnect(client_id)


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count."""
    # Approximate: 1 token ≈ 4 characters or 0.75 words
    return max(len(text) // 4, int(len(text.split()) * 1.3))


async def stream_with_function_calls(
    prompt: str,
    functions: list[Dict[str, Any]],
    db: Session,
    user_id: int,
    model: str = "claude-3-opus"
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream AI response with function calling support."""
    handler = StreamingAIHandler(db, user_id, model)
    session = await handler.create_session(purpose="function_calling")
    
    # Add function definitions to context
    session.context["functions"] = functions
    db.commit()
    
    # This would integrate with the AI provider's function calling API
    # For now, we'll yield a placeholder
    yield {
        "type": "function_call",
        "function": "get_weather",
        "arguments": {"location": "San Francisco"}
    }
    
    yield {
        "type": "content",
        "content": "Based on the weather data..."
    }
    
    await handler.end_session()