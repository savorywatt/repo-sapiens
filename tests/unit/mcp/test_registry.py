"""Unit tests for MCP registry and server specifications."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from repo_sapiens.mcp.registry import (
    DefaultMCPRegistry,
    MCP_REGISTRY,
    MCPServerSpec,
    get_default_registry,
    get_official_servers,
    get_python_native_servers,
    get_servers_by_category,
)


class TestMCPServerSpec:
    """Tests for the MCPServerSpec dataclass."""

    def test_spec_is_frozen(self) -> None:
        """MCPServerSpec instances should be immutable."""
        spec = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
        )

        with pytest.raises(FrozenInstanceError):
            spec.name = "modified"  # type: ignore[misc]

    def test_spec_has_slots(self) -> None:
        """MCPServerSpec should use slots for memory efficiency."""
        spec = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
        )

        # Slots-enabled classes don't have __dict__
        assert not hasattr(spec, "__dict__")

    def test_with_args_returns_new_spec(self) -> None:
        """with_args should return a new spec without modifying the original."""
        original = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
            default_args=("--old",),
        )

        modified = original.with_args(("--new", "--args"))

        assert original.default_args == ("--old",)
        assert modified.default_args == ("--new", "--args")
        assert original is not modified

    def test_spec_default_values(self) -> None:
        """MCPServerSpec should have sensible defaults."""
        spec = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
        )

        assert spec.required_env == ()
        assert spec.optional_env == ()
        assert spec.command is None
        assert spec.default_args == ()
        assert spec.python_native is False
        assert spec.official is False
        assert spec.url == ""


class TestMCPRegistry:
    """Tests for the MCP_REGISTRY constant."""

    def test_registry_has_expected_server_count(self) -> None:
        """MCP_REGISTRY should contain exactly 9 servers."""
        assert len(MCP_REGISTRY) == 9

    def test_registry_contains_expected_servers(self) -> None:
        """MCP_REGISTRY should contain all expected server names."""
        expected_servers = {
            "github",
            "gitlab",
            "jira",
            "linear",
            "taiga",
            "git",
            "filesystem",
            "brave-search",
            "fetch",
        }

        assert set(MCP_REGISTRY.keys()) == expected_servers

    def test_all_registry_entries_are_specs(self) -> None:
        """All registry entries should be MCPServerSpec instances."""
        for name, spec in MCP_REGISTRY.items():
            assert isinstance(spec, MCPServerSpec), f"{name} is not MCPServerSpec"
            assert spec.name == name, f"Spec name mismatch for {name}"


class TestGetPythonNativeServers:
    """Tests for the get_python_native_servers function."""

    def test_returns_only_python_servers(self) -> None:
        """get_python_native_servers should return only servers with python_native=True."""
        python_servers = get_python_native_servers()

        for name, spec in python_servers.items():
            assert spec.python_native is True, f"{name} is not Python-native"

    def test_returns_expected_python_servers(self) -> None:
        """get_python_native_servers should return the expected set of servers."""
        python_servers = get_python_native_servers()

        expected = {"gitlab", "jira", "taiga", "git", "fetch"}
        assert set(python_servers.keys()) == expected

    def test_returns_dict_of_specs(self) -> None:
        """get_python_native_servers should return a dictionary of MCPServerSpec."""
        python_servers = get_python_native_servers()

        assert isinstance(python_servers, dict)
        for spec in python_servers.values():
            assert isinstance(spec, MCPServerSpec)


class TestGetOfficialServers:
    """Tests for the get_official_servers function."""

    def test_returns_only_official_servers(self) -> None:
        """get_official_servers should return only servers with official=True."""
        official_servers = get_official_servers()

        for name, spec in official_servers.items():
            assert spec.official is True, f"{name} is not official"

    def test_returns_expected_official_servers(self) -> None:
        """get_official_servers should return the expected set of servers."""
        official_servers = get_official_servers()

        expected = {"github", "linear", "git", "filesystem", "brave-search", "fetch"}
        assert set(official_servers.keys()) == expected


class TestGetServersByCategory:
    """Tests for the get_servers_by_category function."""

    def test_ticket_category(self) -> None:
        """get_servers_by_category('ticket') should return ticket system servers."""
        servers = get_servers_by_category("ticket")

        expected = {"github", "gitlab", "jira", "linear", "taiga"}
        assert set(servers.keys()) == expected

    def test_development_category(self) -> None:
        """get_servers_by_category('development') should return dev tool servers."""
        servers = get_servers_by_category("development")

        expected = {"git", "filesystem"}
        assert set(servers.keys()) == expected

    def test_search_category(self) -> None:
        """get_servers_by_category('search') should return search servers."""
        servers = get_servers_by_category("search")

        expected = {"brave-search", "fetch"}
        assert set(servers.keys()) == expected

    def test_unknown_category_returns_empty(self) -> None:
        """get_servers_by_category with unknown category should return empty dict."""
        servers = get_servers_by_category("nonexistent")

        assert servers == {}


class TestDefaultMCPRegistry:
    """Tests for the DefaultMCPRegistry class."""

    def test_get_returns_none_for_unknown(self) -> None:
        """get() should return None for unregistered servers."""
        registry = DefaultMCPRegistry()

        assert registry.get("nonexistent") is None

    def test_register_and_get(self) -> None:
        """register() should add a spec retrievable via get()."""
        registry = DefaultMCPRegistry()
        spec = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
        )

        registry.register(spec)

        assert registry.get("test") is spec

    def test_list_all_returns_copy(self) -> None:
        """list_all() should return a copy of the internal dict."""
        registry = DefaultMCPRegistry()
        spec = MCPServerSpec(
            name="test",
            description="Test server",
            install_type="pip",
            package="test-package",
        )
        registry.register(spec)

        all_specs = registry.list_all()

        # Modifying the returned dict should not affect the registry
        all_specs["test2"] = spec
        assert registry.get("test2") is None

    def test_len_and_iter(self) -> None:
        """DefaultMCPRegistry should support len() and iteration."""
        registry = DefaultMCPRegistry()
        spec1 = MCPServerSpec(
            name="test1",
            description="Test 1",
            install_type="pip",
            package="pkg1",
        )
        spec2 = MCPServerSpec(
            name="test2",
            description="Test 2",
            install_type="npm",
            package="pkg2",
        )

        registry.register(spec1)
        registry.register(spec2)

        assert len(registry) == 2
        assert set(registry) == {"test1", "test2"}


class TestGetDefaultRegistry:
    """Tests for the get_default_registry factory function."""

    def test_returns_populated_registry(self) -> None:
        """get_default_registry should return a registry with all builtin servers."""
        registry = get_default_registry()

        assert len(registry) == len(MCP_REGISTRY)

    def test_contains_all_builtin_servers(self) -> None:
        """get_default_registry should contain all servers from MCP_REGISTRY."""
        registry = get_default_registry()

        for name in MCP_REGISTRY:
            spec = registry.get(name)
            assert spec is not None, f"Missing server: {name}"
            assert spec.name == name
