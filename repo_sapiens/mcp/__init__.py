"""MCP (Model Context Protocol) support for sapiens.

This package provides unified MCP support across all agent backends (Claude Code,
Goose, Ollama/builtin). It enables sapiens to install, configure, and manage
MCP servers for enhanced agent capabilities.

Modules:
    registry: Server specifications and registry for known MCP servers.
    client: Stdio client for JSON-RPC communication with MCP servers.
    adapter: Tool adapter for integrating MCP tools with ToolRegistry.
    manager: Lifecycle management for MCP servers.
    exceptions: Exception hierarchy for MCP operations.

Example:
    Looking up available MCP servers::

        from repo_sapiens.mcp import MCP_REGISTRY, get_default_registry

        # Check what's available
        for name, spec in MCP_REGISTRY.items():
            print(f"{name}: {spec.description}")

        # Use the registry for extensibility
        registry = get_default_registry()
        if jira := registry.get("jira"):
            print(f"Jira requires: {jira.required_env}")

    Using MCPManager for lifecycle management::

        from repo_sapiens.mcp import MCPManager, AgentType
        from repo_sapiens.config.mcp import MCPConfig, MCPServerConfig

        config = MCPConfig(servers=[MCPServerConfig(name="github")])

        async with MCPManager(config, Path.cwd()) as manager:
            await manager.setup(AgentType.CLAUDE)
            # .claude.json is now available
"""

from repo_sapiens.mcp.adapter import MCPToolAdapter
from repo_sapiens.mcp.client import StdioMCPClient
from repo_sapiens.mcp.exceptions import (
    MCPConfigError,
    MCPError,
    MCPInstallError,
    MCPProtocolError,
    MCPServerError,
    MCPTimeoutError,
)
from repo_sapiens.mcp.manager import AgentType, MCPManager
from repo_sapiens.mcp.registry import (
    MCP_REGISTRY,
    DefaultMCPRegistry,
    MCPServerRegistry,
    MCPServerSpec,
    get_default_registry,
    get_official_servers,
    get_python_native_servers,
    get_servers_by_category,
)

__all__ = [
    # Registry
    "MCP_REGISTRY",
    "MCPServerSpec",
    "MCPServerRegistry",
    "DefaultMCPRegistry",
    "get_default_registry",
    "get_servers_by_category",
    "get_python_native_servers",
    "get_official_servers",
    # Client
    "StdioMCPClient",
    # Manager
    "MCPManager",
    "AgentType",
    # Adapter
    "MCPToolAdapter",
    # Exceptions
    "MCPError",
    "MCPConfigError",
    "MCPInstallError",
    "MCPServerError",
    "MCPTimeoutError",
    "MCPProtocolError",
]
