"""Structured logging configuration for repo-sapiens using structlog.

This module provides centralized logging setup with support for both human-readable
console output (development) and JSON output (production). It integrates with structlog
for structured logging and stdlib logging for compatibility.
"""

import logging
import logging.config
import re
import sys
from typing import Any, Dict, Optional

import structlog

# Sensitive patterns to redact from logs
SENSITIVE_PATTERNS = [
    # Match API tokens, keys, passwords, and secrets in key=value format
    (re.compile(r'["\']?(?:api[_-]?token|api[_-]?key|password|secret|key)=(?:["\'])?[^"\'\s,}]+', re.IGNORECASE),
     'api_token=***REDACTED***'),
    # Match standalone tokens and passwords (full values that look sensitive)
    (re.compile(r'(^|[\s:])(sk-[a-zA-Z0-9]+|[a-zA-Z0-9\-._~+/]{30,})', re.IGNORECASE),
     r'\1***REDACTED***'),
    # Match bearer tokens
    (re.compile(r'(bearer|token)\s+[a-zA-Z0-9\-._~+/]+', re.IGNORECASE),
     r'\1 ***REDACTED***'),
    # Match connection strings with credentials
    (re.compile(r'(https?://|postgresql://|mysql://)[^:]+:[^@]+@', re.IGNORECASE),
     r'\1***REDACTED***:***REDACTED***@'),
]


def redact_sensitive_data(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive information from log events.

    Args:
        logger: The logger instance
        method_name: The name of the called method
        event_dict: The event dictionary to process

    Returns:
        The event dictionary with sensitive data redacted
    """
    # List of sensitive key names that should always be redacted
    sensitive_keys = {
        'password', 'pwd', 'passwd', 'secret', 'token', 'api_token', 'apitoken',
        'api_key', 'apikey', 'auth', 'authorization', 'bearer', 'key',
        'access_token', 'refresh_token', 'private_key', 'public_key',
    }

    for key, value in event_dict.items():
        # Check if key name suggests sensitive data
        key_lower = key.lower()
        is_sensitive_key = any(pattern in key_lower for pattern in sensitive_keys)

        if isinstance(value, str):
            # If key is sensitive, redact the value
            if is_sensitive_key:
                event_dict[key] = '***REDACTED***'
            else:
                # Otherwise apply pattern matching to the value
                redacted = value
                for pattern, replacement in SENSITIVE_PATTERNS:
                    redacted = pattern.sub(replacement, redacted)
                event_dict[key] = redacted
        elif isinstance(value, dict):
            # Recursively redact nested dictionaries
            event_dict[key] = redact_sensitive_data(logger, method_name, value)
    return event_dict


class StructlogFormatter(logging.Formatter):
    """Custom formatter for structlog integration with stdlib logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a logging record.

        Args:
            record: The logging record to format

        Returns:
            The formatted log message
        """
        if hasattr(record, '_structlog'):
            # If this is from structlog, it already has formatting
            return record.getMessage()
        return super().format(record)


def configure_logging(
    level: str = "INFO",
    json_logs: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Configure structured logging for repo-sapiens.

    Sets up both structlog and stdlib logging to work together. Supports both
    human-readable console output (development) and JSON output (production).

    Args:
        level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to INFO.
        json_logs: If True, output logs as JSON (for production). If False, use
                  human-readable format. Defaults to False.
        context: Additional context dictionary to include in all log messages.
                Defaults to None.

    Raises:
        ValueError: If an invalid logging level is provided.

    Example:
        >>> configure_logging(level="DEBUG", json_logs=False)
        >>> logger = structlog.get_logger()
        >>> logger.info("action", issue_id=42, repository="owner/repo")
    """
    # Validate log level
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    if level.upper() not in valid_levels:
        raise ValueError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(valid_levels)}"
        )

    log_level_int = getattr(logging, level.upper())

    # Processors for structlog - ordered list
    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,  # Redact sensitive data before rendering
    ]

    # Add output renderer
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development-friendly console output
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(),
                exception_formatter=structlog.dev.better_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to work with structlog
    stdlib_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'plain': {
                'format': '%(message)s',
            },
            'standard': {
                '()': StructlogFormatter,
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'default': {
                'level': level.upper(),
                'class': 'logging.StreamHandler',
                'formatter': 'plain',
                'stream': 'ext://sys.stderr',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': level.upper(),
                'propagate': True,
            },
            'repo_sapiens': {
                'handlers': ['default'],
                'level': level.upper(),
                'propagate': False,
            },
        },
    }

    logging.config.dictConfig(stdlib_config)
    logging.getLogger().setLevel(log_level_int)

    # Store context if provided
    if context:
        structlog.contextvars.clear_contextvars()
        for key, value in context.items():
            structlog.contextvars.bind_contextvars(**{key: value})


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Optional logger name. If not provided, uses the caller's module name.

    Returns:
        A structlog logger instance bound to the given name.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_started", task_id="task-001")
    """
    if name is None:
        # Get the caller's module name
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals['__name__']
        else:
            name = '__main__'

    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to all subsequent log messages.

    Context variables are thread-safe when using contextvars (Python 3.7+).

    Args:
        **kwargs: Key-value pairs to add to the logging context.

    Example:
        >>> bind_context(request_id="req-123", user_id="user-456")
        >>> logger.info("action_performed")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables.

    Example:
        >>> clear_context()
    """
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """Unbind specific context variables.

    Args:
        *keys: Names of context variables to remove.

    Example:
        >>> unbind_context("request_id", "user_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)
