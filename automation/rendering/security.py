"""
Security utilities for template rendering.

This module provides additional security checks and utilities
beyond Jinja2's built-in sandboxing.
"""

import re
import secrets
from typing import Any

# Dangerous YAML patterns that could enable injection
DANGEROUS_YAML_PATTERNS = [
    r"!!python/",  # Python object deserialization
    r"!!map",  # Arbitrary map construction
    r"!!omap",  # Ordered map construction
    r"!!pairs",  # Pairs construction
    r"!!set",  # Set construction
    r"!!binary",  # Binary data
    r"!!timestamp",  # Timestamp objects
    r"&\w+",  # Anchors (can enable resource exhaustion)
    r"\*\w+",  # Aliases (can enable billion laughs attack)
]


def check_rendered_output(rendered: str) -> None:
    """
    Check rendered output for dangerous patterns.

    This is a defense-in-depth measure to catch injection attempts
    that might bypass input validation.

    Args:
        rendered: Rendered template output

    Raises:
        ValueError: If dangerous patterns are detected
    """
    for pattern in DANGEROUS_YAML_PATTERNS:
        if re.search(pattern, rendered):
            raise ValueError(f"Dangerous YAML pattern detected in output: {pattern}")


def generate_safe_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Useful for generating workflow secrets or identifiers.

    Args:
        length: Length of token in bytes

    Returns:
        Hex-encoded random token
    """
    return secrets.token_hex(length)


def sanitize_log_output(text: str, max_length: int = 1000) -> str:
    """
    Sanitize text for safe logging.

    Prevents log injection and truncates long output.

    Args:
        text: Text to sanitize
        max_length: Maximum length for output

    Returns:
        Sanitized text
    """
    # Remove control characters except newline/tab
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... (truncated)"

    return sanitized


class SecurityAudit:
    """
    Security audit logger for template rendering.

    Tracks suspicious activity and potential security issues.
    """

    def __init__(self) -> None:
        """Initialize security audit logger.

        Creates an empty event log for tracking security-related events
        during template rendering operations.
        """
        self.events: list[dict[str, Any]] = []

    def log_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of event (e.g., "injection_attempt")
            severity: Severity level (low, medium, high, critical)
            message: Human-readable message
            context: Additional context
        """
        self.events.append(
            {
                "type": event_type,
                "severity": severity,
                "message": sanitize_log_output(message),
                "context": context,
            }
        )

    def get_events(self, min_severity: str = "low") -> list[dict[str, Any]]:
        """
        Get logged events above a minimum severity.

        Args:
            min_severity: Minimum severity to include

        Returns:
            List of matching events
        """
        severity_order = ["low", "medium", "high", "critical"]
        min_index = severity_order.index(min_severity)

        return [
            event for event in self.events if severity_order.index(event["severity"]) >= min_index
        ]
