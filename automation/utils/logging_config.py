"""
Logging configuration using structlog for structured, JSON-based logging.

This module provides centralized logging setup for the entire automation system,
with support for contextual logging and structured output.
"""

from typing import Any

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with JSON output.

    Sets up structlog with a pipeline of processors for rich, structured logs
    that include timestamps, log levels, stack traces, and contextual information.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance.

    Args:
        name: Optional logger name (typically __name__ from calling module)

    Returns:
        A structlog logger instance

    Example:
        >>> log = get_logger(__name__)
        >>> log.info("operation_started", issue_id=42, stage="planning")
        >>> log.error("operation_failed", error=str(e), exc_info=True)
    """
    return structlog.get_logger(name)
