"""RAG (Retrieval-Augmented Generation) Service for BrainOps AI Assistant."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import openai
from sqlalchemy import select, func, desc, text
from sqlalchemy.orm import selectinload
from loguru import logger

from core.database import get_db
from core.config import settings
from models.db import (
    AssistantMessageDB, 
    KnowledgeEntryDB, 
    FileMetadataDB,
    User,
    WorkflowDB,
    TaskDB,
    VoiceCommandDB,
    AuditLog
)
from services.embedding_service import EmbeddingService


class RAGService:
    """Retrieval-Augmented Generation service for semantic search and context retrieval."""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_dimension = 1536
        self.max_context_length = 8000
        
    async def initialize(self):
        """Initialize the RAG service."""
        await self.embedding_service.initialize()
        await self._ensure_vector_extension()
        logger.info("RAG service initialized")
    
    async def _ensure_vector_extension(self):
        """Ensure pgvector extension is enabled."""
        try:
            async with get_db() as db:
                await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await db.commit()
                logger.info("pgvector extension enabled")
        except Exception as e:
            logger.error(f"Failed to enable pgvector extension: {e}")
            raise
    
    async def index_message(self, message: AssistantMessageDB) -> bool:
        """Index a message for semantic search."""
        try:
            # Generate embedding for the message content
            embedding = await self.embedding_service.generate_embedding(
                message.content, 
                metadata={
                    "type": "message",
                    "role": message.role,
                    "message_type": message.message_type,
                    "timestamp": message.timestamp.isoformat(),
                    "session_id": message.session_id
                }
            )
            
            # Update message with embedding
            async with get_db() as db:
                message.embedding = embedding
                db.add(message)
                await db.commit()
                
            logger.debug(f"Indexed message {message.id} with embedding")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index message {message.id}: {e}")
            return False
    
    async def index_knowledge_entry(self, entry: KnowledgeEntryDB) -> bool:
        """Index a knowledge entry for semantic search."""
        try:
            # Generate embedding for the entry content
            combined_content = f"{entry.title}\n\n{entry.content}"
            embedding = await self.embedding_service.generate_embedding(
                combined_content,
                metadata={
                    "type": "knowledge",
                    "category": entry.category,
                    "entry_type": entry.type,
                    "tags": entry.tags,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat()
                }
            )
            
            # Update entry with embedding
            async with get_db() as db:
                entry.embedding = embedding
                db.add(entry)
                await db.commit()
                
            logger.debug(f"Indexed knowledge entry {entry.id} with embedding")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index knowledge entry {entry.id}: {e}")
            return False
    
    async def search_conversations(
        self, 
        query: str, 
        user_id: int, 
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search through conversation history using semantic similarity."""
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            async with get_db() as db:
                # Search for similar messages
                search_query = select(
                    AssistantMessageDB,
                    func.cosine_distance(AssistantMessageDB.embedding, query_embedding).label("distance")
                ).join(
                    AssistantMessageDB.session
                ).where(
                    AssistantMessageDB.session.has(user_id=user_id)
                ).where(
                    func.cosine_distance(AssistantMessageDB.embedding, query_embedding) < (1 - similarity_threshold)
                ).order_by(
                    func.cosine_distance(AssistantMessageDB.embedding, query_embedding)
                ).limit(limit)
                
                result = await db.execute(search_query)
                messages = result.fetchall()
                
                # Format results
                search_results = []
                for message, distance in messages:
                    search_results.append({
                        "id": message.id,
                        "content": message.content,
                        "role": message.role,
                        "timestamp": message.timestamp.isoformat(),
                        "message_type": message.message_type,
                        "session_id": message.session_id,
                        "similarity_score": 1 - distance,
                        "context": message.context,
                        "metadata": message.metadata
                    })
                
                logger.debug(f"Found {len(search_results)} conversation matches for query: {query}")
                return search_results
                
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
    
    async def search_knowledge_base(
        self,
        query: str,
        category: Optional[str] = None,
        entry_type: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search through knowledge base using semantic similarity."""
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            async with get_db() as db:
                # Build search query
                search_query = select(
                    KnowledgeEntryDB,
                    func.cosine_distance(KnowledgeEntryDB.embedding, query_embedding).label("distance")
                ).where(
                    func.cosine_distance(KnowledgeEntryDB.embedding, query_embedding) < (1 - similarity_threshold)
                )
                
                # Add filters
                if category:
                    search_query = search_query.where(KnowledgeEntryDB.category == category)
                if entry_type:
                    search_query = search_query.where(KnowledgeEntryDB.type == entry_type)
                
                search_query = search_query.order_by(
                    func.cosine_distance(KnowledgeEntryDB.embedding, query_embedding)
                ).limit(limit)
                
                result = await db.execute(search_query)
                entries = result.fetchall()
                
                # Format results
                search_results = []
                for entry, distance in entries:
                    search_results.append({
                        "id": entry.id,
                        "title": entry.title,
                        "content": entry.content,
                        "type": entry.type,
                        "category": entry.category,
                        "tags": entry.tags,
                        "source": entry.source,
                        "created_at": entry.created_at.isoformat(),
                        "similarity_score": 1 - distance,
                        "metadata": entry.metadata
                    })
                
                logger.debug(f"Found {len(search_results)} knowledge base matches for query: {query}")
                return search_results
                
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []
    
    async def get_contextual_information(
        self, 
        query: str, 
        user_id: int,
        include_conversations: bool = True,
        include_knowledge: bool = True,
        include_files: bool = True,
        include_workflows: bool = True,
        include_tasks: bool = True,
        max_context_items: int = 20
    ) -> Dict[str, Any]:
        """Get comprehensive contextual information for a query."""
        try:
            context = {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "sources": []
            }
            
            # Search conversations
            if include_conversations:
                conversations = await self.search_conversations(query, user_id, limit=5)
                if conversations:
                    context["sources"].extend([
                        {
                            "type": "conversation",
                            "source": "chat_history",
                            "data": conv,
                            "relevance": conv["similarity_score"]
                        }
                        for conv in conversations[:3]  # Top 3 most relevant
                    ])
            
            # Search knowledge base
            if include_knowledge:
                knowledge = await self.search_knowledge_base(query, limit=5)
                if knowledge:
                    context["sources"].extend([
                        {
                            "type": "knowledge",
                            "source": "knowledge_base",
                            "data": kb,
                            "relevance": kb["similarity_score"]
                        }
                        for kb in knowledge[:3]  # Top 3 most relevant
                    ])
            
            # Search recent tasks
            if include_tasks:
                tasks = await self._search_recent_tasks(query, user_id, limit=3)
                if tasks:
                    context["sources"].extend([
                        {
                            "type": "task",
                            "source": "task_history",
                            "data": task,
                            "relevance": 0.8  # High relevance for recent tasks
                        }
                        for task in tasks
                    ])
            
            # Search workflows
            if include_workflows:
                workflows = await self._search_workflows(query, user_id, limit=3)
                if workflows:
                    context["sources"].extend([
                        {
                            "type": "workflow",
                            "source": "workflow_history",
                            "data": workflow,
                            "relevance": 0.7
                        }
                        for workflow in workflows
                    ])
            
            # Search files
            if include_files:
                files = await self._search_files(query, limit=3)
                if files:
                    context["sources"].extend([
                        {
                            "type": "file",
                            "source": "file_system",
                            "data": file,
                            "relevance": 0.6
                        }
                        for file in files
                    ])
            
            # Sort by relevance and limit
            context["sources"] = sorted(
                context["sources"], 
                key=lambda x: x["relevance"], 
                reverse=True
            )[:max_context_items]
            
            context["total_sources"] = len(context["sources"])
            
            logger.debug(f"Retrieved {context['total_sources']} contextual sources for query: {query}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get contextual information: {e}")
            return {"query": query, "sources": [], "error": str(e)}
    
    async def _search_recent_tasks(self, query: str, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Search recent tasks that might be relevant."""
        try:
            async with get_db() as db:
                # Search tasks by title/description content similarity
                search_query = select(TaskDB).where(
                    TaskDB.created_by == user_id
                ).where(
                    func.to_tsvector('english', TaskDB.title + ' ' + func.coalesce(TaskDB.description, ''))
                    .match(func.plainto_tsquery('english', query))
                ).order_by(desc(TaskDB.created_at)).limit(limit)
                
                result = await db.execute(search_query)
                tasks = result.scalars().all()
                
                return [
                    {
                        "id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "status": task.status,
                        "priority": task.priority,
                        "created_at": task.created_at.isoformat(),
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "tags": task.tags
                    }
                    for task in tasks
                ]
                
        except Exception as e:
            logger.error(f"Failed to search recent tasks: {e}")
            return []
    
    async def _search_workflows(self, query: str, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Search workflows that might be relevant."""
        try:
            async with get_db() as db:
                # Search workflows by name/description content similarity
                search_query = select(WorkflowDB).where(
                    WorkflowDB.created_by == user_id
                ).where(
                    func.to_tsvector('english', WorkflowDB.name + ' ' + func.coalesce(WorkflowDB.description, ''))
                    .match(func.plainto_tsquery('english', query))
                ).order_by(desc(WorkflowDB.last_run)).limit(limit)
                
                result = await db.execute(search_query)
                workflows = result.scalars().all()
                
                return [
                    {
                        "id": workflow.id,
                        "name": workflow.name,
                        "description": workflow.description,
                        "enabled": workflow.enabled,
                        "last_run": workflow.last_run.isoformat() if workflow.last_run else None,
                        "run_count": workflow.run_count,
                        "trigger": workflow.trigger
                    }
                    for workflow in workflows
                ]
                
        except Exception as e:
            logger.error(f"Failed to search workflows: {e}")
            return []
    
    async def _search_files(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search files that might be relevant."""
        try:
            async with get_db() as db:
                # Search files by filename and metadata
                search_query = select(FileMetadataDB).where(
                    func.to_tsvector('english', FileMetadataDB.filename + ' ' + FileMetadataDB.path)
                    .match(func.plainto_tsquery('english', query))
                ).order_by(desc(FileMetadataDB.last_accessed)).limit(limit)
                
                result = await db.execute(search_query)
                files = result.scalars().all()
                
                return [
                    {
                        "id": file.id,
                        "filename": file.filename,
                        "path": file.path,
                        "size_bytes": file.size_bytes,
                        "mime_type": file.mime_type,
                        "created_at": file.created_at.isoformat(),
                        "last_accessed": file.last_accessed.isoformat() if file.last_accessed else None,
                        "tags": file.tags
                    }
                    for file in files
                ]
                
        except Exception as e:
            logger.error(f"Failed to search files: {e}")
            return []
    
    async def generate_contextual_response(
        self,
        query: str,
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4"
    ) -> Dict[str, Any]:
        """Generate a response using retrieved context."""
        try:
            # Get context if not provided
            if context is None:
                context = await self.get_contextual_information(query, user_id)
            
            # Build context prompt
            context_prompt = self._build_context_prompt(context)
            
            # Generate response
            messages = [
                {
                    "role": "system",
                    "content": f"""You are BrainOps AI Assistant. Use the following context to provide accurate, helpful responses.
                    
Context Information:
{context_prompt}

Guidelines:
1. Always cite sources when using information from context
2. Be specific and accurate
3. If information is outdated, mention when it was last updated
4. Provide actionable recommendations when relevant
5. Ask clarifying questions if needed"""
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7
            )
            
            return {
                "response": response.choices[0].message.content,
                "sources_used": len(context.get("sources", [])),
                "context": context,
                "model": model,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate contextual response: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your request. Please try again.",
                "error": str(e),
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _build_context_prompt(self, context: Dict[str, Any]) -> str:
        """Build a context prompt from retrieved information."""
        prompt_parts = []
        
        for source in context.get("sources", []):
            source_type = source["type"]
            data = source["data"]
            relevance = source["relevance"]
            
            if source_type == "conversation":
                prompt_parts.append(f"""
CONVERSATION HISTORY (Relevance: {relevance:.2f}):
- From: {data['timestamp']}
- Role: {data['role']}
- Content: {data['content'][:500]}...
""")
            
            elif source_type == "knowledge":
                prompt_parts.append(f"""
KNOWLEDGE BASE (Relevance: {relevance:.2f}):
- Title: {data['title']}
- Category: {data['category']}
- Content: {data['content'][:500]}...
""")
            
            elif source_type == "task":
                prompt_parts.append(f"""
RECENT TASK (Relevance: {relevance:.2f}):
- Title: {data['title']}
- Status: {data['status']}
- Description: {data['description'][:300]}...
""")
            
            elif source_type == "workflow":
                prompt_parts.append(f"""
WORKFLOW (Relevance: {relevance:.2f}):
- Name: {data['name']}
- Status: {'Enabled' if data['enabled'] else 'Disabled'}
- Description: {data['description'][:300]}...
""")
            
            elif source_type == "file":
                prompt_parts.append(f"""
FILE REFERENCE (Relevance: {relevance:.2f}):
- Filename: {data['filename']}
- Path: {data['path']}
- Size: {data['size_bytes']} bytes
- Last accessed: {data['last_accessed']}
""")
        
        return "\n".join(prompt_parts)
    
    async def bulk_index_existing_data(self, batch_size: int = 100) -> Dict[str, int]:
        """Bulk index all existing data for RAG functionality."""
        try:
            stats = {
                "messages_indexed": 0,
                "knowledge_entries_indexed": 0,
                "errors": 0
            }
            
            async with get_db() as db:
                # Index existing messages without embeddings
                message_query = select(AssistantMessageDB).where(
                    AssistantMessageDB.embedding.is_(None)
                ).limit(batch_size)
                
                result = await db.execute(message_query)
                messages = result.scalars().all()
                
                for message in messages:
                    success = await self.index_message(message)
                    if success:
                        stats["messages_indexed"] += 1
                    else:
                        stats["errors"] += 1
                
                # Index existing knowledge entries without embeddings
                knowledge_query = select(KnowledgeEntryDB).where(
                    KnowledgeEntryDB.embedding.is_(None)
                ).limit(batch_size)
                
                result = await db.execute(knowledge_query)
                entries = result.scalars().all()
                
                for entry in entries:
                    success = await self.index_knowledge_entry(entry)
                    if success:
                        stats["knowledge_entries_indexed"] += 1
                    else:
                        stats["errors"] += 1
            
            logger.info(f"Bulk indexing completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to bulk index existing data: {e}")
            return {"errors": 1, "error_message": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check RAG service health."""
        try:
            async with get_db() as db:
                # Check database connection
                await db.execute(text("SELECT 1"))
                
                # Check vector extension
                result = await db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
                vector_enabled = result.scalar() is not None
                
                # Get indexing stats
                message_count = await db.scalar(select(func.count(AssistantMessageDB.id)))
                indexed_messages = await db.scalar(select(func.count(AssistantMessageDB.id)).where(AssistantMessageDB.embedding.is_not(None)))
                
                knowledge_count = await db.scalar(select(func.count(KnowledgeEntryDB.id)))
                indexed_knowledge = await db.scalar(select(func.count(KnowledgeEntryDB.id)).where(KnowledgeEntryDB.embedding.is_not(None)))
                
                return {
                    "status": "healthy",
                    "vector_extension_enabled": vector_enabled,
                    "embedding_service_ready": await self.embedding_service.health_check(),
                    "indexing_stats": {
                        "total_messages": message_count,
                        "indexed_messages": indexed_messages,
                        "message_index_percentage": (indexed_messages / message_count * 100) if message_count > 0 else 0,
                        "total_knowledge_entries": knowledge_count,
                        "indexed_knowledge_entries": indexed_knowledge,
                        "knowledge_index_percentage": (indexed_knowledge / knowledge_count * 100) if knowledge_count > 0 else 0
                    }
                }
                
        except Exception as e:
            logger.error(f"RAG service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }