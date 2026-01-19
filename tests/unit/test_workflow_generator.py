"""Tests for repo_sapiens/generators/workflow_generator.py.

Tests cover:
- WorkflowGenerator initialization
- Label workflow generation for Gitea/GitHub/GitLab (thin wrapper approach)
- Schedule workflow generation
- Wrapper workflow structure verification
"""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from repo_sapiens.generators.workflow_generator import (
    DISPATCHER_REF,
    GITLAB_COMPONENT_REF,
    WorkflowGenerator,
)


class MockAutomationConfig:
    """Mock automation configuration for testing."""

    def __init__(
        self,
        label_triggers: dict | None = None,
        schedule_triggers: list | None = None,
    ):
        self.label_triggers = label_triggers or {}
        self.schedule_triggers = schedule_triggers or []
        self.mode = MagicMock()
        self.mode.native_enabled = True


class MockGitProviderConfig:
    """Mock git provider configuration."""

    def __init__(self, provider_type: str = "gitea"):
        self.provider_type = provider_type


class MockLabelTriggerConfig:
    """Mock label trigger configuration."""

    def __init__(
        self,
        label_pattern: str,
        handler: str,
        ai_enabled: bool = True,
        remove_on_complete: bool = True,
        success_label: str | None = None,
        failure_label: str | None = "needs-attention",
    ):
        self.label_pattern = label_pattern
        self.handler = handler
        self.ai_enabled = ai_enabled
        self.remove_on_complete = remove_on_complete
        self.success_label = success_label
        self.failure_label = failure_label


class MockScheduleTriggerConfig:
    """Mock schedule trigger configuration."""

    def __init__(
        self,
        cron: str,
        handler: str,
        task_prompt: str | None = None,
        ai_enabled: bool = True,
    ):
        self.cron = cron
        self.handler = handler
        self.task_prompt = task_prompt
        self.ai_enabled = ai_enabled


class MockSettings:
    """Mock AutomationSettings for testing."""

    def __init__(
        self,
        provider_type: str = "gitea",
        label_triggers: dict | None = None,
        schedule_triggers: list | None = None,
    ):
        self.git_provider = MockGitProviderConfig(provider_type)
        self.automation = MockAutomationConfig(label_triggers, schedule_triggers)


class TestWorkflowGeneratorInit:
    """Test WorkflowGenerator initialization."""

    def test_init_with_gitea_provider(self, tmp_path: Path):
        """Test initialization with Gitea provider."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        assert generator.provider == "gitea"
        assert generator.output_dir == tmp_path

    def test_init_with_github_provider(self, tmp_path: Path):
        """Test initialization with GitHub provider."""
        settings = MockSettings(provider_type="github")
        generator = WorkflowGenerator(settings, tmp_path)

        assert generator.provider == "github"

    def test_init_with_gitlab_provider(self, tmp_path: Path):
        """Test initialization with GitLab provider."""
        settings = MockSettings(provider_type="gitlab")
        generator = WorkflowGenerator(settings, tmp_path)

        assert generator.provider == "gitlab"


class TestGenerateAll:
    """Test generate_all method."""

    def test_generate_all_with_label_triggers(self, tmp_path: Path):
        """Test generate_all creates label workflow when triggers exist."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={
                "needs-planning": MockLabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                ),
            },
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generated = generator.generate_all()

        assert len(generated) == 1
        assert generated[0].name == "sapiens.yaml"

    def test_generate_all_with_no_triggers(self, tmp_path: Path):
        """Test generate_all returns empty list when no triggers."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        generated = generator.generate_all()

        assert generated == []

    def test_generate_all_with_schedule_triggers(self, tmp_path: Path):
        """Test generate_all creates schedule workflows."""
        settings = MockSettings(
            provider_type="github",
            schedule_triggers=[
                MockScheduleTriggerConfig(
                    cron="0 8 * * 1-5",
                    handler="daily_triage",
                    task_prompt="Triage issues",
                ),
            ],
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generated = generator.generate_all()

        assert len(generated) == 1
        assert "schedule" in generated[0].name

    def test_generate_all_with_both_trigger_types(self, tmp_path: Path):
        """Test generate_all creates both label and schedule workflows."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={
                "needs-planning": MockLabelTriggerConfig(
                    label_pattern="needs-planning",
                    handler="proposal",
                ),
            },
            schedule_triggers=[
                MockScheduleTriggerConfig(
                    cron="0 8 * * *",
                    handler="daily_check",
                ),
            ],
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generated = generator.generate_all()

        assert len(generated) == 2


class TestGiteaLabelWorkflow:
    """Test Gitea Actions label workflow generation (thin wrapper)."""

    def test_generates_gitea_workflow_directory(self, tmp_path: Path):
        """Test that .gitea/workflows directory is created."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generator.generate_label_workflow()

        assert (tmp_path / ".gitea" / "workflows").exists()

    def test_generates_sapiens_yaml(self, tmp_path: Path):
        """Test that sapiens.yaml is created (not nested in sapiens/ subdirectory)."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".gitea" / "workflows" / "sapiens.yaml"
        assert path.exists()

    def test_workflow_has_correct_name(self, tmp_path: Path):
        """Test workflow has correct name field."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            content = f.read()
            workflow = yaml.safe_load(content)

        assert workflow["name"] == "Sapiens Automation"

    def test_workflow_triggers_on_issues_labeled(self, tmp_path: Path):
        """Test workflow triggers on issues.labeled event."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "issues" in workflow["on"]
        assert "labeled" in workflow["on"]["issues"]["types"]

    def test_workflow_triggers_on_pull_request_labeled(self, tmp_path: Path):
        """Test workflow triggers on pull_request.labeled event."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "pull_request" in workflow["on"]
        assert "labeled" in workflow["on"]["pull_request"]["types"]

    def test_workflow_passes_gitea_specific_inputs(self, tmp_path: Path):
        """Test Gitea wrapper passes git_provider_type and git_provider_url inputs."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        inputs = workflow["jobs"]["sapiens"]["with"]
        assert inputs["git_provider_type"] == "gitea"
        assert "server_url" in inputs["git_provider_url"]


class TestGitHubLabelWorkflow:
    """Test GitHub Actions label workflow generation (thin wrapper)."""

    def test_generates_github_workflow_directory(self, tmp_path: Path):
        """Test that .github/workflows directory is created."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generator.generate_label_workflow()

        assert (tmp_path / ".github" / "workflows").exists()

    def test_generates_sapiens_yaml_for_github(self, tmp_path: Path):
        """Test that sapiens.yaml is created in .github/workflows (not nested)."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".github" / "workflows" / "sapiens.yaml"

    def test_workflow_references_dispatcher(self, tmp_path: Path):
        """Test GitHub workflow references the sapiens-dispatcher workflow."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert workflow["jobs"]["sapiens"]["uses"] == DISPATCHER_REF

    def test_workflow_passes_secrets(self, tmp_path: Path):
        """Test GitHub workflow passes GIT_TOKEN and AI_API_KEY secrets."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        secrets = workflow["jobs"]["sapiens"]["secrets"]
        assert "GIT_TOKEN" in secrets
        assert "SAPIENS_GITHUB_TOKEN" in secrets["GIT_TOKEN"]
        assert "AI_API_KEY" in secrets
        assert "SAPIENS_AI_API_KEY" in secrets["AI_API_KEY"]


class TestGitLabLabelWorkflow:
    """Test GitLab CI label workflow generation (CI/CD component include)."""

    def test_generates_gitlab_ci_yml(self, tmp_path: Path):
        """Test that .gitlab-ci.yml is created with include syntax."""
        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".gitlab-ci.yml"
        assert path.exists()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        # Should have include section with component
        assert "include" in workflow
        assert len(workflow["include"]) == 1
        assert "component" in workflow["include"][0]
        assert workflow["include"][0]["component"] == GITLAB_COMPONENT_REF

    def test_gitlab_ci_has_inputs(self, tmp_path: Path):
        """Test GitLab CI include has inputs block."""
        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        inputs = workflow["include"][0]["inputs"]
        assert inputs["label"] == "$SAPIENS_LABEL"
        assert inputs["issue_number"] == "$SAPIENS_ISSUE"
        assert inputs["event_type"] == "issues.labeled"

    def test_gitlab_ci_merges_with_existing(self, tmp_path: Path):
        """Test GitLab CI merges with existing .gitlab-ci.yml."""
        # Create existing gitlab-ci.yml
        existing_content = {
            "stages": ["build", "test"],
            "build-job": {
                "stage": "build",
                "script": ["echo build"],
            },
        }
        existing_file = tmp_path / ".gitlab-ci.yml"
        with open(existing_file, "w") as f:
            yaml.dump(existing_content, f)

        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        # Should have both existing jobs and new include
        assert "build-job" in workflow
        assert "include" in workflow
        # Verify component is in includes
        component_included = any(
            inc.get("component", "").startswith("gitlab.com/savorywatt/repo-sapiens")
            for inc in workflow["include"]
            if isinstance(inc, dict)
        )
        assert component_included


class TestWrapperWorkflowStructure:
    """Test wrapper workflow structure for GitHub/Gitea."""

    def test_wrapper_has_uses_directive(self, tmp_path: Path):
        """Test wrapper has 'uses:' key in job."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "uses" in workflow["jobs"]["sapiens"]

    def test_wrapper_passes_required_inputs(self, tmp_path: Path):
        """Test wrapper passes label, issue_number, and event_type inputs."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        inputs = workflow["jobs"]["sapiens"]["with"]
        assert "label" in inputs
        assert "github.event.label.name" in inputs["label"]
        assert "issue_number" in inputs
        assert "github.event.issue.number" in inputs["issue_number"]
        assert "event_type" in inputs

    def test_wrapper_passes_secrets(self, tmp_path: Path):
        """Test wrapper passes GIT_TOKEN and AI_API_KEY secrets."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        secrets = workflow["jobs"]["sapiens"]["secrets"]
        assert "GIT_TOKEN" in secrets
        assert "AI_API_KEY" in secrets

    def test_wrapper_passes_gitea_specific_inputs(self, tmp_path: Path):
        """Test Gitea wrapper includes git_provider_type and git_provider_url."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        inputs = workflow["jobs"]["sapiens"]["with"]
        assert inputs["git_provider_type"] == "gitea"
        assert "git_provider_url" in inputs

    def test_wrapper_references_correct_dispatcher(self, tmp_path: Path):
        """Test wrapper uses: value matches expected dispatcher reference."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert workflow["jobs"]["sapiens"]["uses"] == DISPATCHER_REF

    def test_github_wrapper_uses_github_secrets(self, tmp_path: Path):
        """Test GitHub wrapper uses SAPIENS_GITHUB_TOKEN for GIT_TOKEN."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        secrets = workflow["jobs"]["sapiens"]["secrets"]
        assert "SAPIENS_GITHUB_TOKEN" in secrets["GIT_TOKEN"]

    def test_gitea_wrapper_uses_gitea_secrets(self, tmp_path: Path):
        """Test Gitea wrapper uses SAPIENS_GITEA_TOKEN for GIT_TOKEN."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        secrets = workflow["jobs"]["sapiens"]["secrets"]
        assert "SAPIENS_GITEA_TOKEN" in secrets["GIT_TOKEN"]


class TestScheduleWorkflow:
    """Test schedule workflow generation."""

    def test_generates_schedule_workflow_file(self, tmp_path: Path):
        """Test schedule workflow file is generated."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * *",
            handler="daily_check",
        )

        path = generator.generate_schedule_workflow(schedule)

        assert path is not None
        assert path.exists()
        assert path.name == "schedule-daily_check.yaml"

    def test_schedule_workflow_has_cron_trigger(self, tmp_path: Path):
        """Test schedule workflow has cron schedule trigger."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * 1-5",
            handler="weekday_task",
        )

        path = generator.generate_schedule_workflow(schedule)

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "schedule" in workflow["on"]
        assert workflow["on"]["schedule"][0]["cron"] == "0 8 * * 1-5"

    def test_schedule_workflow_has_workflow_dispatch(self, tmp_path: Path):
        """Test schedule workflow includes workflow_dispatch for manual runs."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 0 * * *",
            handler="nightly",
        )

        path = generator.generate_schedule_workflow(schedule)

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "workflow_dispatch" in workflow["on"]

    def test_schedule_workflow_uses_task_prompt(self, tmp_path: Path):
        """Test schedule workflow uses task_prompt in run command."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * *",
            handler="triage",
            task_prompt="Triage all open issues",
        )

        path = generator.generate_schedule_workflow(schedule)

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        run_cmd = workflow["jobs"]["run"]["steps"][-1]["run"]
        assert "Triage all open issues" in run_cmd

    def test_schedule_workflow_uses_handler_when_no_prompt(self, tmp_path: Path):
        """Test schedule workflow uses handler name when no task_prompt."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * *",
            handler="daily_check",
            task_prompt=None,
        )

        path = generator.generate_schedule_workflow(schedule)

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        run_cmd = workflow["jobs"]["run"]["steps"][-1]["run"]
        assert "daily_check" in run_cmd

    def test_gitlab_schedule_returns_none(self, tmp_path: Path):
        """Test GitLab schedule returns None (schedules configured in UI)."""
        settings = MockSettings(provider_type="gitlab")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * *",
            handler="task",
        )

        path = generator.generate_schedule_workflow(schedule)

        assert path is None

    def test_schedule_filename_sanitizes_handler(self, tmp_path: Path):
        """Test schedule filename sanitizes handler with slashes."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 8 * * *",
            handler="category/subcategory",
        )

        path = generator.generate_schedule_workflow(schedule)

        assert path.name == "schedule-category-subcategory.yaml"

    def test_github_schedule_workflow_directory(self, tmp_path: Path):
        """Test GitHub schedule workflow goes to .github/workflows."""
        settings = MockSettings(provider_type="github")
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(
            cron="0 0 * * *",
            handler="nightly",
        )

        path = generator.generate_schedule_workflow(schedule)

        assert ".github" in str(path)


class TestWorkflowContent:
    """Test generated workflow content details."""

    def test_workflow_runs_on_ubuntu(self, tmp_path: Path):
        """Test schedule workflow runs on ubuntu-latest."""
        settings = MockSettings(
            provider_type="gitea",
            schedule_triggers=[
                MockScheduleTriggerConfig(cron="0 8 * * *", handler="test"),
            ],
        )
        generator = WorkflowGenerator(settings, tmp_path)
        schedule = MockScheduleTriggerConfig(cron="0 8 * * *", handler="test")

        path = generator.generate_schedule_workflow(schedule)

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert workflow["jobs"]["run"]["runs-on"] == "ubuntu-latest"

    def test_workflow_file_has_header_comment(self, tmp_path: Path):
        """Test generated workflow file has header comment."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            content = f.read()

        assert "Generated by repo-sapiens" in content
