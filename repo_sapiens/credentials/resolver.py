"""High-level credential resolution with automatic backend selection."""

import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .backend import CredentialBackend
from .encrypted_backend import EncryptedFileBackend
from .environment_backend import EnvironmentBackend
from .exceptions import (
    BackendNotAvailableError,
    CredentialError,
    CredentialNotFoundError,
)
from .keyring_backend import KeyringBackend

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
    KEYRING_PATTERN = re.compile(r"^@keyring:([^/]+)/(.+)$")
    ENV_PATTERN = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")
    ENCRYPTED_PATTERN = re.compile(r"^@encrypted:([^/]+)/(.+)$")

    def __init__(
        self,
        encrypted_file_path: Path | None = None,
        encrypted_master_password: str | None = None,
        backends: Sequence[CredentialBackend] | None = None,
    ) -> None:
        """Initialize credential resolver.

        Args:
            encrypted_file_path: Path to encrypted credentials file
            encrypted_master_password: Master password for encrypted backend
            backends: Optional sequence of custom backends to use instead of
                the default backends. When provided, only these backends will
                be used for resolution (via the `backends` property). The
                sequence is converted to a tuple for immutability.
        """
        # Initialize default backends
        self.keyring_backend = KeyringBackend()
        self.environment_backend = EnvironmentBackend()

        # Encrypted backend initialized lazily
        self._encrypted_backend: EncryptedFileBackend | None = None
        self._encrypted_file_path = encrypted_file_path
        self._encrypted_master_password = encrypted_master_password

        # Store custom backends as immutable tuple (if provided)
        self._custom_backends: tuple[CredentialBackend, ...] | None = (
            tuple(backends) if backends else None
        )

        # Cache for resolved credentials (reduces backend calls)
        self._cache: dict[str, str] = {}

    @property
    def encrypted_backend(self) -> EncryptedFileBackend:
        """Lazy initialization of encrypted file backend."""
        if self._encrypted_backend is None:
            file_path = self._encrypted_file_path or Path(".builder/credentials.enc")
            self._encrypted_backend = EncryptedFileBackend(
                file_path=file_path,
                master_password=self._encrypted_master_password,
            )
        return self._encrypted_backend

    @property
    def backends(self) -> tuple[CredentialBackend, ...]:
        """Return active backends in resolution order.

        Returns:
            Tuple of backends to use for credential resolution. If custom
            backends were provided at initialization, returns those;
            otherwise returns the default backends (environment, keyring,
            encrypted) in standard resolution order.
        """
        if self._custom_backends is not None:
            return self._custom_backends
        # Cast to satisfy mypy - these are all CredentialBackend implementations
        return cast(
            tuple[CredentialBackend, ...],
            (self.environment_backend, self.keyring_backend, self.encrypted_backend),
        )

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

        # Parse reference format to determine backend type and parameters
        keyring_match = self.KEYRING_PATTERN.match(value)
        env_match = self.ENV_PATTERN.match(value)
        encrypted_match = self.ENCRYPTED_PATTERN.match(value)

        # Route to appropriate resolution based on reference format
        resolved: str | None = None

        if keyring_match:
            resolved = self._resolve_via_backends(
                backend_name="keyring",
                service=keyring_match.group(1),
                key=keyring_match.group(2),
                reference=value,
            )
        elif env_match:
            resolved = self._resolve_via_backends(
                backend_name="environment",
                service=env_match.group(1),
                key=None,
                reference=value,
            )
        elif encrypted_match:
            resolved = self._resolve_via_backends(
                backend_name="encrypted",
                service=encrypted_match.group(1),
                key=encrypted_match.group(2),
                reference=value,
            )

        if resolved is not None:
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

    def _resolve_via_backends(
        self,
        backend_name: str,
        service: str,
        key: str | None,
        reference: str,
    ) -> str:
        """Resolve credential by iterating through configured backends.

        Args:
            backend_name: Target backend name ('keyring', 'environment', 'encrypted')
            service: Service identifier or variable name
            key: Key within service (None for environment backend)
            reference: Original reference string for error messages

        Returns:
            Resolved credential value

        Raises:
            CredentialNotFoundError: If credential doesn't exist
            BackendNotAvailableError: If required backend is unavailable
        """
        for backend in self.backends:
            # Match backend by name property
            backend_matches = False
            if hasattr(backend, "name"):
                backend_matches = backend.name == backend_name

            if not backend_matches:
                continue

            # Found matching backend - check availability
            if not backend.available:
                suggestions = {
                    "keyring": (
                        "Install keyring: pip install keyring\n"
                        "Or use environment variables: ${VAR_NAME}"
                    ),
                    "encrypted": "Install cryptography: pip install cryptography",
                    "environment": None,
                }
                backend_display = {
                    "keyring": "Keyring backend is not available on this system",
                    "encrypted": "Encrypted file backend is not available",
                    "environment": "Environment backend is not available",
                }
                raise BackendNotAvailableError(
                    backend_display.get(backend_name, f"{backend_name} backend is not available"),
                    reference=reference,
                    suggestion=suggestions.get(backend_name),
                )

            try:
                # Environment backend takes single arg, others take service/key
                if backend_name == "environment":
                    credential = backend.get(service)  # type: ignore[call-arg]
                else:
                    credential = backend.get(service, key)

                if credential is None:
                    # Use specific error messages matching original behavior
                    if backend_name == "environment":
                        raise CredentialNotFoundError(
                            f"Environment variable not set: {service}",
                            reference=reference,
                            suggestion=(
                                f"Set the environment variable:\n"
                                f"  export {service}='your-credential-here'"
                            ),
                        )
                    elif backend_name == "keyring":
                        raise CredentialNotFoundError(
                            f"Credential not found in keyring: {service}/{key}",
                            reference=reference,
                            suggestion=(
                                f"Store the credential with:\n"
                                f"  builder credentials set --keyring {service}/{key}"
                            ),
                        )
                    elif backend_name == "encrypted":
                        raise CredentialNotFoundError(
                            f"Credential not found in encrypted file: {service}/{key}",
                            reference=reference,
                            suggestion=(
                                f"Store the credential with:\n"
                                f"  builder credentials set --encrypted {service}/{key}"
                            ),
                        )

                log_key = f"{service}/{key}" if key else service
                logger.debug(f"Resolved {backend_name} credential: {log_key}")
                return credential

            except CredentialError:
                raise
            except Exception as e:
                raise CredentialError(
                    f"Failed to resolve {backend_name} credential: {e}",
                    reference=reference,
                ) from e

        # No matching backend found in the configured backends
        raise BackendNotAvailableError(
            f"No {backend_name} backend configured",
            reference=reference,
            suggestion=f"Ensure a {backend_name} backend is available in the resolver.",
        )

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
                ),
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
                    ),
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
                    f"Set the environment variable:\n  export {var_name}='your-credential-here'"
                ),
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
                suggestion="Install cryptography: pip install cryptography",
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
                    ),
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
        if value.startswith(("ghp_", "gho_", "ghu_", "ghs_", "ghr_")):
            return True

        # Long alphanumeric or base64-like
        return len(value) > 20 and value.replace("-", "").replace("_", "").isalnum()

    def clear_cache(self) -> None:
        """Clear resolved credentials cache.

        Use this when credentials may have been updated.
        """
        self._cache.clear()
        logger.debug("Credential cache cleared")
