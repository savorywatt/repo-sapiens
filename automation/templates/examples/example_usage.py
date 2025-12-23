#!/usr/bin/env python3
"""
Example usage of the secure template system.

This script demonstrates how to use the template rendering system
to generate workflow files.

Requirements:
    pip install jinja2>=3.1.3 pydantic>=2.0.0 pyyaml>=6.0
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from automation.rendering import WorkflowRenderer, render_workflow
from automation.rendering.validators import (
    CIBuildConfig,
    LabelSyncConfig,
    PyPIPublishConfig,
)


def example_quick_render():
    """Demonstrate quick workflow rendering."""
    print("=" * 70)
    print("Example 1: Quick Workflow Rendering")
    print("=" * 70)

    workflow = render_workflow(
        "ci/build",
        gitea_url="https://gitea.example.com",
        gitea_owner="example-org",
        gitea_repo="example-repo",
        package_name="example-package",
    )

    print(workflow)
    print()


def example_advanced_config():
    """Demonstrate advanced configuration."""
    print("=" * 70)
    print("Example 2: Advanced Configuration")
    print("=" * 70)

    renderer = WorkflowRenderer()

    config = CIBuildConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="example-org",
        gitea_repo="example-repo",
        workflow_name="Custom CI Pipeline",
        python_versions=["3.11", "3.12", "3.13"],
        linters=["ruff", "mypy", "pylint"],
        fail_fast=True,
        artifact_retention_days=30,
        package_name="example-package",
    )

    workflow = renderer.render_workflow("ci/build", config)
    print(workflow)
    print()


def example_batch_generation():
    """Demonstrate batch workflow generation."""
    print("=" * 70)
    print("Example 3: Batch Workflow Generation")
    print("=" * 70)

    renderer = WorkflowRenderer()
    output_dir = Path("/tmp/workflows-example")

    configs = {
        "ci/build": CIBuildConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="example-org",
            gitea_repo="example-repo",
            package_name="example-package",
        ),
        "automation/label-sync": LabelSyncConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="example-org",
            gitea_repo="example-repo",
            dry_run=True,
        ),
        "release/pypi-publish": PyPIPublishConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="example-org",
            gitea_repo="example-repo",
            package_name="example-package",
            use_trusted_publishing=True,
        ),
    }

    results = renderer.render_all_workflows(configs, output_dir)

    print(f"Generated {len(results)} workflows to {output_dir}:")
    for template, output_file in results.items():
        print(f"  - {template} -> {output_file}")
    print()


def example_list_templates():
    """Demonstrate template listing."""
    print("=" * 70)
    print("Example 4: List Available Templates")
    print("=" * 70)

    renderer = WorkflowRenderer()
    templates = renderer.list_available_templates()

    print(f"Found {len(templates)} available templates:")
    for template in templates:
        print(f"  - {template}")
    print()


def example_security_validation():
    """Demonstrate security validation."""
    print("=" * 70)
    print("Example 5: Security Validation")
    print("=" * 70)

    from automation.rendering.filters import safe_identifier, safe_label, safe_url

    # Valid inputs
    print("Valid inputs:")
    print(f"  URL: {safe_url('https://gitea.example.com')}")
    print(f"  Identifier: {safe_identifier('my-repo')}")
    print(f"  Label: {safe_label('bug fix')}")
    print()

    # Invalid inputs
    print("Invalid inputs (will raise errors):")
    try:
        safe_url("javascript:alert(1)")
    except ValueError as e:
        print(f"  URL validation: {e}")

    try:
        safe_identifier("repo:with:colons")
    except ValueError as e:
        print(f"  Identifier validation: {e}")

    try:
        safe_label("label{with}braces")
    except ValueError as e:
        print(f"  Label validation: {e}")
    print()


if __name__ == "__main__":
    print("\nSecure Template System - Usage Examples")
    print("=" * 70)
    print()

    try:
        example_quick_render()
        example_advanced_config()
        example_batch_generation()
        example_list_templates()
        example_security_validation()

        print("=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
