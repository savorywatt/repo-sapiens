"""CLI commands for repo-sapiens automation system.

This package provides the command-line interface for the automation system,
including initialization, credential management, and workflow commands.

Key Commands:
    - init: Initialize configuration for a repository
    - credentials: Manage secure credential storage
"""

from repo_sapiens.cli.credentials import credentials_group
from repo_sapiens.cli.init import init_command
from repo_sapiens.cli.update import update_command

__all__ = ["credentials_group", "init_command", "update_command"]
