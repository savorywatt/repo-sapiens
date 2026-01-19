"""Unit tests for Git models module.

This test module provides comprehensive coverage for repo_sapiens.git.models,
testing Pydantic models and dataclasses for git data structures.
"""

import pytest
from pydantic import ValidationError

from repo_sapiens.git.models import GitRemote, MultipleRemotesInfo, RepositoryInfo


class TestGitRemote:
    """Tests for GitRemote dataclass."""

    def test_create_ssh_remote(self) -> None:
        """Test creating SSH remote."""
        remote = GitRemote(
            name="origin",
            url="git@github.com:owner/repo.git",
            url_type="ssh",
        )

        assert remote.name == "origin"
        assert remote.url == "git@github.com:owner/repo.git"
        assert remote.url_type == "ssh"

    def test_create_https_remote(self) -> None:
        """Test creating HTTPS remote."""
        remote = GitRemote(
            name="upstream",
            url="https://github.com/owner/repo.git",
            url_type="https",
        )

        assert remote.name == "upstream"
        assert remote.url_type == "https"

    def test_create_unknown_type_remote(self) -> None:
        """Test creating remote with unknown URL type."""
        remote = GitRemote(
            name="local",
            url="/path/to/repo",
            url_type="unknown",
        )

        assert remote.url_type == "unknown"

    def test_git_remote_is_frozen(self) -> None:
        """Test that GitRemote is immutable (frozen dataclass)."""
        remote = GitRemote(name="origin", url="https://github.com/o/r.git", url_type="https")

        with pytest.raises(AttributeError):
            remote.name = "new-name"  # type: ignore[misc]

    def test_git_remote_equality(self) -> None:
        """Test that GitRemote equality works correctly."""
        remote1 = GitRemote(name="origin", url="https://github.com/o/r.git", url_type="https")
        remote2 = GitRemote(name="origin", url="https://github.com/o/r.git", url_type="https")
        remote3 = GitRemote(name="upstream", url="https://github.com/o/r.git", url_type="https")

        assert remote1 == remote2
        assert remote1 != remote3

    def test_git_remote_hashable(self) -> None:
        """Test that GitRemote can be used in sets."""
        remote1 = GitRemote(name="origin", url="https://github.com/o/r.git", url_type="https")
        remote2 = GitRemote(name="origin", url="https://github.com/o/r.git", url_type="https")

        # Should be able to use in sets
        remote_set = {remote1, remote2}
        assert len(remote_set) == 1


class TestRepositoryInfo:
    """Tests for RepositoryInfo Pydantic model."""

    def test_create_valid_repository_info(self) -> None:
        """Test creating valid RepositoryInfo."""
        info = RepositoryInfo(
            owner="myorg",
            repo="myrepo",
            base_url="https://gitea.com",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com/myorg/myrepo.git",
        )

        assert info.owner == "myorg"
        assert info.repo == "myrepo"
        assert str(info.base_url) == "https://gitea.com/"
        assert info.remote_name == "origin"

    def test_full_name_property(self) -> None:
        """Test full_name property returns owner/repo format."""
        info = RepositoryInfo(
            owner="myorg",
            repo="myrepo",
            base_url="https://gitea.com",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com/myorg/myrepo.git",
        )

        assert info.full_name == "myorg/myrepo"

    def test_owner_validation_empty_string(self) -> None:
        """Test that empty owner string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RepositoryInfo(
                owner="",
                repo="myrepo",
                base_url="https://gitea.com",
                remote_name="origin",
                ssh_url="git@gitea.com:myorg/myrepo.git",
                https_url="https://gitea.com/myorg/myrepo.git",
            )

        errors = exc_info.value.errors()
        assert any("Owner and repo must not be empty" in str(e["msg"]) for e in errors)

    def test_owner_validation_whitespace_only(self) -> None:
        """Test that whitespace-only owner raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RepositoryInfo(
                owner="   ",
                repo="myrepo",
                base_url="https://gitea.com",
                remote_name="origin",
                ssh_url="git@gitea.com:myorg/myrepo.git",
                https_url="https://gitea.com/myorg/myrepo.git",
            )

        errors = exc_info.value.errors()
        assert any("Owner and repo must not be empty" in str(e["msg"]) for e in errors)

    def test_repo_validation_empty_string(self) -> None:
        """Test that empty repo string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RepositoryInfo(
                owner="myorg",
                repo="",
                base_url="https://gitea.com",
                remote_name="origin",
                ssh_url="git@gitea.com:myorg/myrepo.git",
                https_url="https://gitea.com/myorg/myrepo.git",
            )

        errors = exc_info.value.errors()
        assert any("Owner and repo must not be empty" in str(e["msg"]) for e in errors)

    def test_repo_git_suffix_removed(self) -> None:
        """Test that .git suffix is automatically removed from repo."""
        info = RepositoryInfo(
            owner="myorg",
            repo="myrepo.git",
            base_url="https://gitea.com",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com/myorg/myrepo.git",
        )

        assert info.repo == "myrepo"

    def test_owner_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from owner."""
        info = RepositoryInfo(
            owner="  myorg  ",
            repo="myrepo",
            base_url="https://gitea.com",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com/myorg/myrepo.git",
        )

        assert info.owner == "myorg"

    def test_base_url_with_port(self) -> None:
        """Test base_url with non-standard port."""
        info = RepositoryInfo(
            owner="myorg",
            repo="myrepo",
            base_url="https://gitea.com:3000",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com:3000/myorg/myrepo.git",
        )

        assert "3000" in str(info.base_url)

    def test_invalid_base_url(self) -> None:
        """Test that invalid base_url raises validation error."""
        with pytest.raises(ValidationError):
            RepositoryInfo(
                owner="myorg",
                repo="myrepo",
                base_url="not-a-valid-url",
                remote_name="origin",
                ssh_url="git@gitea.com:myorg/myrepo.git",
                https_url="https://gitea.com/myorg/myrepo.git",
            )


class TestMultipleRemotesInfo:
    """Tests for MultipleRemotesInfo Pydantic model."""

    def test_create_with_suggested_remote(self) -> None:
        """Test creating MultipleRemotesInfo with suggested remote."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")
        upstream = GitRemote("upstream", "git@github.com:upstream/repo.git", "ssh")

        info = MultipleRemotesInfo(remotes=[origin, upstream], suggested=origin)

        assert len(info.remotes) == 2
        assert info.suggested == origin

    def test_create_without_suggested_remote(self) -> None:
        """Test creating MultipleRemotesInfo without suggested remote."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")

        info = MultipleRemotesInfo(remotes=[origin], suggested=None)

        assert info.suggested is None

    def test_remote_names_property(self) -> None:
        """Test remote_names property returns list of names."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")
        upstream = GitRemote("upstream", "git@github.com:upstream/repo.git", "ssh")
        fork = GitRemote("fork", "git@github.com:fork/repo.git", "ssh")

        info = MultipleRemotesInfo(remotes=[origin, upstream, fork], suggested=origin)

        assert info.remote_names == ["origin", "upstream", "fork"]

    def test_remote_names_empty_list(self) -> None:
        """Test remote_names with empty remotes list."""
        info = MultipleRemotesInfo(remotes=[], suggested=None)

        assert info.remote_names == []

    def test_single_remote(self) -> None:
        """Test with single remote."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")

        info = MultipleRemotesInfo(remotes=[origin], suggested=origin)

        assert info.remote_names == ["origin"]
        assert info.suggested == origin


class TestModelSerialization:
    """Tests for model serialization behavior."""

    def test_repository_info_model_dump(self) -> None:
        """Test RepositoryInfo can be serialized to dict."""
        info = RepositoryInfo(
            owner="myorg",
            repo="myrepo",
            base_url="https://gitea.com",
            remote_name="origin",
            ssh_url="git@gitea.com:myorg/myrepo.git",
            https_url="https://gitea.com/myorg/myrepo.git",
        )

        data = info.model_dump()

        assert data["owner"] == "myorg"
        assert data["repo"] == "myrepo"
        assert data["remote_name"] == "origin"

    def test_multiple_remotes_info_model_dump(self) -> None:
        """Test MultipleRemotesInfo can be serialized to dict."""
        origin = GitRemote("origin", "git@github.com:owner/repo.git", "ssh")

        info = MultipleRemotesInfo(remotes=[origin], suggested=origin)

        data = info.model_dump()

        assert len(data["remotes"]) == 1
        assert data["remotes"][0]["name"] == "origin"
