"""
Business domain models for BrainOps database.

Defines models for users, teams, projects, products, billing, and field operations.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text, Integer, ForeignKey, Index, Float, Enum as SQLEnum, Table
from sqlalchemy.orm import relationship
import uuid
import enum

from .models import Base
from .types import UUID


# Association tables for many-to-many relationships
team_members = Table('team_members', Base.metadata,
    Column('team_id', UUID(as_uuid=True), ForeignKey('teams.id')),
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id')),
    Column('role', String(50), default='member'),
    Column('joined_at', DateTime, default=datetime.utcnow),
    extend_existing=True
)

project_members = Table('project_members', Base.metadata,
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id')),
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id')),
    Column('role', String(50), default='member'),
    Column('joined_at', DateTime, default=datetime.utcnow),
    extend_existing=True
)


class UserRole(enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    USER = "user"
    VIEWER = "viewer"


class SubscriptionTier(enum.Enum):
    """Subscription tier enumeration."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class User(Base):
    """
    User model for authentication and profile management.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile information
    full_name = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    is_seller = Column(Boolean, default=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # Security
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    two_factor_secret_temp = Column(String(255), nullable=True)
    two_factor_backup_codes = Column(JSON, default=[])
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Password reset
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    teams = relationship("Team", secondary=team_members, back_populates="members")
    owned_teams = relationship("Team", back_populates="owner")
    projects = relationship("Project", secondary=project_members, back_populates="members")
    owned_projects = relationship("Project", back_populates="owner")
    tasks = relationship("ProjectTask", foreign_keys="ProjectTask.assignee_id", back_populates="assignee")
    created_tasks = relationship("ProjectTask", foreign_keys="ProjectTask.created_by", back_populates="creator")
    api_keys = relationship("APIKey", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    estimates = relationship("Estimate", back_populates="created_by")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_email_active", "email", "is_active"),
        Index("idx_user_role", "role"),
    )


class Team(Base):
    """
    Team/Organization model for grouping users.
    """
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Team settings
    logo_url = Column(String(500), nullable=True)
    website = Column(String(255), nullable=True)
    max_members = Column(Integer, default=5)
    
    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_teams")
    members = relationship("User", secondary=team_members, back_populates="teams")
    projects = relationship("Project", back_populates="team")


class Project(Base):
    """
    Project model for organizing work.
    """
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Project metadata
    project_type = Column(String(50), default="general")  # general, roofing, automation, etc.
    status = Column(String(50), default="active")  # active, completed, archived
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    
    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # Project details
    start_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    
    # Custom fields
    meta_data = Column(JSON, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="owned_projects")
    team = relationship("Team", back_populates="projects")
    members = relationship("User", secondary=project_members, back_populates="projects")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project")
    
    # Indexes
    __table_args__ = (
        Index("idx_project_status", "status"),
        Index("idx_project_owner_status", "owner_id", "status"),
    )


class ProjectTask(Base):
    """
    Task model for project management.
    """
    __tablename__ = "project_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Task details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="todo")  # todo, in_progress, review, done
    priority = Column(String(20), default="medium")
    
    # Assignment
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timing
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_hours = Column(Float, nullable=True)
    actual_hours = Column(Float, nullable=True)
    
    # Task metadata
    tags = Column(JSON, default=[])
    checklist = Column(JSON, default=[])
    attachments = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="tasks")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_tasks")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_task_project_status", "project_id", "status"),
        Index("idx_task_assignee", "assignee_id"),
    )


class TaskComment(Base):
    """
    Comment model for task discussions.
    """
    __tablename__ = "task_comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    attachments = Column(JSON, default=[])
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    task = relationship("ProjectTask", back_populates="comments")
    user = relationship("User")


class Product(Base):
    """
    Digital product model for marketplace.
    """
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(300), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Product details
    category = Column(String(100), nullable=False)
    product_type = Column(String(50), default="digital")  # digital, service, template
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    
    # Product files/content
    files = Column(JSON, default=[])
    file_url = Column(String(500), nullable=True)
    preview_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Product metadata
    features = Column(JSON, default=[])
    requirements = Column(JSON, default=[])
    tags = Column(JSON, default=[])
    
    # Publishing
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    
    # Stats
    view_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    rating_average = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    downloads = Column(Integer, default=0)
    
    # Version
    version = Column(String(20), default="1.0.0")
    
    # Status
    status = Column(String(50), default="pending")  # pending, approved, rejected
    is_deleted = Column(Boolean, default=False)
    
    # Ownership
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    seller = relationship("User")
    purchases = relationship("Purchase", back_populates="product")
    
    # Indexes
    __table_args__ = (
        Index("idx_product_category", "category"),
        Index("idx_product_published", "is_published"),
    )


class Purchase(Base):
    """
    Purchase/Order model for marketplace transactions.
    """
    __tablename__ = "purchases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Purchase details
    amount = Column(Float, nullable=False)  # Add amount alias for price
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(50), default="pending")  # pending, completed, refunded
    transaction_id = Column(String(255), nullable=True)
    
    # Payment information
    payment_method = Column(String(50))  # stripe, paypal, etc.
    payment_id = Column(String(255), nullable=True)
    
    # License
    license_key = Column(String(255), unique=True, nullable=True)
    license_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="purchases")
    buyer = relationship("User")


class Review(Base):
    """
    Product review model for marketplace feedback.
    """
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Review content
    rating = Column(Integer, nullable=False)  # 1-5 stars
    title = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)
    title = Column(String(200), nullable=True)
    
    # Review metadata
    is_verified_purchase = Column(Boolean, default=False)
    helpful_count = Column(Integer, default=0)
    pros = Column(JSON, default=[])
    cons = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = relationship("Product")
    reviewer = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_review_product", "product_id"),
        Index("idx_review_rating", "rating"),
    )


class Subscription(Base):
    """
    User subscription model for SaaS billing.
    """
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    # Subscription details
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    status = Column(String(50), default="active")  # active, canceled, expired
    
    # Billing
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    
    # Limits
    monthly_ai_requests = Column(Integer, default=100)
    used_ai_requests = Column(Integer, default=0)
    storage_limit_gb = Column(Float, default=1.0)
    used_storage_gb = Column(Float, default=0.0)
    monthly_budget = Column(Float, default=100.0)  # Monthly budget in USD
    
    # Dates
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscription")


class APIKey(Base):
    """
    API key model for programmatic access.
    """
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    name = Column(String(200), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    prefix = Column(String(20), nullable=False)  # Visible prefix for identification
    
    # Permissions
    scopes = Column(JSON, default=[])
    
    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")


class UserSession(Base):
    """
    Active user session tracking.
    """
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Session data
    refresh_token_hash = Column(String(255), unique=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class Document(Base):
    """
    Document model for file management.
    """
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    title = Column(String(500), nullable=True)  # For AI-generated documents
    
    # File details
    file_path = Column(String(1000), nullable=True)  # Optional for AI-generated
    file_size = Column(Integer, nullable=True)  # Optional for AI-generated
    mime_type = Column(String(100), nullable=True)  # Optional for AI-generated
    
    # AI-generated document fields
    document_type = Column(String(50), nullable=True)  # report, proposal, etc.
    content = Column(Text, nullable=True)  # Document content
    format = Column(String(20), nullable=True)  # markdown, html, pdf
    
    # Organization
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Processing
    is_processed = Column(Boolean, default=False)
    extracted_text = Column(Text, nullable=True)
    meta_data = Column(JSON, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="documents")
    owner = relationship("User")


class Notification(Base):
    """
    User notification model.
    """
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Notification content
    type = Column(String(50), nullable=False)  # task_assigned, comment, mention, etc.
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    
    # Metadata
    data = Column(JSON, default={})
    action_url = Column(String(500), nullable=True)
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index("idx_notification_user_unread", "user_id", "is_read"),
    )


# Field Operations Models (Roofing specific)

class Inspection(Base):
    """
    Roofing inspection model.
    """
    __tablename__ = "inspections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    
    # Inspection details
    property_address = Column(Text, nullable=False)
    inspector_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Status
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, completed
    
    # Inspection data
    roof_type = Column(String(100), nullable=True)
    roof_age = Column(Integer, nullable=True)
    measurements = Column(JSON, default={})
    damage_assessment = Column(JSON, default={})
    recommendations = Column(Text, nullable=True)
    
    # Timestamps
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project")
    inspector = relationship("User")
    photos = relationship("InspectionPhoto", back_populates="inspection")
    estimate = relationship("Estimate", back_populates="inspection", uselist=False)


class InspectionPhoto(Base):
    """
    Photos from roofing inspections.
    """
    __tablename__ = "inspection_photos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(UUID(as_uuid=True), ForeignKey("inspections.id"), nullable=False)
    
    # Photo details
    file_path = Column(String(1000), nullable=False)
    thumbnail_path = Column(String(1000), nullable=True)
    
    # Metadata
    caption = Column(Text, nullable=True)
    location = Column(JSON, nullable=True)  # GPS coordinates
    tags = Column(JSON, default=[])
    
    # AI analysis
    ai_analysis = Column(JSON, nullable=True)
    damage_detected = Column(Boolean, default=False)
    
    # Timestamps
    taken_at = Column(DateTime, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    inspection = relationship("Inspection", back_populates="photos")


class Estimate(Base):
    """
    Roofing estimate/quote model.
    """
    __tablename__ = "estimates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(UUID(as_uuid=True), ForeignKey("inspections.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    
    # Estimate details
    estimate_number = Column(String(50), unique=True, nullable=False)
    client_name = Column(String(200), nullable=False)
    client_email = Column(String(255), nullable=True)
    client_phone = Column(String(50), nullable=True)
    
    # Pricing
    subtotal = Column(Float, nullable=False)
    tax_rate = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    
    # Line items
    line_items = Column(JSON, nullable=False)  # Array of items with description, quantity, price
    
    # Status
    status = Column(String(50), default="draft")  # draft, sent, approved, rejected, expired
    
    # Validity
    valid_until = Column(DateTime, nullable=True)
    
    # User who created the estimate
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    sent_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    inspection = relationship("Inspection", back_populates="estimate")
    project = relationship("Project")
    created_by = relationship("User", foreign_keys=[created_by_id])


class Integration(Base):
    """
    Third-party integration configurations.
    """
    __tablename__ = "integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Integration details
    type = Column(String(50), nullable=False)  # slack, clickup, notion, etc.
    name = Column(String(200), nullable=False)
    
    # Configuration
    config = Column(JSON, nullable=False)  # Encrypted sensitive data
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSON, default={})
    
    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # Webhook
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    
    # Timestamps
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # Alias for compatibility
    last_synced_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)  # Alias for compatibility
    
    # Relationships
    user = relationship("User")


class Workflow(Base):
    """
    Automation workflow definitions.
    """
    __tablename__ = "workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Workflow definition
    trigger_type = Column(String(50), nullable=False)  # webhook, schedule, manual
    trigger_config = Column(JSON, nullable=False)
    steps = Column(JSON, nullable=False)  # Array of workflow steps
    
    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)
    
    # Additional attributes
    tags = Column(JSON, default=[])
    meta_data = Column(JSON, default={})
    version = Column(String(20), default="1.0.0")
    
    # Stats
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    last_run_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User")
    team = relationship("Team")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")


class Memory(Base):
    """
    User memory model for storing context and knowledge.
    """
    __tablename__ = "memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Memory content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    memory_type = Column(String(50), default="general")  # general, conversation, document, preference
    
    # Metadata
    tags = Column(JSON, default=[])
    meta_data = Column(JSON, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    
    # Vector embedding (if using vector search)
    embedding = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_memory_user", "user_id"),
        Index("idx_memory_type", "memory_type"),
    )


class WorkflowRun(Base):
    """
    Workflow execution history.
    """
    __tablename__ = "workflow_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    
    # Execution details
    status = Column(String(50), default="running")  # running, completed, failed
    trigger_data = Column(JSON, nullable=True)
    
    # Results
    steps_completed = Column(Integer, default=0)
    steps_total = Column(Integer, nullable=False)
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    logs = Column(JSON, default=[])
    
    # Retry tracking
    parent_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="runs")


class DocumentTemplate(Base):
    """
    Document template for AI-powered document generation.
    """
    __tablename__ = "document_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Template details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    template_type = Column(String(50), nullable=True)  # report, proposal, email, etc.
    document_type = Column(String(50), nullable=True)  # Alias for compatibility
    
    # Template content
    template_content = Column(Text, nullable=False)
    template = Column(Text, nullable=False)  # Alias for compatibility
    variables = Column(JSON, default={})  # Variables that can be filled in
    example_context = Column(JSON, default={})  # Example context for variables
    example_output = Column(Text, nullable=True)
    
    # Settings
    is_public = Column(Boolean, default=False)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")


class AIUsageLog(Base):
    """
    AI service usage tracking for billing and analytics.
    """
    __tablename__ = "ai_usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Usage details
    service = Column(String(50), nullable=False)  # openai, anthropic, google, etc.
    model = Column(String(100), nullable=False)  # gpt-4, claude-3, etc.
    endpoint = Column(String(200), nullable=False)  # /chat, /completions, etc.
    request_type = Column(String(50), nullable=True)  # chat, analysis, generation, etc.
    
    # Metrics
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)  # Alias for compatibility
    
    # Cost tracking
    input_cost = Column(Float, default=0.0)
    output_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    
    # Request details
    request_id = Column(String(255), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    
    # Metadata
    meta_data = Column(JSON, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_ai_usage_user_created", "user_id", "created_at"),
        Index("idx_ai_usage_service_model", "service", "model"),
    )


class SystemConfig(Base):
    """
    Model for storing system configuration and feature flags.
    
    Key-value store for runtime configuration that can be updated
    without redeploying the application.
    """
    __tablename__ = "system_config"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    
    # Configuration metadata
    config_type = Column(String(50), default="general")  # general, feature_flag, integration
    is_secret = Column(Boolean, default=False)
    
    # Audit fields
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)

