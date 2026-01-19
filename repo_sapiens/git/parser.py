"""Git URL parsing utilities.

This module provides parsing functionality for Git URLs in both SSH and HTTPS
formats. It extracts repository information such as host, owner, and repo name,
and can convert between URL formats.

Supported URL formats:
    SSH:
        - git@github.com:owner/repo.git
        - git@github.com:owner/repo
        - user@gitlab.com:group/project.git

    HTTPS:
        - https://github.com/owner/repo.git
        - https://github.com/owner/repo
        - https://gitlab.com:8443/owner/repo.git
        - http://gitea.local/owner/repo.git

Key Exports:
    GitUrlParser: Main class for parsing Git URLs.

Example:
    >>> from repo_sapiens.git.parser import GitUrlParser
    >>> parser = GitUrlParser("git@github.com:owner/repo.git")
    >>> print(f"Owner: {parser.owner}")
    Owner: owner
    >>> print(f"Repo: {parser.repo}")
    Repo: repo
    >>> print(f"Base URL: {parser.base_url}")
    Base URL: https://github.com
    >>> print(f"HTTPS URL: {parser.https_url}")
    HTTPS URL: https://github.com/owner/repo.git

Thread Safety:
    GitUrlParser instances are immutable after initialization and are
    safe for concurrent access from multiple threads.

See Also:
    - repo_sapiens.git.discovery: Repository discovery using URL parsing
    - repo_sapiens.git.exceptions: Custom exceptions for parsing errors
"""

import re
from typing import Literal

from repo_sapiens.git.exceptions import InvalidGitUrlError


class GitUrlParser:
    """Parser for Git URLs in SSH and HTTPS formats.

    Parses Git remote URLs to extract repository information and provides
    properties to access parsed components and generate alternative URL
    formats.

    Supported formats:
        SSH format:
            - git@host:owner/repo.git
            - git@host:owner/repo
            - user@host:path (any user, not just 'git')

        HTTPS format:
            - https://host/owner/repo.git
            - https://host/owner/repo
            - https://host:port/owner/repo.git
            - http://host/owner/repo.git (insecure)

    All properties always return valid values after successful initialization.
    If parsing fails, the constructor raises InvalidGitUrlError.

    Attributes:
        url: Original URL that was parsed.
        url_type: Type of URL detected ('ssh', 'https', or 'unknown').
        host: Hostname of the Git server.
        port: Port number (only for HTTPS with non-standard port, else None).
        owner: Repository owner/organization name.
        repo: Repository name (without .git suffix).
        base_url: Base URL for API access (always HTTPS format).
        ssh_url: SSH clone URL (generated if needed).
        https_url: HTTPS clone URL (generated if needed).

    Example:
        >>> # Parse SSH URL
        >>> parser = GitUrlParser("git@github.com:owner/repo.git")
        >>> parser.url_type
        'ssh'
        >>> parser.host
        'github.com'
        >>> parser.owner
        'owner'
        >>> parser.repo
        'repo'

        >>> # Parse HTTPS URL with port
        >>> parser = GitUrlParser("https://gitea.example.com:3000/myorg/myrepo.git")
        >>> parser.url_type
        'https'
        >>> parser.port
        3000
        >>> parser.base_url
        'https://gitea.example.com:3000'
        >>> parser.ssh_url
        'git@gitea.example.com:myorg/myrepo.git'
    """

    # Regex pattern for SSH format: git@host:path
    # Matches: git@gitea.com:owner/repo.git or user@host:path
    # Requires user@ to avoid matching URLs with colons (like https://...)
    SSH_PATTERN = re.compile(r"^(?P<user>\w+)@(?P<host>[a-zA-Z0-9._-]+):(?P<path>.+?)(?:\.git)?$")

    # Regex pattern for HTTPS format: https://host/path or http://host/path
    # Matches: https://gitea.com/owner/repo.git or https://gitea.com:3000/owner/repo
    HTTPS_PATTERN = re.compile(r"^https?://(?P<host>[a-zA-Z0-9._-]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?$")

    def __init__(self, url: str) -> None:
        """Initialize parser with a Git URL.

        Parses the URL immediately during initialization. If parsing fails,
        raises InvalidGitUrlError with details about the issue.

        Args:
            url: Git URL to parse. Supports SSH and HTTPS formats.
                Leading/trailing whitespace is trimmed automatically.

        Raises:
            InvalidGitUrlError: If URL format is not recognized or is missing
                required components (owner/repo).

        Example:
            >>> # Valid URLs
            >>> parser = GitUrlParser("git@github.com:owner/repo.git")
            >>> parser = GitUrlParser("https://github.com/owner/repo")
            >>> parser = GitUrlParser("  git@host:owner/repo  ")  # Whitespace OK

            >>> # Invalid URLs raise exceptions
            >>> GitUrlParser("not-a-url")
            InvalidGitUrlError: Invalid Git URL 'not-a-url': Must be SSH or HTTPS

            >>> GitUrlParser("https://github.com/owner")  # Missing repo
            InvalidGitUrlError: Invalid Git URL: Path must contain owner/repo
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

        Attempts to parse the URL as SSH format first, then HTTPS.
        Sets internal state on successful parse.

        Raises:
            InvalidGitUrlError: If URL doesn't match SSH or HTTPS format.

        Note:
            This is a private method called by __init__. Do not call directly.
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
            True if successfully parsed as SSH URL, False otherwise.

        Note:
            This is a private method. On success, sets _host, _path, _owner, _repo.
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
            True if successfully parsed as HTTPS URL, False otherwise.

        Note:
            This is a private method. On success, sets _host, _port, _path,
            _owner, _repo.
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
        """Extract owner and repo from the parsed path.

        The path should be in format: owner/repo or owner/repo/...
        For nested paths (e.g., GitLab groups: group/subgroup/repo),
        takes the first two path components as owner and repo.

        Raises:
            InvalidGitUrlError: If path doesn't contain owner/repo.

        Note:
            This is a private method called by _parse_ssh() and _parse_https().
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
        """Get the detected URL type.

        Returns:
            URL type: 'ssh', 'https', or 'unknown'.
            After successful parsing, will always be 'ssh' or 'https'.

        Example:
            >>> GitUrlParser("git@github.com:o/r.git").url_type
            'ssh'
            >>> GitUrlParser("https://github.com/o/r").url_type
            'https'
        """
        return self._url_type

    @property
    def host(self) -> str:
        """Get the hostname of the Git server.

        Returns:
            Hostname string (e.g., 'github.com', 'gitlab.example.com').

        Raises:
            ValueError: If URL has not been successfully parsed (shouldn't
                happen since __init__ raises on failure).

        Example:
            >>> GitUrlParser("git@github.com:o/r.git").host
            'github.com'
        """
        if self._host is None:
            raise ValueError("URL not parsed")
        return self._host

    @property
    def port(self) -> int | None:
        """Get the port number (for HTTPS URLs with non-standard ports).

        Returns:
            Port number if specified in HTTPS URL, None otherwise.
            SSH URLs always return None (SSH port is separate from URL).

        Example:
            >>> GitUrlParser("https://gitea.com:3000/o/r.git").port
            3000
            >>> GitUrlParser("https://github.com/o/r.git").port
            None
            >>> GitUrlParser("git@github.com:o/r.git").port
            None
        """
        return self._port

    @property
    def owner(self) -> str:
        """Get the repository owner/organization name.

        Returns:
            Owner/organization string (first path component).

        Raises:
            ValueError: If URL has not been successfully parsed.

        Example:
            >>> GitUrlParser("git@github.com:myorg/myrepo.git").owner
            'myorg'
        """
        if self._owner is None:
            raise ValueError("URL not parsed")
        return self._owner

    @property
    def repo(self) -> str:
        """Get the repository name.

        Returns:
            Repository name without .git suffix.

        Raises:
            ValueError: If URL has not been successfully parsed.

        Example:
            >>> GitUrlParser("git@github.com:myorg/myrepo.git").repo
            'myrepo'
            >>> GitUrlParser("https://github.com/myorg/myrepo").repo
            'myrepo'
        """
        if self._repo is None:
            raise ValueError("URL not parsed")
        return self._repo

    @property
    def base_url(self) -> str:
        """Get the base URL for API access (always HTTPS).

        Returns the base URL that can be used for API calls. Always returns
        HTTPS format regardless of the original URL type. Includes port
        if specified.

        Returns:
            Base URL like 'https://github.com' or 'https://gitea.com:3000'.

        Raises:
            ValueError: If URL has not been successfully parsed.

        Example:
            >>> GitUrlParser("git@github.com:o/r.git").base_url
            'https://github.com'
            >>> GitUrlParser("https://gitea.com:3000/o/r.git").base_url
            'https://gitea.com:3000'
        """
        if self._host is None:
            raise ValueError("URL not parsed")

        if self._port:
            return f"https://{self._host}:{self._port}"
        return f"https://{self._host}"

    @property
    def ssh_url(self) -> str:
        """Get the SSH clone URL.

        Generates or returns the SSH format clone URL, regardless of the
        original URL format.

        Returns:
            SSH clone URL in format: git@host:owner/repo.git

        Raises:
            ValueError: If URL has not been successfully parsed.

        Example:
            >>> GitUrlParser("https://github.com/o/r").ssh_url
            'git@github.com:o/r.git'
            >>> GitUrlParser("git@github.com:o/r.git").ssh_url
            'git@github.com:o/r.git'

        Note:
            SSH URLs don't include port numbers. If the original URL had
            a port, it won't be included in the SSH URL.
        """
        return f"git@{self.host}:{self.owner}/{self.repo}.git"

    @property
    def https_url(self) -> str:
        """Get the HTTPS clone URL.

        Generates or returns the HTTPS format clone URL, regardless of the
        original URL format. Includes port if the original URL had one.

        Returns:
            HTTPS clone URL in format: https://host/owner/repo.git
            or https://host:port/owner/repo.git

        Raises:
            ValueError: If URL has not been successfully parsed.

        Example:
            >>> GitUrlParser("git@github.com:o/r.git").https_url
            'https://github.com/o/r.git'
            >>> GitUrlParser("https://gitea.com:3000/o/r").https_url
            'https://gitea.com:3000/o/r.git'
        """
        if self._port:
            return f"https://{self.host}:{self._port}/{self.owner}/{self.repo}.git"
        return f"https://{self.host}/{self.owner}/{self.repo}.git"
