"""
Knowledge management module for BrainOps memory system.

Handles document chunking, embedding generation, and semantic retrieval
for the RAG (Retrieval-Augmented Generation) system. Built to provide
AI agents with contextual knowledge for high-quality task execution.
"""

import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import re

import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..core.settings import settings
from ..core.logging import get_logger
from .vector_utils import generate_embeddings, cosine_similarity
from .supabase_client import get_supabase_client


logger = get_logger(__name__)


class KnowledgeManager:
    """
    Comprehensive knowledge management system for RAG.
    
    Transforms documents into searchable knowledge chunks with semantic
    embeddings. Built to provide AI agents with relevant context while
    maintaining performance at scale.
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.encoding = tiktoken.encoding_for_model(settings.EMBEDDING_MODEL)
        
        # Configure text splitter for optimal chunk sizes
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # ~250 tokens for most text
            chunk_overlap=200,  # 20% overlap for context preservation
            length_function=self._count_tokens,
            separators=["\n\n", "\n", ". ", " ", ""]  # Natural break points
        )
    
    async def ingest_document(
        self,
        title: str,
        content: str,
        document_type: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None
    ) -> str:
        """
        Ingest a document into the knowledge base with chunking and embedding.
        
        Transforms raw documents into searchable knowledge, enabling
        AI agents to leverage historical data and domain expertise.
        """
        try:
            # Generate document hash for deduplication
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Check if document already exists
            existing = self.supabase.table("knowledge_documents").select("id").eq(
                "file_hash", content_hash
            ).execute()
            
            if existing.data:
                logger.info(f"Document already exists: {existing.data[0]['id']}")
                return existing.data[0]['id']
            
            # Create document record
            doc_data = {
                "user_id": user_id,
                "title": title,
                "content": content,
                "document_type": document_type,
                "file_path": file_path,
                "file_hash": content_hash,
                "metadata": metadata or {},
                "is_published": True
            }
            
            doc_result = self.supabase.table("knowledge_documents").insert(doc_data).execute()
            document_id = doc_result.data[0]["id"]
            
            # Chunk the content
            chunks = self._chunk_document(content)
            logger.info(f"Created {len(chunks)} chunks for document: {document_id}")
            
            # Process chunks with embeddings
            chunk_records = []
            for idx, chunk_text in enumerate(chunks):
                # Generate embedding for chunk
                embedding = await generate_embeddings(chunk_text)
                
                chunk_records.append({
                    "document_id": document_id,
                    "chunk_index": idx,
                    "content": chunk_text,
                    "embedding": embedding,
                    "metadata": {
                        "char_count": len(chunk_text),
                        "token_count": self._count_tokens(chunk_text)
                    }
                })
            
            # Batch insert chunks
            if chunk_records:
                self.supabase.table("document_chunks").insert(chunk_records).execute()
            
            logger.info(f"Successfully ingested document: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Document ingestion failed: {str(e)}", exc_info=True)
            raise
    
    async def search_knowledge(
        self,
        query: str,
        user_id: Optional[str] = None,
        document_types: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity.
        
        Retrieves relevant knowledge chunks for AI agents, enabling
        context-aware responses and informed decision-making.
        """
        try:
            # Generate query embedding
            query_embedding = await generate_embeddings(query)
            
            # Build base query
            chunk_query = self.supabase.table("document_chunks").select(
                "*, knowledge_documents!inner(id, title, document_type, metadata)"
            )
            
            # Apply filters
            if user_id:
                chunk_query = chunk_query.eq("knowledge_documents.user_id", user_id)
            
            if document_types:
                chunk_query = chunk_query.in_("knowledge_documents.document_type", document_types)
            
            # Execute query (we'll filter by similarity in Python for now)
            # In production, use pgvector's <-> operator for efficient similarity search
            results = chunk_query.execute()
            
            # Calculate similarities and filter
            scored_results = []
            for chunk in results.data:
                # Calculate cosine similarity
                similarity = cosine_similarity(query_embedding, chunk["embedding"])
                
                if similarity >= similarity_threshold:
                    scored_results.append({
                        "chunk_id": chunk["id"],
                        "document_id": chunk["document_id"],
                        "document_title": chunk["knowledge_documents"]["title"],
                        "document_type": chunk["knowledge_documents"]["document_type"],
                        "content": chunk["content"],
                        "chunk_index": chunk["chunk_index"],
                        "similarity": similarity,
                        "metadata": chunk["metadata"]
                    })
            
            # Sort by similarity and limit
            scored_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            return scored_results[:limit]
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {str(e)}", exc_info=True)
            return []
    
    async def get_document_context(
        self,
        document_id: str,
        target_chunk_index: int,
        context_window: int = 2
    ) -> Dict[str, Any]:
        """
        Get expanded context around a specific chunk.
        
        Provides surrounding chunks for better context understanding,
        critical for maintaining coherence in AI responses.
        """
        try:
            # Calculate chunk range
            start_idx = max(0, target_chunk_index - context_window)
            end_idx = target_chunk_index + context_window + 1
            
            # Fetch chunks in range
            chunks = self.supabase.table("document_chunks").select("*").eq(
                "document_id", document_id
            ).gte("chunk_index", start_idx).lt("chunk_index", end_idx).order(
                "chunk_index"
            ).execute()
            
            # Combine chunks into context
            context_parts = []
            for chunk in chunks.data:
                if chunk["chunk_index"] == target_chunk_index:
                    context_parts.append(f"[RELEVANT SECTION]\n{chunk['content']}\n[/RELEVANT SECTION]")
                else:
                    context_parts.append(chunk["content"])
            
            return {
                "document_id": document_id,
                "target_chunk": target_chunk_index,
                "context": "\n\n".join(context_parts),
                "chunk_count": len(chunks.data)
            }
            
        except Exception as e:
            logger.error(f"Failed to get document context: {str(e)}", exc_info=True)
            return {}
    
    def _chunk_document(self, content: str) -> List[str]:
        """
        Split document into semantic chunks for embedding.
        
        Balances chunk size for embedding quality with overlap
        for context preservation. Critical for retrieval accuracy.
        """
        # Clean content for better chunking
        content = self._clean_content(content)
        
        # Use recursive splitter for intelligent chunking
        chunks = self.text_splitter.split_text(content)
        
        # Post-process chunks
        processed_chunks = []
        for chunk in chunks:
            # Skip empty or very short chunks
            if len(chunk.strip()) < 50:
                continue
            
            # Ensure chunk doesn't exceed token limit
            if self._count_tokens(chunk) > 512:
                # Further split oversized chunks
                sub_chunks = self._split_oversized_chunk(chunk)
                processed_chunks.extend(sub_chunks)
            else:
                processed_chunks.append(chunk)
        
        return processed_chunks
    
    def _clean_content(self, content: str) -> str:
        """
        Clean document content for better chunking and embedding.
        
        Removes formatting artifacts that can interfere with
        semantic understanding while preserving meaning.
        """
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove special unicode characters that cause issues
        content = content.encode('ascii', 'ignore').decode('ascii')
        
        # Preserve paragraph structure
        content = re.sub(r'\.(?=[A-Z])', '.\n', content)
        
        return content.strip()
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Accurate token counting ensures chunks fit within model
        context windows while maximizing information density.
        """
        return len(self.encoding.encode(text))
    
    def _split_oversized_chunk(self, chunk: str, max_tokens: int = 512) -> List[str]:
        """
        Split chunks that exceed token limits.
        
        Handles edge cases where single sections are too large,
        ensuring all content is properly indexed.
        """
        sentences = chunk.split('. ')
        sub_chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence + '. ')
            
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                sub_chunks.append('. '.join(current_chunk) + '.')
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            sub_chunks.append('. '.join(current_chunk) + '.')
        
        return sub_chunks
    
    async def update_document(
        self,
        document_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update existing document and re-process chunks if content changed.
        
        Maintains knowledge base accuracy as information evolves,
        critical for decision-making based on current data.
        """
        try:
            # Get existing document
            doc = self.supabase.table("knowledge_documents").select("*").eq(
                "id", document_id
            ).single().execute()
            
            if not doc.data:
                logger.error(f"Document not found: {document_id}")
                return False
            
            # Prepare update data
            update_data = {}
            if title:
                update_data["title"] = title
            if metadata:
                update_data["metadata"] = {**doc.data["metadata"], **metadata}
            
            # Handle content update (requires re-chunking)
            if content and content != doc.data["content"]:
                # Update content and hash
                update_data["content"] = content
                update_data["file_hash"] = hashlib.sha256(content.encode()).hexdigest()
                
                # Delete existing chunks
                self.supabase.table("document_chunks").delete().eq(
                    "document_id", document_id
                ).execute()
                
                # Re-chunk and embed
                chunks = self._chunk_document(content)
                chunk_records = []
                
                for idx, chunk_text in enumerate(chunks):
                    embedding = await generate_embeddings(chunk_text)
                    chunk_records.append({
                        "document_id": document_id,
                        "chunk_index": idx,
                        "content": chunk_text,
                        "embedding": embedding,
                        "metadata": {
                            "char_count": len(chunk_text),
                            "token_count": self._count_tokens(chunk_text)
                        }
                    })
                
                # Insert new chunks
                if chunk_records:
                    self.supabase.table("document_chunks").insert(chunk_records).execute()
            
            # Update document record
            if update_data:
                self.supabase.table("knowledge_documents").update(update_data).eq(
                    "id", document_id
                ).execute()
            
            logger.info(f"Successfully updated document: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Document update failed: {str(e)}", exc_info=True)
            return False


# Global knowledge manager instance
knowledge_manager = KnowledgeManager()


# Convenience functions for task usage
async def ingest_knowledge(title: str, content: str, **kwargs) -> str:
    """Ingest a document into the knowledge base."""
    return await knowledge_manager.ingest_document(title, content, **kwargs)


async def search_knowledge(query: str, **kwargs) -> List[Dict[str, Any]]:
    """Search the knowledge base for relevant information."""
    return await knowledge_manager.search_knowledge(query, **kwargs)