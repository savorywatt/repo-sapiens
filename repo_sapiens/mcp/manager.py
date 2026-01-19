"""MCP server lifecycle management.

This module provides the MCPManager class for installing, configuring,
and managing the lifecycle of MCP servers across different agent backends.

Example:
    Using MCPManager as an async context manager::

        from repo_sapiens.mcp import MCPManager, AgentType
        from repo_sapiens.config.mcp import MCPConfig, MCPServerConfig

        config = MCPConfig(servers=[
            MCPServerConfig(name="github"),
            MCPServerConfig(name="fetch"),
        ])

        async with MCPManager(config, Path.cwd()) as manager:
            await manager.setup(AgentType.OLLAMA)
            clients = manager.get_stdio_clients()
            # Use clients...
        # Servers automatically cleaned up
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog

from repo_sapiens.mcp.client import StdioMCPClient
from repo_sapiens.mcp.exceptions import (
    MCPConfigError,
    MCPInstallError,
    MCPServerError,
)
from repo_sapiens.mcp.registry import MCP_REGISTRY

if TYPE_CHECKING:
    from repo_sapiens.config.mcp import MCPConfig, MCPServerConfig

log = structlog.get_logger()


class AgentType(Enum):
    """Supported agent types for MCP configuration."""

    CLAUDE = "claude"
    GOOSE = "goose"
    OLLAMA = "ollama"
    REACT = "react"


class MCPManager:
    """Manages MCP server installation, configuration, and lifecycle.

    Supports async context manager for automatic cleanup:

        async with MCPManager(config, working_dir) as manager:
            await manager.setup(AgentType.OLLAMA)
            clients = manager.get_stdio_clients()
            # ... use clients ...
        # Servers automatically cleaned up

    Attributes:
        config: The MCP configuration.
        working_dir: Working directory for config files and server execution.
    """

    def __init__(self, config: MCPConfig, working_dir: Path) -> None:
        """Initialize the manager.

        Args:
            config: MCP configuration with server definitions.
            working_dir: Working directory for operations.
        """
        self.config = config
        self.working_dir = working_dir
        self._running_servers: dict[str, asyncio.subprocess.Process] = {}
        self._installed: set[str] = set()
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> MCPManager:
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context, cleaning up servers."""
        await self.teardown()

    # === Lifecycle ===

    async def setup(self, agent_type: AgentType) -> None:
        """Full setup: validate, install, configure, start.

        Args:
            agent_type: The type of agent to configure for.

        Raises:
            MCPConfigError: If configuration validation fails.
            MCPInstallError: If package installation fails.
            MCPServerError: If server startup fails.
        """
        if not self.config.enabled:
            return

        async with self._lock:
            self._validate_env()
            await self._install_servers()

            if agent_type == AgentType.CLAUDE:
                self._generate_claude_config()
            elif agent_type == AgentType.GOOSE:
                self._generate_goose_config()
            elif agent_type in (AgentType.OLLAMA, AgentType.REACT):
                await self._start_stdio_servers()

    async def teardown(self) -> None:
        """Stop all running servers and clean up.

        Uses process groups for reliable cleanup of server processes
        and their children.
        """
        async with self._lock:
            for name, process in list(self._running_servers.items()):
                log.info("stopping_mcp_server", name=name, pid=process.pid)
                try:
                    # Try graceful termination first
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        process.terminate()

                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        log.warning("mcp_server_kill", name=name, reason="timeout")
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except (ProcessLookupError, PermissionError):
                            process.kill()
                        await process.wait()

                except Exception as e:
                    log.error("mcp_server_cleanup_error", name=name, error=str(e))

            self._running_servers.clear()

    # === Validation ===

    def _validate_env(self) -> None:
        """Validate all required environment variables are set.

        Raises:
            MCPConfigError: If any required env vars are missing.
        """
        errors: list[str] = []

        for server_cfg in self.config.servers:
            if not server_cfg.enabled:
                continue

            spec = MCP_REGISTRY.get(server_cfg.name)
            if not spec:
                errors.append(f"Unknown MCP server: {server_cfg.name}")
                continue

            for env_var in spec.required_env:
                resolved = self._resolve_env(env_var, server_cfg.env_mapping)
                if not os.environ.get(resolved):
                    errors.append(
                        f"{server_cfg.name}: missing {env_var} (mapped to {resolved})"
                    )

        if errors:
            raise MCPConfigError("MCP configuration errors:\n" + "\n".join(errors))

    def _resolve_env(self, var: str, mapping: dict[str, str]) -> str:
        """Resolve env var name through mapping.

        Args:
            var: The variable name to resolve.
            mapping: Environment variable mapping from config.

        Returns:
            The resolved variable name.
        """
        mapped = mapping.get(var, var)
        # Strip ${} wrapper if present
        if mapped.startswith("${") and mapped.endswith("}"):
            return mapped[2:-1]
        return mapped

    # === Installation ===

    async def _install_servers(self) -> None:
        """Install MCP server packages.

        Raises:
            MCPInstallError: If installation fails.
        """
        for server_cfg in self.config.servers:
            if not server_cfg.enabled:
                continue

            spec = MCP_REGISTRY.get(server_cfg.name)
            if not spec or spec.install_type == "builtin":
                continue

            if spec.install_type == "pip":
                await self._pip_install(spec.package)
            elif spec.install_type == "npm":
                # npm packages are handled by npx at runtime
                pass
            elif spec.install_type == "remote":
                # Remote servers don't need installation
                pass

            self._installed.add(server_cfg.name)

    async def _pip_install(self, package: str) -> None:
        """Install a pip package if not already installed.

        Args:
            package: The package name to install.

        Raises:
            MCPInstallError: If installation fails.
        """
        # Check if already installed via uvx
        log.info("installing_mcp_package", package=package)
        result = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "install",
            package,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise MCPInstallError(package, stderr.decode())

    # === Config Generation ===

    def _generate_claude_config(self) -> Path:
        """Generate .claude.json for Claude Code.

        Returns:
            Path to the generated config file.
        """
        config: dict[str, Any] = {"mcpServers": {}}

        for server_cfg in self.config.servers:
            if not server_cfg.enabled:
                continue

            spec = MCP_REGISTRY.get(server_cfg.name)
            if not spec:
                continue

            # Build env dict with resolved values
            env: dict[str, str] = {}
            for var in spec.required_env + spec.optional_env:
                resolved = self._resolve_env(var, server_cfg.env_mapping)
                value = os.environ.get(resolved, "")
                if value:
                    env[var] = value

            # Build command based on install type
            args = server_cfg.args or list(spec.default_args)

            if spec.install_type == "npm":
                server_entry = {
                    "command": "npx",
                    "args": ["-y", spec.package] + args,
                    "env": env,
                }
            elif spec.install_type == "pip":
                server_entry = {
                    "command": "uvx",
                    "args": [spec.package] + args,
                    "env": env,
                }
            elif spec.install_type == "remote":
                server_entry = {
                    "command": "npx",
                    "args": ["-y", "mcp-remote", spec.package],
                }
            else:
                continue

            config["mcpServers"][server_cfg.name] = server_entry

        # Write config
        config_path = self.working_dir / ".claude.json"
        config_path.write_text(json.dumps(config, indent=2))
        log.info("generated_claude_config", path=str(config_path))
        return config_path

    def _generate_goose_config(self) -> Path:
        """Generate Goose toolkit configuration.

        Returns:
            Path to the generated config file.

        Note:
            Goose config format needs verification. This is a placeholder.
        """
        # Goose uses a different format - this is a placeholder
        config: dict[str, Any] = {"extensions": {}}

        for server_cfg in self.config.servers:
            if not server_cfg.enabled:
                continue

            spec = MCP_REGISTRY.get(server_cfg.name)
            if not spec:
                continue

            # Build env dict
            env: dict[str, str] = {}
            for var in spec.required_env + spec.optional_env:
                resolved = self._resolve_env(var, server_cfg.env_mapping)
                value = os.environ.get(resolved, "")
                if value:
                    env[var] = value

            args = server_cfg.args or list(spec.default_args)

            config["extensions"][server_cfg.name] = {
                "type": "mcp",
                "install_type": spec.install_type,
                "package": spec.package,
                "args": args,
                "env": env,
            }

        config_path = self.working_dir / "goose.yaml"
        # Would use YAML here, but keeping it simple
        config_path.write_text(json.dumps(config, indent=2))
        log.info("generated_goose_config", path=str(config_path))
        return config_path

    # === Stdio Server Management ===

    async def _start_stdio_servers(self) -> None:
        """Start MCP servers as subprocesses for builtin agent.

        Uses process groups (start_new_session=True) for reliable cleanup.

        Raises:
            MCPServerError: If server fails to start.
        """
        for server_cfg in self.config.servers:
            if not server_cfg.enabled:
                continue

            spec = MCP_REGISTRY.get(server_cfg.name)
            if not spec or spec.install_type in ("remote", "builtin"):
                continue

            # Build environment
            env = os.environ.copy()
            for var in spec.required_env:
                resolved = self._resolve_env(var, server_cfg.env_mapping)
                env[var] = os.environ.get(resolved, "")

            # Build command
            args = server_cfg.args or list(spec.default_args)
            if spec.install_type == "pip":
                cmd = ["uvx", spec.package] + args
            elif spec.install_type == "npm":
                cmd = ["npx", "-y", spec.package] + args
            else:
                continue

            log.info("starting_mcp_server", name=server_cfg.name, cmd=cmd)

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=str(self.working_dir),
                    start_new_session=True,
                )
                self._running_servers[server_cfg.name] = process

                # Wait briefly and check if process started successfully
                await asyncio.sleep(0.1)
                if process.returncode is not None:
                    stderr = await process.stderr.read() if process.stderr else b""
                    raise MCPServerError(
                        server_cfg.name,
                        f"Server exited immediately with code {process.returncode}: {stderr.decode()}",
                    )

            except FileNotFoundError:
                raise MCPServerError(server_cfg.name, f"Command not found: {cmd[0]}")
            except MCPServerError:
                raise
            except Exception as e:
                raise MCPServerError(server_cfg.name, str(e))

    def get_stdio_clients(self) -> dict[str, StdioMCPClient]:
        """Get stdio clients for running servers.

        Returns:
            Dictionary mapping server names to their clients.
        """
        clients: dict[str, StdioMCPClient] = {}
        for name, process in self._running_servers.items():
            clients[name] = StdioMCPClient(name, process)
        return clients

    @asynccontextmanager
    async def server(self, name: str) -> AsyncIterator[StdioMCPClient]:
        """Context manager for a single server.

        Convenient for one-off use when you need just one server's client.

        Args:
            name: The server name.

        Yields:
            The StdioMCPClient for the requested server.

        Raises:
            MCPServerError: If the server is not running.

        Example:
            async with manager.server("jira") as client:
                result = await client.call_tool("create_issue", {...})
        """
        clients = self.get_stdio_clients()
        if name not in clients:
            raise MCPServerError(name, "Server not running")
        yield clients[name]
