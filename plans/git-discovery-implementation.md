# Git Repository Discovery and Parsing Implementation Plan

**Date**: 2025-12-22
**Status**: Ready for Implementation
**Priority**: HIGH (Critical for `builder init` command)
**Estimated Effort**: 8-12 hours

---

## Executive Summary

Implement robust Git repository discovery and URL parsing functionality to automatically detect Gitea repository configuration from local Git remotes. This addresses the technical review feedback: **"Git Discovery Implementation Missing"** with complete error handling for all edge cases.

### Key Features
- Automatic detection of Git origin from local repository
- Parsing of both SSH and HTTPS Git URL formats
- Extraction of owner/repo from Git URLs
- Support for multiple remotes (origin, upstream, etc.)
- Gitea base URL detection for API configuration
- Comprehensive error handling for all failure modes

### Integration Point
Part of `builder init` command workflow to auto-populate `.builder/config.toml` with repository details.

---

## Technical Architecture

### 1. Module Structure

```
automation/
└── git/
    ├── __init__.py          # Public API exports
    ├── discovery.py         # Git repository detection
    ├── parser.py            # URL parsing logic
    ├── models.py            # Data models
    └── exceptions.py        # Custom exceptions
```

### 2. Data Models

```python
# automation/git/models.py
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, HttpUrl, field_validator


@dataclass(frozen=True)
class GitRemote:
    """Represents a Git remote configuration.

    Attributes:
        name: Remote name (e.g., 'origin', 'upstream')
        url: Raw URL from git config
        url_type: Whether SSH or HTTPS format
    """
    name: str
    url: str
    url_type: Literal["ssh", "https", "unknown"]


class RepositoryInfo(BaseModel):
    """Parsed repository information.

    Attributes:
        owner: Repository owner/organization
        repo: Repository name
        base_url: Gitea instance base URL (e.g., https://gitea.com)
        remote_name: Which remote was used (origin/upstream/etc)
        ssh_url: SSH clone URL
        https_url: HTTPS clone URL
    """
    owner: str
    repo: str
    base_url: HttpUrl
    remote_name: str
    ssh_url: str
    https_url: str

    @field_validator("owner", "repo")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure owner and repo are not empty."""
        if not v or not v.strip():
            raise ValueError("Owner and repo must not be empty")
        return v.strip()

    @field_validator("repo")
    @classmethod
    def validate_no_git_suffix(cls, v: str) -> str:
        """Ensure .git suffix is removed."""
        return v.removesuffix(".git")

    @property
    def full_name(self) -> str:
        """Return owner/repo format."""
        return f"{self.owner}/{self.repo}"


class MultipleRemotesInfo(BaseModel):
    """Information when multiple remotes are detected.

    Attributes:
        remotes: List of all detected remotes
        suggested: Suggested remote to use (origin > upstream > first)
    """
    remotes: list[GitRemote]
    suggested: GitRemote | None

    @property
    def remote_names(self) -> list[str]:
        """Return list of remote names."""
        return [r.name for r in self.remotes]
```

### 3. Exception Hierarchy

```python
# automation/git/exceptions.py
"""Git discovery exceptions."""


class GitDiscoveryError(Exception):
    """Base exception for Git discovery errors."""

    def __init__(self, message: str, hint: str | None = None):
        """Initialize exception.

        Args:
            message: Error message
            hint: Optional hint for resolution
        """
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        """Format error message with hint."""
        if self.hint:
            return f"{self.message}\n\nHint: {self.hint}"
        return self.message


class NotGitRepositoryError(GitDiscoveryError):
    """Raised when directory is not a Git repository."""

    def __init__(self, path: str):
        super().__init__(
            message=f"Not a Git repository: {path}",
            hint="Run 'git init' or navigate to a Git repository directory."
        )
        self.path = path


class NoRemotesError(GitDiscoveryError):
    """Raised when repository has no remotes configured."""

    def __init__(self):
        super().__init__(
            message="No Git remotes configured in this repository",
            hint="Add a remote with: git remote add origin <url>"
        )


class MultipleRemotesError(GitDiscoveryError):
    """Raised when multiple remotes exist and selection is ambiguous.

    Attributes:
        remotes: Available remotes
        suggested: Suggested remote to use
    """

    def __init__(self, remotes: list[GitRemote], suggested: GitRemote | None):
        remote_list = ", ".join(f"'{r.name}'" for r in remotes)
        suggestion = f"Use --remote {suggested.name}" if suggested else ""

        super().__init__(
            message=f"Multiple remotes found: {remote_list}",
            hint=f"Specify which remote to use. {suggestion}"
        )
        self.remotes = remotes
        self.suggested = suggested


class InvalidGitUrlError(GitDiscoveryError):
    """Raised when Git URL format is not recognized."""

    def __init__(self, url: str, reason: str | None = None):
        msg = f"Invalid Git URL format: {url}"
        if reason:
            msg += f" ({reason})"

        super().__init__(
            message=msg,
            hint="Expected formats:\n"
                 "  - git@gitea.com:owner/repo.git\n"
                 "  - https://gitea.com/owner/repo.git"
        )
        self.url = url


class UnsupportedHostError(GitDiscoveryError):
    """Raised when Git host is not Gitea."""

    def __init__(self, host: str, url: str):
        super().__init__(
            message=f"Unsupported Git host: {host}",
            hint=f"This tool only supports Gitea repositories.\n"
                 f"Remote URL: {url}"
        )
        self.host = host
        self.url = url
```

---

## Implementation Details

### 4. URL Parser

```python
# automation/git/parser.py
"""Git URL parsing utilities."""

import re
from typing import Literal
from urllib.parse import urlparse

from automation.git.exceptions import InvalidGitUrlError


class GitUrlParser:
    """Parser for Git URLs in SSH and HTTPS formats."""

    # Regex patterns for Git URL formats
    SSH_PATTERN = re.compile(
        r"^(?:(?P<user>\w+)@)?(?P<host>[a-zA-Z0-9._-]+):(?P<path>.+?)(?:\.git)?$"
    )

    HTTPS_PATTERN = re.compile(
        r"^https?://(?P<host>[a-zA-Z0-9._-]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?$"
    )

    def __init__(self, url: str):
        """Initialize parser.

        Args:
            url: Git URL to parse
        """
        self.url = url.strip()
        self._url_type: Literal["ssh", "https", "unknown"] = "unknown"
        self._host: str | None = None
        self._port: int | None = None
        self._path: str | None = None
        self._owner: str | None = None
        self._repo: str | None = None

        self._parse()

    def _parse(self) -> None:
        """Parse the Git URL."""
        # Try SSH format first
        if self._parse_ssh():
            self._url_type = "ssh"
            return

        # Try HTTPS format
        if self._parse_https():
            self._url_type = "https"
            return

        # Neither format matched
        raise InvalidGitUrlError(
            self.url,
            reason="Must be SSH (git@host:path) or HTTPS (https://host/path)"
        )

    def _parse_ssh(self) -> bool:
        """Parse SSH format: git@gitea.com:owner/repo.git

        Returns:
            True if successfully parsed
        """
        match = self.SSH_PATTERN.match(self.url)
        if not match:
            return False

        self._host = match.group("host")
        self._path = match.group("path")
        self._extract_owner_repo()
        return True

    def _parse_https(self) -> bool:
        """Parse HTTPS format: https://gitea.com/owner/repo.git

        Returns:
            True if successfully parsed
        """
        match = self.HTTPS_PATTERN.match(self.url)
        if not match:
            return False

        self._host = match.group("host")
        port = match.group("port")
        self._port = int(port) if port else None
        self._path = match.group("path")
        self._extract_owner_repo()
        return True

    def _extract_owner_repo(self) -> None:
        """Extract owner and repo from path.

        Raises:
            InvalidGitUrlError: If path doesn't contain owner/repo
        """
        if not self._path:
            raise InvalidGitUrlError(self.url, reason="Empty path")

        # Remove leading/trailing slashes and .git suffix
        path = self._path.strip("/").removesuffix(".git")

        # Split by / and validate
        parts = path.split("/")

        if len(parts) < 2:
            raise InvalidGitUrlError(
                self.url,
                reason=f"Path must contain owner/repo (got: {path})"
            )

        self._owner = parts[0]
        self._repo = parts[1]

        if not self._owner or not self._repo:
            raise InvalidGitUrlError(
                self.url,
                reason="Owner and repo must not be empty"
            )

    @property
    def url_type(self) -> Literal["ssh", "https", "unknown"]:
        """Return URL type."""
        return self._url_type

    @property
    def host(self) -> str:
        """Return hostname."""
        if self._host is None:
            raise ValueError("URL not parsed")
        return self._host

    @property
    def port(self) -> int | None:
        """Return port (only for HTTPS)."""
        return self._port

    @property
    def owner(self) -> str:
        """Return repository owner."""
        if self._owner is None:
            raise ValueError("URL not parsed")
        return self._owner

    @property
    def repo(self) -> str:
        """Return repository name."""
        if self._repo is None:
            raise ValueError("URL not parsed")
        return self._repo

    @property
    def base_url(self) -> str:
        """Return base URL for API access (always HTTPS).

        Returns:
            Base URL like https://gitea.com or https://gitea.com:3000
        """
        if self._host is None:
            raise ValueError("URL not parsed")

        if self._port:
            return f"https://{self._host}:{self._port}"
        return f"https://{self._host}"

    @property
    def ssh_url(self) -> str:
        """Return SSH clone URL."""
        return f"git@{self.host}:{self.owner}/{self.repo}.git"

    @property
    def https_url(self) -> str:
        """Return HTTPS clone URL."""
        if self._port:
            return f"https://{self.host}:{self._port}/{self.owner}/{self.repo}.git"
        return f"https://{self.host}/{self.owner}/{self.repo}.git"
```

### 5. Git Discovery

```python
# automation/git/discovery.py
"""Git repository discovery."""

from pathlib import Path
from typing import Literal

try:
    import git
    from git.exc import InvalidGitRepositoryError, GitCommandError
except ImportError as e:
    raise ImportError(
        "GitPython is required for Git discovery. "
        "Install it with: pip install gitpython"
    ) from e

from automation.git.exceptions import (
    NotGitRepositoryError,
    NoRemotesError,
    MultipleRemotesError,
    InvalidGitUrlError,
)
from automation.git.models import GitRemote, RepositoryInfo, MultipleRemotesInfo
from automation.git.parser import GitUrlParser


class GitDiscovery:
    """Discovers Git repository configuration."""

    # Preferred remote names in order of preference
    PREFERRED_REMOTES = ["origin", "upstream"]

    def __init__(self, repo_path: str | Path = "."):
        """Initialize discovery.

        Args:
            repo_path: Path to Git repository (default: current directory)
        """
        self.repo_path = Path(repo_path).resolve()
        self._repo: git.Repo | None = None

    def _get_repo(self) -> git.Repo:
        """Get Git repository object.

        Returns:
            GitPython Repo object

        Raises:
            NotGitRepositoryError: If not a Git repository
        """
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            except InvalidGitRepositoryError:
                raise NotGitRepositoryError(str(self.repo_path))

        return self._repo

    def list_remotes(self) -> list[GitRemote]:
        """List all Git remotes.

        Returns:
            List of Git remotes

        Raises:
            NotGitRepositoryError: If not a Git repository
        """
        repo = self._get_repo()

        remotes = []
        for remote in repo.remotes:
            url = remote.url

            # Determine URL type
            url_type: Literal["ssh", "https", "unknown"] = "unknown"
            if url.startswith("git@"):
                url_type = "ssh"
            elif url.startswith(("http://", "https://")):
                url_type = "https"

            remotes.append(GitRemote(
                name=remote.name,
                url=url,
                url_type=url_type
            ))

        return remotes

    def get_remote(
        self,
        remote_name: str | None = None,
        allow_multiple: bool = False
    ) -> GitRemote:
        """Get Git remote by name or use preferred remote.

        Args:
            remote_name: Specific remote name (optional)
            allow_multiple: If False, raise error when multiple remotes exist

        Returns:
            Selected Git remote

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
            MultipleRemotesError: If multiple remotes and none specified
            ValueError: If specified remote not found
        """
        remotes = self.list_remotes()

        if not remotes:
            raise NoRemotesError()

        # If specific remote requested, find it
        if remote_name:
            for remote in remotes:
                if remote.name == remote_name:
                    return remote
            raise ValueError(
                f"Remote '{remote_name}' not found. "
                f"Available: {', '.join(r.name for r in remotes)}"
            )

        # Single remote - use it
        if len(remotes) == 1:
            return remotes[0]

        # Multiple remotes - try preferred names
        for preferred in self.PREFERRED_REMOTES:
            for remote in remotes:
                if remote.name == preferred:
                    return remote

        # Multiple remotes, none preferred
        if not allow_multiple:
            suggested = remotes[0]  # Use first as suggestion
            raise MultipleRemotesError(remotes, suggested)

        # Return first remote as fallback
        return remotes[0]

    def get_multiple_remotes_info(self) -> MultipleRemotesInfo:
        """Get information about multiple remotes.

        Returns:
            Information about all remotes and suggested remote

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
        """
        remotes = self.list_remotes()

        if not remotes:
            raise NoRemotesError()

        # Find suggested remote
        suggested = None
        for preferred in self.PREFERRED_REMOTES:
            for remote in remotes:
                if remote.name == preferred:
                    suggested = remote
                    break
            if suggested:
                break

        if not suggested:
            suggested = remotes[0]

        return MultipleRemotesInfo(remotes=remotes, suggested=suggested)

    def parse_repository(
        self,
        remote_name: str | None = None,
        allow_multiple: bool = False
    ) -> RepositoryInfo:
        """Parse repository information from Git remote.

        Args:
            remote_name: Specific remote name (optional)
            allow_multiple: If False, raise error when multiple remotes exist

        Returns:
            Parsed repository information

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
            MultipleRemotesError: If multiple remotes and none specified
            InvalidGitUrlError: If URL format invalid
        """
        remote = self.get_remote(remote_name, allow_multiple)
        parser = GitUrlParser(remote.url)

        return RepositoryInfo(
            owner=parser.owner,
            repo=parser.repo,
            base_url=parser.base_url,
            remote_name=remote.name,
            ssh_url=parser.ssh_url,
            https_url=parser.https_url,
        )

    def detect_gitea_config(
        self,
        remote_name: str | None = None
    ) -> dict[str, str]:
        """Detect Gitea configuration for .builder/config.toml

        Args:
            remote_name: Specific remote name (optional)

        Returns:
            Dictionary with config values:
                - base_url: Gitea instance URL
                - owner: Repository owner
                - repo: Repository name

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
            MultipleRemotesError: If multiple remotes and none specified
            InvalidGitUrlError: If URL format invalid
        """
        info = self.parse_repository(remote_name, allow_multiple=False)

        return {
            "base_url": str(info.base_url),
            "owner": info.owner,
            "repo": info.repo,
        }


def detect_git_origin(repo_path: str | Path = ".") -> str | None:
    """Quick helper to detect Git origin URL.

    Args:
        repo_path: Path to repository (default: current directory)

    Returns:
        Base URL or None if not found/error
    """
    try:
        discovery = GitDiscovery(repo_path)
        info = discovery.parse_repository(allow_multiple=True)
        return str(info.base_url)
    except Exception:
        return None
```

---

## Error Handling Strategy

### 6. Error Scenarios and Responses

| Scenario | Exception | User Message | Suggested Action |
|----------|-----------|--------------|------------------|
| Not a Git repo | `NotGitRepositoryError` | "Not a Git repository: /path" | "Run 'git init' or navigate to a Git repository" |
| No remotes | `NoRemotesError` | "No Git remotes configured" | "Add a remote with: git remote add origin <url>" |
| Multiple remotes | `MultipleRemotesError` | "Multiple remotes found: origin, upstream" | "Use --remote origin" |
| Invalid URL format | `InvalidGitUrlError` | "Invalid Git URL: xyz://..." | "Expected git@host:path or https://host/path" |
| Missing owner/repo | `InvalidGitUrlError` | "Cannot extract owner/repo from URL" | "URL must contain owner/repo path" |

### 7. CLI Integration Example

```python
# automation/cli/init.py
"""Builder init command."""

import click
from pathlib import Path

from automation.git.discovery import GitDiscovery
from automation.git.exceptions import (
    GitDiscoveryError,
    MultipleRemotesError,
    NoRemotesError,
)


@click.command()
@click.option(
    "--remote",
    default=None,
    help="Git remote name to use (default: auto-detect)"
)
@click.option(
    "--path",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Repository path (default: current directory)"
)
def init(remote: str | None, path: str) -> None:
    """Initialize builder configuration for a repository.

    Automatically detects Gitea repository information from Git remotes.
    """
    try:
        discovery = GitDiscovery(path)

        # Try to get config
        try:
            config = discovery.detect_gitea_config(remote)

            click.echo(f"✓ Detected Gitea repository:")
            click.echo(f"  Base URL: {config['base_url']}")
            click.echo(f"  Owner:    {config['owner']}")
            click.echo(f"  Repo:     {config['repo']}")

            # Create .builder/config.toml with detected values
            # ... (config generation code)

        except MultipleRemotesError as e:
            # Show available remotes and ask user to choose
            info = discovery.get_multiple_remotes_info()

            click.echo("Multiple Git remotes detected:", err=True)
            for r in info.remotes:
                marker = "→" if r == info.suggested else " "
                click.echo(f"  {marker} {r.name}: {r.url}")

            if info.suggested:
                click.echo(f"\nUsing suggested remote: {info.suggested.name}")
                click.echo(f"To use a different remote: builder init --remote <name>")

                # Use suggested remote
                config = discovery.detect_gitea_config(info.suggested.name)
                # ... (continue with config generation)
            else:
                click.echo(
                    f"\nPlease specify which remote to use: "
                    f"builder init --remote <name>",
                    err=True
                )
                raise click.Abort()

    except NoRemotesError as e:
        click.echo(str(e), err=True)
        click.echo(
            "\nManual configuration required. Creating default config...",
            err=True
        )
        # Fall back to interactive prompts
        # ... (manual config code)

    except GitDiscoveryError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
```

---

## Testing Strategy

### 8. Unit Tests

```python
# tests/unit/test_git_parser.py
"""Unit tests for Git URL parser."""

import pytest

from automation.git.parser import GitUrlParser
from automation.git.exceptions import InvalidGitUrlError


class TestGitUrlParser:
    """Tests for GitUrlParser."""

    def test_parse_ssh_url(self):
        """Test parsing SSH format URL."""
        parser = GitUrlParser("git@gitea.com:owner/repo.git")

        assert parser.url_type == "ssh"
        assert parser.host == "gitea.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://gitea.com"
        assert parser.ssh_url == "git@gitea.com:owner/repo.git"
        assert parser.https_url == "https://gitea.com/owner/repo.git"

    def test_parse_ssh_url_without_git_suffix(self):
        """Test parsing SSH URL without .git suffix."""
        parser = GitUrlParser("git@gitea.com:owner/repo")

        assert parser.owner == "owner"
        assert parser.repo == "repo"

    def test_parse_https_url(self):
        """Test parsing HTTPS format URL."""
        parser = GitUrlParser("https://gitea.com/owner/repo.git")

        assert parser.url_type == "https"
        assert parser.host == "gitea.com"
        assert parser.owner == "owner"
        assert parser.repo == "repo"
        assert parser.base_url == "https://gitea.com"

    def test_parse_https_url_with_port(self):
        """Test parsing HTTPS URL with custom port."""
        parser = GitUrlParser("https://gitea.com:3000/owner/repo.git")

        assert parser.host == "gitea.com"
        assert parser.port == 3000
        assert parser.base_url == "https://gitea.com:3000"
        assert parser.https_url == "https://gitea.com:3000/owner/repo.git"

    def test_parse_http_url(self):
        """Test parsing HTTP (insecure) URL."""
        parser = GitUrlParser("http://gitea.local/owner/repo.git")

        assert parser.url_type == "https"  # Still returns https base_url
        assert parser.host == "gitea.local"

    def test_invalid_url_format(self):
        """Test invalid URL format raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("ftp://gitea.com/owner/repo")

        assert "Invalid Git URL" in str(exc_info.value)

    def test_missing_owner_repo(self):
        """Test URL without owner/repo raises error."""
        with pytest.raises(InvalidGitUrlError) as exc_info:
            GitUrlParser("git@gitea.com:repo.git")

        assert "owner/repo" in str(exc_info.value)

    def test_empty_owner_or_repo(self):
        """Test URL with empty owner or repo raises error."""
        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("git@gitea.com:/repo.git")

        with pytest.raises(InvalidGitUrlError):
            GitUrlParser("git@gitea.com:owner/.git")

    def test_nested_path(self):
        """Test URL with nested path (e.g., /group/subgroup/repo)."""
        parser = GitUrlParser("git@gitea.com:group/subgroup/repo.git")

        # Should extract first two parts as owner and repo
        assert parser.owner == "group"
        assert parser.repo == "subgroup"


# tests/unit/test_git_discovery.py
"""Unit tests for Git discovery."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from automation.git.discovery import GitDiscovery
from automation.git.exceptions import (
    NotGitRepositoryError,
    NoRemotesError,
    MultipleRemotesError,
)
from automation.git.models import GitRemote


class TestGitDiscovery:
    """Tests for GitDiscovery."""

    @patch("automation.git.discovery.git.Repo")
    def test_list_remotes_single(self, mock_repo_class):
        """Test listing remotes with single remote."""
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
        assert remotes[0].url_type == "ssh"

    @patch("automation.git.discovery.git.Repo")
    def test_list_remotes_multiple(self, mock_repo_class):
        """Test listing multiple remotes."""
        # Mock multiple remotes
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
        assert remotes[1].name == "upstream"

    @patch("automation.git.discovery.git.Repo")
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

    @patch("automation.git.discovery.git.Repo")
    def test_get_remote_prefers_origin(self, mock_repo_class):
        """Test that origin is preferred over other remotes."""
        mock_origin = Mock()
        mock_origin.name = "origin"
        mock_origin.url = "git@gitea.com:owner/repo.git"

        mock_other = Mock()
        mock_other.name = "other"
        mock_other.url = "git@gitea.com:other/repo.git"

        mock_repo = Mock()
        mock_repo.remotes = [mock_other, mock_origin]  # origin not first
        mock_repo_class.return_value = mock_repo

        discovery = GitDiscovery()
        remote = discovery.get_remote(allow_multiple=True)

        assert remote.name == "origin"

    @patch("automation.git.discovery.git.Repo")
    def test_get_remote_multiple_raises_error(self, mock_repo_class):
        """Test that multiple remotes raise error without allow_multiple."""
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

        # Should raise without allow_multiple
        with pytest.raises(MultipleRemotesError) as exc_info:
            discovery.get_remote(allow_multiple=False)

        assert "origin" in str(exc_info.value)

    @patch("automation.git.discovery.git.Repo")
    def test_parse_repository(self, mock_repo_class):
        """Test parsing repository information."""
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
        assert info.base_url == "https://gitea.com"
        assert info.remote_name == "origin"

    @patch("automation.git.discovery.git.Repo")
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

        assert config["base_url"] == "https://gitea.example.com:3000"
        assert config["owner"] == "myorg"
        assert config["repo"] == "myrepo"
```

### 9. Integration Tests

```python
# tests/integration/test_git_discovery_integration.py
"""Integration tests for Git discovery."""

import pytest
import subprocess
from pathlib import Path
import tempfile
import shutil

from automation.git.discovery import GitDiscovery
from automation.git.exceptions import NotGitRepositoryError, NoRemotesError


class TestGitDiscoveryIntegration:
    """Integration tests with real Git operations."""

    @pytest.fixture
    def temp_repo(self):
        """Create temporary Git repository."""
        temp_dir = Path(tempfile.mkdtemp())

        # Initialize Git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True
        )

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_not_git_repository(self):
        """Test error when directory is not a Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            discovery = GitDiscovery(temp_dir)

            with pytest.raises(NotGitRepositoryError):
                discovery.list_remotes()

    def test_no_remotes(self, temp_repo):
        """Test error when repository has no remotes."""
        discovery = GitDiscovery(temp_repo)

        with pytest.raises(NoRemotesError):
            discovery.get_remote()

    def test_with_ssh_remote(self, temp_repo):
        """Test discovery with SSH remote."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "owner"
        assert info.repo == "repo"
        assert info.base_url == "https://gitea.com"

    def test_with_https_remote(self, temp_repo):
        """Test discovery with HTTPS remote."""
        subprocess.run(
            [
                "git", "remote", "add", "origin",
                "https://gitea.example.com/myorg/myrepo.git"
            ],
            cwd=temp_repo,
            check=True
        )

        discovery = GitDiscovery(temp_repo)
        info = discovery.parse_repository()

        assert info.owner == "myorg"
        assert info.repo == "myrepo"
        assert info.base_url == "https://gitea.example.com"

    def test_multiple_remotes(self, temp_repo):
        """Test discovery with multiple remotes."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitea.com:owner/repo.git"],
            cwd=temp_repo,
            check=True
        )
        subprocess.run(
            ["git", "remote", "add", "upstream", "git@gitea.com:upstream/repo.git"],
            cwd=temp_repo,
            check=True
        )

        discovery = GitDiscovery(temp_repo)

        # Should prefer origin
        info = discovery.parse_repository(allow_multiple=True)
        assert info.owner == "owner"

        # Can explicitly select upstream
        info = discovery.parse_repository(remote_name="upstream")
        assert info.owner == "upstream"
```

---

## Dependencies

### 10. Required Packages

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "gitpython>=3.1.40",  # Git repository interaction
]
```

**Why GitPython?**
- Industry-standard library for Git operations in Python
- Mature, well-maintained (10+ years)
- Type-hint support
- Cross-platform compatibility
- Better than subprocess calls to `git` CLI

---

## Public API

### 11. Module Exports

```python
# automation/git/__init__.py
"""Git repository discovery and parsing.

This module provides functionality to automatically detect Git repository
configuration from local remotes, parse Git URLs, and extract repository
information for use with Gitea automation.

Example:
    >>> from automation.git import GitDiscovery
    >>> discovery = GitDiscovery()
    >>> info = discovery.parse_repository()
    >>> print(f"{info.owner}/{info.repo} @ {info.base_url}")
    owner/repo @ https://gitea.com

Error Handling:
    All exceptions inherit from GitDiscoveryError and include helpful
    error messages and hints for resolution.
"""

from automation.git.discovery import GitDiscovery, detect_git_origin
from automation.git.parser import GitUrlParser
from automation.git.models import GitRemote, RepositoryInfo, MultipleRemotesInfo
from automation.git.exceptions import (
    GitDiscoveryError,
    NotGitRepositoryError,
    NoRemotesError,
    MultipleRemotesError,
    InvalidGitUrlError,
    UnsupportedHostError,
)

__all__ = [
    # Main API
    "GitDiscovery",
    "detect_git_origin",

    # Parser
    "GitUrlParser",

    # Models
    "GitRemote",
    "RepositoryInfo",
    "MultipleRemotesInfo",

    # Exceptions
    "GitDiscoveryError",
    "NotGitRepositoryError",
    "NoRemotesError",
    "MultipleRemotesError",
    "InvalidGitUrlError",
    "UnsupportedHostError",
]
```

---

## Usage Examples

### 12. Common Use Cases

#### Basic Usage
```python
from automation.git import GitDiscovery

# Detect repository info
discovery = GitDiscovery()
info = discovery.parse_repository()

print(f"Base URL: {info.base_url}")
print(f"Owner: {info.owner}")
print(f"Repo: {info.repo}")
```

#### Handle Multiple Remotes
```python
from automation.git import GitDiscovery, MultipleRemotesError

discovery = GitDiscovery()

try:
    info = discovery.parse_repository()
except MultipleRemotesError as e:
    print("Multiple remotes found:")
    for remote in e.remotes:
        print(f"  - {remote.name}: {remote.url}")

    # Use suggested remote
    if e.suggested:
        print(f"Using: {e.suggested.name}")
        info = discovery.parse_repository(remote_name=e.suggested.name)
```

#### Graceful Fallback
```python
from automation.git import detect_git_origin

# Quick check with None fallback
base_url = detect_git_origin()

if base_url:
    print(f"Detected: {base_url}")
else:
    print("No Git remote found, using manual configuration")
    base_url = input("Enter Gitea URL: ")
```

#### CLI Integration
```python
import click
from automation.git import GitDiscovery, GitDiscoveryError

@click.command()
@click.option("--remote", help="Git remote name")
def init(remote):
    """Initialize builder configuration."""
    try:
        discovery = GitDiscovery()
        config = discovery.detect_gitea_config(remote)

        # Use config to create .builder/config.toml
        create_config(config)

    except GitDiscoveryError as e:
        click.echo(f"Error: {e}", err=True)

        # Fall back to manual input
        config = prompt_for_config()
        create_config(config)
```

---

## Implementation Checklist

### Phase 1: Core Implementation (4-6 hours)
- [ ] Create `automation/git/` module structure
- [ ] Implement `exceptions.py` with exception hierarchy
- [ ] Implement `models.py` with Pydantic models
- [ ] Implement `parser.py` with URL parsing logic
- [ ] Implement `discovery.py` with Git detection
- [ ] Create `__init__.py` with public API exports

### Phase 2: Testing (3-4 hours)
- [ ] Write unit tests for `GitUrlParser`
- [ ] Write unit tests for `GitDiscovery`
- [ ] Write integration tests with real Git repos
- [ ] Test edge cases (nested paths, ports, etc.)
- [ ] Test error messages and hints

### Phase 3: Integration (2-3 hours)
- [ ] Integrate into `builder init` command
- [ ] Add `--remote` option to CLI
- [ ] Implement interactive remote selection
- [ ] Add fallback to manual configuration
- [ ] Update documentation

### Phase 4: Documentation (1-2 hours)
- [ ] Add docstrings to all public functions
- [ ] Create usage examples
- [ ] Document error handling
- [ ] Add type hints to all functions
- [ ] Update main README

---

## Edge Cases Handled

### URL Formats
- ✓ SSH with .git suffix: `git@gitea.com:owner/repo.git`
- ✓ SSH without .git: `git@gitea.com:owner/repo`
- ✓ HTTPS with .git: `https://gitea.com/owner/repo.git`
- ✓ HTTPS without .git: `https://gitea.com/owner/repo`
- ✓ Custom port: `https://gitea.com:3000/owner/repo.git`
- ✓ HTTP (insecure): `http://gitea.local/owner/repo.git`
- ✓ Nested paths: `git@gitea.com:group/subgroup/repo.git`

### Repository States
- ✓ Not a Git repository
- ✓ No remotes configured
- ✓ Single remote
- ✓ Multiple remotes (origin + upstream)
- ✓ Multiple remotes (none named origin/upstream)
- ✓ Invalid remote URL format
- ✓ Remote with empty owner or repo

### Platform Compatibility
- ✓ Linux paths
- ✓ Windows paths (GitPython handles this)
- ✓ macOS paths
- ✓ Submodules
- ✓ Worktrees

---

## Security Considerations

### 1. No Credential Exposure
- Never log or display full URLs with embedded credentials
- Use `***` masking for sensitive parts if needed
- Don't cache credentials in memory longer than necessary

### 2. Path Traversal Protection
- Use `Path.resolve()` to normalize paths
- Validate that repo_path stays within expected boundaries
- GitPython handles most path security internally

### 3. Input Validation
- Validate all URL components
- Reject malformed URLs early
- Use Pydantic for automatic validation

---

## Performance Considerations

### 1. Lazy Repository Loading
- Don't load Git repository until actually needed
- Cache `git.Repo` object after first load
- Use `search_parent_directories=True` to find `.git` folder

### 2. Minimal Git Operations
- Only fetch remote URLs (no network calls)
- No `git fetch` or `git pull` operations
- Read-only operations only

### 3. Fast Path for Common Case
- Optimize for single remote named "origin"
- Early return when possible
- Avoid unnecessary parsing

---

## Future Enhancements

### Potential Features (Not in Initial Implementation)
1. **Gitea Instance Validation**
   - Ping base_url to verify it's actually Gitea
   - Check API accessibility
   - Validate credentials

2. **Support for Other Hosts**
   - GitHub detection
   - GitLab detection
   - Generic Git hosting

3. **Submodule Support**
   - Detect and parse submodule URLs
   - Multi-repo configuration

4. **Configuration Caching**
   - Cache detected config to avoid repeated Git calls
   - Invalidation strategy

5. **Rich Output**
   - Color-coded error messages
   - Interactive remote selection with rich
   - Progress indicators

---

## Success Criteria

Implementation is complete when:
1. ✓ All 4 phases completed
2. ✓ 90%+ test coverage
3. ✓ All edge cases handled
4. ✓ Error messages are clear and actionable
5. ✓ Integration with `builder init` works seamlessly
6. ✓ Documentation is complete
7. ✓ Type hints pass mypy strict mode
8. ✓ No external network calls required

---

## Appendix: File Structure

```
automation/
└── git/
    ├── __init__.py          # 60 lines  - Public API
    ├── exceptions.py        # 120 lines - Exception hierarchy
    ├── models.py            # 100 lines - Pydantic models
    ├── parser.py            # 180 lines - URL parsing
    └── discovery.py         # 220 lines - Git discovery

tests/
├── unit/
│   ├── test_git_parser.py      # 250 lines
│   └── test_git_discovery.py   # 200 lines
└── integration/
    └── test_git_discovery_integration.py  # 150 lines

Total: ~1,280 lines of production + test code
```

---

## Related Documentation

- [Technical Review](./packageit/TECHNICAL_REVIEW.md) - Original feedback
- [Builder CLI Redesign](./packageit/builder-cli-redesign.md) - CLI integration
- [PyPI Distribution Plan](./packageit/pip-distribution-plan.md) - Dependencies

---

**Last Updated**: 2025-12-22
**Status**: Ready for Implementation
**Review Date**: 2025-12-29
