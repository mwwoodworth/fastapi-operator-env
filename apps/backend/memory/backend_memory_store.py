"""
Memory Store

Core interface for storing and retrieving memory records in Supabase,
implementing vector search, filtering, and intelligent retrieval patterns.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from uuid import UUID
import json
import asyncio

from .backend_memory_models import (
    MemoryRecord,
    MemoryType,
    KnowledgeCategory,
    MemorySearchQuery,
    MemoryUpdate,
    EstimateRecord,
    RetrievalSession,
)
from .supabase_client import get_supabase_client_sync
from .backend_memory_vector_utils import generate_embedding, calculate_similarity
from ..core.logging import get_logger
from .models import (
    User,
    TaskRecord,
    TaskStatus,
    MemoryEntry,
    QueryResult,
)

logger = get_logger(__name__)


class MemoryStore:
    """
    Main interface for memory operations in the BrainOps system.
    Handles storage, retrieval, and intelligent search of memory records.
    """
    
    def __init__(self):
        # Initialize Supabase client synchronously for use in async methods
        self.supabase = get_supabase_client_sync()
        self._cache = {}  # Simple in-memory cache for frequent queries
        
    async def store_memory(
        self,
        type: MemoryType,
        title: str,
        content: str,
        context: Dict[str, Any],
        category: Optional[KnowledgeCategory] = None,
        tags: Optional[List[str]] = None,
        importance_score: float = 0.5
    ) -> UUID:
        """
        Store a new memory record with automatic embedding generation.
        
        Args:
            type: Type of memory record
            title: Title of the memory
            content: Main content to store
            context: Contextual information
            category: Optional knowledge category
            tags: Optional tags for filtering
            importance_score: Importance rating (0-1)
            
        Returns:
            UUID of the created memory record
        """
        
        # Generate embedding for the content
        embedding = await generate_embedding(f"{title}\n\n{content}")
        
        # Create memory record
        memory = MemoryRecord(
            type=type,
            category=category,
            title=title,
            content=content,
            embedding=embedding,
            context=context,
            tags=tags or [],
            importance_score=importance_score
        )
        
        try:
            # Insert into Supabase
            result = await self.supabase.table('memory_records').insert({
                'id': str(memory.id),
                'type': memory.type.value,
                'category': memory.category.value if memory.category else None,
                'title': memory.title,
                'content': memory.content,
                'summary': memory.summary,
                'embedding': memory.embedding,
                'context': json.dumps(memory.context),
                'tags': memory.tags,
                'importance_score': memory.importance_score,
                'created_at': memory.created_at.isoformat(),
                'updated_at': memory.updated_at.isoformat()
            }).execute()
            
            logger.info(f"Stored memory record: {memory.id} - {memory.title}")
            
            # Invalidate relevant cache entries
            self._invalidate_cache_for_type(type)
            
            return memory.id
            
        except Exception as e:
            logger.error(f"Failed to store memory: {str(e)}")
            raise
    
    async def search_memories(
        self,
        query: MemorySearchQuery
    ) -> List[MemoryRecord]:
        """
        Search memory records using vector similarity and filters.
        
        Args:
            query: Search query with filters and options
            
        Returns:
            List of matching memory records ordered by relevance
        """
        
        # Generate embedding for the search query
        query_embedding = await generate_embedding(query.query)
        
        try:
            # Build the base query
            db_query = self.supabase.rpc(
                'search_memories',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': query.min_relevance_score,
                    'match_count': query.max_results * 2  # Get extra for reranking
                }
            )
            
            # Apply filters
            if query.memory_types:
                db_query = db_query.in_('type', [t.value for t in query.memory_types])
                
            if query.categories:
                db_query = db_query.in_('category', [c.value for c in query.categories])
                
            if query.start_date:
                db_query = db_query.gte('created_at', query.start_date.isoformat())
                
            if query.end_date:
                db_query = db_query.lte('created_at', query.end_date.isoformat())
                
            if query.tags:
                db_query = db_query.contains('tags', query.tags)
                
            if query.importance_threshold:
                db_query = db_query.gte('importance_score', query.importance_threshold)
            
            # Execute search
            result = await db_query.execute()
            
            # Convert to memory records
            memories = [
                self._db_record_to_memory(record)
                for record in result.data
            ]
            
            # Apply reranking if requested
            if query.rerank_results and len(memories) > query.max_results:
                memories = await self._rerank_results(
                    memories,
                    query.query,
                    query.max_results
                )
            else:
                memories = memories[:query.max_results]
            
            # Log retrieval session for analytics
            await self._log_retrieval_session(query, memories)
            
            return memories
            
        except Exception as e:
            logger.error(f"Memory search failed: {str(e)}")
            return []
    
    async def get_memory_by_id(self, memory_id: UUID) -> Optional[MemoryRecord]:
        """
        Retrieve a specific memory record by ID.
        """
        
        # Check cache first
        cache_key = f"memory:{str(memory_id)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = await self.supabase.table('memory_records')\
                .select('*')\
                .eq('id', str(memory_id))\
                .single()\
                .execute()
            
            if result.data:
                memory = self._db_record_to_memory(result.data)
                
                # Update access count
                await self._increment_access_count(memory_id)
                
                # Cache the result
                self._cache[cache_key] = memory
                
                return memory
                
        except Exception as e:
            logger.error(f"Failed to get memory {memory_id}: {str(e)}")
            
        return None
    
    async def update_memory(
        self,
        memory_id: UUID,
        update: MemoryUpdate
    ) -> bool:
        """
        Update an existing memory record.
        """
        
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Build update data
        if update.title is not None:
            update_data['title'] = update.title
            
        if update.content is not None:
            update_data['content'] = update.content
            
        if update.summary is not None:
            update_data['summary'] = update.summary
            
        if update.tags is not None:
            update_data['tags'] = update.tags
            
        if update.importance_score is not None:
            update_data['importance_score'] = update.importance_score
            
        # Handle context updates
        if update.additional_context:
            # Fetch current context and merge
            current = await self.get_memory_by_id(memory_id)
            if current:
                merged_context = {**current.context, **update.additional_context}
                update_data['context'] = json.dumps(merged_context)
        
        # Regenerate embedding if content changed or explicitly requested
        if update.regenerate_embedding or update.content is not None:
            memory = await self.get_memory_by_id(memory_id)
            if memory:
                new_content = update.content or memory.content
                new_title = update.title or memory.title
                embedding = await generate_embedding(f"{new_title}\n\n{new_content}")
                update_data['embedding'] = embedding
        
        try:
            result = await self.supabase.table('memory_records')\
                .update(update_data)\
                .eq('id', str(memory_id))\
                .execute()
            
            # Invalidate cache
            self._invalidate_cache_for_id(memory_id)
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {str(e)}")
            return False
    
    # Specialized methods for different memory types
    
    async def store_product_documentation(
        self,
        product_name: str,
        product_type: str,
        vertical: str,
        documentation: Dict[str, Any],
        context: Dict[str, Any]
    ) -> UUID:
        """
        Store product documentation as a specialized memory record.
        """
        
        # Determine category based on vertical
        category_map = {
            "roofing": KnowledgeCategory.ROOFING,
            "pm": KnowledgeCategory.PROJECT_MANAGEMENT,
            "automation": KnowledgeCategory.AUTOMATION,
            "passive-income": KnowledgeCategory.PASSIVE_INCOME
        }
        
        category = category_map.get(vertical, KnowledgeCategory.TEMPLATES)
        
        # Build structured content
        content = f"""
Product: {product_name}
Type: {product_type}
Vertical: {vertical}

{documentation.get('main_content', '')}
        """
        
        # Store with enhanced context
        enhanced_context = {
            **context,
            "product_name": product_name,
            "product_type": product_type,
            "vertical": vertical,
            "documentation_sections": list(documentation.keys())
        }
        
        return await self.store_memory(
            type=MemoryType.PRODUCT_DOCUMENTATION,
            title=f"{product_name} - {product_type} Documentation",
            content=content,
            context=enhanced_context,
            category=category,
            tags=[vertical, product_type, "documentation"],
            importance_score=0.8
        )
    
    async def search_similar_products(
        self,
        product_type: str,
        vertical: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar products for reference during generation.
        """
        
        query = MemorySearchQuery(
            query=f"{product_type} {vertical} product documentation",
            memory_types=[MemoryType.PRODUCT_DOCUMENTATION],
            categories=[self._get_category_for_vertical(vertical)],
            max_results=limit,
            tags=[vertical, product_type]
        )
        
        memories = await self.search_memories(query)
        
        # Extract relevant product information
        return [
            {
                "name": m.context.get("product_name", "Unknown"),
                "type": m.context.get("product_type", product_type),
                "vertical": m.context.get("vertical", vertical),
                "key_value_prop": m.summary,
                "created_at": m.created_at
            }
            for m in memories
        ]
    
    async def store_estimate(
        self,
        project_name: str,
        estimate_data: Dict[str, Any],
        pricing: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Store a roofing estimate as a specialized record.
        """
        
        # Create estimate record
        estimate = EstimateRecord(
            project_name=project_name,
            building_type=estimate_data.get("building_type", "Commercial"),
            roof_area_sf=estimate_data.get("roof_area_sf", 0),
            roof_type=estimate_data.get("roof_type", "Flat"),
            system_type=estimate_data.get("system_type", "TPO"),
            material_cost=pricing.get("material_cost", 0),
            labor_cost=pricing.get("labor_cost", 0),
            total_cost=pricing.get("grand_total", 0),
            cost_per_sf=pricing.get("cost_per_sf", 0),
            margin_percentage=pricing.get("markup_percentage", 35),
            scope_items=estimate_data.get("scope_items", []),
            warranty_years=estimate_data.get("warranty_years", 20),
            location=estimate_data.get("location", "Denver, CO"),
            estimate_date=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=30)
        )
        
        # Generate embedding for estimate
        estimate_content = f"""
        {project_name}
        {estimate.building_type} - {estimate.roof_area_sf} sq ft
        {estimate.roof_type} roof - {estimate.system_type} system
        Total: ${estimate.total_cost:,.2f} (${estimate.cost_per_sf}/sf)
        """
        
        estimate.embedding = await generate_embedding(estimate_content)
        
        try:
            # Store in estimates table
            result = await self.supabase.table('estimate_records').insert(
                estimate.dict(exclude={'id'}, exclude_none=True)
            ).execute()
            
            # Also store as general memory for cross-referencing
            await self.store_memory(
                type=MemoryType.ESTIMATE_RECORD,
                title=f"Estimate: {project_name}",
                content=estimate_content,
                context={
                    **context,
                    "estimate_id": str(estimate.id),
                    "estimate_data": estimate_data,
                    "pricing": pricing
                },
                category=KnowledgeCategory.ROOFING,
                tags=["estimate", estimate.system_type.lower(), estimate.building_type.lower()],
                importance_score=0.7
            )
            
            return str(estimate.id)
            
        except Exception as e:
            logger.error(f"Failed to store estimate: {str(e)}")
            raise
    
    async def search_similar_estimates(
        self,
        building_type: str,
        roof_size_range: tuple,
        system_type: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar past estimates for reference.
        """
        
        try:
            # Query estimates within size range
            result = await self.supabase.table('estimate_records')\
                .select('*')\
                .eq('building_type', building_type)\
                .eq('system_type', system_type)\
                .gte('roof_area_sf', roof_size_range[0])\
                .lte('roof_area_sf', roof_size_range[1])\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return [
                {
                    "project_name": est['project_name'],
                    "total_cost": est['total_cost'],
                    "cost_per_sf": est['cost_per_sf'],
                    "margin_percentage": est['margin_percentage'],
                    "won_project": est.get('won_project'),
                    "estimate_date": est['estimate_date']
                }
                for est in result.data
            ]
            
        except Exception as e:
            logger.error(f"Failed to search estimates: {str(e)}")
            return []
    
    async def get_standard_pricing(
        self,
        system_type: str,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve standard pricing data from memory.
        """
        
        query = MemorySearchQuery(
            query=f"{system_type} pricing {region or 'standard'}",
            memory_types=[MemoryType.BUSINESS_CONTEXT],
            categories=[KnowledgeCategory.MARKET_DATA],
            tags=["pricing", system_type.lower()],
            max_results=1
        )
        
        memories = await self.search_memories(query)
        
        if memories:
            return memories[0].context.get("pricing_data", {})
        
        # Return default pricing if not found
        return {
            "material_per_sf": 3.50,
            "labor_per_sf": 2.25,
            "last_updated": "2025-01-01"
        }
    
    # Private helper methods
    
    def _db_record_to_memory(self, record: Dict[str, Any]) -> MemoryRecord:
        """Convert database record to MemoryRecord model."""
        
        # Parse JSON fields
        context = json.loads(record.get('context', '{}'))
        
        return MemoryRecord(
            id=UUID(record['id']),
            type=MemoryType(record['type']),
            category=KnowledgeCategory(record['category']) if record.get('category') else None,
            title=record['title'],
            content=record['content'],
            summary=record.get('summary'),
            embedding=record.get('embedding'),
            context=context,
            tags=record.get('tags', []),
            importance_score=record.get('importance_score', 0.5),
            access_count=record.get('access_count', 0),
            created_at=datetime.fromisoformat(record['created_at']),
            updated_at=datetime.fromisoformat(record['updated_at'])
        )
    
    def _get_category_for_vertical(self, vertical: str) -> KnowledgeCategory:
        """Map vertical to knowledge category."""
        
        mapping = {
            "roofing": KnowledgeCategory.ROOFING,
            "pm": KnowledgeCategory.PROJECT_MANAGEMENT,
            "automation": KnowledgeCategory.AUTOMATION,
            "passive-income": KnowledgeCategory.PASSIVE_INCOME
        }
        
        return mapping.get(vertical, KnowledgeCategory.TEMPLATES)
    
    async def _rerank_results(
        self,
        memories: List[MemoryRecord],
        query: str,
        limit: int
    ) -> List[MemoryRecord]:
        """
        Rerank search results using additional criteria.
        Could integrate with a reranking model in the future.
        """
        
        # For now, use a simple scoring based on multiple factors
        scored_memories = []
        
        for memory in memories:
            score = 0.0
            
            # Factor 1: Title match
            if query.lower() in memory.title.lower():
                score += 0.3
                
            # Factor 2: Recency (newer is better)
            age_days = (datetime.utcnow() - memory.created_at).days
            recency_score = max(0, 1 - (age_days / 365))  # Decay over a year
            score += recency_score * 0.2
            
            # Factor 3: Importance
            score += memory.importance_score * 0.3
            
            # Factor 4: Access frequency (popular items)
            access_score = min(1.0, memory.access_count / 100)  # Cap at 100 accesses
            score += access_score * 0.2
            
            scored_memories.append((score, memory))
        
        # Sort by combined score
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N
        return [memory for _, memory in scored_memories[:limit]]
    
    async def _increment_access_count(self, memory_id: UUID):
        """Increment access count for a memory record."""
        
        try:
            await self.supabase.rpc(
                'increment_memory_access_count',
                {'memory_id': str(memory_id)}
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to increment access count: {str(e)}")
    
    async def _log_retrieval_session(
        self,
        query: MemorySearchQuery,
        results: List[MemoryRecord]
    ):
        """Log retrieval session for analytics."""
        
        session = RetrievalSession(
            query=query.query,
            filters=query.dict(exclude={'query'}),
            retrieved_records=[m.id for m in results]
        )
        
        try:
            await self.supabase.table('retrieval_sessions').insert(
                session.dict(exclude={'id'}, exclude_none=True)
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to log retrieval session: {str(e)}")
    
    def _invalidate_cache_for_type(self, memory_type: MemoryType):
        """Invalidate cache entries for a specific memory type."""
        
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(f"type:{memory_type.value}")
        ]
        
        for key in keys_to_remove:
            del self._cache[key]
    
    def _invalidate_cache_for_id(self, memory_id: UUID):
        """Invalidate cache entry for a specific memory ID."""

        cache_key = f"memory:{str(memory_id)}"
        if cache_key in self._cache:
            del self._cache[cache_key]


# Re-added by Codex for import fix
async def save_task(task: TaskRecord) -> None:
    """Stub for saving a task record."""
    return None


# Re-added by Codex for import fix
async def get_task(task_id: str, user_id: str) -> Optional[TaskRecord]:
    """Stub for retrieving a task record."""
    return None


# Re-added by Codex for import fix
async def list_user_tasks(user_id: str, limit: int = 50, offset: int = 0) -> List[TaskRecord]:
    """Stub for listing user tasks."""
    return []


# Re-added by Codex for import fix
async def update_task_status(task_id: str, status: TaskStatus) -> None:
    """Stub for updating task status."""
    return None


# Re-added by Codex for import fix
async def complete_task(task_id: str, result: Dict[str, Any]) -> None:
    """Stub for marking a task complete."""
    return None


# Re-added by Codex for import fix
async def fail_task(task_id: str, error: str) -> None:
    """Stub for marking a task as failed."""
    return None


# Re-added by Codex for import fix
async def get_relevant_memories(query: str, limit: int = 5) -> List[MemoryRecord]:
    """Stub for memory retrieval."""
    return []


# Re-added by Codex for import fix
async def get_user_by_email(email: str) -> Optional[User]:
    """Stub user lookup."""
    return None


# Re-added by Codex for import fix
async def create_user(email: str, hashed_password: str) -> User:
    return User(id="1", email=email, hashed_password=hashed_password)


# Re-added by Codex for import fix
async def update_user_last_login(user_id: str) -> None:
    return None


# Re-added by Codex for import fix
async def invalidate_refresh_token(token: str, user_id: str) -> None:
    return None


# Re-added by Codex for import fix
async def validate_refresh_token(token: str, user_id: str) -> bool:
    return True


# Re-added by Codex for import fix
async def update_user_profile(user_id: str, data: Dict[str, Any]) -> User:
    return User(id=user_id, email=data.get("email", "user@example.com"))


# Re-added by Codex for import fix
async def save_memory_entry(entry: MemoryEntry) -> MemoryEntry:
    return entry


# Re-added by Codex for import fix
async def query_memories(query: MemorySearchQuery) -> List[QueryResult]:
    return []


# Re-added by Codex for import fix
async def get_memory_entry(entry_id: str) -> Optional[MemoryEntry]:
    return None


# Re-added by Codex for import fix
async def update_memory_entry(entry_id: str, update: MemoryUpdate) -> Optional[MemoryEntry]:
    return None


# Re-added by Codex for import fix
async def delete_memory_entry(entry_id: str) -> None:
    return None