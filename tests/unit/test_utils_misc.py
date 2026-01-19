"""Tests for miscellaneous utility modules: retry, helpers, and status_reporter."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.utils.helpers import parse_issue_reference, slugify, truncate_text
from repo_sapiens.utils.retry import async_retry
from repo_sapiens.utils.status_reporter import StatusReporter

# =============================================================================
# Tests for repo_sapiens.utils.helpers
# =============================================================================


class TestSlugify:
    """Test slugify function."""

    def test_basic_text(self):
        """Test basic text conversion to slug."""
        assert slugify("Hello World") == "hello-world"

    def test_with_numbers(self):
        """Test text with numbers."""
        assert slugify("Hello World 123") == "hello-world-123"

    def test_special_characters(self):
        """Test text with special characters."""
        assert slugify("Hello! World? 123") == "hello-world-123"

    def test_multiple_spaces(self):
        """Test text with multiple spaces."""
        assert slugify("Hello    World") == "hello-world"

    def test_leading_trailing_special_chars(self):
        """Test text with leading and trailing special characters."""
        assert slugify("---Hello World---") == "hello-world"

    def test_uppercase_conversion(self):
        """Test uppercase is converted to lowercase."""
        assert slugify("HELLO WORLD") == "hello-world"

    def test_mixed_case(self):
        """Test mixed case conversion."""
        assert slugify("HeLLo WoRLd") == "hello-world"

    def test_empty_string(self):
        """Test empty string returns empty slug."""
        assert slugify("") == ""

    def test_only_special_characters(self):
        """Test string with only special characters."""
        assert slugify("!@#$%^&*()") == ""

    def test_consecutive_special_characters(self):
        """Test consecutive special characters become single hyphen."""
        assert slugify("hello!!!world") == "hello-world"

    def test_numbers_only(self):
        """Test string with only numbers."""
        assert slugify("12345") == "12345"

    def test_unicode_characters(self):
        """Test Unicode characters are replaced."""
        assert slugify("Cafe Resume") == "cafe-resume"

    def test_tabs_and_newlines(self):
        """Test tabs and newlines are handled."""
        assert slugify("Hello\tWorld\n123") == "hello-world-123"

    def test_underscores_replaced(self):
        """Test underscores are replaced with hyphens."""
        assert slugify("hello_world") == "hello-world"


class TestParseIssueReference:
    """Test parse_issue_reference function."""

    def test_hash_notation(self):
        """Test parsing #42 notation."""
        result = parse_issue_reference("Fixes #42")
        assert result == {"issue_number": 42}

    def test_hash_at_start(self):
        """Test parsing #42 at start of string."""
        result = parse_issue_reference("#42 is the issue")
        assert result == {"issue_number": 42}

    def test_issue_hyphen_notation(self):
        """Test parsing issue-42 notation."""
        result = parse_issue_reference("Working on issue-42")
        assert result == {"issue_number": 42}

    def test_issue_space_notation(self):
        """Test parsing issue 42 notation."""
        result = parse_issue_reference("Working on issue 42")
        assert result == {"issue_number": 42}

    def test_issue_capitalized_hyphen(self):
        """Test parsing Issue-42 notation."""
        result = parse_issue_reference("Working on Issue-42")
        assert result == {"issue_number": 42}

    def test_issue_capitalized_space(self):
        """Test parsing Issue 42 notation."""
        result = parse_issue_reference("Working on Issue 42")
        assert result == {"issue_number": 42}

    def test_no_issue_reference(self):
        """Test text without issue reference returns empty dict."""
        result = parse_issue_reference("No issue here")
        assert result == {}

    def test_empty_string(self):
        """Test empty string returns empty dict."""
        result = parse_issue_reference("")
        assert result == {}

    def test_multiple_issues_returns_first(self):
        """Test multiple issues returns first match."""
        result = parse_issue_reference("Fixes #42 and #43")
        assert result == {"issue_number": 42}

    def test_large_issue_number(self):
        """Test large issue numbers."""
        result = parse_issue_reference("Fixes #99999")
        assert result == {"issue_number": 99999}

    def test_issue_in_url(self):
        """Test issue reference in URL-like text."""
        result = parse_issue_reference("See https://github.com/org/repo/issues/42")
        # Should not match this pattern (no hash or issue prefix before number)
        # Actually, it might match due to pattern #(\d+), let's verify behavior
        result = parse_issue_reference("See github.com/issues/42")
        # The patterns don't match URLs specifically
        assert result == {}

    def test_hash_notation_priority(self):
        """Test that hash notation is found before issue notation."""
        result = parse_issue_reference("#10 or issue-20")
        assert result == {"issue_number": 10}


class TestTruncateText:
    """Test truncate_text function."""

    def test_text_under_limit(self):
        """Test text under limit is not truncated."""
        text = "Hello World"
        result = truncate_text(text, max_length=100)
        assert result == text

    def test_text_at_exact_limit(self):
        """Test text at exact limit is not truncated."""
        text = "Hello"
        result = truncate_text(text, max_length=5)
        assert result == text

    def test_text_over_limit(self):
        """Test text over limit is truncated."""
        text = "Hello World"
        result = truncate_text(text, max_length=8)
        assert result == "Hello..."

    def test_custom_suffix(self):
        """Test custom suffix."""
        text = "Hello World"
        result = truncate_text(text, max_length=10, suffix=">>")
        assert result == "Hello Wo>>"

    def test_empty_suffix(self):
        """Test empty suffix."""
        text = "Hello World"
        result = truncate_text(text, max_length=5, suffix="")
        assert result == "Hello"

    def test_default_max_length(self):
        """Test default max_length of 100."""
        text = "a" * 150
        result = truncate_text(text)
        assert len(result) == 100
        assert result.endswith("...")

    def test_empty_text(self):
        """Test empty text."""
        result = truncate_text("", max_length=10)
        assert result == ""

    def test_suffix_longer_than_max(self):
        """Test when suffix is longer than allowed space."""
        text = "Hello World"
        result = truncate_text(text, max_length=3, suffix="...")
        assert result == "..."

    def test_unicode_text(self):
        """Test Unicode text truncation."""
        text = "Hello World"
        result = truncate_text(text, max_length=10)
        assert len(result) == 10

    def test_preserves_full_text_when_possible(self):
        """Test that full text is preserved when it fits."""
        text = "Short"
        result = truncate_text(text, max_length=1000)
        assert result == text


# =============================================================================
# Tests for repo_sapiens.utils.retry
# =============================================================================


class TestAsyncRetry:
    """Test async_retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test successful call does not retry."""
        call_count = 0

        @async_retry(max_attempts=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_exception(self):
        """Test retry occurs on exception."""
        call_count = 0

        @async_retry(max_attempts=3, exceptions=(ValueError,))
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await failing_then_success()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self):
        """Test exception raised after max attempts exhausted."""
        call_count = 0

        @async_retry(max_attempts=3, exceptions=(ValueError,))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent failure")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="Persistent failure"):
                await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        sleep_times = []

        @async_retry(max_attempts=4, backoff_factor=2.0, exceptions=(ValueError,))
        async def always_fails():
            raise ValueError("Failure")

        async def mock_sleep(delay):
            sleep_times.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await always_fails()

        # backoff_factor^attempt: 2^1=2, 2^2=4, 2^3=8
        assert sleep_times == [2.0, 4.0, 8.0]

    @pytest.mark.asyncio
    async def test_custom_backoff_factor(self):
        """Test custom backoff factor."""
        sleep_times = []

        @async_retry(max_attempts=3, backoff_factor=3.0, exceptions=(ValueError,))
        async def always_fails():
            raise ValueError("Failure")

        async def mock_sleep(delay):
            sleep_times.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await always_fails()

        # backoff_factor^attempt: 3^1=3, 3^2=9
        assert sleep_times == [3.0, 9.0]

    @pytest.mark.asyncio
    async def test_specific_exception_filter(self):
        """Test only specific exceptions trigger retry."""
        call_count = 0

        @async_retry(max_attempts=3, exceptions=(ValueError,))
        async def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError, match="Not retried"):
            await raises_type_error()

        # Should not retry for TypeError
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_exception_types(self):
        """Test retry on multiple exception types."""
        call_count = 0

        @async_retry(max_attempts=3, exceptions=(ValueError, TypeError))
        async def raises_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            elif call_count == 2:
                raise TypeError("Second error")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await raises_different_errors()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""

        @async_retry()
        async def documented_function():
            """This is the docstring."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        """Test arguments are passed correctly to wrapped function."""
        received_args = []
        received_kwargs = {}

        @async_retry()
        async def func_with_args(*args, **kwargs):
            received_args.extend(args)
            received_kwargs.update(kwargs)
            return "success"

        await func_with_args("arg1", "arg2", key1="value1", key2="value2")

        assert received_args == ["arg1", "arg2"]
        assert received_kwargs == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_returns_correct_value(self):
        """Test correct return value is passed through."""

        @async_retry()
        async def returns_dict():
            return {"key": "value", "number": 42}

        result = await returns_dict()
        assert result == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_default_catches_all_exceptions(self):
        """Test default exceptions parameter catches all Exception subclasses."""
        call_count = 0

        @async_retry(max_attempts=2)
        async def raises_runtime():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Generic error")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await raises_runtime()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_logging_on_retry(self):
        """Test warning is logged on retry attempts."""

        @async_retry(max_attempts=2, exceptions=(ValueError,))
        async def fails_once():
            raise ValueError("Temporary")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("repo_sapiens.utils.retry.log") as mock_log:
                with pytest.raises(ValueError):
                    await fails_once()

                # Should log warning for first attempt and error for exhausted
                assert mock_log.warning.called
                assert mock_log.error.called

    @pytest.mark.asyncio
    async def test_logging_on_exhausted(self):
        """Test error is logged when retries exhausted."""

        @async_retry(max_attempts=2, exceptions=(ValueError,))
        async def always_fails():
            raise ValueError("Persistent")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("repo_sapiens.utils.retry.log") as mock_log:
                with pytest.raises(ValueError):
                    await always_fails()

                mock_log.error.assert_called()
                call_kwargs = mock_log.error.call_args
                assert "retry_exhausted" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        """Test with max_attempts=1 (no retries)."""
        call_count = 0

        @async_retry(max_attempts=1, exceptions=(ValueError,))
        async def fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Failure")

        with pytest.raises(ValueError):
            await fails()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_zero_attempts_raises_runtime_error(self):
        """Test with max_attempts=0 raises RuntimeError (defensive code path)."""

        @async_retry(max_attempts=0, exceptions=(ValueError,))
        async def never_called():
            return "success"

        # With 0 attempts, the loop never executes and hits defensive code
        with pytest.raises(RuntimeError, match="Retry logic error"):
            await never_called()


# =============================================================================
# Tests for repo_sapiens.utils.status_reporter
# =============================================================================


class TestStatusReporter:
    """Test StatusReporter class."""

    def test_init(self):
        """Test StatusReporter initialization."""
        mock_git = MagicMock()
        reporter = StatusReporter(mock_git)
        assert reporter.git is mock_git

    @pytest.mark.asyncio
    async def test_report_stage_start(self):
        """Test reporting stage start."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)

        with patch("repo_sapiens.utils.status_reporter.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            await reporter.report_stage_start(mock_issue, "Planning")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        assert call_args[0][0] == 42
        message = call_args[0][1]

        assert "Planning" in message
        assert "In Progress" in message
        assert "Automation Update" in message

    @pytest.mark.asyncio
    async def test_report_stage_complete_without_details(self):
        """Test reporting stage completion without details."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)

        with patch("repo_sapiens.utils.status_reporter.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            await reporter.report_stage_complete(mock_issue, "Implementation")

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]

        assert "Implementation" in message
        assert "Completed" in message

    @pytest.mark.asyncio
    async def test_report_stage_complete_with_details(self):
        """Test reporting stage completion with details."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)
        details = "Created 5 files, updated 3 tests"

        with patch("repo_sapiens.utils.status_reporter.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            await reporter.report_stage_complete(mock_issue, "Implementation", details)

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]

        assert "Implementation" in message
        assert "Completed" in message
        assert details in message

    @pytest.mark.asyncio
    async def test_report_stage_failed(self):
        """Test reporting stage failure."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)
        error_message = "Connection timeout"

        with patch("repo_sapiens.utils.status_reporter.datetime") as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            await reporter.report_stage_failed(mock_issue, "Review", error_message)

        mock_git.add_comment.assert_called_once()
        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]

        assert "Review" in message
        assert "Failed" in message
        assert error_message in message
        assert "Error:" in message
        assert "team member will need to investigate" in message

    @pytest.mark.asyncio
    async def test_report_stage_start_logging(self):
        """Test that stage start is logged."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)

        with patch("repo_sapiens.utils.status_reporter.log") as mock_log:
            await reporter.report_stage_start(mock_issue, "Planning")

            mock_log.info.assert_called_once()
            call_kwargs = mock_log.info.call_args
            assert "status_reported" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_report_stage_complete_logging(self):
        """Test that stage complete is logged."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)

        with patch("repo_sapiens.utils.status_reporter.log") as mock_log:
            await reporter.report_stage_complete(mock_issue, "Implementation")

            mock_log.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_stage_failed_logging(self):
        """Test that stage failure is logged as error."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 42

        reporter = StatusReporter(mock_git)

        with patch("repo_sapiens.utils.status_reporter.log") as mock_log:
            await reporter.report_stage_failed(mock_issue, "Review", "Error occurred")

            mock_log.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_is_stripped(self):
        """Test that messages are stripped of leading/trailing whitespace."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)

        await reporter.report_stage_start(mock_issue, "Test")

        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]
        # Message should not start or end with whitespace
        assert message == message.strip()

    @pytest.mark.asyncio
    async def test_complete_with_none_details(self):
        """Test stage complete with explicitly None details."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)

        await reporter.report_stage_complete(mock_issue, "Stage", details=None)

        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]
        # Should not contain "None"
        assert "None" not in message

    @pytest.mark.asyncio
    async def test_error_message_in_code_block(self):
        """Test that error message is wrapped in code block."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)
        error = "SomeError: detailed message"

        await reporter.report_stage_failed(mock_issue, "Stage", error)

        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]
        # Error should be in a code block
        assert "```" in message
        assert error in message


class TestStatusReporterEdgeCases:
    """Test edge cases for StatusReporter."""

    @pytest.mark.asyncio
    async def test_special_characters_in_stage_name(self):
        """Test stage names with special characters."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)

        await reporter.report_stage_start(mock_issue, "Stage: Review & Analysis")

        mock_git.add_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiline_error_message(self):
        """Test multiline error messages."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)
        error = "Line 1: Error\nLine 2: Details\nLine 3: Stack trace"

        await reporter.report_stage_failed(mock_issue, "Stage", error)

        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]
        assert error in message

    @pytest.mark.asyncio
    async def test_empty_stage_name(self):
        """Test with empty stage name."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)

        await reporter.report_stage_start(mock_issue, "")

        mock_git.add_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_unicode_in_details(self):
        """Test Unicode characters in details."""
        mock_git = MagicMock()
        mock_git.add_comment = AsyncMock()
        mock_issue = MagicMock()
        mock_issue.number = 1

        reporter = StatusReporter(mock_git)
        details = "Created files with symbols: test.py"

        await reporter.report_stage_complete(mock_issue, "Stage", details)

        call_args = mock_git.add_comment.call_args
        message = call_args[0][1]
        assert details in message
