"""Tests for credential exceptions."""

from repo_sapiens.credentials.exceptions import (
    BackendNotAvailableError,
    CredentialError,
    CredentialFormatError,
    CredentialNotFoundError,
    EncryptionError,
)


class TestCredentialExceptions:
    """Test credential exception hierarchy."""

    def test_credential_error_basic(self):
        """Test basic CredentialError instantiation."""
        error = CredentialError("Test error")

        assert error.message == "Test error"
        assert error.reference is None
        assert error.suggestion is None
        assert str(error) == "Test error"

    def test_credential_error_with_reference(self):
        """Test CredentialError with reference."""
        error = CredentialError("Test error", reference="@keyring:service/key")

        assert error.message == "Test error"
        assert error.reference == "@keyring:service/key"
        assert "@keyring:service/key" in str(error)

    def test_credential_error_with_suggestion(self):
        """Test CredentialError with suggestion."""
        error = CredentialError("Test error", reference="@keyring:service/key", suggestion="Try installing keyring")

        assert error.message == "Test error"
        assert error.suggestion == "Try installing keyring"
        assert "Suggestion:" in str(error)

    def test_credential_not_found_error(self):
        """Test CredentialNotFoundError is subclass."""
        error = CredentialNotFoundError("Not found")

        assert isinstance(error, CredentialError)
        assert error.message == "Not found"

    def test_credential_format_error(self):
        """Test CredentialFormatError is subclass."""
        error = CredentialFormatError("Invalid format")

        assert isinstance(error, CredentialError)
        assert error.message == "Invalid format"

    def test_backend_not_available_error(self):
        """Test BackendNotAvailableError is subclass."""
        error = BackendNotAvailableError("Backend unavailable")

        assert isinstance(error, CredentialError)
        assert error.message == "Backend unavailable"

    def test_encryption_error(self):
        """Test EncryptionError is subclass."""
        error = EncryptionError("Encryption failed")

        assert isinstance(error, CredentialError)
        assert error.message == "Encryption failed"

    def test_exception_inheritance(self):
        """Test all custom exceptions inherit from Exception."""
        assert issubclass(CredentialError, Exception)
        assert issubclass(CredentialNotFoundError, Exception)
        assert issubclass(CredentialFormatError, Exception)
        assert issubclass(BackendNotAvailableError, Exception)
        assert issubclass(EncryptionError, Exception)
