"""GitHub provider implementation using PyGithub and REST API."""

import asyncio
from collections.abc import Callable
from typing import TypeVar

import structlog
from github import Github, GithubException  # type: ignore[import-not-found]
from github.Branch import Branch as GHBranch  # type: ignore[import-not-found]
from github.Issue import Issue as GHIssue  # type: ignore[import-not-found]
from github.IssueComment import IssueComment as GHComment  # type: ignore[import-not-found]
from github.PullRequest import PullRequest as GHPullRequest  # type: ignore[import-not-found]
from github.Repository import Repository as GHRepository  # type: ignore[import-not-found]

from repo_sapiens.models.domain import Branch, Comment, Issue, IssueState, PullRequest
from repo_sapiens.providers.base import GitProvider

log = structlog.get_logger(__name__)

T = TypeVar("T")


async def _run_sync(func: Callable[[], T]) -> T:
    """Run a synchronous function in a thread pool.

    This prevents blocking the event loop when calling synchronous
    PyGithub methods.
    """
    return await asyncio.to_thread(func)


class GitHubRestProvider(GitProvider):
    """GitHub implementation using PyGithub library."""

    def __init__(
        self,
        token: str,
        owner: str,
        repo: str,
        base_url: str = "https://api.github.com",
    ):
        """Initialize GitHub provider.

        Args:
            token: GitHub personal access token or App token
            owner: Repository owner (user or organization)
            repo: Repository name
            base_url: GitHub API base URL (for GitHub Enterprise)
        """
        self.token = token.strip() if token else token
        self.owner = owner
        self.repo = repo
        # Normalize base_url by removing trailing slash (Pydantic HttpUrl adds it)
        self.base_url = base_url.rstrip("/")
        self._client: Github | None = None
        self._repo: GHRepository | None = None

    async def connect(self) -> None:
        """Initialize GitHub client."""

        def _connect() -> tuple[Github, GHRepository]:
            client = Github(self.token, base_url=self.base_url)
            repo = client.get_repo(f"{self.owner}/{self.repo}")
            return client, repo

        self._client, self._repo = await _run_sync(_connect)
        log.info(
            "github_connected",
            base_url=self.base_url,
            owner=self.owner,
            repo=self.repo,
        )

    async def disconnect(self) -> None:
        """Close GitHub client."""
        if self._client:
            await _run_sync(self._client.close)
            self._client = None
            self._repo = None

    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues via GitHub API."""
        log.info("get_issues", labels=labels, state=state)

        gh_state = state if state in ("open", "closed", "all") else "open"

        try:
            # Wrap synchronous iteration in thread pool
            gh_issues = await _run_sync(lambda: list(self._repo.get_issues(state=gh_state, labels=labels or [])))

            # Convert to our Issue model
            return [self._convert_issue(gh_issue) for gh_issue in gh_issues]

        except GithubException as e:
            log.error("github_get_issues_failed", error=str(e))
            raise

    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number."""
        log.info("get_issue", number=issue_number)

        try:
            gh_issue = await _run_sync(lambda: self._repo.get_issue(issue_number))
            return self._convert_issue(gh_issue)

        except GithubException as e:
            log.error("github_get_issue_failed", number=issue_number, error=str(e))
            raise

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create a new issue."""
        log.info("create_issue", title=title, labels=labels)

        try:
            gh_issue = await _run_sync(
                lambda: self._repo.create_issue(
                    title=title,
                    body=body,
                    labels=labels or [],
                )
            )
            return self._convert_issue(gh_issue)

        except GithubException as e:
            log.error("github_create_issue_failed", error=str(e))
            raise

    async def update_issue(
        self,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
        state: str | None = None,
    ) -> Issue:
        """Update issue fields."""
        log.info("update_issue", number=issue_number)

        try:

            def _update() -> GHIssue:
                gh_issue = self._repo.get_issue(issue_number)

                # Update fields if provided
                if title is not None:
                    gh_issue.edit(title=title)
                if body is not None:
                    gh_issue.edit(body=body)
                if labels is not None:
                    gh_issue.edit(labels=labels)
                if state is not None:
                    gh_issue.edit(state=state)

                # Refresh to get updated data
                return self._repo.get_issue(issue_number)

            gh_issue = await _run_sync(_update)
            return self._convert_issue(gh_issue)

        except GithubException as e:
            log.error("github_update_issue_failed", number=issue_number, error=str(e))
            raise

    async def add_comment(self, issue_number: int, comment: str) -> Comment:
        """Add comment to issue."""
        log.info("add_comment", number=issue_number)

        try:

            def _add_comment() -> GHComment:
                gh_issue = self._repo.get_issue(issue_number)
                return gh_issue.create_comment(comment)

            gh_comment = await _run_sync(_add_comment)
            return self._convert_comment(gh_comment)

        except GithubException as e:
            log.error("github_add_comment_failed", number=issue_number, error=str(e))
            raise

    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Retrieve all comments for an issue."""
        log.info("get_comments", number=issue_number)

        try:

            def _get_comments() -> list[GHComment]:
                gh_issue = self._repo.get_issue(issue_number)
                return list(gh_issue.get_comments())

            gh_comments = await _run_sync(_get_comments)
            return [self._convert_comment(c) for c in gh_comments]

        except GithubException as e:
            log.error("github_get_comments_failed", number=issue_number, error=str(e))
            raise

    async def create_branch(self, branch_name: str, from_branch: str) -> Branch:
        """Create a new branch."""
        log.info("create_branch", branch=branch_name, from_branch=from_branch)

        try:

            def _create_branch() -> GHBranch:
                # Get the source branch reference
                source_ref = self._repo.get_git_ref(f"heads/{from_branch}")
                source_sha = source_ref.object.sha

                # Create new branch from source SHA
                self._repo.create_git_ref(
                    ref=f"refs/heads/{branch_name}",
                    sha=source_sha,
                )

                # Get branch details
                return self._repo.get_branch(branch_name)

            gh_branch = await _run_sync(_create_branch)
            return self._convert_branch(gh_branch)

        except GithubException as e:
            log.error(
                "github_create_branch_failed",
                branch=branch_name,
                from_branch=from_branch,
                error=str(e),
            )
            raise

    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information."""
        log.info("get_branch", branch=branch_name)

        try:
            gh_branch = await _run_sync(lambda: self._repo.get_branch(branch_name))
            return self._convert_branch(gh_branch)

        except GithubException as e:
            if e.status == 404:
                log.debug("github_branch_not_found", branch=branch_name)
                return None
            log.error("github_get_branch_failed", branch=branch_name, error=str(e))
            raise

    async def get_diff(self, base: str, head: str) -> str:
        """Get diff between two branches."""
        log.info("get_diff", base=base, head=head)

        try:

            def _get_diff() -> str:
                comparison = self._repo.compare(base, head)

                # Build unified diff from files
                diff_parts = []
                for file in comparison.files:
                    if file.patch:
                        diff_parts.append(f"diff --git a/{file.filename} b/{file.filename}")
                        diff_parts.append(file.patch)

                return "\n".join(diff_parts)

            return await _run_sync(_get_diff)

        except GithubException as e:
            log.error("github_get_diff_failed", base=base, head=head, error=str(e))
            raise

    async def merge_branches(
        self,
        source: str,
        target: str,
        message: str,
    ) -> None:
        """Merge source branch into target."""
        log.info("merge_branches", source=source, target=target)

        try:
            # GitHub doesn't have direct branch merge - use PR merge instead
            # For now, we'll create a temporary PR and merge it
            # Better approach: Use Git API directly

            # Create merge commit
            await _run_sync(
                lambda: self._repo.merge(
                    base=target,
                    head=source,
                    commit_message=message,
                )
            )

        except GithubException as e:
            log.error(
                "github_merge_branches_failed",
                source=source,
                target=target,
                error=str(e),
            )
            raise

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> PullRequest:
        """Create a pull request."""
        log.info("create_pull_request", title=title, head=head, base=base)

        try:

            def _create_pr() -> GHPullRequest:
                gh_pr = self._repo.create_pull(
                    title=title,
                    body=body,
                    head=head,
                    base=base,
                )

                # Add labels if provided
                if labels:
                    gh_pr.add_to_labels(*labels)

                return gh_pr

            gh_pr = await _run_sync(_create_pr)
            return self._convert_pull_request(gh_pr)

        except GithubException as e:
            log.error("github_create_pr_failed", error=str(e))
            raise

    async def get_pull_request(self, pr_number: int) -> PullRequest:
        """Get pull request by number."""
        log.info("get_pull_request", number=pr_number)

        try:

            def _get_pr() -> GHPullRequest:
                return self._repo.get_pull(pr_number)

            gh_pr = await _run_sync(_get_pr)
            return self._convert_pull_request(gh_pr)

        except GithubException as e:
            log.error("github_get_pr_failed", number=pr_number, error=str(e))
            raise

    async def get_file(self, path: str, ref: str = "main") -> str:
        """Read file contents from repository."""
        log.info("get_file", path=path, ref=ref)

        try:

            def _get_file() -> str:
                contents = self._repo.get_contents(path, ref=ref)

                # Handle if it's a file (not directory)
                if isinstance(contents, list):
                    raise ValueError(f"Path {path} is a directory, not a file")

                return contents.decoded_content.decode("utf-8")

            return await _run_sync(_get_file)

        except GithubException as e:
            log.error("github_get_file_failed", path=path, ref=ref, error=str(e))
            raise

    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> str:
        """Commit file to repository."""
        log.info("commit_file", path=path, branch=branch)

        try:

            def _commit_file() -> str:
                # Check if file exists
                try:
                    existing_file = self._repo.get_contents(path, ref=branch)
                    # Update existing file
                    result = self._repo.update_file(
                        path=path,
                        message=message,
                        content=content,
                        sha=existing_file.sha,
                        branch=branch,
                    )
                except GithubException as e:
                    if e.status == 404:
                        # Create new file
                        result = self._repo.create_file(
                            path=path,
                            message=message,
                            content=content,
                            branch=branch,
                        )
                    else:
                        raise

                return result["commit"].sha

            return await _run_sync(_commit_file)

        except GithubException as e:
            log.error("github_commit_file_failed", path=path, branch=branch, error=str(e))
            raise

    async def set_repository_secret(self, name: str, value: str) -> None:
        """Set repository secret for GitHub Actions.

        Note: PyGithub handles encryption internally via its PyNaCl dependency.
        """
        log.info("set_repository_secret", name=name)

        try:
            # Create or update the secret (PyGithub handles encryption via PyNaCl)
            await _run_sync(
                lambda: self._repo.create_secret(
                    secret_name=name,
                    unencrypted_value=value,
                    secret_type="actions",  # nosec B106 # Literal constant for GitHub API, not a password
                )
            )
            log.info("github_secret_set", name=name)

        except GithubException as e:
            log.error("github_set_secret_failed", name=name, error=str(e))
            raise

    async def setup_automation_labels(
        self,
        labels: list[str] | None = None,
    ) -> dict[str, int]:
        """Set up automation labels in the repository.

        Creates the specified labels if they don't exist. Uses distinct colors
        for each label type to make them visually distinguishable.

        Args:
            labels: List of label names. If None, creates default automation labels.

        Returns:
            Dict mapping label names to their IDs.
        """
        # Default automation labels with distinct colors
        default_labels = {
            "needs-planning": "5319e7",  # Purple - needs attention
            "awaiting-approval": "fbca04",  # Yellow - waiting
            "approved": "0e8a16",  # Green - ready to go
            "in-progress": "1d76db",  # Blue - working on it
            "done": "0e8a16",  # Green - complete
            "proposed": "c5def5",  # Light blue - proposal
        }

        if labels is None:
            labels = list(default_labels.keys())

        # Get existing labels
        existing_labels = {label.name: label.id for label in await _run_sync(lambda: list(self._repo.get_labels()))}

        result: dict[str, int] = {}
        for name in labels:
            if name in existing_labels:
                log.debug("label_exists", name=name)
                result[name] = existing_labels[name]
            else:
                # Create new label with appropriate color
                color = default_labels.get(name, "ededed")  # Default gray if not in defaults
                log.info("creating_automation_label", name=name, color=color)
                new_label = await _run_sync(
                    lambda n=name, c=color: self._repo.create_label(
                        name=n,
                        color=c,
                        description=f"Automation label: {n}",
                    )
                )
                result[name] = new_label.id

        return result

    def _convert_issue(self, gh_issue: GHIssue) -> Issue:
        """Convert GitHub Issue to our Issue model."""
        # Map GitHub state to our IssueState
        if gh_issue.state == "open":
            state = IssueState.OPEN
        elif gh_issue.state == "closed":
            state = IssueState.CLOSED
        else:
            state = IssueState.OPEN

        # Extract labels
        labels = [label.name for label in gh_issue.labels]

        return Issue(
            id=gh_issue.id,
            number=gh_issue.number,
            title=gh_issue.title,
            body=gh_issue.body or "",
            state=state,
            labels=labels,
            created_at=gh_issue.created_at,
            updated_at=gh_issue.updated_at,
            author=gh_issue.user.login if gh_issue.user else "unknown",
            url=gh_issue.html_url,
        )

    def _convert_comment(self, gh_comment: GHComment) -> Comment:
        """Convert GitHub Comment to our Comment model."""
        return Comment(
            id=gh_comment.id,
            body=gh_comment.body,
            author=gh_comment.user.login if gh_comment.user else "unknown",
            created_at=gh_comment.created_at,
        )

    def _convert_branch(self, gh_branch: GHBranch) -> Branch:
        """Convert GitHub Branch to our Branch model."""
        return Branch(
            name=gh_branch.name,
            sha=gh_branch.commit.sha,
            protected=gh_branch.protected,
        )

    def _convert_pull_request(self, gh_pr: GHPullRequest) -> PullRequest:
        """Convert GitHub PullRequest to our PullRequest model."""
        return PullRequest(
            id=gh_pr.id,
            number=gh_pr.number,
            title=gh_pr.title,
            body=gh_pr.body or "",
            state=gh_pr.state,
            head=gh_pr.head.ref,
            base=gh_pr.base.ref,
            url=gh_pr.html_url,
            created_at=gh_pr.created_at,
            author=gh_pr.user.login if gh_pr.user else "",
        )
