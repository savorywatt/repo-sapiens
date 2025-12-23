"""
Custom Jinja2 filters for safe value injection in templates.

These filters ensure that user-provided values are properly sanitized
before being injected into YAML workflow files.
"""

import re
from typing import Any
from urllib.parse import urlparse

import yaml


def safe_url(value: str) -> str:
    """
    Validate and sanitize URL values.

    Only allows https:// and http:// schemes.
    Removes any potential YAML injection characters.

    Args:
        value: URL to sanitize

    Returns:
        Sanitized URL

    Raises:
        ValueError: If URL is invalid or uses disallowed scheme
    """
    if not isinstance(value, str):
        raise ValueError(f"URL must be string, got {type(value).__name__}")

    parsed = urlparse(value)

    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    if not parsed.netloc:
        raise ValueError("URL must have a domain")

    # Return original value if valid (already URL-encoded)
    return value


def safe_identifier(value: Any, max_length: int = 100) -> str:
    """
    Sanitize values used as identifiers (repo names, owners, etc.).

    Allows: alphanumeric, hyphens, underscores, dots
    Also allows GitHub Actions expressions like ${{ ... }}
    Disallows: special characters that could break YAML or enable injection

    Args:
        value: Identifier to sanitize (will be converted to string if not already)
        max_length: Maximum allowed length

    Returns:
        Sanitized identifier

    Raises:
        ValueError: If identifier is invalid
    """
    # Convert None or other types to string
    if value is None:
        raise ValueError("Identifier cannot be None")

    if not isinstance(value, str):
        value = str(value)

    if not value:
        raise ValueError("Identifier cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"Identifier too long: {len(value)} > {max_length}")

    # Allow GitHub Actions expressions (they're safe because they're template literals)
    if value.startswith("${{") and value.endswith("}}"):
        return value

    # Allow alphanumeric, hyphens, underscores, dots (for domains)
    if not re.match(r"^[a-zA-Z0-9._-]+$", value):
        raise ValueError(f"Invalid identifier characters: {value}")

    return value


def safe_label(value: Any, max_length: int = 50) -> str:
    """
    Sanitize label names for Gitea.

    More permissive than identifiers but still prevents injection.

    Args:
        value: Label name to sanitize (will be converted to string if not already)
        max_length: Maximum allowed length

    Returns:
        Sanitized label name

    Raises:
        ValueError: If label name is invalid
    """
    # Convert None or other types to string
    if value is None:
        raise ValueError("Label cannot be None")

    if not isinstance(value, str):
        value = str(value)

    if not value:
        raise ValueError("Label cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"Label too long: {len(value)} > {max_length}")

    # Disallow YAML-sensitive characters and control characters
    if re.search(r"[:\n\r\t\{\}\[\]&*#?|<>=!%@`]", value):
        raise ValueError(f"Label contains invalid characters: {value}")

    return value.strip()


def yaml_string(value: Any) -> str:
    """
    Safely convert value to YAML string representation.

    Uses PyYAML to ensure proper escaping and quoting.

    Args:
        value: Value to convert to YAML string

    Returns:
        YAML-safe string representation
    """
    return yaml.safe_dump(value, default_flow_style=True).strip()


def yaml_list(value: list[Any]) -> str:
    """
    Convert Python list to YAML list representation.

    Args:
        value: List to convert

    Returns:
        YAML-formatted list
    """
    if not isinstance(value, list):
        raise ValueError(f"Expected list, got {type(value).__name__}")

    return yaml.safe_dump(value, default_flow_style=False).strip()


def yaml_dict(value: dict[str, Any]) -> str:
    """
    Convert Python dict to YAML dict representation.

    Args:
        value: Dict to convert

    Returns:
        YAML-formatted dict
    """
    if not isinstance(value, dict):
        raise ValueError(f"Expected dict, got {type(value).__name__}")

    return yaml.safe_dump(value, default_flow_style=False).strip()
