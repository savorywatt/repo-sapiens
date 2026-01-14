"""Tests for repo_sapiens/utils/interactive.py - Interactive Q&A handler."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.models.domain import Comment
from repo_sapiens.utils.interactive import InteractiveQAHandler


class TestInteractiveQAHandlerInit:
    """Tests for InteractiveQAHandler initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default poll interval."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        assert handler.git is mock_git
        assert handler.poll_interval == 30

    def test_init_with_custom_poll_interval(self):
        """Should accept custom poll interval."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git, poll_interval=60)

        assert handler.poll_interval == 60


class TestFormatQuestion:
    """Tests for _format_question method."""

    def test_format_question_without_context(self):
        """Should format question without context."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_question("What color?", None)

        assert "## " in result
        assert "Builder Question" in result
        assert "**Question:** What color?" in result
        assert "Context" not in result
        assert "Posted by Builder Automation" in result

    def test_format_question_with_context(self):
        """Should format question with context."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_question("What color?", "Working on UI design")

        assert "**Question:** What color?" in result
        assert "**Context:** Working on UI design" in result
        assert "Posted by Builder Automation" in result

    def test_format_question_has_reply_instructions(self):
        """Should include reply instructions."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_question("Test question", None)

        assert "reply to this comment" in result
        assert "agent will continue" in result


class TestFormatNotification:
    """Tests for _format_notification method."""

    def test_format_notification_info(self):
        """Should format info notification with info icon."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_notification("Status update", "info")

        assert "Builder Update" in result
        assert "Status update" in result

    def test_format_notification_warning(self):
        """Should format warning notification."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_notification("Watch out!", "warning")

        assert "Builder Update" in result
        assert "Watch out!" in result

    def test_format_notification_error(self):
        """Should format error notification."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_notification("Failed!", "error")

        assert "Builder Update" in result
        assert "Failed!" in result

    def test_format_notification_success(self):
        """Should format success notification."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_notification("Done!", "success")

        assert "Builder Update" in result
        assert "Done!" in result

    def test_format_notification_unknown_type(self):
        """Should default to info icon for unknown type."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_notification("Message", "unknown")

        assert "Builder Update" in result
        assert "Message" in result


class TestFormatProgressReport:
    """Tests for _format_progress_report method."""

    def test_format_progress_in_progress(self):
        """Should format in_progress status."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Build", "in_progress", None)

        assert "Task Progress" in result
        assert "**Task:** Build" in result
        assert "In Progress" in result

    def test_format_progress_completed(self):
        """Should format completed status."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Deploy", "completed", None)

        assert "**Status:** Completed" in result

    def test_format_progress_failed(self):
        """Should format failed status."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Test", "failed", None)

        assert "**Status:** Failed" in result

    def test_format_progress_blocked(self):
        """Should format blocked status."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Review", "blocked", None)

        assert "**Status:** Blocked" in result

    def test_format_progress_with_details(self):
        """Should include details when provided."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Build", "in_progress", "Step 2 of 5")

        assert "**Details:** Step 2 of 5" in result

    def test_format_progress_without_details(self):
        """Should not include details section when None."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Build", "in_progress", None)

        assert "**Details:**" not in result

    def test_format_progress_unknown_status(self):
        """Should use default icon for unknown status."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._format_progress_report("Task", "unknown_status", None)

        assert "**Status:** Unknown Status" in result


class TestIsBotComment:
    """Tests for _is_bot_comment method."""

    def test_is_bot_comment_with_automation_marker(self):
        """Should recognize automation marker."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("Some text\n\n\U0001f916 Posted by Builder Automation")

        assert result is True

    def test_is_bot_comment_with_question_marker(self):
        """Should recognize question marker."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("## Builder Question\n\nWhat is the issue?")

        assert result is True

    def test_is_bot_comment_with_update_marker(self):
        """Should recognize update marker."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("Builder Update: Everything is fine.")

        assert result is True

    def test_is_bot_comment_with_progress_marker(self):
        """Should recognize progress marker."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("Task Progress: Step 1 complete.")

        assert result is True

    def test_is_not_bot_comment(self):
        """Should recognize user comment."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("I think we should use blue.")

        assert result is False

    def test_is_not_bot_comment_empty(self):
        """Should handle empty comment."""
        mock_git = MagicMock()
        handler = InteractiveQAHandler(mock_git)

        result = handler._is_bot_comment("")

        assert result is False


class TestAskUserQuestion:
    """Tests for ask_user_question async method."""

    @pytest.mark.asyncio
    async def test_ask_user_question_gets_response(self):
        """Should return user response when available."""
        mock_git = MagicMock()

        # Mock the add_comment to return a question comment
        question_time = datetime.now(UTC)
        question_comment = Comment(
            id=1,
            body="Question body",
            author="bot",
            created_at=question_time,
        )
        mock_git.add_comment = AsyncMock(return_value=question_comment)

        # Mock get_comments to return user response
        user_response = Comment(
            id=2,
            body="Blue please",
            author="user",
            created_at=question_time + timedelta(seconds=5),
        )
        mock_git.get_comments = AsyncMock(return_value=[question_comment, user_response])

        handler = InteractiveQAHandler(mock_git, poll_interval=1)

        result = await handler.ask_user_question(42, "What color?", timeout_minutes=1)

        assert result == "Blue please"
        mock_git.add_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_user_question_ignores_bot_comments(self):
        """Should ignore bot comments while waiting for response."""
        mock_git = MagicMock()

        question_time = datetime.now(UTC)
        question_comment = Comment(
            id=1,
            body="Question",
            author="bot",
            created_at=question_time,
        )
        mock_git.add_comment = AsyncMock(return_value=question_comment)

        # First call returns only bot comments, second call includes user response
        bot_comment = Comment(
            id=2,
            body="Builder Update: Processing...",
            author="bot",
            created_at=question_time + timedelta(seconds=2),
        )
        user_response = Comment(
            id=3,
            body="Red",
            author="user",
            created_at=question_time + timedelta(seconds=4),
        )

        mock_git.get_comments = AsyncMock(
            side_effect=[
                [question_comment, bot_comment],
                [question_comment, bot_comment, user_response],
            ]
        )

        handler = InteractiveQAHandler(mock_git, poll_interval=0.01)

        result = await handler.ask_user_question(42, "Color?", timeout_minutes=1)

        assert result == "Red"

    @pytest.mark.asyncio
    async def test_ask_user_question_timeout(self):
        """Should return None on timeout."""
        mock_git = MagicMock()

        question_time = datetime.now(UTC)
        question_comment = Comment(
            id=1,
            body="Question",
            author="bot",
            created_at=question_time,
        )
        mock_git.add_comment = AsyncMock(return_value=question_comment)

        # Never return a user response
        mock_git.get_comments = AsyncMock(return_value=[question_comment])

        handler = InteractiveQAHandler(mock_git, poll_interval=0.01)

        # Use very short timeout for test
        with patch(
            "repo_sapiens.utils.interactive.datetime"
        ) as mock_datetime:
            # First call: before timeout, subsequent calls: after timeout
            now = datetime.now(UTC)
            timeout = now + timedelta(minutes=1)
            mock_datetime.now.side_effect = [
                now,  # Initial timeout calculation
                timeout + timedelta(seconds=1),  # First while check - after timeout
            ]
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = await handler.ask_user_question(42, "Color?", timeout_minutes=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_ask_user_question_with_context(self):
        """Should include context in posted question."""
        mock_git = MagicMock()

        question_time = datetime.now(UTC)
        question_comment = Comment(
            id=1,
            body="Question",
            author="bot",
            created_at=question_time,
        )
        mock_git.add_comment = AsyncMock(return_value=question_comment)

        user_response = Comment(
            id=2,
            body="Yes",
            author="user",
            created_at=question_time + timedelta(seconds=1),
        )
        mock_git.get_comments = AsyncMock(return_value=[question_comment, user_response])

        handler = InteractiveQAHandler(mock_git, poll_interval=0.01)

        await handler.ask_user_question(
            42,
            "Proceed?",
            context="This will delete data",
            timeout_minutes=1,
        )

        # Verify the comment was posted with context
        call_args = mock_git.add_comment.call_args
        comment_body = call_args[0][1]
        assert "Proceed?" in comment_body
        assert "delete data" in comment_body


class TestNotifyUser:
    """Tests for notify_user async method."""

    @pytest.mark.asyncio
    async def test_notify_user_basic(self):
        """Should post notification comment."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()

        handler = InteractiveQAHandler(mock_git)

        await handler.notify_user(42, "Task complete!")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        assert call_args[0][0] == 42
        assert "Task complete!" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_notify_user_with_type(self):
        """Should use specified message type."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()

        handler = InteractiveQAHandler(mock_git)

        await handler.notify_user(42, "Warning!", message_type="warning")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        assert "Warning!" in call_args[0][1]


class TestReportProgress:
    """Tests for report_progress async method."""

    @pytest.mark.asyncio
    async def test_report_progress_basic(self):
        """Should post progress report."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()

        handler = InteractiveQAHandler(mock_git)

        await handler.report_progress(42, "Build", "in_progress")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        assert call_args[0][0] == 42
        assert "Build" in call_args[0][1]
        assert "In Progress" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_report_progress_with_details(self):
        """Should include details in progress report."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()

        handler = InteractiveQAHandler(mock_git)

        await handler.report_progress(42, "Deploy", "completed", "Deployed to staging")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        assert "Deployed to staging" in call_args[0][1]
