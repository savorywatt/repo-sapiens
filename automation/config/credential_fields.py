"""Pydantic field types and validators for credential resolution.

This module provides custom field types and validators that automatically
resolve credential references when loading configuration.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, SecretStr
from pydantic_core import PydanticCustomError

from automation.credentials import CredentialResolver
from automation.credentials.exceptions import CredentialError

# Global resolver instance (can be configured per application)
_resolver: CredentialResolver | None = None


def get_resolver() -> CredentialResolver:
    """Get or create global credential resolver instance.

    Returns:
        CredentialResolver instance
    """
    global _resolver
    if _resolver is None:
        _resolver = CredentialResolver()
    return _resolver


def set_resolver(resolver: CredentialResolver) -> None:
    """Set custom credential resolver instance.

    Args:
        resolver: Custom CredentialResolver instance
    """
    global _resolver
    _resolver = resolver


def resolve_credential_string(value: Any) -> str:
    """Validator function to resolve credential references.

    Supports:
    - @keyring:service/key - OS keyring
    - ${VAR_NAME} - Environment variable
    - @encrypted:service/key - Encrypted file
    - Direct values (returned as-is)

    Args:
        value: Input value (can be credential reference or direct value)

    Returns:
        Resolved credential value

    Raises:
        PydanticCustomError: If credential resolution fails
    """
    if not isinstance(value, str):
        return value

    try:
        resolver = get_resolver()
        return resolver.resolve(value)
    except CredentialError as e:
        # Convert to Pydantic validation error
        error_msg = e.message
        if e.suggestion:
            error_msg = f"{error_msg}\n\nSuggestion: {e.suggestion}"

        raise PydanticCustomError(
            "credential_resolution_error", error_msg, {"reference": e.reference}
        ) from e


def resolve_credential_secret(value: Any) -> SecretStr:
    """Validator function to resolve credential references into SecretStr.

    Args:
        value: Input value (can be credential reference or direct value)

    Returns:
        SecretStr with resolved credential value

    Raises:
        PydanticCustomError: If credential resolution fails
    """
    if isinstance(value, SecretStr):
        return value

    if not isinstance(value, str):
        return SecretStr(str(value))

    # Resolve the credential
    resolved = resolve_credential_string(value)

    # Wrap in SecretStr
    return SecretStr(resolved)


# Type aliases for use in Pydantic models

# Resolves to plain string
CredentialStr = Annotated[str, BeforeValidator(resolve_credential_string)]

# Resolves to SecretStr (recommended for sensitive values)
CredentialSecret = Annotated[SecretStr, BeforeValidator(resolve_credential_secret)]


__all__ = [
    "CredentialStr",
    "CredentialSecret",
    "resolve_credential_string",
    "resolve_credential_secret",
    "get_resolver",
    "set_resolver",
]
