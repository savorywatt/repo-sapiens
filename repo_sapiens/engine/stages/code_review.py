"""Code review stage - AI review of implemented code."""

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Review

log = structlog.get_logger(__name__)


class CodeReviewStage(WorkflowStage):
    """Review implemented code using AI agent."""

    async def execute(self, issue: Issue) -> None:
        """Execute code review stage.

        Gets diff, runs AI review, and updates issue based on results.

        Args:
            issue: Issue tagged with code-review
        """
        log.info("code_review_stage_started", issue=issue.number)

        try:
            # 1. Extract task details
            task_id = self._extract_task_id(issue.body)
            plan_id = self._extract_plan_id(issue.body)

            # 2. Get task branch from state
            state = await self.state.load_state(plan_id)
            task_data = state.get("tasks", {}).get(task_id, {})
            branch = task_data.get("branch")

            if not branch:
                raise ValueError(f"No branch found for task {task_id}")

            # 3. Get diff between branch and base
            log.info("getting_diff", branch=branch)
            diff = await self.git.get_diff(
                base=self.settings.repository.default_branch,
                head=branch,
            )

            # 4. Build review context
            context = {
                "task": {
                    "id": task_id,
                    "title": issue.title.replace("[Implement] ", ""),
                },
                "plan_id": plan_id,
                "branch": branch,
            }

            # 5. Use agent to review code
            log.info("running_review", task_id=task_id)
            review = await self.agent.review_code(diff, context)

            # 6. Post review comments on issue
            review_comment = self._format_review_comment(review)
            await self.git.add_comment(issue.number, review_comment)

            # 7. Update based on approval
            if (
                review.approved
                and review.confidence_score >= self.settings.workflow.review_approval_threshold
            ):
                # Approved - mark as merge-ready
                labels = [
                    label for label in issue.labels if label != self.settings.tags.code_review
                ]
                labels.append(self.settings.tags.merge_ready)
                await self.git.update_issue(issue.number, labels=labels)

                await self.state.mark_task_status(
                    plan_id, task_id, "merge_ready", {"review_confidence": review.confidence_score}
                )

                log.info(
                    "code_review_approved", task_id=task_id, confidence=review.confidence_score
                )

            else:
                # Not approved - keep in review or create follow-up
                if review.issues_found:
                    await self.git.add_comment(
                        issue.number,
                        "❌ Review identified issues that need addressing. "
                        "Please review the comments above and make necessary changes.",
                    )

                log.warning(
                    "code_review_rejected", task_id=task_id, confidence=review.confidence_score
                )

            # 8. Update state
            await self.state.mark_stage_complete(
                plan_id,
                "code_review",
                {
                    "task_id": task_id,
                    "approved": review.approved,
                    "confidence": review.confidence_score,
                },
            )

            log.info("code_review_stage_completed", task_id=task_id)

        except Exception as e:
            log.error("code_review_stage_failed", error=str(e))
            await self._handle_stage_error(issue, e)
            raise

    def _extract_task_id(self, issue_body: str) -> str:
        """Extract task ID from issue body."""
        import re

        match = re.search(r"Task ID.*:\s*(\S+)", issue_body)
        return match.group(1) if match else ""

    def _extract_plan_id(self, issue_body: str) -> str:
        """Extract plan ID from issue body."""
        import re

        match = re.search(r"plan #(\d+)", issue_body)
        return match.group(1) if match else ""

    def _format_review_comment(self, review: "Review") -> str:
        """Format review results as comment."""
        if review.approved:
            status = "✅ **Code Review: APPROVED**"
            comment = f"{status} (Confidence: {review.confidence_score:.2%})\n\n"
        else:
            status = "⚠️ **Code Review: NEEDS CHANGES**"
            comment = f"{status} (Confidence: {review.confidence_score:.2%})\n\n"

        if review.comments:
            comment += "## Overall Assessment\n\n"
            for c in review.comments:
                comment += f"- {c}\n"
            comment += "\n"

        if review.issues_found:
            comment += "## Issues Found\n\n"
            for issue in review.issues_found:
                comment += f"- ⚠️ {issue}\n"
            comment += "\n"

        if review.suggestions:
            comment += "## Suggestions\n\n"
            for suggestion in review.suggestions:
                comment += f"- 💡 {suggestion}\n"
            comment += "\n"

        return comment
