"""Tests for repo_sapiens/generators/workflow_generator.py.

Tests cover:
- WorkflowGenerator initialization
- Label workflow generation for Gitea/GitHub/GitLab
- Schedule workflow generation
- Label condition building
- Environment variable block generation
- Run command generation
- GitLab CI merging with existing config
"""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from repo_sapiens.generators.workflow_generator import WorkflowGenerator


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
        assert generated[0].name == "process-label.yaml"

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
    """Test Gitea Actions label workflow generation."""

    def test_generates_gitea_workflow_directory(self, tmp_path: Path):
        """Test that .gitea/workflows directory is created."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generator.generate_label_workflow()

        assert (tmp_path / ".gitea" / "workflows").exists()

    def test_generates_process_label_yaml(self, tmp_path: Path):
        """Test that process-label.yaml is created."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".gitea" / "workflows" / "sapiens" / "process-label.yaml"
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
            # Skip comment lines
            content = f.read()
            workflow = yaml.safe_load(content)

        assert workflow["name"] == "Process Label"

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

    def test_workflow_uses_gitea_env_vars(self, tmp_path: Path):
        """Test Gitea workflow uses gitea-specific environment variables."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        env = workflow["jobs"]["process"]["steps"][-1]["env"]
        assert "GITEA_TOKEN" in env
        assert "gitea.server_url" in env["AUTOMATION__GIT_PROVIDER__BASE_URL"]

    def test_workflow_uses_gitea_event_context(self, tmp_path: Path):
        """Test Gitea workflow uses gitea event context in run command."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        run_cmd = workflow["jobs"]["process"]["steps"][-1]["run"]
        assert "gitea.event.label.name" in run_cmd
        assert "gitea.event.issue.number" in run_cmd


class TestGitHubLabelWorkflow:
    """Test GitHub Actions label workflow generation."""

    def test_generates_github_workflow_directory(self, tmp_path: Path):
        """Test that .github/workflows directory is created."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        generator.generate_label_workflow()

        assert (tmp_path / ".github" / "workflows").exists()

    def test_generates_process_label_yaml_for_github(self, tmp_path: Path):
        """Test that process-label.yaml is created in .github directory."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".github" / "workflows" / "sapiens" / "process-label.yaml"

    def test_workflow_uses_github_env_vars(self, tmp_path: Path):
        """Test GitHub workflow uses github-specific environment variables."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        env = workflow["jobs"]["process"]["steps"][-1]["env"]
        assert "GITHUB_TOKEN" in env
        assert "github.server_url" in env["AUTOMATION__GIT_PROVIDER__BASE_URL"]

    def test_workflow_uses_github_event_context(self, tmp_path: Path):
        """Test GitHub workflow uses github event context."""
        settings = MockSettings(
            provider_type="github",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        run_cmd = workflow["jobs"]["process"]["steps"][-1]["run"]
        assert "github.event.label.name" in run_cmd
        assert "github.event.issue.number" in run_cmd


class TestGitLabLabelWorkflow:
    """Test GitLab CI label workflow generation."""

    def test_generates_gitlab_ci_yml(self, tmp_path: Path):
        """Test that .gitlab-ci.yml is created."""
        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test-label": MockLabelTriggerConfig("test-label", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        assert path == tmp_path / ".gitlab-ci.yml"
        assert path.exists()

    def test_gitlab_ci_has_stages(self, tmp_path: Path):
        """Test GitLab CI has stages section."""
        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "stages" in workflow
        assert "process" in workflow["stages"]

    def test_gitlab_ci_has_process_label_job(self, tmp_path: Path):
        """Test GitLab CI has process-label job."""
        settings = MockSettings(
            provider_type="gitlab",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert "process-label" in workflow

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

        # Should have both existing and new jobs
        assert "build-job" in workflow
        assert "process-label" in workflow
        assert "process" in workflow["stages"]


class TestBuildLabelCondition:
    """Test _build_label_condition method."""

    def test_exact_match_condition(self, tmp_path: Path):
        """Test exact label match condition."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["needs-planning"])

        assert "gitea.event.label.name == 'needs-planning'" in condition

    def test_glob_pattern_condition(self, tmp_path: Path):
        """Test glob pattern uses startsWith."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["sapiens/*"])

        assert "startsWith(gitea.event.label.name, 'sapiens/')" in condition

    def test_multiple_patterns_joined_with_or(self, tmp_path: Path):
        """Test multiple patterns are joined with OR."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["label1", "label2"])

        assert "||" in condition
        assert "label1" in condition
        assert "label2" in condition

    def test_github_uses_github_event_var(self, tmp_path: Path):
        """Test GitHub provider uses github.event.label.name."""
        settings = MockSettings(provider_type="github")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["test"])

        assert "github.event.label.name" in condition

    def test_gitea_uses_gitea_event_var(self, tmp_path: Path):
        """Test Gitea provider uses gitea.event.label.name."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["test"])

        assert "gitea.event.label.name" in condition

    def test_mixed_exact_and_glob_patterns(self, tmp_path: Path):
        """Test mixture of exact and glob patterns."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        condition = generator._build_label_condition(["exact-label", "prefix/*"])

        assert "gitea.event.label.name == 'exact-label'" in condition
        assert "startsWith(gitea.event.label.name, 'prefix/')" in condition


class TestBuildEnvBlock:
    """Test _build_env_block method."""

    def test_gitea_env_block_has_gitea_token(self, tmp_path: Path):
        """Test Gitea env block includes GITEA_TOKEN."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        env = generator._build_env_block()

        assert "GITEA_TOKEN" in env
        assert "SAPIENS_GITEA_TOKEN" in env["GITEA_TOKEN"]

    def test_github_env_block_has_github_token(self, tmp_path: Path):
        """Test GitHub env block includes GITHUB_TOKEN."""
        settings = MockSettings(provider_type="github")
        generator = WorkflowGenerator(settings, tmp_path)

        env = generator._build_env_block()

        assert "GITHUB_TOKEN" in env
        assert "GITHUB_TOKEN" in env["GITHUB_TOKEN"]

    def test_env_block_has_automation_vars(self, tmp_path: Path):
        """Test env block includes AUTOMATION__ prefixed vars."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        env = generator._build_env_block()

        assert "AUTOMATION__GIT_PROVIDER__API_TOKEN" in env
        assert "AUTOMATION__GIT_PROVIDER__BASE_URL" in env
        assert "AUTOMATION__REPOSITORY__OWNER" in env
        assert "AUTOMATION__REPOSITORY__NAME" in env


class TestBuildRunCommand:
    """Test _build_run_command method."""

    def test_gitea_run_command(self, tmp_path: Path):
        """Test Gitea run command format."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        cmd = generator._build_run_command()

        assert "sapiens process-label" in cmd
        assert "--source gitea" in cmd
        assert "gitea.event.label.name" in cmd

    def test_github_run_command(self, tmp_path: Path):
        """Test GitHub run command format."""
        settings = MockSettings(provider_type="github")
        generator = WorkflowGenerator(settings, tmp_path)

        cmd = generator._build_run_command()

        assert "sapiens process-label" in cmd
        assert "--source github" in cmd
        assert "github.event.label.name" in cmd

    def test_run_command_includes_event_type(self, tmp_path: Path):
        """Test run command includes event type flag."""
        settings = MockSettings(provider_type="gitea")
        generator = WorkflowGenerator(settings, tmp_path)

        cmd = generator._build_run_command()

        assert '--event-type "issues.labeled"' in cmd


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

    def test_workflow_has_checkout_step(self, tmp_path: Path):
        """Test workflow includes checkout step."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        steps = workflow["jobs"]["process"]["steps"]
        checkout_step = next(s for s in steps if "Checkout" in s.get("name", ""))
        assert checkout_step["uses"] == "actions/checkout@v4"

    def test_workflow_has_python_setup_step(self, tmp_path: Path):
        """Test workflow includes Python setup step."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        steps = workflow["jobs"]["process"]["steps"]
        python_step = next(s for s in steps if "Python" in s.get("name", ""))
        assert "actions/setup-python" in python_step["uses"]
        assert python_step["with"]["python-version"] == "3.12"

    def test_workflow_has_install_step(self, tmp_path: Path):
        """Test workflow includes repo-sapiens install step."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        steps = workflow["jobs"]["process"]["steps"]
        install_step = next(s for s in steps if "Install" in s.get("name", ""))
        assert "pip install repo-sapiens" in install_step["run"]

    def test_workflow_runs_on_ubuntu(self, tmp_path: Path):
        """Test workflow runs on ubuntu-latest."""
        settings = MockSettings(
            provider_type="gitea",
            label_triggers={"test": MockLabelTriggerConfig("test", "handler")},
        )
        generator = WorkflowGenerator(settings, tmp_path)

        path = generator.generate_label_workflow()

        with open(path) as f:
            workflow = yaml.safe_load(f.read())

        assert workflow["jobs"]["process"]["runs-on"] == "ubuntu-latest"

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
        assert "Do not edit manually" in content
