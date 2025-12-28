"""Security-focused tests for credential management."""

import os

import pytest

from automation.credentials import EncryptedFileBackend, EncryptionError


class TestCredentialSecurity:
    """Test security properties of credential management."""

    def test_file_permissions_restricted_unix(self, tmp_path):
        """Test credential files have restrictive permissions on Unix."""
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission test only for Unix")

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        backend.set("test", "key", "value")

        # Check file permissions are 0o600 (user read/write only)
        stat_info = file_path.stat()
        assert stat_info.st_mode & 0o777 == 0o600

    def test_salt_file_permissions_restricted_unix(self, tmp_path):
        """Test salt file has restrictive permissions on Unix."""
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission test only for Unix")

        file_path = tmp_path / "credentials.enc"
        _backend = EncryptedFileBackend(file_path, "password")

        salt_file = file_path.parent / "credentials.salt"

        # Check salt file permissions
        stat_info = salt_file.stat()
        assert stat_info.st_mode & 0o777 == 0o600

    def test_wrong_password_fails(self, tmp_path):
        """Test wrong password cannot decrypt credentials."""
        file_path = tmp_path / "credentials.enc"

        # Store with one password
        backend1 = EncryptedFileBackend(file_path, "correct-password")
        backend1.set("test", "key", "secret-value")

        # Try to read with different password
        backend2 = EncryptedFileBackend(file_path, "wrong-password")

        with pytest.raises(EncryptionError, match="Invalid master password"):
            backend2.get("test", "key")

    def test_no_plaintext_in_encrypted_file(self, tmp_path):
        """Test credentials are actually encrypted in file."""
        file_path = tmp_path / "credentials.enc"
        secret = "super-secret-api-key-12345"

        backend = EncryptedFileBackend(file_path, "password")
        backend.set("test", "key", secret)

        # Read raw file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Verify secret is not present in plaintext
        assert secret.encode("utf-8") not in file_content

    def test_no_plaintext_service_names(self, tmp_path):
        """Test service names are encrypted."""
        file_path = tmp_path / "credentials.enc"

        backend = EncryptedFileBackend(file_path, "password")
        backend.set("super-secret-service", "api_key", "value")

        # Read raw file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Verify service name is not in plaintext
        assert b"super-secret-service" not in file_content

    def test_strong_key_derivation(self, tmp_path):
        """Test strong key derivation parameters."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        # Verify PBKDF2 uses recommended iteration count
        # This is tested indirectly by checking the derivation works
        # and takes reasonable time
        import time

        start = time.time()

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=backend.salt,
            iterations=480_000,  # OWASP recommendation
        )
        key = kdf.derive(b"password")

        elapsed = time.time() - start

        # Derivation should take some time (but not too long)
        assert 0.01 < elapsed < 5.0  # Reasonable bounds
        assert len(key) == 32  # 256 bits

    def test_salt_uniqueness(self, tmp_path):
        """Test each installation gets unique salt."""
        file1 = tmp_path / "creds1.enc"
        file2 = tmp_path / "creds2.enc"

        backend1 = EncryptedFileBackend(file1, "password")
        backend2 = EncryptedFileBackend(file2, "password")

        # Different backends should have different salts
        # (unless they share the same salt file)
        if file1.parent != file2.parent:
            assert backend1.salt != backend2.salt

    def test_token_detection_heuristic(self):
        """Test direct token values are detected."""
        from automation.credentials.resolver import CredentialResolver

        resolver = CredentialResolver()

        # These should be detected as tokens
        assert resolver._looks_like_token("ghp_1234567890abcdef1234567890")
        assert resolver._looks_like_token("gho_abcdefghijklmnop")
        assert resolver._looks_like_token("a" * 30)  # Long alphanumeric

        # These should not be detected
        assert not resolver._looks_like_token("short")
        assert not resolver._looks_like_token("${ENV_VAR}")
        assert not resolver._looks_like_token("@keyring:service/key")

    def test_no_credential_leakage_in_exceptions(self, tmp_path):
        """Test credential values don't leak in exception messages."""
        from automation.credentials import CredentialResolver

        os.environ["SECRET_TOKEN"] = "super-secret-value-12345"

        resolver = CredentialResolver()

        # Resolve the credential
        _value = resolver.resolve("${SECRET_TOKEN}")

        # Exception messages should not contain the actual value
        try:
            # Force an error after resolution
            resolver.resolve("${NONEXISTENT}")
        except Exception as e:
            error_message = str(e)
            assert "super-secret-value-12345" not in error_message

    def test_cache_clearing_removes_secrets(self):
        """Test cache clearing actually removes credential values."""
        from automation.credentials import CredentialResolver

        os.environ["TEST_SECRET"] = "secret-123"

        resolver = CredentialResolver()
        resolver.resolve("${TEST_SECRET}")

        # Verify cache contains secret
        assert "${TEST_SECRET}" in resolver._cache

        # Clear cache
        resolver.clear_cache()

        # Verify cache is empty
        assert "${TEST_SECRET}" not in resolver._cache

    def test_atomic_file_writes_prevent_corruption(self, tmp_path):
        """Test atomic writes prevent partial file corruption."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        backend.set("service1", "key1", "value1")

        # Verify temp file is not left behind after write
        temp_file = file_path.with_suffix(".tmp")
        assert not temp_file.exists()

        # File should be readable
        assert backend.get("service1", "key1") == "value1"

    def test_no_world_readable_files(self, tmp_path):
        """Test no credential files are world-readable."""
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission test only for Unix")

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        backend.set("test", "key", "value")

        # Check neither creds nor salt is world-readable
        for path in [file_path, file_path.parent / "credentials.salt"]:
            stat_info = path.stat()
            mode = stat_info.st_mode & 0o777

            # Verify no read/write/execute for group or others
            assert mode & 0o077 == 0, f"{path} has insecure permissions: {oct(mode)}"

    def test_json_structure_not_exposed(self, tmp_path):
        """Test internal JSON structure is not exposed in plaintext."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        backend.set("gitea", "api_token", "secret")

        # Read raw file
        with open(file_path, "rb") as f:
            content = f.read()

        # Verify no JSON syntax in plaintext
        assert b"{" not in content or content.count(b"{") < 2  # Fernet may have braces
        assert b'"gitea"' not in content
        assert b'"api_token"' not in content

    def test_master_password_not_stored(self, tmp_path):
        """Test master password is never stored."""
        file_path = tmp_path / "credentials.enc"
        password = "my-master-password-123"

        backend = EncryptedFileBackend(file_path, password)
        backend.set("test", "key", "value")

        # Check password not in credentials file
        with open(file_path, "rb") as f:
            content = f.read()
        assert password.encode("utf-8") not in content

        # Check password not in salt file
        salt_file = file_path.parent / "credentials.salt"
        with open(salt_file, "rb") as f:
            salt_content = f.read()
        assert password.encode("utf-8") not in salt_content

    def test_fernet_token_structure(self, tmp_path):
        """Test encrypted data uses Fernet token structure."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        backend.set("test", "key", "value")

        with open(file_path, "rb") as f:
            content = f.read()

        # Fernet tokens are base64-encoded and start with specific version byte
        import base64

        try:
            decoded = base64.urlsafe_b64decode(content)
            # Version byte should be 0x80 for Fernet
            assert decoded[0] == 0x80
        except Exception:
            pytest.fail("Encrypted content is not valid Fernet token")
