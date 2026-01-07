"""GitLab provider implementation using direct REST API calls."""

import base64
import urllib.parse
from datetime import datetime
from typing import Any

import httpx
import structlog

from repo_sapiens.models.domain import Branch, Comment, Issue, IssueState, PullRequest
from repo_sapiens.providers.base import GitProvider
from repo_sapiens.utils.connection_pool import HTTPConnectionPool, get_pool
from repo_sapiens.utils.retry import async_retry

log = structlog.get_logger(__name__)


class GitLabRestProvider(GitProvider):
    """GitLab implementation using direct REST API v4 calls.

    This provider implements the GitProvider interface for GitLab repositories,
    supporting both gitlab.com and self-hosted GitLab instances.

    GitLab API differences from GitHub/Gitea:
    - Uses 'iid' (internal ID) for project-scoped issue/MR numbers
    - Uses 'description' instead of 'body' for issue content
    - Uses 'opened'/'closed' states instead of 'open'/'closed'
    - Uses 'notes' for comments (filtered to exclude system notes)
    - Uses 'merge_requests' instead of 'pull_requests'
    - Project path must be URL-encoded in API calls
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
    ):
        """Initialize GitLab provider.

        Args:
            base_url: GitLab base URL (e.g., https://gitlab.com)
            token: Personal access token with api, read_repository, write_repository scopes
            owner: Project namespace (user or group, may be nested like 'group/subgroup')
            repo: Project name
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v4"
        self.token = token
        self.owner = owner
        self.repo = repo
        # URL-encode the project path for API calls (GitLab uses encoded path)
        self.project_path = urllib.parse.quote(f"{owner}/{repo}", safe="")
        self._pool: HTTPConnectionPool | None = None

    async def connect(self) -> None:
        """Initialize connection pool and verify connectivity."""
        self._pool = await get_pool(
            name=f"gitlab-{self.base_url}",
            base_url=self.api_base,
            headers={
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json",
            },
        )
        # Verify connection works
        response = await self._pool.get("/version")
        if response.status_code != 200:
            raise ConnectionError(f"Failed to connect to GitLab: {response.status_code}")
        log.info("gitlab_connected", base_url=self.base_url, owner=self.owner, repo=self.repo)

    async def disconnect(self) -> None:
        """Clear pool reference (pool manager handles actual cleanup)."""
        self._pool = None

    async def __aenter__(self) -> "GitLabRestProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues via REST API.

        Args:
            labels: Filter by labels (all labels must match)
            state: Filter by state ("open", "closed", or "all")

        Returns:
            List of Issue objects
        """
        log.info("get_issues", labels=labels, state=state)

        # Map state to GitLab format
        gitlab_state = {"open": "opened", "closed": "closed", "all": "all"}.get(state, "opened")

        params: dict[str, str] = {"state": gitlab_state}
        if labels:
            params["labels"] = ",".join(labels)

        response = await self._pool.get(f"/projects/{self.project_path}/issues", params=params)
        response.raise_for_status()

        issues_data = response.json()
        return [self._parse_issue(issue_data) for issue_data in issues_data]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number (iid in GitLab).

        Args:
            issue_number: Issue number (iid in GitLab terminology)

        Returns:
            Issue object
        """
        log.info("get_issue", issue_number=issue_number)

        response = await self._pool.get(f"/projects/{self.project_path}/issues/{issue_number}")
        response.raise_for_status()

        return self._parse_issue(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create issue via REST API.

        Args:
            title: Issue title
            body: Issue body/description
            labels: Labels to apply

        Returns:
            Created Issue object
        """
        log.info("create_issue", title=title)

        data: dict[str, Any] = {
            "title": title,
            "description": body,  # GitLab uses 'description' not 'body'
        }

        if labels:
            data["labels"] = ",".join(labels)  # GitLab expects comma-separated string

        response = await self._pool.post(f"/projects/{self.project_path}/issues", json=data)
        response.raise_for_status()

        return self._parse_issue(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def update_issue(
        self,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
    ) -> Issue:
        """Update issue via REST API.

        Args:
            issue_number: Issue number
            title: New title (optional)
            body: New body (optional)
            state: New state - "open" or "closed" (optional)
            labels: New labels (optional)

        Returns:
            Updated Issue object
        """
        log.info("update_issue", issue_number=issue_number)

        data: dict[str, Any] = {}

        if title is not None:
            data["title"] = title
        if body is not None:
            data["description"] = body  # GitLab uses 'description'
        if state is not None:
            # GitLab uses state_event: "close" or "reopen"
            data["state_event"] = "close" if state == "closed" else "reopen"
        if labels is not None:
            data["labels"] = ",".join(labels)

        response = await self._pool.put(
            f"/projects/{self.project_path}/issues/{issue_number}",
            json=data,
        )
        response.raise_for_status()

        return self._parse_issue(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def add_comment(self, issue_number: int, body: str) -> Comment:
        """Add comment (note) to issue.

        Args:
            issue_number: Issue number
            body: Comment text (named 'body' for interface compatibility)

        Returns:
            Created Comment object
        """
        log.info("add_comment", issue_number=issue_number)

        response = await self._pool.post(
            f"/projects/{self.project_path}/issues/{issue_number}/notes",
            json={"body": body},
        )
        response.raise_for_status()

        return self._parse_comment(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Get all comments (notes) for an issue.

        GitLab includes both user comments and system-generated notes.
        This method filters to return only user comments.

        Args:
            issue_number: Issue number

        Returns:
            List of Comment objects (excludes system notes)
        """
        log.info("get_comments", issue_number=issue_number)

        response = await self._pool.get(
            f"/projects/{self.project_path}/issues/{issue_number}/notes"
        )
        response.raise_for_status()

        notes_data = response.json()
        # Filter to only user notes (exclude system notes)
        user_notes = [n for n in notes_data if not n.get("system", False)]
        return [self._parse_comment(note) for note in user_notes]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Get file content from repository.

        Args:
            path: File path in repository
            ref: Branch/commit/tag reference

        Returns:
            File contents as string
        """
        log.info("get_file", path=path, ref=ref)

        # URL-encode the file path
        encoded_path = urllib.parse.quote(path, safe="")

        response = await self._pool.get(
            f"/projects/{self.project_path}/repository/files/{encoded_path}",
            params={"ref": ref},
        )
        response.raise_for_status()

        content_data = response.json()
        return base64.b64decode(content_data["content"]).decode("utf-8")

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information.

        Args:
            branch_name: Branch name

        Returns:
            Branch object or None if not found
        """
        log.info("get_branch", branch=branch_name)

        try:
            encoded_branch = urllib.parse.quote(branch_name, safe="")
            response = await self._pool.get(
                f"/projects/{self.project_path}/repository/branches/{encoded_branch}"
            )
            response.raise_for_status()

            branch_data = response.json()
            return Branch(name=branch_data["name"], sha=branch_data["commit"]["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_diff(self, base: str, head: str, mr_number: int | None = None) -> str:
        """Get diff between two branches or for a MR.

        Args:
            base: Base branch name
            head: Head branch name
            mr_number: Optional MR number to get diff from

        Returns:
            Unified diff string
        """
        log.info("get_diff", base=base, head=head, mr=mr_number)

        if mr_number:
            # Get diff directly from MR endpoint
            response = await self._pool.get(
                f"/projects/{self.project_path}/merge_requests/{mr_number}/changes",
            )
            response.raise_for_status()
            mr_data = response.json()

            # Build diff from changes
            diff_parts = []
            for change in mr_data.get("changes", []):
                diff_parts.append(f"diff --git a/{change['old_path']} b/{change['new_path']}")
                diff_parts.append(change.get("diff", ""))

            return "\n".join(diff_parts)

        # Use compare API
        response = await self._pool.get(
            f"/projects/{self.project_path}/repository/compare",
            params={"from": base, "to": head},
        )
        response.raise_for_status()

        compare_data = response.json()

        diff_parts = []
        for diff_item in compare_data.get("diffs", []):
            diff_parts.append(f"diff --git a/{diff_item['old_path']} b/{diff_item['new_path']}")
            diff_parts.append(diff_item.get("diff", ""))

        return "\n".join(diff_parts)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def merge_branches(self, source: str, target: str, message: str) -> None:
        """Merge source branch into target.

        Note: GitLab doesn't have a direct branch merge API like Gitea.
        This uses the repository merge endpoint which performs a merge commit.

        Args:
            source: Source branch name
            target: Target branch name
            message: Merge commit message
        """
        log.info("merge_branches", source=source, target=target)

        response = await self._pool.post(
            f"/projects/{self.project_path}/repository/merge",
            json={
                "source_branch": source,
                "target_branch": target,
                "commit_message": message,
            },
        )
        response.raise_for_status()

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> str:
        """Commit file to repository.

        Creates or updates a file in the repository.

        Args:
            path: File path in repository
            content: File contents
            message: Commit message
            branch: Branch to commit to

        Returns:
            Commit SHA (or file path if SHA not available)
        """
        log.info("commit_file", path=path, branch=branch)

        encoded_path = urllib.parse.quote(path, safe="")
        contents_url = f"/projects/{self.project_path}/repository/files/{encoded_path}"

        # Check if file exists to determine create vs update
        try:
            existing = await self._pool.get(contents_url, params={"ref": branch})
            action = "update" if existing.status_code == 200 else "create"
        except (httpx.HTTPError, ValueError):
            action = "create"

        data = {
            "branch": branch,
            "content": content,
            "commit_message": message,
        }

        if action == "update":
            response = await self._pool.put(contents_url, json=data)
        else:
            response = await self._pool.post(contents_url, json=data)

        response.raise_for_status()
        result = response.json()
        return result.get("commit_id", result.get("file_path", ""))

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> Branch:
        """Create a new branch.

        Args:
            branch_name: Name of new branch
            from_branch: Source branch to branch from

        Returns:
            Created Branch object
        """
        log.info("create_branch", branch=branch_name, from_branch=from_branch)

        # Check if branch already exists
        existing = await self.get_branch(branch_name)
        if existing:
            log.info("branch_exists", branch=branch_name)
            return existing

        response = await self._pool.post(
            f"/projects/{self.project_path}/repository/branches",
            json={
                "branch": branch_name,
                "ref": from_branch,
            },
        )
        response.raise_for_status()

        branch_data = response.json()
        return Branch(name=branch_data["name"], sha=branch_data["commit"]["id"])

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        labels: list[str] | None = None,
    ) -> PullRequest:
        """Create a merge request.

        GitLab uses 'merge request' terminology instead of 'pull request'.
        This method provides interface compatibility while using the GitLab MR API.

        Args:
            title: MR title
            body: MR description
            head: Source branch
            base: Target branch
            labels: Labels to apply

        Returns:
            Created PullRequest object (representing GitLab MR)
        """
        log.info("create_merge_request", title=title, head=head, base=base)

        mrs_path = f"/projects/{self.project_path}/merge_requests"

        # Check if MR already exists for this branch
        list_response = await self._pool.get(mrs_path, params={"state": "opened"})
        list_response.raise_for_status()

        existing_mrs = list_response.json()
        for mr in existing_mrs:
            if mr["source_branch"] == head and mr["target_branch"] == base:
                log.info("merge_request_exists", mr=mr["iid"], head=head)
                # Update existing MR
                mr_number = mr["iid"]
                update_data: dict[str, Any] = {"title": title, "description": body}
                if labels:
                    update_data["labels"] = ",".join(labels)

                update_response = await self._pool.put(
                    f"{mrs_path}/{mr_number}",
                    json=update_data,
                )
                update_response.raise_for_status()
                log.info("merge_request_updated", mr=mr_number)
                return self._parse_merge_request(update_response.json())

        data: dict[str, Any] = {
            "source_branch": head,
            "target_branch": base,
            "title": title,
            "description": body,
        }

        if labels:
            data["labels"] = ",".join(labels)

        response = await self._pool.post(mrs_path, json=data)
        response.raise_for_status()

        return self._parse_merge_request(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_merge_request(self, mr_number: int) -> PullRequest | None:
        """Get a merge request by number.

        Args:
            mr_number: Merge request number (iid)

        Returns:
            PullRequest object or None if not found
        """
        log.info("get_merge_request", mr=mr_number)

        try:
            response = await self._pool.get(
                f"/projects/{self.project_path}/merge_requests/{mr_number}"
            )
            response.raise_for_status()
            return self._parse_merge_request(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.debug("mr_not_found", mr=mr_number)
                return None
            raise

    def _parse_issue(self, data: dict[str, Any]) -> Issue:
        """Parse issue data from GitLab API response.

        Handles GitLab-specific field names:
        - 'iid' -> number (project-scoped ID)
        - 'description' -> body
        - 'opened' state -> IssueState.OPEN
        - 'labels' already a list of strings (not objects)

        Args:
            data: Raw API response data

        Returns:
            Issue domain object
        """
        # GitLab uses "opened"/"closed" states
        state = IssueState.OPEN if data["state"] == "opened" else IssueState.CLOSED

        return Issue(
            id=data["id"],
            number=data["iid"],  # GitLab uses 'iid' for project-scoped ID
            title=data["title"],
            body=data.get("description", "") or "",  # GitLab uses 'description', handle None
            state=state,
            labels=data.get("labels", []),  # Already a list of strings
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            author=data["author"]["username"],
            url=data["web_url"],
        )

    def _parse_comment(self, data: dict[str, Any]) -> Comment:
        """Parse note (comment) data from GitLab API response.

        Args:
            data: Raw note API response data

        Returns:
            Comment domain object
        """
        return Comment(
            id=data["id"],
            body=data["body"],
            author=data["author"]["username"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    def _parse_merge_request(self, data: dict[str, Any]) -> PullRequest:
        """Parse merge request data from GitLab API response.

        Maps GitLab MR fields to PullRequest model:
        - 'iid' -> number
        - 'description' -> body
        - 'source_branch' -> head
        - 'target_branch' -> base

        Args:
            data: Raw MR API response data

        Returns:
            PullRequest domain object
        """
        return PullRequest(
            id=data["id"],
            number=data["iid"],
            title=data["title"],
            body=data.get("description", "") or "",  # Handle None
            state=data["state"],  # GitLab uses "opened", "closed", "merged"
            head=data["source_branch"],
            base=data["target_branch"],
            url=data["web_url"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )
