"""Unit tests for MCP exception hierarchy."""

from __future__ import annotations

import pytest

from repo_sapiens.mcp.exceptions import (
    MCPConfigError,
    MCPError,
    MCPInstallError,
    MCPProtocolError,
    MCPServerError,
    MCPTimeoutError,
)


class TestExceptionHierarchy:
    """Tests for the exception class hierarchy."""

    def test_mcp_error_is_base_exception(self) -> None:
        """MCPError should be the base for all MCP exceptions."""
        assert issubclass(MCPConfigError, MCPError)
        assert issubclass(MCPInstallError, MCPError)
        assert issubclass(MCPServerError, MCPError)

    def test_server_error_subclasses(self) -> None:
        """MCPTimeoutError and MCPProtocolError should inherit from MCPServerError."""
        assert issubclass(MCPTimeoutError, MCPServerError)
        assert issubclass(MCPProtocolError, MCPServerError)

    def test_all_inherit_from_exception(self) -> None:
        """All MCP exceptions should inherit from Exception."""
        for exc_class in [
            MCPError,
            MCPConfigError,
            MCPInstallError,
            MCPServerError,
            MCPTimeoutError,
            MCPProtocolError,
        ]:
            assert issubclass(exc_class, Exception)


class TestMCPError:
    """Tests for the base MCPError class."""

    def test_can_be_raised(self) -> None:
        """MCPError should be raisable with a message."""
        with pytest.raises(MCPError) as exc_info:
            raise MCPError("test message")

        assert str(exc_info.value) == "test message"

    def test_can_be_caught_as_exception(self) -> None:
        """MCPError should be catchable as a generic Exception."""
        try:
            raise MCPError("test")
        except Exception as e:
            assert isinstance(e, MCPError)


class TestMCPConfigError:
    """Tests for the MCPConfigError class."""

    def test_can_be_raised(self) -> None:
        """MCPConfigError should be raisable with a message."""
        with pytest.raises(MCPConfigError) as exc_info:
            raise MCPConfigError("invalid config")

        assert "invalid config" in str(exc_info.value)

    def test_can_be_caught_as_mcp_error(self) -> None:
        """MCPConfigError should be catchable as MCPError."""
        try:
            raise MCPConfigError("config error")
        except MCPError as e:
            assert isinstance(e, MCPConfigError)


class TestMCPInstallError:
    """Tests for the MCPInstallError class."""

    def test_stores_package_name(self) -> None:
        """MCPInstallError should store the package name."""
        error = MCPInstallError("mcp-jira", "network timeout")

        assert error.package == "mcp-jira"

    def test_formats_message(self) -> None:
        """MCPInstallError should format package and message."""
        with pytest.raises(MCPInstallError) as exc_info:
            raise MCPInstallError("mcp-jira", "permission denied")

        message = str(exc_info.value)
        assert "mcp-jira" in message
        assert "permission denied" in message

    def test_can_be_caught_as_mcp_error(self) -> None:
        """MCPInstallError should be catchable as MCPError."""
        try:
            raise MCPInstallError("pkg", "error")
        except MCPError as e:
            assert isinstance(e, MCPInstallError)


class TestMCPServerError:
    """Tests for the MCPServerError class."""

    def test_stores_server_name(self) -> None:
        """MCPServerError should store the server name."""
        error = MCPServerError("jira-server", "connection refused")

        assert error.server_name == "jira-server"

    def test_formats_message(self) -> None:
        """MCPServerError should format server name and message."""
        with pytest.raises(MCPServerError) as exc_info:
            raise MCPServerError("github", "rate limit exceeded")

        message = str(exc_info.value)
        assert "github" in message
        assert "rate limit exceeded" in message

    def test_message_format(self) -> None:
        """MCPServerError should use consistent message format."""
        error = MCPServerError("test-server", "error message")

        # Should follow format: "MCP server 'name': message"
        assert "MCP server 'test-server':" in str(error)
        assert "error message" in str(error)


class TestMCPTimeoutError:
    """Tests for the MCPTimeoutError class."""

    def test_inherits_server_name(self) -> None:
        """MCPTimeoutError should inherit server_name from MCPServerError."""
        error = MCPTimeoutError("slow-server", "tools/call timed out after 30.0s")

        assert error.server_name == "slow-server"

    def test_can_be_caught_as_server_error(self) -> None:
        """MCPTimeoutError should be catchable as MCPServerError."""
        try:
            raise MCPTimeoutError("server", "timeout")
        except MCPServerError as e:
            assert isinstance(e, MCPTimeoutError)

    def test_can_be_caught_as_mcp_error(self) -> None:
        """MCPTimeoutError should be catchable as MCPError."""
        try:
            raise MCPTimeoutError("server", "timeout")
        except MCPError as e:
            assert isinstance(e, MCPTimeoutError)


class TestMCPProtocolError:
    """Tests for the MCPProtocolError class."""

    def test_inherits_server_name(self) -> None:
        """MCPProtocolError should inherit server_name from MCPServerError."""
        error = MCPProtocolError("broken-server", "Invalid JSON in response")

        assert error.server_name == "broken-server"

    def test_can_be_caught_as_server_error(self) -> None:
        """MCPProtocolError should be catchable as MCPServerError."""
        try:
            raise MCPProtocolError("server", "protocol error")
        except MCPServerError as e:
            assert isinstance(e, MCPProtocolError)

    def test_can_be_caught_as_mcp_error(self) -> None:
        """MCPProtocolError should be catchable as MCPError."""
        try:
            raise MCPProtocolError("server", "protocol error")
        except MCPError as e:
            assert isinstance(e, MCPProtocolError)


class TestExceptionChaining:
    """Tests for exception chaining support."""

    def test_mcp_error_can_be_chained(self) -> None:
        """MCPError should support exception chaining."""
        original = ValueError("original error")

        try:
            try:
                raise original
            except ValueError as e:
                raise MCPError("wrapped error") from e
        except MCPError as e:
            assert e.__cause__ is original

    def test_install_error_can_be_chained(self) -> None:
        """MCPInstallError should support exception chaining."""
        original = OSError("disk full")

        try:
            try:
                raise original
            except OSError as e:
                raise MCPInstallError("package", "install failed") from e
        except MCPInstallError as e:
            assert e.__cause__ is original

    def test_server_error_can_be_chained(self) -> None:
        """MCPServerError should support exception chaining."""
        original = ConnectionError("connection reset")

        try:
            try:
                raise original
            except ConnectionError as e:
                raise MCPServerError("server", "communication error") from e
        except MCPServerError as e:
            assert e.__cause__ is original
