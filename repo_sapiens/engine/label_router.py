"""
Label-based routing to workflow stages.

Maps labels to handlers and invokes the appropriate workflow stage.
"""

from typing import Any

import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import LabelTriggerConfig
from repo_sapiens.engine.event_classifier import ClassifiedEvent
from repo_sapiens.engine.orchestrator import WorkflowOrchestrator
from repo_sapiens.models.domain import Issue
from repo_sapiens.providers.base import GitProvider

log = structlog.get_logger(__name__)


# Handler name to stage name mapping
HANDLER_STAGE_MAP = {
    # New granular workflow stages
    "proposal": "proposal",
    "approval": "approval",
    "task_execution": "task_execution",
    "pr_review": "pr_review",
    "pr_fix": "pr_fix",
    "fix_execution": "fix_execution",
    "qa": "qa",
    # Legacy stages
    "planning": "planning",
    "plan_review": "plan_review",
    "implementation": "implementation",
    "code_review": "code_review",
    "merge": "merge",
    # Specialized handlers
    "triage": "triage",
    "security_review": "security_review",
    "docs_generation": "docs_generation",
    "test_coverage": "test_coverage",
    "dependency_audit": "dependency_audit",
}


class LabelRouter:
    """Routes label events to appropriate workflow handlers."""

    def __init__(
        self,
        settings: AutomationSettings,
        git: GitProvider,
        orchestrator: WorkflowOrchestrator,
    ):
        """Initialize router.

        Args:
            settings: Automation settings
            git: Git provider instance
            orchestrator: Workflow orchestrator instance
        """
        self.settings = settings
        self.git = git
        self.orchestrator = orchestrator

    async def route(self, event: ClassifiedEvent) -> dict[str, Any]:
        """Route a classified event to its handler.

        Args:
            event: Classified event from EventClassifier

        Returns:
            Result dictionary with execution details
        """
        if not event.should_process:
            return {
                "success": False,
                "skipped": True,
                "reason": event.skip_reason,
            }

        log.info(
            "routing_event",
            handler=event.handler,
            label=event.label,
            issue=event.issue_number,
            pr=event.pr_number,
        )

        try:
            # Get the issue or PR
            if event.issue_number:
                issue = await self.git.get_issue(event.issue_number)
            elif event.pr_number:
                # PRs are often accessible as issues
                issue = await self.git.get_issue(event.pr_number)
            else:
                return {
                    "success": False,
                    "error": "No issue or PR number in event",
                }

            # Execute the handler
            result = await self._execute_handler(
                handler=event.handler,
                config=event.config,
                issue=issue,
                event=event,
            )

            # Post-processing
            if result.get("success") and event.config:
                await self._post_process_success(issue, event.config)
            elif not result.get("success") and event.config:
                await self._post_process_failure(issue, event.config, result.get("error"))

            return result

        except Exception as e:
            log.error(
                "routing_failed",
                handler=event.handler,
                error=str(e),
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_handler(
        self,
        handler: str,
        config: LabelTriggerConfig | None,
        issue: Issue,
        event: ClassifiedEvent,
    ) -> dict[str, Any]:
        """Execute the specified handler.

        Args:
            handler: Handler name
            config: Handler configuration
            issue: Issue to process
            event: Original classified event

        Returns:
            Execution result
        """
        # Map handler to stage
        stage_name = HANDLER_STAGE_MAP.get(handler)

        if stage_name and stage_name in self.orchestrator.stages:
            # Use existing workflow stage
            stage = self.orchestrator.stages[stage_name]
            await stage.execute(issue)
            return {"success": True, "stage": stage_name}

        # Handler is a custom task - use AI agent
        if config and config.ai_enabled:
            return await self._execute_ai_task(handler, issue, config)

        return {
            "success": False,
            "error": f"Unknown handler: {handler}",
        }

    async def _execute_ai_task(
        self,
        handler: str,
        issue: Issue,
        config: LabelTriggerConfig,
    ) -> dict[str, Any]:
        """Execute a handler using the AI agent.

        Args:
            handler: Handler name
            issue: Issue to process
            config: Handler configuration

        Returns:
            Execution result
        """
        # Build task prompt from handler name and issue
        task_prompt = f"""Process issue #{issue.number}: {issue.title}

Handler: {handler}

Issue body:
{issue.body}

Instructions:
Based on the handler type "{handler}", perform the appropriate action on this issue.
"""

        # Use the orchestrator's agent
        from repo_sapiens.models.domain import Task

        task = Task(
            id=f"label-{handler}-{issue.number}",
            prompt_issue_id=issue.number,
            title=f"{handler} for issue #{issue.number}",
            description=task_prompt,
        )

        result = await self.orchestrator.agent.execute_task(
            task,
            {
                "issue": issue,
                "handler": handler,
            },
        )

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "files_changed": result.files_changed,
        }

    async def _post_process_success(
        self,
        issue: Issue,
        config: LabelTriggerConfig,
    ) -> None:
        """Post-process after successful handler execution.

        Args:
            issue: Processed issue
            config: Handler configuration
        """
        labels = list(issue.labels)

        # Remove trigger label if configured
        if config.remove_on_complete and config.label_pattern in labels:
            labels.remove(config.label_pattern)

        # Add success label if configured
        if config.success_label and config.success_label not in labels:
            labels.append(config.success_label)

        # Update issue labels
        if labels != issue.labels:
            await self.git.update_issue(issue.number, labels=labels)

    async def _post_process_failure(
        self,
        issue: Issue,
        config: LabelTriggerConfig,
        error: str | None,
    ) -> None:
        """Post-process after handler failure.

        Args:
            issue: Processed issue
            config: Handler configuration
            error: Error message
        """
        labels = list(issue.labels)

        # Add failure label if configured
        if config.failure_label and config.failure_label not in labels:
            labels.append(config.failure_label)

        # Update issue labels
        if labels != issue.labels:
            await self.git.update_issue(issue.number, labels=labels)

        # Add error comment
        if error:
            await self.git.add_comment(
                issue.number, f"Label handler failed: {error}\n\nLabel: `{config.label_pattern}`"
            )
