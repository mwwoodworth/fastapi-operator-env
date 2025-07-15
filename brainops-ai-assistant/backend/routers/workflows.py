"""Workflow automation API endpoints."""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services.workflow_engine import WorkflowEngine, TriggerType, StepType
from models.db import User
from utils.audit import AuditLogger

router = APIRouter(prefix="/workflows", tags=["workflows"])
audit_logger = AuditLogger()

# Initialize services
workflow_engine = WorkflowEngine()


class WorkflowCreate(BaseModel):
    """Workflow creation model."""
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    trigger: Dict[str, Any] = Field(..., description="Trigger configuration")
    steps: List[Dict[str, Any]] = Field(..., description="Workflow steps")
    enabled: bool = Field(default=True, description="Whether workflow is enabled")


class WorkflowUpdate(BaseModel):
    """Workflow update model."""
    name: Optional[str] = Field(default=None, description="Workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    trigger: Optional[Dict[str, Any]] = Field(default=None, description="Trigger configuration")
    steps: Optional[List[Dict[str, Any]]] = Field(default=None, description="Workflow steps")
    enabled: Optional[bool] = Field(default=None, description="Whether workflow is enabled")


class WorkflowRun(BaseModel):
    """Workflow run model."""
    trigger_data: Optional[Dict[str, Any]] = Field(default=None, description="Trigger data")
    triggered_by: str = Field(default="manual", description="Who triggered the workflow")


class WorkflowTemplate(BaseModel):
    """Workflow template model."""
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    template_data: Dict[str, Any] = Field(..., description="Template data")


class WebhookTrigger(BaseModel):
    """Webhook trigger model."""
    data: Dict[str, Any] = Field(..., description="Webhook data")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Request headers")


@router.post("/", response_model=Dict[str, Any])
async def create_workflow(
    workflow: WorkflowCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new workflow."""
    try:
        result = await workflow_engine.create_workflow(
            name=workflow.name,
            description=workflow.description,
            trigger=workflow.trigger,
            steps=workflow.steps,
            created_by=current_user.id,
            enabled=workflow.enabled
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="workflow_created",
            resource_type="workflow",
            resource_id=result.id,
            details={
                "name": workflow.name,
                "trigger_type": workflow.trigger.get("type"),
                "steps_count": len(workflow.steps)
            }
        )
        
        return {
            "id": result.id,
            "name": result.name,
            "description": result.description,
            "enabled": result.enabled,
            "created_at": result.created_at.isoformat(),
            "trigger": result.trigger,
            "steps": result.steps
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[Dict[str, Any]])
async def list_workflows(
    enabled: Optional[bool] = None,
    trigger_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """List workflows."""
    try:
        workflows = await workflow_engine.list_workflows(
            created_by=current_user.id,
            enabled=enabled,
            trigger_type=trigger_type,
            limit=limit,
            offset=offset
        )
        
        return [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "enabled": wf.enabled,
                "created_at": wf.created_at.isoformat(),
                "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
                "last_run": wf.last_run.isoformat() if wf.last_run else None,
                "run_count": wf.run_count,
                "error_count": wf.error_count,
                "trigger": wf.trigger,
                "steps": wf.steps
            }
            for wf in workflows
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific workflow."""
    try:
        workflow = await workflow_engine.get_workflow(workflow_id)
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "enabled": workflow.enabled,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            "last_run": workflow.last_run.isoformat() if workflow.last_run else None,
            "run_count": workflow.run_count,
            "error_count": workflow.error_count,
            "trigger": workflow.trigger,
            "steps": workflow.steps,
            "metadata": workflow.metadata
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/run", response_model=Dict[str, Any])
async def run_workflow(
    workflow_id: str,
    run_params: WorkflowRun,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Run a workflow."""
    try:
        workflow_run = await workflow_engine.run_workflow(
            workflow_id=workflow_id,
            trigger_data=run_params.trigger_data,
            triggered_by=f"user:{current_user.id}"
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="workflow_run_started",
            resource_type="workflow_run",
            resource_id=workflow_run.id,
            details={
                "workflow_id": workflow_id,
                "triggered_by": run_params.triggered_by
            }
        )
        
        return {
            "run_id": workflow_run.id,
            "workflow_id": workflow_run.workflow_id,
            "status": workflow_run.status,
            "started_at": workflow_run.started_at.isoformat(),
            "triggered_by": workflow_run.triggered_by,
            "trigger_data": workflow_run.trigger_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/runs", response_model=List[Dict[str, Any]])
async def get_workflow_runs(
    workflow_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get workflow runs."""
    try:
        runs = await workflow_engine.get_workflow_runs(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [
            {
                "id": run.id,
                "workflow_id": run.workflow_id,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_seconds": run.duration_seconds,
                "triggered_by": run.triggered_by,
                "trigger_data": run.trigger_data,
                "step_results": run.step_results,
                "error": run.error
            }
            for run in runs
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}", response_model=Dict[str, Any])
async def get_workflow_run(
    run_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific workflow run."""
    try:
        runs = await workflow_engine.get_workflow_runs(limit=1000)  # Get all runs
        
        workflow_run = None
        for run in runs:
            if run.id == run_id:
                workflow_run = run
                break
        
        if not workflow_run:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        
        return {
            "id": workflow_run.id,
            "workflow_id": workflow_run.workflow_id,
            "status": workflow_run.status,
            "started_at": workflow_run.started_at.isoformat(),
            "completed_at": workflow_run.completed_at.isoformat() if workflow_run.completed_at else None,
            "duration_seconds": workflow_run.duration_seconds,
            "triggered_by": workflow_run.triggered_by,
            "trigger_data": workflow_run.trigger_data,
            "step_results": workflow_run.step_results,
            "error": workflow_run.error,
            "metadata": workflow_run.metadata
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/cancel", response_model=Dict[str, Any])
async def cancel_workflow_run(
    run_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancel a running workflow."""
    try:
        success = await workflow_engine.cancel_workflow_run(run_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Workflow run not found or cannot be cancelled")
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="workflow_run_cancelled",
            resource_type="workflow_run",
            resource_id=run_id
        )
        
        return {
            "success": True,
            "message": "Workflow run cancelled"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/{webhook_id}/trigger", response_model=Dict[str, Any])
async def trigger_webhook(
    webhook_id: str,
    webhook_data: WebhookTrigger
):
    """Trigger a webhook."""
    try:
        result = await workflow_engine.trigger_webhook(
            webhook_id=webhook_id,
            data=webhook_data.data,
            headers=webhook_data.headers
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates", response_model=Dict[str, str])
async def create_workflow_template(
    template: WorkflowTemplate,
    current_user: User = Depends(get_current_user)
):
    """Create a workflow template."""
    try:
        template_id = await workflow_engine.create_workflow_template(
            name=template.name,
            description=template.description,
            template_data=template.template_data,
            created_by=current_user.id
        )
        
        await audit_logger.log_action(
            user_id=current_user.id,
            action="workflow_template_created",
            resource_type="workflow_template",
            resource_id=template_id,
            details={"name": template.name}
        )
        
        return {"template_id": template_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trigger-types", response_model=List[Dict[str, str]])
async def get_trigger_types():
    """Get available trigger types."""
    return [
        {"type": trigger_type.value, "description": trigger_type.value.replace("_", " ").title()}
        for trigger_type in TriggerType
    ]


@router.get("/step-types", response_model=List[Dict[str, str]])
async def get_step_types():
    """Get available step types."""
    return [
        {"type": step_type.value, "description": step_type.value.replace("_", " ").title()}
        for step_type in StepType
    ]


@router.get("/health")
async def health_check():
    """Health check for workflow engine."""
    try:
        # Check workflow engine health
        active_runs_count = len(workflow_engine.active_runs)
        
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "workflow_engine",
            "active_runs": active_runs_count,
            "supported_triggers": [t.value for t in TriggerType],
            "supported_steps": [s.value for s in StepType]
        }
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))