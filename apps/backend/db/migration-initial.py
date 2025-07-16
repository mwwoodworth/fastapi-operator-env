"""
Initial database schema migration.

Creates the foundational tables for BrainOps: task executions, agent logs,
memory entries, webhook events, and system configuration. This migration
establishes the core data model that powers all system operations.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# Revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create initial database schema for BrainOps.
    
    Establishes tables for task tracking, agent execution logging,
    memory system with vector support, and operational infrastructure.
    """
    
    # Enable pgvector extension for similarity search
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create task_executions table
    op.create_table(
        'task_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('task_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('parameters', postgresql.JSON, nullable=True, default={}),
        sa.Column('result', postgresql.JSON, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('triggered_by', sa.String(100), nullable=True),
        sa.Column('trigger_source', sa.String(200), nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for task_executions
    op.create_index('idx_task_status', 'task_executions', ['task_id', 'status'])
    op.create_index('idx_task_created_at', 'task_executions', ['created_at'])
    
    # Create agent_executions table
    op.create_table(
        'agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('task_execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('response', sa.Text, nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('tokens_input', sa.Integer, default=0),
        sa.Column('tokens_output', sa.Integer, default=0),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('cost_cents', sa.Integer, default=0),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_execution_id'], ['task_executions.id'], ondelete='CASCADE')
    )
    
    # Create memory_entries table with vector support
    op.create_table(
        'memory_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('memory_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSON, default={}),
        sa.Column('embedding', postgresql.ARRAY(sa.Float, dimensions=1), nullable=True),  # For pgvector
        sa.Column('user_id', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('source', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('tags', postgresql.JSON, default=[]),
        sa.Column('importance_score', sa.Integer, default=5),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for memory_entries
    op.create_index('idx_memory_type_user', 'memory_entries', ['memory_type', 'user_id'])
    op.create_index('idx_memory_session', 'memory_entries', ['session_id'])
    op.create_index('idx_memory_importance', 'memory_entries', ['importance_score'])
    
    # Create vector similarity search index (requires pgvector)
    op.execute("""
        CREATE INDEX idx_memory_embedding ON memory_entries 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    
    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('headers', postgresql.JSON, default={}),
        sa.Column('payload', postgresql.JSON, nullable=False),
        sa.Column('signature', sa.String(500), nullable=True),
        sa.Column('processed', sa.Boolean, default=False),
        sa.Column('processing_result', postgresql.JSON, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('received_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('task_execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_execution_id'], ['task_executions.id'], ondelete='SET NULL')
    )
    
    # Create indexes for webhook_events
    op.create_index('idx_webhook_source', 'webhook_events', ['source'])
    op.create_index('idx_webhook_processed', 'webhook_events', ['processed'])
    
    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSON, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('config_type', sa.String(50), default='general'),
        sa.Column('is_secret', sa.Boolean, default=False),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )
    
    # Create search function for memory similarity search
    op.execute("""
        CREATE OR REPLACE FUNCTION search_memories(
            query_embedding vector(1536),
            match_count int,
            memory_types text[],
            similarity_threshold float
        )
        RETURNS TABLE (
            id uuid,
            content text,
            metadata jsonb,
            memory_type text,
            similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                m.id,
                m.content,
                m.metadata,
                m.memory_type,
                1 - (m.embedding <=> query_embedding) as similarity
            FROM memory_entries m
            WHERE 
                m.memory_type = ANY(memory_types)
                AND (m.expires_at IS NULL OR m.expires_at > NOW())
                AND 1 - (m.embedding <=> query_embedding) > similarity_threshold
            ORDER BY m.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
    """)
    
    # Insert initial system configuration
    op.execute("""
        INSERT INTO system_config (key, value, description, config_type)
        VALUES 
            ('max_task_retries', '3', 'Maximum number of retries for failed tasks', 'general'),
            ('memory_retention_days', '90', 'Default retention period for memory entries', 'general'),
            ('webhook_timeout_seconds', '30', 'Timeout for webhook processing', 'general'),
            ('enable_cost_tracking', 'true', 'Track costs for AI agent executions', 'feature_flag'),
            ('enable_memory_compression', 'false', 'Compress embeddings for storage optimization', 'feature_flag');
    """)


def downgrade() -> None:
    """
    Remove all tables created in this migration.
    
    This will destroy all data - use with caution in production.
    """
    # Drop search function
    op.execute('DROP FUNCTION IF EXISTS search_memories')
    
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table('system_config')
    op.drop_table('webhook_events')
    op.drop_table('memory_entries')
    op.drop_table('agent_executions')
    op.drop_table('task_executions')
    
    # Drop pgvector extension if no other tables use it
    op.execute('DROP EXTENSION IF EXISTS vector')