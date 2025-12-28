"""CLI commands for credential management."""

import sys
from pathlib import Path

import click

from automation.credentials import (
    CredentialError,
    CredentialResolver,
    EncryptedFileBackend,
    EnvironmentBackend,
    KeyringBackend,
)


@click.group(name="credentials")
def credentials_group():
    """Manage credentials for the automation system.

    Supports three storage backends:
    - keyring: OS-level credential storage (recommended for workstations)
    - environment: Environment variables (recommended for CI/CD)
    - encrypted: Encrypted file storage (fallback for headless systems)

    Examples:

        # Store a credential in OS keyring
        builder credentials set gitea/api_token --backend keyring

        # Store in environment variable
        builder credentials set GITEA_API_TOKEN --backend environment

        # Store in encrypted file
        builder credentials set gitea/api_token --backend encrypted

        # Test credential resolution
        builder credentials get @keyring:gitea/api_token

        # Delete credential
        builder credentials delete gitea/api_token --backend keyring
    """
    pass


@credentials_group.command(name="set")
@click.argument("reference")
@click.option(
    "--backend",
    type=click.Choice(["keyring", "environment", "encrypted"]),
    required=True,
    help="Storage backend to use",
)
@click.option(
    "--value",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Credential value (will prompt if not provided)",
)
@click.option(
    "--master-password",
    envvar="BUILDER_MASTER_PASSWORD",
    help="Master password for encrypted backend (can use env var)",
)
def set_credential(reference: str, backend: str, value: str, master_password: str | None):
    """Store a credential.

    REFERENCE format depends on backend:
    - keyring/encrypted: service/key (e.g., gitea/api_token)
    - environment: VARIABLE_NAME (e.g., GITEA_API_TOKEN)

    Examples:

        builder credentials set gitea/api_token --backend keyring

        builder credentials set GITEA_TOKEN --backend environment

        builder credentials set claude/api_key --backend encrypted
    """
    try:
        if backend == "keyring":
            _set_keyring(reference, value)
        elif backend == "environment":
            _set_environment(reference, value)
        else:  # encrypted
            _set_encrypted(reference, value, master_password)

        click.echo(click.style("Credential stored successfully", fg="green"))

    except CredentialError as e:
        click.echo(click.style(f"Error: {e.message}", fg="red"), err=True)
        if e.suggestion:
            click.echo(click.style(f"Suggestion: {e.suggestion}", fg="yellow"), err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


@credentials_group.command(name="get")
@click.argument("reference")
@click.option("--show-value", is_flag=True, help="Show full credential value (default: masked)")
@click.option(
    "--master-password",
    envvar="BUILDER_MASTER_PASSWORD",
    help="Master password for encrypted backend",
)
def get_credential(reference: str, show_value: bool, master_password: str | None):
    """Retrieve and display a credential (for testing).

    REFERENCE can be:
    - @keyring:service/key
    - ${VARIABLE_NAME}
    - @encrypted:service/key
    - Direct value

    Examples:

        builder credentials get @keyring:gitea/api_token

        builder credentials get ${GITEA_TOKEN}

        builder credentials get @encrypted:claude/api_key
    """
    try:
        # Create resolver with encrypted backend password if provided
        if master_password:
            resolver = CredentialResolver(
                encrypted_file_path=Path(".builder/credentials.enc"),
                encrypted_master_password=master_password,
            )
        else:
            resolver = CredentialResolver()

        # Resolve credential
        value = resolver.resolve(reference, cache=False)

        # Display (masked by default)
        if show_value:
            click.echo(f"Value: {value}")
        else:
            # Mask the value for security
            if len(value) > 8:
                masked = value[:4] + "*" * (len(value) - 8) + value[-4:]
            else:
                masked = "*" * len(value)

            click.echo(f"Value: {masked}")
            click.echo(click.style("Use --show-value to display full credential", fg="yellow"))

        click.echo(click.style("Credential resolved successfully", fg="green"))

    except CredentialError as e:
        click.echo(click.style(f"Error: {e.message}", fg="red"), err=True)
        if e.suggestion:
            click.echo(click.style(f"Suggestion: {e.suggestion}", fg="yellow"), err=True)
        sys.exit(1)


@credentials_group.command(name="delete")
@click.argument("reference")
@click.option(
    "--backend",
    type=click.Choice(["keyring", "environment", "encrypted"]),
    required=True,
    help="Storage backend to use",
)
@click.option(
    "--master-password",
    envvar="BUILDER_MASTER_PASSWORD",
    help="Master password for encrypted backend",
)
@click.confirmation_option(prompt="Are you sure you want to delete this credential?")
def delete_credential(reference: str, backend: str, master_password: str | None):
    """Delete a credential.

    REFERENCE format depends on backend:
    - keyring/encrypted: service/key (e.g., gitea/api_token)
    - environment: VARIABLE_NAME (e.g., GITEA_API_TOKEN)

    Examples:

        builder credentials delete gitea/api_token --backend keyring

        builder credentials delete GITEA_TOKEN --backend environment

        builder credentials delete claude/api_key --backend encrypted
    """
    try:
        if backend == "keyring":
            deleted = _delete_keyring(reference)
        elif backend == "environment":
            deleted = _delete_environment(reference)
        else:  # encrypted
            deleted = _delete_encrypted(reference, master_password)

        if deleted:
            click.echo(click.style("Credential deleted successfully", fg="green"))
        else:
            click.echo(click.style("Credential not found", fg="yellow"))

    except CredentialError as e:
        click.echo(click.style(f"Error: {e.message}", fg="red"), err=True)
        if e.suggestion:
            click.echo(click.style(f"Suggestion: {e.suggestion}", fg="yellow"), err=True)
        sys.exit(1)


@credentials_group.command(name="test")
@click.option(
    "--master-password",
    envvar="BUILDER_MASTER_PASSWORD",
    help="Master password for encrypted backend",
)
def test_credentials(master_password: str | None):
    """Test credential system availability.

    Checks which backends are available and tests basic operations.
    """
    click.echo(click.style("Testing credential backends...", bold=True))
    click.echo()

    # Test keyring backend
    keyring_backend = KeyringBackend()
    click.echo("Keyring backend: ", nl=False)
    if keyring_backend.available:
        click.echo(click.style("Available", fg="green"))
    else:
        click.echo(click.style("Not available", fg="yellow"))
        click.echo("  Install with: pip install keyring")

    # Test environment backend
    _env_backend = EnvironmentBackend()  # Initialized for availability check
    click.echo("Environment backend: ", nl=False)
    click.echo(click.style("Available", fg="green"))

    # Test encrypted backend
    encrypted_backend = EncryptedFileBackend(
        Path(".builder/credentials.enc"), master_password or "test"
    )
    click.echo("Encrypted file backend: ", nl=False)
    if encrypted_backend.available:
        click.echo(click.style("Available", fg="green"))
    else:
        click.echo(click.style("Not available", fg="yellow"))
        click.echo("  Install with: pip install cryptography")

    click.echo()
    click.echo(click.style("All tests passed", fg="green", bold=True))


# Helper functions


def _parse_service_key(reference: str) -> tuple[str, str]:
    """Parse service/key reference.

    Args:
        reference: Reference in format "service/key"

    Returns:
        Tuple of (service, key)

    Raises:
        ValueError: If format is invalid
    """
    if "/" not in reference:
        raise ValueError(
            f"Invalid reference format: {reference}\n"
            "Expected format: service/key (e.g., gitea/api_token)"
        )

    parts = reference.split("/", 1)
    return parts[0], parts[1]


def _set_keyring(reference: str, value: str) -> None:
    """Store credential in keyring."""
    service, key = _parse_service_key(reference)

    backend = KeyringBackend()
    backend.set(service, key, value)

    click.echo(f"Stored in keyring: {service}/{key}")
    click.echo(f"Reference: @keyring:{service}/{key}")


def _set_environment(var_name: str, value: str) -> None:
    """Store credential in environment."""
    backend = EnvironmentBackend()
    backend.set(var_name, value)

    click.echo(f"Set environment variable: {var_name}")
    click.echo(f"Reference: ${{{var_name}}}")
    click.echo(
        click.style("Note: Environment variables only persist in current session", fg="yellow")
    )


def _set_encrypted(reference: str, value: str, master_password: str | None) -> None:
    """Store credential in encrypted file."""
    service, key = _parse_service_key(reference)

    if not master_password:
        master_password = click.prompt("Master password", hide_input=True, confirmation_prompt=True)

    backend = EncryptedFileBackend(
        file_path=Path(".builder/credentials.enc"), master_password=master_password
    )
    backend.set(service, key, value)

    click.echo(f"Stored in encrypted file: {service}/{key}")
    click.echo(f"Reference: @encrypted:{service}/{key}")


def _delete_keyring(reference: str) -> bool:
    """Delete credential from keyring."""
    service, key = _parse_service_key(reference)

    backend = KeyringBackend()
    return backend.delete(service, key)


def _delete_environment(var_name: str) -> bool:
    """Delete credential from environment."""
    backend = EnvironmentBackend()
    return backend.delete(var_name)


def _delete_encrypted(reference: str, master_password: str | None) -> bool:
    """Delete credential from encrypted file."""
    service, key = _parse_service_key(reference)

    if not master_password:
        master_password = click.prompt("Master password", hide_input=True)

    backend = EncryptedFileBackend(
        file_path=Path(".builder/credentials.enc"), master_password=master_password
    )
    return backend.delete(service, key)
