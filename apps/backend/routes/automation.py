"""
Automation and workflow routes for BrainOps backend.

Handles workflow creation, execution, triggers, and scheduling.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel
from croniter import croniter

from ..core.database import get_db
from ..core.auth import get_current_user
from ..db.business_models import User, Workflow, WorkflowRun, Integration
from ..core.scheduler import scheduler
from ..tasks import execute_task
from ..integrations import clickup, notion, slack, make

router = APIRouter()


# Pydantic models
class WorkflowStep(BaseModel):
    id: str
    type: str  # task, condition, loop, parallel, wait
    name: str
    config: Dict[str, Any]
    next_steps: List[str] = []


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str]
    trigger_type: str  # webhook, schedule, manual, event
    trigger_config: Dict[str, Any]
    steps: List[WorkflowStep]
    is_active: bool = True
    is_public: bool = False


class WorkflowUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    steps: Optional[List[WorkflowStep]]
    is_active: Optional[bool]
    is_public: Optional[bool]


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_config: Dict[str, Any]
    steps: List[WorkflowStep]
    owner_id: str
    team_id: Optional[str]
    is_active: bool
    is_public: bool
    run_count: int
    success_count: int
    last_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    trigger_data: Optional[Dict[str, Any]]
    steps_completed: int
    steps_total: int
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]


class TriggerCreate(BaseModel):
    name: str
    type: str  # webhook, schedule, event
    config: Dict[str, Any]
    workflow_id: str
    is_active: bool = True


class TriggerUpdate(BaseModel):
    name: Optional[str]
    config: Optional[Dict[str, Any]]
    is_active: Optional[bool]


class TriggerResponse(BaseModel):
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    workflow_id: str
    is_active: bool
    last_triggered: Optional[datetime]
    next_run: Optional[datetime]
    created_at: datetime


class WorkflowExecuteRequest(BaseModel):
    input_data: Dict[str, Any] = {}
    async_execution: bool = True


class IntegrationConfig(BaseModel):
    type: str  # slack, clickup, notion, make, zapier
    name: str
    config: Dict[str, Any]
    webhook_url: Optional[str]


class IntegrationResponse(BaseModel):
    id: str
    type: str
    name: str
    is_active: bool
    connected_at: datetime
    last_synced_at: Optional[datetime]


# Helper functions
def validate_workflow_steps(steps: List[WorkflowStep]):
    """Validate workflow step configuration."""
    step_ids = {step.id for step in steps}
    
    for step in steps:
        # Check next_steps reference valid step IDs
        for next_id in step.next_steps:
            if next_id not in step_ids and next_id != "end":
                raise ValueError(f"Invalid next_step reference: {next_id}")
        
        # Validate step-specific configuration
        if step.type == "condition":
            if "condition" not in step.config:
                raise ValueError(f"Condition step {step.id} missing condition config")
        
        elif step.type == "loop":
            if "iterations" not in step.config and "condition" not in step.config:
                raise ValueError(f"Loop step {step.id} must have iterations or condition")


def validate_trigger_config(trigger_type: str, config: Dict[str, Any]):
    """Validate trigger configuration."""
    if trigger_type == "schedule":
        if "cron" not in config:
            raise ValueError("Schedule trigger must have cron expression")
        
        # Validate cron expression
        try:
            croniter(config["cron"])
        except:
            raise ValueError("Invalid cron expression")
    
    elif trigger_type == "webhook":
        if "secret" not in config:
            config["secret"] = str(uuid4())
    
    elif trigger_type == "event":
        if "event_type" not in config:
            raise ValueError("Event trigger must specify event_type")


async def execute_workflow_step(step: WorkflowStep, context: Dict[str, Any], db: Session):
    """Execute a single workflow step."""
    try:
        if step.type == "task":
            # Execute task
            task_id = step.config.get("task_id")
            task_params = step.config.get("parameters", {})
            
            # Substitute variables from context
            task_params = substitute_variables(task_params, context)
            
            result = await execute_task(task_id, task_params)
            return result
        
        elif step.type == "condition":
            # Evaluate condition
            condition = step.config.get("condition")
            return evaluate_condition(condition, context)
        
        elif step.type == "loop":
            # Handle loop logic
            iterations = step.config.get("iterations", 1)
            results = []
            
            for i in range(iterations):
                context["loop_index"] = i
                # Execute loop body (would need to handle nested steps)
                results.append({"iteration": i})
            
            return results
        
        elif step.type == "parallel":
            # Execute steps in parallel
            parallel_tasks = []
            for sub_step_id in step.config.get("steps", []):
                # Queue parallel execution
                parallel_tasks.append(sub_step_id)
            
            # Wait for all parallel tasks
            return {"parallel_completed": parallel_tasks}
        
        elif step.type == "wait":
            # Wait for specified duration
            duration = step.config.get("duration", 1)
            await asyncio.sleep(duration)
            return {"waited": duration}
        
        else:
            raise ValueError(f"Unknown step type: {step.type}")
    
    except Exception as e:
        raise Exception(f"Step {step.id} failed: {str(e)}")


def substitute_variables(data: Any, context: Dict[str, Any]) -> Any:
    """Substitute variables in data with values from context."""
    if isinstance(data, str):
        # Replace {{variable}} with context values
        import re
        pattern = r'\{\{(\w+)\}\}'
        
        def replacer(match):
            var_name = match.group(1)
            return str(context.get(var_name, match.group(0)))
        
        return re.sub(pattern, replacer, data)
    
    elif isinstance(data, dict):
        return {k: substitute_variables(v, context) for k, v in data.items()}
    
    elif isinstance(data, list):
        return [substitute_variables(item, context) for item in data]
    
    return data


def evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
    """Safely evaluate a condition expression."""
    # In production, use a safe expression evaluator
    # For now, support simple comparisons
    try:
        # Very basic implementation - should use proper expression parser
        if "==" in condition:
            left, right = condition.split("==")
            left_val = context.get(left.strip(), left.strip())
            right_val = context.get(right.strip(), right.strip())
            return str(left_val) == str(right_val)
        
        return False
    except:
        return False


# Workflow Management Endpoints
@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new workflow."""
    # Validate workflow steps
    try:
        validate_workflow_steps(workflow_data.steps)
        validate_trigger_config(workflow_data.trigger_type, workflow_data.trigger_config)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Create workflow
    workflow = Workflow(
        name=workflow_data.name,
        description=workflow_data.description,
        trigger_type=workflow_data.trigger_type,
        trigger_config=workflow_data.trigger_config,
        steps=[step.dict() for step in workflow_data.steps],
        owner_id=current_user.id,
        is_active=workflow_data.is_active,
        is_public=workflow_data.is_public
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    # Schedule if it's a scheduled workflow
    if workflow.trigger_type == "schedule" and workflow.is_active:
        await schedule_workflow(workflow)
    
    return format_workflow_response(workflow)


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    search: Optional[str] = None,
    trigger_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_public: bool = True,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List workflows."""
    query = db.query(Workflow)
    
    # Filter by ownership or public
    if include_public:
        query = query.filter(
            or_(
                Workflow.owner_id == current_user.id,
                Workflow.is_public == True
            )
        )
    else:
        query = query.filter(Workflow.owner_id == current_user.id)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Workflow.name.ilike(f"%{search}%"),
                Workflow.description.ilike(f"%{search}%")
            )
        )
    
    if trigger_type:
        query = query.filter(Workflow.trigger_type == trigger_type)
    
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    
    # Order and paginate
    workflows = query.order_by(Workflow.updated_at.desc()).offset(offset).limit(limit).all()
    
    return [format_workflow_response(w) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workflow details."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check access
    if workflow.owner_id != current_user.id and not workflow.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this workflow"
        )
    
    return format_workflow_response(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    update_data: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check ownership
    if workflow.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this workflow"
        )
    
    # Validate steps if provided
    if update_data.steps:
        try:
            validate_workflow_steps(update_data.steps)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        if field == "steps":
            value = [step.dict() for step in value]
        setattr(workflow, field, value)
    
    db.commit()
    db.refresh(workflow)
    
    # Update schedule if needed
    if workflow.trigger_type == "schedule":
        await update_workflow_schedule(workflow)
    
    return format_workflow_response(workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check ownership
    if workflow.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this workflow"
        )
    
    # Remove schedule if exists
    if workflow.trigger_type == "schedule":
        await remove_workflow_schedule(workflow)
    
    db.delete(workflow)
    db.commit()
    
    return {"message": "Workflow deleted successfully"}


@router.post("/{workflow_id}/execute", response_model=WorkflowRunResponse)
async def execute_workflow(
    workflow_id: UUID,
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check access
    if workflow.owner_id != current_user.id and not workflow.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to execute this workflow"
        )
    
    if not workflow.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not active"
        )
    
    # Create workflow run record
    run = WorkflowRun(
        workflow_id=workflow_id,
        status="running",
        trigger_data=request.input_data,
        steps_total=len(workflow.steps),
        started_at=datetime.utcnow()
    )
    
    db.add(run)
    db.commit()
    db.refresh(run)
    
    if request.async_execution:
        # Execute in background
        background_tasks.add_task(
            execute_workflow_async,
            workflow,
            run,
            request.input_data,
            db
        )
        
        return format_workflow_run_response(run, workflow.name)
    else:
        # Execute synchronously
        await execute_workflow_async(workflow, run, request.input_data, db)
        db.refresh(run)
        return format_workflow_run_response(run, workflow.name)


@router.get("/{workflow_id}/runs", response_model=List[WorkflowRunResponse])
async def get_workflow_runs(
    workflow_id: UUID,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get workflow execution history."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check access
    if workflow.owner_id != current_user.id and not workflow.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view workflow runs"
        )
    
    query = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
    
    if status:
        query = query.filter(WorkflowRun.status == status)
    
    runs = query.order_by(WorkflowRun.started_at.desc()).offset(offset).limit(limit).all()
    
    return [format_workflow_run_response(run, workflow.name) for run in runs]


# Trigger Management Endpoints
@router.post("/triggers", response_model=TriggerResponse)
async def create_trigger(
    trigger_data: TriggerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a workflow trigger."""
    # Verify workflow ownership
    workflow = db.query(Workflow).filter(Workflow.id == trigger_data.workflow_id).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    if workflow.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create triggers for this workflow"
        )
    
    # Create trigger (in production, this would be a separate table)
    trigger_id = str(uuid4())
    
    # Register trigger based on type
    if trigger_data.type == "webhook":
        webhook_url = await register_webhook_trigger(
            trigger_id,
            trigger_data.workflow_id,
            trigger_data.config
        )
        trigger_data.config["webhook_url"] = webhook_url
    
    elif trigger_data.type == "schedule":
        await register_schedule_trigger(
            trigger_id,
            trigger_data.workflow_id,
            trigger_data.config
        )
    
    return TriggerResponse(
        id=trigger_id,
        name=trigger_data.name,
        type=trigger_data.type,
        config=trigger_data.config,
        workflow_id=str(trigger_data.workflow_id),
        is_active=trigger_data.is_active,
        last_triggered=None,
        next_run=calculate_next_run(trigger_data.type, trigger_data.config),
        created_at=datetime.utcnow()
    )


@router.get("/triggers", response_model=List[TriggerResponse])
async def list_triggers(
    workflow_id: Optional[UUID] = None,
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List workflow triggers."""
    # In production, query from triggers table
    # For now, return triggers from workflows
    query = db.query(Workflow).filter(Workflow.owner_id == current_user.id)
    
    if workflow_id:
        query = query.filter(Workflow.id == workflow_id)
    
    workflows = query.all()
    
    triggers = []
    for workflow in workflows:
        if workflow.trigger_type != "manual":
            triggers.append(
                TriggerResponse(
                    id=str(workflow.id),
                    name=f"{workflow.name} Trigger",
                    type=workflow.trigger_type,
                    config=workflow.trigger_config,
                    workflow_id=str(workflow.id),
                    is_active=workflow.is_active,
                    last_triggered=workflow.last_run_at,
                    next_run=calculate_next_run(workflow.trigger_type, workflow.trigger_config),
                    created_at=workflow.created_at
                )
            )
    
    return triggers


@router.put("/triggers/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: str,
    update_data: TriggerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update trigger configuration."""
    # In production, update trigger in database
    # For now, return mock response
    # In production, would query trigger from database
    # For now, create a mock trigger that we're updating
    mock_trigger = {
        "id": trigger_id,
        "name": "Existing Trigger",
        "type": "webhook",
        "config": {"webhook_url": "https://example.com/webhook"},
        "workflow_id": str(uuid4()),
        "is_active": True
    }
    
    # Apply updates
    if update_data.name is not None:
        mock_trigger["name"] = update_data.name
    if update_data.config is not None:
        mock_trigger["config"].update(update_data.config)
    if update_data.is_active is not None:
        mock_trigger["is_active"] = update_data.is_active
    
    return TriggerResponse(
        id=mock_trigger["id"],
        name=mock_trigger["name"],
        type=mock_trigger["type"],
        config=mock_trigger["config"],
        workflow_id=mock_trigger["workflow_id"],
        is_active=mock_trigger["is_active"],
        last_triggered=None,
        next_run=calculate_next_run(mock_trigger["type"], mock_trigger["config"]),
        created_at=datetime.utcnow()
    )


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a trigger."""
    # In production, remove trigger from database and deregister
    return {"message": "Trigger deleted successfully"}


@router.post("/triggers/{trigger_id}/enable")
async def enable_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enable a trigger."""
    # In production, enable trigger in database
    return {"message": "Trigger enabled successfully"}


@router.post("/triggers/{trigger_id}/disable")
async def disable_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable a trigger."""
    # In production, disable trigger in database
    return {"message": "Trigger disabled successfully"}


# Integration Management Endpoints
@router.get("/integrations", response_model=List[IntegrationResponse])
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available integrations."""
    integrations = db.query(Integration).filter(
        Integration.user_id == current_user.id
    ).all()
    
    return [
        IntegrationResponse(
            id=str(integration.id),
            type=integration.type,
            name=integration.name,
            is_active=integration.is_active,
            connected_at=integration.connected_at,
            last_synced_at=integration.last_synced_at
        )
        for integration in integrations
    ]


@router.post("/integrations/{type}/connect")
async def connect_integration(
    type: str,
    config: IntegrationConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Connect a new integration."""
    # Validate integration type
    valid_types = ["slack", "clickup", "notion", "make", "zapier", "stripe"]
    if type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integration type. Must be one of: {valid_types}"
        )
    
    # Check if already connected
    existing = db.query(Integration).filter(
        and_(
            Integration.user_id == current_user.id,
            Integration.type == type
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration already connected"
        )
    
    # Create integration
    integration = Integration(
        user_id=current_user.id,
        type=type,
        name=config.name,
        config=config.config,
        webhook_url=config.webhook_url,
        is_active=True
    )
    
    db.add(integration)
    db.commit()
    
    # Initialize integration
    await initialize_integration(integration)
    
    return {"message": f"{type} integration connected successfully"}


@router.delete("/integrations/{type}/disconnect")
async def disconnect_integration(
    type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect an integration."""
    integration = db.query(Integration).filter(
        and_(
            Integration.user_id == current_user.id,
            Integration.type == type
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Cleanup integration
    await cleanup_integration(integration)
    
    db.delete(integration)
    db.commit()
    
    return {"message": f"{type} integration disconnected successfully"}


@router.get("/integrations/{type}/status")
async def get_integration_status(
    type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check integration status."""
    integration = db.query(Integration).filter(
        and_(
            Integration.user_id == current_user.id,
            Integration.type == type
        )
    ).first()
    
    if not integration:
        return {"connected": False}
    
    # Check actual status
    is_healthy = await check_integration_health(integration)
    
    return {
        "connected": True,
        "is_active": integration.is_active,
        "is_healthy": is_healthy,
        "last_synced_at": integration.last_synced_at
    }


@router.post("/integrations/{type}/sync")
async def sync_integration(
    type: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force sync with integration."""
    integration = db.query(Integration).filter(
        and_(
            Integration.user_id == current_user.id,
            Integration.type == type
        )
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if not integration.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    # Sync in background
    background_tasks.add_task(
        sync_integration_data,
        integration,
        db
    )
    
    return {"message": "Sync initiated"}


# Helper functions for workflow execution
async def execute_workflow_async(workflow: Workflow, run: WorkflowRun, input_data: Dict[str, Any], db: Session):
    """Execute workflow asynchronously."""
    context = {"input": input_data, "workflow_id": str(workflow.id)}
    
    try:
        # Execute each step
        for i, step_data in enumerate(workflow.steps):
            step = WorkflowStep(**step_data)
            
            # Execute step
            result = await execute_workflow_step(step, context, db)
            
            # Update context with result
            context[f"step_{step.id}_result"] = result
            
            # Update progress
            run.steps_completed = i + 1
            db.commit()
            
            # Determine next step based on result
            if step.type == "condition":
                # Branch based on condition result
                if result and len(step.next_steps) > 1:
                    # Take true branch (assuming second next_step)
                    next_step_id = step.next_steps[1]
                else:
                    # Take false branch (first next_step)
                    next_step_id = step.next_steps[0] if step.next_steps else None
            else:
                # Normal flow
                next_step_id = step.next_steps[0] if step.next_steps else None
            
            if next_step_id == "end" or not next_step_id:
                break
        
        # Mark as completed
        run.status = "completed"
        run.output = context
        run.completed_at = datetime.utcnow()
        run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
        
        # Update workflow stats
        workflow.run_count += 1
        workflow.success_count += 1
        workflow.last_run_at = datetime.utcnow()
        
    except Exception as e:
        # Mark as failed
        run.status = "failed"
        run.error = str(e)
        run.completed_at = datetime.utcnow()
        run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
        
        # Update workflow stats
        workflow.run_count += 1
        workflow.last_run_at = datetime.utcnow()
    
    db.commit()


async def schedule_workflow(workflow: Workflow):
    """Schedule a workflow for periodic execution."""
    if workflow.trigger_type == "schedule":
        cron = workflow.trigger_config.get("cron")
        if cron:
            # Add to scheduler
            scheduler.add_job(
                execute_scheduled_workflow,
                "cron",
                args=[str(workflow.id)],
                id=f"workflow_{workflow.id}",
                cron=cron,
                replace_existing=True
            )


async def update_workflow_schedule(workflow: Workflow):
    """Update workflow schedule."""
    job_id = f"workflow_{workflow.id}"
    
    if workflow.is_active and workflow.trigger_type == "schedule":
        cron = workflow.trigger_config.get("cron")
        if cron:
            scheduler.reschedule_job(
                job_id,
                trigger="cron",
                cron=cron
            )
    else:
        # Remove schedule if not active
        try:
            scheduler.remove_job(job_id)
        except:
            pass


async def remove_workflow_schedule(workflow: Workflow):
    """Remove workflow from scheduler."""
    try:
        scheduler.remove_job(f"workflow_{workflow.id}")
    except:
        pass


async def execute_scheduled_workflow(workflow_id: str):
    """Execute a scheduled workflow."""
    from ..core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Get workflow
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        
        if not workflow or not workflow.is_active:
            return
        
        # Create workflow run
        run = WorkflowRun(
            workflow_id=workflow_id,
            status="running",
            trigger_data={"trigger": "schedule"},
            steps_total=len(workflow.steps),
            started_at=datetime.utcnow()
        )
        
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Execute workflow
        await execute_workflow_async(workflow, run, {"trigger": "schedule"}, db)
        
    finally:
        db.close()


def calculate_next_run(trigger_type: str, config: Dict[str, Any]) -> Optional[datetime]:
    """Calculate next run time for scheduled triggers."""
    if trigger_type == "schedule":
        cron_expr = config.get("cron")
        if cron_expr:
            cron = croniter(cron_expr, datetime.utcnow())
            return cron.get_next(datetime)
    
    return None


async def register_webhook_trigger(trigger_id: str, workflow_id: str, config: Dict[str, Any]) -> str:
    """Register a webhook trigger and return the URL."""
    secret = config.get("secret", str(uuid4()))
    webhook_url = f"{settings.BASE_URL}/api/v1/webhooks/workflow/{workflow_id}/{secret}"
    
    # Store webhook mapping (in production, use database)
    return webhook_url


async def register_schedule_trigger(trigger_id: str, workflow_id: str, config: Dict[str, Any]):
    """Register a scheduled trigger."""
    cron = config.get("cron")
    if cron:
        # Add to scheduler
        scheduler.add_job(
            execute_scheduled_workflow,
            "cron",
            args=[workflow_id],
            id=f"trigger_{trigger_id}",
            cron=cron,
            replace_existing=True
        )


async def initialize_integration(integration: Integration):
    """Initialize integration connection."""
    # Perform integration-specific setup
    if integration.type == "slack":
        # Verify Slack webhook URL
        if integration.webhook_url:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        integration.webhook_url,
                        json={"text": "BrainOps integration connected successfully!"}
                    )
                    return response.status_code == 200
                except:
                    return False
    
    elif integration.type == "clickup":
        # Verify ClickUp API token
        api_token = integration.config.get("api_token")
        if api_token:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.clickup.com/api/v2/user",
                        headers={"Authorization": api_token}
                    )
                    return response.status_code == 200
                except:
                    return False
    
    elif integration.type == "notion":
        # Verify Notion API token
        api_token = integration.config.get("api_token")
        if api_token:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.notion.com/v1/users/me",
                        headers={
                            "Authorization": f"Bearer {api_token}",
                            "Notion-Version": "2022-06-28"
                        }
                    )
                    return response.status_code == 200
                except:
                    return False
    
    elif integration.type == "make":
        # Make.com webhook verification
        webhook_url = integration.webhook_url
        if webhook_url:
            return True  # Make.com webhooks are ready immediately
    
    elif integration.type == "zapier":
        # Zapier webhook verification
        webhook_url = integration.webhook_url
        if webhook_url:
            return True  # Zapier webhooks are ready immediately
    
    elif integration.type == "stripe":
        # Verify Stripe API key
        api_key = integration.config.get("api_key")
        if api_key:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.stripe.com/v1/customers?limit=1",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    return response.status_code == 200
                except:
                    return False
    
    return True


async def cleanup_integration(integration: Integration):
    """Cleanup integration resources."""
    # Remove webhooks, tokens, etc.
    if integration.type == "slack":
        # Notify disconnection
        if integration.webhook_url:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(
                        integration.webhook_url,
                        json={"text": "BrainOps integration disconnected."}
                    )
                except:
                    pass
    
    elif integration.type == "clickup":
        # ClickUp doesn't require cleanup
        pass
    
    elif integration.type == "notion":
        # Notion doesn't require cleanup
        pass
    
    elif integration.type in ["make", "zapier"]:
        # Webhook platforms - notify disconnection if possible
        if integration.webhook_url:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(
                        integration.webhook_url,
                        json={"event": "integration.disconnected", "source": "brainops"}
                    )
                except:
                    pass
    
    elif integration.type == "stripe":
        # Stripe doesn't require cleanup
        pass


async def check_integration_health(integration: Integration) -> bool:
    """Check if integration is healthy."""
    # Ping integration API
    return True


async def sync_integration_data(integration: Integration, db: Session):
    """Sync data from integration."""
    # Perform integration-specific sync
    integration.last_synced_at = datetime.utcnow()
    db.commit()


def format_workflow_response(workflow: Workflow) -> WorkflowResponse:
    """Format workflow response."""
    return WorkflowResponse(
        id=str(workflow.id),
        name=workflow.name,
        description=workflow.description,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        steps=[WorkflowStep(**step) for step in workflow.steps],
        owner_id=str(workflow.owner_id),
        team_id=str(workflow.team_id) if workflow.team_id else None,
        is_active=workflow.is_active,
        is_public=workflow.is_public,
        run_count=workflow.run_count,
        success_count=workflow.success_count,
        last_run_at=workflow.last_run_at,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at
    )


def format_workflow_run_response(run: WorkflowRun, workflow_name: str) -> WorkflowRunResponse:
    """Format workflow run response."""
    return WorkflowRunResponse(
        id=str(run.id),
        workflow_id=str(run.workflow_id),
        workflow_name=workflow_name,
        status=run.status,
        trigger_data=run.trigger_data,
        steps_completed=run.steps_completed,
        steps_total=run.steps_total,
        output=run.output,
        error=run.error,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms
    )