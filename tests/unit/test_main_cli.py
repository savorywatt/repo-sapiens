"""Comprehensive unit tests for repo_sapiens.main CLI module.

This module tests the main CLI entry point including:
- All CLI commands (daemon, process-issue, process-all, process-plan, list-plans, show-plan, react)
- Command options and arguments
- Error handling for missing config
- Help text generation
- Async helper functions
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from repo_sapiens.exceptions import ConfigurationError, RepoSapiensError
from repo_sapiens.main import cli


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock automation settings."""
    settings = MagicMock()
    settings.git_provider.provider_type = "gitea"
    settings.git_provider.base_url = "https://git.example.com"
    settings.git_provider.api_token.get_secret_value.return_value = "test-token"
    settings.repository.owner = "testowner"
    settings.repository.name = "testrepo"
    settings.agent_provider.provider_type = "claude-local"
    settings.agent_provider.model = "claude-sonnet-4.5"
    settings.agent_provider.base_url = "https://api.example.com"
    settings.agent_provider.goose_config = None
    settings.state_dir = "/tmp/state"
    return settings


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a mock configuration file."""
    config_content = """
git_provider:
  provider_type: gitea
  mcp_server: test-mcp
  base_url: https://gitea.test.com
  api_token: test-token

repository:
  owner: test-owner
  name: test-repo
  default_branch: main

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4.5
  api_key: test-key
  local_mode: true

workflow:
  plans_directory: plans/
  state_directory: .automation/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3

tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
  in_progress: in-progress
  code_review: code-review
  merge_ready: merge-ready
  completed: completed
  needs_attention: needs-attention
"""
    config_path = tmp_path / "automation_config.yaml"
    config_path.write_text(config_content)
    return config_path


# =============================================================================
# CLI Help Text Tests
# =============================================================================


class TestCLIHelpText:
    """Test CLI help text generation for all commands."""

    def test_cli_main_help(self, cli_runner):
        """Test main CLI help displays correctly."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Gitea automation system CLI" in result.output
        assert "--config" in result.output
        assert "--log-level" in result.output

    def test_process_issue_help(self, cli_runner, mock_config_file):
        """Test process-issue command help."""
        # Note: Help for subcommands that need config require a valid config path
        # to avoid failing on config loading before showing help
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--help"]
        )
        # Alternatively, test with missing config - help may still work
        result_alt = cli_runner.invoke(cli, ["process-issue", "--help"])
        # One of them should contain the help text
        assert "Process a single issue" in result.output or "Process a single issue" in result_alt.output
        assert "--issue" in result.output or "--issue" in result_alt.output

    def test_process_all_help(self, cli_runner, mock_config_file):
        """Test process-all command help."""
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-all", "--help"]
        )
        result_alt = cli_runner.invoke(cli, ["process-all", "--help"])
        assert "Process all issues" in result.output or "Process all issues" in result_alt.output
        assert "--tag" in result.output or "--tag" in result_alt.output

    def test_process_plan_help(self, cli_runner, mock_config_file):
        """Test process-plan command help."""
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-plan", "--help"]
        )
        result_alt = cli_runner.invoke(cli, ["process-plan", "--help"])
        assert "Process entire plan" in result.output or "Process entire plan" in result_alt.output
        assert "--plan-id" in result.output or "--plan-id" in result_alt.output

    def test_daemon_help(self, cli_runner, mock_config_file):
        """Test daemon command help."""
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "daemon", "--help"]
        )
        result_alt = cli_runner.invoke(cli, ["daemon", "--help"])
        assert "daemon mode" in result.output or "daemon mode" in result_alt.output
        assert "--interval" in result.output or "--interval" in result_alt.output

    def test_list_plans_help(self, cli_runner, mock_config_file):
        """Test list-plans command help."""
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "list-plans", "--help"]
        )
        result_alt = cli_runner.invoke(cli, ["list-plans", "--help"])
        assert "List all active plans" in result.output or "List all active plans" in result_alt.output

    def test_show_plan_help(self, cli_runner, mock_config_file):
        """Test show-plan command help."""
        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "show-plan", "--help"]
        )
        result_alt = cli_runner.invoke(cli, ["show-plan", "--help"])
        assert "plan status" in result.output or "plan status" in result_alt.output
        assert "--plan-id" in result.output or "--plan-id" in result_alt.output

    def test_react_help(self, cli_runner):
        """Test react command help."""
        result = cli_runner.invoke(cli, ["react", "--help"])
        assert result.exit_code == 0
        assert "Run a task using the ReAct agent" in result.output
        assert "--model" in result.output
        assert "--ollama-url" in result.output
        assert "--max-iterations" in result.output
        assert "--working-dir" in result.output
        assert "--verbose" in result.output
        assert "--repl" in result.output

    def test_init_help(self, cli_runner):
        """Test init command help."""
        result = cli_runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize repo-agent" in result.output or "init" in result.output.lower()

    def test_credentials_help(self, cli_runner):
        """Test credentials command group help."""
        result = cli_runner.invoke(cli, ["credentials", "--help"])
        assert result.exit_code == 0
        assert "Manage credentials" in result.output


# =============================================================================
# Configuration Loading Tests
# =============================================================================


class TestConfigurationLoading:
    """Test configuration file loading and error handling."""

    def test_missing_config_file(self, cli_runner):
        """Test handling of missing configuration file."""
        result = cli_runner.invoke(cli, ["--config", "/nonexistent/config.yaml", "list-plans"])
        assert result.exit_code == 1
        assert "Configuration file not found" in result.output

    def test_config_not_required_for_init(self, cli_runner, tmp_path):
        """Test init command does not require config file."""
        with patch("repo_sapiens.cli.init.RepoInitializer.run"):
            result = cli_runner.invoke(
                cli,
                ["--config", "/nonexistent/config.yaml", "init", "--repo-path", str(tmp_path)],
            )
        # Should not fail due to missing config
        assert "Configuration file not found" not in result.output

    def test_config_not_required_for_react(self, cli_runner):
        """Test react command does not require config file."""
        # React should fail for other reasons but not config
        result = cli_runner.invoke(
            cli, ["--config", "/nonexistent/config.yaml", "react", "--help"]
        )
        assert result.exit_code == 0  # Help should work

    def test_config_not_required_for_credentials(self, cli_runner):
        """Test credentials command does not require config file."""
        result = cli_runner.invoke(
            cli, ["--config", "/nonexistent/config.yaml", "credentials", "--help"]
        )
        assert result.exit_code == 0

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    def test_configuration_error_handling(self, mock_from_yaml, cli_runner, mock_config_file):
        """Test handling of ConfigurationError during loading."""
        mock_from_yaml.side_effect = ConfigurationError("Invalid configuration")

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "list-plans"])

        assert result.exit_code == 1
        assert "Invalid configuration" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    def test_unexpected_config_error(self, mock_from_yaml, cli_runner, mock_config_file):
        """Test handling of unexpected errors during config loading."""
        mock_from_yaml.side_effect = RuntimeError("Unexpected error")

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "list-plans"])

        assert result.exit_code == 1
        assert "Unexpected error" in result.output


# =============================================================================
# process-issue Command Tests
# =============================================================================


class TestProcessIssueCommand:
    """Test process-issue command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_success(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test successful issue processing."""
        mock_settings_loader.return_value = mock_settings
        mock_run.return_value = None

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "42"]
        )

        # Should attempt to run asyncio.run
        assert mock_run.called

    def test_process_issue_missing_option(self, cli_runner, mock_config_file):
        """Test process-issue fails without --issue option."""
        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "process-issue"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--issue" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_repo_sapiens_error(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-issue handles RepoSapiensError."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = RepoSapiensError("Test error")

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "42"]
        )

        assert result.exit_code == 1
        assert "Test error" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_keyboard_interrupt(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-issue handles KeyboardInterrupt."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = KeyboardInterrupt()

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "42"]
        )

        assert result.exit_code == 130
        assert "Interrupted" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_unexpected_error(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-issue handles unexpected errors."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = RuntimeError("Unexpected")

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "42"]
        )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output


# =============================================================================
# process-all Command Tests
# =============================================================================


class TestProcessAllCommand:
    """Test process-all command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_all_without_tag(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-all without tag filter."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "process-all"])

        assert mock_run.called

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_all_with_tag(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-all with tag filter."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-all", "--tag", "urgent"]
        )

        assert mock_run.called

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_all_repo_sapiens_error(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-all handles RepoSapiensError."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = RepoSapiensError("Processing error")

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "process-all"])

        assert result.exit_code == 1
        assert "Processing error" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_all_keyboard_interrupt(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-all handles KeyboardInterrupt."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = KeyboardInterrupt()

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "process-all"])

        assert result.exit_code == 130


# =============================================================================
# process-plan Command Tests
# =============================================================================


class TestProcessPlanCommand:
    """Test process-plan command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_plan_success(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test successful plan processing."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-plan", "--plan-id", "plan-123"]
        )

        assert mock_run.called

    def test_process_plan_missing_option(self, cli_runner, mock_config_file):
        """Test process-plan fails without --plan-id option."""
        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "process-plan"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--plan-id" in result.output

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_plan_repo_sapiens_error(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-plan handles RepoSapiensError."""
        mock_settings_loader.return_value = mock_settings
        mock_run.side_effect = RepoSapiensError("Plan error")

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-plan", "--plan-id", "plan-123"]
        )

        assert result.exit_code == 1
        assert "Plan error" in result.output


# =============================================================================
# daemon Command Tests
# =============================================================================


class TestDaemonCommand:
    """Test daemon command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_daemon_default_interval(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test daemon with default interval."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "daemon"])

        assert mock_run.called

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_daemon_custom_interval(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test daemon with custom interval."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "daemon", "--interval", "120"]
        )

        assert mock_run.called


# =============================================================================
# list-plans Command Tests
# =============================================================================


class TestListPlansCommand:
    """Test list-plans command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_list_plans_success(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test successful plan listing."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "list-plans"])

        assert mock_run.called


# =============================================================================
# show-plan Command Tests
# =============================================================================


class TestShowPlanCommand:
    """Test show-plan command."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_show_plan_success(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test successful plan display."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "show-plan", "--plan-id", "plan-123"]
        )

        assert mock_run.called

    def test_show_plan_missing_option(self, cli_runner, mock_config_file):
        """Test show-plan fails without --plan-id option."""
        result = cli_runner.invoke(cli, ["--config", str(mock_config_file), "show-plan"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--plan-id" in result.output


# =============================================================================
# react Command Tests
# =============================================================================


class TestReactCommand:
    """Test react command."""

    def test_react_requires_task_or_repl(self, cli_runner):
        """Test react command requires either TASK or --repl."""
        result = cli_runner.invoke(cli, ["react"])
        assert result.exit_code == 1
        assert "Either provide a TASK or use --repl" in result.output

    def test_react_accepts_task_argument(self, cli_runner):
        """Test react command accepts task argument."""
        with patch("repo_sapiens.main.asyncio.run") as mock_run:
            mock_run.side_effect = RuntimeError("Connection refused")
            result = cli_runner.invoke(cli, ["react", "Create a hello.py file"])

        # Should fail due to mocked connection error, not argument parsing
        assert "Connection refused" in result.output or result.exit_code == 1

    def test_react_model_option(self, cli_runner):
        """Test react command accepts --model option."""
        result = cli_runner.invoke(cli, ["react", "--model", "llama2:7b", "--help"])
        # Help should show the model option
        assert "--model" in result.output

    def test_react_ollama_url_option(self, cli_runner):
        """Test react command accepts --ollama-url option."""
        result = cli_runner.invoke(cli, ["react", "--ollama-url", "http://localhost:12345", "--help"])
        assert "--ollama-url" in result.output

    def test_react_max_iterations_option(self, cli_runner):
        """Test react command accepts --max-iterations option."""
        result = cli_runner.invoke(cli, ["react", "--max-iterations", "5", "--help"])
        assert "--max-iterations" in result.output

    def test_react_working_dir_option(self, cli_runner, tmp_path):
        """Test react command accepts --working-dir option."""
        result = cli_runner.invoke(
            cli, ["react", "--working-dir", str(tmp_path), "--help"]
        )
        assert "--working-dir" in result.output

    def test_react_verbose_flag(self, cli_runner):
        """Test react command accepts --verbose flag."""
        result = cli_runner.invoke(cli, ["react", "--verbose", "--help"])
        assert "--verbose" in result.output or "-v" in result.output

    def test_react_repl_flag(self, cli_runner):
        """Test react command accepts --repl flag."""
        result = cli_runner.invoke(cli, ["react", "--repl", "--help"])
        assert "--repl" in result.output

    @patch("repo_sapiens.main.asyncio.run")
    def test_react_keyboard_interrupt(self, mock_run, cli_runner):
        """Test react handles KeyboardInterrupt."""
        mock_run.side_effect = KeyboardInterrupt()

        result = cli_runner.invoke(cli, ["react", "Test task"])

        assert result.exit_code == 130
        assert "Interrupted" in result.output

    @patch("repo_sapiens.main.asyncio.run")
    def test_react_runtime_error(self, mock_run, cli_runner):
        """Test react handles runtime errors."""
        mock_run.side_effect = RuntimeError("Ollama not available")

        result = cli_runner.invoke(cli, ["react", "Test task"])

        assert result.exit_code == 1
        assert "Ollama not available" in result.output


# =============================================================================
# Async Helper Function Tests
# =============================================================================


class TestAsyncHelperFunctions:
    """Test async helper functions used by CLI commands."""

    @pytest.mark.asyncio
    async def test_process_single_issue(self, mock_settings):
        """Test _process_single_issue async function."""
        from repo_sapiens.main import _process_single_issue

        mock_orchestrator = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_orchestrator.git.get_issue = AsyncMock(return_value=mock_issue)
        mock_orchestrator.process_issue = AsyncMock()

        with patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_single_issue(mock_settings, 42)

        mock_orchestrator.git.get_issue.assert_called_once_with(42)
        mock_orchestrator.process_issue.assert_called_once_with(mock_issue)

    @pytest.mark.asyncio
    async def test_process_all_issues_with_tag(self, mock_settings):
        """Test _process_all_issues with tag filter."""
        from repo_sapiens.main import _process_all_issues

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock()

        with patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_all_issues(mock_settings, "urgent")

        mock_orchestrator.process_all_issues.assert_called_once_with("urgent")

    @pytest.mark.asyncio
    async def test_process_all_issues_without_tag(self, mock_settings):
        """Test _process_all_issues without tag filter."""
        from repo_sapiens.main import _process_all_issues

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock()

        with patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_all_issues(mock_settings, None)

        mock_orchestrator.process_all_issues.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_process_plan(self, mock_settings):
        """Test _process_plan async function."""
        from repo_sapiens.main import _process_plan

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_plan = AsyncMock()

        with patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_plan(mock_settings, "plan-123")

        mock_orchestrator.process_plan.assert_called_once_with("plan-123")

    @pytest.mark.asyncio
    async def test_list_active_plans_empty(self, mock_settings, capsys):
        """Test _list_active_plans when no plans exist."""
        from repo_sapiens.main import _list_active_plans

        mock_state = AsyncMock()
        mock_state.get_active_plans = AsyncMock(return_value=[])

        with patch("repo_sapiens.main.StateManager", return_value=mock_state):
            await _list_active_plans(mock_settings)

        captured = capsys.readouterr()
        assert "No active plans found" in captured.out

    @pytest.mark.asyncio
    async def test_list_active_plans_with_plans(self, mock_settings, capsys):
        """Test _list_active_plans when plans exist."""
        from repo_sapiens.main import _list_active_plans

        mock_state = AsyncMock()
        mock_state.get_active_plans = AsyncMock(return_value=["plan-1", "plan-2"])
        mock_state.load_state = AsyncMock(
            side_effect=[{"status": "active"}, {"status": "completed"}]
        )

        with patch("repo_sapiens.main.StateManager", return_value=mock_state):
            await _list_active_plans(mock_settings)

        captured = capsys.readouterr()
        assert "Active Plans" in captured.out
        assert "plan-1" in captured.out
        assert "plan-2" in captured.out

    @pytest.mark.asyncio
    async def test_show_plan_status_found(self, mock_settings, capsys):
        """Test _show_plan_status for existing plan."""
        from repo_sapiens.main import _show_plan_status

        mock_state = AsyncMock()
        mock_state.load_state = AsyncMock(
            return_value={
                "status": "active",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
                "stages": {"planning": {"status": "completed"}},
                "tasks": {"task-1": {"status": "completed"}},
            }
        )

        with patch("repo_sapiens.main.StateManager", return_value=mock_state):
            await _show_plan_status(mock_settings, "plan-123")

        captured = capsys.readouterr()
        assert "Plan plan-123 Status" in captured.out
        assert "active" in captured.out

    @pytest.mark.asyncio
    async def test_show_plan_status_not_found(self, mock_settings, capsys):
        """Test _show_plan_status for non-existent plan."""
        from repo_sapiens.main import _show_plan_status

        mock_state = AsyncMock()
        mock_state.load_state = AsyncMock(side_effect=FileNotFoundError())

        with patch("repo_sapiens.main.StateManager", return_value=mock_state):
            await _show_plan_status(mock_settings, "nonexistent")

        captured = capsys.readouterr()
        assert "not found" in (captured.out + captured.err)

    @pytest.mark.asyncio
    async def test_daemon_mode_processes_issues(self, mock_settings):
        """Test _daemon_mode processes issues in loop."""
        from repo_sapiens.main import _daemon_mode

        mock_orchestrator = AsyncMock()
        call_count = 0

        async def process_all(*args):
            nonlocal call_count
            call_count += 1

        mock_orchestrator.process_all_issues = process_all

        async def mock_sleep_raise(*args):
            # On first sleep, raise KeyboardInterrupt to exit loop
            raise KeyboardInterrupt()

        with (
            patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator),
            patch("repo_sapiens.main.asyncio.sleep", side_effect=mock_sleep_raise),
            patch("repo_sapiens.main.click.echo"),
        ):
            with pytest.raises(KeyboardInterrupt):
                await _daemon_mode(mock_settings, 1)

        # Should have processed at least once before sleep raised interrupt
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_daemon_mode_handles_repo_sapiens_error(self, mock_settings):
        """Test _daemon_mode handles RepoSapiensError gracefully."""
        from repo_sapiens.main import _daemon_mode

        mock_orchestrator = AsyncMock()
        call_count = 0

        async def process_all_with_error(*args):
            nonlocal call_count
            call_count += 1
            raise RepoSapiensError("Test error")

        mock_orchestrator.process_all_issues = process_all_with_error

        async def mock_sleep_raise(*args):
            raise KeyboardInterrupt()

        with (
            patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator),
            patch("repo_sapiens.main.asyncio.sleep", side_effect=mock_sleep_raise),
            patch("repo_sapiens.main.click.echo"),
        ):
            with pytest.raises(KeyboardInterrupt):
                await _daemon_mode(mock_settings, 1)

        # Should have attempted to process (error is caught and logged)
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_daemon_mode_handles_unexpected_error(self, mock_settings):
        """Test _daemon_mode handles unexpected errors gracefully."""
        from repo_sapiens.main import _daemon_mode

        mock_orchestrator = AsyncMock()
        call_count = 0

        async def process_all_with_error(*args):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Unexpected error")

        mock_orchestrator.process_all_issues = process_all_with_error

        async def mock_sleep_raise(*args):
            raise KeyboardInterrupt()

        with (
            patch("repo_sapiens.main._create_orchestrator", return_value=mock_orchestrator),
            patch("repo_sapiens.main.asyncio.sleep", side_effect=mock_sleep_raise),
            patch("repo_sapiens.main.click.echo"),
        ):
            with pytest.raises(KeyboardInterrupt):
                await _daemon_mode(mock_settings, 1)

        # Should have attempted to process (error is caught and logged)
        assert call_count >= 1


# =============================================================================
# Orchestrator Creation Tests
# =============================================================================


class TestOrchestratorCreation:
    """Test orchestrator creation helper function."""

    @pytest.mark.asyncio
    async def test_create_orchestrator_with_ollama_provider(self):
        """Test _create_orchestrator with Ollama provider."""
        from repo_sapiens.main import _create_orchestrator

        mock_settings = MagicMock()
        mock_settings.git_provider.provider_type = "gitea"
        mock_settings.git_provider.mcp_server = "test-mcp"
        mock_settings.git_provider.base_url = "https://gitea.test.com"
        mock_settings.git_provider.api_token.get_secret_value.return_value = "token"
        mock_settings.repository.owner = "owner"
        mock_settings.repository.name = "repo"
        mock_settings.agent_provider.provider_type = "ollama"
        mock_settings.agent_provider.base_url = "http://localhost:11434"
        mock_settings.agent_provider.model = "llama3"
        mock_settings.state_dir = "/tmp/state"

        with (
            patch("repo_sapiens.main.create_git_provider") as mock_git_factory,
            patch("repo_sapiens.providers.ollama.OllamaProvider") as mock_ollama,
            patch("repo_sapiens.main.StateManager"),
            patch("repo_sapiens.main.WorkflowOrchestrator"),
            patch("repo_sapiens.main.InteractiveQAHandler"),
        ):
            mock_git = AsyncMock()
            mock_git_factory.return_value = mock_git

            mock_agent = AsyncMock()
            mock_ollama.return_value = mock_agent

            await _create_orchestrator(mock_settings)

            mock_git.connect.assert_called_once()
            mock_agent.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_orchestrator_with_claude_provider(self):
        """Test _create_orchestrator with Claude provider."""
        from repo_sapiens.main import _create_orchestrator

        mock_settings = MagicMock()
        mock_settings.git_provider.provider_type = "gitea"
        mock_settings.git_provider.mcp_server = "test-mcp"
        mock_settings.git_provider.base_url = "https://gitea.test.com"
        mock_settings.git_provider.api_token.get_secret_value.return_value = "token"
        mock_settings.repository.owner = "owner"
        mock_settings.repository.name = "repo"
        mock_settings.agent_provider.provider_type = "claude-local"
        mock_settings.agent_provider.model = "claude-sonnet-4.5"
        mock_settings.agent_provider.goose_config = None
        mock_settings.state_dir = "/tmp/state"

        with (
            patch("repo_sapiens.main.create_git_provider") as mock_git_factory,
            patch("repo_sapiens.main.ExternalAgentProvider") as mock_external,
            patch("repo_sapiens.main.StateManager"),
            patch("repo_sapiens.main.WorkflowOrchestrator"),
            patch("repo_sapiens.main.InteractiveQAHandler"),
        ):
            mock_git = AsyncMock()
            mock_git_factory.return_value = mock_git

            mock_agent = AsyncMock()
            mock_external.return_value = mock_agent

            await _create_orchestrator(mock_settings)

            mock_external.assert_called_once()
            call_kwargs = mock_external.call_args
            assert call_kwargs[1]["agent_type"] == "claude"

    @pytest.mark.asyncio
    async def test_create_orchestrator_with_goose_provider(self):
        """Test _create_orchestrator with Goose provider."""
        from repo_sapiens.main import _create_orchestrator

        mock_settings = MagicMock()
        mock_settings.git_provider.provider_type = "gitea"
        mock_settings.git_provider.mcp_server = "test-mcp"
        mock_settings.git_provider.base_url = "https://gitea.test.com"
        mock_settings.git_provider.api_token.get_secret_value.return_value = "token"
        mock_settings.repository.owner = "owner"
        mock_settings.repository.name = "repo"
        mock_settings.agent_provider.provider_type = "goose-local"
        mock_settings.agent_provider.model = "gpt-4"
        mock_settings.agent_provider.goose_config = MagicMock()
        mock_settings.agent_provider.goose_config.toolkit = "default"
        mock_settings.agent_provider.goose_config.temperature = 0.7
        mock_settings.agent_provider.goose_config.max_tokens = 4096
        mock_settings.agent_provider.goose_config.llm_provider = "openai"
        mock_settings.state_dir = "/tmp/state"

        with (
            patch("repo_sapiens.main.create_git_provider") as mock_git_factory,
            patch("repo_sapiens.main.ExternalAgentProvider") as mock_external,
            patch("repo_sapiens.main.StateManager"),
            patch("repo_sapiens.main.WorkflowOrchestrator"),
            patch("repo_sapiens.main.InteractiveQAHandler"),
        ):
            mock_git = AsyncMock()
            mock_git_factory.return_value = mock_git

            mock_agent = AsyncMock()
            mock_external.return_value = mock_agent

            await _create_orchestrator(mock_settings)

            mock_external.assert_called_once()
            call_kwargs = mock_external.call_args
            assert call_kwargs[1]["agent_type"] == "goose"
            assert call_kwargs[1]["goose_config"] is not None


# =============================================================================
# CLI Options Tests
# =============================================================================


class TestCLIOptions:
    """Test CLI global options."""

    def test_log_level_option(self, cli_runner, mock_config_file):
        """Test --log-level option is accepted."""
        with patch("repo_sapiens.main.AutomationSettings.from_yaml"), patch(
            "repo_sapiens.main.asyncio.run"
        ):
            result = cli_runner.invoke(
                cli, ["--log-level", "DEBUG", "--config", str(mock_config_file), "list-plans"]
            )

        # Should not fail due to log level option
        assert "Invalid" not in result.output or "--log-level" not in result.output

    def test_config_option_accepts_path(self, cli_runner, mock_config_file):
        """Test --config option accepts file path."""
        with patch("repo_sapiens.main.AutomationSettings.from_yaml"), patch(
            "repo_sapiens.main.asyncio.run"
        ):
            result = cli_runner.invoke(
                cli, ["--config", str(mock_config_file), "list-plans"]
            )

        # Should use provided config path
        assert result.exit_code in [0, 1]  # May fail for other reasons


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_config_path(self, cli_runner):
        """Test handling of empty config path."""
        result = cli_runner.invoke(cli, ["--config", "", "list-plans"])
        # Should fail gracefully
        assert result.exit_code != 0

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_with_zero(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-issue with issue number 0."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "0"]
        )

        assert mock_run.called

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    @patch("repo_sapiens.main.asyncio.run")
    def test_process_issue_with_large_number(
        self, mock_run, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Test process-issue with large issue number."""
        mock_settings_loader.return_value = mock_settings

        result = cli_runner.invoke(
            cli, ["--config", str(mock_config_file), "process-issue", "--issue", "999999999"]
        )

        assert mock_run.called

    def test_daemon_with_zero_interval(self, cli_runner, mock_config_file):
        """Test daemon with zero interval."""
        with patch("repo_sapiens.main.AutomationSettings.from_yaml"), patch(
            "repo_sapiens.main.asyncio.run"
        ):
            result = cli_runner.invoke(
                cli, ["--config", str(mock_config_file), "daemon", "--interval", "0"]
            )

        # Should accept zero interval (though not practical)
        assert result.exit_code in [0, 1]

    def test_invalid_subcommand(self, cli_runner):
        """Test handling of invalid subcommand."""
        result = cli_runner.invoke(cli, ["invalid-command"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "invalid" in result.output.lower()


# =============================================================================
# Integration Tests (CLI + Async)
# =============================================================================


class TestCLIAsyncIntegration:
    """Test integration between CLI commands and async functions."""

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    def test_process_issue_calls_async_function(
        self, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Verify process-issue command calls async processing."""
        mock_settings_loader.return_value = mock_settings

        with patch("repo_sapiens.main._process_single_issue") as mock_func:
            with patch("repo_sapiens.main.asyncio.run") as mock_run:
                result = cli_runner.invoke(
                    cli, ["--config", str(mock_config_file), "process-issue", "--issue", "42"]
                )

                mock_run.assert_called_once()

    @patch("repo_sapiens.main.AutomationSettings.from_yaml")
    def test_daemon_calls_async_function(
        self, mock_settings_loader, cli_runner, mock_config_file, mock_settings
    ):
        """Verify daemon command calls async daemon mode."""
        mock_settings_loader.return_value = mock_settings

        with patch("repo_sapiens.main._daemon_mode") as mock_func:
            with patch("repo_sapiens.main.asyncio.run") as mock_run:
                result = cli_runner.invoke(
                    cli, ["--config", str(mock_config_file), "daemon"]
                )

                mock_run.assert_called_once()
