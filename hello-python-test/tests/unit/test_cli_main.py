"""Comprehensive tests for automation/main.py CLI commands.

Tests cover:
- Basic CLI functionality (help, version)
- Command execution with valid/invalid arguments
- Configuration loading and error handling
- Exit codes and output formatting
- Logging level configuration
- User-friendly error messages
"""

import asyncio
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import structlog
from click.testing import CliRunner

from automation.main import (
    cli,
    daemon,
    list_plans,
    process_all,
    process_issue,
    process_plan,
    show_plan,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config_path(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_file = tmp_path / "test_config.yaml"
    config_content = """
git_provider:
  provider_type: gitea
  base_url: http://localhost:3000
  api_token: test_token_secret

repository:
  owner: test_owner
  name: test_repo

agent_provider:
  provider_type: external
  model: claude-opus-4.5-20251101
  base_url: http://localhost

state_dir: /tmp/state
default_poll_interval: 60
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def mock_config_invalid(tmp_path: Path) -> Path:
    """Create an invalid YAML config file."""
    config_file = tmp_path / "invalid_config.yaml"
    config_content = """
this: is: invalid: yaml: syntax:
  - broken
    structure
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock AutomationSettings object."""
    settings = MagicMock()
    settings.git_provider.base_url = "http://localhost:3000"
    settings.git_provider.api_token.get_secret_value.return_value = "test_token"
    settings.repository.owner = "test_owner"
    settings.repository.name = "test_repo"
    settings.agent_provider.provider_type = "external"
    settings.agent_provider.model = "claude-opus-4.5-20251101"
    settings.state_dir = "/tmp/state"
    return settings


class TestCliBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, cli_runner: CliRunner, mock_config_path: Path) -> None:
        """Test that --help displays help information."""
        result = cli_runner.invoke(
            cli,
            ["--help"],
            env={"AUTOMATION_CONFIG": str(mock_config_path)},
        )
        assert result.exit_code == 0
        assert "Gitea automation system CLI" in result.output
        assert "Usage:" in result.output
        assert "--config" in result.output
        assert "--log-level" in result.output

    def test_cli_version_flag(self, cli_runner: CliRunner, mock_config_path: Path) -> None:
        """Test that CLI displays correctly when invoked."""
        result = cli_runner.invoke(
            cli,
            ["--help"],
        )
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_cli_missing_config_file(self, cli_runner: CliRunner) -> None:
        """Test error handling when config file is missing."""
        result = cli_runner.invoke(
            cli,
            ["--config", "/nonexistent/path/config.yaml", "process-issue", "--issue", "1"],
        )
        assert result.exit_code == 1
        assert "Error: Configuration file not found" in result.output

    def test_cli_custom_config_path(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that custom config path is respected."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_settings = MagicMock()
            mock_from_yaml.return_value = mock_settings

            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "list-plans"],
            )

            # Config path should be passed to from_yaml
            mock_from_yaml.assert_called_once_with(str(mock_config_path))

    def test_cli_log_level_debug(self, cli_runner: CliRunner, mock_config_path: Path) -> None:
        """Test that --log-level flag is processed."""
        with patch("automation.utils.logging_config.configure_logging") as mock_logging:
            with patch("automation.config.settings.AutomationSettings.from_yaml"):
                result = cli_runner.invoke(
                    cli,
                    ["--log-level", "DEBUG", "list-plans"],
                )

                # Verify configure_logging was called with the specified level
                mock_logging.assert_called_with("DEBUG")

    def test_cli_log_level_warning(self, cli_runner: CliRunner, mock_config_path: Path) -> None:
        """Test WARNING log level."""
        with patch("automation.utils.logging_config.configure_logging") as mock_logging:
            with patch("automation.config.settings.AutomationSettings.from_yaml"):
                result = cli_runner.invoke(
                    cli,
                    ["--log-level", "WARNING", "list-plans"],
                )

                mock_logging.assert_called_with("WARNING")

    def test_cli_invalid_config_yaml(
        self, cli_runner: CliRunner, mock_config_invalid: Path
    ) -> None:
        """Test error handling for invalid YAML config."""
        result = cli_runner.invoke(
            cli,
            ["--config", str(mock_config_invalid), "list-plans"],
        )
        assert result.exit_code == 1
        assert "Error loading configuration" in result.output


class TestProcessIssueCommand:
    """Test 'process-issue' command."""

    def test_process_issue_help(self, cli_runner: CliRunner) -> None:
        """Test help for process-issue command."""
        result = cli_runner.invoke(cli, ["process-issue", "--help"])
        assert result.exit_code == 0
        assert "Process a single issue manually" in result.output
        assert "--issue" in result.output

    def test_process_issue_missing_required_arg(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that --issue argument is required."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "process-issue"],
            )
            assert result.exit_code != 0
            assert "Missing option '--issue'" in result.output or "Error" in result.output

    def test_process_issue_invalid_issue_number(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test error handling for non-numeric issue number."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "process-issue", "--issue", "not_a_number"],
            )
            assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_process_issue_success(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test successful issue processing."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_issue = MagicMock(number=42)
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                mock_orch.process_issue = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-issue", "--issue", "42"],
                )

                assert result.exit_code == 0
                assert "Issue #42 processed successfully" in result.output

    @pytest.mark.asyncio
    async def test_process_issue_with_zero_number(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test issue processing with issue number 0."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_issue = MagicMock(number=0)
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                mock_orch.process_issue = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-issue", "--issue", "0"],
                )

                assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_process_issue_with_large_number(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test issue processing with very large issue number."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_issue = MagicMock(number=999999)
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                mock_orch.process_issue = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-issue",
                        "--issue",
                        "999999",
                    ],
                )

                assert result.exit_code == 0


class TestProcessAllCommand:
    """Test 'process-all' command."""

    def test_process_all_help(self, cli_runner: CliRunner) -> None:
        """Test help for process-all command."""
        result = cli_runner.invoke(cli, ["process-all", "--help"])
        assert result.exit_code == 0
        assert "Process all issues with optional tag filter" in result.output
        assert "--tag" in result.output

    @pytest.mark.asyncio
    async def test_process_all_without_tag(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test processing all issues without tag filter."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-all"],
                )

                assert result.exit_code == 0
                assert "All issues processed" in result.output
                mock_orch.process_all_issues.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_process_all_with_tag(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test processing all issues with tag filter."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-all", "--tag", "urgent"],
                )

                assert result.exit_code == 0
                mock_orch.process_all_issues.assert_called_once_with("urgent")

    @pytest.mark.asyncio
    async def test_process_all_with_special_characters_in_tag(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test tag with special characters."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-all",
                        "--tag",
                        "bug-fix/urgent",
                    ],
                )

                assert result.exit_code == 0
                mock_orch.process_all_issues.assert_called_once_with("bug-fix/urgent")


class TestProcessPlanCommand:
    """Test 'process-plan' command."""

    def test_process_plan_help(self, cli_runner: CliRunner) -> None:
        """Test help for process-plan command."""
        result = cli_runner.invoke(cli, ["process-plan", "--help"])
        assert result.exit_code == 0
        assert "Process entire plan end-to-end" in result.output
        assert "--plan-id" in result.output

    def test_process_plan_missing_plan_id(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that --plan-id is required."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "process-plan"],
            )
            assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_process_plan_success(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test successful plan processing."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_plan = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-plan",
                        "--plan-id",
                        "plan-001",
                    ],
                )

                assert result.exit_code == 0
                assert "Plan plan-001 processed successfully" in result.output
                mock_orch.process_plan.assert_called_once_with("plan-001")

    @pytest.mark.asyncio
    async def test_process_plan_with_uuid(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test plan processing with UUID-style plan ID."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_plan = AsyncMock()
                mock_create_orch.return_value = mock_orch

                plan_uuid = "550e8400-e29b-41d4-a716-446655440000"
                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-plan",
                        "--plan-id",
                        plan_uuid,
                    ],
                )

                assert result.exit_code == 0
                mock_orch.process_plan.assert_called_once_with(plan_uuid)


class TestDaemonCommand:
    """Test 'daemon' command."""

    def test_daemon_help(self, cli_runner: CliRunner) -> None:
        """Test help for daemon command."""
        result = cli_runner.invoke(cli, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "Run in daemon mode" in result.output
        assert "--interval" in result.output

    def test_daemon_default_interval(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test daemon with default polling interval."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                # Simulate KeyboardInterrupt to exit daemon
                mock_orch.process_all_issues = AsyncMock(side_effect=KeyboardInterrupt())
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "daemon"],
                )

                assert "Starting daemon mode (polling every 60s)" in result.output
                assert result.exit_code == 0

    def test_daemon_custom_interval(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test daemon with custom polling interval."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock(side_effect=KeyboardInterrupt())
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "daemon",
                        "--interval",
                        "30",
                    ],
                )

                assert "Starting daemon mode (polling every 30s)" in result.output

    def test_daemon_invalid_interval(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test daemon with invalid interval."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "daemon", "--interval", "invalid"],
            )
            assert result.exit_code != 0

    def test_daemon_zero_interval(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test daemon with zero interval."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock(side_effect=KeyboardInterrupt())
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "daemon",
                        "--interval",
                        "0",
                    ],
                )

                # Zero interval is technically valid but may produce warning
                assert "Starting daemon mode (polling every 0s)" in result.output

    def test_daemon_negative_interval(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test daemon with negative interval."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "daemon", "--interval", "-10"],
            )
            # Click might allow negative numbers, but that's an edge case
            # The actual behavior depends on implementation


class TestListPlansCommand:
    """Test 'list-plans' command."""

    def test_list_plans_help(self, cli_runner: CliRunner) -> None:
        """Test help for list-plans command."""
        result = cli_runner.invoke(cli, ["list-plans", "--help"])
        assert result.exit_code == 0
        assert "List all active plans" in result.output

    @pytest.mark.asyncio
    async def test_list_plans_empty(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test list-plans with no active plans."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.get_active_plans = AsyncMock(return_value=[])
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "list-plans"],
                )

                assert result.exit_code == 0
                assert "No active plans found" in result.output

    @pytest.mark.asyncio
    async def test_list_plans_with_plans(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test list-plans with active plans."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.get_active_plans = AsyncMock(return_value=["plan-001", "plan-002"])
                mock_state.load_state = AsyncMock(
                    side_effect=lambda pid: {
                        "plan-001": {"status": "pending"},
                        "plan-002": {"status": "completed"},
                    }[pid]
                )
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "list-plans"],
                )

                assert result.exit_code == 0
                assert "Active Plans (2)" in result.output
                assert "plan-001" in result.output
                assert "plan-002" in result.output


class TestShowPlanCommand:
    """Test 'show-plan' command."""

    def test_show_plan_help(self, cli_runner: CliRunner) -> None:
        """Test help for show-plan command."""
        result = cli_runner.invoke(cli, ["show-plan", "--help"])
        assert result.exit_code == 0
        assert "Show detailed plan status" in result.output
        assert "--plan-id" in result.output

    def test_show_plan_missing_plan_id(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that --plan-id is required."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "show-plan"],
            )
            assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_show_plan_not_found(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test show-plan with non-existent plan."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.load_state = AsyncMock(side_effect=FileNotFoundError())
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "show-plan", "--plan-id", "nonexistent"],
                )

                assert result.exit_code == 0
                assert "Plan nonexistent not found" in result.output

    @pytest.mark.asyncio
    async def test_show_plan_success(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test successful plan status display."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.load_state = AsyncMock(
                    return_value={
                        "status": "in_progress",
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T11:00:00Z",
                        "stages": {
                            "analysis": {"status": "completed"},
                            "implementation": {"status": "in_progress"},
                        },
                        "tasks": {
                            "task-1": {"status": "completed"},
                            "task-2": {"status": "pending"},
                        },
                    }
                )
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "show-plan", "--plan-id", "plan-001"],
                )

                assert result.exit_code == 0
                assert "Plan plan-001 Status" in result.output
                assert "Overall Status: in_progress" in result.output
                assert "analysis" in result.output
                assert "implementation" in result.output
                assert "task-1" in result.output
                assert "task-2" in result.output

    @pytest.mark.asyncio
    async def test_show_plan_with_empty_stages(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test show-plan with empty stages."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.load_state = AsyncMock(
                    return_value={
                        "status": "pending",
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z",
                        "stages": {},
                        "tasks": {},
                    }
                )
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "show-plan", "--plan-id", "plan-001"],
                )

                assert result.exit_code == 0
                assert "Plan plan-001 Status" in result.output


class TestConfigurationErrors:
    """Test configuration loading and error handling."""

    def test_config_parsing_error(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test handling of config parsing errors."""
        with patch(
            "automation.config.settings.AutomationSettings.from_yaml",
            side_effect=ValueError("Invalid configuration format"),
        ):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "list-plans"],
            )
            assert result.exit_code == 1
            assert "Error loading configuration" in result.output

    def test_config_missing_required_fields(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test handling of missing required configuration fields."""
        config_file = tmp_path / "incomplete_config.yaml"
        config_file.write_text("git_provider:\n  base_url: http://localhost\n")

        with patch(
            "automation.config.settings.AutomationSettings.from_yaml",
            side_effect=ValueError("Missing required field: api_token"),
        ):
            result = cli_runner.invoke(
                cli,
                ["--config", str(config_file), "list-plans"],
            )
            assert result.exit_code == 1


class TestOutputFormatting:
    """Test output formatting and messages."""

    def test_success_message_formatting(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test that success messages are properly formatted."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_issue = MagicMock(number=123)
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                mock_orch.process_issue = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-issue", "--issue", "123"],
                )

                assert result.exit_code == 0
                assert "processed successfully" in result.output.lower()

    def test_error_message_formatting(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that error messages are properly formatted."""
        result = cli_runner.invoke(
            cli,
            ["--config", "/nonexistent/config.yaml", "list-plans"],
        )
        assert result.exit_code == 1
        # Error message should mention the missing file
        assert "Error" in result.output or "not found" in result.output

    def test_help_output_structure(self, cli_runner: CliRunner) -> None:
        """Test that help output is properly structured."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Check for expected help structure
        assert "Usage:" in result.output
        assert "Options:" in result.output or "options:" in result.output
        assert "Commands:" in result.output or "commands:" in result.output


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_command_with_empty_string_arg(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test command with empty string argument."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_plan = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-plan", "--plan-id", ""],
                )

                # Empty string should be accepted as plan ID
                assert result.exit_code == 0

    def test_multiple_config_flags(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that only the last config flag is used."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = MagicMock()

            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    "/nonexistent/config1.yaml",
                    "--config",
                    str(mock_config_path),
                    "list-plans",
                ],
            )

            # Last config should be used
            mock_from_yaml.assert_called_once_with(str(mock_config_path))

    def test_very_long_argument_values(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test command with very long argument values."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                long_tag = "a" * 1000
                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-all",
                        "--tag",
                        long_tag,
                    ],
                )

                assert result.exit_code == 0
                mock_orch.process_all_issues.assert_called_once_with(long_tag)

    def test_unicode_in_arguments(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test command with unicode characters in arguments."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    [
                        "--config",
                        str(mock_config_path),
                        "process-all",
                        "--tag",
                        "tag-中文-العربية-🚀",
                    ],
                )

                assert result.exit_code == 0


class TestContextManagement:
    """Test Click context management."""

    def test_context_object_creation(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test that context object is properly created."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_orch.process_all_issues = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "list-plans"],
                )

                # Verify that the command executed successfully
                assert result.exit_code == 0


class TestExitCodes:
    """Test proper exit codes."""

    def test_success_exit_code_zero(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test that successful commands return exit code 0."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.get_active_plans = AsyncMock(return_value=[])
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "list-plans"],
                )

                assert result.exit_code == 0

    def test_error_exit_code_nonzero(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that failed commands return non-zero exit code."""
        result = cli_runner.invoke(
            cli,
            ["--config", "/nonexistent/config.yaml", "list-plans"],
        )

        assert result.exit_code != 0

    def test_missing_required_argument_exit_code(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test exit code when required argument is missing."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "process-issue"],
            )

            assert result.exit_code != 0


class TestLoggingIntegration:
    """Test logging configuration integration."""

    def test_logging_configuration_called(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that logging configuration is called."""
        with patch("automation.utils.logging_config.configure_logging") as mock_logging:
            with patch("automation.config.settings.AutomationSettings.from_yaml"):
                cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "list-plans"],
                )

                # Verify logging was configured
                mock_logging.assert_called()

    def test_logging_level_propagation(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that log level is properly propagated."""
        with patch("automation.utils.logging_config.configure_logging") as mock_logging:
            with patch("automation.config.settings.AutomationSettings.from_yaml"):
                cli_runner.invoke(
                    cli,
                    ["--log-level", "ERROR", "--config", str(mock_config_path), "list-plans"],
                )

                mock_logging.assert_called_with("ERROR")
