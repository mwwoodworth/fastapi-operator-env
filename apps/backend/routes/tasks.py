"""
Task Management API Routes

This module provides FastAPI endpoints for task operations including creation,
execution, status monitoring, and result retrieval. Tasks represent the core
units of work in BrainOps, from content generation to estimate calculations.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json

from apps.backend.core.security import get_current_user
from apps.backend.memory.models import User, TaskRecord, TaskStatus
from apps.backend.memory.memory_store import save_task, get_task, list_user_tasks
from apps.backend.tasks import task_registry
from apps.backend.agents.base import ExecutionContext


router = APIRouter()


@router.post("/design")
async def design_task(
    task_type: str,
    parameters: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Design a task configuration without executing it.
    
    This endpoint validates parameters and returns a task specification
    that can be reviewed, modified, and executed later.
    """
    # Validate task type exists in registry
    if task_type not in task_registry:
        raise HTTPException(404, f"Unknown task type: {task_type}")
    
    task_class = task_registry[task_type]
    
    # Validate parameters against task schema
    try:
        validated_params = task_class.validate_parameters(parameters)
    except ValueError as e:
        raise HTTPException(400, f"Invalid parameters: {str(e)}")
    
    # Generate task design with estimated cost and duration
    design = {
        "task_id": str(uuid.uuid4()),
        "task_type": task_type,
        "parameters": validated_params,
        "estimated_tokens": task_class.estimate_tokens(validated_params),
        "estimated_duration_seconds": task_class.estimate_duration(validated_params),
        "required_approvals": task_class.get_required_approvals(validated_params),
        "description": task_class.describe(validated_params),
        "created_at": datetime.utcnow().isoformat(),
        "created_by": current_user.id
    }
    
    return design


@router.post("/run")
async def run_task(
    task_type: str,
    parameters: Dict[str, Any],
    background_tasks: BackgroundTasks,
    stream: bool = False,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Execute a task immediately or queue it for background processing.
    
    If stream=True, returns a streaming response for real-time updates.
    Otherwise, queues the task and returns a task ID for status polling.
    """
    # Validate task type and parameters
    if task_type not in task_registry:
        raise HTTPException(404, f"Unknown task type: {task_type}")
    
    task_class = task_registry[task_type]
    
    try:
        validated_params = task_class.validate_parameters(parameters)
    except ValueError as e:
        raise HTTPException(400, f"Invalid parameters: {str(e)}")
    
    # Create task record
    task_id = str(uuid.uuid4())
    task_record = TaskRecord(
        id=task_id,
        user_id=current_user.id,
        task_type=task_type,
        parameters=validated_params,
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    # Save initial task state
    await save_task(task_record)
    
    # Create execution context with user info and memory access
    context = ExecutionContext(
        task_id=task_id,
        user_id=current_user.id,
        parameters=validated_params,
        memory_enabled=True
    )
    
    if stream and hasattr(task_class, 'stream'):
        # Return streaming response for real-time updates
        return StreamingResponse(
            task_class.stream(context),
            media_type="text/event-stream"
        )
    else:
        # Queue task for background execution
        background_tasks.add_task(
            _execute_task_background,
            task_id,
            task_class,
            context
        )
        
        return {
            "task_id": task_id,
            "status": "queued",
            "message": f"Task {task_type} queued for execution",
            "status_url": f"/api/tasks/{task_id}/status"
        }


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get the current status and progress of a task.
    
    Returns execution state, progress percentage, and any intermediate results.
    """
    task = await get_task(task_id, current_user.id)
    
    if not task:
        raise HTTPException(404, "Task not found")
    
    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress": task.progress,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "error": task.error,
        "result_preview": task.result.get("preview") if task.result else None
    }


@router.get("/{task_id}/result")
async def get_task_result(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retrieve the full result of a completed task.
    
    Returns the complete output including generated content, files, or data.
    """
    task = await get_task(task_id, current_user.id)
    
    if not task:
        raise HTTPException(404, "Task not found")
    
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(400, f"Task not completed. Current status: {task.status.value}")
    
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "completed_at": task.completed_at.isoformat(),
        "result": task.result,
        "metadata": task.metadata
    }


@router.get("/history")
async def list_task_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    task_type: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List task execution history for the current user.
    
    Supports filtering by task type and status with pagination.
    """
    tasks = await list_user_tasks(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        task_type=task_type,
        status=status
    )
    
    # Format task list for response
    task_list = [
        {
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "description": task.metadata.get("description", "")
        }
        for task in tasks
    ]
    
    return {
        "tasks": task_list,
        "limit": limit,
        "offset": offset,
        "total": len(task_list)
    }


async def _execute_task_background(task_id: str, task_class: Any, context: ExecutionContext):
    """
    Background task execution handler.
    
    Updates task status throughout execution and handles errors gracefully.
    """
    try:
        # Update task status to running
        await update_task_status(task_id, TaskStatus.RUNNING)
        
        # Execute the task with context
        result = await task_class.run(context)
        
        # Update task with completion status and result
        await complete_task(task_id, result)
        
    except Exception as e:
        # Handle task failure
        await fail_task(task_id, str(e))
