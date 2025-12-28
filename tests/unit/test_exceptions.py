"""Tests for automation.exceptions module."""

import pytest

from automation.exceptions import (
    ConfigurationError,
    CredentialError,
    ExternalServiceError,
    GitOperationError,
    RepoSapiensError,
    TemplateError,
    WorkflowError,
)


class TestRepoSapiensError:
    """Test base RepoSapiensError class."""

    def test_init_with_message(self):
        """Test initialization with message."""
        message = "Test error message"
        error = RepoSapiensError(message)

        assert error.message == message
        assert str(error) == message

    def test_inheritance_from_exception(self):
        """Test that RepoSapiensError inherits from Exception."""
        error = RepoSapiensError("test")
        assert isinstance(error, Exception)

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(RepoSapiensError) as exc_info:
            raise RepoSapiensError("Test error")

        assert exc_info.value.message == "Test error"

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        error = RepoSapiensError("")
        assert error.message == ""

    def test_exception_chain(self):
        """Test exception chaining."""
        original_error = ValueError("Original error")
        error = RepoSapiensError("Wrapped error")

        with pytest.raises(RepoSapiensError):
            raise error from original_error

    def test_exception_string_representation(self):
        """Test string representation of exception."""
        message = "Test message"
        error = RepoSapiensError(message)
        assert str(error) == message


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_configuration_error_inherits_from_base(self):
        """Test that ConfigurationError inherits from RepoSapiensError."""
        error = ConfigurationError("Config error")
        assert isinstance(error, RepoSapiensError)
        assert isinstance(error, Exception)

    def test_configuration_error_with_message(self):
        """Test ConfigurationError with message."""
        message = "Configuration file not found"
        error = ConfigurationError(message)
        assert error.message == message

    def test_configuration_error_can_be_caught(self):
        """Test that ConfigurationError can be caught as RepoSapiensError."""
        with pytest.raises(RepoSapiensError):
            raise ConfigurationError("Config error")

    def test_configuration_error_specific_catch(self):
        """Test catching ConfigurationError specifically."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError("Invalid config")

        assert exc_info.value.message == "Invalid config"


class TestCredentialError:
    """Test CredentialError class."""

    def test_credential_error_inherits(self):
        """Test that CredentialError inherits from RepoSapiensError."""
        error = CredentialError("Credential error")
        assert isinstance(error, RepoSapiensError)

    def test_credential_error_message(self):
        """Test CredentialError with message."""
        message = "Credential not found"
        error = CredentialError(message)
        assert error.message == message

    def test_credential_error_catch_hierarchy(self):
        """Test catching CredentialError in hierarchy."""
        with pytest.raises(RepoSapiensError):
            raise CredentialError("Credential not available")


class TestGitOperationError:
    """Test GitOperationError class."""

    def test_git_operation_error_inherits(self):
        """Test that GitOperationError inherits from RepoSapiensError."""
        error = GitOperationError("Git error")
        assert isinstance(error, RepoSapiensError)

    def test_git_operation_error_message(self):
        """Test GitOperationError with message."""
        message = "Failed to push changes"
        error = GitOperationError(message)
        assert error.message == message

    def test_git_operation_error_catch(self):
        """Test catching GitOperationError."""
        with pytest.raises(GitOperationError):
            raise GitOperationError("No remotes configured")


class TestTemplateError:
    """Test TemplateError class."""

    def test_template_error_inherits(self):
        """Test that TemplateError inherits from RepoSapiensError."""
        error = TemplateError("Template error")
        assert isinstance(error, RepoSapiensError)

    def test_template_error_message(self):
        """Test TemplateError with message."""
        message = "Template rendering failed"
        error = TemplateError(message)
        assert error.message == message

    def test_template_error_catch(self):
        """Test catching TemplateError."""
        with pytest.raises(TemplateError):
            raise TemplateError("Invalid template syntax")


class TestWorkflowError:
    """Test WorkflowError class."""

    def test_workflow_error_inherits(self):
        """Test that WorkflowError inherits from RepoSapiensError."""
        error = WorkflowError("Workflow error")
        assert isinstance(error, RepoSapiensError)

    def test_workflow_error_message(self):
        """Test WorkflowError with message."""
        message = "Plan not found"
        error = WorkflowError(message)
        assert error.message == message

    def test_workflow_error_catch(self):
        """Test catching WorkflowError."""
        with pytest.raises(WorkflowError):
            raise WorkflowError("Invalid plan structure")


class TestExternalServiceError:
    """Test ExternalServiceError class."""

    def test_external_service_error_message_only(self):
        """Test ExternalServiceError with message only."""
        message = "Service unavailable"
        error = ExternalServiceError(message)

        assert error.message == message
        assert error.status_code is None
        assert error.response_text is None

    def test_external_service_error_with_status_code(self):
        """Test ExternalServiceError with status code."""
        message = "API error"
        status_code = 500
        error = ExternalServiceError(message, status_code=status_code)

        assert error.status_code == status_code
        assert error.response_text is None
        assert f"HTTP {status_code}" in str(error)

    def test_external_service_error_with_response_text(self):
        """Test ExternalServiceError with response text."""
        message = "API error"
        response_text = "Internal server error"
        error = ExternalServiceError(message, status_code=500, response_text=response_text)

        assert error.response_text == response_text
        assert error.status_code == 500

    def test_external_service_error_full_details(self):
        """Test ExternalServiceError with all parameters."""
        message = "Request failed"
        status_code = 400
        response_text = "Bad request"
        error = ExternalServiceError(message, status_code=status_code, response_text=response_text)

        assert error.status_code == status_code
        assert error.response_text == response_text

    def test_external_service_error_inherits(self):
        """Test that ExternalServiceError inherits from RepoSapiensError."""
        error = ExternalServiceError("Service error")
        assert isinstance(error, RepoSapiensError)

    def test_external_service_error_catch(self):
        """Test catching ExternalServiceError."""
        with pytest.raises(ExternalServiceError):
            raise ExternalServiceError("HTTP request failed", status_code=503)

    def test_external_service_error_string_with_status(self):
        """Test string representation includes status code."""
        error = ExternalServiceError("API error", status_code=503)
        error_str = str(error)
        assert "503" in error_str

    def test_external_service_error_string_without_status(self):
        """Test string representation without status code."""
        error = ExternalServiceError("API error")
        assert "HTTP" not in str(error)

    def test_external_service_error_with_zero_status(self):
        """Test with status code 0 (should not be included)."""
        error = ExternalServiceError("Error", status_code=0)
        # 0 is falsy, so it should not be included in the message
        assert "HTTP" not in str(error)


class TestExceptionHierarchy:
    """Test exception hierarchy and catching patterns."""

    def test_catch_all_repo_sapiens_errors(self):
        """Test catching all repo-sapiens errors with base exception."""
        errors = [
            ConfigurationError("config"),
            CredentialError("credential"),
            GitOperationError("git"),
            TemplateError("template"),
            WorkflowError("workflow"),
            ExternalServiceError("service"),
        ]

        for error in errors:
            with pytest.raises(RepoSapiensError):
                raise error

    def test_specific_error_not_caught_by_other_type(self):
        """Test that specific errors are not caught by unrelated types."""
        with pytest.raises(ConfigurationError):
            try:
                raise ConfigurationError("config error")
            except CredentialError:
                pass  # Should not catch

    def test_base_error_catches_all_subclasses(self):
        """Test that base error catches all subclasses."""
        error_types = [
            ConfigurationError,
            CredentialError,
            GitOperationError,
            TemplateError,
            WorkflowError,
            ExternalServiceError,
        ]

        for error_type in error_types:
            try:
                raise error_type("test")
            except RepoSapiensError:
                pass  # Should catch

    def test_exception_messages_preserved(self):
        """Test that exception messages are preserved correctly."""
        test_cases = [
            (ConfigurationError, "Config not found"),
            (CredentialError, "Invalid credential"),
            (GitOperationError, "Push failed"),
            (TemplateError, "Render error"),
            (WorkflowError, "Plan failed"),
            (ExternalServiceError, "Timeout"),
        ]

        for error_class, message in test_cases:
            error = error_class(message)
            assert error.message == message
            assert str(error) == message


class TestExceptionEdgeCases:
    """Test edge cases and special scenarios."""

    def test_exception_with_special_characters(self):
        """Test exception with special characters in message."""
        message = "Error: 'test' with \"quotes\" and\nnewlines"
        error = RepoSapiensError(message)
        assert error.message == message

    def test_exception_with_unicode(self):
        """Test exception with Unicode characters."""
        message = "Error: 日本語 and émojis 🚀"
        error = RepoSapiensError(message)
        assert error.message == message

    def test_external_service_error_none_status_code(self):
        """Test ExternalServiceError explicitly with None status code."""
        error = ExternalServiceError("Error", status_code=None, response_text="Text")
        assert error.status_code is None
        assert error.response_text == "Text"

    def test_exception_repr(self):
        """Test exception repr."""
        error = RepoSapiensError("Test error")
        # Should have a valid repr
        repr_str = repr(error)
        assert "RepoSapiensError" in repr_str

    def test_multiple_inheritance_chain(self):
        """Test checking inheritance chain."""
        error = ConfigurationError("test")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, RepoSapiensError)
        assert isinstance(error, Exception)
        assert isinstance(error, BaseException)
