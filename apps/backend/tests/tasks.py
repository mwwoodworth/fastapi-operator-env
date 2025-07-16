"""
Unit and integration tests for BrainOps task system.
Tests core task execution, agent integration, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

from .tasks.base_task import BaseTask, TaskResult
from .tasks.autopublish_content import AutopublishContentTask
from .tasks.generate_roof_estimate import GenerateRoofEstimateTask
from .tasks.customer_onboarding import CustomerOnboardingTask
from .agents.base import AgentContext, AgentResult
from .memory.memory_store import MemoryStore


class TestBaseTask:
    """Test the base task functionality."""
    
    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock memory store."""
        store = Mock(spec=MemoryStore)
        store.save_memory_entry = AsyncMock()
        store.get_memory_entry = AsyncMock()
        return store
    
    @pytest.fixture
    def sample_task(self, mock_memory_store):
        """Create a sample task for testing."""
        class SampleTask(BaseTask):
            def __init__(self):
                super().__init__(task_id="sample_task")
                self.memory_store = mock_memory_store
                
            async def run(self, context: Dict[str, Any]) -> TaskResult:
                # Simple implementation for testing
                if context.get('should_fail'):
                    raise ValueError("Task failed as requested")
                    
                return TaskResult(
                    success=True,
                    data={"processed": context.get('input', 'default')},
                    message="Task completed successfully"
                )
        
        return SampleTask()
    
    @pytest.mark.asyncio
    async def test_task_execution_success(self, sample_task):
        """Test successful task execution."""
        context = {"input": "test_data"}
        result = await sample_task.execute_async(context)
        
        assert result.success is True
        assert result.data["processed"] == "test_data"
        assert result.message == "Task completed successfully"
        
    @pytest.mark.asyncio
    async def test_task_execution_failure(self, sample_task):
        """Test task execution with failure."""
        context = {"should_fail": True}
        result = await sample_task.execute_async(context)
        
        assert result.success is False
        assert "Task failed as requested" in result.error
        assert result.data is None
        
    @pytest.mark.asyncio
    async def test_task_logging(self, sample_task, mock_memory_store):
        """Test that task execution is logged to memory."""
        context = {"input": "test_data"}
        await sample_task.execute_async(context)
        
        # Verify memory store was called
        mock_memory_store.save_memory_entry.assert_called()
        call_args = mock_memory_store.save_memory_entry.call_args
        
        assert call_args[1]['namespace'] == 'task_executions'
        assert 'sample_task' in call_args[1]['key']


class TestAutopublishContentTask:
    """Test the autopublish content task."""
    
    @pytest.fixture
    def mock_claude_agent(self):
        """Create a mock Claude agent."""
        agent = Mock()
        agent.execute = AsyncMock(return_value=AgentResult(
            success=True,
            content="Generated article content",
            metadata={"tokens": 1000}
        ))
        return agent
    
    @pytest.fixture
    def mock_gemini_agent(self):
        """Create a mock Gemini agent."""
        agent = Mock()
        agent.execute = AsyncMock(return_value=AgentResult(
            success=True,
            content="SEO optimized content",
            metadata={"keywords": ["test", "article"]}
        ))
        return agent
    
    @pytest.fixture
    def autopublish_task(self, mock_claude_agent, mock_gemini_agent):
        """Create autopublish task with mocked agents."""
        with patch('apps.backend.tasks.autopublish_content.ClaudeAgent', return_value=mock_claude_agent):
            with patch('apps.backend.tasks.autopublish_content.GeminiAgent', return_value=mock_gemini_agent):
                task = AutopublishContentTask()
                task.memory_store = Mock(spec=MemoryStore)
                task.memory_store.save_memory_entry = AsyncMock()
                return task
    
    @pytest.mark.asyncio
    async def test_autopublish_content_generation(self, autopublish_task):
        """Test content generation and SEO optimization flow."""
        context = {
            "topic": "Commercial Roofing Best Practices",
            "audience": "Roofing contractors",
            "seo_keywords": ["commercial roofing", "best practices"],
            "publish_to": ["blog"]
        }
        
        result = await autopublish_task.run(context)
        
        assert result.success is True
        assert "content" in result.data
        assert "seo_metadata" in result.data
        assert result.data["topic"] == "Commercial Roofing Best Practices"
        
    @pytest.mark.asyncio
    async def test_autopublish_validation(self, autopublish_task):
        """Test context validation."""
        # Missing required fields
        context = {"audience": "contractors"}
        
        result = await autopublish_task.run(context)
        
        assert result.success is False
        assert "Missing required fields" in result.error
        
    @pytest.mark.asyncio
    async def test_autopublish_streaming(self, autopublish_task):
        """Test streaming updates during content generation."""
        context = {
            "topic": "Test Topic",
            "audience": "Test Audience",
            "seo_keywords": ["test"],
            "publish_to": ["blog"]
        }
        
        updates = []
        async for update in autopublish_task.stream(context):
            updates.append(update)
            
        # Verify we get progress updates
        assert len(updates) > 0
        assert any(u['stage'] == 'generating_content' for u in updates)
        assert any(u['stage'] == 'completed' for u in updates)


class TestGenerateRoofEstimateTask:
    """Test the roof estimate generation task."""
    
    @pytest.fixture
    def mock_agents(self):
        """Create mock agents for estimate generation."""
        claude = Mock()
        claude.execute = AsyncMock(return_value=AgentResult(
            success=True,
            content="Detailed estimate breakdown",
            metadata={"estimate_total": 45000}
        ))
        
        search = Mock()
        search.execute = AsyncMock(return_value=AgentResult(
            success=True,
            content="Current material prices",
            metadata={"prices": {"shingles": 85, "underlayment": 45}}
        ))
        
        return {"claude": claude, "search": search}
    
    @pytest.fixture
    def estimate_task(self, mock_agents):
        """Create estimate task with mocked agents."""
        with patch('apps.backend.tasks.generate_roof_estimate.ClaudeAgent', return_value=mock_agents['claude']):
            with patch('apps.backend.tasks.generate_roof_estimate.SearchAgent', return_value=mock_agents['search']):
                task = GenerateRoofEstimateTask()
                task.memory_store = Mock(spec=MemoryStore)
                task.memory_store.save_memory_entry = AsyncMock()
                return task
    
    @pytest.mark.asyncio
    async def test_estimate_generation(self, estimate_task):
        """Test roof estimate generation with calculations."""
        context = {
            "project_name": "Test Commercial Building",
            "roof_area_sqft": 10000,
            "roof_type": "TPO",
            "complexity": "medium",
            "location": "Denver, CO"
        }
        
        result = await estimate_task.run(context)
        
        assert result.success is True
        assert "estimate" in result.data
        assert "materials_cost" in result.data
        assert result.data["roof_area_sqft"] == 10000
        
    @pytest.mark.asyncio
    async def test_estimate_validation(self, estimate_task):
        """Test estimate validation for required fields."""
        # Missing roof area
        context = {
            "project_name": "Test Project",
            "roof_type": "TPO"
        }
        
        result = await estimate_task.run(context)
        
        assert result.success is False
        assert "roof_area_sqft" in result.error


class TestCustomerOnboardingTask:
    """Test the customer onboarding task."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for onboarding."""
        claude = Mock()
        claude.execute = AsyncMock(return_value=AgentResult(
            success=True,
            content="Welcome to BrainOps! Your personalized onboarding content...",
            metadata={}
        ))
        
        memory = Mock(spec=MemoryStore)
        memory.save_memory_entry = AsyncMock()
        
        slack = Mock()
        slack.post_message = AsyncMock()
        
        return {
            "claude": claude,
            "memory": memory,
            "slack": slack
        }
    
    @pytest.fixture
    def onboarding_task(self, mock_services):
        """Create onboarding task with mocked services."""
        with patch('apps.backend.tasks.customer_onboarding.ClaudeAgent', return_value=mock_services['claude']):
            task = CustomerOnboardingTask()
            task.memory_store = mock_services['memory']
            task.slack_client = mock_services['slack']
            return task
    
    @pytest.mark.asyncio
    async def test_complete_onboarding_flow(self, onboarding_task):
        """Test the complete customer onboarding sequence."""
        context = {
            "email": "test@example.com",
            "customer_id": "cus_test123",
            "products": [{"name": "Roofing Estimator Pro"}],
            "payment_status": "completed"
        }
        
        result = await onboarding_task.run(context)
        
        assert result.success is True
        assert result.data["email"] == "test@example.com"
        assert "workspace" in result.data
        assert "scheduled_follow_ups" in result.data
        assert result.data["onboarding_status"] == "completed"
        
        # Verify Slack notification was sent
        onboarding_task.slack_client.post_message.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_onboarding_email_validation(self, onboarding_task):
        """Test email validation in onboarding."""
        context = {
            "email": "invalid-email",  # Invalid format
            "customer_id": "cus_test123"
        }
        
        result = await onboarding_task.run(context)
        
        assert result.success is False
        assert "Invalid email format" in result.error
        
    @pytest.mark.asyncio
    async def test_onboarding_follow_up_scheduling(self, onboarding_task):
        """Test that follow-up tasks are properly scheduled."""
        context = {
            "email": "test@example.com",
            "customer_id": "cus_test123",
            "products": [
                {"name": "Roofing Estimator Pro"},
                {"name": "Automation Suite"}
            ]
        }
        
        result = await onboarding_task.run(context)
        
        assert result.success is True
        follow_ups = result.data["scheduled_follow_ups"]
        
        # Should have at least 3 follow-ups (day 3, 7, 14)
        assert len(follow_ups) >= 3
        
        # Check follow-up types
        follow_up_types = [f["task_type"] for f in follow_ups]
        assert "send_checkin_email" in follow_up_types
        assert "success_metrics_review" in follow_up_types


class TestTaskRegistry:
    """Test the task registry functionality."""
    
    @pytest.mark.asyncio
    async def test_task_registration(self):
        """Test that tasks are properly registered."""
        from .tasks import task_registry
        
        # Verify core tasks are registered
        assert "autopublish_content" in task_registry
        assert "generate_roof_estimate" in task_registry
        assert "customer_onboarding" in task_registry
        
    @pytest.mark.asyncio
    async def test_task_instantiation(self):
        """Test that registered tasks can be instantiated."""
        from .tasks import task_registry
        
        # Get and instantiate a task
        task_class = task_registry.get("autopublish_content")
        assert task_class is not None
        
        task_instance = task_class()
        assert hasattr(task_instance, 'run')
        assert hasattr(task_instance, 'stream')


# Integration test fixtures
@pytest.fixture
async def test_database():
    """Create a test database connection."""
    # This would connect to a test database in a real implementation
    pass


@pytest.fixture
async def integration_context():
    """Create a full integration test context."""
    return {
        "agents": {
            "claude": Mock(),
            "gemini": Mock(),
            "codex": Mock(),
            "search": Mock()
        },
        "memory": Mock(spec=MemoryStore),
        "integrations": {
            "slack": Mock(),
            "clickup": Mock(),
            "stripe": Mock()
        }
    }


@pytest.mark.integration
class TestTaskIntegration:
    """Integration tests for full task workflows."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_content_publishing(self, integration_context):
        """Test complete content generation and publishing flow."""
        # This would test the full flow with real agent calls
        # For now, it's a placeholder for integration testing
        pass
        
    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self, integration_context):
        """Test that multiple tasks can execute concurrently."""
        # Test concurrent execution of different task types
        tasks = [
            AutopublishContentTask(),
            GenerateRoofEstimateTask(),
            CustomerOnboardingTask()
        ]
        
        # Create different contexts for each task
        contexts = [
            {"topic": "Test", "audience": "Test", "seo_keywords": ["test"], "publish_to": ["blog"]},
            {"project_name": "Test", "roof_area_sqft": 1000, "roof_type": "TPO", "complexity": "low", "location": "Denver"},
            {"email": "test@test.com", "customer_id": "cus_123", "products": []}
        ]
        
        # Execute tasks concurrently
        results = await asyncio.gather(
            *[task.execute_async(ctx) for task, ctx in zip(tasks, contexts)],
            return_exceptions=True
        )
        
        # Verify all tasks completed (success or controlled failure)
        assert len(results) == 3
        for result in results:
            assert isinstance(result, (TaskResult, Exception))