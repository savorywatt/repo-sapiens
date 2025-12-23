# Credential Management System Implementation Plan

**Author**: Python Expert Agent
**Date**: 2025-12-22
**Status**: Ready for Implementation
**Priority**: HIGH - Critical for CLI redesign
**Estimated Effort**: 2-3 weeks

## Executive Summary

This plan details the implementation of a secure, flexible credential management system for the builder CLI. The system addresses critical security gaps identified in the technical review, particularly around credential resolution error handling, and provides a foundation for the upcoming CLI redesign.

**Key Features**:
- Multiple storage backends (keyring, environment variables, encrypted files)
- Safe credential resolution with comprehensive error handling
- Reference syntax: `@keyring:service/key`, `${ENV_VAR}`
- Type-safe integration with Pydantic models
- Zero plaintext secrets in version control
- Cross-platform compatibility (Linux, macOS, Windows)

---

## 1. Architecture Overview

### 1.1 Component Hierarchy

```
CredentialStore (Abstract Base)
├── KeyringBackend (Recommended - OS-level security)
├── EnvironmentBackend (CI/CD friendly)
└── EncryptedFileBackend (Fallback for headless systems)

CredentialResolver
├── Parses reference syntax
├── Routes to appropriate backend
├── Validates and caches credentials
└── Provides detailed error context
```

### 1.2 Reference Syntax

```toml
# Config file: .builder/config.toml

[git_provider]
# Option 1: OS Keyring (recommended)
api_token = "@keyring:gitea/api_token"

# Option 2: Environment variable
api_token = "${GITEA_API_TOKEN}"

# Option 3: Encrypted file reference
api_token = "@encrypted:gitea_token"

# Option 4: Direct value (NOT RECOMMENDED - only for testing)
api_token = "ghp_actual_token_here"
```

### 1.3 Integration with Pydantic

```python
from builder.credentials import CredentialResolver

class GitProviderConfig(BaseModel):
    api_token: str  # Raw value from TOML

    @model_validator(mode='after')
    def resolve_credentials(self) -> 'GitProviderConfig':
        resolver = CredentialResolver()
        self.api_token = resolver.resolve(self.api_token)
        return self
```

---

## 2. Core Implementation

### 2.1 Exception Hierarchy

**File**: `automation/credentials/exceptions.py`

```python
"""Credential-related exceptions with detailed error context."""

from typing import Optional


class CredentialError(Exception):
    """Base exception for all credential operations.

    Attributes:
        message: Human-readable error description
        reference: The credential reference that failed (e.g., "@keyring:service/key")
        suggestion: Optional suggestion for resolution
    """

    def __init__(
        self,
        message: str,
        reference: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        self.message = message
        self.reference = reference
        self.suggestion = suggestion

        full_message = message
        if reference:
            full_message = f"{message} (reference: {reference})"
        if suggestion:
            full_message = f"{full_message}\nSuggestion: {suggestion}"

        super().__init__(full_message)


class CredentialNotFoundError(CredentialError):
    """Credential exists in config but not in storage backend."""
    pass


class CredentialFormatError(CredentialError):
    """Credential reference has invalid format."""
    pass


class BackendNotAvailableError(CredentialError):
    """Requested backend is not available on this system."""
    pass


class EncryptionError(CredentialError):
    """Encryption or decryption operation failed."""
    pass
```

### 2.2 Backend Protocol

**File**: `automation/credentials/backend.py`

```python
"""Abstract backend protocol for credential storage."""

from typing import Protocol, Optional


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

    def get(self, service: str, key: str) -> Optional[str]:
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
```

### 2.3 Keyring Backend (Recommended)

**File**: `automation/credentials/keyring_backend.py`

```python
"""OS-level keyring backend using system credential stores.

Platform Support:
- Linux: Secret Service API (GNOME Keyring, KWallet)
- macOS: Keychain
- Windows: Windows Credential Locker
"""

import logging
from typing import Optional

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

    def get(self, service: str, key: str) -> Optional[str]:
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
                suggestion="Install keyring: pip install keyring"
            )

        try:
            # Namespace credentials under 'builder' to avoid conflicts
            full_service = f"builder/{service}"
            credential = keyring.get_password(full_service, key)

            if credential is not None:
                logger.debug(f"Retrieved credential from keyring: {service}/{key}")

            return credential

        except KeyringError as e:
            raise CredentialError(
                f"Keyring operation failed: {e}",
                reference=f"@keyring:{service}/{key}"
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
                suggestion="Install keyring: pip install keyring"
            )

        if not value:
            raise ValueError("Credential value cannot be empty")

        try:
            full_service = f"builder/{service}"
            keyring.set_password(full_service, key, value)
            logger.info(f"Stored credential in keyring: {service}/{key}")

        except KeyringError as e:
            raise CredentialError(
                f"Failed to store credential: {e}",
                reference=f"@keyring:{service}/{key}"
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
            raise BackendNotAvailableError(
                "Keyring backend is not available"
            )

        try:
            full_service = f"builder/{service}"
            keyring.delete_password(full_service, key)
            logger.info(f"Deleted credential from keyring: {service}/{key}")
            return True

        except PasswordDeleteError:
            # Credential doesn't exist - not an error
            return False

        except KeyringError as e:
            raise CredentialError(
                f"Failed to delete credential: {e}",
                reference=f"@keyring:{service}/{key}"
            ) from e
```

### 2.4 Environment Variable Backend

**File**: `automation/credentials/environment_backend.py`

```python
"""Environment variable backend for CI/CD and containerized environments."""

import logging
import os
from typing import Optional

from .exceptions import CredentialError

logger = logging.getLogger(__name__)


class EnvironmentBackend:
    """Environment variable credential storage.

    This backend is ideal for:
    - CI/CD pipelines (GitHub Actions, Gitea Actions)
    - Docker containers
    - Serverless functions
    - Any environment where secrets are injected as env vars

    Security Considerations:
    - Environment variables are visible to all processes
    - May be logged in process listings
    - Not persisted across sessions
    - Suitable for temporary/ephemeral environments

    Example:
        >>> import os
        >>> os.environ['GITEA_API_TOKEN'] = 'ghp_abc123'
        >>> backend = EnvironmentBackend()
        >>> token = backend.get('GITEA_API_TOKEN')
    """

    @property
    def name(self) -> str:
        return "environment"

    @property
    def available(self) -> bool:
        """Environment backend is always available."""
        return True

    def get(self, var_name: str) -> Optional[str]:
        """Retrieve credential from environment variable.

        Args:
            var_name: Environment variable name (e.g., 'GITEA_API_TOKEN')

        Returns:
            Credential value or None if not set

        Note:
            This method uses a single parameter (var_name) unlike other
            backends that use (service, key) to match environment variable
            semantics.
        """
        value = os.getenv(var_name)

        if value is not None:
            logger.debug(f"Retrieved credential from environment: {var_name}")

        return value

    def set(self, var_name: str, value: str) -> None:
        """Set environment variable.

        Args:
            var_name: Environment variable name
            value: Credential value

        Note:
            Changes only affect the current process and child processes.
            Not persisted across sessions.
        """
        if not value:
            raise ValueError("Credential value cannot be empty")

        os.environ[var_name] = value
        logger.debug(f"Set environment variable: {var_name}")

    def delete(self, var_name: str) -> bool:
        """Remove environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            True if deleted, False if not found
        """
        if var_name in os.environ:
            del os.environ[var_name]
            logger.debug(f"Deleted environment variable: {var_name}")
            return True
        return False
```

### 2.5 Encrypted File Backend

**File**: `automation/credentials/encrypted_backend.py`

```python
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
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from .exceptions import EncryptionError, CredentialError

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
        master_password: Optional[str] = None,
        salt: Optional[bytes] = None,
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
        if master_password:
            self.fernet = self._create_fernet(master_password, self.salt)
        else:
            self.fernet = None  # Lazy initialization on first use

        self._credentials_cache: Optional[Dict[str, Dict[str, str]]] = None

    @property
    def name(self) -> str:
        return "encrypted_file"

    @property
    def available(self) -> bool:
        """Check if cryptography package is available."""
        try:
            # Test import
            from cryptography.fernet import Fernet
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
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=480_000,  # OWASP recommendation for SHA-256
        )
        key = kdf.derive(password.encode('utf-8'))
        return Fernet(key)

    def _load_or_generate_salt(self) -> bytes:
        """Load salt from file or generate new one.

        Salt is stored in .builder/credentials.salt

        Returns:
            16-byte cryptographic salt
        """
        salt_file = self.file_path.parent / "credentials.salt"

        if salt_file.exists():
            with open(salt_file, 'rb') as f:
                return f.read()

        # Generate new salt
        import secrets
        salt = secrets.token_bytes(16)

        # Ensure directory exists
        salt_file.parent.mkdir(parents=True, exist_ok=True)

        # Write salt
        with open(salt_file, 'wb') as f:
            f.write(salt)

        # Restrict permissions (Unix only)
        try:
            salt_file.chmod(0o600)
        except Exception as e:
            logger.warning(f"Could not set salt file permissions: {e}")

        return salt

    def _load_credentials(self) -> Dict[str, Dict[str, str]]:
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
                suggestion="Initialize backend with master_password parameter"
            )

        try:
            # Read encrypted data
            with open(self.file_path, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            decrypted_data = self.fernet.decrypt(encrypted_data)

            # Parse JSON
            credentials = json.loads(decrypted_data.decode('utf-8'))

            self._credentials_cache = credentials
            return credentials

        except InvalidToken as e:
            raise EncryptionError(
                "Invalid master password or corrupted credentials file",
                suggestion="Verify your master password"
            ) from e
        except json.JSONDecodeError as e:
            raise EncryptionError(
                "Credentials file is corrupted",
                suggestion="Restore from backup or delete and recreate"
            ) from e
        except Exception as e:
            raise EncryptionError(
                f"Failed to load credentials: {e}"
            ) from e

    def _save_credentials(self, credentials: Dict[str, Dict[str, str]]) -> None:
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
            encrypted_data = self.fernet.encrypt(json_data.encode('utf-8'))

            # Write atomically using temporary file
            temp_file = self.file_path.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
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
            raise EncryptionError(
                f"Failed to save credentials: {e}"
            ) from e

    def get(self, service: str, key: str) -> Optional[str]:
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
```

### 2.6 Credential Resolver

**File**: `automation/credentials/resolver.py`

```python
"""High-level credential resolution with automatic backend selection."""

import logging
import re
from pathlib import Path
from typing import Optional, Dict

from .backend import CredentialBackend
from .keyring_backend import KeyringBackend
from .environment_backend import EnvironmentBackend
from .encrypted_backend import EncryptedFileBackend
from .exceptions import (
    CredentialError,
    CredentialNotFoundError,
    CredentialFormatError,
    BackendNotAvailableError,
)

logger = logging.getLogger(__name__)


class CredentialResolver:
    """Resolve credential references to actual values.

    Supports three reference formats:
    1. @keyring:service/key - OS keyring
    2. ${VAR_NAME} - Environment variable
    3. @encrypted:service/key - Encrypted file
    4. Direct value - Returned as-is (not recommended)

    Example:
        >>> resolver = CredentialResolver()
        >>> token = resolver.resolve("@keyring:gitea/api_token")
        >>> api_key = resolver.resolve("${CLAUDE_API_KEY}")
        >>> direct = resolver.resolve("literal-value")
    """

    # Regex patterns for credential references
    KEYRING_PATTERN = re.compile(r'^@keyring:([^/]+)/(.+)$')
    ENV_PATTERN = re.compile(r'^\$\{([A-Z_][A-Z0-9_]*)\}$')
    ENCRYPTED_PATTERN = re.compile(r'^@encrypted:([^/]+)/(.+)$')

    def __init__(
        self,
        encrypted_file_path: Optional[Path] = None,
        encrypted_master_password: Optional[str] = None,
    ) -> None:
        """Initialize credential resolver.

        Args:
            encrypted_file_path: Path to encrypted credentials file
            encrypted_master_password: Master password for encrypted backend
        """
        # Initialize backends
        self.keyring_backend = KeyringBackend()
        self.environment_backend = EnvironmentBackend()

        # Encrypted backend initialized lazily
        self._encrypted_backend: Optional[EncryptedFileBackend] = None
        self._encrypted_file_path = encrypted_file_path
        self._encrypted_master_password = encrypted_master_password

        # Cache for resolved credentials (reduces backend calls)
        self._cache: Dict[str, str] = {}

    @property
    def encrypted_backend(self) -> EncryptedFileBackend:
        """Lazy initialization of encrypted file backend."""
        if self._encrypted_backend is None:
            file_path = self._encrypted_file_path or Path('.builder/credentials.enc')
            self._encrypted_backend = EncryptedFileBackend(
                file_path=file_path,
                master_password=self._encrypted_master_password,
            )
        return self._encrypted_backend

    def resolve(self, value: str, cache: bool = True) -> str:
        """Resolve credential reference to actual value.

        Args:
            value: Credential reference or direct value
            cache: Whether to cache the resolved value

        Returns:
            Resolved credential value

        Raises:
            CredentialNotFoundError: If credential doesn't exist
            CredentialFormatError: If reference format is invalid
            BackendNotAvailableError: If required backend is unavailable

        Example:
            >>> resolver.resolve("@keyring:gitea/api_token")
            'ghp_abc123...'
            >>> resolver.resolve("${GITEA_TOKEN}")
            'ghp_xyz789...'
            >>> resolver.resolve("literal-value")
            'literal-value'
        """
        # Check cache first
        if cache and value in self._cache:
            logger.debug(f"Credential resolved from cache: {value}")
            return self._cache[value]

        # Try to parse as keyring reference
        keyring_match = self.KEYRING_PATTERN.match(value)
        if keyring_match:
            resolved = self._resolve_keyring(
                service=keyring_match.group(1),
                key=keyring_match.group(2),
                reference=value,
            )
            if cache:
                self._cache[value] = resolved
            return resolved

        # Try to parse as environment variable
        env_match = self.ENV_PATTERN.match(value)
        if env_match:
            resolved = self._resolve_environment(
                var_name=env_match.group(1),
                reference=value,
            )
            if cache:
                self._cache[value] = resolved
            return resolved

        # Try to parse as encrypted file reference
        encrypted_match = self.ENCRYPTED_PATTERN.match(value)
        if encrypted_match:
            resolved = self._resolve_encrypted(
                service=encrypted_match.group(1),
                key=encrypted_match.group(2),
                reference=value,
            )
            if cache:
                self._cache[value] = resolved
            return resolved

        # If no pattern matches, treat as direct value
        # Log warning if it looks like a token (security)
        if self._looks_like_token(value):
            logger.warning(
                "Credential appears to be a direct token value. "
                "Consider using @keyring:, ${ENV_VAR}, or @encrypted: instead."
            )

        return value

    def _resolve_keyring(self, service: str, key: str, reference: str) -> str:
        """Resolve keyring reference.

        Args:
            service: Service identifier
            key: Key within service
            reference: Original reference string (for error messages)

        Returns:
            Credential value

        Raises:
            CredentialNotFoundError: If credential doesn't exist
            BackendNotAvailableError: If keyring is unavailable
        """
        if not self.keyring_backend.available:
            raise BackendNotAvailableError(
                "Keyring backend is not available on this system",
                reference=reference,
                suggestion=(
                    "Install keyring: pip install keyring\n"
                    "Or use environment variables: ${VAR_NAME}"
                )
            )

        try:
            credential = self.keyring_backend.get(service, key)

            if credential is None:
                raise CredentialNotFoundError(
                    f"Credential not found in keyring: {service}/{key}",
                    reference=reference,
                    suggestion=(
                        f"Store the credential with:\n"
                        f"  builder credentials set --keyring {service}/{key}"
                    )
                )

            logger.debug(f"Resolved keyring credential: {service}/{key}")
            return credential

        except CredentialError:
            raise
        except Exception as e:
            raise CredentialError(
                f"Failed to resolve keyring credential: {e}",
                reference=reference,
            ) from e

    def _resolve_environment(self, var_name: str, reference: str) -> str:
        """Resolve environment variable reference.

        Args:
            var_name: Environment variable name
            reference: Original reference string

        Returns:
            Credential value

        Raises:
            CredentialNotFoundError: If variable is not set
        """
        credential = self.environment_backend.get(var_name)

        if credential is None:
            raise CredentialNotFoundError(
                f"Environment variable not set: {var_name}",
                reference=reference,
                suggestion=(
                    f"Set the environment variable:\n"
                    f"  export {var_name}='your-credential-here'"
                )
            )

        logger.debug(f"Resolved environment credential: {var_name}")
        return credential

    def _resolve_encrypted(self, service: str, key: str, reference: str) -> str:
        """Resolve encrypted file reference.

        Args:
            service: Service identifier
            key: Key within service
            reference: Original reference string

        Returns:
            Credential value

        Raises:
            CredentialNotFoundError: If credential doesn't exist
            BackendNotAvailableError: If encrypted backend is unavailable
        """
        if not self.encrypted_backend.available:
            raise BackendNotAvailableError(
                "Encrypted file backend is not available",
                reference=reference,
                suggestion="Install cryptography: pip install cryptography"
            )

        try:
            credential = self.encrypted_backend.get(service, key)

            if credential is None:
                raise CredentialNotFoundError(
                    f"Credential not found in encrypted file: {service}/{key}",
                    reference=reference,
                    suggestion=(
                        f"Store the credential with:\n"
                        f"  builder credentials set --encrypted {service}/{key}"
                    )
                )

            logger.debug(f"Resolved encrypted file credential: {service}/{key}")
            return credential

        except CredentialError:
            raise
        except Exception as e:
            raise CredentialError(
                f"Failed to resolve encrypted credential: {e}",
                reference=reference,
            ) from e

    @staticmethod
    def _looks_like_token(value: str) -> bool:
        """Heuristic check if value looks like an API token.

        Detects common patterns:
        - GitHub tokens (ghp_, gho_, etc.)
        - Long alphanumeric strings (>20 chars)
        - Base64-like strings
        """
        if not value:
            return False

        # GitHub token prefixes
        if value.startswith(('ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_')):
            return True

        # Long alphanumeric or base64-like
        if len(value) > 20 and value.replace('-', '').replace('_', '').isalnum():
            return True

        return False

    def clear_cache(self) -> None:
        """Clear resolved credentials cache.

        Use this when credentials may have been updated.
        """
        self._cache.clear()
        logger.debug("Credential cache cleared")
```

### 2.7 Package Initialization

**File**: `automation/credentials/__init__.py`

```python
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
from .keyring_backend import KeyringBackend
from .environment_backend import EnvironmentBackend
from .encrypted_backend import EncryptedFileBackend
from .resolver import CredentialResolver
from .exceptions import (
    CredentialError,
    CredentialNotFoundError,
    CredentialFormatError,
    BackendNotAvailableError,
    EncryptionError,
)

__all__ = [
    # Backends
    'CredentialBackend',
    'KeyringBackend',
    'EnvironmentBackend',
    'EncryptedFileBackend',

    # Resolver
    'CredentialResolver',

    # Exceptions
    'CredentialError',
    'CredentialNotFoundError',
    'CredentialFormatError',
    'BackendNotAvailableError',
    'EncryptionError',
]
```

---

## 3. Integration with Pydantic Configuration

### 3.1 Updated Settings Model

**File**: `automation/config/settings.py` (modifications)

```python
"""Enhanced configuration with automatic credential resolution."""

from typing import Annotated
from pydantic import BeforeValidator, Field

from automation.credentials import CredentialResolver


def resolve_credential(value: str) -> str:
    """Pydantic validator to resolve credential references."""
    if not isinstance(value, str):
        return value

    resolver = CredentialResolver()
    return resolver.resolve(value)


# Type alias for credential fields
SecureString = Annotated[str, BeforeValidator(resolve_credential)]


class GitProviderConfig(BaseModel):
    """Git provider configuration with automatic credential resolution."""

    provider_type: Literal["gitea", "github"] = "gitea"
    base_url: HttpUrl
    api_token: SecureString  # Automatically resolves @keyring:, ${ENV}, etc.


class AIProviderConfig(BaseModel):
    """AI provider configuration with automatic credential resolution."""

    type: Literal["claude-api", "ollama", "openai"]
    model: str
    api_key: Optional[SecureString] = None  # Automatically resolves references
    base_url: Optional[str] = None

    @field_validator("api_key")
    @classmethod
    def validate_api_key_required(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Validate that API key is provided for cloud providers."""
        provider_type = info.data.get("type")

        if provider_type in ["claude-api", "openai"] and not v:
            raise ValueError(f"{provider_type} requires api_key to be set")

        return v
```

### 3.2 Usage in Configuration Loading

```python
# Example: Loading config with automatic credential resolution

from pathlib import Path
from automation.config import AutomationSettings

# Load config from TOML
config = AutomationSettings.from_yaml("automation/config/automation_config.yaml")

# Credentials are automatically resolved
print(config.git_provider.api_token)  # Actual token value, not "@keyring:..."
```

---

## 4. CLI Integration

### 4.1 Credential Management Commands

**File**: `automation/cli/credentials.py` (new)

```python
"""CLI commands for credential management."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from automation.credentials import (
    CredentialResolver,
    KeyringBackend,
    EnvironmentBackend,
    EncryptedFileBackend,
    CredentialError,
)

console = Console()


@click.group()
def credentials():
    """Manage credentials for the builder CLI."""
    pass


@credentials.command()
@click.argument('reference')
@click.option('--backend', type=click.Choice(['keyring', 'environment', 'encrypted']))
@click.option('--value', prompt=True, hide_input=True, confirmation_prompt=True)
def set(reference: str, backend: str, value: str):
    """Store a credential.

    Examples:

        builder credentials set gitea/api_token --backend keyring
        builder credentials set claude/api_key --backend encrypted
    """
    try:
        # Parse reference
        if '/' not in reference:
            console.print("[red]Error:[/red] Reference must be in format: service/key")
            raise click.Abort()

        service, key = reference.split('/', 1)

        # Select backend
        if backend == 'keyring':
            backend_impl = KeyringBackend()
        elif backend == 'environment':
            backend_impl = EnvironmentBackend()
            # For environment backend, use different parameter
            backend_impl.set(f"{service.upper()}_{key.upper()}", value)
            console.print(f"[green]✓[/green] Set environment variable: {service.upper()}_{key.upper()}")
            return
        else:  # encrypted
            backend_impl = EncryptedFileBackend(
                file_path=Path('.builder/credentials.enc'),
                master_password=click.prompt('Master password', hide_input=True)
            )

        # Store credential
        backend_impl.set(service, key, value)
        console.print(f"[green]✓[/green] Stored credential: {service}/{key} in {backend}")

    except CredentialError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise click.Abort()


@credentials.command()
@click.argument('reference')
def get(reference: str):
    """Retrieve a credential (for debugging).

    Examples:

        builder credentials get @keyring:gitea/api_token
        builder credentials get ${GITEA_TOKEN}
    """
    try:
        resolver = CredentialResolver()
        value = resolver.resolve(reference, cache=False)

        # Mask the value for security
        if len(value) > 8:
            masked = value[:4] + '*' * (len(value) - 8) + value[-4:]
        else:
            masked = '*' * len(value)

        console.print(f"[green]✓[/green] Resolved: {masked}")

    except CredentialError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[yellow]Suggestion:[/yellow] {e.suggestion}")
        raise click.Abort()


@credentials.command()
@click.argument('reference')
@click.option('--backend', type=click.Choice(['keyring', 'environment', 'encrypted']))
def delete(reference: str, backend: str):
    """Delete a credential.

    Examples:

        builder credentials delete gitea/api_token --backend keyring
    """
    try:
        service, key = reference.split('/', 1)

        if backend == 'keyring':
            backend_impl = KeyringBackend()
        elif backend == 'environment':
            backend_impl = EnvironmentBackend()
            var_name = f"{service.upper()}_{key.upper()}"
            if backend_impl.delete(var_name):
                console.print(f"[green]✓[/green] Deleted environment variable: {var_name}")
            else:
                console.print(f"[yellow]![/yellow] Environment variable not found: {var_name}")
            return
        else:  # encrypted
            backend_impl = EncryptedFileBackend(
                file_path=Path('.builder/credentials.enc'),
                master_password=click.prompt('Master password', hide_input=True)
            )

        if backend_impl.delete(service, key):
            console.print(f"[green]✓[/green] Deleted credential: {service}/{key}")
        else:
            console.print(f"[yellow]![/yellow] Credential not found: {service}/{key}")

    except CredentialError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        raise click.Abort()


@credentials.command()
def list():
    """List stored credentials (names only, not values)."""
    table = Table(title="Stored Credentials")
    table.add_column("Backend", style="cyan")
    table.add_column("Service/Key", style="green")

    # This is a simplified example - actual implementation would need
    # backend-specific listing logic
    console.print("[yellow]Note:[/yellow] Credential listing is backend-specific")
    console.print("Use your system's keyring manager to view keyring credentials")
```

### 4.2 Integration with Main CLI

**File**: `automation/main.py` (modifications)

```python
# Add to existing CLI

from automation.cli.credentials import credentials

@click.group()
def cli():
    """Builder automation CLI."""
    pass

# Register credential commands
cli.add_command(credentials)
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

**File**: `tests/test_credentials/test_keyring_backend.py`

```python
"""Tests for keyring backend."""

import pytest
from unittest.mock import Mock, patch

from automation.credentials import KeyringBackend, BackendNotAvailableError


class TestKeyringBackend:
    """Test KeyringBackend functionality."""

    @pytest.fixture
    def backend(self):
        """Create KeyringBackend instance."""
        return KeyringBackend()

    @patch('automation.credentials.keyring_backend.keyring')
    def test_get_credential_success(self, mock_keyring, backend):
        """Test successful credential retrieval."""
        mock_keyring.get_password.return_value = 'test-token'

        result = backend.get('gitea', 'api_token')

        assert result == 'test-token'
        mock_keyring.get_password.assert_called_once_with('builder/gitea', 'api_token')

    @patch('automation.credentials.keyring_backend.keyring')
    def test_get_credential_not_found(self, mock_keyring, backend):
        """Test credential not found returns None."""
        mock_keyring.get_password.return_value = None

        result = backend.get('gitea', 'api_token')

        assert result is None

    @patch('automation.credentials.keyring_backend.KEYRING_AVAILABLE', False)
    def test_unavailable_backend(self):
        """Test backend reports unavailable when keyring not installed."""
        backend = KeyringBackend()

        assert not backend.available

        with pytest.raises(BackendNotAvailableError):
            backend.get('gitea', 'api_token')

    @patch('automation.credentials.keyring_backend.keyring')
    def test_set_credential(self, mock_keyring, backend):
        """Test credential storage."""
        backend.set('gitea', 'api_token', 'new-token')

        mock_keyring.set_password.assert_called_once_with(
            'builder/gitea', 'api_token', 'new-token'
        )

    def test_set_empty_value_raises_error(self, backend):
        """Test that empty values are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            backend.set('gitea', 'api_token', '')
```

**File**: `tests/test_credentials/test_resolver.py`

```python
"""Tests for credential resolver."""

import pytest
from unittest.mock import Mock, patch

from automation.credentials import CredentialResolver, CredentialNotFoundError, CredentialFormatError


class TestCredentialResolver:
    """Test CredentialResolver functionality."""

    @pytest.fixture
    def resolver(self):
        """Create CredentialResolver instance."""
        return CredentialResolver()

    @patch('automation.credentials.resolver.KeyringBackend')
    def test_resolve_keyring_reference(self, mock_backend_class, resolver):
        """Test resolving @keyring:service/key references."""
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = 'test-token'
        mock_backend_class.return_value = mock_backend

        resolver = CredentialResolver()
        result = resolver.resolve('@keyring:gitea/api_token')

        assert result == 'test-token'

    @patch.dict('os.environ', {'GITEA_TOKEN': 'env-token'})
    def test_resolve_env_reference(self, resolver):
        """Test resolving ${VAR} references."""
        result = resolver.resolve('${GITEA_TOKEN}')

        assert result == 'env-token'

    def test_resolve_env_not_found_raises_error(self, resolver):
        """Test that missing environment variables raise error."""
        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolver.resolve('${NONEXISTENT_VAR}')

        assert 'NONEXISTENT_VAR' in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    def test_resolve_direct_value(self, resolver):
        """Test that direct values are returned as-is."""
        result = resolver.resolve('direct-value')

        assert result == 'direct-value'

    def test_cache_resolved_credentials(self, resolver):
        """Test that resolved credentials are cached."""
        with patch.dict('os.environ', {'TEST_VAR': 'cached-value'}):
            # First call
            result1 = resolver.resolve('${TEST_VAR}')

            # Modify environment
            import os
            os.environ['TEST_VAR'] = 'new-value'

            # Second call should return cached value
            result2 = resolver.resolve('${TEST_VAR}')

            assert result1 == result2 == 'cached-value'

    def test_clear_cache(self, resolver):
        """Test cache clearing."""
        with patch.dict('os.environ', {'TEST_VAR': 'value1'}):
            result1 = resolver.resolve('${TEST_VAR}')

            import os
            os.environ['TEST_VAR'] = 'value2'

            resolver.clear_cache()
            result2 = resolver.resolve('${TEST_VAR}')

            assert result1 == 'value1'
            assert result2 == 'value2'
```

### 5.2 Integration Tests

**File**: `tests/test_credentials/test_integration.py`

```python
"""Integration tests for credential system."""

import pytest
import tempfile
from pathlib import Path

from automation.credentials import (
    CredentialResolver,
    EncryptedFileBackend,
)
from automation.config import AutomationSettings


class TestCredentialIntegration:
    """Test full credential resolution flow."""

    def test_pydantic_integration(self, tmp_path):
        """Test Pydantic field validation with credential resolution."""
        import os

        # Set up environment
        os.environ['TEST_GITEA_TOKEN'] = 'test-token-123'

        # Create config with environment reference
        config_data = {
            'git_provider': {
                'provider_type': 'gitea',
                'base_url': 'https://gitea.example.com',
                'api_token': '${TEST_GITEA_TOKEN}',
            },
            'repository': {
                'owner': 'test-owner',
                'name': 'test-repo',
            },
            'agent_provider': {
                'provider_type': 'ollama',
                'model': 'llama3.1:8b',
            }
        }

        # Load config
        config = AutomationSettings(**config_data)

        # Verify credential was resolved
        assert config.git_provider.api_token == 'test-token-123'

    def test_encrypted_file_backend_full_flow(self, tmp_path):
        """Test complete encrypted file workflow."""
        file_path = tmp_path / "credentials.enc"
        password = "test-password-123"

        # Create backend and store credential
        backend = EncryptedFileBackend(file_path, password)
        backend.set('gitea', 'api_token', 'secret-token')

        # Verify file was created
        assert file_path.exists()

        # Create new backend instance (simulating restart)
        backend2 = EncryptedFileBackend(file_path, password)

        # Retrieve credential
        token = backend2.get('gitea', 'api_token')
        assert token == 'secret-token'

        # Delete credential
        assert backend2.delete('gitea', 'api_token')
        assert backend2.get('gitea', 'api_token') is None
```

### 5.3 Security Tests

**File**: `tests/test_credentials/test_security.py`

```python
"""Security-focused tests for credential management."""

import pytest
import os
from pathlib import Path

from automation.credentials import EncryptedFileBackend, EncryptionError


class TestCredentialSecurity:
    """Test security properties of credential management."""

    def test_file_permissions_restricted(self, tmp_path):
        """Test that credential files have restrictive permissions."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        backend.set('test', 'key', 'value')

        # Check file permissions (Unix only)
        if os.name != 'nt':  # Skip on Windows
            stat_info = file_path.stat()
            # Should be 0o600 (user read/write only)
            assert stat_info.st_mode & 0o777 == 0o600

    def test_wrong_password_fails(self, tmp_path):
        """Test that wrong password cannot decrypt credentials."""
        file_path = tmp_path / "credentials.enc"

        # Store with one password
        backend1 = EncryptedFileBackend(file_path, "correct-password")
        backend1.set('test', 'key', 'secret-value')

        # Try to read with different password
        backend2 = EncryptedFileBackend(file_path, "wrong-password")

        with pytest.raises(EncryptionError, match="Invalid master password"):
            backend2.get('test', 'key')

    def test_no_plaintext_in_encrypted_file(self, tmp_path):
        """Test that credentials are actually encrypted."""
        file_path = tmp_path / "credentials.enc"
        secret = "super-secret-api-key-12345"

        backend = EncryptedFileBackend(file_path, "password")
        backend.set('test', 'key', secret)

        # Read raw file content
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Verify secret is not present in plaintext
        assert secret.encode('utf-8') not in file_content

    def test_token_detection_heuristic(self):
        """Test that direct token values trigger warnings."""
        from automation.credentials.resolver import CredentialResolver

        resolver = CredentialResolver()

        # These should be detected as tokens
        assert resolver._looks_like_token('ghp_1234567890abcdef1234567890')
        assert resolver._looks_like_token('a' * 30)  # Long alphanumeric

        # These should not
        assert not resolver._looks_like_token('short')
        assert not resolver._looks_like_token('${ENV_VAR}')
        assert not resolver._looks_like_token('@keyring:service/key')
```

---

## 6. Security Considerations

### 6.1 Threat Model

**Threats Addressed**:

1. **Plaintext Secrets in Version Control**
   - Mitigated by: Reference syntax, no direct values in config
   - Residual risk: Users could still commit direct values (detected with warnings)

2. **Secret Exposure in Logs**
   - Mitigated by: Never log credential values, only references
   - Residual risk: Application code could log secrets

3. **Unauthorized Access to Credentials**
   - Mitigated by: OS keyring security, file permissions (0600), encryption
   - Residual risk: Root/admin users can access all credentials

4. **Credential Theft via Memory Dump**
   - Mitigated by: Minimize time credentials in memory, clear cache
   - Residual risk: Credentials must be in memory when used

5. **Man-in-the-Middle Attacks**
   - Mitigated by: HTTPS for all API calls
   - Out of scope: Transport layer security

### 6.2 Security Best Practices

**Backend Selection Guide**:

| Backend | Security Level | Use Case |
|---------|---------------|----------|
| Keyring | HIGH | Developer workstations, interactive use |
| Environment | MEDIUM | CI/CD, containers, serverless |
| Encrypted File | MEDIUM | Headless systems, shared environments |
| Direct Value | LOW | Testing only, never production |

**Recommendations**:

1. **Always use keyring on developer machines**
   - OS-level security features (encryption, biometrics)
   - Persists across reboots
   - Supports per-user isolation

2. **Use environment variables in CI/CD**
   - Native support in GitHub Actions, Gitea Actions
   - Scoped to workflow execution
   - Automatically cleared after job

3. **Use encrypted file as fallback only**
   - Master password must be protected
   - Not suitable for shared systems
   - Requires manual key rotation

4. **Never commit direct credentials**
   - Use .gitignore for config files
   - Enable pre-commit hooks
   - Use git-secrets or similar tools

### 6.3 Audit and Compliance

**Logging Strategy**:

```python
# Good: Log credential access, not values
logger.info("Retrieved credential from keyring", extra={
    'service': 'gitea',
    'key': 'api_token',
    'backend': 'keyring',
})

# Bad: Never log actual values
logger.info(f"Token: {api_token}")  # DON'T DO THIS
```

**Credential Rotation**:

```bash
# Recommended workflow for rotating credentials

# 1. Generate new credential on service
# 2. Store new credential
builder credentials set gitea/api_token --backend keyring

# 3. Test new credential
builder doctor

# 4. Revoke old credential on service
```

---

## 7. Migration Guide

### 7.1 From Direct Values to References

**Before** (`automation/config/automation_config.yaml`):

```yaml
git_provider:
  base_url: "https://gitea.example.com"
  api_token: "ghp_actual_token_here"  # BAD: Direct value
```

**After**:

```yaml
git_provider:
  base_url: "https://gitea.example.com"
  api_token: "@keyring:gitea/api_token"  # GOOD: Reference
```

**Migration Steps**:

```bash
# 1. Store credential in keyring
builder credentials set gitea/api_token --backend keyring
# (Enter token when prompted)

# 2. Update config file
sed -i 's/api_token: "ghp_.*/api_token: "@keyring:gitea\/api_token"/' config.yaml

# 3. Verify
builder doctor

# 4. Commit updated config (safe - no secrets)
git add config.yaml
git commit -m "chore: Migrate to keyring credential references"
```

### 7.2 From Environment Variables to Keyring

**Before** (`.env` file):

```bash
GITEA_API_TOKEN=ghp_actual_token
CLAUDE_API_KEY=sk-ant-actual-key
```

**After** (config file):

```yaml
git_provider:
  api_token: "@keyring:gitea/api_token"

ai_provider:
  api_key: "@keyring:claude/api_key"
```

**Migration**:

```bash
# 1. Store credentials in keyring
builder credentials set gitea/api_token --backend keyring
builder credentials set claude/api_key --backend keyring

# 2. Remove .env file
rm .env

# 3. Update config references
# ... (edit config.yaml)

# 4. Verify
builder doctor
```

---

## 8. Documentation Requirements

### 8.1 User Documentation

**Topics to Cover**:

1. **Quick Start**
   - How to store first credential
   - How to configure credential references
   - How to verify credentials work

2. **Reference Guide**
   - All supported reference formats
   - Backend comparison table
   - Error messages and solutions

3. **Security Guide**
   - Best practices
   - Threat model
   - Compliance considerations

4. **Troubleshooting**
   - Common errors and fixes
   - Backend availability issues
   - Permission problems

### 8.2 Developer Documentation

**Topics to Cover**:

1. **Architecture Overview**
   - Component diagram
   - Backend protocol
   - Resolution flow

2. **Adding New Backends**
   - Protocol implementation
   - Testing requirements
   - Registration

3. **API Reference**
   - All public classes and methods
   - Type signatures
   - Examples

---

## 9. Implementation Checklist

### Phase 1: Foundation (Week 1)

- [ ] Create `automation/credentials/` package structure
- [ ] Implement exception hierarchy
- [ ] Implement backend protocol
- [ ] Write unit tests for exceptions
- [ ] Update `pyproject.toml` dependencies (add `keyring`, `cryptography`)

### Phase 2: Backend Implementation (Week 1-2)

- [ ] Implement KeyringBackend
  - [ ] Basic CRUD operations
  - [ ] Availability check
  - [ ] Error handling
  - [ ] Unit tests (15+ test cases)
  - [ ] Integration tests

- [ ] Implement EnvironmentBackend
  - [ ] Basic operations
  - [ ] Unit tests (10+ test cases)

- [ ] Implement EncryptedFileBackend
  - [ ] Encryption/decryption
  - [ ] File operations
  - [ ] Permission handling
  - [ ] Unit tests (20+ test cases)
  - [ ] Security tests

### Phase 3: Resolver Implementation (Week 2)

- [ ] Implement CredentialResolver
  - [ ] Reference parsing
  - [ ] Backend routing
  - [ ] Caching
  - [ ] Error handling with suggestions
  - [ ] Unit tests (15+ test cases)

- [ ] Pydantic integration
  - [ ] Validator implementation
  - [ ] Type alias
  - [ ] Integration tests

### Phase 4: CLI Integration (Week 2-3)

- [ ] Implement credential CLI commands
  - [ ] `set` command
  - [ ] `get` command
  - [ ] `delete` command
  - [ ] `list` command
  - [ ] Rich output formatting

- [ ] Update main CLI
  - [ ] Register credential subcommand
  - [ ] Help text
  - [ ] Examples

### Phase 5: Testing & Documentation (Week 3)

- [ ] Comprehensive test suite
  - [ ] Unit tests (60+ test cases)
  - [ ] Integration tests (10+ scenarios)
  - [ ] Security tests (8+ scenarios)
  - [ ] Cross-platform tests (Linux, macOS, Windows)

- [ ] Documentation
  - [ ] API documentation
  - [ ] User guide
  - [ ] Security guide
  - [ ] Migration guide
  - [ ] Troubleshooting

- [ ] Code review
  - [ ] Security review
  - [ ] Type checking (mypy)
  - [ ] Linting (ruff, black)

### Phase 6: Release Preparation (Week 3)

- [ ] Update CHANGELOG.md
- [ ] Update README.md
- [ ] Create example configurations
- [ ] Test PyPI package
- [ ] Create migration script
- [ ] Final QA testing

---

## 10. Success Metrics

**Functional Metrics**:
- Zero credential exposure incidents
- < 2% user-reported credential errors
- 100% test coverage for credential package
- < 1 second credential resolution time

**Security Metrics**:
- Zero plaintext secrets in version control (automated check)
- 100% of direct token values detected with warnings
- All credential files have 0600 permissions (Unix)
- Zero credential values in logs

**Usability Metrics**:
- < 5 minutes to set up first credential
- < 10% of users need support for credential setup
- Clear error messages for 100% of failure modes
- Comprehensive suggestions for 100% of errors

---

## 11. Future Enhancements

### 11.1 Additional Backends (Post-v1.0)

1. **AWS Secrets Manager Backend**
   - Cloud-native secret storage
   - Automatic rotation
   - Audit logging

2. **HashiCorp Vault Backend**
   - Enterprise secret management
   - Dynamic credentials
   - Fine-grained access control

3. **Azure Key Vault Backend**
   - Microsoft cloud integration
   - Managed identities
   - RBAC

### 11.2 Advanced Features

1. **Credential Rotation**
   - Automatic rotation schedules
   - Zero-downtime rotation
   - Rollback support

2. **Multi-Environment Support**
   - Dev/staging/prod credential sets
   - Environment-specific backends
   - Namespace isolation

3. **Credential Sharing**
   - Team credentials
   - Role-based access
   - Audit logging

4. **Credential Health Monitoring**
   - Expiration tracking
   - Usage analytics
   - Security alerts

---

## Appendix A: Error Message Catalog

### Common Errors and Solutions

**Error**: `CredentialNotFoundError: Credential not found in keyring: gitea/api_token`

**Cause**: Credential reference exists in config but not in keyring

**Solution**:
```bash
builder credentials set gitea/api_token --backend keyring
```

---

**Error**: `BackendNotAvailableError: Keyring backend is not available`

**Cause**: keyring package not installed or no backend configured

**Solution**:
```bash
pip install keyring
# Or use environment variables instead:
# Edit config: api_token: "${GITEA_API_TOKEN}"
```

---

**Error**: `CredentialFormatError: Invalid keyring format: @keyring:gitea`

**Cause**: Incomplete keyring reference (missing key)

**Solution**:
```toml
# Wrong:
api_token = "@keyring:gitea"

# Correct:
api_token = "@keyring:gitea/api_token"
```

---

**Error**: `EncryptionError: Invalid master password or corrupted credentials file`

**Cause**: Wrong password or corrupted file

**Solution**:
```bash
# Try correct password or reset:
rm .builder/credentials.enc .builder/credentials.salt
builder credentials set gitea/api_token --backend encrypted
```

---

## Appendix B: Cross-Platform Compatibility

### Linux

**Keyring Backends**:
- GNOME Keyring (default on GNOME)
- KWallet (default on KDE)
- Secret Service API

**Setup**:
```bash
# Install keyring backend
sudo apt install gnome-keyring  # Ubuntu/Debian

# Verify
python -c "import keyring; print(keyring.get_keyring())"
```

### macOS

**Keyring Backend**:
- macOS Keychain (automatic)

**Setup**:
```bash
# No setup required - Keychain is built-in
```

### Windows

**Keyring Backend**:
- Windows Credential Locker (automatic)

**Setup**:
```powershell
# No setup required - Credential Locker is built-in
```

---

**END OF IMPLEMENTATION PLAN**
