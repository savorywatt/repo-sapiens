"""Unit tests for MCP manager."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.config.mcp import MCPConfig, MCPServerConfig
from repo_sapiens.mcp.exceptions import MCPConfigError, MCPServerError
from repo_sapiens.mcp.manager import AgentType, MCPManager


def make_config(
    enabled: bool = True,
    servers: list[dict[str, Any]] | None = None,
) -> MCPConfig:
    """Create an MCPConfig for testing.

    Args:
        enabled: Whether MCP is enabled.
        servers: List of server config dicts.

    Returns:
        An MCPConfig instance.
    """
    if servers is None:
        servers = []

    return MCPConfig(
        enabled=enabled,
        servers=[MCPServerConfig(**s) for s in servers],
    )


class TestAgentType:
    """Tests for the AgentType enum."""

    def test_has_expected_values(self) -> None:
        """AgentType should have all expected agent types."""
        assert AgentType.CLAUDE.value == "claude"
        assert AgentType.GOOSE.value == "goose"
        assert AgentType.OLLAMA.value == "ollama"
        assert AgentType.REACT.value == "react"

    def test_all_values_are_unique(self) -> None:
        """All AgentType values should be unique."""
        values = [t.value for t in AgentType]
        assert len(values) == len(set(values))


class TestMCPManagerInit:
    """Tests for MCPManager initialization."""

    def test_stores_config_and_working_dir(self, tmp_path: Path) -> None:
        """MCPManager should store config and working directory."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        assert manager.config is config
        assert manager.working_dir == tmp_path

    def test_initializes_empty_running_servers(self, tmp_path: Path) -> None:
        """MCPManager should start with no running servers."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        assert manager._running_servers == {}

    def test_initializes_empty_installed_set(self, tmp_path: Path) -> None:
        """MCPManager should start with no installed servers."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        assert manager._installed == set()


class TestAsyncContextManager:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, tmp_path: Path) -> None:
        """__aenter__ should return the manager instance."""
        config = make_config(enabled=False)
        manager = MCPManager(config, tmp_path)

        async with manager as ctx:
            assert ctx is manager

    @pytest.mark.asyncio
    async def test_aexit_calls_teardown(self, tmp_path: Path) -> None:
        """__aexit__ should call teardown."""
        config = make_config(enabled=False)
        manager = MCPManager(config, tmp_path)
        manager.teardown = AsyncMock()

        async with manager:
            pass

        manager.teardown.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_teardown_on_exception(self, tmp_path: Path) -> None:
        """__aexit__ should call teardown even on exception."""
        config = make_config(enabled=False)
        manager = MCPManager(config, tmp_path)
        manager.teardown = AsyncMock()

        with pytest.raises(RuntimeError):
            async with manager:
                raise RuntimeError("test error")

        manager.teardown.assert_called_once()


class TestSetup:
    """Tests for the setup method."""

    @pytest.mark.asyncio
    async def test_does_nothing_when_disabled(self, tmp_path: Path) -> None:
        """setup should do nothing when MCP is disabled."""
        config = make_config(enabled=False)
        manager = MCPManager(config, tmp_path)

        # These should not be called
        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._generate_claude_config = MagicMock()

        await manager.setup(AgentType.CLAUDE)

        manager._validate_env.assert_not_called()
        manager._install_servers.assert_not_called()
        manager._generate_claude_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_validates_env_when_enabled(self, tmp_path: Path) -> None:
        """setup should validate environment when enabled."""
        config = make_config(enabled=True)
        manager = MCPManager(config, tmp_path)

        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._generate_claude_config = MagicMock()

        await manager.setup(AgentType.CLAUDE)

        manager._validate_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_claude_config_for_claude(self, tmp_path: Path) -> None:
        """setup should generate Claude config for AgentType.CLAUDE."""
        config = make_config(enabled=True)
        manager = MCPManager(config, tmp_path)

        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._generate_claude_config = MagicMock(return_value=tmp_path / ".claude.json")

        await manager.setup(AgentType.CLAUDE)

        manager._generate_claude_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_goose_config_for_goose(self, tmp_path: Path) -> None:
        """setup should generate Goose config for AgentType.GOOSE."""
        config = make_config(enabled=True)
        manager = MCPManager(config, tmp_path)

        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._generate_goose_config = MagicMock(return_value=tmp_path / "goose.yaml")

        await manager.setup(AgentType.GOOSE)

        manager._generate_goose_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_starts_stdio_servers_for_ollama(self, tmp_path: Path) -> None:
        """setup should start stdio servers for AgentType.OLLAMA."""
        config = make_config(enabled=True)
        manager = MCPManager(config, tmp_path)

        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._start_stdio_servers = AsyncMock()

        await manager.setup(AgentType.OLLAMA)

        manager._start_stdio_servers.assert_called_once()

    @pytest.mark.asyncio
    async def test_starts_stdio_servers_for_react(self, tmp_path: Path) -> None:
        """setup should start stdio servers for AgentType.REACT."""
        config = make_config(enabled=True)
        manager = MCPManager(config, tmp_path)

        manager._validate_env = MagicMock()
        manager._install_servers = AsyncMock()
        manager._start_stdio_servers = AsyncMock()

        await manager.setup(AgentType.REACT)

        manager._start_stdio_servers.assert_called_once()


class TestValidateEnv:
    """Tests for environment validation."""

    def test_raises_for_unknown_server(self, tmp_path: Path) -> None:
        """_validate_env should raise for unknown server names."""
        config = make_config(
            enabled=True,
            servers=[{"name": "nonexistent-server"}],
        )
        manager = MCPManager(config, tmp_path)

        with pytest.raises(MCPConfigError) as exc_info:
            manager._validate_env()

        assert "Unknown MCP server" in str(exc_info.value)
        assert "nonexistent-server" in str(exc_info.value)

    def test_raises_for_missing_required_env(self, tmp_path: Path) -> None:
        """_validate_env should raise when required env vars are missing."""
        config = make_config(
            enabled=True,
            servers=[{"name": "github"}],  # requires GITHUB_PERSONAL_ACCESS_TOKEN
        )
        manager = MCPManager(config, tmp_path)

        # Ensure the var is not set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MCPConfigError) as exc_info:
                manager._validate_env()

            assert "missing" in str(exc_info.value)

    def test_skips_disabled_servers(self, tmp_path: Path) -> None:
        """_validate_env should skip disabled servers."""
        config = make_config(
            enabled=True,
            servers=[{"name": "github", "enabled": False}],
        )
        manager = MCPManager(config, tmp_path)

        # Should not raise even though GITHUB_PERSONAL_ACCESS_TOKEN is missing
        manager._validate_env()

    def test_resolves_env_mapping(self, tmp_path: Path) -> None:
        """_validate_env should resolve env var names through mapping."""
        config = make_config(
            enabled=True,
            servers=[
                {
                    "name": "github",
                    "env_mapping": {"GITHUB_TOKEN": "MY_TOKEN"},
                }
            ],
        )
        manager = MCPManager(config, tmp_path)

        with patch.dict(os.environ, {"MY_TOKEN": "secret"}, clear=True):
            # Should not raise because MY_TOKEN is set
            manager._validate_env()


class TestResolveEnv:
    """Tests for the _resolve_env helper method."""

    def test_returns_var_when_no_mapping(self, tmp_path: Path) -> None:
        """_resolve_env should return original var when not mapped."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        result = manager._resolve_env("MY_VAR", {})

        assert result == "MY_VAR"

    def test_returns_mapped_value(self, tmp_path: Path) -> None:
        """_resolve_env should return mapped value when present."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        result = manager._resolve_env("MY_VAR", {"MY_VAR": "DIFFERENT_VAR"})

        assert result == "DIFFERENT_VAR"

    def test_strips_dollar_brace_syntax(self, tmp_path: Path) -> None:
        """_resolve_env should strip ${} wrapper from mapped values."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        result = manager._resolve_env("MY_VAR", {"MY_VAR": "${WRAPPED_VAR}"})

        assert result == "WRAPPED_VAR"


class TestGenerateClaudeConfig:
    """Tests for Claude config generation."""

    def test_creates_claude_json_file(self, tmp_path: Path) -> None:
        """_generate_claude_config should create .claude.json file."""
        config = make_config(
            enabled=True,
            servers=[{"name": "fetch"}],
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_claude_config()

        assert path == tmp_path / ".claude.json"
        assert path.exists()

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """_generate_claude_config should write valid JSON."""
        config = make_config(
            enabled=True,
            servers=[{"name": "fetch"}],
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_claude_config()

        content = json.loads(path.read_text())
        assert "mcpServers" in content

    def test_includes_enabled_servers(self, tmp_path: Path) -> None:
        """_generate_claude_config should include enabled servers."""
        config = make_config(
            enabled=True,
            servers=[
                {"name": "fetch", "enabled": True},
                {"name": "git", "enabled": False},
            ],
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_claude_config()

        content = json.loads(path.read_text())
        assert "fetch" in content["mcpServers"]
        assert "git" not in content["mcpServers"]

    def test_pip_packages_use_uvx(self, tmp_path: Path) -> None:
        """_generate_claude_config should use uvx for pip packages."""
        config = make_config(
            enabled=True,
            servers=[{"name": "fetch"}],  # fetch is a pip package
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_claude_config()

        content = json.loads(path.read_text())
        assert content["mcpServers"]["fetch"]["command"] == "uvx"

    def test_npm_packages_use_npx(self, tmp_path: Path) -> None:
        """_generate_claude_config should use npx for npm packages."""
        config = make_config(
            enabled=True,
            servers=[{"name": "brave-search"}],  # brave-search is npm
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_claude_config()

        content = json.loads(path.read_text())
        assert content["mcpServers"]["brave-search"]["command"] == "npx"
        assert "-y" in content["mcpServers"]["brave-search"]["args"]


class TestGenerateGooseConfig:
    """Tests for Goose config generation."""

    def test_creates_goose_yaml_file(self, tmp_path: Path) -> None:
        """_generate_goose_config should create goose.yaml file."""
        config = make_config(
            enabled=True,
            servers=[{"name": "fetch"}],
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_goose_config()

        assert path == tmp_path / "goose.yaml"
        assert path.exists()

    def test_includes_enabled_servers(self, tmp_path: Path) -> None:
        """_generate_goose_config should include enabled servers."""
        config = make_config(
            enabled=True,
            servers=[
                {"name": "fetch", "enabled": True},
                {"name": "git", "enabled": False},
            ],
        )
        manager = MCPManager(config, tmp_path)

        path = manager._generate_goose_config()

        content = json.loads(path.read_text())
        assert "fetch" in content["extensions"]
        assert "git" not in content["extensions"]


class TestGetStdioClients:
    """Tests for the get_stdio_clients method."""

    def test_returns_empty_dict_when_no_servers(self, tmp_path: Path) -> None:
        """get_stdio_clients should return empty dict when no servers running."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        clients = manager.get_stdio_clients()

        assert clients == {}

    def test_creates_clients_for_running_servers(self, tmp_path: Path) -> None:
        """get_stdio_clients should create StdioMCPClient for each server."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        # Simulate a running server
        mock_process = MagicMock(spec=asyncio.subprocess.Process)
        manager._running_servers["test-server"] = mock_process

        clients = manager.get_stdio_clients()

        assert "test-server" in clients
        assert clients["test-server"].name == "test-server"


class TestServerContextManager:
    """Tests for the server context manager."""

    @pytest.mark.asyncio
    async def test_raises_when_server_not_running(self, tmp_path: Path) -> None:
        """server() should raise MCPServerError when server not running."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        with pytest.raises(MCPServerError) as exc_info:
            async with manager.server("missing-server"):
                pass

        assert "not running" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_yields_client_for_running_server(self, tmp_path: Path) -> None:
        """server() should yield StdioMCPClient for running server."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        # Simulate a running server
        mock_process = MagicMock(spec=asyncio.subprocess.Process)
        manager._running_servers["test-server"] = mock_process

        async with manager.server("test-server") as client:
            assert client.name == "test-server"


class TestTeardown:
    """Tests for the teardown method."""

    @pytest.mark.asyncio
    async def test_clears_running_servers(self, tmp_path: Path) -> None:
        """teardown should clear the running servers dict."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        # Simulate running servers
        mock_process = MagicMock(spec=asyncio.subprocess.Process)
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        manager._running_servers["test"] = mock_process

        with patch("os.killpg"):
            with patch("os.getpgid", return_value=12345):
                await manager.teardown()

        assert manager._running_servers == {}

    @pytest.mark.asyncio
    async def test_terminates_processes(self, tmp_path: Path) -> None:
        """teardown should terminate running processes."""
        config = make_config()
        manager = MCPManager(config, tmp_path)

        # Simulate running server
        mock_process = MagicMock(spec=asyncio.subprocess.Process)
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        manager._running_servers["test"] = mock_process

        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=12345):
                await manager.teardown()

        mock_killpg.assert_called()
