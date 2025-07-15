"""BrainOps AI Assistant - Main Application"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from core.config import settings
from core.database import init_db
from core.auth import get_current_user
from routers import (
    assistant,
    files,
    workflows,
    qa
)
from services.assistant import AssistantService
from services.memory import MemoryService
from services.voice_interface import VoiceInterface
from services.workflow_engine import WorkflowEngine
from services.qa_system import QASystem


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting BrainOps AI Assistant...")
    
    # Initialize database
    await init_db()
    
    # Initialize services
    app.state.assistant = AssistantService()
    app.state.memory = MemoryService()
    app.state.voice = VoiceInterface()
    app.state.workflow_engine = WorkflowEngine()
    app.state.qa_system = QASystem()
    
    # Initialize voice interface
    await app.state.voice.initialize()
    
    logger.info("BrainOps AI Assistant ready!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down BrainOps AI Assistant...")
    await app.state.assistant.shutdown()
    await app.state.voice.shutdown()
    await app.state.workflow_engine.shutdown()


app = FastAPI(
    title="BrainOps AI Assistant",
    description="AI Chief of Staff - Full Operational Control",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(assistant.router, prefix="/api", tags=["AI Assistant"])
app.include_router(files.router, prefix="/api", tags=["File Operations"])
app.include_router(workflows.router, prefix="/api", tags=["Workflow Automation"])
app.include_router(qa.router, prefix="/api", tags=["QA System"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.websocket("/ws/assistant")
async def websocket_assistant(
    websocket: WebSocket,
    user=Depends(get_current_user)
):
    """WebSocket endpoint for real-time assistant interaction."""
    await websocket.accept()
    
    assistant = app.state.assistant
    session_id = await assistant.create_session(user.id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Process message
            response = await assistant.process_message(
                session_id=session_id,
                message=data.get("message"),
                message_type=data.get("type", "chat"),
                context=data.get("context", {})
            )
            
            # Send response
            await websocket.send_json(response)
            
    except WebSocketDisconnect:
        await assistant.end_session(session_id)
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "BrainOps AI Assistant",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/status")
async def system_status():
    """Get system status."""
    return {
        "status": "online",
        "services": {
            "assistant": True,
            "voice": True,
            "workflow": True,
            "qa": True,
            "files": True
        },
        "version": "1.0.0",
        "uptime": "00:00:00",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )