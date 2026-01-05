"""OS-level keyring backend using system credential stores.

Platform Support:
- Linux: Secret Service API (GNOME Keyring, KWallet)
- macOS: Keychain
- Windows: Windows Credential Locker
"""

import logging
from typing import cast

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

from .exceptions import BackendNotAvailableError, CredentialError

logger = logging.getLogger(__name__)


class KeyringBackend:
    """OS-level credential storage using system keyring.

    This is the recommended backend for developer machines as it:
    - Integrates with OS security features
    - Supports biometric unlock (Touch ID, Windows Hello)
    - Provides automatic encryption
    - Works across terminal sessions

    Example:
        >>> backend = KeyringBackend()
        >>> backend.set('gitea', 'api_token', 'ghp_abc123')
        >>> token = backend.get('gitea', 'api_token')
        >>> backend.delete('gitea', 'api_token')
    """

    @property
    def name(self) -> str:
        """Get backend identifier.

        Returns:
            Backend name constant "keyring"
        """
        return "keyring"

    @property
    def available(self) -> bool:
        """Check if keyring is available.

        Returns False if:
        - keyring package not installed
        - No backend configured (headless systems)
        - Backend fails to initialize
        """
        if not KEYRING_AVAILABLE:
            return False

        try:
            # Test if keyring backend is functional
            keyring.get_keyring()
            return True
        except Exception as e:
            logger.debug(f"Keyring not available: {e}")
            return False

    def get(self, service: str, key: str) -> str | None:
        """Retrieve credential from OS keyring.

        Args:
            service: Service identifier (e.g., 'gitea')
            key: Key within service (e.g., 'api_token')

        Returns:
            Credential value or None if not found

        Raises:
            BackendNotAvailableError: If keyring is not available
            CredentialError: If keyring operation fails
        """
        if not self.available:
            raise BackendNotAvailableError(
                "Keyring backend is not available",
                suggestion="Install keyring: pip install keyring",
            )

        try:
            # Namespace credentials under 'sapiens' to avoid conflicts
            full_service = f"sapiens/{service}"
            credential = cast(str | None, keyring.get_password(full_service, key))

            if credential is not None:
                logger.debug(f"Retrieved credential from keyring: {service}/{key}")

            return credential

        except KeyringError as e:
            raise CredentialError(
                f"Keyring operation failed: {e}", reference=f"@keyring:{service}/{key}"
            ) from e

    def set(self, service: str, key: str, value: str) -> None:
        """Store credential in OS keyring.

        Args:
            service: Service identifier
            key: Key within service
            value: Credential value

        Raises:
            BackendNotAvailableError: If keyring is not available
            CredentialError: If keyring operation fails
        """
        if not self.available:
            raise BackendNotAvailableError(
                "Keyring backend is not available",
                suggestion="Install keyring: pip install keyring",
            )

        if not value:
            raise ValueError("Credential value cannot be empty")

        try:
            full_service = f"sapiens/{service}"
            keyring.set_password(full_service, key, value)
            logger.info(f"Stored credential in keyring: {service}/{key}")

        except KeyringError as e:
            raise CredentialError(
                f"Failed to store credential: {e}", reference=f"@keyring:{service}/{key}"
            ) from e

    def delete(self, service: str, key: str) -> bool:
        """Delete credential from OS keyring.

        Args:
            service: Service identifier
            key: Key within service

        Returns:
            True if deleted, False if not found

        Raises:
            BackendNotAvailableError: If keyring is not available
            CredentialError: If keyring operation fails
        """
        if not self.available:
            raise BackendNotAvailableError("Keyring backend is not available")

        try:
            full_service = f"sapiens/{service}"
            keyring.delete_password(full_service, key)
            logger.info(f"Deleted credential from keyring: {service}/{key}")
            return True

        except PasswordDeleteError:
            # Credential doesn't exist - not an error
            return False

        except KeyringError as e:
            raise CredentialError(
                f"Failed to delete credential: {e}", reference=f"@keyring:{service}/{key}"
            ) from e
