"""Tests for repo_sapiens.utils.mcp_client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.utils.mcp_client import MCPClient, MCPError, MockMCPClient

# =============================================================================
# Tests for MCPError
# =============================================================================


class TestMCPError:
    """Test MCPError exception class."""

    def test_mcp_error_is_exception(self):
        """Test MCPError inherits from Exception."""
        assert issubclass(MCPError, Exception)

    def test_mcp_error_message(self):
        """Test MCPError stores message correctly."""
        error = MCPError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_mcp_error_can_be_raised(self):
        """Test MCPError can be raised and caught."""
        with pytest.raises(MCPError, match="Test error"):
            raise MCPError("Test error")


# =============================================================================
# Tests for MCPClient
# =============================================================================


class TestMCPClientInit:
    """Test MCPClient initialization."""

    def test_init_sets_server_name(self):
        """Test server_name is set correctly."""
        client = MCPClient("test-server")
        assert client.server_name == "test-server"

    def test_init_process_is_none(self):
        """Test _process is initialized to None."""
        client = MCPClient("test-server")
        assert client._process is None

    def test_init_request_id_is_zero(self):
        """Test _request_id is initialized to 0."""
        client = MCPClient("test-server")
        assert client._request_id == 0

    def test_init_not_connected(self):
        """Test _connected is initialized to False."""
        client = MCPClient("test-server")
        assert client._connected is False

    def test_init_with_different_server_names(self):
        """Test initialization with various server names."""
        for name in ["server1", "mcp-tools", "my_server", ""]:
            client = MCPClient(name)
            assert client.server_name == name


class TestMCPClientConnect:
    """Test MCPClient.connect method."""

    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(self):
        """Test connect sets _connected to True."""
        client = MCPClient("test-server")
        assert client._connected is False

        await client.connect()

        assert client._connected is True

    @pytest.mark.asyncio
    async def test_connect_logs_attempt_and_success(self):
        """Test connect logs connection attempt and success."""
        client = MCPClient("test-server")

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client.connect()

            # Should log attempt
            mock_log.info.assert_any_call("mcp_connect_attempt", server="test-server")
            # Should log success
            mock_log.info.assert_any_call("mcp_connected", server="test-server")

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self):
        """Test calling connect multiple times is safe."""
        client = MCPClient("test-server")

        await client.connect()
        await client.connect()

        assert client._connected is True


class TestMCPClientCallTool:
    """Test MCPClient.call_tool method."""

    @pytest.mark.asyncio
    async def test_call_tool_auto_connects_if_not_connected(self):
        """Test call_tool calls connect if not connected."""
        client = MCPClient("test-server")
        client._send_request = AsyncMock(return_value={"result": {}})

        assert client._connected is False
        await client.call_tool("some_tool")
        assert client._connected is True

    @pytest.mark.asyncio
    async def test_call_tool_increments_request_id(self):
        """Test call_tool increments request_id on each call."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"result": {}})

        await client.call_tool("tool1")
        assert client._request_id == 1

        await client.call_tool("tool2")
        assert client._request_id == 2

        await client.call_tool("tool3")
        assert client._request_id == 3

    @pytest.mark.asyncio
    async def test_call_tool_builds_correct_request(self):
        """Test call_tool builds correct JSON-RPC request."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"result": {}})

        await client.call_tool("test_tool", arg1="value1", arg2=42)

        client._send_request.assert_called_once()
        request = client._send_request.call_args[0][0]

        assert request["jsonrpc"] == "2.0"
        assert request["id"] == 1
        assert request["method"] == "tools/call"
        assert request["params"]["name"] == "test_tool"
        assert request["params"]["arguments"] == {"arg1": "value1", "arg2": 42}

    @pytest.mark.asyncio
    async def test_call_tool_returns_result(self):
        """Test call_tool returns the result from response."""
        client = MCPClient("test-server")
        client._connected = True
        expected_result = {"data": "test_data", "count": 5}
        client._send_request = AsyncMock(return_value={"result": expected_result})

        result = await client.call_tool("test_tool")

        assert result == expected_result

    @pytest.mark.asyncio
    async def test_call_tool_returns_empty_dict_for_missing_result(self):
        """Test call_tool returns empty dict if result key is missing."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={})

        result = await client.call_tool("test_tool")

        assert result == {}

    @pytest.mark.asyncio
    async def test_call_tool_raises_mcp_error_on_error_response(self):
        """Test call_tool raises MCPError when response contains error."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"error": {"message": "Tool not found", "code": -32601}})

        with pytest.raises(MCPError, match="MCP tool test_tool failed: Tool not found"):
            await client.call_tool("test_tool")

    @pytest.mark.asyncio
    async def test_call_tool_handles_error_without_message(self):
        """Test call_tool handles error response without message field."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"error": {}})

        with pytest.raises(MCPError, match="Unknown error"):
            await client.call_tool("test_tool")

    @pytest.mark.asyncio
    async def test_call_tool_logs_error_response(self):
        """Test call_tool logs error details from response."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"error": {"message": "Error msg", "code": -1}})

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            with pytest.raises(MCPError):
                await client.call_tool("test_tool")

            # Called twice: once for mcp_error, once for mcp_call_failed
            assert mock_log.error.call_count >= 1
            # Check first call is the mcp_error
            first_call = mock_log.error.call_args_list[0]
            assert "mcp_error" in str(first_call)
            assert "test_tool" in str(first_call)

    @pytest.mark.asyncio
    async def test_call_tool_logs_debug_on_request(self):
        """Test call_tool logs debug info on request."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"result": {}})

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client.call_tool("test_tool")

            mock_log.debug.assert_called()
            # Check first debug call (request)
            call_args = mock_log.debug.call_args_list[0]
            assert "mcp_request" in str(call_args)

    @pytest.mark.asyncio
    async def test_call_tool_logs_debug_on_response(self):
        """Test call_tool logs debug info on response."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(return_value={"result": {}})

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client.call_tool("test_tool")

            # Check second debug call (response)
            call_args = mock_log.debug.call_args_list[1]
            assert "mcp_response" in str(call_args)

    @pytest.mark.asyncio
    async def test_call_tool_logs_and_reraises_exceptions(self):
        """Test call_tool logs and re-raises exceptions from _send_request."""
        client = MCPClient("test-server")
        client._connected = True
        client._send_request = AsyncMock(side_effect=RuntimeError("Connection lost"))

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            with pytest.raises(RuntimeError, match="Connection lost"):
                await client.call_tool("test_tool")

            mock_log.error.assert_called_once()
            call_kwargs = mock_log.error.call_args
            assert "mcp_call_failed" in str(call_kwargs)


class TestMCPClientSendRequest:
    """Test MCPClient._send_request method."""

    @pytest.mark.asyncio
    async def test_send_request_raises_not_implemented(self):
        """Test _send_request raises NotImplementedError."""
        client = MCPClient("test-server")

        with pytest.raises(NotImplementedError, match="MCP communication not yet implemented"):
            await client._send_request({"jsonrpc": "2.0", "id": 1})


class TestMCPClientClose:
    """Test MCPClient.close method."""

    @pytest.mark.asyncio
    async def test_close_sets_connected_false(self):
        """Test close sets _connected to False."""
        client = MCPClient("test-server")
        client._connected = True

        await client.close()

        assert client._connected is False

    @pytest.mark.asyncio
    async def test_close_terminates_process_if_exists(self):
        """Test close terminates process if it exists."""
        client = MCPClient("test-server")
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        client._process = mock_process

        await client.close()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_logs_when_process_terminated(self):
        """Test close logs when process is terminated."""
        client = MCPClient("test-server")
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        client._process = mock_process

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client.close()

            mock_log.info.assert_called_once_with("mcp_closed", server="test-server")

    @pytest.mark.asyncio
    async def test_close_without_process_does_not_log(self):
        """Test close without process does not log mcp_closed."""
        client = MCPClient("test-server")
        client._connected = True

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client.close()

            mock_log.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """Test calling close multiple times is safe."""
        client = MCPClient("test-server")
        client._connected = True

        await client.close()
        await client.close()

        assert client._connected is False


# =============================================================================
# Tests for MockMCPClient
# =============================================================================


class TestMockMCPClientInit:
    """Test MockMCPClient initialization."""

    def test_init_inherits_from_mcp_client(self):
        """Test MockMCPClient inherits from MCPClient."""
        client = MockMCPClient("test-server")
        assert isinstance(client, MCPClient)

    def test_init_sets_server_name(self):
        """Test server_name is set correctly."""
        client = MockMCPClient("test-server")
        assert client.server_name == "test-server"

    def test_init_with_no_responses(self):
        """Test initialization with no responses defaults to empty dict."""
        client = MockMCPClient("test-server")
        assert client.responses == {}

    def test_init_with_responses(self):
        """Test initialization with predefined responses."""
        responses = {"tool1": {"result": "data"}}
        client = MockMCPClient("test-server", responses=responses)
        assert client.responses == responses

    def test_init_calls_empty_list(self):
        """Test calls is initialized to empty list."""
        client = MockMCPClient("test-server")
        assert client.calls == []


class TestMockMCPClientSendRequest:
    """Test MockMCPClient._send_request method."""

    @pytest.mark.asyncio
    async def test_send_request_records_call(self):
        """Test _send_request records the request in calls list."""
        client = MockMCPClient("test-server")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {"arg": "value"}},
        }

        await client._send_request(request)

        assert len(client.calls) == 1
        assert client.calls[0] == request

    @pytest.mark.asyncio
    async def test_send_request_returns_predefined_response(self):
        """Test _send_request returns predefined response for tool."""
        responses = {"test_tool": {"status": "success", "data": [1, 2, 3]}}
        client = MockMCPClient("test-server", responses=responses)
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {}},
        }

        response = await client._send_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"status": "success", "data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_send_request_returns_empty_result_for_unknown_tool(self):
        """Test _send_request returns empty result for unknown tool."""
        client = MockMCPClient("test-server")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        response = await client._send_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {}

    @pytest.mark.asyncio
    async def test_send_request_calls_callable_response(self):
        """Test _send_request calls callable response with arguments."""

        def dynamic_response(args):
            return {"computed": args.get("input", 0) * 2}

        responses = {"compute_tool": dynamic_response}
        client = MockMCPClient("test-server", responses=responses)
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "compute_tool", "arguments": {"input": 5}},
        }

        response = await client._send_request(request)

        assert response["result"] == {"computed": 10}

    @pytest.mark.asyncio
    async def test_send_request_logs_debug(self):
        """Test _send_request logs debug info."""
        client = MockMCPClient("test-server")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {"key": "value"}},
        }

        with patch("repo_sapiens.utils.mcp_client.log") as mock_log:
            await client._send_request(request)

            mock_log.debug.assert_called_once()
            call_kwargs = mock_log.debug.call_args
            assert "mock_mcp_call" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_send_request_preserves_request_id(self):
        """Test _send_request uses request id in response."""
        client = MockMCPClient("test-server")
        request = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "tool", "arguments": {}},
        }

        response = await client._send_request(request)

        assert response["id"] == 42

    @pytest.mark.asyncio
    async def test_send_request_records_multiple_calls(self):
        """Test _send_request records all calls in order."""
        client = MockMCPClient("test-server")

        for i in range(3):
            request = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/call",
                "params": {"name": f"tool_{i}", "arguments": {}},
            }
            await client._send_request(request)

        assert len(client.calls) == 3
        assert client.calls[0]["params"]["name"] == "tool_0"
        assert client.calls[1]["params"]["name"] == "tool_1"
        assert client.calls[2]["params"]["name"] == "tool_2"


class TestMockMCPClientIntegration:
    """Integration tests for MockMCPClient using call_tool."""

    @pytest.mark.asyncio
    async def test_call_tool_with_mock_client(self):
        """Test using call_tool with MockMCPClient."""
        responses = {"greet": {"message": "Hello, World!"}}
        client = MockMCPClient("test-server", responses=responses)

        result = await client.call_tool("greet")

        assert result == {"message": "Hello, World!"}
        assert len(client.calls) == 1

    @pytest.mark.asyncio
    async def test_call_tool_passes_arguments_to_callable(self):
        """Test call_tool passes arguments correctly to callable response."""

        def concat_response(args):
            return {"result": args.get("prefix", "") + args.get("suffix", "")}

        responses = {"concat": concat_response}
        client = MockMCPClient("test-server", responses=responses)

        result = await client.call_tool("concat", prefix="Hello, ", suffix="World!")

        assert result == {"result": "Hello, World!"}

    @pytest.mark.asyncio
    async def test_multiple_tools_with_different_responses(self):
        """Test multiple tools each returning their configured response."""
        responses = {
            "tool_a": {"data": "A"},
            "tool_b": {"data": "B"},
            "tool_c": {"data": "C"},
        }
        client = MockMCPClient("test-server", responses=responses)

        result_a = await client.call_tool("tool_a")
        result_b = await client.call_tool("tool_b")
        result_c = await client.call_tool("tool_c")

        assert result_a == {"data": "A"}
        assert result_b == {"data": "B"}
        assert result_c == {"data": "C"}
        assert len(client.calls) == 3

    @pytest.mark.asyncio
    async def test_request_id_increments_with_mock(self):
        """Test request IDs increment correctly with mock client."""
        client = MockMCPClient("test-server")

        await client.call_tool("tool1")
        await client.call_tool("tool2")
        await client.call_tool("tool3")

        assert client.calls[0]["id"] == 1
        assert client.calls[1]["id"] == 2
        assert client.calls[2]["id"] == 3
