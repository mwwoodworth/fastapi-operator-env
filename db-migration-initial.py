"""
Initial database migration for BrainOps.
Creates all core tables, indexes, and functions required for the system.
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


def upgrade():
    """
    Create initial database schema for BrainOps.
    Includes all tables, custom types, indexes, and functions.
    """
    
    # Enable required PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')
    
    # Create custom enum types
    task_status_enum = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'cancelled',
        name='task_status'
    )
    task_status_enum.create(op.get_bind())
    
    agent_type_enum = postgresql.ENUM(
        'claude', 'codex', 'gemini', 'search', 'coordinator',
        name='agent_type'
    )
    agent_type_enum.create(op.get_bind())
    
    approval_status_enum = postgresql.ENUM(
        'pending', 'approved', 'rejected', 'auto_approved',
        name='approval_status'
    )
    approval_status_enum.create(op.get_bind())
    
    # Create tasks table - core task tracking
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('status', task_status_enum, server_default='pending'),
        sa.Column('context', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('result', postgresql.JSONB),
        sa.Column('error_message', sa.Text),
        sa.Column('created_by', sa.String(255)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('metadata', postgresql.JSONB, server_default='{}')
    )
    
    # Create indexes for tasks table
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_type', 'tasks', ['task_type'])
    op.create_index('idx_tasks_created_at', 'tasks', ['created_at'], postgresql_using='btree')
    
    # Create agent_executions table
    op.create_table(
        'agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('tasks.id', ondelete='CASCADE')),
        sa.Column('agent_type', agent_type_enum, nullable=False),
        sa.Column('input_data', postgresql.JSONB, nullable=False),
        sa.Column('output_data', postgresql.JSONB),
        sa.Column('error_message', sa.Text),
        sa.Column('execution_time_ms', sa.Integer),
        sa.Column('tokens_used', sa.Integer),
        sa.Column('cost_cents', sa.Integer),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for agent_executions
    op.create_index('idx_agent_exec_task', 'agent_executions', ['task_id'])
    op.create_index('idx_agent_exec_type', 'agent_executions', ['agent_type'])
    op.create_index('idx_agent_exec_created', 'agent_executions', ['created_at'])
    
    # Create memory_entries table with vector column
    op.create_table(
        'memory_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('namespace', sa.String(100), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('embedding', sa.Column('embedding', postgresql.ARRAY(sa.Float))),  # Vector type
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint('namespace', 'key', name='uq_memory_namespace_key')
    )
    
    # Create indexes for memory_entries
    op.create_index('idx_memory_namespace', 'memory_entries', ['namespace'])
    op.create_index('idx_memory_key', 'memory_entries', ['key'])
    op.create_index('idx_memory_updated', 'memory_entries', ['updated_at'])
    
    # Create vector similarity search index
    op.execute("""
        CREATE INDEX idx_memory_embedding ON memory_entries 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('source_url', sa.String(1000)),
        sa.Column('doc_type', sa.String(50)),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Add generated tsvector column for full-text search
    op.execute("""
        ALTER TABLE documents ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(content, '')), 'B')
        ) STORED;
    """)
    
    op.create_index('idx_documents_search', 'documents', ['search_vector'], 
                    postgresql_using='gin')
    
    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('documents.id', ondelete='CASCADE')),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', sa.Column('embedding', postgresql.ARRAY(sa.Float))),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_chunks_doc_index')
    )
    
    op.create_index('idx_chunks_document', 'document_chunks', ['document_id'])
    
    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('event_type', sa.String(100)),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('processed', sa.Boolean, server_default='false'),
        sa.Column('task_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tasks.id')),
        sa.Column('error_message', sa.Text),
        sa.Column('received_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True))
    )
    
    # Create indexes for webhook_events
    op.create_index('idx_webhooks_source', 'webhook_events', ['source'])
    op.create_index('idx_webhooks_processed', 'webhook_events', ['processed'])
    op.create_index('idx_webhooks_received', 'webhook_events', ['received_at'])
    
    # Create approval_queue table
    op.create_table(
        'approval_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tasks.id', ondelete='CASCADE')),
        sa.Column('approval_type', sa.String(100), nullable=False),
        sa.Column('request_data', postgresql.JSONB, nullable=False),
        sa.Column('status', approval_status_enum, server_default='pending'),
        sa.Column('approver_id', sa.String(255)),
        sa.Column('approval_notes', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('responded_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True))
    )
    
    # Create indexes for approval_queue
    op.create_index('idx_approvals_status', 'approval_queue', ['status'])
    op.create_index('idx_approvals_created', 'approval_queue', ['created_at'])
    
    # Create scheduled_tasks table
    op.create_table(
        'scheduled_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('schedule_expression', sa.String(255)),
        sa.Column('next_run_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_run_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('context', postgresql.JSONB, server_default='{}'),
        sa.Column('enabled', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for scheduled_tasks
    op.create_index('idx_scheduled_next_run', 'scheduled_tasks', ['next_run_at'])
    op.create_index('idx_scheduled_enabled', 'scheduled_tasks', ['enabled'])
    
    # Create update trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Apply update triggers
    op.execute("""
        CREATE TRIGGER update_memory_entries_updated_at 
        BEFORE UPDATE ON memory_entries
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_documents_updated_at 
        BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Create vector similarity search function
    op.execute("""
        CREATE OR REPLACE FUNCTION search_similar_memories(
            query_embedding vector(1536),
            match_namespace VARCHAR(100) DEFAULT NULL,
            match_count INT DEFAULT 10,
            match_threshold FLOAT DEFAULT 0.7
        )
        RETURNS TABLE (
            id UUID,
            namespace VARCHAR(100),
            key VARCHAR(255),
            content JSONB,
            similarity FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                m.id,
                m.namespace,
                m.key,
                m.content,
                1 - (m.embedding <=> query_embedding) AS similarity
            FROM memory_entries m
            WHERE 
                (match_namespace IS NULL OR m.namespace = match_namespace)
                AND (expires_at IS NULL OR expires_at > NOW())
                AND 1 - (m.embedding <=> query_embedding) > match_threshold
            ORDER BY m.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create full text document search function
    op.execute("""
        CREATE OR REPLACE FUNCTION search_documents(
            query_text TEXT,
            match_count INT DEFAULT 10
        )
        RETURNS TABLE (
            id UUID,
            title VARCHAR(500),
            content TEXT,
            rank FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                d.id,
                d.title,
                d.content,
                ts_rank(d.search_vector, plainto_tsquery('english', query_text)) AS rank
            FROM documents d
            WHERE d.search_vector @@ plainto_tsquery('english', query_text)
            ORDER BY rank DESC
            LIMIT match_count;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    """
    Drop all tables and custom types created in the upgrade.
    This completely removes the BrainOps schema.
    """
    
    # Drop functions first
    op.execute('DROP FUNCTION IF EXISTS search_documents(TEXT, INT);')
    op.execute('DROP FUNCTION IF EXISTS search_similar_memories(vector, VARCHAR, INT, FLOAT);')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column();')
    
    # Drop all tables (in reverse order of dependencies)
    op.drop_table('scheduled_tasks')
    op.drop_table('approval_queue')
    op.drop_table('webhook_events')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('memory_entries')
    op.drop_table('agent_executions')
    op.drop_table('tasks')
    
    # Drop custom enum types
    approval_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', 'auto_approved',
                                          name='approval_status')
    approval_status_enum.drop(op.get_bind())
    
    agent_type_enum = postgresql.ENUM('claude', 'codex', 'gemini', 'search', 'coordinator',
                                     name='agent_type')
    agent_type_enum.drop(op.get_bind())
    
    task_status_enum = postgresql.ENUM('pending', 'running', 'completed', 'failed', 'cancelled',
                                      name='task_status')
    task_status_enum.drop(op.get_bind())