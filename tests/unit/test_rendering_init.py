"""Tests for repo_sapiens/rendering/__init__.py - WorkflowRenderer and render_workflow."""

from unittest.mock import MagicMock, patch

import pytest

from repo_sapiens.rendering import (
    SecureTemplateEngine,
    WorkflowConfig,
    WorkflowRenderer,
    render_workflow,
)


class TestWorkflowRendererInit:
    """Tests for WorkflowRenderer initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default template directory."""
        renderer = WorkflowRenderer()

        assert renderer.engine is not None
        assert isinstance(renderer.engine, SecureTemplateEngine)

    def test_init_with_custom_template_dir(self, tmp_path):
        """Should initialize with custom template directory."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        renderer = WorkflowRenderer(template_dir=template_dir)

        assert renderer.engine.template_dir == template_dir.resolve()

    def test_init_nonexistent_dir_raises(self, tmp_path):
        """Should raise error for non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError):
            WorkflowRenderer(template_dir=nonexistent)


class TestWorkflowRendererRenderWorkflow:
    """Tests for WorkflowRenderer.render_workflow method."""

    def test_render_workflow_basic(self, tmp_path):
        """Should render a basic workflow template."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        template_file = workflows_dir / "test.yaml.j2"
        template_file.write_text(
            """name: {{ gitea_repo }}
on: push
jobs:
  build:
    runs-on: {{ runner }}
"""
        )

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="my-repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("test", config)

        assert "name: my-repo" in result
        assert "runs-on: ubuntu-latest" in result

    def test_render_workflow_with_output_path(self, tmp_path):
        """Should write rendered workflow to file when output_path provided."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        template_file = workflows_dir / "simple.yaml.j2"
        template_file.write_text("name: {{ gitea_repo }}\n")

        output_dir = tmp_path / "output"
        output_file = output_dir / "workflow.yaml"

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="test-repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("simple", config, output_path=output_file)

        assert output_file.exists()
        assert output_file.read_text() == result
        assert "name: test-repo" in result

    def test_render_workflow_creates_parent_dirs(self, tmp_path):
        """Should create parent directories for output path."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        template_file = workflows_dir / "nested.yaml.j2"
        template_file.write_text("content: true\n")

        deep_output = tmp_path / "a" / "b" / "c" / "workflow.yaml"

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        renderer.render_workflow("nested", config, output_path=deep_output)

        assert deep_output.exists()

    def test_render_workflow_excludes_none_values(self, tmp_path):
        """Should exclude None values from context for default filter."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        template_file = workflows_dir / "defaults.yaml.j2"
        template_file.write_text("name: {{ workflow_name | default('default-name') }}\n")

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            workflow_name=None,  # Should be excluded, allowing default to work
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("defaults", config)

        # Since workflow_name is None and excluded, default filter should apply
        assert "name: default-name" in result

    def test_render_workflow_uses_python_serialization(self, tmp_path):
        """Should use mode='python' for proper type serialization."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        template_file = workflows_dir / "branches.yaml.j2"
        template_file.write_text(
            """branches:
{% for branch in trigger_branches %}
  - {{ branch }}
{% endfor %}
"""
        )

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
            trigger_branches=["main", "develop"],
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("branches", config)

        assert "- main" in result
        assert "- develop" in result


class TestWorkflowRendererRenderAllWorkflows:
    """Tests for WorkflowRenderer.render_all_workflows method."""

    def test_render_all_workflows_basic(self, tmp_path):
        """Should render multiple workflows to output directory."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "build.yaml.j2").write_text("name: build\n")
        (workflows_dir / "test.yaml.j2").write_text("name: test\n")

        output_dir = tmp_path / "output"

        config1 = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )
        config2 = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        results = renderer.render_all_workflows(
            {"build": config1, "test": config2},
            output_dir,
        )

        assert len(results) == 2
        assert "build" in results
        assert "test" in results
        assert results["build"].exists()
        assert results["test"].exists()

    def test_render_all_workflows_creates_output_dir(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "ci.yaml.j2").write_text("name: ci\n")

        output_dir = tmp_path / "new_output_dir"
        assert not output_dir.exists()

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        renderer.render_all_workflows({"ci": config}, output_dir)

        assert output_dir.exists()

    def test_render_all_workflows_sanitizes_filenames(self, tmp_path):
        """Should convert slashes to dashes in output filenames."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        ci_dir = workflows_dir / "ci"
        ci_dir.mkdir(parents=True)

        (ci_dir / "build.yaml.j2").write_text("name: ci-build\n")

        output_dir = tmp_path / "output"

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        results = renderer.render_all_workflows({"ci/build": config}, output_dir)

        assert "ci/build" in results
        assert results["ci/build"].name == "ci-build.yaml"

    def test_render_all_workflows_empty_configs(self, tmp_path):
        """Should handle empty configs dict."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        output_dir = tmp_path / "output"

        renderer = WorkflowRenderer(template_dir=template_dir)
        results = renderer.render_all_workflows({}, output_dir)

        assert results == {}


class TestWorkflowRendererListAvailableTemplates:
    """Tests for WorkflowRenderer.list_available_templates method."""

    def test_list_available_templates_basic(self, tmp_path):
        """Should list available templates."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "build.yaml.j2").write_text("content")
        (workflows_dir / "test.yaml.j2").write_text("content")
        (workflows_dir / "readme.md").write_text("not a template")

        renderer = WorkflowRenderer(template_dir=template_dir)
        templates = renderer.list_available_templates()

        assert "build" in templates
        assert "test" in templates
        assert "readme" not in templates
        assert len(templates) == 2

    def test_list_available_templates_nested(self, tmp_path):
        """Should list nested templates with clean names."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        ci_dir = workflows_dir / "ci"
        ci_dir.mkdir(parents=True)

        (ci_dir / "build.yaml.j2").write_text("content")
        (ci_dir / "test.yaml.j2").write_text("content")

        renderer = WorkflowRenderer(template_dir=template_dir)
        templates = renderer.list_available_templates()

        assert "ci/build" in templates
        assert "ci/test" in templates

    def test_list_available_templates_empty(self, tmp_path):
        """Should return empty list when no templates exist."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        renderer = WorkflowRenderer(template_dir=template_dir)
        templates = renderer.list_available_templates()

        assert templates == []


class TestRenderWorkflowFunction:
    """Tests for the render_workflow convenience function."""

    def test_render_workflow_basic(self, tmp_path):
        """Should render workflow with minimal configuration."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "simple.yaml.j2").write_text(
            """name: {{ gitea_repo }}
owner: {{ gitea_owner }}
url: {{ gitea_url }}
"""
        )

        with patch("repo_sapiens.rendering.WorkflowRenderer") as MockRenderer:
            mock_instance = MagicMock()
            mock_instance.render_workflow.return_value = "rendered content"
            MockRenderer.return_value = mock_instance

            result = render_workflow(
                "simple",
                "https://gitea.example.com",
                "my-owner",
                "my-repo",
            )

            assert result == "rendered content"
            MockRenderer.assert_called_once()
            mock_instance.render_workflow.assert_called_once()

    def test_render_workflow_with_extra_kwargs(self, tmp_path):
        """Should pass extra kwargs to WorkflowConfig."""
        with patch("repo_sapiens.rendering.WorkflowRenderer") as MockRenderer:
            mock_instance = MagicMock()
            mock_instance.render_workflow.return_value = "content"
            MockRenderer.return_value = mock_instance

            render_workflow(
                "template",
                "https://gitea.example.com",
                "owner",
                "repo",
                runner="self-hosted",
                python_version="3.12",
            )

            # Verify the config was created with extra kwargs
            call_args = mock_instance.render_workflow.call_args
            config = call_args[0][1]
            assert config.runner == "self-hosted"
            assert config.python_version == "3.12"


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports_available(self):
        """Should export expected classes and functions."""
        from repo_sapiens import rendering

        assert hasattr(rendering, "SecureTemplateEngine")
        assert hasattr(rendering, "WorkflowRenderer")
        assert hasattr(rendering, "WorkflowConfig")
        assert hasattr(rendering, "render_workflow")

    def test_all_list_complete(self):
        """Should have complete __all__ list."""
        from repo_sapiens.rendering import __all__

        assert "SecureTemplateEngine" in __all__
        assert "WorkflowRenderer" in __all__
        assert "WorkflowConfig" in __all__
        assert "render_workflow" in __all__


class TestWorkflowConfigIntegration:
    """Integration tests for WorkflowConfig with renderer."""

    def test_config_gitea_url_normalized(self, tmp_path):
        """Should normalize gitea_url (remove trailing slash)."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "url.yaml.j2").write_text("url: {{ gitea_url }}\n")

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com/",  # With trailing slash
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("url", config)

        assert "url: https://gitea.example.com" in result
        assert "url: https://gitea.example.com/" not in result

    def test_config_default_values(self, tmp_path):
        """Should use default values from config."""
        template_dir = tmp_path / "templates"
        workflows_dir = template_dir / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "defaults.yaml.j2").write_text(
            """runner: {{ runner }}
python: {{ python_version }}
labels_file: {{ labels_file }}
"""
        )

        config = WorkflowConfig(
            gitea_url="https://gitea.example.com",
            gitea_owner="owner",
            gitea_repo="repo",
        )

        renderer = WorkflowRenderer(template_dir=template_dir)
        result = renderer.render_workflow("defaults", config)

        assert "runner: ubuntu-latest" in result
        assert "python: 3.11" in result
        assert "labels_file: .github/labels.yaml" in result
