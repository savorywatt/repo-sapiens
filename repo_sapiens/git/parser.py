"""Git URL parsing utilities.

This module provides parsing functionality for Git URLs in both SSH and HTTPS
formats. It extracts repository information such as host, owner, and repo name,
and can convert between URL formats.

Example:
    >>> from repo_sapiens.git.parser import GitUrlParser
    >>> parser = GitUrlParser("git@gitea.com:owner/repo.git")
    >>> parser.owner
    'owner'
    >>> parser.repo
    'repo'
    >>> parser.base_url
    'https://gitea.com'
    >>> parser.https_url
    'https://gitea.com/owner/repo.git'
"""

import re
from typing import Literal

from repo_sapiens.git.exceptions import InvalidGitUrlError


class GitUrlParser:
    """Parser for Git URLs in SSH and HTTPS formats.

    This class parses Git URLs and extracts repository information including
    host, owner, repo, and can generate both SSH and HTTPS clone URLs.

    Supported formats:
        - SSH: git@gitea.com:owner/repo.git
        - SSH without .git: git@gitea.com:owner/repo
        - HTTPS: https://gitea.com/owner/repo.git
        - HTTPS with port: https://gitea.com:3000/owner/repo.git
        - HTTP (insecure): http://gitea.local/owner/repo.git

    Attributes:
        url: Original URL that was parsed
        url_type: Type of URL (ssh, https, or unknown)
        host: Hostname of the Git server
        port: Port number (only for HTTPS URLs with non-standard port)
        owner: Repository owner/organization
        repo: Repository name
        base_url: Base URL for API access (always HTTPS)
        ssh_url: SSH clone URL
        https_url: HTTPS clone URL

    Example:
        >>> parser = GitUrlParser("https://gitea.com:3000/owner/repo.git")
        >>> parser.url_type
        'https'
        >>> parser.host
        'gitea.com'
        >>> parser.port
        3000
        >>> parser.owner
        'owner'
        >>> parser.repo
        'repo'
        >>> parser.base_url
        'https://gitea.com:3000'
    """

    # Regex pattern for SSH format: git@host:path
    # Matches: git@gitea.com:owner/repo.git or user@host:path
    # Requires user@ to avoid matching URLs with colons (like https://...)
    SSH_PATTERN = re.compile(r"^(?P<user>\w+)@(?P<host>[a-zA-Z0-9._-]+):(?P<path>.+?)(?:\.git)?$")

    # Regex pattern for HTTPS format: https://host/path or http://host/path
    # Matches: https://gitea.com/owner/repo.git or https://gitea.com:3000/owner/repo
    HTTPS_PATTERN = re.compile(
        r"^https?://(?P<host>[a-zA-Z0-9._-]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?$"
    )

    def __init__(self, url: str) -> None:
        """Initialize parser.

        Args:
            url: Git URL to parse

        Raises:
            InvalidGitUrlError: If URL format is not recognized
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
        """Parse the Git URL.

        Raises:
            InvalidGitUrlError: If URL doesn't match SSH or HTTPS format
        """
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
            reason="Must be SSH (git@host:path) or HTTPS (https://host/path)",
        )

    def _parse_ssh(self) -> bool:
        """Parse SSH format: git@gitea.com:owner/repo.git

        Returns:
            True if successfully parsed, False otherwise
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
            True if successfully parsed, False otherwise
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

        The path should be in the format: owner/repo or owner/repo/...
        For nested paths (e.g., group/subgroup/repo), we take the first
        two components as owner and repo.

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
            raise InvalidGitUrlError(self.url, reason=f"Path must contain owner/repo (got: {path})")

        self._owner = parts[0]
        self._repo = parts[1]

        if not self._owner or not self._repo:
            raise InvalidGitUrlError(self.url, reason="Owner and repo must not be empty")

    @property
    def url_type(self) -> Literal["ssh", "https", "unknown"]:
        """Return URL type.

        Returns:
            URL type: 'ssh', 'https', or 'unknown'
        """
        return self._url_type

    @property
    def host(self) -> str:
        """Return hostname.

        Returns:
            Hostname of the Git server

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        if self._host is None:
            raise ValueError("URL not parsed")
        return self._host

    @property
    def port(self) -> int | None:
        """Return port (only for HTTPS URLs with non-standard port).

        Returns:
            Port number or None if standard port
        """
        return self._port

    @property
    def owner(self) -> str:
        """Return repository owner.

        Returns:
            Repository owner/organization name

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        if self._owner is None:
            raise ValueError("URL not parsed")
        return self._owner

    @property
    def repo(self) -> str:
        """Return repository name.

        Returns:
            Repository name (without .git suffix)

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        if self._repo is None:
            raise ValueError("URL not parsed")
        return self._repo

    @property
    def base_url(self) -> str:
        """Return base URL for API access (always HTTPS).

        This returns the base URL that can be used for API calls,
        always in HTTPS format regardless of the original URL type.

        Returns:
            Base URL like https://gitea.com or https://gitea.com:3000

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        if self._host is None:
            raise ValueError("URL not parsed")

        if self._port:
            return f"https://{self._host}:{self._port}"
        return f"https://{self._host}"

    @property
    def ssh_url(self) -> str:
        """Return SSH clone URL.

        Returns:
            SSH clone URL in format: git@host:owner/repo.git

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        return f"git@{self.host}:{self.owner}/{self.repo}.git"

    @property
    def https_url(self) -> str:
        """Return HTTPS clone URL.

        Returns:
            HTTPS clone URL in format: https://host/owner/repo.git
            or https://host:port/owner/repo.git if port is specified

        Raises:
            ValueError: If URL has not been successfully parsed
        """
        if self._port:
            return f"https://{self.host}:{self._port}/{self.owner}/{self.repo}.git"
        return f"https://{self.host}/{self.owner}/{self.repo}.git"
