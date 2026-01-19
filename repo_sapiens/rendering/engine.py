"""Secure Jinja2 template rendering engine.

This module provides a hardened template rendering engine with security
features to prevent template injection and other attacks. It is the
foundation for all template rendering in repo-sapiens.

Security Features:
    - Sandboxed environment prevents arbitrary code execution
    - StrictUndefined catches missing variables early (fail-fast)
    - Template path validation prevents directory traversal attacks
    - Custom filters for safe value injection (URLs, identifiers, YAML)

The engine uses Jinja2's SandboxedEnvironment which restricts access to
unsafe attributes and methods, preventing templates from executing
arbitrary Python code or accessing sensitive data.

Key Exports:
    SecureTemplateEngine: Main class for secure template rendering.

Example:
    >>> from repo_sapiens.rendering.engine import SecureTemplateEngine
    >>> engine = SecureTemplateEngine()
    >>>
    >>> # Render a template with context
    >>> result = engine.render(
    ...     "workflows/gitea/ci/build.yaml.j2",
    ...     {"gitea_url": "https://gitea.example.com", "gitea_owner": "myorg"},
    ... )
    >>>
    >>> # List available templates
    >>> templates = engine.list_templates("workflows/**/*.yaml.j2")

Thread Safety:
    SecureTemplateEngine instances are thread-safe for rendering operations.
    The Jinja2 environment is immutable after initialization.

See Also:
    - repo_sapiens.rendering.filters: Custom Jinja2 filters
    - repo_sapiens.rendering.validators: Context validation
    - jinja2.sandbox: Jinja2 sandbox documentation
"""

from pathlib import Path
from typing import Any, cast

from jinja2 import (
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
)
from jinja2.sandbox import SandboxedEnvironment


class SecureTemplateEngine:
    """Secure Jinja2 template rendering engine with hardened configuration.

    This class provides a security-focused template rendering environment
    that prevents common template injection attacks while maintaining
    full Jinja2 template functionality.

    Security features:
        - Sandboxed environment: Prevents arbitrary code execution by
          restricting access to unsafe attributes and methods.
        - StrictUndefined: Raises errors for undefined variables instead
          of silently rendering empty strings.
        - Path validation: Prevents directory traversal attacks by
          ensuring all template paths resolve within the template directory.
        - Custom filters: Provides safe_url, safe_identifier, and yaml_*
          filters for secure value injection.

    Configuration options:
        - Autoescape disabled (YAML doesn't need HTML escaping)
        - trim_blocks/lstrip_blocks enabled for clean YAML output
        - keep_trailing_newline preserves file format

    Attributes:
        template_dir: Resolved path to the template directory.
        env: The SandboxedEnvironment instance.

    Example:
        >>> engine = SecureTemplateEngine()
        >>>
        >>> # Render with validation
        >>> yaml = engine.render(
        ...     "workflows/gitea/ci/build.yaml.j2",
        ...     {"gitea_url": "https://gitea.example.com"},
        ... )
        >>>
        >>> # Render without validation (for trusted contexts)
        >>> yaml = engine.render(
        ...     "workflows/gitea/ci/build.yaml.j2",
        ...     context,
        ...     validate=False,
        ... )
        >>>
        >>> # List templates
        >>> templates = engine.list_templates("workflows/**/*.yaml.j2")
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        enable_extensions: bool = False,
    ) -> None:
        """Initialize secure template engine.

        Args:
            template_dir: Root directory for templates. If None, uses the
                package's built-in templates directory. The directory must
                exist and be readable.
            enable_extensions: Allow Jinja2 extensions (disabled by default
                for security). Only enable if you need specific extensions
                and understand the security implications.

        Raises:
            ValueError: If template_dir doesn't exist or isn't a directory.

        Example:
            >>> # Use default package templates
            >>> engine = SecureTemplateEngine()
            >>>
            >>> # Use custom templates
            >>> engine = SecureTemplateEngine(template_dir=Path("./templates"))
            >>>
            >>> # Enable extensions (use with caution)
            >>> engine = SecureTemplateEngine(enable_extensions=True)
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
        """Register custom Jinja2 filters for safe value injection.

        Registers the following filters:
            - safe_url: Validates and sanitizes URLs
            - safe_identifier: Validates identifier strings
            - safe_label: Validates label/tag strings
            - yaml_string: Properly quotes YAML strings
            - yaml_list: Formats Python lists as YAML
            - yaml_dict: Formats Python dicts as YAML

        Note:
            Filters are imported from repo_sapiens.rendering.filters.
            This method is called during __init__.
        """
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
        """Register custom Jinja2 tests for template logic.

        Registers the following tests:
            - valid_url: Tests if value is a valid HTTP(S) URL
            - valid_identifier: Tests if value is a valid Python identifier

        Example usage in templates:
            {% if base_url is valid_url %}
            {% endif %}

        Note:
            This method is called during __init__.
        """
        self.env.tests.update(
            {
                "valid_url": lambda x: isinstance(x, str) and x.startswith(("https://", "http://")),
                "valid_identifier": lambda x: isinstance(x, str) and x.isidentifier(),
            }
        )

    def _register_globals(self) -> None:
        """Register custom global functions and values.

        Registers:
            - none: Python None value for default() filter compatibility

        This helps Jinja2's default() filter work properly with Pydantic
        models that use None for optional fields.

        Note:
            This method is called during __init__.
        """
        # Add None to the Jinja2 undefined for proper default handling
        # This helps Jinja2's default() filter work with Pydantic's None values
        self.env.globals.update(
            {
                "none": None,
            }
        )

    def validate_template_path(self, template_path: str) -> Path:
        """Validate template path to prevent directory traversal attacks.

        Ensures the requested template path resolves to a location within
        the template directory, preventing attacks like "../../../etc/passwd".

        Args:
            template_path: Relative path to template within template_dir.
                Example: "workflows/gitea/ci/build.yaml.j2"

        Returns:
            Resolved absolute path to the template file.

        Raises:
            ValueError: If path escapes template directory (traversal attack).
            TemplateNotFound: If the template file doesn't exist.

        Example:
            >>> path = engine.validate_template_path("workflows/ci/build.yaml.j2")
            >>> print(path)
            /path/to/templates/workflows/ci/build.yaml.j2

            >>> engine.validate_template_path("../../../etc/passwd")
            ValueError: Template path escapes template directory
        """
        # Normalize path and resolve
        requested_path = (self.template_dir / template_path).resolve()

        # Ensure the resolved path is within template_dir
        try:
            requested_path.relative_to(self.template_dir)
        except ValueError as e:
            raise ValueError(f"Template path escapes template directory: {template_path}") from e

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
        """Render a template with the given context.

        Loads the template, optionally validates the context, and renders
        the template with the provided variables.

        Args:
            template_path: Relative path to template within template_dir.
                Example: "workflows/gitea/ci/build.yaml.j2"
            context: Dictionary of variables to pass to the template.
                Keys should match variable names used in the template.
            validate: Whether to validate context before rendering.
                Default is True. Set to False for trusted contexts
                to skip validation overhead.

        Returns:
            Rendered template as a string (typically YAML).

        Raises:
            TemplateNotFound: If template doesn't exist.
            jinja2.TemplateSyntaxError: If template has syntax errors.
            jinja2.UndefinedError: If template uses undefined variables
                (because we use StrictUndefined).
            ValueError: If context validation fails (when validate=True).

        Example:
            >>> context = {
            ...     "gitea_url": "https://gitea.example.com",
            ...     "gitea_owner": "myorg",
            ...     "gitea_repo": "myrepo",
            ... }
            >>> yaml = engine.render(
            ...     "workflows/gitea/ci/build.yaml.j2",
            ...     context,
            ... )
            >>> print(yaml)

        Note:
            The path is validated before rendering to prevent directory
            traversal attacks. The sandboxed environment prevents code
            execution in templates.
        """
        # Validate template path to prevent directory traversal
        self.validate_template_path(template_path)

        # Validate context if requested
        if validate:
            from .validators import validate_template_context

            validate_template_context(context)

        # Load and render template
        template = self.env.get_template(template_path)
        rendered = cast(str, template.render(**context))

        return rendered

    def list_templates(self, pattern: str = "**/*.yaml.j2") -> list[str]:
        """List available templates matching a pattern.

        Scans the template directory for files matching the glob pattern
        and returns their relative paths.

        Args:
            pattern: Glob pattern for matching templates. Default matches
                all YAML Jinja2 templates recursively.

        Returns:
            Sorted list of template paths relative to template_dir.

        Example:
            >>> # List all workflow templates
            >>> templates = engine.list_templates("workflows/**/*.yaml.j2")
            >>> print(templates)
            ['workflows/gitea/ci/build.yaml.j2', 'workflows/github/ci/test.yaml.j2']

            >>> # List only Gitea templates
            >>> templates = engine.list_templates("workflows/gitea/**/*.yaml.j2")
        """
        templates = []
        for template_file in self.template_dir.glob(pattern):
            if template_file.is_file():
                rel_path = template_file.relative_to(self.template_dir)
                templates.append(str(rel_path))
        return sorted(templates)
