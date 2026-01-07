"""Tests for repo_sapiens/rendering/security.py."""

import pytest

from repo_sapiens.rendering.security import (
    DANGEROUS_YAML_PATTERNS,
    SecurityAudit,
    check_rendered_output,
    generate_safe_token,
    sanitize_log_output,
)


class TestCheckRenderedOutput:
    """Tests for check_rendered_output function."""

    def test_safe_yaml_passes(self):
        """Safe YAML content should pass without raising."""
        safe_content = """
        name: test-workflow
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
        """
        # Should not raise
        check_rendered_output(safe_content)

    @pytest.mark.parametrize(
        "dangerous_content",
        [
            "!!python/object:os.system",
            "data: !!binary R0lGODlh",
            "key: &anchor value",
            "*alias_reference",
            "!!map {key: value}",
        ],
    )
    def test_dangerous_patterns_raise(self, dangerous_content):
        """Dangerous YAML patterns should raise ValueError."""
        with pytest.raises(ValueError, match="Dangerous YAML pattern"):
            check_rendered_output(dangerous_content)

    def test_all_dangerous_patterns_defined(self):
        """Ensure dangerous patterns list is populated."""
        assert len(DANGEROUS_YAML_PATTERNS) > 0
        assert all(isinstance(p, str) for p in DANGEROUS_YAML_PATTERNS)


class TestGenerateSafeToken:
    """Tests for generate_safe_token function."""

    def test_default_length(self):
        """Default token should be 64 hex characters (32 bytes)."""
        token = generate_safe_token()
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_custom_length(self):
        """Custom length should produce correct token size."""
        token = generate_safe_token(length=16)
        assert len(token) == 32  # 16 bytes = 32 hex chars

    def test_tokens_are_unique(self):
        """Generated tokens should be unique."""
        tokens = [generate_safe_token() for _ in range(100)]
        assert len(set(tokens)) == 100


class TestSanitizeLogOutput:
    """Tests for sanitize_log_output function."""

    def test_normal_text_unchanged(self):
        """Normal text should pass through unchanged."""
        text = "This is a normal log message"
        assert sanitize_log_output(text) == text

    def test_control_characters_removed(self):
        """Control characters should be removed."""
        text = "Hello\x00World\x1fTest"
        result = sanitize_log_output(text)
        assert "\x00" not in result
        assert "\x1f" not in result
        assert result == "HelloWorldTest"

    def test_newline_and_tab_preserved(self):
        """Newlines and tabs should be preserved."""
        text = "Line1\nLine2\tTabbed"
        assert sanitize_log_output(text) == text

    def test_truncation_at_max_length(self):
        """Long text should be truncated with indicator."""
        long_text = "x" * 2000
        result = sanitize_log_output(long_text, max_length=100)
        assert len(result) < 200
        assert "... (truncated)" in result
        assert result.startswith("x" * 100)

    def test_short_text_not_truncated(self):
        """Short text should not be truncated."""
        short_text = "Short message"
        result = sanitize_log_output(short_text, max_length=1000)
        assert result == short_text
        assert "truncated" not in result


class TestSecurityAudit:
    """Tests for SecurityAudit class."""

    def test_initialization(self):
        """Audit should initialize with empty events."""
        audit = SecurityAudit()
        assert audit.events == []

    def test_log_event(self):
        """Events should be logged correctly."""
        audit = SecurityAudit()
        audit.log_event(
            event_type="injection_attempt",
            severity="high",
            message="Suspicious pattern detected",
            context={"file": "test.yaml"},
        )

        assert len(audit.events) == 1
        assert audit.events[0]["type"] == "injection_attempt"
        assert audit.events[0]["severity"] == "high"

    def test_log_event_sanitizes_message(self):
        """Event messages should be sanitized."""
        audit = SecurityAudit()
        audit.log_event(
            event_type="test",
            severity="low",
            message="Message\x00with\x1fcontrol",
            context={},
        )

        assert "\x00" not in audit.events[0]["message"]

    def test_get_events_filters_by_severity(self):
        """Events should filter by minimum severity."""
        audit = SecurityAudit()
        audit.log_event("low_event", "low", "Low severity", {})
        audit.log_event("medium_event", "medium", "Medium severity", {})
        audit.log_event("high_event", "high", "High severity", {})
        audit.log_event("critical_event", "critical", "Critical severity", {})

        # Get all events
        all_events = audit.get_events(min_severity="low")
        assert len(all_events) == 4

        # Get medium and above
        medium_plus = audit.get_events(min_severity="medium")
        assert len(medium_plus) == 3

        # Get high and above
        high_plus = audit.get_events(min_severity="high")
        assert len(high_plus) == 2

        # Get critical only
        critical_only = audit.get_events(min_severity="critical")
        assert len(critical_only) == 1
        assert critical_only[0]["type"] == "critical_event"
