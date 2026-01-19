"""Tests for encrypted file backend."""

import pytest
from cryptography.fernet import Fernet

from repo_sapiens.credentials import EncryptedFileBackend, EncryptionError


class TestEncryptedFileBackend:
    """Test EncryptedFileBackend functionality."""

    @pytest.fixture
    def temp_path(self, tmp_path):
        """Create temporary path for encrypted file."""
        return tmp_path / "credentials.enc"

    @pytest.fixture
    def backend(self, temp_path):
        """Create EncryptedFileBackend instance."""
        return EncryptedFileBackend(file_path=temp_path, master_password="test-password-123")

    def test_backend_name(self, backend):
        """Test backend name property."""
        assert backend.name == "encrypted_file"

    def test_backend_available(self, backend):
        """Test backend is available when cryptography installed."""
        assert backend.available is True

    def test_salt_generation(self, temp_path):
        """Test salt is generated and persisted."""
        _backend = EncryptedFileBackend(temp_path, "password")

        salt_file = temp_path.parent / "credentials.salt"
        assert salt_file.exists()
        assert len(salt_file.read_bytes()) == 16

    def test_salt_reuse(self, temp_path):
        """Test salt is reused across instances."""
        backend1 = EncryptedFileBackend(temp_path, "password")
        salt1 = backend1.salt

        backend2 = EncryptedFileBackend(temp_path, "password")
        salt2 = backend2.salt

        assert salt1 == salt2

    def test_get_from_empty_file(self, backend):
        """Test getting credential from non-existent file returns None."""
        result = backend.get("gitea", "api_token")

        assert result is None

    def test_set_and_get_credential(self, backend):
        """Test storing and retrieving credential."""
        backend.set("gitea", "api_token", "test-token")

        result = backend.get("gitea", "api_token")

        assert result == "test-token"

    def test_set_empty_value_raises_error(self, backend):
        """Test setting empty value raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            backend.set("gitea", "api_token", "")

    def test_file_created_on_set(self, backend, temp_path):
        """Test encrypted file is created on first set."""
        assert not temp_path.exists()

        backend.set("gitea", "api_token", "token")

        assert temp_path.exists()

    def test_file_permissions_unix(self, backend, temp_path):
        """Test file has restricted permissions on Unix."""
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission test only for Unix")

        backend.set("gitea", "api_token", "token")

        # Check file permissions are 0o600 (user read/write only)
        stat_info = temp_path.stat()
        assert stat_info.st_mode & 0o777 == 0o600

    def test_multiple_services(self, backend):
        """Test storing credentials for multiple services."""
        backend.set("gitea", "api_token", "gitea-token")
        backend.set("claude", "api_key", "claude-key")

        assert backend.get("gitea", "api_token") == "gitea-token"
        assert backend.get("claude", "api_key") == "claude-key"

    def test_multiple_keys_per_service(self, backend):
        """Test storing multiple keys per service."""
        backend.set("gitea", "api_token", "token")
        backend.set("gitea", "webhook_secret", "secret")

        assert backend.get("gitea", "api_token") == "token"
        assert backend.get("gitea", "webhook_secret") == "secret"

    def test_delete_credential(self, backend):
        """Test deleting credential."""
        backend.set("gitea", "api_token", "token")

        result = backend.delete("gitea", "api_token")

        assert result is True
        assert backend.get("gitea", "api_token") is None

    def test_delete_nonexistent_credential(self, backend):
        """Test deleting nonexistent credential returns False."""
        result = backend.delete("gitea", "api_token")

        assert result is False

    def test_delete_nonexistent_service(self, backend):
        """Test deleting from nonexistent service returns False."""
        backend.set("gitea", "api_token", "token")

        result = backend.delete("github", "api_token")

        assert result is False

    def test_delete_cleans_empty_service(self, backend):
        """Test deleting last key removes service entry."""
        backend.set("gitea", "api_token", "token")
        backend.delete("gitea", "api_token")

        # Verify service is removed from file
        credentials = backend._load_credentials()
        assert "gitea" not in credentials

    def test_persistence_across_instances(self, temp_path):
        """Test credentials persist across backend instances."""
        # First instance
        backend1 = EncryptedFileBackend(temp_path, "password")
        backend1.set("gitea", "api_token", "persistent-token")

        # Second instance (simulating restart)
        backend2 = EncryptedFileBackend(temp_path, "password")
        result = backend2.get("gitea", "api_token")

        assert result == "persistent-token"

    def test_wrong_password_fails(self, temp_path):
        """Test wrong password cannot decrypt credentials."""
        # Store with one password
        backend1 = EncryptedFileBackend(temp_path, "correct-password")
        backend1.set("gitea", "api_token", "secret-token")

        # Try to read with different password
        backend2 = EncryptedFileBackend(temp_path, "wrong-password")

        with pytest.raises(EncryptionError, match="Invalid master password"):
            backend2.get("gitea", "api_token")

    def test_no_plaintext_in_file(self, backend, temp_path):
        """Test credentials are encrypted in file."""
        secret = "super-secret-api-key-12345"
        backend.set("gitea", "api_token", secret)

        # Read raw file content
        with open(temp_path, "rb") as f:
            file_content = f.read()

        # Verify secret is not present in plaintext
        assert secret.encode("utf-8") not in file_content

    def test_atomic_writes(self, backend, temp_path):
        """Test file updates are atomic."""
        backend.set("gitea", "api_token", "token1")

        # Verify temp file is not left behind
        temp_file = temp_path.with_suffix(".tmp")
        assert not temp_file.exists()

    def test_caching(self, backend):
        """Test credentials are cached after loading."""
        backend.set("gitea", "api_token", "token")

        # First get loads from file
        backend.get("gitea", "api_token")

        # Cache should be populated
        assert backend._credentials_cache is not None
        assert "gitea" in backend._credentials_cache

    def test_cache_invalidation_on_set(self, backend):
        """Test cache is updated on set."""
        backend.set("gitea", "api_token", "token1")
        backend.get("gitea", "api_token")

        backend.set("gitea", "api_token", "token2")

        result = backend.get("gitea", "api_token")
        assert result == "token2"

    def test_no_password_raises_error(self, temp_path):
        """Test accessing encrypted file without password raises error."""
        # Create file with password
        backend1 = EncryptedFileBackend(temp_path, "password")
        backend1.set("gitea", "api_token", "token")

        # Try to access without password
        backend2 = EncryptedFileBackend(temp_path, master_password=None)

        with pytest.raises(EncryptionError, match="Master password not provided"):
            backend2.get("gitea", "api_token")

    def test_corrupted_json_raises_error(self, backend, temp_path):
        """Test corrupted JSON in file raises EncryptionError."""
        # Write invalid encrypted data
        backend.fernet = Fernet(Fernet.generate_key())
        encrypted = backend.fernet.encrypt(b"not-json")

        with open(temp_path, "wb") as f:
            f.write(encrypted)

        backend._credentials_cache = None  # Clear cache

        with pytest.raises(EncryptionError, match="corrupted"):
            backend.get("gitea", "api_token")

    def test_overwrite_existing_credential(self, backend):
        """Test overwriting existing credential."""
        backend.set("gitea", "api_token", "token1")
        backend.set("gitea", "api_token", "token2")

        result = backend.get("gitea", "api_token")
        assert result == "token2"
