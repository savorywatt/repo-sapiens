"""Integration tests for Git discovery.

These tests use real Git operations to verify the complete workflow.
They create temporary Git repositories with real remotes and test
the discovery functionality end-to-end.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from automation.git.discovery import GitDiscovery, detect_git_origin
from automation.git.exceptions import (
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
)


class TestGitDiscoveryIntegration:
    """Integration tests with real Git operations."""

    @pytest.fixture
    def temp_repo(self):
        """Create temporary Git repository.

        Yields:
            Path to temporary Git repository
        """
        temp_dir = Path(tempfile.mkdtemp())

        # Initialize Git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit (required for some Git operations)
        readme = temp_dir / "README.md"
        readme.write_text("# Test Repository\n")
        subprocess.run(["git", "add", "README.md"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_not_git_repository(self):
        """Test error when directory is not a Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            discovery = GitDiscovery(temp_dir)

            with pytest.raises(NotGitRepositoryError) as exc_info:
                discovery.list_remotes()

            assert temp_dir in str(exc_info.value)
            assert "git init" in str(exc_info.value)

    def test_no_remotes(self, temp_repo):
        """Test error when repository has no remotes."""
        discovery = GitDiscovery(temp_repo)

        # Should be able to list (empty)
        remotes = discovery.list_remotes()
        assert len(remotes) == 0

        # Should raise error when trying to get remote
        with pytest.raises(NoRemotesError) as exc_info:
            discovery.get_remote()

        assert "No Git remotes configured" in str(exc_info.value)
        assert "git remote add" in str(exc_info.value)

    def test_with_ssh_remote(self, temp_repo):
        """Test discovery with SSH remote."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"
        assert str(info.base_url) == "https://gitea.com/"
        assert info.remote_name == "origin"
        assert info.ssh_url == "git@gitea.com:owner/repo.git"
        assert info.https_url == "https://gitea.com/owner/repo.git"

    def test_with_https_remote(self, temp_repo):
        """Test discovery with HTTPS remote."""
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://gitea.example.com/myorg/myrepo.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "myorg"
        assert info.repo == "myrepo"
        assert str(info.base_url) == "https://gitea.example.com/"

    def test_with_https_remote_and_port(self, temp_repo):
        """Test discovery with HTTPS remote using custom port."""
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://gitea.example.com:3000/myorg/myrepo.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "myorg"
        assert info.repo == "myrepo"
        assert str(info.base_url) == "https://gitea.example.com:3000/"
        assert info.https_url == "https://gitea.example.com:3000/myorg/myrepo.git"

    def test_multiple_remotes_prefers_origin(self, temp_repo):
        """Test discovery with multiple remotes prefers origin."""
        subprocess.run(
            ["git", "remote", "add", "upstream", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)

        # Should prefer origin
        info = discovery.parse_repository(allow_multiple=True)
        assert info.owner == "owner"
        assert info.remote_name == "origin"

    def test_multiple_remotes_can_select_specific(self, temp_repo):
        """Test discovery with multiple remotes can select specific one."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "upstream", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)

        # Can explicitly select upstream
        info = discovery.parse_repository(remote_name="upstream")
        assert info.owner == "upstream"
        assert info.remote_name == "upstream"

    def test_multiple_remotes_raises_error_without_allow(self, temp_repo):
        """Test that multiple non-preferred remotes raise error without allow_multiple."""
        # Use non-preferred remote names to trigger the error
        subprocess.run(
            ["git", "remote", "add", "remote1", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "remote2", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)

        # Should raise without allow_multiple when no preferred names exist
        with pytest.raises(MultipleRemotesError) as exc_info:
            discovery.get_remote(allow_multiple=False)

        assert "remote1" in str(exc_info.value)
        assert "remote2" in str(exc_info.value)

    def test_detect_gitea_config(self, temp_repo):
        """Test detecting Gitea configuration."""
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://gitea.example.com:3000/myorg/myrepo.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        config = discovery.detect_gitea_config()

        assert config["base_url"] == "https://gitea.example.com:3000/"
        assert config["owner"] == "myorg"
        assert config["repo"] == "myrepo"

    def test_search_parent_directories(self, temp_repo):
        """Test that discovery searches parent directories for .git."""
        # Create subdirectory
        subdir = temp_repo / "subdir" / "nested"
        subdir.mkdir(parents=True)

        # Add remote to parent repo
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        # Discovery from subdirectory should find parent repo
        discovery = GitDiscovery(subdir)
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"

    def test_url_without_git_suffix(self, temp_repo):
        """Test URL without .git suffix is handled correctly."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"
        # Generated URLs should have .git
        assert info.ssh_url == "git@gitea.com:owner/repo.git"
        assert info.https_url == "https://gitea.com/owner/repo.git"

    def test_remote_with_hyphen_in_repo_name(self, temp_repo):
        """Test remote with hyphen in repository name."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/my-repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "my-repo"

    def test_remote_with_underscore_in_names(self, temp_repo):
        """Test remote with underscores in owner and repo names."""
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "git@gitea.com:my_org/my_repo.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "my_org"
        assert info.repo == "my_repo"


class TestDetectGitOriginIntegration:
    """Integration tests for detect_git_origin helper."""

    @pytest.fixture
    def temp_repo(self):
        """Create temporary Git repository."""
        temp_dir = Path(tempfile.mkdtemp())

        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        yield temp_dir

        shutil.rmtree(temp_dir)

    def test_detect_git_origin_success(self, temp_repo):
        """Test successful Git origin detection."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        base_url = detect_git_origin(temp_repo)

        assert base_url == "https://gitea.com/"

    def test_detect_git_origin_not_git_repo(self):
        """Test that detect_git_origin returns None for non-Git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_url = detect_git_origin(temp_dir)

            assert base_url is None

    def test_detect_git_origin_no_remotes(self, temp_repo):
        """Test that detect_git_origin returns None when no remotes exist."""
        base_url = detect_git_origin(temp_repo)

        assert base_url is None

    def test_detect_git_origin_with_multiple_remotes(self, temp_repo):
        """Test detect_git_origin with multiple remotes (uses first preferred)."""
        subprocess.run(
            ["git", "remote", "add", "upstream", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        base_url = detect_git_origin(temp_repo)

        # Should prefer origin
        assert base_url == "https://gitea.com/"


class TestMultipleRemotesInfo:
    """Integration tests for multiple remotes information."""

    @pytest.fixture
    def temp_repo(self):
        """Create temporary Git repository."""
        temp_dir = Path(tempfile.mkdtemp())

        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        yield temp_dir

        shutil.rmtree(temp_dir)

    def test_get_multiple_remotes_info(self, temp_repo):
        """Test getting information about multiple remotes."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "upstream", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.get_multiple_remotes_info()

        assert len(info.remotes) == 2
        assert "origin" in info.remote_names
        assert "upstream" in info.remote_names
        assert info.suggested is not None
        assert info.suggested.name == "origin"

    def test_get_multiple_remotes_info_no_preferred(self, temp_repo):
        """Test multiple remotes info when no preferred names exist."""
        subprocess.run(
            ["git", "remote", "add", "remote1", "git@gitea.com:owner1/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "remote2", "git@gitea.com:owner2/repo.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.get_multiple_remotes_info()

        assert len(info.remotes) == 2
        assert info.suggested is not None
        # Should suggest first remote
        assert info.suggested.name == "remote1"


class TestRealWorldScenarios:
    """Tests with real-world-like scenarios."""

    @pytest.fixture
    def temp_repo(self):
        """Create temporary Git repository."""
        temp_dir = Path(tempfile.mkdtemp())

        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        yield temp_dir

        shutil.rmtree(temp_dir)

    def test_forked_repository_scenario(self, temp_repo):
        """Test scenario where user has forked a repository.

        Common scenario:
        - origin: user's fork
        - upstream: original repository
        """
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:myuser/project.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "upstream",
                "git@gitea.com:original/project.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)

        # Should prefer origin (user's fork)
        info = discovery.parse_repository(allow_multiple=True)
        assert info.owner == "myuser"
        assert info.remote_name == "origin"

        # Can explicitly get upstream
        upstream_info = discovery.parse_repository(remote_name="upstream")
        assert upstream_info.owner == "original"

    def test_self_hosted_gitea_with_port(self, temp_repo):
        """Test self-hosted Gitea instance with custom port."""
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://git.company.internal:8443/team/project.git",
            ],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        config = discovery.detect_gitea_config()

        assert config["base_url"] == "https://git.company.internal:8443/"
        assert config["owner"] == "team"
        assert config["repo"] == "project"

    def test_repository_with_numbers_in_name(self, temp_repo):
        """Test repository with numbers in owner and repo names."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:team2024/v2-app.git"],
            cwd=temp_repo,
            check=True,
            capture_output=True,
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "team2024"
        assert info.repo == "v2-app"
