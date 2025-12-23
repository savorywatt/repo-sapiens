"""Git repository discovery and parsing.

This module provides functionality to automatically detect Git repository
configuration from local remotes, parse Git URLs, and extract repository
information for use with Gitea automation.

The main entry point is the GitDiscovery class, which can detect repository
information from Git remotes and parse URLs in both SSH and HTTPS formats.

Example:
    >>> from automation.git import GitDiscovery
    >>> discovery = GitDiscovery()
    >>> info = discovery.parse_repository()
    >>> print(f"{info.owner}/{info.repo} @ {info.base_url}")
    owner/repo @ https://gitea.com

Error Handling:
    All exceptions inherit from GitDiscoveryError and include helpful
    error messages and hints for resolution.

    >>> from automation.git import GitDiscovery, NoRemotesError
    >>> try:
    ...     discovery = GitDiscovery()
    ...     info = discovery.parse_repository()
    ... except NoRemotesError as e:
    ...     print(e)
    No Git remotes configured in this repository

    Hint: Add a remote with: git remote add origin <url>
"""

from automation.git.discovery import GitDiscovery, detect_git_origin
from automation.git.exceptions import (
    GitDiscoveryError,
    InvalidGitUrlError,
    MultipleRemotesError,
    NoRemotesError,
    NotGitRepositoryError,
    UnsupportedHostError,
)
from automation.git.models import GitRemote, MultipleRemotesInfo, RepositoryInfo
from automation.git.parser import GitUrlParser

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
