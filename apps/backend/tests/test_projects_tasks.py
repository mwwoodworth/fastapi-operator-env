"""
Comprehensive tests for project and task management endpoints.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, Project, ProjectTask, Team, project_members


@pytest.fixture
def test_project(test_db: Session, test_user: User):
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="A test project",
        project_type="general",
        owner_id=test_user.id,
        start_date=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=30)
    )
    test_db.add(project)
    test_db.commit()
    
    # Add owner as member
    test_db.execute(
        project_members.insert().values(
            project_id=project.id,
            user_id=test_user.id,
            role='admin'
        )
    )
    test_db.commit()
    test_db.refresh(project)
    
    yield project
    
    # Cleanup
    test_db.delete(project)
    test_db.commit()


@pytest.fixture
def test_task(test_db: Session, test_project: Project, test_user: User):
    """Create a test task."""
    task = ProjectTask(
        project_id=test_project.id,
        title="Test Task",
        description="A test task",
        status="todo",
        priority="medium",
        created_by=test_user.id,
        assignee_id=test_user.id,
        due_date=datetime.utcnow() + timedelta(days=7)
    )
    test_db.add(task)
    test_db.commit()
    test_db.refresh(task)
    
    yield task
    
    # Cleanup
    test_db.delete(task)
    test_db.commit()


class TestProjectManagement:
    """Test project management endpoints."""
    
    def test_create_project(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test creating a project."""
        response = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": "New Project",
                "description": "A new project",
                "project_type": "general",
                "tags": ["test", "demo"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Project"
        assert data["owner_id"] == str(test_user.id)
        assert data["member_count"] == 1
        assert data["task_count"] == 0
    
    def test_create_team_project(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test creating a project for a team."""
        response = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": "Team Project",
                "description": "A team project",
                "project_type": "general",
                "team_id": str(test_team.id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["team_id"] == str(test_team.id)
    
    def test_list_projects(self, client: TestClient, test_project: Project, auth_headers: dict):
        """Test listing projects."""
        response = client.get("/api/v1/projects/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["id"] == str(test_project.id) for p in data)
    
    def test_list_projects_with_filters(self, client: TestClient, test_project: Project, auth_headers: dict):
        """Test listing projects with filters."""
        response = client.get(
            "/api/v1/projects/",
            headers=auth_headers,
            params={
                "search": "Test",
                "status": "active",
                "project_type": "general"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all("Test" in p["name"] for p in data)
        assert all(p["status"] == "active" for p in data)
    
    def test_get_project(self, client: TestClient, test_project: Project, auth_headers: dict):
        """Test getting project details."""
        response = client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_project.id)
        assert data["name"] == test_project.name
        assert "member_count" in data
        assert "task_count" in data
    
    def test_update_project(self, client: TestClient, test_project: Project, auth_headers: dict):
        """Test updating project."""
        response = client.put(
            f"/api/v1/projects/{test_project.id}",
            headers=auth_headers,
            json={
                "name": "Updated Project",
                "status": "completed",
                "priority": "high"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project"
        assert data["status"] == "completed"
        assert data["priority"] == "high"
        assert data["completed_at"] is not None
    
    def test_archive_project(self, client: TestClient, test_project: Project, auth_headers: dict, test_db: Session):
        """Test archiving a project."""
        response = client.post(
            f"/api/v1/projects/{test_project.id}/archive",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify project is archived
        test_db.refresh(test_project)
        assert test_project.status == "archived"
        assert test_project.archived_at is not None
    
    def test_restore_project(self, client: TestClient, test_project: Project, auth_headers: dict, test_db: Session):
        """Test restoring an archived project."""
        # Archive project first
        test_project.status = "archived"
        test_db.commit()
        
        response = client.post(
            f"/api/v1/projects/{test_project.id}/restore",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify project is restored
        test_db.refresh(test_project)
        assert test_project.status == "active"
        assert test_project.archived_at is None
    
    def test_get_project_stats(self, client: TestClient, test_project: Project, test_task: ProjectTask, auth_headers: dict):
        """Test getting project statistics."""
        response = client.get(
            f"/api/v1/projects/{test_project.id}/stats",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] >= 1
        assert "completed_tasks" in data
        assert "completion_rate" in data
        assert "members" in data
    
    def test_add_project_member(self, client: TestClient, test_project: Project, auth_headers: dict, test_db: Session):
        """Test adding member to project."""
        # Create new user
        new_user = User(
            email="projectmember@example.com",
            username="projectmember",
            hashed_password="hashed",
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/projects/{test_project.id}/members",
            headers=auth_headers,
            json={
                "user_id": str(new_user.id),
                "role": "member"
            }
        )
        
        assert response.status_code == 200
        
        # Verify member was added
        members = test_db.query(project_members).filter(
            project_members.c.project_id == test_project.id
        ).count()
        assert members == 2


class TestTaskManagement:
    """Test task management endpoints."""
    
    def test_create_task(self, client: TestClient, test_project: Project, test_user: User, auth_headers: dict):
        """Test creating a task."""
        response = client.post(
            f"/api/v1/projects/{test_project.id}/tasks",
            headers=auth_headers,
            json={
                "title": "New Task",
                "description": "Task description",
                "priority": "high",
                "assignee_id": str(test_user.id),
                "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                "tags": ["urgent", "backend"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Task"
        assert data["priority"] == "high"
        assert data["assignee_id"] == str(test_user.id)
    
    def test_list_project_tasks(self, client: TestClient, test_project: Project, test_task: ProjectTask, auth_headers: dict):
        """Test listing project tasks."""
        response = client.get(
            f"/api/v1/projects/{test_project.id}/tasks",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(t["id"] == str(test_task.id) for t in data)
    
    def test_list_tasks_with_filters(self, client: TestClient, test_project: Project, test_task: ProjectTask, auth_headers: dict):
        """Test listing tasks with filters."""
        response = client.get(
            f"/api/v1/projects/{test_project.id}/tasks",
            headers=auth_headers,
            params={
                "status": "todo",
                "priority": "medium",
                "assignee_id": str(test_task.assignee_id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "todo" for t in data)
        assert all(t["priority"] == "medium" for t in data)
    
    def test_get_task(self, client: TestClient, test_task: ProjectTask, auth_headers: dict):
        """Test getting task details."""
        response = client.get(f"/api/v1/projects/tasks/{test_task.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_task.id)
        assert data["title"] == test_task.title
        assert "assignee_name" in data
        assert "creator_name" in data
    
    def test_update_task(self, client: TestClient, test_task: ProjectTask, auth_headers: dict):
        """Test updating task."""
        response = client.put(
            f"/api/v1/projects/tasks/{test_task.id}",
            headers=auth_headers,
            json={
                "title": "Updated Task",
                "status": "in_progress",
                "actual_hours": 2.5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Task"
        assert data["status"] == "in_progress"
        assert data["actual_hours"] == 2.5
    
    def test_assign_task(self, client: TestClient, test_task: ProjectTask, test_user: User, auth_headers: dict, test_db: Session):
        """Test assigning task to user."""
        # Create another project member
        new_user = User(
            email="assignee@example.com",
            username="assignee",
            hashed_password="hashed",
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        # Add as project member
        test_db.execute(
            project_members.insert().values(
                project_id=test_task.project_id,
                user_id=new_user.id,
                role='member'
            )
        )
        test_db.commit()
        
        response = client.post(
            f"/api/v1/projects/tasks/{test_task.id}/assign",
            headers=auth_headers,
            json={"assignee_id": str(new_user.id)}
        )
        
        assert response.status_code == 200
        
        # Verify assignment
        test_db.refresh(test_task)
        assert test_task.assignee_id == new_user.id
    
    def test_complete_task(self, client: TestClient, test_task: ProjectTask, auth_headers: dict, test_db: Session):
        """Test completing a task."""
        response = client.post(
            f"/api/v1/projects/tasks/{test_task.id}/complete",
            headers=auth_headers,
            json={"actual_hours": 5.0}
        )
        
        assert response.status_code == 200
        
        # Verify task is completed
        test_db.refresh(test_task)
        assert test_task.status == "done"
        assert test_task.completed_at is not None
        assert test_task.actual_hours == 5.0
    
    def test_delete_task(self, client: TestClient, test_task: ProjectTask, auth_headers: dict, test_db: Session):
        """Test deleting a task."""
        task_id = test_task.id
        
        response = client.delete(
            f"/api/v1/projects/tasks/{task_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify task is deleted
        task = test_db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
        assert task is None
    
    def test_add_task_comment(self, client: TestClient, test_task: ProjectTask, auth_headers: dict):
        """Test adding comment to task."""
        response = client.post(
            f"/api/v1/projects/tasks/{test_task.id}/comments",
            headers=auth_headers,
            json={
                "content": "This is a test comment",
                "attachments": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "This is a test comment"
        assert "user_name" in data
        assert "created_at" in data
    
    def test_get_task_comments(self, client: TestClient, test_task: ProjectTask, auth_headers: dict, test_db: Session):
        """Test getting task comments."""
        # Add a comment first
        from ..db.business_models import TaskComment
        comment = TaskComment(
            task_id=test_task.id,
            user_id=test_task.created_by,
            content="Test comment"
        )
        test_db.add(comment)
        test_db.commit()
        
        response = client.get(
            f"/api/v1/projects/tasks/{test_task.id}/comments",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["content"] == "Test comment"


class TestProjectAccessControl:
    """Test project access control."""
    
    def test_non_member_cannot_view_project(self, client: TestClient, test_project: Project):
        """Test that non-members cannot view project."""
        # Create another user
        other_user = User(
            email="other@example.com",
            username="other",
            hashed_password="hashed",
            is_active=True
        )
        
        token = create_access_token(data={"sub": other_user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(f"/api/v1/projects/{test_project.id}", headers=headers)
        
        assert response.status_code == 403
    
    def test_non_admin_cannot_add_members(self, client: TestClient, test_project: Project, test_db: Session):
        """Test that non-admin members cannot add other members."""
        # Create a regular member
        member = User(
            email="member@example.com",
            username="member",
            hashed_password="hashed",
            is_active=True
        )
        test_db.add(member)
        test_db.commit()
        
        # Add as regular member
        test_db.execute(
            project_members.insert().values(
                project_id=test_project.id,
                user_id=member.id,
                role='member'
            )
        )
        test_db.commit()
        
        token = create_access_token(data={"sub": member.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to add another member
        response = client.post(
            f"/api/v1/projects/{test_project.id}/members",
            headers=headers,
            json={
                "user_id": str(uuid4()),
                "role": "member"
            }
        )
        
        assert response.status_code == 403
    
    def test_task_assignee_can_update_status(self, client: TestClient, test_task: ProjectTask, test_db: Session):
        """Test that task assignee can update task status."""
        # Ensure task is assigned
        assignee = test_db.query(User).filter(User.id == test_task.assignee_id).first()
        
        token = create_access_token(data={"sub": assignee.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.put(
            f"/api/v1/projects/tasks/{test_task.id}",
            headers=headers,
            json={"status": "in_progress"}
        )
        
        assert response.status_code == 200