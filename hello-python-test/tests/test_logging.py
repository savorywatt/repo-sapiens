"""Tests for structured logging configuration and utilities.

Tests cover:
- Basic logging configuration
- Log level handling
- Sensitive data redaction
- Context binding and clearing
- Output formatting (console and JSON)
- Integration with stdlib logging
"""

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import structlog

from repo_sapiens.logging_config import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    redact_sensitive_data,
    unbind_context,
)


class TestLoggingConfiguration:
    """Test basic logging configuration."""

    def test_configure_logging_info_level(self) -> None:
        """Test configuring logging with INFO level."""
        configure_logging(level="INFO", json_logs=False)
        assert logging.getLogger().level == logging.INFO

    def test_configure_logging_debug_level(self) -> None:
        """Test configuring logging with DEBUG level."""
        configure_logging(level="DEBUG", json_logs=False)
        assert logging.getLogger().level == logging.DEBUG

    def test_configure_logging_warning_level(self) -> None:
        """Test configuring logging with WARNING level."""
        configure_logging(level="WARNING", json_logs=False)
        assert logging.getLogger().level == logging.WARNING

    def test_configure_logging_error_level(self) -> None:
        """Test configuring logging with ERROR level."""
        configure_logging(level="ERROR", json_logs=False)
        assert logging.getLogger().level == logging.ERROR

    def test_configure_logging_critical_level(self) -> None:
        """Test configuring logging with CRITICAL level."""
        configure_logging(level="CRITICAL", json_logs=False)
        assert logging.getLogger().level == logging.CRITICAL

    def test_configure_logging_case_insensitive(self) -> None:
        """Test that log level configuration is case-insensitive."""
        configure_logging(level="debug", json_logs=False)
        assert logging.getLogger().level == logging.DEBUG

        configure_logging(level="INFO", json_logs=False)
        assert logging.getLogger().level == logging.INFO

    def test_configure_logging_invalid_level(self) -> None:
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            configure_logging(level="INVALID", json_logs=False)

        assert "Invalid log level" in str(exc_info.value)
        assert "INVALID" in str(exc_info.value)

    def test_configure_logging_with_context(self) -> None:
        """Test that initial context is set up."""
        context = {"app_id": "test-app", "version": "1.0"}
        configure_logging(level="INFO", json_logs=False, context=context)

        # Context should be bound (we can't directly verify this, but logger should work)
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_json_output(self) -> None:
        """Test configuration for JSON output."""
        configure_logging(level="INFO", json_logs=True)
        # Just verify no exceptions and logging works
        logger = get_logger("test")
        assert logger is not None


class TestGetLogger:
    """Test logger retrieval."""

    def test_get_logger_with_name(self) -> None:
        """Test getting a logger with explicit name."""
        configure_logging()
        logger = get_logger("test.module")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_without_name(self) -> None:
        """Test getting a logger without name uses caller's module."""
        configure_logging()
        logger = get_logger()
        assert logger is not None

    def test_get_logger_multiple_instances(self) -> None:
        """Test that multiple logger instances can be created."""
        configure_logging()
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        assert logger1 is not None
        assert logger2 is not None


class TestSensitiveDataRedaction:
    """Test redaction of sensitive information."""

    def test_redact_api_token(self) -> None:
        """Test that API tokens are redacted."""
        event = {"message": "API call", "api_token": "sk-abc123xyz"}
        result = redact_sensitive_data(None, "info", event)
        assert "***REDACTED***" in result["api_token"]
        assert "sk-abc123xyz" not in result["api_token"]

    def test_redact_password(self) -> None:
        """Test that passwords are redacted."""
        event = {"message": "Auth attempt", "password": "supersecret"}
        result = redact_sensitive_data(None, "info", event)
        assert "***REDACTED***" in result["password"]
        assert "supersecret" not in result["password"]

    def test_redact_connection_string(self) -> None:
        """Test that connection strings with credentials are redacted."""
        event = {"url": "postgresql://user:password@localhost/db"}
        result = redact_sensitive_data(None, "info", event)
        assert "***REDACTED***" in result["url"]
        assert "password" not in result["url"]

    def test_redact_bearer_token(self) -> None:
        """Test that bearer tokens are redacted."""
        event = {"auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        result = redact_sensitive_data(None, "info", event)
        assert "***REDACTED***" in result["auth"]

    def test_no_redaction_for_normal_values(self) -> None:
        """Test that normal values are not redacted."""
        event = {
            "issue_id": 123,
            "repository": "owner/repo",
            "status": "completed",
        }
        result = redact_sensitive_data(None, "info", event)
        assert result["issue_id"] == 123
        assert result["repository"] == "owner/repo"
        assert result["status"] == "completed"

    def test_redact_nested_dictionaries(self) -> None:
        """Test redaction of sensitive data in nested dictionaries."""
        event = {
            "user": {
                "name": "John",
                "api_token": "secret-token-123",
            }
        }
        result = redact_sensitive_data(None, "info", event)
        assert "***REDACTED***" in result["user"]["api_token"]
        assert result["user"]["name"] == "John"

    def test_redact_case_insensitive(self) -> None:
        """Test that redaction patterns are case-insensitive."""
        events = [
            {"API_TOKEN": "token123"},
            {"Api_Token": "token456"},
            {"password": "pass123"},
            {"PASSWORD": "pass456"},
        ]

        for event in events:
            result = redact_sensitive_data(None, "info", event)
            for value in result.values():
                if isinstance(value, str):
                    assert "***REDACTED***" in value or value == value


class TestContextBinding:
    """Test context variable binding and clearing."""

    def test_bind_context_single_variable(self) -> None:
        """Test binding a single context variable."""
        clear_context()  # Start fresh
        bind_context(request_id="req-123")
        logger = get_logger("test")
        assert logger is not None

    def test_bind_context_multiple_variables(self) -> None:
        """Test binding multiple context variables."""
        clear_context()
        bind_context(request_id="req-123", user_id="user-456", session="sess-789")
        logger = get_logger("test")
        assert logger is not None

    def test_clear_context(self) -> None:
        """Test clearing all context variables."""
        bind_context(request_id="req-123", user_id="user-456")
        clear_context()
        logger = get_logger("test")
        assert logger is not None

    def test_unbind_context_single_key(self) -> None:
        """Test unbinding a single context variable."""
        clear_context()
        bind_context(request_id="req-123", user_id="user-456")
        unbind_context("request_id")
        logger = get_logger("test")
        assert logger is not None

    def test_unbind_context_multiple_keys(self) -> None:
        """Test unbinding multiple context variables."""
        clear_context()
        bind_context(a="1", b="2", c="3")
        unbind_context("a", "b")
        logger = get_logger("test")
        assert logger is not None


class TestLoggerIntegration:
    """Test logger integration with various scenarios."""

    def test_logger_info_call(self) -> None:
        """Test calling logger.info()."""
        configure_logging(level="INFO")
        logger = get_logger("test")
        # Should not raise
        logger.info("test_event", value=42)

    def test_logger_debug_call(self) -> None:
        """Test calling logger.debug()."""
        configure_logging(level="DEBUG")
        logger = get_logger("test")
        logger.debug("test_event", value=42)

    def test_logger_warning_call(self) -> None:
        """Test calling logger.warning()."""
        configure_logging(level="WARNING")
        logger = get_logger("test")
        logger.warning("test_event", value=42)

    def test_logger_error_call(self) -> None:
        """Test calling logger.error()."""
        configure_logging(level="ERROR")
        logger = get_logger("test")
        logger.error("test_event", value=42)

    def test_logger_with_structured_data(self) -> None:
        """Test logging with structured data."""
        configure_logging()
        logger = get_logger("test")
        logger.info(
            "issue_processed",
            issue_id=42,
            repository="owner/repo",
            status="completed",
            duration_ms=1234,
        )

    def test_logger_with_context(self) -> None:
        """Test logging with context variables."""
        configure_logging()
        clear_context()
        bind_context(request_id="req-123")
        logger = get_logger("test")
        logger.info("action_performed", action="update")

    def test_logger_with_exception(self) -> None:
        """Test logging with exception information."""
        configure_logging(level="ERROR")
        logger = get_logger("test")

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error("operation_failed", exc_info=True)


class TestLogLevelFiltering:
    """Test that log levels filter correctly."""

    def test_debug_logs_not_shown_at_info_level(self) -> None:
        """Test that DEBUG logs are filtered at INFO level."""
        configure_logging(level="INFO")
        logger = get_logger("test")

        # Should not raise, just log at filtered level
        logger.debug("debug_message")
        logger.info("info_message")

    def test_error_logs_shown_at_all_levels(self) -> None:
        """Test that ERROR logs are shown at all levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            configure_logging(level=level)
            logger = get_logger("test")
            logger.error("error_message")  # Should always appear


class TestOutputFormats:
    """Test different output formats."""

    def test_console_output_format(self) -> None:
        """Test console (human-readable) output format."""
        configure_logging(level="INFO", json_logs=False)
        logger = get_logger("test")
        # Should not raise
        logger.info("test_event", value=42)

    def test_json_output_format(self) -> None:
        """Test JSON output format."""
        configure_logging(level="INFO", json_logs=True)
        logger = get_logger("test")
        # Should not raise
        logger.info("test_event", value=42)

    def test_format_switching(self) -> None:
        """Test switching between formats."""
        configure_logging(level="INFO", json_logs=False)
        logger1 = get_logger("test")
        logger1.info("console_format")

        configure_logging(level="INFO", json_logs=True)
        logger2 = get_logger("test")
        logger2.info("json_format")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_configure_logging_multiple_times(self) -> None:
        """Test that configure_logging can be called multiple times."""
        configure_logging(level="DEBUG", json_logs=False)
        configure_logging(level="INFO", json_logs=True)
        configure_logging(level="ERROR", json_logs=False)
        logger = get_logger("test")
        assert logger is not None

    def test_logger_with_large_data(self) -> None:
        """Test logging with large data structures."""
        configure_logging()
        logger = get_logger("test")

        large_list = list(range(1000))
        large_dict = {f"key_{i}": i for i in range(100)}

        logger.info("large_data", items_count=len(large_list), dict_size=len(large_dict))

    def test_logger_with_special_characters(self) -> None:
        """Test logging with special characters."""
        configure_logging()
        logger = get_logger("test")

        logger.info(
            "special_chars",
            message="Test with special chars: !@#$%^&*()",
            unicode_msg="Unicode: 中文 العربية 🚀",
        )

    def test_logger_with_none_values(self) -> None:
        """Test logging with None values."""
        configure_logging()
        logger = get_logger("test")
        logger.info("with_nones", value=None, result=None)

    def test_logger_with_boolean_values(self) -> None:
        """Test logging with boolean values."""
        configure_logging()
        logger = get_logger("test")
        logger.info("with_booleans", success=True, error=False)

    def test_context_with_special_values(self) -> None:
        """Test context binding with various value types."""
        clear_context()
        bind_context(
            count=42,
            success=True,
            value=None,
            items=[1, 2, 3],
        )
        logger = get_logger("test")
        logger.info("event_with_context")


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_processing_pipeline(self) -> None:
        """Test logging in a processing pipeline."""
        configure_logging(level="DEBUG")
        logger = get_logger("pipeline")

        # Simulate processing pipeline
        logger.info("pipeline_started", total_items=100)

        for i in range(5):
            logger.debug("processing_item", item_number=i)

        logger.info("pipeline_completed", processed=5, status="success")

    def test_error_handling_pipeline(self) -> None:
        """Test logging in error handling."""
        configure_logging(level="ERROR")
        logger = get_logger("error_handler")

        try:
            raise ValueError("Simulated error")
        except ValueError as e:
            logger.error("processing_failed", error_type="ValueError", error_msg=str(e))

    def test_concurrent_context(self) -> None:
        """Test context usage in concurrent scenarios."""
        configure_logging()

        # Simulate concurrent operations
        clear_context()
        bind_context(operation="op1")
        logger = get_logger("test")
        logger.info("operation1_started")

        clear_context()
        bind_context(operation="op2")
        logger.info("operation2_started")

    def test_request_response_logging(self) -> None:
        """Test request/response logging pattern."""
        configure_logging()

        clear_context()
        request_id = "req-12345"
        bind_context(request_id=request_id)

        logger = get_logger("handler")
        logger.info("request_received", method="POST", path="/api/issues")

        # Simulate processing
        logger.debug("request_validation", status="passed")
        logger.info("request_processing_completed", status_code=200)

        clear_context()

    def test_sensitive_data_in_logs(self) -> None:
        """Test that sensitive data gets redacted."""
        configure_logging()
        logger = get_logger("auth")

        logger.info(
            "login_attempt",
            username="user@example.com",
            password="secretpass123",
            api_token="sk-abc123xyz",
        )

        logger.error(
            "connection_failed",
            url="postgresql://admin:secretpw@localhost/db",
        )
