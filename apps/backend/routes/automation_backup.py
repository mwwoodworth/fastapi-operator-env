"""
Automation and Workflow Management Routes

This module handles workflow automation, including creation, execution,
and management of multi-step workflows with various trigger types.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import uuid4

from ..core.auth import get_current_user
from ..db.business_models import User, Workflow, WorkflowRun, Integration
from ..core.database import get_db
from pydantic import BaseModel
import asyncio


router = APIRouter()


class WorkflowStepModel(BaseModel):
    id: str
    type: str
    name: str
    config: Dict[str, Any]
    next_steps: List[str] = []
    error_handler: Optional[str] = None


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str
    trigger_type: str  # manual, schedule, webhook, event
    trigger_config: Dict[str, Any]
    steps: List[Dict[str, Any]]
    is_active: bool = True
    is_public: bool = False


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


class TriggerCreateRequest(BaseModel):
    workflow_id: str
    trigger_type: str
    config: Dict[str, Any]
    is_enabled: bool = True


class IntegrationConnectRequest(BaseModel):
    integration_type: str
    config: Dict[str, Any]
    name: str


@router.post("/")
async def create_workflow(
    request: WorkflowCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new workflow."""
    workflow = Workflow(
        id=str(uuid4()),
        name=request.name,
        description=request.description,
        owner_id=current_user.id,
        trigger_type=request.trigger_type,
        trigger_config=request.trigger_config,
        steps=request.steps,
        is_active=request.is_active
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config,
        "steps": workflow.steps,
        "is_active": workflow.is_active,
        "is_public": False,  # Not in model
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat()
    }


@router.get("/")
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List user's workflows."""
    workflows = db.query(Workflow).filter(
        Workflow.owner_id == current_user.id
    ).all()
    
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "trigger_type": w.trigger_type,
            "is_active": w.is_active,
            "is_public": False,  # Not in model
            "created_at": w.created_at.isoformat(),
            "updated_at": w.updated_at.isoformat()
        }
        for w in workflows
    ]


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get workflow details."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config,
        "steps": workflow.steps,
        "is_active": workflow.is_active,
        "is_public": False,  # Not in model
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat()
    }


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update a workflow."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    # Update fields if provided
    if request.name is not None:
        workflow.name = request.name
    if request.description is not None:
        workflow.description = request.description
    if request.trigger_type is not None:
        workflow.trigger_type = request.trigger_type
    if request.trigger_config is not None:
        workflow.trigger_config = request.trigger_config
    if request.steps is not None:
        workflow.steps = request.steps
    if request.is_active is not None:
        workflow.is_active = request.is_active
    # is_public is not in the model, skip it
    
    workflow.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(workflow)
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config,
        "steps": workflow.steps,
        "is_active": workflow.is_active,
        "is_public": False,  # Not in model
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat()
    }


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Delete a workflow."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    db.delete(workflow)
    db.commit()
    
    return {"message": "Workflow deleted successfully"}


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Execute a workflow."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    if not workflow.is_active:
        raise HTTPException(400, "Workflow is not active")
    
    # Create workflow run
    run = WorkflowRun(
        id=str(uuid4()),
        workflow_id=workflow.id,
        status="running",
        started_at=datetime.utcnow(),
        trigger_data={"type": "manual"},
        steps_total=len(workflow.steps) if isinstance(workflow.steps, list) else 1
    )
    
    db.add(run)
    db.commit()
    db.refresh(run)
    
    # Execute workflow asynchronously
    asyncio.create_task(execute_workflow_async(str(workflow.id), str(run.id), db))
    
    return {
        "run_id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "started_at": run.started_at.isoformat()
    }


@router.get("/{workflow_id}/runs")
async def get_workflow_runs(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, le=100)
) -> List[Dict[str, Any]]:
    """Get workflow execution history."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    runs = db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == workflow_id
    ).order_by(WorkflowRun.started_at.desc()).limit(limit).all()
    
    return [
        {
            "run_id": run.id,
            "status": run.status,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "trigger_type": run.trigger_data.get("type", "unknown") if run.trigger_data else "unknown",
            "error": run.error
        }
        for run in runs
    ]


@router.post("/triggers")
async def create_trigger(
    request: TriggerCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a workflow trigger."""
    # Verify workflow exists and belongs to user
    workflow = db.query(Workflow).filter(
        Workflow.id == request.workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    # In production, this would create the actual trigger
    # For now, we'll return a mock response
    trigger_id = str(uuid4())
    
    return {
        "id": trigger_id,
        "workflow_id": request.workflow_id,
        "trigger_type": request.trigger_type,
        "config": request.config,
        "is_enabled": request.is_enabled,
        "created_at": datetime.utcnow().isoformat()
    }


@router.get("/triggers")
async def list_triggers(
    workflow_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List workflow triggers."""
    # In production, this would query actual triggers
    # For now, return mock data for testing
    return [
        {
            "id": "trigger-1",
            "workflow_id": workflow_id or "workflow-1",
            "trigger_type": "schedule",
            "trigger_config": {"cron": "0 0 * * *"},
            "is_enabled": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    ]


@router.put("/triggers/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    is_enabled: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update a trigger."""
    # In production, this would update the actual trigger
    return {
        "id": trigger_id,
        "is_enabled": is_enabled,
        "updated_at": datetime.utcnow().isoformat()
    }


@router.get("/integrations")
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List available integrations."""
    return [
        {
            "id": "slack",
            "name": "Slack",
            "description": "Send messages to Slack channels",
            "icon": "slack-icon.png",
            "is_connected": False
        },
        {
            "id": "github",
            "name": "GitHub",
            "description": "Interact with GitHub repositories",
            "icon": "github-icon.png",
            "is_connected": False
        },
        {
            "id": "notion",
            "name": "Notion",
            "description": "Create and update Notion pages",
            "icon": "notion-icon.png",
            "is_connected": False
        }
    ]


@router.post("/integrations/connect")
async def connect_integration(
    request: IntegrationConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Connect an integration."""
    integration = Integration(
        id=str(uuid4()),
        user_id=current_user.id,
        type=request.integration_type,
        name=request.name,
        config=request.config,
        is_active=True
    )
    
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    return {
        "id": integration.id,
        "integration_type": integration.type,
        "name": integration.name,
        "is_active": integration.is_active,
        "created_at": integration.created_at.isoformat() if integration.created_at else datetime.utcnow().isoformat()
    }


@router.delete("/integrations/{integration_type}/disconnect")
async def disconnect_integration(
    integration_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Disconnect an integration."""
    integration = db.query(Integration).filter(
        Integration.type == integration_type,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    db.delete(integration)
    db.commit()
    
    return {"message": f"{integration.name} integration disconnected successfully"}


@router.get("/integrations/{integration_type}/status")
async def get_integration_status(
    integration_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get integration status."""
    integration = db.query(Integration).filter(
        Integration.type == integration_type,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    return {
        "id": str(integration.id),
        "type": integration.type,
        "name": integration.name,
        "connected": integration.is_active,
        "is_active": integration.is_active,
        "last_synced_at": integration.last_synced_at.isoformat() if hasattr(integration, 'last_synced_at') and integration.last_synced_at else None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None
    }


async def execute_workflow_async(workflow_id: str, run_id: str, db: Session):
    """Execute workflow steps asynchronously."""
    # This is a mock implementation for testing
    # In production, this would actually execute the workflow steps
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if run:
        await asyncio.sleep(0.1)  # Simulate some work
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.output = {"message": "Workflow executed successfully"}
        db.commit()