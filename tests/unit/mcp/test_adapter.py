"""Unit tests for MCP tool adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from repo_sapiens.agents.tools import ToolDefinition
from repo_sapiens.mcp.adapter import MCPToolAdapter


def make_mock_client(
    name: str,
    tools: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock StdioMCPClient for testing.

    Args:
        name: The server name.
        tools: Optional list of tool definitions to return.

    Returns:
        A MagicMock configured as a StdioMCPClient.
    """
    client = MagicMock()
    client.name = name
    client.list_tools = AsyncMock(return_value=tools or [])
    client.call_tool = AsyncMock(return_value={"content": []})
    return client


class TestMCPToolAdapterInit:
    """Tests for MCPToolAdapter initialization."""

    def test_accepts_empty_clients(self) -> None:
        """Adapter should accept an empty clients dict."""
        adapter = MCPToolAdapter({})

        assert adapter._clients == {}

    def test_stores_clients(self) -> None:
        """Adapter should store the provided clients."""
        client1 = make_mock_client("server1")
        client2 = make_mock_client("server2")

        adapter = MCPToolAdapter({"server1": client1, "server2": client2})

        assert "server1" in adapter._clients
        assert "server2" in adapter._clients


class TestDiscoverTools:
    """Tests for the discover_tools method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_clients(self) -> None:
        """discover_tools should return empty list when no clients."""
        adapter = MCPToolAdapter({})

        tools = await adapter.discover_tools()

        assert tools == []

    @pytest.mark.asyncio
    async def test_prefixes_tool_names_with_server(self) -> None:
        """discover_tools should prefix tool names with server name."""
        client = make_mock_client(
            "github",
            tools=[
                {"name": "list_repos", "description": "List repositories"},
            ],
        )
        adapter = MCPToolAdapter({"github": client})

        tools = await adapter.discover_tools()

        assert len(tools) == 1
        assert tools[0].name == "github_list_repos"

    @pytest.mark.asyncio
    async def test_returns_tool_definitions(self) -> None:
        """discover_tools should return ToolDefinition objects."""
        client = make_mock_client(
            "jira",
            tools=[
                {"name": "create_issue", "description": "Create a new issue"},
            ],
        )
        adapter = MCPToolAdapter({"jira": client})

        tools = await adapter.discover_tools()

        assert len(tools) == 1
        assert isinstance(tools[0], ToolDefinition)
        assert tools[0].description == "Create a new issue"

    @pytest.mark.asyncio
    async def test_extracts_parameters_from_schema(self) -> None:
        """discover_tools should extract parameters from inputSchema."""
        client = make_mock_client(
            "jira",
            tools=[
                {
                    "name": "create_issue",
                    "description": "Create issue",
                    "inputSchema": {
                        "properties": {
                            "title": {"description": "Issue title"},
                            "body": {"description": "Issue body"},
                        }
                    },
                },
            ],
        )
        adapter = MCPToolAdapter({"jira": client})

        tools = await adapter.discover_tools()

        assert tools[0].parameters == {
            "title": "Issue title",
            "body": "Issue body",
        }

    @pytest.mark.asyncio
    async def test_handles_missing_input_schema(self) -> None:
        """discover_tools should handle tools without inputSchema."""
        client = make_mock_client(
            "simple",
            tools=[
                {"name": "ping", "description": "Ping server"},
            ],
        )
        adapter = MCPToolAdapter({"simple": client})

        tools = await adapter.discover_tools()

        assert tools[0].parameters == {}

    @pytest.mark.asyncio
    async def test_handles_missing_description(self) -> None:
        """discover_tools should handle tools without description."""
        client = make_mock_client(
            "server",
            tools=[
                {"name": "undocumented"},
            ],
        )
        adapter = MCPToolAdapter({"server": client})

        tools = await adapter.discover_tools()

        assert tools[0].description == ""

    @pytest.mark.asyncio
    async def test_combines_tools_from_multiple_servers(self) -> None:
        """discover_tools should combine tools from all servers."""
        client1 = make_mock_client(
            "github",
            tools=[{"name": "list_repos", "description": "List repos"}],
        )
        client2 = make_mock_client(
            "jira",
            tools=[{"name": "create_issue", "description": "Create issue"}],
        )
        adapter = MCPToolAdapter({"github": client1, "jira": client2})

        tools = await adapter.discover_tools()

        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert "github_list_repos" in tool_names
        assert "jira_create_issue" in tool_names

    @pytest.mark.asyncio
    async def test_builds_tool_to_server_mapping(self) -> None:
        """discover_tools should populate the tool-to-server mapping."""
        client = make_mock_client(
            "github",
            tools=[
                {"name": "list_repos", "description": "List repos"},
                {"name": "create_pr", "description": "Create PR"},
            ],
        )
        adapter = MCPToolAdapter({"github": client})

        await adapter.discover_tools()

        assert adapter.get_tool_server("github_list_repos") == "github"
        assert adapter.get_tool_server("github_create_pr") == "github"


class TestExecute:
    """Tests for the execute method."""

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_tool(self) -> None:
        """execute should return error string for unknown tool."""
        adapter = MCPToolAdapter({})

        result = await adapter.execute("unknown_tool", {})

        assert "Error" in result
        assert "unknown_tool" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_server(self) -> None:
        """execute should return error if server not in clients."""
        adapter = MCPToolAdapter({})
        adapter._tool_to_server["orphan_tool"] = "missing_server"

        result = await adapter.execute("orphan_tool", {})

        assert "Error" in result
        assert "missing_server" in result

    @pytest.mark.asyncio
    async def test_calls_correct_server(self) -> None:
        """execute should call the tool on the correct server."""
        client = make_mock_client("github")
        client.call_tool = AsyncMock(return_value={"content": [{"type": "text", "text": "success"}]})
        adapter = MCPToolAdapter({"github": client})
        adapter._tool_to_server["github_list_repos"] = "github"

        await adapter.execute("github_list_repos", {"owner": "test"})

        client.call_tool.assert_called_once_with("list_repos", {"owner": "test"})

    @pytest.mark.asyncio
    async def test_strips_prefix_from_tool_name(self) -> None:
        """execute should strip server prefix when calling."""
        client = make_mock_client("my_server")
        client.call_tool = AsyncMock(return_value={"content": []})
        adapter = MCPToolAdapter({"my_server": client})
        adapter._tool_to_server["my_server_some_tool"] = "my_server"

        await adapter.execute("my_server_some_tool", {})

        # Should call with "some_tool", not "my_server_some_tool"
        client.call_tool.assert_called_once_with("some_tool", {})

    @pytest.mark.asyncio
    async def test_extracts_text_content(self) -> None:
        """execute should extract text content from response."""
        client = make_mock_client("server")
        client.call_tool = AsyncMock(
            return_value={
                "content": [
                    {"type": "text", "text": "line 1"},
                    {"type": "text", "text": "line 2"},
                ]
            }
        )
        adapter = MCPToolAdapter({"server": client})
        adapter._tool_to_server["server_tool"] = "server"

        result = await adapter.execute("server_tool", {})

        assert result == "line 1\nline 2"

    @pytest.mark.asyncio
    async def test_handles_empty_content(self) -> None:
        """execute should handle empty content array."""
        client = make_mock_client("server")
        client.call_tool = AsyncMock(return_value={"content": []})
        adapter = MCPToolAdapter({"server": client})
        adapter._tool_to_server["server_tool"] = "server"

        result = await adapter.execute("server_tool", {})

        # Should return stringified result when no text content
        assert "content" in result

    @pytest.mark.asyncio
    async def test_handles_non_text_content(self) -> None:
        """execute should skip non-text content items."""
        client = make_mock_client("server")
        client.call_tool = AsyncMock(
            return_value={
                "content": [
                    {"type": "image", "data": "binary"},
                    {"type": "text", "text": "only text"},
                ]
            }
        )
        adapter = MCPToolAdapter({"server": client})
        adapter._tool_to_server["server_tool"] = "server"

        result = await adapter.execute("server_tool", {})

        assert result == "only text"

    @pytest.mark.asyncio
    async def test_catches_exceptions_and_returns_error(self) -> None:
        """execute should catch exceptions and return error string."""
        client = make_mock_client("server")
        client.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
        adapter = MCPToolAdapter({"server": client})
        adapter._tool_to_server["server_tool"] = "server"

        result = await adapter.execute("server_tool", {})

        assert "Error" in result
        assert "boom" in result


class TestGetToolServer:
    """Tests for the get_tool_server method."""

    def test_returns_none_for_unknown_tool(self) -> None:
        """get_tool_server should return None for unknown tools."""
        adapter = MCPToolAdapter({})

        assert adapter.get_tool_server("unknown") is None

    def test_returns_server_name_for_known_tool(self) -> None:
        """get_tool_server should return server name for known tools."""
        adapter = MCPToolAdapter({})
        adapter._tool_to_server["github_list_repos"] = "github"

        assert adapter.get_tool_server("github_list_repos") == "github"


class TestIsMCPTool:
    """Tests for the is_mcp_tool method."""

    def test_returns_false_for_unknown_tool(self) -> None:
        """is_mcp_tool should return False for unknown tools."""
        adapter = MCPToolAdapter({})

        assert adapter.is_mcp_tool("unknown") is False

    def test_returns_true_for_known_tool(self) -> None:
        """is_mcp_tool should return True for known tools."""
        adapter = MCPToolAdapter({})
        adapter._tool_to_server["github_list_repos"] = "github"

        assert adapter.is_mcp_tool("github_list_repos") is True

    def test_distinguishes_mcp_from_builtin_tools(self) -> None:
        """is_mcp_tool should distinguish MCP tools from builtins."""
        adapter = MCPToolAdapter({})
        adapter._tool_to_server["github_list_repos"] = "github"

        # MCP tool
        assert adapter.is_mcp_tool("github_list_repos") is True

        # Builtin tool (not registered)
        assert adapter.is_mcp_tool("read_file") is False
        assert adapter.is_mcp_tool("write_file") is False
