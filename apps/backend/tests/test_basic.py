"""
Basic tests to verify infrastructure is working.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from ..db.business_models import User, UserRole


def test_database_connection(test_db: Session):
    """Test that database connection works."""
    # This should create tables via conftest fixture
    assert test_db is not None
    
    # Try a simple query
    user_count = test_db.query(User).count()
    assert user_count == 0


def test_create_user(test_db: Session):
    """Test creating a user."""
    user = User(
        email="basic@test.com",
        username="basictest",
        hashed_password="hashed",
        full_name="Basic Test",
        is_active=True,
        is_verified=True,
        role=UserRole.USER
    )
    test_db.add(user)
    test_db.commit()
    
    # Query back
    saved_user = test_db.query(User).filter_by(email="basic@test.com").first()
    assert saved_user is not None
    assert saved_user.username == "basictest"


def test_health_endpoint(client: TestClient):
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint(client: TestClient):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "BrainOps Operator Service"
    assert "status" in data
    assert data["status"] == "operational"