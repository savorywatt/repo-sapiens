"""
Generate native CI/CD workflow files from trigger configuration.

Supports Gitea Actions, GitHub Actions, and GitLab CI.
"""

from pathlib import Path
from typing import Any

import structlog
import yaml

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import (
    ScheduleTriggerConfig,
)

log = structlog.get_logger(__name__)

# Dispatcher workflow reference - users call this reusable workflow
DISPATCHER_REF = "savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v2"

# GitLab CI/CD Component reference
GITLAB_COMPONENT_REF = "gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v2"


class WorkflowGenerator:
    """Generates native CI/CD workflow files.

    For label-triggered workflows, generates thin wrappers that call the
    reusable sapiens-dispatcher workflow. This keeps user repositories
    minimal (~20 lines) while the dispatcher handles all the logic.
    """

    def __init__(
        self,
        settings: AutomationSettings,
        output_dir: Path,
    ):
        """Initialize generator.

        Args:
            settings: Automation settings
            output_dir: Root directory for workflow files
        """
        self.settings = settings
        self.automation = settings.automation
        self.provider = settings.git_provider.provider_type
        self.output_dir = output_dir

    def generate_all(self) -> list[Path]:
        """Generate all workflow files.

        Returns:
            List of generated file paths
        """
        generated = []

        # Generate label trigger workflow
        if self.automation.label_triggers:
            path = self.generate_label_workflow()
            if path:
                generated.append(path)

        # Generate schedule workflows
        for schedule in self.automation.schedule_triggers:
            path = self.generate_schedule_workflow(schedule)
            if path:
                generated.append(path)

        return generated

    def generate_label_workflow(self) -> Path | None:
        """Generate the label-triggered workflow.

        Returns:
            Path to generated file or None
        """
        if self.provider == "gitlab":
            return self._generate_gitlab_label_workflow()
        else:
            return self._generate_actions_label_workflow()

    def _get_dispatcher_ref(self) -> str:
        """Get the dispatcher workflow reference.

        Returns:
            Full reference to the reusable dispatcher workflow
        """
        return DISPATCHER_REF

    def _get_gitlab_component_ref(self) -> str:
        """Get the GitLab CI/CD component reference.

        Returns:
            Full reference to the GitLab CI/CD component
        """
        return GITLAB_COMPONENT_REF

    def _generate_actions_label_workflow(self) -> Path:
        """Generate Gitea/GitHub Actions thin wrapper workflow.

        The wrapper calls the reusable sapiens-dispatcher workflow,
        passing event context and secrets.
        """
        # Determine workflow directory
        if self.provider == "github":
            workflow_dir = self.output_dir / ".github" / "workflows"
        else:
            workflow_dir = self.output_dir / ".gitea" / "workflows"

        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Build the with: block for inputs
        inputs: dict[str, str] = {
            "label": "${{ github.event.label.name }}",
            "issue_number": "${{ github.event.issue.number || github.event.pull_request.number }}",
            "event_type": "${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}",
        }

        # Gitea requires provider type and URL
        if self.provider == "gitea":
            inputs["git_provider_type"] = "gitea"
            # Use server_url from context; users can override in their config
            inputs["git_provider_url"] = "${{ github.server_url }}"

        # Build secrets block
        secrets: dict[str, str] = {
            "GIT_TOKEN": "${{ secrets.SAPIENS_GITHUB_TOKEN }}"
            if self.provider == "github"
            else "${{ secrets.SAPIENS_GITEA_TOKEN }}",
            "AI_API_KEY": "${{ secrets.SAPIENS_AI_API_KEY }}",
        }

        # Generate workflow content
        # Note: permissions must be granted by the caller for cross-repo reusable workflows
        workflow = {
            "name": "Sapiens Automation",
            "on": {
                "issues": {"types": ["labeled"]},
                "pull_request": {"types": ["labeled"]},
            },
            "permissions": {
                "contents": "write",
                "issues": "write",
                "pull-requests": "write",
            },
            "jobs": {
                "sapiens": {
                    "uses": self._get_dispatcher_ref(),
                    "with": inputs,
                    "secrets": secrets,
                },
            },
        }

        # Write workflow file
        output_path = workflow_dir / "sapiens.yaml"
        with open(output_path, "w") as f:
            f.write("# Generated by repo-sapiens\n")
            f.write("# Thin wrapper that calls the reusable sapiens-dispatcher workflow\n")
            f.write("# Regenerate with 'sapiens update --workflows'\n\n")
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)

        log.info("generated_workflow", path=str(output_path))
        return output_path

    def _generate_gitlab_label_workflow(self) -> Path:
        """Generate GitLab CI configuration with CI/CD component include.

        GitLab doesn't have native label triggers, so this generates
        a .gitlab-ci.yml that includes the sapiens-dispatcher component.
        Users need to set up a webhook handler to trigger pipelines on
        label events.
        """
        gitlab_ci_path = self.output_dir / ".gitlab-ci.yml"

        # GitLab CI/CD Component include
        workflow: dict[str, Any] = {
            "include": [
                {
                    "component": self._get_gitlab_component_ref(),
                    "inputs": {
                        "label": "$SAPIENS_LABEL",
                        "issue_number": "$SAPIENS_ISSUE",
                        "event_type": "issues.labeled",
                    },
                },
            ],
        }

        # Add comment about webhook handler requirement
        header_comment = """\
# Generated by repo-sapiens
# GitLab CI/CD configuration using sapiens-dispatcher component
#
# NOTE: GitLab doesn't have native label triggers. You need to set up
# a webhook handler to trigger this pipeline with variables:
#   SAPIENS_LABEL=<label-name>
#   SAPIENS_ISSUE=<issue-number>
#
# See docs/GITLAB_SETUP.md for webhook handler setup instructions.
# Regenerate with 'sapiens update --workflows'

"""

        # Merge with existing gitlab-ci.yml if present
        if gitlab_ci_path.exists():
            with open(gitlab_ci_path) as f:
                existing = yaml.safe_load(f) or {}

            # Merge includes
            existing_includes = existing.get("include", [])
            if not isinstance(existing_includes, list):
                existing_includes = [existing_includes]

            # Check if our component is already included
            already_included = any(
                inc.get("component", "").startswith("gitlab.com/savorywatt/repo-sapiens")
                for inc in existing_includes
                if isinstance(inc, dict)
            )

            if not already_included:
                existing_includes.extend(workflow["include"])
                existing["include"] = existing_includes

            workflow = existing

        with open(gitlab_ci_path, "w") as f:
            f.write(header_comment)
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)

        log.info("generated_gitlab_ci", path=str(gitlab_ci_path))
        return gitlab_ci_path

    # -------------------------------------------------------------------------
    # Deprecated methods - kept for backward compatibility with schedule workflows
    # These were used by the old full workflow generation approach.
    # -------------------------------------------------------------------------

    def _build_label_condition(self, patterns: list[str]) -> str:
        """Build the 'if' condition for label matching.

        .. deprecated::
            No longer used for label workflows. The reusable dispatcher
            handles all label routing internally via sapiens process-label.

        Args:
            patterns: List of label patterns to match

        Returns:
            Condition string for workflow
        """
        if self.provider == "github":
            event_var = "github.event.label.name"
        else:
            event_var = "gitea.event.label.name"

        # Build condition for each pattern
        conditions = []
        for pattern in patterns:
            if "*" in pattern:
                # Glob pattern - use startsWith for prefix matching
                prefix = pattern.split("*")[0]
                conditions.append(f"startsWith({event_var}, '{prefix}')")
            else:
                # Exact match
                conditions.append(f"{event_var} == '{pattern}'")

        return " || ".join(conditions)

    def _build_env_block(self) -> dict[str, str]:
        """Build environment variables block.

        .. deprecated::
            No longer used for label workflows. Environment variables
            are now configured in the reusable dispatcher workflow.
            Kept for schedule workflow generation.
        """
        if self.provider == "github":
            # Note: GITHUB_ prefix is reserved for custom secrets, so we use SAPIENS_GITHUB_TOKEN
            return {
                "GITHUB_TOKEN": "${{ secrets.SAPIENS_GITHUB_TOKEN }}",
                "AUTOMATION__GIT_PROVIDER__API_TOKEN": "${{ secrets.SAPIENS_GITHUB_TOKEN }}",
                "AUTOMATION__GIT_PROVIDER__BASE_URL": "${{ github.server_url }}",
                "AUTOMATION__REPOSITORY__OWNER": "${{ github.repository_owner }}",
                "AUTOMATION__REPOSITORY__NAME": "${{ github.event.repository.name }}",
            }
        else:  # gitea
            return {
                "GITEA_TOKEN": "${{ secrets.SAPIENS_GITEA_TOKEN }}",
                "AUTOMATION__GIT_PROVIDER__API_TOKEN": "${{ secrets.SAPIENS_GITEA_TOKEN }}",
                "AUTOMATION__GIT_PROVIDER__BASE_URL": "${{ gitea.server_url }}",
                "AUTOMATION__REPOSITORY__OWNER": "${{ gitea.repository_owner }}",
                "AUTOMATION__REPOSITORY__NAME": "${{ gitea.event.repository.name }}",
            }

    def _build_run_command(self) -> str:
        """Build the sapiens run command.

        .. deprecated::
            No longer used for label workflows. The command is now
            in the reusable dispatcher workflow. Kept for schedule
            workflow generation.
        """
        if self.provider == "github":
            return (
                "sapiens process-label "
                '--event-type "issues.labeled" '
                '--label "${{ github.event.label.name }}" '
                '--issue "${{ github.event.issue.number || github.event.pull_request.number }}" '
                "--source github"
            )
        else:  # gitea
            return (
                "sapiens process-label "
                '--event-type "issues.labeled" '
                '--label "${{ gitea.event.label.name }}" '
                '--issue "${{ gitea.event.issue.number || gitea.event.pull_request.number }}" '
                "--source gitea"
            )

    def generate_schedule_workflow(
        self,
        schedule: ScheduleTriggerConfig,
    ) -> Path | None:
        """Generate a scheduled workflow.

        Args:
            schedule: Schedule configuration

        Returns:
            Path to generated file or None
        """
        # Safe filename from handler name
        filename = f"schedule-{schedule.handler.replace('/', '-')}.yaml"

        if self.provider == "gitlab":
            # GitLab uses pipeline schedules (configured in UI)
            log.warning(
                "gitlab_schedules_manual",
                handler=schedule.handler,
                cron=schedule.cron,
            )
            return None

        # Gitea/GitHub Actions
        if self.provider == "github":
            workflow_dir = self.output_dir / ".github" / "workflows" / "sapiens"
        else:
            workflow_dir = self.output_dir / ".gitea" / "workflows" / "sapiens"

        workflow_dir.mkdir(parents=True, exist_ok=True)

        workflow = {
            "name": f"Scheduled: {schedule.handler}",
            "on": {
                "schedule": [
                    {"cron": schedule.cron},
                ],
                "workflow_dispatch": {},
            },
            "jobs": {
                "run": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {
                            "name": "Checkout repository",
                            "uses": "actions/checkout@v4",
                        },
                        {
                            "name": "Set up Python",
                            "uses": "actions/setup-python@v5",
                            "with": {
                                "python-version": "3.12",
                            },
                        },
                        {
                            "name": "Install repo-sapiens",
                            "run": "pip install repo-sapiens",
                        },
                        {
                            "name": f"Run {schedule.handler}",
                            "env": self._build_env_block(),
                            "run": f'sapiens run "{schedule.task_prompt or schedule.handler}"',
                        },
                    ],
                },
            },
        }

        output_path = workflow_dir / filename
        with open(output_path, "w") as f:
            f.write("# Generated by repo-sapiens\n")
            f.write(f"# Schedule: {schedule.cron}\n\n")
            yaml.dump(workflow, f, default_flow_style=False, sort_keys=False)

        log.info("generated_schedule_workflow", path=str(output_path))
        return output_path
