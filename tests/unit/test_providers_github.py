"""Tests for repo_sapiens/providers/github_rest.py - GitHub provider implementation."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from repo_sapiens.models.domain import IssueState
from repo_sapiens.providers.github_rest import GitHubRestProvider


@pytest.fixture
def mock_github_client():
    """Create a mock Github client."""
    client = Mock()
    client.close = Mock()
    return client


@pytest.fixture
def mock_github_repo():
    """Create a mock GitHub repository."""
    repo = Mock()
    return repo


@pytest.fixture
def provider():
    """Create GitHubRestProvider instance."""
    return GitHubRestProvider(
        token="ghp_test_token_123",
        owner="test-owner",
        repo="test-repo",
        base_url="https://api.github.com",
    )


class TestGitHubRestProviderInit:
    """Tests for GitHubRestProvider initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default base URL."""
        provider = GitHubRestProvider(
            token="test-token",
            owner="owner",
            repo="repo",
        )

        assert provider.token == "test-token"
        assert provider.owner == "owner"
        assert provider.repo == "repo"
        assert provider.base_url == "https://api.github.com"
        assert provider._client is None
        assert provider._repo is None

    def test_init_with_custom_base_url(self):
        """Should initialize with custom GitHub Enterprise URL."""
        provider = GitHubRestProvider(
            token="ghe-token",
            owner="enterprise-org",
            repo="private-repo",
            base_url="https://github.enterprise.com/api/v3",
        )

        assert provider.base_url == "https://github.enterprise.com/api/v3"
        assert provider.owner == "enterprise-org"
        assert provider.repo == "private-repo"


class TestGitHubRestProviderConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_connect(self, mock_github_class, provider, mock_github_repo):
        """Should initialize GitHub client on connect."""
        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_github_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        mock_github_class.assert_called_once_with(
            "ghp_test_token_123", base_url="https://api.github.com"
        )
        mock_client.get_repo.assert_called_once_with("test-owner/test-repo")
        assert provider._client is mock_client
        assert provider._repo is mock_github_repo

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_disconnect(self, mock_github_class, provider):
        """Should close client and clear references on disconnect."""
        mock_client = Mock()
        mock_client.close = Mock()
        mock_client.get_repo = Mock(return_value=Mock())
        mock_github_class.return_value = mock_client

        await provider.connect()
        await provider.disconnect()

        mock_client.close.assert_called_once()
        assert provider._client is None
        assert provider._repo is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, provider):
        """Should handle disconnect when not connected."""
        # Should not raise error
        await provider.disconnect()
        assert provider._client is None


class TestGitHubRestProviderIssues:
    """Tests for issue operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_issues_open(self, mock_github_class, provider):
        """Should retrieve open issues."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1001
        mock_gh_issue.number = 42
        mock_gh_issue.title = "Test Issue"
        mock_gh_issue.body = "Issue description"
        mock_gh_issue.state = "open"
        # Create mock labels with name attribute
        mock_label1 = Mock()
        mock_label1.name = "bug"
        mock_label2 = Mock()
        mock_label2.name = "enhancement"
        mock_gh_issue.labels = [mock_label1, mock_label2]
        mock_gh_issue.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_gh_issue.updated_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
        mock_gh_issue.user = Mock(login="testuser")
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/42"

        mock_repo = Mock()
        mock_repo.get_issues = Mock(return_value=[mock_gh_issue])

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        issues = await provider.get_issues(state="open")

        assert len(issues) == 1
        assert issues[0].number == 42
        assert issues[0].title == "Test Issue"
        assert issues[0].state == IssueState.OPEN
        assert issues[0].labels == ["bug", "enhancement"]

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_issues_with_labels(self, mock_github_class, provider):
        """Should retrieve issues filtered by labels."""
        mock_repo = Mock()
        mock_repo.get_issues = Mock(return_value=[])

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        await provider.get_issues(labels=["bug", "high-priority"])

        mock_repo.get_issues.assert_called_once()
        call_args = mock_repo.get_issues.call_args
        assert call_args.kwargs["state"] == "open"
        assert call_args.kwargs["labels"] == ["bug", "high-priority"]

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_issue_by_number(self, mock_github_class, provider):
        """Should retrieve single issue by number."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1002
        mock_gh_issue.number = 123
        mock_gh_issue.title = "Specific Issue"
        mock_gh_issue.body = "Description"
        mock_gh_issue.state = "closed"
        mock_gh_issue.labels = []
        mock_gh_issue.created_at = datetime.now(UTC)
        mock_gh_issue.updated_at = datetime.now(UTC)
        mock_gh_issue.user = Mock(login="testuser")
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/123"

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_gh_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        issue = await provider.get_issue(123)

        assert issue.number == 123
        assert issue.title == "Specific Issue"
        assert issue.state == IssueState.CLOSED

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_issue(self, mock_github_class, provider):
        """Should create new issue."""
        mock_created_issue = Mock()
        mock_created_issue.id = 1003
        mock_created_issue.number = 999
        mock_created_issue.title = "New Issue"
        mock_created_issue.body = "New description"
        mock_created_issue.state = "open"
        mock_label = Mock()
        mock_label.name = "bug"
        mock_created_issue.labels = [mock_label]
        mock_created_issue.created_at = datetime.now(UTC)
        mock_created_issue.updated_at = datetime.now(UTC)
        mock_created_issue.user = Mock(login="creator")
        mock_created_issue.html_url = "https://github.com/test-owner/test-repo/issues/999"

        mock_repo = Mock()
        mock_repo.create_issue = Mock(return_value=mock_created_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        issue = await provider.create_issue(
            title="New Issue", body="New description", labels=["bug"]
        )

        assert issue.number == 999
        assert issue.title == "New Issue"
        mock_repo.create_issue.assert_called_once_with(
            title="New Issue", body="New description", labels=["bug"]
        )

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_update_issue(self, mock_github_class, provider):
        """Should update existing issue."""
        mock_issue = Mock()
        mock_issue.id = 1004
        mock_issue.number = 42
        mock_issue.title = "Updated Title"
        mock_issue.body = "Updated body"
        mock_issue.state = "closed"
        mock_label = Mock()
        mock_label.name = "resolved"
        mock_issue.labels = [mock_label]
        mock_issue.created_at = datetime.now(UTC)
        mock_issue.updated_at = datetime.now(UTC)
        mock_issue.user = Mock(login="updater")
        mock_issue.html_url = "https://github.com/test-owner/test-repo/issues/42"
        mock_issue.edit = Mock()

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        updated = await provider.update_issue(
            42, title="Updated Title", state="closed", labels=["resolved"]
        )

        assert updated.number == 42
        assert updated.title == "Updated Title"
        assert mock_issue.edit.call_count >= 1


class TestGitHubRestProviderComments:
    """Tests for comment operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_add_comment(self, mock_github_class, provider):
        """Should add comment to issue."""
        mock_comment = Mock()
        mock_comment.id = 1
        mock_comment.body = "Test comment"
        mock_comment.user = Mock(login="testuser")
        mock_comment.created_at = datetime.now(UTC)

        mock_issue = Mock()
        mock_issue.create_comment = Mock(return_value=mock_comment)

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        comment = await provider.add_comment(42, "Test comment")

        assert comment.id == 1
        assert comment.body == "Test comment"
        assert comment.author == "testuser"

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_comments(self, mock_github_class, provider):
        """Should retrieve all comments for issue."""
        mock_comments = [
            Mock(id=1, body="First", user=Mock(login="user1"), created_at=datetime.now(UTC)),
            Mock(id=2, body="Second", user=Mock(login="user2"), created_at=datetime.now(UTC)),
        ]

        mock_issue = Mock()
        mock_issue.get_comments = Mock(return_value=mock_comments)

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        comments = await provider.get_comments(42)

        assert len(comments) == 2
        assert comments[0].body == "First"
        assert comments[1].body == "Second"


class TestGitHubRestProviderBranches:
    """Tests for branch operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_branch(self, mock_github_class, provider):
        """Should create new branch from source."""
        mock_source_ref = Mock()
        mock_source_ref.object = Mock(sha="abc123")

        mock_branch = Mock()
        mock_branch.name = "feature-branch"
        mock_branch.commit = Mock(sha="abc123")
        mock_branch.protected = False

        mock_repo = Mock()
        mock_repo.get_git_ref = Mock(return_value=mock_source_ref)
        mock_repo.create_git_ref = Mock()
        mock_repo.get_branch = Mock(return_value=mock_branch)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        branch = await provider.create_branch("feature-branch", "main")

        assert branch.name == "feature-branch"
        assert branch.sha == "abc123"
        assert branch.protected is False

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_branch(self, mock_github_class, provider):
        """Should retrieve branch information."""
        mock_branch = Mock()
        mock_branch.name = "main"
        mock_branch.commit = Mock(sha="xyz789")
        mock_branch.protected = True

        mock_repo = Mock()
        mock_repo.get_branch = Mock(return_value=mock_branch)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        branch = await provider.get_branch("main")

        assert branch.name == "main"
        assert branch.sha == "xyz789"
        assert branch.protected is True

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_branch_not_found(self, mock_github_class, provider):
        """Should return None for non-existent branch."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_branch = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        branch = await provider.get_branch("nonexistent")

        assert branch is None


class TestGitHubRestProviderFiles:
    """Tests for file operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_file(self, mock_github_class, provider):
        """Should retrieve file contents."""
        mock_file = Mock()
        mock_file.decoded_content = b"File contents here"

        mock_repo = Mock()
        mock_repo.get_contents = Mock(return_value=mock_file)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        content = await provider.get_file("README.md", ref="main")

        assert content == "File contents here"

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_commit_file_new(self, mock_github_class, provider):
        """Should create new file."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_contents = Mock(side_effect=GithubException(404, "Not Found"))
        mock_repo.create_file = Mock(return_value={"commit": Mock(sha="new123")})

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        sha = await provider.commit_file("new.txt", "New content", "Add new file", "main")

        assert sha == "new123"

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_commit_file_update(self, mock_github_class, provider):
        """Should update existing file."""
        mock_existing = Mock()
        mock_existing.sha = "old123"

        mock_repo = Mock()
        mock_repo.get_contents = Mock(return_value=mock_existing)
        mock_repo.update_file = Mock(return_value={"commit": Mock(sha="updated456")})

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        sha = await provider.commit_file("existing.txt", "Updated content", "Update file", "main")

        assert sha == "updated456"


class TestGitHubRestProviderPullRequests:
    """Tests for pull request operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_pull_request(self, mock_github_class, provider):
        """Should create pull request."""
        mock_pr = Mock()
        mock_pr.id = 2001
        mock_pr.number = 100
        mock_pr.title = "Feature PR"
        mock_pr.body = "PR description"
        mock_pr.state = "open"
        mock_pr.head = Mock(ref="feature")
        mock_pr.base = Mock(ref="main")
        mock_pr.html_url = "https://github.com/test-owner/test-repo/pull/100"
        mock_pr.created_at = datetime.now(UTC)
        mock_pr.add_to_labels = Mock()

        mock_repo = Mock()
        mock_repo.create_pull = Mock(return_value=mock_pr)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        pr = await provider.create_pull_request(
            "Feature PR", "PR description", "feature", "main", labels=["enhancement"]
        )

        assert pr.number == 100
        assert pr.title == "Feature PR"
        mock_pr.add_to_labels.assert_called_once_with("enhancement")


class TestGitHubRestProviderErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_github_exception_propagates(self, mock_github_class, provider):
        """Should propagate GitHub API exceptions."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_issues = Mock(side_effect=GithubException(500, "Server Error"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_issues()


class TestGitHubRestProviderConversions:
    """Tests for model conversion methods."""

    def test_convert_issue_open(self, provider):
        """Should convert GitHub issue to domain Issue model."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1005
        mock_gh_issue.number = 42
        mock_gh_issue.title = "Test"
        mock_gh_issue.body = "Description"
        mock_gh_issue.state = "open"
        mock_label = Mock()
        mock_label.name = "bug"
        mock_gh_issue.labels = [mock_label]
        mock_gh_issue.created_at = datetime(2024, 1, 1, tzinfo=UTC)
        mock_gh_issue.updated_at = datetime(2024, 1, 2, tzinfo=UTC)
        mock_gh_issue.user = Mock(login="testuser")
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/42"

        issue = provider._convert_issue(mock_gh_issue)

        assert issue.number == 42
        assert issue.title == "Test"
        assert issue.state == IssueState.OPEN
        assert issue.labels == ["bug"]

    def test_convert_issue_closed(self, provider):
        """Should convert closed issue."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1006
        mock_gh_issue.number = 1
        mock_gh_issue.title = "Closed"
        mock_gh_issue.body = None  # Test None body
        mock_gh_issue.state = "closed"
        mock_gh_issue.labels = []
        mock_gh_issue.created_at = datetime.now(UTC)
        mock_gh_issue.updated_at = datetime.now(UTC)
        mock_gh_issue.user = Mock(login="closer")
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/1"

        issue = provider._convert_issue(mock_gh_issue)

        assert issue.state == IssueState.CLOSED
        assert issue.body == ""  # None converted to empty string

    def test_convert_issue_unknown_state(self, provider):
        """Should default to OPEN for unknown state."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1007
        mock_gh_issue.number = 2
        mock_gh_issue.title = "Unknown State"
        mock_gh_issue.body = "Description"
        mock_gh_issue.state = "unknown"  # Unknown state
        mock_gh_issue.labels = []
        mock_gh_issue.created_at = datetime.now(UTC)
        mock_gh_issue.updated_at = datetime.now(UTC)
        mock_gh_issue.user = Mock(login="user")
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/2"

        issue = provider._convert_issue(mock_gh_issue)

        assert issue.state == IssueState.OPEN  # Defaults to OPEN

    def test_convert_issue_no_user(self, provider):
        """Should handle missing user."""
        mock_gh_issue = Mock()
        mock_gh_issue.id = 1008
        mock_gh_issue.number = 3
        mock_gh_issue.title = "No User"
        mock_gh_issue.body = "Description"
        mock_gh_issue.state = "open"
        mock_gh_issue.labels = []
        mock_gh_issue.created_at = datetime.now(UTC)
        mock_gh_issue.updated_at = datetime.now(UTC)
        mock_gh_issue.user = None
        mock_gh_issue.html_url = "https://github.com/test-owner/test-repo/issues/3"

        issue = provider._convert_issue(mock_gh_issue)

        assert issue.author == "unknown"

    def test_convert_comment_no_user(self, provider):
        """Should handle comment with missing user."""
        mock_comment = Mock()
        mock_comment.id = 101
        mock_comment.body = "Comment body"
        mock_comment.user = None
        mock_comment.created_at = datetime.now(UTC)

        comment = provider._convert_comment(mock_comment)

        assert comment.author == "unknown"


class TestGitHubRestProviderGetDiff:
    """Tests for get_diff operation."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_diff_with_patches(self, mock_github_class, provider):
        """Should get diff between two branches with file patches."""
        mock_file1 = Mock()
        mock_file1.filename = "src/app.py"
        mock_file1.patch = "+def new_function():\n+    pass"

        mock_file2 = Mock()
        mock_file2.filename = "README.md"
        mock_file2.patch = "+## New Section"

        mock_comparison = Mock()
        mock_comparison.files = [mock_file1, mock_file2]

        mock_repo = Mock()
        mock_repo.compare = Mock(return_value=mock_comparison)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        diff = await provider.get_diff("main", "feature")

        assert "diff --git a/src/app.py b/src/app.py" in diff
        assert "+def new_function()" in diff
        assert "diff --git a/README.md b/README.md" in diff
        mock_repo.compare.assert_called_once_with("main", "feature")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_diff_file_without_patch(self, mock_github_class, provider):
        """Should skip files without patches (e.g., binary files)."""
        mock_file1 = Mock()
        mock_file1.filename = "src/code.py"
        mock_file1.patch = "+new code"

        mock_file2 = Mock()
        mock_file2.filename = "image.png"
        mock_file2.patch = None  # Binary files have no patch

        mock_comparison = Mock()
        mock_comparison.files = [mock_file1, mock_file2]

        mock_repo = Mock()
        mock_repo.compare = Mock(return_value=mock_comparison)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        diff = await provider.get_diff("main", "feature")

        assert "src/code.py" in diff
        assert "image.png" not in diff

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_diff_exception(self, mock_github_class, provider):
        """Should propagate exception from get_diff."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.compare = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_diff("main", "nonexistent")


class TestGitHubRestProviderMergeBranches:
    """Tests for merge_branches operation."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_merge_branches_success(self, mock_github_class, provider):
        """Should merge source branch into target."""
        mock_repo = Mock()
        mock_repo.merge = Mock()

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        await provider.merge_branches("feature", "main", "Merge feature into main")

        mock_repo.merge.assert_called_once_with(
            base="main",
            head="feature",
            commit_message="Merge feature into main",
        )

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_merge_branches_exception(self, mock_github_class, provider):
        """Should propagate exception from merge."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.merge = Mock(side_effect=GithubException(409, "Merge conflict"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.merge_branches("feature", "main", "Merge")


class TestGitHubRestProviderGetFileDirectoryError:
    """Tests for get_file directory handling."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_file_directory_raises_error(self, mock_github_class, provider):
        """Should raise ValueError when path is a directory."""
        # When get_contents returns a list, it's a directory
        mock_files = [Mock(), Mock()]

        mock_repo = Mock()
        mock_repo.get_contents = Mock(return_value=mock_files)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(ValueError, match="is a directory"):
            await provider.get_file("src/", ref="main")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_file_exception(self, mock_github_class, provider):
        """Should propagate exception from get_file."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_contents = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_file("nonexistent.txt", ref="main")


class TestGitHubRestProviderCommitFileExceptions:
    """Tests for commit_file exception handling."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_commit_file_non_404_exception(self, mock_github_class, provider):
        """Should propagate non-404 exceptions from get_contents."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_contents = Mock(side_effect=GithubException(500, "Server Error"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.commit_file("file.txt", "content", "msg", "main")


class TestGitHubRestProviderSetRepositorySecret:
    """Tests for set_repository_secret operation."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_set_repository_secret_success(self, mock_github_class, provider):
        """Should set repository secret successfully."""
        mock_repo = Mock()
        mock_repo.create_secret = Mock()

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        await provider.set_repository_secret("API_KEY", "secret-value-123")

        mock_repo.create_secret.assert_called_once_with(
            secret_name="API_KEY",
            unencrypted_value="secret-value-123",
            secret_type="actions",
        )

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_set_repository_secret_github_exception(self, mock_github_class, provider):
        """Should propagate GitHub exception from create_secret."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.create_secret = Mock(side_effect=GithubException(403, "Forbidden"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.set_repository_secret("SECRET", "value")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_set_repository_secret_import_error(self, mock_github_class, provider):
        """Should propagate ImportError when PyNaCl is not installed.

        PyGithub handles encryption internally and raises ImportError if PyNaCl
        is missing. The error propagates from the thread pool.
        """
        mock_repo = Mock()

        # Make create_secret trigger the ImportError path by patching the import
        def mock_create_secret(*args, **kwargs):
            # Simulate the ImportError that happens when nacl is not available
            raise ImportError("No module named 'nacl'")

        mock_repo.create_secret = mock_create_secret

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(ImportError, match="nacl"):
            await provider.set_repository_secret("SECRET", "value")


class TestGitHubRestProviderIssueExceptions:
    """Additional exception handling tests for issue operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_issue_exception(self, mock_github_class, provider):
        """Should propagate exception from get_issue."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_issue = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_issue(9999)

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_issue_exception(self, mock_github_class, provider):
        """Should propagate exception from create_issue."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.create_issue = Mock(side_effect=GithubException(422, "Validation error"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.create_issue("Title", "Body")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_update_issue_exception(self, mock_github_class, provider):
        """Should propagate exception from update_issue."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_issue = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.update_issue(9999, title="New Title")


class TestGitHubRestProviderCommentExceptions:
    """Exception handling tests for comment operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_add_comment_exception(self, mock_github_class, provider):
        """Should propagate exception from add_comment."""
        from github import GithubException

        mock_issue = Mock()
        mock_issue.create_comment = Mock(side_effect=GithubException(403, "Forbidden"))

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.add_comment(42, "Comment")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_comments_exception(self, mock_github_class, provider):
        """Should propagate exception from get_comments."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_issue = Mock(side_effect=GithubException(404, "Not Found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_comments(9999)


class TestGitHubRestProviderBranchExceptions:
    """Exception handling tests for branch operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_branch_exception(self, mock_github_class, provider):
        """Should propagate exception from create_branch."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_git_ref = Mock(side_effect=GithubException(404, "Branch not found"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.create_branch("new-branch", "nonexistent")

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_get_branch_non_404_exception(self, mock_github_class, provider):
        """Should propagate non-404 exceptions from get_branch."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.get_branch = Mock(side_effect=GithubException(500, "Server Error"))

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.get_branch("main")


class TestGitHubRestProviderPullRequestExceptions:
    """Exception handling tests for pull request operations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_create_pull_request_exception(self, mock_github_class, provider):
        """Should propagate exception from create_pull_request."""
        from github import GithubException

        mock_repo = Mock()
        mock_repo.create_pull = Mock(
            side_effect=GithubException(422, "No commits between base and head")
        )

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()

        with pytest.raises(GithubException):
            await provider.create_pull_request("Title", "Body", "head", "base")


class TestGitHubRestProviderUpdateIssueFields:
    """Tests for update_issue with various field combinations."""

    @pytest.mark.asyncio
    @patch("repo_sapiens.providers.github_rest.Github")
    async def test_update_issue_body_only(self, mock_github_class, provider):
        """Should update only body field."""
        mock_issue = Mock()
        mock_issue.id = 1009
        mock_issue.number = 42
        mock_issue.title = "Original Title"
        mock_issue.body = "New Body"
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.created_at = datetime.now(UTC)
        mock_issue.updated_at = datetime.now(UTC)
        mock_issue.user = Mock(login="user")
        mock_issue.html_url = "https://github.com/test-owner/test-repo/issues/42"
        mock_issue.edit = Mock()

        mock_repo = Mock()
        mock_repo.get_issue = Mock(return_value=mock_issue)

        mock_client = Mock()
        mock_client.get_repo = Mock(return_value=mock_repo)
        mock_github_class.return_value = mock_client

        await provider.connect()
        updated = await provider.update_issue(42, body="New Body")

        # Verify edit was called with body
        mock_issue.edit.assert_called_with(body="New Body")
        assert updated.body == "New Body"


class TestGitHubRestProviderBaseUrlNormalization:
    """Tests for base URL normalization."""

    def test_init_strips_trailing_slash_from_base_url(self):
        """Should strip trailing slash from base URL."""
        provider = GitHubRestProvider(
            token="token",
            owner="owner",
            repo="repo",
            base_url="https://github.enterprise.com/api/v3/",
        )

        assert provider.base_url == "https://github.enterprise.com/api/v3"

    def test_init_strips_multiple_trailing_slashes(self):
        """Should strip multiple trailing slashes."""
        provider = GitHubRestProvider(
            token="token",
            owner="owner",
            repo="repo",
            base_url="https://github.enterprise.com/api/v3///",
        )

        assert provider.base_url == "https://github.enterprise.com/api/v3"
