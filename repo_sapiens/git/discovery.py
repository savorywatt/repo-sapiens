"""Git repository discovery and configuration extraction.

This module provides functionality to discover Git repository configuration
from local repositories, including remote detection, URL parsing, and
provider type identification. It supports GitHub, GitLab, and Gitea.

The discovery system can automatically detect:
    - Repository owner and name from remote URLs
    - Git provider type (GitHub, GitLab, Gitea)
    - Base URL for API access
    - SSH and HTTPS clone URLs

Key Exports:
    GitDiscovery: Main class for repository discovery operations.
    detect_git_origin: Quick helper to get the base URL of a repository.

Example:
    >>> from repo_sapiens.git.discovery import GitDiscovery
    >>> discovery = GitDiscovery()
    >>> info = discovery.parse_repository()
    >>> print(f"{info.owner}/{info.repo} @ {info.base_url}")
    owner/repo @ https://gitea.com

    >>> # Auto-detect provider type
    >>> provider = discovery.detect_provider_type()
    >>> print(provider)  # 'github', 'gitlab', or 'gitea'

Thread Safety:
    GitDiscovery instances cache the git.Repo object internally. While
    the class itself is not thread-safe, each instance can be used
    safely within a single thread.

Dependencies:
    Requires GitPython (gitpython) package for repository access.

See Also:
    - repo_sapiens.git.parser: Git URL parsing utilities
    - repo_sapiens.git.models: Data models for repository information
    - repo_sapiens.git.exceptions: Custom exceptions for git operations
"""

from pathlib import Path
from typing import Literal

try:
    import git
    from git.exc import InvalidGitRepositoryError
except ImportError as e:
    raise ImportError("GitPython is required for Git discovery. Install it with: pip install gitpython") from e

from repo_sapiens.git.exceptions import (
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
)
from repo_sapiens.git.models import GitRemote, MultipleRemotesInfo, RepositoryInfo
from repo_sapiens.git.parser import GitUrlParser


class GitDiscovery:
    """Discovers Git repository configuration from local repositories.

    This class provides methods to discover Git repository information from
    local Git repositories, including remote detection, URL parsing, and
    configuration extraction. It handles various edge cases like multiple
    remotes and different URL formats.

    The class uses lazy initialization for the git.Repo object, only
    accessing it when needed. This allows creating GitDiscovery instances
    before validating that the path is a valid Git repository.

    Attributes:
        repo_path: Resolved absolute path to the Git repository.
        PREFERRED_REMOTES: Class variable listing preferred remote names
            in order of preference ("origin", "upstream").

    Example:
        >>> discovery = GitDiscovery()
        >>>
        >>> # List all remotes
        >>> for remote in discovery.list_remotes():
        ...     print(f"{remote.name}: {remote.url}")
        >>>
        >>> # Get repository info
        >>> info = discovery.parse_repository()
        >>> print(f"Owner: {info.owner}")
        >>> print(f"Repo: {info.repo}")
        >>> print(f"Base URL: {info.base_url}")
        >>>
        >>> # Auto-detect configuration for config file
        >>> config = discovery.detect_git_config()
        >>> print(config)
        {'provider_type': 'github', 'base_url': 'https://api.github.com', ...}
    """

    # Preferred remote names in order of preference
    PREFERRED_REMOTES = ["origin", "upstream"]

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize Git discovery for a repository path.

        Args:
            repo_path: Path to the Git repository. Can be any path within
                the repository - parent directories are searched automatically.
                Default is current directory.

        Example:
            >>> # Current directory
            >>> discovery = GitDiscovery()
            >>>
            >>> # Specific path
            >>> discovery = GitDiscovery("/path/to/my/repo")
            >>>
            >>> # Path inside repository
            >>> discovery = GitDiscovery("/path/to/repo/src/module")

        Note:
            The repository is not validated during initialization. Validation
            occurs on first access to repository data (lazy initialization).
        """
        self.repo_path = Path(repo_path).resolve()
        self._repo: git.Repo | None = None

    def _get_repo(self) -> git.Repo:
        """Get the Git repository object, initializing if needed.

        Uses lazy initialization to defer repository access until needed.
        The repository is cached after first access.

        Returns:
            GitPython Repo object for the repository.

        Raises:
            NotGitRepositoryError: If the path is not within a Git repository.

        Note:
            This is a private method. Use the public methods like
            list_remotes() or parse_repository() instead.
        """
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            except InvalidGitRepositoryError as e:
                raise NotGitRepositoryError(str(self.repo_path)) from e

        return self._repo

    def list_remotes(self) -> list[GitRemote]:
        """List all configured Git remotes.

        Returns all remotes configured in the repository with their
        names, URLs, and detected URL types (ssh/https).

        Returns:
            List of GitRemote objects containing name, URL, and URL type.

        Raises:
            NotGitRepositoryError: If not within a Git repository.

        Example:
            >>> discovery = GitDiscovery()
            >>> remotes = discovery.list_remotes()
            >>> for remote in remotes:
            ...     print(f"{remote.name}: {remote.url} ({remote.url_type})")
            origin: git@github.com:owner/repo.git (ssh)
            upstream: https://github.com/original/repo.git (https)
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
        """Get a Git remote by name or using automatic selection.

        Retrieves a Git remote. If no specific name is provided, uses
        intelligent selection based on preference order and repository
        configuration.

        Selection logic (when remote_name is None):
            1. If only one remote exists, use it
            2. If multiple remotes exist, prefer 'origin' then 'upstream'
            3. If no preferred remote found and allow_multiple is False, raise error

        Args:
            remote_name: Specific remote name to retrieve (optional).
            allow_multiple: If True, return first remote when multiple exist
                and none match preferred names. If False (default), raise
                MultipleRemotesError in this situation.

        Returns:
            The selected GitRemote object.

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.
            MultipleRemotesError: If multiple remotes exist, none are preferred,
                and allow_multiple is False.
            ValueError: If the specified remote_name doesn't exist.

        Example:
            >>> discovery = GitDiscovery()
            >>>
            >>> # Get default remote (usually 'origin')
            >>> remote = discovery.get_remote()
            >>> print(remote.name)
            origin
            >>>
            >>> # Get specific remote
            >>> remote = discovery.get_remote("upstream")
            >>> print(remote.url)
        """
        remotes = self.list_remotes()

        if not remotes:
            raise NoRemotesError()

        # If specific remote requested, find it
        if remote_name:
            for remote in remotes:
                if remote.name == remote_name:
                    return remote
            raise ValueError(f"Remote '{remote_name}' not found. Available: {', '.join(r.name for r in remotes)}")

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
        """Get information about all remotes with a suggested default.

        Returns information about all configured remotes along with a
        suggestion for which one to use based on naming conventions.

        Suggestion priority:
            1. 'origin' if present
            2. 'upstream' if present
            3. First remote in list

        Returns:
            MultipleRemotesInfo containing all remotes and the suggested one.

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.

        Example:
            >>> discovery = GitDiscovery()
            >>> info = discovery.get_multiple_remotes_info()
            >>> print(f"Available remotes: {info.remote_names}")
            Available remotes: ['origin', 'upstream', 'fork']
            >>> print(f"Suggested: {info.suggested.name}")
            Suggested: origin
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

    def parse_repository(self, remote_name: str | None = None, allow_multiple: bool = False) -> RepositoryInfo:
        """Parse complete repository information from a Git remote.

        Extracts comprehensive repository information from a Git remote URL,
        including owner, repo name, base URL, and both SSH and HTTPS clone URLs.

        Args:
            remote_name: Specific remote name (optional). If None, uses
                automatic remote selection.
            allow_multiple: If True, allow selection when multiple remotes
                exist without a preferred one.

        Returns:
            RepositoryInfo containing parsed repository details.

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.
            MultipleRemotesError: If multiple remotes and none specified/preferred.
            InvalidGitUrlError: If the remote URL format is invalid.

        Example:
            >>> discovery = GitDiscovery()
            >>> info = discovery.parse_repository()
            >>> print(f"Full name: {info.full_name}")
            Full name: owner/repo
            >>> print(f"Base URL: {info.base_url}")
            Base URL: https://github.com
            >>> print(f"SSH URL: {info.ssh_url}")
            SSH URL: git@github.com:owner/repo.git
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

    def detect_provider_type(self, remote_name: str | None = None) -> Literal["github", "gitlab", "gitea"]:
        """Detect the Git provider type from the remote URL.

        Analyzes the remote URL to determine whether it points to GitHub,
        GitLab, or Gitea (including self-hosted instances).

        Detection rules:
            1. GitHub: URL contains 'github.com' or GitHub Enterprise patterns
            2. GitLab: URL contains 'gitlab.com' or 'gitlab' in hostname
            3. Gitea: Everything else (default for self-hosted)

        Args:
            remote_name: Specific remote name (optional). If None, uses
                automatic remote selection with allow_multiple=True.

        Returns:
            Provider type string: "github", "gitlab", or "gitea".

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.

        Example:
            >>> discovery = GitDiscovery("/path/to/github-repo")
            >>> print(discovery.detect_provider_type())
            github

            >>> discovery = GitDiscovery("/path/to/gitea-repo")
            >>> print(discovery.detect_provider_type())
            gitea
        """
        remote = self.get_remote(remote_name, allow_multiple=True)
        url_lower = remote.url.lower()

        # Check for GitHub
        if "github.com" in url_lower:
            return "github"

        # Check for GitHub Enterprise (common patterns)
        if "github" in url_lower and ("enterprise" in url_lower or "ghe" in url_lower):
            return "github"

        # Check for GitLab
        if "gitlab.com" in url_lower:
            return "gitlab"

        # Check for self-hosted GitLab (gitlab in hostname)
        if "gitlab" in url_lower:
            return "gitlab"

        # Default to Gitea (self-hosted)
        return "gitea"

    def detect_git_config(self, remote_name: str | None = None) -> dict[str, str]:
        """Detect Git provider configuration for config file generation.

        Analyzes the repository and returns a dictionary suitable for
        generating configuration files. Automatically detects the provider
        type and constructs appropriate API URLs.

        Args:
            remote_name: Specific remote name (optional).

        Returns:
            Dictionary containing:
                - provider_type: "github", "gitlab", or "gitea"
                - base_url: Provider API URL (e.g., "https://api.github.com")
                - owner: Repository owner/organization
                - repo: Repository name

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.
            MultipleRemotesError: If multiple remotes and none specified.
            InvalidGitUrlError: If URL format is invalid.

        Example:
            >>> discovery = GitDiscovery()
            >>> config = discovery.detect_git_config()
            >>> print(config)
            {
                'provider_type': 'github',
                'base_url': 'https://api.github.com',
                'owner': 'myorg',
                'repo': 'myrepo'
            }

        Note:
            For GitHub, the base_url is set to 'https://api.github.com'
            rather than 'https://github.com' for direct API usage.
        """
        info = self.parse_repository(remote_name, allow_multiple=False)
        provider_type = self.detect_provider_type(remote_name)

        # Determine API URL based on provider type
        base_url = str(info.base_url)
        if provider_type == "github" and base_url == "https://github.com":
            # GitHub uses api.github.com for API calls
            api_url = "https://api.github.com"
        elif provider_type == "gitlab":
            # GitLab uses same base URL (API path /api/v4 is added by provider)
            api_url = base_url
        else:
            api_url = base_url

        return {
            "provider_type": provider_type,
            "base_url": api_url,
            "owner": info.owner,
            "repo": info.repo,
        }

    def detect_gitea_config(self, remote_name: str | None = None) -> dict[str, str]:
        """Detect Gitea-specific configuration.

        Legacy method for backwards compatibility. Returns configuration
        suitable for Gitea repositories.

        Args:
            remote_name: Specific remote name (optional).

        Returns:
            Dictionary containing:
                - base_url: Gitea instance URL
                - owner: Repository owner
                - repo: Repository name

        Raises:
            NotGitRepositoryError: If not within a Git repository.
            NoRemotesError: If no remotes are configured.
            MultipleRemotesError: If multiple remotes and none specified.
            InvalidGitUrlError: If URL format is invalid.

        Example:
            >>> discovery = GitDiscovery()
            >>> config = discovery.detect_gitea_config()
            >>> print(config)
            {
                'base_url': 'https://gitea.example.com',
                'owner': 'myorg',
                'repo': 'myrepo'
            }

        Note:
            For new code, prefer detect_git_config() which handles
            multiple provider types.
        """
        info = self.parse_repository(remote_name, allow_multiple=False)

        return {
            "base_url": str(info.base_url),
            "owner": info.owner,
            "repo": info.repo,
        }


def detect_git_origin(repo_path: str | Path = ".") -> str | None:
    """Quick helper to detect the Git origin base URL.

    Convenience function that attempts to detect the base URL of a Git
    repository. Returns None on any error, making it suitable for
    graceful fallback scenarios.

    Args:
        repo_path: Path to repository (default: current directory).

    Returns:
        Base URL (e.g., "https://github.com") or None if detection fails.

    Example:
        >>> from repo_sapiens.git.discovery import detect_git_origin
        >>> base_url = detect_git_origin()
        >>> if base_url:
        ...     print(f"Detected: {base_url}")
        ... else:
        ...     print("No Git remote found")
        Detected: https://github.com

        >>> # Works from any path in the repo
        >>> base_url = detect_git_origin("/path/to/repo/src/module")

    Note:
        This function swallows all exceptions and returns None on failure.
        For detailed error handling, use GitDiscovery directly.
    """
    try:
        discovery = GitDiscovery(repo_path)
        info = discovery.parse_repository(allow_multiple=True)
        return str(info.base_url)
    except Exception:
        return None
