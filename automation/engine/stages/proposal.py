"""Proposal stage - creates plan proposal issue for user review."""

from pathlib import Path
import structlog

from automation.engine.stages.base import WorkflowStage
from automation.models.domain import Issue

log = structlog.get_logger(__name__)


class ProposalStage(WorkflowStage):
    """Create plan proposal for user review.

    This stage:
    1. Generates plan using AI
    2. Creates proposal issue with `proposed` label
    3. Comments on original issue with link to proposal
    4. Waits for user approval
    """

    async def execute(self, issue: Issue) -> None:
        """Execute proposal stage.

        Args:
            issue: Original issue requesting planning
        """
        log.info("proposal_stage_start", issue=issue.number)

        # Notify user
        await self.git.add_comment(
            issue.number,
            "📋 **Generating Plan Proposal**\n\n"
            "I'm analyzing your requirements and creating a development plan.\n"
            "I'll post a proposal issue for your review shortly.\n\n"
            "🤖 Posted by Builder Automation"
        )

        try:
            # Generate plan using agent
            plan = await self.agent.generate_plan(issue)
            log.info("plan_generated", plan_id=plan.id)

            # Ensure file_path is set
            if not plan.file_path:
                plan.file_path = f"plans/{issue.number}-{issue.title.lower().replace(' ', '-')}.md"

            # Format plan as markdown
            plan_content = self._format_plan_markdown(plan, issue)

            # TODO: Fix Gitea file commit API - currently returns 422
            # For now, skip committing plan file - it's in the proposal issue body anyway
            # plan_path = str(self.settings.plans_dir / Path(plan.file_path).name)
            # await self.git.commit_file(
            #     path=plan_path,
            #     content=plan_content,
            #     message=f"Add plan proposal for issue #{issue.number}: {issue.title}",
            #     branch=self.settings.repository.default_branch,
            # )
            plan_path = plan.file_path

            # Create proposal issue
            proposal_title = f"[PROPOSAL] Plan for #{issue.number}: {issue.title}"
            proposal_body = self._format_proposal_body(plan, issue, plan_path)

            proposal_issue = await self.git.create_issue(
                title=proposal_title,
                body=proposal_body,
                labels=["proposed", f"plan-for-{issue.number}"],
            )

            log.info("proposal_created", proposal=proposal_issue.number)

            # Comment on original issue
            await self.git.add_comment(
                issue.number,
                f"✅ **Plan Proposal Created**\n\n"
                f"I've created a development plan proposal: [#{proposal_issue.number}]({proposal_issue.url})\n\n"
                f"**Blocked by**: #{proposal_issue.number}\n\n"
                f"**Next Steps:**\n"
                f"1. Review the proposed plan at [#{proposal_issue.number}]({proposal_issue.url})\n"
                f"2. Comment `ok` on the proposal to approve\n"
                f"3. I'll then create a project and task issues for execution\n\n"
                f"🤖 Posted by Builder Automation"
            )

            # Update labels on original issue
            updated_labels = [l for l in issue.labels if l != self.settings.tags.needs_planning]
            updated_labels.append("awaiting-approval")

            await self.git.update_issue(
                issue.number,
                labels=updated_labels,
            )

            log.info("proposal_stage_complete", issue=issue.number, proposal=proposal_issue.number)

        except Exception as e:
            log.error("proposal_stage_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Plan Generation Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"🤖 Posted by Builder Automation"
            )
            raise

    def _format_plan_markdown(self, plan, issue: Issue) -> str:
        """Format plan as markdown file."""
        lines = [
            f"# Plan: {plan.title}",
            "",
            f"**Issue**: #{issue.number}",
            f"**Created**: {plan.created_at.isoformat() if hasattr(plan, 'created_at') else 'now'}",
            "",
            "## Overview",
            "",
            plan.description,
            "",
        ]

        if plan.tasks:
            lines.extend([
                "## Tasks",
                "",
            ])
            for i, task in enumerate(plan.tasks, 1):
                lines.extend([
                    f"### Task {i}: {task.title}",
                    "",
                    f"**ID**: {task.id}",
                    f"**Dependencies**: {', '.join(task.dependencies) if task.dependencies else 'None'}",
                    "",
                    task.description,
                    "",
                ])

        return "\n".join(lines)

    def _format_proposal_body(self, plan, issue: Issue, plan_path: str) -> str:
        """Format proposal issue body."""
        lines = [
            f"# Development Plan Proposal",
            "",
            f"**Original Issue**: [#{issue.number}]({issue.url}) - {issue.title}",
            f"**Plan File**: `{plan_path}`",
            "",
            f"**Blocks**: #{issue.number}",
            "",
            "---",
            "",
            "## Plan Overview",
            "",
            plan.description,
            "",
        ]

        if plan.tasks:
            lines.extend([
                "## Proposed Tasks",
                "",
            ])
            for i, task in enumerate(plan.tasks, 1):
                deps = f" (requires: {', '.join(task.dependencies)})" if task.dependencies else ""
                lines.extend([
                    f"### {i}. {task.title}{deps}",
                    "",
                    task.description,
                    "",
                ])

        lines.extend([
            "---",
            "",
            "## Approval",
            "",
            "**To approve this plan:**",
            "- Comment `ok`, `approve`, or `lgtm` on this issue",
            "",
            "**Once approved, I will:**",
            "1. Create a project board for tracking",
            "2. Create individual task issues for each step",
            "3. Link all tasks to the original issue",
            "4. Wait for you to mark tasks as `execute` when ready",
            "",
            "🤖 Posted by Builder Automation",
        ])

        return "\n".join(lines)
