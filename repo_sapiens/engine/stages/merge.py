"""
Merge stage - Create pull request and finalize completed work.

This module implements the MergeStage, which handles the final phase of the
workflow. When all tasks in a plan are marked as merge-ready, this stage
creates an integration branch, opens a pull request, and closes related
issues.

Workflow Integration:
    The merge stage is triggered by the ``merge-ready`` label. It waits
    until ALL tasks in the plan are merge-ready before proceeding.

    Label Flow: merge-ready -> (issue closed)

Branch Strategy:
    The stage uses a configurable branching strategy to create an
    integration branch. This allows different merge patterns:
    - Single branch: All tasks already on one branch
    - Multi-branch: Tasks on separate branches, merged into integration

Pull Request:
    The generated PR includes:
    - Summary of all completed tasks
    - List of changed files (if available)
    - Test plan checklist
    - References to all related issues

Issue Management:
    Upon successful PR creation:
    - All task issues are closed with a link to the PR
    - The plan issue is closed with a completion message

Example:
    A plan with 3 tasks, all with "merge-ready" label, will:
    1. Verify all tasks are ready
    2. Create integration branch from task branches
    3. Generate comprehensive PR description
    4. Create PR targeting the default branch
    5. Close all task issues with PR reference
    6. Close the plan issue
"""

import structlog

from repo_sapiens.engine.branching import get_branching_strategy
from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue

log = structlog.get_logger(__name__)


class MergeStage(WorkflowStage):
    """Finalize completed work by creating a pull request.

    This stage handles the culmination of the workflow: verifying all
    tasks are complete, creating an integration branch, generating a
    comprehensive pull request, and closing all related issues.

    Execution Flow:
        1. Extract plan_id from the issue body
        2. Load plan state and verify all tasks are merge-ready
        3. Get the branching strategy based on configuration
        4. Collect all task branches from state
        5. Create an integration branch (strategy-dependent)
        6. Generate a comprehensive PR description
        7. Create the pull request
        8. Close all task issues with PR reference
        9. Close the plan issue with completion message
        10. Persist merge completion to state

    Waiting Behavior:
        If not all tasks are merge-ready, the stage posts a comment
        indicating which tasks are still pending and returns without
        error. The orchestrator will retry when the next task becomes
        ready.

    Branching Strategies:
        The stage delegates branch creation to a configurable strategy:
        - GitFlow: Creates release branches
        - Single: Uses a single integration branch
        - Feature: Creates feature branches per task

    Attributes:
        Inherited from WorkflowStage: git, agent, state, settings

    Example:
        >>> stage = MergeStage(git, agent, state, settings)
        >>> await stage.execute(plan_issue)  # Creates PR if all ready
    """

    async def execute(self, issue: Issue) -> None:
        """Create a pull request for the completed plan.

        Orchestrates the merge process, but only proceeds if all tasks
        in the plan are marked as merge-ready. Otherwise, posts a
        waiting message and returns.

        Args:
            issue: Issue with the ``merge-ready`` label. Must be a plan
                issue (body contains plan ID reference).

        Raises:
            Exception: If PR creation fails. Handled via
                ``_handle_stage_error()`` before re-raising.

        Side Effects:
            - Creates integration branch (via branching strategy)
            - Creates pull request
            - Closes all task issues with PR link
            - Closes the plan issue with completion message
            - Persists merge completion to state

        Note:
            If not all tasks are ready, posts a waiting comment and
            returns without error. This is expected behavior.

        Example:
            >>> await stage.execute(plan_issue)
            >>> # If all tasks ready: PR created, issues closed
            >>> # If tasks pending: "Waiting for tasks..." comment posted
        """
        log.info("merge_stage_started", issue=issue.number)

        try:
            # 1. Extract plan_id from issue
            plan_id = self._extract_plan_id(issue.body)

            # 2. Check all tasks are merge-ready
            state = await self.state.load_state(plan_id)
            tasks_state = state.get("tasks", {})

            all_ready = all(task.get("status") == "merge_ready" for task in tasks_state.values())

            if not all_ready:
                log.warning("not_all_tasks_ready", plan_id=plan_id)
                await self.git.add_comment(
                    issue.number,
                    "⏳ Not all tasks are merge-ready yet. Waiting for remaining tasks...",
                )
                return

            # 3. Get branching strategy
            branching = get_branching_strategy(
                self.settings.workflow.branching_strategy,
                self.git,
                self.settings,
            )

            # 4. Create integration branch based on strategy
            task_branches = [task_data.get("branch") for task_data in tasks_state.values() if task_data.get("branch")]

            log.info("creating_integration_branch", plan_id=plan_id, branches=len(task_branches))
            integration_branch = await branching.create_integration(plan_id, task_branches)

            # 5. Generate PR description
            pr_title = f"[Plan #{plan_id}] {self._get_plan_title(state)}"
            pr_body = self._generate_pr_body(plan_id, state, tasks_state)

            # 6. Create PR
            log.info("creating_pull_request", plan_id=plan_id, branch=integration_branch)
            pr = await self.git.create_pull_request(
                title=pr_title,
                body=pr_body,
                head=integration_branch,
                base=self.settings.repository.default_branch,
                labels=["automated"],
            )

            # 7. Update all related issues
            pr_link = pr.url
            for task_data in tasks_state.values():
                if task_issue_num := task_data.get("issue_number"):
                    await self.git.add_comment(task_issue_num, f"✅ Task included in pull request: {pr_link}")
                    await self.git.update_issue(task_issue_num, state="closed")

            # 8. Update plan issue
            await self.git.add_comment(
                issue.number,
                f"🎉 Pull request created: {pr_link}\n\nAll tasks have been completed and merged.",
            )
            await self.git.update_issue(issue.number, state="closed")

            # 9. Mark plan as completed in state
            await self.state.mark_stage_complete(
                plan_id,
                "merge",
                {
                    "integration_branch": integration_branch,
                    "pr_number": pr.number,
                    "pr_url": pr.url,
                },
            )

            log.info("merge_stage_completed", plan_id=plan_id, pr=pr.number)

        except Exception as e:
            log.error("merge_stage_failed", error=str(e))
            await self._handle_stage_error(issue, e)
            raise

    def _extract_plan_id(self, issue_body: str) -> str:
        """Extract the plan ID from the issue body.

        Parses the issue body for a plan reference. Tries multiple
        patterns to accommodate different formatting styles.

        Args:
            issue_body: The markdown-formatted issue body.

        Returns:
            The plan number as a string, or an empty string if not found.
            Patterns matched: "plan #123" or "Plan #123".

        Example:
            >>> self._extract_plan_id("Implementation of plan #42")
            '42'
        """
        import re

        # Try lowercase pattern first
        match = re.search(r"plan #(\d+)", issue_body)
        if not match:
            # Try alternative pattern with capital P
            match = re.search(r"Plan.*#(\d+)", issue_body)
        return match.group(1) if match else ""

    def _get_plan_title(self, state: dict) -> str:
        """Get a display title for the plan.

        Attempts to extract a meaningful title from the state. Falls
        back to a generic title with the plan ID if no title is found.

        Args:
            state: The plan's workflow state dictionary.

        Returns:
            A display-friendly title for the plan.

        Example:
            >>> self._get_plan_title({"plan_id": "42"})
            'Plan 42'
        """
        # TODO: Extract title from original issue or metadata
        return f"Plan {state.get('plan_id', 'unknown')}"

    def _generate_pr_body(self, plan_id: str, state: dict, tasks_state: dict) -> str:
        """Generate a comprehensive pull request description.

        Creates a detailed PR body that includes plan summary, task list,
        file changes, and a test plan checklist. This provides reviewers
        with full context about the changes.

        Args:
            plan_id: The plan identifier for display.
            state: The full workflow state dictionary.
            tasks_state: Dictionary of task states, mapping task IDs to
                their state data.

        Returns:
            Markdown-formatted PR body containing:
            - Plan header and summary
            - Total task count and status
            - Branching strategy used
            - Completed tasks with issue references
            - List of changed files (if available)
            - Test plan checklist

        Example:
            >>> body = self._generate_pr_body("42", state, tasks)
            >>> "Development Plan #42" in body
            True
        """
        body = f"""# Development Plan #{plan_id}

This pull request implements the complete development plan #{plan_id}.

## Summary

"""

        # Add task summary
        body += f"- **Total tasks:** {len(tasks_state)}\n"
        body += "- **Status:** All tasks completed and reviewed\n"
        body += f"- **Branching strategy:** {self.settings.workflow.branching_strategy}\n\n"

        # List all tasks
        body += "## Tasks Completed\n\n"
        for task_id, task_data in tasks_state.items():
            issue_num = task_data.get("issue_number", "?")
            branch = task_data.get("branch", "unknown")
            body += f"- [x] {task_id} (#{issue_num}) - `{branch}`\n"

        body += "\n## Files Changed\n\n"
        all_files = set()
        for task_data in tasks_state.values():
            files = task_data.get("files_changed", [])
            all_files.update(files)

        if all_files:
            for file in sorted(all_files):
                body += f"- `{file}`\n"
        else:
            body += "_(File list not available)_\n"

        body += "\n## Test Plan\n\n"
        body += "- [ ] All unit tests pass\n"
        body += "- [ ] Integration tests pass\n"
        body += "- [ ] Manual testing completed\n"

        body += "\n---\n"
        body += "🤖 Generated with automation system\n"

        return body
