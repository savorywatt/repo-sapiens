"""Tests for repo_sapiens/cli/health.py."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from repo_sapiens.cli.health import (
    EXIT_AGENT_PROVIDER_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_CREDENTIAL_ERROR,
    EXIT_GIT_PROVIDER_ERROR,
    EXIT_SUCCESS,
    _print_check,
    health_check,
)


class TestExitCodes:
    """Tests for exit code constants."""

    def test_exit_codes_defined(self):
        """Should have all exit codes defined."""
        assert EXIT_SUCCESS == 0
        assert EXIT_CONFIG_ERROR == 1
        assert EXIT_CREDENTIAL_ERROR == 2
        assert EXIT_GIT_PROVIDER_ERROR == 3
        assert EXIT_AGENT_PROVIDER_ERROR == 4


class TestPrintCheck:
    """Tests for _print_check function."""

    def test_print_check_success(self, capsys):
        """Should print success check."""
        _print_check("Test check", True)

        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "Test check" in captured.out

    def test_print_check_failure(self, capsys):
        """Should print failure check."""
        _print_check("Test check", False)

        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
        assert "Test check" in captured.out

    def test_print_check_with_detail(self, capsys):
        """Should print detail message."""
        _print_check("Test check", True, "Additional detail")

        captured = capsys.readouterr()
        assert "Additional detail" in captured.out


class TestHealthCheckCommand:
    """Tests for health_check CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_missing_config_file(self, runner, tmp_path):
        """Should fail when config file doesn't exist."""
        config_path = tmp_path / "nonexistent.yaml"

        result = runner.invoke(health_check, ["--config", str(config_path)])

        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "File not found" in result.output

    def test_invalid_yaml_config(self, runner, tmp_path):
        """Should fail for invalid YAML."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        result = runner.invoke(health_check, ["--config", str(config_file)])

        assert result.exit_code == EXIT_CONFIG_ERROR

    def test_valid_config_skip_connectivity(self, runner, tmp_path):
        """Should pass with valid config and skip connectivity."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
git_provider:
  provider_type: gitea
  base_url: https://gitea.example.com
  api_token: test-token-123

repository:
  owner: test-owner
  name: test-repo
  default_branch: main

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4.5
  local_mode: true

workflow:
  state_directory: /tmp/state
"""
        )

        # Mock the CLI check
        with patch("shutil.which", return_value="/usr/bin/claude"):
            result = runner.invoke(health_check, ["--config", str(config_file), "--skip-connectivity"])

        # Should complete without network checks
        assert "repo-sapiens Health Check" in result.output
        assert "Configuration:" in result.output

    def test_verbose_flag(self, runner, tmp_path):
        """Should show verbose output."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
git_provider:
  provider_type: github
  base_url: https://api.github.com
  api_token: ghp_testtoken123

repository:
  owner: test-owner
  name: test-repo
  default_branch: main

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4.5
  local_mode: true

workflow:
  state_directory: /tmp/state
"""
        )

        with patch("shutil.which", return_value="/usr/bin/claude"):
            result = runner.invoke(health_check, ["--config", str(config_file), "--skip-connectivity", "-v"])

        # Verbose should include more details
        assert "repo-sapiens Health Check" in result.output

    def test_help_text(self, runner):
        """Should display help text."""
        result = runner.invoke(health_check, ["--help"])

        assert result.exit_code == 0
        assert "Validate configuration" in result.output
        assert "--config" in result.output
        assert "--verbose" in result.output
        assert "--skip-connectivity" in result.output
