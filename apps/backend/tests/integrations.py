"""
Integration tests for external service connections.

Tests webhook handling, API client functionality, and data synchronization
for all integrated services including Slack, ClickUp, Notion, Make.com,
and Stripe.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json
import hmac
import hashlib

from fastapi.testclient import TestClient
from .integrations.slack import SlackIntegration
from .integrations.clickup import ClickUpIntegration
from .integrations.notion import NotionIntegration
from .integrations.make import MakeIntegration
from .integrations.stripe import StripeIntegration
from .core.settings import settings


@pytest.mark.asyncio
class TestSlackIntegration:
    """Test Slack integration functionality."""
    
    async def test_slash_command_validation(self):
        """Test Slack slash command signature validation."""
        slack = SlackIntegration()
        
        # Create valid signature
        timestamp = str(int(datetime.utcnow().timestamp()))
        base_string = f"v0:{timestamp}:command=/brainops&text=test"
        signature = 'v0=' + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode(),
            base_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Test valid signature
        is_valid = slack.verify_request_signature(
            signature=signature,
            timestamp=timestamp,
            body="command=/brainops&text=test"
        )
        assert is_valid is True
        
        # Test invalid signature
        is_valid = slack.verify_request_signature(
            signature="v0=invalid",
            timestamp=timestamp,
            body="command=/brainops&text=test"
        )
        assert is_valid is False
    
    async def test_slash_command_parsing(self):
        """Test parsing of Slack slash commands."""
        slack = SlackIntegration()
        
        # Test various command formats
        test_cases = [
            {
                "text": "task generate-report weekly",
                "expected_command": "task",
                "expected_args": ["generate-report", "weekly"]
            },
            {
                "text": "search roofing estimates Denver",
                "expected_command": "search",
                "expected_args": ["roofing", "estimates", "Denver"]
            },
            {
                "text": "help",
                "expected_command": "help",
                "expected_args": []
            }
        ]
        
        for case in test_cases:
            command, args = slack.parse_command_text(case["text"])
            assert command == case["expected_command"]
            assert args == case["expected_args"]
    
    async def test_message_posting(self):
        """Test posting messages to Slack."""
        slack = SlackIntegration()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"ok": True}
            
            # Test simple message
            result = await slack.post_message(
                channel="#general",
                text="Test message"
            )
            
            assert result["ok"] is True
            mock_post.assert_called_once()
            
            # Verify message structure
            call_args = mock_post.call_args[1]["json"]
            assert call_args["channel"] == "#general"
            assert call_args["text"] == "Test message"
    
    async def test_interactive_message(self):
        """Test handling interactive message actions."""
        slack = SlackIntegration()
        
        # Mock interactive payload
        payload = {
            "type": "interactive_message",
            "actions": [{
                "name": "approve",
                "value": "task_123"
            }],
            "user": {"id": "U12345"},
            "channel": {"id": "C12345"},
            "message_ts": "1234567890.123"
        }
        
        with patch.object(slack, 'update_message') as mock_update:
            result = await slack.handle_interaction(payload)
            
            # Verify action was processed
            assert result["response_type"] == "in_channel"
            mock_update.assert_called_once()


@pytest.mark.asyncio
class TestClickUpIntegration:
    """Test ClickUp integration functionality."""
    
    async def test_webhook_validation(self):
        """Test ClickUp webhook signature validation."""
        clickup = ClickUpIntegration()
        
        # Create test webhook payload
        payload = {"task_id": "123", "event": "taskUpdated"}
        secret = settings.CLICKUP_WEBHOOK_SECRET
        
        # Generate valid signature
        signature = hmac.new(
            secret.encode(),
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Test validation
        is_valid = await clickup.validate_webhook(
            signature=signature,
            payload=payload
        )
        assert is_valid is True
    
    async def test_task_retrieval(self):
        """Test retrieving tasks from ClickUp."""
        clickup = ClickUpIntegration()
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock ClickUp API response
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "tasks": [
                    {
                        "id": "task_123",
                        "name": "Test Task",
                        "status": {"status": "open"},
                        "assignees": [{"username": "john"}]
                    }
                ]
            }
            
            # Test task retrieval
            tasks = await clickup.get_tasks(
                list_id="list_123",
                include_subtasks=True
            )
            
            assert len(tasks) == 1
            assert tasks[0]["id"] == "task_123"
            assert tasks[0]["name"] == "Test Task"
    
    async def test_task_creation(self):
        """Test creating tasks in ClickUp."""
        clickup = ClickUpIntegration()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "new_task_123",
                "name": "New Task"
            }
            
            # Create task
            task = await clickup.create_task(
                list_id="list_123",
                name="New Task",
                description="Task description",
                assignees=["user_123"]
            )
            
            assert task["id"] == "new_task_123"
            assert task["name"] == "New Task"


@pytest.mark.asyncio
class TestNotionIntegration:
    """Test Notion integration functionality."""
    
    async def test_database_query(self):
        """Test querying Notion databases."""
        notion = NotionIntegration()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock Notion API response
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "results": [
                    {
                        "id": "page_123",
                        "properties": {
                            "Name": {
                                "title": [{"plain_text": "Test Page"}]
                            }
                        }
                    }
                ],
                "has_more": False
            }
            
            # Query database
            pages = await notion.query_database(
                database_id="db_123",
                filter_properties={"Status": "Active"}
            )
            
            assert len(pages) == 1
            assert pages[0]["id"] == "page_123"
    
    async def test_page_creation(self):
        """Test creating pages in Notion."""
        notion = NotionIntegration()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "new_page_123"
            }
            
            # Create page
            page = await notion.create_page(
                parent_database_id="db_123",
                properties={
                    "Name": {"title": [{"text": {"content": "New Page"}}]},
                    "Status": {"select": {"name": "Active"}}
                }
            )
            
            assert page["id"] == "new_page_123"


@pytest.mark.asyncio
class TestMakeIntegration:
    """Test Make.com integration functionality."""
    
    async def test_webhook_authentication(self):
        """Test Make.com webhook authentication."""
        make = MakeIntegration()
        
        # Test with correct secret
        payload = MakeWebhookPayload(
            task_id="test_task",
            parameters={},
            webhook_secret=settings.MAKE_WEBHOOK_SECRET
        )
        
        # Should not raise exception
        try:
            await make.handle_webhook(payload)
        except Exception as e:
            # Only task not found error is expected
            assert "not found" in str(e).lower()
    
    async def test_scenario_triggering(self):
        """Test triggering Make.com scenarios."""
        make = MakeIntegration()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "executionId": "exec_123",
                "status": "success"
            }
            
            # Trigger scenario
            result = await make.trigger_scenario(
                scenario_id="scenario_123",
                data={"key": "value"}
            )
            
            assert result["executionId"] == "exec_123"
            assert result["status"] == "success"


@pytest.mark.asyncio
class TestStripeIntegration:
    """Test Stripe integration functionality."""
    
    async def test_webhook_signature_verification(self):
        """Test Stripe webhook signature verification."""
        stripe_integration = StripeIntegration()
        
        # Mock Stripe webhook construction
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = {
                "type": "customer.subscription.created",
                "data": {"object": {"id": "sub_123"}}
            }
            
            # Test webhook handling
            result = await stripe_integration.handle_webhook(
                payload='{"test": "data"}',
                signature="test_signature"
            )
            
            assert result["status"] == "processed"
            assert result["event_type"] == "customer.subscription.created"
    
    async def test_subscription_event_handling(self):
        """Test handling of subscription events."""
        stripe_integration = StripeIntegration()
        
        # Test subscription created event
        event = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "items": {
                        "data": [{"price": {"id": "price_123"}}]
                    }
                }
            }
        }
        
        with patch.object(stripe_integration.memory_store, 'add_knowledge') as mock_memory:
            await stripe_integration._handle_subscription_created(event)
            
            # Verify customer knowledge was stored
            mock_memory.assert_called()
            call_args = mock_memory.call_args[1]
            assert "subscription" in call_args["content"].lower()
            assert call_args["metadata"]["customer_id"] == "cus_123"
    
    async def test_payment_event_handling(self):
        """Test handling of payment events."""
        stripe_integration = StripeIntegration()
        
        # Test payment succeeded event
        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 10000,  # $100.00
                    "currency": "usd",
                    "customer": "cus_123"
                }
            }
        }
        
        with patch.object(stripe_integration, '_trigger_onboarding_sequence') as mock_onboard:
            await stripe_integration._handle_payment_succeeded(event)
            
            # Verify onboarding was triggered for new payment
            mock_onboard.assert_called_once_with("cus_123", 100.00)


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    from apps.backend.main import app
    return TestClient(app)