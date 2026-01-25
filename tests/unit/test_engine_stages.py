"""Comprehensive unit tests for engine stages.

This module provides tests for:
- ApprovalStage
- CodeReviewStage
- TaskExecutionStage
- PlanningStage
- QAStage

Each stage is tested for:
1. Stage initialization
2. Execute methods (happy path and edge cases)
3. State transitions
4. Error handling
5. Integration with providers (mocked)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.stages.approval import ApprovalStage
from repo_sapiens.engine.stages.code_review import CodeReviewStage
from repo_sapiens.engine.stages.execution import TaskExecutionStage
from repo_sapiens.engine.stages.planning import PlanningStage
from repo_sapiens.engine.stages.qa import QAStage
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.models.domain import (
    Branch,
    Comment,
    Issue,
    IssueState,
    Plan,
    PullRequest,
    Review,
    Task,
    TaskResult,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_git_provider():
    """Create a mock GitProvider with all required methods."""
    mock = AsyncMock()

    # Default return values for common operations
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
        title="Created Issue",
        body="Body",
        state=IssueState.OPEN,
        labels=["task"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="bot",
        url="https://gitea.test/issues/100",
    )
    mock.get_issue.return_value = Issue(
        id=42,
        number=42,
        title="Original Issue",
        body="Original body",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/42",
    )
    mock.create_branch.return_value = Branch(
        name="feature-branch",
        sha="abc123",
        protected=False,
    )
    mock.get_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
    mock.create_pull_request.return_value = PullRequest(
        id=1,
        number=10,
        title="Test PR",
        body="PR body",
        head="feature-branch",
        base="main",
        state="open",
        url="https://gitea.test/pulls/10",
        created_at=datetime.now(UTC),
        mergeable=True,
        merged=False,
    )
    mock.commit_file.return_value = "commit-sha-123"
    mock.get_pull_request.return_value = PullRequest(
        id=1,
        number=10,
        title="Test PR",
        body="PR body",
        head="feature-branch",
        base="main",
        state="open",
        url="https://gitea.test/pulls/10",
        created_at=datetime.now(UTC),
    )
    mock.get_issues.return_value = []

    return mock


@pytest.fixture
def mock_agent_provider():
    """Create a mock AgentProvider with all required methods."""
    mock = AsyncMock()

    # Default return values
    mock.generate_plan.return_value = Plan(
        id="plan-42",
        title="Test Plan",
        description="A comprehensive plan",
        tasks=[
            Task(
                id="task-1",
                prompt_issue_id=42,
                title="Task 1",
                description="First task",
                dependencies=[],
            ),
        ],
        file_path="plans/42-test-plan.md",
        created_at=datetime.now(UTC),
    )

    mock.review_code.return_value = Review(
        approved=True,
        comments=["Good implementation"],
        issues_found=[],
        suggestions=["Consider adding tests"],
        confidence_score=0.95,
    )

    mock.execute_task.return_value = TaskResult(
        success=True,
        branch="feature-branch",
        commits=["abc123"],
        files_changed=["file.py"],
        error=None,
        execution_time=10.5,
        output="Task completed successfully",
    )

    mock.execute_prompt = AsyncMock(return_value={"success": True, "output": "Tests created"})

    # Add working_dir attribute for execution stage
    mock.working_dir = "/tmp/workspace"

    return mock


@pytest.fixture
def mock_state_manager(tmp_path):
    """Create a mock StateManager."""
    mock = AsyncMock(spec=StateManager)

    # Default state for load_state
    mock.load_state.return_value = {
        "plan_id": "42",
        "status": "in_progress",
        "tasks": {
            "task-1": {
                "status": "pending",
                "branch": "feature/task-1",
            }
        },
        "stages": {},
    }

    mock.save_state.return_value = None
    mock.mark_stage_complete.return_value = None
    mock.mark_task_status.return_value = None

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
            "api_key": "test-key",
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
        title="Test Issue",
        body="Issue body content",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/42",
    )


@pytest.fixture
def closed_issue():
    """Create a closed issue for testing."""
    return Issue(
        id=42,
        number=42,
        title="Test Issue",
        body="Issue body content",
        state=IssueState.CLOSED,
        labels=["completed"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/42",
    )


# ==============================================================================
# ApprovalStage Tests
# ==============================================================================


class TestApprovalStageInitialization:
    """Tests for ApprovalStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly with all required providers."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider
        assert stage.state is mock_state_manager
        assert stage.settings is mock_settings

    def test_approval_keywords_defined(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test that approval keywords are properly defined."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        expected_keywords = ["ok", "approve", "approved", "lgtm", "looks good"]
        assert expected_keywords == stage.APPROVAL_KEYWORDS


class TestApprovalStageExecute:
    """Tests for ApprovalStage.execute method."""

    @pytest.mark.asyncio
    async def test_skip_already_closed_issue(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        closed_issue,
    ):
        """Test that closed issues are skipped."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(closed_issue)

        # Should not get comments if already closed
        mock_git_provider.get_comments.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_approval_no_action(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that issues without approval comments are not processed."""
        issue = Issue(
            id=50,
            number=50,
            title="[PROPOSAL] Plan for #42: Test",
            body="Proposal body",
            state=IssueState.OPEN,
            labels=["proposal"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        # No approval comments
        mock_git_provider.get_comments.return_value = [
            Comment(
                id=1,
                body="This needs more details",
                author="reviewer",
                created_at=datetime.now(UTC),
            )
        ]

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should only get comments, not create anything
        mock_git_provider.get_comments.assert_called_once_with(50)
        mock_git_provider.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_approval_via_label(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test approval detection via approved label."""
        issue = Issue(
            id=50,
            number=50,
            title="[PROPOSAL] Plan for #42: Test Feature",
            body="""## Plan Overview

### 1. Implement feature
Description of task 1

### 2. Add tests
Description of task 2
""",
            state=IssueState.OPEN,
            labels=["proposal", "approved"],  # Has approved label
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        mock_git_provider.get_comments.return_value = []

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should process approval
        assert mock_git_provider.add_comment.called
        assert mock_git_provider.create_issue.called

    @pytest.mark.asyncio
    async def test_approval_via_comment(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test approval detection via comment keyword."""
        issue = Issue(
            id=50,
            number=50,
            title="[PROPOSAL] Plan for #42: Test Feature",
            body="""## Plan Overview

### 1. Implement feature
Description of task 1
""",
            state=IssueState.OPEN,
            labels=["proposal"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        # Approval comment present
        mock_git_provider.get_comments.return_value = [
            Comment(
                id=1,
                body="lgtm",
                author="approver",
                created_at=datetime.now(UTC),
            )
        ]

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should process approval and create tasks
        assert mock_git_provider.add_comment.called
        assert mock_git_provider.create_issue.called

    @pytest.mark.asyncio
    async def test_bot_comment_ignored(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that bot comments are ignored for approval detection."""
        issue = Issue(
            id=50,
            number=50,
            title="[PROPOSAL] Plan for #42: Test Feature",
            body="Proposal body",
            state=IssueState.OPEN,
            labels=["proposal"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        # Bot comment with approval keyword
        mock_git_provider.get_comments.return_value = [
            Comment(
                id=1,
                body="ok, this looks good\n\n◆ Posted by Sapiens Automation",
                author="bot",
                created_at=datetime.now(UTC),
            )
        ]

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should not create issues since bot comment is ignored
        mock_git_provider.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_cannot_parse_original_issue(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test handling when original issue number cannot be parsed."""
        issue = Issue(
            id=50,
            number=50,
            title="Invalid Title Without Issue Number",  # No #number
            body="Proposal body",
            state=IssueState.OPEN,
            labels=["proposal", "approved"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        mock_git_provider.get_comments.return_value = []

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should not create anything if title cannot be parsed
        mock_git_provider.create_issue.assert_not_called()


class TestApprovalStageHelperMethods:
    """Tests for ApprovalStage helper methods."""

    def test_is_bot_comment_true(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test bot comment detection returns True for bot comments."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage._is_bot_comment("Some text\n\n◆ Posted by Sapiens Automation")
        assert stage._is_bot_comment("◆ Posted by Sapiens Automation")

    def test_is_bot_comment_false(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test bot comment detection returns False for non-bot comments."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert not stage._is_bot_comment("Regular comment")
        assert not stage._is_bot_comment("lgtm")

    def test_parse_tasks_from_plan(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test parsing tasks from plan content."""
        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = """## Plan Overview

### 1. Setup project structure
Create the initial project layout

### 2. Implement core logic (requires: Task 1)
Build the main functionality

### 3. Add tests (requires: Task 1, Task 2)
Write comprehensive tests
"""

        tasks = stage._parse_tasks_from_plan("", body)

        assert len(tasks) == 3
        assert tasks[0]["number"] == 1
        assert tasks[0]["title"] == "Setup project structure"
        assert tasks[0]["dependencies"] == []
        assert tasks[1]["number"] == 2
        assert "Task 1" in tasks[1]["dependencies"]
        assert tasks[2]["number"] == 3
        assert len(tasks[2]["dependencies"]) == 2


class TestApprovalStageErrorHandling:
    """Tests for ApprovalStage error handling."""

    @pytest.mark.asyncio
    async def test_error_posts_failure_comment(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that errors result in failure comment being posted."""
        issue = Issue(
            id=50,
            number=50,
            title="[PROPOSAL] Plan for #42: Test Feature",
            body="Proposal body",
            state=IssueState.OPEN,
            labels=["proposal", "approved"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/50",
        )

        mock_git_provider.get_comments.return_value = []
        mock_git_provider.get_issue.side_effect = Exception("API Error")

        stage = ApprovalStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception, match="API Error"):
            await stage.execute(issue)

        # Check that failure comment was posted
        calls = mock_git_provider.add_comment.call_args_list
        assert any("Failed" in str(call) for call in calls)


# ==============================================================================
# CodeReviewStage Tests
# ==============================================================================


class TestCodeReviewStageInitialization:
    """Tests for CodeReviewStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly."""
        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider


class TestCodeReviewStageExecute:
    """Tests for CodeReviewStage.execute method."""

    @pytest.mark.asyncio
    async def test_successful_review_approved(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test successful code review with approval."""
        issue = Issue(
            id=43,
            number=43,
            title="[Implement] User authentication",
            body="Task ID: task-1\nPart of plan #42",
            state=IssueState.OPEN,
            labels=["code-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        mock_agent_provider.review_code.return_value = Review(
            approved=True,
            comments=["Well implemented"],
            issues_found=[],
            suggestions=[],
            confidence_score=0.95,
        )

        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should have reviewed code
        mock_agent_provider.review_code.assert_called_once()

        # Should have updated labels to merge-ready
        mock_git_provider.update_issue.assert_called()

        # Should have marked stage complete
        mock_state_manager.mark_stage_complete.assert_called()

    @pytest.mark.asyncio
    async def test_review_rejected(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test code review with rejection."""
        issue = Issue(
            id=43,
            number=43,
            title="[Implement] User authentication",
            body="Task ID: task-1\nPart of plan #42",
            state=IssueState.OPEN,
            labels=["code-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        mock_agent_provider.review_code.return_value = Review(
            approved=False,
            comments=["Needs improvement"],
            issues_found=["Missing error handling", "No input validation"],
            suggestions=["Add try-catch blocks"],
            confidence_score=0.6,
        )

        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should have posted rejection comment
        calls = mock_git_provider.add_comment.call_args_list
        assert any("issues" in str(call).lower() for call in calls)

    @pytest.mark.asyncio
    async def test_review_low_confidence(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that low confidence reviews are not auto-approved."""
        issue = Issue(
            id=43,
            number=43,
            title="[Implement] User authentication",
            body="Task ID: task-1\nPart of plan #42",
            state=IssueState.OPEN,
            labels=["code-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        # Approved but low confidence (below threshold of 0.8)
        mock_agent_provider.review_code.return_value = Review(
            approved=True,
            comments=["Looks okay"],
            issues_found=[],
            suggestions=[],
            confidence_score=0.5,  # Below threshold
        )

        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Labels should not be updated to merge-ready due to low confidence
        update_calls = mock_git_provider.update_issue.call_args_list
        # Verify merge-ready was NOT added
        for call in update_calls:
            labels = call.kwargs.get("labels", [])
            assert "merge-ready" not in labels

    @pytest.mark.asyncio
    async def test_missing_branch_raises_error(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test error when branch is not found in state."""
        issue = Issue(
            id=43,
            number=43,
            title="[Implement] User authentication",
            body="Task ID: task-1\nPart of plan #42",
            state=IssueState.OPEN,
            labels=["code-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        # No branch in state
        mock_state_manager.load_state.return_value = {
            "plan_id": "42",
            "tasks": {"task-1": {"status": "pending"}},  # No branch
        }

        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception):
            await stage.execute(issue)


class TestCodeReviewStageHelperMethods:
    """Tests for CodeReviewStage helper methods."""

    def test_extract_task_id(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test task ID extraction from issue body."""
        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = "Some text\nTask ID: my-task-123\nMore text"
        assert stage._extract_task_id(body) == "my-task-123"

        # Empty body
        assert stage._extract_task_id("") == ""

    def test_extract_plan_id(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test plan ID extraction from issue body."""
        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = "Part of plan #42\nOther content"
        assert stage._extract_plan_id(body) == "42"

        # No plan reference
        assert stage._extract_plan_id("No plan here") == ""

    def test_format_review_comment_approved(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test formatting approved review comment."""
        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        review = Review(
            approved=True,
            comments=["Good work"],
            issues_found=[],
            suggestions=["Add more tests"],
            confidence_score=0.9,
        )

        comment = stage._format_review_comment(review)

        assert "APPROVED" in comment
        assert "90" in comment  # 0.9 as percentage
        assert "Good work" in comment
        assert "Add more tests" in comment

    def test_format_review_comment_rejected(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test formatting rejected review comment."""
        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        review = Review(
            approved=False,
            comments=["Needs work"],
            issues_found=["Missing validation", "No tests"],
            suggestions=[],
            confidence_score=0.7,
        )

        comment = stage._format_review_comment(review)

        assert "NEEDS CHANGES" in comment
        assert "Missing validation" in comment
        assert "No tests" in comment


# ==============================================================================
# TaskExecutionStage Tests
# ==============================================================================


class TestTaskExecutionStageInitialization:
    """Tests for TaskExecutionStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly."""
        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider


class TestTaskExecutionStageExecute:
    """Tests for TaskExecutionStage.execute method."""

    @pytest.mark.asyncio
    async def test_skip_non_task_issue(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that non-task issues are skipped."""
        issue = Issue(
            id=43,
            number=43,
            title="Regular Issue",
            body="Not a task",
            state=IssueState.OPEN,
            labels=["execute"],  # Has execute but not task label
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should not execute anything
        mock_agent_provider.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_already_in_review(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that issues already in review are skipped."""
        issue = Issue(
            id=43,
            number=43,
            title="[TASK 1/5] Do something",
            body="Task body",
            state=IssueState.OPEN,
            labels=["task", "execute", "review"],  # Already in review
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        mock_agent_provider.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_cannot_parse_task_number(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test handling of unparseable task title."""
        issue = Issue(
            id=43,
            number=43,
            title="Invalid Task Title",  # No [TASK N/M] format
            body="Task body",
            state=IssueState.OPEN,
            labels=["task", "execute"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        mock_agent_provider.execute_task.assert_not_called()


class TestTaskExecutionStageHelperMethods:
    """Tests for TaskExecutionStage helper methods."""

    def test_extract_original_issue(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test extracting original issue number from body."""
        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = "**Original Issue**: #42 - Some Title"
        assert stage._extract_original_issue(body) == 42

        # No original issue
        assert stage._extract_original_issue("No issue reference") is None

    def test_extract_description(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test extracting description from task body."""
        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = """Some header text

## Description

This is the actual description
that spans multiple lines.

## Dependencies

- Task 1
"""

        desc = stage._extract_description(body)
        assert "actual description" in desc
        assert "Dependencies" not in desc

    def test_extract_dependencies(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test extracting dependencies from task body."""
        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        body = """## Description

Some description

## Dependencies

This task requires:
- Task 1
- Task 2

## Execution
"""

        deps = stage._extract_dependencies(body)
        assert len(deps) == 2
        assert "Task 1" in deps
        assert "Task 2" in deps

    def test_slugify(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test slugify method."""
        stage = TaskExecutionStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage._slugify("Hello World!") == "hello-world"
        assert stage._slugify("[TASK 1/5] Do Something") == "do-something"

        # Long title truncated
        long_title = "A" * 100
        assert len(stage._slugify(long_title)) <= 50


# ==============================================================================
# PlanningStage Tests
# ==============================================================================


class TestPlanningStageInitialization:
    """Tests for PlanningStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider


class TestPlanningStageExecute:
    """Tests for PlanningStage.execute method."""

    @pytest.mark.asyncio
    async def test_successful_plan_generation(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test successful plan generation flow."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Should generate plan
        mock_agent_provider.generate_plan.assert_called_once_with(open_issue)

        # Should commit plan file
        mock_git_provider.commit_file.assert_called_once()

        # Should create review issue
        mock_git_provider.create_issue.assert_called_once()

        # Should update issue labels
        mock_git_provider.update_issue.assert_called()

        # Should mark stage complete
        mock_state_manager.mark_stage_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_generation_notifies_user(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test that planning stage posts notification comment."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # First call should be the start notification
        first_comment_call = mock_git_provider.add_comment.call_args_list[0]
        assert "Starting" in str(first_comment_call) or "Builder" in str(first_comment_call)

    @pytest.mark.asyncio
    async def test_plan_generation_failure_handled(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test that plan generation errors are handled."""
        mock_agent_provider.generate_plan.side_effect = Exception("Agent error")

        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception, match="Agent error"):
            await stage.execute(open_issue)

    @pytest.mark.asyncio
    async def test_plan_fallback_file_path(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test fallback when plan has no file_path set."""
        plan_without_path = Plan(
            id="plan-42",
            title="Test Plan",
            description="A plan",
            tasks=[],
            file_path=None,  # No file path
            created_at=datetime.now(UTC),
        )
        mock_agent_provider.generate_plan.return_value = plan_without_path

        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Should still work with fallback path
        mock_git_provider.commit_file.assert_called_once()


class TestPlanningStageHelperMethods:
    """Tests for PlanningStage helper methods."""

    def test_format_plan_basic(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test basic plan formatting."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        issue = Issue(
            id=42,
            number=42,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Plan description",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        formatted = stage._format_plan(plan, issue)

        assert "# Test Plan" in formatted
        assert "**Issue:** #42" in formatted
        assert "Plan description" in formatted

    def test_format_plan_with_tasks(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test plan formatting with tasks."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        issue = Issue(
            id=42,
            number=42,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="Plan description",
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

        formatted = stage._format_plan(plan, issue)

        assert "## Tasks" in formatted
        assert "### Task 1: First Task" in formatted
        assert "### Task 2: Second Task" in formatted
        assert "**Dependencies:**" in formatted

    def test_create_review_body(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test review issue body creation."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        issue = Issue(
            id=42,
            number=42,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description="A short description of the plan",
            tasks=[],
            created_at=datetime.now(UTC),
        )

        body = stage._create_review_body(issue, plan, "plans/test.md")

        assert "# Plan Review" in body
        assert "#42" in body
        assert "plans/test.md" in body
        assert "Review Checklist" in body

    def test_create_review_body_truncates_long_description(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test that long descriptions are truncated in review body."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        issue = Issue(
            id=42,
            number=42,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/42",
        )

        long_description = "A" * 1000  # Very long description

        plan = Plan(
            id="plan-42",
            title="Test Plan",
            description=long_description,
            tasks=[],
            created_at=datetime.now(UTC),
        )

        body = stage._create_review_body(issue, plan, "plans/test.md")

        # Should have ellipsis indicating truncation
        assert "..." in body


# ==============================================================================
# QAStage Tests
# ==============================================================================


class TestQAStageInitialization:
    """Tests for QAStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly."""
        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider


class TestQAStageExecute:
    """Tests for QAStage.execute method."""

    @pytest.mark.asyncio
    async def test_skip_already_qa_checked(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that already QA'd issues are skipped."""
        issue = Issue(
            id=43,
            number=43,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=["requires-qa", "qa-passed"],  # Already has qa-passed
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        mock_git_provider.get_pull_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_already_qa_failed(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that already QA'd (failed) issues are skipped."""
        issue = Issue(
            id=43,
            number=43,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=["requires-qa", "qa-failed"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        mock_git_provider.get_pull_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pr_found(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test handling when no PR is associated with issue."""
        issue = Issue(
            id=43,
            number=43,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=["requires-qa"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        mock_git_provider.get_pull_request.side_effect = Exception("Not found")

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should not post any comments about QA
        for call in mock_git_provider.add_comment.call_args_list:
            assert "QA" not in str(call) or "Starting" not in str(call)


class TestQAStageHelperMethods:
    """Tests for QAStage helper methods."""

    @pytest.mark.asyncio
    async def test_get_pr_for_issue_success(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test getting PR for issue successfully."""
        expected_pr = PullRequest(
            id=1,
            number=43,
            title="Test PR",
            body="PR body",
            head="feature-branch",
            base="main",
            state="open",
            url="https://gitea.test/pulls/43",
            created_at=datetime.now(UTC),
        )
        mock_git_provider.get_pull_request.return_value = expected_pr

        issue = Issue(
            id=43,
            number=43,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=["requires-qa"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        pr = await stage._get_pr_for_issue(issue)

        assert pr == expected_pr
        mock_git_provider.get_pull_request.assert_called_once_with(43)

    @pytest.mark.asyncio
    async def test_get_pr_for_issue_not_found(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test getting PR for issue when PR doesn't exist."""
        mock_git_provider.get_pull_request.side_effect = Exception("Not found")

        issue = Issue(
            id=43,
            number=43,
            title="Test Issue",
            body="Issue body",
            state=IssueState.OPEN,
            labels=["requires-qa"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/43",
        )

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        pr = await stage._get_pr_for_issue(issue)

        assert pr is None

    @pytest.mark.asyncio
    async def test_run_build_no_build_system(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test build when no build system is detected."""
        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        result = await stage._run_build(tmp_path)

        assert result["success"] is True
        assert result["command"] == "none"
        assert "static" in result["output"].lower() or "no build" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_run_test_no_test_system(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test test execution when no test system is detected."""
        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        result = await stage._run_test(tmp_path)

        assert result["success"] is True
        assert result["command"] == "none"

    @pytest.mark.asyncio
    async def test_run_build_with_python_project(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test build detection for Python project with pyproject.toml."""
        # Create pyproject.toml to indicate Python project
        (tmp_path / "pyproject.toml").write_text("[build-system]\n")

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        # This may fail if python -m build isn't installed, but it should try
        result = await stage._run_build(tmp_path)

        # Either it runs or falls back, but should have a result
        assert "success" in result
        assert "output" in result

    @pytest.mark.asyncio
    async def test_run_test_with_tests_directory(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test detection with tests directory present."""
        # Create tests directory
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_example.py").write_text("def test_example(): pass")

        stage = QAStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        result = await stage._run_test(tmp_path)

        # Should have attempted to run tests
        assert "success" in result


# ==============================================================================
# Base Stage Error Handling Tests
# ==============================================================================


class TestWorkflowStageErrorHandling:
    """Tests for common error handling in WorkflowStage base class."""

    @pytest.mark.asyncio
    async def test_handle_stage_error(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test that _handle_stage_error adds comment and label."""
        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        test_error = Exception("Test error message")

        await stage._handle_stage_error(open_issue, test_error)

        # Should add error comment
        mock_git_provider.add_comment.assert_called()
        comment_call = mock_git_provider.add_comment.call_args
        assert "Test error message" in str(comment_call)

        # Should update labels to include needs-attention
        mock_git_provider.update_issue.assert_called()
        update_call = mock_git_provider.update_issue.call_args
        assert "needs-attention" in update_call.kwargs.get("labels", [])


# ==============================================================================
# Integration-like Tests (still using mocks but testing multi-step flows)
# ==============================================================================


class TestStageIntegration:
    """Tests for stage interactions and workflows."""

    @pytest.mark.asyncio
    async def test_planning_to_review_flow(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        open_issue,
    ):
        """Test that planning stage sets up issue for review correctly."""
        # Configure mock to return review issue
        review_issue = Issue(
            id=100,
            number=100,
            title="Plan Review: Test Issue",
            body="Review body",
            state=IssueState.OPEN,
            labels=["plan-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/100",
        )
        mock_git_provider.create_issue.return_value = review_issue

        stage = PlanningStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(open_issue)

        # Verify review issue was created with correct label
        create_call = mock_git_provider.create_issue.call_args
        assert "Plan Review" in create_call.kwargs.get("title", create_call.args[0] if create_call.args else "")

        # Verify original issue labels were updated
        update_call = mock_git_provider.update_issue.call_args
        labels = update_call.kwargs.get("labels", [])
        assert "plan-review" in labels

    @pytest.mark.asyncio
    async def test_code_review_approval_updates_state(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that approved code review updates state correctly."""
        issue = Issue(
            id=43,
            number=43,
            title="[Implement] User authentication",
            body="Task ID: task-1\nPart of plan #42",
            state=IssueState.OPEN,
            labels=["code-review"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="bot",
            url="https://gitea.test/issues/43",
        )

        mock_agent_provider.review_code.return_value = Review(
            approved=True,
            comments=["Excellent work"],
            issues_found=[],
            suggestions=[],
            confidence_score=0.95,
        )

        stage = CodeReviewStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Verify state was updated
        mock_state_manager.mark_task_status.assert_called_once()
        status_call = mock_state_manager.mark_task_status.call_args
        assert status_call.args[2] == "merge_ready"

        # Verify stage was marked complete
        mock_state_manager.mark_stage_complete.assert_called_once()
        stage_call = mock_state_manager.mark_stage_complete.call_args
        assert stage_call.args[1] == "code_review"
        assert stage_call.args[2]["approved"] is True
