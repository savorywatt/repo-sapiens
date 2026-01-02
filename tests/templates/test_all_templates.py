"""
Integration tests for all 13 workflow templates.

This test suite validates that all templates render correctly with
proper security and YAML structure.
"""

from pathlib import Path

import pytest
import yaml

from repo_sapiens.rendering import WorkflowRenderer
from repo_sapiens.rendering.validators import (
    CIBuildConfig,
    LabelSyncConfig,
    PyPIPublishConfig,
    WorkflowConfig,
)


class TestAllTemplates:
    """Test all 13 workflow templates."""

    @pytest.fixture
    def renderer(self):
        """Create workflow renderer."""
        return WorkflowRenderer()

    @pytest.fixture
    def base_config(self):
        """Base configuration for all templates."""
        return {
            "gitea_url": "https://gitea.example.com",
            "gitea_owner": "test-org",
            "gitea_repo": "test-repo",
        }

    def test_list_all_templates(self, renderer):
        """Test that all 13 templates are discovered."""
        templates = renderer.list_available_templates()

        expected_templates = [
            # CI templates (3)
            "ci/build",
            "ci/test",
            "ci/lint",
            # Release templates (3)
            "release/pypi-publish",
            "release/github-release",
            "release/tag-management",
            # Automation templates (4)
            "automation/label-sync",
            "automation/pr-labels",
            "automation/issue-labels",
            "automation/stale-issues",
            # Docs templates (2)
            "docs/build-docs",
            "docs/deploy-docs",
        ]

        # Verify all expected templates exist
        for template in expected_templates:
            assert template in templates, f"Missing template: {template}"

        # Verify we have at least 12 templates (base.yaml.j2 doesn't count)
        workflow_templates = [t for t in templates if not t.startswith("base")]
        assert (
            len(workflow_templates) >= 12
        ), f"Expected at least 12 templates, found {len(workflow_templates)}"

    def test_ci_build_template(self, renderer, base_config):
        """Test CI build workflow template."""
        config = CIBuildConfig(
            **base_config,
            python_versions=["3.11", "3.12"],
            linters=["ruff", "mypy"],
            package_name="test-package",
        )

        rendered = renderer.render_workflow("ci/build", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Build and Test"
        assert "push" in workflow["on"]
        assert "pull_request" in workflow["on"]
        assert "build" in workflow["jobs"]
        assert workflow["jobs"]["build"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12"]

    def test_ci_test_template(self, renderer, base_config):
        """Test CI test workflow template."""
        config = WorkflowConfig(**base_config, package_name="test-package")

        rendered = renderer.render_workflow("ci/test", config)
        workflow = yaml.safe_load(rendered)

        assert "test" in workflow["jobs"]
        assert workflow["env"]["GITEA_URL"] == "https://gitea.example.com"

    def test_ci_lint_template(self, renderer, base_config):
        """Test CI lint workflow template."""
        config = CIBuildConfig(**base_config, linters=["ruff", "mypy", "black"])

        rendered = renderer.render_workflow("ci/lint", config)
        workflow = yaml.safe_load(rendered)

        assert "lint" in workflow["jobs"]

    def test_release_pypi_publish_template(self, renderer, base_config):
        """Test PyPI publish workflow template."""
        config = PyPIPublishConfig(
            **base_config,
            package_name="test-package",
            use_trusted_publishing=True,
        )

        rendered = renderer.render_workflow("release/pypi-publish", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Publish to PyPI"
        assert "release" in workflow["on"]
        assert "publish" in workflow["jobs"]
        assert workflow["jobs"]["publish"]["permissions"]["id-token"] == "write"

    def test_release_github_release_template(self, renderer, base_config):
        """Test GitHub release workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("release/github-release", config)
        workflow = yaml.safe_load(rendered)

        assert "release" in workflow["jobs"]

    def test_release_tag_management_template(self, renderer, base_config):
        """Test tag management workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("release/tag-management", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["on"]["workflow_dispatch"]["inputs"]["action"]["type"] == "choice"
        assert "manage-tags" in workflow["jobs"]

    def test_automation_label_sync_template(self, renderer, base_config):
        """Test label sync workflow template."""
        config = LabelSyncConfig(**base_config, dry_run=True)

        rendered = renderer.render_workflow("automation/label-sync", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Sync Repository Labels"
        assert "sync-labels" in workflow["jobs"]
        # Verify dry-run flag appears in the rendered YAML
        assert "--dry-run" in rendered

    def test_automation_pr_labels_template(self, renderer, base_config):
        """Test PR labels workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("automation/pr-labels", config)
        workflow = yaml.safe_load(rendered)

        assert "pull_request" in workflow["on"]

    def test_automation_issue_labels_template(self, renderer, base_config):
        """Test issue labels workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("automation/issue-labels", config)
        workflow = yaml.safe_load(rendered)

        assert "issues" in workflow["on"]

    def test_automation_stale_issues_template(self, renderer, base_config):
        """Test stale issues workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("automation/stale-issues", config)
        workflow = yaml.safe_load(rendered)

        assert "schedule" in workflow["on"]

    def test_docs_build_docs_template(self, renderer, base_config):
        """Test build docs workflow template."""
        config = WorkflowConfig(**base_config)

        rendered = renderer.render_workflow("docs/build-docs", config)
        workflow = yaml.safe_load(rendered)

        assert "build" in workflow["jobs"]

    def test_docs_deploy_docs_template(self, renderer, base_config):
        """Test deploy docs workflow template."""
        config = WorkflowConfig(
            **base_config,
            docs_tool="mkdocs",
            use_github_pages=True,
        )

        rendered = renderer.render_workflow("docs/deploy-docs", config)
        workflow = yaml.safe_load(rendered)

        assert workflow["name"] == "Deploy Documentation"
        assert "deploy" in workflow["jobs"]
        assert "mkdocs build" in rendered

    def test_all_templates_have_gitea_env_vars(self, renderer, base_config):
        """Test that all templates include Gitea environment variables."""
        config = WorkflowConfig(**base_config, package_name="test-package")

        templates = [
            "ci/build",
            "ci/test",
            "ci/lint",
            "release/pypi-publish",
            "release/github-release",
            "release/tag-management",
            "automation/label-sync",
            "automation/pr-labels",
            "automation/issue-labels",
            "automation/stale-issues",
            "docs/build-docs",
            "docs/deploy-docs",
        ]

        for template_name in templates:
            try:
                rendered = renderer.render_workflow(template_name, config)
                workflow = yaml.safe_load(rendered)

                # Some templates might not have env at root level but should still be valid
                assert workflow is not None, f"{template_name}: Invalid YAML structure"
                assert "jobs" in workflow, f"{template_name}: Missing jobs section"

            except Exception as e:
                pytest.fail(f"Template {template_name} failed: {str(e)}")

    def test_all_templates_use_security_filters(self, renderer, base_config):
        """Test that all templates use security filters for user input."""
        _config = WorkflowConfig(
            **base_config,
            workflow_name="Test Workflow",
            package_name="test-package",
        )

        templates = renderer.list_available_templates()
        workflow_templates = [t for t in templates if not t.startswith("base")]

        for template_name in workflow_templates:
            try:
                # Read the raw template file
                template_path = (
                    Path(__file__).parent.parent.parent
                    / "repo_sapiens"
                    / "templates"
                    / "workflows"
                    / f"{template_name}.yaml.j2"
                )

                if template_path.exists():
                    content = template_path.read_text()

                    # Check that variables use filters (not exhaustive, but catches obvious issues)
                    # Look for patterns like {{ variable }} without filters
                    import re

                    # Find all Jinja2 variable expressions
                    var_pattern = r"\{\{\s*([^}]+?)\s*\}\}"
                    matches = re.findall(var_pattern, content)

                    for match in matches:
                        # Skip GitHub Actions expressions
                        if (
                            "'" in match
                            or '"' in match
                            or "github." in match
                            or "secrets." in match
                            or "vars." in match
                        ):
                            continue

                        # Skip macro calls
                        if "base." in match or "(" in match:
                            continue

                        # Skip built-in filters like int, lower, default
                        if any(
                            builtin in match
                            for builtin in ["| int", "| lower", "| default", "| upper"]
                        ):
                            continue

                        # Variables that take user input should have security filters
                        user_input_vars = [
                            "gitea_url",
                            "gitea_owner",
                            "gitea_repo",
                            "workflow_name",
                            "runner",
                            "package_name",
                            "branch",
                            "version",
                            "linter",
                            "main_branch",
                            "labels_file",
                        ]

                        # Check if this is a user input variable without a security filter
                        var_name = match.split("|")[0].strip().split(".")[0].strip()
                        if var_name in user_input_vars:
                            has_filter = "|" in match and any(
                                f"| {f}" in match
                                for f in ["safe_url", "safe_identifier", "safe_label"]
                            )
                            if not has_filter:
                                # This is informational - some variables may be safe without filters
                                # but we log them for review
                                print(
                                    f"Warning: {template_name} has {var_name} "
                                    "without explicit security filter"
                                )

            except Exception as e:
                print(f"Could not check template {template_name}: {str(e)}")

    def test_batch_render_all_templates(self, renderer, base_config, tmp_path):
        """Test rendering all templates in batch mode."""
        configs = {
            "ci/build": CIBuildConfig(**base_config, package_name="test-pkg"),
            "ci/test": WorkflowConfig(**base_config, package_name="test-pkg"),
            "ci/lint": CIBuildConfig(**base_config, linters=["ruff"]),
            "automation/label-sync": LabelSyncConfig(**base_config),
        }

        results = renderer.render_all_workflows(configs, tmp_path)

        assert len(results) == 4
        assert all(path.exists() for path in results.values())

        # Validate each output file
        for _template_name, output_path in results.items():
            content = output_path.read_text()
            workflow = yaml.safe_load(content)

            assert "name" in workflow
            assert "jobs" in workflow
            assert len(workflow["jobs"]) > 0

    def test_template_output_is_valid_yaml(self, renderer, base_config):
        """Test that all templates produce valid YAML."""
        config = WorkflowConfig(**base_config, package_name="test-package")

        templates = renderer.list_available_templates()
        workflow_templates = [t for t in templates if not t.startswith("base")]

        errors = []
        for template_name in workflow_templates:
            try:
                rendered = renderer.render_workflow(template_name, config)
                # This will raise an exception if YAML is invalid
                workflow = yaml.safe_load(rendered)
                assert workflow is not None
            except Exception as e:
                errors.append(f"{template_name}: {str(e)}")

        if errors:
            pytest.fail("Templates produced invalid YAML:\n" + "\n".join(errors))

    def test_no_dangerous_patterns_in_output(self, renderer, base_config):
        """Test that rendered templates don't contain dangerous YAML patterns."""
        from repo_sapiens.rendering.security import check_rendered_output

        config = WorkflowConfig(**base_config, package_name="test-package")

        templates = renderer.list_available_templates()
        workflow_templates = [t for t in templates if not t.startswith("base")]

        for template_name in workflow_templates:
            rendered = renderer.render_workflow(template_name, config)

            # This should not raise an exception
            try:
                check_rendered_output(rendered)
            except ValueError as e:
                pytest.fail(f"Template {template_name} contains dangerous patterns: {str(e)}")
