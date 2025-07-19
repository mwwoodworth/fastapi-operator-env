"""
Comprehensive tests for LangGraph multi-agent orchestration.
Tests workflow creation, execution, persistence, and recovery.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import json

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from ..main import app
from ..agents.langgraph_orchestrator import (
    LangGraphOrchestrator, WorkflowState, WorkflowStatus,
    AgentRole, AgentNode, execute_analysis_workflow
)
from ..agents.claude_agent import ClaudeAgent
from ..db.business_models import User


client = TestClient(app)


class TestLangGraphOrchestrator:
    """Test the core orchestrator functionality."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator instance."""
        return LangGraphOrchestrator()
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for testing."""
        agent = MagicMock(spec=ClaudeAgent)
        agent.agenerate = AsyncMock()
        agent.agenerate.return_value = MagicMock(
            generations=[[MagicMock(text="Test response")]],
            llm_output={"model": "test"}
        )
        return agent
    
    @pytest.fixture
    def test_workflow_definition(self):
        """Create test workflow definition."""
        return {
            "nodes": {
                "start": {
                    "agent_type": "claude",
                    "role": "analyzer",
                    "agent_config": {"model": "claude-3-sonnet-20240229"}
                },
                "process": {
                    "agent_type": "claude",
                    "role": "executor",
                    "agent_config": {"model": "claude-3-haiku-20240307"}
                },
                "review": {
                    "agent_type": "claude",
                    "role": "reviewer",
                    "agent_config": {"model": "claude-3-opus-20240229"}
                }
            },
            "edges": [
                {"type": "direct", "from": "start", "to": "process"},
                {"type": "direct", "from": "process", "to": "review"}
            ],
            "entry_point": "start"
        }
    
    async def test_workflow_creation(self, orchestrator, test_workflow_definition):
        """Test creating a workflow from definition."""
        workflow_id = "test_workflow_1"
        
        # Create workflow
        workflow = orchestrator.create_workflow(workflow_id, test_workflow_definition)
        
        assert workflow is not None
        assert workflow_id in orchestrator.workflows
    
    async def test_agent_node_execution(self, mock_agent):
        """Test agent node execution with retry logic."""
        node = AgentNode(
            agent=mock_agent,
            role=AgentRole.ANALYZER,
            max_retries=3,
            timeout=60
        )
        
        state = WorkflowState()
        input_data = {"prompt": "Test prompt"}
        
        # Test successful execution
        result = await node.execute(state, input_data)
        
        assert result["content"] == "Test response"
        assert result["agent_role"] == "analyzer"
        assert "timestamp" in result
        mock_agent.agenerate.assert_called_once()
    
    async def test_agent_node_retry_on_failure(self, mock_agent):
        """Test agent node retry logic on failure."""
        # Make first two calls fail
        mock_agent.agenerate.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            MagicMock(
                generations=[[MagicMock(text="Success after retries")]],
                llm_output={}
            )
        ]
        
        node = AgentNode(
            agent=mock_agent,
            role=AgentRole.EXECUTOR,
            max_retries=3
        )
        
        state = WorkflowState()
        result = await node.execute(state, {"prompt": "Test"})
        
        assert result["content"] == "Success after retries"
        assert mock_agent.agenerate.call_count == 3
    
    async def test_agent_node_timeout(self, mock_agent):
        """Test agent node timeout handling."""
        # Make agent take too long
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(2)
            return MagicMock()
        
        mock_agent.agenerate = slow_generate
        
        node = AgentNode(
            agent=mock_agent,
            role=AgentRole.PLANNER,
            timeout=1  # 1 second timeout
        )
        
        state = WorkflowState()
        
        with pytest.raises(Exception) as exc_info:
            await node.execute(state, {"prompt": "Test"})
        
        assert "timed out" in str(exc_info.value)
        assert len(state.errors) > 0
    
    async def test_workflow_execution(self, orchestrator, test_workflow_definition):
        """Test full workflow execution."""
        workflow_id = "test_workflow_exec"
        
        # Mock agent responses
        with patch('apps.backend.agents.langgraph_orchestrator.ClaudeAgent') as MockClaude:
            mock_instance = MagicMock()
            mock_instance.agenerate = AsyncMock()
            mock_instance.agenerate.return_value = MagicMock(
                generations=[[MagicMock(text="Agent response")]],
                llm_output={}
            )
            MockClaude.return_value = mock_instance
            
            # Create and execute workflow
            orchestrator.create_workflow(workflow_id, test_workflow_definition)
            
            state = await orchestrator.execute_workflow(
                workflow_id,
                {"prompt": "Test workflow execution"},
                user_id="test_user"
            )
            
            assert state.status == WorkflowStatus.COMPLETED
            assert len(state.messages) > 0
            assert "analyzer" in state.results
            assert "executor" in state.results
            assert "reviewer" in state.results
    
    async def test_workflow_persistence(self, orchestrator):
        """Test workflow state persistence."""
        state = WorkflowState(
            workflow_id="test_persist",
            status=WorkflowStatus.COMPLETED,
            results={"test": "data"}
        )
        
        # Mock memory store
        orchestrator.memory_store.add_memory = AsyncMock()
        
        await orchestrator._persist_workflow_state(state)
        
        orchestrator.memory_store.add_memory.assert_called_once()
        call_args = orchestrator.memory_store.add_memory.call_args
        assert call_args[1]["metadata"]["workflow_id"] == "test_persist"
    
    async def test_workflow_checkpoint_and_resume(self, orchestrator):
        """Test workflow checkpointing and resume functionality."""
        workflow_id = "test_checkpoint"
        
        # Create checkpoint
        state = WorkflowState(
            workflow_id=workflow_id,
            current_step="process",
            results={"start": {"content": "Initial result"}}
        )
        
        orchestrator.memory_store.add_memory = AsyncMock()
        orchestrator.memory_store.search_memories = AsyncMock()
        orchestrator.memory_store.search_memories.return_value = [{
            "content": state.json(),
            "metadata": {"checkpoint_id": "test_checkpoint_1"}
        }]
        
        await orchestrator._checkpoint_state(state)
        
        # Load checkpoint
        loaded_state = await orchestrator._load_workflow_state(workflow_id)
        
        assert loaded_state is not None
        assert loaded_state.workflow_id == workflow_id
        assert loaded_state.current_step == "process"
    
    async def test_workflow_cancellation(self, orchestrator):
        """Test workflow cancellation."""
        workflow_id = "test_cancel"
        
        # Add active workflow
        state = WorkflowState(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING
        )
        orchestrator.active_executions[workflow_id] = state
        orchestrator.memory_store.add_memory = AsyncMock()
        
        # Cancel workflow
        success = await orchestrator.cancel_workflow(workflow_id)
        
        assert success is True
        assert workflow_id not in orchestrator.active_executions
        assert state.status == WorkflowStatus.CANCELLED
    
    async def test_parallel_execution(self, orchestrator):
        """Test parallel agent execution in workflow."""
        definition = {
            "nodes": {
                "coordinator": {
                    "agent_type": "claude",
                    "role": "coordinator"
                },
                "worker1": {
                    "agent_type": "claude",
                    "role": "specialist"
                },
                "worker2": {
                    "agent_type": "claude",
                    "role": "specialist"
                }
            },
            "edges": [
                {"type": "direct", "from": "coordinator", "to": "worker1"},
                {"type": "direct", "from": "coordinator", "to": "worker2"}
            ],
            "entry_point": "coordinator"
        }
        
        with patch('apps.backend.agents.langgraph_orchestrator.ClaudeAgent'):
            workflow_id = orchestrator.create_parallel_research_workflow()
            assert workflow_id.startswith("research_")
    
    async def test_conditional_routing(self, orchestrator):
        """Test conditional routing in workflow."""
        definition = {
            "nodes": {
                "check": {
                    "agent_type": "claude",
                    "role": "analyzer"
                },
                "path_a": {
                    "agent_type": "claude",
                    "role": "executor"
                },
                "path_b": {
                    "agent_type": "claude",
                    "role": "executor"
                }
            },
            "edges": [
                {
                    "type": "conditional",
                    "from": "check",
                    "condition": "needs_revision",
                    "routes": {
                        "true": "path_a",
                        "false": "path_b"
                    }
                }
            ],
            "entry_point": "check"
        }
        
        # Test condition function
        condition_func = orchestrator._create_condition_function("needs_revision")
        
        # Test true condition
        state_true = {"reviewer": {"content": "Revision needed for accuracy"}}
        assert condition_func({"state": {}, **state_true}) == "true"
        
        # Test false condition
        state_false = {"reviewer": {"content": "Looks good!"}}
        assert condition_func({"state": {}, **state_false}) == "false"


class TestLangGraphAPI:
    """Test LangGraph API endpoints."""
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Get auth headers for test user."""
        return {"Authorization": f"Bearer {test_user.token}"}
    
    @pytest.fixture
    def admin_headers(self, admin_user):
        """Get auth headers for admin user."""
        return {"Authorization": f"Bearer {admin_user.token}"}
    
    def test_create_workflow(self, admin_headers):
        """Test workflow creation endpoint."""
        workflow_config = {
            "id": "test_api_workflow",
            "nodes": {
                "analyze": {
                    "agent_type": "claude",
                    "role": "analyzer"
                }
            },
            "edges": [],
            "entry_point": "analyze"
        }
        
        response = client.post(
            "/api/v1/langgraph/workflows",
            json=workflow_config,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "test_api_workflow"
        assert data["status"] == "created"
    
    def test_execute_workflow_async(self, admin_headers):
        """Test async workflow execution."""
        with patch('apps.backend.routes.langgraph.orchestrator.execute_workflow') as mock_execute:
            mock_execute.return_value = None
            
            response = client.post(
                "/api/v1/langgraph/workflows/test_workflow/execute",
                json={"prompt": "Test execution"},
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"
    
    def test_execute_workflow_sync(self, admin_headers):
        """Test synchronous workflow execution."""
        mock_state = WorkflowState(
            workflow_id="test_sync",
            status=WorkflowStatus.COMPLETED,
            results={"test": "result"}
        )
        
        with patch('apps.backend.routes.langgraph.orchestrator.execute_workflow') as mock_execute:
            mock_execute.return_value = mock_state
            
            response = client.post(
                "/api/v1/langgraph/workflows/test_sync/execute-sync",
                json={"prompt": "Test sync execution"},
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["results"]["test"] == "result"
    
    def test_get_workflow_status(self, auth_headers):
        """Test getting workflow status."""
        # Test active workflow
        with patch('apps.backend.routes.langgraph.orchestrator.get_active_workflows') as mock_active:
            mock_active.return_value = {
                "test_status": WorkflowState(
                    workflow_id="test_status",
                    status=WorkflowStatus.RUNNING,
                    current_step="process"
                )
            }
            
            response = client.get(
                "/api/v1/langgraph/workflows/test_status/status",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["current_step"] == "process"
    
    def test_cancel_workflow(self, admin_headers):
        """Test workflow cancellation."""
        with patch('apps.backend.routes.langgraph.orchestrator.cancel_workflow') as mock_cancel:
            mock_cancel.return_value = True
            
            response = client.post(
                "/api/v1/langgraph/workflows/test_cancel/cancel",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cancelled"
    
    def test_analysis_workflow(self, admin_headers):
        """Test predefined analysis workflow."""
        mock_state = WorkflowState(
            workflow_id="analysis_test",
            status=WorkflowStatus.COMPLETED,
            results={
                "reviewer": {"content": "Analysis complete: Test passed"}
            }
        )
        
        with patch('apps.backend.routes.langgraph.execute_analysis_workflow') as mock_analysis:
            mock_analysis.return_value = mock_state
            
            response = client.post(
                "/api/v1/langgraph/workflows/analysis",
                json={
                    "prompt": "Analyze this test",
                    "context": {"test": True}
                },
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "Analysis complete" in data["analysis"]
    
    def test_research_workflow(self, admin_headers):
        """Test parallel research workflow."""
        mock_state = WorkflowState(
            workflow_id="research_test",
            status=WorkflowStatus.COMPLETED,
            results={
                "reviewer": {"content": "Research synthesis: All topics covered"}
            }
        )
        
        with patch('apps.backend.routes.langgraph.execute_parallel_research') as mock_research:
            mock_research.return_value = mock_state
            
            response = client.post(
                "/api/v1/langgraph/workflows/research",
                json={
                    "topics": ["AI", "Blockchain", "Quantum"],
                    "context": {}
                },
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "Research synthesis" in data["synthesis"]
    
    def test_workflow_history(self, auth_headers):
        """Test getting workflow history."""
        mock_history = [
            {
                "checkpoint_id": "cp1",
                "step": "start",
                "status": "running",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        with patch('apps.backend.routes.langgraph.orchestrator.get_workflow_history') as mock_hist:
            mock_hist.return_value = mock_history
            
            response = client.get(
                "/api/v1/langgraph/workflows/test_history/history",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["history"]) == 1
            assert data["history"][0]["checkpoint_id"] == "cp1"
    
    def test_list_workflows_admin(self, admin_headers):
        """Test listing all workflows (admin only)."""
        with patch('apps.backend.routes.langgraph.orchestrator.get_active_workflows') as mock_active:
            mock_active.return_value = {
                "wf1": WorkflowState(status=WorkflowStatus.RUNNING),
                "wf2": WorkflowState(status=WorkflowStatus.COMPLETED)
            }
            
            response = client.get(
                "/api/v1/langgraph/workflows",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["active"] == 1
    
    async def test_workflow_streaming(self, auth_headers):
        """Test workflow execution streaming."""
        # This would need a more complex test setup for SSE
        pass
    
    async def test_workflow_websocket(self):
        """Test WebSocket connection for workflow updates."""
        # This would need WebSocket test client
        pass


class TestWorkflowIntegration:
    """Integration tests for complete workflows."""
    
    async def test_end_to_end_analysis_workflow(self):
        """Test complete analysis workflow execution."""
        # This would be an integration test with real agents
        pass
    
    async def test_error_recovery_workflow(self):
        """Test workflow error recovery and retry."""
        orchestrator = LangGraphOrchestrator()
        
        # Create workflow with failing node
        definition = {
            "nodes": {
                "fail_node": {
                    "agent_type": "claude",
                    "role": "analyzer",
                    "max_retries": 2
                }
            },
            "edges": [],
            "entry_point": "fail_node"
        }
        
        with patch('apps.backend.agents.langgraph_orchestrator.ClaudeAgent') as MockClaude:
            # Make agent fail
            mock_instance = MagicMock()
            mock_instance.agenerate = AsyncMock(side_effect=Exception("Agent error"))
            MockClaude.return_value = mock_instance
            
            workflow_id = "test_error_recovery"
            orchestrator.create_workflow(workflow_id, definition)
            
            state = await orchestrator.execute_workflow(
                workflow_id,
                {"prompt": "Test error"},
                timeout=10
            )
            
            assert state.status == WorkflowStatus.FAILED
            assert len(state.errors) > 0
            assert "Agent error" in state.errors[0]["error"]
    
    async def test_complex_multi_agent_workflow(self):
        """Test complex workflow with multiple agents and conditions."""
        # This would test a real-world scenario
        pass


def test_workflow_performance():
    """Test workflow performance and scalability."""
    # Measure execution time, memory usage, etc.
    pass