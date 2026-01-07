"""Plan review stage - Generate prompts from approved plan."""

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Task

log = structlog.get_logger(__name__)


class PlanReviewStage(WorkflowStage):
    """Review plan and generate prompt issues for implementation."""

    async def execute(self, issue: Issue) -> None:
        """Execute plan review stage.

        Extracts plan information, generates prompts for each task,
        and creates implementation issues.

        Args:
            issue: Issue tagged with plan-review
        """
        log.info("plan_review_stage_started", issue=issue.number)

        try:
            # 1. Extract plan_id from issue body
            plan_id = self._extract_plan_id(issue.body)
            if not plan_id:
                raise ValueError("Could not extract plan_id from issue")

            # 2. Read plan file from repository
            plan_path = self._extract_plan_path(issue.body)
            if not plan_path:
                raise ValueError("Could not extract plan_path from issue")

            log.info("reading_plan", path=plan_path)
            await self.git.get_file(
                path=plan_path,
                ref=self.settings.repository.default_branch,
            )

            # 3. Create Plan object for generating prompts
            from repo_sapiens.models.domain import Plan

            plan = Plan(
                id=plan_id,
                title=issue.title.replace("[Plan Review] ", ""),
                description="",
                tasks=[],
                file_path=plan_path,
            )

            # 4. Generate prompts from plan
            log.info("generating_prompts", plan_id=plan_id)
            tasks = await self.agent.generate_prompts(plan)

            # 5. Create implementation issue for each task
            created_issues = []
            for task in tasks:
                issue_title = f"[Implement] {task.title}"
                issue_body = self._create_task_issue_body(task, plan_id, plan_path)

                task_issue = await self.git.create_issue(
                    title=issue_title,
                    body=issue_body,
                    labels=[self.settings.tags.ready_to_implement],
                )

                # Store task issue ID in task
                task.prompt_issue_id = task_issue.number
                created_issues.append(task_issue.number)

                log.info("created_task_issue", task_id=task.id, issue=task_issue.number)

            # 6. Update state with task dependencies
            async with self.state.transaction(plan_id) as state:
                for task in tasks:
                    state["tasks"][task.id] = {
                        "status": "pending",
                        "issue_number": task.prompt_issue_id,
                        "dependencies": task.dependencies,
                    }

            # 7. Close plan review issue
            await self.git.update_issue(issue.number, state="closed")

            # 8. Update state
            await self.state.mark_stage_complete(
                plan_id,
                "plan_review",
                {
                    "tasks_created": len(tasks),
                    "task_issues": created_issues,
                },
            )

            log.info("plan_review_stage_completed", plan_id=plan_id, tasks=len(tasks))

        except Exception as e:
            log.error("plan_review_stage_failed", error=str(e))
            await self._handle_stage_error(issue, e)
            raise

    def _extract_plan_id(self, issue_body: str) -> str:
        """Extract plan ID from issue body."""
        import re

        match = re.search(r"Original Issue.*#(\d+)", issue_body)
        return match.group(1) if match else ""

    def _extract_plan_path(self, issue_body: str) -> str:
        """Extract plan path from issue body."""
        import re

        match = re.search(r"Plan File.*`([^`]+)`", issue_body)
        return match.group(1) if match else ""

    def _create_task_issue_body(self, task: "Task", plan_id: str, plan_path: str) -> str:
        """Create task implementation issue body."""
        body = f"""This task is part of plan #{plan_id}.

## Task Details

**Task ID:** {task.id}
**Plan:** `{plan_path}`

## Description

{task.description}

"""

        if task.dependencies:
            body += """
## Dependencies

This task depends on the following tasks being completed:
"""
            for dep_id in task.dependencies:
                body += f"- {dep_id}\n"

        body += """
## Implementation

This task will be automatically implemented by the automation system.
Progress will be tracked in this issue.
"""

        return body
