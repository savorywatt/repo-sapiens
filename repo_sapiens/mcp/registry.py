"""MCP server registry and specifications.

This module defines the registry of known MCP servers, their installation
requirements, and environment variable dependencies.

Example:
    Looking up a server specification::

        from repo_sapiens.mcp.registry import MCP_REGISTRY, get_default_registry

        # Direct lookup
        github_spec = MCP_REGISTRY["github"]
        print(f"Requires: {github_spec.required_env}")

        # Via registry (supports custom servers)
        registry = get_default_registry()
        if jira := registry.get("jira"):
            print(f"Install via: {jira.install_type}")
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator


# === Immutable Server Specification ===


@dataclass(frozen=True, slots=True)
class MCPServerSpec:
    """Immutable specification for a known MCP server.

    Using frozen=True ensures specs can't be accidentally modified after creation.
    Using slots=True improves memory efficiency and attribute access speed.

    Attributes:
        name: Unique identifier for the server.
        description: Human-readable description of server capabilities.
        install_type: How to install the server (pip, npm, uvx, remote, builtin).
        package: Package name for pip/npm, or command/URL for others.
        required_env: Environment variables that must be set.
        optional_env: Environment variables that may be set.
        command: Override default command (derived from install_type if None).
        default_args: Default arguments passed to the server.
        python_native: Whether this is a Python-native server (no Node.js).
        official: Whether this is an official/maintained server.
        url: Documentation or repository URL.
    """

    name: str
    description: str

    # Installation
    install_type: Literal["pip", "npm", "uvx", "remote", "builtin"]
    package: str

    # Environment (tuples for immutability)
    required_env: tuple[str, ...] = ()
    optional_env: tuple[str, ...] = ()

    # Execution
    command: tuple[str, ...] | None = None
    default_args: tuple[str, ...] = ()

    # Metadata
    python_native: bool = False
    official: bool = False
    url: str = ""

    def with_args(self, args: tuple[str, ...]) -> MCPServerSpec:
        """Create a new spec with different args (immutable update pattern).

        Args:
            args: New default arguments for the server.

        Returns:
            A new MCPServerSpec with updated args.
        """
        return replace(self, default_args=args)


# === Protocol-Based Registry Interface ===


class MCPServerRegistry(Protocol):
    """Protocol for MCP server registries.

    This protocol enables custom registry implementations, such as
    registries that load specs from external sources.
    """

    def get(self, name: str) -> MCPServerSpec | None:
        """Get a server spec by name.

        Args:
            name: The server name to look up.

        Returns:
            The server spec if found, None otherwise.
        """
        ...

    def list_all(self) -> dict[str, MCPServerSpec]:
        """List all available server specs.

        Returns:
            Dictionary mapping server names to their specs.
        """
        ...

    def register(self, spec: MCPServerSpec) -> None:
        """Register a new server spec.

        Args:
            spec: The server specification to register.
        """
        ...


class DefaultMCPRegistry:
    """Default registry implementation with builtin servers.

    This class provides a mutable registry that can be extended with
    custom server specifications at runtime.
    """

    def __init__(self) -> None:
        self._specs: dict[str, MCPServerSpec] = {}

    def get(self, name: str) -> MCPServerSpec | None:
        """Get a server spec by name."""
        return self._specs.get(name)

    def list_all(self) -> dict[str, MCPServerSpec]:
        """List all available server specs."""
        return dict(self._specs)

    def register(self, spec: MCPServerSpec) -> None:
        """Register a new server spec."""
        self._specs[spec.name] = spec

    def __iter__(self) -> Iterator[str]:
        """Iterate over server names."""
        return iter(self._specs)

    def __len__(self) -> int:
        """Return number of registered servers."""
        return len(self._specs)


# === Builtin Server Registry ===

MCP_REGISTRY: dict[str, MCPServerSpec] = {
    # === Ticket Systems ===
    "github": MCPServerSpec(
        name="github",
        description="GitHub API - issues, PRs, repos, actions",
        install_type="npm",
        package="@modelcontextprotocol/server-github",
        required_env=("GITHUB_TOKEN",),
        official=True,
        url="https://github.com/modelcontextprotocol/servers",
    ),
    "gitlab": MCPServerSpec(
        name="gitlab",
        description="GitLab API - issues, MRs, pipelines",
        install_type="pip",
        package="gitlab-mcp-server",
        required_env=("GITLAB_TOKEN", "GITLAB_URL"),
        python_native=True,
        url="https://github.com/LuisCusihuaman/gitlab-mcp-server",
    ),
    "jira": MCPServerSpec(
        name="jira",
        description="Jira/Confluence - issues, projects, pages",
        install_type="pip",
        package="mcp-atlassian",
        required_env=("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN"),
        python_native=True,
        url="https://github.com/sooperset/mcp-atlassian",
    ),
    "linear": MCPServerSpec(
        name="linear",
        description="Linear - issues, projects, cycles",
        install_type="remote",
        package="https://mcp.linear.app/mcp",
        required_env=(),  # OAuth flow
        official=True,
        url="https://linear.app/docs/mcp",
    ),
    "taiga": MCPServerSpec(
        name="taiga",
        description="Taiga - agile project management",
        install_type="pip",
        package="pytaiga-mcp",
        required_env=("TAIGA_API_URL", "TAIGA_USERNAME", "TAIGA_PASSWORD"),
        python_native=True,
        url="https://github.com/talhaorak/pytaiga-mcp",
    ),
    # === Development Tools ===
    "git": MCPServerSpec(
        name="git",
        description="Git operations - log, diff, blame, status",
        install_type="pip",
        package="mcp-server-git",
        required_env=(),
        default_args=("--repository", "."),
        python_native=True,
        official=True,
        url="https://pypi.org/project/mcp-server-git/",
    ),
    "filesystem": MCPServerSpec(
        name="filesystem",
        description="Secure file operations",
        install_type="npm",
        package="@modelcontextprotocol/server-filesystem",
        required_env=(),
        default_args=("/allowed/path",),
        official=True,
        url="https://github.com/modelcontextprotocol/servers",
    ),
    # === Search ===
    "brave-search": MCPServerSpec(
        name="brave-search",
        description="Web search via Brave API",
        install_type="npm",
        package="@anthropic/mcp-server-brave-search",
        required_env=("BRAVE_API_KEY",),
        official=True,
        url="https://github.com/anthropics/mcp-servers",
    ),
    "fetch": MCPServerSpec(
        name="fetch",
        description="Fetch and parse web content",
        install_type="pip",
        package="mcp-server-fetch",
        required_env=(),
        python_native=True,
        official=True,
        url="https://pypi.org/project/mcp-server-fetch/",
    ),
}


# === Registry Factory Functions ===


def get_default_registry() -> DefaultMCPRegistry:
    """Get a populated default registry instance.

    Returns:
        A registry containing all builtin server specs.
    """
    registry = DefaultMCPRegistry()
    for spec in MCP_REGISTRY.values():
        registry.register(spec)
    return registry


def get_servers_by_category(category: str) -> dict[str, MCPServerSpec]:
    """Get servers filtered by category.

    Args:
        category: One of "ticket", "development", "search".

    Returns:
        Dictionary of servers matching the category.
    """
    categories = {
        "ticket": ("github", "gitlab", "jira", "linear", "taiga"),
        "development": ("git", "filesystem"),
        "search": ("brave-search", "fetch"),
    }
    names = categories.get(category, ())
    return {name: MCP_REGISTRY[name] for name in names if name in MCP_REGISTRY}


def get_python_native_servers() -> dict[str, MCPServerSpec]:
    """Get all Python-native servers (no Node.js required).

    Returns:
        Dictionary of servers with python_native=True.
    """
    return {name: spec for name, spec in MCP_REGISTRY.items() if spec.python_native}


def get_official_servers() -> dict[str, MCPServerSpec]:
    """Get all official/maintained servers.

    Returns:
        Dictionary of servers with official=True.
    """
    return {name: spec for name, spec in MCP_REGISTRY.items() if spec.official}
