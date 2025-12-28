"""
Template rendering API for workflow generation.

This module provides a high-level interface for rendering Jinja2 templates
with security validation and error handling.
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
    """
    High-level API for rendering workflow templates.

    This class provides a user-friendly interface for template rendering
    with automatic validation, error handling, and output management.
    """

    def __init__(self, template_dir: Path | None = None):
        """
        Initialize workflow renderer.

        Args:
            template_dir: Custom template directory (default: package templates)
        """
        self.engine = SecureTemplateEngine(template_dir=template_dir)

    def render_workflow(
        self,
        template_name: str,
        config: WorkflowConfig,
        output_path: Path | None = None,
    ) -> str:
        """
        Render a workflow template with validation.

        Args:
            template_name: Name of template (e.g., "ci/build")
            config: Validated workflow configuration
            output_path: Optional path to write rendered workflow

        Returns:
            Rendered workflow YAML

        Raises:
            TemplateNotFound: If template doesn't exist
            ValueError: If configuration is invalid
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
        """
        Render multiple workflows to an output directory.

        Args:
            configs: Mapping of template names to configurations
            output_dir: Directory to write rendered workflows

        Returns:
            Mapping of template names to output file paths
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
        """
        List all available workflow templates.

        Returns:
            List of template names (without .yaml.j2 extension)
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
    """
    Quick workflow rendering with minimal configuration.

    Args:
        template_name: Name of template (e.g., "ci/build")
        gitea_url: Gitea instance URL
        gitea_owner: Repository owner
        gitea_repo: Repository name
        **kwargs: Additional template variables

    Returns:
        Rendered workflow YAML
    """
    config = WorkflowConfig(
        gitea_url=gitea_url,
        gitea_owner=gitea_owner,
        gitea_repo=gitea_repo,
        **kwargs,
    )

    renderer = WorkflowRenderer()
    return renderer.render_workflow(template_name, config)
