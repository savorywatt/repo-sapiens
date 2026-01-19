"""Template rendering API for workflow generation.

This module provides a high-level interface for rendering Jinja2 templates
with security validation and error handling. It is the primary entry point
for generating CI/CD workflow files from templates.

The rendering system is built on a secure Jinja2 environment with:
    - Sandboxed execution to prevent arbitrary code execution
    - StrictUndefined to catch missing variables early
    - Custom filters for safe value injection (URLs, identifiers, YAML)
    - Template path validation to prevent directory traversal attacks

Key Exports:
    SecureTemplateEngine: Low-level secure Jinja2 rendering engine.
    WorkflowRenderer: High-level API for rendering workflow templates.
    WorkflowConfig: Pydantic model for workflow configuration validation.
    render_workflow: Convenience function for quick one-off rendering.

Example:
    >>> from repo_sapiens.rendering import WorkflowRenderer, WorkflowConfig
    >>>
    >>> # Create a renderer
    >>> renderer = WorkflowRenderer()
    >>>
    >>> # List available templates
    >>> templates = renderer.list_available_templates()
    >>> print(templates)  # ['gitea/sapiens/process-label', ...]
    >>>
    >>> # Render a workflow
    >>> config = WorkflowConfig(
    ...     gitea_url="https://gitea.example.com",
    ...     gitea_owner="myorg",
    ...     gitea_repo="myrepo",
    ... )
    >>> yaml_content = renderer.render_workflow("gitea/sapiens/process-label", config)
    >>> print(yaml_content)

Quick Rendering:
    For simple use cases, use the convenience function:

    >>> from repo_sapiens.rendering import render_workflow
    >>> yaml = render_workflow(
    ...     "gitea/sapiens/process-label",
    ...     gitea_url="https://gitea.example.com",
    ...     gitea_owner="myorg",
    ...     gitea_repo="myrepo",
    ... )

See Also:
    - repo_sapiens.rendering.engine: SecureTemplateEngine implementation
    - repo_sapiens.rendering.validators: WorkflowConfig and validation
    - repo_sapiens.rendering.filters: Custom Jinja2 filters
"""

from pathlib import Path
from typing import Any

from .engine import SecureTemplateEngine
from .validators import WorkflowConfig

__all__ = [
    "SecureTemplateEngine",
    "WorkflowRenderer",
    "WorkflowConfig",
    "render_workflow",
]


class WorkflowRenderer:
    """High-level API for rendering workflow templates.

    This class provides a user-friendly interface for template rendering
    with automatic validation, error handling, and output management.
    It wraps SecureTemplateEngine with workflow-specific conveniences.

    The renderer automatically:
        - Validates configuration using Pydantic models
        - Locates templates in the package's template directory
        - Handles template path construction and extension
        - Optionally writes rendered output to files

    Attributes:
        engine: The underlying SecureTemplateEngine instance.

    Example:
        >>> renderer = WorkflowRenderer()
        >>>
        >>> # List what's available
        >>> for template in renderer.list_available_templates():
        ...     print(f"  - {template}")
        >>>
        >>> # Render a single workflow
        >>> config = WorkflowConfig(
        ...     gitea_url="https://gitea.example.com",
        ...     gitea_owner="myorg",
        ...     gitea_repo="myrepo",
        ... )
        >>> yaml = renderer.render_workflow("gitea/ci/build", config)
        >>>
        >>> # Render and save to file
        >>> renderer.render_workflow(
        ...     "gitea/ci/build",
        ...     config,
        ...     output_path=Path(".gitea/workflows/build.yaml"),
        ... )
        >>>
        >>> # Render multiple workflows at once
        >>> configs = {
        ...     "gitea/ci/build": config,
        ...     "gitea/ci/test": config,
        ... }
        >>> paths = renderer.render_all_workflows(configs, Path(".gitea/workflows"))
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize workflow renderer.

        Args:
            template_dir: Custom template directory. If None (default),
                uses the package's built-in templates directory.

        Example:
            >>> # Use default templates
            >>> renderer = WorkflowRenderer()
            >>>
            >>> # Use custom templates
            >>> renderer = WorkflowRenderer(template_dir=Path("./my-templates"))
        """
        self.engine = SecureTemplateEngine(template_dir=template_dir)

    def render_workflow(
        self,
        template_name: str,
        config: WorkflowConfig,
        output_path: Path | None = None,
    ) -> str:
        """Render a workflow template with validation.

        Takes a template name and validated configuration, renders the
        template, and optionally writes the output to a file.

        Args:
            template_name: Name of template without extension or prefix.
                Examples: "gitea/ci/build", "github/sapiens/process-label"
            config: Validated WorkflowConfig with template variables.
            output_path: Optional path to write rendered workflow. Parent
                directories are created if they don't exist.

        Returns:
            Rendered workflow as a YAML string.

        Raises:
            TemplateNotFound: If the template doesn't exist.
            ValueError: If configuration is invalid for the template.
            jinja2.TemplateSyntaxError: If template has syntax errors.

        Example:
            >>> config = WorkflowConfig(
            ...     gitea_url="https://gitea.example.com",
            ...     gitea_owner="myorg",
            ...     gitea_repo="myrepo",
            ... )
            >>>
            >>> # Just get the rendered content
            >>> yaml = renderer.render_workflow("gitea/ci/build", config)
            >>>
            >>> # Render and save to file
            >>> yaml = renderer.render_workflow(
            ...     "gitea/ci/build",
            ...     config,
            ...     output_path=Path(".gitea/workflows/build.yaml"),
            ... )
        """
        # Build template path
        template_path = f"workflows/{template_name}.yaml.j2"

        # Convert config to dict for rendering, excluding None values
        # This allows Jinja2's default() filter to work properly
        # Use mode='python' to get proper serialization of custom types like HttpUrl
        context = config.model_dump(mode="python", exclude_none=True)

        # Render template
        rendered = self.engine.render(template_path, context)

        # Write to file if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered)

        return rendered

    def render_all_workflows(
        self,
        configs: dict[str, WorkflowConfig],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Render multiple workflows to an output directory.

        Batch renders multiple templates with their configurations,
        writing each to a file in the output directory.

        Args:
            configs: Mapping of template names to configurations.
            output_dir: Directory to write rendered workflows.

        Returns:
            Mapping of template names to output file paths.

        Example:
            >>> config = WorkflowConfig(
            ...     gitea_url="https://gitea.example.com",
            ...     gitea_owner="myorg",
            ...     gitea_repo="myrepo",
            ... )
            >>> configs = {
            ...     "gitea/ci/build": config,
            ...     "gitea/ci/test": config,
            ...     "gitea/ci/deploy": config,
            ... }
            >>> paths = renderer.render_all_workflows(
            ...     configs,
            ...     Path(".gitea/workflows"),
            ... )
            >>> for name, path in paths.items():
            ...     print(f"{name} -> {path}")
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        for template_name, config in configs.items():
            # Determine output filename
            output_file = output_dir / f"{template_name.replace('/', '-')}.yaml"

            # Render workflow
            self.render_workflow(template_name, config, output_file)
            results[template_name] = output_file

        return results

    def list_available_templates(self) -> list[str]:
        """List all available workflow templates.

        Scans the template directory for workflow templates and returns
        their names in a format suitable for render_workflow().

        Returns:
            List of template names without the .yaml.j2 extension.
            Example: ["gitea/ci/build", "gitea/sapiens/process-label"]

        Example:
            >>> templates = renderer.list_available_templates()
            >>> for t in templates:
            ...     print(f"  {t}")
        """
        templates = self.engine.list_templates("workflows/**/*.yaml.j2")

        # Remove prefix and suffix for cleaner names
        cleaned = []
        for template in templates:
            name = template.replace("workflows/", "").replace(".yaml.j2", "")
            cleaned.append(name)

        return cleaned


# Convenience function for quick rendering
def render_workflow(
    template_name: str,
    gitea_url: str,
    gitea_owner: str,
    gitea_repo: str,
    **kwargs: Any,
) -> str:
    """Quick workflow rendering with minimal configuration.

    Convenience function for one-off template rendering without
    manually constructing WorkflowConfig and WorkflowRenderer objects.

    Args:
        template_name: Name of template (e.g., "gitea/ci/build").
        gitea_url: Gitea instance URL (e.g., "https://gitea.example.com").
        gitea_owner: Repository owner/organization name.
        gitea_repo: Repository name.
        **kwargs: Additional template variables to pass to WorkflowConfig.

    Returns:
        Rendered workflow YAML as a string.

    Raises:
        TemplateNotFound: If the template doesn't exist.
        ValueError: If configuration is invalid.

    Example:
        >>> yaml = render_workflow(
        ...     "gitea/ci/build",
        ...     gitea_url="https://gitea.example.com",
        ...     gitea_owner="myorg",
        ...     gitea_repo="myrepo",
        ...     python_version="3.11",
        ... )
        >>> print(yaml)
    """
    config = WorkflowConfig(
        gitea_url=gitea_url,
        gitea_owner=gitea_owner,
        gitea_repo=gitea_repo,
        **kwargs,
    )

    renderer = WorkflowRenderer()
    return renderer.render_workflow(template_name, config)
