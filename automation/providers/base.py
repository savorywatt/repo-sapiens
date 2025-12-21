"""
Abstract base classes for providers.

This module defines the provider interfaces that enable pluggable implementations
for Git operations (Gitea, GitHub) and AI agents (Claude, OpenAI).
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from automation.models.domain import (
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
        labels: Optional[List[str]] = None,
        state: str = "open",
    ) -> List[Issue]:
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
        labels: Optional[List[str]] = None,
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
        title: Optional[str] = None,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        state: Optional[str] = None,
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
    async def get_comments(self, issue_number: int) -> List[Comment]:
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
    async def get_branch(self, branch_name: str) -> Optional[Branch]:
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
        labels: Optional[List[str]] = None,
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


class AgentProvider(ABC):
    """Abstract base class for AI agent implementations."""

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
    async def generate_prompts(self, plan: Plan) -> List[Task]:
        """Break plan into executable tasks.

        Args:
            plan: Plan to break down

        Returns:
            List of Task objects with dependencies
        """
        pass

    @abstractmethod
    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        """Execute a development task.

        Args:
            task: Task to execute
            context: Execution context (workspace, branch, dependencies, etc.)

        Returns:
            TaskResult with execution details
        """
        pass

    @abstractmethod
    async def review_code(self, diff: str, context: dict) -> Review:
        """Review code changes.

        Args:
            diff: Code diff to review
            context: Review context (plan, task, etc.)

        Returns:
            Review object with approval status and comments
        """
        pass

    @abstractmethod
    async def resolve_conflict(self, conflict_info: dict) -> str:
        """Resolve merge conflict.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolved file content
        """
        pass
