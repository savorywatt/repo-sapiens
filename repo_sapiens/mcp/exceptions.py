"""Exception hierarchy for MCP operations.

This module defines a structured exception hierarchy for MCP-related errors,
enabling precise error handling and informative error messages.

Exception Hierarchy:
    MCPError (base)
    ├── MCPConfigError - Configuration validation errors
    ├── MCPInstallError - Package installation failures
    └── MCPServerError - Server runtime errors
        ├── MCPTimeoutError - Operation timeouts
        └── MCPProtocolError - JSON-RPC protocol errors
"""

from __future__ import annotations


class MCPError(Exception):
    """Base exception for all MCP-related errors."""

    pass


class MCPConfigError(MCPError):
    """Configuration validation errors (missing env vars, invalid config)."""

    pass


class MCPInstallError(MCPError):
    """Package installation failures.

    Attributes:
        package: The package that failed to install.
    """

    def __init__(self, package: str, message: str) -> None:
        self.package = package
        super().__init__(f"Failed to install {package}: {message}")


class MCPServerError(MCPError):
    """Server runtime errors (startup failure, crash, communication error).

    Attributes:
        server_name: The name of the server that encountered the error.
    """

    def __init__(self, server_name: str, message: str) -> None:
        self.server_name = server_name
        super().__init__(f"MCP server '{server_name}': {message}")


class MCPTimeoutError(MCPServerError):
    """Server operation timeout.

    Inherits server_name from MCPServerError.
    """

    pass


class MCPProtocolError(MCPServerError):
    """JSON-RPC protocol errors (malformed responses, ID mismatches).

    Inherits server_name from MCPServerError.
    """

    pass
