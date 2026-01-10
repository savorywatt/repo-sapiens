"""Unit tests for label router module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import (
    AutomationConfig,
    AutomationModeConfig,
    LabelTriggerConfig,
    TriggerType,
)
from repo_sapiens.engine.event_classifier import ClassifiedEvent, EventSource
from repo_sapiens.engine.label_router import HANDLER_STAGE_MAP, LabelRouter
from repo_sapiens.models.domain import Issue, IssueState


@pytest.fixture
def mock_settings():
    """Create mock automation settings."""
    return AutomationSettings(
        git_provider={
            "provider_type": "gitea",
            "base_url": "https://gitea.example.com",
            "api_token": "test-token",
        },
        repository={
            "owner": "test-owner",
            "name": "test-repo",
        },
        agent_provider={
            "provider_type": "claude-local",
            "model": "claude-3-sonnet",
        },
        automation=AutomationConfig(
            mode=AutomationModeConfig(
                mode="hybrid",
                native_enabled=True,
            ),
            label_triggers={
                "needs-planning": LabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                    ai_enabled=True,
                    remove_on_complete=True,
                    success_label="proposed",
                    failure_label="needs-attention",
                ),
                "custom-task": LabelTriggerConfig(
                    label_pattern="custom-task",
                    handler="custom",
                    ai_enabled=True,
                    remove_on_complete=False,
                ),
            },
        ),
    )


@pytest.fixture
def mock_git():
    """Create mock Git provider."""
    git = MagicMock()
    git.get_issue = AsyncMock()
    git.update_issue = AsyncMock()
    git.add_comment = AsyncMock()
    return git


@pytest.fixture
def mock_orchestrator():
    """Create mock workflow orchestrator."""
    orchestrator = MagicMock()

    # Mock stages
    mock_stage = MagicMock()
    mock_stage.execute = AsyncMock()

    orchestrator.stages = {
        "proposal": mock_stage,
        "approval": mock_stage,
        "task_execution": mock_stage,
        "planning": mock_stage,
        "implementation": mock_stage,
        "code_review": mock_stage,
        "merge": mock_stage,
    }

    # Mock agent
    orchestrator.agent = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = "Task completed"
    mock_result.error = None
    mock_result.files_changed = ["file.py"]
    orchestrator.agent.execute_task = AsyncMock(return_value=mock_result)

    return orchestrator


@pytest.fixture
def sample_issue():
    """Create a sample issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Test issue",
        body="This is a test issue body",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="testuser",
        url="https://gitea.example.com/owner/repo/issues/42",
    )


@pytest.fixture
def classified_event():
    """Create a sample classified event."""
    return ClassifiedEvent(
        trigger_type=TriggerType.LABEL_ADDED,
        source=EventSource.GITEA,
        handler="proposal",
        config=LabelTriggerConfig(
            label_pattern="needs-planning",
            handler="proposal",
            ai_enabled=True,
            remove_on_complete=True,
            success_label="proposed",
            failure_label="needs-attention",
        ),
        issue_number=42,
        pr_number=None,
        label="needs-planning",
        raw_event={"action": "labeled"},
        should_process=True,
        skip_reason=None,
    )


class TestHandlerStageMap:
    """Tests for HANDLER_STAGE_MAP constant."""

    def test_contains_granular_stages(self):
        """Test that granular workflow stages are mapped."""
        assert "proposal" in HANDLER_STAGE_MAP
        assert "approval" in HANDLER_STAGE_MAP
        assert "task_execution" in HANDLER_STAGE_MAP
        assert "pr_review" in HANDLER_STAGE_MAP
        assert "pr_fix" in HANDLER_STAGE_MAP
        assert "fix_execution" in HANDLER_STAGE_MAP
        assert "qa" in HANDLER_STAGE_MAP

    def test_contains_legacy_stages(self):
        """Test that legacy workflow stages are mapped."""
        assert "planning" in HANDLER_STAGE_MAP
        assert "plan_review" in HANDLER_STAGE_MAP
        assert "implementation" in HANDLER_STAGE_MAP
        assert "code_review" in HANDLER_STAGE_MAP
        assert "merge" in HANDLER_STAGE_MAP

    def test_contains_specialized_handlers(self):
        """Test that specialized handlers are mapped."""
        assert "triage" in HANDLER_STAGE_MAP
        assert "security_review" in HANDLER_STAGE_MAP
        assert "docs_generation" in HANDLER_STAGE_MAP
        assert "test_coverage" in HANDLER_STAGE_MAP
        assert "dependency_audit" in HANDLER_STAGE_MAP


class TestLabelRouter:
    """Tests for LabelRouter class."""

    def test_initialization(self, mock_settings, mock_git, mock_orchestrator):
        """Test LabelRouter initialization."""
        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)

        assert router.settings == mock_settings
        assert router.git == mock_git
        assert router.orchestrator == mock_orchestrator

    @pytest.mark.asyncio
    async def test_route_skipped_event(self, mock_settings, mock_git, mock_orchestrator):
        """Test routing an event that should be skipped."""
        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)

        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITEA,
            handler=None,
            config=None,
            issue_number=42,
            pr_number=None,
            label="unknown",
            raw_event={},
            should_process=False,
            skip_reason="No handler configured",
        )

        result = await router.route(event)

        assert result["success"] is False
        assert result["skipped"] is True
        assert result["reason"] == "No handler configured"
        mock_git.get_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_with_stage_handler(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue, classified_event
    ):
        """Test routing to an existing workflow stage."""
        mock_git.get_issue.return_value = sample_issue
        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)

        result = await router.route(classified_event)

        assert result["success"] is True
        assert result["stage"] == "proposal"
        mock_git.get_issue.assert_called_once_with(42)
        mock_orchestrator.stages["proposal"].execute.assert_called_once_with(sample_issue)

    @pytest.mark.asyncio
    async def test_route_with_pr_number(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue
    ):
        """Test routing when event has PR number instead of issue number."""
        mock_git.get_issue.return_value = sample_issue

        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITHUB,
            handler="proposal",
            config=LabelTriggerConfig(
                label_pattern="needs-planning",
                handler="proposal",
            ),
            issue_number=None,
            pr_number=99,
            label="needs-planning",
            raw_event={},
            should_process=True,
            skip_reason=None,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router.route(event)

        mock_git.get_issue.assert_called_once_with(99)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_route_no_issue_or_pr(self, mock_settings, mock_git, mock_orchestrator):
        """Test routing fails when no issue or PR number."""
        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITEA,
            handler="proposal",
            config=LabelTriggerConfig(
                label_pattern="needs-planning",
                handler="proposal",
            ),
            issue_number=None,
            pr_number=None,
            label="needs-planning",
            raw_event={},
            should_process=True,
            skip_reason=None,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router.route(event)

        assert result["success"] is False
        assert "No issue or PR number" in result["error"]

    @pytest.mark.asyncio
    async def test_route_custom_handler_with_ai(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue
    ):
        """Test routing to custom AI handler."""
        mock_git.get_issue.return_value = sample_issue

        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITEA,
            handler="custom",  # Not in HANDLER_STAGE_MAP
            config=LabelTriggerConfig(
                label_pattern="custom-task",
                handler="custom",
                ai_enabled=True,
            ),
            issue_number=42,
            pr_number=None,
            label="custom-task",
            raw_event={},
            should_process=True,
            skip_reason=None,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router.route(event)

        assert result["success"] is True
        mock_orchestrator.agent.execute_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_unknown_handler(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue
    ):
        """Test routing to unknown handler without AI."""
        mock_git.get_issue.return_value = sample_issue

        event = ClassifiedEvent(
            trigger_type=TriggerType.LABEL_ADDED,
            source=EventSource.GITEA,
            handler="nonexistent",
            config=LabelTriggerConfig(
                label_pattern="unknown",
                handler="nonexistent",
                ai_enabled=False,  # AI disabled
            ),
            issue_number=42,
            pr_number=None,
            label="unknown",
            raw_event={},
            should_process=True,
            skip_reason=None,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router.route(event)

        assert result["success"] is False
        assert "Unknown handler" in result["error"]

    @pytest.mark.asyncio
    async def test_route_exception_handling(
        self, mock_settings, mock_git, mock_orchestrator, classified_event
    ):
        """Test routing handles exceptions gracefully."""
        mock_git.get_issue.side_effect = Exception("API error")

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router.route(classified_event)

        assert result["success"] is False
        assert "API error" in result["error"]


class TestPostProcessing:
    """Tests for post-processing methods."""

    @pytest.mark.asyncio
    async def test_post_process_success_removes_label(
        self, mock_settings, mock_git, mock_orchestrator
    ):
        """Test successful post-processing removes trigger label."""
        issue = Issue(
            id=1,
            number=42,
            title="Test",
            body="Body",
            state=IssueState.OPEN,
            labels=["needs-planning", "other"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
            url="https://example.com",
        )

        config = LabelTriggerConfig(
            label_pattern="needs-planning",
            handler="proposal",
            remove_on_complete=True,
            success_label="proposed",
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        await router._post_process_success(issue, config)

        mock_git.update_issue.assert_called_once()
        call_args = mock_git.update_issue.call_args
        assert "needs-planning" not in call_args.kwargs["labels"]
        assert "proposed" in call_args.kwargs["labels"]

    @pytest.mark.asyncio
    async def test_post_process_success_no_label_change(
        self, mock_settings, mock_git, mock_orchestrator
    ):
        """Test post-processing when no label changes needed."""
        issue = Issue(
            id=1,
            number=42,
            title="Test",
            body="Body",
            state=IssueState.OPEN,
            labels=["proposed"],  # Already has success label, no trigger label
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
            url="https://example.com",
        )

        config = LabelTriggerConfig(
            label_pattern="needs-planning",
            handler="proposal",
            remove_on_complete=True,
            success_label="proposed",
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        await router._post_process_success(issue, config)

        # No update needed when labels already match desired state
        mock_git.update_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_process_failure_adds_label_and_comment(
        self, mock_settings, mock_git, mock_orchestrator
    ):
        """Test failure post-processing adds label and comment."""
        issue = Issue(
            id=1,
            number=42,
            title="Test",
            body="Body",
            state=IssueState.OPEN,
            labels=["needs-planning"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
            url="https://example.com",
        )

        config = LabelTriggerConfig(
            label_pattern="needs-planning",
            handler="proposal",
            failure_label="needs-attention",
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        await router._post_process_failure(issue, config, "Task failed")

        mock_git.update_issue.assert_called_once()
        call_args = mock_git.update_issue.call_args
        assert "needs-attention" in call_args.kwargs["labels"]

        mock_git.add_comment.assert_called_once()
        comment_call = mock_git.add_comment.call_args
        assert "Task failed" in comment_call.args[1]


class TestExecuteHandler:
    """Tests for _execute_handler method."""

    @pytest.mark.asyncio
    async def test_execute_known_stage(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue, classified_event
    ):
        """Test executing a known workflow stage."""
        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)

        result = await router._execute_handler(
            handler="proposal",
            config=classified_event.config,
            issue=sample_issue,
            event=classified_event,
        )

        assert result["success"] is True
        assert result["stage"] == "proposal"
        mock_orchestrator.stages["proposal"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ai_task(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue, classified_event
    ):
        """Test executing an AI task for custom handler."""
        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)

        config = LabelTriggerConfig(
            label_pattern="custom",
            handler="custom",
            ai_enabled=True,
        )

        result = await router._execute_handler(
            handler="custom",
            config=config,
            issue=sample_issue,
            event=classified_event,
        )

        assert result["success"] is True
        mock_orchestrator.agent.execute_task.assert_called_once()


class TestExecuteAITask:
    """Tests for _execute_ai_task method."""

    @pytest.mark.asyncio
    async def test_execute_ai_task_success(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue
    ):
        """Test successful AI task execution."""
        config = LabelTriggerConfig(
            label_pattern="custom",
            handler="custom",
            ai_enabled=True,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router._execute_ai_task("custom", sample_issue, config)

        assert result["success"] is True
        assert result["output"] == "Task completed"
        assert result["files_changed"] == ["file.py"]

        # Verify task was created correctly
        task_call = mock_orchestrator.agent.execute_task.call_args
        task = task_call.args[0]
        assert f"#{sample_issue.number}" in task.title
        assert "custom" in task.description

    @pytest.mark.asyncio
    async def test_execute_ai_task_failure(
        self, mock_settings, mock_git, mock_orchestrator, sample_issue
    ):
        """Test failed AI task execution."""
        # Configure agent to return failure
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.output = None
        mock_result.error = "Task execution failed"
        mock_result.files_changed = []
        mock_orchestrator.agent.execute_task.return_value = mock_result

        config = LabelTriggerConfig(
            label_pattern="custom",
            handler="custom",
            ai_enabled=True,
        )

        router = LabelRouter(mock_settings, mock_git, mock_orchestrator)
        result = await router._execute_ai_task("custom", sample_issue, config)

        assert result["success"] is False
        assert result["error"] == "Task execution failed"
