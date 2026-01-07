"""Gitea provider implementation using MCP."""

from datetime import datetime

import structlog

from repo_sapiens.models.domain import Branch, Comment, Issue, IssueState, PullRequest
from repo_sapiens.providers.base import GitProvider
from repo_sapiens.utils.mcp_client import MCPClient
from repo_sapiens.utils.retry import async_retry

log = structlog.get_logger(__name__)


class GiteaProvider(GitProvider):
    """Gitea implementation using MCP for all operations."""

    def __init__(
        self,
        mcp_server: str,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
    ):
        """Initialize Gitea provider.

        Args:
            mcp_server: MCP server name
            base_url: Gitea base URL
            token: API token
            owner: Repository owner
            repo: Repository name
        """
        self.mcp = MCPClient(mcp_server)
        self.base_url = base_url
        self.token = token.strip() if token else token
        self.owner = owner
        self.repo = repo

    async def connect(self) -> None:
        """Connect to MCP server."""
        await self.mcp.connect()

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[Issue]:
        """Retrieve issues via MCP."""
        log.info("get_issues", labels=labels, state=state)

        params = {
            "owner": self.owner,
            "repo": self.repo,
            "state": state,
        }

        if labels:
            params["labels"] = ",".join(labels)

        result = await self.mcp.call_tool("gitea_list_issues", **params)
        issues = result.get("issues", [])

        return [self._parse_issue(issue_data) for issue_data in issues]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_issue(self, issue_number: int) -> Issue:
        """Get single issue by number."""
        log.info("get_issue", issue_number=issue_number)

        result = await self.mcp.call_tool(
            "gitea_get_issue",
            owner=self.owner,
            repo=self.repo,
            number=issue_number,
        )

        return self._parse_issue(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create issue via MCP."""
        log.info("create_issue", title=title)

        result = await self.mcp.call_tool(
            "gitea_create_issue",
            owner=self.owner,
            repo=self.repo,
            title=title,
            body=body,
            labels=labels or [],
        )

        return self._parse_issue(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def update_issue(
        self,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        labels: list[str] | None = None,
        state: str | None = None,
    ) -> Issue:
        """Update issue via MCP with retry."""
        log.info("update_issue", issue=issue_number)

        params = {
            "owner": self.owner,
            "repo": self.repo,
            "number": issue_number,
        }

        if title is not None:
            params["title"] = title
        if body is not None:
            params["body"] = body
        if labels is not None:
            params["labels"] = labels
        if state is not None:
            params["state"] = state

        result = await self.mcp.call_tool("gitea_update_issue", **params)
        return self._parse_issue(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def add_comment(self, issue_number: int, comment: str) -> Comment:
        """Add comment to issue."""
        log.info("add_comment", issue_number=issue_number)

        result = await self.mcp.call_tool(
            "gitea_create_comment",
            owner=self.owner,
            repo=self.repo,
            number=issue_number,
            body=comment,
        )

        return self._parse_comment(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_comments(self, issue_number: int) -> list[Comment]:
        """Retrieve all comments for an issue."""
        log.info("get_comments", issue_number=issue_number)

        result = await self.mcp.call_tool(
            "gitea_list_comments",
            owner=self.owner,
            repo=self.repo,
            number=issue_number,
        )

        comments = result.get("comments", [])
        return [self._parse_comment(c) for c in comments]

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def create_branch(self, branch_name: str, from_branch: str) -> Branch:
        """Create a new branch."""
        log.info("create_branch", branch=branch_name, from_branch=from_branch)

        result = await self.mcp.call_tool(
            "gitea_create_branch",
            owner=self.owner,
            repo=self.repo,
            branch_name=branch_name,
            from_branch=from_branch,
        )

        return self._parse_branch(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_branch(self, branch_name: str) -> Branch | None:
        """Get branch information."""
        log.info("get_branch", branch=branch_name)

        try:
            result = await self.mcp.call_tool(
                "gitea_get_branch",
                owner=self.owner,
                repo=self.repo,
                branch=branch_name,
            )
            return self._parse_branch(result)
        except Exception as e:
            log.warning("branch_not_found", branch=branch_name, error=str(e))
            return None

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_diff(self, base: str, head: str) -> str:
        """Get diff between two branches."""
        log.info("get_diff", base=base, head=head)

        result = await self.mcp.call_tool(
            "gitea_compare",
            owner=self.owner,
            repo=self.repo,
            base=base,
            head=head,
        )

        return result.get("diff", "")

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def merge_branches(
        self,
        source: str,
        target: str,
        message: str,
    ) -> None:
        """Merge source branch into target."""
        log.info("merge_branches", source=source, target=target)

        await self.mcp.call_tool(
            "gitea_merge",
            owner=self.owner,
            repo=self.repo,
            source=source,
            target=target,
            message=message,
        )

        log.info("merge_completed", source=source, target=target)

    @async_retry(max_attempts=3, backoff_factor=2.0)
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

        result = await self.mcp.call_tool(
            "gitea_create_pull_request",
            owner=self.owner,
            repo=self.repo,
            title=title,
            body=body,
            head=head,
            base=base,
            labels=labels or [],
        )

        return self._parse_pull_request(result)

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Read file contents from repository."""
        log.info("get_file", path=path, ref=ref)

        result = await self.mcp.call_tool(
            "gitea_get_file",
            owner=self.owner,
            repo=self.repo,
            path=path,
            ref=ref,
        )

        return result.get("content", "")

    @async_retry(max_attempts=3, backoff_factor=2.0)
    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> str:
        """Commit file via MCP."""
        log.info("commit_file", path=path, branch=branch)

        result = await self.mcp.call_tool(
            "gitea_commit_file",
            owner=self.owner,
            repo=self.repo,
            path=path,
            content=content,
            message=message,
            branch=branch,
        )

        sha = result.get("sha", "")
        log.info("file_committed", path=path, branch=branch, sha=sha)
        return sha

    def _parse_issue(self, data: dict) -> Issue:
        """Parse issue data from API response."""
        return Issue(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=IssueState(data["state"]),
            labels=[
                label["name"] if isinstance(label, dict) else label
                for label in data.get("labels", [])
            ],
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"]),
            author=data.get("user", {}).get("login", "unknown"),
            url=data.get("html_url", ""),
        )

    def _parse_comment(self, data: dict) -> Comment:
        """Parse comment data from API response."""
        return Comment(
            id=data["id"],
            body=data["body"],
            author=data.get("user", {}).get("login", "unknown"),
            created_at=self._parse_datetime(data["created_at"]),
        )

    def _parse_branch(self, data: dict) -> Branch:
        """Parse branch data from API response."""
        return Branch(
            name=data["name"],
            sha=data.get("commit", {}).get("sha", data.get("sha", "")),
            protected=data.get("protected", False),
        )

    def _parse_pull_request(self, data: dict) -> PullRequest:
        """Parse pull request data from API response."""
        return PullRequest(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            head=data["head"]["ref"],
            base=data["base"]["ref"],
            state=data["state"],
            url=data.get("html_url", ""),
            created_at=self._parse_datetime(data["created_at"]),
            mergeable=data.get("mergeable", True),
            merged=data.get("merged", False),
        )

    @staticmethod
    def _parse_datetime(dt_string: str) -> datetime:
        """Parse datetime string from API."""
        # Handle ISO format with Z timezone
        if dt_string.endswith("Z"):
            dt_string = dt_string[:-1] + "+00:00"
        return datetime.fromisoformat(dt_string)
