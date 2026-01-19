"""
Integration tests for workflow template rendering.

Tests validate that workflows are correctly generated from templates
and that all expected fields are present and valid.
"""

import pytest
import yaml

from repo_sapiens.rendering import WorkflowRenderer
from repo_sapiens.rendering.validators import (
    CIBuildConfig,
    LabelSyncConfig,
    WorkflowConfig,
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
            package_name="test-package",
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
                package_name="test-package",
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
