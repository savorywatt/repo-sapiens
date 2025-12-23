"""Secure credential management for the builder CLI.

This package provides:
- Multiple storage backends (keyring, environment, encrypted file)
- Safe credential resolution with comprehensive error handling
- Type-safe integration with Pydantic configuration
- Cross-platform compatibility

Example usage:

    from automation.credentials import CredentialResolver, KeyringBackend

    # Store a credential
    backend = KeyringBackend()
    backend.set('gitea', 'api_token', 'ghp_abc123')

    # Resolve a credential reference
    resolver = CredentialResolver()
    token = resolver.resolve('@keyring:gitea/api_token')

See the documentation for detailed usage and security considerations.
"""

from .backend import CredentialBackend
from .encrypted_backend import EncryptedFileBackend
from .environment_backend import EnvironmentBackend
from .exceptions import (
    BackendNotAvailableError,
    CredentialError,
    CredentialFormatError,
    CredentialNotFoundError,
    EncryptionError,
)
from .keyring_backend import KeyringBackend
from .resolver import CredentialResolver

__all__ = [
    # Backends
    "CredentialBackend",
    "KeyringBackend",
    "EnvironmentBackend",
    "EncryptedFileBackend",
    # Resolver
    "CredentialResolver",
    # Exceptions
    "CredentialError",
    "CredentialNotFoundError",
    "CredentialFormatError",
    "BackendNotAvailableError",
    "EncryptionError",
]
