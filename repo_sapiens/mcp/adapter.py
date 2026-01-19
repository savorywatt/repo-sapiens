"""Tool adapter for integrating MCP servers with ToolRegistry.

This module bridges MCP servers to the sapiens ToolRegistry, converting
MCP tool schemas to ToolDefinition format and routing tool calls to
the appropriate server.

Example:
    Using the adapter with running MCP servers::

        clients = manager.get_stdio_clients()
        adapter = MCPToolAdapter(clients)

        # Discover all tools
        tools = await adapter.discover_tools()
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")

        # Execute a tool
        result = await adapter.execute("github_list_repos", {"owner": "anthropics"})
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from repo_sapiens.agents.tools import ToolDefinition

if TYPE_CHECKING:
    from repo_sapiens.mcp.client import StdioMCPClient


class MCPToolAdapter:
    """Adapts MCP server tools for use with sapiens ToolRegistry.

    Converts MCP tool schemas to ToolDefinition format and routes
    tool calls to the appropriate MCP server. Tool names are prefixed
    with the server name to avoid collisions (e.g., "github_list_repos").

    Attributes:
        clients: Dictionary mapping server names to their clients.
    """

    def __init__(self, clients: dict[str, StdioMCPClient]) -> None:
        """Initialize the adapter.

        Args:
            clients: Dictionary mapping server names to StdioMCPClient instances.
        """
        self._clients = clients
        self._tool_to_server: dict[str, str] = {}

    async def discover_tools(self) -> list[ToolDefinition]:
        """Discover all tools from connected MCP servers.

        Returns:
            List of ToolDefinition objects suitable for ToolRegistry.
            Tool names are prefixed with server name (e.g., "jira_create_issue").

        Raises:
            MCPServerError: If a server fails to respond.
            MCPTimeoutError: If a server times out.
        """
        tools: list[ToolDefinition] = []

        for server_name, client in self._clients.items():
            mcp_tools = await client.list_tools()

            for mcp_tool in mcp_tools:
                # Prefix tool names with server to avoid collisions
                prefixed_name = f"{server_name}_{mcp_tool['name']}"
                self._tool_to_server[prefixed_name] = server_name

                # Convert MCP schema to ToolDefinition
                params: dict[str, str] = {}
                input_schema = mcp_tool.get("inputSchema", {})
                for prop_name, prop_schema in input_schema.get("properties", {}).items():
                    params[prop_name] = prop_schema.get("description", "")

                tools.append(
                    ToolDefinition(
                        name=prefixed_name,
                        description=mcp_tool.get("description", ""),
                        parameters=params,
                    )
                )

        return tools

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool via the appropriate MCP server.

        Args:
            tool_name: Prefixed tool name (e.g., "jira_create_issue").
            arguments: Tool arguments dictionary.

        Returns:
            Tool result as a string. On error, returns an error message
            string rather than raising an exception.
        """
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return f"Error: Unknown tool '{tool_name}'"

        client = self._clients.get(server_name)
        if not client:
            return f"Error: Server '{server_name}' not available"

        # Strip prefix to get original tool name
        original_name = tool_name[len(server_name) + 1 :]  # +1 for underscore

        try:
            result = await client.call_tool(original_name, arguments)
            # Extract text content from MCP response
            content = result.get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return "\n".join(texts) if texts else str(result)
        except Exception as e:
            return f"Error calling {tool_name}: {e}"

    def get_tool_server(self, tool_name: str) -> str | None:
        """Get the server name for a given tool.

        Args:
            tool_name: The prefixed tool name.

        Returns:
            The server name, or None if the tool is unknown.
        """
        return self._tool_to_server.get(tool_name)

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name belongs to an MCP server.

        Args:
            tool_name: The tool name to check.

        Returns:
            True if this is an MCP tool, False otherwise.
        """
        return tool_name in self._tool_to_server
