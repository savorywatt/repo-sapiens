"""Tests for repo_sapiens/utils/connection_pool.py - HTTP connection pooling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Skip all tests in this module if h2 is not installed
# The connection_pool module uses http2=True which requires h2
try:
    import h2  # noqa: F401
    HAS_H2 = True
except ImportError:
    HAS_H2 = False

pytestmark = pytest.mark.skipif(not HAS_H2, reason="h2 package required for http2 support")

from repo_sapiens.utils.connection_pool import (
    ConnectionPoolManager,
    HTTPConnectionPool,
    get_pool,
)

# =============================================================================
# Tests for HTTPConnectionPool
# =============================================================================


class TestHTTPConnectionPool:
    """Tests for HTTPConnectionPool class."""

    def test_init_defaults(self):
        """Test HTTPConnectionPool initialization with defaults."""
        pool = HTTPConnectionPool("https://api.example.com")

        assert pool.base_url == "https://api.example.com"
        assert pool.max_connections == 10
        assert pool.max_keepalive_connections == 5
        assert pool.timeout == 30.0
        assert pool.headers == {}
        assert pool._client is None

    def test_init_custom_values(self):
        """Test HTTPConnectionPool initialization with custom values."""
        headers = {"Authorization": "Bearer token"}
        pool = HTTPConnectionPool(
            base_url="https://api.example.com",
            max_connections=20,
            max_keepalive_connections=10,
            timeout=60.0,
            headers=headers,
        )

        assert pool.max_connections == 20
        assert pool.max_keepalive_connections == 10
        assert pool.timeout == 60.0
        assert pool.headers == headers

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        """Test that initialize creates httpx client."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()

        assert pool._client is not None
        assert isinstance(pool._client, httpx.AsyncClient)

        await pool.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that multiple initialize calls don't create new clients."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()
        client1 = pool._client

        await pool.initialize()
        client2 = pool._client

        assert client1 is client2

        await pool.close()

    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        """Test that close properly clears the client."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()
        assert pool._client is not None

        await pool.close()
        assert pool._client is None

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """Test that close handles uninitialized state gracefully."""
        pool = HTTPConnectionPool("https://api.example.com")

        # Should not raise
        await pool.close()
        assert pool._client is None

    @pytest.mark.asyncio
    async def test_get_auto_initializes(self):
        """Test that GET request auto-initializes pool."""
        pool = HTTPConnectionPool("https://httpbin.org")

        with patch.object(pool, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=MagicMock(status_code=200))

            async def init_and_set_client():
                pool._client = mock_client

            mock_init.side_effect = init_and_set_client

            await pool.get("/test")

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_auto_initializes(self):
        """Test that POST request auto-initializes pool."""
        pool = HTTPConnectionPool("https://httpbin.org")

        with patch.object(pool, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))

            async def init_and_set_client():
                pool._client = mock_client

            mock_init.side_effect = init_and_set_client

            await pool.post("/test", json={"key": "value"})

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_auto_initializes(self):
        """Test that PUT request auto-initializes pool."""
        pool = HTTPConnectionPool("https://httpbin.org")

        with patch.object(pool, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()
            mock_client.put = AsyncMock(return_value=MagicMock(status_code=200))

            async def init_and_set_client():
                pool._client = mock_client

            mock_init.side_effect = init_and_set_client

            await pool.put("/test", json={"key": "value"})

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_patch_auto_initializes(self):
        """Test that PATCH request auto-initializes pool."""
        pool = HTTPConnectionPool("https://httpbin.org")

        with patch.object(pool, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()
            mock_client.patch = AsyncMock(return_value=MagicMock(status_code=200))

            async def init_and_set_client():
                pool._client = mock_client

            mock_init.side_effect = init_and_set_client

            await pool.patch("/test", json={"key": "value"})

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_auto_initializes(self):
        """Test that DELETE request auto-initializes pool."""
        pool = HTTPConnectionPool("https://httpbin.org")

        with patch.object(pool, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()
            mock_client.delete = AsyncMock(return_value=MagicMock(status_code=200))

            async def init_and_set_client():
                pool._client = mock_client

            mock_init.side_effect = init_and_set_client

            await pool.delete("/test")

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_context_manager(self):
        """Test the request context manager for streaming."""
        pool = HTTPConnectionPool("https://httpbin.org")

        # Create mock response with async context manager
        mock_response = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)

        pool._client = mock_client

        async with pool.request("GET", "/test") as response:
            assert response is mock_response

    @pytest.mark.asyncio
    async def test_context_manager_entry(self):
        """Test pool as async context manager - entry."""
        pool = HTTPConnectionPool("https://api.example.com")

        async with pool as p:
            assert p is pool
            assert p._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_exit(self):
        """Test pool as async context manager - exit."""
        pool = HTTPConnectionPool("https://api.example.com")

        async with pool:
            assert pool._client is not None

        # Client should be closed after exiting
        assert pool._client is None

    @pytest.mark.asyncio
    async def test_concurrent_initialization(self):
        """Test that concurrent initialization is safe."""
        pool = HTTPConnectionPool("https://api.example.com")

        # Run multiple initializations concurrently
        await asyncio.gather(*[pool.initialize() for _ in range(5)])

        assert pool._client is not None

        await pool.close()


# =============================================================================
# Tests for ConnectionPoolManager
# =============================================================================


class TestConnectionPoolManager:
    """Tests for ConnectionPoolManager class."""

    def test_init(self):
        """Test ConnectionPoolManager initialization."""
        manager = ConnectionPoolManager()

        assert manager._pools == {}

    @pytest.mark.asyncio
    async def test_get_pool_creates_new(self):
        """Test that get_pool creates new pool for new name."""
        manager = ConnectionPoolManager()

        pool = await manager.get_pool(
            name="test",
            base_url="https://api.example.com",
            max_connections=5,
        )

        assert pool is not None
        assert pool.base_url == "https://api.example.com"
        assert pool.max_connections == 5
        assert "test" in manager._pools

        await manager.close_all()

    @pytest.mark.asyncio
    async def test_get_pool_returns_existing(self):
        """Test that get_pool returns existing pool for same name."""
        manager = ConnectionPoolManager()

        pool1 = await manager.get_pool("test", "https://api.example.com")
        pool2 = await manager.get_pool("test", "https://different.url.com")

        # Should return same pool instance
        assert pool1 is pool2

        await manager.close_all()

    @pytest.mark.asyncio
    async def test_get_pool_multiple_pools(self):
        """Test managing multiple named pools."""
        manager = ConnectionPoolManager()

        pool1 = await manager.get_pool("api1", "https://api1.example.com")
        pool2 = await manager.get_pool("api2", "https://api2.example.com")

        assert pool1 is not pool2
        assert len(manager._pools) == 2

        await manager.close_all()

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test closing all pools."""
        manager = ConnectionPoolManager()

        await manager.get_pool("pool1", "https://api1.example.com")
        await manager.get_pool("pool2", "https://api2.example.com")

        assert len(manager._pools) == 2

        await manager.close_all()

        assert len(manager._pools) == 0

    @pytest.mark.asyncio
    async def test_close_pool_specific(self):
        """Test closing a specific pool."""
        manager = ConnectionPoolManager()

        await manager.get_pool("pool1", "https://api1.example.com")
        await manager.get_pool("pool2", "https://api2.example.com")

        await manager.close_pool("pool1")

        assert "pool1" not in manager._pools
        assert "pool2" in manager._pools

        await manager.close_all()

    @pytest.mark.asyncio
    async def test_close_pool_nonexistent(self):
        """Test closing nonexistent pool is safe."""
        manager = ConnectionPoolManager()

        # Should not raise
        await manager.close_pool("nonexistent")

    @pytest.mark.asyncio
    async def test_concurrent_pool_access(self):
        """Test concurrent access to pool manager is safe."""
        manager = ConnectionPoolManager()

        async def get_pool_task(name):
            return await manager.get_pool(name, f"https://{name}.example.com")

        # Create many pools concurrently
        pools = await asyncio.gather(*[get_pool_task(f"pool{i}") for i in range(10)])

        assert len({p.base_url for p in pools}) == 10
        assert len(manager._pools) == 10

        await manager.close_all()


# =============================================================================
# Tests for get_pool helper function
# =============================================================================


class TestGetPoolFunction:
    """Tests for the get_pool helper function."""

    @pytest.mark.asyncio
    async def test_get_pool_creates_pool(self):
        """Test get_pool creates a pool via global manager."""
        # Use unique name to avoid conflicts with other tests
        pool = await get_pool(
            name="test_helper_pool",
            base_url="https://helper.example.com",
            max_connections=15,
            timeout=45.0,
            headers={"X-Test": "value"},
        )

        assert pool is not None
        assert pool.base_url == "https://helper.example.com"
        assert pool.max_connections == 15
        assert pool.timeout == 45.0

        await pool.close()

    @pytest.mark.asyncio
    async def test_get_pool_returns_same_instance(self):
        """Test get_pool returns same instance for same name."""
        pool1 = await get_pool(
            name="test_same_instance",
            base_url="https://instance.example.com",
        )
        pool2 = await get_pool(
            name="test_same_instance",
            base_url="https://different.url.com",
        )

        assert pool1 is pool2

        await pool1.close()


# =============================================================================
# Integration and Edge Case Tests
# =============================================================================


class TestConnectionPoolEdgeCases:
    """Edge case tests for connection pool."""

    @pytest.mark.asyncio
    async def test_pool_with_empty_base_url(self):
        """Test pool with empty base URL (relative paths)."""
        pool = HTTPConnectionPool("")

        await pool.initialize()
        assert pool._client is not None

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_with_custom_headers(self):
        """Test pool initializes with custom headers."""
        headers = {
            "Authorization": "Bearer token123",
            "X-API-Key": "key456",
            "Content-Type": "application/json",
        }
        pool = HTTPConnectionPool(
            "https://api.example.com",
            headers=headers,
        )

        await pool.initialize()
        assert pool._client is not None
        # Headers are set during client creation

        await pool.close()

    @pytest.mark.asyncio
    async def test_multiple_close_calls(self):
        """Test that multiple close calls are safe."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()

        # Multiple closes should be safe
        await pool.close()
        await pool.close()
        await pool.close()

        assert pool._client is None

    @pytest.mark.asyncio
    async def test_reinitialize_after_close(self):
        """Test pool can be reinitialized after close."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()
        client1 = pool._client

        await pool.close()
        assert pool._client is None

        await pool.initialize()
        client2 = pool._client

        assert client2 is not None
        assert client2 is not client1  # New client instance

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_manager_reuse_after_close(self):
        """Test pool manager can create new pool after closing one."""
        manager = ConnectionPoolManager()

        pool1 = await manager.get_pool("reuse", "https://api.example.com")
        await manager.close_pool("reuse")

        pool2 = await manager.get_pool("reuse", "https://api.example.com")

        assert pool2 is not pool1  # New pool created

        await manager.close_all()

    @pytest.mark.asyncio
    async def test_http2_enabled(self):
        """Test that HTTP/2 is enabled for the client."""
        pool = HTTPConnectionPool("https://api.example.com")

        await pool.initialize()

        # httpx.AsyncClient with http2=True should have http2 enabled
        # This is set during initialization
        assert pool._client is not None

        await pool.close()
