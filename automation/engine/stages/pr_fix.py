"""PR fix stage - creates fix proposal from review comments."""

import re
from typing import Optional

import structlog

from automation.engine.stages.base import WorkflowStage
from automation.models.domain import Issue

log = structlog.get_logger(__name__)


class PRFixStage(WorkflowStage):
    """Create fix proposal when PR has 'needs-fix' label.

    This stage:
    1. Detects PRs with 'needs-fix' label
    2. Collects all review comments from the PR
    3. Creates a fix proposal issue
    4. When approved, creates fix tasks
    5. Executes fixes on the same branch
    """

    async def execute(self, issue: Issue) -> None:
        """Execute PR fix proposal creation.

        Args:
            issue: PR issue with 'needs-fix' label
        """
        log.info("pr_fix_start", issue=issue.number)

        # Check if already processed
        if "fix-proposed" in issue.labels:
            log.debug("already_proposed", issue=issue.number)
            return

        log.info("creating_fix_proposal", issue=issue.number)

        try:
            # Get all comments from the issue to find review feedback
            comments = await self.git.get_comments(issue.number)

            # Find the review comment
            review_comment = None
            for comment in comments:
                if "Code Review Complete" in comment.body and "items to address" in comment.body:
                    review_comment = comment
                    break

            if not review_comment:
                log.warning("no_review_comment_found", issue=issue.number)
                await self.git.add_comment(
                    issue.number,
                    f"⚠️ **No Review Feedback Found**\n\n"
                    f"Cannot create fix proposal without review comments.\n"
                    f"Please ensure the PR has been reviewed first.\n\n"
                    f"🤖 Posted by Builder Automation"
                )
                return

            # Extract PR details
            pr_number = issue.number  # Assuming issue number matches PR number
            pr_title = issue.title

            # Get branch from labels
            plan_label = None
            for label in issue.labels:
                if label.startswith("plan-"):
                    plan_label = label
                    break

            if not plan_label:
                log.error("cannot_find_plan_label", issue=issue.number)
                return

            branch_name = f"{plan_label}-implementation"

            # Create fix proposal issue
            fix_issue_title = f"[FIX PROPOSAL] Address review feedback for PR #{pr_number}"
            fix_issue_body = self._format_fix_proposal(
                pr_number,
                pr_title,
                branch_name,
                review_comment.body
            )

            fix_issue = await self.git.create_issue(
                title=fix_issue_title,
                body=fix_issue_body,
                labels=["fix-proposal", plan_label, "awaiting-approval"]
            )

            log.info("fix_proposal_created", fix_issue=fix_issue.number, pr=pr_number)

            # Update PR issue
            await self.git.add_comment(
                issue.number,
                f"🔧 **Fix Proposal Created**\n\n"
                f"Created fix proposal: #{fix_issue.number}\n\n"
                f"Review the proposal and add `approved` label to proceed with fixes.\n\n"
                f"🤖 Posted by Builder Automation"
            )

            # Update labels
            updated_labels = [l for l in issue.labels if l != "needs-fix"]
            updated_labels.append("fix-proposed")
            await self.git.update_issue(issue.number, labels=updated_labels)

        except Exception as e:
            log.error("pr_fix_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Fix Proposal Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"🤖 Posted by Builder Automation"
            )
            raise

    def _format_fix_proposal(
        self,
        pr_number: int,
        pr_title: str,
        branch_name: str,
        review_feedback: str
    ) -> str:
        """Format fix proposal issue body."""
        lines = [
            f"# Fix Proposal for PR #{pr_number}",
            "",
            f"**Original PR**: #{pr_number} - {pr_title}",
            f"**Branch**: `{branch_name}`",
            "",
            "## Review Feedback",
            "",
            review_feedback,
            "",
            "## Proposed Fixes",
            "",
            "This proposal will create tasks to address the review feedback above.",
            "Each item will be fixed and committed to the same branch.",
            "",
            "## Approval",
            "",
            "To proceed with fixes:",
            "1. Review the feedback above",
            "2. Add the `approved` label to this issue",
            "3. Builder will create and execute fix tasks",
            "",
            "---",
            "",
            "🤖 Posted by Builder Automation",
        ]

        return "\n".join(lines)
