"""
Caching utilities for performance optimization.
"""

from functools import wraps
from typing import Any, Callable, Optional
import hashlib
import json
from datetime import datetime, timedelta
from ..core.logging import get_logger

logger = get_logger(__name__)

# In-memory cache for development
# In production, would use Redis
_cache_store = {}

# Cache instance for backward compatibility
cache = None

def cache_key_builder(*args, **kwargs) -> str:
    """Build a cache key from function arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    return hashlib.md5(":".join(key_parts).encode()).hexdigest()


def cache_result(ttl: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            # Check cache
            cached = _get_from_cache(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            _store_in_cache(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: Optional[str] = None):
    """
    Invalidate cached entries.
    
    Args:
        pattern: Optional pattern to match cache keys
    """
    if pattern is None:
        # Clear all cache
        _cache_store.clear()
        logger.info("Cleared entire cache")
    else:
        # Clear matching keys
        keys_to_remove = [
            key for key in _cache_store.keys()
            if pattern in key
        ]
        for key in keys_to_remove:
            del _cache_store[key]
        logger.info(f"Cleared {len(keys_to_remove)} cache entries matching {pattern}")


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a unique cache key."""
    # Create a string representation of arguments
    key_parts = [func_name]
    
    # Add positional arguments
    for arg in args:
        if hasattr(arg, 'id'):  # Handle model objects
            key_parts.append(f"id:{arg.id}")
        elif isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # Skip complex objects that can't be easily serialized
            continue
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")
    
    # Generate hash
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def _get_from_cache(key: str) -> Optional[Any]:
    """Get value from cache if not expired."""
    if key in _cache_store:
        entry = _cache_store[key]
        if entry['expires_at'] > datetime.utcnow():
            return entry['value']
        else:
            # Remove expired entry
            del _cache_store[key]
    return None


def _store_in_cache(key: str, value: Any, ttl: int):
    """Store value in cache with expiration."""
    _cache_store[key] = {
        'value': value,
        'expires_at': datetime.utcnow() + timedelta(seconds=ttl)
    }