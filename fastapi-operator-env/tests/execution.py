"""
Task execution tests for BrainOps backend.

Tests the core task execution framework, including task registration,
parameter validation, execution flow, and error handling across all
task types in the system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from apps.backend.tasks import task_registry
from apps.backend.tasks.base import BaseTask
from apps.backend.tasks.autopublish_content import AutoPublishContentTask
from apps.backend.tasks.generate_roof_estimate import GenerateRoofEstimateTask
from apps.backend.db.models import TaskExecution, AgentExecution


class TestTaskRegistry:
    """Test task registration and discovery functionality."""
    
    def test_task_registration(self):
        """Verify all expected tasks are registered in the task registry."""
        # Core tasks that should always be registered
        expected_tasks = [
            "autopublish_content",
            "generate_roof_estimate",
            "generate_product_docs",
            "sync_database",
            "generate_weekly_report"
        ]
        
        for task_id in expected_tasks:
            assert task_id in task_registry, f"Task {task_id} not found in registry"
            assert issubclass(task_registry[task_id], BaseTask), f"Task {task_id} is not a BaseTask subclass"
    
    def test_task_metadata(self):
        """Verify task metadata is properly defined."""
        for task_id, task_class in task_registry.items():
            assert hasattr(task_class, 'TASK_ID'), f"Task {task_id} missing TASK_ID"
            assert hasattr(task_class, 'DESCRIPTION'), f"Task {task_id} missing DESCRIPTION"
            assert task_class.TASK_ID == task_id, f"Task ID mismatch for {task_id}"


@pytest.mark.asyncio
class TestAutoPublishContentTask:
    """Test the auto-publish content task functionality."""
    
    async def test_successful_content_generation(self):
        """Test successful content generation and publishing flow."""
        task = AutoPublishContentTask()
        
        # Mock the agent calls
        with patch.object(task.claude, 'generate_content') as mock_claude:
            with patch.object(task.gemini, 'optimize_for_seo') as mock_gemini:
                with patch.object(task.memory_store, 'add_knowledge') as mock_memory:
                    
                    # Configure mocks
                    mock_claude.return_value = {
                        "title": "Test Article",
                        "content": "This is test content.",
                        "meta_description": "Test description"
                    }
                    mock_gemini.return_value = {
                        "optimized_content": "This is SEO-optimized test content.",
                        "keywords": ["test", "content", "seo"]
                    }
                    
                    # Execute task
                    result = await task.run(
                        topic="Test Topic",
                        target_audience="developers",
                        content_type="blog_post",
                        publish_destination="draft"
                    )
                    
                    # Verify execution
                    assert result["status"] == "completed"
                    assert "content" in result
                    assert result["content"]["title"] == "Test Article"
                    assert "seo_optimized" in result["content"]
                    
                    # Verify agent calls
                    mock_claude.assert_called_once()
                    mock_gemini.assert_called_once()
                    mock_memory.assert_called()
    
    async def test_content_generation_with_research(self):
        """Test content generation with research agent integration."""
        task = AutoPublishContentTask()
        
        with patch.object(task.search_agent, 'search') as mock_search:
            with patch.object(task.claude, 'generate_content') as mock_claude:
                
                # Configure search mock
                mock_search.return_value = {
                    "results": [
                        {"title": "Research Item 1", "snippet": "Relevant research"},
                        {"title": "Research Item 2", "snippet": "More research"}
                    ]
                }
                
                mock_claude.return_value = {
                    "title": "Research-Based Article",
                    "content": "Content based on research",
                    "meta_description": "Research-driven content"
                }
                
                # Execute with research
                result = await task.run(
                    topic="AI Trends 2025",
                    include_research=True,
                    target_audience="tech professionals"
                )
                
                # Verify research was used
                assert result["status"] == "completed"
                mock_search.assert_called_once()
                
                # Verify research was passed to content generation
                claude_call_args = mock_claude.call_args[1]
                assert "research_context" in claude_call_args
    
    async def test_error_handling(self):
        """Test error handling during content generation."""
        task = AutoPublishContentTask()
        
        with patch.object(task.claude, 'generate_content') as mock_claude:
            # Simulate Claude API error
            mock_claude.side_effect = Exception("Claude API error")
            
            with pytest.raises(Exception) as exc_info:
                await task.run(topic="Test Topic")
            
            assert "Claude API error" in str(exc_info.value)


@pytest.mark.asyncio
class TestGenerateRoofEstimateTask:
    """Test the roof estimate generation task."""
    
    async def test_estimate_calculation(self):
        """Test basic roof estimate calculation."""
        task = GenerateRoofEstimateTask()
        
        # Test input parameters
        roof_data = {
            "building_type": "commercial",
            "roof_area_sqft": 10000,
            "roof_type": "tpo",
            "existing_condition": "fair",
            "location": "Denver, CO"
        }
        
        with patch.object(task.memory_store, 'search_knowledge') as mock_search:
            # Mock material pricing data
            mock_search.return_value = [{
                "content": "TPO pricing: $7.50-$9.00 per sqft installed",
                "metadata": {"source": "pricing_database"}
            }]
            
            result = await task.run(**roof_data)
            
            # Verify estimate structure
            assert result["status"] == "completed"
            assert "estimate" in result
            assert "total_cost" in result["estimate"]
            assert "breakdown" in result["estimate"]
            assert "timeline" in result["estimate"]
            
            # Verify calculations are reasonable
            estimate = result["estimate"]
            assert 75000 <= estimate["total_cost"] <= 100000  # $7.50-$10/sqft range
            assert estimate["roof_area_sqft"] == 10000
    
    async def test_complex_roof_features(self):
        """Test estimate with complex roof features."""
        task = GenerateRoofEstimateTask()
        
        complex_roof_data = {
            "building_type": "commercial",
            "roof_area_sqft": 15000,
            "roof_type": "tpo",
            "existing_condition": "poor",
            "location": "Denver, CO",
            "special_features": {
                "hvac_units": 5,
                "skylights": 3,
                "drainage_issues": True,
                "insulation_upgrade": True
            }
        }
        
        result = await task.run(**complex_roof_data)
        
        # Verify complex features are accounted for
        assert result["status"] == "completed"
        breakdown = result["estimate"]["breakdown"]
        
        # Should have line items for special features
        assert any("HVAC" in item["description"] for item in breakdown)
        assert any("skylight" in item["description"].lower() for item in breakdown)
        assert any("drainage" in item["description"].lower() for item in breakdown)
        assert any("insulation" in item["description"].lower() for item in breakdown)
    
    async def test_regional_adjustments(self):
        """Test regional cost adjustments."""
        task = GenerateRoofEstimateTask()
        
        # Test different locations
        locations = [
            ("Denver, CO", 1.0),      # Baseline
            ("San Francisco, CA", 1.3),  # High cost area
            ("Kansas City, MO", 0.85)    # Lower cost area
        ]
        
        base_roof_data = {
            "building_type": "commercial",
            "roof_area_sqft": 10000,
            "roof_type": "tpo",
            "existing_condition": "good"
        }
        
        estimates = {}
        
        for location, _ in locations:
            roof_data = {**base_roof_data, "location": location}
            result = await task.run(**roof_data)
            estimates[location] = result["estimate"]["total_cost"]
        
        # Verify regional variations
        assert estimates["San Francisco, CA"] > estimates["Denver, CO"]
        assert estimates["Kansas City, MO"] < estimates["Denver, CO"]


@pytest.mark.asyncio
class TestTaskExecution:
    """Test general task execution framework functionality."""
    
    async def test_task_execution_logging(self, db_session):
        """Test that task executions are properly logged to database."""
        task = AutoPublishContentTask()
        
        # Execute task
        result = await task.run(
            topic="Test Topic",
            target_audience="test audience"
        )
        
        # Verify execution was logged
        execution = db_session.query(TaskExecution).filter_by(
            task_id="autopublish_content"
        ).first()
        
        assert execution is not None
        assert execution.status == "completed"
        assert execution.parameters["topic"] == "Test Topic"
        assert execution.result is not None
    
    async def test_agent_execution_tracking(self, db_session):
        """Test that individual agent calls are tracked."""
        task = AutoPublishContentTask()
        
        with patch.object(task.claude, 'generate_content') as mock_claude:
            mock_claude.return_value = {"content": "test"}
            
            # Execute task
            await task.run(topic="Test")
            
            # Verify agent execution was logged
            agent_execution = db_session.query(AgentExecution).filter_by(
                agent_type="claude"
            ).first()
            
            assert agent_execution is not None
            assert agent_execution.status == "completed"
            assert agent_execution.model_name is not None
    
    async def test_task_error_logging(self, db_session):
        """Test that task errors are properly logged."""
        task = GenerateRoofEstimateTask()
        
        # Execute with invalid parameters
        with pytest.raises(ValueError):
            await task.run(roof_area_sqft=-1000)  # Invalid area
        
        # Verify error was logged
        execution = db_session.query(TaskExecution).filter_by(
            task_id="generate_roof_estimate",
            status="failed"
        ).first()
        
        assert execution is not None
        assert execution.error_message is not None
        assert "Invalid roof area" in execution.error_message


@pytest.fixture
async def db_session():
    """Provide a test database session."""
    # This would typically set up a test database
    # For now, return a mock
    from unittest.mock import MagicMock
    session = MagicMock()
    yield session
    # Cleanup would happen here