"""Fix execution stage - implements fixes from approved proposals."""

import re
from pathlib import Path

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue
from repo_sapiens.utils.async_subprocess import run_command

log = structlog.get_logger(__name__)


class FixExecutionStage(WorkflowStage):
    """Execute fixes when fix proposal is approved.

    This stage:
    1. Detects fix proposal with 'approved' label
    2. Extracts review feedback
    3. Executes agent to implement fixes
    4. Commits fixes to the PR branch
    5. Updates PR and closes fix proposal
    """

    async def execute(self, issue: Issue) -> None:
        """Execute fix implementation.

        Args:
            issue: Fix proposal issue with 'approved' label
        """
        log.info("fix_execution_start", issue=issue.number)

        # Verify this is a fix proposal
        if "fix-proposal" not in issue.labels:
            log.debug("not_a_fix_proposal", issue=issue.number)
            return

        # Check if already executed
        if issue.state.value == "closed":
            log.debug("already_executed", issue=issue.number)
            return

        # Extract PR number from title
        match = re.search(r"PR #(\d+)", issue.title)
        if not match:
            log.error("cannot_parse_pr_number", title=issue.title)
            return

        pr_number = int(match.group(1))

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

        log.info("fix_execution_starting", fix_proposal=issue.number, pr=pr_number, branch=branch_name)

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔧 **Starting Fix Implementation**\n\n"
                f"Branch: `{branch_name}`\n"
                f"PR: #{pr_number}\n\n"
                f"I'll implement the fixes and push to the branch.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Checkout branch in playground repo
            playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
            if not playground_dir.exists():
                raise Exception(f"Playground repo not found at {playground_dir}")

            log.info("checking_out_branch", branch=branch_name, path=str(playground_dir))

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

            log.info("branch_checked_out", branch=branch_name)

            # Extract review feedback from issue body
            feedback = self._extract_feedback(issue.body)

            # Build context for agent
            context = {
                "fix_proposal_number": issue.number,
                "pr_number": pr_number,
                "branch": branch_name,
                "feedback": feedback,
            }

            # Execute fixes with agent
            log.info("executing_fix_agent", fix_proposal=issue.number)

            # Temporarily change agent working directory
            original_working_dir = self.agent.working_dir
            self.agent.working_dir = str(playground_dir)

            try:
                prompt = f"""You are implementing fixes based on code review feedback.

**PR Number**: #{pr_number}
**Branch**: {branch_name}

**Review Feedback to Address**:
{feedback}

**CRITICAL Instructions**:
1. You MUST fix ALL the issues mentioned in the feedback
2. Use the Edit tool to modify existing files
3. Make sure each fix addresses the specific concern raised
4. Test that your changes don't break anything
5. The changes will be automatically committed

**What to do**:
- Read each piece of feedback carefully
- Locate the file and line mentioned
- Implement the suggested fix or a better solution
- Ensure the code quality improves
- Make all necessary changes

Focus on addressing the feedback completely and correctly.
"""

                result = await self.agent.execute_prompt(prompt, context, f"fix-{issue.number}")

                if not result.get("success"):
                    raise Exception(f"Fix execution failed: {result.get('error')}")

                log.info("fix_agent_complete", fix_proposal=issue.number)

                # Commit and push changes
                log.info("committing_fixes", branch=branch_name)

                # Git add all changes
                await run_command("git", "add", ".", cwd=playground_dir, check=True)

                # Check if there are changes to commit
                status_stdout, _, _ = await run_command(
                    "git",
                    "status",
                    "--porcelain",
                    cwd=playground_dir,
                    check=True,
                )

                if status_stdout.strip():
                    # Commit changes
                    commit_message = (
                        f"fix: Address review feedback [FIX-{issue.number}]\n\n"
                        f"Fixes from code review on PR #{pr_number}\n"
                        f"Fix proposal: #{issue.number}"
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

                    log.info("fixes_committed_and_pushed", branch=branch_name)

                    # Update fix proposal issue
                    await self.git.add_comment(
                        issue.number,
                        f"✅ **Fixes Implemented**\n\n"
                        f"All review feedback has been addressed.\n"
                        f"Changes have been pushed to branch `{branch_name}`.\n\n"
                        f"Please review PR #{pr_number} again.\n\n"
                        f"◆ Posted by Sapiens Automation",
                    )

                    # Close fix proposal
                    await self.git.update_issue(issue.number, state="closed")

                    # Comment on PR
                    await self.git.add_comment(
                        pr_number,
                        f"🔧 **Fixes Applied**\n\n"
                        f"Review feedback has been addressed via fix proposal #{issue.number}.\n"
                        f"Please review the updates.\n\n"
                        f"◆ Posted by Sapiens Automation",
                    )

                    log.info("fix_execution_complete", fix_proposal=issue.number, pr=pr_number)
                else:
                    log.warning("no_changes_to_commit", fix_proposal=issue.number)
                    await self.git.add_comment(
                        issue.number,
                        "⚠️ **No Changes Made**\n\n"
                        "The agent didn't make any changes.\n"
                        "Please review the feedback and try again.\n\n"
                        "◆ Posted by Sapiens Automation",
                    )

            finally:
                # Restore original working directory
                self.agent.working_dir = original_working_dir

        except Exception as e:
            log.error("fix_execution_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Fix Implementation Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please review the error and try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    def _extract_feedback(self, body: str) -> str:
        """Extract review feedback section from fix proposal body."""
        # Find "## Review Feedback" section
        match = re.search(r"## Review Feedback\s+(.+?)(?=\s+##|$)", body, re.DOTALL)
        if match:
            return match.group(1).strip()
        return body
