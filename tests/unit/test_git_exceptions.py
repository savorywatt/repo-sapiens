"""Unit tests for Git exceptions module.

This test module provides comprehensive coverage for repo_sapiens.git.exceptions,
testing the exception hierarchy, error messages, and hint formatting.
"""


from repo_sapiens.git.exceptions import (
    GitDiscoveryError,
    InvalidGitUrlError,
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
    UnsupportedHostError,
)
from repo_sapiens.git.models import GitRemote


class TestGitDiscoveryError:
    """Tests for GitDiscoveryError base class."""

    def test_create_with_message_only(self) -> None:
        """Test creating error with message only."""
        error = GitDiscoveryError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.hint is None
        assert str(error) == "Something went wrong"

    def test_create_with_message_and_hint(self) -> None:
        """Test creating error with message and hint."""
        error = GitDiscoveryError("Failed to connect", hint="Check your network connection")

        assert error.message == "Failed to connect"
        assert error.hint == "Check your network connection"
        assert "Failed to connect" in str(error)
        assert "Hint:" in str(error)
        assert "Check your network connection" in str(error)

    def test_str_format_with_hint(self) -> None:
        """Test string representation includes hint properly formatted."""
        error = GitDiscoveryError("Error occurred", hint="Try this fix")

        expected = "Error occurred\n\nHint: Try this fix"
        assert str(error) == expected

    def test_inherits_from_git_operation_error(self) -> None:
        """Test that GitDiscoveryError inherits from GitOperationError."""
        from repo_sapiens.exceptions import GitOperationError

        error = GitDiscoveryError("test")
        assert isinstance(error, GitOperationError)


class TestNotGitRepositoryError:
    """Tests for NotGitRepositoryError."""

    def test_create_with_path(self) -> None:
        """Test creating error with path."""
        error = NotGitRepositoryError("/path/to/not-a-repo")

        assert error.path == "/path/to/not-a-repo"
        assert "Not a Git repository" in error.message
        assert "/path/to/not-a-repo" in error.message

    def test_hint_suggests_git_init(self) -> None:
        """Test that hint suggests git init."""
        error = NotGitRepositoryError("/tmp/test")

        assert "git init" in error.hint

    def test_str_includes_path_and_hint(self) -> None:
        """Test string representation includes path and hint."""
        error = NotGitRepositoryError("/some/path")

        error_str = str(error)
        assert "/some/path" in error_str
        assert "Hint:" in error_str
        assert "git init" in error_str

    def test_with_absolute_path(self) -> None:
        """Test with absolute Unix path."""
        error = NotGitRepositoryError("/home/user/projects/myproject")

        assert error.path == "/home/user/projects/myproject"

    def test_with_relative_path(self) -> None:
        """Test with relative path."""
        error = NotGitRepositoryError("./my-folder")

        assert error.path == "./my-folder"


class TestNoRemotesError:
    """Tests for NoRemotesError."""

    def test_create_no_arguments(self) -> None:
        """Test creating error without arguments."""
        error = NoRemotesError()

        assert "No Git remotes configured" in error.message

    def test_hint_suggests_git_remote_add(self) -> None:
        """Test that hint suggests adding a remote."""
        error = NoRemotesError()

        assert "git remote add" in error.hint

    def test_str_includes_hint(self) -> None:
        """Test string representation includes hint."""
        error = NoRemotesError()

        error_str = str(error)
        assert "No Git remotes" in error_str
        assert "Hint:" in error_str


class TestMultipleRemotesError:
    """Tests for MultipleRemotesError."""

    def test_create_with_remotes_and_suggestion(self) -> None:
        """Test creating error with remotes list and suggested remote."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")
        upstream = GitRemote("upstream", "git@github.com:upstream/repo.git", "ssh")

        error = MultipleRemotesError(remotes=[origin, upstream], suggested=origin)

        assert error.remotes == [origin, upstream]
        assert error.suggested == origin

    def test_message_lists_remote_names(self) -> None:
        """Test that message lists all remote names."""
        fork = GitRemote("fork", "git@github.com:fork/repo.git", "ssh")
        upstream = GitRemote("upstream-org", "git@github.com:upstream/repo.git", "ssh")

        error = MultipleRemotesError(remotes=[fork, upstream], suggested=fork)

        assert "'fork'" in error.message
        assert "'upstream-org'" in error.message

    def test_hint_suggests_specific_remote(self) -> None:
        """Test that hint suggests using --remote flag with suggested name."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")

        error = MultipleRemotesError(remotes=[origin], suggested=origin)

        assert "--remote" in error.hint
        assert "origin" in error.hint

    def test_hint_without_suggestion(self) -> None:
        """Test hint when no remote is suggested."""
        remote = GitRemote("custom", "git@github.com:owner/repo.git", "ssh")

        error = MultipleRemotesError(remotes=[remote], suggested=None)

        assert "Specify which remote to use" in error.hint

    def test_multiple_remotes_in_message(self) -> None:
        """Test message with many remotes."""
        remotes = [
            GitRemote("fork", "git@github.com:fork/repo.git", "ssh"),
            GitRemote("upstream", "git@github.com:upstream/repo.git", "ssh"),
            GitRemote("backup", "git@backup.com:owner/repo.git", "ssh"),
        ]

        error = MultipleRemotesError(remotes=remotes, suggested=remotes[0])

        assert "Multiple remotes found" in error.message
        for remote in remotes:
            assert f"'{remote.name}'" in error.message


class TestInvalidGitUrlError:
    """Tests for InvalidGitUrlError."""

    def test_create_with_url_only(self) -> None:
        """Test creating error with URL only."""
        error = InvalidGitUrlError("invalid-url")

        assert error.url == "invalid-url"
        assert "Invalid Git URL format" in error.message
        assert "invalid-url" in error.message

    def test_create_with_url_and_reason(self) -> None:
        """Test creating error with URL and reason."""
        error = InvalidGitUrlError("bad://url", reason="Unsupported protocol")

        assert error.url == "bad://url"
        assert "Unsupported protocol" in error.message

    def test_hint_shows_expected_formats(self) -> None:
        """Test that hint shows expected URL formats."""
        error = InvalidGitUrlError("invalid")

        assert "git@" in error.hint
        assert "https://" in error.hint
        assert ".git" in error.hint

    def test_str_includes_url_and_hint(self) -> None:
        """Test string representation includes URL and hint."""
        error = InvalidGitUrlError("malformed")

        error_str = str(error)
        assert "malformed" in error_str
        assert "Hint:" in error_str
        assert "Expected formats" in error_str


class TestUnsupportedHostError:
    """Tests for UnsupportedHostError."""

    def test_create_with_host_and_url(self) -> None:
        """Test creating error with host and URL."""
        error = UnsupportedHostError("gitlab.com", "https://gitlab.com/owner/repo.git")

        assert error.host == "gitlab.com"
        assert error.url == "https://gitlab.com/owner/repo.git"

    def test_message_includes_host(self) -> None:
        """Test that message includes unsupported host."""
        error = UnsupportedHostError("bitbucket.org", "https://bitbucket.org/owner/repo.git")

        assert "Unsupported Git host" in error.message
        assert "bitbucket.org" in error.message

    def test_hint_mentions_gitea(self) -> None:
        """Test that hint mentions Gitea support."""
        error = UnsupportedHostError("github.com", "https://github.com/o/r.git")

        assert "Gitea" in error.hint

    def test_hint_includes_remote_url(self) -> None:
        """Test that hint includes the remote URL for reference."""
        url = "https://somehost.com/owner/repo.git"
        error = UnsupportedHostError("somehost.com", url)

        assert url in error.hint

    def test_str_format(self) -> None:
        """Test complete string representation."""
        error = UnsupportedHostError("example.com", "https://example.com/o/r.git")

        error_str = str(error)
        assert "Unsupported Git host" in error_str
        assert "example.com" in error_str
        assert "Hint:" in error_str
        assert "Gitea" in error_str


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_exceptions_inherit_from_git_discovery_error(self) -> None:
        """Test that all specific exceptions inherit from GitDiscoveryError."""
        exceptions = [
            NotGitRepositoryError("/path"),
            NoRemotesError(),
            MultipleRemotesError(
                [GitRemote("origin", "url", "ssh")],
                GitRemote("origin", "url", "ssh"),
            ),
            InvalidGitUrlError("url"),
            UnsupportedHostError("host", "url"),
        ]

        for exc in exceptions:
            assert isinstance(exc, GitDiscoveryError)

    def test_exceptions_can_be_caught_as_base_type(self) -> None:
        """Test that all exceptions can be caught as GitDiscoveryError."""
        try:
            raise NotGitRepositoryError("/path")
        except GitDiscoveryError as e:
            assert isinstance(e, NotGitRepositoryError)

        try:
            raise NoRemotesError()
        except GitDiscoveryError as e:
            assert isinstance(e, NoRemotesError)

    def test_exception_args_preserved(self) -> None:
        """Test that exception args are preserved for logging/debugging."""
        error = NotGitRepositoryError("/test/path")

        # Should be able to access via args
        assert len(error.args) == 1
