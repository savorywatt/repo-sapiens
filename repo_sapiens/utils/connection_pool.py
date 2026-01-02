"""
HTTP connection pooling for API requests.
Improves performance through connection reuse and HTTP/2 multiplexing.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class HTTPConnectionPool:
    """HTTP connection pool for API requests."""

    def __init__(
        self,
        base_url: str,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.timeout = timeout
        self.headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            if self._client is None:
                limits = httpx.Limits(
                    max_keepalive_connections=self.max_keepalive_connections,
                    max_connections=self.max_connections,
                    keepalive_expiry=30.0,
                )

                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    limits=limits,
                    timeout=self.timeout,
                    http2=True,  # Enable HTTP/2 for multiplexing
                    headers=self.headers,
                )

                log.info(
                    "connection_pool_initialized",
                    base_url=self.base_url,
                    max_connections=self.max_connections,
                )

    async def close(self) -> None:
        """Close the connection pool."""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None
                log.info("connection_pool_closed", base_url=self.base_url)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make GET request."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make POST request."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.post(path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make PUT request."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.put(path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make PATCH request."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.patch(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make DELETE request."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        return await self._client.delete(path, **kwargs)

    @asynccontextmanager
    async def request(self, method: str, path: str, **kwargs: Any) -> AsyncIterator[httpx.Response]:
        """Context manager for making requests."""
        if self._client is None:
            await self.initialize()

        assert self._client is not None
        async with self._client.stream(method, path, **kwargs) as response:
            yield response

    async def __aenter__(self) -> "HTTPConnectionPool":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


class ConnectionPoolManager:
    """Manage multiple connection pools."""

    def __init__(self) -> None:
        self._pools: dict[str, HTTPConnectionPool] = {}
        self._lock = asyncio.Lock()

    async def get_pool(
        self,
        name: str,
        base_url: str,
        max_connections: int = 10,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> HTTPConnectionPool:
        """Get or create a named connection pool."""
        async with self._lock:
            if name not in self._pools:
                pool = HTTPConnectionPool(
                    base_url=base_url,
                    max_connections=max_connections,
                    timeout=timeout,
                    headers=headers,
                )
                await pool.initialize()
                self._pools[name] = pool
                log.info("connection_pool_created", name=name, base_url=base_url)

            return self._pools[name]

    async def close_all(self) -> None:
        """Close all connection pools."""
        async with self._lock:
            for pool in self._pools.values():
                await pool.close()
            self._pools.clear()
            log.info("all_connection_pools_closed")

    async def close_pool(self, name: str) -> None:
        """Close a specific connection pool."""
        async with self._lock:
            if name in self._pools:
                await self._pools[name].close()
                del self._pools[name]
                log.info("connection_pool_closed", name=name)


# Global pool manager
_pool_manager = ConnectionPoolManager()


async def get_pool(
    name: str,
    base_url: str,
    max_connections: int = 10,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> HTTPConnectionPool:
    """Get a named connection pool from the global manager."""
    return await _pool_manager.get_pool(
        name=name,
        base_url=base_url,
        max_connections=max_connections,
        timeout=timeout,
        headers=headers,
    )
