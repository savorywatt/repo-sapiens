"""Git repository discovery.

This module provides functionality to discover Git repository configuration
from local repositories, including remote detection and repository information
parsing.

Example:
    >>> from automation.git.discovery import GitDiscovery
    >>> discovery = GitDiscovery()
    >>> info = discovery.parse_repository()
    >>> print(f"{info.owner}/{info.repo} @ {info.base_url}")
    owner/repo @ https://gitea.com
"""

from pathlib import Path
from typing import Literal

try:
    import git
    from git.exc import InvalidGitRepositoryError
except ImportError as e:
    raise ImportError(
        "GitPython is required for Git discovery. Install it with: pip install gitpython"
    ) from e

from automation.git.exceptions import (
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
)
from automation.git.models import GitRemote, MultipleRemotesInfo, RepositoryInfo
from automation.git.parser import GitUrlParser


class GitDiscovery:
    """Discovers Git repository configuration.

    This class provides methods to discover Git repository information from
    local Git repositories, including remote detection, URL parsing, and
    configuration extraction.

    Attributes:
        repo_path: Path to the Git repository
        PREFERRED_REMOTES: List of preferred remote names in order

    Example:
        >>> discovery = GitDiscovery()
        >>> config = discovery.detect_gitea_config()
        >>> print(config['base_url'])
        https://gitea.com
    """

    # Preferred remote names in order of preference
    PREFERRED_REMOTES = ["origin", "upstream"]

    def __init__(self, repo_path: str | Path = ".") -> None:
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
            except InvalidGitRepositoryError as e:
                raise NotGitRepositoryError(str(self.repo_path)) from e

        return self._repo

    def list_remotes(self) -> list[GitRemote]:
        """List all Git remotes.

        Returns:
            List of Git remotes with their names, URLs, and types

        Raises:
            NotGitRepositoryError: If not a Git repository

        Example:
            >>> discovery = GitDiscovery()
            >>> remotes = discovery.list_remotes()
            >>> for remote in remotes:
            ...     print(f"{remote.name}: {remote.url}")
            origin: git@gitea.com:owner/repo.git
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

            remotes.append(GitRemote(name=remote.name, url=url, url_type=url_type))

        return remotes

    def get_remote(self, remote_name: str | None = None, allow_multiple: bool = False) -> GitRemote:
        """Get Git remote by name or use preferred remote.

        This method retrieves a Git remote. If a specific remote name is
        provided, it looks for that remote. Otherwise, it uses the following
        preference order:
        1. If only one remote exists, use it
        2. If multiple remotes exist, prefer 'origin' then 'upstream'
        3. If no preferred remote found and allow_multiple is False, raise error

        Args:
            remote_name: Specific remote name (optional)
            allow_multiple: If False, raise error when multiple remotes exist
                and none match preferred names

        Returns:
            Selected Git remote

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
            MultipleRemotesError: If multiple remotes and none specified/preferred
            ValueError: If specified remote not found

        Example:
            >>> discovery = GitDiscovery()
            >>> remote = discovery.get_remote()
            >>> print(remote.name)
            origin
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
                f"Remote '{remote_name}' not found. Available: {', '.join(r.name for r in remotes)}"
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

        Returns information about all remotes and suggests which one to use
        based on naming conventions (origin > upstream > first).

        Returns:
            Information about all remotes and suggested remote

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured

        Example:
            >>> discovery = GitDiscovery()
            >>> info = discovery.get_multiple_remotes_info()
            >>> print(info.remote_names)
            ['origin', 'upstream']
            >>> print(info.suggested.name)
            origin
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
        self, remote_name: str | None = None, allow_multiple: bool = False
    ) -> RepositoryInfo:
        """Parse repository information from Git remote.

        Extracts complete repository information from a Git remote URL,
        including owner, repo name, base URL, and clone URLs.

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

        Example:
            >>> discovery = GitDiscovery()
            >>> info = discovery.parse_repository()
            >>> print(info.full_name)
            owner/repo
            >>> print(info.base_url)
            https://gitea.com
        """
        remote = self.get_remote(remote_name, allow_multiple)
        parser = GitUrlParser(remote.url)

        return RepositoryInfo(
            owner=parser.owner,
            repo=parser.repo,
            base_url=parser.base_url,  # type: ignore[arg-type]  # Pydantic validates str to HttpUrl
            remote_name=remote.name,
            ssh_url=parser.ssh_url,
            https_url=parser.https_url,
        )

    def detect_provider_type(self, remote_name: str | None = None) -> Literal["github", "gitea"]:
        """Detect Git provider type (GitHub or Gitea) from remote URL.

        Args:
            remote_name: Specific remote name (optional)

        Returns:
            Provider type: "github" or "gitea"

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured

        Example:
            >>> discovery = GitDiscovery()
            >>> provider = discovery.detect_provider_type()
            >>> print(provider)
            github
        """
        remote = self.get_remote(remote_name, allow_multiple=True)
        url_lower = remote.url.lower()

        # Check for GitHub
        if "github.com" in url_lower:
            return "github"

        # Check for GitHub Enterprise (common patterns)
        if "github" in url_lower and ("enterprise" in url_lower or "ghe" in url_lower):
            return "github"

        # Default to Gitea (self-hosted)
        return "gitea"

    def detect_git_config(self, remote_name: str | None = None) -> dict[str, str]:
        """Detect Git provider configuration.

        Detects repository configuration and returns a dictionary suitable
        for generating configuration files. Automatically detects if the
        remote is GitHub or Gitea.

        Args:
            remote_name: Specific remote name (optional)

        Returns:
            Dictionary with config values:
                - provider_type: "github" or "gitea"
                - base_url: Provider instance URL
                - owner: Repository owner
                - repo: Repository name

        Raises:
            NotGitRepositoryError: If not a Git repository
            NoRemotesError: If no remotes configured
            MultipleRemotesError: If multiple remotes and none specified
            InvalidGitUrlError: If URL format invalid

        Example:
            >>> discovery = GitDiscovery()
            >>> config = discovery.detect_git_config()
            >>> print(config)
            {
                'provider_type': 'github',
                'base_url': 'https://github.com',
                'owner': 'myorg',
                'repo': 'myrepo'
            }
        """
        info = self.parse_repository(remote_name, allow_multiple=False)
        provider_type = self.detect_provider_type(remote_name)

        # For GitHub, use api.github.com for API calls
        base_url = str(info.base_url)
        if provider_type == "github" and base_url == "https://github.com":
            api_url = "https://api.github.com"
        else:
            api_url = base_url

        return {
            "provider_type": provider_type,
            "base_url": api_url,
            "owner": info.owner,
            "repo": info.repo,
        }

    def detect_gitea_config(self, remote_name: str | None = None) -> dict[str, str]:
        """Detect Gitea configuration for .builder/config.toml

        Detects repository configuration and returns a dictionary suitable
        for generating configuration files.

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

        Example:
            >>> discovery = GitDiscovery()
            >>> config = discovery.detect_gitea_config()
            >>> print(config)
            {
                'base_url': 'https://gitea.com',
                'owner': 'myorg',
                'repo': 'myrepo'
            }
        """
        info = self.parse_repository(remote_name, allow_multiple=False)

        return {
            "base_url": str(info.base_url),
            "owner": info.owner,
            "repo": info.repo,
        }


def detect_git_origin(repo_path: str | Path = ".") -> str | None:
    """Quick helper to detect Git origin URL.

    This is a convenience function that attempts to detect the base URL
    of a Git repository. Returns None on any error, making it suitable
    for graceful fallback scenarios.

    Args:
        repo_path: Path to repository (default: current directory)

    Returns:
        Base URL or None if not found/error

    Example:
        >>> from automation.git import detect_git_origin
        >>> base_url = detect_git_origin()
        >>> if base_url:
        ...     print(f"Detected: {base_url}")
        ... else:
        ...     print("No Git remote found")
        Detected: https://gitea.com
    """
    try:
        discovery = GitDiscovery(repo_path)
        info = discovery.parse_repository(allow_multiple=True)
        return str(info.base_url)
    except Exception:
        return None
