"""Retrieval-Augmented Generation with pgvector for semantic search."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any

import numpy as np
from loguru import logger
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from core.settings import Settings
from db.models import Document, User
from utils.metrics import RAG_QUERY_DURATION, RAG_DOCUMENTS_RETRIEVED, EMBEDDING_GENERATION_DURATION

settings = Settings()

# Initialize OpenAI client for embeddings
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class RAGEngine:
    """Enhanced RAG engine with pgvector for semantic search."""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI."""
        start_time = datetime.now()
        
        try:
            response = await openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            
            # Track metrics
            duration = (datetime.now() - start_time).total_seconds()
            EMBEDDING_GENERATION_DURATION.observe(duration)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def add_document(
        self,
        title: str,
        content: str,
        source: str = "manual",
        source_url: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Add a document to the RAG system with embedding."""
        # Generate embedding
        embedding = await self.generate_embedding(content)
        
        # Create document
        document = Document(
            user_id=self.user_id,
            title=title,
            content=content,
            embedding=embedding,
            source=source,
            source_url=source_url,
            category=category or "general",
            tags=tags or [],
            metadata=metadata or {}
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        logger.info(f"Added document: {title} (ID: {document.id})")
        return document
    
    async def search_documents(
        self,
        query: str,
        limit: int = 10,
        category: Optional[str] = None,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search documents using semantic similarity."""
        start_time = datetime.now()
        
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Build SQL query with pgvector
        sql = text("""
            SELECT 
                id,
                title,
                content,
                source,
                source_url,
                category,
                tags,
                metadata,
                created_at,
                1 - (embedding <=> :embedding) as similarity
            FROM documents
            WHERE user_id = :user_id
                AND (1 - (embedding <=> :embedding)) > :threshold
                AND (:category IS NULL OR category = :category)
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)
        
        # Execute query
        result = self.db.execute(
            sql,
            {
                "embedding": query_embedding,
                "user_id": self.user_id,
                "threshold": similarity_threshold,
                "category": category,
                "limit": limit
            }
        )
        
        documents = []
        for row in result:
            documents.append({
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "source": row.source,
                "source_url": row.source_url,
                "category": row.category,
                "tags": row.tags,
                "metadata": row.metadata,
                "created_at": row.created_at,
                "similarity": row.similarity
            })
        
        # Track metrics
        duration = (datetime.now() - start_time).total_seconds()
        RAG_QUERY_DURATION.observe(duration)
        RAG_DOCUMENTS_RETRIEVED.observe(len(documents))
        
        logger.info(f"Found {len(documents)} documents for query: {query}")
        return documents
    
    async def hybrid_search(
        self,
        query: str,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining keyword and semantic search."""
        # Semantic search
        semantic_results = await self.search_documents(query, limit=limit * 2)
        
        # Keyword search using PostgreSQL full-text search
        keyword_sql = text("""
            SELECT 
                id,
                title,
                content,
                source,
                source_url,
                category,
                tags,
                metadata,
                created_at,
                ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) as rank
            FROM documents
            WHERE user_id = :user_id
                AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)
        
        keyword_result = self.db.execute(
            keyword_sql,
            {"query": query, "user_id": self.user_id, "limit": limit * 2}
        )
        
        # Combine results with weighted scores
        combined_scores = {}
        
        # Add semantic results
        for doc in semantic_results:
            doc_id = doc["id"]
            combined_scores[doc_id] = {
                **doc,
                "combined_score": doc["similarity"] * semantic_weight
            }
        
        # Add keyword results
        max_rank = 0.0
        for row in keyword_result:
            max_rank = max(max_rank, row.rank)
            
        keyword_result = self.db.execute(
            keyword_sql,
            {"query": query, "user_id": self.user_id, "limit": limit * 2}
        )
        
        for row in keyword_result:
            doc_id = row.id
            normalized_rank = row.rank / max_rank if max_rank > 0 else 0
            
            if doc_id in combined_scores:
                combined_scores[doc_id]["combined_score"] += normalized_rank * keyword_weight
            else:
                combined_scores[doc_id] = {
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "source": row.source,
                    "source_url": row.source_url,
                    "category": row.category,
                    "tags": row.tags,
                    "metadata": row.metadata,
                    "created_at": row.created_at,
                    "combined_score": normalized_rank * keyword_weight
                }
        
        # Sort by combined score and return top results
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )[:limit]
        
        return sorted_results
    
    async def get_context_for_prompt(
        self,
        query: str,
        max_context_length: int = 4000,
        include_metadata: bool = True
    ) -> str:
        """Get relevant context for a prompt using RAG."""
        # Search for relevant documents
        documents = await self.hybrid_search(query, limit=5)
        
        if not documents:
            return ""
        
        # Build context
        context_parts = []
        current_length = 0
        
        for doc in documents:
            # Format document
            doc_text = f"## {doc['title']}\n"
            
            if include_metadata:
                doc_text += f"Source: {doc['source']}"
                if doc['source_url']:
                    doc_text += f" ({doc['source_url']})"
                doc_text += f"\nCategory: {doc['category']}\n"
                if doc['tags']:
                    doc_text += f"Tags: {', '.join(doc['tags'])}\n"
            
            doc_text += f"\n{doc['content']}\n\n---\n\n"
            
            # Check if adding this document would exceed the limit
            if current_length + len(doc_text) > max_context_length:
                # Try to add a truncated version
                remaining_space = max_context_length - current_length
                if remaining_space > 500:  # Only add if we have reasonable space
                    truncated_content = doc['content'][:remaining_space - 200] + "..."
                    doc_text = f"## {doc['title']} (truncated)\n{truncated_content}\n\n"
                    context_parts.append(doc_text)
                break
            
            context_parts.append(doc_text)
            current_length += len(doc_text)
        
        return "".join(context_parts)
    
    async def update_document_embedding(self, document_id: int):
        """Update embedding for an existing document."""
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == self.user_id
        ).first()
        
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Generate new embedding
        embedding = await self.generate_embedding(document.content)
        
        # Update document
        document.embedding = embedding
        document.updated_at = datetime.utcnow()
        
        self.db.commit()
        logger.info(f"Updated embedding for document: {document.title}")
    
    async def batch_add_documents(self, documents: List[Dict[str, Any]]):
        """Add multiple documents in batch."""
        tasks = []
        
        for doc_data in documents:
            task = self.add_document(
                title=doc_data["title"],
                content=doc_data["content"],
                source=doc_data.get("source", "batch"),
                source_url=doc_data.get("source_url"),
                category=doc_data.get("category"),
                tags=doc_data.get("tags"),
                metadata=doc_data.get("metadata")
            )
            tasks.append(task)
        
        # Process in parallel with concurrency limit
        results = []
        for i in range(0, len(tasks), 5):  # Process 5 at a time
            batch = tasks[i:i+5]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        
        # Log results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        logger.info(f"Batch add complete: {successful} successful, {failed} failed")
        
        return results
    
    async def delete_document(self, document_id: int):
        """Delete a document from the RAG system."""
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == self.user_id
        ).first()
        
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        self.db.delete(document)
        self.db.commit()
        
        logger.info(f"Deleted document: {document.title}")
    
    async def get_document_stats(self) -> Dict[str, Any]:
        """Get statistics about documents in the RAG system."""
        total_count = self.db.query(Document).filter(
            Document.user_id == self.user_id
        ).count()
        
        category_counts = self.db.execute(
            text("""
                SELECT category, COUNT(*) as count
                FROM documents
                WHERE user_id = :user_id
                GROUP BY category
                ORDER BY count DESC
            """),
            {"user_id": self.user_id}
        ).fetchall()
        
        source_counts = self.db.execute(
            text("""
                SELECT source, COUNT(*) as count
                FROM documents
                WHERE user_id = :user_id
                GROUP BY source
                ORDER BY count DESC
            """),
            {"user_id": self.user_id}
        ).fetchall()
        
        return {
            "total_documents": total_count,
            "categories": {row.category: row.count for row in category_counts},
            "sources": {row.source: row.count for row in source_counts}
        }


# Utility functions for document preprocessing
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks for better context."""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to end at a sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            if last_period > chunk_size - 200:
                end = start + last_period + 1
                chunk = text[start:end]
        
        chunks.append(chunk)
        start = end - overlap
    
    return chunks


def extract_metadata_from_content(content: str) -> Dict[str, Any]:
    """Extract metadata from document content."""
    metadata = {}
    
    # Extract potential dates
    import re
    date_pattern = r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b'
    dates = re.findall(date_pattern, content)
    if dates:
        metadata["dates_mentioned"] = dates
    
    # Extract potential URLs
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, content)
    if urls:
        metadata["urls_mentioned"] = urls
    
    # Extract potential email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, content)
    if emails:
        metadata["emails_mentioned"] = emails
    
    return metadata