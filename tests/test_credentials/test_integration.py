"""Integration tests for credential system."""

import os
from pathlib import Path

import pytest

from repo_sapiens.credentials import (
    CredentialResolver,
    EncryptedFileBackend,
    EnvironmentBackend,
)


class TestCredentialIntegration:
    """Test full credential resolution flow."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up test environment variables."""
        yield
        test_vars = [key for key in os.environ if key.startswith("TEST_")]
        for var in test_vars:
            os.environ.pop(var, None)

    def test_encrypted_file_backend_full_flow(self, tmp_path):
        """Test complete encrypted file workflow."""
        file_path = tmp_path / "credentials.enc"
        password = "test-password-123"

        # Create backend and store credential
        backend = EncryptedFileBackend(file_path, password)
        backend.set("gitea", "api_token", "secret-token")

        # Verify file was created
        assert file_path.exists()

        # Create new backend instance (simulating restart)
        backend2 = EncryptedFileBackend(file_path, password)

        # Retrieve credential
        token = backend2.get("gitea", "api_token")
        assert token == "secret-token"

        # Update credential
        backend2.set("gitea", "api_token", "new-secret-token")

        # Verify update
        token = backend2.get("gitea", "api_token")
        assert token == "new-secret-token"

        # Delete credential
        assert backend2.delete("gitea", "api_token")
        assert backend2.get("gitea", "api_token") is None

    def test_environment_backend_full_flow(self):
        """Test complete environment backend workflow."""
        backend = EnvironmentBackend()

        # Set credential
        backend.set("TEST_API_TOKEN", "env-token")

        # Verify it's in environment
        assert os.environ["TEST_API_TOKEN"] == "env-token"

        # Get credential
        token = backend.get("TEST_API_TOKEN")
        assert token == "env-token"

        # Update credential
        backend.set("TEST_API_TOKEN", "new-env-token")
        assert backend.get("TEST_API_TOKEN") == "new-env-token"

        # Delete credential
        assert backend.delete("TEST_API_TOKEN")
        assert backend.get("TEST_API_TOKEN") is None

    def test_resolver_with_multiple_backends(self, tmp_path):
        """Test resolver with multiple backend types."""
        # Set up environment
        os.environ["TEST_ENV_TOKEN"] = "from-environment"

        # Set up encrypted file
        file_path = tmp_path / "credentials.enc"
        encrypted_backend = EncryptedFileBackend(file_path, "password")
        encrypted_backend.set("gitea", "api_token", "from-encrypted-file")

        # Create resolver
        resolver = CredentialResolver(encrypted_file_path=file_path, encrypted_master_password="password")

        # Resolve from different backends
        env_result = resolver.resolve("${TEST_ENV_TOKEN}")
        encrypted_result = resolver.resolve("@encrypted:gitea/api_token")
        direct_result = resolver.resolve("direct-value")

        assert env_result == "from-environment"
        assert encrypted_result == "from-encrypted-file"
        assert direct_result == "direct-value"

    def test_resolver_caching_across_backends(self, tmp_path):
        """Test resolver caches credentials from different backends."""
        os.environ["TEST_VAR1"] = "value1"
        os.environ["TEST_VAR2"] = "value2"

        resolver = CredentialResolver()

        # Resolve multiple credentials
        resolver.resolve("${TEST_VAR1}")
        resolver.resolve("${TEST_VAR2}")
        resolver.resolve("direct-value")

        # Check cache
        assert "${TEST_VAR1}" in resolver._cache
        assert "${TEST_VAR2}" in resolver._cache
        assert "direct-value" in resolver._cache

    def test_multiple_services_in_encrypted_file(self, tmp_path):
        """Test storing credentials for multiple services."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        # Store credentials for different services
        backend.set("gitea", "api_token", "gitea-token")
        backend.set("gitea", "webhook_secret", "gitea-webhook")
        backend.set("claude", "api_key", "claude-key")
        backend.set("github", "api_token", "github-token")

        # Verify all can be retrieved
        assert backend.get("gitea", "api_token") == "gitea-token"
        assert backend.get("gitea", "webhook_secret") == "gitea-webhook"
        assert backend.get("claude", "api_key") == "claude-key"
        assert backend.get("github", "api_token") == "github-token"

        # Delete one service's credential
        backend.delete("gitea", "api_token")

        # Verify others still exist
        assert backend.get("gitea", "api_token") is None
        assert backend.get("gitea", "webhook_secret") == "gitea-webhook"
        assert backend.get("claude", "api_key") == "claude-key"

    def test_resolver_error_recovery(self, tmp_path):
        """Test resolver handles errors gracefully."""
        from repo_sapiens.credentials import CredentialNotFoundError

        resolver = CredentialResolver()

        # Try to resolve non-existent env var
        with pytest.raises(CredentialNotFoundError):
            resolver.resolve("${NONEXISTENT_VAR}")

        # Resolver should still work for other credentials
        os.environ["TEST_GOOD_VAR"] = "good-value"
        result = resolver.resolve("${TEST_GOOD_VAR}")
        assert result == "good-value"

    def test_persistence_after_process_restart(self, tmp_path):
        """Test credentials persist across simulated process restarts."""
        file_path = tmp_path / "credentials.enc"
        password = "persistent-password"

        # First "process"
        backend1 = EncryptedFileBackend(file_path, password)
        backend1.set("service1", "key1", "value1")
        backend1.set("service2", "key2", "value2")
        del backend1  # Simulate process end

        # Second "process"
        backend2 = EncryptedFileBackend(file_path, password)
        assert backend2.get("service1", "key1") == "value1"
        assert backend2.get("service2", "key2") == "value2"

        # Update in second process
        backend2.set("service1", "key1", "updated-value1")
        del backend2

        # Third "process"
        backend3 = EncryptedFileBackend(file_path, password)
        assert backend3.get("service1", "key1") == "updated-value1"
        assert backend3.get("service2", "key2") == "value2"

    def test_mixed_backend_types_in_resolver(self, tmp_path):
        """Test resolver handles mixed backend types correctly."""
        # Set up all backends
        os.environ["ENV_SECRET"] = "env-value"

        file_path = tmp_path / "credentials.enc"
        encrypted = EncryptedFileBackend(file_path, "password")
        encrypted.set("encrypted", "secret", "encrypted-value")

        resolver = CredentialResolver(encrypted_file_path=file_path, encrypted_master_password="password")

        # Resolve from each backend in sequence
        results = {
            "env": resolver.resolve("${ENV_SECRET}"),
            "encrypted": resolver.resolve("@encrypted:encrypted/secret"),
            "direct": resolver.resolve("direct-value"),
        }

        assert results == {
            "env": "env-value",
            "encrypted": "encrypted-value",
            "direct": "direct-value",
        }

    def test_resolver_with_config_like_data(self, tmp_path):
        """Test resolver with realistic config-like data."""
        # Simulate a configuration file with mixed credential types
        config_values = {
            "git_token": "@encrypted:gitea/api_token",
            "ai_key": "${CLAUDE_API_KEY}",
            "webhook_url": "https://example.com/webhook",  # Direct value
            "admin_token": "@encrypted:admin/token",
        }

        # Set up backends
        os.environ["CLAUDE_API_KEY"] = "sk-ant-test-key"

        file_path = tmp_path / "credentials.enc"
        encrypted = EncryptedFileBackend(file_path, "password")
        encrypted.set("gitea", "api_token", "gitea-secret-token")
        encrypted.set("admin", "token", "admin-secret-token")

        resolver = CredentialResolver(encrypted_file_path=file_path, encrypted_master_password="password")

        # Resolve all config values
        resolved = {key: resolver.resolve(value) for key, value in config_values.items()}

        assert resolved == {
            "git_token": "gitea-secret-token",
            "ai_key": "sk-ant-test-key",
            "webhook_url": "https://example.com/webhook",
            "admin_token": "admin-secret-token",
        }

    def test_backend_availability_check(self):
        """Test backend availability detection."""
        # Environment backend should always be available
        env_backend = EnvironmentBackend()
        assert env_backend.available is True

        # Encrypted backend should be available if cryptography installed
        encrypted_backend = EncryptedFileBackend(Path("/tmp/test.enc"), "password")
        assert encrypted_backend.available is True

    def test_concurrent_access_to_encrypted_file(self, tmp_path):
        """Test multiple backend instances can access same file."""
        file_path = tmp_path / "credentials.enc"
        password = "shared-password"

        # Create two backends pointing to same file
        backend1 = EncryptedFileBackend(file_path, password)
        backend2 = EncryptedFileBackend(file_path, password)

        # Write with backend1
        backend1.set("service", "key1", "value1")

        # Read with backend2 (should see the change)
        # Note: This requires clearing cache
        backend2._credentials_cache = None
        assert backend2.get("service", "key1") == "value1"

        # Write with backend2
        backend2.set("service", "key2", "value2")

        # Read with backend1
        backend1._credentials_cache = None
        assert backend1.get("service", "key2") == "value2"

    def test_empty_credentials_file_handling(self, tmp_path):
        """Test handling of empty or missing credentials file."""
        file_path = tmp_path / "credentials.enc"
        backend = EncryptedFileBackend(file_path, "password")

        # Getting from non-existent file should return None
        assert backend.get("service", "key") is None

        # Setting should create the file
        backend.set("service", "key", "value")
        assert file_path.exists()

        # Getting should now work
        assert backend.get("service", "key") == "value"
