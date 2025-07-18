"""
Enhanced Automation and Workflow Management Routes

This module provides comprehensive automation capabilities including:
- Workflow CRUD with versioning
- Advanced trigger management (webhooks, schedules, events)
- Third-party integrations
- Bulk operations
- Admin endpoints
- Monitoring and health checks
- Error handling and logging
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request, Response, status
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import and_, or_, func
from uuid import uuid4
import asyncio
import json
import logging
from enum import Enum
import hashlib
import hmac
from pydantic import BaseModel, Field, validator
import httpx
from croniter import croniter

from ..core.auth import get_current_user, get_admin_user
from ..db.business_models import User, Workflow, WorkflowRun, Integration
from ..db.models import WebhookEvent
from ..core.database import get_db
from ..core.pagination import paginate
from ..core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Enums for better type safety
class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"
    API = "api"
    EMAIL = "email"
    FILE = "file"

class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    ERROR = "error"

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class StepType(str, Enum):
    HTTP = "http"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    TRANSFORM = "transform"
    NOTIFICATION = "notification"
    DATABASE = "database"
    AI = "ai"
    INTEGRATION = "integration"
    SCRIPT = "script"
    APPROVAL = "approval"
    DELAY = "delay"

class IntegrationType(str, Enum):
    SLACK = "slack"
    GITHUB = "github"
    NOTION = "notion"
    DISCORD = "discord"
    TEAMS = "teams"
    JIRA = "jira"
    TRELLO = "trello"
    ASANA = "asana"
    CLICKUP = "clickup"
    AIRTABLE = "airtable"
    GOOGLE_SHEETS = "google_sheets"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    MAILCHIMP = "mailchimp"
    SENDGRID = "sendgrid"
    TWILIO = "twilio"
    STRIPE = "stripe"
    SHOPIFY = "shopify"
    WORDPRESS = "wordpress"
    MEDIUM = "medium"

# Request/Response Models
class WorkflowStepModel(BaseModel):
    id: str
    type: StepType
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]
    next_steps: List[str] = []
    error_handler: Optional[str] = None
    retry_config: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 300  # seconds
    conditions: Optional[List[Dict[str, Any]]] = None

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., max_length=1000)
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    steps: List[WorkflowStepModel]
    is_active: bool = True
    is_public: bool = False
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    version: Optional[str] = "1.0.0"
    
    @validator('trigger_config')
    def validate_trigger_config(cls, v, values):
        trigger_type = values.get('trigger_type')
        if trigger_type == TriggerType.SCHEDULE:
            if 'cron' not in v:
                raise ValueError("Schedule trigger requires 'cron' in config")
            if not croniter.is_valid(v['cron']):
                raise ValueError("Invalid cron expression")
        elif trigger_type == TriggerType.WEBHOOK:
            if 'secret' not in v:
                v['secret'] = str(uuid4())
        return v

class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    trigger_type: Optional[TriggerType] = None
    trigger_config: Optional[Dict[str, Any]] = None
    steps: Optional[List[WorkflowStepModel]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class WorkflowBulkRequest(BaseModel):
    workflow_ids: List[str]
    action: str = Field(..., pattern="^(activate|deactivate|archive|delete|export)$")
    options: Dict[str, Any] = {}

class TriggerCreateRequest(BaseModel):
    workflow_id: str
    trigger_type: TriggerType
    config: Dict[str, Any]
    is_enabled: bool = True
    name: Optional[str] = None
    description: Optional[str] = None

class TriggerUpdateRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None
    name: Optional[str] = None
    description: Optional[str] = None

class IntegrationConnectRequest(BaseModel):
    integration_type: IntegrationType
    config: Dict[str, Any]
    name: str
    description: Optional[str] = None
    scopes: List[str] = []

class IntegrationUpdateRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class WorkflowExecuteRequest(BaseModel):
    input_data: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    dry_run: bool = False
    async_execution: bool = True

class WebhookTestRequest(BaseModel):
    webhook_url: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = {}
    method: str = "POST"

class WorkflowImportRequest(BaseModel):
    workflows: List[Dict[str, Any]]
    mode: str = Field("merge", pattern="^(merge|overwrite|skip)$")
    dry_run: bool = False

# Health check models
class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, Dict[str, Any]]
    metrics: Dict[str, Any]

# Basic workflow endpoints
@router.post("/workflows", response_model=Dict[str, Any])
async def create_workflow(
    request: WorkflowCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new workflow with validation."""
    try:
        # Validate workflow steps
        step_ids = {step.id for step in request.steps}
        for step in request.steps:
            for next_step in step.next_steps:
                if next_step != "end" and next_step not in step_ids:
                    raise HTTPException(400, f"Invalid next_step reference: {next_step}")
            if step.error_handler and step.error_handler not in step_ids:
                raise HTTPException(400, f"Invalid error_handler reference: {step.error_handler}")
        
        workflow = Workflow(
            id=str(uuid4()),
            name=request.name,
            description=request.description,
            owner_id=current_user.id,
            trigger_type=request.trigger_type.value,
            trigger_config=request.trigger_config,
            steps=[step.dict() for step in request.steps],
            is_active=request.is_active,
            tags=request.tags,
            meta_data=request.metadata,
            version=request.version
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        # Log workflow creation
        logger.info(f"Workflow created: {workflow.id} by user {current_user.id}")
        
        # Schedule if needed
        if workflow.is_active and workflow.trigger_type == TriggerType.SCHEDULE.value:
            background_tasks.add_task(schedule_workflow, workflow.id)
        
        return workflow_to_dict(workflow)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error creating workflow: {str(e)}")
        db.rollback()
        raise HTTPException(500, f"Failed to create workflow: {str(e)}")

@router.get("/workflows", response_model=Dict[str, Any])
async def list_workflows(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    trigger_type: Optional[TriggerType] = None,
    status: Optional[WorkflowStatus] = None,
    tags: Optional[List[str]] = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|name|runs_count)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List workflows with filtering, searching, and pagination."""
    query = db.query(Workflow).filter(Workflow.owner_id == current_user.id)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Workflow.name.ilike(f"%{search}%"),
                Workflow.description.ilike(f"%{search}%")
            )
        )
    
    if trigger_type:
        query = query.filter(Workflow.trigger_type == trigger_type.value)
    
    if status:
        if status == WorkflowStatus.ACTIVE:
            query = query.filter(Workflow.is_active == True)
        elif status == WorkflowStatus.PAUSED:
            query = query.filter(Workflow.is_active == False)
    
    if tags:
        for tag in tags:
            query = query.filter(Workflow.tags.contains([tag]))
    
    # Apply sorting
    if sort_by == "runs_count":
        query = query.outerjoin(WorkflowRun).group_by(Workflow.id)
        order_by = func.count(WorkflowRun.id)
    else:
        order_by = getattr(Workflow, sort_by)
    
    if sort_order == "desc":
        query = query.order_by(order_by.desc())
    else:
        query = query.order_by(order_by.asc())
    
    # Paginate
    total = query.count()
    workflows = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [workflow_to_dict(w) for w in workflows],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    include_runs: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workflow details with optional run history."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    result = workflow_to_dict(workflow)
    
    if include_runs:
        runs = db.query(WorkflowRun).filter(
            WorkflowRun.workflow_id == workflow_id
        ).order_by(WorkflowRun.started_at.desc()).limit(10).all()
        result["recent_runs"] = [run_to_dict(run) for run in runs]
    
    return result

@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a workflow with version tracking."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    # Track version
    old_version = workflow.version or "1.0.0"
    version_parts = old_version.split(".")
    version_parts[2] = str(int(version_parts[2]) + 1)
    new_version = ".".join(version_parts)
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "steps" and value is not None:
            value = [step.dict() if hasattr(step, 'dict') else step for step in value]
        setattr(workflow, field, value)
    
    workflow.version = new_version
    workflow.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(workflow)
        logger.info(f"Workflow updated: {workflow_id} to version {new_version}")
        return workflow_to_dict(workflow)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating workflow: {str(e)}")
        raise HTTPException(500, f"Failed to update workflow: {str(e)}")

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    force: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a workflow with optional force delete."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    # Check for active runs
    active_runs = db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.status.in_([RunStatus.RUNNING.value, RunStatus.PENDING.value])
    ).count()
    
    if active_runs > 0 and not force:
        raise HTTPException(400, f"Cannot delete workflow with {active_runs} active runs. Use force=true to override.")
    
    try:
        db.delete(workflow)
        db.commit()
        logger.info(f"Workflow deleted: {workflow_id}")
        return {"message": "Workflow deleted successfully", "id": workflow_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting workflow: {str(e)}")
        raise HTTPException(500, f"Failed to delete workflow: {str(e)}")

# Workflow execution endpoints
@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a workflow with options for dry run and sync/async execution."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    if not workflow.is_active and not request.dry_run:
        raise HTTPException(400, "Workflow is not active")
    
    # Create workflow run
    run = WorkflowRun(
        id=str(uuid4()),
        workflow_id=workflow.id,
        status=RunStatus.PENDING.value if request.dry_run else RunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
        trigger_data={
            "type": "manual",
            "user_id": str(current_user.id),
            "input": request.input_data,
            "context": request.context,
            "dry_run": request.dry_run
        },
        steps_total=len(workflow.steps) if isinstance(workflow.steps, list) else 1
    )
    
    db.add(run)
    db.commit()
    db.refresh(run)
    
    if request.dry_run:
        # Perform dry run validation
        validation_result = validate_workflow_execution(workflow, request.input_data)
        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.utcnow()
        run.output = {"dry_run": True, "validation": validation_result}
        db.commit()
        return run_to_dict(run, detailed=True)
    
    if request.async_execution:
        # Execute asynchronously
        background_tasks.add_task(
            execute_workflow_async,
            str(workflow.id),
            str(run.id),
            request.input_data,
            request.context
        )
        return run_to_dict(run)
    else:
        # Execute synchronously
        try:
            result = await execute_workflow_sync(workflow, run, request.input_data, request.context, db)
            return result
        except HTTPException as e:
            run.status = RunStatus.FAILED.value
            run.error = str(e)
            run.completed_at = datetime.utcnow()
            db.commit()
            raise
        except Exception as e:
            run.status = RunStatus.FAILED.value
            run.error = str(e)
            run.completed_at = datetime.utcnow()
            db.commit()
            raise HTTPException(500, f"Workflow execution failed: {str(e)}")

@router.get("/workflows/{workflow_id}/runs")
async def get_workflow_runs(
    workflow_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[RunStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workflow execution history with filtering."""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    query = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
    
    if status:
        query = query.filter(WorkflowRun.status == status.value)
    
    if start_date:
        query = query.filter(WorkflowRun.started_at >= start_date)
    
    if end_date:
        query = query.filter(WorkflowRun.started_at <= end_date)
    
    query = query.order_by(WorkflowRun.started_at.desc())
    
    total = query.count()
    runs = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [run_to_dict(run) for run in runs],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "stats": get_run_stats(workflow_id, db)
    }

@router.get("/runs/{run_id}")
async def get_workflow_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a workflow run."""
    run = db.query(WorkflowRun).join(Workflow).filter(
        WorkflowRun.id == run_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(404, "Workflow run not found")
    
    return run_to_dict(run, detailed=True)

@router.put("/runs/{run_id}/cancel")
async def cancel_workflow_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a running workflow execution."""
    run = db.query(WorkflowRun).join(Workflow).filter(
        WorkflowRun.id == run_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(404, "Workflow run not found")
    
    if run.status not in [RunStatus.RUNNING.value, RunStatus.PENDING.value]:
        raise HTTPException(400, f"Cannot cancel run with status: {run.status}")
    
    run.status = RunStatus.CANCELLED.value
    run.completed_at = datetime.utcnow()
    run.error = "Cancelled by user"
    
    db.commit()
    
    # TODO: Implement actual cancellation logic for running workflows
    
    return {"message": "Workflow run cancelled", "run_id": run_id}

@router.post("/runs/{run_id}/retry")
async def retry_workflow_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retry a failed workflow run."""
    run = db.query(WorkflowRun).join(Workflow).filter(
        WorkflowRun.id == run_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(404, "Workflow run not found")
    
    if run.status != RunStatus.FAILED.value:
        raise HTTPException(400, "Can only retry failed runs")
    
    workflow = db.query(Workflow).filter(Workflow.id == run.workflow_id).first()
    if not workflow.is_active:
        raise HTTPException(400, "Workflow is not active")
    
    # Create new run based on failed run
    new_run = WorkflowRun(
        id=str(uuid4()),
        workflow_id=run.workflow_id,
        status=RunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
        trigger_data=run.trigger_data,
        steps_total=run.steps_total,
        parent_run_id=run.id
    )
    
    db.add(new_run)
    db.commit()
    
    background_tasks.add_task(
        execute_workflow_async,
        run.workflow_id,
        new_run.id,
        run.trigger_data.get("input", {}),
        run.trigger_data.get("context", {})
    )
    
    return run_to_dict(new_run)

# Trigger management endpoints
@router.post("/triggers")
async def create_trigger(
    request: TriggerCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a workflow trigger."""
    workflow = db.query(Workflow).filter(
        Workflow.id == request.workflow_id,
        Workflow.owner_id == current_user.id
    ).first()
    
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    
    # Validate trigger configuration
    if request.trigger_type == TriggerType.SCHEDULE:
        if 'cron' not in request.config:
            raise HTTPException(400, "Schedule trigger requires 'cron' in config")
        if not croniter.is_valid(request.config['cron']):
            raise HTTPException(400, "Invalid cron expression")
    elif request.trigger_type == TriggerType.WEBHOOK:
        if 'secret' not in request.config:
            request.config['secret'] = str(uuid4())
    
    trigger_id = str(uuid4())
    
    # Store trigger in workflow metadata
    if 'triggers' not in workflow.meta_data:
        workflow.meta_data['triggers'] = []
    
    trigger = {
        "id": trigger_id,
        "type": request.trigger_type.value,
        "config": request.config,
        "is_enabled": request.is_enabled,
        "name": request.name or f"{request.trigger_type.value} trigger",
        "description": request.description,
        "created_at": datetime.utcnow().isoformat()
    }
    
    workflow.meta_data['triggers'].append(trigger)
    
    # Mark as modified for SQLAlchemy to detect changes
    flag_modified(workflow, 'meta_data')
    db.commit()
    
    return trigger

@router.get("/triggers")
async def list_triggers(
    workflow_id: Optional[str] = None,
    trigger_type: Optional[TriggerType] = None,
    is_enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List workflow triggers."""
    query = db.query(Workflow).filter(Workflow.owner_id == current_user.id)
    
    if workflow_id:
        query = query.filter(Workflow.id == workflow_id)
    
    workflows = query.all()
    triggers = []
    
    for workflow in workflows:
        workflow_triggers = workflow.meta_data.get('triggers', [])
        for trigger in workflow_triggers:
            if trigger_type and trigger['type'] != trigger_type.value:
                continue
            if is_enabled is not None and trigger['is_enabled'] != is_enabled:
                continue
            
            trigger['workflow_id'] = workflow.id
            trigger['workflow_name'] = workflow.name
            triggers.append(trigger)
    
    return triggers

@router.get("/triggers/{trigger_id}")
async def get_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trigger details."""
    workflows = db.query(Workflow).filter(Workflow.owner_id == current_user.id).all()
    
    for workflow in workflows:
        triggers = workflow.meta_data.get('triggers', [])
        for trigger in triggers:
            if trigger['id'] == trigger_id:
                trigger['workflow_id'] = workflow.id
                trigger['workflow_name'] = workflow.name
                return trigger
    
    raise HTTPException(404, "Trigger not found")

@router.put("/triggers/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    request: TriggerUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a trigger."""
    workflows = db.query(Workflow).filter(Workflow.owner_id == current_user.id).all()
    
    for workflow in workflows:
        triggers = workflow.meta_data.get('triggers', [])
        for i, trigger in enumerate(triggers):
            if trigger['id'] == trigger_id:
                # Update trigger
                update_data = request.dict(exclude_unset=True)
                trigger.update(update_data)
                trigger['updated_at'] = datetime.utcnow().isoformat()
                
                workflow.meta_data['triggers'][i] = trigger
                # Mark as modified for SQLAlchemy to detect changes
                flag_modified(workflow, 'meta_data')
                db.commit()
                
                return trigger
    
    raise HTTPException(404, "Trigger not found")

@router.delete("/triggers/{trigger_id}")
async def delete_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a trigger."""
    workflows = db.query(Workflow).filter(Workflow.owner_id == current_user.id).all()
    
    for workflow in workflows:
        triggers = workflow.meta_data.get('triggers', [])
        for i, trigger in enumerate(triggers):
            if trigger['id'] == trigger_id:
                workflow.meta_data['triggers'].pop(i)
                # Mark as modified for SQLAlchemy to detect changes
                flag_modified(workflow, 'meta_data')
                db.commit()
                return {"message": "Trigger deleted successfully"}
    
    raise HTTPException(404, "Trigger not found")

# Webhook endpoints
@router.post("/webhooks/{webhook_id}/receive")
async def receive_webhook(
    webhook_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Receive webhook and trigger associated workflows."""
    body = await request.body()
    headers = dict(request.headers)
    
    # Find workflows with this webhook trigger
    workflows = db.query(Workflow).filter(
        Workflow.trigger_type == TriggerType.WEBHOOK.value,
        Workflow.is_active == True
    ).all()
    
    triggered_count = 0
    
    for workflow in workflows:
        webhook_config = workflow.trigger_config
        if webhook_config.get('webhook_id') == webhook_id:
            # Verify webhook signature if configured
            if 'secret' in webhook_config:
                signature = headers.get('x-webhook-signature', '')
                expected_signature = hmac.new(
                    webhook_config['secret'].encode(),
                    body,
                    hashlib.sha256
                ).hexdigest()
                
                if signature != expected_signature:
                    logger.warning(f"Invalid webhook signature for workflow {workflow.id}")
                    continue
            
            # Log webhook event
            event = WebhookEvent(
                id=str(uuid4()),
                source=f"webhook_{webhook_id}",
                event_type="workflow_trigger",
                headers=headers,
                payload=json.loads(body) if body else {},
                signature=headers.get('x-webhook-signature'),
                processed=False
            )
            db.add(event)
            
            # Create workflow run
            run = WorkflowRun(
                id=str(uuid4()),
                workflow_id=workflow.id,
                status=RunStatus.RUNNING.value,
                started_at=datetime.utcnow(),
                trigger_data={
                    "type": "webhook",
                    "webhook_id": webhook_id,
                    "headers": headers,
                    "body": json.loads(body) if body else {}
                },
                steps_total=len(workflow.steps)
            )
            
            db.add(run)
            db.commit()
            
            # Execute workflow
            background_tasks.add_task(
                execute_workflow_async,
                workflow.id,
                run.id,
                json.loads(body) if body else {},
                {"headers": headers}
            )
            
            triggered_count += 1
    
    if triggered_count == 0:
        raise HTTPException(404, "No active workflows found for this webhook")
    
    return {
        "message": f"Webhook received and triggered {triggered_count} workflow(s)",
        "webhook_id": webhook_id,
        "triggered_count": triggered_count
    }

@router.post("/webhooks/test")
async def test_webhook(
    request: WebhookTestRequest,
    current_user: User = Depends(get_current_user)
):
    """Test a webhook endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=request.webhook_url,
                json=request.payload,
                headers=request.headers,
                timeout=10.0
            )
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:1000],  # Limit response size
                "success": 200 <= response.status_code < 300
            }
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }

@router.get("/webhooks/{webhook_id}/events")
async def get_webhook_events(
    webhook_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get webhook event history."""
    # Verify user owns workflows with this webhook
    workflow = db.query(Workflow).filter(
        Workflow.owner_id == current_user.id,
        Workflow.trigger_type == TriggerType.WEBHOOK.value
    ).first()
    
    if not workflow or workflow.trigger_config.get('webhook_id') != webhook_id:
        raise HTTPException(403, "Access denied")
    
    query = db.query(WebhookEvent).filter(
        WebhookEvent.source == f"webhook_{webhook_id}"
    ).order_by(WebhookEvent.received_at.desc())
    
    total = query.count()
    events = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [
            {
                "id": str(event.id),
                "source": event.source,
                "event_type": event.event_type,
                "headers": event.headers,
                "payload": event.payload,
                "processed": event.processed,
                "received_at": event.received_at.isoformat() if hasattr(event, 'received_at') and event.received_at else datetime.utcnow().isoformat()
            }
            for event in events
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

# Integration management endpoints
@router.get("/integrations/available")
async def list_available_integrations():
    """List all available integration types."""
    integrations = []
    
    for integration_type in IntegrationType:
        integrations.append({
            "id": integration_type.value,
            "name": integration_type.value.replace("_", " ").title(),
            "description": get_integration_description(integration_type),
            "icon": f"{integration_type.value}-icon.png",
            "required_config": get_integration_required_config(integration_type),
            "available_actions": get_integration_actions(integration_type)
        })
    
    return integrations

@router.get("/integrations/connected")
async def list_connected_integrations(
    integration_type: Optional[IntegrationType] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's connected integrations."""
    query = db.query(Integration).filter(Integration.user_id == current_user.id)
    
    if integration_type:
        query = query.filter(Integration.type == integration_type.value)
    
    if is_active is not None:
        query = query.filter(Integration.is_active == is_active)
    
    integrations = query.all()
    
    return [
        {
            "id": str(integration.id),
            "type": integration.type,
            "name": integration.name,
            "description": getattr(integration, 'description', None),
            "is_active": integration.is_active,
            "scopes": integration.meta_data.get('scopes', []) if integration.meta_data else [],
            "created_at": integration.created_at.isoformat() if integration.created_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if hasattr(integration, 'last_synced_at') and integration.last_synced_at else None
        }
        for integration in integrations
    ]

@router.post("/integrations/connect")
async def connect_integration(
    request: IntegrationConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Connect a new integration."""
    # Check if already connected
    existing = db.query(Integration).filter(
        Integration.user_id == current_user.id,
        Integration.type == request.integration_type.value
    ).first()
    
    if existing:
        raise HTTPException(400, f"{request.integration_type.value} integration already connected")
    
    # Validate configuration
    required_config = get_integration_required_config(request.integration_type)
    for field in required_config:
        if field not in request.config:
            raise HTTPException(400, f"Missing required field: {field}")
    
    integration = Integration(
        id=str(uuid4()),
        user_id=current_user.id,
        type=request.integration_type.value,
        name=request.name,
        config=request.config,
        is_active=True,
        meta_data={
            "description": request.description,
            "scopes": request.scopes
        }
    )
    
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    logger.info(f"Integration connected: {integration.type} for user {current_user.id}")
    
    return {
        "id": str(integration.id),
        "type": integration.type,
        "name": integration.name,
        "is_active": integration.is_active,
        "created_at": integration.created_at.isoformat() if integration.created_at else datetime.utcnow().isoformat()
    }

@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: str,
    request: IntegrationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an integration."""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "config" and value:
            # Merge config
            integration.config.update(value)
            flag_modified(integration, 'config')
        elif field == "meta_data" and value:
            integration.meta_data.update(value)
            flag_modified(integration, 'meta_data')
        else:
            setattr(integration, field, value)
    
    db.commit()
    db.refresh(integration)
    
    return {
        "id": str(integration.id),
        "type": integration.type,
        "name": integration.name,
        "config": integration.config,
        "is_active": integration.is_active,
        "updated": True
    }

@router.delete("/integrations/{integration_id}")
async def disconnect_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect an integration."""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    db.delete(integration)
    db.commit()
    
    logger.info(f"Integration disconnected: {integration.type} for user {current_user.id}")
    
    return {"message": f"{integration.name} integration disconnected successfully"}

@router.get("/integrations/{integration_id}/status")
async def get_integration_status(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get integration status and health."""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    # Test integration connection
    health = await test_integration_health(integration)
    
    return {
        "id": str(integration.id),
        "type": integration.type,
        "name": integration.name,
        "is_active": integration.is_active,
        "health": health,
        "last_synced_at": integration.last_synced_at.isoformat() if hasattr(integration, 'last_synced_at') and integration.last_synced_at else None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None
    }

@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test an integration connection."""
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.user_id == current_user.id
    ).first()
    
    if not integration:
        raise HTTPException(404, "Integration not found")
    
    result = await test_integration_connection(integration)
    
    return result

# Bulk operations
@router.post("/workflows/bulk")
async def bulk_workflow_operations(
    request: WorkflowBulkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform bulk operations on workflows."""
    workflows = db.query(Workflow).filter(
        Workflow.id.in_(request.workflow_ids),
        Workflow.owner_id == current_user.id
    ).all()
    
    if len(workflows) != len(request.workflow_ids):
        raise HTTPException(400, "Some workflows not found or access denied")
    
    results = []
    
    for workflow in workflows:
        try:
            if request.action == "activate":
                workflow.is_active = True
                result = {"id": workflow.id, "status": "activated"}
            elif request.action == "deactivate":
                workflow.is_active = False
                result = {"id": workflow.id, "status": "deactivated"}
            elif request.action == "archive":
                workflow.meta_data['archived'] = True
                workflow.meta_data['archived_at'] = datetime.utcnow().isoformat()
                flag_modified(workflow, 'meta_data')
                result = {"id": workflow.id, "status": "archived"}
            elif request.action == "delete":
                db.delete(workflow)
                result = {"id": workflow.id, "status": "deleted"}
            elif request.action == "export":
                result = {
                    "id": workflow.id,
                    "status": "exported",
                    "data": workflow_to_dict(workflow, include_sensitive=False)
                }
            
            results.append(result)
        except Exception as e:
            results.append({
                "id": workflow.id,
                "status": "error",
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "action": request.action,
        "total": len(workflows),
        "results": results
    }

@router.post("/workflows/import")
async def import_workflows(
    request: WorkflowImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import workflows from exported data."""
    results = []
    
    for workflow_data in request.workflows:
        try:
            # Check if workflow exists
            existing = None
            if 'id' in workflow_data:
                existing = db.query(Workflow).filter(
                    Workflow.id == workflow_data['id'],
                    Workflow.owner_id == current_user.id
                ).first()
            
            if existing:
                if request.mode == "skip":
                    results.append({
                        "name": workflow_data.get('name'),
                        "status": "skipped",
                        "message": "Workflow already exists"
                    })
                    continue
                elif request.mode == "overwrite":
                    # Update existing workflow
                    for key, value in workflow_data.items():
                        if key not in ['id', 'owner_id', 'created_at']:
                            setattr(existing, key, value)
                    
                    if not request.dry_run:
                        db.commit()
                    
                    results.append({
                        "name": workflow_data.get('name'),
                        "status": "updated",
                        "id": existing.id
                    })
                elif request.mode == "merge":
                    # Create new version
                    workflow_data['id'] = str(uuid4())
                    workflow_data['name'] = f"{workflow_data.get('name', 'Imported')} (Copy)"
            
            if not existing or request.mode == "merge":
                # Create new workflow
                workflow = Workflow(
                    id=workflow_data.get('id', str(uuid4())),
                    owner_id=current_user.id,
                    name=workflow_data.get('name', 'Imported Workflow'),
                    description=workflow_data.get('description', ''),
                    trigger_type=workflow_data.get('trigger_type', 'manual'),
                    trigger_config=workflow_data.get('trigger_config', {}),
                    steps=workflow_data.get('steps', []),
                    is_active=workflow_data.get('is_active', False),
                    tags=workflow_data.get('tags', []),
                    metadata=workflow_data.get('metadata', {}),
                    version=workflow_data.get('version', '1.0.0')
                )
                
                if not request.dry_run:
                    db.add(workflow)
                
                results.append({
                    "name": workflow.name,
                    "status": "created",
                    "id": workflow.id
                })
                
        except Exception as e:
            results.append({
                "name": workflow_data.get('name', 'Unknown'),
                "status": "error",
                "error": str(e)
            })
    
    if not request.dry_run:
        db.commit()
    
    return {
        "mode": request.mode,
        "dry_run": request.dry_run,
        "total": len(request.workflows),
        "results": results
    }

# Admin endpoints
@router.get("/admin/workflows", dependencies=[Depends(get_admin_user)])
async def admin_list_all_workflows(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all workflows."""
    query = db.query(Workflow)
    
    if user_id:
        query = query.filter(Workflow.owner_id == user_id)
    
    total = query.count()
    workflows = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [workflow_to_dict(w, include_owner=True) for w in workflows],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/admin/runs", dependencies=[Depends(get_admin_user)])
async def admin_list_all_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[RunStatus] = None,
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all workflow runs."""
    query = db.query(WorkflowRun)
    
    if status:
        query = query.filter(WorkflowRun.status == status.value)
    
    query = query.order_by(WorkflowRun.started_at.desc())
    
    total = query.count()
    runs = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": [run_to_dict(run, include_workflow=True) for run in runs],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/admin/stats", dependencies=[Depends(get_admin_user)])
async def get_admin_stats(db: Session = Depends(get_db)):
    """Get system-wide automation statistics."""
    stats = {
        "total_workflows": db.query(Workflow).count(),
        "active_workflows": db.query(Workflow).filter(Workflow.is_active == True).count(),
        "total_runs": db.query(WorkflowRun).count(),
        "runs_by_status": {},
        "integrations_count": db.query(Integration).count(),
        "webhook_events_count": db.query(WebhookEvent).count()
    }
    
    # Get runs by status
    for status in RunStatus:
        count = db.query(WorkflowRun).filter(WorkflowRun.status == status.value).count()
        stats["runs_by_status"][status.value] = count
    
    return stats

# Health and monitoring endpoints
@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Check automation service health."""
    services = {}
    
    # Check database
    try:
        db.execute("SELECT 1")
        services["database"] = {"status": "healthy", "response_time": 0.001}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Check scheduler
    services["scheduler"] = {
        "status": "healthy",
        "active_schedules": 0  # TODO: Implement actual scheduler check
    }
    
    # Check integrations
    active_integrations = db.query(Integration).filter(Integration.is_active == True).count()
    services["integrations"] = {
        "status": "healthy",
        "active_count": active_integrations
    }
    
    # Calculate metrics
    metrics = {
        "workflows_total": db.query(Workflow).count(),
        "workflows_active": db.query(Workflow).filter(Workflow.is_active == True).count(),
        "runs_last_hour": db.query(WorkflowRun).filter(
            WorkflowRun.started_at >= datetime.utcnow() - timedelta(hours=1)
        ).count(),
        "avg_run_duration": 0  # TODO: Calculate actual average
    }
    
    overall_status = "healthy" if all(
        s.get("status") == "healthy" for s in services.values()
    ) else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services,
        metrics=metrics
    )

@router.get("/metrics")
async def get_metrics(
    time_range: str = Query("1h", pattern="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's automation metrics."""
    # Calculate time range
    time_ranges = {
        "1h": timedelta(hours=1),
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30)
    }
    
    start_time = datetime.utcnow() - time_ranges[time_range]
    
    # Get user's workflows
    user_workflows = db.query(Workflow.id).filter(
        Workflow.owner_id == current_user.id
    ).subquery()
    
    # Calculate metrics
    metrics = {
        "time_range": time_range,
        "workflows": {
            "total": db.query(Workflow).filter(Workflow.owner_id == current_user.id).count(),
            "active": db.query(Workflow).filter(
                Workflow.owner_id == current_user.id,
                Workflow.is_active == True
            ).count()
        },
        "runs": {
            "total": db.query(WorkflowRun).filter(
                WorkflowRun.workflow_id.in_(user_workflows),
                WorkflowRun.started_at >= start_time
            ).count(),
            "by_status": {}
        },
        "performance": {
            "avg_duration_seconds": 0,
            "success_rate": 0
        }
    }
    
    # Get runs by status
    for status in RunStatus:
        count = db.query(WorkflowRun).filter(
            WorkflowRun.workflow_id.in_(user_workflows),
            WorkflowRun.started_at >= start_time,
            WorkflowRun.status == status.value
        ).count()
        metrics["runs"]["by_status"][status.value] = count
    
    # Calculate success rate
    total_completed = metrics["runs"]["by_status"].get(RunStatus.COMPLETED.value, 0)
    total_failed = metrics["runs"]["by_status"].get(RunStatus.FAILED.value, 0)
    if total_completed + total_failed > 0:
        metrics["performance"]["success_rate"] = total_completed / (total_completed + total_failed)
    
    return metrics

# Helper functions
def workflow_to_dict(workflow: Workflow, include_sensitive: bool = True, include_owner: bool = False) -> Dict[str, Any]:
    """Convert workflow to dictionary."""
    result = {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "trigger_type": workflow.trigger_type,
        "trigger_config": workflow.trigger_config if include_sensitive else {k: v for k, v in workflow.trigger_config.items() if k != 'secret'},
        "steps": workflow.steps,
        "is_active": workflow.is_active,
        "is_public": workflow.meta_data.get('is_public', False),
        "tags": workflow.tags or [],
        "metadata": workflow.meta_data or {},
        "version": workflow.version or "1.0.0",
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat()
    }
    
    if include_owner:
        result["owner_id"] = workflow.owner_id
    
    return result

def run_to_dict(run: WorkflowRun, detailed: bool = False, include_workflow: bool = False) -> Dict[str, Any]:
    """Convert workflow run to dictionary."""
    result = {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": (run.completed_at - run.started_at).total_seconds() if run.completed_at else None,
        "trigger_type": run.trigger_data.get("type", "unknown") if run.trigger_data else "unknown",
        "steps_completed": run.steps_completed,
        "steps_total": run.steps_total,
        "error": run.error
    }
    
    if detailed:
        result["trigger_data"] = run.trigger_data
        result["output"] = run.output
        result["logs"] = run.logs
    
    if include_workflow and hasattr(run, 'workflow'):
        result["workflow_name"] = run.workflow.name
    
    return result

def validate_workflow_execution(workflow: Workflow, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate workflow can be executed."""
    validation = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check workflow is active
    if not workflow.is_active:
        validation["warnings"].append("Workflow is not active")
    
    # Validate steps
    if not workflow.steps:
        validation["valid"] = False
        validation["errors"].append("Workflow has no steps")
    
    # Validate step references
    step_ids = {step['id'] for step in workflow.steps}
    for step in workflow.steps:
        for next_step in step.get('next_steps', []):
            if next_step != 'end' and next_step not in step_ids:
                validation["valid"] = False
                validation["errors"].append(f"Invalid next_step reference: {next_step}")
    
    return validation

async def execute_workflow_sync(workflow: Workflow, run: WorkflowRun, input_data: Dict[str, Any], context: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Execute workflow synchronously."""
    # Mock implementation
    await asyncio.sleep(0.1)
    
    run.status = RunStatus.COMPLETED.value
    run.completed_at = datetime.utcnow()
    run.steps_completed = run.steps_total
    run.output = {"message": "Workflow executed successfully", "input": input_data}
    
    db.commit()
    
    return run_to_dict(run, detailed=True)

async def execute_workflow_async(workflow_id: str, run_id: str, input_data: Dict[str, Any], context: Dict[str, Any]):
    """Execute workflow asynchronously."""
    # Mock implementation
    # In production, this would be handled by a background task queue
    logger.info(f"Executing workflow {workflow_id} run {run_id}")
    await asyncio.sleep(1)

def schedule_workflow(workflow_id: str):
    """Schedule workflow execution."""
    # Mock implementation
    # In production, this would add to scheduler
    logger.info(f"Scheduling workflow {workflow_id}")

def get_integration_description(integration_type: IntegrationType) -> str:
    """Get integration description."""
    descriptions = {
        IntegrationType.SLACK: "Send messages and notifications to Slack channels",
        IntegrationType.GITHUB: "Interact with GitHub repositories, issues, and pull requests",
        IntegrationType.NOTION: "Create and update pages in Notion",
        IntegrationType.DISCORD: "Send messages to Discord servers",
        IntegrationType.TEAMS: "Send messages to Microsoft Teams",
        IntegrationType.JIRA: "Create and update issues in Jira",
        IntegrationType.TRELLO: "Manage cards and boards in Trello",
        IntegrationType.ASANA: "Create and manage tasks in Asana",
        IntegrationType.CLICKUP: "Manage tasks and projects in ClickUp",
        IntegrationType.AIRTABLE: "Read and write data to Airtable bases",
        IntegrationType.GOOGLE_SHEETS: "Read and write data to Google Sheets",
        IntegrationType.SALESFORCE: "Manage leads and opportunities in Salesforce",
        IntegrationType.HUBSPOT: "Manage contacts and deals in HubSpot",
        IntegrationType.MAILCHIMP: "Send emails and manage subscribers",
        IntegrationType.SENDGRID: "Send transactional emails",
        IntegrationType.TWILIO: "Send SMS and make phone calls",
        IntegrationType.STRIPE: "Process payments and manage subscriptions",
        IntegrationType.SHOPIFY: "Manage products and orders",
        IntegrationType.WORDPRESS: "Create and update posts",
        IntegrationType.MEDIUM: "Publish articles to Medium"
    }
    return descriptions.get(integration_type, "")

def get_integration_required_config(integration_type: IntegrationType) -> List[str]:
    """Get required configuration fields for integration."""
    configs = {
        IntegrationType.SLACK: ["webhook_url"],
        IntegrationType.GITHUB: ["access_token"],
        IntegrationType.NOTION: ["api_key", "database_id"],
        IntegrationType.DISCORD: ["webhook_url"],
        IntegrationType.TEAMS: ["webhook_url"],
        IntegrationType.JIRA: ["domain", "email", "api_token"],
        IntegrationType.TRELLO: ["api_key", "token"],
        IntegrationType.ASANA: ["access_token"],
        IntegrationType.CLICKUP: ["api_token"],
        IntegrationType.AIRTABLE: ["api_key", "base_id"],
        IntegrationType.GOOGLE_SHEETS: ["credentials_json", "spreadsheet_id"],
        IntegrationType.SALESFORCE: ["instance_url", "access_token"],
        IntegrationType.HUBSPOT: ["api_key"],
        IntegrationType.MAILCHIMP: ["api_key", "list_id"],
        IntegrationType.SENDGRID: ["api_key"],
        IntegrationType.TWILIO: ["account_sid", "auth_token", "from_number"],
        IntegrationType.STRIPE: ["api_key"],
        IntegrationType.SHOPIFY: ["shop_domain", "access_token"],
        IntegrationType.WORDPRESS: ["site_url", "username", "password"],
        IntegrationType.MEDIUM: ["integration_token"]
    }
    return configs.get(integration_type, [])

def get_integration_actions(integration_type: IntegrationType) -> List[str]:
    """Get available actions for integration."""
    actions = {
        IntegrationType.SLACK: ["send_message", "send_file", "create_channel"],
        IntegrationType.GITHUB: ["create_issue", "create_pr", "add_comment", "create_release"],
        IntegrationType.NOTION: ["create_page", "update_page", "add_database_row"],
        IntegrationType.DISCORD: ["send_message", "send_embed"],
        IntegrationType.TEAMS: ["send_message", "send_card"],
        IntegrationType.JIRA: ["create_issue", "update_issue", "add_comment"],
        IntegrationType.TRELLO: ["create_card", "move_card", "add_comment"],
        IntegrationType.ASANA: ["create_task", "update_task", "add_comment"],
        IntegrationType.CLICKUP: ["create_task", "update_task", "add_comment"],
        IntegrationType.AIRTABLE: ["create_record", "update_record", "find_records"],
        IntegrationType.GOOGLE_SHEETS: ["append_row", "update_cell", "read_range"],
        IntegrationType.SALESFORCE: ["create_lead", "update_lead", "create_opportunity"],
        IntegrationType.HUBSPOT: ["create_contact", "update_contact", "create_deal"],
        IntegrationType.MAILCHIMP: ["add_subscriber", "send_campaign", "update_subscriber"],
        IntegrationType.SENDGRID: ["send_email", "send_template_email"],
        IntegrationType.TWILIO: ["send_sms", "make_call"],
        IntegrationType.STRIPE: ["create_charge", "create_subscription", "create_invoice"],
        IntegrationType.SHOPIFY: ["create_product", "update_inventory", "create_order"],
        IntegrationType.WORDPRESS: ["create_post", "update_post", "upload_media"],
        IntegrationType.MEDIUM: ["create_post", "update_post"]
    }
    return actions.get(integration_type, [])

async def test_integration_health(integration: Integration) -> Dict[str, Any]:
    """Test integration health."""
    # Mock implementation
    return {
        "status": "healthy" if integration.is_active else "inactive",
        "response_time": 0.05,
        "last_error": None
    }

async def test_integration_connection(integration: Integration) -> Dict[str, Any]:
    """Test integration connection."""
    # Mock implementation
    return {
        "success": True,
        "message": f"{integration.type} connection test successful",
        "details": {
            "authenticated": True,
            "permissions": get_integration_actions(IntegrationType(integration.type))
        }
    }

def get_run_stats(workflow_id: str, db: Session) -> Dict[str, Any]:
    """Get workflow run statistics."""
    stats = {
        "total_runs": db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).count(),
        "success_rate": 0,
        "avg_duration": 0,
        "by_status": {}
    }
    
    # Get runs by status
    for status in RunStatus:
        count = db.query(WorkflowRun).filter(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.status == status.value
        ).count()
        stats["by_status"][status.value] = count
    
    # Calculate success rate
    completed = stats["by_status"].get(RunStatus.COMPLETED.value, 0)
    failed = stats["by_status"].get(RunStatus.FAILED.value, 0)
    if completed + failed > 0:
        stats["success_rate"] = completed / (completed + failed)
    
    return stats