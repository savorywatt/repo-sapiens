"""Unit tests for MCP stdio client."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.mcp.client import StdioMCPClient
from repo_sapiens.mcp.exceptions import (
    MCPProtocolError,
    MCPServerError,
    MCPTimeoutError,
)


def make_mock_process(
    *,
    returncode: int | None = None,
    stdout_data: bytes | None = None,
) -> MagicMock:
    """Create a mock subprocess for testing.

    Args:
        returncode: Process return code (None = still running).
        stdout_data: Data to return from stdout.readline().

    Returns:
        A MagicMock configured as an asyncio subprocess.
    """
    process = MagicMock(spec=asyncio.subprocess.Process)
    process.returncode = returncode

    # Mock stdin
    process.stdin = MagicMock()
    process.stdin.write = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdin.close = MagicMock()
    process.stdin.wait_closed = AsyncMock()

    # Mock stdout
    process.stdout = MagicMock()
    if stdout_data is not None:
        process.stdout.readline = AsyncMock(return_value=stdout_data)
    else:
        process.stdout.readline = AsyncMock(return_value=b"")

    return process


def json_response(request_id: int, result: dict[str, Any]) -> bytes:
    """Create a JSON-RPC response line."""
    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
    return json.dumps(response).encode() + b"\n"


def json_error_response(
    request_id: int,
    code: int,
    message: str,
) -> bytes:
    """Create a JSON-RPC error response line."""
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    return json.dumps(response).encode() + b"\n"


class TestStdioMCPClientProperties:
    """Tests for StdioMCPClient properties."""

    def test_is_running_true_when_no_returncode(self) -> None:
        """is_running should be True when process has no return code."""
        process = make_mock_process(returncode=None)
        client = StdioMCPClient("test-server", process)

        assert client.is_running is True

    def test_is_running_false_when_exited(self) -> None:
        """is_running should be False when process has exited."""
        process = make_mock_process(returncode=0)
        client = StdioMCPClient("test-server", process)

        assert client.is_running is False

    def test_name_property(self) -> None:
        """Client should expose the server name."""
        process = make_mock_process()
        client = StdioMCPClient("my-server", process)

        assert client.name == "my-server"


class TestListTools:
    """Tests for the list_tools method."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools(self) -> None:
        """list_tools should return tools from server response."""
        tools = [
            {"name": "tool1", "description": "First tool"},
            {"name": "tool2", "description": "Second tool"},
        ]
        response_data = json_response(1, {"tools": tools})
        process = make_mock_process(returncode=None, stdout_data=response_data)

        client = StdioMCPClient("test-server", process)
        result = await client.list_tools()

        assert result == tools

    @pytest.mark.asyncio
    async def test_list_tools_caches_result(self) -> None:
        """list_tools should cache the result after first call."""
        tools = [{"name": "cached-tool"}]
        response_data = json_response(1, {"tools": tools})
        process = make_mock_process(returncode=None, stdout_data=response_data)

        client = StdioMCPClient("test-server", process)

        # First call fetches from server
        result1 = await client.list_tools()

        # Second call uses cache (readline should not be called again)
        process.stdout.readline.reset_mock()
        result2 = await client.list_tools()

        assert result1 == result2
        process.stdout.readline.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_tools_force_refresh(self) -> None:
        """list_tools with force_refresh should bypass cache."""
        tools1 = [{"name": "tool-v1"}]
        tools2 = [{"name": "tool-v2"}]
        process = make_mock_process(returncode=None)

        # Set up two different responses
        process.stdout.readline = AsyncMock(
            side_effect=[
                json_response(1, {"tools": tools1}),
                json_response(2, {"tools": tools2}),
            ]
        )

        client = StdioMCPClient("test-server", process)

        result1 = await client.list_tools()
        result2 = await client.list_tools(force_refresh=True)

        assert result1 == tools1
        assert result2 == tools2


class TestCallTool:
    """Tests for the call_tool method."""

    @pytest.mark.asyncio
    async def test_call_tool_sends_request(self) -> None:
        """call_tool should send properly formatted JSON-RPC request."""
        response_data = json_response(1, {"content": "result"})
        process = make_mock_process(returncode=None, stdout_data=response_data)

        client = StdioMCPClient("test-server", process)
        await client.call_tool("my_tool", {"arg1": "value1"})

        # Verify request was written
        process.stdin.write.assert_called_once()
        written_data = process.stdin.write.call_args[0][0]
        request = json.loads(written_data.decode().strip())

        assert request["jsonrpc"] == "2.0"
        assert request["id"] == 1
        assert request["method"] == "tools/call"
        assert request["params"] == {"name": "my_tool", "arguments": {"arg1": "value1"}}

    @pytest.mark.asyncio
    async def test_call_tool_returns_result(self) -> None:
        """call_tool should return the result from server response."""
        expected_result = {"content": "tool output", "metadata": {"key": "value"}}
        response_data = json_response(1, expected_result)
        process = make_mock_process(returncode=None, stdout_data=response_data)

        client = StdioMCPClient("test-server", process)
        result = await client.call_tool("my_tool", {})

        assert result == expected_result


class TestTimeoutHandling:
    """Tests for timeout handling in the client."""

    @pytest.mark.asyncio
    async def test_call_tool_timeout_raises_error(self) -> None:
        """call_tool should raise MCPTimeoutError on timeout."""
        process = make_mock_process(returncode=None)
        # Simulate timeout by raising asyncio.TimeoutError
        process.stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError())

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPTimeoutError) as exc_info:
            await client.call_tool("slow_tool", {}, timeout=1.0)

        assert "test-server" in str(exc_info.value)
        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_error_includes_method_name(self) -> None:
        """MCPTimeoutError should include the method name."""
        process = make_mock_process(returncode=None)
        process.stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError())

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPTimeoutError) as exc_info:
            await client.call_tool("my_tool", {}, timeout=5.0)

        assert "tools/call" in str(exc_info.value)
        assert "5.0s" in str(exc_info.value)


class TestServerErrorResponses:
    """Tests for server error response handling."""

    @pytest.mark.asyncio
    async def test_server_not_running_raises_error(self) -> None:
        """Should raise MCPServerError when server has exited."""
        process = make_mock_process(returncode=1)

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPServerError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "test-server" in str(exc_info.value)
        assert "exited" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_json_rpc_error_response(self) -> None:
        """Should raise MCPServerError on JSON-RPC error response."""
        error_response = json_error_response(1, -32600, "Invalid request")
        process = make_mock_process(returncode=None, stdout_data=error_response)

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPServerError) as exc_info:
            await client.call_tool("failing_tool", {})

        assert "test-server" in str(exc_info.value)
        assert "-32600" in str(exc_info.value)
        assert "Invalid request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_response_raises_error(self) -> None:
        """Should raise MCPServerError on empty response."""
        process = make_mock_process(returncode=None, stdout_data=b"")

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPServerError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "Empty response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_json_raises_protocol_error(self) -> None:
        """Should raise MCPProtocolError on invalid JSON response."""
        process = make_mock_process(returncode=None, stdout_data=b"not json\n")

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPProtocolError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "Invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_id_mismatch_raises_protocol_error(self) -> None:
        """Should raise MCPProtocolError when response ID doesn't match request."""
        # Response with wrong ID
        wrong_id_response = json.dumps(
            {"jsonrpc": "2.0", "id": 999, "result": {}}
        ).encode() + b"\n"
        process = make_mock_process(returncode=None, stdout_data=wrong_id_response)

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPProtocolError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "ID mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_stdin_raises_error(self) -> None:
        """Should raise MCPServerError when stdin is not available."""
        process = make_mock_process(returncode=None)
        process.stdin = None

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPServerError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "No stdin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_stdout_raises_error(self) -> None:
        """Should raise MCPServerError when stdout is not available."""
        process = make_mock_process(returncode=None)
        process.stdout = None

        client = StdioMCPClient("test-server", process)

        with pytest.raises(MCPServerError) as exc_info:
            await client.call_tool("any_tool", {})

        assert "No stdout" in str(exc_info.value)


class TestClientClose:
    """Tests for the close method."""

    @pytest.mark.asyncio
    async def test_close_closes_stdin(self) -> None:
        """close() should close stdin and wait for it."""
        process = make_mock_process(returncode=None)

        client = StdioMCPClient("test-server", process)
        await client.close()

        process.stdin.close.assert_called_once()
        process.stdin.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_missing_stdin(self) -> None:
        """close() should handle case when stdin is None."""
        process = make_mock_process(returncode=None)
        process.stdin = None

        client = StdioMCPClient("test-server", process)

        # Should not raise
        await client.close()


class TestRequestIdIncrement:
    """Tests for request ID incrementing."""

    @pytest.mark.asyncio
    async def test_request_ids_increment(self) -> None:
        """Each request should have an incrementing ID."""
        process = make_mock_process(returncode=None)

        # Set up responses with matching IDs
        process.stdout.readline = AsyncMock(
            side_effect=[
                json_response(1, {}),
                json_response(2, {}),
                json_response(3, {}),
            ]
        )

        client = StdioMCPClient("test-server", process)

        await client.call_tool("tool1", {})
        await client.call_tool("tool2", {})
        await client.call_tool("tool3", {})

        # Verify three calls were made with incrementing IDs
        calls = process.stdin.write.call_args_list
        assert len(calls) == 3

        for i, call in enumerate(calls, start=1):
            request = json.loads(call[0][0].decode().strip())
            assert request["id"] == i
