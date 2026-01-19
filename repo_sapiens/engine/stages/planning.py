"""
Planning stage implementation.

This module implements the planning stage of the workflow, which generates
a development plan from an issue and creates a review issue for approval.
This is typically one of the first stages in the workflow after an issue
is labeled for automation.

Workflow Integration:
    The planning stage is triggered by the ``needs-planning`` label (or its
    configured equivalent). Upon completion, it:
    1. Generates a plan file in the repository
    2. Creates a review issue for human approval
    3. Updates labels to move to the plan review stage

    Label Flow: needs-planning -> plan-review

Plan Generation:
    The AI agent analyzes the issue and generates a structured plan containing:
    - Description of the overall approach
    - List of discrete tasks with dependencies
    - Estimated effort and complexity

Plan Storage:
    Plans are stored as markdown files in the configured plans directory
    (typically ``plans/``). The file is committed directly to the default
    branch.

Review Process:
    A separate review issue is created with a checklist for human reviewers.
    This allows stakeholders to approve, request changes, or reject the plan
    before implementation begins.

Example:
    An issue titled "Add user authentication" with label "needs-planning"
    will result in:
    1. A plan file: ``plans/issue-42-add-user-authentication.md``
    2. A review issue: "Plan Review: Add user authentication"
    3. Label change: needs-planning -> plan-review
"""

from pathlib import Path

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Plan

log = structlog.get_logger(__name__)


class PlanningStage(WorkflowStage):
    """Generate a development plan from an issue using AI.

    This stage takes an issue that has been marked for automation and
    generates a comprehensive development plan. The plan is saved to the
    repository and a review issue is created for human approval.

    Execution Flow:
        1. Notify user that planning has started (comment on issue)
        2. Use AI agent to generate a structured plan
        3. Format plan as markdown and commit to repository
        4. Create a review issue with approval checklist
        5. Add comment to original issue linking to plan and review
        6. Update issue labels for next stage
        7. Persist completion to state manager

    Plan Contents:
        The generated plan includes:
        - Title and description
        - List of tasks with descriptions
        - Dependencies between tasks
        - Created timestamp

    Review Issue:
        The review issue includes:
        - Link to original issue
        - Link to plan file
        - Summary of the plan
        - Approval checklist
        - Instructions for approval/rejection

    Attributes:
        Inherited from WorkflowStage: git, agent, state, settings

    Example:
        >>> stage = PlanningStage(git, agent, state, settings)
        >>> await stage.execute(issue)  # Creates plan and review issue
    """

    async def execute(self, issue: Issue) -> None:
        """Generate a development plan for the given issue.

        Orchestrates the complete plan generation workflow from AI generation
        to file commit to review issue creation.

        Args:
            issue: The issue to generate a plan for. Should have the
                ``needs-planning`` label (or configured equivalent).

        Raises:
            Exception: If any step fails. The error is handled via
                ``_handle_stage_error()`` before being re-raised.

        Side Effects:
            - Adds "starting" comment to the issue
            - Generates a plan file and commits it to the repository
            - Creates a review issue with approval checklist
            - Adds comment to original issue with plan location
            - Updates issue labels (removes needs-planning, adds plan-review)
            - Persists stage completion to state manager

        Example:
            >>> await stage.execute(issue)
            >>> # Plan file created at plans/issue-42-add-feature.md
            >>> # Review issue created: "Plan Review: Add Feature"
        """
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
            await self._handle_stage_error(issue, e)
            raise

    def _format_plan(self, plan: Plan, issue: Issue) -> str:
        """Convert a Plan object to markdown format for storage.

        Creates a well-structured markdown document from the plan data,
        including metadata, description, and all tasks with their
        dependencies.

        Args:
            plan: The Plan object to format. Contains title, description,
                tasks, and timestamps.
            issue: The original issue that spawned this plan. Used to
                add the issue reference to the document.

        Returns:
            A markdown-formatted string suitable for saving to a file.
            Includes headers, metadata, description, and task list.

        Example:
            >>> markdown = self._format_plan(plan, issue)
            >>> markdown.startswith("# ")  # Has title header
            True
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
        """Create the body text for the plan review issue.

        Generates a structured review issue that includes links to the
        original issue and plan file, a summary of the plan, a review
        checklist, and instructions for approval or rejection.

        Args:
            issue: The original issue that spawned the plan. Used for
                title and number references.
            plan: The generated plan. Used for description summary.
            plan_path: The repository path to the plan file. Displayed
                as a clickable link in the review issue.

        Returns:
            Markdown-formatted text for the review issue body. Includes
            headers, links, checklist, and action instructions.

        Note:
            The description is truncated to 500 characters with ellipsis
            to keep the review issue concise.
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
