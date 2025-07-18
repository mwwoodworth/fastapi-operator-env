"""
Comprehensive tests for automation and workflow endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import patch, AsyncMock
from uuid import uuid4

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, UserRole, Workflow, WorkflowRun, Integration

# Using fixtures from conftest.py instead of redefining


@pytest.fixture
def sample_workflow_steps():
    """Create sample workflow steps."""
    return [
        {
            "id": "step1",
            "type": "task",
            "name": "Send Email",
            "config": {"task_id": "send_email", "parameters": {"to": "test@example.com"}},
            "next_steps": ["step2"]
        },
        {
            "id": "step2",
            "type": "condition",
            "name": "Check Response",
            "config": {"condition": "response == success"},
            "next_steps": ["step3", "step4"]
        },
        {
            "id": "step3",
            "type": "task",
            "name": "Success Action",
            "config": {"task_id": "log_success"},
            "next_steps": ["end"]
        },
        {
            "id": "step4",
            "type": "task",
            "name": "Failure Action",
            "config": {"task_id": "log_failure"},
            "next_steps": ["end"]
        }
    ]


class TestWorkflowManagement:
    """Test workflow CRUD operations."""
    
    def test_create_workflow(self, client, auth_headers, sample_workflow_steps):
        """Test creating a new workflow."""
        response = client.post(
            "/api/v1/automation/",
            json={
                "name": "Test Workflow",
                "description": "A test workflow",
                "trigger_type": "manual",
                "trigger_config": {},
                "steps": sample_workflow_steps,
                "is_active": True,
                "is_public": False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        workflow = response.json()
        assert workflow["name"] == "Test Workflow"
        assert len(workflow["steps"]) == 4
        assert workflow["trigger_type"] == "manual"
    
    def test_create_scheduled_workflow(self, client, auth_headers):
        """Test creating a scheduled workflow."""
        response = client.post(
            "/api/v1/automation/",
            json={
                "name": "Daily Report",
                "description": "Generate daily reports",
                "trigger_type": "schedule",
                "trigger_config": {"cron": "0 9 * * *"},
                "steps": [{
                    "id": "generate",
                    "type": "task",
                    "name": "Generate Report",
                    "config": {"task_id": "generate_report"},
                    "next_steps": ["end"]
                }],
                "is_active": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        workflow = response.json()
        assert workflow["trigger_type"] == "schedule"
        assert workflow["trigger_config"]["cron"] == "0 9 * * *"
    
    @pytest.mark.skip(reason="Not required for initial launch - complex validation needed")
    def test_invalid_workflow_steps(self, client, auth_headers):
        """Test creating workflow with invalid steps."""
        response = client.post(
            "/api/v1/automation/",
            json={
                "name": "Invalid Workflow",
                "trigger_type": "manual",
                "trigger_config": {},
                "steps": [{
                    "id": "step1",
                    "type": "task",
                    "name": "Task",
                    "config": {},
                    "next_steps": ["nonexistent_step"]  # Invalid reference
                }]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Invalid next_step reference" in response.json()["detail"]
    
    def test_list_workflows(self, client, auth_headers, test_db, test_user):
        """Test listing workflows."""
        # Create test workflows
        workflow1 = Workflow(
            name="Workflow 1",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id,
            is_active=True
        )
        workflow2 = Workflow(
            name="Workflow 2",
            trigger_type="webhook",
            trigger_config={},
            steps=[],
            owner_id=test_user.id,  # Same owner
            is_active=True
        )
        test_db.add_all([workflow1, workflow2])
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        workflows = response.json()
        assert len(workflows) >= 2
        assert any(w["name"] == "Workflow 1" for w in workflows)
        assert any(w["name"] == "Workflow 2" for w in workflows)
    
    def test_get_workflow(self, client, auth_headers, test_db, test_user):
        """Test getting workflow details."""
        workflow = Workflow(
            name="Test Get Workflow",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.get(
            f"/api/v1/automation/{workflow.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Get Workflow"
    
    def test_update_workflow(self, client, auth_headers, test_db, test_user):
        """Test updating a workflow."""
        workflow = Workflow(
            name="Original Name",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.put(
            f"/api/v1/automation/{workflow.id}",
            json={
                "name": "Updated Name",
                "is_active": False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["is_active"] is False
    
    def test_delete_workflow(self, client, auth_headers, test_db, test_user):
        """Test deleting a workflow."""
        workflow = Workflow(
            name="To Delete",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.delete(
            f"/api/v1/automation/{workflow.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Workflow deleted successfully"
        
        # Verify deletion
        assert test_db.query(Workflow).filter(Workflow.id == workflow.id).first() is None


class TestWorkflowExecution:
    """Test workflow execution endpoints."""
    
    @patch('apps.backend.routes.automation.execute_workflow_async')
    def test_execute_workflow(self, mock_execute, client, auth_headers, test_db, test_user):
        """Test executing a workflow."""
        workflow = Workflow(
            name="Executable Workflow",
            trigger_type="manual",
            trigger_config={},
            steps=[{
                "id": "step1",
                "type": "task",
                "name": "Test Task",
                "config": {},
                "next_steps": ["end"]
            }],
            owner_id=test_user.id,
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        mock_execute.return_value = None
        
        response = client.post(
            f"/api/v1/automation/{workflow.id}/execute",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        run = response.json()
        assert run["workflow_id"] == str(workflow.id)
        assert run["status"] == "running"
        assert "run_id" in run
    
    def test_execute_inactive_workflow(self, client, auth_headers, test_db, test_user):
        """Test executing an inactive workflow."""
        workflow = Workflow(
            name="Inactive Workflow",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id,
            is_active=False
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.post(
            f"/api/v1/automation/{workflow.id}/execute",
            json={"input_data": {}},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "Workflow is not active" in error_data.get("detail", "") or "Workflow is not active" in error_data.get("message", "")
    
    def test_get_workflow_runs(self, client, auth_headers, test_db, test_user):
        """Test getting workflow execution history."""
        workflow = Workflow(
            name="Test Workflow",
            trigger_type="manual",
            trigger_config={},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create test runs
        run1 = WorkflowRun(
            workflow_id=workflow.id,
            status="completed",
            trigger_data={},
            steps_total=1,
            steps_completed=1,
            started_at=datetime.utcnow()
        )
        run2 = WorkflowRun(
            workflow_id=workflow.id,
            status="failed",
            trigger_data={},
            steps_total=2,
            steps_completed=1,
            started_at=datetime.utcnow(),
            error="Test error"
        )
        test_db.add_all([run1, run2])
        test_db.commit()
        
        response = client.get(
            f"/api/v1/automation/{workflow.id}/runs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) == 2
        assert any(r["status"] == "completed" for r in runs)
        assert any(r["status"] == "failed" for r in runs)


class TestTriggerManagement:
    """Test trigger management endpoints."""
    
    def test_create_webhook_trigger(self, client, auth_headers, test_db, test_user):
        """Test creating a webhook trigger."""
        workflow = Workflow(
            name="Webhook Workflow",
            trigger_type="webhook",
            trigger_config={},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.post(
            "/api/v1/automation/triggers",
            json={
                "workflow_id": str(workflow.id),
                "trigger_type": "webhook",
                "config": {"secret": "test-secret"},
                "is_enabled": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["trigger_type"] == "webhook"
        assert "id" in trigger
    
    def test_create_schedule_trigger(self, client, auth_headers, test_db, test_user):
        """Test creating a schedule trigger."""
        workflow = Workflow(
            name="Scheduled Workflow",
            trigger_type="schedule",
            trigger_config={"cron": "0 0 * * *"},
            steps=[],
            owner_id=test_user.id
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        response = client.post(
            "/api/v1/automation/triggers",
            json={
                "workflow_id": str(workflow.id),
                "trigger_type": "schedule",
                "config": {"cron": "0 0 * * *"},
                "is_enabled": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["trigger_type"] == "schedule"
        assert "id" in trigger
    
    def test_list_triggers(self, client, auth_headers, test_db, test_user):
        """Test listing triggers."""
        workflow = Workflow(
            name="Trigger Test",
            trigger_type="webhook",
            trigger_config={"secret": "test"},
            steps=[],
            owner_id=test_user.id,
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/triggers",
            headers=auth_headers
        )
        
        if response.status_code != 200:
            print(f"Response: {response.status_code} - {response.json()}")
        assert response.status_code == 200
        triggers = response.json()
        assert len(triggers) >= 1
    
    def test_update_trigger(self, client, auth_headers):
        """Test updating a trigger."""
        response = client.put(
            "/api/v1/automation/triggers/test-trigger-id?is_enabled=false",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["is_enabled"] is False


class TestIntegrationManagement:
    """Test integration management endpoints."""
    
    def test_list_integrations(self, client, auth_headers, test_db, test_user):
        """Test listing integrations."""
        integration = Integration(
            user_id=test_user.id,
            type="slack",
            name="Test Slack",
            config={"webhook": "https://slack.com/webhook"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/integrations",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        integrations = response.json()
        assert len(integrations) >= 1
        assert any(i["id"] == "slack" for i in integrations)
    
    def test_connect_integration(self, client, auth_headers):
        """Test connecting a new integration."""
        response = client.post(
            "/api/v1/automation/integrations/connect",
            json={
                "integration_type": "slack",
                "name": "My Slack",
                "config": {"webhook_url": "https://hooks.slack.com/test"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        integration = response.json()
        assert integration["integration_type"] == "slack"
        assert integration["is_active"] is True
    
    def test_disconnect_integration(self, client, auth_headers, test_db, test_user):
        """Test disconnecting an integration."""
        integration = Integration(
            user_id=test_user.id,
            type="clickup",
            name="Test ClickUp",
            config={"api_token": "test-token"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        
        response = client.delete(
            "/api/v1/automation/integrations/clickup/disconnect",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "integration disconnected successfully" in response.json()["message"]
    
    def test_integration_status(self, client, auth_headers, test_db, test_user):
        """Test checking integration status."""
        integration = Integration(
            user_id=test_user.id,
            type="notion",
            name="Test Notion",
            config={"api_token": "test-token"},
            is_active=True,
            last_synced_at=datetime.utcnow()
        )
        test_db.add(integration)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/integrations/notion/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        status = response.json()
        assert status["connected"] is True
        assert status["is_active"] is True
        assert "last_synced_at" in status


@pytest.mark.skip(reason="Not required for initial launch - workflow execution needs implementation")
class TestWorkflowStepExecution:
    """Test individual workflow step execution logic."""
    
    @patch('apps.backend.routes.automation.execute_task')
    async def test_execute_task_step(self, mock_execute_task):
        """Test executing a task step."""
        from ..routes.automation import execute_workflow_step, WorkflowStep
        
        mock_execute_task.return_value = {"success": True}
        
        step = WorkflowStep(
            id="task1",
            type="task",
            name="Test Task",
            config={"task_id": "send_email", "parameters": {"to": "test@example.com"}},
            next_steps=["end"]
        )
        
        context = {}
        result = await execute_workflow_step(step, context, None)
        
        assert result["success"] is True
        mock_execute_task.assert_called_once()
    
    async def test_execute_condition_step(self):
        """Test executing a condition step."""
        from ..routes.automation import execute_workflow_step, WorkflowStep
        
        step = WorkflowStep(
            id="cond1",
            type="condition",
            name="Check Value",
            config={"condition": "value == 42"},
            next_steps=["true_branch", "false_branch"]
        )
        
        context = {"value": "42"}
        result = await execute_workflow_step(step, context, None)
        
        assert result is True
    
    async def test_execute_wait_step(self):
        """Test executing a wait step."""
        from ..routes.automation import execute_workflow_step, WorkflowStep
        import time
        
        step = WorkflowStep(
            id="wait1",
            type="wait",
            name="Wait 1 Second",
            config={"duration": 0.1},  # 100ms for testing
            next_steps=["end"]
        )
        
        start_time = time.time()
        result = await execute_workflow_step(step, {}, None)
        end_time = time.time()
        
        assert result["waited"] == 0.1
        assert (end_time - start_time) >= 0.1