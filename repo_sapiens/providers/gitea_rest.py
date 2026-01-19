"""Gitea provider implementation using direct REST API calls."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from repo_sapiens.models.domain import Branch, Comment, Issue, IssueState, PullRequest
from repo_sapiens.providers.base import GitProvider
from repo_sapiens.utils.connection_pool import HTTPConnectionPool, get_pool
from repo_sapiens.utils.retry import async_retry

log = structlog.get_logger(__name__)


class GiteaRestProvider(GitProvider):
    """Gitea implementation using direct REST API calls."""

    def __init__(
        self,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
    ):
        """Initialize Gitea provider.

        Args:
            base_url: Gitea base URL (e.g., http://gitea.example.com)
            token: API token
            owner: Repository owner
            repo: Repository name
        """
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1"
        self.token = token.strip() if token else token
        self.owner = owner
        self.repo = repo
        self._pool: HTTPConnectionPool | None = None

    async def connect(self) -> None:
        """Initialize connection pool and verify connectivity."""
        self._pool = await get_pool(
            name=f"gitea-{self.base_url}",
            base_url=self.api_base,
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
        )
        # Verify connection works
        response = await self._pool.get("/version")
        if response.status_code != 200:
            raise ConnectionError(f"Failed to connect to Gitea: {response.status_code}")
        log.info("gitea_connected", base_url=self.base_url, owner=self.owner, repo=self.repo)

    async def disconnect(self) -> None:
        """Clear pool reference (pool manager handles actual cleanup)."""
        self._pool = None

    async def __aenter__(self) -> "GiteaRestProvider":
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
        """Retrieve issues via REST API."""
        log.info("get_issues", labels=labels, state=state)

        params: dict[str, str] = {"state": state}
        if labels:
            params["labels"] = ",".join(labels)

        response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/issues", params=params)
        response.raise_for_status()

        issues_data = response.json()
        return [self._parse_issue(issue_data) for issue_data in issues_data]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number."""
        log.info("get_issue", issue_number=issue_number)

        response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/issues/{issue_number}")
        response.raise_for_status()

        return self._parse_issue(response.json())

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create issue via REST API."""
        log.info("create_issue", title=title)

        data: dict[str, Any] = {
            "title": title,
            "body": body,
        }

        # Convert label names to IDs if labels provided
        if labels:
            label_ids = await self._get_or_create_label_ids(labels)
            data["labels"] = label_ids

        response = await self._pool.post(f"/repos/{self.owner}/{self.repo}/issues", json=data)
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
        """Update issue via REST API."""
        log.info("update_issue", issue_number=issue_number)

        # Update labels separately if provided (Gitea requires PUT to labels endpoint)
        if labels is not None:
            label_ids = await self._get_or_create_label_ids(labels)
            labels_response = await self._pool.put(
                f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels",
                json={"labels": label_ids},
            )
            labels_response.raise_for_status()

        # Update other fields if provided
        if title is not None or body is not None or state is not None:
            data: dict[str, str] = {}

            if title is not None:
                data["title"] = title
            if body is not None:
                data["body"] = body
            if state is not None:
                data["state"] = state

            response = await self._pool.patch(
                f"/repos/{self.owner}/{self.repo}/issues/{issue_number}",
                json=data,
            )
            response.raise_for_status()

        # Fetch and return updated issue
        return await self.get_issue(issue_number)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def add_comment(self, issue_number: int, body: str) -> Comment:
        """Add comment to issue."""
        log.info("add_comment", issue_number=issue_number)

        response = await self._pool.post(
            f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()

        comment_data = response.json()
        return self._parse_comment(comment_data)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Get file content from repository."""
        log.info("get_file", path=path, ref=ref)

        response = await self._pool.get(
            f"/repos/{self.owner}/{self.repo}/contents/{path}",
            params={"ref": ref},
        )
        response.raise_for_status()

        import base64

        content_data = response.json()
        return base64.b64decode(content_data["content"]).decode("utf-8")

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Get all comments for an issue."""
        log.info("get_comments", issue_number=issue_number)

        response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments")
        response.raise_for_status()

        comments_data = response.json()
        return [self._parse_comment(comment_data) for comment_data in comments_data]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information."""
        log.info("get_branch", branch=branch_name)

        try:
            response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/branches/{branch_name}")
            response.raise_for_status()

            branch_data = response.json()
            return Branch(name=branch_data["name"], sha=branch_data["commit"]["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        log.info("delete_branch", branch=branch_name)

        try:
            response = await self._pool.delete(f"/repos/{self.owner}/{self.repo}/branches/{branch_name}")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.debug("gitea_branch_not_found", branch=branch_name)
                return False
            log.error("gitea_delete_branch_failed", branch=branch_name, error=str(e))
            raise

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_diff(self, base: str, head: str, pr_number: int | None = None) -> str:
        """Get diff between two branches or for a PR.

        Args:
            base: Base branch name
            head: Head branch name
            pr_number: Optional PR number to get diff from

        Returns:
            Unified diff string
        """
        log.info("get_diff", base=base, head=head, pr=pr_number)

        if pr_number:
            # Get diff directly from PR endpoint (more reliable)
            response = await self._pool.get(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}.diff",
                headers={"Accept": "text/plain"},
            )
            response.raise_for_status()
            return response.text

        # Fallback to compare API (note: may not include patches in all Gitea versions)
        response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/compare/{base}...{head}")
        response.raise_for_status()

        compare_data = response.json()

        # Build a unified diff string from the files
        diff_parts = []
        for file in compare_data.get("files", []):
            diff_parts.append(f"diff --git a/{file['filename']} b/{file['filename']}")
            diff_parts.append(file.get("patch", ""))

        return "\n".join(diff_parts)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def merge_branches(self, source: str, target: str, message: str) -> None:
        """Merge source branch into target."""
        log.info("merge_branches", source=source, target=target)

        response = await self._pool.post(
            f"/repos/{self.owner}/{self.repo}/branches/{target}/merge",
            json={"head": source, "base": target, "message": message},
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
        """Commit file to repository."""
        log.info("commit_file", path=path, branch=branch)

        import base64

        contents_path = f"/repos/{self.owner}/{self.repo}/contents/{path}"

        # Try to get existing file SHA
        sha = None
        try:
            existing = await self._pool.get(contents_path, params={"ref": branch})
            if existing.status_code == 200:
                sha = existing.json().get("sha")
        except (httpx.HTTPError, ValueError) as e:
            # File doesn't exist yet or response parsing failed, which is fine
            log.debug("file_not_exists", path=contents_path, error=str(e))

        data: dict[str, str] = {
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "message": message,
            "branch": branch,
        }

        if sha:
            data["sha"] = sha

        response = await self._pool.post(contents_path, json=data)
        response.raise_for_status()

        result = response.json()
        return result["commit"]["sha"]

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> Branch:
        """Create a new branch."""
        log.info("create_branch", branch=branch_name, from_branch=from_branch)

        # Check if branch already exists
        existing = await self.get_branch(branch_name)
        if existing:
            log.info("branch_exists", branch=branch_name)
            return existing

        # Create new branch using Gitea's branches endpoint
        response = await self._pool.post(
            f"/repos/{self.owner}/{self.repo}/branches",
            json={
                "new_branch_name": branch_name,
                "old_branch_name": from_branch,
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
        """Create a pull request."""
        log.info("create_pull_request", title=title, head=head, base=base)

        pulls_path = f"/repos/{self.owner}/{self.repo}/pulls"

        # Check if PR already exists for this branch
        list_response = await self._pool.get(pulls_path, params={"state": "open"})
        list_response.raise_for_status()

        existing_prs = list_response.json()
        for pr in existing_prs:
            if pr["head"]["ref"] == head and pr["base"]["ref"] == base:
                log.info("pull_request_exists", pr=pr["number"], head=head)
                # Update the existing PR with new title and body
                pr_number = pr["number"]
                update_response = await self._pool.patch(
                    f"{pulls_path}/{pr_number}",
                    json={"title": title, "body": body},
                )
                update_response.raise_for_status()
                log.info("pull_request_updated", pr=pr_number)
                return self._parse_pull_request(update_response.json())

        data: dict[str, Any] = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

        if labels:
            # Convert label names to IDs
            label_ids = await self._get_or_create_label_ids(labels)
            data["labels"] = label_ids

        response = await self._pool.post(pulls_path, json=data)
        response.raise_for_status()

        pr_data = response.json()
        return self._parse_pull_request(pr_data)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_pull_request(self, pr_number: int) -> PullRequest | None:
        """Get a pull request by number.

        Args:
            pr_number: Pull request number

        Returns:
            PullRequest object or None if not found
        """
        log.info("get_pull_request", pr=pr_number)

        try:
            response = await self._pool.get(f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}")
            response.raise_for_status()
            pr_data = response.json()
            return self._parse_pull_request(pr_data)
        except Exception as e:
            log.debug("pr_not_found", pr=pr_number, error=str(e))
            return None

    async def _get_or_create_label_ids(self, label_names: list[str]) -> list[int]:
        """Get or create labels and return their numeric IDs.

        Gitea requires label IDs (not names) when creating or updating issues.
        This method resolves label names to IDs, creating any labels that
        don't already exist in the repository.

        The workflow:
            1. Fetch all existing labels from the repository
            2. Build a name->ID mapping for quick lookup
            3. For each requested label name:
               - If exists: use existing ID
               - If missing: create with default gray color, get new ID

        Args:
            label_names: List of label names to resolve. Order is preserved
                in the returned ID list.

        Returns:
            List of label IDs in the same order as the input names.

        Raises:
            httpx.HTTPStatusError: If fetching labels or creating a new label fails.

        Note:
            Auto-created labels use a default gray color (#ededed) and a
            description indicating they were auto-created. This differs from
            setup_automation_labels which uses distinct colors per label type.
        """
        labels_path = f"/repos/{self.owner}/{self.repo}/labels"

        # Get existing labels
        response = await self._pool.get(labels_path)
        response.raise_for_status()

        existing_labels = response.json()
        label_map = {label["name"]: label["id"] for label in existing_labels}

        label_ids = []
        for name in label_names:
            if name in label_map:
                # Label exists, use its ID
                label_ids.append(label_map[name])
            else:
                # Create new label
                log.info("creating_label", name=name)
                create_response = await self._pool.post(
                    labels_path,
                    json={
                        "name": name,
                        "color": "ededed",  # Default gray color
                        "description": f"Auto-created label: {name}",
                    },
                )
                create_response.raise_for_status()
                new_label = create_response.json()
                label_ids.append(new_label["id"])

        return label_ids

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

        labels_path = f"/repos/{self.owner}/{self.repo}/labels"

        # Get existing labels
        response = await self._pool.get(labels_path)
        response.raise_for_status()
        existing_labels = {label["name"]: label["id"] for label in response.json()}

        result: dict[str, int] = {}
        for name in labels:
            if name in existing_labels:
                log.debug("label_exists", name=name)
                result[name] = existing_labels[name]
            else:
                # Create new label with appropriate color
                color = default_labels.get(name, "ededed")  # Default gray if not in defaults
                log.info("creating_automation_label", name=name, color=color)
                create_response = await self._pool.post(
                    labels_path,
                    json={
                        "name": name,
                        "color": color,
                        "description": f"Automation label: {name}",
                    },
                )
                create_response.raise_for_status()
                new_label = create_response.json()
                result[name] = new_label["id"]

        return result

    def _parse_issue(self, data: dict[str, Any]) -> Issue:
        """Parse issue data from Gitea REST API response to internal Issue model.

        Transforms the raw JSON response from Gitea's /repos/{owner}/{repo}/issues
        endpoint into our normalized Issue dataclass.

        Field mappings:
            - data["id"] -> id (Gitea's internal issue ID)
            - data["number"] -> number (repository-scoped issue number)
            - data["title"] -> title
            - data["body"] -> body (empty string if None/missing)
            - data["state"] -> state ("open" -> OPEN, anything else -> CLOSED)
            - data["labels"] -> labels (list of label objects -> list of names)
            - data["created_at"] -> created_at (ISO 8601 string -> datetime)
            - data["updated_at"] -> updated_at (ISO 8601 string -> datetime)
            - data["user"]["login"] -> author (issue creator's username)
            - data["html_url"] -> url (web UI link)

        Args:
            data: Raw JSON dict from Gitea API response.

        Returns:
            Normalized Issue object for internal use.

        Note:
            Gitea timestamps use ISO 8601 format with 'Z' suffix for UTC.
            The 'Z' is replaced with '+00:00' for Python's fromisoformat().
            Labels are returned as objects with 'name', 'id', 'color' fields;
            we extract only the names for the normalized model.
        """
        return Issue(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=IssueState.OPEN if data["state"] == "open" else IssueState.CLOSED,
            labels=[label["name"] for label in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            author=data["user"]["login"],
            url=data["html_url"],
        )

    def _parse_comment(self, data: dict[str, Any]) -> Comment:
        """Parse comment data from Gitea REST API response to internal Comment model.

        Transforms the raw JSON response from Gitea's issue comments endpoint
        into our normalized Comment dataclass.

        Field mappings:
            - data["id"] -> id (Gitea's internal comment ID)
            - data["body"] -> body (Markdown content)
            - data["user"]["login"] -> author (comment author's username)
            - data["created_at"] -> created_at (ISO 8601 string -> datetime)

        Args:
            data: Raw JSON dict from Gitea API response for a single comment.

        Returns:
            Normalized Comment object for internal use.

        Note:
            Gitea also returns 'updated_at' and 'html_url' for comments, but
            these are not included in our Comment model. The 'user' object
            contains additional fields (id, email, avatar_url) not captured.
        """
        return Comment(
            id=data["id"],
            body=data["body"],
            author=data["user"]["login"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    def _parse_pull_request(self, data: dict[str, Any]) -> PullRequest:
        """Parse pull request data from Gitea REST API response to internal PullRequest model.

        Transforms the raw JSON response from Gitea's /repos/{owner}/{repo}/pulls
        endpoint into our normalized PullRequest dataclass.

        Field mappings:
            - data["id"] -> id (Gitea's internal PR ID)
            - data["number"] -> number (repository-scoped PR number)
            - data["title"] -> title
            - data["body"] -> body (empty string if None/missing)
            - data["state"] -> state (string: "open", "closed", "merged")
            - data["head"]["ref"] -> head (source branch name)
            - data["base"]["ref"] -> base (target branch name)
            - data["html_url"] -> url (web UI link)
            - data["created_at"] -> created_at (ISO 8601 string -> datetime)

        Args:
            data: Raw JSON dict from Gitea API response for a pull request.

        Returns:
            Normalized PullRequest object for internal use.

        Note:
            Gitea's head/base objects contain additional fields (repo, sha, label)
            that are not captured. The 'author' field is not populated in this
            implementation but could be extracted from data["user"]["login"].
            Gitea PRs also have 'mergeable', 'merged', 'merged_at' fields available.
        """
        return PullRequest(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=data["state"],
            head=data["head"]["ref"],
            base=data["base"]["ref"],
            url=data["html_url"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )
