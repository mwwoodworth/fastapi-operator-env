-- BrainOps Database Schema for Supabase/PostgreSQL
-- Includes tables for tasks, memory, agent execution logs, and integrations

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types
CREATE TYPE task_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE agent_type AS ENUM ('claude', 'codex', 'gemini', 'search', 'coordinator');
CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected', 'auto_approved');

-- Tasks table: Core task execution tracking
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(100) NOT NULL,
    status task_status DEFAULT 'pending',
    context JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error_message TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    
    -- Indexes for common queries
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_type (task_type),
    INDEX idx_tasks_created_at (created_at DESC)
);

-- Agent executions: Track individual agent calls within tasks
CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    agent_type agent_type NOT NULL,
    input_data JSONB NOT NULL,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    tokens_used INTEGER,
    cost_cents INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Performance tracking
    INDEX idx_agent_exec_task (task_id),
    INDEX idx_agent_exec_type (agent_type),
    INDEX idx_agent_exec_created (created_at DESC)
);

-- Memory entries: Knowledge base and context storage
CREATE TABLE IF NOT EXISTS memory_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace VARCHAR(100) NOT NULL,
    key VARCHAR(255) NOT NULL,
    content JSONB NOT NULL,
    embedding vector(1536), -- OpenAI embeddings dimension
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Unique constraint on namespace + key
    UNIQUE(namespace, key),
    
    -- Indexes for retrieval
    INDEX idx_memory_namespace (namespace),
    INDEX idx_memory_key (key),
    INDEX idx_memory_updated (updated_at DESC)
);

-- Create vector similarity search index
CREATE INDEX idx_memory_embedding ON memory_entries 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Documents: Larger text documents for knowledge base
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    source_url VARCHAR(1000),
    doc_type VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Full text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) STORED,
    
    INDEX idx_documents_search USING GIN (search_vector)
);

-- Document chunks: For RAG retrieval
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    
    -- Ensure chunks are ordered
    UNIQUE(document_id, chunk_index),
    INDEX idx_chunks_document (document_id)
);

-- Webhook events: Track incoming webhooks
CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50) NOT NULL, -- 'slack', 'clickup', 'stripe', 'make'
    event_type VARCHAR(100),
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    task_id UUID REFERENCES tasks(id),
    error_message TEXT,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    INDEX idx_webhooks_source (source),
    INDEX idx_webhooks_processed (processed),
    INDEX idx_webhooks_received (received_at DESC)
);

-- Approval queue: Human-in-the-loop approvals
CREATE TABLE IF NOT EXISTS approval_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    approval_type VARCHAR(100) NOT NULL,
    request_data JSONB NOT NULL,
    status approval_status DEFAULT 'pending',
    approver_id VARCHAR(255),
    approval_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    responded_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    INDEX idx_approvals_status (status),
    INDEX idx_approvals_created (created_at DESC)
);

-- Scheduled tasks: For recurring or delayed execution
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(100) NOT NULL,
    schedule_expression VARCHAR(255), -- Cron expression or 'once'
    next_run_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_run_at TIMESTAMP WITH TIME ZONE,
    context JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_scheduled_next_run (next_run_at),
    INDEX idx_scheduled_enabled (enabled)
);

-- API keys: For external service authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    key_hash VARCHAR(255) NOT NULL, -- Store hashed version
    service VARCHAR(50) NOT NULL,
    permissions JSONB DEFAULT '[]',
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    INDEX idx_api_keys_service (service)
);

-- Audit log: Track all system actions
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    user_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_audit_created (created_at DESC),
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_user (user_id)
);

-- Create update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to relevant tables
CREATE TRIGGER update_memory_entries_updated_at BEFORE UPDATE ON memory_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function for vector similarity search
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

-- Function for full text document search
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

-- Row Level Security (RLS) policies
-- Enable RLS on sensitive tables
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_queue ENABLE ROW LEVEL SECURITY;

-- Create initial indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_metadata ON tasks USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_memory_metadata ON memory_entries USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_webhook_payload ON webhook_events USING GIN (payload);

-- Comments for schema documentation
COMMENT ON TABLE tasks IS 'Core task execution tracking for all BrainOps automation tasks';
COMMENT ON TABLE agent_executions IS 'Individual AI agent calls within task executions';
COMMENT ON TABLE memory_entries IS 'Key-value memory store with vector embeddings for RAG';
COMMENT ON TABLE documents IS 'Full documents for knowledge base with full-text search';
COMMENT ON TABLE document_chunks IS 'Chunked documents with embeddings for semantic search';
COMMENT ON TABLE webhook_events IS 'Incoming webhook events from external integrations';
COMMENT ON TABLE approval_queue IS 'Human-in-the-loop approval requests';
COMMENT ON TABLE scheduled_tasks IS 'Recurring or delayed task scheduling';
COMMENT ON TABLE api_keys IS 'Hashed API keys for external service authentication';
COMMENT ON TABLE audit_log IS 'Comprehensive audit trail of all system actions';