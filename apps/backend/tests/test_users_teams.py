"""
Comprehensive tests for user and team management endpoints.
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..main import app
from ..core.database import get_db
from ..core.auth import get_password_hash, create_access_token
from ..db.business_models import User, UserRole, Team, team_members


@pytest.fixture
def admin_user(test_db: Session):
    """Create an admin user."""
    user = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=get_password_hash("adminpassword"),
        full_name="Admin User",
        is_active=True,
        is_verified=True,
        role=UserRole.ADMIN
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    yield user
    
    # Cleanup
    test_db.delete(user)
    test_db.commit()


@pytest.fixture
def admin_headers(admin_user: User):
    """Create admin authorization headers."""
    token = create_access_token(data={"sub": admin_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_team(test_db: Session, test_user: User):
    """Create a test team."""
    team = Team(
        name="Test Team",
        slug="test-team",
        description="A test team",
        owner_id=test_user.id
    )
    test_db.add(team)
    test_db.commit()
    
    # Add owner as member
    test_db.execute(
        team_members.insert().values(
            team_id=team.id,
            user_id=test_user.id,
            role='admin'
        )
    )
    test_db.commit()
    test_db.refresh(team)
    
    yield team
    
    # Cleanup
    test_db.delete(team)
    test_db.commit()


class TestUserManagement:
    """Test user management endpoints."""
    
    def test_list_users_admin_only(self, client: TestClient, auth_headers: dict):
        """Test that only admins can list all users."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403
    
    def test_list_users_as_admin(self, client: TestClient, admin_headers: dict):
        """Test listing users as admin."""
        response = client.get("/api/v1/users/", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_list_users_with_filters(self, client: TestClient, admin_headers: dict):
        """Test listing users with filters."""
        response = client.get(
            "/api/v1/users/",
            headers=admin_headers,
            params={
                "search": "admin",
                "role": "admin",
                "is_active": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all("admin" in user["email"].lower() for user in data)
    
    def test_get_user_own_profile(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting own user profile."""
        response = client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
    
    def test_get_user_other_profile_forbidden(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test that users cannot view other profiles."""
        other_id = str(uuid4())
        response = client.get(f"/api/v1/users/{other_id}", headers=auth_headers)
        
        assert response.status_code == 403
    
    def test_update_user_profile(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test updating user profile."""
        response = client.put(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers,
            json={
                "full_name": "Updated Name",
                "bio": "Updated bio"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["bio"] == "Updated bio"
    
    def test_admin_update_user(self, client: TestClient, test_user: User, admin_headers: dict, test_db: Session):
        """Test admin updating user settings."""
        response = client.put(
            f"/api/v1/users/{test_user.id}/admin",
            headers=admin_headers,
            json={
                "role": "viewer",
                "is_verified": True
            }
        )
        
        assert response.status_code == 200
        
        # Verify changes
        test_db.refresh(test_user)
        assert test_user.role == UserRole.VIEWER
        assert test_user.is_verified is True
    
    def test_delete_user(self, client: TestClient, test_user: User, admin_headers: dict, test_db: Session):
        """Test deleting a user."""
        response = client.delete(f"/api/v1/users/{test_user.id}", headers=admin_headers)
        
        assert response.status_code == 200
        
        # Verify user is soft deleted
        test_db.refresh(test_user)
        assert test_user.is_active is False
    
    def test_suspend_user(self, client: TestClient, test_user: User, admin_headers: dict, test_db: Session):
        """Test suspending a user."""
        response = client.post(
            f"/api/v1/users/{test_user.id}/suspend",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # Verify user is suspended
        test_db.refresh(test_user)
        assert test_user.is_active is False
        assert test_user.suspended_at is not None
    
    def test_activate_user(self, client: TestClient, test_user: User, admin_headers: dict, test_db: Session):
        """Test activating a suspended user."""
        # First suspend the user
        test_user.is_active = False
        test_db.commit()
        
        response = client.post(
            f"/api/v1/users/{test_user.id}/activate",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # Verify user is active
        test_db.refresh(test_user)
        assert test_user.is_active is True
    
    def test_get_user_activity(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting user activity."""
        response = client.get(
            f"/api/v1/users/{test_user.id}/activity",
            headers=auth_headers,
            params={"days": 7}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestTeamManagement:
    """Test team management endpoints."""
    
    def test_create_team(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test creating a team."""
        response = client.post(
            "/api/v1/users/teams",
            headers=auth_headers,
            json={
                "name": "New Team",
                "slug": "new-team",
                "description": "A new team"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Team"
        assert data["slug"] == "new-team"
        assert data["owner_id"] == str(test_user.id)
        assert data["member_count"] == 1
    
    def test_create_team_duplicate_slug(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test creating team with duplicate slug."""
        response = client.post(
            "/api/v1/users/teams",
            headers=auth_headers,
            json={
                "name": "Another Team",
                "slug": test_team.slug,
                "description": "Another team"
            }
        )
        
        assert response.status_code == 400
        assert "slug already exists" in response.json()["detail"]
    
    def test_list_teams(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test listing teams."""
        response = client.get("/api/v1/users/teams", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(team["id"] == str(test_team.id) for team in data)
    
    def test_list_my_teams(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test listing only user's teams."""
        response = client.get(
            "/api/v1/users/teams",
            headers=auth_headers,
            params={"my_teams": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(team["id"] == str(test_team.id) for team in data)
    
    def test_get_team(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test getting team details."""
        response = client.get(f"/api/v1/users/teams/{test_team.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_team.id)
        assert data["name"] == test_team.name
    
    def test_update_team(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test updating team details."""
        response = client.put(
            f"/api/v1/users/teams/{test_team.id}",
            headers=auth_headers,
            json={
                "name": "Updated Team Name",
                "description": "Updated description"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Team Name"
        assert data["description"] == "Updated description"
    
    def test_delete_team(self, client: TestClient, test_team: Team, auth_headers: dict, test_db: Session):
        """Test deleting a team."""
        response = client.delete(f"/api/v1/users/teams/{test_team.id}", headers=auth_headers)
        
        assert response.status_code == 200
        
        # Verify team is soft deleted
        test_db.refresh(test_team)
        assert test_team.is_active is False
    
    def test_add_team_member(self, client: TestClient, test_team: Team, test_user: User, auth_headers: dict, test_db: Session):
        """Test adding a member to team."""
        # Create another user
        new_user = User(
            email="newmember@example.com",
            username="newmember",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/users/teams/{test_team.id}/members",
            headers=auth_headers,
            json={
                "user_email": new_user.email,
                "role": "member"
            }
        )
        
        assert response.status_code == 200
        
        # Verify member was added
        members = test_db.query(team_members).filter(
            team_members.c.team_id == test_team.id
        ).count()
        assert members == 2
    
    def test_list_team_members(self, client: TestClient, test_team: Team, auth_headers: dict):
        """Test listing team members."""
        response = client.get(
            f"/api/v1/users/teams/{test_team.id}/members",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["role"] == "admin"
    
    def test_remove_team_member(self, client: TestClient, test_team: Team, auth_headers: dict, test_db: Session):
        """Test removing a team member."""
        # Add a member first
        new_user = User(
            email="removeme@example.com",
            username="removeme",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        test_db.execute(
            team_members.insert().values(
                team_id=test_team.id,
                user_id=new_user.id,
                role='member'
            )
        )
        test_db.commit()
        
        response = client.delete(
            f"/api/v1/users/teams/{test_team.id}/members/{new_user.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify member was removed
        members = test_db.query(team_members).filter(
            team_members.c.team_id == test_team.id
        ).count()
        assert members == 1
    
    def test_update_member_role(self, client: TestClient, test_team: Team, auth_headers: dict, test_db: Session):
        """Test updating team member role."""
        # Add a member
        new_user = User(
            email="promote@example.com",
            username="promote",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        test_db.execute(
            team_members.insert().values(
                team_id=test_team.id,
                user_id=new_user.id,
                role='member'
            )
        )
        test_db.commit()
        
        response = client.put(
            f"/api/v1/users/teams/{test_team.id}/members/{new_user.id}/role",
            headers=auth_headers,
            json={"role": "admin"}
        )
        
        assert response.status_code == 200
        
        # Verify role was updated
        member = test_db.query(team_members).filter(
            team_members.c.team_id == test_team.id,
            team_members.c.user_id == new_user.id
        ).first()
        assert member.role == "admin"
    
    def test_team_member_limit(self, client: TestClient, test_team: Team, auth_headers: dict, test_db: Session):
        """Test team member limit enforcement."""
        # Set low member limit
        test_team.max_members = 2
        test_db.commit()
        
        # Try to add member when at limit
        new_user = User(
            email="overlimit@example.com",
            username="overlimit",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        test_db.add(new_user)
        test_db.commit()
        
        # Add one more member to reach limit
        test_db.execute(
            team_members.insert().values(
                team_id=test_team.id,
                user_id=new_user.id,
                role='member'
            )
        )
        test_db.commit()
        
        # Try to add another member
        another_user = User(
            email="rejected@example.com",
            username="rejected",
            hashed_password=get_password_hash("password"),
            is_active=True
        )
        test_db.add(another_user)
        test_db.commit()
        
        response = client.post(
            f"/api/v1/users/teams/{test_team.id}/members",
            headers=auth_headers,
            json={
                "user_email": another_user.email,
                "role": "member"
            }
        )
        
        assert response.status_code == 400
        assert "member limit" in response.json()["detail"]