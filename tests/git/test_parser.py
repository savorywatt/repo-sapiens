"""Unit tests for Git URL parser.

Tests cover:
- SSH URL parsing (with and without .git suffix)
- HTTPS URL parsing (standard and with custom port)
- HTTP URL parsing
- Invalid URL format handling
- Missing owner/repo handling
- Empty owner/repo handling
- Nested path handling
- URL type detection
- Base URL generation
- Clone URL generation
"""

import pytest

from automation.git.exceptions import InvalidGitUrlError
from automation.git.parser import GitUrlParser


class TestGitUrlParserSSH:
    """Tests for SSH URL parsing."""

    def test_parse_ssh_url_with_git_suffix(self):
        """Test parsing SSH format URL with .git suffix."""
        parser = GitUrlParser("git@gitea.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "gitea.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://gitea.com"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"
        assert parser.https_url == "https://gitea.com/owner/repo.git"
        assert parser.port is None

    def test_parse_ssh_url_without_git_suffix(self):
        """Test parsing SSH URL without .git suffix."""
        parser = GitUrlParser("git@gitea.com:owner/repo")

        assert parser.url_type == "ssh"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"
        assert parser.https_url == "https://gitea.com/owner/repo.git"

    def test_parse_ssh_url_with_custom_user(self):
        """Test parsing SSH URL with custom user."""
        parser = GitUrlParser("user@gitea.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "gitea.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"

    def test_parse_ssh_url_with_hyphen_in_host(self):
        """Test parsing SSH URL with hyphen in hostname."""
        parser = GitUrlParser("git@my-gitea.example.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "my-gitea.example.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"

    def test_parse_ssh_url_with_underscore_in_names(self):
        """Test parsing SSH URL with underscores in owner/repo."""
        parser = GitUrlParser("git@gitea.com:my_org/my_repo.git")

        assert parser.url_type == "ssh"
        assert parser.owner == "my_org"
        assert parser.repo == "my_repo"


class TestGitUrlParserHTTPS:
    """Tests for HTTPS URL parsing."""

    def test_parse_https_url_with_git_suffix(self):
        """Test parsing HTTPS format URL with .git suffix."""
        parser = GitUrlParser("https://gitea.com/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "gitea.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://gitea.com"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"
        assert parser.https_url == "https://gitea.com/owner/repo.git"
        assert parser.port is None

    def test_parse_https_url_without_git_suffix(self):
        """Test parsing HTTPS URL without .git suffix."""
        parser = GitUrlParser("https://gitea.com/owner/repo")

        assert parser.url_type == "https"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.https_url == "https://gitea.com/owner/repo.git"

    def test_parse_https_url_with_custom_port(self):
        """Test parsing HTTPS URL with custom port."""
        parser = GitUrlParser("https://gitea.com:3000/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "gitea.com"
        assert parser.port == 3000
        assert parser.base_url == "https://gitea.com:3000"
        assert parser.https_url == "https://gitea.com:3000/owner/repo.git"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"

    def test_parse_http_url(self):
        """Test parsing HTTP (insecure) URL."""
        parser = GitUrlParser("http://gitea.local/owner/repo.git")

        assert parser.url_type == "https"  # Still returns https base_url
        assert parser.host == "gitea.local"
        assert parser.base_url == "https://gitea.local"

    def test_parse_https_url_with_hyphen_in_host(self):
        """Test parsing HTTPS URL with hyphen in hostname."""
        parser = GitUrlParser("https://my-gitea.example.com/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "my-gitea.example.com"

    def test_parse_https_url_with_port_and_no_git_suffix(self):
        """Test parsing HTTPS URL with port and no .git suffix."""
        parser = GitUrlParser("https://gitea.com:8080/owner/repo")

        assert parser.port == 8080
        assert parser.base_url == "https://gitea.com:8080"
        assert parser.https_url == "https://gitea.com:8080/owner/repo.git"


class TestGitUrlParserEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_parse_nested_path(self):
        """Test URL with nested path (e.g., /group/subgroup/repo).

        For nested paths, we extract the first two components as owner and repo.
        """
        parser = GitUrlParser("git@gitea.com:group/subgroup/repo.git")

        # Should extract first two parts as owner and repo
        assert parser.owner == "group"
        assert parser.repo == "subgroup"

    def test_parse_url_with_leading_trailing_whitespace(self):
        """Test URL parsing with leading/trailing whitespace."""
        parser = GitUrlParser("  git@gitea.com:owner/repo.git  ")

        assert parser.url_type == "ssh"
        assert parser.owner == "owner"
        assert parser.repo == "repo"

    def test_repo_name_has_git_suffix_removed_in_model(self):
        """Test that .git suffix is removed from repo name."""
        parser = GitUrlParser("git@gitea.com:owner/repo.git")

        # The repo property should already have .git removed
        assert parser.repo == "repo"
        assert not parser.repo.endswith(".git")


class TestGitUrlParserErrors:
    """Tests for error handling."""

    def test_invalid_url_format_ftp(self):
        """Test invalid URL format (FTP) raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("ftp://gitea.com/owner/repo")

        assert "Invalid Git URL" in str(exc_info.value)
        assert "ftp://gitea.com/owner/repo" in str(exc_info.value)

    def test_invalid_url_format_random_string(self):
        """Test invalid URL format (random string) raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("not-a-valid-url")

        assert "Invalid Git URL" in str(exc_info.value)

    def test_missing_owner_repo_ssh(self):
        """Test SSH URL without owner/repo raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("git@gitea.com:repo.git")

        assert "owner/repo" in str(exc_info.value).lower()

    def test_missing_owner_repo_https(self):
        """Test HTTPS URL without owner/repo raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("https://gitea.com/repo.git")

        assert "owner/repo" in str(exc_info.value).lower()

    def test_empty_owner_ssh(self):
        """Test SSH URL with empty owner raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("git@gitea.com:/repo.git")

    def test_empty_repo_ssh(self):
        """Test SSH URL with empty repo raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("git@gitea.com:owner/.git")

    def test_empty_owner_https(self):
        """Test HTTPS URL with empty owner raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("https://gitea.com//repo.git")

    def test_empty_path_ssh(self):
        """Test SSH URL with empty path raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("git@gitea.com:")

        # Error message should indicate invalid format
        assert "Invalid Git URL" in str(exc_info.value)

    def test_only_slashes_in_path(self):
        """Test URL with only slashes in path raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("https://gitea.com//")


class TestGitUrlParserProperties:
    """Tests for property accessors."""

    def test_all_properties_accessible(self):
        """Test that all properties can be accessed after parsing."""
        parser = GitUrlParser("https://gitea.com:3000/owner/repo.git")

        # All these should work without raising
        assert parser.url_type == "https"
        assert parser.host == "gitea.com"
        assert parser.port == 3000
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://gitea.com:3000"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"
        assert parser.https_url == "https://gitea.com:3000/owner/repo.git"

    def test_url_property_preservation(self):
        """Test that original URL is preserved."""
        original_url = "git@gitea.com:owner/repo.git"
        parser = GitUrlParser(original_url)

        assert parser.url == original_url


class TestGitUrlParserRealWorldExamples:
    """Tests with real-world URL examples."""

    def test_github_style_ssh_url(self):
        """Test GitHub-style SSH URL (same format as Gitea)."""
        parser = GitUrlParser("git@github.com:torvalds/linux.git")

        assert parser.url_type == "ssh"
        assert parser.host == "github.com"
        assert parser.owner == "torvalds"
        assert parser.repo == "linux"

    def test_gitlab_style_https_url(self):
        """Test GitLab-style HTTPS URL (same format as Gitea)."""
        parser = GitUrlParser("https://gitlab.com/gitlab-org/gitlab.git")

        assert parser.url_type == "https"
        assert parser.host == "gitlab.com"
        assert parser.owner == "gitlab-org"
        assert parser.repo == "gitlab"

    def test_self_hosted_with_port(self):
        """Test self-hosted Git server with custom port."""
        parser = GitUrlParser("https://git.company.com:8443/team/project.git")

        assert parser.url_type == "https"
        assert parser.host == "git.company.com"
        assert parser.port == 8443
        assert parser.owner == "team"
        assert parser.repo == "project"
        assert parser.base_url == "https://git.company.com:8443"

    def test_local_development_http(self):
        """Test local development HTTP URL."""
        parser = GitUrlParser("http://localhost:3000/dev/test-repo.git")

        assert parser.url_type == "https"  # Always returns https base_url
        assert parser.host == "localhost"
        assert parser.port == 3000
        assert parser.owner == "dev"
        assert parser.repo == "test-repo"
