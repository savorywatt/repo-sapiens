"""Tests for keyring backend."""

from unittest.mock import MagicMock, patch

import pytest

from repo_sapiens.credentials import BackendNotAvailableError, CredentialError, KeyringBackend


class TestKeyringBackend:
    """Test KeyringBackend functionality."""

    @pytest.fixture
    def backend(self):
        """Create KeyringBackend instance."""
        return KeyringBackend()

    def test_backend_name(self, backend):
        """Test backend name property."""
        assert backend.name == "keyring"

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_available_when_keyring_installed(self, mock_keyring, backend):
        """Test backend reports available when keyring is installed."""
        mock_keyring.get_keyring.return_value = MagicMock()

        assert backend.available is True

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False)
    def test_unavailable_when_keyring_not_installed(self):
        """Test backend reports unavailable when keyring not installed."""
        backend = KeyringBackend()

        assert backend.available is False

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_unavailable_when_keyring_fails(self, mock_keyring):
        """Test backend reports unavailable when keyring fails to initialize."""
        mock_keyring.get_keyring.side_effect = Exception("Keyring failed")
        backend = KeyringBackend()

        assert backend.available is False

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_get_credential_success(self, mock_keyring, backend):
        """Test successful credential retrieval."""
        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.get_password.return_value = "test-token"

        result = backend.get("gitea", "api_token")

        assert result == "test-token"
        mock_keyring.get_password.assert_called_once_with("builder/gitea", "api_token")

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_get_credential_not_found(self, mock_keyring, backend):
        """Test credential not found returns None."""
        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.get_password.return_value = None

        result = backend.get("gitea", "api_token")

        assert result is None

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False)
    def test_get_raises_when_unavailable(self):
        """Test get raises BackendNotAvailableError when unavailable."""
        backend = KeyringBackend()

        with pytest.raises(BackendNotAvailableError) as exc_info:
            backend.get("gitea", "api_token")

        assert "not available" in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_get_raises_on_keyring_error(self, mock_keyring, backend):
        """Test get raises CredentialError on keyring failure."""
        from keyring.errors import KeyringError

        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.get_password.side_effect = KeyringError("Test error")

        with pytest.raises(CredentialError) as exc_info:
            backend.get("gitea", "api_token")

        assert "Keyring operation failed" in str(exc_info.value)
        assert exc_info.value.reference == "@keyring:gitea/api_token"

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_set_credential(self, mock_keyring, backend):
        """Test credential storage."""
        mock_keyring.get_keyring.return_value = MagicMock()

        backend.set("gitea", "api_token", "new-token")

        mock_keyring.set_password.assert_called_once_with("builder/gitea", "api_token", "new-token")

    def test_set_empty_value_raises_error(self, backend):
        """Test that empty values are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            backend.set("gitea", "api_token", "")

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False)
    def test_set_raises_when_unavailable(self):
        """Test set raises BackendNotAvailableError when unavailable."""
        backend = KeyringBackend()

        with pytest.raises(BackendNotAvailableError):
            backend.set("gitea", "api_token", "token")

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_set_raises_on_keyring_error(self, mock_keyring, backend):
        """Test set raises CredentialError on keyring failure."""
        from keyring.errors import KeyringError

        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.set_password.side_effect = KeyringError("Test error")

        with pytest.raises(CredentialError) as exc_info:
            backend.set("gitea", "api_token", "token")

        assert "Failed to store credential" in str(exc_info.value)

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_delete_credential_success(self, mock_keyring, backend):
        """Test successful credential deletion."""
        mock_keyring.get_keyring.return_value = MagicMock()

        result = backend.delete("gitea", "api_token")

        assert result is True
        mock_keyring.delete_password.assert_called_once_with("builder/gitea", "api_token")

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_delete_credential_not_found(self, mock_keyring, backend):
        """Test delete returns False when credential not found."""
        from keyring.errors import PasswordDeleteError

        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.delete_password.side_effect = PasswordDeleteError("Not found")

        result = backend.delete("gitea", "api_token")

        assert result is False

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False)
    def test_delete_raises_when_unavailable(self):
        """Test delete raises BackendNotAvailableError when unavailable."""
        backend = KeyringBackend()

        with pytest.raises(BackendNotAvailableError):
            backend.delete("gitea", "api_token")

    @patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True)
    @patch("repo_sapiens.credentials.keyring_backend.keyring")
    def test_delete_raises_on_keyring_error(self, mock_keyring, backend):
        """Test delete raises CredentialError on keyring failure."""
        from keyring.errors import KeyringError

        mock_keyring.get_keyring.return_value = MagicMock()
        mock_keyring.delete_password.side_effect = KeyringError("Test error")

        with pytest.raises(CredentialError) as exc_info:
            backend.delete("gitea", "api_token")

        assert "Failed to delete credential" in str(exc_info.value)
