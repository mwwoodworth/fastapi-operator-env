"""Knowledge base service for information storage and retrieval."""

from __future__ import annotations

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from loguru import logger
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.config import settings
from models.db import KnowledgeEntryDB, User
from models.assistant import KnowledgeEntry
from services.ai_orchestrator import AIOrchestrator
from utils.audit import AuditLogger


class KnowledgeBase:
    """Comprehensive knowledge base with semantic search capabilities."""
    
    def __init__(self):
        self.ai_orchestrator = AIOrchestrator()
        self.audit_logger = AuditLogger()
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            lowercase=True,
            ngram_range=(1, 2)
        )
        self.knowledge_cache: Dict[str, KnowledgeEntry] = {}
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        
        # Knowledge categories
        self.categories = {
            "technical": "Technical documentation and procedures",
            "business": "Business processes and policies",
            "code": "Code examples and programming knowledge",
            "troubleshooting": "Problem-solving guides and solutions",
            "reference": "Reference materials and quick lookups",
            "tutorial": "Step-by-step tutorials and guides",
            "faq": "Frequently asked questions and answers",
            "api": "API documentation and examples"
        }
        
        # Entry types
        self.entry_types = {
            "document": "General document or article",
            "procedure": "Step-by-step procedure",
            "code": "Code snippet or example",
            "reference": "Quick reference or lookup",
            "troubleshooting": "Problem-solving guide",
            "faq": "FAQ entry",
            "tutorial": "Tutorial or guide",
            "api_doc": "API documentation"
        }
    
    async def add_entry(
        self,
        title: str,
        content: str,
        entry_type: str,
        category: str,
        tags: List[str] = None,
        source: Optional[str] = None,
        created_by: int = 1
    ) -> KnowledgeEntry:
        """Add a new knowledge entry."""
        try:
            entry_id = str(uuid.uuid4())
            
            # Generate embedding
            embedding = await self._generate_embedding(f"{title} {content}")
            
            # Create database entry
            db_entry = KnowledgeEntryDB(
                id=entry_id,
                title=title,
                content=content,
                type=entry_type,
                category=category,
                tags=tags or [],
                source=source,
                embedding=embedding.tolist() if embedding is not None else None,
                created_by=created_by
            )
            
            async with get_db() as db:
                db.add(db_entry)
                await db.commit()
                
                # Log entry creation
                await self.audit_logger.log_action(
                    user_id=created_by,
                    action="knowledge_entry_created",
                    resource_type="knowledge",
                    resource_id=entry_id,
                    details={
                        "title": title,
                        "type": entry_type,
                        "category": category,
                        "tags": tags or []
                    }
                )
                
                # Convert to domain model
                entry = self._db_to_domain(db_entry)
                
                # Cache entry
                self.knowledge_cache[entry_id] = entry
                if embedding is not None:
                    self.embeddings_cache[entry_id] = embedding
                
                logger.info(f"Added knowledge entry {entry_id}: {title}")
                return entry
                
        except Exception as e:
            logger.error(f"Error adding knowledge entry: {e}")
            raise
    
    async def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get a knowledge entry by ID."""
        try:
            # Check cache first
            if entry_id in self.knowledge_cache:
                return self.knowledge_cache[entry_id]
            
            async with get_db() as db:
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.id == entry_id)
                )
                
                db_entry = result.scalar_one_or_none()
                
                if not db_entry:
                    return None
                
                # Update access count
                db_entry.access_count += 1
                db_entry.last_accessed = datetime.utcnow()
                await db.commit()
                
                # Convert to domain model
                entry = self._db_to_domain(db_entry)
                
                # Cache entry
                self.knowledge_cache[entry_id] = entry
                
                return entry
                
        except Exception as e:
            logger.error(f"Error getting knowledge entry {entry_id}: {e}")
            return None
    
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        entry_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        min_score: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Search knowledge base with semantic and keyword matching."""
        try:
            # Get query embedding
            query_embedding = await self._generate_embedding(query)
            
            async with get_db() as db:
                # Build base query
                search_query = select(KnowledgeEntryDB)
                
                # Apply filters
                filters = []
                
                if category:
                    filters.append(KnowledgeEntryDB.category == category)
                
                if entry_type:
                    filters.append(KnowledgeEntryDB.type == entry_type)
                
                if tags:
                    for tag in tags:
                        filters.append(KnowledgeEntryDB.tags.contains([tag]))
                
                if filters:
                    search_query = search_query.where(and_(*filters))
                
                # Execute query
                result = await db.execute(search_query)
                entries = result.scalars().all()
                
                # Calculate relevance scores
                scored_results = []
                
                for entry in entries:
                    # Semantic similarity
                    semantic_score = 0.0
                    if query_embedding is not None and entry.embedding:
                        entry_embedding = np.array(entry.embedding)
                        semantic_score = cosine_similarity(
                            query_embedding.reshape(1, -1),
                            entry_embedding.reshape(1, -1)
                        )[0][0]
                    
                    # Keyword matching
                    keyword_score = self._calculate_keyword_score(query, entry)
                    
                    # Tag matching
                    tag_score = self._calculate_tag_score(query, entry.tags)
                    
                    # Combined score
                    combined_score = (
                        semantic_score * 0.5 +
                        keyword_score * 0.3 +
                        tag_score * 0.2
                    )
                    
                    if combined_score >= min_score:
                        scored_results.append({
                            "entry": self._db_to_domain(entry),
                            "score": combined_score,
                            "semantic_score": semantic_score,
                            "keyword_score": keyword_score,
                            "tag_score": tag_score
                        })
                
                # Sort by score and limit
                scored_results.sort(key=lambda x: x["score"], reverse=True)
                return scored_results[:limit]
                
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    async def update_entry(
        self,
        entry_id: str,
        updates: Dict[str, Any],
        updated_by: int = 1
    ) -> Optional[KnowledgeEntry]:
        """Update a knowledge entry."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.id == entry_id)
                )
                
                db_entry = result.scalar_one_or_none()
                
                if not db_entry:
                    return None
                
                # Store original values for audit
                original_values = {
                    "title": db_entry.title,
                    "content": db_entry.content,
                    "category": db_entry.category,
                    "tags": db_entry.tags
                }
                
                # Apply updates
                content_updated = False
                for key, value in updates.items():
                    if hasattr(db_entry, key):
                        setattr(db_entry, key, value)
                        if key in ["title", "content"]:
                            content_updated = True
                
                # Update timestamp
                db_entry.updated_at = datetime.utcnow()
                
                # Regenerate embedding if content changed
                if content_updated:
                    embedding = await self._generate_embedding(f"{db_entry.title} {db_entry.content}")
                    db_entry.embedding = embedding.tolist() if embedding is not None else None
                
                await db.commit()
                
                # Log update
                await self.audit_logger.log_action(
                    user_id=updated_by,
                    action="knowledge_entry_updated",
                    resource_type="knowledge",
                    resource_id=entry_id,
                    details={
                        "updates": updates,
                        "original_values": original_values
                    }
                )
                
                # Convert to domain model
                entry = self._db_to_domain(db_entry)
                
                # Update cache
                self.knowledge_cache[entry_id] = entry
                if content_updated and embedding is not None:
                    self.embeddings_cache[entry_id] = embedding
                
                logger.info(f"Updated knowledge entry {entry_id}")
                return entry
                
        except Exception as e:
            logger.error(f"Error updating knowledge entry {entry_id}: {e}")
            return None
    
    async def delete_entry(self, entry_id: str, deleted_by: int = 1) -> bool:
        """Delete a knowledge entry."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.id == entry_id)
                )
                
                db_entry = result.scalar_one_or_none()
                
                if not db_entry:
                    return False
                
                # Remove from cache
                self.knowledge_cache.pop(entry_id, None)
                self.embeddings_cache.pop(entry_id, None)
                
                # Delete from database
                await db.delete(db_entry)
                await db.commit()
                
                # Log deletion
                await self.audit_logger.log_action(
                    user_id=deleted_by,
                    action="knowledge_entry_deleted",
                    resource_type="knowledge",
                    resource_id=entry_id,
                    details={
                        "title": db_entry.title,
                        "category": db_entry.category
                    }
                )
                
                logger.info(f"Deleted knowledge entry {entry_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting knowledge entry {entry_id}: {e}")
            return False
    
    async def list_entries(
        self,
        category: Optional[str] = None,
        entry_type: Optional[str] = None,
        created_by: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[KnowledgeEntry]:
        """List knowledge entries with filtering and sorting."""
        try:
            async with get_db() as db:
                query = select(KnowledgeEntryDB)
                
                # Apply filters
                filters = []
                
                if category:
                    filters.append(KnowledgeEntryDB.category == category)
                
                if entry_type:
                    filters.append(KnowledgeEntryDB.type == entry_type)
                
                if created_by:
                    filters.append(KnowledgeEntryDB.created_by == created_by)
                
                if filters:
                    query = query.where(and_(*filters))
                
                # Apply sorting
                if sort_by and hasattr(KnowledgeEntryDB, sort_by):
                    order_column = getattr(KnowledgeEntryDB, sort_by)
                    if sort_order.lower() == "desc":
                        query = query.order_by(desc(order_column))
                    else:
                        query = query.order_by(order_column)
                
                # Apply pagination
                query = query.limit(limit).offset(offset)
                
                result = await db.execute(query)
                db_entries = result.scalars().all()
                
                # Convert to domain models
                entries = [self._db_to_domain(db_entry) for db_entry in db_entries]
                
                return entries
                
        except Exception as e:
            logger.error(f"Error listing knowledge entries: {e}")
            return []
    
    async def get_popular_entries(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        days: int = 30
    ) -> List[KnowledgeEntry]:
        """Get popular knowledge entries by access count."""
        try:
            async with get_db() as db:
                query = select(KnowledgeEntryDB).order_by(desc(KnowledgeEntryDB.access_count))
                
                if category:
                    query = query.where(KnowledgeEntryDB.category == category)
                
                # Filter by recent activity
                from datetime import timedelta
                recent_date = datetime.utcnow() - timedelta(days=days)
                query = query.where(KnowledgeEntryDB.last_accessed >= recent_date)
                
                query = query.limit(limit)
                
                result = await db.execute(query)
                db_entries = result.scalars().all()
                
                # Convert to domain models
                entries = [self._db_to_domain(db_entry) for db_entry in db_entries]
                
                return entries
                
        except Exception as e:
            logger.error(f"Error getting popular entries: {e}")
            return []
    
    async def get_categories_stats(self) -> Dict[str, Any]:
        """Get statistics by category."""
        try:
            async with get_db() as db:
                # Count by category
                category_result = await db.execute(
                    select(KnowledgeEntryDB.category, func.count(KnowledgeEntryDB.id))
                    .group_by(KnowledgeEntryDB.category)
                )
                
                category_counts = dict(category_result.fetchall())
                
                # Count by type
                type_result = await db.execute(
                    select(KnowledgeEntryDB.type, func.count(KnowledgeEntryDB.id))
                    .group_by(KnowledgeEntryDB.type)
                )
                
                type_counts = dict(type_result.fetchall())
                
                # Total entries
                total_result = await db.execute(
                    select(func.count(KnowledgeEntryDB.id))
                )
                total_entries = total_result.scalar()
                
                return {
                    "total_entries": total_entries,
                    "by_category": category_counts,
                    "by_type": type_counts,
                    "available_categories": list(self.categories.keys()),
                    "available_types": list(self.entry_types.keys())
                }
                
        except Exception as e:
            logger.error(f"Error getting category stats: {e}")
            return {}
    
    async def generate_answer(
        self,
        question: str,
        context_entries: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate an answer to a question using knowledge base."""
        try:
            # Search for relevant entries
            relevant_entries = await self.search(question, limit=5)
            
            # Include specific context entries if provided
            if context_entries:
                for entry_id in context_entries:
                    entry = await self.get_entry(entry_id)
                    if entry:
                        relevant_entries.append({
                            "entry": entry,
                            "score": 1.0,
                            "semantic_score": 1.0,
                            "keyword_score": 1.0,
                            "tag_score": 1.0
                        })
            
            # Build context from entries
            context_parts = []
            for result in relevant_entries:
                entry = result["entry"]
                context_parts.append(f"Title: {entry.title}\nContent: {entry.content}\n")
            
            context = "\n---\n".join(context_parts)
            
            # Generate answer using AI
            system_prompt = """You are a knowledgeable assistant. Answer the user's question based on the provided context from the knowledge base.

Instructions:
1. Use only information from the provided context
2. If the context doesn't contain sufficient information, say so
3. Provide specific, actionable answers
4. Reference the source information when relevant
5. Be concise but comprehensive"""
            
            prompt = f"""Context from knowledge base:
{context}

Question: {question}

Please provide a detailed answer based on the context above."""
            
            ai_response = await self.ai_orchestrator.query(
                prompt=prompt,
                system_prompt=system_prompt,
                query_type="knowledge_answer",
                user_id=user_id
            )
            
            return {
                "answer": ai_response["response"],
                "sources": [result["entry"].id for result in relevant_entries],
                "confidence": sum(result["score"] for result in relevant_entries) / len(relevant_entries) if relevant_entries else 0,
                "model_used": ai_response["model"],
                "cost": ai_response["cost"]
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                "answer": "I'm sorry, I encountered an error while generating the answer.",
                "sources": [],
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def import_from_file(
        self,
        file_path: str,
        category: str,
        entry_type: str = "document",
        tags: List[str] = None,
        created_by: int = 1
    ) -> KnowledgeEntry:
        """Import knowledge from a file."""
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from filename
            import os
            title = os.path.splitext(os.path.basename(file_path))[0]
            
            # Create entry
            entry = await self.add_entry(
                title=title,
                content=content,
                entry_type=entry_type,
                category=category,
                tags=tags,
                source=file_path,
                created_by=created_by
            )
            
            logger.info(f"Imported knowledge from {file_path}")
            return entry
            
        except Exception as e:
            logger.error(f"Error importing from file {file_path}: {e}")
            raise
    
    async def export_to_file(
        self,
        entry_id: str,
        file_path: str,
        format: str = "markdown"
    ) -> bool:
        """Export knowledge entry to file."""
        try:
            entry = await self.get_entry(entry_id)
            if not entry:
                return False
            
            # Format content
            if format == "markdown":
                content = f"# {entry.title}\n\n"
                content += f"**Category:** {entry.category}\n"
                content += f"**Type:** {entry.type}\n"
                content += f"**Tags:** {', '.join(entry.tags)}\n"
                content += f"**Created:** {entry.created_at.isoformat()}\n\n"
                content += entry.content
            elif format == "json":
                content = json.dumps({
                    "id": entry.id,
                    "title": entry.title,
                    "content": entry.content,
                    "type": entry.type,
                    "category": entry.category,
                    "tags": entry.tags,
                    "created_at": entry.created_at.isoformat(),
                    "metadata": entry.metadata
                }, indent=2)
            else:
                content = entry.content
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Exported knowledge entry {entry_id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting entry {entry_id}: {e}")
            return False
    
    # Helper methods
    async def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text using AI model."""
        try:
            # For now, use a simple TF-IDF approach
            # In production, you'd use a proper embedding model
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            # Create a simple embedding using TF-IDF
            vectorizer = TfidfVectorizer(max_features=384, stop_words='english')
            
            # Fit on the text (in production, you'd have a pre-trained model)
            vectors = vectorizer.fit_transform([text])
            
            return vectors.toarray()[0]
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def _calculate_keyword_score(self, query: str, entry: KnowledgeEntryDB) -> float:
        """Calculate keyword matching score."""
        query_lower = query.lower()
        title_lower = entry.title.lower()
        content_lower = entry.content.lower()
        
        score = 0.0
        
        # Title matching (higher weight)
        if query_lower in title_lower:
            score += 0.8
        
        # Content matching
        if query_lower in content_lower:
            score += 0.4
        
        # Word-level matching
        query_words = query_lower.split()
        title_words = title_lower.split()
        content_words = content_lower.split()
        
        title_matches = sum(1 for word in query_words if word in title_words)
        content_matches = sum(1 for word in query_words if word in content_words)
        
        if query_words:
            score += (title_matches / len(query_words)) * 0.3
            score += (content_matches / len(query_words)) * 0.2
        
        return min(1.0, score)
    
    def _calculate_tag_score(self, query: str, tags: List[str]) -> float:
        """Calculate tag matching score."""
        if not tags:
            return 0.0
        
        query_lower = query.lower()
        tag_matches = sum(1 for tag in tags if tag.lower() in query_lower)
        
        return tag_matches / len(tags)
    
    def _db_to_domain(self, db_entry: KnowledgeEntryDB) -> KnowledgeEntry:
        """Convert database model to domain model."""
        return KnowledgeEntry(
            id=db_entry.id,
            title=db_entry.title,
            content=db_entry.content,
            type=db_entry.type,
            category=db_entry.category,
            tags=db_entry.tags,
            source=db_entry.source,
            embedding=db_entry.embedding,
            created_by=db_entry.created_by,
            created_at=db_entry.created_at,
            updated_at=db_entry.updated_at,
            access_count=db_entry.access_count,
            last_accessed=db_entry.last_accessed,
            metadata=db_entry.metadata
        )