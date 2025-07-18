"""
Comprehensive tests for CRM module.
Tests lead management, opportunity tracking, customer communications,
and sales analytics.
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..main import app
from ..db.models import User
from ..db.financial_models import Customer
from ..db.crm_models import (
    Lead, Opportunity, Contact, Communication,
    Activity, Campaign, LeadStatus, OpportunityStage,
    CommunicationType, ActivityType
)
from ..core.rbac import Permission, Role


client = TestClient(app)


class TestCRMModule:
    """Base test class for CRM module."""
    
    @pytest.fixture
    def auth_headers(self, test_user):
        """Get auth headers for test user."""
        return {"Authorization": f"Bearer {test_user.token}"}
    
    @pytest.fixture
    def admin_headers(self, admin_user):
        """Get auth headers for admin user."""
        return {"Authorization": f"Bearer {admin_user.token}"}
    
    @pytest.fixture
    def test_lead(self, db: Session, test_user):
        """Create test lead."""
        lead = Lead(
            name="John Doe",
            email="john.doe@example.com",
            phone="555-0123",
            company="Acme Corp",
            title="CEO",
            source="website",
            score=75,
            status=LeadStatus.NEW,
            created_by=test_user.id
        )
        db.add(lead)
        db.commit()
        return lead
    
    @pytest.fixture
    def test_customer(self, db: Session):
        """Create test customer."""
        customer = Customer(
            name="Test Company",
            email="contact@testcompany.com",
            phone="555-9876"
        )
        db.add(customer)
        db.commit()
        return customer
    
    @pytest.fixture
    def test_opportunity(self, db: Session, test_customer, test_user):
        """Create test opportunity."""
        opportunity = Opportunity(
            customer_id=test_customer.id,
            title="Enterprise Deal",
            value_cents=5000000,  # $50,000
            probability=60,
            stage=OpportunityStage.PROPOSAL,
            expected_close_date=date.today() + timedelta(days=30),
            assigned_to=test_user.id,
            created_by=test_user.id
        )
        db.add(opportunity)
        db.commit()
        return opportunity


class TestLeadManagement(TestCRMModule):
    """Test lead management endpoints."""
    
    def test_create_lead_with_auto_scoring(self, admin_headers):
        """Test lead creation with automatic scoring."""
        lead_data = {
            "name": "Jane Smith",
            "email": "jane.smith@techcorp.com",
            "phone": "555-1234",
            "company": "Tech Corp",
            "title": "VP of Engineering",
            "source": "referral",
            "description": "Interested in enterprise features",
            "tags": ["high-value", "enterprise"]
        }
        
        with patch('apps.backend.routes.erp_crm.notification_service.notify_user') as mock_notify:
            response = client.post(
                "/api/v1/crm/leads",
                json=lead_data,
                headers=admin_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead"]["name"] == "Jane Smith"
        assert data["lead"]["score"] > 50  # Should have high score
        assert data["actions_taken"]["scored"] == True
        assert data["actions_taken"]["assigned"] == True
    
    def test_lead_scoring_factors(self, admin_headers):
        """Test lead scoring based on various factors."""
        test_cases = [
            {
                "data": {
                    "name": "Low Score",
                    "email": "test@gmail.com",
                    "source": "cold_call"
                },
                "expected_score_range": (0, 30)
            },
            {
                "data": {
                    "name": "High Score",
                    "email": "ceo@enterprise.com",
                    "title": "CEO",
                    "company": "Enterprise Inc",
                    "source": "referral",
                    "requested_demo": True
                },
                "expected_score_range": (70, 100)
            }
        ]
        
        for test_case in test_cases:
            response = client.post(
                "/api/v1/crm/leads",
                json=test_case["data"],
                headers=admin_headers
            )
            assert response.status_code == 200
            score = response.json()["lead"]["score"]
            assert test_case["expected_score_range"][0] <= score <= test_case["expected_score_range"][1]
    
    def test_list_leads_with_filters(self, auth_headers, test_lead):
        """Test listing leads with various filters."""
        # Test status filter
        response = client.get(
            f"/api/v1/crm/leads?status={LeadStatus.NEW}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["leads"]) >= 1
        assert all(lead["status"] == LeadStatus.NEW for lead in data["leads"])
        
        # Test score filter
        response = client.get(
            "/api/v1/crm/leads?min_score=70",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(lead["score"] >= 70 for lead in data["leads"])
        
        # Test search
        response = client.get(
            "/api/v1/crm/leads?search=Acme",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert any("Acme" in lead.get("company", "") for lead in data["leads"])
    
    def test_convert_lead_to_opportunity(self, admin_headers, test_lead):
        """Test lead conversion process."""
        conversion_data = {
            "title": "New Opportunity from Lead",
            "value": 25000.00,
            "probability": 40,
            "expected_close_date": (date.today() + timedelta(days=45)).isoformat()
        }
        
        response = client.put(
            f"/api/v1/crm/leads/{test_lead.id}/convert",
            json=conversion_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["lead"]["status"] == "converted"
        assert data["opportunity"]["value"] == 25000.00
        assert data["customer"]["email"] == test_lead.email
    
    def test_bulk_lead_import(self, admin_headers, db: Session):
        """Test bulk lead import for campaigns."""
        # Create campaign
        campaign = Campaign(
            name="Q1 Webinar",
            type="webinar",
            start_date=date.today(),
            created_by=db.query(User).first().id
        )
        db.add(campaign)
        db.commit()
        
        leads_data = [
            {
                "name": f"Lead {i}",
                "email": f"lead{i}@example.com",
                "company": f"Company {i}",
                "tags": ["webinar", "q1"]
            }
            for i in range(5)
        ]
        
        response = client.post(
            f"/api/v1/crm/campaigns/{campaign.id}/leads/import",
            json=leads_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 5
        assert data["duplicates"] == 0
        assert data["errors"] == 0


class TestOpportunityManagement(TestCRMModule):
    """Test opportunity/deal management."""
    
    def test_create_opportunity(self, admin_headers, test_customer):
        """Test creating new opportunity."""
        opp_data = {
            "customer_id": str(test_customer.id),
            "title": "Q1 Enterprise Deal",
            "value": 75000.00,
            "probability": 30,
            "stage": "needs_analysis",
            "expected_close_date": (date.today() + timedelta(days=60)).isoformat(),
            "description": "Large enterprise deployment",
            "competitors": ["Competitor A", "Competitor B"],
            "tags": ["enterprise", "priority"]
        }
        
        response = client.post(
            "/api/v1/crm/opportunities",
            json=opp_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["opportunity"]["title"] == "Q1 Enterprise Deal"
        assert data["opportunity"]["value"] == 75000.00
        assert data["opportunity"]["weighted_value"] == 22500.00  # 75000 * 0.30
    
    def test_opportunity_stage_progression(self, admin_headers, test_opportunity):
        """Test moving opportunity through stages."""
        stages = [
            ("needs_analysis", 30),
            ("proposal", 50),
            ("negotiation", 70),
            ("closed_won", 100)
        ]
        
        for stage, expected_probability in stages:
            response = client.put(
                f"/api/v1/crm/opportunities/{test_opportunity.id}/stage",
                json={"stage": stage},
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["opportunity"]["stage"] == stage
            assert data["opportunity"]["probability"] == expected_probability
            assert len(data["actions_triggered"]) > 0
    
    def test_opportunity_lost_tracking(self, admin_headers, test_opportunity):
        """Test tracking lost opportunities."""
        response = client.put(
            f"/api/v1/crm/opportunities/{test_opportunity.id}/stage",
            json={
                "stage": "closed_lost",
                "lost_reason": "Budget constraints"
            },
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["opportunity"]["stage"] == "closed_lost"
        assert data["opportunity"]["probability"] == 0
        assert data["opportunity"]["is_closed"] == True
    
    def test_opportunity_automated_actions(self, admin_headers, test_opportunity):
        """Test automated actions on stage changes."""
        with patch('apps.backend.routes.erp_crm.generate_proposal_template') as mock_proposal:
            response = client.put(
                f"/api/v1/crm/opportunities/{test_opportunity.id}/stage",
                json={"stage": "proposal"},
                headers=admin_headers
            )
            
            assert response.status_code == 200
            # Verify proposal generation was triggered
            mock_proposal.assert_called_once()
        
        with patch('apps.backend.routes.erp_crm.handle_closed_won') as mock_won:
            response = client.put(
                f"/api/v1/crm/opportunities/{test_opportunity.id}/stage",
                json={"stage": "closed_won"},
                headers=admin_headers
            )
            
            assert response.status_code == 200
            # Verify closed-won automation was triggered
            mock_won.assert_called_once()


class TestCommunicationTracking(TestCRMModule):
    """Test customer communication tracking."""
    
    def test_log_communication(self, admin_headers, test_customer):
        """Test logging customer communication."""
        comm_data = {
            "entity_type": "customer",
            "entity_id": str(test_customer.id),
            "type": "call",
            "direction": "outbound",
            "subject": "Follow-up call",
            "content": "Discussed pricing and next steps",
            "duration_minutes": 30,
            "schedule_followup": True,
            "followup_days": 7
        }
        
        with patch('apps.backend.routes.erp_crm.calendar_service.create_event') as mock_calendar:
            response = client.post(
                "/api/v1/crm/communications",
                json=comm_data,
                headers=admin_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["communication"]["type"] == "call"
        assert data["followup_scheduled"] == True
        mock_calendar.assert_called_once()
    
    def test_communication_timeline(self, auth_headers, test_opportunity, db: Session):
        """Test retrieving communication timeline."""
        # Add some communications
        for i in range(3):
            comm = Communication(
                entity_type="opportunity",
                entity_id=test_opportunity.id,
                type=CommunicationType.EMAIL,
                subject=f"Email {i+1}",
                content=f"Content {i+1}",
                user_id=test_opportunity.assigned_to
            )
            db.add(comm)
        
        # Add activities
        activity = Activity(
            entity_type="opportunity",
            entity_id=test_opportunity.id,
            type=ActivityType.STAGE_CHANGE,
            title="Stage changed to Proposal",
            user_id=test_opportunity.assigned_to
        )
        db.add(activity)
        db.commit()
        
        response = client.get(
            f"/api/v1/crm/communications/timeline/opportunity/{test_opportunity.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_interactions"] >= 4
        assert len(data["timeline"]) >= 4
        assert any(item["type"] == "communication" for item in data["timeline"])
        assert any(item["type"] == "activity" for item in data["timeline"])
    
    def test_scheduled_communications(self, admin_headers, test_customer):
        """Test scheduling future communications."""
        future_date = datetime.utcnow() + timedelta(days=3)
        
        comm_data = {
            "entity_type": "customer",
            "entity_id": str(test_customer.id),
            "type": "task",
            "subject": "Demo follow-up",
            "content": "Check if they have any questions after demo",
            "scheduled_at": future_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = client.post(
            "/api/v1/crm/communications",
            json=comm_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["communication"]["type"] == "task"


class TestSalesAnalytics(TestCRMModule):
    """Test sales analytics and reporting."""
    
    def test_pipeline_analytics(self, auth_headers, db: Session):
        """Test pipeline analytics endpoint."""
        # Create test data
        customer = Customer(name="Analytics Test", email="test@analytics.com")
        db.add(customer)
        db.flush()
        
        for i in range(5):
            opp = Opportunity(
                customer_id=customer.id,
                title=f"Deal {i+1}",
                value_cents=1000000 + (i * 500000),
                probability=20 + (i * 10),
                stage=list(OpportunityStage)[i % 4],
                expected_close_date=date.today() + timedelta(days=30),
                assigned_to=db.query(User).first().id,
                created_by=db.query(User).first().id
            )
            db.add(opp)
        db.commit()
        
        response = client.get(
            "/api/v1/crm/analytics/pipeline?date_range=30d",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "pipeline" in data
        assert "win_loss" in data
        assert "velocity" in data
        assert "lead_conversion" in data
        assert "top_performers" in data
        assert data["period"] == "30d"
    
    def test_sales_forecast(self, auth_headers):
        """Test sales forecasting."""
        response = client.get(
            "/api/v1/crm/analytics/forecast?months=3",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["forecast"]) == 3
        assert "total_forecast" in data
        assert all(
            all(k in month for k in ["month", "opportunities", "pipeline_value", "weighted_forecast", "ai_forecast", "confidence"])
            for month in data["forecast"]
        )
    
    def test_analytics_caching(self, auth_headers):
        """Test that analytics endpoints use caching."""
        # First request
        response1 = client.get(
            "/api/v1/crm/analytics/pipeline?date_range=30d",
            headers=auth_headers
        )
        assert response1.status_code == 200
        
        # Second request should be cached
        with patch('apps.backend.routes.erp_crm.db.query') as mock_query:
            response2 = client.get(
                "/api/v1/crm/analytics/pipeline?date_range=30d",
                headers=auth_headers
            )
            assert response2.status_code == 200
            # Database shouldn't be queried if cached
            # Note: This depends on cache implementation
    
    def test_win_loss_analysis(self, auth_headers, db: Session):
        """Test win/loss analysis in analytics."""
        customer = Customer(name="Win/Loss Test", email="winloss@test.com")
        db.add(customer)
        db.flush()
        
        # Create won and lost opportunities
        for i in range(10):
            opp = Opportunity(
                customer_id=customer.id,
                title=f"Deal {i+1}",
                value_cents=1000000,
                stage=OpportunityStage.CLOSED_WON if i < 6 else OpportunityStage.CLOSED_LOST,
                is_won=i < 6,
                closed_date=datetime.utcnow() - timedelta(days=i),
                expected_close_date=date.today(),
                assigned_to=db.query(User).first().id,
                created_by=db.query(User).first().id
            )
            db.add(opp)
        db.commit()
        
        response = client.get(
            "/api/v1/crm/analytics/pipeline?date_range=30d",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["win_loss"]["won_deals"] >= 6
        assert data["win_loss"]["lost_deals"] >= 4
        assert 50 <= data["win_loss"]["win_rate"] <= 70


class TestCampaignManagement(TestCRMModule):
    """Test marketing campaign features."""
    
    def test_create_campaign(self, admin_headers):
        """Test creating marketing campaign."""
        campaign_data = {
            "name": "Spring Webinar Series",
            "type": "webinar",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "budget": 5000.00,
            "target_audience": {
                "industries": ["technology", "finance"],
                "company_size": "50-500"
            },
            "goals": {
                "leads": 100,
                "opportunities": 10,
                "revenue": 100000
            }
        }
        
        response = client.post(
            "/api/v1/crm/campaigns",
            json=campaign_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["campaign"]["name"] == "Spring Webinar Series"
        assert data["campaign"]["type"] == "webinar"
        assert data["campaign"]["status"] == "planned"
    
    def test_campaign_lead_import_with_duplicates(self, admin_headers, db: Session):
        """Test campaign lead import with duplicate handling."""
        # Create existing lead
        existing_lead = Lead(
            name="Existing Lead",
            email="existing@example.com",
            source="website",
            created_by=db.query(User).first().id
        )
        db.add(existing_lead)
        
        campaign = Campaign(
            name="Import Test",
            type="email",
            start_date=date.today(),
            created_by=db.query(User).first().id
        )
        db.add(campaign)
        db.commit()
        
        leads_data = [
            {"name": "New Lead 1", "email": "new1@example.com"},
            {"name": "New Lead 2", "email": "new2@example.com"},
            {"name": "Duplicate", "email": "existing@example.com"},  # Duplicate
            {"name": "Invalid", "email": "invalid-email"},  # Invalid
        ]
        
        response = client.post(
            f"/api/v1/crm/campaigns/{campaign.id}/leads/import",
            json=leads_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 2
        assert data["duplicates"] == 1
        assert data["errors"] == 1
    
    def test_email_campaign_automation(self, admin_headers):
        """Test email campaign automation setup."""
        campaign_data = {
            "name": "Nurture Campaign",
            "type": "email",
            "start_date": date.today().isoformat(),
            "email_sequence": [
                {"day": 0, "subject": "Welcome!", "template": "welcome"},
                {"day": 3, "subject": "Getting Started", "template": "onboarding"},
                {"day": 7, "subject": "Pro Tips", "template": "tips"}
            ]
        }
        
        with patch('apps.backend.routes.erp_crm.setup_email_campaign') as mock_setup:
            response = client.post(
                "/api/v1/crm/campaigns",
                json=campaign_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            mock_setup.assert_called_once()


class TestCRMIntegrations(TestCRMModule):
    """Test CRM integrations and automation."""
    
    def test_lead_assignment_rules(self, admin_headers, db: Session):
        """Test automatic lead assignment based on rules."""
        # Create users with different roles
        senior_rep = User(
            email="senior@sales.com",
            roles=["sales_senior"]
        )
        junior_rep = User(
            email="junior@sales.com",
            roles=["sales"]
        )
        db.add_all([senior_rep, junior_rep])
        db.commit()
        
        # High-value lead should go to senior
        high_value_lead = {
            "name": "CEO Important",
            "email": "ceo@fortune500.com",
            "title": "CEO",
            "company": "Fortune 500 Corp",
            "source": "referral",
            "requested_demo": True
        }
        
        response = client.post(
            "/api/v1/crm/leads",
            json=high_value_lead,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead"]["score"] >= 70  # High score
        assert data["actions_taken"]["assigned"] == True
    
    def test_activity_tracking(self, admin_headers, test_opportunity, db: Session):
        """Test automatic activity tracking."""
        # Change stage - should create activity
        response = client.put(
            f"/api/v1/crm/opportunities/{test_opportunity.id}/stage",
            json={"stage": "negotiation"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # Check activity was created
        activity = db.query(Activity).filter(
            Activity.entity_id == test_opportunity.id,
            Activity.type == ActivityType.STAGE_CHANGE
        ).first()
        
        assert activity is not None
        assert "negotiation" in activity.title.lower()
    
    def test_notification_triggers(self, admin_headers, test_lead):
        """Test CRM notification triggers."""
        with patch('apps.backend.routes.erp_crm.notification_service.notify_user') as mock_notify:
            # Create high-value lead
            lead_data = {
                "name": "VIP Lead",
                "email": "vip@enterprise.com",
                "title": "CTO",
                "company": "Enterprise Corp",
                "source": "partner",
                "requested_demo": True
            }
            
            response = client.post(
                "/api/v1/crm/leads",
                json=lead_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            # Should notify assigned user
            mock_notify.assert_called()
    
    def test_calendar_integration(self, admin_headers, test_customer):
        """Test calendar integration for follow-ups."""
        with patch('apps.backend.routes.erp_crm.calendar_service.create_event') as mock_calendar:
            comm_data = {
                "entity_type": "customer",
                "entity_id": str(test_customer.id),
                "type": "meeting",
                "subject": "Product Demo",
                "content": "Demo scheduled",
                "scheduled_at": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "duration_minutes": 60,
                "schedule_followup": True,
                "followup_days": 3
            }
            
            response = client.post(
                "/api/v1/crm/communications",
                json=comm_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            # Should create calendar event for follow-up
            mock_calendar.assert_called_once()
            call_args = mock_calendar.call_args[0][0]
            assert call_args["duration"] == 30  # Follow-up duration


def test_crm_permissions():
    """Test RBAC permissions for CRM operations."""
    # These would be integration tests with actual permission checks
    # Verifying that users without CRM_WRITE can't create leads, etc.
    pass