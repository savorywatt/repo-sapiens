"""Unit tests for Git discovery.

Tests cover:
- Listing remotes (single and multiple)
- Getting specific remotes by name
- Remote preference order (origin > upstream > first)
- Multiple remotes error handling
- Repository parsing
- Gitea config detection
- Edge cases and error scenarios
"""

from unittest.mock import Mock, patch

import pytest

from repo_sapiens.git.discovery import GitDiscovery, detect_git_origin
from repo_sapiens.git.exceptions import (
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
)


class TestGitDiscoveryRemoteListing:
    """Tests for listing Git remotes."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_list_remotes_single_ssh(self, mock_repo_class):
        """Test listing remotes with single SSH remote."""
        # Mock git.Repo
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remotes = discovery.list_remotes()

        assert len(remotes) == 1
        assert remotes[0].name == "origin"
        assert remotes[0].url == "git@gitea.com:owner/repo.git"
        assert remotes[0].url_type == "ssh"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_list_remotes_single_https(self, mock_repo_class):
        """Test listing remotes with single HTTPS remote."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "https://gitea.com/owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remotes = discovery.list_remotes()

        assert len(remotes) == 1
        assert remotes[0].url_type == "https"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_list_remotes_multiple(self, mock_repo_class):
        """Test listing multiple remotes."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "https://gitea.com/upstream/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_origin, mock_upstream]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remotes = discovery.list_remotes()

        assert len(remotes) == 2
        assert remotes[0].name == "origin"
        assert remotes[0].url_type == "ssh"
        assert remotes[1].name == "upstream"
        assert remotes[1].url_type == "https"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_list_remotes_empty(self, mock_repo_class):
        """Test listing remotes when none exist."""
        mock_repo = Mock()
        mock_repo.remotes = []
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remotes = discovery.list_remotes()

        assert len(remotes) == 0

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_list_remotes_unknown_url_type(self, mock_repo_class):
        """Test listing remotes with unknown URL type."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "file:///local/repo"  # Neither ssh nor https

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remotes = discovery.list_remotes()

        assert len(remotes) == 1
        assert remotes[0].url_type == "unknown"


class TestGitDiscoveryGetRemote:
    """Tests for getting specific remotes."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_single(self, mock_repo_class):
        """Test getting remote when only one exists."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remote = discovery.get_remote()

        assert remote.name == "origin"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_by_name(self, mock_repo_class):
        """Test getting remote by specific name."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "git@gitea.com:upstream/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_origin, mock_upstream]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remote = discovery.get_remote(remote_name="upstream")

        assert remote.name == "upstream"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_prefers_origin(self, mock_repo_class):
        """Test that origin is preferred over other remotes."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_other = Mock()
        mock_other.name = "other"
        mock_other.url = "git@gitea.com:other/repo.git"

        mock_repo = Mock()
        # Put origin second to ensure preference, not order
        mock_repo.remotes = [mock_other, mock_origin]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remote = discovery.get_remote(allow_multiple=True)

        assert remote.name == "origin"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_prefers_upstream_over_others(self, mock_repo_class):
        """Test that upstream is preferred when origin doesn't exist."""
        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "git@gitea.com:upstream/repo.git"

        mock_other = Mock()
        mock_other.name = "other"
        mock_other.url = "git@gitea.com:other/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_other, mock_upstream]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remote = discovery.get_remote(allow_multiple=True)

        assert remote.name == "upstream"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_multiple_raises_error(self, mock_repo_class):
        """Test that multiple remotes raise error without allow_multiple when no preferred names."""
        # Use non-preferred remote names to trigger the error
        mock_remote1 = Mock()
        mock_remote1.name = "remote1"
        mock_remote1.url = "git@gitea.com:owner1/repo.git"

        mock_remote2 = Mock()
        mock_remote2.name = "remote2"
        mock_remote2.url = "git@gitea.com:owner2/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote1, mock_remote2]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        # Should raise without allow_multiple when no preferred names exist
        with pytest.raises(MultipleRemotesError) as exc_info:
            discovery.get_remote(allow_multiple=False)

        assert "remote1" in str(exc_info.value)
        assert "remote2" in str(exc_info.value)
        assert exc_info.value.remotes is not None
        assert len(exc_info.value.remotes) == 2
        assert exc_info.value.suggested is not None

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_nonexistent_name(self, mock_repo_class):
        """Test getting remote with non-existent name raises error."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        with pytest.raises(ValueError) as exc_info:
            discovery.get_remote(remote_name="nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "origin" in str(exc_info.value)

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_remote_no_remotes_raises_error(self, mock_repo_class):
        """Test getting remote when none exist raises error."""
        mock_repo = Mock()
        mock_repo.remotes = []
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        with pytest.raises(NoRemotesError):
            discovery.get_remote()


class TestGitDiscoveryMultipleRemotesInfo:
    """Tests for getting multiple remotes information."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_multiple_remotes_info_suggests_origin(self, mock_repo_class):
        """Test that origin is suggested when present."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "git@gitea.com:upstream/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_upstream, mock_origin]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.get_multiple_remotes_info()

        assert len(info.remotes) == 2
        assert info.suggested is not None
        assert info.suggested.name == "origin"
        assert info.remote_names == ["upstream", "origin"]

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_multiple_remotes_info_suggests_upstream(self, mock_repo_class):
        """Test that upstream is suggested when origin doesn't exist."""
        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "git@gitea.com:upstream/repo.git"

        mock_other = Mock()
        mock_other.name = "other"
        mock_other.url = "git@gitea.com:other/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_other, mock_upstream]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.get_multiple_remotes_info()

        assert info.suggested is not None
        assert info.suggested.name == "upstream"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_multiple_remotes_info_suggests_first(self, mock_repo_class):
        """Test that first remote is suggested when no preferred names."""
        mock_remote1 = Mock()
        mock_remote1.name = "remote1"
        mock_remote1.url = "git@gitea.com:remote1/repo.git"

        mock_remote2 = Mock()
        mock_remote2.name = "remote2"
        mock_remote2.url = "git@gitea.com:remote2/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote1, mock_remote2]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.get_multiple_remotes_info()

        assert info.suggested is not None
        assert info.suggested.name == "remote1"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_get_multiple_remotes_info_no_remotes_raises_error(self, mock_repo_class):
        """Test that no remotes raises error."""
        mock_repo = Mock()
        mock_repo.remotes = []
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        with pytest.raises(NoRemotesError):
            discovery.get_multiple_remotes_info()


class TestGitDiscoveryParseRepository:
    """Tests for parsing repository information."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_parse_repository_ssh(self, mock_repo_class):
        """Test parsing repository with SSH URL."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"
        assert str(info.base_url) == "https://gitea.com/"
        assert info.remote_name == "origin"
        assert info.ssh_url == "git@gitea.com:owner/repo.git"
        assert info.https_url == "https://gitea.com/owner/repo.git"
        assert info.full_name == "owner/repo"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_parse_repository_https(self, mock_repo_class):
        """Test parsing repository with HTTPS URL."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "https://gitea.com/owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"
        assert str(info.base_url) == "https://gitea.com/"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_parse_repository_with_port(self, mock_repo_class):
        """Test parsing repository with custom port."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "https://gitea.example.com:3000/myorg/myrepo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.parse_repository()

        assert info.owner == "myorg"
        assert info.repo == "myrepo"
        assert str(info.base_url) == "https://gitea.example.com:3000/"
        assert info.https_url == "https://gitea.example.com:3000/myorg/myrepo.git"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_parse_repository_specific_remote(self, mock_repo_class):
        """Test parsing repository with specific remote."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_upstream = Mock()
        mock_upstream.name = "upstream"
        mock_upstream.url = "git@gitea.com:upstream/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_origin, mock_upstream]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        info = discovery.parse_repository(remote_name="upstream")

        assert info.owner == "upstream"
        assert info.remote_name == "upstream"


class TestGitDiscoveryDetectGiteaConfig:
    """Tests for detecting Gitea configuration."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_detect_gitea_config(self, mock_repo_class):
        """Test detecting Gitea configuration."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "https://gitea.example.com:3000/myorg/myrepo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        config = discovery.detect_gitea_config()

        assert config["base_url"] == "https://gitea.example.com:3000/"
        assert config["owner"] == "myorg"
        assert config["repo"] == "myrepo"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_detect_gitea_config_multiple_remotes_raises_error(self, mock_repo_class):
        """Test that multiple non-preferred remotes raises error."""
        # Use non-preferred remote names to trigger the error
        mock_remote1 = Mock()
        mock_remote1.name = "remote1"
        mock_remote1.url = "git@gitea.com:owner/repo.git"

        mock_remote2 = Mock()
        mock_remote2.name = "remote2"
        mock_remote2.url = "git@gitea.com:upstream/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote1, mock_remote2]
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        # Should raise because allow_multiple=False in detect_gitea_config
        # and no preferred remote names exist
        with pytest.raises(MultipleRemotesError):
            discovery.detect_gitea_config()


class TestGitDiscoveryErrorHandling:
    """Tests for error handling."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_not_git_repository(self, mock_repo_class):
        """Test error when directory is not a Git repository."""
        from git.exc import InvalidGitRepositoryError as GitInvalidRepoError

        mock_repo_class.side_effect = GitInvalidRepoError

        discovery = GitDiscovery("/tmp/not-a-repo")

        with pytest.raises(NotGitRepositoryError) as exc_info:
            discovery.list_remotes()

        assert "/tmp/not-a-repo" in str(exc_info.value)
        assert "git init" in str(exc_info.value)

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_repository_path_resolution(self, mock_repo_class):
        """Test that repository path is resolved to absolute path."""
        mock_repo = Mock()
        mock_repo.remotes = []
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery(".")

        # Path should be resolved to absolute
        assert discovery.repo_path.is_absolute()


class TestDetectGitOriginHelper:
    """Tests for detect_git_origin helper function."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_detect_git_origin_success(self, mock_repo_class):
        """Test successful Git origin detection."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        base_url = detect_git_origin()

        assert base_url == "https://gitea.com/"

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_detect_git_origin_returns_none_on_error(self, mock_repo_class):
        """Test that detect_git_origin returns None on error."""
        from git.exc import InvalidGitRepositoryError as GitInvalidRepoError

        mock_repo_class.side_effect = GitInvalidRepoError

        base_url = detect_git_origin()

        assert base_url is None

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_detect_git_origin_with_path(self, mock_repo_class):
        """Test detect_git_origin with custom path."""
        mock_remote = Mock()
        mock_remote.name = "origin"
        mock_remote.url = "git@gitea.com:owner/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_remote]
        mock_repo_class.return_value = mock_repo

        base_url = detect_git_origin("/path/to/repo")

        assert base_url == "https://gitea.com/"


class TestGitDiscoveryLazyLoading:
    """Tests for lazy loading of Git repository."""

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_repo_lazy_loaded(self, mock_repo_class):
        """Test that Git repo is not loaded until needed."""
        discovery = GitDiscovery()

        # Repo should not be loaded yet
        assert discovery._repo is None

        # Now trigger loading
        discovery.list_remotes()

        # Repo should now be loaded
        assert discovery._repo is not None
        mock_repo_class.assert_called_once()

    @patch("repo_sapiens.git.discovery.git.Repo")
    def test_repo_cached_after_first_load(self, mock_repo_class):
        """Test that Git repo is cached after first load."""
        mock_repo = Mock()
        mock_repo.remotes = []
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()

        # Call multiple times
        discovery.list_remotes()
        discovery.list_remotes()

        # Should only be called once (cached)
        mock_repo_class.assert_called_once()
