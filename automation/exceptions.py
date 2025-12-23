"""Custom exception hierarchy for repo-sapiens automation system.

This module defines a structured exception hierarchy that enables
precise error handling, better debugging, and user-friendly error messages
throughout the automation system.

Exception Hierarchy:
    RepoSapiensError (base)
    ├── ConfigurationError
    ├── CredentialError
    ├── GitOperationError
    ├── TemplateError
    ├── WorkflowError
    └── ExternalServiceError

Example Usage:
    >>> from automation.exceptions import ConfigurationError
    >>> try:
    ...     load_config(path)
    ... except FileNotFoundError as e:
    ...     raise ConfigurationError(f"Config file not found: {path}") from e
"""


class RepoSapiensError(Exception):
    """Base exception for all repo-sapiens errors.

    All custom exceptions in the automation system inherit from this base
    class, allowing callers to catch all repo-sapiens-specific errors with
    a single except clause.

    Attributes:
        message: Human-readable error description
    """

    def __init__(self, message: str) -> None:
        """Initialize exception.

        Args:
            message: Error message
        """
        self.message = message
        super().__init__(message)


class ConfigurationError(RepoSapiensError):
    """Configuration-related errors.

    Raised when configuration files are invalid, missing, or contain
    incompatible settings.

    Examples:
        - Configuration file not found
        - Invalid YAML/JSON syntax
        - Missing required configuration fields
        - Invalid configuration values
    """

    pass


class CredentialError(RepoSapiensError):
    """Credential-related errors.

    Raised when credentials cannot be loaded, resolved, or are invalid.

    This is the base class for credential-specific errors. See the
    automation.credentials.exceptions module for more specific error types:
    - CredentialNotFoundError: Credential reference doesn't exist
    - CredentialFormatError: Invalid credential reference format
    - BackendNotAvailableError: Storage backend unavailable
    - EncryptionError: Encryption/decryption failed

    Examples:
        - Credential not found in storage backend
        - Invalid credential reference format
        - Keyring/encryption system unavailable
        - Failed to decrypt credential
    """

    pass


class GitOperationError(RepoSapiensError):
    """Git operation errors.

    Raised when Git operations fail (clone, fetch, commit, push, etc.)
    or repository state is invalid.

    This is the base class for Git-specific errors. See the
    automation.git.exceptions module for more specific error types:
    - NotGitRepositoryError: Directory is not a Git repository
    - NoRemotesError: No Git remotes configured
    - MultipleRemotesError: Multiple remotes and selection is ambiguous
    - InvalidGitUrlError: Git URL format invalid
    - UnsupportedHostError: Git host is not Gitea

    Examples:
        - Directory is not a Git repository
        - Git command execution failed
        - Remote repository unavailable
        - Invalid Git URL format
    """

    pass


class TemplateError(RepoSapiensError):
    """Template rendering errors.

    Raised when template processing fails (rendering, validation, etc.).

    Examples:
        - Template file not found
        - Invalid template syntax
        - Template rendering failed
        - Missing template variables
        - Template validation failed
    """

    pass


class WorkflowError(RepoSapiensError):
    """Workflow execution errors.

    Raised when workflow execution fails (orchestration, state management, etc.).

    Examples:
        - Workflow validation failed
        - Plan not found
        - Invalid plan structure
        - Workflow step failed
        - State persistence failed
    """

    pass


class ExternalServiceError(RepoSapiensError):
    """External service communication errors.

    Raised when communication with external services fails
    (HTTP errors, API failures, timeouts, etc.).

    Examples:
        - HTTP request failed
        - API returned error
        - Service timeout
        - Network connectivity issue
        - Rate limiting
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            status_code: HTTP status code (if applicable)
            response_text: Response body text (if applicable)
        """
        self.message = message
        self.status_code = status_code
        self.response_text = response_text

        full_message = message
        if status_code:
            full_message = f"{message} (HTTP {status_code})"

        super().__init__(full_message)
