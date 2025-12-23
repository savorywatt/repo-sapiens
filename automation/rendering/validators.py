"""
Validation models and functions for template contexts.

Uses Pydantic for strong typing and validation of template variables.
"""

from typing import Any
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class WorkflowConfig(BaseModel):
    """
    Base configuration for all workflow templates.

    This model defines required and common optional fields for workflow
    generation. Template-specific fields should be added as needed.
    """

    # Required fields
    gitea_url: str = Field(
        ...,
        description="URL of Gitea instance (e.g., https://gitea.example.com)",
    )
    gitea_owner: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="Repository owner/organization name",
    )
    gitea_repo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="Repository name",
    )

    # Common optional fields
    workflow_name: str | None = Field(
        None,
        max_length=100,
        description="Custom workflow name",
    )
    runner: str = Field(
        "ubuntu-latest",
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="GitHub Actions runner to use",
    )
    python_version: str = Field(
        "3.11",
        pattern=r"^\d+\.\d+$",
        description="Python version for workflows",
    )

    # Template-specific fields (examples)
    trigger_branches: list[str] = Field(
        default_factory=lambda: ["main"],
        description="Branches that trigger the workflow",
    )
    labels_file: str = Field(
        ".github/labels.yaml",
        description="Path to labels configuration file",
    )
    package_name: str | None = Field(
        None,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="Python package name",
    )

    model_config = {
        "extra": "allow",  # Allow template-specific fields
        "str_strip_whitespace": True,
    }

    @field_validator("trigger_branches")
    @classmethod
    def validate_branches(cls, v: list[str]) -> list[str]:
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
    def validate_gitea_url(cls, v: str) -> str:
        """Ensure Gitea URL uses HTTPS in production."""
        # Validate it's a valid URL
        parsed = urlparse(v)

        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {v}")

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme}")

        # Warn about HTTP (allow for local development)
        if parsed.scheme == "http" and not parsed.netloc.startswith("localhost"):
            import warnings

            warnings.warn(
                f"Using insecure HTTP for Gitea URL: {v}. " "Consider using HTTPS in production.",
                UserWarning,
            )

        # Remove trailing slash for consistency
        return v.rstrip("/")

    @model_validator(mode="after")
    def validate_package_name_if_needed(self) -> "WorkflowConfig":
        """Validate package_name is set for PyPI workflows."""
        # This can be extended to check template-specific requirements
        return self


class CIBuildConfig(WorkflowConfig):
    """Configuration specific to CI build workflows."""

    python_versions: list[str] = Field(
        default_factory=lambda: ["3.11", "3.12"],
        description="Python versions to test",
    )
    linters: list[str] = Field(
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
    def validate_python_versions(cls, v: list[str]) -> list[str]:
        """Validate Python version strings."""
        for version in v:
            if not version or not version[0].isdigit():
                raise ValueError(f"Invalid Python version: {version}")
        return v


class LabelSyncConfig(WorkflowConfig):
    """Configuration for label synchronization workflows."""

    main_branch: str = Field(
        "main",
        pattern=r"^[a-zA-Z0-9._/-]+$",
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
        pattern=r"^[a-zA-Z0-9._-]+$",
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


def validate_template_context(context: dict[str, Any]) -> None:
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
                f"Value for '{key}' exceeds maximum length " f"({len(value)} > {MAX_VALUE_LENGTH})"
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
