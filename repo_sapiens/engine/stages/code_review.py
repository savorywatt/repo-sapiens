"""
Code review stage - AI-powered review of implemented code.

This module implements the CodeReviewStage, which performs automated code
review using an AI agent. The stage examines the diff between a feature
branch and the base branch, then posts review comments on the issue.

Workflow Integration:
    The code review stage is triggered by the ``code-review`` label.
    Upon completion, it either:
    - Approves the code and adds ``merge-ready`` label
    - Requests changes and posts issues to address

    Label Flow (approved): code-review -> merge-ready
    Label Flow (changes needed): code-review remains

Review Process:
    1. Extract task and plan identifiers from the issue
    2. Load the task's branch from state
    3. Fetch the diff between the branch and base
    4. Use AI agent to review the diff
    5. Post review comments to the issue
    6. Update labels based on approval status
    7. Persist review results to state

Approval Criteria:
    The AI review produces a confidence score. The code is approved if:
    - The ``review.approved`` flag is True
    - The confidence score meets or exceeds the configured threshold
      (``settings.workflow.review_approval_threshold``)

Review Comment Format:
    Comments include:
    - Approval status with confidence percentage
    - Overall assessment
    - Specific issues found (if any)
    - Suggestions for improvement (if any)

Example:
    An issue with label "code-review" for a task branch will:
    1. Get the diff for the branch
    2. Run AI review on the diff
    3. Post a comment like "Code Review: APPROVED (Confidence: 92%)"
    4. Add "merge-ready" label if approved
"""

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Review

log = structlog.get_logger(__name__)


class CodeReviewStage(WorkflowStage):
    """Perform automated code review using an AI agent.

    This stage reviews the code changes made by a task implementation,
    providing feedback and determining whether the code is ready for
    merge. The review considers code quality, potential bugs, and
    adherence to best practices.

    Execution Flow:
        1. Extract task_id and plan_id from the issue body
        2. Load the task's branch name from state
        3. Fetch the diff between the task branch and base branch
        4. Build context for the AI review
        5. Run the AI agent's code review
        6. Post formatted review comments to the issue
        7. Update labels based on approval (merge-ready or keep reviewing)
        8. Persist review results to state manager

    Review Outcomes:
        - Approved: Code meets quality bar, add merge-ready label
        - Changes Needed: Issues found, keep code-review label and
          post feedback

    Attributes:
        Inherited from WorkflowStage: git, agent, state, settings

    Example:
        >>> stage = CodeReviewStage(git, agent, state, settings)
        >>> await stage.execute(issue)  # Reviews code and posts comments
    """

    async def execute(self, issue: Issue) -> None:
        """Execute AI code review for the given issue.

        Orchestrates the complete code review workflow from diff retrieval
        to comment posting to label updates.

        Args:
            issue: Issue with the ``code-review`` label. The issue body
                must contain task ID and plan ID references.

        Raises:
            ValueError: If no branch is found for the task in state.
            Exception: Any other exception during review. Handled via
                ``_handle_stage_error()`` before re-raising.

        Side Effects:
            - Fetches diff from git provider
            - Posts review comment to the issue
            - Updates issue labels (adds merge-ready if approved)
            - Persists task status and review results to state
            - Logs review outcome

        Example:
            >>> await stage.execute(code_review_issue)
            >>> # Review comment posted with approval or feedback
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
            if review.approved and review.confidence_score >= self.settings.workflow.review_approval_threshold:
                # Approved - mark as merge-ready
                labels = [label for label in issue.labels if label != self.settings.tags.code_review]
                labels.append(self.settings.tags.merge_ready)
                await self.git.update_issue(issue.number, labels=labels)

                await self.state.mark_task_status(
                    plan_id, task_id, "merge_ready", {"review_confidence": review.confidence_score}
                )

                log.info("code_review_approved", task_id=task_id, confidence=review.confidence_score)

            else:
                # Not approved - keep in review or create follow-up
                if review.issues_found:
                    await self.git.add_comment(
                        issue.number,
                        "❌ Review identified issues that need addressing. "
                        "Please review the comments above and make necessary changes.",
                    )

                log.warning("code_review_rejected", task_id=task_id, confidence=review.confidence_score)

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
        """Extract the task ID from the issue body.

        Parses the issue body for a "Task ID:" reference. This is used
        to look up the task's branch and state information.

        Args:
            issue_body: The markdown-formatted issue body.

        Returns:
            The task ID string, or an empty string if not found.
            The pattern matched is "Task ID: <id>" or "Task ID: <id>".

        Example:
            >>> self._extract_task_id("Task ID: task-42")
            'task-42'
        """
        import re

        match = re.search(r"Task ID.*:\s*(\S+)", issue_body)
        return match.group(1) if match else ""

    def _extract_plan_id(self, issue_body: str) -> str:
        """Extract the plan ID from the issue body.

        Parses the issue body for a "plan #" reference. This is used
        to load the plan state containing task information.

        Args:
            issue_body: The markdown-formatted issue body.

        Returns:
            The plan number as a string, or an empty string if not found.
            The pattern matched is "plan #123".

        Example:
            >>> self._extract_plan_id("Part of plan #42")
            '42'
        """
        import re

        match = re.search(r"plan #(\d+)", issue_body)
        return match.group(1) if match else ""

    def _format_review_comment(self, review: "Review") -> str:
        """Format the AI review results as a markdown comment.

        Creates a well-structured comment that presents the review
        outcome, overall assessment, issues found, and suggestions
        in a readable format.

        Args:
            review: The Review object from the AI agent containing
                approval status, confidence score, comments, issues,
                and suggestions.

        Returns:
            A markdown-formatted string suitable for posting as an
            issue comment. Includes emoji indicators for visual clarity.

        Sections:
            - Header: Approval status with confidence percentage
            - Overall Assessment: General comments from the review
            - Issues Found: Specific problems that need addressing
            - Suggestions: Non-blocking improvement recommendations

        Example:
            >>> comment = self._format_review_comment(review)
            >>> "APPROVED" in comment or "NEEDS CHANGES" in comment
            True
        """
        # Build header with approval status and confidence
        if review.approved:
            status = "**Code Review: APPROVED**"
            comment = f"{status} (Confidence: {review.confidence_score:.2%})\n\n"
        else:
            status = "**Code Review: NEEDS CHANGES**"
            comment = f"{status} (Confidence: {review.confidence_score:.2%})\n\n"

        # Add overall assessment section if comments exist
        if review.comments:
            comment += "## Overall Assessment\n\n"
            for c in review.comments:
                comment += f"- {c}\n"
            comment += "\n"

        # Add issues section if problems were found
        if review.issues_found:
            comment += "## Issues Found\n\n"
            for issue in review.issues_found:
                comment += f"- {issue}\n"
            comment += "\n"

        # Add suggestions section for non-blocking improvements
        if review.suggestions:
            comment += "## Suggestions\n\n"
            for suggestion in review.suggestions:
                comment += f"- {suggestion}\n"
            comment += "\n"

        return comment
