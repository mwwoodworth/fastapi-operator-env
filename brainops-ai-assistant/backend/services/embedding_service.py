"""Embedding service for generating vector embeddings."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Dict, Any, List, Optional

import openai
from loguru import logger
import redis.asyncio as redis

from core.config import settings


class EmbeddingService:
    """Service for generating and caching vector embeddings."""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-ada-002"
        self.dimension = 1536
        self.redis_client = None
        self.cache_ttl = 86400 * 7  # 7 days
        
    async def initialize(self):
        """Initialize the embedding service."""
        try:
            # Initialize Redis client for caching
            self.redis_client = redis.from_url(settings.REDIS_URL)
            await self.redis_client.ping()
            logger.info("Embedding service initialized with Redis caching")
        except Exception as e:
            logger.warning(f"Redis not available for embedding cache: {e}")
            self.redis_client = None
    
    async def generate_embedding(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[float]:
        """Generate embedding for text with optional caching."""
        try:
            # Generate cache key
            cache_key = None
            if use_cache and self.redis_client:
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                cache_key = f"embedding:{self.model}:{content_hash}"
                
                # Try to get from cache
                cached_embedding = await self.redis_client.get(cache_key)
                if cached_embedding:
                    logger.debug(f"Retrieved embedding from cache for text: {text[:50]}...")
                    return json.loads(cached_embedding)
            
            # Generate embedding using OpenAI
            start_time = time.time()
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension
            )
            
            embedding = response.data[0].embedding
            generation_time = time.time() - start_time
            
            # Cache the embedding
            if use_cache and self.redis_client and cache_key:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(embedding)
                )
            
            logger.debug(f"Generated embedding in {generation_time:.2f}s for text: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def generate_batch_embeddings(
        self, 
        texts: List[str], 
        metadata: Optional[List[Dict[str, Any]]] = None,
        use_cache: bool = True,
        batch_size: int = 100
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts in batches."""
        try:
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_metadata = metadata[i:i + batch_size] if metadata else None
                
                # Process batch
                batch_embeddings = []
                for j, text in enumerate(batch_texts):
                    text_metadata = batch_metadata[j] if batch_metadata else None
                    embedding = await self.generate_embedding(text, text_metadata, use_cache)
                    batch_embeddings.append(embedding)
                
                all_embeddings.extend(batch_embeddings)
                
                # Small delay between batches to avoid rate limits
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            logger.info(f"Generated {len(all_embeddings)} embeddings for {len(texts)} texts")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise
    
    async def find_similar_texts(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]],
        similarity_threshold: float = 0.7
    ) -> List[Tuple[int, float]]:
        """Find similar texts using cosine similarity."""
        try:
            similarities = []
            
            for i, candidate_embedding in enumerate(candidate_embeddings):
                similarity = self._cosine_similarity(query_embedding, candidate_embedding)
                if similarity >= similarity_threshold:
                    similarities.append((i, similarity))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            return similarities
            
        except Exception as e:
            logger.error(f"Failed to find similar texts: {e}")
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            # Dot product
            dot_product = sum(x * y for x, y in zip(a, b))
            
            # Magnitudes
            magnitude_a = sum(x * x for x in a) ** 0.5
            magnitude_b = sum(x * x for x in b) ** 0.5
            
            # Cosine similarity
            if magnitude_a == 0 or magnitude_b == 0:
                return 0.0
            
            return dot_product / (magnitude_a * magnitude_b)
            
        except Exception as e:
            logger.error(f"Failed to calculate cosine similarity: {e}")
            return 0.0
    
    async def clear_cache(self, pattern: str = "embedding:*") -> int:
        """Clear embedding cache."""
        try:
            if not self.redis_client:
                return 0
                
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} embedding cache entries")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Failed to clear embedding cache: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get embedding cache statistics."""
        try:
            if not self.redis_client:
                return {"cache_enabled": False}
            
            # Get cache keys
            keys = await self.redis_client.keys("embedding:*")
            
            # Get memory usage
            memory_info = await self.redis_client.info("memory")
            
            return {
                "cache_enabled": True,
                "cached_embeddings": len(keys),
                "memory_used_mb": memory_info.get("used_memory", 0) / 1024 / 1024,
                "cache_ttl_seconds": self.cache_ttl,
                "model": self.model,
                "dimension": self.dimension
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"cache_enabled": False, "error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check embedding service health."""
        try:
            # Test embedding generation
            start_time = time.time()
            test_embedding = await self.generate_embedding("Health check test", use_cache=False)
            response_time = time.time() - start_time
            
            # Check cache
            cache_status = "healthy" if self.redis_client else "disabled"
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                except:
                    cache_status = "unhealthy"
            
            return {
                "status": "healthy",
                "model": self.model,
                "dimension": self.dimension,
                "response_time_seconds": response_time,
                "cache_status": cache_status,
                "embedding_length": len(test_embedding)
            }
            
        except Exception as e:
            logger.error(f"Embedding service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def close(self):
        """Close the embedding service."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Embedding service closed")