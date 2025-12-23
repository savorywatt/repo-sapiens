"""Helper utilities and custom assertions for CLI tests."""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock


def create_mock_settings(**kwargs: Any) -> MagicMock:
    """Create a mock AutomationSettings object with customizable attributes.

    Args:
        **kwargs: Custom settings to override defaults

    Returns:
        MagicMock configured as AutomationSettings

    Example:
        settings = create_mock_settings(
            git_provider_base_url="http://custom:3000"
        )
    """
    settings = MagicMock()

    # Git provider config
    settings.git_provider.provider_type = kwargs.get("git_provider_type", "gitea")
    settings.git_provider.base_url = kwargs.get("git_provider_base_url", "http://localhost:3000")
    settings.git_provider.api_token.get_secret_value.return_value = kwargs.get(
        "git_api_token", "test_token"
    )

    # Repository config
    settings.repository.owner = kwargs.get("repo_owner", "test_owner")
    settings.repository.name = kwargs.get("repo_name", "test_repo")

    # Agent provider config
    settings.agent_provider.provider_type = kwargs.get("agent_provider_type", "external")
    settings.agent_provider.model = kwargs.get("agent_model", "claude-opus-4.5-20251101")
    settings.agent_provider.base_url = kwargs.get("agent_base_url", "http://localhost")

    # State config
    settings.state_dir = kwargs.get("state_dir", "/tmp/state")
    settings.default_poll_interval = kwargs.get("poll_interval", 60)

    return settings


def create_mock_issue(
    number: int = 1,
    title: str = "Test Issue",
    **kwargs: Any
) -> MagicMock:
    """Create a mock Issue object.

    Args:
        number: Issue number
        title: Issue title
        **kwargs: Additional attributes

    Returns:
        MagicMock configured as Issue

    Example:
        issue = create_mock_issue(number=42, title="Bug Report")
    """
    issue = MagicMock()
    issue.number = number
    issue.title = title

    for key, value in kwargs.items():
        setattr(issue, key, value)

    return issue


def create_mock_plan_state(
    status: str = "pending",
    stages: Optional[Dict[str, Dict[str, str]]] = None,
    tasks: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Create a mock plan state dictionary.

    Args:
        status: Plan status
        stages: Dictionary of stage statuses
        tasks: Dictionary of task statuses

    Returns:
        Dictionary representing plan state

    Example:
        state = create_mock_plan_state(
            status="in_progress",
            stages={"analysis": {"status": "completed"}},
            tasks={"task1": {"status": "pending"}}
        )
    """
    return {
        "status": status,
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T11:00:00Z",
        "stages": stages or {},
        "tasks": tasks or {},
    }


def create_mock_orchestrator() -> AsyncMock:
    """Create a fully mocked WorkflowOrchestrator.

    Returns:
        AsyncMock configured as WorkflowOrchestrator

    Example:
        orch = create_mock_orchestrator()
        orch.process_issue = AsyncMock()
    """
    orchestrator = AsyncMock()

    # Mock main methods
    orchestrator.process_issue = AsyncMock()
    orchestrator.process_all_issues = AsyncMock()
    orchestrator.process_plan = AsyncMock()

    # Mock git provider
    orchestrator.git = AsyncMock()
    orchestrator.git.get_issue = AsyncMock()
    orchestrator.git.list_issues = AsyncMock()
    orchestrator.git.connect = AsyncMock()

    # Mock agent provider
    orchestrator.agent = AsyncMock()
    orchestrator.agent.connect = AsyncMock()

    # Mock state manager
    orchestrator.state = AsyncMock()
    orchestrator.state.get_active_plans = AsyncMock()
    orchestrator.state.load_state = AsyncMock()

    return orchestrator


def create_mock_state_manager(plans: Optional[list] = None) -> AsyncMock:
    """Create a mocked StateManager.

    Args:
        plans: List of active plan IDs

    Returns:
        AsyncMock configured as StateManager

    Example:
        state = create_mock_state_manager(plans=["plan-1", "plan-2"])
    """
    manager = AsyncMock()
    manager.get_active_plans = AsyncMock(return_value=plans or [])
    manager.load_state = AsyncMock()
    manager.save_state = AsyncMock()

    return manager


def assert_successful_exit(result: Any) -> None:
    """Assert that a CLI result indicates success.

    Args:
        result: Click CLI test result

    Raises:
        AssertionError: If exit code is not 0

    Example:
        result = runner.invoke(cli, ["list-plans"])
        assert_successful_exit(result)
    """
    assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}: {result.output}"


def assert_failed_exit(result: Any) -> None:
    """Assert that a CLI result indicates failure.

    Args:
        result: Click CLI test result

    Raises:
        AssertionError: If exit code is 0

    Example:
        result = runner.invoke(cli, ["--config", "/nonexistent", "list-plans"])
        assert_failed_exit(result)
    """
    assert result.exit_code != 0, f"Command succeeded unexpectedly: {result.output}"


def assert_output_contains(result: Any, *texts: str) -> None:
    """Assert that output contains all specified texts.

    Args:
        result: Click CLI test result
        *texts: Texts that should appear in output

    Raises:
        AssertionError: If any text is missing from output

    Example:
        result = runner.invoke(cli, ["list-plans"])
        assert_output_contains(result, "Active Plans", "plan-001")
    """
    for text in texts:
        assert text in result.output, f"Output missing '{text}':\n{result.output}"


def assert_output_not_contains(result: Any, *texts: str) -> None:
    """Assert that output does not contain specified texts.

    Args:
        result: Click CLI test result
        *texts: Texts that should not appear in output

    Raises:
        AssertionError: If any text is found in output

    Example:
        result = runner.invoke(cli, ["list-plans"])
        assert_output_not_contains(result, "Error", "Failed")
    """
    for text in texts:
        assert text not in result.output, f"Output unexpectedly contains '{text}':\n{result.output}"


def assert_help_output(result: Any) -> None:
    """Assert that output is valid help text.

    Args:
        result: Click CLI test result

    Raises:
        AssertionError: If output doesn't look like help text

    Example:
        result = runner.invoke(cli, ["--help"])
        assert_help_output(result)
    """
    assert_successful_exit(result)
    assert_output_contains(result, "Usage:", "Options:")


def create_mock_git_provider() -> AsyncMock:
    """Create a mocked Git provider.

    Returns:
        AsyncMock configured as GiteaRestProvider or similar

    Example:
        git = create_mock_git_provider()
        git.get_issue = AsyncMock(return_value=issue)
    """
    provider = AsyncMock()

    # Mock connection
    provider.connect = AsyncMock()
    provider.disconnect = AsyncMock()

    # Mock issue operations
    provider.get_issue = AsyncMock()
    provider.list_issues = AsyncMock(return_value=[])
    provider.update_issue = AsyncMock()
    provider.comment_issue = AsyncMock()

    # Mock branch operations
    provider.create_branch = AsyncMock()
    provider.delete_branch = AsyncMock()
    provider.list_branches = AsyncMock(return_value=[])

    # Mock file operations
    provider.get_file = AsyncMock()
    provider.update_file = AsyncMock()
    provider.create_file = AsyncMock()

    return provider


def create_mock_agent_provider() -> AsyncMock:
    """Create a mocked Agent provider.

    Returns:
        AsyncMock configured as ExternalAgentProvider or OllamaProvider

    Example:
        agent = create_mock_agent_provider()
        agent.execute = AsyncMock(return_value="result")
    """
    provider = AsyncMock()

    # Mock connection
    provider.connect = AsyncMock()
    provider.disconnect = AsyncMock()

    # Mock execution
    provider.execute = AsyncMock()
    provider.execute_plan = AsyncMock()
    provider.ask_question = AsyncMock()
    provider.get_status = AsyncMock(return_value="ready")

    return provider


def format_mock_call_info(mock: Any) -> str:
    """Format mock call information for debugging.

    Args:
        mock: A mock object

    Returns:
        Formatted string of call information

    Example:
        print(format_mock_call_info(mock_orch.process_issue))
    """
    if not mock.called:
        return "Mock was never called"

    info = f"Called {mock.call_count} time(s)\n"
    info += "Call args:\n"

    for i, call in enumerate(mock.call_args_list, 1):
        info += f"  {i}. args={call[0]}, kwargs={call[1]}\n"

    return info
