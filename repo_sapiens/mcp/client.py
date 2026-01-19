"""Stdio client for MCP server communication.

This module implements a JSON-RPC 2.0 client for communicating with MCP servers
over stdin/stdout. It handles request serialization, response parsing, and
error handling according to the MCP protocol.

Example:
    Using the client with a running server process::

        client = StdioMCPClient("github", process)

        # List available tools
        tools = await client.list_tools()
        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")

        # Call a tool
        result = await client.call_tool("list_repos", {"owner": "anthropics"})
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from repo_sapiens.mcp.exceptions import (
    MCPProtocolError,
    MCPServerError,
    MCPTimeoutError,
)


class StdioMCPClient:
    """Client for communicating with an MCP server via stdio.

    Implements JSON-RPC 2.0 over stdin/stdout for the MCP protocol.
    Thread-safe via asyncio.Lock for request serialization.

    Attributes:
        name: The server name (for error messages).
        is_running: Whether the server process is still running.
    """

    def __init__(self, name: str, process: asyncio.subprocess.Process) -> None:
        """Initialize the client.

        Args:
            name: The server name (used in error messages).
            process: The subprocess running the MCP server.
        """
        self.name = name
        self._process = process
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._tools: list[dict[str, Any]] | None = None

    @property
    def is_running(self) -> bool:
        """Check if the server process is still running."""
        return self._process.returncode is None

    async def list_tools(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get available tools from this server.

        Args:
            force_refresh: If True, bypass cache and query server.

        Returns:
            List of tool definitions from the server.

        Raises:
            MCPServerError: If the server is not running or returns an error.
            MCPTimeoutError: If the request times out.
            MCPProtocolError: If the response is malformed.
        """
        if self._tools is not None and not force_refresh:
            return self._tools

        result = await self._send_request("tools/list", {})
        self._tools = result.get("tools", [])
        return self._tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Call a tool on this MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments as a dictionary.
            timeout: Request timeout in seconds (default: 30).

        Returns:
            Tool result content from the server.

        Raises:
            MCPServerError: If the server returns an error.
            MCPTimeoutError: If the tool call times out.
            MCPProtocolError: If the response is malformed.
        """
        return await self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            timeout=timeout,
        )

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response.

        Thread-safe via lock - serializes concurrent requests to the same server.

        Args:
            method: The JSON-RPC method name.
            params: Method parameters.
            timeout: Request timeout in seconds.

        Returns:
            The 'result' field from the JSON-RPC response.

        Raises:
            MCPServerError: If the server is not running or returns an error.
            MCPTimeoutError: If the request times out.
            MCPProtocolError: If the response is malformed or ID mismatches.
        """
        if not self.is_running:
            raise MCPServerError(self.name, "Server process has exited")

        async with self._lock:
            self._request_id += 1
            request_id = self._request_id

            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }

            # Write request
            request_bytes = json.dumps(request).encode() + b"\n"
            if self._process.stdin is None:
                raise MCPServerError(self.name, "No stdin available")

            self._process.stdin.write(request_bytes)
            await self._process.stdin.drain()

            # Read response
            if self._process.stdout is None:
                raise MCPServerError(self.name, "No stdout available")

            try:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=timeout,
                )
            except TimeoutError:
                raise MCPTimeoutError(
                    self.name,
                    f"Request {method} timed out after {timeout}s",
                )

            if not response_line:
                if self._process.returncode is not None:
                    raise MCPServerError(
                        self.name,
                        f"Server exited with code {self._process.returncode}",
                    )
                raise MCPServerError(self.name, "Empty response from server")

            # Parse response
            try:
                response = json.loads(response_line.decode())
            except json.JSONDecodeError as e:
                raise MCPProtocolError(self.name, f"Invalid JSON response: {e}")

            # Validate response
            if response.get("id") != request_id:
                raise MCPProtocolError(
                    self.name,
                    f"Response ID mismatch: expected {request_id}, got {response.get('id')}",
                )

            if "error" in response:
                error = response["error"]
                raise MCPServerError(
                    self.name,
                    f"[{error.get('code', 'unknown')}] {error.get('message', 'Unknown error')}",
                )

            return cast(dict[str, Any], response.get("result", {}))

    async def close(self) -> None:
        """Close the connection (does not terminate the server process)."""
        if self._process.stdin:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
