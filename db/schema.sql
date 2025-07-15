-- BrainOps Database Schema
-- PostgreSQL with pgvector extension for AI-powered memory and search
-- Built to handle high-stakes automation with complete audit trails

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- Encryption functions
CREATE EXTENSION IF NOT EXISTS "vector";         -- Vector similarity search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Text similarity search

-- Create custom types for better data integrity
CREATE TYPE task_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE auth_event_type AS ENUM ('login', 'logout', 'token_refresh', 'access_denied', 'api_key_created');
CREATE TYPE integration_type AS ENUM ('slack', 'clickup', 'notion', 'make', 'stripe', 'webhook');

-- Users table: Core authentication and authorization
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    permissions JSONB DEFAULT '[]'::jsonb,  -- Array of permission strings
    metadata JSONB DEFAULT '{}'::jsonb,     -- Extensible user metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Index for fast email lookups during authentication
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;

-- API Keys table: For programmatic access
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_id VARCHAR(50) UNIQUE NOT NULL,     -- Public identifier (bops_xxxxx)
    key_hash VARCHAR(64) NOT NULL,          -- SHA256 hash of secret portion
    name VARCHAR(255) NOT NULL,             -- User-friendly name
    permissions JSONB DEFAULT '[]'::jsonb,  -- Scoped permissions
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT key_id_format CHECK (key_id ~ '^bops_[a-zA-Z0-9_-]+$')
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_id ON api_keys(key_id) WHERE revoked_at IS NULL;

-- Auth Events table: Security audit trail
CREATE TABLE auth_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type auth_event_type NOT NULL,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for security analysis and user activity tracking
CREATE INDEX idx_auth_events_user ON auth_events(user_id);
CREATE INDEX idx_auth_events_created ON auth_events(created_at DESC);

-- Task Definitions table: Registry of available automation tasks
CREATE TABLE task_definitions (
    id VARCHAR(100) PRIMARY KEY,            -- e.g., 'generate_roof_estimate'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),                   -- e.g., 'content', 'estimation', 'integration'
    input_schema JSONB NOT NULL,           -- JSON Schema for validation
    output_schema JSONB,
    required_permissions JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_definitions_category ON task_definitions(category);
CREATE INDEX idx_task_definitions_active ON task_definitions(is_active) WHERE is_active = true;

-- Task Executions table: Runtime tracking and audit trail
CREATE TABLE task_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(100) NOT NULL REFERENCES task_definitions(id),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status task_status NOT NULL DEFAULT 'pending',
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs JSONB,
    error_message TEXT,
    error_details JSONB,
    context JSONB DEFAULT '{}'::jsonb,      -- Source, trigger info, etc.
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER GENERATED ALWAYS AS (
        CASE 
            WHEN completed_at IS NOT NULL AND started_at IS NOT NULL 
            THEN EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 
            ELSE NULL 
        END
    ) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance monitoring and analysis
CREATE INDEX idx_task_executions_task ON task_executions(task_id);
CREATE INDEX idx_task_executions_user ON task_executions(user_id);
CREATE INDEX idx_task_executions_status ON task_executions(status);
CREATE INDEX idx_task_executions_created ON task_executions(created_at DESC);

-- Memory Entries table: RAG system knowledge base
CREATE TABLE memory_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    content_type VARCHAR(50),               -- e.g., 'document', 'conversation', 'note'
    embedding vector(1536),                 -- OpenAI text-embedding-3-small dimension
    metadata JSONB DEFAULT '{}'::jsonb,
    source_url TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for vector similarity and text search
CREATE INDEX idx_memory_embedding ON memory_entries USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memory_content ON memory_entries USING gin(to_tsvector('english', content));
CREATE INDEX idx_memory_user ON memory_entries(user_id) WHERE is_active = true;
CREATE INDEX idx_memory_metadata ON memory_entries USING gin(metadata);

-- Knowledge Documents table: Structured documents for RAG
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    document_type VARCHAR(50),              -- e.g., 'sop', 'template', 'guide'
    file_path TEXT,
    file_hash VARCHAR(64),                  -- SHA256 for deduplication
    metadata JSONB DEFAULT '{}'::jsonb,
    is_published BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_docs_user ON knowledge_documents(user_id);
CREATE INDEX idx_knowledge_docs_type ON knowledge_documents(document_type);
CREATE INDEX idx_knowledge_docs_published ON knowledge_documents(is_published) WHERE is_published = true;

-- Document Chunks table: Chunked documents for efficient RAG retrieval
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);

-- Scheduled Jobs table: Background task persistence
CREATE TABLE scheduled_jobs (
    id VARCHAR(255) PRIMARY KEY,            -- Job identifier
    task_id VARCHAR(100) REFERENCES task_definitions(id),
    next_run_time TIMESTAMP WITH TIME ZONE,
    job_state BYTEA,                        -- Pickled job state for APScheduler
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scheduled_jobs_next_run ON scheduled_jobs(next_run_time) WHERE next_run_time IS NOT NULL;

-- Integration Connections table: External service configurations
CREATE TABLE integration_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    integration_type integration_type NOT NULL,
    name VARCHAR(255) NOT NULL,
    configuration JSONB NOT NULL,           -- Encrypted sensitive data
    is_active BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, integration_type, name)
);

CREATE INDEX idx_integrations_user ON integration_connections(user_id);
CREATE INDEX idx_integrations_type ON integration_connections(integration_type) WHERE is_active = true;

-- Webhook Events table: Incoming webhook tracking
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_type integration_type NOT NULL,
    event_id VARCHAR(255),                  -- External event ID for deduplication
    event_type VARCHAR(100),
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(integration_type, event_id)
);

CREATE INDEX idx_webhook_events_type ON webhook_events(integration_type, event_type);
CREATE INDEX idx_webhook_events_processed ON webhook_events(processed, created_at) WHERE processed = false;

-- Payment Events table: Stripe transaction tracking
CREATE TABLE payment_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stripe_event_id VARCHAR(255) UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    customer_id VARCHAR(255),
    amount INTEGER,                         -- Amount in cents
    currency VARCHAR(3),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_events_customer ON payment_events(customer_id);
CREATE INDEX idx_payment_events_created ON payment_events(created_at DESC);

-- Analytics Events table: Usage tracking and metrics
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_name VARCHAR(100) NOT NULL,
    event_category VARCHAR(50),
    properties JSONB DEFAULT '{}'::jsonb,
    session_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optimized for time-series queries
CREATE INDEX idx_analytics_time ON analytics_events(created_at DESC);
CREATE INDEX idx_analytics_user_time ON analytics_events(user_id, created_at DESC);
CREATE INDEX idx_analytics_event ON analytics_events(event_name, created_at DESC);

-- Functions and triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_definitions_updated_at BEFORE UPDATE ON task_definitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_entries_updated_at BEFORE UPDATE ON memory_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_documents_updated_at BEFORE UPDATE ON knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integration_connections_updated_at BEFORE UPDATE ON integration_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scheduled_jobs_updated_at BEFORE UPDATE ON scheduled_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries
CREATE VIEW active_user_tasks AS
SELECT 
    te.id,
    te.task_id,
    td.name as task_name,
    te.user_id,
    u.email as user_email,
    te.status,
    te.started_at,
    te.duration_ms,
    te.created_at
FROM task_executions te
JOIN task_definitions td ON te.task_id = td.id
LEFT JOIN users u ON te.user_id = u.id
WHERE te.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days';

-- Performance and monitoring views
CREATE VIEW system_health AS
SELECT 
    'total_users' as metric,
    COUNT(*) as value
FROM users WHERE is_active = true
UNION ALL
SELECT 
    'tasks_last_hour' as metric,
    COUNT(*) as value
FROM task_executions 
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
UNION ALL
SELECT 
    'active_integrations' as metric,
    COUNT(*) as value
FROM integration_connections 
WHERE is_active = true;

-- Grant appropriate permissions (adjust based on your user setup)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO brainops_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO brainops_app;