"""Tests for repo_sapiens/engine/stages/pr_review.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from repo_sapiens.engine.stages.pr_review import PRReviewStage
from repo_sapiens.models.domain import Issue, IssueState, PullRequest


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


def make_pr(**kwargs):
    """Helper to create PullRequest with required fields."""
    defaults = {
        "id": 1,
        "number": 42,
        "title": "Test PR",
        "body": "Test body",
        "state": "open",
        "head": "feature-branch",
        "base": "main",
        "url": "https://example.com/pr/42",
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return PullRequest(**defaults)


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
    settings.tags.needs_review = "needs-review"
    return settings


@pytest.fixture
def pr_review_stage(mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
    """Create PRReviewStage instance."""
    stage = PRReviewStage(mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings)
    return stage


class TestParseReviewComments:
    """Tests for _parse_review_comments method."""

    def test_parse_single_comment(self, pr_review_stage):
        """Should parse single review comment."""
        output = """
REVIEW_COMMENT:
File: src/main.py
Line: 42
Issue: Missing error handling
Suggestion: Add try/except block
"""
        comments = pr_review_stage._parse_review_comments(output)

        assert len(comments) == 1
        assert comments[0]["file"] == "src/main.py"
        assert comments[0]["line"] == 42
        assert "error handling" in comments[0]["issue"]
        assert "try/except" in comments[0]["suggestion"]

    def test_parse_multiple_comments(self, pr_review_stage):
        """Should parse multiple review comments."""
        output = """
REVIEW_COMMENT:
File: src/main.py
Line: 10
Issue: Unused import
Suggestion: Remove unused import

REVIEW_COMMENT:
File: src/utils.py
Line: 25
Issue: Missing docstring
Suggestion: Add docstring to function
"""
        comments = pr_review_stage._parse_review_comments(output)

        assert len(comments) == 2
        assert comments[0]["file"] == "src/main.py"
        assert comments[1]["file"] == "src/utils.py"

    def test_parse_comment_without_line(self, pr_review_stage):
        """Should handle comment without line number."""
        output = """
REVIEW_COMMENT:
File: src/main.py
Issue: General code quality issue
Suggestion: Refactor for clarity
"""
        comments = pr_review_stage._parse_review_comments(output)

        assert len(comments) == 1
        assert comments[0]["file"] == "src/main.py"
        assert "line" not in comments[0]

    def test_parse_empty_output(self, pr_review_stage):
        """Should return empty list for no comments."""
        output = "REVIEW_APPROVED"

        comments = pr_review_stage._parse_review_comments(output)

        assert comments == []

    def test_parse_malformed_comment(self, pr_review_stage):
        """Should skip malformed comments."""
        output = """
REVIEW_COMMENT:
This is not a properly formatted comment

REVIEW_COMMENT:
File: src/valid.py
Issue: Valid issue
Suggestion: Valid fix
"""
        comments = pr_review_stage._parse_review_comments(output)

        # Should only get the valid comment
        assert len(comments) == 1
        assert comments[0]["file"] == "src/valid.py"


class TestPRReviewStageExecute:
    """Tests for PRReviewStage execute method."""

    @pytest.mark.asyncio
    async def test_skip_if_no_pr(self, pr_review_stage, mock_git_provider):
        """Should skip if no PR found for issue."""
        mock_git_provider.get_pull_request.side_effect = Exception("Not a PR")

        issue = make_issue(labels=["needs-review"])

        await pr_review_stage.execute(issue)

        # Should not try to add comments
        mock_git_provider.add_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_if_already_reviewed(self, pr_review_stage, mock_git_provider):
        """Should skip if PR already has review labels."""
        mock_git_provider.get_pull_request.return_value = make_pr()

        issue = make_issue(labels=["needs-review", "approved"])  # Already approved

        await pr_review_stage.execute(issue)

        # Should not proceed with review
        mock_git_provider.get_diff.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_if_needs_fix_label(self, pr_review_stage, mock_git_provider):
        """Should skip if PR has needs-fix label."""
        mock_git_provider.get_pull_request.return_value = make_pr()

        issue = make_issue(labels=["needs-review", "needs-fix"])

        await pr_review_stage.execute(issue)

        mock_git_provider.get_diff.assert_not_called()


class TestGetPRForIssue:
    """Tests for _get_pr_for_issue method."""

    @pytest.mark.asyncio
    async def test_returns_pr_when_found(self, pr_review_stage, mock_git_provider):
        """Should return PR when found."""
        expected_pr = make_pr(head="feature")
        mock_git_provider.get_pull_request.return_value = expected_pr

        issue = make_issue()

        result = await pr_review_stage._get_pr_for_issue(issue)

        assert result == expected_pr

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, pr_review_stage, mock_git_provider):
        """Should return None when PR lookup fails."""
        mock_git_provider.get_pull_request.side_effect = Exception("Not found")

        issue = make_issue()

        result = await pr_review_stage._get_pr_for_issue(issue)

        assert result is None
