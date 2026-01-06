"""Task execution stage - implements individual tasks."""

import re

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.exceptions import TaskExecutionError, WorkflowError
from repo_sapiens.models.domain import Issue

log = structlog.get_logger(__name__)


class TaskExecutionStage(WorkflowStage):
    """Execute individual task when label changes to 'execute'.

    This stage:
    1. Detects tasks with 'execute' label
    2. Creates feature branch for the task
    3. Executes agent with task context
    4. Creates pull request
    5. Updates task label to 'review'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute task implementation.

        Args:
            issue: Task issue with 'execute' label
        """
        log.info("task_execution_start", issue=issue.number)

        # Verify this is a task issue
        if "task" not in issue.labels:
            log.debug("not_a_task_issue", issue=issue.number)
            return

        # Check if already in review (avoid re-execution)
        if "review" in issue.labels:
            log.debug("already_in_review", issue=issue.number)
            return

        # Extract task number from title "[TASK 1/7] ..."
        match = re.match(r"\[TASK (\d+)/(\d+)\]", issue.title)
        if not match:
            log.error("cannot_parse_task_number", title=issue.title)
            return

        task_num = match.group(1)
        total_tasks = match.group(2)

        # Extract original issue number from body
        original_issue_number = self._extract_original_issue(issue.body)
        if not original_issue_number:
            log.error("cannot_find_original_issue", issue=issue.number)
            return

        # Extract plan number from labels (e.g., "plan-1")
        plan_label = None
        for label in issue.labels:
            if label.startswith("plan-"):
                plan_label = label
                break

        if not plan_label:
            log.error("cannot_find_plan_label", issue=issue.number)
            return

        log.info(
            "task_execution_starting",
            task=task_num,
            original=original_issue_number,
            plan=plan_label,
        )

        try:
            # Create plan-based branch name (all tasks in same plan go to same branch)
            branch_name = f"{plan_label}-implementation"

            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔨 **Starting Implementation**\n\n"
                f"Branch: `{branch_name}`\n"
                f"Task: {task_num} of {total_tasks}\n\n"
                f"I'll implement this task and create a pull request when complete.\n\n"
                f"🤖 Posted by Builder Automation",
            )

            # Create branch
            base_branch = self.settings.repository.default_branch
            await self.git.create_branch(branch_name, from_branch=base_branch)
            log.info("branch_created", branch=branch_name)

            # Checkout branch locally in the playground repo
            from pathlib import Path

            from repo_sapiens.utils.async_subprocess import run_command

            # Assume playground repo is in ../playground relative to builder
            # __file__ = .../builder/repo_sapiens/engine/stages/execution.py
            # parent x5 = .../Workspace
            playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
            if not playground_dir.exists():
                raise WorkflowError(f"Playground repo not found at {playground_dir}")

            log.info("checking_out_branch", branch=branch_name, path=str(playground_dir))

            # Fetch latest from remote
            await run_command("git", "fetch", "origin", cwd=playground_dir, check=True)

            # Check if the plan branch exists on remote
            _, _, branch_check_code = await run_command(
                "git",
                "rev-parse",
                f"origin/{branch_name}",
                cwd=playground_dir,
                check=False,
            )

            if branch_check_code == 0:
                # Plan branch exists on remote, check it out and pull latest
                log.info("plan_branch_exists_on_remote", branch=branch_name)
                await run_command(
                    "git",
                    "checkout",
                    "-B",
                    branch_name,
                    f"origin/{branch_name}",
                    cwd=playground_dir,
                    check=True,
                )
            else:
                # Plan branch doesn't exist yet, create from base branch
                log.info("creating_new_plan_branch", branch=branch_name, base=base_branch)
                await run_command(
                    "git",
                    "checkout",
                    f"origin/{base_branch}",
                    cwd=playground_dir,
                    check=True,
                )
                await run_command(
                    "git",
                    "checkout",
                    "-B",
                    branch_name,
                    cwd=playground_dir,
                    check=True,
                )

            log.info("branch_checked_out", branch=branch_name)

            # Get original issue for context
            original_issue = await self.git.get_issue(original_issue_number)

            # Build context for agent
            context = {
                "task_number": task_num,
                "total_tasks": total_tasks,
                "task_title": issue.title,
                "task_description": self._extract_description(issue.body),
                "original_issue": {
                    "number": original_issue.number,
                    "title": original_issue.title,
                    "body": original_issue.body,
                },
                "dependencies": self._extract_dependencies(issue.body),
                "branch": branch_name,
            }

            # Execute task with agent in playground directory
            log.info("executing_agent", task=task_num, working_dir=str(playground_dir))

            # Temporarily change agent working directory
            original_working_dir = self.agent.working_dir
            self.agent.working_dir = str(playground_dir)

            try:
                # Create task object for agent
                from repo_sapiens.models.domain import Task

                task = Task(
                    id=f"task-{issue.number}",
                    prompt_issue_id=issue.number,
                    title=issue.title,
                    description=self._extract_description(issue.body),
                    dependencies=[],
                    context=context,
                )

                result = await self.agent.execute_task(task, context)

                if not result.success:
                    raise TaskExecutionError(
                        f"Task execution failed: {result.error}",
                        task_id=task.id,
                        stage="execution",
                        recoverable=True,
                    )

                log.info("agent_execution_complete", task=task_num)

                # Commit and push changes
                log.info("committing_changes", branch=branch_name)

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
                    # Commit changes with conventional commit format
                    # Extract task title without the [TASK N/M] prefix
                    task_title = issue.title.replace(f"[TASK {task_num}/{total_tasks}] ", "")
                    task_title_lower = task_title.lower()

                    # Determine commit type based on task title
                    if (
                        "setup" in task_title_lower
                        or "structure" in task_title_lower
                        or "initialize" in task_title_lower
                    ) or (
                        "implement" in task_title_lower
                        or "add" in task_title_lower
                        or "create" in task_title_lower
                    ):
                        commit_type = "feat"
                    elif "fix" in task_title_lower or "bug" in task_title_lower:
                        commit_type = "fix"
                    elif "refactor" in task_title_lower:
                        commit_type = "refactor"
                    elif "test" in task_title_lower:
                        commit_type = "test"
                    elif "doc" in task_title_lower:
                        commit_type = "docs"
                    else:
                        commit_type = "feat"

                    commit_message = (
                        f"{commit_type}: {task_title} [TASK-{issue.number}]\n\n"
                        f"Task {task_num}/{total_tasks} for {plan_label}\n"
                        f"Original issue: #{original_issue_number}"
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

                    log.info("changes_committed_and_pushed", branch=branch_name)
                else:
                    log.warning("no_changes_to_commit", task=task_num)

            finally:
                # Restore original working directory
                self.agent.working_dir = original_working_dir

            # Update task issue labels FIRST (before PR update so checklist is accurate)
            # Update labels: remove 'execute', add 'review'
            updated_labels = [label for label in issue.labels if label != "execute"]
            updated_labels.append("review")
            await self.git.update_issue(issue.number, labels=updated_labels)

            # Create or get pull request (plan-based, shared across all tasks)
            # Do this AFTER updating issue labels so the checklist reflects the completed task
            pr_title = f"{plan_label.replace('plan-', 'Plan #')}: {original_issue.title}"
            pr_body = await self._format_plan_pr_body(
                plan_label, original_issue, task_num, total_tasks
            )

            pr = await self.git.create_pull_request(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=base_branch,
                labels=["plan-implementation", plan_label],
            )

            log.info("pull_request_ready", pr=pr.number, task=task_num, plan=plan_label)

            # Update task issue with comment
            await self.git.add_comment(
                issue.number,
                f"✅ **Implementation Complete**\n\n"
                f"Pull Request: #{pr.number}\n"
                f"Branch: `{branch_name}`\n\n"
                f"**Next Steps:**\n"
                f"- Review the pull request\n"
                f"- Merge when satisfied, or comment for changes\n"
                f"- Task will be closed automatically when PR is merged\n\n"
                f"🤖 Posted by Builder Automation",
            )

            log.info("task_execution_complete", task=task_num, pr=pr.number)

        except Exception as e:
            log.error("task_execution_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Task Execution Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please review the error and try again.\n\n"
                f"🤖 Posted by Builder Automation",
            )
            raise

    def _extract_original_issue(self, body: str) -> int | None:
        """Extract original issue number from task body."""
        match = re.search(r"\*\*Original Issue\*\*: #(\d+)", body)
        if match:
            return int(match.group(1))
        return None

    def _extract_description(self, body: str) -> str:
        """Extract task description from body."""
        # Find "## Description" section
        match = re.search(r"## Description\s+(.+?)(?=\s+##|\Z)", body, re.DOTALL)
        if match:
            return match.group(1).strip()
        return body

    def _extract_dependencies(self, body: str) -> list:
        """Extract dependencies from task body."""
        dependencies = []
        match = re.search(r"## Dependencies\s+(.+?)(?=\s+##|\Z)", body, re.DOTALL)
        if match:
            dep_section = match.group(1)
            # Find all lines starting with "-"
            for line in dep_section.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    dependencies.append(line[1:].strip())
        return dependencies

    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        # Remove [TASK N/M] prefix if present
        text = re.sub(r"\[TASK \d+/\d+\]\s*", "", text)
        # Convert to lowercase and replace spaces/special chars with hyphens
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text[:50]  # Limit length

    async def _format_plan_pr_body(
        self, plan_label: str, original_issue: Issue, current_task_num: str, total_tasks: str
    ) -> str:
        """Format pull request body for plan implementation.

        Shows all tasks and their completion status.
        """
        # Get all task issues for this plan
        all_issues = await self.git.get_issues(labels=[plan_label, "task"], state="all")

        # Sort by task number
        task_issues = []
        for issue in all_issues:
            match = re.match(r"\[TASK (\d+)/(\d+)\]", issue.title)
            if match:
                task_issues.append((int(match.group(1)), issue))

        task_issues.sort(key=lambda x: x[0])

        lines = [
            f"# {plan_label.replace('plan-', 'Plan #')} Implementation",
            "",
            f"**Original Issue**: #{original_issue.number} - {original_issue.title}",
            "",
            "## Tasks",
            "",
        ]

        for task_num, task_issue in task_issues:
            # Check if completed (has review label or is closed)
            is_completed = "review" in task_issue.labels or task_issue.state.value == "closed"
            checkbox = "x" if is_completed else " "
            task_title = task_issue.title.replace(f"[TASK {task_num}/{total_tasks}] ", "")
            lines.append(f"- [{checkbox}] Task {task_num}: {task_title} (#{task_issue.number})")

        lines.extend(
            [
                "",
                "## Implementation Notes",
                "",
                "This PR implements the full plan with all tasks committed to a single branch.",
                "Each task is implemented sequentially and committed separately for easy review.",
                "",
                "---",
                "",
                f"**Related Issues**: Implements #{original_issue.number}",
                "",
                "🤖 Posted by Builder Automation",
            ]
        )

        return "\n".join(lines)

    def _format_pr_body(self, task_issue: Issue, original_issue: Issue, result) -> str:
        """Format pull request body."""
        lines = [
            "# Task Implementation",
            "",
            f"**Task Issue**: #{task_issue.number}",
            f"**Original Issue**: #{original_issue.number} - {original_issue.title}",
            "",
            "## Task Description",
            "",
            self._extract_description(task_issue.body),
            "",
        ]

        dependencies = self._extract_dependencies(task_issue.body)
        if dependencies:
            lines.extend(
                [
                    "## Dependencies",
                    "",
                    "This task required:",
                ]
            )
            for dep in dependencies:
                lines.append(f"- {dep}")
            lines.append("")

        lines.extend(
            [
                "## Implementation",
                "",
                "This PR implements the task as specified.",
                "",
                "## Testing",
                "",
                "Please review and test the implementation.",
                "",
                "---",
                "",
                (
                    f"**Related Issues**: Closes #{task_issue.number}, "
                    f"Implements #{original_issue.number}"
                ),
                "",
                "🤖 Posted by Builder Automation",
            ]
        )

        return "\n".join(lines)
