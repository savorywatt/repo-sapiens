"""Custom exception hierarchy for repo-sapiens automation system.

This module defines a structured exception hierarchy that enables
precise error handling, better debugging, and user-friendly error messages
throughout the automation system.

Exception Hierarchy:
    RepoSapiensError (base)
    ├── ConfigurationError
    ├── CredentialError
    │   ├── CredentialNotFoundError
    │   ├── CredentialFormatError
    │   ├── BackendNotAvailableError
    │   └── EncryptionError
    ├── GitOperationError
    ├── TemplateError
    ├── WorkflowError
    │   └── TaskExecutionError
    ├── ExternalServiceError
    └── AgentError
        ├── AgentTimeoutError
        ├── AgentContextError
        ├── AgentToolError
        └── ProviderConnectionError

Example Usage:
    >>> from repo_sapiens.exceptions import ConfigurationError
    >>> try:
    ...     load_config(path)
    ... except FileNotFoundError as e:
    ...     raise ConfigurationError(f"Config file not found: {path}") from e
"""

from typing import Any


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

    This is the base class for credential-specific errors. Subclasses:
    - CredentialNotFoundError: Credential reference doesn't exist
    - CredentialFormatError: Invalid credential reference format
    - BackendNotAvailableError: Storage backend unavailable
    - EncryptionError: Encryption/decryption failed

    Attributes:
        message: Human-readable error description
        reference: The credential reference that failed (e.g., "@keyring:service/key")
        suggestion: Optional suggestion for resolution

    Examples:
        - Credential not found in storage backend
        - Invalid credential reference format
        - Keyring/encryption system unavailable
        - Failed to decrypt credential
    """

    def __init__(
        self,
        message: str,
        reference: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            reference: The credential reference that failed
            suggestion: Optional suggestion for resolution
        """
        self.reference = reference
        self.suggestion = suggestion

        full_message = message
        if reference:
            full_message = f"{message} (reference: {reference})"
        if suggestion:
            full_message = f"{full_message}\nSuggestion: {suggestion}"

        super().__init__(full_message)
        # Preserve original message (super sets self.message to full_message)
        self.message = message


class CredentialNotFoundError(CredentialError):
    """Credential exists in config but not in storage backend."""

    pass


class CredentialFormatError(CredentialError):
    """Credential reference has invalid format."""

    pass


class BackendNotAvailableError(CredentialError):
    """Requested backend is not available on this system."""

    pass


class EncryptionError(CredentialError):
    """Encryption or decryption operation failed."""

    pass


class GitOperationError(RepoSapiensError):
    """Git operation errors.

    Raised when Git operations fail (clone, fetch, commit, push, etc.)
    or repository state is invalid.

    This is the base class for Git-specific errors. See the
    repo_sapiens.git.exceptions module for more specific error types:
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


# =============================================================================
# Agent Errors
# =============================================================================


class AgentError(RepoSapiensError):
    """Base exception for agent execution errors.

    Raised when LLM agent operations fail (connection, execution, timeouts, etc.).

    This is the base class for agent-specific errors. Subclasses:
    - AgentTimeoutError: Agent took too long to respond
    - AgentContextError: Context/conversation issues
    - AgentToolError: Tool execution failures
    - ProviderConnectionError: Can't connect to LLM provider

    Attributes:
        message: Human-readable error description
        agent_type: Type of agent (e.g., "ollama", "openai", "claude")
        task_id: Optional task ID being executed when error occurred

    Examples:
        - Ollama server not running
        - OpenAI API returned an error
        - Agent execution timed out
        - Tool execution failed
    """

    def __init__(
        self,
        message: str,
        agent_type: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            agent_type: Type of agent that failed
            task_id: Task ID being executed when error occurred
        """
        self.agent_type = agent_type
        self.task_id = task_id

        parts = [message]
        if agent_type:
            parts.append(f"agent: {agent_type}")
        if task_id:
            parts.append(f"task: {task_id}")

        full_message = message if len(parts) == 1 else f"{message} ({', '.join(parts[1:])})"
        super().__init__(full_message)
        # Preserve original message
        self.message = message


class AgentTimeoutError(AgentError):
    """Agent took too long to respond.

    Raised when an agent operation exceeds the configured timeout.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
        agent_type: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            timeout_seconds: The timeout that was exceeded
            agent_type: Type of agent that timed out
            task_id: Task ID being executed when timeout occurred
        """
        self.timeout_seconds = timeout_seconds
        if timeout_seconds and "timeout" not in message.lower():
            message = f"{message} (timeout: {timeout_seconds}s)"
        super().__init__(message, agent_type=agent_type, task_id=task_id)


class AgentContextError(AgentError):
    """Context or conversation issues with the agent.

    Raised when there are problems with the agent's context window,
    conversation history, or memory management.

    Examples:
        - Context window exceeded
        - Invalid conversation history
        - Memory retrieval failed
    """

    pass


class AgentToolError(AgentError):
    """Tool execution failed within the agent.

    Raised when a tool invoked by the agent fails to execute properly.

    Attributes:
        tool_name: Name of the tool that failed
        tool_args: Arguments passed to the tool (for debugging)
    """

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        agent_type: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            tool_name: Name of the tool that failed
            tool_args: Arguments passed to the tool
            agent_type: Type of agent executing the tool
            task_id: Task ID being executed when tool failed
        """
        self.tool_name = tool_name
        self.tool_args = tool_args
        if tool_name and "tool" not in message.lower():
            message = f"Tool '{tool_name}' failed: {message}"
        super().__init__(message, agent_type=agent_type, task_id=task_id)


class ProviderConnectionError(AgentError):
    """Cannot connect to the LLM provider.

    Raised when the agent cannot establish a connection to the LLM
    backend server (Ollama, OpenAI, vLLM, etc.).

    Attributes:
        provider_url: URL of the provider that couldn't be reached
        suggestion: Helpful suggestion for resolving the issue
    """

    def __init__(
        self,
        message: str,
        provider_url: str | None = None,
        suggestion: str | None = None,
        agent_type: str | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            provider_url: URL of the unreachable provider
            suggestion: Suggestion for resolving the issue
            agent_type: Type of agent/provider
        """
        self.provider_url = provider_url
        self.suggestion = suggestion

        full_message = message
        if provider_url:
            full_message = f"{message} (url: {provider_url})"
        if suggestion:
            full_message = f"{full_message}\nSuggestion: {suggestion}"

        # Call grandparent __init__ to avoid double-formatting
        RepoSapiensError.__init__(self, full_message)
        self.agent_type = agent_type
        self.task_id = None
        self.message = message


# =============================================================================
# Task Execution Errors
# =============================================================================


class TaskExecutionError(WorkflowError):
    """Task execution failed in a workflow stage.

    Raised when a specific task within a workflow fails to execute.

    Attributes:
        task_id: Identifier of the failed task
        stage: Workflow stage where failure occurred
        recoverable: Whether the error can be recovered from
    """

    def __init__(
        self,
        message: str,
        task_id: str | None = None,
        stage: str | None = None,
        recoverable: bool = True,
    ) -> None:
        """Initialize exception.

        Args:
            message: Error message
            task_id: Identifier of the failed task
            stage: Workflow stage where failure occurred
            recoverable: Whether the error can potentially be recovered
        """
        self.task_id = task_id
        self.stage = stage
        self.recoverable = recoverable

        parts = [message]
        if task_id:
            parts.append(f"task: {task_id}")
        if stage:
            parts.append(f"stage: {stage}")

        full_message = message if len(parts) == 1 else f"{message} ({', '.join(parts[1:])})"
        super().__init__(full_message)
        # Preserve original message
        self.message = message
