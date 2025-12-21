"""Helper utility functions."""

import re
from typing import Any, Dict


def slugify(text: str) -> str:
    """Convert text to URL-safe slug.

    Args:
        text: Text to convert

    Returns:
        Slugified text (lowercase, alphanumeric with hyphens)

    Example:
        >>> slugify("Hello World! 123")
        'hello-world-123'
    """
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    # Replace multiple hyphens with single hyphen
    text = re.sub(r"-+", "-", text)
    return text


def parse_issue_reference(text: str) -> Dict[str, Any]:
    """Parse issue reference from text (e.g., '#42' or 'issue-42').

    Args:
        text: Text containing issue reference

    Returns:
        Dictionary with parsed info or empty dict

    Example:
        >>> parse_issue_reference("Fixes #42")
        {'issue_number': 42}
    """
    # Match #42 or issue-42 or issue 42
    patterns = [
        r"#(\d+)",
        r"issue[- ](\d+)",
        r"Issue[- ](\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {"issue_number": int(match.group(1))}

    return {}


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix
