"""
Pytest configuration and fixtures for backend tests.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from typing import Generator

# Override database URL for tests
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Import all models to ensure they're registered with Base.metadata
from ..db import models as db_models
from ..db import business_models

from ..main import app
from ..core.database import Base, get_db
from ..core.auth import create_access_token, get_password_hash
from ..db.business_models import User, UserRole, Team


# Create test database engine
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    return engine


@pytest.fixture(scope="function")
def test_db():
    """Create test database session."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up tables after each test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator:
    """Create test client with database override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.USER,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_user(test_db: Session) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        username="adminuser",
        full_name="Admin User",
        hashed_password=get_password_hash("testpassword"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    token = create_access_token({"sub": test_user.email, "user_id": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user: User) -> dict:
    """Create authentication headers for admin user."""
    token = create_access_token({"sub": admin_user.email, "user_id": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_team(test_db: Session, test_user: User) -> Team:
    """Create a test team."""
    team = Team(
        name="Test Team",
        slug="test-team",
        description="A test team",
        owner_id=test_user.id
    )
    test_db.add(team)
    test_db.commit()
    test_db.refresh(team)
    return team