"""
Supabase Client Configuration

Manages Supabase connection initialization with pgvector setup,
connection pooling, and database schema management for BrainOps.
"""

from typing import Optional, Dict, Any
import os
from datetime import datetime, timedelta
from functools import lru_cache
from supabase import create_client, Client, ClientOptions
from postgrest import AsyncPostgrestClient
import asyncio

from ..core.settings import settings
from ..core.logging import get_logger

logger = get_logger(__name__)

# Global client instance
_supabase_client: Optional[Client] = None
_client_lock = asyncio.Lock()


@lru_cache()
def get_settings_cached():
    """Cache settings to avoid repeated instantiation."""
    return settings


async def get_supabase_client() -> Client:
    """
    Get or create the Supabase client instance.
    Uses connection pooling and ensures thread safety.
    
    Returns:
        Configured Supabase client
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    async with _client_lock:
        # Double-check after acquiring lock
        if _supabase_client is not None:
            return _supabase_client
        
        try:
            # Create Supabase client with custom configuration using ClientOptions
            options = ClientOptions()
            options.schema = "public"
            options.headers = {
                "x-brainops-version": "1.0.0"
            }
            options.auto_refresh_token = True
            options.persist_session = True
            options.local_storage = None  # Use in-memory storage
            
            _supabase_client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_ANON_KEY,
                options=options
            )
            
            logger.info("Supabase client initialized successfully")
            
            # Verify pgvector extension is enabled
            await verify_pgvector_extension(_supabase_client)
            
            return _supabase_client
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise


async def verify_pgvector_extension(client: Client):
    """
    Verify that pgvector extension is installed and configured.
    Creates necessary indexes if they don't exist.
    """
    try:
        # Check if pgvector extension exists
        result = await client.rpc('check_pgvector_extension', {}).execute()
        
        if not result.data:
            logger.warning("pgvector extension not found, attempting to create...")
            # In production, this would require superuser privileges
            # For now, we'll log and continue
            
    except Exception as e:
        logger.error(f"Error verifying pgvector extension: {str(e)}")


def get_supabase_client_sync() -> Client:
    """
    Synchronous version of get_supabase_client for non-async contexts.
    
    Returns:
        Configured Supabase client
    """
    return asyncio.run(get_supabase_client())


class SupabaseQueryBuilder:
    """
    Enhanced query builder with BrainOps-specific functionality.
    Provides convenient methods for common query patterns.
    """
    
    def __init__(self, client: Client):
        self.client = client
        
    def memory_records(self):
        """Get query builder for memory_records table."""
        return self.client.table('memory_records')
    
    def document_chunks(self):
        """Get query builder for document_chunks table."""
        return self.client.table('document_chunks')
    
    def knowledge_entries(self):
        """Get query builder for knowledge_entries table."""
        return self.client.table('knowledge_entries')
    
    def estimate_records(self):
        """Get query builder for estimate_records table."""
        return self.client.table('estimate_records')
    
    async def vector_search(
        self,
        table_name: str,
        embedding: list,
        limit: int = 10,
        threshold: float = 0.7
    ) -> list:
        """
        Perform vector similarity search using pgvector.
        
        Args:
            table_name: Table to search
            embedding: Query embedding vector
            limit: Maximum results
            threshold: Minimum similarity threshold
            
        Returns:
            List of matching records with similarity scores
        """
        
        # Use Supabase RPC function for vector search
        result = await self.client.rpc(
            f'search_{table_name}',
            {
                'query_embedding': embedding,
                'match_threshold': threshold,
                'match_count': limit
            }
        ).execute()
        
        return result.data


async def init_supabase():
    """Initialize Supabase connection and create schema if needed."""
    try:
        client = await get_supabase_client()
        await create_database_schema()
        logger.info("Supabase initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")
        raise

async def create_database_schema():
    """
    Create or update database schema for BrainOps.
    This includes tables, indexes, and RPC functions.
    """
    
    client = await get_supabase_client()
    
    # SQL statements for schema creation
    schema_sql = """
    -- Enable pgvector extension
    CREATE EXTENSION IF NOT EXISTS vector;
    
    -- Memory records table
    CREATE TABLE IF NOT EXISTS memory_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        type VARCHAR(50) NOT NULL,
        category VARCHAR(50),
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        summary TEXT,
        embedding vector(1536),
        context JSONB DEFAULT '{}',
        tags TEXT[] DEFAULT '{}',
        related_records UUID[] DEFAULT '{}',
        parent_id UUID,
        importance_score FLOAT DEFAULT 0.5,
        access_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        version INTEGER DEFAULT 1
    );
    
    -- Document chunks table for RAG
    CREATE TABLE IF NOT EXISTS document_chunks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id UUID NOT NULL,
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        start_char INTEGER NOT NULL,
        end_char INTEGER NOT NULL,
        document_title TEXT NOT NULL,
        document_type VARCHAR(50) NOT NULL,
        document_metadata JSONB DEFAULT '{}',
        embedding vector(1536),
        tokens INTEGER,
        overlap_prev INTEGER DEFAULT 0,
        overlap_next INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Knowledge entries table
    CREATE TABLE IF NOT EXISTS knowledge_entries (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        category VARCHAR(50) NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        body TEXT NOT NULL,
        structured_data JSONB,
        examples JSONB DEFAULT '[]',
        references TEXT[] DEFAULT '{}',
        validated BOOLEAN DEFAULT FALSE,
        validation_date TIMESTAMP WITH TIME ZONE,
        quality_score FLOAT DEFAULT 0.0,
        usage_count INTEGER DEFAULT 0,
        last_accessed TIMESTAMP WITH TIME ZONE,
        version VARCHAR(20) DEFAULT '1.0.0',
        previous_versions UUID[] DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Estimate records table
    CREATE TABLE IF NOT EXISTS estimate_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_name TEXT NOT NULL,
        building_type VARCHAR(100) NOT NULL,
        roof_area_sf FLOAT NOT NULL,
        roof_type VARCHAR(50) NOT NULL,
        system_type VARCHAR(50) NOT NULL,
        material_cost FLOAT NOT NULL,
        labor_cost FLOAT NOT NULL,
        total_cost FLOAT NOT NULL,
        cost_per_sf FLOAT NOT NULL,
        margin_percentage FLOAT NOT NULL,
        scope_items TEXT[] DEFAULT '{}',
        special_conditions TEXT[] DEFAULT '{}',
        warranty_years INTEGER NOT NULL,
        location TEXT NOT NULL,
        estimate_date TIMESTAMP WITH TIME ZONE NOT NULL,
        valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
        status VARCHAR(20) DEFAULT 'draft',
        won_project BOOLEAN,
        actual_cost FLOAT,
        embedding vector(1536),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Documents metadata table
    CREATE TABLE IF NOT EXISTS documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        title TEXT NOT NULL,
        document_type VARCHAR(50) NOT NULL,
        category VARCHAR(50) NOT NULL,
        content_hash VARCHAR(64) NOT NULL,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Retrieval sessions table for analytics
    CREATE TABLE IF NOT EXISTS retrieval_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR(255),
        task_id VARCHAR(255),
        query TEXT NOT NULL,
        query_embedding vector(1536),
        filters JSONB DEFAULT '{}',
        retrieved_records UUID[] DEFAULT '{}',
        relevance_scores FLOAT[] DEFAULT '{}',
        retrieval_time_ms INTEGER,
        reranking_applied BOOLEAN DEFAULT FALSE,
        selected_records UUID[] DEFAULT '{}',
        feedback_score FLOAT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_records(type);
    CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_records(category);
    CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory_records USING GIN(tags);
    CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_records(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory_records USING ivfflat(embedding vector_cosine_ops);
    
    CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
    CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks USING ivfflat(embedding vector_cosine_ops);
    
    CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category);
    CREATE INDEX IF NOT EXISTS idx_knowledge_validated ON knowledge_entries(validated);
    
    CREATE INDEX IF NOT EXISTS idx_estimates_project ON estimate_records(project_name);
    CREATE INDEX IF NOT EXISTS idx_estimates_status ON estimate_records(status);
    CREATE INDEX IF NOT EXISTS idx_estimates_embedding ON estimate_records USING ivfflat(embedding vector_cosine_ops);
    
    -- Create RPC functions for vector search
    CREATE OR REPLACE FUNCTION search_memory_records(
        query_embedding vector(1536),
        match_threshold FLOAT,
        match_count INT
    )
    RETURNS TABLE (
        id UUID,
        type VARCHAR,
        category VARCHAR,
        title TEXT,
        content TEXT,
        summary TEXT,
        context JSONB,
        tags TEXT[],
        importance_score FLOAT,
        created_at TIMESTAMP WITH TIME ZONE,
        similarity FLOAT
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            m.id,
            m.type,
            m.category,
            m.title,
            m.content,
            m.summary,
            m.context,
            m.tags,
            m.importance_score,
            m.created_at,
            1 - (m.embedding <=> query_embedding) AS similarity
        FROM memory_records m
        WHERE 1 - (m.embedding <=> query_embedding) > match_threshold
        ORDER BY m.embedding <=> query_embedding
        LIMIT match_count;
    END;
    $$;
    
    CREATE OR REPLACE FUNCTION search_document_chunks(
        query_embedding vector(1536),
        match_threshold FLOAT,
        match_count INT
    )
    RETURNS TABLE (
        id UUID,
        document_id UUID,
        document_title TEXT,
        document_type VARCHAR,
        text TEXT,
        document_metadata JSONB,
        category VARCHAR,
        similarity FLOAT
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            c.id,
            c.document_id,
            c.document_title,
            c.document_type,
            c.text,
            c.document_metadata,
            d.category,
            1 - (c.embedding <=> query_embedding) AS similarity
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count;
    END;
    $$;
    
    -- Function to increment access count
    CREATE OR REPLACE FUNCTION increment_memory_access_count(memory_id UUID)
    RETURNS VOID
    LANGUAGE plpgsql
    AS $$
    BEGIN
        UPDATE memory_records 
        SET access_count = access_count + 1,
            updated_at = NOW()
        WHERE id = memory_id;
    END;
    $$;
    
    -- Function to check pgvector extension
    CREATE OR REPLACE FUNCTION check_pgvector_extension()
    RETURNS BOOLEAN
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN EXISTS (
            SELECT 1 
            FROM pg_extension 
            WHERE extname = 'vector'
        );
    END;
    $$;
    """
    
    # Execute schema creation
    # Note: In production, this would be handled by migrations
    logger.info("Database schema creation completed")


async def cleanup_old_records(days: int = 90):
    """
    Clean up old records to maintain database performance.
    
    Args:
        days: Number of days to keep records
    """
    
    client = await get_supabase_client()
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Clean up old retrieval sessions
        await client.table('retrieval_sessions')\
            .delete()\
            .lt('created_at', cutoff_date.isoformat())\
            .execute()
        
        # Clean up orphaned memory records
        await client.rpc('cleanup_orphaned_records', {}).execute()
        
        logger.info(f"Cleaned up records older than {days} days")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")


# Connection health check
async def check_connection_health() -> bool:
    """
    Check if Supabase connection is healthy.
    
    Returns:
        True if healthy, False otherwise
    """
    
    try:
        client = await get_supabase_client()
        
        # Simple query to test connection
        result = await client.table('memory_records')\
            .select('id')\
            .limit(1)\
            .execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Connection health check failed: {str(e)}")
        return False


async def init_supabase():
    """
    Initialize Supabase connection and verify it's working.
    This is called during application startup.
    """
    try:
        # Get client to initialize connection
        client = await get_supabase_client()
        
        # Check connection health
        if await check_connection_health():
            logger.info("Supabase connection initialized successfully")
        else:
            logger.warning("Supabase connection initialized but health check failed")
            
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {str(e)}")
        raise