"""Tests for repo_sapiens/providers/gitlab_rest.py - GitLab REST API provider implementation.

This module provides comprehensive test coverage for the GitLabRestProvider class,
testing initialization, connection management, issue/MR operations, file handling,
branch management, and GitLab-specific field mappings.

Key GitLab differences tested:
- iid -> number mapping (project-scoped ID)
- description -> body mapping
- opened state -> IssueState.OPEN mapping
- System notes filtering in get_comments
- state_event for closing/reopening issues
- Labels as comma-separated strings
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.models.domain import IssueState
from repo_sapiens.providers.gitlab_rest import GitLabRestProvider
from repo_sapiens.utils.connection_pool import HTTPConnectionPool

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def provider() -> GitLabRestProvider:
    """Create a GitLabRestProvider instance for testing."""
    return GitLabRestProvider(
        base_url="https://gitlab.example.com/",
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
    """Sample issue data as returned by GitLab API.

    Note GitLab-specific fields:
    - 'iid' instead of 'number' for project-scoped ID
    - 'description' instead of 'body'
    - 'opened' state instead of 'open'
    - 'labels' as a list of strings (not objects)
    - 'author' dict with 'username' (not 'user' with 'login')
    - 'web_url' instead of 'html_url'
    """
    return {
        "id": 1001,
        "iid": 42,
        "title": "Fix authentication bug",
        "description": "Users cannot log in with special characters in password.",
        "state": "opened",
        "labels": ["bug", "high-priority"],
        "created_at": "2024-06-15T10:30:00Z",
        "updated_at": "2024-06-16T14:45:00Z",
        "author": {"username": "developer123"},
        "web_url": "https://gitlab.example.com/test-owner/test-repo/-/issues/42",
    }


@pytest.fixture
def sample_comment_data() -> dict:
    """Sample note (comment) data as returned by GitLab API.

    Note: GitLab calls comments 'notes' and includes system-generated notes.
    """
    return {
        "id": 5001,
        "body": "I've identified the root cause. Working on a fix.",
        "author": {"username": "reviewer"},
        "created_at": "2024-06-16T16:00:00Z",
        "system": False,
    }


@pytest.fixture
def sample_system_note_data() -> dict:
    """Sample system-generated note as returned by GitLab API."""
    return {
        "id": 5002,
        "body": "added ~bug label",
        "author": {"username": "reviewer"},
        "created_at": "2024-06-16T16:01:00Z",
        "system": True,
    }


@pytest.fixture
def sample_branch_data() -> dict:
    """Sample branch data as returned by GitLab API."""
    return {
        "name": "feature/authentication-fix",
        "commit": {
            "id": "abc123def456789",
            "message": "Fix password validation",
        },
    }


@pytest.fixture
def sample_mr_data() -> dict:
    """Sample merge request data as returned by GitLab API.

    Note GitLab-specific fields:
    - 'iid' for project-scoped MR number
    - 'source_branch' instead of 'head'
    - 'target_branch' instead of 'base'
    - 'description' instead of 'body'
    """
    return {
        "id": 2001,
        "iid": 15,
        "title": "Fix authentication with special characters",
        "description": "This MR resolves the authentication issue.",
        "state": "opened",
        "source_branch": "feature/auth-fix",
        "target_branch": "main",
        "web_url": "https://gitlab.example.com/test-owner/test-repo/-/merge_requests/15",
        "created_at": "2024-06-17T09:00:00Z",
    }


# =============================================================================
# Initialization Tests
# =============================================================================


class TestGitLabRestProviderInit:
    """Tests for GitLabRestProvider initialization."""

    @pytest.mark.parametrize(
        "base_url,expected_base,expected_api",
        [
            (
                "https://gitlab.test.com",
                "https://gitlab.test.com",
                "https://gitlab.test.com/api/v4",
            ),
            (
                "https://gitlab.test.com/",
                "https://gitlab.test.com",
                "https://gitlab.test.com/api/v4",
            ),
            (
                "http://localhost:8080",
                "http://localhost:8080",
                "http://localhost:8080/api/v4",
            ),
        ],
        ids=["no_trailing_slash", "with_trailing_slash", "custom_port"],
    )
    def test_init_url_handling(self, base_url, expected_base, expected_api) -> None:
        """Should handle various URL formats correctly."""
        provider = GitLabRestProvider(
            base_url=base_url,
            token="token",
            owner="owner",
            repo="repo",
        )

        assert provider.base_url == expected_base
        assert provider.api_base == expected_api
        assert provider._pool is None

    def test_init_project_path_encoding(self) -> None:
        """Should URL-encode the project path for GitLab API."""
        provider = GitLabRestProvider(
            base_url="https://gitlab.com",
            token="token",
            owner="my-group/sub-group",
            repo="my-repo",
        )

        # Forward slashes should be encoded
        assert provider.project_path == "my-group%2Fsub-group%2Fmy-repo"

    def test_init_simple_project_path(self) -> None:
        """Should encode simple project paths correctly."""
        provider = GitLabRestProvider(
            base_url="https://gitlab.com",
            token="token",
            owner="user",
            repo="project",
        )

        assert provider.project_path == "user%2Fproject"


# =============================================================================
# Connection Management Tests
# =============================================================================


class TestGitLabRestProviderConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.gitlab_rest.get_pool")
    async def test_connect_creates_client(
        self, mock_get_pool: AsyncMock, provider: GitLabRestProvider
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

        # GitLab uses PRIVATE-TOKEN header, not Authorization
        assert "PRIVATE-TOKEN" in call_kwargs["headers"]
        assert call_kwargs["headers"]["PRIVATE-TOKEN"] == "test_api_token_12345"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert provider._pool is mock_pool

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.gitlab_rest.get_pool")
    async def test_connect_verifies_connectivity(
        self, mock_get_pool: AsyncMock, provider: GitLabRestProvider
    ) -> None:
        """Should verify connectivity by calling /version endpoint."""
        mock_pool = AsyncMock(spec=HTTPConnectionPool)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_pool.get = AsyncMock(return_value=mock_response)
        mock_get_pool.return_value = mock_pool

        await provider.connect()

        mock_pool.get.assert_called_once_with("/version")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.gitlab_rest.get_pool")
    async def test_connect_raises_on_failure(
        self, mock_get_pool: AsyncMock, provider: GitLabRestProvider
    ) -> None:
        """Should raise ConnectionError if verification fails."""
        mock_pool = AsyncMock(spec=HTTPConnectionPool)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_pool.get = AsyncMock(return_value=mock_response)
        mock_get_pool.return_value = mock_pool

        with pytest.raises(ConnectionError, match="Failed to connect to GitLab"):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_disconnect_clears_pool(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should clear pool reference on disconnect."""
        provider._pool = mock_pool

        await provider.disconnect()

        assert provider._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, provider: GitLabRestProvider) -> None:
        """Should handle disconnect when no pool exists."""
        assert provider._pool is None
        await provider.disconnect()
        assert provider._pool is None


# =============================================================================
# Issue Operations Tests
# =============================================================================


class TestGitLabRestProviderIssues:
    """Tests for issue operations with GitLab-specific field mappings."""

    @pytest.mark.asyncio
    async def test_get_issues_returns_parsed_issues(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should retrieve and parse issues correctly with GitLab field mappings."""
        mock_response = MagicMock()
        mock_response.json.return_value = [sample_issue_data]
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issues = await provider.get_issues(state="open")

        assert len(issues) == 1
        issue = issues[0]
        assert issue.id == 1001
        assert issue.number == 42  # Mapped from 'iid'
        assert issue.title == "Fix authentication bug"
        assert issue.body == "Users cannot log in with special characters in password."
        assert issue.state == IssueState.OPEN  # Mapped from 'opened'
        assert issue.labels == ["bug", "high-priority"]  # Already list of strings
        assert issue.author == "developer123"  # From 'author.username'

        mock_pool.get.assert_called_once()
        call_args = mock_pool.get.call_args
        assert "/projects/" in call_args.args[0]
        assert "/issues" in call_args.args[0]
        # GitLab uses 'opened' instead of 'open'
        assert call_args.kwargs["params"]["state"] == "opened"

    @pytest.mark.asyncio
    async def test_get_issues_maps_state_correctly(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should map 'open'/'closed'/'all' to GitLab states."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        # Test 'open' -> 'opened'
        await provider.get_issues(state="open")
        assert mock_pool.get.call_args.kwargs["params"]["state"] == "opened"

        # Test 'closed' -> 'closed'
        await provider.get_issues(state="closed")
        assert mock_pool.get.call_args.kwargs["params"]["state"] == "closed"

        # Test 'all' -> 'all'
        await provider.get_issues(state="all")
        assert mock_pool.get.call_args.kwargs["params"]["state"] == "all"

    @pytest.mark.asyncio
    async def test_get_issues_with_labels_filter(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should filter issues by labels as comma-separated string."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.get_issues(labels=["bug", "critical"], state="all")

        call_args = mock_pool.get.call_args
        assert call_args.kwargs["params"]["labels"] == "bug,critical"

    @pytest.mark.asyncio
    async def test_get_issue_by_number(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should retrieve single issue by number (iid)."""
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
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should create issue using 'description' field instead of 'body'."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.create_issue(title="New bug report", body="Description of the bug")

        assert issue.id == 1001
        call_args = mock_pool.post.call_args
        posted_data = call_args.kwargs["json"]
        assert posted_data["title"] == "New bug report"
        # GitLab uses 'description' not 'body'
        assert posted_data["description"] == "Description of the bug"
        assert "labels" not in posted_data

    @pytest.mark.asyncio
    async def test_create_issue_with_labels(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should create issue with labels as comma-separated string."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.create_issue(
            title="New feature", body="Feature description", labels=["bug", "enhancement"]
        )

        create_call = mock_pool.post.call_args
        posted_data = create_call.kwargs["json"]
        # GitLab expects comma-separated string, not label IDs
        assert posted_data["labels"] == "bug,enhancement"

    @pytest.mark.asyncio
    async def test_update_issue_title_and_body(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should update issue using 'description' field for body."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.put = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.update_issue(
            issue_number=42, title="Updated title", body="Updated description"
        )

        assert issue.number == 42
        put_call = mock_pool.put.call_args
        patched_data = put_call.kwargs["json"]
        assert patched_data["title"] == "Updated title"
        # GitLab uses 'description' not 'body'
        assert patched_data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_issue_state_close(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should use state_event 'close' to close an issue."""
        sample_issue_data["state"] = "closed"
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.put = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.update_issue(issue_number=42, state="closed")

        put_call = mock_pool.put.call_args
        # GitLab uses state_event, not state
        assert put_call.kwargs["json"]["state_event"] == "close"
        assert issue.state == IssueState.CLOSED

    @pytest.mark.asyncio
    async def test_update_issue_state_reopen(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should use state_event 'reopen' to reopen an issue."""
        sample_issue_data["state"] = "opened"
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.put = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        issue = await provider.update_issue(issue_number=42, state="open")

        put_call = mock_pool.put.call_args
        # GitLab uses 'reopen' not 'open'
        assert put_call.kwargs["json"]["state_event"] == "reopen"
        assert issue.state == IssueState.OPEN

    @pytest.mark.asyncio
    async def test_update_issue_labels(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_issue_data: dict,
    ) -> None:
        """Should update issue labels as comma-separated string."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_issue_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.put = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.update_issue(issue_number=42, labels=["bug", "enhancement"])

        put_call = mock_pool.put.call_args
        # GitLab uses comma-separated string, not label IDs
        assert put_call.kwargs["json"]["labels"] == "bug,enhancement"


# =============================================================================
# Comment Operations Tests
# =============================================================================


class TestGitLabRestProviderComments:
    """Tests for comment (notes) operations with system note filtering."""

    @pytest.mark.asyncio
    async def test_add_comment(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_comment_data: dict,
    ) -> None:
        """Should add note to issue using notes endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_comment_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.post = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        comment = await provider.add_comment(42, "Test comment body")

        assert comment.id == 5001
        assert comment.author == "reviewer"
        call_args = mock_pool.post.call_args
        # GitLab uses 'notes' endpoint
        assert "/issues/42/notes" in call_args.args[0]
        assert call_args.kwargs["json"]["body"] == "Test comment body"

    @pytest.mark.asyncio
    async def test_get_comments_filters_system_notes(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_comment_data: dict,
        sample_system_note_data: dict,
    ) -> None:
        """Should filter out system-generated notes."""
        mock_response = MagicMock()
        mock_response.json.return_value = [sample_comment_data, sample_system_note_data]
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        comments = await provider.get_comments(42)

        # Should only return user comment, not system note
        assert len(comments) == 1
        assert comments[0].id == 5001
        assert comments[0].body == "I've identified the root cause. Working on a fix."

    @pytest.mark.asyncio
    async def test_get_comments_multiple_user_notes(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_comment_data: dict,
    ) -> None:
        """Should return all user comments."""
        second_comment = {
            "id": 5003,
            "body": "LGTM, merging now.",
            "author": {"username": "maintainer"},
            "created_at": "2024-06-17T08:00:00Z",
            "system": False,
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

    @pytest.mark.asyncio
    async def test_get_comments_all_system_notes_filtered(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_system_note_data: dict,
    ) -> None:
        """Should return empty list if all notes are system-generated."""
        second_system_note = {
            "id": 5004,
            "body": "changed the description",
            "author": {"username": "developer"},
            "created_at": "2024-06-17T09:00:00Z",
            "system": True,
        }

        mock_response = MagicMock()
        mock_response.json.return_value = [sample_system_note_data, second_system_note]
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        comments = await provider.get_comments(42)

        assert len(comments) == 0


# =============================================================================
# Merge Request Operations Tests
# =============================================================================


class TestGitLabRestProviderMergeRequests:
    """Tests for merge request operations (GitLab's equivalent of pull requests)."""

    @pytest.mark.asyncio
    async def test_create_pull_request_new(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_mr_data: dict,
    ) -> None:
        """Should create new merge request using GitLab MR API."""
        list_response = MagicMock()
        list_response.json.return_value = []
        list_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = sample_mr_data
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=list_response)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        pr = await provider.create_pull_request(
            title="New feature MR",
            body="MR description",
            head="feature/auth-fix",
            base="main",
        )

        assert pr.number == 15  # Mapped from 'iid'
        assert pr.title == "Fix authentication with special characters"
        assert pr.head == "feature/auth-fix"  # Mapped from 'source_branch'
        assert pr.base == "main"  # Mapped from 'target_branch'

        post_call = mock_pool.post.call_args
        posted_data = post_call.kwargs["json"]
        # GitLab uses source_branch/target_branch
        assert posted_data["source_branch"] == "feature/auth-fix"
        assert posted_data["target_branch"] == "main"
        # GitLab uses 'description' not 'body'
        assert posted_data["description"] == "MR description"

    @pytest.mark.asyncio
    async def test_create_pull_request_updates_existing(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_mr_data: dict,
    ) -> None:
        """Should update existing MR if one exists for the same branches."""
        existing_mr = {
            "iid": 15,
            "source_branch": "feature/auth-fix",
            "target_branch": "main",
        }
        list_response = MagicMock()
        list_response.json.return_value = [existing_mr]
        list_response.raise_for_status = MagicMock()

        update_response = MagicMock()
        update_response.json.return_value = sample_mr_data
        update_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=list_response)
        mock_pool.put = AsyncMock(return_value=update_response)
        provider._pool = mock_pool

        pr = await provider.create_pull_request(
            title="Updated MR title",
            body="Updated description",
            head="feature/auth-fix",
            base="main",
        )

        assert pr.number == 15
        mock_pool.put.assert_called_once()
        mock_pool.post.assert_not_called()

        put_call = mock_pool.put.call_args
        # GitLab uses 'description' not 'body'
        assert put_call.kwargs["json"]["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_create_pull_request_with_labels(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_mr_data: dict,
    ) -> None:
        """Should create MR with labels as comma-separated string."""
        list_response = MagicMock()
        list_response.json.return_value = []
        list_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = sample_mr_data
        create_response.raise_for_status = MagicMock()

        mock_pool.get = AsyncMock(return_value=list_response)
        mock_pool.post = AsyncMock(return_value=create_response)
        provider._pool = mock_pool

        await provider.create_pull_request(
            title="Feature",
            body="Description",
            head="feature",
            base="main",
            labels=["enhancement", "ready"],
        )

        post_call = mock_pool.post.call_args
        # GitLab uses comma-separated labels
        assert post_call.kwargs["json"]["labels"] == "enhancement,ready"

    @pytest.mark.asyncio
    async def test_get_merge_request(
        self,
        provider: GitLabRestProvider,
        mock_pool: AsyncMock,
        sample_mr_data: dict,
    ) -> None:
        """Should retrieve merge request by number (iid)."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_mr_data
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        pr = await provider.get_merge_request(15)

        assert pr is not None
        assert pr.number == 15
        assert pr.title == "Fix authentication with special characters"

    @pytest.mark.asyncio
    async def test_get_merge_request_not_found(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should return None for non-existent MR."""
        http_error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        mock_pool.get = AsyncMock(side_effect=http_error)
        provider._pool = mock_pool

        pr = await provider.get_merge_request(999)

        assert pr is None

    @pytest.mark.asyncio
    async def test_get_diff_from_mr(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should get diff from MR changes endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "changes": [
                {
                    "old_path": "file.py",
                    "new_path": "file.py",
                    "diff": "@@ -1,3 +1,5 @@\n+new line",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        diff = await provider.get_diff("main", "feature", mr_number=42)

        assert "diff --git a/file.py b/file.py" in diff
        assert "+new line" in diff
        call_args = mock_pool.get.call_args
        assert "/merge_requests/42/changes" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_diff_compare_branches(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should compare branches when no MR number provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "diffs": [
                {
                    "old_path": "src/auth.py",
                    "new_path": "src/auth.py",
                    "diff": "@@ -1,3 +1,5 @@\n+# Auth module",
                },
                {
                    "old_path": "tests/test_auth.py",
                    "new_path": "tests/test_auth.py",
                    "diff": "@@ -0,0 +1,10 @@\n+import pytest",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        diff = await provider.get_diff("main", "feature")

        assert "diff --git a/src/auth.py" in diff
        assert "diff --git a/tests/test_auth.py" in diff
        call_args = mock_pool.get.call_args
        assert "/repository/compare" in call_args.args[0]
        assert call_args.kwargs["params"]["from"] == "main"
        assert call_args.kwargs["params"]["to"] == "feature"


# =============================================================================
# Branch Operations Tests
# =============================================================================


class TestGitLabRestProviderBranches:
    """Tests for branch operations."""

    @pytest.mark.asyncio
    async def test_get_branch(
        self,
        provider: GitLabRestProvider,
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
    async def test_get_branch_encodes_name(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should URL-encode branch name in API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "feature/test",
            "commit": {"id": "abc123"},
        }
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.get_branch("feature/test")

        call_args = mock_pool.get.call_args
        # Branch name should be URL-encoded (/ -> %2F)
        assert "feature%2Ftest" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_get_branch_not_found(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
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
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
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
        provider: GitLabRestProvider,
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
        # GitLab uses 'branch' and 'ref' for create
        assert posted_data["branch"] == "feature/new-feature"
        assert posted_data["ref"] == "main"

    @pytest.mark.asyncio
    async def test_create_branch_already_exists(
        self,
        provider: GitLabRestProvider,
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


# =============================================================================
# File Operations Tests
# =============================================================================


class TestGitLabRestProviderFiles:
    """Tests for file operations."""

    @pytest.mark.asyncio
    async def test_get_file(self, provider: GitLabRestProvider, mock_pool: AsyncMock) -> None:
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
        # GitLab URL-encodes the file path
        assert "/repository/files/" in call_args.args[0]
        assert call_args.kwargs["params"]["ref"] == "main"

    @pytest.mark.asyncio
    async def test_get_file_encodes_path(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should URL-encode file path in API call."""
        file_content = "content"
        encoded_content = base64.b64encode(file_content.encode()).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": encoded_content}
        mock_response.raise_for_status = MagicMock()
        mock_pool.get = AsyncMock(return_value=mock_response)
        provider._pool = mock_pool

        await provider.get_file("src/main/test.py", ref="main")

        call_args = mock_pool.get.call_args
        # Path separators should be URL-encoded
        assert "src%2Fmain%2Ftest.py" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_commit_file_new(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should create new file when it doesn't exist."""
        not_found_response = MagicMock()
        not_found_response.status_code = 404
        mock_pool.get = AsyncMock(return_value=not_found_response)

        create_response = MagicMock()
        create_response.json.return_value = {"commit_id": "newfile123", "file_path": "new_file.txt"}
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
        assert posted_data["commit_message"] == "Add new file"
        # GitLab doesn't base64 encode, just sends raw content
        assert posted_data["content"] == "New file content"
        assert posted_data["branch"] == "main"

    @pytest.mark.asyncio
    async def test_commit_file_update(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should update existing file with PUT."""
        existing_response = MagicMock()
        existing_response.status_code = 200
        mock_pool.get = AsyncMock(return_value=existing_response)

        update_response = MagicMock()
        update_response.json.return_value = {"commit_id": "updated456", "file_path": "existing.txt"}
        update_response.raise_for_status = MagicMock()
        mock_pool.put = AsyncMock(return_value=update_response)

        provider._pool = mock_pool

        sha = await provider.commit_file(
            path="existing.txt",
            content="Updated content",
            message="Update file",
            branch="develop",
        )

        assert sha == "updated456"
        # Should use PUT for update
        mock_pool.put.assert_called_once()


# =============================================================================
# Model Parsing Tests
# =============================================================================


class TestGitLabRestProviderParsing:
    """Tests for model parsing methods with GitLab-specific field mappings."""

    @pytest.mark.parametrize(
        "state,expected_state",
        [("opened", IssueState.OPEN), ("closed", IssueState.CLOSED)],
        ids=["opened", "closed"],
    )
    def test_parse_issue_state(self, provider: GitLabRestProvider, state, expected_state) -> None:
        """Should parse GitLab 'opened'/'closed' states correctly."""
        data = {
            "id": 1,
            "iid": 10,
            "title": "Test Issue",
            "description": "Description",
            "state": state,
            "labels": ["bug"],
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-16T12:00:00Z",
            "author": {"username": "author"},
            "web_url": "https://gitlab.example.com/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.state == expected_state

    def test_parse_issue_iid_to_number(self, provider: GitLabRestProvider) -> None:
        """Should map 'iid' to 'number' field."""
        data = {
            "id": 1001,
            "iid": 42,
            "title": "Test Issue",
            "description": "Description",
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/issues/42",
        }

        issue = provider._parse_issue(data)

        assert issue.id == 1001
        assert issue.number == 42

    def test_parse_issue_description_to_body(self, provider: GitLabRestProvider) -> None:
        """Should map 'description' to 'body' field."""
        data = {
            "id": 1,
            "iid": 10,
            "title": "Test Issue",
            "description": "This is the issue description",
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.body == "This is the issue description"

    def test_parse_issue_missing_description(self, provider: GitLabRestProvider) -> None:
        """Should handle missing description field with empty string."""
        data = {
            "id": 3,
            "iid": 12,
            "title": "No Body",
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/issues/12",
        }

        issue = provider._parse_issue(data)

        assert issue.body == ""

    def test_parse_issue_null_description(self, provider: GitLabRestProvider) -> None:
        """Should handle null description with empty string."""
        data = {
            "id": 3,
            "iid": 12,
            "title": "Null Body",
            "description": None,
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/issues/12",
        }

        issue = provider._parse_issue(data)

        assert issue.body == ""

    def test_parse_issue_labels_as_strings(self, provider: GitLabRestProvider) -> None:
        """Should handle labels as list of strings (GitLab format)."""
        data = {
            "id": 1,
            "iid": 10,
            "title": "Test Issue",
            "description": "Description",
            "state": "opened",
            "labels": ["bug", "high-priority", "backend"],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.labels == ["bug", "high-priority", "backend"]

    def test_parse_issue_author_username(self, provider: GitLabRestProvider) -> None:
        """Should extract author from 'author.username' (not 'user.login')."""
        data = {
            "id": 1,
            "iid": 10,
            "title": "Test Issue",
            "description": "Description",
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "developer123"},
            "web_url": "https://gitlab.example.com/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.author == "developer123"

    def test_parse_issue_web_url(self, provider: GitLabRestProvider) -> None:
        """Should use 'web_url' field (not 'html_url')."""
        data = {
            "id": 1,
            "iid": 10,
            "title": "Test Issue",
            "description": "Description",
            "state": "opened",
            "labels": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "author": {"username": "user"},
            "web_url": "https://gitlab.example.com/group/project/-/issues/10",
        }

        issue = provider._parse_issue(data)

        assert issue.url == "https://gitlab.example.com/group/project/-/issues/10"

    def test_parse_comment(self, provider: GitLabRestProvider) -> None:
        """Should parse note (comment) correctly."""
        data = {
            "id": 100,
            "body": "Comment text",
            "author": {"username": "commenter"},
            "created_at": "2024-02-01T08:30:00Z",
        }

        comment = provider._parse_comment(data)

        assert comment.id == 100
        assert comment.body == "Comment text"
        assert comment.author == "commenter"

    def test_parse_merge_request_iid_to_number(self, provider: GitLabRestProvider) -> None:
        """Should map 'iid' to 'number' for MRs."""
        data = {
            "id": 500,
            "iid": 50,
            "title": "Feature MR",
            "description": "MR description",
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/merge_requests/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_merge_request(data)

        assert pr.id == 500
        assert pr.number == 50

    def test_parse_merge_request_branches(self, provider: GitLabRestProvider) -> None:
        """Should map 'source_branch'/'target_branch' to 'head'/'base'."""
        data = {
            "id": 500,
            "iid": 50,
            "title": "Feature MR",
            "description": "MR description",
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/merge_requests/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_merge_request(data)

        assert pr.head == "feature-branch"
        assert pr.base == "main"

    def test_parse_merge_request_description_to_body(self, provider: GitLabRestProvider) -> None:
        """Should map 'description' to 'body' for MRs."""
        data = {
            "id": 500,
            "iid": 50,
            "title": "Feature MR",
            "description": "This is the MR description",
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/merge_requests/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_merge_request(data)

        assert pr.body == "This is the MR description"

    def test_parse_merge_request_missing_description(self, provider: GitLabRestProvider) -> None:
        """Should handle missing description with empty string."""
        data = {
            "id": 500,
            "iid": 50,
            "title": "Feature MR",
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/merge_requests/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_merge_request(data)

        assert pr.body == ""

    def test_parse_merge_request_null_description(self, provider: GitLabRestProvider) -> None:
        """Should handle null description with empty string."""
        data = {
            "id": 500,
            "iid": 50,
            "title": "Feature MR",
            "description": None,
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "web_url": "https://gitlab.example.com/merge_requests/50",
            "created_at": "2024-03-01T14:00:00Z",
        }

        pr = provider._parse_merge_request(data)

        assert pr.body == ""

    def test_parse_datetime_with_z(self, provider: GitLabRestProvider) -> None:
        """Should parse ISO datetime with Z suffix."""
        data = {
            "id": 1,
            "iid": 1,
            "title": "Test",
            "description": "",
            "state": "opened",
            "labels": [],
            "created_at": "2024-06-15T10:30:00Z",
            "updated_at": "2024-06-15T10:30:00Z",
            "author": {"username": "user"},
            "web_url": "https://example.com/1",
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


class TestGitLabRestProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_http_error_propagates(
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
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
        self, provider: GitLabRestProvider, mock_pool: AsyncMock
    ) -> None:
        """Should propagate network errors."""
        mock_pool.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        provider._pool = mock_pool

        with pytest.raises(httpx.ConnectError):
            await provider.get_issues()
