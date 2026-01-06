"""Merge stage - Create PR and merge completed work."""

import structlog

from repo_sapiens.engine.branching import get_branching_strategy
from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue

log = structlog.get_logger(__name__)


class MergeStage(WorkflowStage):
    """Merge completed tasks and create pull request."""

    async def execute(self, issue: Issue) -> None:
        """Execute merge stage.

        Checks all tasks are ready, creates integration branch (if needed),
        and creates pull request.

        Args:
            issue: Issue tagged with merge-ready
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
            task_branches = [
                task_data.get("branch")
                for task_data in tasks_state.values()
                if task_data.get("branch")
            ]

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
                    await self.git.add_comment(
                        task_issue_num, f"✅ Task included in pull request: {pr_link}"
                    )
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
        """Extract plan ID from issue body."""
        import re

        match = re.search(r"plan #(\d+)", issue_body)
        if not match:
            # Try alternative pattern
            match = re.search(r"Plan.*#(\d+)", issue_body)
        return match.group(1) if match else ""

    def _get_plan_title(self, state: dict) -> str:
        """Get plan title from state."""
        # Fallback to plan_id
        return f"Plan {state.get('plan_id', 'unknown')}"

    def _generate_pr_body(self, plan_id: str, state: dict, tasks_state: dict) -> str:
        """Generate comprehensive PR description."""
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
