"""Tests for automation.main CLI module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from automation.exceptions import RepoSapiensError
from automation.main import cli


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.git_provider.base_url = "https://git.example.com"
    settings.git_provider.api_token.get_secret_value.return_value = "test-token"
    settings.repository.owner = "testowner"
    settings.repository.name = "testrepo"
    settings.agent_provider.provider_type = "claude"
    settings.agent_provider.model = "claude-3-sonnet"
    settings.agent_provider.base_url = "https://api.example.com"
    settings.state_dir = "/tmp/state"
    return settings


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, cli_runner):
        """Test CLI help command."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Gitea automation system CLI" in result.output

    def test_cli_missing_config(self, cli_runner):
        """Test CLI handles missing config file."""
        result = cli_runner.invoke(cli, ["--config", "/nonexistent/file.yaml", "list-plans"])
        # Should fail because config doesn't exist
        assert result.exit_code == 1
        assert "Configuration file not found" in result.output


class TestAsyncMainFunctions:
    """Test async helper functions."""

    @pytest.mark.asyncio
    async def test_process_single_issue(self, mock_settings):
        """Test processing a single issue."""
        from automation.main import _process_single_issue

        mock_orchestrator = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_orchestrator.git.get_issue = AsyncMock(return_value=mock_issue)
        mock_orchestrator.process_issue = AsyncMock()

        with patch("automation.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_single_issue(mock_settings, 42)

            mock_orchestrator.git.get_issue.assert_called_once_with(42)
            mock_orchestrator.process_issue.assert_called_once_with(mock_issue)

    @pytest.mark.asyncio
    async def test_process_all_issues_with_tag(self, mock_settings):
        """Test processing all issues with tag filter."""
        from automation.main import _process_all_issues

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock()

        with patch("automation.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_all_issues(mock_settings, "urgent")

            mock_orchestrator.process_all_issues.assert_called_once_with("urgent")

    @pytest.mark.asyncio
    async def test_process_all_issues_no_tag(self, mock_settings):
        """Test processing all issues without tag."""
        from automation.main import _process_all_issues

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock()

        with patch("automation.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_all_issues(mock_settings, None)

            mock_orchestrator.process_all_issues.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_process_plan(self, mock_settings):
        """Test processing a plan."""
        from automation.main import _process_plan

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_plan = AsyncMock()

        with patch("automation.main._create_orchestrator", return_value=mock_orchestrator):
            await _process_plan(mock_settings, "plan-123")

            mock_orchestrator.process_plan.assert_called_once_with("plan-123")

    @pytest.mark.asyncio
    async def test_list_active_plans_empty(self, mock_settings, capsys):
        """Test listing plans when no plans exist."""
        from automation.main import _list_active_plans

        mock_state = AsyncMock()
        mock_state.get_active_plans = AsyncMock(return_value=[])

        with patch("automation.main.StateManager", return_value=mock_state):
            await _list_active_plans(mock_settings)

            captured = capsys.readouterr()
            assert "No active plans found" in captured.out

    @pytest.mark.asyncio
    async def test_list_active_plans_with_plans(self, mock_settings, capsys):
        """Test listing plans when plans exist."""
        from automation.main import _list_active_plans

        mock_state = AsyncMock()
        mock_state.get_active_plans = AsyncMock(return_value=["plan-1", "plan-2"])
        mock_state.load_state = AsyncMock(
            side_effect=[{"status": "active"}, {"status": "completed"}]
        )

        with patch("automation.main.StateManager", return_value=mock_state):
            await _list_active_plans(mock_settings)

            captured = capsys.readouterr()
            assert "Active Plans" in captured.out

    @pytest.mark.asyncio
    async def test_show_plan_status_found(self, mock_settings, capsys):
        """Test showing status of existing plan."""
        from automation.main import _show_plan_status

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

        with patch("automation.main.StateManager", return_value=mock_state):
            await _show_plan_status(mock_settings, "plan-123")

            captured = capsys.readouterr()
            assert "Plan plan-123 Status" in captured.out

    @pytest.mark.asyncio
    async def test_show_plan_status_not_found(self, mock_settings, capsys):
        """Test showing status of non-existent plan."""
        from automation.main import _show_plan_status

        mock_state = AsyncMock()
        mock_state.load_state = AsyncMock(side_effect=FileNotFoundError())

        with patch("automation.main.StateManager", return_value=mock_state):
            await _show_plan_status(mock_settings, "plan-123")

            captured = capsys.readouterr()
            # Message is printed to err, not out
            assert "not found" in (captured.out + captured.err)

    @pytest.mark.asyncio
    async def test_daemon_mode_keyboard_interrupt(self, mock_settings):
        """Test daemon mode handles keyboard interrupt."""
        from automation.main import _daemon_mode

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock()

        with (
            patch("automation.main._create_orchestrator", return_value=mock_orchestrator),
            patch("automation.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("automation.main.click.echo"),
        ):
            mock_sleep.side_effect = KeyboardInterrupt()

            with pytest.raises(KeyboardInterrupt):
                await _daemon_mode(mock_settings, 1)

    @pytest.mark.asyncio
    async def test_daemon_mode_error_handling(self, mock_settings):
        """Test daemon mode handles errors gracefully."""
        from automation.main import _daemon_mode

        mock_orchestrator = AsyncMock()
        mock_orchestrator.process_all_issues = AsyncMock(side_effect=RepoSapiensError("Test error"))

        with (
            patch("automation.main._create_orchestrator", return_value=mock_orchestrator),
            patch("automation.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("automation.main.click.echo"),
        ):
            mock_sleep.side_effect = KeyboardInterrupt()

            with pytest.raises(KeyboardInterrupt):
                await _daemon_mode(mock_settings, 1)
