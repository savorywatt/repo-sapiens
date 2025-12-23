"""repo-sapiens: Intelligent repository automation and management tool.

A comprehensive Python package for automating repository workflows with
structured logging, git integration, and intelligent task management.
"""

__version__ = "0.0.2"
__author__ = "savorywatt"
__email__ = "maintainer@savorywatt.com"

from .core import get_greeting, greet
from .logging_config import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    unbind_context,
)

__all__ = [
    "greet",
    "get_greeting",
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "unbind_context",
    "__version__",
]
