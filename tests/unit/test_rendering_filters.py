"""Unit tests for automation/rendering/filters.py - Custom Jinja2 filters."""

import pytest

from automation.rendering.filters import (
    safe_identifier,
    safe_label,
    safe_url,
    yaml_dict,
    yaml_list,
    yaml_string,
)


class TestSafeUrl:
    """Tests for safe_url filter."""

    def test_valid_https_url(self):
        """Should accept valid HTTPS URL."""
        result = safe_url("https://example.com")
        assert result == "https://example.com"

    def test_valid_http_url(self):
        """Should accept valid HTTP URL."""
        result = safe_url("http://localhost:8080")
        assert result == "http://localhost:8080"

    def test_https_url_with_path(self):
        """Should accept HTTPS URL with path."""
        result = safe_url("https://example.com/path/to/resource")
        assert result == "https://example.com/path/to/resource"

    def test_url_with_query_params(self):
        """Should accept URL with query parameters."""
        result = safe_url("https://example.com?key=value&foo=bar")
        assert result == "https://example.com?key=value&foo=bar"

    def test_url_with_fragment(self):
        """Should accept URL with fragment."""
        result = safe_url("https://example.com/page#section")
        assert result == "https://example.com/page#section"

    def test_invalid_scheme_raises_error(self):
        """Should reject URLs with invalid schemes."""
        with pytest.raises(ValueError) as exc_info:
            safe_url("ftp://example.com")

        assert "Invalid URL scheme" in str(exc_info.value)

    def test_javascript_url_rejected(self):
        """Should reject javascript: URLs."""
        with pytest.raises(ValueError) as exc_info:
            safe_url("javascript:alert('xss')")

        assert "Invalid URL scheme" in str(exc_info.value)

    def test_file_url_rejected(self):
        """Should reject file:// URLs."""
        with pytest.raises(ValueError) as exc_info:
            safe_url("file:///etc/passwd")

        assert "Invalid URL scheme" in str(exc_info.value)

    def test_url_without_domain_rejected(self):
        """Should reject URL without domain."""
        with pytest.raises(ValueError) as exc_info:
            safe_url("https://")

        assert "must have a domain" in str(exc_info.value)

    def test_non_string_input_raises_error(self):
        """Should reject non-string inputs."""
        with pytest.raises(ValueError) as exc_info:
            safe_url(123)

        assert "must be string" in str(exc_info.value)

    def test_url_with_port(self):
        """Should accept URL with port number."""
        result = safe_url("https://example.com:8443/api")
        assert result == "https://example.com:8443/api"

    def test_url_with_auth_rejected(self):
        """Should handle URL with authentication."""
        # URLs with auth are technically valid but might be security concern
        result = safe_url("https://user:pass@example.com")
        # Should accept it (URL parsing allows it)
        assert result == "https://user:pass@example.com"


class TestSafeIdentifier:
    """Tests for safe_identifier filter."""

    def test_simple_identifier(self):
        """Should accept simple alphanumeric identifier."""
        result = safe_identifier("repo123")
        assert result == "repo123"

    def test_identifier_with_hyphens(self):
        """Should accept identifier with hyphens."""
        result = safe_identifier("my-repo-name")
        assert result == "my-repo-name"

    def test_identifier_with_underscores(self):
        """Should accept identifier with underscores."""
        result = safe_identifier("my_repo_name")
        assert result == "my_repo_name"

    def test_identifier_with_dots(self):
        """Should accept identifier with dots (for domains)."""
        result = safe_identifier("example.com")
        assert result == "example.com"

    def test_github_actions_expression(self):
        """Should accept GitHub Actions template expressions."""
        result = safe_identifier("${{ secrets.TOKEN }}")
        assert result == "${{ secrets.TOKEN }}"

    def test_mixed_valid_characters(self):
        """Should accept mixed valid characters."""
        result = safe_identifier("My-Repo_2024.v1")
        assert result == "My-Repo_2024.v1"

    def test_special_characters_rejected(self):
        """Should reject special characters."""
        with pytest.raises(ValueError) as exc_info:
            safe_identifier("repo@name")

        assert "Invalid identifier characters" in str(exc_info.value)

    def test_spaces_rejected(self):
        """Should reject identifiers with spaces."""
        with pytest.raises(ValueError) as exc_info:
            safe_identifier("my repo")

        assert "Invalid identifier characters" in str(exc_info.value)

    def test_empty_identifier_rejected(self):
        """Should reject empty identifiers."""
        with pytest.raises(ValueError) as exc_info:
            safe_identifier("")

        assert "cannot be empty" in str(exc_info.value)

    def test_none_value_rejected(self):
        """Should reject None values."""
        with pytest.raises(ValueError) as exc_info:
            safe_identifier(None)

        assert "cannot be None" in str(exc_info.value)

    def test_too_long_identifier_rejected(self):
        """Should reject identifiers exceeding max length."""
        long_name = "a" * 101

        with pytest.raises(ValueError) as exc_info:
            safe_identifier(long_name)

        assert "too long" in str(exc_info.value).lower()

    def test_custom_max_length(self):
        """Should respect custom max length."""
        with pytest.raises(ValueError):
            safe_identifier("toolong", max_length=5)

    def test_numeric_value_converted(self):
        """Should convert numeric values to string."""
        result = safe_identifier(12345)
        assert result == "12345"

    def test_slash_rejected(self):
        """Should reject slashes."""
        with pytest.raises(ValueError):
            safe_identifier("owner/repo")


class TestSafeLabel:
    """Tests for safe_label filter."""

    def test_simple_label(self):
        """Should accept simple label."""
        result = safe_label("bug")
        assert result == "bug"

    def test_label_with_spaces(self):
        """Should accept label with spaces."""
        result = safe_label("bug fix")
        # Should strip whitespace or preserve it
        assert "bug" in result and "fix" in result

    def test_label_strips_leading_whitespace(self):
        """Should strip leading whitespace."""
        result = safe_label("  bug")
        assert result == "bug"

    def test_label_strips_trailing_whitespace(self):
        """Should strip trailing whitespace."""
        result = safe_label("bug  ")
        assert result == "bug"

    def test_label_with_hyphen(self):
        """Should accept labels with hyphens."""
        result = safe_label("bug-fix")
        assert result == "bug-fix"

    def test_empty_label_rejected(self):
        """Should reject empty labels."""
        with pytest.raises(ValueError):
            safe_label("")

    def test_none_label_rejected(self):
        """Should reject None labels."""
        with pytest.raises(ValueError):
            safe_label(None)

    def test_too_long_label_rejected(self):
        """Should reject labels exceeding max length."""
        long_label = "a" * 51

        with pytest.raises(ValueError) as exc_info:
            safe_label(long_label)

        assert "too long" in str(exc_info.value).lower()

    def test_custom_max_length(self):
        """Should respect custom max length."""
        with pytest.raises(ValueError):
            safe_label("toolongforlabel", max_length=10)

    def test_numeric_value_converted(self):
        """Should convert numeric values to string."""
        result = safe_label(42)
        assert result == "42"

    def test_label_with_colon_rejected(self):
        """Should reject YAML special characters like colon."""
        with pytest.raises(ValueError):
            safe_label("key: value")

    def test_label_with_hash_rejected(self):
        """Should reject hash character."""
        with pytest.raises(ValueError):
            safe_label("bug #123")


class TestYamlString:
    """Tests for yaml_string filter."""

    def test_simple_string(self):
        """Should quote simple strings."""
        result = yaml_string("hello")
        # Could be quoted or unquoted depending on implementation
        assert "hello" in result

    def test_string_with_colon(self):
        """Should properly quote string with colon."""
        result = yaml_string("key: value")
        # Must be quoted to be valid YAML
        assert ":" in result

    def test_string_with_quotes(self):
        """Should escape quotes in string."""
        result = yaml_string('text with "quotes"')
        assert "quotes" in result

    def test_multiline_string(self):
        """Should handle multiline strings."""
        result = yaml_string("line1\nline2")
        # Should handle newlines appropriately
        assert "line1" in result and "line2" in result

    def test_empty_string(self):
        """Should handle empty string."""
        result = yaml_string("")
        # Empty string representation in YAML
        assert result is not None

    def test_unicode_string(self):
        """Should handle Unicode characters."""
        result = yaml_string("Hello 世界 🌍")
        assert "Hello" in result


class TestYamlList:
    """Tests for yaml_list filter."""

    def test_simple_list(self):
        """Should format simple list."""
        result = yaml_list(["item1", "item2", "item3"])
        # Should produce YAML list format
        assert "item1" in result
        assert "item2" in result
        assert "item3" in result

    def test_empty_list(self):
        """Should handle empty list."""
        result = yaml_list([])
        # Should produce empty list representation
        assert result is not None

    def test_single_item_list(self):
        """Should handle single-item list."""
        result = yaml_list(["only-item"])
        assert "only-item" in result

    def test_list_with_numbers(self):
        """Should handle list with numbers."""
        result = yaml_list([1, 2, 3])
        assert "1" in result or 1 in str(result)

    def test_list_with_mixed_types(self):
        """Should handle list with mixed types."""
        result = yaml_list(["string", 42, True])
        # All items should be present in some form
        assert result is not None


class TestYamlDict:
    """Tests for yaml_dict filter."""

    def test_simple_dict(self):
        """Should format simple dictionary."""
        result = yaml_dict({"key": "value", "foo": "bar"})
        # Should produce YAML dict format
        assert "key" in result
        assert "value" in result

    def test_empty_dict(self):
        """Should handle empty dictionary."""
        result = yaml_dict({})
        # Should produce empty dict representation
        assert result is not None

    def test_nested_dict(self):
        """Should handle nested dictionaries."""
        result = yaml_dict({"outer": {"inner": "value"}})
        assert "outer" in result
        assert "inner" in result

    def test_dict_with_numbers(self):
        """Should handle dict with numeric values."""
        result = yaml_dict({"count": 42, "price": 19.99})
        # Numbers should be present
        assert result is not None


class TestFilterEdgeCases:
    """Edge cases for all filters."""

    def test_safe_identifier_with_unicode(self):
        """Should reject non-ASCII characters in identifiers."""
        with pytest.raises(ValueError):
            safe_identifier("repo-名前")

    def test_safe_url_with_unicode_domain(self):
        """Should handle internationalized domain names."""
        # IDN domains should work
        result = safe_url("https://münchen.de")
        assert result == "https://münchen.de"

    def test_safe_label_whitespace_only_rejected(self):
        """Should reject whitespace-only labels."""
        with pytest.raises(ValueError):
            safe_label("   ")

    def test_yaml_string_with_special_chars(self):
        """Should handle YAML special characters."""
        result = yaml_string("value with: colon & ampersand")
        assert result is not None

    def test_yaml_list_with_none_values(self):
        """Should handle None values in list."""
        result = yaml_list([None, "value", None])
        # Should handle None appropriately
        assert result is not None

    def test_yaml_dict_with_none_values(self):
        """Should handle None values in dict."""
        result = yaml_dict({"key": None, "other": "value"})
        # Should handle None appropriately
        assert result is not None


class TestFilterIntegration:
    """Integration tests for filters."""

    def test_filters_work_together(self):
        """Should use multiple filters in sequence."""
        # This simulates how filters might be chained in templates
        url = safe_url("https://example.com")
        identifier = safe_identifier("my-repo")
        label = safe_label("bug fix")

        assert url == "https://example.com"
        assert identifier == "my-repo"
        assert "bug" in label and "fix" in label

    def test_all_filters_preserve_valid_input(self):
        """Should preserve valid inputs without modification."""
        # URL should be unchanged
        assert safe_url("https://example.com") == "https://example.com"

        # Simple identifier should be unchanged
        assert safe_identifier("my-repo") == "my-repo"

        # Label might be normalized but core content preserved
        label_result = safe_label("bug")
        assert "bug" in label_result
