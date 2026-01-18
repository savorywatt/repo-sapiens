"""
Abstract base classes for providers.

This module defines the provider interfaces that enable pluggable implementations
for Git operations (Gitea, GitHub) and AI agents (Claude, OpenAI).
"""

from abc import ABC, abstractmethod
from typing import Any

from repo_sapiens.models.domain import (
    Branch,
    Comment,
    Issue,
    Plan,
    PullRequest,
    Review,
    Task,
    TaskResult,
)


class GitProvider(ABC):
    """Abstract base class for Git provider implementations."""

    @abstractmethod
    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues from repository.

        Args:
            labels: Filter by labels (all labels must match)
            state: Filter by state ("open", "closed", or "all")

        Returns:
            List of Issue objects
        """
        pass

    @abstractmethod
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number.

        Args:
            issue_number: Issue number

        Returns:
            Issue object
        """
        pass

    @abstractmethod
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create a new issue.

        Args:
            title: Issue title
            body: Issue body/description
            labels: Labels to apply

        Returns:
            Created Issue object
        """
        pass

    @abstractmethod
    async def update_issue(
        self,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
        state: str | None = None,
    ) -> Issue:
        """Update issue fields.

        Args:
            issue_number: Issue number
            title: New title (optional)
            body: New body (optional)
            labels: New labels (optional)
            state: New state (optional)

        Returns:
            Updated Issue object
        """
        pass

    @abstractmethod
    async def add_comment(self, issue_number: int, comment: str) -> Comment:
        """Add comment to issue.

        Args:
            issue_number: Issue number
            comment: Comment text

        Returns:
            Created Comment object
        """
        pass

    @abstractmethod
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Retrieve all comments for an issue.

        Args:
            issue_number: Issue number

        Returns:
            List of Comment objects
        """
        pass

    @abstractmethod
    async def create_branch(self, branch_name: str, from_branch: str) -> Branch:
        """Create a new branch.

        Args:
            branch_name: Name of new branch
            from_branch: Source branch to branch from

        Returns:
            Created Branch object
        """
        pass

    @abstractmethod
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information.

        Args:
            branch_name: Branch name

        Returns:
            Branch object or None if not found
        """
        pass

    @abstractmethod
    async def get_diff(self, base: str, head: str) -> str:
        """Get diff between two branches.

        Args:
            base: Base branch name
            head: Head branch name

        Returns:
            Diff as string
        """
        pass

    @abstractmethod
    async def merge_branches(
        self,
        source: str,
        target: str,
        message: str,
    ) -> None:
        """Merge source branch into target.

        Args:
            source: Source branch name
            target: Target branch name
            message: Merge commit message
        """
        pass

    @abstractmethod
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> PullRequest:
        """Create a pull request.

        Args:
            title: PR title
            body: PR description
            head: Head branch
            base: Base branch
            labels: Labels to apply

        Returns:
            Created PullRequest object
        """
        pass

    @abstractmethod
    async def get_pull_request(self, pr_number: int) -> PullRequest:
        """Get pull request by number.

        Args:
            pr_number: Pull request number

        Returns:
            PullRequest object
        """
        pass

    async def add_comment_reply(self, comment_id: int, reply: str) -> Comment:
        """Reply to a specific comment.

        This is an optional method - not all providers support threaded replies.
        Default implementation posts a regular comment.

        Args:
            comment_id: ID of the comment to reply to
            reply: Reply text

        Returns:
            Created Comment object
        """
        # Default: fall back to regular comment (issue number not available here)
        raise NotImplementedError("Provider does not support comment replies")

    @abstractmethod
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Read file contents from repository.

        Args:
            path: File path in repository
            ref: Branch/commit/tag reference

        Returns:
            File contents as string
        """
        pass

    @abstractmethod
    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> str:
        """Commit file to repository.

        Args:
            path: File path in repository
            content: File contents
            message: Commit message
            branch: Branch to commit to

        Returns:
            Commit SHA
        """
        pass

    async def setup_automation_labels(
        self,
        labels: list[str] | None = None,
    ) -> dict[str, int]:
        """Set up automation labels in the repository.

        Creates the specified labels if they don't exist. This is used during
        init and bootstrap to ensure required labels are available.

        Default labels (if none specified):
            - needs-planning: Issues requiring AI planning
            - awaiting-approval: Plans waiting for review
            - approved: Plans approved for implementation
            - in-progress: Implementation in progress
            - done: Implementation complete

        Args:
            labels: List of label names to create. If None, creates defaults.

        Returns:
            Dict mapping label names to their IDs
        """
        # Default implementation does nothing - providers override as needed
        return {}


class AgentProvider(ABC):
    """Abstract base class for AI agent implementations."""

    # Working directory for agent operations (can be set by implementations)
    working_dir: str | None = None

    @abstractmethod
    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt and return the result.

        This is the core method for running AI prompts. Used by comment analysis,
        fix execution, and other interactive AI operations.

        Args:
            prompt: The prompt text to execute
            context: Optional context dict (pr_number, comment_id, etc.)
            task_id: Optional task identifier for tracking

        Returns:
            Dict with 'success' bool and either 'output' or 'error'
        """
        pass

    @abstractmethod
    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue.

        Args:
            issue: Issue to plan for

        Returns:
            Generated Plan object
        """
        pass

    @abstractmethod
    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        Args:
            plan: Plan to break down

        Returns:
            List of Task objects with dependencies
        """
        pass

    @abstractmethod
    async def execute_task(self, task: Task, context: dict[str, Any]) -> TaskResult:
        """Execute a development task.

        Args:
            task: Task to execute
            context: Execution context (workspace, branch, dependencies, etc.)

        Returns:
            TaskResult with execution details
        """
        pass

    @abstractmethod
    async def review_code(self, diff: str, context: dict[str, Any]) -> Review:
        """Review code changes.

        Args:
            diff: Code diff to review
            context: Review context (plan, task, etc.)

        Returns:
            Review object with approval status and comments
        """
        pass

    @abstractmethod
    async def resolve_conflict(self, conflict_info: dict[str, Any]) -> str:
        """Resolve merge conflict.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolved file content
        """
        pass
