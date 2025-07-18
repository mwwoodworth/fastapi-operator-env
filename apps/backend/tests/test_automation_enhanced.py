"""
Comprehensive tests for enhanced automation endpoints.
Tests all workflow, trigger, webhook, integration, and admin functionality.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
import hmac
import hashlib

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, UserRole, Workflow, WorkflowRun, Integration
from ..db.models import WebhookEvent

# Test data
SAMPLE_WORKFLOW_STEPS = [
    {
        "id": "step1",
        "type": "http",
        "name": "Call API",
        "config": {"url": "https://api.example.com", "method": "GET"},
        "next_steps": ["step2"]
    },
    {
        "id": "step2",
        "type": "condition",
        "name": "Check Response",
        "config": {"condition": "response.status == 200"},
        "next_steps": ["step3", "step4"]
    },
    {
        "id": "step3",
        "type": "notification",
        "name": "Success Notification",
        "config": {"channel": "slack", "message": "Success!"},
        "next_steps": ["end"]
    },
    {
        "id": "step4",
        "type": "notification",
        "name": "Error Notification",
        "config": {"channel": "email", "message": "Failed!"},
        "next_steps": ["end"],
        "error_handler": "step5"
    },
    {
        "id": "step5",
        "type": "script",
        "name": "Error Handler",
        "config": {"script": "console.log('Error handled')"},
        "next_steps": ["end"]
    }
]


class TestWorkflowCRUD:
    """Test workflow CRUD operations with enhanced features."""
    
    def test_create_workflow_with_validation(self, client, auth_headers):
        """Test creating workflow with step validation."""
        response = client.post(
            "/api/v1/automation/workflows",
            json={
                "name": "Test Workflow",
                "description": "A test workflow with validation",
                "trigger_type": "manual",
                "trigger_config": {},
                "steps": SAMPLE_WORKFLOW_STEPS,
                "tags": ["test", "automation"],
                "metadata": {"category": "testing"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert len(data["steps"]) == 5
        assert data["tags"] == ["test", "automation"]
        assert data["version"] == "1.0.0"
    
    def test_create_workflow_invalid_step_reference(self, client, auth_headers):
        """Test workflow creation with invalid step reference."""
        invalid_steps = [
            {
                "id": "step1",
                "type": "http",
                "name": "Call API",
                "config": {"url": "https://api.example.com"},
                "next_steps": ["nonexistent_step"]  # Invalid reference
            }
        ]
        
        response = client.post(
            "/api/v1/automation/workflows",
            json={
                "name": "Invalid Workflow",
                "description": "Workflow with bad step reference",
                "trigger_type": "manual",
                "trigger_config": {},
                "steps": invalid_steps
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        # Check if detail is in response, otherwise print response for debugging
        response_json = response.json()
        if "detail" in response_json:
            assert "Invalid next_step reference" in response_json["detail"]
        else:
            # FastAPI might return a different format
            assert "Invalid next_step reference" in str(response_json)
    
    def test_create_scheduled_workflow(self, client, auth_headers):
        """Test creating a scheduled workflow with cron validation."""
        response = client.post(
            "/api/v1/automation/workflows",
            json={
                "name": "Daily Report",
                "description": "Generate daily reports at 9 AM",
                "trigger_type": "schedule",
                "trigger_config": {"cron": "0 9 * * *"},
                "steps": [{
                    "id": "generate",
                    "type": "script",
                    "name": "Generate Report",
                    "config": {"script": "generateReport()"},
                    "next_steps": ["end"]
                }]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["trigger_type"] == "schedule"
        assert data["trigger_config"]["cron"] == "0 9 * * *"
    
    def test_create_workflow_invalid_cron(self, client, auth_headers):
        """Test scheduled workflow with invalid cron expression."""
        response = client.post(
            "/api/v1/automation/workflows",
            json={
                "name": "Invalid Schedule",
                "description": "Bad cron expression",
                "trigger_type": "schedule",
                "trigger_config": {"cron": "invalid cron"},
                "steps": []
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Invalid cron expression" in str(response.json())
    
    def test_list_workflows_with_filters(self, client, auth_headers, test_db, test_user):
        """Test listing workflows with various filters."""
        # Create test workflows
        workflows = []
        for i in range(5):
            workflow = Workflow(
                name=f"Workflow {i}",
                description=f"Test workflow {i}",
                owner_id=test_user.id,
                trigger_type="manual" if i % 2 == 0 else "webhook",
                trigger_config={},
                steps=[],
                is_active=i % 2 == 0,
                tags=["test", f"tag{i}"],
                meta_data={"index": i}
            )
            workflows.append(workflow)
        
        test_db.add_all(workflows)
        test_db.commit()
        
        # Test filtering by trigger type
        response = client.get(
            "/api/v1/automation/workflows?trigger_type=webhook",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(w["trigger_type"] == "webhook" for w in data["items"])
        
        # Test filtering by status
        response = client.get(
            "/api/v1/automation/workflows?status=active",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(w["is_active"] for w in data["items"])
        
        # Test search
        response = client.get(
            "/api/v1/automation/workflows?search=Workflow 3",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Workflow 3"
        
        # Test pagination
        response = client.get(
            "/api/v1/automation/workflows?page=1&limit=2",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["limit"] == 2
    
    def test_update_workflow_with_versioning(self, client, auth_headers, test_db, test_user):
        """Test workflow update with automatic version increment."""
        workflow = Workflow(
            name="Original Workflow",
            description="Original description",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[],
            version="1.0.0"
        )
        test_db.add(workflow)
        test_db.commit()
        test_db.refresh(workflow)
        
        # Update workflow
        response = client.put(
            f"/api/v1/automation/workflows/{workflow.id}",
            json={
                "name": "Updated Workflow",
                "description": "Updated description",
                "steps": SAMPLE_WORKFLOW_STEPS[:2]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workflow"
        assert data["version"] == "1.0.1"  # Version incremented
        assert len(data["steps"]) == 2
    
    def test_delete_workflow_with_active_runs(self, client, auth_headers, test_db, test_user):
        """Test deleting workflow with active runs."""
        workflow = Workflow(
            name="Active Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create active run
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            trigger_data={},
            steps_total=1
        )
        test_db.add(run)
        test_db.commit()
        
        # Try to delete without force
        response = client.delete(
            f"/api/v1/automation/workflows/{workflow.id}",
            headers=auth_headers
        )
        assert response.status_code == 400
        response_json = response.json()
        if "detail" in response_json:
            assert "active runs" in response_json["detail"]
        else:
            assert "active runs" in str(response_json)
        
        # Delete with force
        response = client.delete(
            f"/api/v1/automation/workflows/{workflow.id}?force=true",
            headers=auth_headers
        )
        assert response.status_code == 200


class TestWorkflowExecution:
    """Test workflow execution with enhanced features."""
    
    def test_execute_workflow_dry_run(self, client, auth_headers, test_db, test_user):
        """Test dry run execution."""
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=SAMPLE_WORKFLOW_STEPS,
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/automation/workflows/{workflow.id}/execute",
            json={
                "input_data": {"test": "data"},
                "dry_run": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["output"]["dry_run"] is True
        assert data["output"]["validation"]["valid"] is True
    
    def test_execute_workflow_sync(self, client, auth_headers, test_db, test_user):
        """Test synchronous workflow execution."""
        workflow = Workflow(
            name="Sync Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[{
                "id": "step1",
                "type": "script",
                "name": "Simple Script",
                "config": {"script": "return {success: true}"},
                "next_steps": ["end"]
            }],
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/automation/workflows/{workflow.id}/execute",
            json={
                "input_data": {"value": 42},
                "async_execution": False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["steps_completed"] == data["steps_total"]
    
    @patch('apps.backend.routes.automation.execute_workflow_async')
    def test_execute_workflow_async(self, mock_execute, client, auth_headers, test_db, test_user):
        """Test asynchronous workflow execution."""
        workflow = Workflow(
            name="Async Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=SAMPLE_WORKFLOW_STEPS,
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        mock_execute.return_value = None
        
        response = client.post(
            f"/api/v1/automation/workflows/{workflow.id}/execute",
            json={
                "input_data": {"test": "async"},
                "async_execution": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert mock_execute.called
    
    def test_get_workflow_runs_with_filters(self, client, auth_headers, test_db, test_user):
        """Test getting workflow runs with filters."""
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create runs with different statuses
        for i, status in enumerate(["completed", "failed", "running"]):
            run = WorkflowRun(
                workflow_id=workflow.id,
                status=status,
                trigger_data={"index": i},
                steps_total=3,
                steps_completed=i,
                started_at=datetime.utcnow() - timedelta(hours=i)
            )
            test_db.add(run)
        test_db.commit()
        
        # Filter by status
        response = client.get(
            f"/api/v1/automation/workflows/{workflow.id}/runs?status=completed",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "completed" for r in data["items"])
        
        # Filter by date range
        start = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        response = client.get(
            f"/api/v1/automation/workflows/{workflow.id}/runs?start_date={start}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        
        # Check stats
        assert "stats" in data
        assert data["stats"]["total_runs"] == 3
    
    def test_cancel_workflow_run(self, client, auth_headers, test_db, test_user):
        """Test cancelling a running workflow."""
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        test_db.add(workflow)
        test_db.commit()
        
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            trigger_data={},
            steps_total=5,
            steps_completed=2
        )
        test_db.add(run)
        test_db.commit()
        
        response = client.put(
            f"/api/v1/automation/runs/{run.id}/cancel",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Workflow run cancelled"
        
        # Verify run is cancelled
        test_db.refresh(run)
        assert run.status == "cancelled"
        assert run.error == "Cancelled by user"
    
    def test_retry_failed_run(self, client, auth_headers, test_db, test_user):
        """Test retrying a failed workflow run."""
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[],
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create failed run
        failed_run = WorkflowRun(
            workflow_id=workflow.id,
            status="failed",
            trigger_data={"input": "test"},
            steps_total=3,
            steps_completed=1,
            error="Test error"
        )
        test_db.add(failed_run)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/automation/runs/{failed_run.id}/retry",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        new_run = response.json()
        assert new_run["status"] == "running"
        assert new_run["id"] != str(failed_run.id)


class TestTriggerManagement:
    """Test trigger management endpoints."""
    
    def test_create_schedule_trigger(self, client, auth_headers, test_db, test_user):
        """Test creating a schedule trigger with validation."""
        workflow = Workflow(
            name="Scheduled Workflow",
            owner_id=test_user.id,
            trigger_type="schedule",
            trigger_config={},
            steps=[],
            meta_data={}
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            "/api/v1/automation/triggers",
            json={
                "workflow_id": str(workflow.id),
                "trigger_type": "schedule",
                "config": {"cron": "0 */6 * * *"},  # Every 6 hours
                "name": "Six Hour Schedule",
                "description": "Runs every 6 hours"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["type"] == "schedule"
        assert trigger["config"]["cron"] == "0 */6 * * *"
        assert trigger["name"] == "Six Hour Schedule"
    
    def test_create_webhook_trigger(self, client, auth_headers, test_db, test_user):
        """Test creating a webhook trigger."""
        workflow = Workflow(
            name="Webhook Workflow",
            owner_id=test_user.id,
            trigger_type="webhook",
            trigger_config={},
            steps=[],
            meta_data={}
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            "/api/v1/automation/triggers",
            json={
                "workflow_id": str(workflow.id),
                "trigger_type": "webhook",
                "config": {"path": "/custom-webhook"},
                "name": "Custom Webhook"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["type"] == "webhook"
        assert "secret" in trigger["config"]  # Auto-generated
    
    def test_list_triggers_with_filters(self, client, auth_headers, test_db, test_user):
        """Test listing triggers with filters."""
        # Create workflows with triggers
        for i in range(3):
            workflow = Workflow(
                name=f"Workflow {i}",
                owner_id=test_user.id,
                trigger_type="manual",
                trigger_config={},
                steps=[],
                meta_data={
                    "triggers": [
                        {
                            "id": f"trigger-{i}-1",
                            "type": "schedule" if i % 2 == 0 else "webhook",
                            "config": {"cron": "0 0 * * *"} if i % 2 == 0 else {"path": f"/hook{i}"},
                            "is_enabled": i != 1,
                            "name": f"Trigger {i}"
                        }
                    ]
                }
            )
            test_db.add(workflow)
        test_db.commit()
        
        # Filter by type
        response = client.get(
            "/api/v1/automation/triggers?trigger_type=schedule",
            headers=auth_headers
        )
        assert response.status_code == 200
        triggers = response.json()
        assert all(t["type"] == "schedule" for t in triggers)
        
        # Filter by enabled status
        response = client.get(
            "/api/v1/automation/triggers?is_enabled=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        triggers = response.json()
        assert all(t["is_enabled"] for t in triggers)
    
    def test_update_trigger(self, client, auth_headers, test_db, test_user):
        """Test updating a trigger."""
        trigger_id = str(uuid4())
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="schedule",
            trigger_config={},
            steps=[],
            meta_data={
                "triggers": [{
                    "id": trigger_id,
                    "type": "schedule",
                    "config": {"cron": "0 0 * * *"},
                    "is_enabled": True,
                    "name": "Daily Schedule"
                }]
            }
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.put(
            f"/api/v1/automation/triggers/{trigger_id}",
            json={
                "config": {"cron": "0 0 * * 1"},  # Weekly instead of daily
                "is_enabled": False,
                "name": "Weekly Schedule"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        updated = response.json()
        assert updated["config"]["cron"] == "0 0 * * 1"
        assert updated["is_enabled"] is False
        assert updated["name"] == "Weekly Schedule"
    
    def test_delete_trigger(self, client, auth_headers, test_db, test_user):
        """Test deleting a trigger."""
        trigger_id = str(uuid4())
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="webhook",
            trigger_config={},
            steps=[],
            meta_data={
                "triggers": [{
                    "id": trigger_id,
                    "type": "webhook",
                    "config": {"path": "/test"},
                    "is_enabled": True
                }]
            }
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.delete(
            f"/api/v1/automation/triggers/{trigger_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Trigger deleted successfully"
        
        # Verify trigger is deleted
        test_db.refresh(workflow)
        assert len(workflow.meta_data.get("triggers", [])) == 0


class TestWebhookEndpoints:
    """Test webhook functionality."""
    
    def test_receive_webhook(self, client, test_db):
        """Test receiving a webhook and triggering workflows."""
        webhook_id = "test-webhook-123"
        secret = "webhook-secret"
        
        # Create workflow with webhook trigger
        workflow = Workflow(
            name="Webhook Workflow",
            trigger_type="webhook",
            trigger_config={"webhook_id": webhook_id, "secret": secret},
            steps=[{
                "id": "log",
                "type": "script",
                "name": "Log Webhook",
                "config": {"script": "console.log(input)"},
                "next_steps": ["end"]
            }],
            is_active=True,
            owner_id=str(uuid4())
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Prepare webhook payload
        payload = {"event": "test", "data": {"value": 123}}
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        response = client.post(
            f"/api/v1/automation/webhooks/{webhook_id}/receive",
            content=body,
            headers={
                "x-webhook-signature": signature,
                "content-type": "application/json"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["triggered_count"] == 1
        
        # Verify webhook event was logged
        event = test_db.query(WebhookEvent).filter_by(source=f"webhook_{webhook_id}").first()
        assert event is not None
        assert event.payload == payload
    
    def test_webhook_invalid_signature(self, client, test_db):
        """Test webhook with invalid signature."""
        webhook_id = "secure-webhook"
        secret = "webhook-secret"
        
        workflow = Workflow(
            name="Secure Webhook",
            trigger_type="webhook",
            trigger_config={"webhook_id": webhook_id, "secret": secret},
            steps=[],
            is_active=True,
            owner_id=str(uuid4())
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/automation/webhooks/{webhook_id}/receive",
            json={"test": "data"},
            headers={"x-webhook-signature": "invalid-signature"}
        )
        
        assert response.status_code == 404  # No workflows triggered
    
    def test_test_webhook_endpoint(self, client, auth_headers):
        """Test the webhook testing endpoint."""
        response = client.post(
            "/api/v1/automation/webhooks/test",
            json={
                "webhook_url": "https://httpbin.org/post",
                "payload": {"test": "data"},
                "headers": {"X-Custom-Header": "test"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        if "error" not in data:  # May fail in test environment
            assert "status_code" in data
            assert "success" in data
    
    def test_get_webhook_events(self, client, auth_headers, test_db, test_user):
        """Test getting webhook event history."""
        webhook_id = "test-webhook"
        workflow = Workflow(
            name="Test Workflow",
            owner_id=test_user.id,
            trigger_type="webhook",
            trigger_config={"webhook_id": webhook_id},
            steps=[]
        )
        test_db.add(workflow)
        
        # Create webhook events
        for i in range(5):
            event = WebhookEvent(
                source=f"webhook_{webhook_id}",
                event_type="workflow_trigger",
                headers={"content-type": "application/json"},
                payload={"index": i},
                processed=False
            )
            test_db.add(event)
        test_db.commit()
        
        response = client.get(
            f"/api/v1/automation/webhooks/{webhook_id}/events?page=1&limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 5
        assert data["pages"] == 2


class TestIntegrationManagement:
    """Test integration management endpoints."""
    
    def test_list_available_integrations(self, client, auth_headers):
        """Test listing all available integration types."""
        response = client.get(
            "/api/v1/automation/integrations/available",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        integrations = response.json()
        assert len(integrations) >= 20  # We have 20+ integrations
        
        # Check structure
        slack = next(i for i in integrations if i["id"] == "slack")
        assert slack["name"] == "Slack"
        assert "webhook_url" in slack["required_config"]
        assert "send_message" in slack["available_actions"]
    
    def test_connect_integration(self, client, auth_headers, test_db, test_user):
        """Test connecting a new integration."""
        response = client.post(
            "/api/v1/automation/integrations/connect",
            json={
                "integration_type": "slack",
                "name": "My Slack Workspace",
                "config": {"webhook_url": "https://hooks.slack.com/test"},
                "description": "Team notifications",
                "scopes": ["chat:write", "files:write"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        integration = response.json()
        assert integration["type"] == "slack"
        assert integration["name"] == "My Slack Workspace"
        assert integration["is_active"] is True
        
        # Verify in database
        db_integration = test_db.query(Integration).filter_by(
            user_id=test_user.id,
            type="slack"
        ).first()
        assert db_integration is not None
        # Scopes are stored in meta_data
        assert db_integration.meta_data.get("scopes") == ["chat:write", "files:write"]
    
    def test_connect_duplicate_integration(self, client, auth_headers, test_db, test_user):
        """Test connecting duplicate integration type."""
        # Create existing integration
        existing = Integration(
            user_id=test_user.id,
            type="github",
            name="Existing GitHub",
            config={"access_token": "old-token"},
            is_active=True
        )
        test_db.add(existing)
        test_db.commit()
        
        response = client.post(
            "/api/v1/automation/integrations/connect",
            json={
                "integration_type": "github",
                "name": "New GitHub",
                "config": {"access_token": "new-token"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "already connected" in response.json()["message"]
    
    def test_connect_integration_missing_config(self, client, auth_headers):
        """Test connecting integration with missing required config."""
        response = client.post(
            "/api/v1/automation/integrations/connect",
            json={
                "integration_type": "jira",
                "name": "My Jira",
                "config": {"domain": "test.atlassian.net"}  # Missing email and api_token
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        # Response format - handle both validation and business logic errors
        error_resp = response.json()
        error_message = error_resp.get("message", "").lower()
        # Accept either validation error or missing field error
        assert any(phrase in error_message for phrase in ["validation failed", "missing required field"])
    
    def test_list_connected_integrations(self, client, auth_headers, test_db, test_user):
        """Test listing user's connected integrations."""
        # Create test integrations
        integrations = [
            Integration(
                user_id=test_user.id,
                type="slack",
                name="Slack Integration",
                config={"webhook_url": "https://slack.com"},
                is_active=True,
                meta_data={"scopes": ["chat:write"]}
            ),
            Integration(
                user_id=test_user.id,
                type="github",
                name="GitHub Integration",
                config={"access_token": "token"},
                is_active=False,
                meta_data={}
            )
        ]
        test_db.add_all(integrations)
        test_db.commit()
        
        # List all
        response = client.get(
            "/api/v1/automation/integrations/connected",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Filter by type
        response = client.get(
            "/api/v1/automation/integrations/connected?integration_type=slack",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "slack"
        
        # Filter by active status
        response = client.get(
            "/api/v1/automation/integrations/connected?is_active=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(i["is_active"] for i in data)
    
    def test_update_integration(self, client, auth_headers, test_db, test_user):
        """Test updating an integration."""
        integration = Integration(
            user_id=test_user.id,
            type="notion",
            name="Old Notion",
            config={"api_key": "old-key", "database_id": "old-db"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        test_db.refresh(integration)
        
        response = client.put(
            f"/api/v1/automation/integrations/{integration.id}",
            json={
                "name": "Updated Notion",
                "config": {"database_id": "new-db"},  # Partial update
                "is_active": False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Notion"
        assert data["is_active"] is False
        
        # Verify config was merged - need to check the returned data
        assert data["config"]["api_key"] == "old-key"  # Preserved
        assert data["config"]["database_id"] == "new-db"  # Updated
    
    def test_disconnect_integration(self, client, auth_headers, test_db, test_user):
        """Test disconnecting an integration."""
        integration = Integration(
            user_id=test_user.id,
            type="discord",
            name="My Discord",
            config={"webhook_url": "https://discord.com"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        test_db.refresh(integration)
        
        response = client.delete(
            f"/api/v1/automation/integrations/{integration.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "disconnected successfully" in response.json()["message"]
        
        # Verify deleted
        assert test_db.query(Integration).filter_by(id=integration.id).first() is None
    
    @patch('apps.backend.routes.automation.test_integration_health')
    async def test_get_integration_status(self, mock_health, client, auth_headers, test_db, test_user):
        """Test getting integration status."""
        integration = Integration(
            user_id=test_user.id,
            type="stripe",
            name="Stripe Integration",
            config={"api_key": "sk_test_123"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        test_db.refresh(integration)
        
        mock_health.return_value = {
            "status": "healthy",
            "response_time": 0.123,
            "last_error": None
        }
        
        response = client.get(
            f"/api/v1/automation/integrations/{integration.id}/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "stripe"
        assert data["health"]["status"] == "healthy"
    
    @patch('apps.backend.routes.automation.test_integration_connection')
    async def test_test_integration(self, mock_test, client, auth_headers, test_db, test_user):
        """Test integration connection test."""
        integration = Integration(
            user_id=test_user.id,
            type="sendgrid",
            name="SendGrid",
            config={"api_key": "SG.test"},
            is_active=True
        )
        test_db.add(integration)
        test_db.commit()
        test_db.refresh(integration)
        
        mock_test.return_value = {
            "success": True,
            "message": "Connection successful",
            "details": {"authenticated": True}
        }
        
        response = client.post(
            f"/api/v1/automation/integrations/{integration.id}/test",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestBulkOperations:
    """Test bulk workflow operations."""
    
    def test_bulk_activate_workflows(self, client, auth_headers, test_db, test_user):
        """Test bulk activating workflows."""
        workflows = []
        for i in range(3):
            workflow = Workflow(
                name=f"Workflow {i}",
                owner_id=test_user.id,
                trigger_type="manual",
                trigger_config={},
                steps=[],
                is_active=False
            )
            workflows.append(workflow)
        test_db.add_all(workflows)
        test_db.commit()
        
        workflow_ids = [str(w.id) for w in workflows]
        
        response = client.post(
            "/api/v1/automation/workflows/bulk",
            json={
                "workflow_ids": workflow_ids,
                "action": "activate"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all(r["status"] == "activated" for r in data["results"])
        
        # Verify in database
        for workflow in workflows:
            test_db.refresh(workflow)
            assert workflow.is_active is True
    
    def test_bulk_archive_workflows(self, client, auth_headers, test_db, test_user):
        """Test bulk archiving workflows."""
        workflows = []
        for i in range(2):
            workflow = Workflow(
                name=f"To Archive {i}",
                owner_id=test_user.id,
                trigger_type="manual",
                trigger_config={},
                steps=[],
                meta_data={}
            )
            workflows.append(workflow)
        test_db.add_all(workflows)
        test_db.commit()
        
        workflow_ids = [str(w.id) for w in workflows]
        
        response = client.post(
            "/api/v1/automation/workflows/bulk",
            json={
                "workflow_ids": workflow_ids,
                "action": "archive"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "archived" for r in data["results"])
        
        # Verify archived
        for workflow in workflows:
            test_db.refresh(workflow)
            assert workflow.meta_data.get("archived") is True
            assert "archived_at" in workflow.meta_data
    
    def test_bulk_export_workflows(self, client, auth_headers, test_db, test_user):
        """Test bulk exporting workflows."""
        workflow = Workflow(
            name="Export Test",
            owner_id=test_user.id,
            trigger_type="webhook",
            trigger_config={"webhook_id": "test", "secret": "secret123"},
            steps=SAMPLE_WORKFLOW_STEPS[:2],
            tags=["export", "test"]
        )
        test_db.add(workflow)
        test_db.commit()
        
        response = client.post(
            "/api/v1/automation/workflows/bulk",
            json={
                "workflow_ids": [str(workflow.id)],
                "action": "export"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["status"] == "exported"
        
        exported = data["results"][0]["data"]
        assert exported["name"] == "Export Test"
        assert "secret" not in exported["trigger_config"]  # Sensitive data excluded
        assert len(exported["steps"]) == 2
    
    def test_bulk_delete_workflows(self, client, auth_headers, test_db, test_user):
        """Test bulk deleting workflows."""
        workflows = []
        for i in range(2):
            workflow = Workflow(
                name=f"To Delete {i}",
                owner_id=test_user.id,
                trigger_type="manual",
                trigger_config={},
                steps=[]
            )
            workflows.append(workflow)
        test_db.add_all(workflows)
        test_db.commit()
        
        workflow_ids = [str(w.id) for w in workflows]
        
        response = client.post(
            "/api/v1/automation/workflows/bulk",
            json={
                "workflow_ids": workflow_ids,
                "action": "delete"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "deleted" for r in data["results"])
        
        # Verify deleted
        for wf_id in workflow_ids:
            assert test_db.query(Workflow).filter_by(id=wf_id).first() is None
    
    def test_bulk_operation_access_control(self, client, auth_headers, test_db, test_user):
        """Test bulk operations with workflows not owned by user."""
        other_user_id = str(uuid4())
        
        # User's workflow
        my_workflow = Workflow(
            name="My Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        
        # Other user's workflow
        other_workflow = Workflow(
            name="Other Workflow",
            owner_id=other_user_id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        
        test_db.add_all([my_workflow, other_workflow])
        test_db.commit()
        
        response = client.post(
            "/api/v1/automation/workflows/bulk",
            json={
                "workflow_ids": [str(my_workflow.id), str(other_workflow.id)],
                "action": "activate"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "not found or access denied" in response.json()["message"]


class TestImportExport:
    """Test workflow import/export functionality."""
    
    def test_import_workflows_merge_mode(self, client, auth_headers, test_db, test_user):
        """Test importing workflows in merge mode."""
        import_data = {
            "workflows": [
                {
                    "name": "Imported Workflow 1",
                    "description": "First import",
                    "trigger_type": "manual",
                    "trigger_config": {},
                    "steps": SAMPLE_WORKFLOW_STEPS[:2],
                    "tags": ["imported"],
                    "is_active": True
                },
                {
                    "name": "Imported Workflow 2",
                    "description": "Second import",
                    "trigger_type": "schedule",
                    "trigger_config": {"cron": "0 0 * * *"},
                    "steps": [],
                    "is_active": False
                }
            ],
            "mode": "merge"
        }
        
        response = client.post(
            "/api/v1/automation/workflows/import",
            json=import_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(r["status"] == "created" for r in data["results"])
        
        # Verify workflows created
        imported = test_db.query(Workflow).filter(
            Workflow.owner_id == test_user.id,
            Workflow.name.like("Imported%")
        ).all()
        assert len(imported) == 2
    
    def test_import_workflows_overwrite_mode(self, client, auth_headers, test_db, test_user):
        """Test importing workflows in overwrite mode."""
        # Create existing workflow
        existing = Workflow(
            id=str(uuid4()),
            name="Existing Workflow",
            description="Will be overwritten",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[],
            version="1.0.0"
        )
        test_db.add(existing)
        test_db.commit()
        
        import_data = {
            "workflows": [{
                "id": str(existing.id),
                "name": "Updated Workflow",
                "description": "Overwritten",
                "trigger_type": "webhook",
                "trigger_config": {"webhook_id": "new"},
                "steps": SAMPLE_WORKFLOW_STEPS[:1]
            }],
            "mode": "overwrite"
        }
        
        response = client.post(
            "/api/v1/automation/workflows/import",
            json=import_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["status"] == "updated"
        
        # Verify overwritten
        test_db.refresh(existing)
        assert existing.name == "Updated Workflow"
        assert existing.trigger_type == "webhook"
    
    def test_import_workflows_skip_mode(self, client, auth_headers, test_db, test_user):
        """Test importing workflows in skip mode."""
        # Create existing workflow
        existing = Workflow(
            id=str(uuid4()),
            name="Existing Workflow",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        test_db.add(existing)
        test_db.commit()
        
        import_data = {
            "workflows": [
                {
                    "id": str(existing.id),
                    "name": "Should Be Skipped"
                },
                {
                    "name": "New Workflow",
                    "trigger_type": "manual",
                    "trigger_config": {},
                    "steps": []
                }
            ],
            "mode": "skip"
        }
        
        response = client.post(
            "/api/v1/automation/workflows/import",
            json=import_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["status"] == "skipped"
        assert data["results"][1]["status"] == "created"
    
    def test_import_workflows_dry_run(self, client, auth_headers):
        """Test dry run import."""
        import_data = {
            "workflows": [{
                "name": "Dry Run Test",
                "trigger_type": "manual",
                "trigger_config": {},
                "steps": []
            }],
            "mode": "merge",
            "dry_run": True
        }
        
        response = client.post(
            "/api/v1/automation/workflows/import",
            json=import_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True
        assert data["results"][0]["status"] == "created"
        
        # Verify not actually created
        assert client.get(
            "/api/v1/automation/workflows?search=Dry Run Test",
            headers=auth_headers
        ).json()["total"] == 0


class TestAdminEndpoints:
    """Test admin-only endpoints."""
    
    def test_admin_list_all_workflows(self, client, admin_headers, test_db):
        """Test admin listing all workflows."""
        # Create workflows for different users
        for i in range(3):
            workflow = Workflow(
                name=f"User {i} Workflow",
                owner_id=str(uuid4()),
                trigger_type="manual",
                trigger_config={},
                steps=[]
            )
            test_db.add(workflow)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/admin/workflows?page=1&limit=10",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        assert "owner_id" in data["items"][0]  # Admin sees owner info
    
    def test_admin_list_workflows_by_user(self, client, admin_headers, test_db):
        """Test admin filtering workflows by user."""
        user_id = str(uuid4())
        
        # Create workflows for specific user
        for i in range(2):
            workflow = Workflow(
                name=f"User Workflow {i}",
                owner_id=user_id,
                trigger_type="manual",
                trigger_config={},
                steps=[]
            )
            test_db.add(workflow)
        test_db.commit()
        
        response = client.get(
            f"/api/v1/automation/admin/workflows?user_id={user_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(w["owner_id"] == user_id for w in data["items"])
    
    def test_admin_list_all_runs(self, client, admin_headers, test_db):
        """Test admin listing all workflow runs."""
        # Create runs for different workflows
        for i in range(3):
            workflow = Workflow(
                name=f"Workflow {i}",
                owner_id=str(uuid4()),
                trigger_type="manual",
                trigger_config={},
                steps=[]
            )
            test_db.add(workflow)
            test_db.commit()
            
            run = WorkflowRun(
                workflow_id=workflow.id,
                status="completed" if i % 2 == 0 else "failed",
                trigger_data={},
                steps_total=5,
                steps_completed=5 if i % 2 == 0 else 3
            )
            test_db.add(run)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/admin/runs",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        assert "workflow_name" in data["items"][0]  # Includes workflow info
    
    def test_admin_get_stats(self, client, admin_headers, test_db):
        """Test admin getting system statistics."""
        # Create test data
        workflows = []
        for i in range(5):
            workflow = Workflow(
                name=f"Workflow {i}",
                owner_id=str(uuid4()),
                trigger_type="manual",
                trigger_config={},
                steps=[],
                is_active=i < 3
            )
            workflows.append(workflow)
        test_db.add_all(workflows)
        test_db.commit()
        
        # Create runs
        for workflow in workflows[:3]:
            for status in ["completed", "failed", "running"]:
                run = WorkflowRun(
                    workflow_id=workflow.id,
                    status=status,
                    trigger_data={},
                    steps_total=1
                )
                test_db.add(run)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/admin/stats",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_workflows"] >= 5
        assert data["active_workflows"] >= 3
        assert data["total_runs"] >= 9
        assert "completed" in data["runs_by_status"]
        assert "failed" in data["runs_by_status"]
    
    def test_non_admin_access_denied(self, client, auth_headers):
        """Test non-admin user cannot access admin endpoints."""
        endpoints = [
            "/api/v1/automation/admin/workflows",
            "/api/v1/automation/admin/runs",
            "/api/v1/automation/admin/stats"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint, headers=auth_headers)
            assert response.status_code == 403
            assert "Admin privileges required" in response.json()["message"]


class TestHealthAndMonitoring:
    """Test health check and monitoring endpoints."""
    
    def test_health_check(self, client, test_db):
        """Test automation service health check."""
        # Create some test data
        Integration(
            user_id=str(uuid4()),
            type="slack",
            name="Test",
            config={},
            is_active=True
        )
        test_db.commit()
        
        response = client.get("/api/v1/automation/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data
        assert "database" in data["services"]
        assert "scheduler" in data["services"]
        assert "integrations" in data["services"]
        assert "metrics" in data
        assert data["metrics"]["workflows_total"] >= 0
    
    def test_get_user_metrics(self, client, auth_headers, test_db, test_user):
        """Test getting user automation metrics."""
        # Create workflows and runs
        workflow = Workflow(
            name="Metrics Test",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[],
            is_active=True
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create runs with different statuses
        for status in ["completed", "completed", "failed"]:
            run = WorkflowRun(
                workflow_id=workflow.id,
                status=status,
                trigger_data={},
                steps_total=3,
                started_at=datetime.utcnow() - timedelta(minutes=30)
            )
            test_db.add(run)
        test_db.commit()
        
        response = client.get(
            "/api/v1/automation/metrics?time_range=1h",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "1h"
        assert data["workflows"]["total"] >= 1
        assert data["workflows"]["active"] >= 1
        assert data["runs"]["total"] >= 3
        assert data["runs"]["by_status"]["completed"] == 2
        assert data["runs"]["by_status"]["failed"] == 1
        assert data["performance"]["success_rate"] == 0.666666666666666 or \
               data["performance"]["success_rate"] == 2/3
    
    def test_metrics_different_time_ranges(self, client, auth_headers, test_db, test_user):
        """Test metrics with different time ranges."""
        workflow = Workflow(
            name="Time Range Test",
            owner_id=test_user.id,
            trigger_type="manual",
            trigger_config={},
            steps=[]
        )
        test_db.add(workflow)
        test_db.commit()
        
        # Create runs at different times
        times = [
            timedelta(minutes=30),   # Last hour
            timedelta(hours=12),     # Last 24h
            timedelta(days=3),       # Last 7d
            timedelta(days=15),      # Last 30d
            timedelta(days=45)       # Outside 30d
        ]
        
        for delta in times:
            run = WorkflowRun(
                workflow_id=workflow.id,
                status="completed",
                trigger_data={},
                steps_total=1,
                started_at=datetime.utcnow() - delta
            )
            test_db.add(run)
        test_db.commit()
        
        # Test different ranges
        ranges = {
            "1h": 1,
            "24h": 2,
            "7d": 3,
            "30d": 4
        }
        
        for time_range, expected_count in ranges.items():
            response = client.get(
                f"/api/v1/automation/metrics?time_range={time_range}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["runs"]["total"] == expected_count


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_workflow_not_found(self, client, auth_headers):
        """Test accessing non-existent workflow."""
        fake_id = str(uuid4())
        
        # Test GET endpoints
        get_endpoints = [
            f"/api/v1/automation/workflows/{fake_id}",
            f"/api/v1/automation/workflows/{fake_id}/runs"
        ]
        
        for endpoint in get_endpoints:
            response = client.get(endpoint, headers=auth_headers)
            assert response.status_code == 404
            assert "not found" in response.json()["message"].lower()
        
        # Test POST endpoint
        response = client.post(
            f"/api/v1/automation/workflows/{fake_id}/execute",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
    
    def test_trigger_not_found(self, client, auth_headers):
        """Test accessing non-existent trigger."""
        fake_id = str(uuid4())
        
        response = client.get(
            f"/api/v1/automation/triggers/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
    
    def test_integration_not_found(self, client, auth_headers):
        """Test accessing non-existent integration."""
        fake_id = str(uuid4())
        
        # Test GET endpoint
        response = client.get(
            f"/api/v1/automation/integrations/{fake_id}/status",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
        
        # Test POST endpoint
        response = client.post(
            f"/api/v1/automation/integrations/{fake_id}/test",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
    
    def test_invalid_enum_values(self, client, auth_headers):
        """Test invalid enum values in requests."""
        # Invalid trigger type
        response = client.post(
            "/api/v1/automation/workflows",
            json={
                "name": "Invalid Trigger",
                "description": "Test",
                "trigger_type": "invalid_type",
                "trigger_config": {},
                "steps": []
            },
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Invalid integration type
        response = client.post(
            "/api/v1/automation/integrations/connect",
            json={
                "integration_type": "invalid_integration",
                "name": "Test",
                "config": {}
            },
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_rate_limiting_simulation(self, client, auth_headers):
        """Test behavior under rate limiting conditions."""
        # This is a simulation - actual rate limiting would be implemented
        # at the API gateway or middleware level
        
        # Make multiple rapid requests
        for i in range(5):
            response = client.get(
                "/api/v1/automation/workflows",
                headers=auth_headers
            )
            assert response.status_code == 200
            
        # In production, after rate limit is hit:
        # assert response.status_code == 429
        # assert "rate limit" in response.json()["detail"].lower()


# Test fixtures for admin user
@pytest.fixture
def admin_user(test_db):
    """Create an admin user for testing."""
    admin = User(
        email="admin@test.com",
        username="admin",
        hashed_password="hashed_admin_pass",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        role=UserRole.ADMIN
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def admin_headers(admin_user):
    """Create auth headers for admin user."""
    token = create_access_token({"sub": admin_user.email})
    return {"Authorization": f"Bearer {token}"}