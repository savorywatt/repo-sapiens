"""MCP (Model Context Protocol) client for communicating with MCP servers.

This module provides client implementations for the Model Context Protocol,
enabling communication with MCP servers that provide tools, resources, and
other capabilities to AI agents.

The MCP protocol uses JSON-RPC 2.0 over various transports (stdio, HTTP, etc.)
to allow AI models to interact with external tools and data sources in a
standardized way.

Key Exports:
    MCPClient: Production client for real MCP server communication.
    MockMCPClient: Test double for unit testing without real servers.
    MCPError: Exception raised on MCP protocol errors.

Example:
    >>> from repo_sapiens.utils.mcp_client import MCPClient
    >>> client = MCPClient("filesystem")
    >>> await client.connect()
    >>> result = await client.call_tool("read_file", path="/etc/hosts")
    >>> await client.close()

Note:
    The base MCPClient is currently a stub implementation. Real MCP
    communication requires implementing the _send_request method for
    your specific transport (stdio, HTTP, etc.).

Thread Safety:
    MCP clients are not thread-safe. Use one client instance per async
    context. The client maintains internal state (request IDs, connection
    status) that is not protected by locks.

See Also:
    - MCP Specification: https://modelcontextprotocol.io/
    - JSON-RPC 2.0: https://www.jsonrpc.org/specification
"""

import asyncio
from typing import Any, cast

import structlog

log = structlog.get_logger(__name__)


class MCPError(Exception):
    """Exception raised when MCP protocol operations fail.

    This exception is raised when:
        - Tool execution fails on the MCP server
        - The server returns an error response
        - Connection or communication errors occur

    Attributes:
        message: Human-readable error description.

    Example:
        >>> try:
        ...     result = await client.call_tool("unknown_tool")
        ... except MCPError as e:
        ...     print(f"MCP operation failed: {e}")
    """

    pass


class MCPClient:
    """Client for interacting with MCP servers via JSON-RPC.

    This class provides the interface for communicating with MCP servers,
    allowing callers to invoke tools and receive results. The implementation
    uses subprocess communication for local MCP servers.

    The client manages connection lifecycle, request ID generation, and
    error handling for MCP protocol operations.

    Attributes:
        server_name: Name/identifier of the MCP server.

    Example:
        >>> client = MCPClient("code-tools")
        >>> await client.connect()
        >>> try:
        ...     result = await client.call_tool(
        ...         "search_code",
        ...         query="def main",
        ...         path="/project"
        ...     )
        ...     print(result)
        ... finally:
        ...     await client.close()

    Note:
        The base implementation's _send_request raises NotImplementedError.
        Subclass this and implement _send_request for your transport, or
        use MockMCPClient for testing.
    """

    def __init__(self, server_name: str) -> None:
        """Initialize MCP client.

        Args:
            server_name: Name of the MCP server to connect to. This is used
                for logging and identification purposes.

        Example:
            >>> client = MCPClient("filesystem")
            >>> client = MCPClient("code-search")
        """
        self.server_name = server_name
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to MCP server.

        This method initializes the connection to the MCP server. For
        subprocess-based servers, this would start the server process.
        For HTTP-based servers, this might establish a session.

        Raises:
            MCPError: If connection cannot be established.

        Note:
            The current implementation is a stub that marks the client
            as connected without actual server communication. Implement
            transport-specific connection logic in subclasses.

        Example:
            >>> client = MCPClient("tools")
            >>> await client.connect()
            >>> # Now ready to call tools
        """
        log.info("mcp_connect_attempt", server=self.server_name)
        # In a real implementation, this would start the MCP server process
        # or establish a connection to a running MCP server
        self._connected = True
        log.info("mcp_connected", server=self.server_name)

    async def call_tool(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        """Call an MCP tool with arguments.

        Invokes a tool on the MCP server and returns the result. The client
        automatically connects if not already connected.

        Args:
            tool_name: Name of the MCP tool to call (e.g., "read_file",
                "search_code", "execute_command").
            **kwargs: Arguments to pass to the tool. These are tool-specific
                and should match the tool's expected parameters.

        Returns:
            Tool result as a dictionary. The structure depends on the
            specific tool being called.

        Raises:
            MCPError: If tool execution fails or server returns an error.
            NotImplementedError: If using the base class without implementing
                _send_request.

        Example:
            >>> # Read a file
            >>> result = await client.call_tool("read_file", path="/etc/hosts")
            >>> print(result["content"])

            >>> # Search code
            >>> result = await client.call_tool(
            ...     "search_code",
            ...     query="import asyncio",
            ...     file_pattern="*.py"
            ... )
            >>> for match in result["matches"]:
            ...     print(f"{match['file']}:{match['line']}")
        """
        if not self._connected:
            await self.connect()

        self._request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": kwargs},
        }

        log.debug(
            "mcp_request",
            tool=tool_name,
            request_id=self._request_id,
            server=self.server_name,
        )

        try:
            response = await self._send_request(request)

            if "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                error_code = response["error"].get("code", -1)
                log.error(
                    "mcp_error",
                    tool=tool_name,
                    error=error_msg,
                    code=error_code,
                )
                raise MCPError(f"MCP tool {tool_name} failed: {error_msg}")

            log.debug("mcp_response", tool=tool_name, request_id=self._request_id)
            return cast(dict[str, Any], response.get("result", {}))

        except Exception as e:
            log.error(
                "mcp_call_failed",
                tool=tool_name,
                error=str(e),
                exc_info=True,
            )
            raise

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request to MCP server.

        This is the transport layer for MCP communication. Subclasses should
        override this method to implement the actual communication mechanism.

        Args:
            request: JSON-RPC 2.0 request dictionary with keys:
                - jsonrpc: Always "2.0"
                - id: Request identifier (integer)
                - method: Method name (e.g., "tools/call")
                - params: Method parameters

        Returns:
            JSON-RPC 2.0 response dictionary with either:
                - result: Success response data
                - error: Error object with code and message

        Raises:
            NotImplementedError: Base class does not implement actual
                communication. Use MockMCPClient for testing or implement
                a transport-specific subclass.

        Note:
            In a production implementation, this would:
            1. Serialize request to JSON
            2. Send via stdio/HTTP/WebSocket to server
            3. Wait for and parse response
            4. Handle timeouts and connection errors
        """
        # For now, raise NotImplementedError to indicate this needs actual MCP integration
        # In Phase 1, tests will mock this client
        # In Phase 2, we'll implement real MCP communication
        raise NotImplementedError(
            "MCP communication not yet implemented. "
            "Use mock MCP client for testing or implement server-specific protocol."
        )

    async def close(self) -> None:
        """Close connection to MCP server.

        Terminates the server process (if applicable) and cleans up resources.
        This method is idempotent and safe to call multiple times.

        Example:
            >>> client = MCPClient("tools")
            >>> await client.connect()
            >>> try:
            ...     result = await client.call_tool("some_tool")
            ... finally:
            ...     await client.close()
        """
        if self._process:
            self._process.terminate()
            await self._process.wait()
            log.info("mcp_closed", server=self.server_name)

        self._connected = False


class MockMCPClient(MCPClient):
    """Mock MCP client for testing.

    This client returns predefined responses for testing purposes, allowing
    unit tests to run without requiring actual MCP servers. It also records
    all calls made for assertion in tests.

    Attributes:
        responses: Dictionary mapping tool names to response data or callables.
        calls: List of all JSON-RPC requests made to this client.

    Example:
        >>> # Static responses
        >>> mock = MockMCPClient("test-server", responses={
        ...     "read_file": {"content": "Hello, World!"},
        ...     "list_files": {"files": ["a.py", "b.py"]},
        ... })
        >>> result = await mock.call_tool("read_file", path="/test.txt")
        >>> assert result["content"] == "Hello, World!"

        >>> # Dynamic responses
        >>> mock = MockMCPClient("test-server", responses={
        ...     "echo": lambda args: {"echoed": args["message"]},
        ... })
        >>> result = await mock.call_tool("echo", message="hi")
        >>> assert result["echoed"] == "hi"

        >>> # Verify calls were made
        >>> assert len(mock.calls) == 1
        >>> assert mock.calls[0]["params"]["name"] == "echo"
    """

    def __init__(self, server_name: str, responses: dict[str, Any] | None = None) -> None:
        """Initialize mock MCP client.

        Args:
            server_name: Name of the MCP server (for logging).
            responses: Dictionary mapping tool names to response data.
                Values can be:
                - Static dict: Returned directly as the tool result
                - Callable: Called with tool arguments, return value used as result

        Example:
            >>> # Empty mock (returns {} for all tools)
            >>> mock = MockMCPClient("test")

            >>> # With static responses
            >>> mock = MockMCPClient("test", responses={
            ...     "get_time": {"time": "2024-01-01T00:00:00Z"},
            ... })

            >>> # With dynamic responses
            >>> mock = MockMCPClient("test", responses={
            ...     "add": lambda args: {"sum": args["a"] + args["b"]},
            ... })
        """
        super().__init__(server_name)
        self.responses = responses or {}
        self.calls: list[dict[str, Any]] = []

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return mock response based on tool name.

        Records the request for later verification and returns either
        a predefined response or an empty result.

        Args:
            request: JSON-RPC request dictionary.

        Returns:
            JSON-RPC response with result from predefined responses,
            or empty result if tool not in responses dict.
        """
        # Record the call
        self.calls.append(request)

        tool_name = request["params"]["name"]
        arguments = request["params"]["arguments"]

        log.debug("mock_mcp_call", tool=tool_name, args=arguments)

        # Return predefined response or generate default
        if tool_name in self.responses:
            result = self.responses[tool_name]
            if callable(result):
                result = result(arguments)
            return {"jsonrpc": "2.0", "id": request["id"], "result": result}

        # Default empty response
        return {"jsonrpc": "2.0", "id": request["id"], "result": {}}
