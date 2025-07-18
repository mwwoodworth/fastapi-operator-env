"""
Comprehensive tests for agent endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
import asyncio

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, UserRole, Task, AgentExecution


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_db():
    """Create test database session."""
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(test_db: Session):
    """Create a test user."""
    user = User(
        email="agent@example.com",
        username="agentuser",
        hashed_password="hashedpassword",
        full_name="Agent Test User",
        is_active=True,
        is_verified=True,
        role=UserRole.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_task(test_db: Session, test_user):
    """Create a test task."""
    task = Task(
        title="Test Agent Task",
        description="Task for agent testing",
        project_id=uuid4(),
        assignee_id=test_user.id,
        status="pending",
        priority="high"
    )
    test_db.add(task)
    test_db.commit()
    test_db.refresh(task)
    return task


class TestAgentExecution:
    """Test agent execution endpoints."""
    
    @patch('apps.backend.routes.agents.claude_agent')
    @patch('apps.backend.routes.agents.execute_agent_task')
    def test_execute_agent_task(self, mock_execute, mock_claude, client, auth_headers, test_task):
        """Test executing an agent task."""
        mock_execute.return_value = None  # Background task
        
        response = client.post(
            f"/api/v1/agents/execute/{test_task.id}",
            json={
                "agent_type": "claude",
                "instructions": "Complete this task efficiently",
                "auto_approve": False,
                "max_iterations": 10
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["status"] == "started"
        assert data["task_id"] == str(test_task.id)
    
    def test_execute_nonexistent_task(self, client, auth_headers):
        """Test executing a nonexistent task."""
        fake_task_id = uuid4()
        
        response = client.post(
            f"/api/v1/agents/execute/{fake_task_id}",
            json={
                "agent_type": "claude",
                "instructions": "Complete this task"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "Task not found" in response.json()["detail"]
    
    def test_get_agent_execution_status(self, client, auth_headers, test_db, test_user, test_task):
        """Test getting agent execution status."""
        # Create a test execution
        execution = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="running",
            started_at=datetime.utcnow(),
            steps_completed=3,
            current_step="Analyzing requirements"
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)
        
        response = client.get(
            f"/api/v1/agents/execution/{execution.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["steps_completed"] == 3
        assert data["current_step"] == "Analyzing requirements"
    
    def test_stop_agent_execution(self, client, auth_headers, test_db, test_user, test_task):
        """Test stopping an agent execution."""
        execution = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="running",
            started_at=datetime.utcnow()
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)
        
        response = client.post(
            f"/api/v1/agents/execution/{execution.id}/stop",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Agent execution stopped"
        
        # Verify status updated
        test_db.refresh(execution)
        assert execution.status == "stopped"


class TestAgentApprovals:
    """Test agent approval workflow."""
    
    def test_list_pending_approvals(self, client, auth_headers, test_db, test_user, test_task):
        """Test listing pending agent approvals."""
        # Create executions with pending approvals
        execution1 = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="awaiting_approval",
            started_at=datetime.utcnow(),
            pending_action={"action": "delete_file", "file": "test.txt"}
        )
        execution2 = AgentExecution(
            task_id=uuid4(),
            agent_type="gpt",
            status="awaiting_approval",
            started_at=datetime.utcnow(),
            pending_action={"action": "send_email", "to": "user@example.com"}
        )
        test_db.add_all([execution1, execution2])
        test_db.commit()
        
        response = client.get(
            "/api/v1/agents/approvals",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        approvals = response.json()
        assert len(approvals) >= 1  # At least our test task
        assert any(a["task_id"] == str(test_task.id) for a in approvals)
    
    @patch('apps.backend.routes.agents.notify_agent_decision')
    def test_approve_agent_action(self, mock_notify, client, auth_headers, test_db, test_user, test_task):
        """Test approving an agent action."""
        mock_notify.return_value = None
        
        execution = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="awaiting_approval",
            started_at=datetime.utcnow(),
            pending_action={"action": "create_file", "filename": "report.md"},
            approval_id="approval123"
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)
        
        response = client.post(
            f"/api/v1/agents/approve/{execution.id}",
            json={
                "approval_id": "approval123",
                "approved": True,
                "reason": "Action looks good"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Approval processed"
        
        # Verify notification was sent
        mock_notify.assert_called_once()
    
    def test_reject_agent_action(self, client, auth_headers, test_db, test_user, test_task):
        """Test rejecting an agent action."""
        execution = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="awaiting_approval",
            started_at=datetime.utcnow(),
            pending_action={"action": "delete_database", "database": "prod"},
            approval_id="approval456"
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)
        
        response = client.post(
            f"/api/v1/agents/approve/{execution.id}",
            json={
                "approval_id": "approval456",
                "approved": False,
                "reason": "Too dangerous"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify status updated
        test_db.refresh(execution)
        assert execution.status == "running"  # Continues after rejection


class TestAgentHistory:
    """Test agent execution history."""
    
    def test_get_task_agent_history(self, client, auth_headers, test_db, test_task, test_user):
        """Test getting agent execution history for a task."""
        # Create execution history
        executions = []
        for i in range(3):
            exec = AgentExecution(
                task_id=test_task.id,
                agent_type="claude" if i % 2 == 0 else "gpt",
                status="completed" if i < 2 else "failed",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if i < 2 else None,
                result={"success": True} if i < 2 else None,
                error="Test error" if i == 2 else None
            )
            executions.append(exec)
        test_db.add_all(executions)
        test_db.commit()
        
        response = client.get(
            f"/api/v1/agents/history/{test_task.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        history = response.json()
        assert len(history) == 3
        assert sum(1 for h in history if h["status"] == "completed") == 2
        assert sum(1 for h in history if h["status"] == "failed") == 1


class TestAgentStreaming:
    """Test real-time agent streaming."""
    
    @patch('apps.backend.routes.agents.subscribe_to_agent_events')
    async def test_stream_agent_execution(self, mock_subscribe, client, auth_headers):
        """Test streaming agent execution events."""
        # Create mock event queue
        mock_queue = asyncio.Queue()
        await mock_queue.put(json.dumps({
            "type": "step",
            "step": "Initializing",
            "progress": 10
        }))
        await mock_queue.put(json.dumps({
            "type": "step",
            "step": "Processing",
            "progress": 50
        }))
        await mock_queue.put(json.dumps({
            "type": "complete",
            "result": {"success": True}
        }))
        
        mock_subscribe.return_value = mock_queue
        
        # Note: Testing SSE endpoints requires special handling
        # This is a simplified test structure
        task_id = uuid4()
        execution_id = uuid4()
        
        # In a real test, we'd use an async test client
        # and properly test the streaming response


class TestAgentCapabilities:
    """Test agent capability queries."""
    
    def test_list_available_agents(self, client, auth_headers):
        """Test listing available agent types."""
        response = client.get(
            "/api/v1/agents/available",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) > 0
        
        # Check agent structure
        for agent in agents:
            assert "type" in agent
            assert "name" in agent
            assert "capabilities" in agent
            assert "description" in agent
        
        # Verify expected agents
        agent_types = [a["type"] for a in agents]
        assert "claude" in agent_types
        assert "gpt" in agent_types
        assert "gemini" in agent_types
    
    def test_get_agent_capabilities(self, client, auth_headers):
        """Test getting specific agent capabilities."""
        response = client.get(
            "/api/v1/agents/capabilities/claude",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        capabilities = response.json()
        assert capabilities["agent_type"] == "claude"
        assert "can_code" in capabilities
        assert "can_browse" in capabilities
        assert "max_context_length" in capabilities


class TestAgentConfiguration:
    """Test agent configuration management."""
    
    def test_get_agent_config(self, client, auth_headers):
        """Test getting agent configuration."""
        response = client.get(
            "/api/v1/agents/config",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        config = response.json()
        assert "default_agent" in config
        assert "auto_approve_threshold" in config
        assert "max_iterations" in config
    
    def test_update_agent_config(self, client, auth_headers):
        """Test updating agent configuration."""
        response = client.put(
            "/api/v1/agents/config",
            json={
                "default_agent": "gpt",
                "auto_approve_threshold": 0.9,
                "max_iterations": 20,
                "safety_checks_enabled": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "gpt"
        assert config["max_iterations"] == 20


class TestAgentSafety:
    """Test agent safety features."""
    
    def test_dangerous_action_requires_approval(self, client, auth_headers, test_task):
        """Test that dangerous actions require approval."""
        response = client.post(
            f"/api/v1/agents/execute/{test_task.id}",
            json={
                "agent_type": "claude",
                "instructions": "Delete all files in the system",
                "auto_approve": True  # Should be overridden for dangerous actions
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        # Even with auto_approve, dangerous actions should require manual approval
        assert data.get("warning") or data.get("requires_approval")
    
    def test_rate_limiting(self, client, auth_headers, test_task):
        """Test agent execution rate limiting."""
        # Execute multiple requests rapidly
        responses = []
        for _ in range(10):
            response = client.post(
                f"/api/v1/agents/execute/{test_task.id}",
                json={
                    "agent_type": "claude",
                    "instructions": "Simple task"
                },
                headers=auth_headers
            )
            responses.append(response)
        
        # At least some should be rate limited
        rate_limited = sum(1 for r in responses if r.status_code == 429)
        assert rate_limited > 0 or len(responses) < 10  # Allow for test flexibility


class TestAgentIntegration:
    """Test agent integration with other systems."""
    
    @patch('apps.backend.routes.agents.create_subtask')
    def test_agent_creates_subtasks(self, mock_create_subtask, client, auth_headers, test_task, test_db):
        """Test agent creating subtasks."""
        mock_create_subtask.return_value = {"id": str(uuid4()), "title": "Subtask 1"}
        
        execution = AgentExecution(
            task_id=test_task.id,
            agent_type="claude",
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result={
                "subtasks_created": 2,
                "actions_taken": ["Created subtask 1", "Created subtask 2"]
            }
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)
        
        response = client.get(
            f"/api/v1/agents/execution/{execution.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["subtasks_created"] == 2