"""Caching layer for performance optimization.

Provides async-compatible caching with TTL (time-to-live) support and
function decorators for transparent result caching. Designed for use
in async contexts where traditional synchronous caching solutions
would block the event loop.

Key Features:
    - Async-first design with asyncio.Lock for thread-safe access
    - Configurable TTL for automatic cache expiration
    - LRU-style eviction when max size is reached
    - Function decorator for transparent caching
    - Named cache management for organizing multiple caches
    - Cache statistics (hit rate, size, etc.)

Key Exports:
    AsyncCache: Core async cache with TTL support.
    cached: Decorator for caching async function results.
    CacheKeyBuilder: Helper for consistent cache key generation.
    CacheManager: Manager for multiple named caches.
    get_cache: Get a named cache from the global manager.

Example:
    >>> from repo_sapiens.utils.caching import AsyncCache, cached
    >>>
    >>> # Direct cache usage
    >>> cache = AsyncCache(ttl_seconds=300, max_size=100)
    >>> await cache.set("user:123", {"name": "Alice"})
    >>> user = await cache.get("user:123")
    >>>
    >>> # Decorator usage
    >>> @cached(ttl_seconds=600)
    ... async def fetch_user(user_id: int) -> dict:
    ...     return await database.get_user(user_id)

Thread Safety:
    All cache operations use asyncio.Lock for synchronization, making
    them safe for concurrent access from multiple async tasks. However,
    the caches are not designed for multi-process scenarios; use Redis
    or similar for distributed caching.

Performance Notes:
    - Cache keys are hashed using MD5 (non-cryptographic, for speed)
    - Eviction is O(n) when cache is full (finds oldest entry)
    - Consider max_size carefully for memory-constrained environments
"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


class AsyncCache:
    """Async cache with TTL (time-to-live) support.

    Provides a simple key-value cache with automatic expiration and
    size limits. All operations are async and use locking for safe
    concurrent access.

    Attributes:
        _cache: Internal storage mapping keys to (value, timestamp) tuples.
        _ttl: Time-to-live as a timedelta.
        _max_size: Maximum number of entries before eviction.
        _lock: asyncio.Lock for synchronization.
        _hits: Count of cache hits (successful gets).
        _misses: Count of cache misses (keys not found or expired).

    Example:
        >>> cache = AsyncCache(ttl_seconds=60, max_size=1000)
        >>> await cache.set("key", {"data": "value"})
        >>> result = await cache.get("key")
        >>> print(result)  # {"data": "value"}
        >>>
        >>> # After 60 seconds...
        >>> result = await cache.get("key")
        >>> print(result)  # None (expired)
        >>>
        >>> # Check cache statistics
        >>> stats = await cache.get_stats()
        >>> print(f"Hit rate: {stats['hit_rate']:.2%}")
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000) -> None:
        """Initialize the async cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds.
                Entries older than this are considered expired and will
                be removed on next access. Default is 300 (5 minutes).
            max_size: Maximum number of entries to store. When exceeded,
                the oldest entry is evicted to make room. Default is 1000.

        Example:
            >>> # Short-lived cache for frequently changing data
            >>> cache = AsyncCache(ttl_seconds=30, max_size=100)
            >>>
            >>> # Longer-lived cache for stable data
            >>> cache = AsyncCache(ttl_seconds=3600, max_size=10000)
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Retrieves the cached value if it exists and hasn't expired.
        Expired entries are automatically removed.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value if found and not expired, None otherwise.

        Example:
            >>> await cache.set("user:123", {"name": "Alice"})
            >>> user = await cache.get("user:123")
            >>> if user:
            ...     print(user["name"])
            ... else:
            ...     print("Cache miss, fetch from database")

        Note:
            A return value of None could mean either the key doesn't
            exist or it has expired. If you need to cache None values,
            wrap them in a container object.
        """
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if datetime.now(UTC) - timestamp < self._ttl:
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
        """Set a value in the cache.

        Stores the value with the current timestamp. If the cache is
        at max capacity, the oldest entry is evicted first.

        Args:
            key: The cache key.
            value: The value to cache. Can be any Python object, but
                be mindful of memory usage for large objects.

        Example:
            >>> await cache.set("user:123", {"name": "Alice", "email": "alice@example.com"})
            >>> await cache.set("config:theme", "dark")

        Note:
            Setting a key that already exists updates the value and
            resets the TTL timer.
        """
        async with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self._max_size:
                await self._evict_oldest()

            self._cache[key] = (value, datetime.now(UTC))
            log.debug("cache_set", key=key)

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Removes the entry if it exists. This is useful for invalidating
        cached data when the underlying data changes.

        Args:
            key: The cache key to delete.

        Returns:
            True if the key existed and was deleted, False otherwise.

        Example:
            >>> await cache.set("user:123", {"name": "Alice"})
            >>> deleted = await cache.delete("user:123")
            >>> print(deleted)  # True
            >>> deleted = await cache.delete("user:123")
            >>> print(deleted)  # False (already deleted)
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                log.debug("cache_delete", key=key)
                return True
            return False

    async def clear(self) -> None:
        """Clear the entire cache.

        Removes all entries and resets statistics. Use with caution
        in production as this may cause a sudden increase in backend
        load as all data needs to be re-fetched.

        Example:
            >>> await cache.clear()
            >>> stats = await cache.get_stats()
            >>> print(stats["size"])  # 0
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            log.info("cache_cleared", entries_cleared=count)

    async def _evict_oldest(self) -> None:
        """Evict the oldest cache entry.

        Internal method called when the cache reaches max_size.
        Removes the entry with the oldest timestamp.

        Note:
            This method assumes the lock is already held. It should
            only be called from within other locked methods.
        """
        if not self._cache:
            return

        oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
        del self._cache[oldest_key]
        log.debug("cache_evicted", key=oldest_key)

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns metrics about cache performance and current state.
        Useful for monitoring and tuning cache configuration.

        Returns:
            Dictionary containing:
                - size: Current number of entries
                - max_size: Maximum allowed entries
                - hits: Number of successful cache lookups
                - misses: Number of cache misses (not found or expired)
                - hit_rate: Ratio of hits to total requests (0.0 to 1.0)
                - ttl_seconds: Configured TTL in seconds

        Example:
            >>> stats = await cache.get_stats()
            >>> print(f"Cache size: {stats['size']}/{stats['max_size']}")
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
            >>> if stats['hit_rate'] < 0.5:
            ...     print("Consider increasing TTL or max_size")
        """
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


def cached(ttl_seconds: int = 300, key_prefix: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for caching async function results.

    Wraps an async function to automatically cache its results based on
    the function name and arguments. Subsequent calls with the same
    arguments return the cached result without executing the function.

    Args:
        ttl_seconds: Time-to-live for cached values in seconds.
            Default is 300 (5 minutes).
        key_prefix: Optional prefix for cache keys. Useful for
            namespacing when multiple functions might have similar
            argument patterns.

    Returns:
        Decorator function that wraps async functions with caching.

    Example:
        >>> @cached(ttl_seconds=600)
        ... async def get_user(user_id: int) -> dict:
        ...     '''Fetch user from database.'''
        ...     print(f"Fetching user {user_id} from database")
        ...     return await database.get_user(user_id)
        >>>
        >>> # First call - fetches from database
        >>> user = await get_user(123)  # Prints: Fetching user 123 from database
        >>>
        >>> # Second call - returns cached result
        >>> user = await get_user(123)  # No print, uses cache
        >>>
        >>> # Different arguments - fetches from database
        >>> user = await get_user(456)  # Prints: Fetching user 456 from database

        >>> # Access the underlying cache for management
        >>> await get_user.cache.clear()  # Clear this function's cache
        >>> stats = await get_user.cache.get_stats()

    Note:
        The cache key is generated from the function name and a hash
        of the arguments. This means:
        - Functions with different names have separate caches
        - Argument order matters (f(1, 2) != f(2, 1))
        - Keyword vs positional doesn't matter for the same values

    Warning:
        Arguments must be representable as strings for key generation.
        Complex objects with changing __str__ representations may cause
        cache misses.
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
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode(), usedforsecurity=False).hexdigest()

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
    """Helper for building consistent cache keys.

    Provides static methods for generating cache keys from various
    inputs. Ensures consistent key format across the application
    and handles hashing for long or complex key components.

    Example:
        >>> key = CacheKeyBuilder.build_key("user", 123, "profile")
        >>> print(key)  # "a1b2c3..."  (MD5 hash of "user:123:profile")
        >>>
        >>> key = CacheKeyBuilder.build_namespaced_key("api", "user", 123)
        >>> print(key)  # "api:a1b2c3..."
    """

    @staticmethod
    def build_key(*parts: Any) -> str:
        """Build a cache key from multiple parts.

        Joins parts with colons and hashes the result for a fixed-length
        key that's safe to use regardless of input length.

        Args:
            *parts: Key components to combine. Each part is converted
                to a string before joining.

        Returns:
            MD5 hash of the joined parts (32 hex characters).

        Example:
            >>> key = CacheKeyBuilder.build_key("issue", 42, "comments")
            >>> # Equivalent to hashing "issue:42:comments"
        """
        key_str = ":".join(str(part) for part in parts)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def build_namespaced_key(namespace: str, *parts: Any) -> str:
        """Build a namespaced cache key.

        Creates a key with a readable namespace prefix followed by a
        hashed key. Useful for organizing keys by domain or service.

        Args:
            namespace: Human-readable namespace prefix.
            *parts: Key components to hash.

        Returns:
            String in format "namespace:hash".

        Example:
            >>> key = CacheKeyBuilder.build_namespaced_key("github", "repo", "owner/name")
            >>> print(key)  # "github:a1b2c3..."
        """
        return f"{namespace}:{CacheKeyBuilder.build_key(*parts)}"


class CacheManager:
    """Manager for multiple named caches.

    Provides centralized management of cache instances, allowing
    different parts of an application to use separate caches with
    different configurations while sharing a common management
    interface.

    Attributes:
        _caches: Dictionary mapping cache names to AsyncCache instances.
        _lock: asyncio.Lock for thread-safe cache creation.

    Example:
        >>> manager = CacheManager()
        >>>
        >>> # Get or create caches with different configurations
        >>> user_cache = await manager.get_cache("users", ttl_seconds=600)
        >>> api_cache = await manager.get_cache("api_responses", ttl_seconds=60)
        >>>
        >>> # Use caches normally
        >>> await user_cache.set("user:123", user_data)
        >>>
        >>> # Get statistics for all caches
        >>> all_stats = await manager.get_all_stats()
        >>> for name, stats in all_stats.items():
        ...     print(f"{name}: {stats['hit_rate']:.1%} hit rate")
        >>>
        >>> # Clear all caches at once
        >>> await manager.clear_all()
    """

    def __init__(self) -> None:
        """Initialize the cache manager.

        Creates an empty manager with no caches. Caches are created
        on-demand via get_cache().
        """
        self._caches: dict[str, AsyncCache] = {}
        self._lock = asyncio.Lock()

    async def get_cache(self, name: str, ttl_seconds: int = 300, max_size: int = 1000) -> AsyncCache:
        """Get or create a named cache.

        Returns an existing cache if one with the given name exists,
        otherwise creates a new cache with the specified configuration.

        Args:
            name: Unique name for the cache.
            ttl_seconds: TTL for new cache (ignored if cache exists).
            max_size: Max size for new cache (ignored if cache exists).

        Returns:
            The named AsyncCache instance.

        Example:
            >>> cache = await manager.get_cache("issues", ttl_seconds=300)
            >>> await cache.set("issue:1", issue_data)
            >>>
            >>> # Getting the same cache again returns the same instance
            >>> same_cache = await manager.get_cache("issues")
            >>> assert cache is same_cache

        Note:
            If a cache with the name already exists, the ttl_seconds
            and max_size parameters are ignored. The existing cache
            retains its original configuration.
        """
        async with self._lock:
            if name not in self._caches:
                self._caches[name] = AsyncCache(ttl_seconds, max_size)
                log.info("cache_created", name=name, ttl=ttl_seconds, max_size=max_size)

            return self._caches[name]

    async def clear_all(self) -> None:
        """Clear all managed caches.

        Iterates through all caches and clears each one. Use with
        caution as this may cause significant backend load.

        Example:
            >>> await manager.clear_all()
            >>> print("All caches cleared")
        """
        async with self._lock:
            for cache in self._caches.values():
                await cache.clear()
            log.info("all_caches_cleared", count=len(self._caches))

    async def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all managed caches.

        Returns statistics from each managed cache, organized by
        cache name.

        Returns:
            Dictionary mapping cache names to their statistics dicts.

        Example:
            >>> stats = await manager.get_all_stats()
            >>> for name, cache_stats in stats.items():
            ...     print(f"{name}: {cache_stats['size']} entries, "
            ...           f"{cache_stats['hit_rate']:.1%} hit rate")
        """
        stats = {}
        for name, cache in self._caches.items():
            stats[name] = await cache.get_stats()
        return stats


# Global cache manager instance
_cache_manager = CacheManager()


async def get_cache(name: str, ttl_seconds: int = 300) -> AsyncCache:
    """Get a named cache from the global cache manager.

    Convenience function for accessing the global CacheManager instance.
    Creates a new cache if one with the given name doesn't exist.

    Args:
        name: Unique name for the cache.
        ttl_seconds: TTL for new cache (ignored if cache exists).

    Returns:
        The named AsyncCache instance.

    Example:
        >>> cache = await get_cache("issues", ttl_seconds=300)
        >>> await cache.set("issue:42", issue_data)
        >>>
        >>> # Elsewhere in the code...
        >>> cache = await get_cache("issues")
        >>> issue = await cache.get("issue:42")

    Note:
        This uses a module-level global CacheManager. For testing or
        when you need isolated cache instances, create your own
        CacheManager instead.
    """
    return await _cache_manager.get_cache(name, ttl_seconds)
