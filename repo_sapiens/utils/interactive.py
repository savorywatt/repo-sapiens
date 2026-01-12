"""Interactive Q&A system for agent-to-user communication via issue comments."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from repo_sapiens.providers.base import GitProvider

log = structlog.get_logger(__name__)


class InteractiveQAHandler:
    """Handles interactive Q&A between agents and users via issue comments."""

    def __init__(self, git: GitProvider, poll_interval: int = 30):
        """Initialize Q&A handler.

        Args:
            git: Git provider for posting/reading comments
            poll_interval: How often to poll for responses (seconds)
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

        Args:
            issue_number: Issue to post question to
            question: The question to ask
            context: Additional context about why the question is being asked
            timeout_minutes: How long to wait for response

        Returns:
            User's response or None if timeout
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

        Args:
            issue_number: Issue to post to
            message: Message to post
            message_type: Type of message (info, warning, error, success)
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

        Args:
            issue_number: Issue to report to
            task_name: Name of the task
            status: Current status (in_progress, completed, failed)
            details: Additional details
        """
        log.info("reporting_progress", issue=issue_number, task=task_name, status=status)

        message = self._format_progress_report(task_name, status, details)
        await self.git.add_comment(issue_number, message)

    def _format_question(self, question: str, context: str | None) -> str:
        """Format a question for posting."""
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
                "🤖 Posted by Builder Automation",
            ]
        )

        return "\n".join(parts)

    def _format_notification(self, message: str, message_type: str) -> str:
        """Format a notification message."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }

        icon = icons.get(message_type, "ℹ️")

        return f"{icon} **Builder Update**\n\n{message}\n\n🤖 Posted by Builder Automation"

    def _format_progress_report(
        self,
        task_name: str,
        status: str,
        details: str | None,
    ) -> str:
        """Format a progress report."""
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
                "🤖 Posted by Builder Automation",
            ]
        )

        return "\n".join(parts)

    def _is_bot_comment(self, body: str) -> bool:
        """Check if a comment is from the bot."""
        bot_markers = [
            "🤖 Posted by Builder Automation",
            "Builder Question",
            "Builder Update",
            "Task Progress",
        ]

        return any(marker in body for marker in bot_markers)
