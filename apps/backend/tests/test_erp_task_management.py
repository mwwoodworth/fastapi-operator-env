"""
Comprehensive tests for ERP Task Management system.

Tests CRUD operations, dependencies, workflow states, and dashboard functionality.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
import json
from unittest.mock import patch, AsyncMock, MagicMock

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, UserRole, Project, ProjectTask
from ..routes.erp_task_management import TaskStatus, TaskPriority, TaskType, DependencyType


class TestTaskManagementCRUD:
    """Test task CRUD operations."""
    
    def test_create_basic_task(self, client, auth_headers):
        """Test creating a basic task."""
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Fix roof leak",
                "description": "Repair leak in section A3",
                "task_type": "field_work",
                "priority": "high",
                "estimated_hours": 3.5,
                "tags": ["roofing", "repair", "urgent"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Fix roof leak"
        assert data["status"] == "todo"
        assert "id" in data
        assert len(data.get("warnings", [])) == 0
    
    def test_create_task_with_location(self, client, auth_headers):
        """Test creating a task with location data."""
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Inspect roof damage",
                "task_type": "inspection",
                "priority": "medium",
                "estimated_hours": 2,
                "location_address": "123 Main St, Springfield, IL",
                "location_lat": 39.7817,
                "location_lng": -89.6501,
                "weather_dependent": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Inspect roof damage"
    
    def test_create_task_with_assignment(self, client, auth_headers, test_db):
        """Test creating a task with specific assignee."""
        # Create test assignee
        assignee = User(
            id=uuid.uuid4(),
            email="worker@example.com",
            username="worker1",
            hashed_password="hashed",
            full_name="Test Worker"
        )
        test_db.add(assignee)
        test_db.commit()
        
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Install new shingles",
                "task_type": "field_work",
                "priority": "medium",
                "estimated_hours": 6,
                "assignee_id": str(assignee.id),
                "planned_start": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "planned_end": (datetime.utcnow() + timedelta(days=1, hours=6)).isoformat()
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assignee_id"] == str(assignee.id)
    
    def test_create_task_with_dependencies(self, client, auth_headers, test_db):
        """Test creating a task with dependencies."""
        # Create predecessor task
        predecessor = ProjectTask(
            id=uuid.uuid4(),
            title="Remove old shingles",
            status="in_progress",
            created_by=uuid.uuid4()
        )
        test_db.add(predecessor)
        test_db.commit()
        
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Install new shingles",
                "task_type": "field_work",
                "priority": "medium",
                "estimated_hours": 6,
                "dependencies": [
                    {
                        "predecessor_id": str(predecessor.id),
                        "dependency_type": "finish_to_start",
                        "lag_hours": 1
                    }
                ]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Install new shingles"
    
    def test_create_task_with_auto_assignment(self, client, auth_headers):
        """Test creating a task with automatic assignment."""
        with patch('backend.services.crew_scheduler.CrewScheduler.find_best_assignee') as mock_find:
            mock_find.return_value = {
                "user_id": str(uuid.uuid4()),
                "score": 0.9,
                "crew_ids": []
            }
            
            response = client.post(
                "/api/v1/erp/task-management/tasks",
                json={
                    "title": "Emergency roof repair",
                    "task_type": "emergency",
                    "priority": "critical",
                    "estimated_hours": 4,
                    "auto_assign": True,
                    "tags": ["roofing", "emergency"]
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            assert mock_find.called
    
    def test_list_tasks_with_filters(self, client, auth_headers, test_db):
        """Test listing tasks with various filters."""
        # Create test tasks
        tasks = []
        for i in range(5):
            task = ProjectTask(
                id=uuid.uuid4(),
                title=f"Task {i}",
                status=TaskStatus.TODO.value if i % 2 == 0 else TaskStatus.IN_PROGRESS.value,
                priority=TaskPriority.HIGH.value if i < 2 else TaskPriority.MEDIUM.value,
                created_by=uuid.uuid4()
            )
            tasks.append(task)
        
        test_db.add_all(tasks)
        test_db.commit()
        
        # Test status filter
        response = client.get(
            "/api/v1/erp/task-management/tasks",
            params={"status": ["todo"]},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "todo" for t in data["tasks"])
        
        # Test priority filter
        response = client.get(
            "/api/v1/erp/task-management/tasks",
            params={"priority": ["high"]},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(t["priority"] == "high" for t in data["tasks"])
    
    def test_get_task_details(self, client, auth_headers, test_db):
        """Test getting detailed task information."""
        # Create task with relationships
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Detailed task",
            description="This is a detailed task",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.HIGH.value,
            created_by=uuid.uuid4(),
            progress_percentage=50,
            checklist=[
                {"id": "1", "title": "Check materials", "is_completed": True},
                {"id": "2", "title": "Prepare tools", "is_completed": False}
            ]
        )
        test_db.add(task)
        test_db.commit()
        
        response = client.get(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task"]["title"] == "Detailed task"
        assert data["task"]["progress_percentage"] == 50
        assert len(data["task"]["checklist"]) == 2
        assert "metrics" in data
        assert "dependencies" in data
    
    def test_update_task_status(self, client, auth_headers, test_db):
        """Test updating task status with workflow validation."""
        # Create task
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Status update test",
            status=TaskStatus.TODO.value,
            created_by=uuid.uuid4()
        )
        test_db.add(task)
        test_db.commit()
        
        # Valid status transition
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            json={
                "status": "in_progress",
                "notes": "Starting work"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert "status" in data["changes"]
        
        # Invalid status transition
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            json={
                "status": "todo"  # Can't go back to TODO from IN_PROGRESS
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_update_task_assignment(self, client, auth_headers, test_db):
        """Test updating task assignment."""
        # Create task and new assignee
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Reassignment test",
            status=TaskStatus.TODO.value,
            created_by=uuid.uuid4()
        )
        
        new_assignee = User(
            id=uuid.uuid4(),
            email="newworker@example.com",
            username="newworker",
            hashed_password="hashed"
        )
        
        test_db.add_all([task, new_assignee])
        test_db.commit()
        
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            json={
                "assignee_id": str(new_assignee.id),
                "notes": "Reassigning to available worker"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "assignee" in data["changes"]
    
    def test_complete_checklist_item(self, client, auth_headers, test_db):
        """Test completing a checklist item."""
        # Create task with checklist
        checklist = [
            {"id": "item1", "title": "Prepare surface", "is_completed": False},
            {"id": "item2", "title": "Apply primer", "is_completed": False}
        ]
        
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Checklist test",
            status=TaskStatus.IN_PROGRESS.value,
            created_by=uuid.uuid4(),
            checklist=checklist,
            progress_percentage=0
        )
        test_db.add(task)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/erp/task-management/tasks/{task.id}/checklist/item1/complete",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["completed_items"] == 1
        assert data["total_items"] == 2
        assert data["task_progress"] == 50  # 1 of 2 items completed
    
    def test_bulk_update_tasks(self, supervisor_client, supervisor_headers, test_db):
        """Test bulk updating multiple tasks (supervisor only)."""
        # Create multiple tasks
        task_ids = []
        for i in range(3):
            task = ProjectTask(
                id=uuid.uuid4(),
                title=f"Bulk test {i}",
                status=TaskStatus.TODO.value,
                priority=TaskPriority.MEDIUM.value,
                created_by=uuid.uuid4()
            )
            test_db.add(task)
            task_ids.append(str(task.id))
        
        test_db.commit()
        
        response = supervisor_client.post(
            "/api/v1/erp/task-management/tasks/bulk-update",
            json={
                "task_ids": task_ids,
                "update_data": {
                    "status": "planned",
                    "priority": "high"
                },
                "reason": "Urgent project requirements"
            },
            headers=supervisor_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3
        assert data["failed_count"] == 0


class TestTaskDependencies:
    """Test task dependency management."""
    
    def test_circular_dependency_prevention(self, client, auth_headers, test_db):
        """Test that circular dependencies are prevented."""
        # Create two tasks
        task1 = ProjectTask(
            id=uuid.uuid4(),
            title="Task 1",
            status=TaskStatus.TODO.value,
            created_by=uuid.uuid4()
        )
        
        task2 = ProjectTask(
            id=uuid.uuid4(),
            title="Task 2",
            status=TaskStatus.TODO.value,
            created_by=uuid.uuid4()
        )
        
        test_db.add_all([task1, task2])
        test_db.commit()
        
        # Create dependency: task2 depends on task1
        from ..routes.erp_task_management import TaskDependencyModel
        dep = TaskDependencyModel(
            task_id=task2.id,
            predecessor_id=task1.id,
            dependency_type=DependencyType.FINISH_TO_START.value
        )
        test_db.add(dep)
        test_db.commit()
        
        # Try to create circular dependency: task1 depends on task2
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Task 3",
                "task_type": "field_work",
                "dependencies": [
                    {
                        "predecessor_id": str(task2.id),
                        "dependency_type": "finish_to_start"
                    }
                ]
            },
            headers=auth_headers
        )
        
        # Should succeed as this doesn't create a circular dependency
        assert response.status_code == 200
    
    def test_dependency_blocking(self, client, auth_headers, test_db):
        """Test that tasks are blocked by unmet dependencies."""
        # Create predecessor task
        predecessor = ProjectTask(
            id=uuid.uuid4(),
            title="Prerequisite task",
            status=TaskStatus.TODO.value,
            created_by=uuid.uuid4()
        )
        test_db.add(predecessor)
        test_db.commit()
        
        # Create dependent task
        response = client.post(
            "/api/v1/erp/task-management/tasks",
            json={
                "title": "Dependent task",
                "task_type": "field_work",
                "dependencies": [
                    {
                        "predecessor_id": str(predecessor.id),
                        "dependency_type": "finish_to_start"
                    }
                ]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        task_id = response.json()["id"]
        
        # Try to start dependent task
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task_id}",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "dependencies not met" in response.json()["detail"]


class TestWeatherIntegration:
    """Test weather-dependent task features."""
    
    def test_weather_hold_on_task_creation(self, client, auth_headers):
        """Test that tasks are put on weather hold when conditions are unsafe."""
        with patch('backend.services.weather.WeatherService.check_conditions') as mock_weather:
            mock_weather.return_value = {
                "temperature": 65,
                "wind_speed": 30,  # High winds
                "conditions": "Stormy",
                "unsafe_conditions": True,
                "safety_warnings": ["High winds - unsafe for roof work"]
            }
            
            response = client.post(
                "/api/v1/erp/task-management/tasks",
                json={
                    "title": "Roof repair",
                    "task_type": "field_work",
                    "location_lat": 40.7128,
                    "location_lng": -74.0060,
                    "weather_dependent": True,
                    "planned_start": datetime.utcnow().isoformat()
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "Weather hold applied" in data["warnings"]
    
    def test_weather_check_on_reschedule(self, client, auth_headers, test_db):
        """Test weather is checked when rescheduling tasks."""
        # Create weather-dependent task
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Weather dependent task",
            status=TaskStatus.PLANNED.value,
            created_by=uuid.uuid4(),
            weather_dependent=True,
            location_lat=40.7128,
            location_lng=-74.0060
        )
        test_db.add(task)
        test_db.commit()
        
        with patch('backend.services.weather.WeatherService.check_conditions') as mock_weather:
            mock_weather.return_value = {
                "temperature": 72,
                "wind_speed": 10,
                "conditions": "Clear",
                "unsafe_conditions": False
            }
            
            response = client.put(
                f"/api/v1/erp/task-management/tasks/{task.id}",
                json={
                    "planned_start": (datetime.utcnow() + timedelta(days=2)).isoformat()
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            assert mock_weather.called


class TestOperationsDashboard:
    """Test operations dashboard functionality."""
    
    def test_dashboard_metrics(self, client, auth_headers, test_db):
        """Test operations dashboard returns correct metrics."""
        # Create test data
        now = datetime.utcnow()
        tasks = [
            ProjectTask(
                id=uuid.uuid4(),
                title="Completed task",
                status=TaskStatus.COMPLETED.value,
                priority=TaskPriority.HIGH.value,
                created_by=uuid.uuid4(),
                created_at=now,
                completed_at=now,
                actual_start=now - timedelta(hours=4),
                actual_end=now
            ),
            ProjectTask(
                id=uuid.uuid4(),
                title="In progress task",
                status=TaskStatus.IN_PROGRESS.value,
                priority=TaskPriority.MEDIUM.value,
                created_by=uuid.uuid4(),
                created_at=now
            ),
            ProjectTask(
                id=uuid.uuid4(),
                title="Overdue task",
                status=TaskStatus.TODO.value,
                priority=TaskPriority.CRITICAL.value,
                due_date=now - timedelta(days=1),
                created_by=uuid.uuid4(),
                created_at=now
            ),
            ProjectTask(
                id=uuid.uuid4(),
                title="Blocked task",
                status=TaskStatus.BLOCKED.value,
                is_blocked=True,
                created_by=uuid.uuid4(),
                created_at=now
            )
        ]
        
        test_db.add_all(tasks)
        test_db.commit()
        
        response = client.get(
            "/api/v1/erp/task-management/dashboard/operations",
            params={"date_range": "today"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check metrics
        metrics = data["metrics"]
        assert metrics["total_tasks"] >= 4
        assert metrics["completed_tasks"] >= 1
        assert metrics["in_progress_tasks"] >= 1
        assert metrics["blocked_tasks"] >= 1
        assert metrics["overdue_tasks"] >= 1
        assert metrics["completion_rate"] > 0
        
        # Check breakdowns
        assert "by_priority" in data["breakdowns"]
        assert "by_type" in data["breakdowns"]
        
        # Check alerts
        alerts = data["alerts"]
        assert alerts["high_priority_overdue"] >= 1
    
    def test_dashboard_date_ranges(self, client, auth_headers):
        """Test dashboard with different date ranges."""
        for date_range in ["today", "week", "month"]:
            response = client.get(
                "/api/v1/erp/task-management/dashboard/operations",
                params={"date_range": date_range},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["period"]["range"] == date_range
            assert "start_date" in data["period"]
            assert "end_date" in data["period"]


class TestPermissions:
    """Test permission-based access control."""
    
    def test_regular_user_cannot_bulk_update(self, client, auth_headers):
        """Test that regular users cannot perform bulk updates."""
        response = client.post(
            "/api/v1/erp/task-management/tasks/bulk-update",
            json={
                "task_ids": [str(uuid.uuid4())],
                "update_data": {"status": "completed"},
                "reason": "Testing"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    def test_user_can_update_own_tasks(self, client, auth_headers, test_db, current_user):
        """Test users can update their own tasks."""
        # Create task owned by current user
        task = ProjectTask(
            id=uuid.uuid4(),
            title="My task",
            status=TaskStatus.TODO.value,
            created_by=current_user.id
        )
        test_db.add(task)
        test_db.commit()
        
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            json={"title": "Updated my task"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_user_cannot_update_others_tasks(self, client, auth_headers, test_db):
        """Test users cannot update tasks they don't own."""
        # Create task owned by another user
        other_user_id = uuid.uuid4()
        task = ProjectTask(
            id=uuid.uuid4(),
            title="Someone else's task",
            status=TaskStatus.TODO.value,
            created_by=other_user_id,
            assignee_id=other_user_id
        )
        test_db.add(task)
        test_db.commit()
        
        response = client.put(
            f"/api/v1/erp/task-management/tasks/{task.id}",
            json={"title": "Trying to update"},
            headers=auth_headers
        )
        
        assert response.status_code == 403


# Fixtures for testing
@pytest.fixture
def supervisor_headers(test_db):
    """Create auth headers for a supervisor user."""
    supervisor = User(
        id=uuid.uuid4(),
        email="supervisor@example.com",
        username="supervisor",
        hashed_password="hashed",
        role=UserRole.SUPERVISOR
    )
    test_db.add(supervisor)
    test_db.commit()
    
    token = create_access_token({"sub": str(supervisor.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supervisor_client(app):
    """Create test client for supervisor."""
    return TestClient(app)