"""Unit tests for credential backend implementations.

Tests cover:
- EncryptedFileBackend: Fernet encryption, PBKDF2 key derivation, file operations
- KeyringBackend: OS keyring interactions (mocked)
- EnvironmentBackend: Environment variable operations
- CredentialResolver: Reference parsing, multi-backend resolution

Consolidated for efficiency while maintaining full coverage.
"""

import os
import secrets
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from repo_sapiens.credentials.encrypted_backend import EncryptedFileBackend
from repo_sapiens.credentials.environment_backend import EnvironmentBackend
from repo_sapiens.credentials.exceptions import (
    BackendNotAvailableError,
    CredentialError,
    CredentialNotFoundError,
    EncryptionError,
)
from repo_sapiens.credentials.keyring_backend import KeyringBackend
from repo_sapiens.credentials.resolver import CredentialResolver

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_credentials_dir(tmp_path):
    """Create temporary directory for credential files."""
    creds_dir = tmp_path / ".builder"
    creds_dir.mkdir(parents=True)
    return creds_dir


@pytest.fixture
def encrypted_backend(temp_credentials_dir):
    """Create EncryptedFileBackend with temporary file path."""
    file_path = temp_credentials_dir / "credentials.enc"
    salt = secrets.token_bytes(16)
    return EncryptedFileBackend(
        file_path=file_path,
        master_password="test_master_password",
        salt=salt,
    )


@pytest.fixture
def credential_resolver():
    """Create CredentialResolver with mocked backends."""
    return CredentialResolver()


# =============================================================================
# Backend Properties Tests (Consolidated)
# =============================================================================


class TestBackendProperties:
    """Tests for backend property accessors across all backends."""

    @pytest.mark.parametrize(
        "backend_class,expected_name",
        [
            (EnvironmentBackend, "environment"),
            (KeyringBackend, "keyring"),
        ],
    )
    def test_backend_name(self, backend_class, expected_name):
        """Should return correct backend identifier."""
        backend = backend_class()
        assert backend.name == expected_name

    def test_encrypted_backend_name(self, encrypted_backend):
        """Should return 'encrypted_file' as backend identifier."""
        assert encrypted_backend.name == "encrypted_file"

    def test_environment_always_available(self):
        """Environment backend should always be available."""
        backend = EnvironmentBackend()
        assert backend.available is True

    def test_keyring_available_when_installed(self):
        """Should return True when keyring module is available and functional."""
        with patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True):
            with patch("repo_sapiens.credentials.keyring_backend.keyring") as mock_kr:
                mock_kr.get_keyring.return_value = Mock()
                backend = KeyringBackend()
                assert backend.available is True

    @pytest.mark.parametrize(
        "keyring_available,get_keyring_effect,expected",
        [
            (False, None, False),  # Not installed
            (True, Exception("No backend"), False),  # Fails to init
        ],
    )
    def test_keyring_unavailable_scenarios(self, keyring_available, get_keyring_effect, expected):
        """Should return False when keyring is unavailable."""
        with patch(
            "repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE",
            keyring_available,
        ):
            if keyring_available:
                with patch("repo_sapiens.credentials.keyring_backend.keyring") as mock_kr:
                    mock_kr.get_keyring.side_effect = get_keyring_effect
                    backend = KeyringBackend()
                    assert backend.available is expected
            else:
                backend = KeyringBackend()
                assert backend.available is expected

    def test_encrypted_backend_available(self, encrypted_backend):
        """Should return True when cryptography is available."""
        assert encrypted_backend.available is True


# =============================================================================
# EnvironmentBackend Tests
# =============================================================================


class TestEnvironmentBackend:
    """Tests for EnvironmentBackend operations."""

    @pytest.mark.parametrize(
        "var_value,expected",
        [
            ("test_secret_value", "test_secret_value"),
            ("", ""),
            ("secret!@#$%^&*()_+-=[]{}|;':\",./<>?", "secret!@#$%^&*()_+-=[]{}|;':\",./<>?"),
            (
                "secret_value_\u00e9\u00e8\u00ea\u4e2d\u6587",
                "secret_value_\u00e9\u00e8\u00ea\u4e2d\u6587",
            ),
        ],
        ids=["normal", "empty", "special_chars", "unicode"],
    )
    def test_get_existing_variable(self, var_value, expected):
        """Should retrieve existing environment variable with various values."""
        backend = EnvironmentBackend()
        test_var = "TEST_CREDENTIAL_BACKEND_VAR"
        with patch.dict(os.environ, {test_var: var_value}):
            result = backend.get(test_var)
        assert result == expected

    def test_get_nonexistent_variable(self):
        """Should return None for non-existent variable."""
        backend = EnvironmentBackend()
        var_name = "NONEXISTENT_VAR_12345_XYZZY"
        if var_name in os.environ:
            del os.environ[var_name]
        assert backend.get(var_name) is None

    def test_set_creates_and_overwrites_variable(self):
        """Should create and overwrite environment variables."""
        backend = EnvironmentBackend()
        test_var = "TEST_SET_VAR_NEW"
        try:
            if test_var in os.environ:
                del os.environ[test_var]
            # Create
            backend.set(test_var, "new_value")
            assert os.environ.get(test_var) == "new_value"
            # Overwrite
            backend.set(test_var, "updated_value")
            assert os.environ.get(test_var) == "updated_value"
        finally:
            if test_var in os.environ:
                del os.environ[test_var]

    @pytest.mark.parametrize("value", ["", None], ids=["empty", "none"])
    def test_set_invalid_value_raises_error(self, value):
        """Should raise error for empty or None value."""
        backend = EnvironmentBackend()
        with pytest.raises((ValueError, TypeError)):
            backend.set("TEST_VAR", value)

    def test_delete_existing_and_nonexistent(self):
        """Should delete existing variable and handle non-existent gracefully."""
        backend = EnvironmentBackend()
        test_var = "TEST_DELETE_VAR"
        try:
            os.environ[test_var] = "value_to_delete"
            assert backend.delete(test_var) is True
            assert test_var not in os.environ
        finally:
            if test_var in os.environ:
                del os.environ[test_var]
        # Non-existent
        assert backend.delete("NONEXISTENT_DELETE_VAR_12345") is False


# =============================================================================
# KeyringBackend Tests
# =============================================================================


class TestKeyringBackend:
    """Tests for KeyringBackend operations."""

    @pytest.fixture
    def mock_keyring_available(self):
        """Context manager for mocking available keyring."""
        with patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", True):
            with patch("repo_sapiens.credentials.keyring_backend.keyring") as mock_kr:
                mock_kr.get_keyring.return_value = Mock()
                yield mock_kr

    def test_get_existing_credential(self, mock_keyring_available):
        """Should retrieve credential from keyring."""
        mock_keyring_available.get_password.return_value = "secret_token"
        backend = KeyringBackend()
        result = backend.get("gitea", "api_token")
        assert result == "secret_token"
        mock_keyring_available.get_password.assert_called_once_with("sapiens/gitea", "api_token")

    def test_get_nonexistent_credential(self, mock_keyring_available):
        """Should return None for non-existent credential."""
        mock_keyring_available.get_password.return_value = None
        backend = KeyringBackend()
        assert backend.get("unknown", "key") is None

    def test_get_when_keyring_unavailable(self):
        """Should raise BackendNotAvailableError when keyring unavailable."""
        with patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False):
            backend = KeyringBackend()
            with pytest.raises(BackendNotAvailableError) as exc_info:
                backend.get("service", "key")
            assert "not available" in str(exc_info.value)
            assert "pip install keyring" in str(exc_info.value)

    def test_get_handles_keyring_error(self, mock_keyring_available):
        """Should wrap KeyringError in CredentialError."""
        from keyring.errors import KeyringError

        mock_keyring_available.get_password.side_effect = KeyringError("Access denied")
        backend = KeyringBackend()
        with pytest.raises(CredentialError) as exc_info:
            backend.get("service", "key")
        assert "Keyring operation failed" in str(exc_info.value)

    def test_set_stores_credential(self, mock_keyring_available):
        """Should store credential in keyring."""
        backend = KeyringBackend()
        backend.set("gitea", "api_token", "ghp_abc123")
        mock_keyring_available.set_password.assert_called_once_with(
            "sapiens/gitea", "api_token", "ghp_abc123"
        )

    def test_set_empty_value_raises_error(self, mock_keyring_available):
        """Should raise ValueError for empty value."""
        backend = KeyringBackend()
        with pytest.raises(ValueError, match="Credential value cannot be empty"):
            backend.set("service", "key", "")

    def test_set_when_unavailable_raises_error(self):
        """Should raise BackendNotAvailableError when keyring unavailable."""
        with patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False):
            backend = KeyringBackend()
            with pytest.raises(BackendNotAvailableError):
                backend.set("service", "key", "value")

    def test_set_handles_keyring_error(self, mock_keyring_available):
        """Should wrap KeyringError in CredentialError."""
        from keyring.errors import KeyringError

        mock_keyring_available.set_password.side_effect = KeyringError("Write denied")
        backend = KeyringBackend()
        with pytest.raises(CredentialError, match="Failed to store credential"):
            backend.set("service", "key", "value")

    def test_delete_existing_credential(self, mock_keyring_available):
        """Should delete credential and return True."""
        backend = KeyringBackend()
        result = backend.delete("gitea", "api_token")
        assert result is True
        mock_keyring_available.delete_password.assert_called_once_with("sapiens/gitea", "api_token")

    def test_delete_nonexistent_credential(self, mock_keyring_available):
        """Should return False when credential doesn't exist."""
        from keyring.errors import PasswordDeleteError

        mock_keyring_available.delete_password.side_effect = PasswordDeleteError("Not found")
        backend = KeyringBackend()
        assert backend.delete("unknown", "key") is False

    def test_delete_when_unavailable_raises_error(self):
        """Should raise BackendNotAvailableError when keyring unavailable."""
        with patch("repo_sapiens.credentials.keyring_backend.KEYRING_AVAILABLE", False):
            backend = KeyringBackend()
            with pytest.raises(BackendNotAvailableError):
                backend.delete("service", "key")

    def test_delete_handles_keyring_error(self, mock_keyring_available):
        """Should wrap KeyringError in CredentialError."""
        from keyring.errors import KeyringError

        mock_keyring_available.delete_password.side_effect = KeyringError("Delete failed")
        backend = KeyringBackend()
        with pytest.raises(CredentialError, match="Failed to delete credential"):
            backend.delete("service", "key")


# =============================================================================
# EncryptedFileBackend Tests
# =============================================================================


class TestEncryptedFileBackendInit:
    """Tests for EncryptedFileBackend initialization."""

    def test_init_with_password_creates_fernet(self, temp_credentials_dir):
        """Should initialize Fernet when password provided."""
        backend = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password="test_password",
            salt=secrets.token_bytes(16),
        )
        assert backend.fernet is not None
        assert isinstance(backend.fernet, Fernet)

    def test_init_without_password_defers_fernet(self, temp_credentials_dir):
        """Should defer Fernet initialization when no password."""
        backend = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password=None,
            salt=secrets.token_bytes(16),
        )
        assert backend.fernet is None

    def test_init_generates_and_loads_salt(self, temp_credentials_dir):
        """Should generate salt when not provided and load existing salt."""
        # Generate
        backend1 = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password="test",
        )
        salt_file = temp_credentials_dir / "credentials.salt"
        assert salt_file.exists()
        assert len(backend1.salt) == 16

        # Load existing
        expected_salt = secrets.token_bytes(16)
        with open(salt_file, "wb") as f:
            f.write(expected_salt)
        backend2 = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password="test",
        )
        assert backend2.salt == expected_salt


class TestEncryptedFileBackendKeyDerivation:
    """Tests for PBKDF2 key derivation."""

    def test_create_fernet_produces_valid_cipher(self):
        """Should create valid Fernet cipher that encrypts/decrypts."""
        salt = secrets.token_bytes(16)
        fernet = EncryptedFileBackend._create_fernet("test_password", salt)
        assert isinstance(fernet, Fernet)
        plaintext = b"test message"
        assert fernet.decrypt(fernet.encrypt(plaintext)) == plaintext

    def test_same_password_salt_produces_same_key(self):
        """Should produce deterministic key from same inputs."""
        salt = secrets.token_bytes(16)
        fernet1 = EncryptedFileBackend._create_fernet("test_password", salt)
        fernet2 = EncryptedFileBackend._create_fernet("test_password", salt)
        plaintext = b"test message"
        assert fernet2.decrypt(fernet1.encrypt(plaintext)) == plaintext

    def test_different_salt_produces_different_key(self):
        """Should produce different keys for different salts."""
        fernet1 = EncryptedFileBackend._create_fernet("test", secrets.token_bytes(16))
        fernet2 = EncryptedFileBackend._create_fernet("test", secrets.token_bytes(16))
        with pytest.raises(InvalidToken):
            fernet2.decrypt(fernet1.encrypt(b"test"))


class TestEncryptedFileBackendOperations:
    """Tests for EncryptedFileBackend get/set/delete operations."""

    def test_get_returns_none_when_file_missing(self, encrypted_backend):
        """Should return None when file doesn't exist."""
        assert encrypted_backend.get("gitea", "api_token") is None

    def test_get_existing_credential(self, encrypted_backend):
        """Should retrieve stored credential."""
        encrypted_backend.set("gitea", "api_token", "ghp_abc123")
        assert encrypted_backend.get("gitea", "api_token") == "ghp_abc123"

    def test_get_uses_cache(self, encrypted_backend):
        """Should use cached credentials after first load."""
        encrypted_backend.set("gitea", "api_token", "value1")
        encrypted_backend.get("gitea", "api_token")
        encrypted_backend._credentials_cache["gitea"]["api_token"] = "cached_value"
        assert encrypted_backend.get("gitea", "api_token") == "cached_value"

    def test_get_without_password_raises_error(self, temp_credentials_dir):
        """Should raise EncryptionError when password not provided."""
        backend = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password=None,
            salt=secrets.token_bytes(16),
        )
        (temp_credentials_dir / "credentials.enc").write_bytes(b"dummy")
        with pytest.raises(EncryptionError, match="Master password not provided"):
            backend.get("service", "key")

    def test_get_with_wrong_password_raises_error(self, temp_credentials_dir):
        """Should raise EncryptionError with wrong password."""
        salt = secrets.token_bytes(16)
        backend1 = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password="correct_password",
            salt=salt,
        )
        backend1.set("gitea", "api_token", "secret")

        backend2 = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password="wrong_password",
            salt=salt,
        )
        with pytest.raises(EncryptionError, match="Invalid master password"):
            backend2.get("gitea", "api_token")

    def test_get_with_corrupted_file_raises_error(self, encrypted_backend):
        """Should raise EncryptionError for corrupted file."""
        encrypted_backend.file_path.write_bytes(b"not valid encrypted data")
        with pytest.raises(EncryptionError):
            encrypted_backend.get("service", "key")

    def test_set_creates_encrypted_file(self, encrypted_backend):
        """Should create encrypted file when storing first credential."""
        assert not encrypted_backend.file_path.exists()
        encrypted_backend.set("gitea", "api_token", "ghp_abc123")
        assert encrypted_backend.file_path.exists()
        raw = encrypted_backend.file_path.read_bytes()
        assert b"ghp_abc123" not in raw
        assert b"gitea" not in raw

    def test_set_multiple_and_overwrite(self, encrypted_backend):
        """Should store multiple credentials and overwrite existing."""
        encrypted_backend.set("gitea", "api_token", "token1")
        encrypted_backend.set("gitea", "webhook_secret", "secret1")
        encrypted_backend.set("claude", "api_key", "key1")
        assert encrypted_backend.get("gitea", "api_token") == "token1"
        assert encrypted_backend.get("gitea", "webhook_secret") == "secret1"
        assert encrypted_backend.get("claude", "api_key") == "key1"
        # Overwrite
        encrypted_backend.set("gitea", "api_token", "updated")
        assert encrypted_backend.get("gitea", "api_token") == "updated"

    def test_set_empty_value_raises_error(self, encrypted_backend):
        """Should raise ValueError for empty value."""
        with pytest.raises(ValueError, match="Credential value cannot be empty"):
            encrypted_backend.set("service", "key", "")

    def test_set_without_password_raises_error(self, temp_credentials_dir):
        """Should raise EncryptionError when password not provided."""
        backend = EncryptedFileBackend(
            file_path=temp_credentials_dir / "credentials.enc",
            master_password=None,
            salt=secrets.token_bytes(16),
        )
        with pytest.raises(EncryptionError, match="Master password not provided"):
            backend.set("service", "key", "value")

    def test_set_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        nested = tmp_path / "deep" / "nested" / "dir" / "credentials.enc"
        backend = EncryptedFileBackend(
            file_path=nested,
            master_password="test",
            salt=secrets.token_bytes(16),
        )
        backend.set("service", "key", "value")
        assert nested.exists()

    def test_delete_credential(self, encrypted_backend):
        """Should delete credential and handle non-existent cases."""
        encrypted_backend.set("gitea", "api_token", "secret")
        assert encrypted_backend.delete("gitea", "api_token") is True
        assert encrypted_backend.get("gitea", "api_token") is None
        # Non-existent
        assert encrypted_backend.delete("unknown_service", "key") is False
        # Non-existent key
        encrypted_backend.set("gitea", "api_token", "secret")
        assert encrypted_backend.delete("gitea", "unknown_key") is False

    def test_delete_removes_empty_service(self, encrypted_backend):
        """Should remove service entry when last key deleted."""
        encrypted_backend.set("gitea", "api_token", "secret")
        encrypted_backend.delete("gitea", "api_token")
        assert "gitea" not in encrypted_backend._load_credentials()

    def test_delete_preserves_other_keys(self, encrypted_backend):
        """Should preserve other keys when deleting one."""
        encrypted_backend.set("gitea", "api_token", "token1")
        encrypted_backend.set("gitea", "webhook_secret", "secret1")
        encrypted_backend.delete("gitea", "api_token")
        assert encrypted_backend.get("gitea", "api_token") is None
        assert encrypted_backend.get("gitea", "webhook_secret") == "secret1"


class TestEncryptedFileBackendAtomicOperations:
    """Tests for atomic file operations."""

    def test_atomic_write_cleans_temp_file(self, encrypted_backend):
        """Should use and clean up temporary file for atomic writes."""
        encrypted_backend.set("service", "key", "value")
        assert not encrypted_backend.file_path.with_suffix(".tmp").exists()
        assert encrypted_backend.file_path.exists()

    def test_file_permissions_set_to_600(self, encrypted_backend):
        """Should set restrictive file permissions."""
        encrypted_backend.set("service", "key", "value")
        mode = encrypted_backend.file_path.stat().st_mode
        assert mode & 0o777 == 0o600


# =============================================================================
# CredentialResolver Tests
# =============================================================================


class TestCredentialResolverPatterns:
    """Tests for credential reference pattern matching."""

    @pytest.mark.parametrize(
        "reference,expected_service,expected_key",
        [
            ("@keyring:gitea/api_token", "gitea", "api_token"),
            ("@keyring:service/path/to/key", "service", "path/to/key"),
            ("@encrypted:claude/api_key", "claude", "api_key"),
        ],
    )
    def test_keyring_and_encrypted_patterns(self, reference, expected_service, expected_key):
        """Should match @keyring: and @encrypted: formats."""
        if reference.startswith("@keyring:"):
            match = CredentialResolver.KEYRING_PATTERN.match(reference)
        else:
            match = CredentialResolver.ENCRYPTED_PATTERN.match(reference)
        assert match is not None
        assert match.group(1) == expected_service
        assert match.group(2) == expected_key

    @pytest.mark.parametrize(
        "reference,expected_var",
        [
            ("${GITEA_API_TOKEN}", "GITEA_API_TOKEN"),
        ],
    )
    def test_env_pattern_matches(self, reference, expected_var):
        """Should match ${VAR_NAME} format."""
        match = CredentialResolver.ENV_PATTERN.match(reference)
        assert match is not None
        assert match.group(1) == expected_var

    @pytest.mark.parametrize(
        "invalid_ref",
        ["${1_INVALID}", "${lowercase}"],
        ids=["starts_with_number", "lowercase"],
    )
    def test_env_pattern_rejects_invalid(self, invalid_ref):
        """Should not match invalid variable names."""
        assert CredentialResolver.ENV_PATTERN.match(invalid_ref) is None


class TestCredentialResolverResolve:
    """Tests for CredentialResolver.resolve method."""

    def test_resolve_environment_variable(self, credential_resolver):
        """Should resolve environment variable reference."""
        with patch.dict(os.environ, {"TEST_API_KEY": "env_secret"}):
            assert credential_resolver.resolve("${TEST_API_KEY}") == "env_secret"

    def test_resolve_missing_env_var_raises_error(self, credential_resolver):
        """Should raise CredentialNotFoundError for missing env var."""
        var = "NONEXISTENT_VAR_XYZ_123"
        if var in os.environ:
            del os.environ[var]
        with pytest.raises(CredentialNotFoundError) as exc_info:
            credential_resolver.resolve(f"${{{var}}}")
        assert "Environment variable not set" in str(exc_info.value)

    def test_resolve_keyring_reference(self, credential_resolver):
        """Should resolve keyring reference."""
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = "keyring_secret"
        credential_resolver.keyring_backend = mock_backend
        assert credential_resolver.resolve("@keyring:gitea/api_token") == "keyring_secret"
        mock_backend.get.assert_called_once_with("gitea", "api_token")

    def test_resolve_keyring_unavailable_raises_error(self, credential_resolver):
        """Should raise BackendNotAvailableError when keyring unavailable."""
        mock_backend = Mock()
        mock_backend.available = False
        credential_resolver.keyring_backend = mock_backend
        with pytest.raises(BackendNotAvailableError, match="Keyring backend"):
            credential_resolver.resolve("@keyring:gitea/api_token")

    def test_resolve_keyring_not_found_raises_error(self, credential_resolver):
        """Should raise CredentialNotFoundError when key not in keyring."""
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = None
        credential_resolver.keyring_backend = mock_backend
        with pytest.raises(CredentialNotFoundError, match="not found in keyring"):
            credential_resolver.resolve("@keyring:unknown/key")

    def test_resolve_encrypted_reference(self, credential_resolver, tmp_path):
        """Should resolve encrypted file reference."""
        credential_resolver._encrypted_file_path = tmp_path / "creds.enc"
        credential_resolver._encrypted_master_password = "test_password"
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = "encrypted_secret"
        credential_resolver._encrypted_backend = mock_backend
        assert credential_resolver.resolve("@encrypted:claude/api_key") == "encrypted_secret"

    def test_resolve_encrypted_unavailable_raises_error(self, credential_resolver):
        """Should raise BackendNotAvailableError when encrypted unavailable."""
        mock_backend = Mock()
        mock_backend.available = False
        credential_resolver._encrypted_backend = mock_backend
        with pytest.raises(BackendNotAvailableError, match="Encrypted file backend"):
            credential_resolver.resolve("@encrypted:service/key")

    def test_resolve_direct_value_returns_as_is(self, credential_resolver):
        """Should return direct values unchanged."""
        assert credential_resolver.resolve("literal-value") == "literal-value"

    def test_resolve_caching_behavior(self, credential_resolver):
        """Should cache by default and bypass cache when requested."""
        with patch.dict(os.environ, {"CACHED_VAR": "cached_value"}):
            result1 = credential_resolver.resolve("${CACHED_VAR}")
        if "CACHED_VAR" in os.environ:
            del os.environ["CACHED_VAR"]
        # Cached
        assert credential_resolver.resolve("${CACHED_VAR}") == "cached_value"
        # No cache
        os.environ["UNCACHED_VAR"] = "value1"
        credential_resolver.resolve("${UNCACHED_VAR}", cache=False)
        os.environ["UNCACHED_VAR"] = "value2"
        assert credential_resolver.resolve("${UNCACHED_VAR}", cache=False) == "value2"
        del os.environ["UNCACHED_VAR"]

    def test_resolve_warns_on_token_like_value(self, credential_resolver, caplog):
        """Should warn when value looks like a direct token."""
        import logging

        with caplog.at_level(logging.WARNING):
            credential_resolver.resolve("ghp_abc123def456789012345678901234")
        assert "direct token value" in caplog.text.lower()


class TestCredentialResolverLooksLikeToken:
    """Tests for _looks_like_token heuristic."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("ghp_abc123", True),
            ("gho_abc123", True),
            ("ghu_abc123", True),
            ("ghs_abc123", True),
            ("ghr_abc123", True),
            ("a" * 21, True),
            ("a" * 20, False),
            ("short", False),
            ("test-value", False),
            ("", False),
            ("this has spaces in it quite long", False),
        ],
        ids=[
            "ghp",
            "gho",
            "ghu",
            "ghs",
            "ghr",
            "long_21",
            "short_20",
            "short",
            "hyphenated",
            "empty",
            "spaces",
        ],
    )
    def test_token_detection(self, value, expected):
        """Should detect token-like strings correctly."""
        assert CredentialResolver._looks_like_token(value) is expected


class TestCredentialResolverCacheAndLazyInit:
    """Tests for cache management and lazy initialization."""

    def test_clear_cache(self, credential_resolver):
        """Should clear all cached credentials."""
        with patch.dict(os.environ, {"VAR1": "val1", "VAR2": "val2"}):
            credential_resolver.resolve("${VAR1}")
            credential_resolver.resolve("${VAR2}")
        assert len(credential_resolver._cache) > 0
        credential_resolver.clear_cache()
        assert len(credential_resolver._cache) == 0

    def test_encrypted_backend_lazy_init(self, tmp_path):
        """Should lazily initialize encrypted backend."""
        resolver = CredentialResolver(
            encrypted_file_path=tmp_path / "lazy.enc",
            encrypted_master_password="lazy_password",
        )
        assert resolver._encrypted_backend is None
        backend = resolver.encrypted_backend
        assert backend is not None
        assert resolver._encrypted_backend is backend

    def test_encrypted_backend_default_path(self):
        """Should use default path when not specified."""
        resolver = CredentialResolver()
        assert ".sapiens/credentials.enc" in str(resolver.encrypted_backend.file_path)


# =============================================================================
# Integration Tests
# =============================================================================


class TestEncryptionRoundTrip:
    """Tests for encryption/decryption round trips."""

    def test_full_credential_lifecycle(self, temp_credentials_dir):
        """Should store, retrieve, update, and delete credential."""
        backend = EncryptedFileBackend(
            file_path=temp_credentials_dir / "lifecycle.enc",
            master_password="lifecycle_password",
            salt=secrets.token_bytes(16),
        )
        # Store & retrieve
        backend.set("service", "key", "original_value")
        assert backend.get("service", "key") == "original_value"
        # Update
        backend.set("service", "key", "updated_value")
        assert backend.get("service", "key") == "updated_value"
        # Delete
        assert backend.delete("service", "key") is True
        assert backend.get("service", "key") is None

    def test_persistence_across_instances(self, temp_credentials_dir):
        """Should persist credentials across backend instances."""
        file_path = temp_credentials_dir / "persist.enc"
        salt = secrets.token_bytes(16)
        password = "persist_password"

        backend1 = EncryptedFileBackend(file_path=file_path, master_password=password, salt=salt)
        backend1.set("gitea", "api_token", "persistent_value")

        backend2 = EncryptedFileBackend(file_path=file_path, master_password=password, salt=salt)
        assert backend2.get("gitea", "api_token") == "persistent_value"

    @pytest.mark.parametrize(
        "value",
        [
            "secret!@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t",
            "password_\u4e2d\u6587_\u00e9\u00e8\u00ea",
            "x" * 100000,
        ],
        ids=["special_chars", "unicode", "large_100kb"],
    )
    def test_special_values(self, encrypted_backend, value):
        """Should handle special characters, unicode, and large values."""
        encrypted_backend.set("service", "key", value)
        assert encrypted_backend.get("service", "key") == value


class TestResolverBackendIntegration:
    """Tests for resolver integration with backends."""

    def test_resolver_with_environment_backend(self):
        """Should resolve environment credentials through resolver."""
        resolver = CredentialResolver()
        with patch.dict(os.environ, {"INTEGRATION_TEST_VAR": "integration_value"}):
            assert resolver.resolve("${INTEGRATION_TEST_VAR}") == "integration_value"

    def test_resolver_with_encrypted_backend(self, tmp_path):
        """Should resolve encrypted credentials through resolver."""
        resolver = CredentialResolver(
            encrypted_file_path=tmp_path / "resolver_test.enc",
            encrypted_master_password="resolver_password",
        )
        resolver.encrypted_backend.set("test", "key", "encrypted_integration_value")
        assert resolver.resolve("@encrypted:test/key") == "encrypted_integration_value"


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for custom exception attributes and messages."""

    def test_credential_error_attributes(self):
        """Should include message, reference, and suggestion."""
        error = CredentialError(
            message="Test error",
            reference="@keyring:service/key",
            suggestion="Try this instead",
        )
        assert "Test error" in error.message
        assert error.reference == "@keyring:service/key"
        assert error.suggestion == "Try this instead"
        assert "@keyring:service/key" in str(error)
        assert "Try this instead" in str(error)

    def test_encryption_error_inheritance(self):
        """Should inherit from CredentialError."""
        error = EncryptionError("Encryption failed")
        assert isinstance(error, CredentialError)
        assert "Encryption failed" in str(error)

    def test_backend_not_available_error_inheritance(self):
        """Should inherit from CredentialError."""
        error = BackendNotAvailableError("Backend unavailable")
        assert isinstance(error, CredentialError)

    def test_error_includes_suggestion(self):
        """Should include actionable suggestion in errors."""
        error = EncryptionError("Invalid password", suggestion="Verify your master password")
        assert "Verify your master password" in str(error)

    def test_not_found_error_includes_reference(self):
        """Should include reference in not found errors."""
        error = CredentialNotFoundError("Credential not found", reference="${MISSING_VAR}")
        assert "${MISSING_VAR}" in str(error)
