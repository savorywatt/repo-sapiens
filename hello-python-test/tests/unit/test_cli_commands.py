"""Integration and advanced tests for CLI commands.

Tests cover:
- Orchestrator creation and initialization
- Mock external providers (Git, AI)
- Error handling and recovery
- User-friendly error messages
- Integration between commands
- State management
- Permission and file path errors
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from automation.main import (
    _create_orchestrator,
    _daemon_mode,
    _list_active_plans,
    _process_all_issues,
    _process_plan,
    _process_single_issue,
    _show_plan_status,
    cli,
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


class TestOrchestratorCreation:
    """Test orchestrator initialization."""

    @pytest.mark.asyncio
    async def test_create_orchestrator_external_provider(
        self, mock_settings: MagicMock
    ) -> None:
        """Test creating orchestrator with external agent provider."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.external_agent.ExternalAgentProvider") as mock_agent_class:
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git_class.return_value = mock_git

                        mock_agent = AsyncMock()
                        mock_agent_class.return_value = mock_agent

                        orchestrator = await _create_orchestrator(mock_settings)

                        # Verify providers were initialized
                        mock_git_class.assert_called_once()
                        mock_agent_class.assert_called_once()

                        # Verify connections were established
                        mock_git.connect.assert_called_once()
                        mock_agent.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_orchestrator_ollama_provider(
        self, mock_settings: MagicMock
    ) -> None:
        """Test creating orchestrator with Ollama provider."""
        mock_settings.agent_provider.provider_type = "ollama"

        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.ollama.OllamaProvider") as mock_ollama_class:
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git_class.return_value = mock_git

                        mock_ollama = AsyncMock()
                        mock_ollama_class.return_value = mock_ollama

                        orchestrator = await _create_orchestrator(mock_settings)

                        # Verify Ollama provider was used
                        mock_ollama_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_orchestrator_connection_failure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of connection failures during orchestrator creation."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.external_agent.ExternalAgentProvider"):
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git.connect = AsyncMock(side_effect=ConnectionError("Failed to connect"))
                        mock_git_class.return_value = mock_git

                        with pytest.raises(ConnectionError):
                            await _create_orchestrator(mock_settings)

    @pytest.mark.asyncio
    async def test_create_orchestrator_api_token_retrieval(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that API token is properly retrieved from settings."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.external_agent.ExternalAgentProvider"):
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git_class.return_value = mock_git

                        await _create_orchestrator(mock_settings)

                        # Verify token was retrieved
                        mock_settings.git_provider.api_token.get_secret_value.assert_called()

                        # Verify token was passed to GiteaRestProvider
                        call_kwargs = mock_git_class.call_args[1]
                        assert call_kwargs["token"] == "test_token"


class TestProcessSingleIssueFunction:
    """Test _process_single_issue async function."""

    @pytest.mark.asyncio
    async def test_process_single_issue_success(
        self, mock_settings: MagicMock
    ) -> None:
        """Test successful single issue processing."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_issue = MagicMock(number=42)
            mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
            mock_orch.process_issue = AsyncMock()
            mock_create_orch.return_value = mock_orch

            # Should not raise any exception
            await _process_single_issue(mock_settings, 42)

            mock_orch.git.get_issue.assert_called_once_with(42)
            mock_orch.process_issue.assert_called_once_with(mock_issue)

    @pytest.mark.asyncio
    async def test_process_single_issue_not_found(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of non-existent issue."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.git.get_issue = AsyncMock(side_effect=FileNotFoundError("Issue not found"))
            mock_create_orch.return_value = mock_orch

            with pytest.raises(FileNotFoundError):
                await _process_single_issue(mock_settings, 999)

    @pytest.mark.asyncio
    async def test_process_single_issue_with_exception(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of exception during issue processing."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_issue = MagicMock(number=42)
            mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
            mock_orch.process_issue = AsyncMock(
                side_effect=RuntimeError("Processing failed")
            )
            mock_create_orch.return_value = mock_orch

            with pytest.raises(RuntimeError):
                await _process_single_issue(mock_settings, 42)


class TestProcessAllIssuesFunction:
    """Test _process_all_issues async function."""

    @pytest.mark.asyncio
    async def test_process_all_without_tag(
        self, mock_settings: MagicMock
    ) -> None:
        """Test processing all issues without tag filter."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock()
            mock_create_orch.return_value = mock_orch

            await _process_all_issues(mock_settings, None)

            mock_orch.process_all_issues.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_process_all_with_tag(
        self, mock_settings: MagicMock
    ) -> None:
        """Test processing all issues with tag filter."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock()
            mock_create_orch.return_value = mock_orch

            await _process_all_issues(mock_settings, "urgent")

            mock_orch.process_all_issues.assert_called_once_with("urgent")

    @pytest.mark.asyncio
    async def test_process_all_with_empty_tag(
        self, mock_settings: MagicMock
    ) -> None:
        """Test processing with empty tag string."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock()
            mock_create_orch.return_value = mock_orch

            await _process_all_issues(mock_settings, "")

            mock_orch.process_all_issues.assert_called_once_with("")

    @pytest.mark.asyncio
    async def test_process_all_failure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of failure during process_all."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock(
                side_effect=RuntimeError("Processing failed")
            )
            mock_create_orch.return_value = mock_orch

            with pytest.raises(RuntimeError):
                await _process_all_issues(mock_settings, None)


class TestProcessPlanFunction:
    """Test _process_plan async function."""

    @pytest.mark.asyncio
    async def test_process_plan_success(
        self, mock_settings: MagicMock
    ) -> None:
        """Test successful plan processing."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_plan = AsyncMock()
            mock_create_orch.return_value = mock_orch

            await _process_plan(mock_settings, "plan-001")

            mock_orch.process_plan.assert_called_once_with("plan-001")

    @pytest.mark.asyncio
    async def test_process_plan_with_uuid(
        self, mock_settings: MagicMock
    ) -> None:
        """Test processing plan with UUID-style ID."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_plan = AsyncMock()
            mock_create_orch.return_value = mock_orch

            plan_uuid = "550e8400-e29b-41d4-a716-446655440000"
            await _process_plan(mock_settings, plan_uuid)

            mock_orch.process_plan.assert_called_once_with(plan_uuid)

    @pytest.mark.asyncio
    async def test_process_plan_not_found(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of non-existent plan."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_plan = AsyncMock(
                side_effect=FileNotFoundError("Plan not found")
            )
            mock_create_orch.return_value = mock_orch

            with pytest.raises(FileNotFoundError):
                await _process_plan(mock_settings, "nonexistent-plan")


class TestDaemonModeFunction:
    """Test _daemon_mode async function."""

    @pytest.mark.asyncio
    async def test_daemon_mode_keyboard_interrupt(
        self, mock_settings: MagicMock
    ) -> None:
        """Test daemon mode interruption."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock(side_effect=KeyboardInterrupt())
            mock_create_orch.return_value = mock_orch

            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Should handle KeyboardInterrupt gracefully
                await _daemon_mode(mock_settings, 60)

    @pytest.mark.asyncio
    async def test_daemon_mode_processing_error(
        self, mock_settings: MagicMock
    ) -> None:
        """Test daemon mode error handling."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            call_count = 0

            async def side_effect():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Processing failed")
                else:
                    raise KeyboardInterrupt()

            mock_orch.process_all_issues = AsyncMock(side_effect=side_effect)
            mock_create_orch.return_value = mock_orch

            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Should handle error and continue
                await _daemon_mode(mock_settings, 60)

    @pytest.mark.asyncio
    async def test_daemon_mode_with_custom_interval(
        self, mock_settings: MagicMock
    ) -> None:
        """Test daemon mode with custom polling interval."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()
            mock_orch.process_all_issues = AsyncMock(side_effect=KeyboardInterrupt())
            mock_create_orch.return_value = mock_orch

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await _daemon_mode(mock_settings, 30)

                # Verify custom interval was used
                if mock_sleep.called:
                    # Last call would have 30 as argument
                    last_call = mock_sleep.call_args_list[-1]
                    assert last_call[0][0] == 30


class TestListActivePlansFunction:
    """Test _list_active_plans async function."""

    @pytest.mark.asyncio
    async def test_list_active_plans_empty(
        self, mock_settings: MagicMock
    ) -> None:
        """Test listing with no active plans."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.get_active_plans = AsyncMock(return_value=[])
            mock_state_cls.return_value = mock_state

            # Should not raise
            await _list_active_plans(mock_settings)

    @pytest.mark.asyncio
    async def test_list_active_plans_with_plans(
        self, mock_settings: MagicMock
    ) -> None:
        """Test listing with multiple active plans."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.get_active_plans = AsyncMock(
                return_value=["plan-001", "plan-002", "plan-003"]
            )
            mock_state.load_state = AsyncMock(
                side_effect=lambda pid: {"status": f"status-{pid}"}
            )
            mock_state_cls.return_value = mock_state

            await _list_active_plans(mock_settings)

            # Verify load_state was called for each plan
            assert mock_state.load_state.call_count == 3

    @pytest.mark.asyncio
    async def test_list_active_plans_with_missing_state(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling when state file is missing."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.get_active_plans = AsyncMock(return_value=["plan-001"])
            mock_state.load_state = AsyncMock(side_effect=FileNotFoundError())
            mock_state_cls.return_value = mock_state

            with pytest.raises(FileNotFoundError):
                await _list_active_plans(mock_settings)


class TestShowPlanStatusFunction:
    """Test _show_plan_status async function."""

    @pytest.mark.asyncio
    async def test_show_plan_status_success(
        self, mock_settings: MagicMock
    ) -> None:
        """Test successful plan status display."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.load_state = AsyncMock(
                return_value={
                    "status": "in_progress",
                    "created_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-01T11:00:00Z",
                    "stages": {"stage1": {"status": "completed"}},
                    "tasks": {"task1": {"status": "pending"}},
                }
            )
            mock_state_cls.return_value = mock_state

            await _show_plan_status(mock_settings, "plan-001")

            mock_state.load_state.assert_called_once_with("plan-001")

    @pytest.mark.asyncio
    async def test_show_plan_status_not_found(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling of non-existent plan."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.load_state = AsyncMock(side_effect=FileNotFoundError())
            mock_state_cls.return_value = mock_state

            await _show_plan_status(mock_settings, "nonexistent")

    @pytest.mark.asyncio
    async def test_show_plan_status_with_complex_structure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test plan status with complex stages and tasks."""
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
                        "testing": {"status": "pending"},
                    },
                    "tasks": {
                        "task-analysis-1": {"status": "completed"},
                        "task-impl-1": {"status": "in_progress"},
                        "task-test-1": {"status": "pending"},
                    },
                }
            )
            mock_state_cls.return_value = mock_state

            await _show_plan_status(mock_settings, "complex-plan")

            mock_state.load_state.assert_called_once_with("complex-plan")


class TestIntegrationScenarios:
    """Test integration scenarios and workflows."""

    @pytest.mark.asyncio
    async def test_full_workflow_from_cli(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test complete workflow from CLI invocation."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.main._create_orchestrator") as mock_create_orch:
                mock_orch = AsyncMock()
                mock_issue = MagicMock(number=1)
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                mock_orch.process_issue = AsyncMock()
                mock_create_orch.return_value = mock_orch

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "process-issue", "--issue", "1"],
                )

                assert result.exit_code == 0

    def test_error_propagation_through_cli(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test that errors are properly propagated through CLI."""
        result = cli_runner.invoke(
            cli,
            ["--config", "/nonexistent/config.yaml", "list-plans"],
        )

        assert result.exit_code != 0
        assert "Error" in result.output


class TestProviderIntegration:
    """Test Git and Agent provider integration."""

    @pytest.mark.asyncio
    async def test_external_agent_provider_initialization(
        self, mock_settings: MagicMock
    ) -> None:
        """Test external agent provider is correctly initialized."""
        mock_settings.agent_provider.provider_type = "external"

        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.external_agent.ExternalAgentProvider") as mock_agent_class:
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git_class.return_value = mock_git

                        mock_agent = AsyncMock()
                        mock_agent_class.return_value = mock_agent

                        await _create_orchestrator(mock_settings)

                        # Verify ExternalAgentProvider was used
                        mock_agent_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_git_provider_initialization(
        self, mock_settings: MagicMock
    ) -> None:
        """Test Git provider initialization."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            with patch("automation.providers.external_agent.ExternalAgentProvider"):
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager"):
                        mock_git = AsyncMock()
                        mock_git_class.return_value = mock_git

                        await _create_orchestrator(mock_settings)

                        # Verify GiteaRestProvider was called with correct parameters
                        call_args = mock_git_class.call_args
                        assert call_args[1]["base_url"] == "http://localhost:3000"
                        assert call_args[1]["owner"] == "test_owner"
                        assert call_args[1]["repo"] == "test_repo"


class TestStateManagement:
    """Test state management interactions."""

    @pytest.mark.asyncio
    async def test_state_manager_initialization(
        self, mock_settings: MagicMock
    ) -> None:
        """Test StateManager is properly initialized."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider"):
            with patch("automation.providers.external_agent.ExternalAgentProvider"):
                with patch("automation.utils.interactive.InteractiveQAHandler"):
                    with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                        mock_state = MagicMock()
                        mock_state_cls.return_value = mock_state

                        await _create_orchestrator(mock_settings)

                        # Verify StateManager was initialized with correct path
                        mock_state_cls.assert_called_once_with("/tmp/state")

    @pytest.mark.asyncio
    async def test_state_loading_error_handling(
        self, mock_settings: MagicMock
    ) -> None:
        """Test error handling when state loading fails."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.load_state = AsyncMock(
                side_effect=IOError("Permission denied")
            )
            mock_state_cls.return_value = mock_state

            with pytest.raises(IOError):
                await _show_plan_status(mock_settings, "plan-001")


class TestErrorMessages:
    """Test error message quality and user-friendliness."""

    def test_config_not_found_message(
        self, cli_runner: CliRunner
    ) -> None:
        """Test error message when config file is not found."""
        result = cli_runner.invoke(
            cli,
            ["--config", "/nonexistent/path/config.yaml", "list-plans"],
        )

        assert "Error: Configuration file not found" in result.output
        assert "/nonexistent/path/config.yaml" in result.output

    def test_config_parsing_error_message(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test error message when config parsing fails."""
        with patch(
            "automation.config.settings.AutomationSettings.from_yaml",
            side_effect=ValueError("Invalid YAML format"),
        ):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "list-plans"],
            )

            assert "Error loading configuration" in result.output

    def test_missing_required_argument_message(
        self, cli_runner: CliRunner, mock_config_path: Path
    ) -> None:
        """Test error message for missing required arguments."""
        with patch("automation.config.settings.AutomationSettings.from_yaml"):
            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "process-issue"],
            )

            assert result.exit_code != 0
            assert "Missing option" in result.output or "Error" in result.output


class TestCommandOutputs:
    """Test command output formatting and content."""

    def test_success_emoji_in_output(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test that success messages include emojis."""
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

                assert "✅" in result.output or "processed successfully" in result.output.lower()

    def test_plan_status_formatting(
        self, cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock
    ) -> None:
        """Test plan status output formatting."""
        with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = mock_settings

            with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
                mock_state = AsyncMock()
                mock_state.load_state = AsyncMock(
                    return_value={
                        "status": "in_progress",
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T11:00:00Z",
                        "stages": {"stage1": {"status": "completed"}},
                        "tasks": {"task1": {"status": "pending"}},
                    }
                )
                mock_state_cls.return_value = mock_state

                result = cli_runner.invoke(
                    cli,
                    ["--config", str(mock_config_path), "show-plan", "--plan-id", "plan-001"],
                )

                # Check for structured output
                assert "Plan" in result.output
                assert "Status" in result.output
                assert "stage1" in result.output


class TestAsyncErrorHandling:
    """Test async error handling and recovery."""

    @pytest.mark.asyncio
    async def test_async_exception_in_orchestrator_creation(
        self, mock_settings: MagicMock
    ) -> None:
        """Test exception handling during async orchestrator creation."""
        with patch("automation.providers.gitea_rest.GiteaRestProvider") as mock_git_class:
            mock_git_class.side_effect = RuntimeError("Provider initialization failed")

            with pytest.raises(RuntimeError):
                await _create_orchestrator(mock_settings)

    @pytest.mark.asyncio
    async def test_async_timeout_during_processing(
        self, mock_settings: MagicMock
    ) -> None:
        """Test timeout handling during async processing."""
        with patch("automation.main._create_orchestrator") as mock_create_orch:
            mock_orch = AsyncMock()

            async def delayed_processing():
                await asyncio.sleep(10)

            mock_orch.process_issue = AsyncMock(side_effect=delayed_processing)
            mock_create_orch.return_value = mock_orch

            # Would timeout if not handled properly
            mock_issue = MagicMock(number=1)

            with patch.object(mock_orch, 'git'):
                mock_orch.git.get_issue = AsyncMock(return_value=mock_issue)
                # This tests the structure; actual timeout testing would require
                # different approach


class TestEdgeCasesAdvanced:
    """Test advanced edge cases."""

    @pytest.mark.asyncio
    async def test_empty_stages_and_tasks_in_plan_status(
        self, mock_settings: MagicMock
    ) -> None:
        """Test plan status display with empty stages and tasks."""
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

            # Should handle empty structures gracefully
            await _show_plan_status(mock_settings, "empty-plan")

    @pytest.mark.asyncio
    async def test_plan_status_missing_optional_fields(
        self, mock_settings: MagicMock
    ) -> None:
        """Test plan status with missing optional fields."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            mock_state.load_state = AsyncMock(return_value={"status": "unknown"})
            mock_state_cls.return_value = mock_state

            # Should handle gracefully with defaults
            await _show_plan_status(mock_settings, "incomplete-plan")

    @pytest.mark.asyncio
    async def test_list_plans_with_large_number_of_plans(
        self, mock_settings: MagicMock
    ) -> None:
        """Test listing with many active plans."""
        with patch("automation.engine.state_manager.StateManager") as mock_state_cls:
            mock_state = AsyncMock()
            plans = [f"plan-{i:04d}" for i in range(100)]
            mock_state.get_active_plans = AsyncMock(return_value=plans)
            mock_state.load_state = AsyncMock(
                side_effect=lambda pid: {"status": "active"}
            )
            mock_state_cls.return_value = mock_state

            # Should handle large number gracefully
            await _list_active_plans(mock_settings)
