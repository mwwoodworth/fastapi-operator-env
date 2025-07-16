"""
Vector Utilities for Memory System

Handles embedding generation, text chunking, and similarity calculations
for the BrainOps RAG and memory systems.
"""

from typing import List, Tuple, Optional, Dict, Any
import asyncio
try:
    import tiktoken
except ImportError:  # Re-added by Codex for import fix
    tiktoken = None
import numpy as np
from openai import AsyncOpenAI
import hashlib
from functools import lru_cache

from apps.backend.core.settings import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


# Re-added by Codex for import fix
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    return float(np.dot(v1, v2) / denom) if denom else 0.0

# Initialize OpenAI client
_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """
    Get or create OpenAI client instance.
    
    Returns:
        Configured OpenAI client
    """
    global _openai_client
    
    if _openai_client is None:
        
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    return _openai_client


@lru_cache(maxsize=1)
def get_tokenizer(model: str = "text-embedding-ada-002"):
    """Return a tokenizer; falls back to a simple implementation if tiktoken is missing."""
    if tiktoken is None:
        class _DummyTokenizer:
            def encode(self, text: str):
                return list(text.encode())

            def decode(self, tokens):
                return bytes(tokens).decode()

        return _DummyTokenizer()

    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


async def generate_embedding(
    text: str,
    model: str = "text-embedding-ada-002",
    cache_key: Optional[str] = None
) -> List[float]:
    """
    Generate embedding vector for the given text using OpenAI.
    
    Args:
        text: Text to embed
        model: OpenAI embedding model to use
        cache_key: Optional cache key for deduplication
        
    Returns:
        Embedding vector (1536 dimensions for ada-002)
    """
    
    # Clean and prepare text
    text = text.strip()
    if not text:
        raise ValueError("Cannot generate embedding for empty text")
    
    # Check token count and truncate if necessary
    tokenizer = get_tokenizer(model)
    tokens = tokenizer.encode(text)
    
    # Max tokens for ada-002 is 8191
    if len(tokens) > 8191:
        logger.warning(f"Text too long ({len(tokens)} tokens), truncating to 8191")
        tokens = tokens[:8191]
        text = tokenizer.decode(tokens)
    
    try:
        client = get_openai_client()
        
        # Generate embedding
        response = await client.embeddings.create(
            model=model,
            input=text
        )
        
        embedding = response.data[0].embedding
        
        # Log usage for cost tracking
        logger.debug(f"Generated embedding using {response.usage.total_tokens} tokens")
        
        return embedding
        
    except Exception as e:
        logger.error(f"Failed to generate embedding: {str(e)}")
        raise


def chunk_text_with_overlap(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
    min_chunk_size: int = 500,
    use_sentences: bool = True
) -> List[Tuple[str, int, int]]:
    """
    Split text into overlapping chunks for optimal retrieval.
    
    Args:
        text: Text to chunk
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum acceptable chunk size
        use_sentences: Try to break at sentence boundaries
        
    Returns:
        List of tuples (chunk_text, start_position, end_position)
    """
    
    if not text:
        return []
    
    chunks = []
    
    if use_sentences:
        # Split by sentence boundaries
        sentences = _split_into_sentences(text)
        
        current_chunk = []
        current_size = 0
        chunk_start = 0
        
        for i, sentence in enumerate(sentences):
            sentence_size = len(sentence)
            
            # If adding this sentence exceeds chunk size
            if current_size + sentence_size > chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))
                
                # Calculate overlap
                overlap_sentences = []
                overlap_size = 0
                
                # Work backwards to include overlap
                for j in range(len(current_chunk) - 1, -1, -1):
                    overlap_size += len(current_chunk[j])
                    overlap_sentences.insert(0, current_chunk[j])
                    if overlap_size >= overlap:
                        break
                
                # Start new chunk with overlap
                current_chunk = overlap_sentences
                current_size = overlap_size
                chunk_start = chunk_start + len(chunk_text) - overlap_size
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        # Add final chunk
        if current_chunk and current_size >= min_chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))
    
    else:
        # Simple character-based chunking
        start = 0
        text_length = len(text)
        
        while start < text_length:
            # Calculate end position
            end = min(start + chunk_size, text_length)
            
            # Extract chunk
            chunk = text[start:end]
            
            # Only add if meets minimum size
            if len(chunk) >= min_chunk_size:
                chunks.append((chunk, start, end))
            
            # Move start position (accounting for overlap)
            start = end - overlap if end < text_length else end
    
    return chunks


def calculate_similarity(
    embedding1: List[float],
    embedding2: List[float],
    metric: str = "cosine"
) -> float:
    """
    Calculate similarity between two embedding vectors.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        metric: Similarity metric to use (cosine, euclidean, dot)
        
    Returns:
        Similarity score (0-1 for cosine, higher is more similar)
    """
    
    # Convert to numpy arrays
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    if metric == "cosine":
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        # Convert to 0-1 range
        return (similarity + 1) / 2
        
    elif metric == "euclidean":
        # Euclidean distance (inverted to similarity)
        distance = np.linalg.norm(vec1 - vec2)
        # Convert to similarity (0-1)
        return 1 / (1 + distance)
        
    elif metric == "dot":
        # Dot product similarity
        return float(np.dot(vec1, vec2))
        
    else:
        raise ValueError(f"Unknown similarity metric: {metric}")


async def batch_generate_embeddings(
    texts: List[str],
    model: str = "text-embedding-ada-002",
    batch_size: int = 100
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in batches.
    
    Args:
        texts: List of texts to embed
        model: OpenAI embedding model
        batch_size: Number of texts per API call
        
    Returns:
        List of embedding vectors
    """
    
    client = get_openai_client()
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            response = await client.embeddings.create(
                model=model,
                input=batch
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)
            
            logger.debug(f"Generated batch embeddings: {i+1}-{i+len(batch)} of {len(texts)}")
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            # Return None for failed embeddings
            all_embeddings.extend([None] * len(batch))
    
    return all_embeddings


# Re-added by Codex for import fix
async def generate_embeddings(texts: List[str], model: str = "text-embedding-ada-002") -> List[List[float]]:
    return await batch_generate_embeddings(texts, model=model)


def estimate_tokens(text: str, model: str = "text-embedding-ada-002") -> int:
    """
    Estimate token count for the given text.
    
    Args:
        text: Text to count tokens for
        model: Model to use for tokenization
        
    Returns:
        Estimated token count
    """
    
    tokenizer = get_tokenizer(model)
    return len(tokenizer.encode(text))


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using basic heuristics.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    
    # Simple sentence splitting (can be enhanced with NLTK or spaCy)
    import re
    
    # Pattern for sentence boundaries
    sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
    
    # Split by pattern
    sentences = re.split(sentence_pattern, text)
    
    # Clean up sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            cleaned_sentences.append(sentence)
    
    return cleaned_sentences


def create_content_hash(content: str) -> str:
    """
    Create a hash of content for deduplication.
    
    Args:
        content: Content to hash
        
    Returns:
        SHA256 hash as hex string
    """
    
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


async def find_optimal_chunk_size(
    text: str,
    target_chunks: int = 10,
    min_size: int = 500,
    max_size: int = 2000
) -> int:
    """
    Find optimal chunk size for a given text to achieve target number of chunks.
    
    Args:
        text: Text to analyze
        target_chunks: Desired number of chunks
        min_size: Minimum chunk size
        max_size: Maximum chunk size
        
    Returns:
        Optimal chunk size
    """
    
    text_length = len(text)
    
    # Calculate ideal chunk size
    ideal_size = text_length // target_chunks
    
    # Constrain to min/max bounds
    optimal_size = max(min_size, min(ideal_size, max_size))
    
    # Adjust for better sentence boundaries
    if optimal_size < max_size:
        # Round up to nearest 100 for cleaner chunks
        optimal_size = ((optimal_size + 99) // 100) * 100
    
    return optimal_size


class EmbeddingCache:
    """
    Simple in-memory cache for embeddings to avoid redundant API calls.
    """
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, List[float]] = {}
        self.max_size = max_size
        self.access_order: List[str] = []
    
    def get(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache if available."""
        
        key = create_content_hash(text)
        
        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        
        return None
    
    def set(self, text: str, embedding: List[float]):
        """Store embedding in cache."""
        
        key = create_content_hash(text)
        
        # Check cache size
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Remove least recently used
            lru_key = self.access_order.pop(0)
            del self.cache[lru_key]
        
        self.cache[key] = embedding
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def clear(self):
        """Clear the cache."""
        
        self.cache.clear()
        self.access_order.clear()


# Global embedding cache instance
_embedding_cache = EmbeddingCache()


async def generate_embedding_with_cache(
    text: str,
    model: str = "text-embedding-ada-002"
) -> List[float]:
    """
    Generate embedding with caching support.
    
    Args:
        text: Text to embed
        model: Embedding model
        
    Returns:
        Embedding vector
    """
    
    # Check cache first
    cached = _embedding_cache.get(text)
    if cached is not None:
        logger.debug("Retrieved embedding from cache")
        return cached
    
    # Generate new embedding
    embedding = await generate_embedding(text, model)
    
    # Cache the result
    _embedding_cache.set(text, embedding)
    
    return embedding

