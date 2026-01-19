"""CLI commands for repo-sapiens automation system.

This package provides the command-line interface for the automation system,
including initialization, credential management, health checking, and
workflow commands.

The CLI is built using Click and follows a hierarchical command structure
with the main entry point ``sapiens``. Commands can be accessed either
directly or through command groups.

Key Commands:
    init (repo_sapiens.cli.init):
        Interactive setup wizard for initializing repo-sapiens in a Git
        repository. Handles provider detection, credential collection,
        agent configuration, and workflow deployment.

    credentials (repo_sapiens.cli.credentials):
        Command group for managing secure credential storage. Supports
        keyring (OS-level), environment variables, and encrypted file
        backends.

    health-check (repo_sapiens.cli.health):
        Validates configuration and tests connectivity to git providers
        and AI agents. Supports comprehensive validation with test
        resource creation (--full flag).

    update (repo_sapiens.cli.update):
        Updates existing configuration or workflow templates.

Usage Examples:
    Initialize a repository::

        $ sapiens init

    Check configuration health::

        $ sapiens health-check --verbose

    Store credentials::

        $ sapiens credentials set gitea/api_token --backend keyring

    Run a task with the agent::

        $ sapiens task "Review this PR and suggest improvements"

Module Structure:
    - init.py: Repository initialization wizard (RepoInitializer class)
    - health.py: Health check and validation commands
    - credentials.py: Credential management command group
    - update.py: Configuration and template update commands
"""

from repo_sapiens.cli.credentials import credentials_group
from repo_sapiens.cli.init import init_command
from repo_sapiens.cli.update import update_command

__all__ = ["credentials_group", "init_command", "update_command"]
