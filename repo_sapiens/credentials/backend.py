"""Abstract backend protocol for credential storage."""

from typing import Protocol


class CredentialBackend(Protocol):
    """Protocol defining the interface for credential storage backends.

    All backends must implement these methods to be compatible
    with the CredentialResolver.
    """

    @property
    def name(self) -> str:
        """Backend identifier (e.g., 'keyring', 'environment')."""
        ...

    @property
    def available(self) -> bool:
        """Check if this backend is available on the current system."""
        ...

    def get(self, service: str, key: str) -> str | None:
        """Retrieve a credential.

        Args:
            service: Service identifier (e.g., 'gitea', 'claude')
            key: Key within the service (e.g., 'api_token')

        Returns:
            Credential value or None if not found

        Raises:
            BackendNotAvailableError: If backend is not available
        """
        ...

    def set(self, service: str, key: str, value: str) -> None:
        """Store a credential.

        Args:
            service: Service identifier
            key: Key within the service
            value: Credential value to store

        Raises:
            BackendNotAvailableError: If backend is not available
        """
        ...

    def delete(self, service: str, key: str) -> bool:
        """Delete a credential.

        Args:
            service: Service identifier
            key: Key within the service

        Returns:
            True if credential was deleted, False if not found

        Raises:
            BackendNotAvailableError: If backend is not available
        """
        ...
