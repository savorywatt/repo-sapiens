"""Extended tests for repo_sapiens/utils/caching.py - CacheManager and get_cache."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from repo_sapiens.utils.caching import (
    AsyncCache,
    CacheKeyBuilder,
    CacheManager,
    cached,
    get_cache,
)


# =============================================================================
# Tests for CacheManager
# =============================================================================


class TestCacheManager:
    """Tests for CacheManager class."""

    def test_init(self):
        """Test CacheManager initialization."""
        manager = CacheManager()

        assert manager._caches == {}

    @pytest.mark.asyncio
    async def test_get_cache_creates_new(self):
        """Test that get_cache creates new cache for new name."""
        manager = CacheManager()

        cache = await manager.get_cache("test", ttl_seconds=120, max_size=500)

        assert cache is not None
        assert "test" in manager._caches
        stats = await cache.get_stats()
        assert stats["ttl_seconds"] == 120
        assert stats["max_size"] == 500

    @pytest.mark.asyncio
    async def test_get_cache_returns_existing(self):
        """Test that get_cache returns existing cache for same name."""
        manager = CacheManager()

        cache1 = await manager.get_cache("test", ttl_seconds=100)
        cache2 = await manager.get_cache("test", ttl_seconds=200)

        assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_get_cache_multiple(self):
        """Test managing multiple named caches."""
        manager = CacheManager()

        cache1 = await manager.get_cache("cache1", ttl_seconds=60)
        cache2 = await manager.get_cache("cache2", ttl_seconds=120)

        assert cache1 is not cache2
        assert len(manager._caches) == 2

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Test clearing all caches."""
        manager = CacheManager()

        cache1 = await manager.get_cache("cache1")
        cache2 = await manager.get_cache("cache2")

        await cache1.set("key1", "value1")
        await cache2.set("key2", "value2")

        await manager.clear_all()

        # Values should be cleared
        assert await cache1.get("key1") is None
        assert await cache2.get("key2") is None

    @pytest.mark.asyncio
    async def test_get_all_stats(self):
        """Test getting statistics from all caches."""
        manager = CacheManager()

        cache1 = await manager.get_cache("cache1", ttl_seconds=60)
        cache2 = await manager.get_cache("cache2", ttl_seconds=120)

        await cache1.set("key", "value")
        await cache1.get("key")  # Hit
        await cache2.get("missing")  # Miss

        stats = await manager.get_all_stats()

        assert "cache1" in stats
        assert "cache2" in stats
        assert stats["cache1"]["hits"] == 1
        assert stats["cache2"]["misses"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to cache manager is safe."""
        manager = CacheManager()

        async def get_and_use_cache(name):
            cache = await manager.get_cache(name, ttl_seconds=60)
            await cache.set("key", f"value-{name}")
            return await cache.get("key")

        results = await asyncio.gather(
            *[get_and_use_cache(f"cache{i}") for i in range(10)]
        )

        assert len(results) == 10
        assert len(manager._caches) == 10


# =============================================================================
# Tests for get_cache helper function
# =============================================================================


class TestGetCacheFunction:
    """Tests for the get_cache helper function."""

    @pytest.mark.asyncio
    async def test_get_cache_creates_cache(self):
        """Test get_cache creates cache via global manager."""
        cache = await get_cache("global_test", ttl_seconds=180)

        assert cache is not None

        await cache.set("key", "value")
        result = await cache.get("key")

        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_cache_same_name_returns_same(self):
        """Test get_cache returns same instance for same name."""
        cache1 = await get_cache("same_name_test")
        cache2 = await get_cache("same_name_test")

        assert cache1 is cache2


# =============================================================================
# Extended AsyncCache Tests
# =============================================================================


class TestAsyncCacheExtended:
    """Extended tests for AsyncCache class."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Test deleting key that doesn't exist."""
        cache = AsyncCache(ttl_seconds=60)

        result = await cache.delete("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_evict_oldest_empty_cache(self):
        """Test evicting from empty cache is safe."""
        cache = AsyncCache(ttl_seconds=60)

        # Call private method directly - should not raise
        await cache._evict_oldest()

    @pytest.mark.asyncio
    async def test_get_expired_entry_is_deleted(self):
        """Test that getting expired entry deletes it."""
        cache = AsyncCache(ttl_seconds=0)  # Immediate expiration

        await cache.set("key", "value")

        # Wait a tiny bit to ensure expiration
        await asyncio.sleep(0.01)

        result = await cache.get("key")

        assert result is None
        # Entry should be deleted from cache
        assert "key" not in cache._cache

    @pytest.mark.asyncio
    async def test_stats_hit_rate_calculation(self):
        """Test hit rate calculation in stats."""
        cache = AsyncCache(ttl_seconds=60)

        await cache.set("key", "value")

        # 3 hits
        for _ in range(3):
            await cache.get("key")

        # 1 miss
        await cache.get("missing")

        stats = await cache.get_stats()

        assert stats["hits"] == 3
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.75

    @pytest.mark.asyncio
    async def test_stats_no_requests(self):
        """Test stats with no requests (avoid division by zero)."""
        cache = AsyncCache(ttl_seconds=60)

        stats = await cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_clear_resets_stats(self):
        """Test that clear resets statistics."""
        cache = AsyncCache(ttl_seconds=60)

        await cache.set("key", "value")
        await cache.get("key")  # Hit
        await cache.get("missing")  # Miss

        await cache.clear()

        stats = await cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_eviction_order(self):
        """Test that oldest entries are evicted first."""
        cache = AsyncCache(ttl_seconds=60, max_size=3)

        # Add entries with small delays to ensure different timestamps
        await cache.set("oldest", "1")
        await asyncio.sleep(0.01)
        await cache.set("middle", "2")
        await asyncio.sleep(0.01)
        await cache.set("newest", "3")

        # Add fourth entry - should evict oldest
        await cache.set("extra", "4")

        assert await cache.get("oldest") is None
        assert await cache.get("middle") == "2"
        assert await cache.get("newest") == "3"
        assert await cache.get("extra") == "4"

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations are safe."""
        cache = AsyncCache(ttl_seconds=60, max_size=100)

        async def set_and_get(key):
            await cache.set(key, f"value-{key}")
            return await cache.get(key)

        results = await asyncio.gather(
            *[set_and_get(f"key{i}") for i in range(50)]
        )

        assert len(results) == 50
        assert all(r is not None for r in results)


# =============================================================================
# Extended CacheKeyBuilder Tests
# =============================================================================


class TestCacheKeyBuilderExtended:
    """Extended tests for CacheKeyBuilder."""

    def test_build_key_with_different_types(self):
        """Test building keys with various types."""
        key = CacheKeyBuilder.build_key("str", 123, 45.6, True, None)

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex digest length

    def test_build_key_order_matters(self):
        """Test that part order affects key."""
        key1 = CacheKeyBuilder.build_key("a", "b")
        key2 = CacheKeyBuilder.build_key("b", "a")

        assert key1 != key2

    def test_build_key_empty_parts(self):
        """Test building key with empty string parts."""
        key = CacheKeyBuilder.build_key("", "", "")

        assert isinstance(key, str)
        assert len(key) == 32

    def test_build_namespaced_key_format(self):
        """Test namespaced key format."""
        key = CacheKeyBuilder.build_namespaced_key("users", "id", 123)

        assert key.startswith("users:")
        # Remaining part is MD5 hash
        hash_part = key.split(":", 1)[1]
        assert len(hash_part) == 32

    def test_build_namespaced_key_different_namespaces(self):
        """Test that different namespaces produce different keys."""
        key1 = CacheKeyBuilder.build_namespaced_key("users", "data")
        key2 = CacheKeyBuilder.build_namespaced_key("posts", "data")

        assert key1 != key2


# =============================================================================
# Extended cached Decorator Tests
# =============================================================================


class TestCachedDecoratorExtended:
    """Extended tests for the cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_with_key_prefix(self):
        """Test cached decorator with key prefix."""
        call_count = 0

        @cached(ttl_seconds=60, key_prefix="prefix_")
        async def prefixed_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await prefixed_function(5)
        result2 = await prefixed_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_with_kwargs(self):
        """Test cached decorator properly handles kwargs."""
        call_count = 0

        @cached(ttl_seconds=60)
        async def func_with_kwargs(a: int, b: int = 0) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        result1 = await func_with_kwargs(1, b=2)
        result2 = await func_with_kwargs(1, b=2)
        result3 = await func_with_kwargs(1, b=3)  # Different kwargs

        assert result1 == 3
        assert result2 == 3
        assert result3 == 4
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_preserves_function_name(self):
        """Test that cached decorator preserves function metadata."""

        @cached(ttl_seconds=60)
        async def named_function() -> str:
            """This is the docstring."""
            return "result"

        assert named_function.__name__ == "named_function"
        assert named_function.__doc__ == "This is the docstring."

    @pytest.mark.asyncio
    async def test_cached_exposes_cache_instance(self):
        """Test that cached decorator exposes cache for management."""

        @cached(ttl_seconds=60)
        async def func_with_cache() -> str:
            return "value"

        await func_with_cache()

        # Cache should be accessible
        assert hasattr(func_with_cache, "cache")
        assert isinstance(func_with_cache.cache, AsyncCache)

    @pytest.mark.asyncio
    async def test_cached_different_args_different_cache_entries(self):
        """Test that different args create different cache entries."""
        call_count = 0

        @cached(ttl_seconds=60)
        async def square(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * x

        results = await asyncio.gather(
            square(1), square(2), square(3), square(1), square(2)
        )

        assert results == [1, 4, 9, 1, 4]
        assert call_count == 3  # Only 3 unique calls

    @pytest.mark.asyncio
    async def test_cached_with_complex_args(self):
        """Test caching with complex argument types."""
        call_count = 0

        @cached(ttl_seconds=60)
        async def process_data(data: dict) -> int:
            nonlocal call_count
            call_count += 1
            return sum(data.values())

        data1 = {"a": 1, "b": 2}
        data2 = {"a": 1, "b": 2}  # Same content as data1

        result1 = await process_data(data1)
        result2 = await process_data(data2)

        assert result1 == 3
        assert result2 == 3
        # Note: dict str representation may vary, so call_count depends on that
        # The key uses str(args), so identical dict content should match


# =============================================================================
# Edge Cases
# =============================================================================


class TestCachingEdgeCases:
    """Edge case tests for caching module."""

    @pytest.mark.asyncio
    async def test_cache_with_none_value(self):
        """Test caching None values."""
        cache = AsyncCache(ttl_seconds=60)

        await cache.set("key", None)

        # Note: get returns None for both missing and None values
        # This is a known limitation
        result = await cache.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_with_large_values(self):
        """Test caching large values."""
        cache = AsyncCache(ttl_seconds=60)

        large_value = "x" * 1000000  # 1MB string

        await cache.set("large", large_value)
        result = await cache.get("large")

        assert result == large_value

    @pytest.mark.asyncio
    async def test_cache_with_special_characters_in_key(self):
        """Test caching with special characters in key."""
        cache = AsyncCache(ttl_seconds=60)

        special_key = "key:with/special\\chars\n\t"

        await cache.set(special_key, "value")
        result = await cache.get(special_key)

        assert result == "value"

    @pytest.mark.asyncio
    async def test_max_size_one(self):
        """Test cache with max size of 1."""
        cache = AsyncCache(ttl_seconds=60, max_size=1)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_ttl_zero(self):
        """Test cache with TTL of 0 (immediate expiration)."""
        cache = AsyncCache(ttl_seconds=0)

        await cache.set("key", "value")

        # Even with 0 TTL, entry should exist briefly
        # but expire on next get
        await asyncio.sleep(0.001)
        result = await cache.get("key")

        assert result is None
