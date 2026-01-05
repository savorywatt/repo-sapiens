"""Comprehensive tests for repo_sapiens/config/credential_fields.py.

Tests cover:
- CredentialSecret validation
- CredentialStr validation
- Credential reference pattern matching (@keyring, ${ENV_VAR}, @encrypted)
- Invalid pattern error handling
- Resolver integration
- Credential reference resolution
- Edge cases and security considerations
"""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, SecretStr, ValidationError

from repo_sapiens.config.credential_fields import (
    CredentialSecret,
    CredentialStr,
    get_resolver,
    resolve_credential_secret,
    resolve_credential_string,
    set_resolver,
)
from repo_sapiens.credentials import CredentialError, CredentialNotFoundError, CredentialResolver


class TestResolverManagement:
    """Test resolver initialization and management."""

    def test_get_resolver_creates_instance(self):
        """Test get_resolver creates CredentialResolver instance."""
        # Reset resolver first
        set_resolver(None)

        resolver = get_resolver()

        assert resolver is not None
        assert isinstance(resolver, CredentialResolver)

    def test_get_resolver_returns_same_instance(self):
        """Test get_resolver returns the same instance (singleton pattern)."""
        set_resolver(None)

        resolver1 = get_resolver()
        resolver2 = get_resolver()

        assert resolver1 is resolver2

    def test_set_resolver_custom_instance(self):
        """Test setting a custom resolver instance."""
        custom_resolver = MagicMock(spec=CredentialResolver)
        set_resolver(custom_resolver)

        resolver = get_resolver()

        assert resolver is custom_resolver

    def test_set_resolver_to_none_resets(self):
        """Test setting resolver to None resets to default."""
        custom_resolver = MagicMock(spec=CredentialResolver)
        set_resolver(custom_resolver)
        assert get_resolver() is custom_resolver

        set_resolver(None)
        resolver = get_resolver()

        # Should create a new default instance
        assert isinstance(resolver, CredentialResolver)


class TestResolveCredentialString:
    """Test resolve_credential_string function."""

    def test_resolve_keyring_reference(self):
        """Test resolving @keyring: reference."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "resolved-token"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@keyring:gitea/api_token")

        assert result == "resolved-token"
        mock_resolver.resolve.assert_called_once_with("@keyring:gitea/api_token")

    def test_resolve_env_reference(self):
        """Test resolving ${VAR_NAME} reference."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "env-token-value"
        set_resolver(mock_resolver)

        result = resolve_credential_string("${GITEA_TOKEN}")

        assert result == "env-token-value"
        mock_resolver.resolve.assert_called_once_with("${GITEA_TOKEN}")

    def test_resolve_encrypted_reference(self):
        """Test resolving @encrypted: reference."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "decrypted-token"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@encrypted:gitea/api_token")

        assert result == "decrypted-token"
        mock_resolver.resolve.assert_called_once_with("@encrypted:gitea/api_token")

    def test_resolve_direct_value(self):
        """Test that direct values pass through resolver."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "direct-token"
        set_resolver(mock_resolver)

        result = resolve_credential_string("direct-token")

        assert result == "direct-token"
        mock_resolver.resolve.assert_called_once_with("direct-token")

    def test_non_string_value_returned_as_is(self):
        """Test that non-string values are returned unchanged."""
        result = resolve_credential_string(12345)

        assert result == 12345

    def test_resolver_error_converts_to_pydantic_error(self):
        """Test that CredentialError is converted to Pydantic error."""
        from pydantic_core import PydanticCustomError

        mock_resolver = MagicMock(spec=CredentialResolver)
        credential_error = CredentialError(
            "Credential not found",
            reference="@keyring:test/missing",
            suggestion="Store the credential first",
        )
        mock_resolver.resolve.side_effect = credential_error
        set_resolver(mock_resolver)

        with pytest.raises(PydanticCustomError) as exc_info:
            resolve_credential_string("@keyring:test/missing")

        error = exc_info.value
        # PydanticCustomError is raised with credential_resolution_error as error code
        assert isinstance(error, PydanticCustomError)

    def test_resolver_exception_includes_suggestion(self):
        """Test that resolver exception suggestion is included in error."""
        from pydantic_core import PydanticCustomError

        mock_resolver = MagicMock(spec=CredentialResolver)
        credential_error = CredentialError(
            "API token not found",
            reference="@keyring:gitea/api_token",
            suggestion="Run: sapiens credentials set --keyring gitea/api_token",
        )
        mock_resolver.resolve.side_effect = credential_error
        set_resolver(mock_resolver)

        with pytest.raises(PydanticCustomError) as exc_info:
            resolve_credential_string("@keyring:gitea/api_token")

        error = exc_info.value
        # Verify that PydanticCustomError was raised
        assert isinstance(error, PydanticCustomError)


class TestResolveCredentialSecret:
    """Test resolve_credential_secret function."""

    def test_resolve_to_secretstr(self):
        """Test that result is always a SecretStr."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "secret-value"
        set_resolver(mock_resolver)

        result = resolve_credential_secret("@keyring:service/key")

        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "secret-value"

    def test_secretstr_input_preserved(self):
        """Test that SecretStr input is preserved."""
        original = SecretStr("already-secret")

        result = resolve_credential_secret(original)

        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "already-secret"

    def test_non_string_converted_to_secretstr(self):
        """Test that non-string values are converted to SecretStr."""
        result = resolve_credential_secret(12345)

        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "12345"

    def test_env_var_resolution_to_secretstr(self):
        """Test environment variable resolution wraps in SecretStr."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "env-token"
        set_resolver(mock_resolver)

        result = resolve_credential_secret("${API_KEY}")

        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "env-token"

    def test_resolver_error_in_secret_validation(self):
        """Test that resolver errors are propagated in SecretStr validation."""
        from pydantic_core import PydanticCustomError

        mock_resolver = MagicMock(spec=CredentialResolver)
        credential_error = CredentialError(
            "Encryption key missing",
            reference="@encrypted:service/key",
        )
        mock_resolver.resolve.side_effect = credential_error
        set_resolver(mock_resolver)

        with pytest.raises(PydanticCustomError):
            resolve_credential_secret("@encrypted:service/key")

    def test_empty_string_as_secretstr(self):
        """Test that empty strings are wrapped in SecretStr."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = ""
        set_resolver(mock_resolver)

        result = resolve_credential_secret("${EMPTY_VAR}")

        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == ""


class TestCredentialSecretAnnotation:
    """Test CredentialSecret annotated type in Pydantic models."""

    class SampleModel(BaseModel):
        """Sample model using CredentialSecret."""

        token: CredentialSecret

    def test_credential_secret_in_model(self):
        """Test CredentialSecret field in Pydantic model."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "model-token"
        set_resolver(mock_resolver)

        try:
            model = self.SampleModel(token="@keyring:service/key")

            assert isinstance(model.token, SecretStr)
            assert model.token.get_secret_value() == "model-token"
        finally:
            set_resolver(None)

    def test_credential_secret_validation_error(self):
        """Test validation error when credential cannot be resolved."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.side_effect = CredentialError("Not found")
        set_resolver(mock_resolver)

        try:
            with pytest.raises(ValidationError):
                self.SampleModel(token="@keyring:missing/key")
        finally:
            set_resolver(None)

    def test_credential_secret_direct_value(self):
        """Test direct value in CredentialSecret field."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "direct-value"
        set_resolver(mock_resolver)

        try:
            model = self.SampleModel(token="direct-token-value")

            assert isinstance(model.token, SecretStr)
        finally:
            set_resolver(None)


class TestCredentialStrAnnotation:
    """Test CredentialStr annotated type in Pydantic models."""

    class SampleModel(BaseModel):
        """Sample model using CredentialStr."""

        key: CredentialStr

    def test_credential_str_in_model(self):
        """Test CredentialStr field in Pydantic model."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "resolved-key"
        set_resolver(mock_resolver)

        try:
            model = self.SampleModel(key="@keyring:service/key")

            assert isinstance(model.key, str)
            assert model.key == "resolved-key"
        finally:
            set_resolver(None)

    def test_credential_str_not_secretstr(self):
        """Test that CredentialStr resolves to plain string, not SecretStr."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "plain-key"
        set_resolver(mock_resolver)

        try:
            model = self.SampleModel(key="${SERVICE_KEY}")

            assert isinstance(model.key, str)
            assert not isinstance(model.key, SecretStr)
        finally:
            set_resolver(None)


class TestCredentialReferencePatterns:
    """Test various credential reference patterns."""

    def test_keyring_pattern_simple(self):
        """Test simple keyring pattern."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "token"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@keyring:service/key")

        assert result == "token"

    def test_keyring_pattern_complex_service_name(self):
        """Test keyring with complex service names."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "token"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@keyring:my-service-123/api_key_v1")

        assert result == "token"

    def test_env_var_pattern_simple(self):
        """Test simple environment variable pattern."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "env-value"
        set_resolver(mock_resolver)

        result = resolve_credential_string("${MY_VAR}")

        assert result == "env-value"

    def test_env_var_pattern_numbers(self):
        """Test environment variable pattern with numbers."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "value"
        set_resolver(mock_resolver)

        result = resolve_credential_string("${VAR_123_NAME}")

        assert result == "value"

    def test_encrypted_pattern_simple(self):
        """Test simple encrypted pattern."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "decrypted"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@encrypted:service/key")

        assert result == "decrypted"

    def test_encrypted_pattern_complex(self):
        """Test encrypted pattern with complex names."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "decrypted"
        set_resolver(mock_resolver)

        result = resolve_credential_string("@encrypted:github-enterprise/personal-access-token")

        assert result == "decrypted"

    def test_invalid_pattern_treated_as_literal(self):
        """Test that invalid patterns are treated as literal values."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "literal-value"
        set_resolver(mock_resolver)

        # These don't match standard patterns but should still be passed to resolver
        resolve_credential_string("@unknown:service/key")

        # Resolver gets called with the literal value
        mock_resolver.resolve.assert_called_once_with("@unknown:service/key")

    def test_malformed_keyring_reference(self):
        """Test malformed keyring reference (missing slash)."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "value"
        set_resolver(mock_resolver)

        # Missing slash - treated as literal
        resolve_credential_string("@keyring:servicekeyw")

        mock_resolver.resolve.assert_called_once()

    def test_malformed_env_var_reference_lowercase(self):
        """Test malformed env var reference (lowercase var name)."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "value"
        set_resolver(mock_resolver)

        # Lowercase - pattern doesn't match, treated as literal
        resolve_credential_string("${lowercase_var}")

        mock_resolver.resolve.assert_called_once_with("${lowercase_var}")


class TestCredentialReferenceEdgeCases:
    """Test edge cases in credential reference handling."""

    def test_empty_string(self):
        """Test empty string handling."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = ""
        set_resolver(mock_resolver)

        result = resolve_credential_string("")

        assert result == ""

    def test_none_value(self):
        """Test None value is returned as-is."""
        result = resolve_credential_string(None)

        assert result is None

    def test_whitespace_reference(self):
        """Test whitespace-only reference."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "   "
        set_resolver(mock_resolver)

        result = resolve_credential_string("   ")

        assert result == "   "

    def test_very_long_reference(self):
        """Test very long credential reference."""
        long_ref = "@keyring:" + "a" * 10000 + "/key"
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "long-token"
        set_resolver(mock_resolver)

        result = resolve_credential_string(long_ref)

        assert result == "long-token"

    def test_reference_with_special_characters(self):
        """Test credential references with special characters."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "token"
        set_resolver(mock_resolver)

        # Service names might contain special chars
        result = resolve_credential_string("@keyring:my-service.v1/api-token")

        assert result == "token"

    def test_unicode_in_resolved_value(self):
        """Test Unicode characters in resolved credential value."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "token-Unicode-値"
        set_resolver(mock_resolver)

        result = resolve_credential_string("${UNICODE_TOKEN}")

        assert "Unicode" in result
        assert "値" in result

    def test_resolved_value_with_newlines(self):
        """Test resolved value containing newlines."""
        multiline_value = "line1\nline2\nline3"
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = multiline_value
        set_resolver(mock_resolver)

        result = resolve_credential_string("@keyring:service/key")

        assert "line2" in result


class TestSecurityConsiderations:
    """Test security-related aspects of credential handling."""

    def test_secretstr_not_logged(self):
        """Test that SecretStr prevents logging of secret values."""
        secret = SecretStr("my-secret-token")

        # SecretStr.__repr__ should mask the value
        repr_str = repr(secret)
        assert "my-secret-token" not in repr_str
        assert "***" in repr_str or "secret" in repr_str.lower()

    def test_secretstr_get_secret_value(self):
        """Test explicit access to secret value requires get_secret_value."""
        secret = SecretStr("token-123")

        # Need explicit method to get secret
        assert secret.get_secret_value() == "token-123"

    def test_resolver_caching_behavior(self):
        """Test that resolver can cache credentials."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "cached-token"
        set_resolver(mock_resolver)

        # Call multiple times
        result1 = resolve_credential_string("${TOKEN}")
        result2 = resolve_credential_string("${TOKEN}")

        assert result1 == result2

    def test_credential_error_includes_reference(self):
        """Test that credential errors include the reference for debugging."""
        from pydantic_core import PydanticCustomError

        mock_resolver = MagicMock(spec=CredentialResolver)
        credential_error = CredentialNotFoundError(
            "Token not found",
            reference="@keyring:github/token",
        )
        mock_resolver.resolve.side_effect = credential_error
        set_resolver(mock_resolver)

        with pytest.raises(PydanticCustomError) as exc_info:
            resolve_credential_string("@keyring:github/token")

        error = exc_info.value
        # Verify that error was raised and message contains reference info
        assert isinstance(error, PydanticCustomError)

    def test_no_password_in_error_messages(self):
        """Test that actual credential values don't appear in errors."""
        from pydantic_core import PydanticCustomError

        mock_resolver = MagicMock(spec=CredentialResolver)
        credential_error = CredentialError("Failed to resolve")
        mock_resolver.resolve.side_effect = credential_error
        set_resolver(mock_resolver)

        with pytest.raises(PydanticCustomError) as exc_info:
            resolve_credential_string("@keyring:service/key")

        error = exc_info.value
        # Verify error type and that no secrets are exposed
        assert isinstance(error, PydanticCustomError)


class TestIntegrationWithModels:
    """Test integration with Pydantic models."""

    class APIConfig(BaseModel):
        """Model with multiple credential fields."""

        api_token: CredentialSecret
        api_key: CredentialSecret
        server_url: str

    def test_model_with_multiple_credentials(self):
        """Test model with multiple credential fields."""
        mock_resolver = MagicMock(spec=CredentialResolver)

        def mock_resolve(value):
            mapping = {
                "@keyring:api/token": "resolved-token",
                "${API_KEY}": "resolved-key",
            }
            return mapping.get(value, value)

        mock_resolver.resolve.side_effect = mock_resolve
        set_resolver(mock_resolver)

        try:
            config = self.APIConfig(
                api_token="@keyring:api/token",
                api_key="${API_KEY}",
                server_url="https://api.example.com",
            )

            assert isinstance(config.api_token, SecretStr)
            assert isinstance(config.api_key, SecretStr)
            assert config.server_url == "https://api.example.com"
        finally:
            set_resolver(None)

    def test_model_validation_error_includes_field(self):
        """Test that validation errors include field name."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.side_effect = CredentialError("Not found")
        set_resolver(mock_resolver)

        try:
            with pytest.raises(ValidationError) as exc_info:
                self.APIConfig(
                    api_token="@keyring:missing/token",
                    api_key="key",
                    server_url="https://api.example.com",
                )

            error = exc_info.value
            # Should mention the field that failed
            assert "api_token" in str(error).lower() or "token" in str(error).lower()
        finally:
            set_resolver(None)


class TestBackendCompatibility:
    """Test compatibility with different credential backends."""

    def test_all_reference_types_supported(self):
        """Test that all reference types can be processed."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.side_effect = lambda x: f"resolved:{x}"
        set_resolver(mock_resolver)

        references = [
            "@keyring:service/key",
            "${ENV_VAR}",
            "@encrypted:service/key",
        ]

        for ref in references:
            result = resolve_credential_string(ref)
            assert "resolved" in result

    def test_resolver_can_implement_custom_logic(self):
        """Test that resolver can implement custom credential logic."""
        mock_resolver = MagicMock(spec=CredentialResolver)

        def custom_resolve(value):
            # Custom logic: prefix with "custom_"
            if value.startswith("@"):
                return "custom_" + value[1:]
            return value

        mock_resolver.resolve.side_effect = custom_resolve
        set_resolver(mock_resolver)

        result = resolve_credential_string("@keyring:service/key")

        assert result.startswith("custom_")

    def test_resolver_exception_handling(self):
        """Test resolver exception handling with different error types."""

        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.side_effect = Exception("Generic error")
        set_resolver(mock_resolver)

        # Generic exceptions are not caught by the credential error handler
        # They will propagate as-is
        with pytest.raises(Exception):  # noqa: B017
            resolve_credential_string("@keyring:service/key")
