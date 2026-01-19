"""Git repository data models.

This module defines Pydantic models for Git repository information, including
remotes, parsed repository details, and multi-remote scenarios.

Example:
    >>> from repo_sapiens.git.models import RepositoryInfo
    >>> info = RepositoryInfo(
    ...     owner="myorg",
    ...     repo="myrepo",
    ...     base_url="https://gitea.com",
    ...     remote_name="origin",
    ...     ssh_url="git@gitea.com:myorg/myrepo.git",
    ...     https_url="https://gitea.com/myorg/myrepo.git"
    ... )
    >>> info.full_name
    'myorg/myrepo'
"""

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

    This model represents complete information about a Git repository parsed
    from a remote URL, including owner, repo name, base URL, and clone URLs.

    Attributes:
        owner: Repository owner/organization
        repo: Repository name (without .git suffix)
        base_url: Gitea instance base URL (e.g., https://gitea.com)
        remote_name: Which remote was used (origin/upstream/etc)
        ssh_url: SSH clone URL
        https_url: HTTPS clone URL

    Example:
        >>> info = RepositoryInfo(
        ...     owner="myorg",
        ...     repo="myrepo",
        ...     base_url="https://gitea.com",
        ...     remote_name="origin",
        ...     ssh_url="git@gitea.com:myorg/myrepo.git",
        ...     https_url="https://gitea.com/myorg/myrepo.git"
        ... )
        >>> info.full_name
        'myorg/myrepo'
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
        """Ensure owner and repo are not empty.

        Args:
            v: The value to validate

        Returns:
            Stripped value

        Raises:
            ValueError: If value is empty or whitespace
        """
        if not v or not v.strip():
            raise ValueError("Owner and repo must not be empty")
        return v.strip()

    @field_validator("repo")
    @classmethod
    def validate_no_git_suffix(cls, v: str) -> str:
        """Ensure .git suffix is removed.

        Args:
            v: The repo name

        Returns:
            Repo name without .git suffix
        """
        return v.removesuffix(".git")

    @property
    def full_name(self) -> str:
        """Return owner/repo format.

        Returns:
            Repository full name in owner/repo format
        """
        return f"{self.owner}/{self.repo}"


class MultipleRemotesInfo(BaseModel):
    """Information when multiple remotes are detected.

    This model provides information about all detected remotes and suggests
    which one should be used based on naming conventions.

    Attributes:
        remotes: List of all detected remotes
        suggested: Suggested remote to use (origin > upstream > first)

    Example:
        >>> from repo_sapiens.git.models import GitRemote, MultipleRemotesInfo
        >>> remotes = [
        ...     GitRemote("origin", "git@gitea.com:owner/repo.git", "ssh"),
        ...     GitRemote("upstream", "git@gitea.com:upstream/repo.git", "ssh")
        ... ]
        >>> info = MultipleRemotesInfo(remotes=remotes, suggested=remotes[0])
        >>> info.remote_names
        ['origin', 'upstream']
    """

    remotes: list[GitRemote]
    suggested: GitRemote | None

    @property
    def remote_names(self) -> list[str]:
        """Return list of remote names.

        Returns:
            List of remote names
        """
        return [r.name for r in self.remotes]
