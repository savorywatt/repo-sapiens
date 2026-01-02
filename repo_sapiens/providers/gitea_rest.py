"""Gitea provider implementation using direct REST API calls."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from repo_sapiens.models.domain import Branch, Comment, Issue, IssueState, PullRequest
from repo_sapiens.providers.base import GitProvider
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
        self.token = token
        self.owner = owner
        self.repo = repo
        self.client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        log.info("gitea_connected", base_url=self.base_url, owner=self.owner, repo=self.repo)

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues via REST API."""
        log.info("get_issues", labels=labels, state=state)

        params = {"state": state}
        if labels:
            params["labels"] = ",".join(labels)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues"
        response = await self.client.get(url, params=params)
        response.raise_for_status()

        issues_data = response.json()
        return [self._parse_issue(issue_data) for issue_data in issues_data]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number."""
        log.info("get_issue", issue_number=issue_number)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues/{issue_number}"
        response = await self.client.get(url)
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

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues"
        data = {
            "title": title,
            "body": body,
        }

        # Convert label names to IDs if labels provided
        if labels:
            label_ids = await self._get_or_create_label_ids(labels)
            data["labels"] = label_ids

        response = await self.client.post(url, json=data)
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
            labels_url = (
                f"{self.api_base}/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels"
            )
            labels_response = await self.client.put(labels_url, json={"labels": label_ids})
            labels_response.raise_for_status()

        # Update other fields if provided
        if title is not None or body is not None or state is not None:
            url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues/{issue_number}"
            data = {}

            if title is not None:
                data["title"] = title
            if body is not None:
                data["body"] = body
            if state is not None:
                data["state"] = state

            response = await self.client.patch(url, json=data)
            response.raise_for_status()

        # Fetch and return updated issue
        return await self.get_issue(issue_number)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def add_comment(self, issue_number: int, body: str) -> Comment:
        """Add comment to issue."""
        log.info("add_comment", issue_number=issue_number)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments"
        data = {"body": body}

        response = await self.client.post(url, json=data)
        response.raise_for_status()

        comment_data = response.json()
        return self._parse_comment(comment_data)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Get file content from repository."""
        log.info("get_file", path=path, ref=ref)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{path}"
        params = {"ref": ref}

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        import base64

        content_data = response.json()
        return base64.b64decode(content_data["content"]).decode("utf-8")

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Get all comments for an issue."""
        log.info("get_comments", issue_number=issue_number)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments"
        response = await self.client.get(url)
        response.raise_for_status()

        comments_data = response.json()
        return [self._parse_comment(comment_data) for comment_data in comments_data]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information."""
        log.info("get_branch", branch=branch_name)

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/branches/{branch_name}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            branch_data = response.json()
            return Branch(name=branch_data["name"], sha=branch_data["commit"]["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
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
            url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls/{pr_number}.diff"
            response = await self.client.get(url, headers={"Accept": "text/plain"})
            response.raise_for_status()
            return response.text

        # Fallback to compare API (note: may not include patches in all Gitea versions)
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/compare/{base}...{head}"
        response = await self.client.get(url)
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

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/branches/{target}/merge"
        data = {"head": source, "base": target, "message": message}

        response = await self.client.post(url, json=data)
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

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{path}"

        # Try to get existing file SHA
        sha = None
        try:
            existing = await self.client.get(url, params={"ref": branch})
            if existing.status_code == 200:
                sha = existing.json().get("sha")
        except (httpx.HTTPError, ValueError) as e:
            # File doesn't exist yet or response parsing failed, which is fine
            log.debug("file_not_exists", url=url, error=str(e))
            pass

        data = {
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "message": message,
            "branch": branch,
        }

        if sha:
            data["sha"] = sha

        response = await self.client.post(url, json=data)
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
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/branches"
        data = {
            "new_branch_name": branch_name,
            "old_branch_name": from_branch,
        }

        response = await self.client.post(url, json=data)
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

        # Check if PR already exists for this branch
        list_url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls"
        list_response = await self.client.get(list_url, params={"state": "open"})
        list_response.raise_for_status()

        existing_prs = list_response.json()
        for pr in existing_prs:
            if pr["head"]["ref"] == head and pr["base"]["ref"] == base:
                log.info("pull_request_exists", pr=pr["number"], head=head)
                # Update the existing PR with new title and body
                pr_number = pr["number"]
                update_url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
                update_data = {
                    "title": title,
                    "body": body,
                }
                update_response = await self.client.patch(update_url, json=update_data)
                update_response.raise_for_status()
                log.info("pull_request_updated", pr=pr_number)
                return self._parse_pull_request(update_response.json())

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls"
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

        if labels:
            # Convert label names to IDs
            label_ids = await self._get_or_create_label_ids(labels)
            data["labels"] = label_ids

        response = await self.client.post(url, json=data)
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

        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/pulls/{pr_number}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            pr_data = response.json()
            return self._parse_pull_request(pr_data)
        except Exception as e:
            log.debug("pr_not_found", pr=pr_number, error=str(e))
            return None

    async def _get_or_create_label_ids(self, label_names: list[str]) -> list[int]:
        """Get or create labels and return their IDs.

        Args:
            label_names: List of label names

        Returns:
            List of label IDs
        """
        # Get existing labels
        labels_url = f"{self.api_base}/repos/{self.owner}/{self.repo}/labels"
        response = await self.client.get(labels_url)
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
                create_url = f"{self.api_base}/repos/{self.owner}/{self.repo}/labels"
                create_data = {
                    "name": name,
                    "color": "ededed",  # Default gray color
                    "description": f"Auto-created label: {name}",
                }
                create_response = await self.client.post(create_url, json=create_data)
                create_response.raise_for_status()
                new_label = create_response.json()
                label_ids.append(new_label["id"])

        return label_ids

    def _parse_issue(self, data: dict[str, Any]) -> Issue:
        """Parse issue data from API response."""
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
        """Parse comment data from API response."""
        return Comment(
            id=data["id"],
            body=data["body"],
            author=data["user"]["login"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    def _parse_pull_request(self, data: dict[str, Any]) -> PullRequest:
        """Parse pull request data from API response."""
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
