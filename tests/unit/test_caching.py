"""
Tests for caching system.
"""

import asyncio

import pytest

from repo_sapiens.utils.caching import AsyncCache, CacheKeyBuilder, cached


@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test basic cache set and get operations."""
    cache = AsyncCache(ttl_seconds=60)

    await cache.set("key1", "value1")
    result = await cache.get("key1")

    assert result == "value1"


@pytest.mark.asyncio
async def test_cache_miss():
    """Test cache miss behavior."""
    cache = AsyncCache(ttl_seconds=60)

    result = await cache.get("nonexistent")

    assert result is None


@pytest.mark.asyncio
@pytest.mark.needs_real_timing
async def test_cache_ttl_expiration():
    """Test that cache entries expire after TTL."""
    cache = AsyncCache(ttl_seconds=1)  # 1 second TTL

    await cache.set("key1", "value1")

    # Wait for expiration
    await asyncio.sleep(1.1)

    result = await cache.get("key1")

    assert result is None


@pytest.mark.asyncio
async def test_cache_clear():
    """Test cache clear operation."""
    cache = AsyncCache(ttl_seconds=60)

    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    await cache.clear()

    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_cache_delete():
    """Test deleting specific cache entry."""
    cache = AsyncCache(ttl_seconds=60)

    await cache.set("key1", "value1")
    deleted = await cache.delete("key1")

    assert deleted is True
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_cache_stats():
    """Test cache statistics."""
    cache = AsyncCache(ttl_seconds=60)

    await cache.set("key1", "value1")
    await cache.get("key1")  # Hit
    await cache.get("key2")  # Miss

    stats = await cache.get_stats()

    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5


@pytest.mark.asyncio
async def test_cache_max_size():
    """Test cache max size enforcement."""
    cache = AsyncCache(ttl_seconds=60, max_size=2)

    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")  # Should evict oldest

    # One of the first two keys should be evicted
    values = [
        await cache.get("key1"),
        await cache.get("key2"),
        await cache.get("key3"),
    ]

    assert values.count(None) == 1  # One evicted
    assert "value3" in values  # Most recent still there


@pytest.mark.asyncio
async def test_cached_decorator():
    """Test cached decorator."""
    call_count = 0

    @cached(ttl_seconds=60)
    async def expensive_function(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return x * 2

    # First call - should execute function
    result1 = await expensive_function(5)
    assert result1 == 10
    assert call_count == 1

    # Second call with same args - should use cache
    result2 = await expensive_function(5)
    assert result2 == 10
    assert call_count == 1  # Not incremented

    # Different args - should execute function
    result3 = await expensive_function(10)
    assert result3 == 20
    assert call_count == 2


def test_cache_key_builder():
    """Test cache key builder."""
    key1 = CacheKeyBuilder.build_key("part1", "part2", 123)
    key2 = CacheKeyBuilder.build_key("part1", "part2", 123)
    key3 = CacheKeyBuilder.build_key("part1", "part2", 456)

    assert key1 == key2  # Same inputs = same key
    assert key1 != key3  # Different inputs = different key


def test_namespaced_key():
    """Test namespaced cache key builder."""
    key1 = CacheKeyBuilder.build_namespaced_key("users", "id", 123)
    key2 = CacheKeyBuilder.build_namespaced_key("posts", "id", 123)

    assert key1.startswith("users:")
    assert key2.startswith("posts:")
    assert key1 != key2  # Different namespaces
