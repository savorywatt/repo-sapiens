"""
Tests for Pydantic validation models.
"""

import pytest
from pydantic import ValidationError

from automation.rendering.validators import (
    CIBuildConfig,
    PyPIPublishConfig,
    WorkflowConfig,
    validate_template_context,
)


class TestWorkflowConfig:
    """Test base WorkflowConfig validation."""

    def test_valid_config(self):
        """Test valid configuration is accepted."""
        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="test-org",
            gitea_repo="test-repo",
        )
        assert config.gitea_owner == "test-org"
        assert config.gitea_repo == "test-repo"

    def test_invalid_url_scheme(self):
        """Test invalid URL scheme is rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(
                gitea_url="ftp://gitea.example.com",
                gitea_owner="owner",
                gitea_repo="repo",
            )

    def test_invalid_owner_characters(self):
        """Test invalid owner characters are rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner/with/slashes",
                gitea_repo="repo",
            )

    def test_empty_owner_rejected(self):
        """Test empty owner is rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="",
                gitea_repo="repo",
            )

    def test_branch_validation(self):
        """Test branch name validation."""
        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            trigger_branches=["main", "develop", "feature/test"],
        )
        assert len(config.trigger_branches) == 3

    def test_invalid_branch_characters(self):
        """Test invalid branch characters are rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner",
                gitea_repo="repo",
                trigger_branches=["main\nmalicious"],
            )


class TestCIBuildConfig:
    """Test CI build configuration."""

    def test_valid_ci_config(self):
        """Test valid CI configuration."""
        config = CIBuildConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            python_versions=["3.11", "3.12", "3.13"],
            linters=["ruff", "mypy", "pylint"],
        )
        assert len(config.python_versions) == 3
        assert len(config.linters) == 3

    def test_invalid_python_version(self):
        """Test invalid Python version is rejected."""
        with pytest.raises(ValidationError):
            CIBuildConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner",
                gitea_repo="repo",
                python_versions=["invalid"],
            )

    def test_artifact_retention_validation(self):
        """Test artifact retention days validation."""
        # Valid retention
        config = CIBuildConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            artifact_retention_days=30,
        )
        assert config.artifact_retention_days == 30

        # Invalid retention (too high)
        with pytest.raises(ValidationError):
            CIBuildConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner",
                gitea_repo="repo",
                artifact_retention_days=100,
            )


class TestPyPIPublishConfig:
    """Test PyPI publishing configuration."""

    def test_valid_pypi_config(self):
        """Test valid PyPI configuration."""
        config = PyPIPublishConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            package_name="my-package",
        )
        assert config.package_name == "my-package"

    def test_package_name_required(self):
        """Test package name is required."""
        with pytest.raises(ValidationError):
            PyPIPublishConfig(
                gitea_url="https://gitea.example.com",
                gitea_owner="owner",
                gitea_repo="repo",
            )


class TestTemplateContextValidation:
    """Test template context validation function."""

    def test_valid_context(self):
        """Test valid context passes validation."""
        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo",
            "workflow_name": "Test Workflow",
        }
        # Should not raise
        validate_template_context(context)

    def test_missing_required_fields(self):
        """Test missing required fields are detected."""
        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            # Missing gitea_repo
        }
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_template_context(context)

    def test_null_byte_detection(self):
        """Test null bytes are detected."""
        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo\0malicious",
        }
        with pytest.raises(ValueError, match="Null byte"):
            validate_template_context(context)

    def test_nested_null_byte_detection(self):
        """Test null bytes in nested structures are detected."""
        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo",
            "nested": {
                "value": "test\0injection",
            },
        }
        with pytest.raises(ValueError, match="Null byte"):
            validate_template_context(context)

    def test_excessive_length_rejected(self):
        """Test excessively long values are rejected."""
        context = {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "owner",
            "gitea_repo": "repo",
            "long_value": "a" * 10001,
        }
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_template_context(context)
