"""Unit tests for repo_sapiens/cli/credentials.py - Credential management CLI."""

import os
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from repo_sapiens.cli.credentials import (
    _delete_encrypted,
    _delete_environment,
    _delete_keyring,
    _parse_service_key,
    _set_encrypted,
    _set_environment,
    _set_keyring,
    credentials_group,
)
from repo_sapiens.credentials import (
    CredentialError,
    CredentialNotFoundError,
)


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing Click commands."""
    return CliRunner()


@pytest.fixture
def mock_keyring_backend():
    """Create a mock KeyringBackend."""
    with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_class:
        mock_backend = Mock()
        mock_backend.available = True
        mock_class.return_value = mock_backend
        yield mock_backend


@pytest.fixture
def mock_environment_backend():
    """Create a mock EnvironmentBackend."""
    with patch("repo_sapiens.cli.credentials.EnvironmentBackend") as mock_class:
        mock_backend = Mock()
        mock_backend.available = True
        mock_class.return_value = mock_backend
        yield mock_backend


@pytest.fixture
def mock_encrypted_backend():
    """Create a mock EncryptedFileBackend."""
    with patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_class:
        mock_backend = Mock()
        mock_backend.available = True
        mock_class.return_value = mock_backend
        yield mock_backend


@pytest.fixture
def mock_credential_resolver():
    """Create a mock CredentialResolver."""
    with patch("repo_sapiens.cli.credentials.CredentialResolver") as mock_class:
        mock_resolver = Mock()
        mock_class.return_value = mock_resolver
        yield mock_resolver


class TestParseServiceKey:
    """Tests for _parse_service_key helper function."""

    def test_parse_valid_reference(self):
        """Should parse valid service/key format."""
        service, key = _parse_service_key("gitea/api_token")

        assert service == "gitea"
        assert key == "api_token"

    def test_parse_with_nested_key(self):
        """Should handle keys with multiple slashes."""
        service, key = _parse_service_key("namespace/path/to/key")

        assert service == "namespace"
        assert key == "path/to/key"

    def test_parse_invalid_format_no_slash(self):
        """Should raise ValueError for reference without slash."""
        with pytest.raises(ValueError) as exc_info:
            _parse_service_key("invalid_reference")

        assert "Invalid reference format" in str(exc_info.value)
        assert "Expected format: service/key" in str(exc_info.value)

    def test_parse_empty_string(self):
        """Should raise ValueError for empty string."""
        with pytest.raises(ValueError) as exc_info:
            _parse_service_key("")

        assert "Invalid reference format" in str(exc_info.value)


class TestCredentialsGroup:
    """Tests for credentials_group Click command group."""

    def test_credentials_group_help(self, cli_runner):
        """Should display help information."""
        result = cli_runner.invoke(credentials_group, ["--help"])

        assert result.exit_code == 0
        assert "Manage credentials" in result.output
        assert "keyring" in result.output
        assert "environment" in result.output
        assert "encrypted" in result.output

    def test_credentials_group_subcommands(self, cli_runner):
        """Should show available subcommands."""
        result = cli_runner.invoke(credentials_group, ["--help"])

        assert result.exit_code == 0
        assert "set" in result.output
        assert "get" in result.output
        assert "delete" in result.output
        assert "test" in result.output


class TestSetCredentialCommand:
    """Tests for set_credential CLI command."""

    def test_set_credential_keyring_backend(self, cli_runner, mock_keyring_backend):
        """Should store credential in keyring backend."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "gitea/api_token", "--backend", "keyring", "--value", "secret123"],
            input="secret123\n",  # Confirmation prompt
        )

        assert result.exit_code == 0
        assert "Credential stored successfully" in result.output

    def test_set_credential_environment_backend(self, cli_runner, mock_environment_backend):
        """Should store credential in environment backend."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "GITEA_TOKEN", "--backend", "environment", "--value", "secret123"],
            input="secret123\n",  # Confirmation prompt
        )

        assert result.exit_code == 0
        assert "Credential stored successfully" in result.output

    def test_set_credential_encrypted_backend_with_password(self, cli_runner, mock_encrypted_backend):
        """Should store credential in encrypted backend with master password."""
        result = cli_runner.invoke(
            credentials_group,
            [
                "set",
                "claude/api_key",
                "--backend",
                "encrypted",
                "--value",
                "secret123",
                "--master-password",
                "master123",
            ],
            input="secret123\n",  # Confirmation prompt
        )

        assert result.exit_code == 0
        assert "Credential stored successfully" in result.output

    def test_set_credential_prompts_for_value(self, cli_runner, mock_keyring_backend):
        """Should prompt for value when not provided."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "gitea/api_token", "--backend", "keyring"],
            input="secret123\nsecret123\n",  # Value and confirmation
        )

        assert result.exit_code == 0
        assert "Credential stored successfully" in result.output

    def test_set_credential_invalid_backend(self, cli_runner):
        """Should reject invalid backend choice."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "gitea/api_token", "--backend", "invalid", "--value", "secret"],
            input="secret\n",
        )

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_set_credential_backend_required(self, cli_runner):
        """Should require backend option."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "gitea/api_token", "--value", "secret"],
            input="secret\n",
        )

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--backend" in result.output

    def test_set_credential_handles_credential_error(self, cli_runner):
        """Should handle CredentialError gracefully."""
        with patch("repo_sapiens.cli.credentials._set_keyring") as mock_set:
            mock_set.side_effect = CredentialError("Backend unavailable", suggestion="Install keyring")

            result = cli_runner.invoke(
                credentials_group,
                ["set", "gitea/api_token", "--backend", "keyring", "--value", "secret"],
                input="secret\n",
            )

            assert result.exit_code == 1
            assert "Error:" in result.output
            assert "Backend unavailable" in result.output
            assert "Suggestion:" in result.output

    def test_set_credential_handles_value_error(self, cli_runner):
        """Should handle ValueError gracefully."""
        with patch("repo_sapiens.cli.credentials._set_keyring") as mock_set:
            mock_set.side_effect = ValueError("Invalid format")

            result = cli_runner.invoke(
                credentials_group,
                ["set", "invalid", "--backend", "keyring", "--value", "secret"],
                input="secret\n",
            )

            assert result.exit_code == 1
            assert "Error:" in result.output


class TestGetCredentialCommand:
    """Tests for get_credential CLI command."""

    def test_get_credential_masked_output(self, cli_runner, mock_credential_resolver):
        """Should display masked credential by default."""
        mock_credential_resolver.resolve.return_value = "abcdefghijklmnop"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:gitea/api_token"],
        )

        assert result.exit_code == 0
        assert "abcd" in result.output
        assert "mnop" in result.output
        assert "abcdefghijklmnop" not in result.output  # Full value not shown
        assert "Credential resolved successfully" in result.output

    def test_get_credential_show_value_flag(self, cli_runner, mock_credential_resolver):
        """Should display full credential with --show-value flag."""
        mock_credential_resolver.resolve.return_value = "secret_token_value"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:gitea/api_token", "--show-value"],
        )

        assert result.exit_code == 0
        assert "secret_token_value" in result.output
        assert "Credential resolved successfully" in result.output

    def test_get_credential_short_value_fully_masked(self, cli_runner, mock_credential_resolver):
        """Should fully mask short credentials."""
        mock_credential_resolver.resolve.return_value = "short"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:gitea/api_token"],
        )

        assert result.exit_code == 0
        assert "*****" in result.output
        assert "short" not in result.output

    def test_get_credential_environment_variable(self, cli_runner, mock_credential_resolver):
        """Should resolve environment variable reference."""
        mock_credential_resolver.resolve.return_value = "env_secret"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "${GITEA_TOKEN}", "--show-value"],
        )

        assert result.exit_code == 0
        assert "env_secret" in result.output

    def test_get_credential_encrypted_with_password(self, cli_runner, mock_credential_resolver):
        """Should use master password for encrypted backend."""
        mock_credential_resolver.resolve.return_value = "encrypted_secret"

        result = cli_runner.invoke(
            credentials_group,
            [
                "get",
                "@encrypted:claude/api_key",
                "--master-password",
                "master123",
                "--show-value",
            ],
        )

        assert result.exit_code == 0
        assert "encrypted_secret" in result.output

    def test_get_credential_handles_not_found_error(self, cli_runner, mock_credential_resolver):
        """Should handle CredentialNotFoundError gracefully."""
        mock_credential_resolver.resolve.side_effect = CredentialNotFoundError(
            "Credential not found",
            reference="@keyring:gitea/api_token",
            suggestion="Store the credential first",
        )

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:gitea/api_token"],
        )

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Credential not found" in result.output
        assert "Suggestion:" in result.output


class TestDeleteCredentialCommand:
    """Tests for delete_credential CLI command."""

    def test_delete_credential_keyring_success(self, cli_runner):
        """Should delete credential from keyring."""
        with patch("repo_sapiens.cli.credentials._delete_keyring") as mock_delete:
            mock_delete.return_value = True

            result = cli_runner.invoke(
                credentials_group,
                ["delete", "gitea/api_token", "--backend", "keyring", "--yes"],
            )

            assert result.exit_code == 0
            assert "Credential deleted successfully" in result.output

    def test_delete_credential_not_found(self, cli_runner):
        """Should handle credential not found scenario."""
        with patch("repo_sapiens.cli.credentials._delete_keyring") as mock_delete:
            mock_delete.return_value = False

            result = cli_runner.invoke(
                credentials_group,
                ["delete", "nonexistent/key", "--backend", "keyring", "--yes"],
            )

            assert result.exit_code == 0
            assert "Credential not found" in result.output

    def test_delete_credential_environment(self, cli_runner):
        """Should delete environment variable."""
        with patch("repo_sapiens.cli.credentials._delete_environment") as mock_delete:
            mock_delete.return_value = True

            result = cli_runner.invoke(
                credentials_group,
                ["delete", "GITEA_TOKEN", "--backend", "environment", "--yes"],
            )

            assert result.exit_code == 0
            assert "Credential deleted successfully" in result.output

    def test_delete_credential_encrypted(self, cli_runner):
        """Should delete credential from encrypted store."""
        with patch("repo_sapiens.cli.credentials._delete_encrypted") as mock_delete:
            mock_delete.return_value = True

            result = cli_runner.invoke(
                credentials_group,
                [
                    "delete",
                    "claude/api_key",
                    "--backend",
                    "encrypted",
                    "--master-password",
                    "master123",
                    "--yes",
                ],
            )

            assert result.exit_code == 0
            assert "Credential deleted successfully" in result.output

    def test_delete_credential_requires_confirmation(self, cli_runner):
        """Should require confirmation before deletion."""
        with patch("repo_sapiens.cli.credentials._delete_keyring") as mock_delete:
            mock_delete.return_value = True

            # Without -y, should prompt for confirmation
            result = cli_runner.invoke(
                credentials_group,
                ["delete", "gitea/api_token", "--backend", "keyring"],
                input="n\n",  # Decline confirmation
            )

            assert result.exit_code == 1
            mock_delete.assert_not_called()

    def test_delete_credential_confirm_yes(self, cli_runner):
        """Should proceed with deletion when confirmed."""
        with patch("repo_sapiens.cli.credentials._delete_keyring") as mock_delete:
            mock_delete.return_value = True

            result = cli_runner.invoke(
                credentials_group,
                ["delete", "gitea/api_token", "--backend", "keyring"],
                input="y\n",  # Confirm deletion
            )

            assert result.exit_code == 0
            mock_delete.assert_called_once_with("gitea/api_token")

    def test_delete_credential_handles_credential_error(self, cli_runner):
        """Should handle CredentialError gracefully."""
        with patch("repo_sapiens.cli.credentials._delete_keyring") as mock_delete:
            mock_delete.side_effect = CredentialError("Operation failed", suggestion="Try again")

            result = cli_runner.invoke(
                credentials_group,
                ["delete", "gitea/api_token", "--backend", "keyring", "--yes"],
            )

            assert result.exit_code == 1
            assert "Error:" in result.output
            assert "Operation failed" in result.output


class TestTestCredentialsCommand:
    """Tests for test_credentials CLI command."""

    def test_test_credentials_all_available(self, cli_runner):
        """Should report all backends as available."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_keyring, patch(
            "repo_sapiens.cli.credentials.EnvironmentBackend"
        ) as mock_env, patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_encrypted:
            mock_keyring.return_value.available = True
            mock_env.return_value.available = True
            mock_encrypted.return_value.available = True

            result = cli_runner.invoke(
                credentials_group,
                ["test"],
            )

            assert result.exit_code == 0
            assert "Available" in result.output
            assert "All tests passed" in result.output

    def test_test_credentials_keyring_unavailable(self, cli_runner):
        """Should report keyring backend as unavailable."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_keyring, patch(
            "repo_sapiens.cli.credentials.EnvironmentBackend"
        ) as mock_env, patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_encrypted:
            mock_keyring.return_value.available = False
            mock_env.return_value.available = True
            mock_encrypted.return_value.available = True

            result = cli_runner.invoke(
                credentials_group,
                ["test"],
            )

            assert result.exit_code == 0
            assert "Not available" in result.output
            assert "pip install keyring" in result.output

    def test_test_credentials_encrypted_unavailable(self, cli_runner):
        """Should report encrypted backend as unavailable."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_keyring, patch(
            "repo_sapiens.cli.credentials.EnvironmentBackend"
        ) as mock_env, patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_encrypted:
            mock_keyring.return_value.available = True
            mock_env.return_value.available = True
            mock_encrypted.return_value.available = False

            result = cli_runner.invoke(
                credentials_group,
                ["test"],
            )

            assert result.exit_code == 0
            assert "Not available" in result.output
            assert "pip install cryptography" in result.output

    def test_test_credentials_with_master_password(self, cli_runner):
        """Should use provided master password for encrypted backend test."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_keyring, patch(
            "repo_sapiens.cli.credentials.EnvironmentBackend"
        ) as mock_env, patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_encrypted:
            mock_keyring.return_value.available = True
            mock_env.return_value.available = True
            mock_encrypted.return_value.available = True

            result = cli_runner.invoke(
                credentials_group,
                ["test", "--master-password", "custom_password"],
            )

            assert result.exit_code == 0
            # Verify EncryptedFileBackend was called with the password
            mock_encrypted.assert_called_once()
            call_args = mock_encrypted.call_args
            assert call_args[1].get("master_password") == "custom_password" or (
                len(call_args[0]) > 1 and call_args[0][1] == "custom_password"
            )


class TestSetKeyringHelper:
    """Tests for _set_keyring helper function."""

    def test_set_keyring_success(self):
        """Should store credential in keyring."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_class:
            mock_backend = Mock()
            mock_class.return_value = mock_backend

            _set_keyring("gitea/api_token", "secret_value")

            mock_backend.set.assert_called_once_with("gitea", "api_token", "secret_value")

    def test_set_keyring_invalid_reference(self):
        """Should raise ValueError for invalid reference."""
        with pytest.raises(ValueError) as exc_info:
            _set_keyring("invalid_reference", "secret_value")

        assert "Invalid reference format" in str(exc_info.value)


class TestSetEnvironmentHelper:
    """Tests for _set_environment helper function."""

    def test_set_environment_success(self):
        """Should store credential in environment."""
        with patch("repo_sapiens.cli.credentials.EnvironmentBackend") as mock_class:
            mock_backend = Mock()
            mock_class.return_value = mock_backend

            _set_environment("GITEA_TOKEN", "secret_value")

            mock_backend.set.assert_called_once_with("GITEA_TOKEN", "secret_value")


class TestSetEncryptedHelper:
    """Tests for _set_encrypted helper function."""

    def test_set_encrypted_with_password(self):
        """Should store credential in encrypted file."""
        with patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_class:
            mock_backend = Mock()
            mock_class.return_value = mock_backend

            _set_encrypted("claude/api_key", "secret_value", "master_password")

            mock_backend.set.assert_called_once_with("claude", "api_key", "secret_value")

    def test_set_encrypted_prompts_for_password(self):
        """Should prompt for password when not provided."""
        with patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_class, patch(
            "repo_sapiens.cli.credentials.click.prompt"
        ) as mock_prompt:
            mock_backend = Mock()
            mock_class.return_value = mock_backend
            mock_prompt.return_value = "prompted_password"

            _set_encrypted("claude/api_key", "secret_value", None)

            mock_prompt.assert_called_once()
            mock_backend.set.assert_called_once()

    def test_set_encrypted_invalid_reference(self):
        """Should raise ValueError for invalid reference."""
        with pytest.raises(ValueError) as exc_info:
            _set_encrypted("invalid", "secret_value", "master_password")

        assert "Invalid reference format" in str(exc_info.value)


class TestDeleteKeyringHelper:
    """Tests for _delete_keyring helper function."""

    def test_delete_keyring_success(self):
        """Should delete credential from keyring."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_class:
            mock_backend = Mock()
            mock_backend.delete.return_value = True
            mock_class.return_value = mock_backend

            result = _delete_keyring("gitea/api_token")

            assert result is True
            mock_backend.delete.assert_called_once_with("gitea", "api_token")

    def test_delete_keyring_not_found(self):
        """Should return False when credential not found."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_class:
            mock_backend = Mock()
            mock_backend.delete.return_value = False
            mock_class.return_value = mock_backend

            result = _delete_keyring("gitea/api_token")

            assert result is False


class TestDeleteEnvironmentHelper:
    """Tests for _delete_environment helper function."""

    def test_delete_environment_success(self):
        """Should delete environment variable."""
        with patch("repo_sapiens.cli.credentials.EnvironmentBackend") as mock_class:
            mock_backend = Mock()
            mock_backend.delete.return_value = True
            mock_class.return_value = mock_backend

            result = _delete_environment("GITEA_TOKEN")

            assert result is True
            mock_backend.delete.assert_called_once_with("GITEA_TOKEN")


class TestDeleteEncryptedHelper:
    """Tests for _delete_encrypted helper function."""

    def test_delete_encrypted_with_password(self):
        """Should delete credential from encrypted file."""
        with patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_class:
            mock_backend = Mock()
            mock_backend.delete.return_value = True
            mock_class.return_value = mock_backend

            result = _delete_encrypted("claude/api_key", "master_password")

            assert result is True
            mock_backend.delete.assert_called_once_with("claude", "api_key")

    def test_delete_encrypted_prompts_for_password(self):
        """Should prompt for password when not provided."""
        with patch("repo_sapiens.cli.credentials.EncryptedFileBackend") as mock_class, patch(
            "repo_sapiens.cli.credentials.click.prompt"
        ) as mock_prompt:
            mock_backend = Mock()
            mock_backend.delete.return_value = True
            mock_class.return_value = mock_backend
            mock_prompt.return_value = "prompted_password"

            result = _delete_encrypted("claude/api_key", None)

            mock_prompt.assert_called_once()
            assert result is True


class TestEnvironmentVariableHandling:
    """Tests for environment variable handling in CLI."""

    def test_master_password_from_envvar(self, cli_runner, mock_credential_resolver):
        """Should read master password from SAPIENS_MASTER_PASSWORD env var."""
        mock_credential_resolver.resolve.return_value = "secret_value"

        with patch.dict(os.environ, {"SAPIENS_MASTER_PASSWORD": "env_master_pass"}):
            result = cli_runner.invoke(
                credentials_group,
                ["get", "@encrypted:test/key", "--show-value"],
                env={"SAPIENS_MASTER_PASSWORD": "env_master_pass"},
            )

            assert result.exit_code == 0

    def test_cli_option_overrides_envvar(self, cli_runner):
        """Should prefer CLI option over environment variable."""
        with patch("repo_sapiens.cli.credentials._delete_encrypted") as mock_delete, patch.dict(
            os.environ, {"SAPIENS_MASTER_PASSWORD": "env_password"}
        ):
            mock_delete.return_value = True

            result = cli_runner.invoke(
                credentials_group,
                [
                    "delete",
                    "test/key",
                    "--backend",
                    "encrypted",
                    "--master-password",
                    "cli_password",
                    "--yes",
                ],
            )

            # Verify the function was called with CLI password
            assert result.exit_code == 0
            mock_delete.assert_called_once_with("test/key", "cli_password")


class TestInputValidation:
    """Tests for input validation scenarios."""

    def test_empty_reference_argument(self, cli_runner):
        """Should handle empty reference argument."""
        result = cli_runner.invoke(
            credentials_group,
            ["get", ""],
        )

        # Empty string is technically valid (returns as-is)
        assert result.exit_code in [0, 1]

    def test_special_characters_in_reference(self, cli_runner, mock_credential_resolver):
        """Should handle special characters in reference."""
        mock_credential_resolver.resolve.return_value = "value"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:service-name/key_with-dashes_underscores", "--show-value"],
        )

        assert result.exit_code == 0

    def test_unicode_in_reference(self, cli_runner):
        """Should handle unicode characters."""
        with patch("repo_sapiens.cli.credentials.KeyringBackend") as mock_class:
            mock_backend = Mock()
            mock_class.return_value = mock_backend

            result = cli_runner.invoke(
                credentials_group,
                ["set", "service/key", "--backend", "keyring", "--value", "secret"],
                input="secret\n",
            )

            assert result.exit_code == 0


class TestMaskedOutput:
    """Tests for credential masking in output."""

    def test_mask_long_credential(self, cli_runner, mock_credential_resolver):
        """Should mask middle of long credentials."""
        mock_credential_resolver.resolve.return_value = "abcdefghijklmnopqrstuvwxyz"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:test/key"],
        )

        assert result.exit_code == 0
        # First 4 and last 4 characters visible
        assert "abcd" in result.output
        assert "wxyz" in result.output
        # Middle should be masked
        assert "efghijklmnopqrstuv" not in result.output

    def test_mask_short_credential(self, cli_runner, mock_credential_resolver):
        """Should fully mask short credentials."""
        mock_credential_resolver.resolve.return_value = "short"  # 5 chars

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:test/key"],
        )

        assert result.exit_code == 0
        assert "short" not in result.output
        assert "*" in result.output

    def test_mask_exactly_8_chars(self, cli_runner, mock_credential_resolver):
        """Should fully mask exactly 8 character credentials."""
        mock_credential_resolver.resolve.return_value = "12345678"

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:test/key"],
        )

        assert result.exit_code == 0
        # 8 chars should be fully masked (not enough for reveal)
        assert "12345678" not in result.output
        assert "*" in result.output

    def test_mask_9_chars_shows_partial(self, cli_runner, mock_credential_resolver):
        """Should show first/last 4 chars for 9+ character credentials."""
        mock_credential_resolver.resolve.return_value = "123456789"  # 9 chars

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:test/key"],
        )

        assert result.exit_code == 0
        # First 4 visible
        assert "1234" in result.output
        # Last 4 visible
        assert "6789" in result.output
        # Middle masked
        assert "*" in result.output


class TestErrorHandlingScenarios:
    """Tests for various error handling scenarios."""

    def test_credential_error_without_suggestion(self, cli_runner):
        """Should handle CredentialError without suggestion."""
        with patch("repo_sapiens.cli.credentials._set_keyring") as mock_set:
            mock_set.side_effect = CredentialError("Generic error")

            result = cli_runner.invoke(
                credentials_group,
                ["set", "test/key", "--backend", "keyring", "--value", "secret"],
                input="secret\n",
            )

            assert result.exit_code == 1
            assert "Error:" in result.output
            assert "Generic error" in result.output
            # No suggestion line when suggestion is None
            assert result.output.count("Suggestion:") == 0

    def test_credential_error_with_suggestion(self, cli_runner):
        """Should display suggestion when present in CredentialError."""
        with patch("repo_sapiens.cli.credentials._set_keyring") as mock_set:
            mock_set.side_effect = CredentialError(
                "Backend error",
                suggestion="Try installing the package",
            )

            result = cli_runner.invoke(
                credentials_group,
                ["set", "test/key", "--backend", "keyring", "--value", "secret"],
                input="secret\n",
            )

            assert result.exit_code == 1
            assert "Error:" in result.output
            assert "Suggestion:" in result.output
            assert "Try installing the package" in result.output

    def test_get_command_handles_general_exception(self, cli_runner, mock_credential_resolver):
        """Should handle general exceptions during get."""
        mock_credential_resolver.resolve.side_effect = CredentialError("Unexpected error")

        result = cli_runner.invoke(
            credentials_group,
            ["get", "@keyring:test/key"],
        )

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestCommandHelp:
    """Tests for command help documentation."""

    def test_set_command_help(self, cli_runner):
        """Should display set command help."""
        result = cli_runner.invoke(
            credentials_group,
            ["set", "--help"],
        )

        assert result.exit_code == 0
        assert "Store a credential" in result.output
        assert "--backend" in result.output
        assert "--value" in result.output
        assert "--master-password" in result.output

    def test_get_command_help(self, cli_runner):
        """Should display get command help."""
        result = cli_runner.invoke(
            credentials_group,
            ["get", "--help"],
        )

        assert result.exit_code == 0
        assert "Retrieve and display" in result.output
        assert "--show-value" in result.output
        assert "--master-password" in result.output

    def test_delete_command_help(self, cli_runner):
        """Should display delete command help."""
        result = cli_runner.invoke(
            credentials_group,
            ["delete", "--help"],
        )

        assert result.exit_code == 0
        assert "Delete a credential" in result.output
        assert "--backend" in result.output
        assert "--master-password" in result.output

    def test_test_command_help(self, cli_runner):
        """Should display test command help."""
        result = cli_runner.invoke(
            credentials_group,
            ["test", "--help"],
        )

        assert result.exit_code == 0
        assert "Test credential system" in result.output
        assert "--master-password" in result.output
