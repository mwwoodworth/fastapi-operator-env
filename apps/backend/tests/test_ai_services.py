"""
Comprehensive tests for AI service endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import patch, AsyncMock

from ..main import app
from ..core.database import get_db
from ..core.auth import create_access_token
from ..db.business_models import User, UserRole, Subscription


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
    """Create a test user with subscription."""
    user = User(
        email="aitest@example.com",
        username="aitestuser",
        hashed_password="hashedpassword",
        full_name="AI Test User",
        is_active=True,
        is_verified=True,
        role=UserRole.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    # Add subscription
    subscription = Subscription(
        user_id=user.id,
        plan_name="Pro",
        monthly_ai_requests=1000,
        used_ai_requests=0,
        monthly_budget=100.0
    )
    test_db.add(subscription)
    test_db.commit()
    
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


class TestChatEndpoints:
    """Test chat-related endpoints."""
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_chat_message(self, mock_claude, client, auth_headers):
        """Test sending a chat message."""
        mock_claude.generate = AsyncMock(return_value="Hello! How can I help you?")
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Hello, AI!",
                "model": "claude",
                "stream": False
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["message"] == "Hello! How can I help you?"
        assert data["model_used"] == "claude"
    
    @patch('apps.backend.routes.ai_services.VectorStore')
    def test_list_chat_sessions(self, mock_vector_store, client, auth_headers):
        """Test listing chat sessions."""
        mock_store = mock_vector_store.return_value
        mock_store.get_user_sessions = AsyncMock(return_value=[
            {
                "id": "session1",
                "title": "Test Chat",
                "model": "claude",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "message_count": 5
            }
        ])
        
        response = client.get(
            "/api/v1/ai/chat/sessions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["title"] == "Test Chat"
    
    @patch('apps.backend.routes.ai_services.VectorStore')
    def test_get_chat_session(self, mock_vector_store, client, auth_headers):
        """Test getting chat session history."""
        mock_store = mock_vector_store.return_value
        mock_messages = [
            type('Message', (), {
                'role': 'user',
                'content': 'Hello',
                'timestamp': datetime.utcnow()
            }),
            type('Message', (), {
                'role': 'assistant',
                'content': 'Hi there!',
                'timestamp': datetime.utcnow()
            })
        ]
        mock_store.get_conversation_history = AsyncMock(return_value=mock_messages)
        
        response = client.get(
            "/api/v1/ai/chat/sessions/test-session-id",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-id"
        assert len(data["messages"]) == 2
    
    @patch('apps.backend.routes.ai_services.VectorStore')
    def test_delete_chat_session(self, mock_vector_store, client, auth_headers):
        """Test deleting a chat session."""
        mock_store = mock_vector_store.return_value
        mock_store.delete_session = AsyncMock()
        
        response = client.delete(
            "/api/v1/ai/chat/sessions/test-session-id",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Session deleted successfully"


class TestDocumentGeneration:
    """Test document generation endpoints."""
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_generate_document(self, mock_claude, client, auth_headers, test_db):
        """Test document generation."""
        mock_claude.generate = AsyncMock(return_value="# Generated Report\n\nThis is a test report.")
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/documents/generate",
            json={
                "document_type": "report",
                "title": "Test Report",
                "context": {"topic": "AI Testing"},
                "format": "markdown"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["title"] == "Test Report"
        assert data["type"] == "report"
        assert data["format"] == "markdown"
    
    def test_create_document_template(self, client, auth_headers, test_db):
        """Test creating a document template."""
        response = client.post(
            "/api/v1/ai/documents/templates",
            json={
                "name": "Test Template",
                "description": "A test template",
                "document_type": "report",
                "template": "# {{title}}\n\n{{content}}",
                "variables": ["title", "content"],
                "example_context": {"title": "Example", "content": "Example content"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        template = response.json()
        assert template["name"] == "Test Template"
    
    def test_list_document_templates(self, client, auth_headers):
        """Test listing document templates."""
        response = client.get(
            "/api/v1/ai/documents/templates",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestAnalysisEndpoints:
    """Test analysis endpoints."""
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_analyze_text(self, mock_claude, client, auth_headers):
        """Test text analysis."""
        mock_claude.generate = AsyncMock(return_value="Sentiment: Positive (0.8)")
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/analyze/text",
            json={
                "content": "This is a great product!",
                "analysis_type": "sentiment"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_type"] == "sentiment"
        assert "result" in data
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_summarize_content(self, mock_claude, client, auth_headers):
        """Test content summarization."""
        mock_claude.generate = AsyncMock(return_value="This is a summary.")
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/summarize",
            json={
                "content": "Long text to summarize...",
                "summary_length": "short"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"] == "This is a summary."
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_translate_text(self, mock_claude, client, auth_headers):
        """Test text translation."""
        mock_claude.generate = AsyncMock(return_value="Bonjour")
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/translate",
            json={
                "text": "Hello",
                "target_language": "French"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["translated_text"] == "Bonjour"
        assert data["target_language"] == "French"
    
    @patch('apps.backend.routes.ai_services.claude_agent')
    def test_extract_data(self, mock_claude, client, auth_headers):
        """Test data extraction."""
        extracted = {"name": "John Doe", "email": "john@example.com"}
        mock_claude.generate = AsyncMock(return_value=json.dumps(extracted))
        mock_claude.name = "claude"
        
        response = client.post(
            "/api/v1/ai/extract",
            json={
                "content": "Contact: John Doe at john@example.com",
                "extraction_schema": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                }
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["extracted_data"] == extracted


class TestModelManagement:
    """Test model management endpoints."""
    
    def test_list_available_models(self, client, auth_headers):
        """Test listing available AI models."""
        response = client.get(
            "/api/v1/ai/models",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        models = response.json()
        assert len(models) > 0
        assert all("name" in model for model in models)
        assert all("provider" in model for model in models)
        assert all("capabilities" in model for model in models)
    
    @patch('apps.backend.routes.ai_services.VectorStore')
    def test_select_model_for_session(self, mock_vector_store, client, auth_headers):
        """Test selecting a model for a session."""
        mock_store = mock_vector_store.return_value
        mock_store.update_session_model = AsyncMock()
        
        response = client.post(
            "/api/v1/ai/models/select",
            json={
                "session_id": "test-session",
                "model": "claude"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Model claude selected for session"
    
    def test_get_model_usage(self, client, auth_headers, test_db):
        """Test getting model usage statistics."""
        response = client.get(
            "/api/v1/ai/models/usage?period=month",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        usage = response.json()
        assert "period" in usage
        assert "total_requests" in usage
        assert "total_tokens" in usage
    
    def test_get_usage_costs(self, client, auth_headers, test_db):
        """Test getting usage cost breakdown."""
        response = client.get(
            "/api/v1/ai/models/costs?period=month",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        costs = response.json()
        assert "period" in costs
        assert "total_cost" in costs
        assert "remaining_budget" in costs


class TestQuotaLimits:
    """Test quota and rate limiting."""
    
    def test_quota_exceeded(self, client, auth_headers, test_db, test_user):
        """Test behavior when quota is exceeded."""
        # Update user's subscription to exceed quota
        subscription = test_db.query(Subscription).filter(
            Subscription.user_id == test_user.id
        ).first()
        subscription.used_ai_requests = subscription.monthly_ai_requests
        test_db.commit()
        
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "Hello"},
            headers=auth_headers
        )
        
        assert response.status_code == 429
        assert "Monthly AI request limit reached" in response.json()["detail"]