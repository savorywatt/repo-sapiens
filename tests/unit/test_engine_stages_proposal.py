"""Unit tests for ProposalStage.

This module provides comprehensive tests for repo_sapiens/engine/stages/proposal.py
targeting >50% coverage.

Tested areas:
- ProposalStage initialization
- execute method (happy path and error cases)
- _format_plan_markdown helper
- _format_proposal_body helper
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.stages.proposal import ProposalStage
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.models.domain import (
    Comment,
    Issue,
    IssueState,
    Plan,
    Task,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_git_provider():
    """Create a mock GitProvider with all required methods."""
    mock = AsyncMock()

    mock.get_comments.return_value = []
    mock.add_comment.return_value = Comment(
        id=1,
        body="Test comment",
        author="bot",
        created_at=datetime.now(UTC),
    )
    mock.update_issue.return_value = None
    mock.create_issue.return_value = Issue(
        id=100,
        number=100,
        title="[PROPOSAL] Plan for #42: Test Feature",
        body="Proposal body",
        state=IssueState.OPEN,
        labels=["proposed", "plan-for-42"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="bot",
        url="https://gitea.test/issues/100",
    )
    mock.commit_file.return_value = "commit-sha-123"

    return mock


@pytest.fixture
def mock_agent_provider():
    """Create a mock AgentProvider with all required methods."""
    mock = AsyncMock()

    mock.generate_plan.return_value = Plan(
        id="plan-42",
        title="Test Plan",
        description="A comprehensive plan for implementing the feature.",
        tasks=[
            Task(
                id="task-1",
                prompt_issue_id=42,
                title="Setup project structure",
                description="Create the initial project layout",
                dependencies=[],
            ),
            Task(
                id="task-2",
                prompt_issue_id=42,
                title="Implement core logic",
                description="Build the main functionality",
                dependencies=["task-1"],
            ),
        ],
        file_path="plans/42-test-feature.md",
        created_at=datetime.now(UTC),
    )

    mock.working_dir = "/tmp/workspace"

    return mock


@pytest.fixture
def mock_state_manager(tmp_path):
    """Create a mock StateManager."""
    mock = AsyncMock(spec=StateManager)

    mock.load_state.return_value = {
        "plan_id": "42",
        "status": "in_progress",
        "tasks": {},
        "stages": {},
    }
    mock.save_state.return_value = None
    mock.mark_stage_complete.return_value = None

    return mock


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock AutomationSettings."""
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
            "api_key": "test-key",  # pragma: allowlist secret
            "local_mode": True,
        },
        workflow={
            "plans_directory": str(tmp_path / "plans"),
            "state_directory": str(tmp_path / "state"),
            "branching_strategy": "per-agent",
            "max_concurrent_tasks": 3,
            "review_approval_threshold": 0.8,
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
def open_issue():
    """Create an open issue for testing."""
    return Issue(
        id=42,
        number=42,
        title="Test Feature",
        body="Implement a new test feature with comprehensive testing.",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/42",
    )


# ==============================================================================
# ProposalStage Initialization Tests
# ==============================================================================


class TestProposalStageInitialization:
    """Tests for ProposalStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly with all required providers."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider
        assert stage.state is mock_state_manager
        assert stage.settings is mock_settings

    def test_inherits_from_workflow_stage(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test that ProposalStage inherits from WorkflowStage."""
        from repo_sapiens.engine.stages.base import WorkflowStage

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert isinstance(stage, WorkflowStage)


# ==============================================================================
# ProposalStage.execute Tests
# ==============================================================================


class TestProposalStageExecute:
    """Tests for ProposalStage.execute method."""

    @pytest.mark.asyncio
    async def test_execute_success_full_flow(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test successful execution of proposal stage."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Should notify user at start
        first_comment = mock_git_provider.add_comment.call_args_list[0]
        assert "Generating Plan Proposal" in first_comment.args[1]

        # Should generate plan
        mock_agent_provider.generate_plan.assert_called_once_with(open_issue)

        # Should create proposal issue
        mock_git_provider.create_issue.assert_called_once()
        create_call = mock_git_provider.create_issue.call_args
        assert "[PROPOSAL]" in create_call.kwargs["title"]
        assert "#42" in create_call.kwargs["title"]
        assert "proposed" in create_call.kwargs["labels"]

        # Should comment on original issue with proposal link
        comment_calls = mock_git_provider.add_comment.call_args_list
        proposal_comment = comment_calls[1]
        assert "Plan Proposal Created" in proposal_comment.args[1]
        assert "#100" in proposal_comment.args[1]

        # Should update original issue labels
        mock_git_provider.update_issue.assert_called_once()
        update_call = mock_git_provider.update_issue.call_args
        assert "awaiting-approval" in update_call.kwargs["labels"]
        assert "needs-planning" not in update_call.kwargs["labels"]

    @pytest.mark.asyncio
    async def test_execute_plan_without_file_path(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test execution when plan has no file_path - should use fallback."""
        plan_without_path = Plan(
            id="plan-42",
            title="Test Plan",
            description="A plan description",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="Task 1",
                    description="First task",
                    dependencies=[],
                ),
            ],
            file_path=None,  # No file path
            created_at=datetime.now(UTC),
        )
        mock_agent_provider.generate_plan.return_value = plan_without_path

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Should still succeed and create proposal
        mock_git_provider.create_issue.assert_called_once()

        # The plan should now have a generated file_path
        assert plan_without_path.file_path is not None
        assert "plans/" in plan_without_path.file_path
        assert "42" in plan_without_path.file_path

    @pytest.mark.asyncio
    async def test_execute_plan_generation_failure(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test that plan generation failure is handled properly."""
        mock_agent_provider.generate_plan.side_effect = Exception("AI service unavailable")

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception, match="AI service unavailable"):
            await stage.execute(open_issue)

        # Should post failure comment
        comment_calls = mock_git_provider.add_comment.call_args_list
        failure_comment = comment_calls[-1]
        assert "Plan Generation Failed" in failure_comment.args[1]
        assert "AI service unavailable" in failure_comment.args[1]

    @pytest.mark.asyncio
    async def test_execute_issue_creation_failure(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test handling when proposal issue creation fails."""
        mock_git_provider.create_issue.side_effect = Exception("API rate limit exceeded")

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception, match="API rate limit exceeded"):
            await stage.execute(open_issue)

        # Should post failure comment
        comment_calls = mock_git_provider.add_comment.call_args_list
        failure_comment = comment_calls[-1]
        assert "Plan Generation Failed" in failure_comment.args[1]

    @pytest.mark.asyncio
    async def test_execute_removes_needs_planning_label(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test that needs-planning label is removed from original issue."""
        issue_with_multiple_labels = Issue(
            id=42,
            number=42,
            title="Test Feature",
            body="Test body",
            state=IssueState.OPEN,
            labels=["needs-planning", "enhancement", "priority-high"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue_with_multiple_labels)

        update_call = mock_git_provider.update_issue.call_args
        updated_labels = update_call.kwargs["labels"]

        assert "needs-planning" not in updated_labels
        assert "enhancement" in updated_labels
        assert "priority-high" in updated_labels
        assert "awaiting-approval" in updated_labels


# ==============================================================================
# ProposalStage._format_plan_markdown Tests
# ==============================================================================


class TestFormatPlanMarkdown:
    """Tests for ProposalStage._format_plan_markdown method."""

    def test_format_plan_basic(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test basic plan formatting."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="My Test Plan",
            description="This is the plan description.",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        result = stage._format_plan_markdown(plan, open_issue)

        assert "# Plan: My Test Plan" in result
        assert "**Issue**: #42" in result
        assert "## Overview" in result
        assert "This is the plan description." in result

    def test_format_plan_with_tasks(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test plan formatting with tasks."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="First Task",
                    description="Do the first thing",
                    dependencies=[],
                ),
                Task(
                    id="task-2",
                    prompt_issue_id=42,
                    title="Second Task",
                    description="Do the second thing",
                    dependencies=["task-1"],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_plan_markdown(plan, open_issue)

        assert "## Tasks" in result
        assert "### Task 1: First Task" in result
        assert "**ID**: task-1" in result
        assert "Do the first thing" in result
        assert "### Task 2: Second Task" in result
        assert "**ID**: task-2" in result
        assert "task-1" in result  # Dependency

    def test_format_plan_task_without_dependencies(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test task formatting when task has no dependencies."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="Independent Task",
                    description="No dependencies",
                    dependencies=[],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_plan_markdown(plan, open_issue)

        assert "**Dependencies**: None" in result

    def test_format_plan_task_with_multiple_dependencies(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test task formatting with multiple dependencies."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-3",
                    prompt_issue_id=42,
                    title="Complex Task",
                    description="Depends on multiple tasks",
                    dependencies=["task-1", "task-2"],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_plan_markdown(plan, open_issue)

        assert "task-1, task-2" in result

    def test_format_plan_without_created_at(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test plan formatting when plan lacks created_at attribute."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        # Create a plan-like object without created_at
        class PlanWithoutCreatedAt:
            id = "plan-42"
            title = "Test Plan"
            description = "Overview"
            tasks = []
            file_path = None

        plan = PlanWithoutCreatedAt()
        result = stage._format_plan_markdown(plan, open_issue)

        assert "**Created**: now" in result


# ==============================================================================
# ProposalStage._format_proposal_body Tests
# ==============================================================================


class TestFormatProposalBody:
    """Tests for ProposalStage._format_proposal_body method."""

    def test_format_proposal_body_basic(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test basic proposal body formatting."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Plan description here.",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        result = stage._format_proposal_body(plan, open_issue, "plans/42-test.md")

        assert "# Development Plan Proposal" in result
        assert "**Original Issue**: [#42]" in result
        assert "Test Feature" in result  # Issue title
        assert "**Plan File**: `plans/42-test.md`" in result
        assert "**Blocks**: #42" in result
        assert "## Plan Overview" in result
        assert "Plan description here." in result
        assert "## Approval" in result
        assert "`ok`" in result
        assert "`approve`" in result
        assert "`lgtm`" in result

    def test_format_proposal_body_with_tasks(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test proposal body formatting with tasks."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="Setup",
                    description="Initial setup",
                    dependencies=[],
                ),
                Task(
                    id="task-2",
                    prompt_issue_id=42,
                    title="Implement",
                    description="Main implementation",
                    dependencies=["task-1"],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_proposal_body(plan, open_issue, "plans/42.md")

        assert "## Proposed Tasks" in result
        assert "### 1. Setup" in result
        assert "Initial setup" in result
        assert "### 2. Implement (requires: task-1)" in result
        assert "Main implementation" in result

    def test_format_proposal_body_task_no_dependencies(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test proposal body task without dependencies has no requires clause."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="Independent Task",
                    description="No deps",
                    dependencies=[],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_proposal_body(plan, open_issue, "plans/42.md")

        # Task 1 should not have (requires: ...) suffix
        assert "### 1. Independent Task\n" in result
        assert "(requires:" not in result.split("### 1. Independent Task")[1].split("\n")[0]

    def test_format_proposal_body_includes_automation_footer(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test that proposal body includes automation footer."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        result = stage._format_proposal_body(plan, open_issue, "plans/42.md")

        assert "Posted by Builder Automation" in result

    def test_format_proposal_body_approval_instructions(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test that proposal body includes approval instructions."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        result = stage._format_proposal_body(plan, open_issue, "plans/42.md")

        assert "**To approve this plan:**" in result
        assert "**Once approved, I will:**" in result
        assert "Create a project board" in result
        assert "Create individual task issues" in result
        assert "Link all tasks to the original issue" in result
        assert "mark tasks as `execute`" in result


# ==============================================================================
# Edge Cases and Error Scenarios
# ==============================================================================


class TestProposalStageEdgeCases:
    """Tests for edge cases in ProposalStage."""

    @pytest.mark.asyncio
    async def test_execute_with_empty_plan_description(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test execution when plan has empty description."""
        plan_with_empty_desc = Plan(
            id="plan-42",
            title="Empty Plan",
            description="",
            tasks=[],
            created_at=datetime.now(UTC),
        )
        mock_agent_provider.generate_plan.return_value = plan_with_empty_desc

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Should still succeed
        mock_git_provider.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_special_characters_in_title(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test execution with special characters in issue title."""
        issue_with_special_chars = Issue(
            id=42,
            number=42,
            title="Feature: Add @mentions & #hashtags support!",
            body="Test body",
            state=IssueState.OPEN,
            labels=["needs-planning"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue_with_special_chars)

        create_call = mock_git_provider.create_issue.call_args
        assert "@mentions" in create_call.kwargs["title"] or "mentions" in create_call.kwargs["title"]

    @pytest.mark.asyncio
    async def test_execute_label_includes_issue_number(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test that proposal issue includes plan-for-{issue_number} label."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        create_call = mock_git_provider.create_issue.call_args
        labels = create_call.kwargs["labels"]

        assert "plan-for-42" in labels

    def test_format_plan_markdown_preserves_multiline_descriptions(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings, open_issue
    ):
        """Test that multiline task descriptions are preserved."""
        stage = ProposalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Overview",
            tasks=[
                Task(
                    id="task-1",
                    prompt_issue_id=42,
                    title="Complex Task",
                    description="Line 1\nLine 2\nLine 3",
                    dependencies=[],
                ),
            ],
            created_at=datetime.now(UTC),
        )

        result = stage._format_plan_markdown(plan, open_issue)

        assert "Line 1\nLine 2\nLine 3" in result
