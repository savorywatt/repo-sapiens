"""Approval detection stage - monitors for plan approval comments."""

import structlog

from automation.engine.stages.base import WorkflowStage
from automation.models.domain import Issue

log = structlog.get_logger(__name__)


class ApprovalStage(WorkflowStage):
    """Detect plan approval and create project + task issues.

    This stage:
    1. Checks for approval comments ("ok", "approve", "lgtm")
    2. Parses the plan to extract tasks
    3. Creates Gitea project board
    4. Creates task issues with dependencies
    5. Updates original issue
    6. Closes proposal issue
    """

    APPROVAL_KEYWORDS = ["ok", "approve", "approved", "lgtm", "looks good"]

    async def execute(self, issue: Issue) -> None:
        """Execute approval stage.

        Args:
            issue: Proposal issue to check for approval
        """
        log.info("approval_stage_start", issue=issue.number)

        # Check if already processed (proposal closed means tasks already created)
        if issue.state.value == "closed":
            log.debug("already_processed", issue=issue.number)
            return

        # Get comments on the proposal
        comments = await self.git.get_comments(issue.number)

        # Check for approval via label OR comment
        approved = False
        approver = None

        # Check 1: approved label exists
        if "approved" in issue.labels:
            approved = True
            # Try to find who added the label by checking recent comments
            # Default to issue author if we can't determine
            approver = issue.author
            log.info("approval_detected_via_label", issue=issue.number)

        # Check 2: approval keyword in comments
        if not approved:
            for comment in comments:
                comment_lower = comment.body.lower().strip()
                has_keyword = any(keyword in comment_lower for keyword in self.APPROVAL_KEYWORDS)
                if has_keyword and not self._is_bot_comment(comment.body):
                    approved = True
                    approver = comment.author
                    log.info("approval_detected_via_comment", issue=issue.number, approver=approver)
                    break

        if not approved:
            log.debug("not_yet_approved", issue=issue.number)
            return

        log.info("approval_detected", issue=issue.number, approver=approver)

        try:
            # Extract original issue number from title
            # Format: "[PROPOSAL] Plan for #42: ..."
            import re

            match = re.search(r"#(\d+)", issue.title)
            if not match:
                log.error("cannot_parse_original_issue", title=issue.title)
                return

            original_issue_number = int(match.group(1))
            original_issue = await self.git.get_issue(original_issue_number)

            # Get plan file path from issue body
            plan_content = self._extract_plan_from_body(issue.body)

            # Parse tasks from plan
            tasks = self._parse_tasks_from_plan(plan_content, issue.body)

            log.info("creating_project", original=original_issue_number, task_count=len(tasks))

            # Notify approval
            await self.git.add_comment(
                issue.number,
                f"✅ **Plan Approved by @{approver}**\n\n"
                f"Creating project and {len(tasks)} task issues...\n\n"
                f"🤖 Posted by Builder Automation",
            )

            # Create task issues
            task_issues = []
            for i, task in enumerate(tasks, 1):
                task_issue = await self._create_task_issue(
                    original_issue,
                    task,
                    i,
                    len(tasks),
                )
                task_issues.append(task_issue)
                log.info("task_issue_created", task_number=i, issue=task_issue.number)

            # Build task list with links
            task_lines = []
            for task_issue in task_issues:
                # Extract just the title without [TASK N/M] prefix
                title = task_issue.title
                if "]" in title:
                    title = title.split("]", 1)[1].strip()
                task_lines.append(f"- [#{task_issue.number}]({task_issue.url}): {title}")

            # Update original issue with detailed summary
            comment_parts = [
                "🎯 **Plan Approved & Tasks Created**",
                "",
                f"**Approved by**: @{approver}",
                "",
                f"**Tasks Created** ({len(task_issues)} tasks):",
                "",
            ]
            comment_parts.extend(task_lines)
            comment_parts.extend(
                [
                    "",
                    "**Next Steps:**",
                    "- Review individual task issues above",
                    "- Change any task label from `ready` to `execute` to start implementation",
                    "- Tasks will be executed in dependency order",
                    "",
                    "🤖 Posted by Builder Automation",
                ]
            )

            await self.git.add_comment(original_issue_number, "\n".join(comment_parts))

            # Remove awaiting-approval, add in-progress
            updated_labels = [
                label for label in original_issue.labels if label != "awaiting-approval"
            ]
            updated_labels.append("in-progress")
            await self.git.update_issue(original_issue_number, labels=updated_labels)

            # Keep proposal open but mark as approved (user wants to keep it)
            # Note: 'approved' label was already added when user approved it
            await self.git.add_comment(
                issue.number,
                f"✅ **Proposal Executed**\n\n"
                f"Created {len(task_issues)} task issues.\n"
                f"Keeping this proposal open for reference.\n\n"
                f"🤖 Posted by Builder Automation",
            )

            log.info(
                "approval_stage_complete", original=original_issue_number, tasks=len(task_issues)
            )

        except Exception as e:
            log.error("approval_stage_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Approval Processing Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"🤖 Posted by Builder Automation",
            )
            raise

    def _is_bot_comment(self, body: str) -> bool:
        """Check if comment is from bot."""
        return "🤖 Posted by Builder Automation" in body

    def _extract_plan_from_body(self, body: str) -> str:
        """Extract plan content from proposal body."""
        # The plan is in the body after "## Plan Overview"
        return body

    def _parse_tasks_from_plan(self, plan_content: str, body: str) -> list:
        """Parse tasks from plan content."""
        tasks = []

        # Simple parser - looks for "### N. Task Title"
        import re

        # Split by task headings
        task_pattern = r"### (\d+)\.\s+(.+?)(?:\(requires: (.+?)\))?$"

        lines = body.split("\n")
        current_task = None

        for line in lines:
            match = re.match(task_pattern, line)
            if match:
                if current_task:
                    tasks.append(current_task)

                task_num = int(match.group(1))
                title = match.group(2).strip()
                deps_str = match.group(3)

                # Parse dependencies
                dependencies = []
                if deps_str:
                    dependencies = [d.strip() for d in deps_str.split(",")]

                current_task = {
                    "number": task_num,
                    "title": title,
                    "description": "",
                    "dependencies": dependencies,
                }
            elif current_task and line.strip() and not line.startswith("#"):
                # Accumulate description
                current_task["description"] += line + "\n"

        if current_task:
            tasks.append(current_task)

        return tasks

    async def _create_project(self, project_name: str, issue_number: int) -> dict:
        """Create a Gitea project board.

        Args:
            project_name: Name of the project
            issue_number: Original issue number

        Returns:
            Project data dict with id and html_url, or None if creation fails
        """
        try:
            # Try to create project using Gitea API
            # Note: Gitea projects API endpoint format
            url = f"{self.git.api_base}/repos/{self.git.owner}/{self.git.repo}/projects"
            data = {
                "title": project_name,
                "body": f"Project board for issue #{issue_number}",
            }

            response = await self.git.client.post(url, json=data)
            response.raise_for_status()

            project_data = response.json()
            return {
                "id": project_data.get("id"),
                "html_url": project_data.get("html_url"),
            }
        except Exception as e:
            log.warning("project_creation_failed", error=str(e))
            return None

    async def _create_task_issue(
        self,
        original_issue: Issue,
        task: dict,
        task_number: int,
        total_tasks: int,
    ) -> Issue:
        """Create a task issue."""

        title = f"[TASK {task_number}/{total_tasks}] {task['title']}"

        body_parts = [
            f"**Original Issue**: #{original_issue.number} - {original_issue.title}",
            f"**Task**: {task_number} of {total_tasks}",
            "",
            "## Description",
            "",
            task["description"].strip(),
            "",
        ]

        if task["dependencies"]:
            body_parts.extend(
                [
                    "## Dependencies",
                    "",
                    "This task requires:",
                ]
            )
            for dep in task["dependencies"]:
                body_parts.append(f"- {dep}")
            body_parts.append("")

        body_parts.extend(
            [
                "## Execution",
                "",
                "**To execute this task:**",
                "- Change this issue's label from `ready` to `execute`",
                "- Builder will create a branch and implement the task",
                "- A pull request will be created for review",
                "",
                "🤖 Posted by Builder Automation",
            ]
        )

        issue = await self.git.create_issue(
            title=title,
            body="\n".join(body_parts),
            labels=["task", "ready", f"plan-{original_issue.number}"],
        )

        return issue
