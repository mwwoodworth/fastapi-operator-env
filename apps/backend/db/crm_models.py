"""
CRM (Customer Relationship Management) domain models.
Handles leads, opportunities, contacts, communications, and sales analytics.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text, Integer, ForeignKey, Index, Float, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from enum import Enum

from .models import Base


class LeadStatus(str, Enum):
    """Lead lifecycle status."""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"
    LOST = "lost"


class OpportunityStage(str, Enum):
    """Sales opportunity stages."""
    QUALIFICATION = "qualification"
    NEEDS_ANALYSIS = "needs_analysis"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class CommunicationType(str, Enum):
    """Types of customer communications."""
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"
    SMS = "sms"


class ActivityType(str, Enum):
    """Types of CRM activities."""
    LEAD_CREATED = "lead_created"
    LEAD_CONVERSION = "lead_conversion"
    STAGE_CHANGE = "stage_change"
    COMMUNICATION = "communication"
    TASK_COMPLETED = "task_completed"
    DEAL_WON = "deal_won"
    DEAL_LOST = "deal_lost"


class Lead(Base):
    """Sales lead model."""
    __tablename__ = "leads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Contact info
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(200), nullable=True)
    title = Column(String(100), nullable=True)
    
    # Lead details
    source = Column(String(50), nullable=False)  # website, referral, event, etc.
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    score = Column(Integer, default=0)  # 0-100 lead score
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW)
    
    # Assignment
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Additional info
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=[])
    custom_fields = Column(JSON, default={})
    
    # Conversion tracking
    converted_to_opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True)
    converted_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    created_by_user = relationship("User", foreign_keys=[created_by])
    campaign = relationship("Campaign", back_populates="leads")
    communications = relationship("Communication", 
                                primaryjoin="and_(Communication.entity_type=='lead', "
                                           "Communication.entity_id==Lead.id)",
                                foreign_keys="[Communication.entity_id]",
                                viewonly=True)
    
    __table_args__ = (
        Index("idx_lead_status", "status"),
        Index("idx_lead_score", "score"),
        Index("idx_lead_source", "source"),
        Index("idx_lead_assigned", "assigned_to"),
        {'extend_existing': True}
    )


class Opportunity(Base):
    """Sales opportunity/deal model."""
    __tablename__ = "opportunities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    
    # Opportunity details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Value and probability
    value_cents = Column(Integer, nullable=False)  # Deal value in cents
    probability = Column(Integer, default=20)  # 0-100 probability of closing
    
    # Stage and dates
    stage = Column(SQLEnum(OpportunityStage), default=OpportunityStage.QUALIFICATION)
    expected_close_date = Column(Date, nullable=False)
    closed_date = Column(DateTime, nullable=True)
    
    # Assignment
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Win/Loss tracking
    is_won = Column(Boolean, nullable=True)
    lost_reason = Column(String(100), nullable=True)
    competitors = Column(JSON, default=[])
    
    # Additional info
    tags = Column(JSON, default=[])
    custom_fields = Column(JSON, default={})
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="opportunities")
    lead = relationship("Lead")
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    created_by_user = relationship("User", foreign_keys=[created_by])
    activities = relationship("Activity", 
                            primaryjoin="and_(Activity.entity_type=='opportunity', "
                                       "Activity.entity_id==Opportunity.id)",
                            foreign_keys="[Activity.entity_id]",
                            viewonly=True)
    
    __table_args__ = (
        Index("idx_opportunity_stage", "stage"),
        Index("idx_opportunity_assigned", "assigned_to"),
        Index("idx_opportunity_close_date", "expected_close_date"),
        Index("idx_opportunity_customer", "customer_id"),
        {'extend_existing': True}
    )


class Contact(Base):
    """Customer contact person model."""
    __tablename__ = "contacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Contact info
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    mobile = Column(String(50), nullable=True)
    title = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    
    # Preferences
    preferred_contact_method = Column(String(20), default="email")
    do_not_contact = Column(Boolean, default=False)
    
    # Additional info
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=[])
    
    # Status
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="contacts")
    
    __table_args__ = (
        Index("idx_contact_customer", "customer_id"),
        Index("idx_contact_email", "email"),
        {'extend_existing': True}
    )


class Communication(Base):
    """Customer communication log."""
    __tablename__ = "communications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Entity reference (polymorphic)
    entity_type = Column(String(20), nullable=False)  # lead, opportunity, customer
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Communication details
    type = Column(SQLEnum(CommunicationType), nullable=False)
    direction = Column(String(10), default="outbound")  # inbound, outbound
    subject = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    
    # Call specific
    duration_minutes = Column(Integer, nullable=True)
    
    # Task specific
    is_completed = Column(Boolean, default=True)
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Attachments
    attachments = Column(JSON, default=[])
    
    # User
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    
    __table_args__ = (
        Index("idx_communication_entity", "entity_type", "entity_id"),
        Index("idx_communication_type", "type"),
        Index("idx_communication_user", "user_id"),
        Index("idx_communication_scheduled", "scheduled_at"),
        {'extend_existing': True}
    )


class Activity(Base):
    """CRM activity tracking."""
    __tablename__ = "activities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Entity reference (polymorphic)
    entity_type = Column(String(20), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Activity details
    type = Column(SQLEnum(ActivityType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Metadata
    activity_metadata = Column("metadata", JSON, default={})
    
    # User
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    
    __table_args__ = (
        Index("idx_activity_entity", "entity_type", "entity_id"),
        Index("idx_activity_type", "type"),
        Index("idx_activity_user", "user_id"),
        Index("idx_activity_created", "created_at"),
        {'extend_existing': True}
    )


class Campaign(Base):
    """Marketing campaign model."""
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Campaign info
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)  # email, event, webinar, content, social
    description = Column(Text, nullable=True)
    
    # Dates
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    
    # Budget
    budget_cents = Column(Integer, default=0)
    actual_cost_cents = Column(Integer, default=0)
    
    # Targeting
    target_audience = Column(JSON, default={})
    
    # Goals and metrics
    goals = Column(JSON, default={})
    leads_generated = Column(Integer, default=0)
    opportunities_created = Column(Integer, default=0)
    revenue_attributed_cents = Column(Integer, default=0)
    
    # Content
    content_urls = Column(JSON, default=[])
    email_templates = Column(JSON, default=[])
    
    # Status
    status = Column(String(20), default="planned")  # planned, active, completed, cancelled
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    leads = relationship("Lead", back_populates="campaign")
    created_by_user = relationship("User")
    
    __table_args__ = (
        Index("idx_campaign_status", "status"),
        Index("idx_campaign_dates", "start_date", "end_date"),
        Index("idx_campaign_type", "type"),
        {'extend_existing': True}
    )


class SalesGoal(Base):
    """Sales goals and quotas."""
    __tablename__ = "sales_goals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Goal scope
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # Period
    period_type = Column(String(20), nullable=False)  # monthly, quarterly, yearly
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Targets
    revenue_target_cents = Column(Integer, nullable=False)
    deals_target = Column(Integer, nullable=True)
    activities_target = Column(Integer, nullable=True)
    
    # Actuals (updated regularly)
    revenue_actual_cents = Column(Integer, default=0)
    deals_actual = Column(Integer, default=0)
    activities_actual = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        Index("idx_sales_goal_user", "user_id"),
        Index("idx_sales_goal_period", "period_start", "period_end"),
        {'extend_existing': True}
    )


class CustomerSegment(Base):
    """Customer segmentation for targeted marketing."""
    __tablename__ = "customer_segments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Segment info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Criteria (JSON query)
    criteria = Column(JSON, nullable=False)
    
    # Cached members
    member_count = Column(Integer, default=0)
    last_calculated = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User")
    
    __table_args__ = {'extend_existing': True}


class LeadSource(Base):
    """Lead source tracking and analytics."""
    __tablename__ = "lead_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source info
    name = Column(String(50), unique=True, nullable=False)
    category = Column(String(50), nullable=False)  # organic, paid, referral, etc.
    
    # Metrics (updated regularly)
    total_leads = Column(Integer, default=0)
    qualified_leads = Column(Integer, default=0)
    converted_leads = Column(Integer, default=0)
    total_revenue_cents = Column(Integer, default=0)
    
    # Cost tracking
    cost_cents = Column(Integer, default=0)
    
    # Calculated metrics
    conversion_rate = Column(Float, default=0.0)
    cost_per_lead = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_lead_source_category", "category"),
        {'extend_existing': True}
    )