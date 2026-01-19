"""
Domain models for the automation system.

This module contains all data classes and enums representing the core business
entities of the automation system, including issues, tasks, plans, and reviews.
These models serve as the normalized internal representation, converted from
provider-specific formats (GitHub, GitLab, Gitea).

Example:
    Creating an issue from provider data::

        issue = Issue(
            id=12345,
            number=42,
            title="Fix login bug",
            body="Users cannot log in with SSO",
            state=IssueState.OPEN,
            labels=["bug", "priority:high"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="jdoe",
            url="https://github.com/org/repo/issues/42"
        )
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IssueState(str, Enum):
    """Enumeration of possible issue states.

    All git providers normalize to these two states, regardless of their
    native state representations (e.g., GitLab's "opened" becomes OPEN).
    """

    OPEN = "open"
    """Issue is active and awaiting resolution."""

    CLOSED = "closed"
    """Issue has been resolved or dismissed."""


class TaskStatus(str, Enum):
    """Task execution status throughout the workflow lifecycle.

    Tasks progress through these states as they move through the automation
    pipeline. The typical happy path is:
    PENDING -> IN_PROGRESS -> CODE_REVIEW -> MERGE_READY -> COMPLETED

    Example:
        Checking if a task can be executed::

            if task_status == TaskStatus.PENDING:
                # Ready to start execution
                pass
            elif task_status == TaskStatus.FAILED:
                # Requires manual intervention or retry
                pass
    """

    PENDING = "pending"
    """Task is queued but not yet started."""

    IN_PROGRESS = "in_progress"
    """Task is actively being executed by an agent."""

    CODE_REVIEW = "code_review"
    """Implementation complete, awaiting code review."""

    MERGE_READY = "merge_ready"
    """Review approved, ready to merge to target branch."""

    COMPLETED = "completed"
    """Task fully completed and merged."""

    FAILED = "failed"
    """Task failed during execution and requires attention."""


@dataclass
class Issue:
    """Represents a Git issue from any provider.

    This is the normalized representation used internally, converted from
    provider-specific formats (GitHub Issue, Gitea Issue, GitLab Issue).
    The automation system works exclusively with this model.

    Example:
        Converting from GitHub API response::

            issue = Issue(
                id=response["id"],
                number=response["number"],
                title=response["title"],
                body=response["body"] or "",
                state=IssueState(response["state"]),
                labels=[l["name"] for l in response["labels"]],
                created_at=parse_datetime(response["created_at"]),
                updated_at=parse_datetime(response["updated_at"]),
                author=response["user"]["login"],
                url=response["html_url"]
            )
    """

    id: int
    """Unique identifier assigned by the git provider's database.

    This is an internal ID that may change across API versions or data
    migrations. Prefer using `number` for stable references.
    """

    number: int
    """Human-readable issue number (e.g., #42).

    This is the stable identifier shown in the UI and URLs. Unlike `id`,
    this number persists across API versions and is what users reference.
    """

    title: str
    """Issue title/summary, typically a single line.

    Should be concise but descriptive enough to understand the issue
    at a glance.
    """

    body: str
    """Full issue description in markdown format.

    Contains the detailed problem description, reproduction steps,
    expected behavior, etc. May be empty for simple issues.
    """

    state: IssueState
    """Current state of the issue (open or closed)."""

    labels: list[str]
    """List of label names attached to the issue.

    Labels control workflow behavior (e.g., "sapiens:execute" triggers
    automation). Provider-specific label metadata is not preserved.
    """

    created_at: datetime
    """Timestamp when the issue was originally created."""

    updated_at: datetime
    """Timestamp of the most recent update to the issue.

    This includes edits, comments, label changes, and state changes.
    """

    author: str
    """Username of the issue creator.

    This is the login/username, not the display name.
    """

    url: str
    """Web URL to view the issue in the provider's UI.

    This is the human-friendly URL, not the API endpoint.
    """


@dataclass
class Comment:
    """Represents an issue or pull request comment.

    Comments are used for communication between users and the automation
    system, including plan approvals, review feedback, and status updates.
    """

    id: int
    """Unique identifier for the comment within the provider."""

    body: str
    """Comment content in markdown format.

    May contain commands for the automation system (e.g., "LGTM",
    "Please fix the typo on line 42").
    """

    author: str
    """Username of the comment author."""

    created_at: datetime
    """Timestamp when the comment was posted."""


@dataclass
class Branch:
    """Represents a Git branch.

    Used for tracking feature branches created during task execution
    and for managing merges.
    """

    name: str
    """Full branch name (e.g., "feature/add-login", "main").

    Does not include the "refs/heads/" prefix.
    """

    sha: str
    """Git commit SHA that the branch currently points to.

    This is the full 40-character SHA, not abbreviated.
    """

    protected: bool = False
    """Whether the branch has protection rules enabled.

    Protected branches typically require pull requests and reviews
    before changes can be merged.
    """


@dataclass
class PullRequest:
    """Represents a pull request (merge request in GitLab terminology).

    Pull requests are created by the automation system after implementing
    a task, linking code changes back to the original issue.

    Example:
        Checking if a PR is ready to merge::

            if pr.mergeable and not pr.merged and pr.state == "open":
                # Safe to merge
                pass
    """

    id: int
    """Unique identifier assigned by the git provider."""

    number: int
    """Human-readable PR number (e.g., #123).

    This is displayed in the UI and used in most API operations.
    """

    title: str
    """Pull request title, typically describing the change."""

    body: str
    """Pull request description in markdown format.

    Usually includes a summary of changes, testing instructions,
    and links to related issues.
    """

    head: str
    """Source branch name containing the changes to merge."""

    base: str
    """Target branch name to merge into (e.g., "main", "develop")."""

    state: str
    """Current PR state (provider-specific: "open", "closed", "merged")."""

    url: str
    """Web URL to view the pull request in the provider's UI."""

    created_at: datetime
    """Timestamp when the pull request was created."""

    author: str = ""
    """Username of the pull request author.

    May be empty for PRs created by automation before author tracking
    was added.
    """

    mergeable: bool = True
    """Whether the PR can be cleanly merged.

    False indicates merge conflicts that must be resolved manually.
    Some providers return None when mergeability is still being computed.
    """

    merged: bool = False
    """Whether the PR has already been merged.

    Once True, the PR cannot be merged again.
    """


@dataclass
class Task:
    """Represents a single development task extracted from a plan.

    Tasks are the atomic units of work that agents execute. Each task
    results in code changes on a dedicated branch and a pull request.

    Example:
        A plan for "Add user authentication" might contain tasks like::

            Task(id="task-1", title="Create User model", ...)
            Task(id="task-2", title="Add login endpoint", dependencies=["task-1"])
            Task(id="task-3", title="Add logout endpoint", dependencies=["task-1"])
    """

    id: str
    """Unique identifier for the task within its plan.

    Typically formatted as "task-1", "task-2", etc. Used for dependency
    references and state tracking.
    """

    prompt_issue_id: int
    """Issue number that this task was derived from.

    Links the task back to the original feature request or bug report.
    """

    title: str
    """Brief description of what the task accomplishes.

    Should be actionable and specific (e.g., "Add input validation to
    login form" not "Fix login").
    """

    description: str
    """Detailed instructions for the agent executing the task.

    Includes specific requirements, acceptance criteria, and any context
    needed for implementation.
    """

    dependencies: list[str] = field(default_factory=list)
    """List of task IDs that must complete before this task.

    Tasks are executed in topological order respecting these dependencies.
    An empty list means the task can start immediately.
    """

    context: dict[str, Any] = field(default_factory=dict)
    """Additional context data for task execution.

    May include relevant file paths, code snippets, API documentation,
    or other information helpful for the agent.
    """


@dataclass
class TaskResult:
    """Result of executing a task.

    Captures everything produced by a task execution, including success/failure
    status, code changes, and agent output.

    Example:
        Handling a task result::

            result = await agent.execute(task)
            if result.success:
                print(f"Created {len(result.commits)} commits on {result.branch}")
            else:
                print(f"Task failed: {result.error}")
    """

    success: bool
    """Whether the task completed successfully.

    False indicates the agent encountered an error or could not complete
    the requested work.
    """

    branch: str | None = None
    """Git branch where changes were committed.

    None if the task failed before creating a branch.
    """

    commits: list[str] = field(default_factory=list)
    """List of commit SHAs created during task execution.

    In chronological order (oldest first). Empty if no commits were made.
    """

    files_changed: list[str] = field(default_factory=list)
    """List of file paths that were modified, added, or deleted.

    Paths are relative to the repository root.
    """

    error: str | None = None
    """Error message if the task failed.

    Contains details about what went wrong. None if successful.
    """

    execution_time: float = 0.0
    """Time taken to execute the task in seconds.

    Useful for performance monitoring and timeout configuration.
    """

    output: str | None = None
    """Agent's final answer or output text.

    Contains the agent's summary of what was done, any important notes,
    or responses to questions in the task.
    """


@dataclass
class Plan:
    """Represents a development plan generated from an issue.

    A plan breaks down a feature request or bug report into actionable
    tasks. Plans are reviewed and approved before execution begins.

    Example:
        Creating a plan from AI analysis::

            plan = Plan(
                id="plan-issue-42",
                title="Implement user authentication",
                description="Add login/logout with session management",
                tasks=[task1, task2, task3],
                file_path=".sapiens/plans/plan-issue-42.yaml"
            )
    """

    id: str
    """Unique identifier for the plan.

    Typically formatted as "plan-issue-{number}" to link back to
    the originating issue.
    """

    title: str
    """Human-readable title summarizing the plan's goal."""

    description: str
    """Detailed description of the plan's scope and approach.

    Explains what will be implemented and any important decisions
    or constraints.
    """

    tasks: list[Task]
    """Ordered list of tasks to execute.

    Tasks should be ordered considering dependencies, though the
    execution engine will also respect explicit dependency declarations.
    """

    file_path: str | None = None
    """Path where the plan is persisted on disk.

    None for plans that haven't been saved yet. Typically under
    .sapiens/plans/ directory.
    """

    created_at: datetime = field(default_factory=datetime.now)
    """Timestamp when the plan was generated."""


@dataclass
class Review:
    """Code review result from automated analysis.

    Contains the outcome of an AI-powered code review, including
    whether changes are approved and any feedback.

    Example:
        Processing a review result::

            review = await reviewer.analyze(pr)
            if review.approved:
                await merge_pr(pr)
            else:
                await post_review_comments(pr, review.issues_found)
    """

    approved: bool
    """Whether the code changes are approved for merging.

    True means no blocking issues were found. False means issues
    must be addressed before merging.
    """

    comments: list[str] = field(default_factory=list)
    """General comments about the code changes.

    These are observations that don't necessarily block approval,
    such as praise or minor notes.
    """

    issues_found: list[str] = field(default_factory=list)
    """List of issues that should be fixed.

    These are problems that blocked approval, such as bugs,
    security issues, or significant style violations.
    """

    suggestions: list[str] = field(default_factory=list)
    """Optional improvement suggestions.

    Nice-to-have changes that don't block approval but would
    improve the code quality.
    """

    confidence_score: float = 0.0
    """AI confidence in the review accuracy (0.0 to 1.0).

    Lower scores may indicate the AI struggled to understand
    the code or context. Scores below 0.7 should prompt human review.
    """
