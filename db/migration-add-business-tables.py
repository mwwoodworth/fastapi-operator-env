"""
Add business-specific tables for BrainOps verticals.

Creates tables to support roofing estimates, project tracking, content
publishing, and customer management. These tables protect your business
data integrity and enable reliable decision-making under pressure.

Revision ID: 002_add_business_tables
Revises: 001_initial_schema
Create Date: 2024-01-14 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# Revision identifiers
revision = '002_add_business_tables'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create business-specific tables that protect operational data.
    
    These tables form the foundation for estimate accuracy, project
    tracking, and customer relationship management - critical systems
    that prevent costly mistakes and build trust at scale.
    """
    
    # Create roofing_estimates table - protects margin through accurate estimation
    op.create_table(
        'roofing_estimates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('estimate_number', sa.String(50), nullable=False, unique=True),
        sa.Column('project_name', sa.String(200), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=True),
        sa.Column('building_type', sa.String(50), nullable=False),  # commercial, industrial, institutional
        sa.Column('roof_area_sqft', sa.Integer, nullable=False),
        sa.Column('roof_type', sa.String(50), nullable=False),  # tpo, epdm, modified_bitumen, metal
        sa.Column('existing_condition', sa.String(50), nullable=False),  # excellent, good, fair, poor
        sa.Column('location', sa.String(200), nullable=False),
        
        # Special features that impact cost - prevents underestimation
        sa.Column('special_features', postgresql.JSON, default={}),  # hvac_units, skylights, drainage_issues
        
        # Financial data - the numbers that matter
        sa.Column('total_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('material_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('labor_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('overhead_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('profit_margin', sa.Numeric(5, 2), nullable=False),
        
        # Detailed breakdown for transparency and accuracy
        sa.Column('cost_breakdown', postgresql.JSON, nullable=False),  # Line items with descriptions
        sa.Column('timeline_days', sa.Integer, nullable=False),
        sa.Column('warranty_years', sa.Integer, default=20),
        
        # Status tracking - know where every estimate stands
        sa.Column('status', sa.String(50), default='draft'),  # draft, sent, approved, rejected, expired
        sa.Column('valid_until', sa.Date, nullable=False),
        
        # Audit trail - protect against disputes
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('sent_at', sa.DateTime, nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        
        # Notes and assumptions - critical context
        sa.Column('assumptions', sa.Text, nullable=True),
        sa.Column('exclusions', sa.Text, nullable=True),
        sa.Column('internal_notes', sa.Text, nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for fast, reliable queries when it matters
    op.create_index('idx_estimate_number', 'roofing_estimates', ['estimate_number'])
    op.create_index('idx_estimate_status', 'roofing_estimates', ['status'])
    op.create_index('idx_estimate_customer', 'roofing_estimates', ['customer_id'])
    op.create_index('idx_estimate_created', 'roofing_estimates', ['created_at'])
    
    # Create projects table - central tracking for all active work
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('project_code', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('vertical', sa.String(50), nullable=False),  # roofing, automation, project_management, passive_income
        sa.Column('customer_id', sa.String(100), nullable=True),
        sa.Column('estimate_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Project details
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('deliverables', postgresql.JSON, default=[]),
        sa.Column('milestones', postgresql.JSON, default=[]),
        
        # Timeline - prevents schedule drift
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('target_end_date', sa.Date, nullable=False),
        sa.Column('actual_end_date', sa.Date, nullable=True),
        
        # Status and progress tracking
        sa.Column('status', sa.String(50), default='planning'),  # planning, active, on_hold, completed, cancelled
        sa.Column('progress_percentage', sa.Integer, default=0),
        sa.Column('health_status', sa.String(50), default='green'),  # green, yellow, red
        
        # Financial tracking - know your numbers
        sa.Column('budget', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_cost', sa.Numeric(10, 2), default=0),
        sa.Column('revenue', sa.Numeric(10, 2), default=0),
        
        # Integration points
        sa.Column('clickup_task_id', sa.String(100), nullable=True),
        sa.Column('notion_page_id', sa.String(100), nullable=True),
        
        # Audit fields
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['estimate_id'], ['roofing_estimates.id'], ondelete='SET NULL')
    )
    
    # Indexes for project management efficiency
    op.create_index('idx_project_code', 'projects', ['project_code'])
    op.create_index('idx_project_status', 'projects', ['status'])
    op.create_index('idx_project_vertical', 'projects', ['vertical'])
    
    # Create content_assets table - manages all published content
    op.create_table(
        'content_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('content_type', sa.String(50), nullable=False),  # blog_post, template, guide, checklist
        sa.Column('vertical', sa.String(50), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('slug', sa.String(300), nullable=False, unique=True),
        
        # Content details
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('meta_description', sa.String(500), nullable=True),
        sa.Column('keywords', postgresql.JSON, default=[]),
        
        # SEO optimization data
        sa.Column('seo_score', sa.Integer, nullable=True),
        sa.Column('readability_score', sa.Integer, nullable=True),
        
        # Publishing workflow - control your content pipeline
        sa.Column('status', sa.String(50), default='draft'),  # draft, review, published, archived
        sa.Column('publish_date', sa.DateTime, nullable=True),
        sa.Column('last_updated', sa.DateTime, nullable=True),
        
        # Performance tracking - measure what matters
        sa.Column('views', sa.Integer, default=0),
        sa.Column('conversions', sa.Integer, default=0),
        sa.Column('engagement_score', sa.Float, nullable=True),
        
        # AI generation metadata
        sa.Column('ai_generated', sa.Boolean, default=False),
        sa.Column('generation_params', postgresql.JSON, nullable=True),
        sa.Column('human_edited', sa.Boolean, default=False),
        
        # Relationships
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Audit trail
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('updated_by', sa.String(100), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL')
    )
    
    # Indexes for content management
    op.create_index('idx_content_slug', 'content_assets', ['slug'])
    op.create_index('idx_content_status', 'content_assets', ['status'])
    op.create_index('idx_content_type', 'content_assets', ['content_type'])
    op.create_index('idx_content_vertical', 'content_assets', ['vertical'])
    
    # Create customers table - know who you're protecting
    op.create_table(
        'customers',
        sa.Column('id', sa.String(100), nullable=False),  # Can be Stripe ID or internal ID
        sa.Column('email', sa.String(200), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('company', sa.String(200), nullable=True),
        sa.Column('customer_type', sa.String(50), nullable=False),  # contractor, architect, owner, homeowner
        
        # Contact information
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', postgresql.JSON, nullable=True),
        
        # Business information - understand their context
        sa.Column('business_size', sa.String(50), nullable=True),  # small, medium, large, enterprise
        sa.Column('annual_volume', sa.String(50), nullable=True),  # revenue range
        sa.Column('primary_services', postgresql.JSON, default=[]),
        
        # Subscription and product data
        sa.Column('subscription_status', sa.String(50), default='none'),  # none, trial, active, cancelled
        sa.Column('subscription_tier', sa.String(50), nullable=True),
        sa.Column('products_purchased', postgresql.JSON, default=[]),
        
        # Engagement tracking - build better relationships
        sa.Column('last_interaction', sa.DateTime, nullable=True),
        sa.Column('lifetime_value', sa.Numeric(10, 2), default=0),
        sa.Column('support_tickets', sa.Integer, default=0),
        
        # Integration IDs
        sa.Column('stripe_customer_id', sa.String(100), nullable=True, unique=True),
        sa.Column('clickup_contact_id', sa.String(100), nullable=True),
        sa.Column('slack_user_id', sa.String(100), nullable=True),
        
        # Preferences and settings
        sa.Column('preferences', postgresql.JSON, default={}),
        sa.Column('notifications_enabled', sa.Boolean, default=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for customer queries
    op.create_index('idx_customer_email', 'customers', ['email'])
    op.create_index('idx_customer_stripe', 'customers', ['stripe_customer_id'])
    op.create_index('idx_customer_type', 'customers', ['customer_type'])
    
    # Create estimate_templates table - standardize excellence
    op.create_table(
        'estimate_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('template_code', sa.String(50), nullable=False, unique=True),
        sa.Column('roof_type', sa.String(50), nullable=False),
        sa.Column('building_type', sa.String(50), nullable=False),
        
        # Template configuration - build consistency
        sa.Column('base_pricing', postgresql.JSON, nullable=False),  # Material and labor rates
        sa.Column('markup_rules', postgresql.JSON, nullable=False),  # Overhead and profit calculations
        sa.Column('standard_inclusions', postgresql.JSON, default=[]),
        sa.Column('standard_exclusions', postgresql.JSON, default=[]),
        
        # Regional adjustments - location matters
        sa.Column('regional_factors', postgresql.JSON, default={}),
        
        # Usage tracking
        sa.Column('times_used', sa.Integer, default=0),
        sa.Column('last_used', sa.DateTime, nullable=True),
        sa.Column('success_rate', sa.Float, nullable=True),  # Percentage of estimates that convert
        
        # Template management
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('version', sa.Integer, default=1),
        
        # Audit fields
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Index for template lookups
    op.create_index('idx_template_code', 'estimate_templates', ['template_code'])
    op.create_index('idx_template_type', 'estimate_templates', ['roof_type', 'building_type'])


def downgrade() -> None:
    """
    Remove business tables - handle with care in production.
    
    This will remove all business data. Ensure proper backups
    before executing in any environment with real data.
    """
    # Drop tables in reverse order to respect foreign keys
    op.drop_table('estimate_templates')
    op.drop_table('customers')
    op.drop_table('content_assets')
    op.drop_table('projects')
    op.drop_table('roofing_estimates')