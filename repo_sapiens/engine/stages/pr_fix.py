"""PR fix stage - dynamically responds to review comments."""

from pathlib import Path
from typing import Any

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue
from repo_sapiens.models.review import CommentCategory
from repo_sapiens.utils.async_subprocess import run_command
from repo_sapiens.utils.comment_analyzer import CommentAnalyzer

log = structlog.get_logger(__name__)


class PRFixStage(WorkflowStage):
    """Respond to review comments dynamically when PR has 'needs-fix' label.

    New dynamic workflow:
    1. Detects PRs with 'needs-fix' label
    2. Reads ALL comments from reviewers/maintainers
    3. AI analyzes each comment (simple fix / controversial / question / info)
    4. Replies to each comment with planned action
    5. Batch executes simple fixes immediately
    6. For controversial fixes, posts plan and waits for approval
    7. Removes 'needs-fix' label when done
    """

    async def execute(self, issue: Issue) -> None:
        """Execute dynamic review comment response.

        Args:
            issue: PR issue with 'needs-fix' label
        """
        log.info("pr_fix_start_dynamic", issue=issue.number)

        # Check if already processed (avoid re-processing)
        if "fixes-in-progress" in issue.labels:
            log.debug("already_processing", issue=issue.number)
            return

        log.info("analyzing_review_comments", issue=issue.number)

        try:
            # Mark as in-progress
            updated_labels = list(issue.labels)
            updated_labels.append("fixes-in-progress")
            await self.git.update_issue(issue.number, labels=updated_labels)

            # Get all comments
            comments = await self.git.get_comments(issue.number)

            if not comments:
                # No review comments - analyze issue and propose a fix
                log.info("no_comments_proposing_fix", issue=issue.number)
                await self._propose_fix_for_issue(issue)
                # Remove in-progress label
                updated_labels = [label for label in updated_labels if label != "fixes-in-progress"]
                await self.git.update_issue(issue.number, labels=updated_labels)
                return

            # Analyze all comments with AI
            analyzer = CommentAnalyzer(self.git, self.agent)
            analysis = await analyzer.analyze_comments(issue.number, comments)

            log.info(
                "analysis_complete",
                issue=issue.number,
                simple=len(analysis.simple_fixes),
                controversial=len(analysis.controversial_fixes),
                questions=len(analysis.questions),
            )

            # Post summary comment
            await self._post_summary_comment(issue.number, analysis)

            # Reply to each comment with planned action
            await self._reply_to_comments(analysis)

            # Execute simple fixes in batch
            if analysis.has_executable_fixes():
                await self._execute_simple_fixes(issue.number, analysis)

            # Update labels based on results
            await self._update_labels_after_fixes(issue.number, analysis)

            log.info("pr_fix_complete", issue=issue.number)

        except Exception as e:
            log.error("pr_fix_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Fix Processing Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please review the error and try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            # Remove in-progress label on failure
            updated_labels = [label for label in issue.labels if label != "fixes-in-progress"]
            await self.git.update_issue(issue.number, labels=updated_labels)
            raise

    async def _post_summary_comment(self, pr_number: int, analysis) -> None:
        """Post summary of analysis plan.

        Args:
            pr_number: PR number
            analysis: ReviewAnalysisResult
        """
        lines = [
            "🔍 **Review Comment Analysis Complete**",
            "",
            f"Analyzed **{analysis.reviewer_comments}** comments from reviewers.",
            "",
        ]

        if analysis.simple_fixes:
            lines.append(f"✅ **{len(analysis.simple_fixes)}** simple fixes - will execute immediately")
        if analysis.controversial_fixes:
            lines.append(f"⚠️  **{len(analysis.controversial_fixes)}** controversial fixes - need approval")
        if analysis.questions:
            lines.append(f"❓ **{len(analysis.questions)}** questions - will answer")
        if analysis.info_comments:
            lines.append(f"ℹ️  **{len(analysis.info_comments)}** info comments - acknowledged")
        if analysis.already_done:
            lines.append(f"✓ **{len(analysis.already_done)}** already done")
        if analysis.wont_fix:
            lines.append(f"🚫 **{len(analysis.wont_fix)}** won't fix")

        lines.extend(
            [
                "",
                "I'll reply to each comment with my planned action.",
                "",
                "---",
                "◆ Posted by Sapiens Automation",
            ]
        )

        await self.git.add_comment(pr_number, "\n".join(lines))

    async def _reply_to_comments(self, analysis) -> None:
        """Reply to each comment with planned action.

        Args:
            analysis: ReviewAnalysisResult
        """
        for comment in analysis.get_all_analyses():
            await self._reply_to_single_comment(comment)

    async def _reply_to_single_comment(self, comment) -> None:
        """Reply to a single comment.

        Args:
            comment: CommentAnalysis
        """
        # Build reply based on category
        if comment.category == CommentCategory.SIMPLE_FIX:
            reply = f"✅ **Will fix**: {comment.proposed_action}\n\n"
            reply += f"*Reason*: {comment.reasoning}\n\n"
            reply += "This will be implemented immediately."

        elif comment.category == CommentCategory.CONTROVERSIAL_FIX:
            reply = f"⚠️  **Needs approval**: {comment.proposed_action}\n\n"
            reply += f"*Reason*: {comment.reasoning}\n\n"
            reply += "This is a significant change. Please approve by:\n"
            reply += "- Reacting with 👍 to this comment, OR\n"
            reply += "- Replying with 'approved'\n\n"
            reply += "I'll implement this once approved."

        elif comment.category == CommentCategory.QUESTION:
            reply = f"❓ **Answer**: {comment.answer}\n\n"
            reply += f"*Context*: {comment.reasoning}"

        elif comment.category == CommentCategory.INFO:
            reply = f"ℹ️  **Acknowledged**: {comment.reasoning}\n\n"
            reply += "Thank you for the feedback."

        elif comment.category == CommentCategory.ALREADY_DONE:
            reply = f"✓ **Already done**: {comment.reasoning}\n\n"
            reply += "This is already addressed in the current code."

        elif comment.category == CommentCategory.WONT_FIX:
            reply = f"🚫 **Won't fix**: {comment.reasoning}\n\n"
            reply += f"*Explanation*: {comment.proposed_action}"

        else:
            reply = f"🤔 **Analyzed**: {comment.reasoning}"

        reply += "\n\n---\n◆ Posted by Sapiens Automation"

        # Post reply
        try:
            await self.git.add_comment_reply(comment.comment_id, reply)
            comment.reply_posted = True
            log.info("posted_reply", comment_id=comment.comment_id, category=comment.category)
        except Exception as e:
            log.error("reply_failed", comment_id=comment.comment_id, error=str(e))
            # Fallback: post as regular comment mentioning the original
            fallback_reply = f"*Re: comment by @{comment.comment_author}*\n\n{reply}"
            await self.git.add_comment(comment.comment_id, fallback_reply)

    async def _execute_simple_fixes(self, pr_number: int, analysis) -> None:
        """Execute all simple fixes in batch.

        Args:
            pr_number: PR number
            analysis: ReviewAnalysisResult
        """
        if not analysis.simple_fixes:
            return

        log.info("executing_simple_fixes", pr_number=pr_number, count=len(analysis.simple_fixes))

        # Get PR to find branch
        pr = await self.git.get_pull_request(pr_number)
        branch_name = pr.head

        # Checkout branch in playground
        playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
        if not playground_dir.exists():
            raise Exception(f"Playground repo not found at {playground_dir}")

        log.info("checking_out_branch", branch=branch_name)

        # Fetch and checkout
        await run_command("git", "fetch", "origin", cwd=playground_dir, check=True)
        await run_command(
            "git",
            "checkout",
            "-B",
            branch_name,
            f"origin/{branch_name}",
            cwd=playground_dir,
            check=True,
        )

        # Execute each fix with agent
        original_working_dir = self.agent.working_dir
        self.agent.working_dir = str(playground_dir)

        try:
            for fix in analysis.simple_fixes:
                await self._execute_single_fix(fix, pr_number)

            # Commit all changes
            await self._commit_fixes(playground_dir, branch_name, analysis.simple_fixes)

        finally:
            self.agent.working_dir = original_working_dir

    async def _execute_single_fix(self, fix, pr_number: int) -> None:
        """Execute a single fix.

        Args:
            fix: CommentAnalysis for a simple fix
            pr_number: PR number
        """
        log.info("executing_fix", comment_id=fix.comment_id, file=fix.file_path)

        prompt = f"""You are implementing a code fix based on review feedback.

**PR Number**: #{pr_number}
**Comment**: {fix.comment_body}
**Planned Action**: {fix.proposed_action}
**File**: {fix.file_path or "not specified"}
**Line**: {fix.line_number or "not specified"}

**CRITICAL**:
1. Implement the fix exactly as planned
2. Use the Edit tool to modify files
3. Make ONLY the specific change requested
4. Don't make unrelated changes

Implement the fix now.
"""

        result = await self.agent.execute_prompt(
            prompt,
            context={"pr_number": pr_number, "comment_id": fix.comment_id},
            task_id=f"fix-{fix.comment_id}",
        )

        fix.executed = True
        fix.execution_result = "success" if result.get("success") else f"failed: {result.get('error')}"

        log.info("fix_executed", comment_id=fix.comment_id, success=result.get("success"))

    async def _commit_fixes(self, playground_dir: Path, branch_name: str, fixes: list[Any]) -> None:
        """Commit all fixes.

        Args:
            playground_dir: Working directory
            branch_name: Branch name
            fixes: List of CommentAnalysis fixes
        """
        # Git add all changes
        await run_command("git", "add", ".", cwd=playground_dir, check=True)

        # Check if there are changes
        status_stdout, _, _ = await run_command(
            "git",
            "status",
            "--porcelain",
            cwd=playground_dir,
            check=True,
        )

        if not status_stdout.strip():
            log.warning("no_changes_to_commit")
            return

        # Build commit message with references
        comment_refs = ", ".join([f"#{fix.comment_id}" for fix in fixes])
        commit_message = (
            f"fix: Address review feedback\n\n"
            f"Implemented fixes for review comments: {comment_refs}\n\n"
            f"Co-authored-by: Sapiens AI <noreply@sapiens.dev>"
        )

        await run_command(
            "git",
            "commit",
            "-m",
            commit_message,
            cwd=playground_dir,
            check=True,
        )

        # Push to remote
        await run_command(
            "git",
            "push",
            "origin",
            branch_name,
            cwd=playground_dir,
            check=True,
        )

        log.info("fixes_committed", branch=branch_name, fixes=len(fixes))

    async def _update_labels_after_fixes(self, pr_number: int, analysis) -> None:
        """Update PR labels based on fix results.

        Args:
            pr_number: PR number
            analysis: ReviewAnalysisResult
        """
        issue = await self.git.get_issue(pr_number)
        updated_labels = [label for label in issue.labels if label not in ["needs-fix", "fixes-in-progress"]]

        # Add needs-approval if there are controversial fixes
        if analysis.has_controversial_fixes():
            updated_labels.append("needs-approval")

        await self.git.update_issue(pr_number, labels=updated_labels)

        log.info("labels_updated", pr_number=pr_number, labels=updated_labels)

    async def _propose_fix_for_issue(self, issue: Issue) -> None:
        """Propose a fix for an issue when no review comments exist.

        This fallback analyzes the issue content and proposes a solution.
        """
        log.info("proposing_fix_for_issue", issue=issue.number)

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔧 **Analyzing Issue for Fix**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll analyze the problem and propose a solution.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Build context for agent
            context = {
                "issue_number": issue.number,
                "issue_title": issue.title,
                "issue_body": issue.body,
            }

            # Execute fix proposal with agent
            prompt = f"""You are analyzing an issue and proposing a fix.

**Issue Title**: {issue.title}

**Issue Description**:
{issue.body or "(No description provided)"}

**Instructions**:
Analyze this issue and provide:
1. **Problem Summary**: A clear summary of what needs to be fixed
2. **Root Cause Analysis**: What might be causing this issue
3. **Proposed Fix**: A detailed proposal for how to fix it
4. **Implementation Steps**: Step-by-step instructions
5. **Testing Suggestions**: How to verify the fix works

Be specific and actionable. If code changes are needed, describe them clearly.
If this is a feature request rather than a bug, propose an implementation approach.

Format your response with clear sections and bullet points.
"""

            result = await self.agent.execute_prompt(prompt, context, f"fix-proposal-{issue.number}")

            if not result.get("success"):
                raise Exception(f"Fix proposal failed: {result.get('error')}")

            output = result.get("output", "No fix proposal generated.")

            # Post fix proposal
            await self.git.add_comment(
                issue.number,
                f"📋 **Fix Proposal**\n\n"
                f"{output}\n\n"
                f"---\n"
                f"To approve this fix, add the `approved` label.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Update labels: remove needs-fix, add fix-proposed
            updated_labels = [
                label for label in issue.labels if label not in ["needs-fix", "sapiens/needs-fix", "fixes-in-progress"]
            ]
            updated_labels.append("fix-proposed")
            await self.git.update_issue(issue.number, labels=updated_labels)

            log.info("fix_proposal_complete", issue=issue.number)

        except Exception as e:
            log.error("fix_proposal_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Fix Proposal Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise
