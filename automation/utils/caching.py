"""
Caching layer for performance optimization.
Provides async cache with TTL support and function decorators.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


class AsyncCache:
    """Async cache with TTL support."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000) -> None:
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if datetime.now() - timestamp < self._ttl:
                    self._hits += 1
                    log.debug("cache_hit", key=key)
                    return value
                else:
                    del self._cache[key]
                    log.debug("cache_expired", key=key)

            self._misses += 1
            log.debug("cache_miss", key=key)
            return None

    async def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        async with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self._max_size:
                await self._evict_oldest()

            self._cache[key] = (value, datetime.now())
            log.debug("cache_set", key=key)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                log.debug("cache_delete", key=key)
                return True
            return False

    async def clear(self) -> None:
        """Clear entire cache."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            log.info("cache_cleared", entries_cleared=count)

    async def _evict_oldest(self) -> None:
        """Evict oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
        del self._cache[oldest_key]
        log.debug("cache_evicted", key=oldest_key)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self._ttl.total_seconds(),
        }


def cached(ttl_seconds: int = 300, key_prefix: str = "") -> Callable[[Callable], Callable]:
    """
    Decorator for caching async function results.

    Args:
        ttl_seconds: Time to live for cached values
        key_prefix: Optional prefix for cache keys

    Example:
        @cached(ttl_seconds=600)
        async def get_issue(issue_number: int) -> Issue:
            # ... implementation
    """
    cache = AsyncCache(ttl_seconds)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create cache key from function name and arguments
            key_data = {
                "func": f"{key_prefix}{func.__name__}",
                "args": str(args),  # Simple string representation
                "kwargs": str(sorted(kwargs.items())),
            }
            key = hashlib.md5(
                json.dumps(key_data, sort_keys=True).encode()
            ).hexdigest()

            # Try cache first
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result)
            return result

        # Attach cache instance for management
        wrapper.cache = cache  # type: ignore
        return wrapper

    return decorator


class CacheKeyBuilder:
    """Helper for building consistent cache keys."""

    @staticmethod
    def build_key(*parts: Any) -> str:
        """Build cache key from parts."""
        key_str = ":".join(str(part) for part in parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    @staticmethod
    def build_namespaced_key(namespace: str, *parts: Any) -> str:
        """Build namespaced cache key."""
        return f"{namespace}:{CacheKeyBuilder.build_key(*parts)}"


class CacheManager:
    """Manage multiple named caches."""

    def __init__(self) -> None:
        self._caches: Dict[str, AsyncCache] = {}
        self._lock = asyncio.Lock()

    async def get_cache(
        self, name: str, ttl_seconds: int = 300, max_size: int = 1000
    ) -> AsyncCache:
        """Get or create a named cache."""
        async with self._lock:
            if name not in self._caches:
                self._caches[name] = AsyncCache(ttl_seconds, max_size)
                log.info("cache_created", name=name, ttl=ttl_seconds, max_size=max_size)

            return self._caches[name]

    async def clear_all(self) -> None:
        """Clear all managed caches."""
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear()
            log.info("all_caches_cleared", count=len(self._caches))

    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches."""
        stats = {}
        for name, cache in self._caches.items():
            stats[name] = await cache.get_stats()
        return stats


# Global cache manager instance
_cache_manager = CacheManager()


async def get_cache(name: str, ttl_seconds: int = 300) -> AsyncCache:
    """Get a named cache from the global cache manager."""
    return await _cache_manager.get_cache(name, ttl_seconds)
