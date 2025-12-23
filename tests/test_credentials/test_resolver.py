"""Tests for credential resolver."""

import os
from unittest.mock import Mock, patch

import pytest

from automation.credentials import (
    BackendNotAvailableError,
    CredentialNotFoundError,
    CredentialResolver,
)


class TestCredentialResolver:
    """Test CredentialResolver functionality."""

    @pytest.fixture
    def resolver(self):
        """Create CredentialResolver instance."""
        return CredentialResolver()

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up test environment variables."""
        yield
        test_vars = [key for key in os.environ if key.startswith("TEST_")]
        for var in test_vars:
            os.environ.pop(var, None)

    # Pattern matching tests

    def test_keyring_pattern_matches(self, resolver):
        """Test keyring pattern matching."""
        assert resolver.KEYRING_PATTERN.match("@keyring:gitea/api_token")
        assert resolver.KEYRING_PATTERN.match("@keyring:service/key")
        assert not resolver.KEYRING_PATTERN.match("keyring:service/key")
        assert not resolver.KEYRING_PATTERN.match("@keyring:service")

    def test_env_pattern_matches(self, resolver):
        """Test environment variable pattern matching."""
        assert resolver.ENV_PATTERN.match("${GITEA_API_TOKEN}")
        assert resolver.ENV_PATTERN.match("${_PRIVATE_VAR}")
        assert not resolver.ENV_PATTERN.match("$GITEA_TOKEN")
        assert not resolver.ENV_PATTERN.match("${lowercase}")
        assert not resolver.ENV_PATTERN.match("${123INVALID}")

    def test_encrypted_pattern_matches(self, resolver):
        """Test encrypted file pattern matching."""
        assert resolver.ENCRYPTED_PATTERN.match("@encrypted:gitea/api_token")
        assert resolver.ENCRYPTED_PATTERN.match("@encrypted:service/key")
        assert not resolver.ENCRYPTED_PATTERN.match("encrypted:service/key")
        assert not resolver.ENCRYPTED_PATTERN.match("@encrypted:service")

    # Environment variable resolution tests

    def test_resolve_env_reference(self, resolver):
        """Test resolving environment variable reference."""
        os.environ["TEST_TOKEN"] = "env-token-123"

        result = resolver.resolve("${TEST_TOKEN}")

        assert result == "env-token-123"

    def test_resolve_env_not_found_raises_error(self, resolver):
        """Test missing environment variable raises error."""
        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolver.resolve("${NONEXISTENT_VAR}")

        assert "NONEXISTENT_VAR" in str(exc_info.value)
        assert exc_info.value.reference == "${NONEXISTENT_VAR}"
        assert exc_info.value.suggestion is not None
        assert "export" in exc_info.value.suggestion

    # Keyring resolution tests

    @patch("automation.credentials.resolver.KeyringBackend")
    def test_resolve_keyring_reference(self, mock_backend_class, resolver):
        """Test resolving keyring reference."""
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = "keyring-token"
        resolver.keyring_backend = mock_backend

        result = resolver.resolve("@keyring:gitea/api_token")

        assert result == "keyring-token"
        mock_backend.get.assert_called_once_with("gitea", "api_token")

    @patch("automation.credentials.resolver.KeyringBackend")
    def test_resolve_keyring_not_found(self, mock_backend_class, resolver):
        """Test keyring credential not found raises error."""
        mock_backend = Mock()
        mock_backend.available = True
        mock_backend.get.return_value = None
        resolver.keyring_backend = mock_backend

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolver.resolve("@keyring:gitea/api_token")

        assert "gitea/api_token" in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    @patch("automation.credentials.resolver.KeyringBackend")
    def test_resolve_keyring_unavailable(self, mock_backend_class, resolver):
        """Test keyring backend unavailable raises error."""
        mock_backend = Mock()
        mock_backend.available = False
        resolver.keyring_backend = mock_backend

        with pytest.raises(BackendNotAvailableError) as exc_info:
            resolver.resolve("@keyring:gitea/api_token")

        assert "not available" in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    # Encrypted file resolution tests

    def test_resolve_encrypted_reference(self, resolver, tmp_path):
        """Test resolving encrypted file reference."""
        from automation.credentials import EncryptedFileBackend

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        backend.set("gitea", "api_token", "encrypted-token")

        resolver._encrypted_backend = backend

        result = resolver.resolve("@encrypted:gitea/api_token")

        assert result == "encrypted-token"

    def test_resolve_encrypted_not_found(self, resolver, tmp_path):
        """Test encrypted credential not found raises error."""
        from automation.credentials import EncryptedFileBackend

        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        resolver._encrypted_backend = backend

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolver.resolve("@encrypted:gitea/api_token")

        assert "gitea/api_token" in str(exc_info.value)

    # Direct value tests

    def test_resolve_direct_value(self, resolver):
        """Test direct values are returned as-is."""
        result = resolver.resolve("direct-value")

        assert result == "direct-value"

    def test_looks_like_token_github_prefix(self, resolver):
        """Test token detection for GitHub tokens."""
        assert resolver._looks_like_token("ghp_1234567890abcdef")
        assert resolver._looks_like_token("gho_1234567890abcdef")
        assert resolver._looks_like_token("ghu_1234567890abcdef")
        assert resolver._looks_like_token("ghs_1234567890abcdef")
        assert resolver._looks_like_token("ghr_1234567890abcdef")

    def test_looks_like_token_long_string(self, resolver):
        """Test token detection for long alphanumeric strings."""
        assert resolver._looks_like_token("a" * 30)
        assert resolver._looks_like_token("abc123def456ghi789jkl012")
        assert not resolver._looks_like_token("short")

    def test_looks_like_token_excludes_references(self, resolver):
        """Test token detection excludes reference syntax."""
        assert not resolver._looks_like_token("${ENV_VAR}")
        assert not resolver._looks_like_token("@keyring:service/key")
        assert not resolver._looks_like_token("@encrypted:service/key")

    @patch("automation.credentials.resolver.logger")
    def test_direct_token_logs_warning(self, mock_logger, resolver):
        """Test direct token values trigger warning."""
        resolver.resolve("ghp_1234567890abcdefghij")

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        assert "direct token" in str(mock_logger.warning.call_args).lower()

    # Caching tests

    def test_caching_enabled_by_default(self, resolver):
        """Test resolved credentials are cached by default."""
        os.environ["TEST_VAR"] = "value1"

        result1 = resolver.resolve("${TEST_VAR}")

        # Change environment
        os.environ["TEST_VAR"] = "value2"

        # Should return cached value
        result2 = resolver.resolve("${TEST_VAR}")

        assert result1 == result2 == "value1"

    def test_caching_can_be_disabled(self, resolver):
        """Test caching can be disabled per call."""
        os.environ["TEST_VAR"] = "value1"

        result1 = resolver.resolve("${TEST_VAR}", cache=False)

        os.environ["TEST_VAR"] = "value2"

        result2 = resolver.resolve("${TEST_VAR}", cache=False)

        assert result1 == "value1"
        assert result2 == "value2"

    def test_clear_cache(self, resolver):
        """Test cache clearing."""
        os.environ["TEST_VAR"] = "value1"

        result1 = resolver.resolve("${TEST_VAR}")

        os.environ["TEST_VAR"] = "value2"

        resolver.clear_cache()

        result2 = resolver.resolve("${TEST_VAR}")

        assert result1 == "value1"
        assert result2 == "value2"

    def test_different_references_cached_separately(self, resolver):
        """Test different references are cached independently."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"

        result1 = resolver.resolve("${VAR1}")
        result2 = resolver.resolve("${VAR2}")

        assert result1 == "value1"
        assert result2 == "value2"

    # Integration tests

    def test_multiple_backend_types(self, resolver, tmp_path):
        """Test resolving from different backends in same session."""
        from automation.credentials import EncryptedFileBackend

        # Set up environment
        os.environ["TEST_ENV_TOKEN"] = "env-value"

        # Set up encrypted file
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")
        backend.set("gitea", "api_token", "encrypted-value")
        resolver._encrypted_backend = backend

        # Resolve from both backends
        env_result = resolver.resolve("${TEST_ENV_TOKEN}")
        encrypted_result = resolver.resolve("@encrypted:gitea/api_token")
        direct_result = resolver.resolve("direct-value")

        assert env_result == "env-value"
        assert encrypted_result == "encrypted-value"
        assert direct_result == "direct-value"

    def test_lazy_encrypted_backend_initialization(self, resolver):
        """Test encrypted backend is initialized lazily."""
        # Backend should not be initialized yet
        assert resolver._encrypted_backend is None

        # Access encrypted_backend property
        backend = resolver.encrypted_backend

        # Now it should be initialized
        assert backend is not None
        assert resolver._encrypted_backend is backend

    def test_custom_encrypted_file_path(self, tmp_path):
        """Test resolver with custom encrypted file path."""
        file_path = tmp_path / "custom_creds.enc"

        resolver = CredentialResolver(
            encrypted_file_path=file_path, encrypted_master_password="password"
        )

        # Set and resolve credential
        resolver.encrypted_backend.set("test", "key", "value")
        result = resolver.resolve("@encrypted:test/key")

        assert result == "value"
        assert file_path.exists()

    def test_error_messages_include_context(self, resolver):
        """Test error messages include helpful context."""
        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolver.resolve("${MISSING_VAR}")

        error = exc_info.value
        assert error.message is not None
        assert error.reference == "${MISSING_VAR}"
        assert error.suggestion is not None
        assert "export" in error.suggestion
