"""
Knowledge Management

Functions for document chunking, embedding generation, and intelligent
retrieval of knowledge base content for the BrainOps system.
"""

from typing import Dict, Any, Optional, List, Tuple
import asyncio
from datetime import datetime
import hashlib
import re
from uuid import UUID, uuid4

from .models import (
    DocumentChunk, KnowledgeEntry, KnowledgeCategory,
    MemoryType, MemoryRecord
)
from .supabase_client import get_supabase_client
from .vector_utils import generate_embedding, chunk_text_with_overlap
from ..core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeManager:
    """
    Manages document processing, chunking, and knowledge base operations.
    Optimized for BrainOps' specific domains: roofing, PM, automation.
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        
        # Chunking parameters optimized for different content types
        self.chunk_configs = {
            "documentation": {
                "chunk_size": 1500,
                "overlap": 200,
                "min_chunk_size": 500
            },
            "technical_specs": {
                "chunk_size": 2000,
                "overlap": 300,
                "min_chunk_size": 800
            },
            "templates": {
                "chunk_size": 1000,
                "overlap": 150,
                "min_chunk_size": 400
            },
            "estimates": {
                "chunk_size": 800,
                "overlap": 100,
                "min_chunk_size": 300
            }
        }
    
    async def ingest_document(
        self,
        title: str,
        content: str,
        document_type: str,
        category: KnowledgeCategory,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Ingest a document into the knowledge base with intelligent chunking.
        
        Args:
            title: Document title
            content: Full document content
            document_type: Type of document (documentation, template, etc.)
            category: Knowledge category
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        
        document_id = uuid4()
        
        # Select chunking configuration
        config = self.chunk_configs.get(
            document_type, 
            self.chunk_configs["documentation"]
        )
        
        # Create document hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if document already exists
        existing = await self._check_duplicate_document(content_hash)
        if existing:
            logger.info(f"Document already exists with ID: {existing}")
            return existing
        
        try:
            # Store document metadata
            doc_metadata = {
                "id": str(document_id),
                "title": title,
                "document_type": document_type,
                "category": category.value,
                "content_hash": content_hash,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table('documents').insert(doc_metadata).execute()
            
            # Process and store chunks
            chunks = await self._create_document_chunks(
                document_id=document_id,
                content=content,
                title=title,
                document_type=document_type,
                config=config,
                metadata=metadata
            )
            
            logger.info(f"Ingested document '{title}' with {len(chunks)} chunks")
            
            # Create knowledge entry if it's curated content
            if metadata and metadata.get("curated", False):
                await self._create_knowledge_entry(
                    document_id=document_id,
                    title=title,
                    content=content,
                    category=category,
                    metadata=metadata
                )
            
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to ingest document: {str(e)}")
            raise
    
    async def search_knowledge(
        self,
        query: str,
        categories: Optional[List[KnowledgeCategory]] = None,
        document_types: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base using semantic similarity.
        
        Args:
            query: Search query
            categories: Filter by categories
            document_types: Filter by document types
            limit: Maximum results
            threshold: Minimum similarity threshold
            
        Returns:
            List of relevant knowledge items with metadata
        """
        
        # Generate query embedding
        query_embedding = await generate_embedding(query)
        
        try:
            # Build vector search query
            search_params = {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": limit * 2  # Get extra for filtering
            }
            
            # Execute vector search
            result = self.supabase.rpc(
                'search_document_chunks',
                search_params
            ).execute()
            
            # Process and filter results
            chunks = []
            for chunk_data in result.data:
                # Apply category filter
                if categories and chunk_data['category'] not in [c.value for c in categories]:
                    continue
                    
                # Apply document type filter
                if document_types and chunk_data['document_type'] not in document_types:
                    continue
                
                chunks.append({
                    "chunk_id": chunk_data['id'],
                    "document_id": chunk_data['document_id'],
                    "document_title": chunk_data['document_title'],
                    "text": chunk_data['text'],
                    "similarity": chunk_data['similarity'],
                    "metadata": chunk_data.get('document_metadata', {}),
                    "category": chunk_data['category'],
                    "document_type": chunk_data['document_type']
                })
                
                if len(chunks) >= limit:
                    break
            
            # Group chunks by document and aggregate
            grouped_results = await self._group_chunks_by_document(chunks)
            
            return grouped_results[:limit]
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {str(e)}")
            return []
    
    async def get_context_for_task(
        self,
        task_type: str,
        parameters: Dict[str, Any],
        max_context_length: int = 4000
    ) -> str:
        """
        Retrieve relevant context for a specific task type.
        
        Args:
            task_type: Type of task (e.g., "generate_estimate", "create_template")
            parameters: Task-specific parameters
            max_context_length: Maximum context length in characters
            
        Returns:
            Formatted context string
        """
        
        # Build context query based on task type
        context_queries = self._build_context_queries(task_type, parameters)
        
        all_context_items = []
        
        # Execute multiple targeted searches
        for query in context_queries:
            results = await self.search_knowledge(
                query=query["query"],
                categories=query.get("categories"),
                document_types=query.get("document_types"),
                limit=query.get("limit", 5),
                threshold=query.get("threshold", 0.7)
            )
            
            all_context_items.extend(results)
        
        # Deduplicate and rank results
        unique_items = self._deduplicate_context_items(all_context_items)
        
        # Build context string within length limit
        context = await self._build_context_string(
            items=unique_items,
            max_length=max_context_length,
            task_type=task_type
        )
        
        return context
    
    async def update_knowledge_entry(
        self,
        entry_id: UUID,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update a curated knowledge entry.
        
        Args:
            entry_id: Knowledge entry ID
            updates: Dictionary of fields to update
            
        Returns:
            Success status
        """
        
        try:
            # Add updated timestamp
            updates["updated_at"] = datetime.utcnow().isoformat()
            
            # Increment version if content changed
            if "body" in updates:
                current = self.supabase.table('knowledge_entries')\
                    .select('version')\
                    .eq('id', str(entry_id))\
                    .single()\
                    .execute()
                
                if current.data:
                    version_parts = current.data['version'].split('.')
                    version_parts[2] = str(int(version_parts[2]) + 1)
                    updates['version'] = '.'.join(version_parts)
            
            # Update the entry
            result = self.supabase.table('knowledge_entries')\
                .update(updates)\
                .eq('id', str(entry_id))\
                .execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to update knowledge entry: {str(e)}")
            return False
    
    async def validate_knowledge_entry(
        self,
        entry_id: UUID,
        validation_notes: Optional[str] = None
    ) -> bool:
        """
        Mark a knowledge entry as validated by human review.
        """
        
        updates = {
            "validated": True,
            "validation_date": datetime.utcnow().isoformat(),
            "quality_score": 1.0  # Max score for human-validated content
        }
        
        if validation_notes:
            updates["metadata"] = {"validation_notes": validation_notes}
        
        return await self.update_knowledge_entry(entry_id, updates)
    
    # Private helper methods
    
    async def _create_document_chunks(
        self,
        document_id: UUID,
        content: str,
        title: str,
        document_type: str,
        config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """
        Create and store document chunks with embeddings.
        """
        
        # Special handling for different document types
        if document_type == "estimates":
            chunks = self._chunk_estimate_content(content, config)
        elif document_type == "templates":
            chunks = self._chunk_template_content(content, config)
        else:
            chunks = chunk_text_with_overlap(
                content,
                chunk_size=config["chunk_size"],
                overlap=config["overlap"],
                min_chunk_size=config["min_chunk_size"]
            )
        
        # Create chunk objects and generate embeddings
        chunk_objects = []
        
        for idx, (text, start, end) in enumerate(chunks):
            # Generate embedding for chunk
            embedding = await generate_embedding(text)
            
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=idx,
                text=text,
                start_char=start,
                end_char=end,
                document_title=title,
                document_type=document_type,
                document_metadata=metadata or {},
                embedding=embedding
            )
            
            chunk_objects.append(chunk)
        
        # Batch insert chunks
        if chunk_objects:
            chunk_dicts = [
                {
                    **chunk.dict(exclude={'id'}),
                    "id": str(chunk.id)
                }
                for chunk in chunk_objects
            ]
            
            self.supabase.table('document_chunks').insert(chunk_dicts).execute()
        
        return chunk_objects
    
    def _chunk_estimate_content(
        self,
        content: str,
        config: Dict[str, Any]
    ) -> List[Tuple[str, int, int]]:
        """
        Special chunking for roofing estimates to preserve structure.
        """
        
        # Split by major sections
        sections = re.split(r'\n(?=(?:SCOPE|MATERIALS|LABOR|EQUIPMENT|WARRANTY|TERMS))', content)
        
        chunks = []
        current_pos = 0
        
        for section in sections:
            if len(section) > config["chunk_size"]:
                # Further chunk large sections
                sub_chunks = chunk_text_with_overlap(
                    section,
                    chunk_size=config["chunk_size"],
                    overlap=config["overlap"],
                    min_chunk_size=config["min_chunk_size"]
                )
                
                for text, start, end in sub_chunks:
                    chunks.append((text, current_pos + start, current_pos + end))
            else:
                chunks.append((section, current_pos, current_pos + len(section)))
            
            current_pos += len(section) + 1  # +1 for newline
        
        return chunks
    
    def _chunk_template_content(
        self,
        content: str,
        config: Dict[str, Any]
    ) -> List[Tuple[str, int, int]]:
        """
        Special chunking for templates to preserve logical blocks.
        """
        
        # Look for template sections or code blocks
        blocks = re.split(r'(?=```)|(?<=```)', content)
        
        chunks = []
        current_pos = 0
        current_chunk = ""
        
        for block in blocks:
            if len(current_chunk) + len(block) <= config["chunk_size"]:
                current_chunk += block
            else:
                if current_chunk:
                    chunks.append((
                        current_chunk,
                        current_pos - len(current_chunk),
                        current_pos
                    ))
                current_chunk = block
            
            current_pos += len(block)
        
        # Add final chunk
        if current_chunk:
            chunks.append((
                current_chunk,
                current_pos - len(current_chunk),
                current_pos
            ))
        
        return chunks
    
    async def _check_duplicate_document(self, content_hash: str) -> Optional[UUID]:
        """
        Check if a document with the same content hash already exists.
        """
        
        try:
            result = self.supabase.table('documents')\
                .select('id')\
                .eq('content_hash', content_hash)\
                .single()\
                .execute()
            
            if result.data:
                return UUID(result.data['id'])
                
        except Exception:
            pass
            
        return None
    
    async def _create_knowledge_entry(
        self,
        document_id: UUID,
        title: str,
        content: str,
        category: KnowledgeCategory,
        metadata: Dict[str, Any]
    ):
        """
        Create a curated knowledge entry from a document.
        """
        
        entry = KnowledgeEntry(
            category=category,
            title=title,
            description=metadata.get("description", ""),
            body=content,
            structured_data=metadata.get("structured_data"),
            examples=metadata.get("examples", []),
            references=metadata.get("references", []),
            validated=metadata.get("validated", False)
        )
        
        try:
            self.supabase.table('knowledge_entries').insert({
                **entry.dict(exclude={'id'}),
                "id": str(entry.id),
                "document_id": str(document_id)
            }).execute()
            
            logger.info(f"Created knowledge entry: {entry.title}")
            
        except Exception as e:
            logger.error(f"Failed to create knowledge entry: {str(e)}")
    
    async def _group_chunks_by_document(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Group chunks by document and aggregate relevance.
        """
        
        document_groups = {}
        
        for chunk in chunks:
            doc_id = chunk['document_id']
            
            if doc_id not in document_groups:
                document_groups[doc_id] = {
                    "document_id": doc_id,
                    "document_title": chunk['document_title'],
                    "category": chunk['category'],
                    "document_type": chunk['document_type'],
                    "metadata": chunk['metadata'],
                    "chunks": [],
                    "max_similarity": 0,
                    "avg_similarity": 0
                }
            
            document_groups[doc_id]['chunks'].append({
                "text": chunk['text'],
                "similarity": chunk['similarity']
            })
            
            document_groups[doc_id]['max_similarity'] = max(
                document_groups[doc_id]['max_similarity'],
                chunk['similarity']
            )
        
        # Calculate average similarity and sort chunks
        results = []
        for doc_data in document_groups.values():
            total_sim = sum(c['similarity'] for c in doc_data['chunks'])
            doc_data['avg_similarity'] = total_sim / len(doc_data['chunks'])
            
            # Sort chunks by similarity
            doc_data['chunks'].sort(key=lambda x: x['similarity'], reverse=True)
            
            # Keep only top 3 chunks per document
            doc_data['chunks'] = doc_data['chunks'][:3]
            
            results.append(doc_data)
        
        # Sort by maximum similarity
        results.sort(key=lambda x: x['max_similarity'], reverse=True)
        
        return results
    
    def _build_context_queries(
        self,
        task_type: str,
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build targeted queries for different task types.
        """
        
        queries = []
        
        if task_type == "generate_estimate":
            # Query for similar estimates
            queries.append({
                "query": f"{parameters.get('system_type', 'roofing')} estimate {parameters.get('building_type', '')}",
                "categories": [KnowledgeCategory.ROOFING],
                "document_types": ["estimates"],
                "limit": 3
            })
            
            # Query for technical specifications
            queries.append({
                "query": f"{parameters.get('system_type', 'TPO')} specifications installation",
                "categories": [KnowledgeCategory.TECHNICAL_SPECS],
                "limit": 2
            })
            
        elif task_type == "generate_product_docs":
            # Query for similar products
            queries.append({
                "query": f"{parameters.get('product_type', '')} {parameters.get('vertical', '')} template",
                "categories": [self._get_category_for_vertical(parameters.get('vertical', ''))],
                "document_types": ["templates", "documentation"],
                "limit": 3
            })
            
            # Query for best practices
            queries.append({
                "query": f"{parameters.get('vertical', '')} best practices documentation",
                "categories": [KnowledgeCategory.BEST_PRACTICES],
                "limit": 2
            })
        
        return queries
    
    def _deduplicate_context_items(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate context items based on document ID.
        """
        
        seen_docs = set()
        unique_items = []
        
        for item in items:
            doc_id = item['document_id']
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                unique_items.append(item)
        
        return unique_items
    
    async def _build_context_string(
        self,
        items: List[Dict[str, Any]],
        max_length: int,
        task_type: str
    ) -> str:
        """
        Build a formatted context string within length limits.
        """
        
        context_parts = [
            f"# Relevant Context for {task_type}\n"
        ]
        
        current_length = len(context_parts[0])
        
        for item in items:
            # Build item context
            item_context = f"\n## {item['document_title']}\n"
            item_context += f"Type: {item['document_type']} | Category: {item['category']}\n"
            
            # Add most relevant chunks
            for chunk in item['chunks'][:2]:  # Max 2 chunks per document
                chunk_text = chunk['text'][:500]  # Limit chunk length
                item_context += f"\n{chunk_text}\n"
            
            # Check if adding this would exceed limit
            if current_length + len(item_context) > max_length:
                break
                
            context_parts.append(item_context)
            current_length += len(item_context)
        
        return ''.join(context_parts)
    
    def _get_category_for_vertical(self, vertical: str) -> KnowledgeCategory:
        """
        Map vertical to knowledge category.
        """
        
        mapping = {
            "roofing": KnowledgeCategory.ROOFING,
            "pm": KnowledgeCategory.PROJECT_MANAGEMENT,
            "automation": KnowledgeCategory.AUTOMATION,
            "passive-income": KnowledgeCategory.PASSIVE_INCOME
        }
        
        return mapping.get(vertical, KnowledgeCategory.TEMPLATES)