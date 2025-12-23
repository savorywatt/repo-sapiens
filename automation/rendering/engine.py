"""
Secure Jinja2 template rendering engine.

This module provides a hardened template rendering engine with security
features to prevent template injection and other attacks.
"""

from pathlib import Path
from typing import Any

from jinja2 import (
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
)
from jinja2.sandbox import SandboxedEnvironment


class SecureTemplateEngine:
    """
    Secure Jinja2 template rendering engine with hardened configuration.

    Security features:
    - Sandboxed environment prevents arbitrary code execution
    - StrictUndefined catches missing variables early
    - Autoescape disabled (YAML doesn't need HTML escaping, but we validate differently)
    - Custom filters for safe value injection
    - Template path validation prevents directory traversal
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        enable_extensions: bool = False,
    ):
        """
        Initialize secure template engine.

        Args:
            template_dir: Root directory for templates. Defaults to package templates.
            enable_extensions: Allow Jinja2 extensions (disabled by default for security)
        """
        if template_dir is None:
            # Use package templates by default
            template_dir = Path(__file__).parent.parent / "templates"

        self.template_dir = template_dir.resolve()

        # Verify template directory exists and is readable
        if not self.template_dir.exists():
            raise ValueError(f"Template directory does not exist: {self.template_dir}")
        if not self.template_dir.is_dir():
            raise ValueError(f"Template path is not a directory: {self.template_dir}")

        # Create sandboxed environment with strict security settings
        self.env = SandboxedEnvironment(
            loader=FileSystemLoader(str(self.template_dir)),
            undefined=StrictUndefined,  # Fail on undefined variables
            autoescape=False,  # YAML doesn't need HTML escaping
            trim_blocks=True,  # Remove first newline after block
            lstrip_blocks=True,  # Strip leading spaces/tabs from block
            keep_trailing_newline=True,  # Preserve final newline
            extensions=[] if not enable_extensions else ["jinja2.ext.do"],
        )

        # Register custom filters for safe value handling
        self._register_filters()

        # Register custom tests
        self._register_tests()

        # Register custom globals
        self._register_globals()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters for safe value injection."""
        from .filters import (
            safe_identifier,
            safe_label,
            safe_url,
            yaml_dict,
            yaml_list,
            yaml_string,
        )

        self.env.filters.update(
            {
                "safe_url": safe_url,
                "safe_identifier": safe_identifier,
                "safe_label": safe_label,
                "yaml_string": yaml_string,
                "yaml_list": yaml_list,
                "yaml_dict": yaml_dict,
            }
        )

    def _register_tests(self) -> None:
        """Register custom Jinja2 tests for template logic."""
        self.env.tests.update(
            {
                "valid_url": lambda x: isinstance(x, str) and x.startswith(("https://", "http://")),
                "valid_identifier": lambda x: isinstance(x, str) and x.isidentifier(),
            }
        )

    def _register_globals(self) -> None:
        """Register custom global functions."""
        # Add None to the Jinja2 undefined for proper default handling
        # This helps Jinja2's default() filter work with Pydantic's None values
        self.env.globals.update(
            {
                "none": None,
            }
        )

    def validate_template_path(self, template_path: str) -> Path:
        """
        Validate template path to prevent directory traversal attacks.

        Args:
            template_path: Relative path to template within template_dir

        Returns:
            Resolved absolute path to template

        Raises:
            ValueError: If path is invalid or outside template directory
        """
        # Normalize path and resolve
        requested_path = (self.template_dir / template_path).resolve()

        # Ensure the resolved path is within template_dir
        try:
            requested_path.relative_to(self.template_dir)
        except ValueError:
            raise ValueError(f"Template path escapes template directory: {template_path}")

        # Ensure file exists
        if not requested_path.exists():
            raise TemplateNotFound(template_path)

        return requested_path

    def render(
        self,
        template_path: str,
        context: dict[str, Any],
        validate: bool = True,
    ) -> str:
        """
        Render a template with the given context.

        Args:
            template_path: Relative path to template (e.g., "workflows/ci/build.yaml.j2")
            context: Dictionary of variables to pass to template
            validate: Whether to validate context before rendering (default: True)

        Returns:
            Rendered template as string

        Raises:
            TemplateNotFound: If template doesn't exist
            TemplateSyntaxError: If template has syntax errors
            ValueError: If context validation fails
        """
        # Validate template path to prevent directory traversal
        self.validate_template_path(template_path)

        # Validate context if requested
        if validate:
            from .validators import validate_template_context

            validate_template_context(context)

        # Load and render template
        template = self.env.get_template(template_path)
        rendered = template.render(**context)

        return rendered

    def list_templates(self, pattern: str = "**/*.yaml.j2") -> list[str]:
        """
        List available templates matching a pattern.

        Args:
            pattern: Glob pattern for matching templates

        Returns:
            List of template paths relative to template_dir
        """
        templates = []
        for template_file in self.template_dir.glob(pattern):
            if template_file.is_file():
                rel_path = template_file.relative_to(self.template_dir)
                templates.append(str(rel_path))
        return sorted(templates)
