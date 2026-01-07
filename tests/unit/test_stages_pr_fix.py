"""Tests for repo_sapiens/engine/stages/pr_fix.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from repo_sapiens.engine.stages.pr_fix import PRFixStage
from repo_sapiens.models.domain import Issue, IssueState


def make_issue(**kwargs):
    """Helper to create Issue with required fields."""
    defaults = {
        "id": 1,
        "number": 42,
        "title": "Test Issue",
        "body": "Test body",
        "state": IssueState.OPEN,
        "labels": [],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "author": "user",
        "url": "https://example.com/42",
    }
    defaults.update(kwargs)
    return Issue(**defaults)


@pytest.fixture
def mock_git_provider():
    """Create mock git provider."""
    return AsyncMock()


@pytest.fixture
def mock_agent_provider():
    """Create mock agent provider."""
    return AsyncMock()


@pytest.fixture
def mock_state_manager():
    """Create mock state manager."""
    return MagicMock()


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings."""
    settings = MagicMock()
    settings.workflow.state_directory = str(tmp_path / "state")
    return settings


@pytest.fixture
def pr_fix_stage(mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
    """Create PRFixStage instance."""
    stage = PRFixStage(mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings)
    return stage


class TestFormatFixProposal:
    """Tests for _format_fix_proposal method."""

    def test_formats_proposal_correctly(self, pr_fix_stage):
        """Should format fix proposal with all sections."""
        result = pr_fix_stage._format_fix_proposal(
            pr_number=42,
            pr_title="Add user authentication",
            branch_name="plan-42-implementation",
            review_feedback="Found 3 issues:\n1. Missing tests\n2. No error handling",
        )

        assert "# Fix Proposal for PR #42" in result
        assert "Add user authentication" in result
        assert "plan-42-implementation" in result
        assert "Found 3 issues" in result
        assert "## Review Feedback" in result
        assert "## Proposed Fixes" in result
        assert "## Approval" in result
        assert "Builder Automation" in result

    def test_includes_branch_name(self, pr_fix_stage):
        """Should include branch name in proposal."""
        result = pr_fix_stage._format_fix_proposal(
            pr_number=99,
            pr_title="Feature",
            branch_name="feature/custom-branch",
            review_feedback="Feedback",
        )

        assert "`feature/custom-branch`" in result

    def test_includes_approval_instructions(self, pr_fix_stage):
        """Should include approval instructions."""
        result = pr_fix_stage._format_fix_proposal(
            pr_number=1,
            pr_title="Title",
            branch_name="branch",
            review_feedback="Feedback",
        )

        assert "approved" in result.lower()
        assert "label" in result.lower()


class TestPRFixStageExecute:
    """Tests for PRFixStage execute method."""

    @pytest.mark.asyncio
    async def test_skip_if_already_proposed(self, pr_fix_stage, mock_git_provider):
        """Should skip if fix already proposed."""
        issue = make_issue(labels=["needs-fix", "fix-proposed"])  # Already proposed

        await pr_fix_stage.execute(issue)

        # Should not try to get comments
        mock_git_provider.get_comments.assert_not_called()

    @pytest.mark.asyncio
    async def test_warns_if_no_review_comment(self, pr_fix_stage, mock_git_provider):
        """Should warn if no review comment found."""
        mock_git_provider.get_comments.return_value = [
            MagicMock(body="Just a regular comment"),
            MagicMock(body="Another comment"),
        ]

        issue = make_issue(labels=["needs-fix", "plan-42"])

        await pr_fix_stage.execute(issue)

        # Should post warning comment
        mock_git_provider.add_comment.assert_called_once()
        call_args = mock_git_provider.add_comment.call_args[0]
        assert "No Review Feedback Found" in call_args[1]

    @pytest.mark.asyncio
    async def test_skips_without_plan_label(self, pr_fix_stage, mock_git_provider):
        """Should skip if no plan label found."""
        mock_git_provider.get_comments.return_value = [
            MagicMock(body="Code Review Complete\nitems to address"),
        ]

        issue = make_issue(labels=["needs-fix"])  # No plan-* label

        await pr_fix_stage.execute(issue)

        # Should not create fix issue without plan label
        mock_git_provider.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_fix_proposal(self, pr_fix_stage, mock_git_provider):
        """Should create fix proposal issue."""
        review_comment = MagicMock()
        review_comment.body = "Code Review Complete\n3 items to address:\n1. Fix error handling"

        mock_git_provider.get_comments.return_value = [review_comment]

        fix_issue = MagicMock()
        fix_issue.number = 100
        mock_git_provider.create_issue.return_value = fix_issue

        issue = make_issue(title="Test Feature PR", labels=["needs-fix", "plan-42"])

        await pr_fix_stage.execute(issue)

        # Should create fix proposal issue
        mock_git_provider.create_issue.assert_called_once()
        call_kwargs = mock_git_provider.create_issue.call_args[1]
        assert "[FIX PROPOSAL]" in call_kwargs["title"]
        assert "fix-proposal" in call_kwargs["labels"]
        assert "plan-42" in call_kwargs["labels"]

        # Should add comment to original issue
        assert mock_git_provider.add_comment.call_count >= 1

        # Should update labels
        mock_git_provider.update_issue.assert_called_once()
        update_kwargs = mock_git_provider.update_issue.call_args[1]
        assert "fix-proposed" in update_kwargs["labels"]
        assert "needs-fix" not in update_kwargs["labels"]

    @pytest.mark.asyncio
    async def test_handles_execution_error(self, pr_fix_stage, mock_git_provider):
        """Should handle and report execution errors."""
        mock_git_provider.get_comments.side_effect = Exception("API error")

        issue = make_issue(labels=["needs-fix", "plan-42"])

        with pytest.raises(Exception, match="API error"):
            await pr_fix_stage.execute(issue)

        # Should post error comment
        mock_git_provider.add_comment.assert_called_once()
        call_args = mock_git_provider.add_comment.call_args[0]
        assert "Fix Proposal Failed" in call_args[1]
