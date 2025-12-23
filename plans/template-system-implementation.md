# Jinja2-based Workflow Template System Implementation Plan

**Document Version:** 1.0
**Date:** 2025-12-22
**Status:** Planning
**Python Version:** 3.11+
**Jinja2 Version:** 3.1.3+

## Executive Summary

This document outlines the implementation of a secure, maintainable Jinja2-based template system for generating Gitea Actions workflow files. The system addresses security concerns raised in the technical review regarding template injection vulnerabilities while providing a flexible, testable architecture for managing 13+ workflow templates.

## 1. Template Directory Structure

### 1.1 Proposed Directory Layout

```
repo-agent/
├── src/
│   └── repo_agent/
│       ├── templates/
│       │   ├── __init__.py
│       │   ├── workflows/          # Jinja2 workflow templates
│       │   │   ├── __init__.py
│       │   │   ├── base.yaml.j2    # Base template with common elements
│       │   │   ├── ci/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── build.yaml.j2
│       │   │   │   ├── test.yaml.j2
│       │   │   │   └── lint.yaml.j2
│       │   │   ├── release/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── pypi-publish.yaml.j2
│       │   │   │   ├── github-release.yaml.j2
│       │   │   │   └── tag-management.yaml.j2
│       │   │   ├── automation/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── label-sync.yaml.j2
│       │   │   │   ├── pr-labels.yaml.j2
│       │   │   │   ├── issue-labels.yaml.j2
│       │   │   │   └── stale-issues.yaml.j2
│       │   │   └── docs/
│       │   │       ├── __init__.py
│       │   │       ├── build-docs.yaml.j2
│       │   │       └── deploy-docs.yaml.j2
│       │   ├── macros/              # Reusable Jinja2 macros
│       │   │   ├── __init__.py
│       │   │   ├── steps.yaml.j2   # Common step definitions
│       │   │   ├── jobs.yaml.j2    # Common job patterns
│       │   │   └── triggers.yaml.j2 # Common trigger patterns
│       │   └── schemas/            # JSON schemas for validation
│       │       ├── __init__.py
│       │       ├── workflow-config.schema.json
│       │       └── template-vars.schema.json
│       └── rendering/
│           ├── __init__.py
│           ├── engine.py           # Core rendering engine
│           ├── validators.py       # Input validation
│           ├── filters.py          # Custom Jinja2 filters
│           └── security.py         # Security utilities
├── tests/
│   └── templates/
│       ├── test_rendering.py
│       ├── test_security.py
│       ├── test_validators.py
│       └── fixtures/
│           ├── valid_configs/
│           └── invalid_configs/
└── docs/
    └── templates/
        ├── template-guide.md
        └── security-guidelines.md
```

### 1.2 Directory Design Rationale

- **Categorization**: Templates organized by workflow type (ci, release, automation, docs)
- **Reusability**: Shared macros prevent duplication
- **Validation**: Schema files enable strict input validation
- **Testability**: Clear separation of rendering logic from templates
- **Discoverability**: `__init__.py` files can export template metadata

## 2. Secure Jinja2 Environment Setup

### 2.1 Core Security Configuration

```python
# src/repo_agent/rendering/engine.py
from pathlib import Path
from typing import Any, Dict, Optional
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    select_autoescape,
    TemplateNotFound,
    TemplateSyntaxError,
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
        template_dir: Optional[Path] = None,
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

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters for safe value injection."""
        from .filters import (
            safe_url,
            safe_identifier,
            safe_label,
            yaml_string,
            yaml_list,
            yaml_dict,
        )

        self.env.filters.update({
            "safe_url": safe_url,
            "safe_identifier": safe_identifier,
            "safe_label": safe_label,
            "yaml_string": yaml_string,
            "yaml_list": yaml_list,
            "yaml_dict": yaml_dict,
        })

    def _register_tests(self) -> None:
        """Register custom Jinja2 tests for template logic."""
        self.env.tests.update({
            "valid_url": lambda x: x.startswith(("https://", "http://")),
            "valid_identifier": lambda x: x.isidentifier(),
        })

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
            raise ValueError(
                f"Template path escapes template directory: {template_path}"
            )

        # Ensure file exists
        if not requested_path.exists():
            raise TemplateNotFound(template_path)

        return requested_path

    def render(
        self,
        template_path: str,
        context: Dict[str, Any],
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
```

### 2.2 Custom Security Filters

```python
# src/repo_agent/rendering/filters.py
"""
Custom Jinja2 filters for safe value injection in templates.

These filters ensure that user-provided values are properly sanitized
before being injected into YAML workflow files.
"""
import re
from typing import Any
from urllib.parse import urlparse
import yaml


def safe_url(value: str) -> str:
    """
    Validate and sanitize URL values.

    Only allows https:// and http:// schemes.
    Removes any potential YAML injection characters.

    Args:
        value: URL to sanitize

    Returns:
        Sanitized URL

    Raises:
        ValueError: If URL is invalid or uses disallowed scheme
    """
    if not isinstance(value, str):
        raise ValueError(f"URL must be string, got {type(value).__name__}")

    parsed = urlparse(value)

    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    if not parsed.netloc:
        raise ValueError("URL must have a domain")

    # Return original value if valid (already URL-encoded)
    return value


def safe_identifier(value: str, max_length: int = 100) -> str:
    """
    Sanitize values used as identifiers (repo names, owners, etc.).

    Allows: alphanumeric, hyphens, underscores
    Disallows: special characters that could break YAML or enable injection

    Args:
        value: Identifier to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized identifier

    Raises:
        ValueError: If identifier is invalid
    """
    if not isinstance(value, str):
        raise ValueError(f"Identifier must be string, got {type(value).__name__}")

    if not value:
        raise ValueError("Identifier cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"Identifier too long: {len(value)} > {max_length}")

    # Allow alphanumeric, hyphens, underscores, dots (for domains)
    if not re.match(r'^[a-zA-Z0-9._-]+$', value):
        raise ValueError(f"Invalid identifier characters: {value}")

    return value


def safe_label(value: str, max_length: int = 50) -> str:
    """
    Sanitize label names for Gitea.

    More permissive than identifiers but still prevents injection.

    Args:
        value: Label name to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized label name

    Raises:
        ValueError: If label name is invalid
    """
    if not isinstance(value, str):
        raise ValueError(f"Label must be string, got {type(value).__name__}")

    if not value:
        raise ValueError("Label cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"Label too long: {len(value)} > {max_length}")

    # Disallow YAML-sensitive characters and control characters
    if re.search(r'[:\n\r\t\{\}\[\]&*#?|<>=!%@`]', value):
        raise ValueError(f"Label contains invalid characters: {value}")

    return value.strip()


def yaml_string(value: Any) -> str:
    """
    Safely convert value to YAML string representation.

    Uses PyYAML to ensure proper escaping and quoting.

    Args:
        value: Value to convert to YAML string

    Returns:
        YAML-safe string representation
    """
    return yaml.safe_dump(value, default_flow_style=True).strip()


def yaml_list(value: list[Any]) -> str:
    """
    Convert Python list to YAML list representation.

    Args:
        value: List to convert

    Returns:
        YAML-formatted list
    """
    if not isinstance(value, list):
        raise ValueError(f"Expected list, got {type(value).__name__}")

    return yaml.safe_dump(value, default_flow_style=False).strip()


def yaml_dict(value: dict[str, Any]) -> str:
    """
    Convert Python dict to YAML dict representation.

    Args:
        value: Dict to convert

    Returns:
        YAML-formatted dict
    """
    if not isinstance(value, dict):
        raise ValueError(f"Expected dict, got {type(value).__name__}")

    return yaml.safe_dump(value, default_flow_style=False).strip()
```

## 3. Workflow Template Design

### 3.1 Base Template with Macros

```yaml
{# src/repo_agent/templates/workflows/base.yaml.j2 #}
{# Base template with common patterns and security #}

{% macro checkout_step(ref='', fetch_depth=1) -%}
- name: Checkout code
  uses: actions/checkout@v4
  with:
    {%- if ref %}
    ref: {{ ref | safe_identifier }}
    {%- endif %}
    fetch-depth: {{ fetch_depth | int }}
{%- endmacro %}

{% macro setup_python_step(version='3.11') -%}
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '{{ version | safe_identifier }}'
    cache: 'pip'
{%- endmacro %}

{% macro install_dependencies_step(requirements_file='requirements.txt') -%}
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r {{ requirements_file | safe_identifier }}
{%- endmacro %}

{% macro security_check(value, validator) -%}
{# Helper to validate values in templates #}
{%- if value is not defined -%}
  {{ raise("Required value not provided") }}
{%- endif -%}
{{ value }}
{%- endmacro %}

{# Common environment variables for all workflows #}
{% macro gitea_env_vars() -%}
env:
  GITEA_URL: {{ gitea_url | safe_url }}
  GITEA_OWNER: {{ gitea_owner | safe_identifier }}
  GITEA_REPO: {{ gitea_repo | safe_identifier }}
{%- endmacro %}
```

### 3.2 Example CI Build Template

```yaml
{# src/repo_agent/templates/workflows/ci/build.yaml.j2 #}
{% import 'workflows/base.yaml.j2' as base %}

name: {{ workflow_name | default('Build and Test') | safe_label }}

on:
  push:
    branches:
      {% for branch in trigger_branches | default(['main', 'develop']) -%}
      - {{ branch | safe_identifier }}
      {% endfor %}
  pull_request:
    branches:
      {% for branch in pr_branches | default(['main']) -%}
      - {{ branch | safe_identifier }}
      {% endfor %}
  workflow_dispatch:

{{ base.gitea_env_vars() }}

jobs:
  build:
    name: Build and Test
    runs-on: {{ runner | default('ubuntu-latest') | safe_identifier }}

    strategy:
      matrix:
        python-version:
          {% for version in python_versions | default(['3.11', '3.12']) -%}
          - '{{ version | safe_identifier }}'
          {% endfor %}
      fail-fast: {{ fail_fast | default(false) | lower }}

    steps:
      {{ base.checkout_step() }}

      {{ base.setup_python_step(version='${{ matrix.python-version }}') }}

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip build wheel
          pip install -e .[dev]

      - name: Run linters
        run: |
          {% for linter in linters | default(['ruff', 'mypy']) -%}
          {{ linter | safe_identifier }} .
          {% endfor %}

      - name: Run tests
        run: |
          pytest tests/ \
            --cov={{ package_name | safe_identifier }} \
            --cov-report=xml \
            --cov-report=term-missing \
            -v

      - name: Build package
        run: python -m build

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.python-version }}
          path: dist/
          retention-days: {{ artifact_retention_days | default(7) | int }}
```

### 3.3 Example Label Sync Template

```yaml
{# src/repo_agent/templates/workflows/automation/label-sync.yaml.j2 #}
{% import 'workflows/base.yaml.j2' as base %}

name: {{ workflow_name | default('Sync Repository Labels') | safe_label }}

on:
  push:
    branches:
      - {{ main_branch | default('main') | safe_identifier }}
    paths:
      - '{{ labels_file | default('.github/labels.yaml') }}'
  workflow_dispatch:

{{ base.gitea_env_vars() }}

jobs:
  sync-labels:
    name: Sync Labels
    runs-on: {{ runner | default('ubuntu-latest') | safe_identifier }}

    steps:
      {{ base.checkout_step() }}

      {{ base.setup_python_step() }}

      - name: Install repo-agent
        run: pip install repo-agent

      - name: Sync labels
        env:
          GITEA_TOKEN: ${{ '{{' }} secrets.GITEA_TOKEN {{ '}}' }}
        run: |
          repo-agent labels sync \
            --url {{ gitea_url | safe_url }} \
            --owner {{ gitea_owner | safe_identifier }} \
            --repo {{ gitea_repo | safe_identifier }} \
            --file {{ labels_file | default('.github/labels.yaml') }} \
            {% if dry_run | default(false) -%}
            --dry-run
            {%- endif %}

      - name: Report results
        if: always()
        run: |
          echo "Label sync completed"
          repo-agent labels list \
            --url {{ gitea_url | safe_url }} \
            --owner {{ gitea_owner | safe_identifier }} \
            --repo {{ gitea_repo | safe_identifier }}
```

### 3.4 PyPI Publishing Template

```yaml
{# src/repo_agent/templates/workflows/release/pypi-publish.yaml.j2 #}
{% import 'workflows/base.yaml.j2' as base %}

name: {{ workflow_name | default('Publish to PyPI') | safe_label }}

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      test-pypi:
        description: 'Publish to Test PyPI instead of PyPI'
        required: false
        default: 'false'
        type: boolean

{{ base.gitea_env_vars() }}

jobs:
  publish:
    name: Build and Publish
    runs-on: {{ runner | default('ubuntu-latest') | safe_identifier }}

    environment:
      name: {{ environment | default('release') | safe_identifier }}
      url: https://pypi.org/project/{{ package_name | safe_identifier }}/

    permissions:
      contents: read
      id-token: write  # Required for trusted publishing

    steps:
      {{ base.checkout_step(fetch_depth=0) }}

      {{ base.setup_python_step(version=python_version | default('3.11')) }}

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip build twine

      - name: Verify version matches tag
        if: github.event_name == 'release'
        run: |
          TAG_VERSION="${GITHUB_REF#refs/tags/v}"
          PKG_VERSION=$(python -c "import {{ package_name | safe_identifier }}; print({{ package_name | safe_identifier }}.__version__)")
          if [ "$TAG_VERSION" != "$PKG_VERSION" ]; then
            echo "Version mismatch: tag=$TAG_VERSION package=$PKG_VERSION"
            exit 1
          fi

      - name: Build package
        run: python -m build

      - name: Check package
        run: twine check dist/*

      {% if use_trusted_publishing | default(true) -%}
      - name: Publish to PyPI (trusted publishing)
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: {{ '${{ inputs.test-pypi == \'true\' && \'https://test.pypi.org/legacy/\' || \'https://upload.pypi.org/legacy/\' }}' }}
      {%- else -%}
      - name: Publish to PyPI (API token)
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ '{{' }} secrets.PYPI_API_TOKEN {{ '}}' }}
        run: |
          {% if test_pypi | default(false) -%}
          twine upload --repository testpypi dist/*
          {%- else -%}
          twine upload dist/*
          {%- endif %}
      {%- endif %}

      - name: Create GitHub Release
        if: github.event_name == 'release'
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
          generate_release_notes: true
```

## 4. Template Rendering Engine

### 4.1 High-Level Rendering API

```python
# src/repo_agent/rendering/__init__.py
"""
Template rendering API for workflow generation.

This module provides a high-level interface for rendering Jinja2 templates
with security validation and error handling.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from .engine import SecureTemplateEngine
from .validators import WorkflowConfig, validate_template_context


class WorkflowRenderer:
    """
    High-level API for rendering workflow templates.

    This class provides a user-friendly interface for template rendering
    with automatic validation, error handling, and output management.
    """

    def __init__(self, template_dir: Optional[Path] = None):
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
        output_path: Optional[Path] = None,
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

        # Convert config to dict for rendering
        context = config.model_dump()

        # Render template
        rendered = self.engine.render(template_path, context)

        # Write to file if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered)

        return rendered

    def render_all_workflows(
        self,
        configs: Dict[str, WorkflowConfig],
        output_dir: Path,
    ) -> Dict[str, Path]:
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
```

## 5. Variable Injection and Validation

### 5.1 Pydantic Models for Type Safety

```python
# src/repo_agent/rendering/validators.py
"""
Validation models and functions for template contexts.

Uses Pydantic for strong typing and validation of template variables.
"""
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    HttpUrl,
)


class WorkflowConfig(BaseModel):
    """
    Base configuration for all workflow templates.

    This model defines required and common optional fields for workflow
    generation. Template-specific fields should be added as needed.
    """

    # Required fields
    gitea_url: HttpUrl = Field(
        ...,
        description="URL of Gitea instance (e.g., https://gitea.example.com)",
    )
    gitea_owner: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Repository owner/organization name",
    )
    gitea_repo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Repository name",
    )

    # Common optional fields
    workflow_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom workflow name",
    )
    runner: str = Field(
        "ubuntu-latest",
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="GitHub Actions runner to use",
    )
    python_version: str = Field(
        "3.11",
        pattern=r'^\d+\.\d+$',
        description="Python version for workflows",
    )

    # Template-specific fields (examples)
    trigger_branches: List[str] = Field(
        default_factory=lambda: ["main"],
        description="Branches that trigger the workflow",
    )
    labels_file: str = Field(
        ".github/labels.yaml",
        description="Path to labels configuration file",
    )
    package_name: Optional[str] = Field(
        None,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Python package name",
    )

    model_config = {
        "extra": "allow",  # Allow template-specific fields
        "str_strip_whitespace": True,
    }

    @field_validator("trigger_branches")
    @classmethod
    def validate_branches(cls, v: List[str]) -> List[str]:
        """Validate branch names."""
        for branch in v:
            if not branch or len(branch) > 255:
                raise ValueError(f"Invalid branch name: {branch}")
            # Branch names can contain most characters, but validate basics
            if any(char in branch for char in ["\n", "\r", "\0"]):
                raise ValueError(f"Branch name contains invalid characters: {branch}")
        return v

    @field_validator("gitea_url")
    @classmethod
    def validate_gitea_url(cls, v: HttpUrl) -> str:
        """Ensure Gitea URL uses HTTPS in production."""
        url_str = str(v)
        parsed = urlparse(url_str)

        # Warn about HTTP (allow for local development)
        if parsed.scheme == "http" and not parsed.netloc.startswith("localhost"):
            import warnings
            warnings.warn(
                f"Using insecure HTTP for Gitea URL: {url_str}. "
                "Consider using HTTPS in production.",
                UserWarning,
            )

        return url_str

    @model_validator(mode="after")
    def validate_package_name_if_needed(self) -> "WorkflowConfig":
        """Validate package_name is set for PyPI workflows."""
        # This can be extended to check template-specific requirements
        return self


class CIBuildConfig(WorkflowConfig):
    """Configuration specific to CI build workflows."""

    python_versions: List[str] = Field(
        default_factory=lambda: ["3.11", "3.12"],
        description="Python versions to test",
    )
    linters: List[str] = Field(
        default_factory=lambda: ["ruff", "mypy"],
        description="Linters to run",
    )
    fail_fast: bool = Field(
        False,
        description="Whether to fail fast in matrix builds",
    )
    artifact_retention_days: int = Field(
        7,
        ge=1,
        le=90,
        description="Days to retain build artifacts",
    )

    @field_validator("python_versions")
    @classmethod
    def validate_python_versions(cls, v: List[str]) -> List[str]:
        """Validate Python version strings."""
        for version in v:
            if not version or not version[0].isdigit():
                raise ValueError(f"Invalid Python version: {version}")
        return v


class LabelSyncConfig(WorkflowConfig):
    """Configuration for label synchronization workflows."""

    main_branch: str = Field(
        "main",
        pattern=r'^[a-zA-Z0-9._/-]+$',
        description="Main branch to trigger sync",
    )
    dry_run: bool = Field(
        False,
        description="Run in dry-run mode (no changes)",
    )


class PyPIPublishConfig(WorkflowConfig):
    """Configuration for PyPI publishing workflows."""

    package_name: str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9._-]+$',
        description="Package name for PyPI",
    )
    environment: str = Field(
        "release",
        description="GitHub environment for deployment protection",
    )
    use_trusted_publishing: bool = Field(
        True,
        description="Use PyPI trusted publishing (recommended)",
    )
    test_pypi: bool = Field(
        False,
        description="Publish to Test PyPI",
    )


def validate_template_context(context: Dict[str, Any]) -> None:
    """
    Validate template context dictionary.

    Performs security checks on context values to prevent injection attacks.

    Args:
        context: Template context to validate

    Raises:
        ValueError: If context contains invalid or dangerous values
    """
    # Check for required fields
    required_fields = {"gitea_url", "gitea_owner", "gitea_repo"}
    missing = required_fields - set(context.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Validate no null bytes (common injection vector)
    for key, value in context.items():
        if isinstance(value, str) and "\0" in value:
            raise ValueError(f"Null byte detected in field '{key}'")

    # Validate no excessively long values (DoS prevention)
    MAX_VALUE_LENGTH = 10000
    for key, value in context.items():
        if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
            raise ValueError(
                f"Value for '{key}' exceeds maximum length "
                f"({len(value)} > {MAX_VALUE_LENGTH})"
            )

    # Recursively check nested structures
    def check_nested(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                check_nested(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                check_nested(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            if "\0" in obj:
                raise ValueError(f"Null byte in nested value at {path}")

    check_nested(context)
```

### 5.2 JSON Schema for External Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Workflow Template Variables Schema",
  "description": "Validation schema for workflow template context variables",
  "type": "object",
  "required": ["gitea_url", "gitea_owner", "gitea_repo"],
  "properties": {
    "gitea_url": {
      "type": "string",
      "format": "uri",
      "pattern": "^https?://",
      "description": "Gitea instance URL"
    },
    "gitea_owner": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "pattern": "^[a-zA-Z0-9._-]+$",
      "description": "Repository owner"
    },
    "gitea_repo": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "pattern": "^[a-zA-Z0-9._-]+$",
      "description": "Repository name"
    },
    "workflow_name": {
      "type": "string",
      "maxLength": 100,
      "description": "Custom workflow name"
    },
    "runner": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9._-]+$",
      "default": "ubuntu-latest"
    },
    "python_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$",
      "default": "3.11"
    },
    "trigger_branches": {
      "type": "array",
      "items": {
        "type": "string",
        "maxLength": 255
      },
      "minItems": 1,
      "default": ["main"]
    },
    "labels_file": {
      "type": "string",
      "default": ".github/labels.yaml"
    },
    "package_name": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9._-]+$"
    }
  },
  "additionalProperties": true
}
```

## 6. Template Testing Strategy

### 6.1 Unit Tests for Security Filters

```python
# tests/templates/test_security.py
"""
Security tests for template rendering system.

Tests validate that injection attacks are prevented and that
security filters work correctly.
"""
import pytest
from jinja2 import TemplateSyntaxError, UndefinedError

from repo_agent.rendering.engine import SecureTemplateEngine
from repo_agent.rendering.filters import (
    safe_url,
    safe_identifier,
    safe_label,
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
        template_file.write_text("""
name: {{ name }}
command: {{ command }}
""")

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

        context = {"value": "test\0injection"}

        with pytest.raises(ValueError, match="Null byte"):
            engine.render("test.yaml.j2", context, validate=True)
```

### 6.2 Integration Tests for Workflow Generation

```python
# tests/templates/test_rendering.py
"""
Integration tests for workflow template rendering.

Tests validate that workflows are correctly generated from templates
and that all expected fields are present and valid.
"""
import pytest
import yaml

from repo_agent.rendering import WorkflowRenderer
from repo_agent.rendering.validators import (
    WorkflowConfig,
    CIBuildConfig,
    LabelSyncConfig,
)


class TestWorkflowRendering:
    """Test end-to-end workflow rendering."""

    @pytest.fixture
    def renderer(self):
        """Create workflow renderer."""
        return WorkflowRenderer()

    def test_render_ci_build_workflow(self, renderer, tmp_path):
        """Test rendering CI build workflow."""
        config = CIBuildConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="test-org",
            gitea_repo="test-repo",
            python_versions=["3.11", "3.12"],
            linters=["ruff", "mypy"],
        )

        output_file = tmp_path / "build.yaml"
        rendered = renderer.render_workflow("ci/build", config, output_file)

        # Validate YAML structure
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Build and Test"
        assert "push" in workflow["on"]
        assert "pull_request" in workflow["on"]
        assert "jobs" in workflow
        assert "build" in workflow["jobs"]

        # Validate environment variables
        assert workflow["env"]["GITEA_URL"] == "https://gitea.example.com"
        assert workflow["env"]["GITEA_OWNER"] == "test-org"
        assert workflow["env"]["GITEA_REPO"] == "test-repo"

        # Validate matrix
        matrix = workflow["jobs"]["build"]["strategy"]["matrix"]
        assert "3.11" in matrix["python-version"]
        assert "3.12" in matrix["python-version"]

        # Validate file was written
        assert output_file.exists()
        assert output_file.read_text() == rendered

    def test_render_label_sync_workflow(self, renderer):
        """Test rendering label sync workflow."""
        config = LabelSyncConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="test-org",
            gitea_repo="test-repo",
            dry_run=True,
        )

        rendered = renderer.render_workflow("automation/label-sync", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Sync Repository Labels"
        assert "sync-labels" in workflow["jobs"]

        # Check dry-run flag is present
        steps = workflow["jobs"]["sync-labels"]["steps"]
        sync_step = next(s for s in steps if "Sync labels" in s["name"])
        assert "--dry-run" in sync_step["run"]

    def test_render_all_workflows(self, renderer, tmp_path):
        """Test rendering multiple workflows at once."""
        configs = {
            "ci/build": CIBuildConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="org",
                gitea_repo="repo",
            ),
            "automation/label-sync": LabelSyncConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="org",
                gitea_repo="repo",
            ),
        }

        results = renderer.render_all_workflows(configs, tmp_path)

        assert len(results) == 2
        assert all(path.exists() for path in results.values())

        # Validate each workflow is valid YAML
        for path in results.values():
            workflow = yaml.safe_load(path.read_text())
            assert "name" in workflow
            assert "jobs" in workflow

    def test_list_available_templates(self, renderer):
        """Test listing available templates."""
        templates = renderer.list_available_templates()

        # Should find templates in package
        assert len(templates) > 0

        # Should have clean names (no .yaml.j2 or workflows/ prefix)
        assert all(".j2" not in t for t in templates)
        assert all("workflows/" not in t for t in templates)


class TestValidationIntegration:
    """Test validation integration with rendering."""

    def test_invalid_url_rejected(self):
        """Test that invalid URLs are rejected during validation."""
        with pytest.raises(ValueError):
            WorkflowConfig(
                gitea_url="not-a-url",
                gitea_owner="owner",
                gitea_repo="repo",
            )

    def test_invalid_identifier_rejected(self):
        """Test that invalid identifiers are rejected."""
        with pytest.raises(ValueError):
            WorkflowConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner/with/slashes",
                gitea_repo="repo",
            )

    def test_extra_fields_allowed(self):
        """Test that template-specific fields are allowed."""
        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            custom_field="custom_value",
            another_field=123,
        )

        assert config.model_dump()["custom_field"] == "custom_value"
        assert config.model_dump()["another_field"] == 123
```

### 6.3 Snapshot Testing for Templates

```python
# tests/templates/test_snapshots.py
"""
Snapshot tests for template output.

These tests capture the expected output of templates and detect
unintended changes.
"""
import pytest
from pathlib import Path

from repo_agent.rendering import WorkflowRenderer
from repo_agent.rendering.validators import CIBuildConfig


@pytest.fixture
def snapshot_dir(tmp_path):
    """Create directory for snapshots."""
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    return snapshots


def test_ci_build_snapshot(snapshot_dir):
    """Snapshot test for CI build workflow."""
    renderer = WorkflowRenderer()
    config = CIBuildConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="test-org",
        gitea_repo="test-repo",
        python_versions=["3.11", "3.12"],
        linters=["ruff", "mypy"],
    )

    rendered = renderer.render_workflow("ci/build", config)

    snapshot_file = snapshot_dir / "ci-build.yaml"

    if snapshot_file.exists():
        # Compare with existing snapshot
        expected = snapshot_file.read_text()
        assert rendered == expected, "Template output changed unexpectedly"
    else:
        # Create new snapshot
        snapshot_file.write_text(rendered)
        pytest.skip("Created new snapshot")
```

## 7. Security Hardening

### 7.1 Security Checklist

- [x] **Sandboxed Environment**: Use `SandboxedEnvironment` to prevent code execution
- [x] **Strict Undefined**: Use `StrictUndefined` to catch missing variables
- [x] **Input Validation**: Validate all context variables with Pydantic
- [x] **Path Validation**: Prevent directory traversal attacks
- [x] **Custom Filters**: Use security filters for all user input
- [x] **No Autoescaping**: YAML doesn't need HTML escaping (validated differently)
- [x] **Length Limits**: Enforce maximum lengths on all string inputs
- [x] **Character Whitelisting**: Allow only safe characters in identifiers
- [x] **Null Byte Detection**: Reject strings containing null bytes
- [x] **URL Scheme Validation**: Only allow http/https schemes
- [x] **No Extensions**: Disable Jinja2 extensions unless explicitly needed
- [x] **Version Pinning**: Pin Jinja2 version to prevent security regressions

### 7.2 Security Testing

```python
# src/repo_agent/rendering/security.py
"""
Security utilities for template rendering.

This module provides additional security checks and utilities
beyond Jinja2's built-in sandboxing.
"""
import re
from typing import Any, Dict
import secrets


# Dangerous YAML patterns that could enable injection
DANGEROUS_YAML_PATTERNS = [
    r'!!python/',  # Python object deserialization
    r'!!map',      # Arbitrary map construction
    r'!!omap',     # Ordered map construction
    r'!!pairs',    # Pairs construction
    r'!!set',      # Set construction
    r'!!binary',   # Binary data
    r'!!timestamp', # Timestamp objects
    r'&\w+',       # Anchors (can enable resource exhaustion)
    r'\*\w+',      # Aliases (can enable billion laughs attack)
]


def check_rendered_output(rendered: str) -> None:
    """
    Check rendered output for dangerous patterns.

    This is a defense-in-depth measure to catch injection attempts
    that might bypass input validation.

    Args:
        rendered: Rendered template output

    Raises:
        ValueError: If dangerous patterns are detected
    """
    for pattern in DANGEROUS_YAML_PATTERNS:
        if re.search(pattern, rendered):
            raise ValueError(
                f"Dangerous YAML pattern detected in output: {pattern}"
            )


def generate_safe_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Useful for generating workflow secrets or identifiers.

    Args:
        length: Length of token in bytes

    Returns:
        Hex-encoded random token
    """
    return secrets.token_hex(length)


def sanitize_log_output(text: str, max_length: int = 1000) -> str:
    """
    Sanitize text for safe logging.

    Prevents log injection and truncates long output.

    Args:
        text: Text to sanitize
        max_length: Maximum length for output

    Returns:
        Sanitized text
    """
    # Remove control characters except newline/tab
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... (truncated)"

    return sanitized


class SecurityAudit:
    """
    Security audit logger for template rendering.

    Tracks suspicious activity and potential security issues.
    """

    def __init__(self):
        self.events: list[Dict[str, Any]] = []

    def log_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        context: Dict[str, Any],
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of event (e.g., "injection_attempt")
            severity: Severity level (low, medium, high, critical)
            message: Human-readable message
            context: Additional context
        """
        self.events.append({
            "type": event_type,
            "severity": severity,
            "message": sanitize_log_output(message),
            "context": context,
        })

    def get_events(self, min_severity: str = "low") -> list[Dict[str, Any]]:
        """
        Get logged events above a minimum severity.

        Args:
            min_severity: Minimum severity to include

        Returns:
            List of matching events
        """
        severity_order = ["low", "medium", "high", "critical"]
        min_index = severity_order.index(min_severity)

        return [
            event for event in self.events
            if severity_order.index(event["severity"]) >= min_index
        ]
```

### 7.3 Runtime Security Monitoring

```python
# tests/templates/test_security_monitoring.py
"""
Tests for runtime security monitoring.
"""
import pytest

from repo_agent.rendering.security import (
    check_rendered_output,
    SecurityAudit,
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
```

## 8. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
1. Create directory structure
2. Implement `SecureTemplateEngine` with sandboxing
3. Implement custom security filters
4. Write unit tests for filters
5. Create Pydantic validation models

### Phase 2: Template Development (Week 2)
1. Create base template with macros
2. Implement 13+ workflow templates:
   - CI: build, test, lint
   - Release: PyPI publish, GitHub release, tag management
   - Automation: label sync, PR labels, issue labels, stale issues
   - Docs: build docs, deploy docs
3. Write template documentation

### Phase 3: Rendering Engine (Week 3)
1. Implement `WorkflowRenderer` high-level API
2. Add template discovery and listing
3. Implement batch rendering
4. Write integration tests
5. Create snapshot tests

### Phase 4: Security Hardening (Week 4)
1. Implement runtime security checks
2. Add security audit logging
3. Perform security review and penetration testing
4. Document security best practices
5. Create security guidelines for template authors

### Phase 5: Testing and Documentation (Week 5)
1. Achieve 100% test coverage
2. Write comprehensive documentation
3. Create example workflows and tutorials
4. Perform load testing for performance
5. Final security audit

## 9. Usage Examples

### 9.1 Basic Usage

```python
from repo_agent.rendering import render_workflow

# Quick rendering with defaults
workflow = render_workflow(
    "ci/build",
    gitea_url="https://gitea.example.com",
    gitea_owner="my-org",
    gitea_repo="my-repo",
)

print(workflow)
```

### 9.2 Advanced Configuration

```python
from pathlib import Path
from repo_agent.rendering import WorkflowRenderer
from repo_agent.rendering.validators import CIBuildConfig

# Create renderer
renderer = WorkflowRenderer()

# Configure workflow with full options
config = CIBuildConfig(
    gitea_url="https://gitea.example.com",
    gitea_owner="my-org",
    gitea_repo="my-repo",
    workflow_name="Custom Build Pipeline",
    python_versions=["3.11", "3.12", "3.13"],
    linters=["ruff", "mypy", "pylint"],
    fail_fast=True,
    artifact_retention_days=30,
)

# Render to file
output_path = Path(".gitea/workflows/build.yaml")
renderer.render_workflow("ci/build", config, output_path)
```

### 9.3 Batch Generation

```python
from pathlib import Path
from repo_agent.rendering import WorkflowRenderer
from repo_agent.rendering.validators import (
    CIBuildConfig,
    LabelSyncConfig,
    PyPIPublishConfig,
)

renderer = WorkflowRenderer()

# Configure all workflows
configs = {
    "ci/build": CIBuildConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
    ),
    "automation/label-sync": LabelSyncConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
    ),
    "release/pypi-publish": PyPIPublishConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
        package_name="my-package",
    ),
}

# Render all workflows
output_dir = Path(".gitea/workflows")
results = renderer.render_all_workflows(configs, output_dir)

for template, output_file in results.items():
    print(f"Generated {template} -> {output_file}")
```

## 10. Security Best Practices for Template Authors

### 10.1 Template Writing Guidelines

1. **Always use security filters**: Apply `safe_*` filters to all user inputs
2. **Use macros for common patterns**: Avoid duplication and ensure consistency
3. **Validate in templates**: Use Jinja2 tests to validate assumptions
4. **Avoid dynamic template loading**: Never load templates based on user input
5. **Document required variables**: Use comments to specify expected context
6. **Test edge cases**: Write tests for empty values, special characters, etc.

### 10.2 Example Secure Template Pattern

```yaml
{# Good: Using security filters #}
name: {{ workflow_name | safe_label }}
on:
  push:
    branches:
      {% for branch in branches -%}
      - {{ branch | safe_identifier }}
      {% endfor %}

{# Bad: No filtering #}
name: {{ workflow_name }}
on:
  push:
    branches:
      {% for branch in branches -%}
      - {{ branch }}
      {% endfor %}
```

## 11. Monitoring and Maintenance

### 11.1 Security Updates

- Monitor Jinja2 security advisories
- Pin Jinja2 version in dependencies
- Regular security audits (quarterly)
- Automated dependency scanning (Dependabot/Renovate)

### 11.2 Template Versioning

- Version templates using semver
- Maintain changelog for template changes
- Support migration paths for breaking changes
- Deprecate templates gracefully

## 12. References

- **Jinja2 Documentation**: https://jinja.palletsprojects.com/
- **Jinja2 Sandbox**: https://jinja.palletsprojects.com/en/3.1.x/sandbox/
- **Pydantic**: https://docs.pydantic.dev/
- **YAML Specification**: https://yaml.org/spec/1.2/spec.html
- **OWASP Injection Prevention**: https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html
- **Python Security Best Practices**: https://python.readthedocs.io/en/stable/library/security_warnings.html

## Appendix A: Complete Template Inventory

| Category | Template Name | Purpose |
|----------|---------------|---------|
| CI | `ci/build.yaml.j2` | Build and test Python package |
| CI | `ci/test.yaml.j2` | Run test suite with coverage |
| CI | `ci/lint.yaml.j2` | Run linters (ruff, mypy) |
| Release | `release/pypi-publish.yaml.j2` | Publish to PyPI |
| Release | `release/github-release.yaml.j2` | Create GitHub release |
| Release | `release/tag-management.yaml.j2` | Manage Git tags |
| Automation | `automation/label-sync.yaml.j2` | Sync repository labels |
| Automation | `automation/pr-labels.yaml.j2` | Auto-label pull requests |
| Automation | `automation/issue-labels.yaml.j2` | Auto-label issues |
| Automation | `automation/stale-issues.yaml.j2` | Mark stale issues |
| Docs | `docs/build-docs.yaml.j2` | Build documentation |
| Docs | `docs/deploy-docs.yaml.j2` | Deploy documentation |

## Appendix B: Security Threat Model

### Identified Threats

1. **Template Injection**: Malicious code in template variables
   - **Mitigation**: Sandboxed environment + input validation

2. **Directory Traversal**: Access to files outside template directory
   - **Mitigation**: Path validation in `validate_template_path()`

3. **YAML Injection**: Malicious YAML constructs in output
   - **Mitigation**: Output validation + character whitelisting

4. **DoS via Anchors**: Billion laughs attack with YAML anchors
   - **Mitigation**: Output pattern detection + rendering timeouts

5. **Secret Exposure**: Accidental inclusion of secrets in templates
   - **Mitigation**: Template review + secret scanning

6. **Dependency Vulnerabilities**: Security issues in Jinja2
   - **Mitigation**: Version pinning + automated scanning

---

**Document Status**: Ready for Implementation
**Next Steps**: Begin Phase 1 implementation of core infrastructure
