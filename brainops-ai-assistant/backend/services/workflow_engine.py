"""Workflow automation engine for cross-platform orchestration."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
import httpx
from croniter import croniter

from loguru import logger
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.config import settings
from models.db import WorkflowDB, WorkflowRunDB, User
from models.assistant import Workflow, WorkflowRun
from services.command_executor import CommandExecutor
from services.file_ops import FileOperationsService
from services.task_manager import TaskManager
from services.ai_orchestrator import AIOrchestrator
from utils.audit import AuditLogger
from utils.safety import SafetyChecker


class TriggerType(str, Enum):
    """Workflow trigger types."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    FILE_CHANGE = "file_change"
    TASK_STATUS = "task_status"
    EMAIL = "email"
    API_CALL = "api_call"
    CHAT_COMMAND = "chat_command"
    VOICE_COMMAND = "voice_command"


class StepType(str, Enum):
    """Workflow step types."""
    COMMAND = "command"
    API_CALL = "api_call"
    FILE_OPERATION = "file_operation"
    TASK_OPERATION = "task_operation"
    EMAIL = "email"
    SLACK = "slack"
    MAKE_COM = "make_com"
    CLICKUP = "clickup"
    NOTION = "notion"
    CONDITION = "condition"
    DELAY = "delay"
    AI_QUERY = "ai_query"
    WEBHOOK = "webhook"


class WorkflowStatus(str, Enum):
    """Workflow run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowEngine:
    """Advanced workflow automation engine."""
    
    def __init__(self):
        self.command_executor = CommandExecutor()
        self.file_ops = FileOperationsService()
        self.task_manager = TaskManager()
        self.ai_orchestrator = AIOrchestrator()
        self.audit_logger = AuditLogger()
        self.safety_checker = SafetyChecker()
        
        # Active workflow runs
        self.active_runs: Dict[str, WorkflowRun] = {}
        
        # Webhook handlers
        self.webhook_handlers: Dict[str, Callable] = {}
        
        # Scheduled workflows
        self.scheduled_workflows: Dict[str, Dict[str, Any]] = {}
        
        # Step executors
        self.step_executors = {
            StepType.COMMAND: self._execute_command_step,
            StepType.API_CALL: self._execute_api_call_step,
            StepType.FILE_OPERATION: self._execute_file_operation_step,
            StepType.TASK_OPERATION: self._execute_task_operation_step,
            StepType.EMAIL: self._execute_email_step,
            StepType.SLACK: self._execute_slack_step,
            StepType.MAKE_COM: self._execute_make_com_step,
            StepType.CLICKUP: self._execute_clickup_step,
            StepType.NOTION: self._execute_notion_step,
            StepType.CONDITION: self._execute_condition_step,
            StepType.DELAY: self._execute_delay_step,
            StepType.AI_QUERY: self._execute_ai_query_step,
            StepType.WEBHOOK: self._execute_webhook_step
        }
        
        # Integration clients
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.integrations = {
            "make_com": self._init_make_com_client(),
            "clickup": self._init_clickup_client(),
            "notion": self._init_notion_client(),
            "slack": self._init_slack_client()
        }
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        trigger: Dict[str, Any],
        steps: List[Dict[str, Any]],
        created_by: int,
        enabled: bool = True
    ) -> Workflow:
        """Create a new workflow."""
        try:
            workflow_id = str(uuid.uuid4())
            
            # Validate workflow steps
            await self._validate_workflow_steps(steps)
            
            # Create database workflow
            db_workflow = WorkflowDB(
                id=workflow_id,
                name=name,
                description=description,
                trigger=trigger,
                steps=steps,
                enabled=enabled,
                created_by=created_by
            )
            
            async with get_db() as db:
                db.add(db_workflow)
                await db.commit()
                
                # Log workflow creation
                await self.audit_logger.log_action(
                    user_id=created_by,
                    action="workflow_created",
                    resource_type="workflow",
                    resource_id=workflow_id,
                    details={
                        "name": name,
                        "trigger_type": trigger.get("type"),
                        "steps_count": len(steps)
                    }
                )
                
                # Schedule if needed
                if trigger.get("type") == TriggerType.SCHEDULE and enabled:
                    await self._schedule_workflow(workflow_id, trigger)
                
                # Convert to domain model
                workflow = self._db_to_domain(db_workflow)
                
                logger.info(f"Created workflow {workflow_id}: {name}")
                return workflow
                
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            raise
    
    async def run_workflow(
        self,
        workflow_id: str,
        trigger_data: Dict[str, Any] = None,
        triggered_by: str = "manual"
    ) -> WorkflowRun:
        """Run a workflow."""
        try:
            # Get workflow
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            if not workflow.enabled:
                raise ValueError(f"Workflow {workflow_id} is disabled")
            
            # Create workflow run
            run_id = str(uuid.uuid4())
            
            workflow_run = WorkflowRun(
                id=run_id,
                workflow_id=workflow_id,
                triggered_by=triggered_by,
                trigger_data=trigger_data or {},
                status=WorkflowStatus.PENDING,
                started_at=datetime.utcnow(),
                step_results=[],
                metadata={}
            )
            
            # Store in database
            db_run = WorkflowRunDB(
                id=run_id,
                workflow_id=workflow_id,
                triggered_by=triggered_by,
                trigger_data=trigger_data or {},
                status=WorkflowStatus.PENDING.value,
                started_at=datetime.utcnow(),
                step_results=[],
                metadata={}
            )
            
            async with get_db() as db:
                db.add(db_run)
                await db.commit()
            
            # Add to active runs
            self.active_runs[run_id] = workflow_run
            
            # Execute workflow asynchronously
            asyncio.create_task(self._execute_workflow_run(workflow, workflow_run))
            
            logger.info(f"Started workflow run {run_id} for workflow {workflow_id}")
            return workflow_run
            
        except Exception as e:
            logger.error(f"Error running workflow {workflow_id}: {e}")
            raise
    
    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(WorkflowDB).where(WorkflowDB.id == workflow_id)
                )
                
                db_workflow = result.scalar_one_or_none()
                
                if not db_workflow:
                    return None
                
                return self._db_to_domain(db_workflow)
                
        except Exception as e:
            logger.error(f"Error getting workflow {workflow_id}: {e}")
            return None
    
    async def list_workflows(
        self,
        created_by: Optional[int] = None,
        enabled: Optional[bool] = None,
        trigger_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Workflow]:
        """List workflows with filtering."""
        try:
            async with get_db() as db:
                query = select(WorkflowDB)
                
                # Apply filters
                filters = []
                
                if created_by is not None:
                    filters.append(WorkflowDB.created_by == created_by)
                
                if enabled is not None:
                    filters.append(WorkflowDB.enabled == enabled)
                
                if trigger_type:
                    filters.append(WorkflowDB.trigger["type"].astext == trigger_type)
                
                if filters:
                    query = query.where(and_(*filters))
                
                # Apply pagination
                query = query.order_by(desc(WorkflowDB.created_at))
                query = query.limit(limit).offset(offset)
                
                result = await db.execute(query)
                db_workflows = result.scalars().all()
                
                # Convert to domain models
                workflows = [self._db_to_domain(db_workflow) for db_workflow in db_workflows]
                
                return workflows
                
        except Exception as e:
            logger.error(f"Error listing workflows: {e}")
            return []
    
    async def get_workflow_runs(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[WorkflowRun]:
        """Get workflow runs with filtering."""
        try:
            async with get_db() as db:
                query = select(WorkflowRunDB)
                
                # Apply filters
                filters = []
                
                if workflow_id:
                    filters.append(WorkflowRunDB.workflow_id == workflow_id)
                
                if status:
                    filters.append(WorkflowRunDB.status == status)
                
                if filters:
                    query = query.where(and_(*filters))
                
                # Apply pagination
                query = query.order_by(desc(WorkflowRunDB.started_at))
                query = query.limit(limit).offset(offset)
                
                result = await db.execute(query)
                db_runs = result.scalars().all()
                
                # Convert to domain models
                runs = [self._run_db_to_domain(db_run) for db_run in db_runs]
                
                return runs
                
        except Exception as e:
            logger.error(f"Error getting workflow runs: {e}")
            return []
    
    async def cancel_workflow_run(self, run_id: str) -> bool:
        """Cancel a running workflow."""
        try:
            if run_id in self.active_runs:
                workflow_run = self.active_runs[run_id]
                workflow_run.status = WorkflowStatus.CANCELLED
                workflow_run.completed_at = datetime.utcnow()
                
                # Update database
                async with get_db() as db:
                    result = await db.execute(
                        select(WorkflowRunDB).where(WorkflowRunDB.id == run_id)
                    )
                    
                    db_run = result.scalar_one_or_none()
                    if db_run:
                        db_run.status = WorkflowStatus.CANCELLED.value
                        db_run.completed_at = datetime.utcnow()
                        await db.commit()
                
                # Remove from active runs
                del self.active_runs[run_id]
                
                logger.info(f"Cancelled workflow run {run_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling workflow run {run_id}: {e}")
            return False
    
    async def register_webhook_handler(
        self,
        webhook_id: str,
        handler: Callable[[Dict[str, Any]], Any]
    ):
        """Register a webhook handler."""
        self.webhook_handlers[webhook_id] = handler
        logger.info(f"Registered webhook handler for {webhook_id}")
    
    async def trigger_webhook(
        self,
        webhook_id: str,
        data: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Trigger a webhook."""
        try:
            # Find workflows with this webhook trigger
            workflows = await self.list_workflows(trigger_type=TriggerType.WEBHOOK)
            
            triggered_workflows = []
            for workflow in workflows:
                if workflow.trigger.get("webhook_id") == webhook_id:
                    run = await self.run_workflow(
                        workflow.id,
                        trigger_data={"webhook_data": data, "headers": headers},
                        triggered_by=f"webhook:{webhook_id}"
                    )
                    triggered_workflows.append(run.id)
            
            # Call custom handler if registered
            if webhook_id in self.webhook_handlers:
                await self.webhook_handlers[webhook_id](data)
            
            return {
                "success": True,
                "webhook_id": webhook_id,
                "triggered_workflows": triggered_workflows
            }
            
        except Exception as e:
            logger.error(f"Error triggering webhook {webhook_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_workflow_template(
        self,
        name: str,
        description: str,
        template_data: Dict[str, Any],
        created_by: int
    ) -> str:
        """Create a workflow template."""
        try:
            template_id = str(uuid.uuid4())
            
            # Store template in system config
            from models.db import SystemConfigDB
            
            async with get_db() as db:
                config = SystemConfigDB(
                    id=template_id,
                    key=f"workflow_template_{name}",
                    value=template_data,
                    description=f"Workflow template: {name}",
                    updated_by=created_by
                )
                
                db.add(config)
                await db.commit()
                
                logger.info(f"Created workflow template {name}")
                return template_id
                
        except Exception as e:
            logger.error(f"Error creating workflow template: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the workflow engine."""
        # Cancel all active runs
        for run_id in list(self.active_runs.keys()):
            await self.cancel_workflow_run(run_id)
        
        # Close HTTP client
        await self.http_client.aclose()
        
        logger.info("Workflow engine shutdown complete")
    
    # Private methods
    async def _execute_workflow_run(
        self,
        workflow: Workflow,
        workflow_run: WorkflowRun
    ):
        """Execute a workflow run."""
        try:
            workflow_run.status = WorkflowStatus.RUNNING
            
            # Update database
            await self._update_workflow_run_status(workflow_run.id, WorkflowStatus.RUNNING)
            
            # Execute steps
            context = {
                "workflow_id": workflow.id,
                "run_id": workflow_run.id,
                "trigger_data": workflow_run.trigger_data,
                "variables": {}
            }
            
            for i, step in enumerate(workflow.steps):
                try:
                    step_result = await self._execute_step(step, context)
                    
                    # Store step result
                    workflow_run.step_results.append({
                        "step_index": i,
                        "step_type": step.get("type"),
                        "step_name": step.get("name", f"Step {i+1}"),
                        "result": step_result,
                        "timestamp": datetime.utcnow().isoformat(),
                        "success": step_result.get("success", False)
                    })
                    
                    # Update context with step output
                    if step_result.get("output"):
                        context["variables"].update(step_result["output"])
                    
                    # Check if step failed and should stop
                    if not step_result.get("success", False):
                        if not step.get("continue_on_error", False):
                            raise Exception(f"Step {i+1} failed: {step_result.get('error')}")
                    
                except Exception as e:
                    logger.error(f"Step {i+1} failed in workflow {workflow.id}: {e}")
                    workflow_run.step_results.append({
                        "step_index": i,
                        "step_type": step.get("type"),
                        "step_name": step.get("name", f"Step {i+1}"),
                        "result": {"success": False, "error": str(e)},
                        "timestamp": datetime.utcnow().isoformat(),
                        "success": False
                    })
                    
                    if not step.get("continue_on_error", False):
                        workflow_run.status = WorkflowStatus.FAILED
                        workflow_run.error = str(e)
                        break
            
            # Determine final status
            if workflow_run.status == WorkflowStatus.RUNNING:
                workflow_run.status = WorkflowStatus.COMPLETED
            
            # Update completion time
            workflow_run.completed_at = datetime.utcnow()
            workflow_run.duration_seconds = (
                workflow_run.completed_at - workflow_run.started_at
            ).total_seconds()
            
            # Update database
            await self._update_workflow_run_completion(workflow_run)
            
            # Remove from active runs
            self.active_runs.pop(workflow_run.id, None)
            
            # Log completion
            await self.audit_logger.log_action(
                user_id=workflow.created_by,
                action="workflow_completed",
                resource_type="workflow_run",
                resource_id=workflow_run.id,
                details={
                    "workflow_id": workflow.id,
                    "status": workflow_run.status.value,
                    "duration_seconds": workflow_run.duration_seconds,
                    "steps_executed": len(workflow_run.step_results)
                }
            )
            
            logger.info(f"Workflow run {workflow_run.id} completed with status {workflow_run.status}")
            
        except Exception as e:
            logger.error(f"Error executing workflow run {workflow_run.id}: {e}")
            
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.error = str(e)
            workflow_run.completed_at = datetime.utcnow()
            
            await self._update_workflow_run_completion(workflow_run)
            self.active_runs.pop(workflow_run.id, None)
    
    async def _execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single workflow step."""
        step_type = StepType(step.get("type"))
        
        if step_type not in self.step_executors:
            return {"success": False, "error": f"Unknown step type: {step_type}"}
        
        # Replace variables in step configuration
        step_config = self._replace_variables(step, context)
        
        # Execute step
        return await self.step_executors[step_type](step_config, context)
    
    async def _execute_command_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a command step."""
        try:
            command = step.get("command")
            args = step.get("args", [])
            
            result = await self.command_executor.execute(command, args)
            
            return {
                "success": result["success"],
                "output": {
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("exit_code", 0)
                },
                "error": result.get("error")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_api_call_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an API call step."""
        try:
            method = step.get("method", "GET").upper()
            url = step.get("url")
            headers = step.get("headers", {})
            data = step.get("data")
            
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None
            )
            
            response_data = None
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return {
                "success": response.status_code < 400,
                "output": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "data": response_data
                },
                "error": None if response.status_code < 400 else f"HTTP {response.status_code}"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_file_operation_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a file operation step."""
        try:
            operation = step.get("operation")
            path = step.get("path")
            
            if operation == "read":
                result = await self.file_ops.read_file(path)
            elif operation == "write":
                content = step.get("content", "")
                result = await self.file_ops.write_file(path, content)
            elif operation == "delete":
                result = await self.file_ops.delete_file(path)
            elif operation == "list":
                result = await self.file_ops.list_directory(path)
            else:
                return {"success": False, "error": f"Unknown file operation: {operation}"}
            
            return {
                "success": result["success"],
                "output": result,
                "error": result.get("error")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_task_operation_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task operation step."""
        try:
            operation = step.get("operation")
            
            if operation == "create":
                task = await self.task_manager.create_task(
                    title=step.get("title", "Workflow Task"),
                    description=step.get("description"),
                    priority=step.get("priority", "medium"),
                    assigned_to=step.get("assigned_to")
                )
                
                return {
                    "success": True,
                    "output": {"task_id": task.id},
                    "error": None
                }
            
            elif operation == "update":
                task_id = step.get("task_id")
                updates = step.get("updates", {})
                
                task = await self.task_manager.update_task(task_id, updates)
                
                return {
                    "success": task is not None,
                    "output": {"task_id": task.id} if task else None,
                    "error": None if task else "Task not found"
                }
            
            else:
                return {"success": False, "error": f"Unknown task operation: {operation}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_email_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an email step."""
        try:
            # Email implementation would go here
            # For now, return success
            return {
                "success": True,
                "output": {"message": "Email sent (mock)"},
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_slack_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a Slack step."""
        try:
            # Slack API implementation would go here
            message = step.get("message", "")
            channel = step.get("channel", "#general")
            
            # Mock implementation
            return {
                "success": True,
                "output": {"message": f"Sent to {channel}: {message}"},
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_make_com_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a Make.com step."""
        try:
            # Make.com integration would go here
            webhook_url = step.get("webhook_url")
            data = step.get("data", {})
            
            if webhook_url:
                response = await self.http_client.post(webhook_url, json=data)
                
                return {
                    "success": response.status_code < 400,
                    "output": {"status_code": response.status_code},
                    "error": None if response.status_code < 400 else f"HTTP {response.status_code}"
                }
            
            return {"success": False, "error": "No webhook URL provided"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_clickup_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a ClickUp step."""
        try:
            # ClickUp API implementation would go here
            return {
                "success": True,
                "output": {"message": "ClickUp operation completed (mock)"},
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_notion_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a Notion step."""
        try:
            # Notion API implementation would go here
            return {
                "success": True,
                "output": {"message": "Notion operation completed (mock)"},
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_condition_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a condition step."""
        try:
            condition = step.get("condition")
            
            # Simple condition evaluation
            # In production, use a proper expression evaluator
            if condition:
                # Replace variables
                condition = self._replace_variables_in_string(condition, context)
                
                # Evaluate condition (simplified)
                result = eval(condition)  # SECURITY: Use proper expression evaluator
                
                return {
                    "success": True,
                    "output": {"condition_result": result},
                    "error": None
                }
            
            return {"success": False, "error": "No condition provided"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_delay_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a delay step."""
        try:
            delay_seconds = step.get("delay_seconds", 1)
            
            await asyncio.sleep(delay_seconds)
            
            return {
                "success": True,
                "output": {"delayed": delay_seconds},
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_ai_query_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an AI query step."""
        try:
            query = step.get("query", "")
            model = step.get("model")
            
            result = await self.ai_orchestrator.query(
                prompt=query,
                model=model,
                query_type="workflow"
            )
            
            return {
                "success": True,
                "output": {
                    "response": result["response"],
                    "model": result["model"],
                    "cost": result["cost"]
                },
                "error": None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_webhook_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a webhook step."""
        try:
            url = step.get("url")
            data = step.get("data", {})
            method = step.get("method", "POST")
            
            response = await self.http_client.request(
                method=method,
                url=url,
                json=data
            )
            
            return {
                "success": response.status_code < 400,
                "output": {"status_code": response.status_code},
                "error": None if response.status_code < 400 else f"HTTP {response.status_code}"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Helper methods
    def _replace_variables(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Replace variables in step configuration."""
        step_str = json.dumps(step)
        step_str = self._replace_variables_in_string(step_str, context)
        return json.loads(step_str)
    
    def _replace_variables_in_string(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """Replace variables in a string."""
        import re
        
        # Replace {{variable}} patterns
        def replace_var(match):
            var_name = match.group(1)
            return str(context.get("variables", {}).get(var_name, match.group(0)))
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, text)
    
    async def _validate_workflow_steps(self, steps: List[Dict[str, Any]]):
        """Validate workflow steps."""
        for i, step in enumerate(steps):
            step_type = step.get("type")
            
            if not step_type:
                raise ValueError(f"Step {i+1} missing type")
            
            if step_type not in [t.value for t in StepType]:
                raise ValueError(f"Step {i+1} has invalid type: {step_type}")
            
            # Validate step-specific requirements
            if step_type == StepType.COMMAND:
                if not step.get("command"):
                    raise ValueError(f"Command step {i+1} missing command")
            
            elif step_type == StepType.API_CALL:
                if not step.get("url"):
                    raise ValueError(f"API call step {i+1} missing URL")
    
    async def _schedule_workflow(self, workflow_id: str, trigger: Dict[str, Any]):
        """Schedule a workflow."""
        try:
            cron_expression = trigger.get("cron")
            
            if cron_expression:
                self.scheduled_workflows[workflow_id] = {
                    "cron": cron_expression,
                    "next_run": croniter(cron_expression, datetime.utcnow()).get_next(datetime)
                }
                
                logger.info(f"Scheduled workflow {workflow_id} with cron: {cron_expression}")
            
        except Exception as e:
            logger.error(f"Error scheduling workflow {workflow_id}: {e}")
    
    async def _update_workflow_run_status(self, run_id: str, status: WorkflowStatus):
        """Update workflow run status in database."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(WorkflowRunDB).where(WorkflowRunDB.id == run_id)
                )
                
                db_run = result.scalar_one_or_none()
                if db_run:
                    db_run.status = status.value
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"Error updating workflow run status: {e}")
    
    async def _update_workflow_run_completion(self, workflow_run: WorkflowRun):
        """Update workflow run completion in database."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(WorkflowRunDB).where(WorkflowRunDB.id == workflow_run.id)
                )
                
                db_run = result.scalar_one_or_none()
                if db_run:
                    db_run.status = workflow_run.status.value
                    db_run.completed_at = workflow_run.completed_at
                    db_run.duration_seconds = workflow_run.duration_seconds
                    db_run.step_results = workflow_run.step_results
                    db_run.error = workflow_run.error
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"Error updating workflow run completion: {e}")
    
    def _db_to_domain(self, db_workflow: WorkflowDB) -> Workflow:
        """Convert database model to domain model."""
        return Workflow(
            id=db_workflow.id,
            name=db_workflow.name,
            description=db_workflow.description,
            trigger=db_workflow.trigger,
            steps=db_workflow.steps,
            enabled=db_workflow.enabled,
            created_by=db_workflow.created_by,
            created_at=db_workflow.created_at,
            updated_at=db_workflow.updated_at,
            last_run=db_workflow.last_run,
            run_count=db_workflow.run_count,
            error_count=db_workflow.error_count,
            metadata=db_workflow.metadata
        )
    
    def _run_db_to_domain(self, db_run: WorkflowRunDB) -> WorkflowRun:
        """Convert database run model to domain model."""
        return WorkflowRun(
            id=db_run.id,
            workflow_id=db_run.workflow_id,
            triggered_by=db_run.triggered_by,
            trigger_data=db_run.trigger_data,
            status=WorkflowStatus(db_run.status),
            started_at=db_run.started_at,
            completed_at=db_run.completed_at,
            duration_seconds=db_run.duration_seconds,
            step_results=db_run.step_results,
            error=db_run.error,
            metadata=db_run.metadata
        )
    
    # Integration clients
    def _init_make_com_client(self):
        """Initialize Make.com client."""
        return None  # Implement based on Make.com API
    
    def _init_clickup_client(self):
        """Initialize ClickUp client."""
        return None  # Implement based on ClickUp API
    
    def _init_notion_client(self):
        """Initialize Notion client."""
        return None  # Implement based on Notion API
    
    def _init_slack_client(self):
        """Initialize Slack client."""
        return None  # Implement based on Slack API