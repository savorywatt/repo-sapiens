"""Pytest configuration and shared fixtures."""

from datetime import datetime
from pathlib import Path

import pytest

from automation.config.settings import AutomationSettings
from automation.engine.state_manager import StateManager
from automation.models.domain import Issue, IssueState, Plan, Task
from automation.utils.mcp_client import MockMCPClient


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def state_manager(temp_state_dir: Path) -> StateManager:
    """StateManager instance with temp directory."""
    return StateManager(str(temp_state_dir))


@pytest.fixture
def sample_issue() -> Issue:
    """Sample issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Implement user authentication",
        body="We need login, signup, and password reset functionality.",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="testuser",
        url="https://gitea.example.com/owner/repo/issues/42",
    )


@pytest.fixture
def sample_task() -> Task:
    """Sample task for testing."""
    return Task(
        id="task-1",
        prompt_issue_id=43,
        title="Create user model",
        description="Implement User model with authentication fields",
        dependencies=[],
        plan_id="42",
    )


@pytest.fixture
def sample_plan() -> Plan:
    """Sample plan for testing."""
    return Plan(
        id="42",
        title="User Authentication System",
        description="Complete authentication system",
        tasks=[],
        file_path="plans/42-user-authentication.md",
        created_at=datetime.now(),
    )


@pytest.fixture
def mock_settings(tmp_path: Path) -> AutomationSettings:
    """Mock settings for testing."""
    return AutomationSettings(
        git_provider={
            "provider_type": "gitea",
            "mcp_server": "test-mcp",
            "base_url": "https://gitea.test.com",
            "api_token": "test-token",
        },
        repository={
            "owner": "test-owner",
            "name": "test-repo",
            "default_branch": "main",
        },
        agent_provider={
            "provider_type": "claude-local",
            "model": "claude-sonnet-4.5",
            "api_key": "test-key",
            "local_mode": True,
        },
        workflow={
            "plans_directory": "plans/",
            "state_directory": str(tmp_path / "state"),
            "branching_strategy": "per-agent",
            "max_concurrent_tasks": 3,
        },
        tags={
            "needs_planning": "needs-planning",
            "plan_review": "plan-review",
            "ready_to_implement": "ready-to-implement",
            "in_progress": "in-progress",
            "code_review": "code-review",
            "merge_ready": "merge-ready",
            "completed": "completed",
            "needs_attention": "needs-attention",
        },
    )


@pytest.fixture
def mock_mcp_client() -> MockMCPClient:
    """Mock MCP client for testing."""
    responses = {
        "gitea_list_issues": {
            "issues": [
                {
                    "id": 1,
                    "number": 42,
                    "title": "Test Issue",
                    "body": "Test body",
                    "state": "open",
                    "labels": [{"name": "needs-planning"}],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "user": {"login": "testuser"},
                    "html_url": "https://gitea.test/issues/42",
                }
            ]
        },
        "gitea_create_issue": lambda args: {
            "id": 2,
            "number": 43,
            "title": args.get("title", "New Issue"),
            "body": args.get("body", ""),
            "state": "open",
            "labels": [{"name": label} for label in args.get("labels", [])],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user": {"login": "testuser"},
            "html_url": "https://gitea.test/issues/43",
        },
        "gitea_commit_file": {"sha": "abc123"},
    }

    return MockMCPClient("test-mcp", responses)


class MockTask:
    """Mock task for testing cost optimizer."""

    def __init__(
        self,
        description: str = "",
        dependencies: list = None,
        context: dict = None,
        task_id: str = "test-task",
    ):
        self.description = description
        self.dependencies = dependencies or []
        self.context = context or {}
        self.id = task_id


@pytest.fixture
def mock_task():
    """Factory fixture for creating mock tasks."""
    return MockTask
