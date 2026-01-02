"""Encrypted file backend using Fernet symmetric encryption.

Security Model:
- Master key derived from user password or stored in keyring
- Credentials encrypted with Fernet (AES-128-CBC + HMAC)
- File stored at .builder/credentials.enc
- Suitable for headless systems without keyring support
"""

import json
import logging
from pathlib import Path
from typing import cast

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import EncryptionError

logger = logging.getLogger(__name__)


class EncryptedFileBackend:
    """Encrypted file-based credential storage.

    This backend provides:
    - Symmetric encryption using Fernet (AES-128)
    - Password-based key derivation (PBKDF2-HMAC-SHA256)
    - Structured JSON storage
    - Atomic file operations

    Security Considerations:
    - Master password must be protected
    - File permissions should be 600 (user read/write only)
    - Not suitable for production systems (use keyring or env vars)
    - Vulnerable if master password is compromised

    Example:
        >>> backend = EncryptedFileBackend(
        ...     file_path=Path(".builder/credentials.enc"),
        ...     master_password="secure-password"
        ... )
        >>> backend.set('gitea', 'api_token', 'ghp_abc123')
        >>> token = backend.get('gitea', 'api_token')
    """

    def __init__(
        self,
        file_path: Path,
        master_password: str | None = None,
        salt: bytes | None = None,
    ) -> None:
        """Initialize encrypted file backend.

        Args:
            file_path: Path to encrypted credentials file
            master_password: Password for encryption (if None, will prompt)
            salt: Cryptographic salt (generated if not provided)
        """
        self.file_path = file_path
        self.salt = salt or self._load_or_generate_salt()

        # Derive encryption key from password
        self.fernet: Fernet | None
        if master_password:
            self.fernet = self._create_fernet(master_password, self.salt)
        else:
            self.fernet = None  # Lazy initialization on first use

        self._credentials_cache: dict[str, dict[str, str]] | None = None

    @property
    def name(self) -> str:
        """Get backend identifier.

        Returns:
            Backend name constant "encrypted_file"
        """
        return "encrypted_file"

    @property
    def available(self) -> bool:
        """Check if cryptography package is available."""
        try:
            # Test import
            from cryptography.fernet import Fernet  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def _create_fernet(password: str, salt: bytes) -> Fernet:
        """Derive encryption key from password.

        Uses PBKDF2-HMAC-SHA256 with 480,000 iterations (OWASP 2023 recommendation).

        Args:
            password: Master password
            salt: Cryptographic salt

        Returns:
            Fernet cipher instance
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=480_000,  # OWASP recommendation for SHA-256
        )
        key = kdf.derive(password.encode("utf-8"))
        # Fernet requires base64-encoded key
        import base64

        return Fernet(base64.urlsafe_b64encode(key))

    def _load_or_generate_salt(self) -> bytes:
        """Load salt from file or generate new one.

        Salt is stored in .builder/credentials.salt

        Returns:
            16-byte cryptographic salt
        """
        salt_file = self.file_path.parent / "credentials.salt"

        if salt_file.exists():
            with open(salt_file, "rb") as f:
                return f.read()

        # Generate new salt
        import secrets

        salt = secrets.token_bytes(16)

        # Ensure directory exists
        salt_file.parent.mkdir(parents=True, exist_ok=True)

        # Write salt
        with open(salt_file, "wb") as f:
            f.write(salt)

        # Restrict permissions (Unix only)
        try:
            salt_file.chmod(0o600)
        except Exception as e:
            logger.warning(f"Could not set salt file permissions: {e}")

        return salt

    def _load_credentials(self) -> dict[str, dict[str, str]]:
        """Load and decrypt credentials from file.

        Returns:
            Dictionary mapping service -> {key -> value}

        Raises:
            EncryptionError: If decryption fails
        """
        if self._credentials_cache is not None:
            return self._credentials_cache

        if not self.file_path.exists():
            self._credentials_cache = {}
            return self._credentials_cache

        if self.fernet is None:
            raise EncryptionError(
                "Master password not provided",
                suggestion="Initialize backend with master_password parameter",
            )

        try:
            # Read encrypted data
            with open(self.file_path, "rb") as f:
                encrypted_data = f.read()

            # Decrypt
            decrypted_data = self.fernet.decrypt(encrypted_data)

            # Parse JSON
            credentials = cast(
                dict[str, dict[str, str]], json.loads(decrypted_data.decode("utf-8"))
            )

            self._credentials_cache = credentials
            return credentials

        except InvalidToken as e:
            raise EncryptionError(
                "Invalid master password or corrupted credentials file",
                suggestion="Verify your master password",
            ) from e
        except json.JSONDecodeError as e:
            raise EncryptionError(
                "Credentials file is corrupted",
                suggestion="Restore from backup or delete and recreate",
            ) from e
        except Exception as e:
            raise EncryptionError(f"Failed to load credentials: {e}") from e

    def _save_credentials(self, credentials: dict[str, dict[str, str]]) -> None:
        """Encrypt and save credentials to file.

        Args:
            credentials: Dictionary mapping service -> {key -> value}

        Raises:
            EncryptionError: If encryption fails
        """
        if self.fernet is None:
            raise EncryptionError("Master password not provided")

        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize to JSON
            json_data = json.dumps(credentials, indent=2)

            # Encrypt
            encrypted_data = self.fernet.encrypt(json_data.encode("utf-8"))

            # Write atomically using temporary file
            temp_file = self.file_path.with_suffix(".tmp")
            with open(temp_file, "wb") as f:
                f.write(encrypted_data)

            # Restrict permissions before moving
            try:
                temp_file.chmod(0o600)
            except Exception as e:
                logger.warning(f"Could not set file permissions: {e}")

            # Atomic rename
            temp_file.replace(self.file_path)

            # Update cache
            self._credentials_cache = credentials

            logger.debug(f"Saved credentials to {self.file_path}")

        except Exception as e:
            raise EncryptionError(f"Failed to save credentials: {e}") from e

    def get(self, service: str, key: str) -> str | None:
        """Retrieve credential from encrypted file.

        Args:
            service: Service identifier (e.g., 'gitea')
            key: Key within service (e.g., 'api_token')

        Returns:
            Credential value or None if not found

        Raises:
            EncryptionError: If decryption fails
        """
        credentials = self._load_credentials()

        service_creds = credentials.get(service, {})
        value = service_creds.get(key)

        if value is not None:
            logger.debug(f"Retrieved credential from encrypted file: {service}/{key}")

        return value

    def set(self, service: str, key: str, value: str) -> None:
        """Store credential in encrypted file.

        Args:
            service: Service identifier
            key: Key within service
            value: Credential value

        Raises:
            EncryptionError: If encryption fails
        """
        if not value:
            raise ValueError("Credential value cannot be empty")

        credentials = self._load_credentials()

        # Create service entry if doesn't exist
        if service not in credentials:
            credentials[service] = {}

        credentials[service][key] = value

        self._save_credentials(credentials)
        logger.info(f"Stored credential in encrypted file: {service}/{key}")

    def delete(self, service: str, key: str) -> bool:
        """Delete credential from encrypted file.

        Args:
            service: Service identifier
            key: Key within service

        Returns:
            True if deleted, False if not found

        Raises:
            EncryptionError: If file operations fail
        """
        credentials = self._load_credentials()

        if service not in credentials:
            return False

        if key not in credentials[service]:
            return False

        del credentials[service][key]

        # Remove service entry if empty
        if not credentials[service]:
            del credentials[service]

        self._save_credentials(credentials)
        logger.info(f"Deleted credential from encrypted file: {service}/{key}")
        return True
