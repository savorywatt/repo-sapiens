"""Git discovery exceptions.

This module defines the exception hierarchy for Git repository discovery and
parsing operations. All exceptions inherit from GitDiscoveryError and include
helpful error messages with hints for resolution.

Example:
    >>> from automation.git.exceptions import NotGitRepositoryError
    >>> raise NotGitRepositoryError("/tmp/not-a-repo")
    Traceback (most recent call last):
        ...
    NotGitRepositoryError: Not a Git repository: /tmp/not-a-repo

    Hint: Run 'git init' or navigate to a Git repository directory.
"""

from typing import TYPE_CHECKING

from automation.exceptions import GitOperationError

if TYPE_CHECKING:
    from automation.git.models import GitRemote


class GitDiscoveryError(GitOperationError):
    """Base exception for Git discovery errors.

    Attributes:
        message: Error message
        hint: Optional hint for resolution
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        """Initialize exception.

        Args:
            message: Error message
            hint: Optional hint for resolution
        """
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        """Format error message with hint.

        Returns:
            Formatted error message with optional hint
        """
        if self.hint:
            return f"{self.message}\n\nHint: {self.hint}"
        return self.message


class NotGitRepositoryError(GitDiscoveryError):
    """Raised when directory is not a Git repository.

    Attributes:
        path: Path to the directory that is not a Git repository
    """

    def __init__(self, path: str) -> None:
        """Initialize exception.

        Args:
            path: Path to the directory
        """
        super().__init__(
            message=f"Not a Git repository: {path}",
            hint="Run 'git init' or navigate to a Git repository directory.",
        )
        self.path = path


class NoRemotesError(GitDiscoveryError):
    """Raised when repository has no remotes configured."""

    def __init__(self) -> None:
        """Initialize exception."""
        super().__init__(
            message="No Git remotes configured in this repository",
            hint="Add a remote with: git remote add origin <url>",
        )


class MultipleRemotesError(GitDiscoveryError):
    """Raised when multiple remotes exist and selection is ambiguous.

    Attributes:
        remotes: List of available remotes
        suggested: Suggested remote to use (if any)
    """

    def __init__(self, remotes: list["GitRemote"], suggested: "GitRemote | None") -> None:
        """Initialize exception.

        Args:
            remotes: List of available remotes
            suggested: Suggested remote to use
        """
        remote_list = ", ".join(f"'{r.name}'" for r in remotes)
        suggestion = f"Use --remote {suggested.name}" if suggested else ""

        super().__init__(
            message=f"Multiple remotes found: {remote_list}",
            hint=f"Specify which remote to use. {suggestion}",
        )
        self.remotes = remotes
        self.suggested = suggested


class InvalidGitUrlError(GitDiscoveryError):
    """Raised when Git URL format is not recognized.

    Attributes:
        url: The invalid URL
    """

    def __init__(self, url: str, reason: str | None = None) -> None:
        """Initialize exception.

        Args:
            url: The invalid URL
            reason: Optional reason for the error
        """
        msg = f"Invalid Git URL format: {url}"
        if reason:
            msg += f" ({reason})"

        super().__init__(
            message=msg,
            hint=(
                "Expected formats:\n"
                "  - git@gitea.com:owner/repo.git\n"
                "  - https://gitea.com/owner/repo.git"
            ),
        )
        self.url = url


class UnsupportedHostError(GitDiscoveryError):
    """Raised when Git host is not Gitea.

    Attributes:
        host: The unsupported host
        url: The full URL
    """

    def __init__(self, host: str, url: str) -> None:
        """Initialize exception.

        Args:
            host: The unsupported host
            url: The full URL
        """
        super().__init__(
            message=f"Unsupported Git host: {host}",
            hint=(f"This tool only supports Gitea repositories.\n" f"Remote URL: {url}"),
        )
        self.host = host
        self.url = url
