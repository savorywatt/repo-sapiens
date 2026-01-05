"""Implementation stage - Execute development tasks."""

import structlog

from repo_sapiens.engine.branching import get_branching_strategy
from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, Task

log = structlog.get_logger(__name__)


class ImplementationStage(WorkflowStage):
    """Execute implementation tasks using AI agent."""

    async def execute(self, issue: Issue) -> None:
        """Execute implementation stage.

        Checks dependencies, creates branch, executes task, and updates state.

        Args:
            issue: Issue tagged with needs-implementation
        """
        log.info("implementation_stage_started", issue=issue.number)

        try:
            # 1. Extract task details from issue
            task = self._extract_task_from_issue(issue)
            plan_id = self._extract_plan_id(issue.body)

            log.info("executing_task", task_id=task.id, plan_id=plan_id)

            # 2. Check dependencies are complete
            if not await self._check_dependencies(plan_id, task):
                log.warning("dependencies_not_complete", task_id=task.id)
                await self.git.add_comment(
                    issue.number, "⏳ Task dependencies not yet complete. Waiting..."
                )
                return

            # 3. Create/checkout branch based on strategy
            branching = get_branching_strategy(
                self.settings.workflow.branching_strategy,
                self.git,
                self.settings,
            )

            branch = await branching.create_task_branch(plan_id, task)

            # 4. Build task context
            context = await self._build_task_context(plan_id, task, branch)

            # 5. Execute task using agent
            log.info("running_agent", task_id=task.id, branch=branch)
            result = await self.agent.execute_task(task, context)

            if not result.success:
                raise RuntimeError(f"Task execution failed: {result.error}")

            # 6. Update issue with results
            await self.git.add_comment(
                issue.number,
                f"✅ Implementation complete!\n\n"
                f"- Branch: `{branch}`\n"
                f"- Commits: {len(result.commits)}\n"
                f"- Files changed: {len(result.files_changed)}\n"
                f"- Execution time: {result.execution_time:.2f}s",
            )

            # 7. Tag issue for code review
            labels = [
                label for label in issue.labels if label != self.settings.tags.needs_implementation
            ]
            labels.append(self.settings.tags.code_review)
            await self.git.update_issue(issue.number, labels=labels)

            # 8. Update state
            await self.state.mark_task_status(
                plan_id,
                task.id,
                "code_review",
                {
                    "branch": branch,
                    "commits": result.commits,
                    "files_changed": result.files_changed,
                },
            )

            log.info("implementation_stage_completed", task_id=task.id)

        except Exception as e:
            log.error("implementation_stage_failed", error=str(e))
            await self._handle_stage_error(issue, "implementation", e)
            raise

    def _extract_task_from_issue(self, issue: Issue) -> Task:
        """Extract Task object from issue."""
        import re

        # Extract task ID
        match = re.search(r"Task ID.*:\s*(\S+)", issue.body)
        task_id = match.group(1) if match else "unknown"

        # Extract description (between "## Description" and next "##")
        match = re.search(r"## Description\s+(.*?)(?=\n##|$)", issue.body, re.DOTALL)
        description = match.group(1).strip() if match else ""

        # Extract dependencies
        dependencies = []
        if "## Dependencies" in issue.body:
            dep_pattern = r"-\s+(\S+)"
            dependencies = re.findall(dep_pattern, issue.body)

        title = issue.title.replace("[Implement] ", "")

        return Task(
            id=task_id,
            prompt_issue_id=issue.number,
            title=title,
            description=description,
            dependencies=dependencies,
        )

    def _extract_plan_id(self, issue_body: str) -> str:
        """Extract plan ID from issue body."""
        import re

        match = re.search(r"plan #(\d+)", issue_body)
        return match.group(1) if match else ""

    async def _check_dependencies(self, plan_id: str, task: Task) -> bool:
        """Check if all task dependencies are complete."""
        if not task.dependencies:
            return True

        state = await self.state.load_state(plan_id)
        tasks_state = state.get("tasks", {})

        for dep_id in task.dependencies:
            dep_status = tasks_state.get(dep_id, {}).get("status")
            if dep_status not in ["code_review", "merge_ready", "completed"]:
                log.info(
                    "dependency_not_ready", task_id=task.id, dependency=dep_id, status=dep_status
                )
                return False

        return True

    async def _build_task_context(self, plan_id: str, task: Task, branch: str) -> dict:
        """Build execution context for task."""
        # Read plan file
        plan_path_match = await self._get_plan_path(plan_id)

        plan_content = ""
        if plan_path_match:
            try:
                plan_content = await self.git.get_file(
                    path=plan_path_match,
                    ref=self.settings.repository.default_branch,
                )
            except Exception as e:
                log.warning("failed_to_read_plan", error=str(e))

        # Get info about completed dependencies
        state = await self.state.load_state(plan_id)
        dependencies_completed = []

        for dep_id in task.dependencies:
            dep_data = state.get("tasks", {}).get(dep_id, {})
            dependencies_completed.append(
                {
                    "task_id": dep_id,
                    "branch": dep_data.get("branch"),
                    "files": dep_data.get("files_changed", []),
                }
            )

        return {
            "workspace": str(self.settings.workflow.plans_directory),
            "branch": branch,
            "plan_content": plan_content,
            "dependencies_completed": dependencies_completed,
        }

    async def _get_plan_path(self, plan_id: str) -> str:
        """Get plan file path from state."""
        state = await self.state.load_state(plan_id)
        return state.get("stages", {}).get("planning", {}).get("data", {}).get("plan_path", "")
