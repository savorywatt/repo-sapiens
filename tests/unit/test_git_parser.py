"""Unit tests for Git URL parser module.

This test module provides comprehensive coverage for repo_sapiens.git.parser,
testing GitUrlParser class with various URL formats, edge cases, and error conditions.
"""

import pytest

from repo_sapiens.git.parser import GitUrlParser
from repo_sapiens.git.exceptions import InvalidGitUrlError


class TestGitUrlParserSSH:
    """Tests for SSH URL parsing."""

    def test_parse_standard_ssh_url(self) -> None:
        """Test parsing standard SSH URL with .git suffix."""
        parser = GitUrlParser("git@github.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "github.com"
        assert parser.port is None
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://github.com"
        assert parser.ssh_url == "git@github.com:owner/repo.git"
        assert parser.https_url == "https://github.com/owner/repo.git"

    def test_parse_ssh_url_without_git_suffix(self) -> None:
        """Test parsing SSH URL without .git suffix."""
        parser = GitUrlParser("git@gitea.example.com:myorg/myrepo")

        assert parser.url_type == "ssh"
        assert parser.owner == "myorg"
        assert parser.repo == "myrepo"

    def test_parse_ssh_url_with_different_user(self) -> None:
        """Test parsing SSH URL with non-git user."""
        parser = GitUrlParser("deploy@example.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "example.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        # SSH URL is normalized to git@ user
        assert parser.ssh_url == "git@example.com:owner/repo.git"

    def test_parse_ssh_url_with_nested_path(self) -> None:
        """Test parsing SSH URL with nested groups (GitLab-style)."""
        parser = GitUrlParser("git@gitlab.com:group/subgroup/repo.git")

        assert parser.url_type == "ssh"
        # Takes first two path components
        assert parser.owner == "group"
        assert parser.repo == "subgroup"

    def test_parse_ssh_url_with_hostname_containing_dots(self) -> None:
        """Test parsing SSH URL with multi-part hostname."""
        parser = GitUrlParser("git@git.company.example.com:team/project.git")

        assert parser.url_type == "ssh"
        assert parser.host == "git.company.example.com"
        assert parser.base_url == "https://git.company.example.com"

    def test_parse_ssh_url_with_dashes_in_host(self) -> None:
        """Test parsing SSH URL with dashes in hostname."""
        parser = GitUrlParser("git@my-git-server.local:owner/repo.git")

        assert parser.host == "my-git-server.local"

    def test_parse_ssh_url_with_underscores_in_path(self) -> None:
        """Test parsing SSH URL with underscores in owner/repo names."""
        parser = GitUrlParser("git@github.com:my_org/my_repo.git")

        assert parser.owner == "my_org"
        assert parser.repo == "my_repo"

    def test_parse_ssh_url_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from URL."""
        parser = GitUrlParser("  git@github.com:owner/repo.git  ")

        assert parser.url == "git@github.com:owner/repo.git"
        assert parser.owner == "owner"


class TestGitUrlParserHTTPS:
    """Tests for HTTPS URL parsing."""

    def test_parse_standard_https_url(self) -> None:
        """Test parsing standard HTTPS URL."""
        parser = GitUrlParser("https://github.com/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "github.com"
        assert parser.port is None
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://github.com"
        assert parser.https_url == "https://github.com/owner/repo.git"

    def test_parse_https_url_without_git_suffix(self) -> None:
        """Test parsing HTTPS URL without .git suffix."""
        parser = GitUrlParser("https://github.com/owner/repo")

        assert parser.owner == "owner"
        assert parser.repo == "repo"

    def test_parse_https_url_with_port(self) -> None:
        """Test parsing HTTPS URL with custom port."""
        parser = GitUrlParser("https://gitea.example.com:3000/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "gitea.example.com"
        assert parser.port == 3000
        assert parser.base_url == "https://gitea.example.com:3000"
        assert parser.https_url == "https://gitea.example.com:3000/owner/repo.git"

    def test_parse_http_url_insecure(self) -> None:
        """Test parsing insecure HTTP URL."""
        parser = GitUrlParser("http://gitea.local/owner/repo.git")

        assert parser.url_type == "https"  # Treated as HTTPS type
        assert parser.host == "gitea.local"
        # Base URL is always HTTPS
        assert parser.base_url == "https://gitea.local"

    def test_parse_http_url_with_port(self) -> None:
        """Test parsing HTTP URL with port."""
        parser = GitUrlParser("http://192.168.1.100:3000/owner/repo.git")

        assert parser.host == "192.168.1.100"
        assert parser.port == 3000
        assert parser.base_url == "https://192.168.1.100:3000"

    def test_parse_https_url_nested_path(self) -> None:
        """Test parsing HTTPS URL with nested groups."""
        parser = GitUrlParser("https://gitlab.com/group/subgroup/repo.git")

        assert parser.owner == "group"
        assert parser.repo == "subgroup"

    def test_parse_https_url_with_long_port(self) -> None:
        """Test parsing HTTPS URL with 5-digit port."""
        parser = GitUrlParser("https://gitea.local:65535/owner/repo.git")

        assert parser.port == 65535

    def test_parse_https_url_trailing_slashes_in_path(self) -> None:
        """Test that trailing slashes in path are handled."""
        # The regex handles this correctly
        parser = GitUrlParser("https://github.com/owner/repo/")

        assert parser.owner == "owner"
        assert parser.repo == "repo"


class TestGitUrlParserErrorConditions:
    """Tests for error handling in URL parsing."""

    def test_invalid_url_no_owner_repo(self) -> None:
        """Test that URL without owner/repo raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("https://github.com")

        assert "github.com" in str(exc_info.value)
        assert exc_info.value.url == "https://github.com"

    def test_invalid_url_single_path_component(self) -> None:
        """Test that URL with single path component raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("https://github.com/onlyowner")

        error = exc_info.value
        assert "Path must contain owner/repo" in str(error)
        assert error.url == "https://github.com/onlyowner"

    def test_invalid_url_empty_path(self) -> None:
        """Test that URL with empty path raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("git@github.com:")

        assert "Empty path" in str(exc_info.value)

    def test_invalid_url_empty_owner(self) -> None:
        """Test that URL with empty owner raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("https://github.com//repo.git")

        assert "Owner and repo must not be empty" in str(exc_info.value)

    def test_invalid_url_completely_malformed(self) -> None:
        """Test that completely malformed URL raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("not-a-valid-url")

        error = exc_info.value
        assert "Invalid Git URL format" in error.message
        assert "SSH" in error.hint
        assert "HTTPS" in error.hint

    def test_invalid_url_file_protocol(self) -> None:
        """Test that file:// protocol raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("file:///path/to/repo")

    def test_invalid_url_ftp_protocol(self) -> None:
        """Test that ftp:// protocol raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("ftp://server/repo.git")

    def test_invalid_url_ssh_missing_colon(self) -> None:
        """Test that SSH-like URL without colon raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("git@github.com/owner/repo.git")

    def test_error_includes_hint(self) -> None:
        """Test that InvalidGitUrlError includes helpful hint."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("invalid")

        error = exc_info.value
        assert error.hint is not None
        assert "git@" in error.hint
        assert "https://" in error.hint


class TestGitUrlParserProperties:
    """Tests for property accessors and edge cases."""

    def test_original_url_preserved(self) -> None:
        """Test that original URL is preserved."""
        url = "git@github.com:owner/repo.git"
        parser = GitUrlParser(url)

        assert parser.url == url

    def test_ssh_url_generated_from_https(self) -> None:
        """Test SSH URL generation from HTTPS source."""
        parser = GitUrlParser("https://github.com/owner/repo.git")

        # Should generate valid SSH URL regardless of source format
        assert parser.ssh_url == "git@github.com:owner/repo.git"

    def test_https_url_generated_from_ssh(self) -> None:
        """Test HTTPS URL generation from SSH source."""
        parser = GitUrlParser("git@github.com:owner/repo.git")

        # Should generate valid HTTPS URL regardless of source format
        assert parser.https_url == "https://github.com/owner/repo.git"

    def test_port_preserved_in_generated_urls(self) -> None:
        """Test that port is preserved in generated URLs."""
        parser = GitUrlParser("https://gitea.com:3000/owner/repo.git")

        assert parser.https_url == "https://gitea.com:3000/owner/repo.git"
        # SSH URL doesn't include port (standard SSH port assumed)
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"

    def test_git_suffix_removed_from_repo(self) -> None:
        """Test that .git suffix is removed from repo name."""
        parser = GitUrlParser("git@github.com:owner/repo.git")

        assert parser.repo == "repo"
        assert not parser.repo.endswith(".git")

    def test_full_name_format(self) -> None:
        """Test that owner/repo can be combined correctly."""
        parser = GitUrlParser("git@github.com:myorg/myrepo.git")

        # Can combine owner and repo for full name
        full_name = f"{parser.owner}/{parser.repo}"
        assert full_name == "myorg/myrepo"


class TestGitUrlParserRegexPatterns:
    """Tests for regex pattern edge cases."""

    def test_host_with_numbers(self) -> None:
        """Test hostname with numbers."""
        parser = GitUrlParser("git@git123.example.com:owner/repo.git")

        assert parser.host == "git123.example.com"

    def test_host_is_ip_address(self) -> None:
        """Test IP address as hostname."""
        parser = GitUrlParser("https://192.168.1.100/owner/repo.git")

        assert parser.host == "192.168.1.100"

    def test_owner_with_dots(self) -> None:
        """Test owner name with dots (edge case)."""
        parser = GitUrlParser("https://github.com/owner.name/repo.git")

        assert parser.owner == "owner.name"

    def test_repo_with_dots(self) -> None:
        """Test repo name with dots."""
        parser = GitUrlParser("https://github.com/owner/repo.name.git")

        assert parser.repo == "repo.name"

    def test_very_long_path(self) -> None:
        """Test URL with very long nested path."""
        parser = GitUrlParser("https://gitlab.com/a/b/c/d/e/f.git")

        # Only first two components used
        assert parser.owner == "a"
        assert parser.repo == "b"
