"""Status reporting for posting updates to issues."""

from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class StatusReporter:
    """Report workflow status back to issues."""

    def __init__(self, git: Any) -> None:
        """Initialize with git provider.

        Args:
            git: GitProvider instance
        """
        self.git = git

    async def report_stage_start(self, issue: Any, stage: str) -> None:
        """Report that stage has started.

        Args:
            issue: Issue object
            stage: Stage name
        """
        message = f"""🤖 **Automation Update**

Stage: **{stage}**
Status: ⏳ In Progress
Started: {datetime.now(UTC).isoformat()}
"""
        await self.git.add_comment(issue.number, message.strip())
        log.info("status_reported", issue=issue.number, stage=stage, status="started")

    async def report_stage_complete(
        self, issue: Any, stage: str, details: str | None = None
    ) -> None:
        """Report that stage completed successfully.

        Args:
            issue: Issue object
            stage: Stage name
            details: Optional details to include
        """
        message = f"""🤖 **Automation Update**

Stage: **{stage}**
Status: ✅ Completed
Completed: {datetime.now(UTC).isoformat()}

{details or ""}
"""
        await self.git.add_comment(issue.number, message.strip())
        log.info("status_reported", issue=issue.number, stage=stage, status="completed")

    async def report_stage_failed(self, issue: Any, stage: str, error: str) -> None:
        """Report that stage failed.

        Args:
            issue: Issue object
            stage: Stage name
            error: Error message
        """
        message = f"""🤖 **Automation Update**

Stage: **{stage}**
Status: ❌ Failed
Failed: {datetime.now(UTC).isoformat()}

**Error:**
```
{error}
```

A team member will need to investigate and resolve this issue.
"""
        await self.git.add_comment(issue.number, message.strip())
        log.error("status_reported", issue=issue.number, stage=stage, status="failed")
