"""Unit tests for repo_sapiens/rendering/engine.py - Template rendering engine."""

from pathlib import Path

import pytest
from jinja2 import StrictUndefined, TemplateNotFound
from jinja2.exceptions import UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from repo_sapiens.rendering.engine import SecureTemplateEngine


class TestSecureTemplateEngineInit:
    """Tests for SecureTemplateEngine initialization."""

    def test_init_with_default_template_dir(self):
        """Should use package templates directory by default."""
        engine = SecureTemplateEngine()

        assert engine.template_dir.exists()
        assert engine.template_dir.is_dir()
        assert engine.env is not None
        assert isinstance(engine.env, SandboxedEnvironment)

    def test_init_with_custom_template_dir(self, tmp_path):
        """Should use custom template directory."""
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()

        engine = SecureTemplateEngine(template_dir=custom_dir)

        assert engine.template_dir == custom_dir.resolve()

    def test_init_nonexistent_dir_raises_error(self, tmp_path):
        """Should raise ValueError for non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError) as exc_info:
            SecureTemplateEngine(template_dir=nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_init_file_instead_of_dir_raises_error(self, tmp_path):
        """Should raise ValueError if path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(ValueError) as exc_info:
            SecureTemplateEngine(template_dir=file_path)

        assert "not a directory" in str(exc_info.value)

    def test_sandboxed_environment_configured(self):
        """Should create sandboxed environment with strict settings."""
        engine = SecureTemplateEngine()

        assert isinstance(engine.env, SandboxedEnvironment)
        assert isinstance(engine.env.undefined, type(StrictUndefined))
        assert engine.env.autoescape is False
        assert engine.env.trim_blocks is True
        assert engine.env.lstrip_blocks is True
        assert engine.env.keep_trailing_newline is True

    def test_extensions_disabled_by_default(self):
        """Should have no extensions enabled by default."""
        engine = SecureTemplateEngine()

        assert engine.env.extensions == {}

    def test_extensions_enabled_when_requested(self, tmp_path):
        """Should enable extensions when explicitly requested."""
        custom_dir = tmp_path / "templates"
        custom_dir.mkdir()

        engine = SecureTemplateEngine(template_dir=custom_dir, enable_extensions=True)

        # jinja2.ext.do extension should be available (registered as ExprStmtExtension)
        assert "jinja2.ext.ExprStmtExtension" in engine.env.extensions


class TestSecureTemplateEngineFilters:
    """Tests for custom filter registration."""

    def test_safe_url_filter_registered(self):
        """Should register safe_url filter."""
        engine = SecureTemplateEngine()

        assert "safe_url" in engine.env.filters

    def test_safe_identifier_filter_registered(self):
        """Should register safe_identifier filter."""
        engine = SecureTemplateEngine()

        assert "safe_identifier" in engine.env.filters

    def test_safe_label_filter_registered(self):
        """Should register safe_label filter."""
        engine = SecureTemplateEngine()

        assert "safe_label" in engine.env.filters

    def test_yaml_string_filter_registered(self):
        """Should register yaml_string filter."""
        engine = SecureTemplateEngine()

        assert "yaml_string" in engine.env.filters

    def test_yaml_list_filter_registered(self):
        """Should register yaml_list filter."""
        engine = SecureTemplateEngine()

        assert "yaml_list" in engine.env.filters

    def test_yaml_dict_filter_registered(self):
        """Should register yaml_dict filter."""
        engine = SecureTemplateEngine()

        assert "yaml_dict" in engine.env.filters

    def test_all_required_filters_registered(self):
        """Should register all required custom filters."""
        engine = SecureTemplateEngine()

        required_filters = [
            "safe_url",
            "safe_identifier",
            "safe_label",
            "yaml_string",
            "yaml_list",
            "yaml_dict",
        ]

        for filter_name in required_filters:
            assert filter_name in engine.env.filters


class TestSecureTemplateEngineRendering:
    """Tests for template rendering."""

    def test_render_simple_template(self, tmp_path):
        """Should render simple template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "simple.j2"
        template_file.write_text("Hello {{ name }}!")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("simple.j2")
        result = template.render(name="World")

        assert result == "Hello World!"

    def test_render_with_context(self, tmp_path):
        """Should render template with context variables."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "context.j2"
        template_file.write_text("{{ greeting }} {{ name }}!")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("context.j2")
        result = template.render(greeting="Hello", name="User")

        assert result == "Hello User!"

    def test_undefined_variable_raises_error(self, tmp_path):
        """Should raise UndefinedError for missing variables."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "undefined.j2"
        template_file.write_text("{{ missing_var }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("undefined.j2")

        with pytest.raises(UndefinedError):
            template.render()

    def test_nonexistent_template_raises_error(self):
        """Should raise TemplateNotFound for missing templates."""
        engine = SecureTemplateEngine()

        with pytest.raises(TemplateNotFound):
            engine.env.get_template("nonexistent.j2")

    def test_trim_blocks_removes_newlines(self, tmp_path):
        """Should trim blocks correctly."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "trim.j2"
        template_file.write_text("{% if true %}\nContent\n{% endif %}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("trim.j2")
        result = template.render()

        # trim_blocks and lstrip_blocks should remove extra whitespace
        assert "Content" in result
        assert result.strip() == "Content"

    def test_keep_trailing_newline(self, tmp_path):
        """Should preserve final newline in template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "trailing.j2"
        template_file.write_text("Content\n")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("trailing.j2")
        result = template.render()

        assert result.endswith("\n")


class TestSecureTemplateEngineSecurity:
    """Tests for security features."""

    def test_sandboxed_environment_prevents_dangerous_operations(self, tmp_path):
        """Should prevent dangerous operations in sandboxed environment."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Attempt to access __class__ which should be restricted
        template_file = template_dir / "dangerous.j2"
        template_file.write_text("{{ ''.__class__ }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("dangerous.j2")

        # Sandboxed environment should prevent this
        with pytest.raises(Exception):  # noqa: B017 - Will raise SecurityError or similar
            template.render()

    def test_no_autoescape_for_yaml(self, tmp_path):
        """Should not HTML-escape values (YAML doesn't need it)."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "no_escape.j2"
        template_file.write_text("{{ value }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("no_escape.j2")
        result = template.render(value="<tag>")

        # Should NOT escape HTML entities for YAML
        assert result == "<tag>"

    def test_cannot_access_filesystem_outside_template_dir(self, tmp_path):
        """Should not allow directory traversal attacks."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("sensitive data")

        engine = SecureTemplateEngine(template_dir=template_dir)

        # Attempt to access file outside template directory
        with pytest.raises(TemplateNotFound):
            engine.env.get_template("../secret.txt")


class TestSecureTemplateEngineEdgeCases:
    """Edge cases and error handling."""

    def test_template_with_unicode(self, tmp_path):
        """Should handle Unicode characters correctly."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "unicode.j2"
        template_file.write_text("{{ emoji }} {{ text }}", encoding="utf-8")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("unicode.j2")
        result = template.render(emoji="🚀", text="Unicode テスト")

        assert "🚀" in result
        assert "テスト" in result

    def test_template_with_special_yaml_characters(self, tmp_path):
        """Should handle YAML special characters."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "yaml_chars.j2"
        template_file.write_text("value: {{ data }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("yaml_chars.j2")

        # Test with colon, which is special in YAML
        result = template.render(data="key:value")
        assert "key:value" in result

    def test_empty_template(self, tmp_path):
        """Should handle empty templates."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "empty.j2"
        template_file.write_text("")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("empty.j2")
        result = template.render()

        assert result == ""

    def test_template_with_only_whitespace(self, tmp_path):
        """Should handle whitespace-only templates."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "whitespace.j2"
        template_file.write_text("   \n  \n   ")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("whitespace.j2")
        result = template.render()

        # Should preserve some whitespace due to settings
        assert len(result) > 0

    def test_nested_template_directory(self, tmp_path):
        """Should support nested template directories."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        nested_dir = template_dir / "nested"
        nested_dir.mkdir()

        template_file = nested_dir / "template.j2"
        template_file.write_text("Nested: {{ value }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("nested/template.j2")
        result = template.render(value="test")

        assert result == "Nested: test"

    def test_template_path_normalization(self, tmp_path):
        """Should normalize template directory path."""
        import os

        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Change to tmp_path and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            relative_path = Path("templates")

            engine = SecureTemplateEngine(template_dir=relative_path)

            # Should be resolved to absolute path
            assert engine.template_dir.is_absolute()
            assert engine.template_dir == template_dir.resolve()
        finally:
            os.chdir(original_cwd)


class TestSecureTemplateEngineIntegration:
    """Integration tests for template engine."""

    def test_render_workflow_like_template(self, tmp_path):
        """Should render GitHub Actions-like workflow."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "workflow.j2"
        template_file.write_text(
            """name: {{ workflow_name }}
on:
  push:
    branches:
      - {{ branch }}
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Test
        run: {{ command }}
"""
        )

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("workflow.j2")
        result = template.render(
            workflow_name="CI Test",
            branch="main",
            command="pytest",
        )

        assert "name: CI Test" in result
        assert "- main" in result
        assert "run: pytest" in result

    def test_render_with_filters(self, tmp_path):
        """Should render template using custom filters."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "with_filters.j2"
        template_file.write_text(
            """url: {{ url | safe_url }}
identifier: {{ name | safe_identifier }}
label: {{ label | safe_label }}
"""
        )

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("with_filters.j2")
        result = template.render(
            url="https://example.com",
            name="my-repo",
            label="bug fix",
        )

        assert "url: https://example.com" in result
        assert "identifier: my-repo" in result
        assert "label: bug-fix" in result or "label: bug fix" in result


class TestSecureTemplateEngineRenderMethod:
    """Tests for the render() method."""

    def test_render_method_basic(self, tmp_path):
        """Should render template via render() method."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "simple.yaml.j2"
        template_file.write_text("name: {{ name }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        result = engine.render("simple.yaml.j2", {"name": "test"}, validate=False)

        assert result == "name: test"

    def test_render_validates_context_by_default(self, tmp_path):
        """Should validate context by default."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.yaml.j2"
        template_file.write_text("value: {{ value }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        # Provide required fields for validation
        context = {
            "value": "safe",
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo",
        }
        result = engine.render("test.yaml.j2", context)
        assert "value: safe" in result

    def test_render_skip_validation(self, tmp_path):
        """Should skip validation when validate=False."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "skip.yaml.j2"
        template_file.write_text("{{ data }}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        result = engine.render("skip.yaml.j2", {"data": "test"}, validate=False)

        assert result == "test"


class TestValidateTemplatePath:
    """Tests for validate_template_path() method."""

    def test_valid_path(self, tmp_path):
        """Should return resolved path for valid template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "valid.j2"
        template_file.write_text("content")

        engine = SecureTemplateEngine(template_dir=template_dir)
        path = engine.validate_template_path("valid.j2")

        assert path.exists()
        assert path.is_absolute()
        assert path.name == "valid.j2"

    def test_nested_valid_path(self, tmp_path):
        """Should allow nested paths within template dir."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        nested = template_dir / "workflows"
        nested.mkdir()

        template_file = nested / "ci.j2"
        template_file.write_text("content")

        engine = SecureTemplateEngine(template_dir=template_dir)
        path = engine.validate_template_path("workflows/ci.j2")

        assert path.exists()
        assert "workflows" in str(path)

    def test_directory_traversal_blocked(self, tmp_path):
        """Should block directory traversal attempts."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Create a file outside template dir
        outside = tmp_path / "secret.txt"
        outside.write_text("secret")

        engine = SecureTemplateEngine(template_dir=template_dir)

        with pytest.raises(ValueError) as exc_info:
            engine.validate_template_path("../secret.txt")

        assert "escapes template directory" in str(exc_info.value)

    def test_nonexistent_template_raises_error(self, tmp_path):
        """Should raise TemplateNotFound for nonexistent template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        engine = SecureTemplateEngine(template_dir=template_dir)

        with pytest.raises(TemplateNotFound):
            engine.validate_template_path("nonexistent.j2")


class TestListTemplates:
    """Tests for list_templates() method."""

    def test_list_templates_default_pattern(self, tmp_path):
        """Should list templates matching default pattern."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Create some template files
        (template_dir / "workflow1.yaml.j2").write_text("content1")
        (template_dir / "workflow2.yaml.j2").write_text("content2")
        (template_dir / "readme.md").write_text("not a template")

        engine = SecureTemplateEngine(template_dir=template_dir)
        templates = engine.list_templates()

        assert len(templates) == 2
        assert "workflow1.yaml.j2" in templates
        assert "workflow2.yaml.j2" in templates
        assert "readme.md" not in templates

    def test_list_templates_custom_pattern(self, tmp_path):
        """Should list templates matching custom pattern."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        (template_dir / "template.j2").write_text("content")
        (template_dir / "config.yaml.j2").write_text("yaml content")

        engine = SecureTemplateEngine(template_dir=template_dir)
        templates = engine.list_templates(pattern="*.j2")

        assert len(templates) == 2

    def test_list_templates_nested_directories(self, tmp_path):
        """Should find templates in nested directories."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        nested = template_dir / "workflows" / "ci"
        nested.mkdir(parents=True)

        (nested / "build.yaml.j2").write_text("build content")
        (template_dir / "main.yaml.j2").write_text("main content")

        engine = SecureTemplateEngine(template_dir=template_dir)
        templates = engine.list_templates()

        assert len(templates) == 2
        assert "main.yaml.j2" in templates
        assert any("build.yaml.j2" in t for t in templates)

    def test_list_templates_empty_directory(self, tmp_path):
        """Should return empty list for empty directory."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        engine = SecureTemplateEngine(template_dir=template_dir)
        templates = engine.list_templates()

        assert templates == []

    def test_list_templates_sorted(self, tmp_path):
        """Should return templates in sorted order."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        (template_dir / "z.yaml.j2").write_text("z")
        (template_dir / "a.yaml.j2").write_text("a")
        (template_dir / "m.yaml.j2").write_text("m")

        engine = SecureTemplateEngine(template_dir=template_dir)
        templates = engine.list_templates()

        assert templates == ["a.yaml.j2", "m.yaml.j2", "z.yaml.j2"]


class TestSecureTemplateEngineCustomTests:
    """Tests for custom Jinja2 tests."""

    def test_valid_url_test_registered(self):
        """Should register valid_url test."""
        engine = SecureTemplateEngine()
        assert "valid_url" in engine.env.tests

    def test_valid_identifier_test_registered(self):
        """Should register valid_identifier test."""
        engine = SecureTemplateEngine()
        assert "valid_identifier" in engine.env.tests

    def test_valid_url_test_https(self, tmp_path):
        """Should recognize https URL as valid."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "url_test.j2"
        template_file.write_text("{% if url is valid_url %}valid{% else %}invalid{% endif %}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("url_test.j2")

        assert template.render(url="https://example.com") == "valid"
        assert template.render(url="not-a-url") == "invalid"

    def test_valid_identifier_test(self, tmp_path):
        """Should recognize Python identifiers."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "id_test.j2"
        template_file.write_text("{% if name is valid_identifier %}yes{% else %}no{% endif %}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("id_test.j2")

        assert template.render(name="valid_name") == "yes"
        assert template.render(name="123invalid") == "no"


class TestSecureTemplateEngineGlobals:
    """Tests for custom global functions."""

    def test_none_global_registered(self):
        """Should register none global."""
        engine = SecureTemplateEngine()
        assert "none" in engine.env.globals
        assert engine.env.globals["none"] is None

    def test_none_in_template(self, tmp_path):
        """Should be able to use none in template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "none_test.j2"
        template_file.write_text("{% if value is none %}null{% else %}{{ value }}{% endif %}")

        engine = SecureTemplateEngine(template_dir=template_dir)
        template = engine.env.get_template("none_test.j2")

        assert template.render(value=None) == "null"
        assert template.render(value="something") == "something"
