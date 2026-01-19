"""MCP (Model Context Protocol) configuration models.

This module defines Pydantic models for configuring MCP servers
within the sapiens automation system.

Example:
    YAML configuration format::

        mcp:
          enabled: true
          servers:
            - name: github
              enabled: true
              env_mapping:
                GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
            - name: jira
              enabled: true
              args: ["--project", "PROJ"]
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Attributes:
        name: Server name (must match registry key).
        enabled: Whether this server is enabled.
        env_mapping: Map MCP env var names to local env vars.
        args: Additional command-line arguments.
    """

    name: str = Field(..., description="MCP server name from registry")
    enabled: bool = Field(default=True, description="Whether server is enabled")
    env_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map MCP env var names to local env vars",
    )
    args: list[str] | None = Field(
        default=None,
        description="Additional command-line arguments",
    )


class MCPConfig(BaseModel):
    """Root MCP configuration.

    Attributes:
        enabled: Master switch for MCP support.
        servers: List of configured MCP servers.
    """

    enabled: bool = Field(default=False, description="Enable MCP support")
    servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description="List of MCP server configurations",
    )

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get list of enabled server configurations.

        Returns:
            List of MCPServerConfig where enabled=True.
        """
        return [s for s in self.servers if s.enabled]

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get configuration for a specific server.

        Args:
            name: Server name to find.

        Returns:
            The server configuration, or None if not found.
        """
        for server in self.servers:
            if server.name == name:
                return server
        return None
