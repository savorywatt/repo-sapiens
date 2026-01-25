"""PR review stage - performs code review on pull requests."""

import re

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, PullRequest

log = structlog.get_logger(__name__)


class PRReviewStage(WorkflowStage):
    """Review pull request when label changes to 'needs-review'.

    This stage:
    1. Detects PRs with 'needs-review' label
    2. Gets PR diff and changed files
    3. Executes agent to perform code review
    4. Posts inline comments on specific lines
    5. Updates label to 'needs-fix' or 'approved'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute PR code review.

        Args:
            issue: PR issue with 'needs-review' label
        """
        log.info("pr_review_start", issue=issue.number)

        # This should only run on PR issues
        # For now, we'll check if there's an associated PR by trying to get it
        pr = await self._get_pr_for_issue(issue)
        if not pr:
            # No PR found - review the issue content instead
            log.info("no_pr_found_reviewing_issue", issue=issue.number)
            await self._review_issue_content(issue)
            return

        # Check if already reviewed
        if "needs-fix" in issue.labels or "approved" in issue.labels:
            log.debug("already_reviewed", issue=issue.number)
            return

        log.info("reviewing_pr", pr=pr.number)

        try:
            # Get PR diff
            diff = await self.git.get_diff(pr.base, pr.head, pr_number=pr.number)

            if not diff:
                log.warning("empty_diff", pr=pr.number)
                return

            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔍 **Starting Code Review**\n\n"
                f"Reviewing PR #{pr.number}\n"
                f"Branch: `{pr.head}`\n\n"
                f"I'll analyze the code and provide feedback.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Build context for agent
            context = {
                "pr_number": pr.number,
                "pr_title": pr.title,
                "pr_body": pr.body,
                "base_branch": pr.base,
                "head_branch": pr.head,
                "diff": diff,
            }

            # Execute review with agent
            log.info("executing_review_agent", pr=pr.number)

            prompt = f"""You are performing a code review on a pull request.

**PR Title**: {pr.title}
**PR Description**:
{pr.body}

**Branch**: {pr.head} → {pr.base}

**Code Diff**:
```diff
{diff}
```

**Instructions**:
Review this code and provide feedback. Focus on:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance concerns
4. Security vulnerabilities
5. Maintainability and readability

For each issue you find, provide:
- The file path
- The line number (approximate from diff context)
- A clear description of the issue
- A suggestion for how to fix it

Format your response as a list of review comments:

REVIEW_COMMENT:
File: path/to/file.js
Line: 42
Issue: Description of the problem
Suggestion: How to fix it

If the code looks good with no issues, respond with:
REVIEW_APPROVED

Be constructive and specific in your feedback.
"""

            result = await self.agent.execute_prompt(prompt, context, f"pr-review-{pr.number}")

            if not result.get("success"):
                raise Exception(f"Review execution failed: {result.get('error')}")

            # Parse review output
            output = result.get("output", "")

            if "REVIEW_APPROVED" in output:
                # No issues found
                await self.git.add_comment(
                    issue.number,
                    "✅ **Code Review Complete**\n\n"
                    "The code looks good! No issues found.\n\n"
                    "◆ Posted by Sapiens Automation",
                )

                # Update labels: remove 'needs-review', add 'approved'
                updated_labels = [label for label in issue.labels if label != "needs-review"]
                updated_labels.append("approved")
                await self.git.update_issue(issue.number, labels=updated_labels)

                log.info("pr_review_approved", pr=pr.number)
            else:
                # Parse review comments
                comments = self._parse_review_comments(output)

                if comments:
                    # Post review summary
                    summary_lines = [
                        "📝 **Code Review Complete**\n",
                        f"Found {len(comments)} items to address:\n",
                    ]

                    for i, comment in enumerate(comments, 1):
                        summary_lines.append(f"\n{i}. **{comment['file']}** (Line {comment.get('line', 'N/A')})")
                        summary_lines.append(f"   - {comment['issue']}")

                    summary_lines.extend(
                        [
                            "\n\n---\n",
                            (
                                "Please address these items. When ready, "
                                "add the `needs-fix` label to create fix tasks.\n\n"
                            ),
                            "◆ Posted by Sapiens Automation",
                        ]
                    )

                    await self.git.add_comment(issue.number, "\n".join(summary_lines))

                    # Update labels: remove 'needs-review', add 'reviewed'
                    updated_labels = [label for label in issue.labels if label != "needs-review"]
                    updated_labels.append("reviewed")
                    await self.git.update_issue(issue.number, labels=updated_labels)

                    log.info("pr_review_complete", pr=pr.number, comments=len(comments))
                else:
                    log.warning("no_comments_parsed", pr=pr.number)

        except Exception as e:
            log.error("pr_review_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Code Review Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _get_pr_for_issue(self, issue: Issue) -> "PullRequest | None":
        """Try to find a PR associated with this issue.

        In Gitea, PRs are also issues, so we try to get a PR with the same number.
        """
        try:
            # Try to get PR with the same number as the issue
            pr = await self.git.get_pull_request(issue.number)
            return pr
        except Exception as e:
            log.debug("pr_lookup_failed", issue=issue.number, error=str(e))
            return None

    async def _review_issue_content(self, issue: Issue) -> None:
        """Review issue content when no PR is associated.

        This fallback provides useful feedback on the issue description itself.
        """
        log.info("reviewing_issue_content", issue=issue.number)

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔍 **Starting Issue Review**\n\n"
                f"Reviewing issue #{issue.number}: {issue.title}\n\n"
                f"Since this is an issue (not a PR), I'll review the requirements "
                f"and provide feedback on the approach.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Build context for agent
            context = {
                "issue_number": issue.number,
                "issue_title": issue.title,
                "issue_body": issue.body,
            }

            # Execute review with agent
            prompt = f"""You are reviewing an issue/request.

**Issue Title**: {issue.title}

**Issue Description**:
{issue.body or "(No description provided)"}

**Instructions**:
Review this issue and provide feedback on:
1. Clarity of requirements - are they well-defined?
2. Scope - is the scope reasonable and achievable?
3. Potential challenges or risks
4. Suggested approach or implementation strategy
5. Any clarifying questions that should be asked

Provide constructive, actionable feedback that helps improve the issue quality
and sets up for successful implementation.

Format your response as a structured review with clear sections.
"""

            result = await self.agent.execute_prompt(prompt, context, f"issue-review-{issue.number}")

            if not result.get("success"):
                raise Exception(f"Review execution failed: {result.get('error')}")

            output = result.get("output", "No feedback generated.")

            # Post review
            await self.git.add_comment(
                issue.number,
                f"📝 **Issue Review Complete**\n\n" f"{output}\n\n" f"---\n" f"◆ Posted by Sapiens Automation",
            )

            # Update labels: remove review label, add 'reviewed'
            updated_labels = [label for label in issue.labels if label not in ["needs-review", "sapiens/needs-review"]]
            updated_labels.append("reviewed")
            await self.git.update_issue(issue.number, labels=updated_labels)

            log.info("issue_review_complete", issue=issue.number)

        except Exception as e:
            log.error("issue_review_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Issue Review Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    def _parse_review_comments(self, output: str) -> list:
        """Parse review comments from agent output."""
        comments = []

        # Split by REVIEW_COMMENT markers
        comment_blocks = output.split("REVIEW_COMMENT:")

        for block in comment_blocks[1:]:  # Skip first empty block
            comment = {}

            # Extract file
            file_match = re.search(r"File:\s*(.+)", block)
            if file_match:
                comment["file"] = file_match.group(1).strip()

            # Extract line
            line_match = re.search(r"Line:\s*(\d+)", block)
            if line_match:
                comment["line"] = int(line_match.group(1))

            # Extract issue
            issue_match = re.search(r"Issue:\s*(.+?)(?=Suggestion:|$)", block, re.DOTALL)
            if issue_match:
                comment["issue"] = issue_match.group(1).strip()

            # Extract suggestion
            suggestion_match = re.search(r"Suggestion:\s*(.+)", block, re.DOTALL)
            if suggestion_match:
                comment["suggestion"] = suggestion_match.group(1).strip()

            if comment.get("file") and comment.get("issue"):
                comments.append(comment)

        return comments
