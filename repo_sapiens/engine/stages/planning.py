"""
Planning stage implementation.

This module implements the planning stage of the workflow, which generates
a development plan from an issue and creates a review issue for approval.
"""

from pathlib import Path

import structlog

from repo_sapiens.engine.context import ExecutionContext
from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Plan

log = structlog.get_logger(__name__)


class PlanningStage(WorkflowStage):
    """Planning stage: Generate development plan from issue.

    This stage:
    1. Generates a plan using the AI agent
    2. Commits the plan file to the repository
    3. Creates a plan review issue
    4. Adds a comment to the original issue
    5. Updates workflow state
    """

    async def execute(self, context: ExecutionContext) -> None:
        """Execute planning stage.

        Args:
            context: Execution context containing the issue and workflow state

        Raises:
            Exception: If plan generation fails
        """
        issue = context.issue
        log.info("planning_stage_start", issue=issue.number, title=issue.title)

        # Notify user that planning has started
        await self.git.add_comment(
            issue.number,
            "🚀 **Builder Starting**\n\nI'm starting to work on this issue. "
            "I'll generate a development plan and post it for review.\n\n"
            "🤖 Posted by Builder Automation",
        )

        try:
            # Generate plan using agent
            plan = await self.agent.generate_plan(issue)
            log.info("plan_generated", plan_id=plan.id)

            # Ensure file_path is set (fallback if agent didn't set it)
            if not plan.file_path:
                plan.file_path = f"plans/{issue.number}-{issue.title.lower().replace(' ', '-')}.md"

            # Format plan as markdown
            plan_content = self._format_plan(plan, issue)

            # Commit plan file to repository
            plan_path = str(self.settings.plans_dir / Path(plan.file_path).name)
            await self.git.commit_file(
                path=plan_path,
                content=plan_content,
                message=f"Add plan for issue #{issue.number}: {issue.title}",
                branch=self.settings.repository.default_branch,
            )
            log.info("plan_committed", path=plan_path)

            # Create plan review issue
            review_body = self._create_review_body(issue, plan, plan_path)
            review_issue = await self.git.create_issue(
                title=f"Plan Review: {issue.title}",
                body=review_body,
                labels=[self.settings.tags.plan_review],
            )
            log.info("review_issue_created", review_issue=review_issue.number)

            # Add comment to original issue
            await self.git.add_comment(
                issue.number,
                f"Development plan created: {plan_path}\n\nReview issue: #{review_issue.number}",
            )

            # Update issue labels
            labels = [label for label in issue.labels if label != self.settings.tags.needs_planning]
            labels.append(self.settings.tags.plan_review)
            await self.git.update_issue(issue.number, labels=labels)

            # Update state
            await self.state.mark_stage_complete(
                plan_id=plan.id,
                stage="planning",
                data={
                    "plan_path": plan_path,
                    "review_issue": review_issue.number,
                },
            )

            log.info("planning_stage_complete", issue=issue.number, plan_id=plan.id)

        except Exception as e:
            log.error("planning_stage_failed", issue=issue.number, error=str(e), exc_info=True)
            await self._handle_stage_error(context, e)
            raise

    def _format_plan(self, plan: Plan, issue: Issue) -> str:
        """Convert Plan object to markdown format.

        Args:
            plan: Plan to format
            issue: Original issue

        Returns:
            Markdown formatted plan
        """
        lines = [
            f"# {plan.title}",
            "",
            f"**Issue:** #{issue.number}",
            f"**Created:** {plan.created_at.isoformat()}",
            "",
            "## Description",
            "",
            plan.description,
            "",
        ]

        if plan.tasks:
            lines.extend(
                [
                    "## Tasks",
                    "",
                ]
            )
            for i, task in enumerate(plan.tasks, 1):
                lines.append(f"### Task {i}: {task.title}")
                lines.append("")
                lines.append(task.description)
                lines.append("")
                if task.dependencies:
                    lines.append(f"**Dependencies:** {', '.join(task.dependencies)}")
                    lines.append("")

        return "\n".join(lines)

    def _create_review_body(self, issue: Issue, plan: Plan, plan_path: str) -> str:
        """Create review issue body.

        Args:
            issue: Original issue
            plan: Generated plan
            plan_path: Path to plan file

        Returns:
            Review issue body text
        """
        return f"""# Plan Review

**Original Issue:** #{issue.number} - {issue.title}
**Plan File:** `{plan_path}`

## Summary

{plan.description[:500]}{"..." if len(plan.description) > 500 else ""}

## Review Checklist

- [ ] Plan addresses all requirements from the original issue
- [ ] Tasks are properly broken down and scoped
- [ ] Dependencies are correctly identified
- [ ] Implementation approach is sound
- [ ] No security or performance concerns

## Actions

- To approve: Close this issue and add label (
    `{self.settings.tags.ready_to_implement}` to #{issue.number}
)
- To request changes: Comment with feedback and add label (
    `{self.settings.tags.needs_attention}` to #{issue.number}
)

---
*This plan was automatically generated by the automation system.*
"""
