"""
Tests for runtime security monitoring.
"""

import pytest

from automation.rendering.security import (
    SecurityAudit,
    check_rendered_output,
)


class TestSecurityMonitoring:
    """Test security monitoring and auditing."""

    def test_detect_python_deserialization(self):
        """Test detection of Python object deserialization."""
        dangerous_yaml = """
name: test
command: !!python/object/apply:os.system ['ls']
"""
        with pytest.raises(ValueError, match="Dangerous YAML pattern"):
            check_rendered_output(dangerous_yaml)

    def test_detect_yaml_anchors(self):
        """Test detection of YAML anchors (DoS vector)."""
        dangerous_yaml = """
name: &anchor test
ref: *anchor
"""
        with pytest.raises(ValueError, match="Dangerous YAML pattern"):
            check_rendered_output(dangerous_yaml)

    def test_safe_output_passes(self):
        """Test that safe YAML passes checks."""
        safe_yaml = """
name: Build and Test
on:
  push:
    branches:
      - main
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        # Should not raise
        check_rendered_output(safe_yaml)

    def test_audit_logging(self):
        """Test security audit logging."""
        audit = SecurityAudit()

        audit.log_event(
            "injection_attempt",
            "high",
            "Detected potential injection in template context",
            {"field": "gitea_owner", "value": "test&anchor"},
        )

        events = audit.get_events(min_severity="high")
        assert len(events) == 1
        assert events[0]["type"] == "injection_attempt"
        assert events[0]["severity"] == "high"
