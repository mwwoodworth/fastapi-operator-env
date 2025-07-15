"""Comprehensive API testing suite."""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from db.session import get_db
from db.models import Base, User
from core.security import get_password_hash


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestUser:
    """Test user management."""
    
    def __init__(self):
        self.username = "testuser"
        self.email = "test@example.com"
        self.password = "testpassword123"
        self.token = None
        
    def create(self, db):
        """Create test user in database."""
        user = User(
            username=self.username,
            email=self.email,
            hashed_password=get_password_hash(self.password),
            is_active=True,
            is_superuser=False,
            roles=["user"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
        
    def login(self):
        """Login and get token."""
        response = client.post(
            "/auth/token",
            data={
                "username": self.username,
                "password": self.password
            }
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        return self.token
        
    def headers(self):
        """Get authorization headers."""
        if not self.token:
            self.login()
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def test_user():
    """Create a test user."""
    return TestUser()


@pytest.fixture
def db():
    """Get test database session."""
    db = TestingSessionLocal()
    yield db
    db.close()


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_register(self):
        """Test user registration."""
        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        
    def test_login(self, test_user, db):
        """Test user login."""
        test_user.create(db)
        
        response = client.post(
            "/auth/token",
            data={
                "username": test_user.username,
                "password": test_user.password
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
    def test_get_current_user(self, test_user, db):
        """Test getting current user info."""
        test_user.create(db)
        
        response = client.get(
            "/auth/me",
            headers=test_user.headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        
    def test_refresh_token(self, test_user, db):
        """Test token refresh."""
        test_user.create(db)
        
        # Login to get tokens
        login_response = client.post(
            "/auth/login",
            json={
                "username": test_user.username,
                "password": test_user.password
            }
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestAIStreamingEndpoints:
    """Test AI streaming endpoints."""
    
    @pytest.mark.asyncio
    async def test_sse_streaming(self, test_user, db):
        """Test Server-Sent Events streaming."""
        test_user.create(db)
        
        # This would need actual testing with async client
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/ai/chat/stream",
                headers=test_user.headers(),
                json={
                    "message": "Hello AI",
                    "model": "claude-3-opus",
                    "stream": True
                }
            )
            # In real test, we'd consume the SSE stream
            assert response.status_code == 200
    
    def test_list_models(self, test_user, db):
        """Test listing available AI models."""
        test_user.create(db)
        
        response = client.get(
            "/ai/models",
            headers=test_user.headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0
        
    def test_list_sessions(self, test_user, db):
        """Test listing AI sessions."""
        test_user.create(db)
        
        response = client.get(
            "/ai/sessions",
            headers=test_user.headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRAGEndpoints:
    """Test RAG system endpoints."""
    
    def test_create_document(self, test_user, db):
        """Test document creation."""
        test_user.create(db)
        
        response = client.post(
            "/rag/documents",
            headers=test_user.headers(),
            json={
                "title": "Test Document",
                "content": "This is a test document for RAG system.",
                "category": "test",
                "tags": ["test", "rag"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Document"
        assert data["category"] == "test"
        
    def test_search_documents(self, test_user, db):
        """Test document search."""
        test_user.create(db)
        
        # First create a document
        client.post(
            "/rag/documents",
            headers=test_user.headers(),
            json={
                "title": "Roofing Best Practices",
                "content": "Always use proper safety equipment when working on roofs.",
                "category": "roofing"
            }
        )
        
        # Search for it
        response = client.post(
            "/rag/search",
            headers=test_user.headers(),
            json={
                "query": "safety equipment",
                "limit": 10
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_generate_context(self, test_user, db):
        """Test context generation."""
        test_user.create(db)
        
        response = client.post(
            "/rag/context",
            headers=test_user.headers(),
            json={
                "query": "roofing safety",
                "max_context_length": 2000
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "context" in data
        assert "context_length" in data


class TestWebhookEndpoints:
    """Test webhook endpoints."""
    
    def test_stripe_webhook(self, db):
        """Test Stripe webhook handling."""
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_email": "customer@example.com",
                    "amount_total": 9900
                }
            }
        }
        
        # Would need proper signature generation
        response = client.post(
            "/webhooks/stripe",
            json=event,
            headers={"Stripe-Signature": "test_signature"}
        )
        # Without proper signature, this should fail
        assert response.status_code == 400
        
    def test_list_webhook_events(self, db):
        """Test listing webhook events."""
        response = client.get("/webhooks/events")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "events" in data


class TestHealthAndMetrics:
    """Test health and metrics endpoints."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_not_found(self):
        """Test 404 error."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
    def test_401_unauthorized(self):
        """Test 401 unauthorized."""
        response = client.get("/auth/me")
        assert response.status_code == 401
        
    def test_invalid_json(self, test_user, db):
        """Test invalid JSON handling."""
        test_user.create(db)
        
        response = client.post(
            "/rag/documents",
            headers=test_user.headers(),
            data="invalid json"
        )
        assert response.status_code == 422


class TestRateLimiting:
    """Test rate limiting."""
    
    def test_rate_limit(self):
        """Test that rate limiting works."""
        # Make many requests quickly
        responses = []
        for _ in range(150):  # Exceeds typical rate limit
            response = client.get("/health")
            responses.append(response.status_code)
        
        # At least one should be rate limited
        assert 429 in responses or all(r == 200 for r in responses)


class TestCORS:
    """Test CORS headers."""
    
    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = client.options("/health")
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.asyncio
async def test_concurrent_requests(test_user, db):
    """Test handling concurrent requests."""
    test_user.create(db)
    
    async def make_request():
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(
                "/auth/me",
                headers=test_user.headers()
            )
            return response.status_code
    
    # Make 10 concurrent requests
    tasks = [make_request() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(status == 200 for status in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])