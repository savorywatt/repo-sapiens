"""Credential-related exceptions.

This module re-exports credential exceptions from repo_sapiens.exceptions
for backward compatibility. New code should import directly from
repo_sapiens.exceptions.
"""

from repo_sapiens.exceptions import (
    BackendNotAvailableError,
    CredentialError,
    CredentialFormatError,
    CredentialNotFoundError,
    EncryptionError,
)

__all__ = [
    "CredentialError",
    "CredentialNotFoundError",
    "CredentialFormatError",
    "BackendNotAvailableError",
    "EncryptionError",
]
