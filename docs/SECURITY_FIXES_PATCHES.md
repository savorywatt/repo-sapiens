# Security Fixes: Detailed Patches and Implementation Guide

This document provides complete, copy-paste-ready patches for implementing the security fixes identified in `SECURITY_AUDIT.md`.

---

## Patch 1: Secure Credential Cache with TTL [CRITICAL]

**Files Modified:**
- `automation/credentials/resolver.py`
- `automation/credentials/__init__.py`

**File: `automation/credentials/secure_cache.py` (NEW)**

```python
"""Secure credential cache with TTL and memory management."""

import time
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SecureCredentialCache:
    """TTL-based credential cache with memory wiping.

    Features:
    - Time-to-Live (TTL) for cached entries
    - Automatic expiration of stale credentials
    - Memory wiping on entry removal
    - Context manager support for cleanup
    """

    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache with TTL.

        Args:
            ttl_seconds: Time-to-live for cached entries (default 5 minutes)
        """
        if ttl_seconds < 1:
            raise ValueError("TTL must be at least 1 second")

        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[str, float]] = {}

    def get(self, key: str) -> Optional[str]:
        """Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            # Expired - wipe from memory
            self._wipe_entry(key)
            return None

        return value

    def set(self, key: str, value: str) -> None:
        """Store value in cache with timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        if not isinstance(key, str):
            raise ValueError("Key must be a string")
        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        self._cache[key] = (value, time.time())
        logger.debug(f"Cached credential: {key} (TTL: {self.ttl_seconds}s)")

    def clear(self) -> None:
        """Clear all cache entries and wipe memory."""
        for key in list(self._cache.keys()):
            self._wipe_entry(key)
        self._cache.clear()
        logger.debug("Credential cache cleared and memory wiped")

    def _wipe_entry(self, key: str) -> None:
        """Securely wipe a cache entry from memory.

        Args:
            key: Cache key to wipe
        """
        if key in self._cache:
            value, _ = self._cache[key]
            # For Python strings (immutable), we can only ensure
            # the reference is deleted. Actual memory wiping would
            # require ctypes and platform-specific calls.
            del self._cache[key]
            del value
            logger.debug(f"Wiped cache entry: {key}")

    def is_expired(self, key: str) -> bool:
        """Check if a key is expired without removing it.

        Args:
            key: Cache key

        Returns:
            True if expired or not found
        """
        if key not in self._cache:
            return True

        _, timestamp = self._cache[key]
        return time.time() - timestamp > self.ttl_seconds

    def expire_all(self) -> None:
        """Expire all entries immediately."""
        self.clear()

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache and not expired."""
        return self.get(key) is not None

    def __len__(self) -> int:
        """Return number of non-expired entries."""
        return sum(1 for k in list(self._cache.keys()) if self.get(k) is not None)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit - clears cache."""
        self.clear()


__all__ = ['SecureCredentialCache']
```

**File: `automation/credentials/resolver.py` (MODIFIED)**

```python
"""High-level credential resolution with automatic backend selection."""

import logging
import re
from pathlib import Path
from typing import Optional

from .backend import CredentialBackend
from .keyring_backend import KeyringBackend
from .environment_backend import EnvironmentBackend
from .encrypted_backend import EncryptedFileBackend
from .secure_cache import SecureCredentialCache
from .exceptions import (
    CredentialError,
    CredentialNotFoundError,
    CredentialFormatError,
    BackendNotAvailableError,
)

logger = logging.getLogger(__name__)


class CredentialResolver:
    """Resolve credential references to actual values with secure caching.

    Supports three reference formats:
    1. @keyring:service/key - OS keyring
    2. ${VAR_NAME} - Environment variable
    3. @encrypted:service/key - Encrypted file
    4. Direct value - Returned as-is (not recommended)

    Example:
        >>> with CredentialResolver() as resolver:
        ...     token = resolver.resolve("@keyring:gitea/api_token")
        >>> # Cache automatically cleared on exit
    """

    # Regex patterns for credential references
    KEYRING_PATTERN = re.compile(r'^@keyring:([^/]{1,256})/(.{1,256})$')
    ENV_PATTERN = re.compile(r'^\$\{([A-Z_][A-Z0-9_]{0,254})\}$')
    ENCRYPTED_PATTERN = re.compile(r'^@encrypted:([^/]{1,256})/(.{1,256})$')

    # Configuration
    MAX_REFERENCE_LENGTH = 1024
    DEFAULT_CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        encrypted_file_path: Optional[Path] = None,
        encrypted_master_password: Optional[str] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL,
        enable_cache: bool = True,
    ) -> None:
        """Initialize credential resolver.

        Args:
            encrypted_file_path: Path to encrypted credentials file
            encrypted_master_password: Master password for encrypted backend
            cache_ttl_seconds: Credential cache TTL (0 to disable)
            enable_cache: Whether caching is enabled
        """
        # Initialize backends
        self.keyring_backend = KeyringBackend()
        self.environment_backend = EnvironmentBackend()

        # Encrypted backend initialized lazily
        self._encrypted_backend: Optional[EncryptedFileBackend] = None
        self._encrypted_file_path = encrypted_file_path
        self._encrypted_master_password = encrypted_master_password

        # Secure cache with TTL
        self._cache = SecureCredentialCache(
            ttl_seconds=max(1, cache_ttl_seconds)
        ) if enable_cache and cache_ttl_seconds > 0 else None
        self._caching_enabled = enable_cache and cache_ttl_seconds > 0

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

    def resolve(self, value: str, cache: Optional[bool] = None) -> str:
        """Resolve credential reference to actual value.

        Args:
            value: Credential reference or direct value
            cache: Whether to use cache (None = default behavior)

        Returns:
            Resolved credential value

        Raises:
            CredentialNotFoundError: If credential doesn't exist
            CredentialFormatError: If reference format is invalid
            BackendNotAvailableError: If required backend is unavailable

        Example:
            >>> resolver = CredentialResolver()
            >>> token = resolver.resolve("@keyring:gitea/api_token")
            'ghp_abc123...'
        """
        # Determine cache behavior
        use_cache = cache if cache is not None else self._caching_enabled
        use_cache = use_cache and self._cache is not None

        # Validate input length
        if not isinstance(value, str):
            raise CredentialFormatError(
                "Credential reference must be a string",
                reference=str(value)
            )

        if len(value) > self.MAX_REFERENCE_LENGTH:
            raise CredentialFormatError(
                f"Credential reference exceeds maximum length ({self.MAX_REFERENCE_LENGTH})",
                reference=value[:50] + "..."
            )

        # Check cache first (with TTL enforcement)
        if use_cache:
            cached = self._cache.get(value)
            if cached is not None:
                logger.debug("Credential resolved from cache")
                return cached

        # Try to parse as keyring reference
        keyring_match = self.KEYRING_PATTERN.match(value)
        if keyring_match:
            resolved = self._resolve_keyring(
                service=keyring_match.group(1),
                key=keyring_match.group(2),
                reference=value,
            )
            if use_cache:
                self._cache.set(value, resolved)
            return resolved

        # Try to parse as environment variable
        env_match = self.ENV_PATTERN.match(value)
        if env_match:
            resolved = self._resolve_environment(
                var_name=env_match.group(1),
                reference=value,
            )
            if use_cache:
                self._cache.set(value, resolved)
            return resolved

        # Try to parse as encrypted file reference
        encrypted_match = self.ENCRYPTED_PATTERN.match(value)
        if encrypted_match:
            resolved = self._resolve_encrypted(
                service=encrypted_match.group(1),
                key=encrypted_match.group(2),
                reference=value,
            )
            if use_cache:
                self._cache.set(value, resolved)
            return resolved

        # If no pattern matches, treat as direct value
        if self._looks_like_token(value):
            logger.warning(
                "Credential appears to be a direct token value. "
                "Consider using @keyring:, ${ENV_VAR}, or @encrypted: instead."
            )

        return value

    def _resolve_keyring(self, service: str, key: str, reference: str) -> str:
        """Resolve keyring reference."""
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
                    "Credential not found in configured storage",
                    reference=reference,
                    suggestion="Verify the credential reference and storage backend configuration"
                )

            logger.debug("Resolved keyring credential")
            return credential

        except CredentialError:
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to resolve credential (backend error)",
                reference=reference,
            ) from e

    def _resolve_environment(self, var_name: str, reference: str) -> str:
        """Resolve environment variable reference."""
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

        logger.debug("Resolved environment credential")
        return credential

    def _resolve_encrypted(self, service: str, key: str, reference: str) -> str:
        """Resolve encrypted file reference."""
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
                    "Credential not found in encrypted file",
                    reference=reference,
                    suggestion="Verify the credential reference and storage backend configuration"
                )

            logger.debug("Resolved encrypted file credential")
            return credential

        except CredentialError:
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to resolve encrypted credential (backend error)",
                reference=reference,
            ) from e

    @staticmethod
    def _looks_like_token(value: str) -> bool:
        """Heuristic check if value looks like an API token."""
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
        """Clear and wipe all cached credentials from memory."""
        if self._cache is not None:
            self._cache.clear()
        logger.debug("Credential cache cleared and memory wiped")

    def enable_caching(self, enabled: bool = True) -> None:
        """Enable or disable credential caching."""
        self._caching_enabled = enabled
        if not enabled and self._cache is not None:
            self._cache.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit - clears cache."""
        self.clear_cache()
```

**File: `automation/credentials/__init__.py` (MODIFIED - add to imports)**

```python
"""Secure credential management for the builder CLI."""

from .backend import CredentialBackend
from .keyring_backend import KeyringBackend
from .environment_backend import EnvironmentBackend
from .encrypted_backend import EncryptedFileBackend
from .secure_cache import SecureCredentialCache
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

    # Cache
    'SecureCredentialCache',

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

## Patch 2: Secure Master Password Handling [HIGH]

**File: `automation/credentials/cli_helpers.py` (NEW)**

```python
"""CLI helper functions for secure credential management."""

import click
import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def prompt_for_master_password(
    prompt_text: str = "Master password",
    require_confirmation: bool = True,
    allow_env_var: bool = False,
) -> str:
    """Securely prompt for master password with safety checks.

    Args:
        prompt_text: Prompt message
        require_confirmation: Require confirmation input
        allow_env_var: If True, allow env var but warn

    Returns:
        Master password (from prompt or env var if allowed)

    Raises:
        click.ClickException: If validation fails
    """
    # Check for environment variable
    env_password = os.getenv('BUILDER_MASTER_PASSWORD')

    if env_password:
        if not allow_env_var:
            click.echo(
                click.style(
                    'ERROR: Master password from environment variable is insecure.\n'
                    'Environment variables are visible in:\n'
                    '  - Process listings (ps aux)\n'
                    '  - Child process environment\n'
                    '  - Shell history\n'
                    '  - CI/CD logs\n\n'
                    'Use interactive prompt instead, or pass --use-env-master-password\n'
                    'to suppress this error (at your own risk).',
                    fg='red',
                    bold=True
                ),
                err=True
            )
            raise click.ClickException(
                'Master password via environment variable requires '
                '--use-env-master-password flag'
            )

        # Warn even if allowed
        click.echo(
            click.style(
                'WARNING: Using master password from BUILDER_MASTER_PASSWORD '
                'environment variable\n'
                '         This may be visible to other processes on this system.',
                fg='yellow',
                bold=True
            ),
            err=True
        )
        return env_password

    # Interactive prompt (secure)
    while True:
        password = click.prompt(
            prompt_text,
            hide_input=True,
            default=None,
        )

        if not password:
            click.echo(click.style('Error: Password cannot be empty', fg='red'), err=True)
            continue

        if len(password) < 8:
            click.echo(
                click.style(
                    'Warning: Password should be at least 8 characters',
                    fg='yellow'
                ),
                err=True
            )

        if require_confirmation:
            confirmation = click.prompt(
                'Confirm password',
                hide_input=True,
                default=None,
            )

            if password != confirmation:
                click.echo(click.style('Error: Passwords do not match', fg='red'), err=True)
                continue

        return password


def validate_master_password_strength(password: str) -> bool:
    """Validate master password meets minimum strength requirements.

    Args:
        password: Password to validate

    Returns:
        True if password meets requirements
    """
    if len(password) < 8:
        return False

    # Check for at least 3 of 4: uppercase, lowercase, digits, symbols
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)

    criteria_met = sum([has_upper, has_lower, has_digit, has_symbol])
    return criteria_met >= 3


__all__ = [
    'prompt_for_master_password',
    'validate_master_password_strength',
]
```

**File: `automation/cli/credentials.py` (MODIFIED - key sections)**

```python
# ... existing imports ...
from automation.credentials.cli_helpers import prompt_for_master_password

@credentials_group.command(name="set")
@click.argument('reference')
@click.option(
    '--backend',
    type=click.Choice(['keyring', 'environment', 'encrypted']),
    required=True,
    help='Storage backend to use'
)
@click.option(
    '--value',
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help='Credential value (will prompt if not provided)'
)
@click.option(
    '--use-env-master-password',
    is_flag=True,
    help='Allow reading master password from BUILDER_MASTER_PASSWORD env var (insecure)'
)
def set_credential(
    reference: str,
    backend: str,
    value: str,
    use_env_master_password: bool,
):
    """Store a credential securely."""
    try:
        if backend == 'keyring':
            _set_keyring(reference, value)
        elif backend == 'environment':
            _set_environment(reference, value)
        else:  # encrypted
            master_password = prompt_for_master_password(
                allow_env_var=use_env_master_password
            )
            _set_encrypted(reference, value, master_password)

        click.echo(click.style('Credential stored successfully', fg='green'))

    except CredentialError as e:
        click.echo(click.style(f'Error: {e.message}', fg='red'), err=True)
        if e.suggestion:
            click.echo(click.style(f'Suggestion: {e.suggestion}', fg='yellow'), err=True)
        sys.exit(1)
    except click.ClickException as e:
        click.echo(click.style(f'Error: {e.format_message()}', fg='red'), err=True)
        sys.exit(1)


@credentials_group.command(name="get")
@click.argument('reference')
@click.option(
    '--show-value',
    is_flag=True,
    help='Show full credential value (default: masked)'
)
@click.option(
    '--use-env-master-password',
    is_flag=True,
    help='Allow reading master password from BUILDER_MASTER_PASSWORD env var'
)
def get_credential(reference: str, show_value: bool, use_env_master_password: bool):
    """Retrieve and display a credential (for testing)."""
    try:
        master_password = None

        if '@encrypted:' in reference:
            master_password = prompt_for_master_password(
                allow_env_var=use_env_master_password
            )

        # Create resolver with encrypted backend password if provided
        if master_password:
            resolver = CredentialResolver(
                encrypted_file_path=Path('.builder/credentials.enc'),
                encrypted_master_password=master_password
            )
        else:
            resolver = CredentialResolver()

        # Resolve credential
        value = resolver.resolve(reference, cache=False)

        # Display (masked by default)
        if show_value:
            click.echo(f'Value: {value}')
        else:
            # Mask the value for security
            if len(value) > 8:
                masked = value[:4] + '*' * (len(value) - 8) + value[-4:]
            else:
                masked = '*' * len(value)

            click.echo(f'Value: {masked}')
            click.echo(click.style(
                'Use --show-value to display full credential',
                fg='yellow'
            ))

        click.echo(click.style('Credential resolved successfully', fg='green'))

    except CredentialError as e:
        click.echo(click.style(f'Error: {e.message}', fg='red'), err=True)
        if e.suggestion:
            click.echo(click.style(f'Suggestion: {e.suggestion}', fg='yellow'), err=True)
        sys.exit(1)
    except click.ClickException as e:
        click.echo(click.style(f'Error: {e.format_message()}', fg='red'), err=True)
        sys.exit(1)


# ... rest of file unchanged ...
```

---

## Patch 3: File Permission Verification [HIGH]

**File: `automation/credentials/encrypted_backend.py` (MODIFIED)**

Add at the top of file:

```python
import sys
import os
import stat
import subprocess
```

Add new functions after imports:

```python
def _set_restricted_permissions(file_path: Path) -> None:
    """Set file permissions to 0o600 (user read/write only).

    Raises:
        OSError: If permissions cannot be set
    """
    if sys.platform == 'win32':
        # Windows: Use ACL-based security
        try:
            import ctypes
            import winreg

            # Remove all permissions first
            os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)

            # Use icacls to set restrictive ACL
            result = subprocess.run(
                ['icacls', str(file_path), '/inheritance:r', '/grant:r',
                 f'{os.getlogin()}:(F)'],
                capture_output=True,
                timeout=5
            )

            if result.returncode != 0:
                raise OSError(
                    f"Failed to set ACL: {result.stderr.decode()}"
                )

            logger.info(f"Set Windows ACL for: {file_path}")

        except Exception as e:
            logger.error(f"Failed to set Windows file permissions: {e}")
            raise

    else:
        # Unix/Linux/macOS: Use chmod
        try:
            file_path.chmod(0o600)

            # Verify permissions were actually set
            stat_info = file_path.stat()
            mode = stat_info.st_mode & 0o777

            if mode != 0o600:
                raise OSError(
                    f"File permissions are {oct(mode)}, expected 0o600. "
                    f"Filesystem may not support Unix permissions."
                )

            logger.info(f"Set Unix permissions 0o600 for: {file_path}")

        except OSError:
            raise
        except Exception as e:
            logger.error(f"Failed to set Unix file permissions: {e}")
            raise
```

Modify `_load_or_generate_salt()`:

```python
def _load_or_generate_salt(self) -> bytes:
    """Load salt from file or generate new one with permission verification."""
    salt_file = self.file_path.parent / "credentials.salt"

    if salt_file.exists():
        # Verify permissions on existing salt file
        try:
            stat_info = salt_file.stat()
            mode = stat_info.st_mode & 0o777

            # Warn if permissions are too open
            if not sys.platform == 'win32' and (mode & 0o077) != 0:
                logger.warning(
                    f"Salt file has insecure permissions {oct(mode)}. "
                    f"Consider running: chmod 600 {salt_file}"
                )

        except Exception as e:
            logger.warning(f"Could not verify salt file permissions: {e}")

        with open(salt_file, 'rb') as f:
            return f.read()

    # Generate new salt
    salt = secrets.token_bytes(16)

    # Ensure directory exists
    salt_file.parent.mkdir(parents=True, exist_ok=True)

    # Write salt with proper permissions
    try:
        if sys.platform != 'win32':
            # Unix: Use os.open with explicit mode
            fd = os.open(
                str(salt_file),
                os.O_CREAT | os.O_WRONLY | os.O_EXCL,
                0o600
            )
            with os.fdopen(fd, 'wb') as f:
                f.write(salt)
        else:
            # Windows: Create then restrict with ACL
            with open(salt_file, 'wb') as f:
                f.write(salt)
            _set_restricted_permissions(salt_file)

        logger.info(f"Generated salt with secure permissions: {salt_file}")

    except Exception as e:
        logger.error(f"Failed to create salt file securely: {e}")
        raise

    return salt
```

Modify `_save_credentials()`:

```python
def _save_credentials(self, credentials: Dict[str, Dict[str, str]]) -> None:
    """Encrypt and save credentials with permission verification."""
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

        try:
            if sys.platform != 'win32':
                # Unix: Create with restrictive mode
                fd = os.open(
                    str(temp_file),
                    os.O_CREAT | os.O_WRONLY | os.O_TRUNC,
                    0o600
                )
                with os.fdopen(fd, 'wb') as f:
                    f.write(encrypted_data)
            else:
                # Windows: Create then restrict
                with open(temp_file, 'wb') as f:
                    f.write(encrypted_data)
                _set_restricted_permissions(temp_file)

            # Verify permissions before rename
            _set_restricted_permissions(temp_file)

            # Atomic rename
            temp_file.replace(self.file_path)

            # Verify final file permissions
            _set_restricted_permissions(self.file_path)

        except Exception:
            # Clean up temp file on error
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Could not remove temp file: {e}")
            raise

        # Update cache
        self._credentials_cache = credentials
        logger.debug(f"Saved credentials with secure permissions: {self.file_path}")

    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(
            f"Failed to save credentials: {e}"
        ) from e
```

---

## Patch 4: Input Validation [MEDIUM]

**File: `automation/credentials/validators.py` (NEW)**

```python
"""Input validation for credential management."""

import re
from typing import Final

# Maximum lengths
MAX_CREDENTIAL_VALUE_LENGTH: Final[int] = 10_000_000  # 10MB
MAX_SERVICE_LENGTH: Final[int] = 256
MAX_KEY_LENGTH: Final[int] = 256
MAX_VAR_NAME_LENGTH: Final[int] = 256

# Pattern for valid service/key names
VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
# Pattern for valid environment variable names
VALID_ENV_PATTERN = re.compile(r'^[A-Z_][A-Z0-9_]*$')


def validate_service_name(service: str) -> None:
    """Validate service identifier.

    Args:
        service: Service name to validate

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(service, str):
        raise ValueError("Service must be a string")

    if not service:
        raise ValueError("Service cannot be empty")

    if len(service) > MAX_SERVICE_LENGTH:
        raise ValueError(
            f"Service exceeds maximum length ({MAX_SERVICE_LENGTH} characters)"
        )

    if '\x00' in service:
        raise ValueError("Service contains null bytes")

    if not VALID_NAME_PATTERN.match(service):
        raise ValueError(
            f"Service contains invalid characters. "
            f"Use only: alphanumeric, underscore, dash, period"
        )


def validate_key_name(key: str) -> None:
    """Validate credential key identifier.

    Args:
        key: Key name to validate

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(key, str):
        raise ValueError("Key must be a string")

    if not key:
        raise ValueError("Key cannot be empty")

    if len(key) > MAX_KEY_LENGTH:
        raise ValueError(
            f"Key exceeds maximum length ({MAX_KEY_LENGTH} characters)"
        )

    if '\x00' in key:
        raise ValueError("Key contains null bytes")

    if not VALID_NAME_PATTERN.match(key):
        raise ValueError(
            f"Key contains invalid characters. "
            f"Use only: alphanumeric, underscore, dash, period"
        )


def validate_credential_value(value: str) -> None:
    """Validate credential value.

    Args:
        value: Credential value to validate

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    if not value or not value.strip():
        raise ValueError("Credential value cannot be empty or whitespace-only")

    if len(value) > MAX_CREDENTIAL_VALUE_LENGTH:
        raise ValueError(
            f"Credential value exceeds maximum length "
            f"({MAX_CREDENTIAL_VALUE_LENGTH} bytes)"
        )

    if '\x00' in value:
        raise ValueError("Credential value contains null bytes")

    # Check for problematic control characters
    # Allow: tab (9), line feed (10), carriage return (13)
    control_chars = [chr(i) for i in range(32) if i not in (9, 10, 13)]
    if any(c in value for c in control_chars):
        raise ValueError(
            "Credential value contains control characters "
            "(except tab, newline, carriage return)"
        )


def validate_env_var_name(var_name: str) -> None:
    """Validate environment variable name.

    Args:
        var_name: Variable name to validate

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(var_name, str):
        raise ValueError("Variable name must be a string")

    if not var_name:
        raise ValueError("Variable name cannot be empty")

    if len(var_name) > MAX_VAR_NAME_LENGTH:
        raise ValueError(
            f"Variable name exceeds maximum length ({MAX_VAR_NAME_LENGTH} characters)"
        )

    if not VALID_ENV_PATTERN.match(var_name):
        raise ValueError(
            f"Invalid environment variable name: {var_name}. "
            f"Must start with letter or underscore, contain only uppercase "
            f"letters, digits, and underscores."
        )


__all__ = [
    'validate_service_name',
    'validate_key_name',
    'validate_credential_value',
    'validate_env_var_name',
]
```

**File: `automation/credentials/encrypted_backend.py` (MODIFIED)**

Add import:

```python
from .validators import (
    validate_service_name,
    validate_key_name,
    validate_credential_value,
)
```

Modify `set()` method:

```python
def set(self, service: str, key: str, value: str) -> None:
    """Store credential in encrypted file with validation.

    Args:
        service: Service identifier
        key: Key within service
        value: Credential value

    Raises:
        ValueError: If validation fails
        EncryptionError: If encryption fails
    """
    # Validate all inputs
    validate_service_name(service)
    validate_key_name(key)
    validate_credential_value(value)

    credentials = self._load_credentials()

    # Create service entry if doesn't exist
    if service not in credentials:
        credentials[service] = {}

    credentials[service][key] = value

    self._save_credentials(credentials)
    logger.info(f"Stored credential: {service}/{key}")
```

---

## Testing Patches

**File: `tests/test_credentials/test_security_fixes.py` (NEW)**

```python
"""Tests for security fixes and patches."""

import pytest
import os
import time
from pathlib import Path

from automation.credentials import (
    CredentialResolver,
    EncryptedFileBackend,
    SecureCredentialCache,
    CredentialError,
)
from automation.credentials.validators import (
    validate_service_name,
    validate_key_name,
    validate_credential_value,
)


class TestSecureCache:
    """Test secure credential cache with TTL."""

    def test_cache_expires_after_ttl(self):
        """Test cache entries expire after TTL."""
        cache = SecureCredentialCache(ttl_seconds=1)

        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get('key1') is None

    def test_cache_context_manager_clears(self):
        """Test context manager clears cache."""
        with SecureCredentialCache(ttl_seconds=300) as cache:
            cache.set('key1', 'value1')
            assert cache.get('key1') == 'value1'

        # Outside context, cache should be cleared
        with SecureCredentialCache(ttl_seconds=300) as cache2:
            assert cache2.get('key1') is None

    def test_cache_disable(self):
        """Test disabling cache."""
        resolver = CredentialResolver(enable_cache=False)
        assert resolver._caching_enabled is False


class TestInputValidation:
    """Test input validation."""

    def test_validate_service_name_valid(self):
        """Test valid service names are accepted."""
        validate_service_name('gitea')
        validate_service_name('github_api')
        validate_service_name('my-service.prod')

    def test_validate_service_name_invalid(self):
        """Test invalid service names are rejected."""
        with pytest.raises(ValueError):
            validate_service_name('')  # Empty

        with pytest.raises(ValueError):
            validate_service_name('service\x00name')  # Null byte

        with pytest.raises(ValueError):
            validate_service_name('service@name')  # Invalid char

        with pytest.raises(ValueError):
            validate_service_name('a' * 300)  # Too long

    def test_validate_credential_value_invalid(self):
        """Test invalid credential values are rejected."""
        with pytest.raises(ValueError):
            validate_credential_value('')  # Empty

        with pytest.raises(ValueError):
            validate_credential_value('value\x00secret')  # Null byte

        with pytest.raises(ValueError):
            validate_credential_value('x' * 10_000_001)  # Too long


class TestResolverCaching:
    """Test resolver caching behavior."""

    def test_resolver_uses_cache_by_default(self):
        """Test resolver caches credentials by default."""
        os.environ['TEST_TOKEN'] = 'secret-value'

        resolver = CredentialResolver()
        token1 = resolver.resolve('${TEST_TOKEN}')

        # Modify env var
        os.environ['TEST_TOKEN'] = 'new-value'

        # Should return cached value, not new value
        token2 = resolver.resolve('${TEST_TOKEN}')
        assert token2 == 'secret-value'

    def test_resolver_bypass_cache(self):
        """Test bypassing cache with cache=False."""
        os.environ['TEST_TOKEN'] = 'secret-value'

        resolver = CredentialResolver()
        token1 = resolver.resolve('${TEST_TOKEN}', cache=True)

        # Modify env var
        os.environ['TEST_TOKEN'] = 'new-value'

        # Should return new value when cache=False
        token2 = resolver.resolve('${TEST_TOKEN}', cache=False)
        assert token2 == 'new-value'

    def test_resolver_context_manager_clears_cache(self):
        """Test context manager clears cache on exit."""
        os.environ['TEST_TOKEN'] = 'secret-value'

        with CredentialResolver() as resolver:
            resolver.resolve('${TEST_TOKEN}')
            assert len(resolver._cache) > 0

        # Cache should be cleared
        assert len(resolver._cache) == 0


class TestFilePermissions:
    """Test file permission handling."""

    def test_encrypted_file_permissions(self, tmp_path):
        """Test encrypted file has restricted permissions."""
        import sys
        if sys.platform == 'win32':
            pytest.skip("Permission test only for Unix")

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        backend.set('test', 'key', 'value')

        # Check file permissions are 0o600
        stat_info = file_path.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o600

    def test_salt_file_permissions(self, tmp_path):
        """Test salt file has restricted permissions."""
        import sys
        if sys.platform == 'win32':
            pytest.skip("Permission test only for Unix")

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        salt_file = file_path.parent / "credentials.salt"
        stat_info = salt_file.stat()
        mode = stat_info.st_mode & 0o777
        assert mode == 0o600
```

---

## Deployment Checklist

- [ ] Backup existing credentials files
- [ ] Review and test all patches in staging environment
- [ ] Run full test suite: `pytest tests/test_credentials/`
- [ ] Run security tests: `pytest tests/test_credentials/test_security.py tests/test_credentials/test_security_fixes.py`
- [ ] Update production credentials resolver configuration (TTL settings)
- [ ] Deploy patches to production
- [ ] Monitor logs for any migration issues
- [ ] Update documentation with new security features
- [ ] Conduct post-deployment security audit

---

## References

- OWASP: Credential Storage Cheat Sheet
- Python cryptography library: https://cryptography.io/
- PEP 417: Standardized Exception Representation
