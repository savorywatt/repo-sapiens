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
    """Abstract base class for Git provider implementations.

    This interface defines the contract that all Git provider implementations
    (GitHub, Gitea, GitLab) must fulfill. It normalizes provider-specific APIs
    into a common interface using the domain models defined in models.domain.

    Implementations handle provider-specific quirks such as:
    - Different field names (e.g., GitLab's 'description' vs GitHub's 'body')
    - Different ID schemes (e.g., GitLab's 'iid' vs 'id')
    - Different state names (e.g., GitLab's 'opened' vs GitHub's 'open')
    - Authentication header formats (Bearer, token, PRIVATE-TOKEN)

    All methods are async to support non-blocking I/O with HTTP clients.
    """

    @abstractmethod
    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues from repository.

        Args:
            labels: Filter by labels. When multiple labels are provided,
                implementations should return issues matching ALL labels
                (intersection, not union).
            state: Filter by state. Valid values are "open", "closed", or "all".
                Implementations normalize provider-specific state names.

        Returns:
            List of Issue objects sorted by creation date (newest first,
            though exact ordering may vary by provider).

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).
            ConnectionError: If the provider connection is not established.
        """
        pass

    @abstractmethod
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number.

        Args:
            issue_number: The repository-scoped issue number (not the global ID).
                In GitLab terminology, this corresponds to the 'iid'.

        Returns:
            Issue object with all fields populated.

        Raises:
            httpx.HTTPStatusError: If the API request fails or issue not found (Gitea/GitLab).
            GithubException: If the API request fails or issue not found (GitHub).
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
            title: Issue title. Should be concise but descriptive.
            body: Issue body/description. Supports Markdown formatting.
                Mapped to 'description' for GitLab.
            labels: Labels to apply. Labels are created automatically if they
                don't exist (for Gitea/GitLab; GitHub requires pre-existing labels).

        Returns:
            Created Issue object with server-assigned ID and number.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).
            ValueError: If required fields are missing or invalid.
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

        Only provided fields are updated; None values are ignored.
        This is a partial update (PATCH semantics), not a full replacement.

        Args:
            issue_number: Issue number to update.
            title: New title. Pass None to leave unchanged.
            body: New body/description. Pass None to leave unchanged.
            labels: New labels. Pass None to leave unchanged. When provided,
                replaces all existing labels (not additive).
            state: New state ("open" or "closed"). Pass None to leave unchanged.
                GitLab uses 'state_event' internally ("close" or "reopen").

        Returns:
            Updated Issue object reflecting all current field values.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            For Gitea, labels are updated via a separate API endpoint before
            other fields, which may result in two API calls.
        """
        pass

    @abstractmethod
    async def add_comment(self, issue_number: int, comment: str) -> Comment:
        """Add comment to issue.

        Creates a new comment on the specified issue. Comments support
        Markdown formatting on all providers.

        Args:
            issue_number: Issue number to comment on.
            comment: Comment text (Markdown supported). Named 'body' in
                the actual API calls for GitHub/GitLab.

        Returns:
            Created Comment object with server-assigned ID and timestamp.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            GitLab calls these 'notes' internally; this method uses the
            /notes endpoint for GitLab.
        """
        pass

    @abstractmethod
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Retrieve all comments for an issue.

        Returns all user-created comments on the specified issue, ordered
        by creation time (oldest first).

        Args:
            issue_number: Issue number.

        Returns:
            List of Comment objects. Empty list if no comments exist.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            For GitLab, this filters out system-generated notes (e.g.,
            "changed the description", "added label") and returns only
            user-authored comments.
        """
        pass

    @abstractmethod
    async def create_branch(self, branch_name: str, from_branch: str) -> Branch:
        """Create a new branch.

        Creates a new branch pointing to the same commit as the source branch.
        If the branch already exists, implementations should return the existing
        branch without raising an error.

        Args:
            branch_name: Name for the new branch. Should follow Git branch
                naming conventions (no spaces, special characters limited).
            from_branch: Source branch to create from. Must exist.

        Returns:
            Branch object with name and commit SHA.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            GitHub uses the Git refs API to create branches, while Gitea
            and GitLab have dedicated branch creation endpoints.
        """
        pass

    @abstractmethod
    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch.

        Removes a branch from the repository. Cannot delete protected branches
        or the default branch.

        Args:
            branch_name: Name of the branch to delete.

        Returns:
            True if the branch was deleted, False if it didn't exist.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).
            PermissionError: If the branch is protected or is the default branch.

        Note:
            GitHub uses the Git refs API to delete branches, while Gitea
            and GitLab have dedicated branch deletion endpoints.
        """
        pass

    @abstractmethod
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information.

        Args:
            branch_name: Branch name to look up.

        Returns:
            Branch object with name, SHA, and protection status,
            or None if the branch does not exist.

        Raises:
            httpx.HTTPStatusError: If the API request fails for reasons
                other than 404 (Gitea/GitLab).
            GithubException: If the API request fails for reasons
                other than 404 (GitHub).

        Note:
            A 404 response is handled gracefully and returns None rather
            than raising an exception. This allows callers to check for
            branch existence without try/except.
        """
        pass

    @abstractmethod
    async def get_diff(self, base: str, head: str) -> str:
        """Get diff between two branches.

        Returns the unified diff showing changes from base to head.
        The diff format follows Git's unified diff format with
        'diff --git' headers for each file.

        Args:
            base: Base branch name (the "before" state).
            head: Head branch name (the "after" state).

        Returns:
            Unified diff as string. May be empty if branches are identical.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            Gitea and GitLab implementations accept an optional pr_number/mr_number
            parameter to get the diff directly from a PR/MR, which is more
            reliable for large diffs.
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

        Performs a merge commit combining source branch changes into target.
        This is a server-side merge, not requiring a local clone.

        Args:
            source: Source branch name containing the changes to merge.
            target: Target branch name to merge into.
            message: Merge commit message.

        Raises:
            httpx.HTTPStatusError: If the merge fails due to conflicts or
                API errors (Gitea/GitLab).
            GithubException: If the merge fails (GitHub).

        Note:
            GitHub uses the repository merge API, while Gitea/GitLab have
            dedicated branch merge endpoints. Merge conflicts will cause
            the operation to fail; manual conflict resolution is required.
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
        """Create a pull request (or merge request for GitLab).

        If a PR/MR already exists for the same head->base combination,
        implementations should update the existing PR/MR with the new
        title and body rather than creating a duplicate.

        Args:
            title: PR/MR title.
            body: PR/MR description (Markdown supported). Mapped to
                'description' for GitLab.
            head: Head branch (source branch containing changes).
            base: Base branch (target branch to merge into).
            labels: Labels to apply. Converted to label IDs for Gitea,
                comma-separated string for GitLab.

        Returns:
            Created or updated PullRequest object.

        Raises:
            httpx.HTTPStatusError: If the API request fails (Gitea/GitLab).
            GithubException: If the API request fails (GitHub).

        Note:
            GitLab terminology uses 'merge request' (MR) and 'source_branch'/
            'target_branch', which are mapped to head/base respectively.
        """
        pass

    @abstractmethod
    async def get_pull_request(self, pr_number: int) -> PullRequest:
        """Get pull request by number.

        Args:
            pr_number: Pull request number (iid for GitLab MRs).

        Returns:
            PullRequest object with all fields populated.

        Raises:
            httpx.HTTPStatusError: If the PR is not found or API fails (Gitea/GitLab).
            GithubException: If the PR is not found or API fails (GitHub).
            ValueError: If the MR is not found (GitLab, via get_pull_request wrapper).
        """
        pass

    async def add_comment_reply(self, comment_id: int, reply: str) -> Comment:
        """Reply to a specific comment.

        This is an optional method - not all providers support threaded replies.
        Default implementation raises NotImplementedError.

        Args:
            comment_id: ID of the comment to reply to (global ID, not issue-scoped).
            reply: Reply text (Markdown supported).

        Returns:
            Created Comment object representing the reply.

        Raises:
            NotImplementedError: If the provider does not support threaded
                comment replies (default behavior).

        Note:
            Threaded replies are a platform-specific feature. GitHub supports
            them on PR review comments but not issue comments. GitLab supports
            them on MR discussions. Gitea support varies by version.
        """
        # Default: fall back to regular comment (issue number not available here)
        raise NotImplementedError("Provider does not support comment replies")

    @abstractmethod
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Read file contents from repository.

        Retrieves the content of a single file at a specific Git reference.
        File content is returned decoded as UTF-8 text.

        Args:
            path: File path relative to repository root (e.g., "src/main.py").
                Must not start with "/". GitLab requires URL-encoding internally.
            ref: Branch name, tag, or commit SHA to read from. Defaults to "main".

        Returns:
            File contents as decoded UTF-8 string.

        Raises:
            httpx.HTTPStatusError: If the file is not found or API fails (Gitea/GitLab).
            GithubException: If the file is not found or API fails (GitHub).
            ValueError: If the path points to a directory instead of a file (GitHub).

        Note:
            Binary files are not well-supported; this method assumes text content.
            The file content is returned base64-decoded by all providers.
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

        Creates or updates a file in the repository via a single commit.
        If the file exists, it is updated; otherwise, a new file is created.

        Args:
            path: File path relative to repository root (e.g., "src/main.py").
            content: New file contents as string. Will be base64-encoded for
                the API request (Gitea/GitLab) or passed directly (GitHub).
            message: Commit message describing the change.
            branch: Target branch to commit to. Must exist.

        Returns:
            Commit SHA of the created commit. GitLab may return the file path
            if the commit ID is not available in the response.

        Raises:
            httpx.HTTPStatusError: If the commit fails (Gitea/GitLab).
            GithubException: If the commit fails (GitHub).

        Note:
            This is a server-side commit, not requiring a local clone.
            For updating existing files, the file's current SHA is fetched
            automatically to enable the update (required by GitHub/Gitea).
        """
        pass

    async def setup_automation_labels(
        self,
        labels: list[str] | None = None,
    ) -> dict[str, int]:
        """Set up automation labels in the repository.

        Creates the specified labels if they don't exist. This is used during
        init and bootstrap to ensure required labels are available for the
        workflow automation.

        Default labels created (if none specified):
            - needs-planning: Issues requiring AI planning (purple)
            - awaiting-approval: Plans waiting for human review (yellow)
            - approved: Plans approved for implementation (green)
            - in-progress: Implementation in progress (blue)
            - done: Implementation complete (green)
            - proposed: Proposals awaiting discussion (light blue)

        Args:
            labels: List of label names to create. If None, creates the
                default automation label set.

        Returns:
            Dict mapping label names to their provider-specific IDs.

        Raises:
            httpx.HTTPStatusError: If label creation fails (Gitea/GitLab).
            GithubException: If label creation fails (GitHub).

        Note:
            This is an optional method with a no-op default implementation.
            Each provider override assigns distinct colors to labels for
            visual differentiation in the UI.
        """
        # Default implementation does nothing - providers override as needed
        return {}


class AgentProvider(ABC):
    """Abstract base class for AI agent implementations.

    This interface defines the contract for AI agents that can generate plans,
    execute development tasks, and review code. Implementations may use different
    AI backends (Claude, OpenAI, Ollama, etc.) but must conform to this interface.

    The agent lifecycle typically follows:
        1. generate_plan() - Analyze issue and create implementation plan
        2. generate_prompts() - Break plan into executable tasks
        3. execute_task() - Run each task to implement changes
        4. review_code() - Review the resulting code changes

    Attributes:
        working_dir: Optional working directory for agent operations. When set,
            file operations are relative to this directory.
    """

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
            prompt: The prompt text to execute. May contain instructions,
                questions, or code to analyze.
            context: Optional context dict providing additional information:
                - pr_number: Pull request number for context
                - comment_id: Comment ID being responded to
                - issue_number: Related issue number
                - branch: Current working branch
            task_id: Optional task identifier for tracking and logging.

        Returns:
            Dict with the following structure:
                - 'success': bool indicating if execution completed
                - 'output': str with the agent's response (if success=True)
                - 'error': str with error message (if success=False)

        Raises:
            Implementation-specific exceptions may be raised for API errors,
            timeout, or rate limiting.
        """
        pass

    @abstractmethod
    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue.

        Analyzes the issue's title, body, and labels to produce a structured
        plan for implementation. The plan includes a description of the approach
        and a list of tasks to be executed.

        Args:
            issue: Issue to plan for. The issue body should contain sufficient
                detail for the agent to understand the requirements.

        Returns:
            Plan object containing:
                - id: Unique identifier for the plan
                - title: Plan title (often derived from issue title)
                - description: High-level approach description
                - tasks: List of Task objects to execute

        Raises:
            Implementation-specific exceptions for API errors or if the issue
            lacks sufficient detail for planning.
        """
        pass

    @abstractmethod
    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        Decomposes a high-level plan into specific, executable tasks.
        Each task should be atomic and independently executable, though
        tasks may have dependencies on other tasks.

        Args:
            plan: Plan to decompose. The plan's description guides how
                tasks are structured and ordered.

        Returns:
            List of Task objects, each containing:
                - id: Unique task identifier
                - title: Brief task description
                - description: Detailed instructions for execution
                - dependencies: List of task IDs that must complete first
                - context: Additional context needed for execution

        Raises:
            Implementation-specific exceptions for API errors.
        """
        pass

    @abstractmethod
    async def execute_task(self, task: Task, context: dict[str, Any]) -> TaskResult:
        """Execute a development task.

        Runs a single task, typically involving code generation, modification,
        or other development activities. The agent operates within the provided
        context (branch, workspace, etc.).

        Args:
            task: Task to execute, containing the detailed instructions.
            context: Execution context dict containing:
                - workspace: Path to the working directory
                - branch: Git branch to work on
                - dependencies: Results from dependent tasks
                - issue_number: Related issue number
                - Additional implementation-specific context

        Returns:
            TaskResult containing:
                - success: Whether the task completed successfully
                - branch: Branch where changes were made
                - commits: List of commit SHAs created
                - files_changed: List of modified file paths
                - error: Error message if success=False
                - execution_time: Duration in seconds
                - output: Agent's summary of work done

        Raises:
            Implementation-specific exceptions for API errors or execution failures.
        """
        pass

    @abstractmethod
    async def review_code(self, diff: str, context: dict[str, Any]) -> Review:
        """Review code changes.

        Analyzes a diff for code quality, correctness, and adherence to
        the original plan/requirements. Returns a structured review with
        approval decision and detailed feedback.

        Args:
            diff: Unified diff string to review. Should follow standard
                Git diff format with file headers and hunks.
            context: Review context dict containing:
                - plan: Original Plan object
                - task: Task that produced the changes
                - issue: Related Issue object
                - Additional implementation-specific context

        Returns:
            Review object containing:
                - approved: Whether the code passes review
                - comments: General review comments
                - issues_found: List of problems identified
                - suggestions: Improvement recommendations
                - confidence_score: 0.0-1.0 confidence in the review

        Raises:
            Implementation-specific exceptions for API errors.
        """
        pass

    @abstractmethod
    async def resolve_conflict(self, conflict_info: dict[str, Any]) -> str:
        """Resolve merge conflict.

        Analyzes a merge conflict and produces a resolved version of the
        file that incorporates changes from both sides appropriately.

        Args:
            conflict_info: Dict containing conflict details:
                - file_path: Path to the conflicted file
                - base_content: Common ancestor content
                - ours_content: Content from current branch
                - theirs_content: Content from incoming branch
                - conflict_markers: Raw file with conflict markers
                - context: Additional context about the change intent

        Returns:
            Resolved file content as a string, with all conflict markers
            removed and changes appropriately merged.

        Raises:
            Implementation-specific exceptions for API errors or if the
            conflict cannot be resolved automatically.
        """
        pass
