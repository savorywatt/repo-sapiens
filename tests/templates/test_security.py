"""
Security tests for template rendering system.

Tests validate that injection attacks are prevented and that
security filters work correctly.
"""

import pytest
from jinja2 import UndefinedError

from repo_sapiens.rendering.engine import SecureTemplateEngine
from repo_sapiens.rendering.filters import (
    safe_identifier,
    safe_label,
    safe_url,
)


class TestSecurityFilters:
    """Test custom security filters."""

    def test_safe_url_valid_https(self):
        """Test safe_url accepts valid HTTPS URLs."""
        url = "https://gitea.example.com"
        assert safe_url(url) == url

    def test_safe_url_valid_http(self):
        """Test safe_url accepts HTTP URLs (with warning)."""
        url = "http://localhost:3000"
        assert safe_url(url) == url

    def test_safe_url_rejects_invalid_scheme(self):
        """Test safe_url rejects non-HTTP schemes."""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            safe_url("javascript:alert(1)")

        with pytest.raises(ValueError, match="Invalid URL scheme"):
            safe_url("file:///etc/passwd")

    def test_safe_url_rejects_non_string(self):
        """Test safe_url rejects non-string values."""
        with pytest.raises(ValueError, match="must be string"):
            safe_url(123)

    def test_safe_identifier_valid(self):
        """Test safe_identifier accepts valid identifiers."""
        assert safe_identifier("repo-name") == "repo-name"
        assert safe_identifier("owner_name") == "owner_name"
        assert safe_identifier("repo.name") == "repo.name"

    def test_safe_identifier_rejects_special_chars(self):
        """Test safe_identifier rejects YAML-dangerous characters."""
        dangerous = [
            "repo:name",  # YAML key separator
            "repo\nname",  # Newline
            "repo{name}",  # YAML flow mapping
            "repo[name]",  # YAML flow sequence
            "repo&name",  # YAML anchor
            "repo*name",  # YAML alias
        ]

        for value in dangerous:
            with pytest.raises(ValueError, match="Invalid identifier"):
                safe_identifier(value)

    def test_safe_identifier_length_limit(self):
        """Test safe_identifier enforces length limits."""
        long_name = "a" * 101
        with pytest.raises(ValueError, match="too long"):
            safe_identifier(long_name)

    def test_safe_label_valid(self):
        """Test safe_label accepts valid label names."""
        assert safe_label("bug") == "bug"
        assert safe_label("help wanted") == "help wanted"
        assert safe_label("good-first-issue") == "good-first-issue"

    def test_safe_label_strips_whitespace(self):
        """Test safe_label strips leading/trailing whitespace."""
        assert safe_label("  bug  ") == "bug"

    def test_safe_label_rejects_yaml_chars(self):
        """Test safe_label rejects YAML-sensitive characters."""
        dangerous = [
            "bug:critical",
            "bug\ntask",
            "bug{test}",
        ]

        for value in dangerous:
            with pytest.raises(ValueError, match="invalid characters"):
                safe_label(value)


class TestTemplateInjection:
    """Test prevention of template injection attacks."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create a temporary template engine."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        return SecureTemplateEngine(template_dir=template_dir)

    def test_prevent_code_execution(self, engine, tmp_path):
        """Test that arbitrary code execution is prevented."""
        # Create malicious template
        template_file = tmp_path / "templates" / "malicious.yaml.j2"
        template_file.write_text(
            """
name: {{ name }}
command: {{ command }}
"""
        )

        # Attempt code execution through template
        context = {
            "name": "test",
            "command": "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        }

        rendered = engine.render("malicious.yaml.j2", context, validate=False)

        # Should render as literal string, not execute
        assert "__subclasses__" in rendered
        assert "class" not in rendered  # Should not access __class__

    def test_undefined_variable_strict(self, engine, tmp_path):
        """Test that undefined variables cause errors."""
        template_file = tmp_path / "templates" / "strict.yaml.j2"
        template_file.write_text("value: {{ undefined_var }}")

        with pytest.raises(UndefinedError):
            engine.render("strict.yaml.j2", {}, validate=False)

    def test_directory_traversal_prevention(self, engine, tmp_path):
        """Test that directory traversal is prevented."""
        # Try to access parent directory
        with pytest.raises(ValueError, match="escapes template directory"):
            engine.validate_template_path("../etc/passwd")

        with pytest.raises(ValueError, match="escapes template directory"):
            engine.validate_template_path("subdir/../../etc/passwd")

    def test_null_byte_injection(self, engine, tmp_path):
        """Test that null bytes in context are rejected."""
        template_file = tmp_path / "templates" / "test.yaml.j2"
        template_file.write_text("value: {{ value }}")

        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo",
            "value": "test\0injection",
        }

        with pytest.raises(ValueError, match="Null byte"):
            engine.render("test.yaml.j2", context, validate=True)
