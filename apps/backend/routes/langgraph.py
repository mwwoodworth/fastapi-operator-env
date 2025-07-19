"""
LangGraph orchestration API endpoints.

Provides REST API for multi-agent workflow orchestration with:
- Workflow creation and management
- Execution with monitoring
- State persistence and recovery
- Result streaming
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import asyncio

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from ..db.business_models import User
from ..core.auth import get_current_user
from ..core.database import get_db
from ..core.rbac import Permission, require_permission
from ..agents.langgraph_orchestrator import (
    orchestrator, WorkflowState, WorkflowStatus,
    execute_analysis_workflow, execute_parallel_research
)
from ..core.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)


# Workflow Creation and Management
@router.post("/workflows", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_WRITE)
async def create_workflow(
    workflow_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new multi-agent workflow."""
    try:
        workflow_id = workflow_config.get("id", f"workflow_{UUID()}")
        
        # Validate workflow definition
        if "nodes" not in workflow_config:
            raise HTTPException(400, "Workflow must have nodes defined")
        
        if "edges" not in workflow_config:
            raise HTTPException(400, "Workflow must have edges defined")
        
        # Create workflow
        orchestrator.create_workflow(workflow_id, workflow_config)
        
        logger.info(f"Created workflow {workflow_id} by user {current_user.id}")
        
        return {
            "workflow_id": workflow_id,
            "status": "created",
            "nodes": len(workflow_config["nodes"]),
            "edges": len(workflow_config["edges"])
        }
        
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to create workflow: {str(e)}")


@router.post("/workflows/{workflow_id}/execute", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_EXECUTE)
async def execute_workflow(
    workflow_id: str,
    input_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Execute a workflow asynchronously."""
    try:
        # Start execution in background
        background_tasks.add_task(
            orchestrator.execute_workflow,
            workflow_id,
            input_data,
            str(current_user.id)
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "message": "Workflow execution started in background"
        }
        
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to start workflow: {str(e)}")


@router.post("/workflows/{workflow_id}/execute-sync", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_EXECUTE)
async def execute_workflow_sync(
    workflow_id: str,
    input_data: Dict[str, Any],
    timeout: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Execute a workflow synchronously and wait for result."""
    try:
        # Execute workflow
        state = await orchestrator.execute_workflow(
            workflow_id,
            input_data,
            str(current_user.id),
            timeout=timeout
        )
        
        return {
            "workflow_id": workflow_id,
            "status": state.status.value,
            "results": state.results,
            "errors": state.errors,
            "duration": state.metadata.get("duration")
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(408, f"Workflow execution timed out after {timeout}s")
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(500, f"Workflow execution failed: {str(e)}")


@router.get("/workflows/{workflow_id}/status", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_READ)
async def get_workflow_status(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current status of a workflow execution."""
    # Check active executions first
    active = orchestrator.get_active_workflows()
    if workflow_id in active:
        state = active[workflow_id]
        return {
            "workflow_id": workflow_id,
            "status": state.status.value,
            "current_step": state.current_step,
            "progress": len(state.results),
            "errors": len(state.errors)
        }
    
    # Check persisted state
    state = await orchestrator._load_workflow_state(workflow_id)
    if state:
        return {
            "workflow_id": workflow_id,
            "status": state.status.value,
            "completed_at": state.metadata.get("end_time"),
            "duration": state.metadata.get("duration"),
            "results": state.results,
            "errors": state.errors
        }
    
    raise HTTPException(404, f"Workflow {workflow_id} not found")


@router.post("/workflows/{workflow_id}/resume", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_EXECUTE)
async def resume_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    checkpoint_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Resume a paused or failed workflow."""
    try:
        # Resume in background
        background_tasks.add_task(
            orchestrator.resume_workflow,
            workflow_id,
            checkpoint_id
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "resuming",
            "checkpoint_id": checkpoint_id
        }
        
    except Exception as e:
        logger.error(f"Failed to resume workflow: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to resume workflow: {str(e)}")


@router.post("/workflows/{workflow_id}/cancel", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_WRITE)
async def cancel_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cancel a running workflow."""
    success = await orchestrator.cancel_workflow(workflow_id)
    
    if not success:
        raise HTTPException(404, f"Workflow {workflow_id} not found or not running")
    
    return {
        "workflow_id": workflow_id,
        "status": "cancelled"
    }


@router.get("/workflows/{workflow_id}/history", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_READ)
async def get_workflow_history(
    workflow_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get execution history for a workflow."""
    history = await orchestrator.get_workflow_history(workflow_id, limit)
    
    return {
        "workflow_id": workflow_id,
        "history": history,
        "total": len(history)
    }


# Predefined Workflows
@router.post("/workflows/analysis", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_EXECUTE)
async def run_analysis_workflow(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Run a predefined analysis workflow."""
    try:
        state = await execute_analysis_workflow(
            prompt=request["prompt"],
            context=request.get("context", {}),
            user_id=str(current_user.id)
        )
        
        return {
            "workflow_id": state.workflow_id,
            "status": state.status.value,
            "results": state.results,
            "analysis": state.results.get("reviewer", {}).get("content", "")
        }
        
    except Exception as e:
        logger.error(f"Analysis workflow failed: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis workflow failed: {str(e)}")


@router.post("/workflows/research", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_EXECUTE)
async def run_research_workflow(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Run a parallel research workflow."""
    try:
        topics = request.get("topics", [])
        if not topics:
            raise HTTPException(400, "Topics list is required")
        
        state = await execute_parallel_research(
            topics=topics,
            context=request.get("context", {}),
            user_id=str(current_user.id)
        )
        
        return {
            "workflow_id": state.workflow_id,
            "status": state.status.value,
            "results": state.results,
            "synthesis": state.results.get("reviewer", {}).get("content", "")
        }
        
    except Exception as e:
        logger.error(f"Research workflow failed: {e}", exc_info=True)
        raise HTTPException(500, f"Research workflow failed: {str(e)}")


# Streaming and Real-time
@router.get("/workflows/{workflow_id}/stream")
@require_permission(Permission.AUTOMATION_READ)
async def stream_workflow_execution(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stream workflow execution updates."""
    async def event_generator():
        last_update = None
        
        while True:
            # Check for updates
            active = orchestrator.get_active_workflows()
            
            if workflow_id in active:
                state = active[workflow_id]
                
                # Send update if changed
                current_update = state.updated_at
                if current_update != last_update:
                    yield f"data: {json.dumps({
                        'status': state.status.value,
                        'step': state.current_step,
                        'messages': len(state.messages),
                        'results': len(state.results),
                        'errors': len(state.errors)
                    })}\n\n"
                    last_update = current_update
                
                # Check if completed
                if state.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                    yield f"data: {json.dumps({
                        'status': state.status.value,
                        'completed': True,
                        'results': state.results,
                        'errors': state.errors
                    })}\n\n"
                    break
            else:
                # Workflow not active anymore
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.websocket("/workflows/{workflow_id}/ws")
async def workflow_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str  # Pass auth token as query param for WebSocket
):
    """WebSocket connection for real-time workflow updates."""
    await websocket.accept()
    
    try:
        # Simplified auth check - in production use proper WebSocket auth
        # Verify token here
        
        last_update = None
        
        while True:
            # Check for updates
            active = orchestrator.get_active_workflows()
            
            if workflow_id in active:
                state = active[workflow_id]
                
                # Send update if changed
                current_update = state.updated_at
                if current_update != last_update:
                    await websocket.send_json({
                        "type": "update",
                        "status": state.status.value,
                        "step": state.current_step,
                        "progress": {
                            "messages": len(state.messages),
                            "results": len(state.results),
                            "errors": len(state.errors)
                        }
                    })
                    last_update = current_update
                
                # Send latest message
                if state.messages:
                    latest_message = state.messages[-1]
                    await websocket.send_json({
                        "type": "message",
                        "message": latest_message
                    })
                
                # Check if completed
                if state.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                    await websocket.send_json({
                        "type": "complete",
                        "status": state.status.value,
                        "results": state.results,
                        "errors": state.errors
                    })
                    break
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Workflow not found"
                })
                break
            
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for workflow {workflow_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.close()


# Admin endpoints
@router.get("/workflows", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_ADMIN)
async def list_workflows(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all workflows (admin only)."""
    active = orchestrator.get_active_workflows()
    
    workflows = []
    for wf_id, state in active.items():
        if status and state.status.value != status:
            continue
            
        workflows.append({
            "workflow_id": wf_id,
            "status": state.status.value,
            "created_at": state.created_at.isoformat(),
            "user_id": state.metadata.get("user_id")
        })
    
    return {
        "workflows": workflows[:limit],
        "total": len(workflows),
        "active": len([w for w in workflows if w["status"] == "running"])
    }


@router.delete("/workflows/cleanup", response_model=Dict[str, Any])
@require_permission(Permission.AUTOMATION_ADMIN)
async def cleanup_old_workflows(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clean up old workflow checkpoints (admin only)."""
    cleaned = await orchestrator.cleanup_old_checkpoints(days)
    
    return {
        "cleaned": cleaned,
        "message": f"Cleaned up {cleaned} old checkpoints"
    }