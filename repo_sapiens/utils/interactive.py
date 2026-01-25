"""Interactive Q&A system for agent-to-user communication via issue comments.

This module provides a mechanism for AI agents to interact with human users
during automated workflows by posting questions to issue comments and waiting
for responses. This enables human-in-the-loop workflows where agents can
request clarification or approval.

Key Features:
    - Post questions to issues and wait for user responses
    - Configurable timeout for response waiting
    - Progress reporting and status notifications
    - Bot comment detection to filter out automated messages

Key Exports:
    InteractiveQAHandler: Main class for handling interactive Q&A flows.

Example:
    >>> from repo_sapiens.utils.interactive import InteractiveQAHandler
    >>> handler = InteractiveQAHandler(git_provider, poll_interval=60)
    >>> response = await handler.ask_user_question(
    ...     issue_number=42,
    ...     question="Should I use async or sync implementation?",
    ...     context="Both approaches have trade-offs for this use case.",
    ...     timeout_minutes=30,
    ... )
    >>> if response:
    ...     print(f"User said: {response}")
    ... else:
    ...     print("No response within timeout")

Thread Safety:
    InteractiveQAHandler instances are not thread-safe. Use one instance
    per async context. The handler maintains no internal state between
    calls, but concurrent calls on the same instance may interfere with
    logging context.

Note:
    This module uses polling to detect new comments. For high-volume
    use cases, consider implementing webhook-based notification instead.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from repo_sapiens.providers.base import GitProvider

log = structlog.get_logger(__name__)


class InteractiveQAHandler:
    """Handles interactive Q&A between agents and users via issue comments.

    This class enables AI agents to pause their workflow, ask humans for
    input via issue comments, and resume processing once a response is
    received. It's useful for:
        - Requesting clarification on ambiguous requirements
        - Asking for approval before making significant changes
        - Gathering preferences for implementation approaches

    The handler posts formatted comments that are clearly marked as
    automated, and filters responses to exclude bot messages.

    Attributes:
        git: Git provider used for posting and reading comments.
        poll_interval: Seconds between polling for new comments.

    Example:
        >>> handler = InteractiveQAHandler(git_provider, poll_interval=30)
        >>>
        >>> # Ask a question and wait for response
        >>> response = await handler.ask_user_question(
        ...     issue_number=123,
        ...     question="Which database should I use: PostgreSQL or SQLite?",
        ...     context="This is for a small single-user application.",
        ...     timeout_minutes=60,
        ... )
        >>>
        >>> # Send notifications
        >>> await handler.notify_user(
        ...     issue_number=123,
        ...     message="Starting implementation with PostgreSQL",
        ...     message_type="info",
        ... )
        >>>
        >>> # Report progress
        >>> await handler.report_progress(
        ...     issue_number=123,
        ...     task_name="Database Setup",
        ...     status="completed",
        ...     details="PostgreSQL schema created successfully",
        ... )
    """

    def __init__(self, git: GitProvider, poll_interval: int = 30) -> None:
        """Initialize the interactive Q&A handler.

        Args:
            git: Git provider for posting and reading comments. Must support
                add_comment and get_comments methods.
            poll_interval: How often to check for new comments, in seconds.
                Lower values mean faster response detection but more API calls.
                Default is 30 seconds.

        Example:
            >>> from repo_sapiens.providers.gitea import GiteaProvider
            >>> git = GiteaProvider(base_url="https://gitea.example.com", token="...")
            >>> handler = InteractiveQAHandler(git, poll_interval=60)
        """
        self.git = git
        self.poll_interval = poll_interval

    async def ask_user_question(
        self,
        issue_number: int,
        question: str,
        context: str | None = None,
        timeout_minutes: int = 60,
    ) -> str | None:
        """Post a question to the issue and wait for user response.

        Posts a formatted question comment to the specified issue, then
        polls for new comments until a human response is detected or
        the timeout is reached.

        Args:
            issue_number: Issue number to post the question to.
            question: The question to ask the user. Should be clear and
                specific to get a useful response.
            context: Optional additional context explaining why the question
                is being asked. Helps users provide better answers.
            timeout_minutes: Maximum time to wait for a response, in minutes.
                After this time, the method returns None.

        Returns:
            The body of the first non-bot comment posted after the question,
            or None if no response was received within the timeout.

        Raises:
            Any exceptions from git.add_comment or git.get_comments are
            propagated to the caller.

        Example:
            >>> response = await handler.ask_user_question(
            ...     issue_number=42,
            ...     question="Should I include deprecated API support?",
            ...     context="Adding deprecated API support increases maintenance burden.",
            ...     timeout_minutes=120,
            ... )
            >>> if response:
            ...     if "yes" in response.lower():
            ...         print("User wants deprecated API support")
            ...     else:
            ...         print("User declined deprecated API support")
            ... else:
            ...     print("No response, proceeding with default (no deprecated APIs)")

        Note:
            The question is formatted with a header and footer that identify
            it as an automated message. Bot comments are automatically
            filtered when checking for responses.
        """
        log.info("asking_user_question", issue=issue_number)

        # Format question as a comment
        comment_body = self._format_question(question, context)

        # Post the question
        question_comment = await self.git.add_comment(issue_number, comment_body)
        question_time = question_comment.created_at

        log.info("question_posted", issue=issue_number, comment_id=question_comment.id)

        # Wait for response
        timeout = datetime.now(UTC) + timedelta(minutes=timeout_minutes)

        while datetime.now(UTC) < timeout:
            # Get all comments since our question
            comments = await self.git.get_comments(issue_number)

            # Look for responses after our question
            for comment in comments:
                if (
                    comment.created_at > question_time
                    and comment.id != question_comment.id
                    and not self._is_bot_comment(comment.body)
                ):
                    # This is a user response (doesn't start with bot markers)
                    log.info(
                        "user_response_received",
                        issue=issue_number,
                        comment_id=comment.id,
                    )
                    return comment.body

            # Wait before polling again
            await asyncio.sleep(self.poll_interval)

        log.warning("question_timeout", issue=issue_number, timeout_minutes=timeout_minutes)
        return None

    async def notify_user(
        self,
        issue_number: int,
        message: str,
        message_type: str = "info",
    ) -> None:
        """Post an informational message to the issue.

        Posts a formatted notification that doesn't expect a response.
        Useful for status updates, warnings, or completion notices.

        Args:
            issue_number: Issue number to post the notification to.
            message: The notification message content.
            message_type: Type of message, affects the icon displayed.
                Supported values: "info", "warning", "error", "success".
                Default is "info".

        Raises:
            Any exceptions from git.add_comment are propagated.

        Example:
            >>> # Informational update
            >>> await handler.notify_user(
            ...     issue_number=42,
            ...     message="Starting code review analysis",
            ...     message_type="info",
            ... )

            >>> # Warning notification
            >>> await handler.notify_user(
            ...     issue_number=42,
            ...     message="Found 3 potential security issues",
            ...     message_type="warning",
            ... )

            >>> # Success notification
            >>> await handler.notify_user(
            ...     issue_number=42,
            ...     message="All tests passing, ready for merge",
            ...     message_type="success",
            ... )

            >>> # Error notification
            >>> await handler.notify_user(
            ...     issue_number=42,
            ...     message="Build failed due to missing dependency",
            ...     message_type="error",
            ... )
        """
        log.info("notifying_user", issue=issue_number, type=message_type)

        formatted_message = self._format_notification(message, message_type)
        await self.git.add_comment(issue_number, formatted_message)

    async def report_progress(
        self,
        issue_number: int,
        task_name: str,
        status: str,
        details: str | None = None,
    ) -> None:
        """Report progress on a task to the issue.

        Posts a formatted progress update showing the current status of
        a named task. Useful for long-running operations where users
        want visibility into what's happening.

        Args:
            issue_number: Issue number to report to.
            task_name: Human-readable name of the task being performed.
            status: Current status of the task. Supported values:
                "in_progress", "completed", "failed", "blocked".
            details: Optional additional details about the current status,
                such as error messages or completion metrics.

        Raises:
            Any exceptions from git.add_comment are propagated.

        Example:
            >>> # Task started
            >>> await handler.report_progress(
            ...     issue_number=42,
            ...     task_name="Code Analysis",
            ...     status="in_progress",
            ...     details="Scanning 150 Python files",
            ... )

            >>> # Task completed
            >>> await handler.report_progress(
            ...     issue_number=42,
            ...     task_name="Code Analysis",
            ...     status="completed",
            ...     details="Found 12 issues across 5 files",
            ... )

            >>> # Task failed
            >>> await handler.report_progress(
            ...     issue_number=42,
            ...     task_name="Code Analysis",
            ...     status="failed",
            ...     details="Memory limit exceeded while processing large file",
            ... )

            >>> # Task blocked
            >>> await handler.report_progress(
            ...     issue_number=42,
            ...     task_name="Deployment",
            ...     status="blocked",
            ...     details="Waiting for approval from @maintainer",
            ... )
        """
        log.info("reporting_progress", issue=issue_number, task=task_name, status=status)

        message = self._format_progress_report(task_name, status, details)
        await self.git.add_comment(issue_number, message)

    def _format_question(self, question: str, context: str | None) -> str:
        """Format a question for posting as an issue comment.

        Args:
            question: The question text.
            context: Optional context explaining why the question is asked.

        Returns:
            Formatted markdown string ready to post as a comment.
        """
        parts = [
            "## 🤔 Builder Question",
            "",
            "The automation agent needs clarification:",
            "",
            f"**Question:** {question}",
        ]

        if context:
            parts.extend(
                [
                    "",
                    f"**Context:** {context}",
                ]
            )

        parts.extend(
            [
                "",
                "---",
                ("*Please reply to this comment with your answer. " "The agent will continue once you respond.*"),
                "",
                "◆ Posted by Sapiens Automation",
            ]
        )

        return "\n".join(parts)

    def _format_notification(self, message: str, message_type: str) -> str:
        """Format a notification message for posting.

        Args:
            message: The notification content.
            message_type: Type affecting icon choice (info/warning/error/success).

        Returns:
            Formatted markdown string ready to post as a comment.
        """
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }

        icon = icons.get(message_type, "ℹ️")

        return f"{icon} **Builder Update**\n\n{message}\n\n◆ Posted by Sapiens Automation"

    def _format_progress_report(
        self,
        task_name: str,
        status: str,
        details: str | None,
    ) -> str:
        """Format a progress report for posting.

        Args:
            task_name: Name of the task being reported on.
            status: Current status (in_progress/completed/failed/blocked).
            details: Optional additional details.

        Returns:
            Formatted markdown string ready to post as a comment.
        """
        status_icons = {
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌",
            "blocked": "⏸️",
        }

        icon = status_icons.get(status, "📋")
        status_text = status.replace("_", " ").title()

        parts = [
            f"{icon} **Task Progress**",
            "",
            f"**Task:** {task_name}",
            f"**Status:** {status_text}",
        ]

        if details:
            parts.extend(
                [
                    "",
                    f"**Details:** {details}",
                ]
            )

        parts.extend(
            [
                "",
                "◆ Posted by Sapiens Automation",
            ]
        )

        return "\n".join(parts)

    def _is_bot_comment(self, body: str) -> bool:
        """Check if a comment appears to be from the automation bot.

        Used to filter out bot comments when looking for human responses.

        Args:
            body: The comment body text.

        Returns:
            True if the comment contains bot markers, False otherwise.
        """
        bot_markers = [
            "◆ Posted by Sapiens Automation",
            "Builder Question",
            "Builder Update",
            "Task Progress",
        ]

        return any(marker in body for marker in bot_markers)
