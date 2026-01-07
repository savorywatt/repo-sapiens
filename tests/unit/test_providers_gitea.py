"""Tests for repo_sapiens/providers/gitea_rest.py - Gitea REST API provider implementation.

This module provides comprehensive test coverage for the GiteaRestProvider class,
testing initialization, connection management, issue/PR operations, file handling,
branch management, label operations, and error handling scenarios.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.models.domain import IssueState
from repo_sapiens.providers.gitea_rest import GiteaRestProvider
from repo_sapiens.utils.connection_pool import HTTPConnectionPool


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def provider() -> GiteaRestProvider:
    """Create a GiteaRestProvider instance for testing."""
    return GiteaRestProvider(
        base_url="https://gitea.example.com/",
        token="test_api_token_12345",
        owner="test-owner",
        repo="test-repo",
    )


@pytest.fixture
def mock_pool() -> AsyncMock:
    """Create a mock HTTPConnectionPool."""
    pool = AsyncMock(spec=HTTPConnectionPool)
    return pool


@pytest.fixture
def sample_issue_data() -> dict:
    """Sample issue data as returned by Gitea API."""
    return {
        "id": 1001,
        "number": 42,
        "title": "Fix authentication bug",
        "body": "Users cannot log in with special characters in password.",
        "state": "open",
        "labels": [
            {"id": 1, "name": "bug"},
            {"id": 2, "name": "high-priority"},
        ],
        "created_at": "2024-06-15T10:30:00Z",
        "updated_at": "2024-06-16T14:45:00Z",
        "user": {"login": "developer123"},
        "html_url": "https://gitea.example.com/test-owner/test-repo/issues/42",
    }


@pytest.fixture
def sample_comment_data() -> dict:
    """Sample comment data as returned by Gitea API."""
    return {
        "id": 5001,
        "body": "I've identified the root cause. Working on a fix.",
        "user": {"login": "reviewer"},
        "created_at": "2024-06-16T16:00:00Z",
    }


@pytest.fixture
def sample_branch_data() -> dict:
    """Sample branch data as returned by Gitea API."""
    return {
        "name": "feature/authentication-fix",
        "commit": {
            "id": "abc123def456789",
            "message": "Fix password validation",
        },
    }


@pytest.fixture
def sample_pr_data() -> dict:
    """Sample pull request data as returned by Gitea API."""
    return {
        "id": 2001,
        "number": 15,
        "title": "Fix authentication with special characters",
        "body": "This PR resolves the authentication issue.",
        "state": "open",
        "head": {"ref": "feature/auth-fix"},
        "base": {"ref": "main"},
        "html_url": "https://gitea.example.com/test-owner/test-repo/pull/15",
        "created_at": "2024-06-17T09:00:00Z",
    }


@pytest.fixture
def sample_label_data() -> list[dict]:
    """Sample label data as returned by Gitea API."""
    return [
        {"id": 1, "name": "bug", "color": "d73a4a"},
        {"id": 2, "name": "enhancement", "color": "a2eeef"},
        {"id": 3, "name": "documentation", "color": "0075ca"},
    ]


# =============================================================================
# Initialization Tests
# =============================================================================


class TestGiteaRestProviderInit:
    """Tests for GiteaRestProvider initialization."""

    @pytest.mark.parametrize(
        "base_url,expected_base,expected_api",
        [
            ("https://gitea.test.com", "https://gitea.test.com", "https://gitea.test.com/api/v1"),
            (
                "https://gitea.test.com/",
                "https://gitea.test.com",
                "https://gitea.test.com/api/v1",
            ),
            (
                "http://localhost:3000",
                "http://localhost:3000",
                "http://localhost:3000/api/v1",
            ),
        ],
        ids=["no_trailing_slash", "with_trailing_slash", "custom_port"],
    )
    def test_init_url_handling(self, base_url, expected_base, expected_api) -> None:
        """Should handle various URL formats correctly."""
        provider = GiteaRestProvider(
            base_url=base_url,
            token="token",
            owner="owner",
            repo="repo",
        )

        assert provider.base_url == expected_base
        assert provider.api_base == expected_api
        assert provider._pool is None


# =============================================================================
# Connection Management Tests
# =============================================================================


class TestGiteaRestProviderConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.gitea_rest.get_pool")
    async def test_connect_creates_client(
        self, mock_get_pool: AsyncMock, provider: GiteaRestProvider
    ) -> None:
        """Should create connection pool with proper headers on connect."""
        mock_pool = AsyncMock(spec=HTTPConnectionPool)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_pool.get = AsyncMock(return_value=mock_response)
        mock_get_pool.return_value = mock_pool

        await provider.connect()

        mock_get_pool.assert_called_once()
        call_kwargs = mock_get_pool.call_args.kwargs

        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "token test_api_token_12345"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert provider._pool is mock_pool

    @pytest.mark.asyncio
    async def test_disconnect_clears_pool(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should clear pool reference on disconnect."""
        provider._pool = mock_pool

        await provider.disconnect()

        assert provider._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, provider: GiteaRestProvider) -> None:
        """Should handle disconnect when no pool exists."""
        assert provider._pool is None
        await provider.disconnect()
        assert provider._pool is None


# =============================================================================
# Issue Operations Tests
# =============================================================================


class TestGiteaRestProviderIssues:
    """Tests for issue operations."""

    @pytest.mark.asyncio
    async def test_get_issues_returns_parsed_issues(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should retrieve and parse issues correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = [sample_issue_data]
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issues = await provider.get_issues(state="open")

        assert len(issues) == 1
        issue = issues[0]
        assert issue.id == 1001
        assert issue.number == 42
        assert issue.title == "Fix authentication bug"
        assert issue.state == IssueState.OPEN
        assert issue.labels == ["bug", "high-priority"]
        assert issue.author == "developer123"

        mock_pool.get.assert_called_once()
        call_args = mock_pool.get.call_args
        assert "/repos/test-owner/test-repo/issues" in call_args.args[0]
        assert call_args.kwargs["params"]["state"] == "open"

    @pytest.mark.asyncio
    async def test_get_issues_with_labels_filter(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should filter issues by labels."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.get_issues(labels=["bug", "critical"], state="all")

        call_args = mock_pool.get.call_args
        assert call_args.kwargs["params"]["labels"] == "bug,critical"
        assert call_args.kwargs["params"]["state"] == "all"

    @pytest.mark.asyncio
    async def test_get_issue_by_number(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should retrieve single issue by number."""
        sample_issue_data["state"] = "closed"
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.get_issue(42)

        assert issue.number == 42
        assert issue.state == IssueState.CLOSED
        assert "/issues/42" in mock_pool.get.call_args.args[0]

    @pytest.mark.asyncio
    async def test_create_issue_without_labels(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should create issue without labels."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.create_issue(
            title="New bug report", body="Description of the bug"
        )

        assert issue.id == 1001
        call_args = mock_pool.post.call_args
        posted_data = call_args.kwargs["json"]
        assert posted_data["title"] == "New bug report"
        assert "labels" not in posted_data

    @pytest.mark.asyncio
    async def test_create_issue_with_existing_labels(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
        sample_label_data: list[dict],
    ) -> None:
        """Should create issue with existing labels."""
        labels_response = MagicMock()
        labels_response.json.return_value = sample_label_data
        labels_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = sample_issue_data
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=labels_response)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        await provider.create_issue(
            title="New feature", body="Feature description", labels=["bug", "enhancement"]
        )

        create_call = mock_pool.post.call_args
        posted_data = create_call.kwargs["json"]
        assert posted_data["labels"] == [1, 2]

    @pytest.mark.asyncio
    async def test_update_issue_title_and_body(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should update issue title and body."""
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_pool.patch = AsyncMock(return_value=patch_response)

        get_response = MagicMock()
        get_response.json.return_value = sample_issue_data
        get_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=get_response)

        provider._pool = mock_pool

        issue = await provider.update_issue(
            issue_number=42, title="Updated title", body="Updated description"
        )

        assert issue.number == 42
        patch_call = mock_pool.patch.call_args
        patched_data = patch_call.kwargs["json"]
        assert patched_data["title"] == "Updated title"
        assert patched_data["body"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_issue_state(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should update issue state."""
        patch_response = MagicMock()
        patch_response.raise_for_status = MagicMock()
        mock_pool.patch = AsyncMock(return_value=patch_response)

        sample_issue_data["state"] = "closed"
        get_response = MagicMock()
        get_response.json.return_value = sample_issue_data
        get_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=get_response)

        provider._pool = mock_pool

        issue = await provider.update_issue(issue_number=42, state="closed")

        patch_call = mock_pool.patch.call_args
        assert patch_call.kwargs["json"]["state"] == "closed"
        assert issue.state == IssueState.CLOSED

    @pytest.mark.asyncio
    async def test_update_issue_labels(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
        sample_label_data: list[dict],
    ) -> None:
        """Should update issue labels separately."""
        labels_response = MagicMock()
        labels_response.json.return_value = sample_label_data
        labels_response.raise_for_status = MagicMock()

        put_response = MagicMock()
        put_response.raise_for_status = MagicMock()

        get_response = MagicMock()
        get_response.json.return_value = sample_issue_data
        get_response.raise_for_status = MagicMock()

        call_count = {"get": 0}

        async def mock_get(url: str, params: dict | None = None) -> MagicMock:
            call_count["get"] += 1
            if call_count["get"] == 1:
                return labels_response
            return get_response

        mock_pool.get = AsyncMock(side_effect=mock_get)
        mock_pool.put = AsyncMock(return_value=put_response)
        provider._pool = mock_pool

        await provider.update_issue(issue_number=42, labels=["bug", "enhancement"])

        put_call = mock_pool.put.call_args
        assert "/issues/42/labels" in put_call.args[0]
        assert put_call.kwargs["json"]["labels"] == [1, 2]


# =============================================================================
# Comment Operations Tests
# =============================================================================


class TestGiteaRestProviderComments:
    """Tests for comment operations."""

    @pytest.mark.asyncio
    async def test_add_comment(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_comment_data: dict,
    ) -> None:
        """Should add comment to issue."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_comment_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        comment = await provider.add_comment(42, "Test comment body")

        assert comment.id == 5001
        assert comment.author == "reviewer"
        call_args = mock_pool.post.call_args
        assert "/issues/42/comments" in call_args.args[0]
        assert call_args.kwargs["json"]["body"] == "Test comment body"

    @pytest.mark.asyncio
    async def test_get_comments(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_comment_data: dict,
    ) -> None:
        """Should retrieve all comments for an issue."""
        second_comment = {
            "id": 5002,
            "body": "LGTM, merging now.",
            "user": {"login": "maintainer"},
            "created_at": "2024-06-17T08:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = [sample_comment_data, second_comment]
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        comments = await provider.get_comments(42)

        assert len(comments) == 2
        assert comments[0].author == "reviewer"
        assert comments[1].author == "maintainer"


# =============================================================================
# File Operations Tests
# =============================================================================


class TestGiteaRestProviderFiles:
    """Tests for file operations."""

    @pytest.mark.asyncio
    async def test_get_file(self, provider: GiteaRestProvider, mock_pool: AsyncMock) -> None:
        """Should retrieve and decode file contents."""
        file_content = "# README\n\nThis is a test project."
        encoded_content = base64.b64encode(file_content.encode()).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": encoded_content}
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        content = await provider.get_file("README.md", ref="main")

        assert content == file_content
        call_args = mock_pool.get.call_args
        assert "/contents/README.md" in call_args.args[0]
        assert call_args.kwargs["params"]["ref"] == "main"

    @pytest.mark.asyncio
    async def test_commit_file_new(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should create new file when it doesn't exist."""
        not_found_response = MagicMock()
        not_found_response.status_code = 404
        mock_pool.get = AsyncMock(return_value=not_found_response)

        create_response = MagicMock()
        create_response.json.return_value = {"commit": {"sha": "newfile123"}}
        create_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=create_response)

        provider._pool = mock_pool

        sha = await provider.commit_file(
            path="new_file.txt",
            content="New file content",
            message="Add new file",
            branch="main",
        )

        assert sha == "newfile123"
        post_call = mock_pool.post.call_args
        posted_data = post_call.kwargs["json"]
        assert posted_data["message"] == "Add new file"
        decoded = base64.b64decode(posted_data["content"]).decode()
        assert decoded == "New file content"
        assert "sha" not in posted_data

    @pytest.mark.asyncio
    async def test_commit_file_update(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should update existing file with SHA."""
        existing_response = MagicMock()
        existing_response.status_code = 200
        existing_response.json.return_value = {"sha": "existing123"}
        mock_pool.get = AsyncMock(return_value=existing_response)

        update_response = MagicMock()
        update_response.json.return_value = {"commit": {"sha": "updated456"}}
        update_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=update_response)

        provider._pool = mock_pool

        sha = await provider.commit_file(
            path="existing.txt",
            content="Updated content",
            message="Update file",
            branch="develop",
        )

        assert sha == "updated456"
        post_call = mock_pool.post.call_args
        posted_data = post_call.kwargs["json"]
        assert posted_data["sha"] == "existing123"


# =============================================================================
# Branch Operations Tests
# =============================================================================


class TestGiteaRestProviderBranches:
    """Tests for branch operations."""

    @pytest.mark.asyncio
    async def test_get_branch(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_branch_data: dict,
    ) -> None:
        """Should retrieve branch information."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_branch_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        branch = await provider.get_branch("feature/authentication-fix")

        assert branch is not None
        assert branch.name == "feature/authentication-fix"
        assert branch.sha == "abc123def456789"

    @pytest.mark.asyncio
    async def test_get_branch_not_found(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should return None for non-existent branch."""
        http_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        mock_pool.get = AsyncMock(side_effect=http_error)
        provider._pool = mock_pool

        branch = await provider.get_branch("nonexistent-branch")

        assert branch is None

    @pytest.mark.asyncio
    async def test_get_branch_other_error_propagates(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should propagate non-404 HTTP errors."""
        http_error = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        mock_pool.get = AsyncMock(side_effect=http_error)
        provider._pool = mock_pool

        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_branch("some-branch")

    @pytest.mark.asyncio
    async def test_create_branch_new(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_branch_data: dict,
    ) -> None:
        """Should create new branch when it doesn't exist."""
        http_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        create_response = MagicMock()
        create_response.json.return_value = sample_branch_data
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(side_effect=http_error)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        branch = await provider.create_branch("feature/new-feature", "main")

        assert branch.name == "feature/authentication-fix"
        post_call = mock_pool.post.call_args
        posted_data = post_call.kwargs["json"]
        assert posted_data["new_branch_name"] == "feature/new-feature"
        assert posted_data["old_branch_name"] == "main"

    @pytest.mark.asyncio
    async def test_create_branch_already_exists(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_branch_data: dict,
    ) -> None:
        """Should return existing branch if it already exists."""
        get_response = MagicMock()
        get_response.json.return_value = sample_branch_data
        get_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=get_response)
        provider._pool = mock_pool

        branch = await provider.create_branch("feature/authentication-fix")

        assert branch.name == "feature/authentication-fix"
        mock_pool.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_branches(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should merge source branch into target."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.merge_branches(
            source="feature/completed", target="main", message="Merge feature branch"
        )

        post_call = mock_pool.post.call_args
        assert "/branches/main/merge" in post_call.args[0]
        posted_data = post_call.kwargs["json"]
        assert posted_data["head"] == "feature/completed"
        assert posted_data["message"] == "Merge feature branch"


# =============================================================================
# Pull Request Operations Tests
# =============================================================================


class TestGiteaRestProviderPullRequests:
    """Tests for pull request operations."""

    @pytest.mark.asyncio
    async def test_create_pull_request_new(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_pr_data: dict,
    ) -> None:
        """Should create new pull request."""
        list_response = MagicMock()
        list_response.json.return_value = []
        list_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = sample_pr_data
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=list_response)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        pr = await provider.create_pull_request(
            title="New feature PR",
            body="PR description",
            head="feature/auth-fix",
            base="main",
        )

        assert pr.number == 15
        assert pr.title == "Fix authentication with special characters"
        assert pr.head == "feature/auth-fix"
        assert pr.base == "main"

    @pytest.mark.asyncio
    async def test_create_pull_request_updates_existing(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_pr_data: dict,
    ) -> None:
        """Should update existing PR if one exists for the same branches."""
        existing_pr = {
            "number": 15,
            "head": {"ref": "feature/auth-fix"},
            "base": {"ref": "main"},
        }
        list_response = MagicMock()
        list_response.json.return_value = [existing_pr]
        list_response.raise_for_status = MagicMock()

        update_response = MagicMock()
        update_response.json.return_value = sample_pr_data
        update_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=list_response)
        mock_pool.patch = AsyncMock(return_value=update_response)
        provider._pool = mock_pool

        pr = await provider.create_pull_request(
            title="Updated PR title",
            body="Updated description",
            head="feature/auth-fix",
            base="main",
        )

        assert pr.number == 15
        mock_pool.patch.assert_called_once()
        mock_pool.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pull_request(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_pr_data: dict,
    ) -> None:
        """Should retrieve pull request by number."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_pr_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        pr = await provider.get_pull_request(15)

        assert pr is not None
        assert pr.number == 15
        assert pr.title == "Fix authentication with special characters"

    @pytest.mark.asyncio
    async def test_get_pull_request_not_found(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should return None for non-existent PR."""
        mock_pool.get = AsyncMock(side_effect=Exception("Not found"))
        provider._pool = mock_pool

        pr = await provider.get_pull_request(999)

        assert pr is None

    @pytest.mark.asyncio
    async def test_get_diff_from_pr(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should get diff from PR endpoint."""
        mock_response = MagicMock()
        mock_response.text = "diff --git a/file.py b/file.py\n+new line"
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        diff = await provider.get_diff("main", "feature", pr_number=42)

        assert "diff --git" in diff
        call_args = mock_pool.get.call_args
        assert "/pulls/42.diff" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_diff_compare_branches(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should compare branches when no PR number provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "files": [
                {"filename": "src/auth.py", "patch": "@@ -1,3 +1,5 @@\n+# Auth module"},
                {"filename": "tests/test_auth.py", "patch": "@@ -0,0 +1,10 @@\n+import pytest"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        diff = await provider.get_diff("main", "feature")

        assert "diff --git a/src/auth.py" in diff
        assert "diff --git a/tests/test_auth.py" in diff


# =============================================================================
# Label Operations Tests
# =============================================================================


class TestGiteaRestProviderLabels:
    """Tests for label operations."""

    @pytest.mark.asyncio
    async def test_get_or_create_label_ids_existing(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_label_data: list[dict],
    ) -> None:
        """Should return IDs for existing labels."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_label_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        label_ids = await provider._get_or_create_label_ids(["bug", "documentation"])

        assert label_ids == [1, 3]
        mock_pool.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_label_ids_creates_new(
        self,
        provider: GiteaRestProvider,
        mock_pool: AsyncMock,
        sample_label_data: list[dict],
    ) -> None:
        """Should create new labels when they don't exist."""
        get_response = MagicMock()
        get_response.json.return_value = sample_label_data
        get_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = {"id": 100, "name": "new-label"}
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=get_response)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        label_ids = await provider._get_or_create_label_ids(["bug", "new-label"])

        assert label_ids == [1, 100]
        mock_pool.post.assert_called_once()
        post_call = mock_pool.post.call_args
        posted_data = post_call.kwargs["json"]
        assert posted_data["name"] == "new-label"
        assert posted_data["color"] == "ededed"


# =============================================================================
# Model Parsing Tests - Consolidated
# =============================================================================


class TestGiteaRestProviderParsing:
    """Tests for model parsing methods."""

    @pytest.mark.parametrize(
        "state,expected_state",
        [("open", IssueState.OPEN), ("closed", IssueState.CLOSED)],
        ids=["open", "closed"],
    )
    def test_parse_issue_state(self, provider: GiteaRestProvider, state, expected_state) -> None:
        """Should parse issue state correctly."""
        data = {
            "id": 1,
            "number": 10,
            "title": "Test Issue",
            "body": "Description",
            "state": state,
            "labels": [{"name": "bug"}],
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-16T12:00:00Z",
            "user": {"login": "author"},
            "html_url": "https://gitea.example.com/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.state == expected_state

    def test_parse_issue_missing_body(self, provider: GiteaRestProvider) -> None:
        """Should handle missing body field."""
        data = {
            "id": 3,
            "number": 12,
            "title": "No Body",
            "state": "open",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "user": {"login": "user"},
            "html_url": "https://gitea.example.com/issues/12",
        }

        issue = provider._parse_issue(data)

        assert issue.body == ""

    def test_parse_comment(self, provider: GiteaRestProvider) -> None:
        """Should parse comment correctly."""
        data = {
            "id": 100,
            "body": "Comment text",
            "user": {"login": "commenter"},
            "created_at": "2024-02-01T08:30:00Z",
        }

        comment = provider._parse_comment(data)

        assert comment.id == 100
        assert comment.body == "Comment text"
        assert comment.author == "commenter"

    def test_parse_pull_request_body(self, provider: GiteaRestProvider) -> None:
        """Should parse PR body correctly."""
        data = {
            "id": 500,
            "number": 50,
            "title": "Feature PR",
            "body": "PR description",
            "state": "open",
            "head": {"ref": "feature-branch"},
            "base": {"ref": "main"},
            "html_url": "https://gitea.example.com/pull/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_pull_request(data)

        assert pr.body == "PR description"

    def test_parse_pull_request_missing_body(self, provider: GiteaRestProvider) -> None:
        """Should handle missing body field with empty string."""
        data = {
            "id": 500,
            "number": 50,
            "title": "Feature PR",
            # body key intentionally omitted to test .get default
            "state": "open",
            "head": {"ref": "feature-branch"},
            "base": {"ref": "main"},
            "html_url": "https://gitea.example.com/pull/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_pull_request(data)

        assert pr.body == ""

    def test_parse_datetime_with_z(self, provider: GiteaRestProvider) -> None:
        """Should parse ISO datetime with Z suffix."""
        data = {
            "id": 1,
            "number": 1,
            "title": "Test",
            "body": "",
            "state": "open",
            "labels": [],
            "created_at": "2024-06-15T10:30:00Z",
            "updated_at": "2024-06-15T10:30:00Z",
            "user": {"login": "user"},
            "html_url": "https://example.com/1",
        }

        issue = provider._parse_issue(data)

        assert issue.created_at.year == 2024
        assert issue.created_at.month == 6
        assert issue.created_at.day == 15
        assert issue.created_at.hour == 10
        assert issue.created_at.minute == 30
        assert issue.created_at.tzinfo is not None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestGiteaRestProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_http_error_propagates(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should propagate HTTP errors from API calls."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_issues()

    @pytest.mark.asyncio
    async def test_network_error_propagates(
        self, provider: GiteaRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should propagate network errors."""
        mock_pool.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        provider._pool = mock_pool

        with pytest.raises(httpx.ConnectError):
            await provider.get_issues()
