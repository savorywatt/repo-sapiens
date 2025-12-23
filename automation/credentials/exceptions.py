"""Credential-related exceptions with detailed error context."""

from automation.exceptions import CredentialError as BaseCredentialError


class CredentialError(BaseCredentialError):
    """Base exception for all credential operations.

    Attributes:
        message: Human-readable error description
        reference: The credential reference that failed (e.g., "@keyring:service/key")
        suggestion: Optional suggestion for resolution
    """

    def __init__(
        self,
        message: str,
        reference: str | None = None,
        suggestion: str | None = None,
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
