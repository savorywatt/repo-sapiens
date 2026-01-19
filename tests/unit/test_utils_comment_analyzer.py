"""Tests for repo_sapiens.utils.comment_analyzer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.models.review import CommentAnalysis, CommentCategory, ReviewAnalysisResult
from repo_sapiens.utils.comment_analyzer import CommentAnalyzer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_git_provider():
    """Create a mock GitProvider."""
    mock = MagicMock()
    mock.get_pull_request = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_provider():
    """Create a mock AgentProvider."""
    mock = MagicMock()
    mock.execute_prompt = AsyncMock()
    return mock


@pytest.fixture
def analyzer(mock_git_provider, mock_agent_provider):
    """Create a CommentAnalyzer instance with mocked providers."""
    return CommentAnalyzer(git=mock_git_provider, agent=mock_agent_provider)


@pytest.fixture
def sample_comment_dict():
    """Create a sample comment as a dictionary."""
    return {
        "id": 123,
        "author": "reviewer1",
        "body": "Please fix the typo on line 42",
        "created_at": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def sample_comment_object():
    """Create a sample comment as an object with attributes."""
    comment = MagicMock()
    comment.id = 456
    comment.author = "maintainer1"
    comment.body = "Consider renaming this variable for clarity"
    comment.created_at = "2024-01-15T11:00:00Z"
    return comment


@pytest.fixture
def mock_pr():
    """Create a mock PullRequest."""
    pr = MagicMock()
    pr.number = 42
    pr.author = "developer1"
    return pr


# =============================================================================
# Tests for CommentAnalyzer initialization
# =============================================================================


class TestCommentAnalyzerInit:
    """Test CommentAnalyzer initialization."""

    def test_init_stores_providers(self, mock_git_provider, mock_agent_provider):
        """Test that __init__ stores git and agent providers."""
        analyzer = CommentAnalyzer(git=mock_git_provider, agent=mock_agent_provider)

        assert analyzer.git is mock_git_provider
        assert analyzer.agent is mock_agent_provider

    def test_init_with_different_providers(self):
        """Test initialization with different mock providers."""
        git1 = MagicMock()
        git2 = MagicMock()
        agent1 = MagicMock()

        analyzer1 = CommentAnalyzer(git=git1, agent=agent1)
        analyzer2 = CommentAnalyzer(git=git2, agent=agent1)

        assert analyzer1.git is git1
        assert analyzer2.git is git2
        assert analyzer1.agent is analyzer2.agent


# =============================================================================
# Tests for is_reviewer_or_maintainer
# =============================================================================


class TestIsReviewerOrMaintainer:
    """Test is_reviewer_or_maintainer method."""

    @pytest.mark.asyncio
    async def test_pr_author_is_reviewer(self, analyzer, mock_git_provider, mock_pr):
        """Test that PR author is considered a reviewer."""
        mock_git_provider.get_pull_request.return_value = mock_pr
        mock_pr.author = "developer1"

        result = await analyzer.is_reviewer_or_maintainer("developer1", 42)

        assert result is True
        mock_git_provider.get_pull_request.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_non_author_is_also_reviewer(self, analyzer, mock_git_provider, mock_pr):
        """Test that non-authors are currently allowed (permissive mode)."""
        mock_git_provider.get_pull_request.return_value = mock_pr
        mock_pr.author = "developer1"

        result = await analyzer.is_reviewer_or_maintainer("some_other_user", 42)

        # Currently returns True for all (permissive mode per TODO in source)
        assert result is True

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, analyzer, mock_git_provider):
        """Test that exceptions during check return False."""
        mock_git_provider.get_pull_request.side_effect = Exception("API error")

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = await analyzer.is_reviewer_or_maintainer("anyuser", 42)

        assert result is False
        mock_log.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_logs_warning(self, analyzer, mock_git_provider):
        """Test that exceptions are logged as warnings."""
        mock_git_provider.get_pull_request.side_effect = ValueError("Connection failed")

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            await analyzer.is_reviewer_or_maintainer("testuser", 99)

        mock_log.warning.assert_called_once()
        call_args = mock_log.warning.call_args
        assert "reviewer_check_failed" in str(call_args)
        assert "testuser" in str(call_args)


# =============================================================================
# Tests for _parse_ai_response
# =============================================================================


class TestParseAIResponse:
    """Test _parse_ai_response method."""

    def test_parse_valid_json(self, analyzer):
        """Test parsing valid JSON response."""
        output = '{"category": "simple_fix", "reasoning": "typo", "proposed_action": "fix it"}'

        result = analyzer._parse_ai_response(output)

        assert result == {
            "category": "simple_fix",
            "reasoning": "typo",
            "proposed_action": "fix it",
        }

    def test_parse_json_with_surrounding_text(self, analyzer):
        """Test parsing JSON embedded in text."""
        output = """Here is my analysis:
        {"category": "question", "reasoning": "needs clarification", "proposed_action": "ask user"}
        Let me know if you need more details.
        """

        result = analyzer._parse_ai_response(output)

        assert result is not None
        assert result["category"] == "question"
        assert result["reasoning"] == "needs clarification"

    def test_parse_json_with_extra_fields(self, analyzer):
        """Test parsing JSON with extra fields."""
        output = """{"category": "info", "reasoning": "just info", "proposed_action": "none", "extra": "ignored"}"""

        result = analyzer._parse_ai_response(output)

        assert result["category"] == "info"
        assert result["extra"] == "ignored"

    def test_parse_invalid_json_returns_none(self, analyzer):
        """Test that invalid JSON returns None."""
        output = "This is not valid JSON at all"

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = analyzer._parse_ai_response(output)

        assert result is None
        mock_log.error.assert_called_once()

    def test_parse_malformed_json_returns_none(self, analyzer):
        """Test that malformed JSON returns None."""
        output = '{"category": "simple_fix", "reasoning": missing quotes}'

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = analyzer._parse_ai_response(output)

        assert result is None

    def test_parse_empty_string_returns_none(self, analyzer):
        """Test that empty string returns None."""
        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = analyzer._parse_ai_response("")

        assert result is None

    def test_parse_json_with_newlines(self, analyzer):
        """Test parsing JSON that spans multiple lines."""
        output = """{
            "category": "controversial_fix",
            "reasoning": "changes architecture",
            "proposed_action": "refactor module",
            "file_path": "src/main.py",
            "line_number": 100
        }"""

        result = analyzer._parse_ai_response(output)

        assert result["category"] == "controversial_fix"
        assert result["file_path"] == "src/main.py"
        assert result["line_number"] == 100

    def test_parse_json_with_null_values(self, analyzer):
        """Test parsing JSON with null values."""
        output = '{"category": "info", "reasoning": "ok", "proposed_action": "none", "file_path": null}'

        result = analyzer._parse_ai_response(output)

        assert result is not None
        assert result["file_path"] is None

    def test_parse_nested_json(self, analyzer):
        """Test parsing JSON with nested structures."""
        output = '{"category": "simple_fix", "reasoning": "test", "proposed_action": "fix", "meta": {"nested": true}}'

        result = analyzer._parse_ai_response(output)

        assert result is not None
        assert result["meta"] == {"nested": True}


# =============================================================================
# Tests for _analyze_single_comment
# =============================================================================


class TestAnalyzeSingleComment:
    """Test _analyze_single_comment method."""

    @pytest.mark.asyncio
    async def test_analyze_dict_comment_success(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test successful analysis of a dict-style comment."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "simple_fix", "reasoning": "typo fix", "proposed_action": "correct spelling"}',
        }

        result = await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        assert result is not None
        assert isinstance(result, CommentAnalysis)
        assert result.comment_id == 123
        assert result.comment_author == "reviewer1"
        assert result.category == CommentCategory.SIMPLE_FIX
        assert result.reasoning == "typo fix"

    @pytest.mark.asyncio
    async def test_analyze_object_comment_success(self, analyzer, mock_agent_provider, sample_comment_object):
        """Test successful analysis of an object-style comment."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": (
                '{"category": "question", "reasoning": "needs answer", '
                '"proposed_action": "respond", "answer": "Yes, use snake_case"}'
            ),
        }

        result = await analyzer._analyze_single_comment(sample_comment_object, pr_number=10)

        assert result is not None
        assert result.comment_id == 456
        assert result.comment_author == "maintainer1"
        assert result.category == CommentCategory.QUESTION
        assert result.answer == "Yes, use snake_case"

    @pytest.mark.asyncio
    async def test_analyze_comment_agent_failure(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test handling when agent returns failure."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": False,
            "error": "Rate limit exceeded",
        }

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        assert result is None
        mock_log.error.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_comment_invalid_ai_response(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test handling when AI returns unparseable response."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": "I cannot analyze this comment properly",
        }

        with patch("repo_sapiens.utils.comment_analyzer.log"):
            result = await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_comment_exception(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test handling when an exception occurs during analysis."""
        mock_agent_provider.execute_prompt.side_effect = RuntimeError("API timeout")

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            result = await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        assert result is None
        mock_log.error.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_comment_with_file_path_and_line(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test analysis result includes file_path and line_number."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": (
                '{"category": "simple_fix", "reasoning": "add comment", '
                '"proposed_action": "add docstring", "file_path": "src/utils.py", "line_number": 25}'
            ),
        }

        result = await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        assert result is not None
        assert result.file_path == "src/utils.py"
        assert result.line_number == 25

    @pytest.mark.asyncio
    async def test_analyze_comment_prompt_includes_context(self, analyzer, mock_agent_provider, sample_comment_dict):
        """Test that the AI prompt includes correct context."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "noted", "proposed_action": "acknowledge"}',
        }

        await analyzer._analyze_single_comment(sample_comment_dict, pr_number=42)

        # Verify execute_prompt was called with correct parameters
        mock_agent_provider.execute_prompt.assert_called_once()
        call_args = mock_agent_provider.execute_prompt.call_args

        # Check prompt contains comment body
        prompt = call_args[0][0]
        assert "Please fix the typo on line 42" in prompt
        assert "reviewer1" in prompt
        assert "#42" in prompt

        # Check context
        context = call_args[1]["context"] if "context" in call_args[1] else call_args[0][1]
        assert context["pr_number"] == 42
        assert context["comment_id"] == 123

    @pytest.mark.asyncio
    async def test_analyze_comment_missing_author_uses_unknown(self, analyzer, mock_agent_provider):
        """Test that missing author defaults to 'unknown'."""
        comment = {"id": 789, "body": "Test comment"}  # No author field

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "test", "proposed_action": "none"}',
        }

        result = await analyzer._analyze_single_comment(comment, pr_number=1)

        assert result is not None
        assert result.comment_author == "unknown"

    @pytest.mark.asyncio
    async def test_analyze_comment_missing_body_uses_empty(self, analyzer, mock_agent_provider):
        """Test that missing body defaults to empty string."""
        comment = {"id": 789, "author": "user1"}  # No body field

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "empty", "proposed_action": "skip"}',
        }

        result = await analyzer._analyze_single_comment(comment, pr_number=1)

        assert result is not None
        assert result.comment_body == ""

    @pytest.mark.asyncio
    async def test_analyze_all_category_types(self, analyzer, mock_agent_provider):
        """Test that all CommentCategory types can be parsed."""
        categories = [
            ("simple_fix", CommentCategory.SIMPLE_FIX),
            ("controversial_fix", CommentCategory.CONTROVERSIAL_FIX),
            ("question", CommentCategory.QUESTION),
            ("info", CommentCategory.INFO),
            ("already_done", CommentCategory.ALREADY_DONE),
            ("wont_fix", CommentCategory.WONT_FIX),
        ]

        for cat_str, cat_enum in categories:
            comment = {"id": 1, "author": "user", "body": "test"}
            mock_agent_provider.execute_prompt.return_value = {
                "success": True,
                "output": f'{{"category": "{cat_str}", "reasoning": "test", "proposed_action": "test"}}',
            }

            result = await analyzer._analyze_single_comment(comment, pr_number=1)

            assert result is not None, f"Failed for category {cat_str}"
            assert result.category == cat_enum, f"Expected {cat_enum}, got {result.category}"


# =============================================================================
# Tests for analyze_comments
# =============================================================================


class TestAnalyzeComments:
    """Test analyze_comments method."""

    @pytest.mark.asyncio
    async def test_analyze_empty_comments_list(self, analyzer, mock_git_provider, mock_pr):
        """Test analyzing empty comments list."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        result = await analyzer.analyze_comments(pr_number=42, comments=[])

        assert isinstance(result, ReviewAnalysisResult)
        assert result.pr_number == 42
        assert result.total_comments == 0
        assert result.reviewer_comments == 0
        assert len(result.simple_fixes) == 0

    @pytest.mark.asyncio
    async def test_analyze_single_comment(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr, sample_comment_dict
    ):
        """Test analyzing a single comment."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "simple_fix", "reasoning": "typo", "proposed_action": "fix typo"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[sample_comment_dict])

        assert result.total_comments == 1
        assert result.reviewer_comments == 1
        assert len(result.simple_fixes) == 1
        assert result.simple_fixes[0].category == CommentCategory.SIMPLE_FIX

    @pytest.mark.asyncio
    async def test_analyze_multiple_comments_different_categories(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test analyzing multiple comments with different categories."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [
            {"id": 1, "author": "user1", "body": "Fix typo"},
            {"id": 2, "author": "user2", "body": "What does this do?"},
            {"id": 3, "author": "user3", "body": "Nice work!"},
            {"id": 4, "author": "user4", "body": "Refactor the architecture"},
        ]

        responses = [
            '{"category": "simple_fix", "reasoning": "typo", "proposed_action": "fix"}',
            (
                '{"category": "question", "reasoning": "needs answer", '
                '"proposed_action": "answer", "answer": "It processes data"}'
            ),
            '{"category": "info", "reasoning": "praise", "proposed_action": "acknowledge"}',
            '{"category": "controversial_fix", "reasoning": "big change", "proposed_action": "discuss"}',
        ]

        mock_agent_provider.execute_prompt.side_effect = [{"success": True, "output": r} for r in responses]

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        assert result.total_comments == 4
        assert result.reviewer_comments == 4
        assert len(result.simple_fixes) == 1
        assert len(result.questions) == 1
        assert len(result.info_comments) == 1
        assert len(result.controversial_fixes) == 1

    @pytest.mark.asyncio
    async def test_analyze_comments_with_failed_analysis(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test that failed analyses are excluded from results."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [
            {"id": 1, "author": "user1", "body": "Good comment"},
            {"id": 2, "author": "user2", "body": "Bad comment"},
        ]

        mock_agent_provider.execute_prompt.side_effect = [
            {"success": True, "output": '{"category": "info", "reasoning": "ok", "proposed_action": "ack"}'},
            {"success": False, "error": "Failed"},  # This one fails
        ]

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        assert result.total_comments == 2
        assert result.reviewer_comments == 2
        # Only one successful analysis
        assert len(result.info_comments) == 1

    @pytest.mark.asyncio
    async def test_analyze_comments_filters_non_reviewers(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test that non-reviewer comments are filtered (when implemented)."""
        # Currently permissive, so all pass through
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [
            {"id": 1, "author": "reviewer", "body": "Please fix"},
        ]

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "simple_fix", "reasoning": "fix", "proposed_action": "fix"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        assert result.reviewer_comments == 1

    @pytest.mark.asyncio
    async def test_analyze_comments_logs_progress(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test that analysis progress is logged."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [{"id": 1, "author": "user", "body": "test"}]
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "ok", "proposed_action": "ack"}',
        }

        with patch("repo_sapiens.utils.comment_analyzer.log") as mock_log:
            await analyzer.analyze_comments(pr_number=42, comments=comments)

        # Should log at start and end
        assert mock_log.info.call_count >= 2

    @pytest.mark.asyncio
    async def test_analyze_comments_all_categories_sorted(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test that all category types are properly sorted into result."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [
            {"id": 1, "author": "u1", "body": "c1"},
            {"id": 2, "author": "u2", "body": "c2"},
            {"id": 3, "author": "u3", "body": "c3"},
            {"id": 4, "author": "u4", "body": "c4"},
            {"id": 5, "author": "u5", "body": "c5"},
            {"id": 6, "author": "u6", "body": "c6"},
        ]

        responses = [
            '{"category": "simple_fix", "reasoning": "r", "proposed_action": "a"}',
            '{"category": "controversial_fix", "reasoning": "r", "proposed_action": "a"}',
            '{"category": "question", "reasoning": "r", "proposed_action": "a"}',
            '{"category": "info", "reasoning": "r", "proposed_action": "a"}',
            '{"category": "already_done", "reasoning": "r", "proposed_action": "a"}',
            '{"category": "wont_fix", "reasoning": "r", "proposed_action": "a"}',
        ]

        mock_agent_provider.execute_prompt.side_effect = [{"success": True, "output": r} for r in responses]

        result = await analyzer.analyze_comments(pr_number=1, comments=comments)

        assert len(result.simple_fixes) == 1
        assert len(result.controversial_fixes) == 1
        assert len(result.questions) == 1
        assert len(result.info_comments) == 1
        assert len(result.already_done) == 1
        assert len(result.wont_fix) == 1

    @pytest.mark.asyncio
    async def test_analyze_comments_with_object_style_comments(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test analyzing comments that are objects with attributes."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comment = MagicMock()
        comment.id = 100
        comment.author = "objuser"
        comment.body = "Object-style comment"
        comment.created_at = "2024-01-15"

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "obj", "proposed_action": "ack"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        assert result.total_comments == 1
        assert len(result.info_comments) == 1
        assert result.info_comments[0].comment_author == "objuser"


# =============================================================================
# Edge cases and error handling
# =============================================================================


class TestCommentAnalyzerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_comment_with_none_created_at(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test handling comment with None created_at."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comment = {"id": 1, "author": "user", "body": "test", "created_at": None}

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "ok", "proposed_action": "ack"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        assert len(result.info_comments) == 1
        assert result.info_comments[0].comment_created_at is None

    @pytest.mark.asyncio
    async def test_comment_with_special_characters_in_body(
        self, analyzer, mock_git_provider, mock_agent_provider, mock_pr
    ):
        """Test handling comments with special characters."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comment = {
            "id": 1,
            "author": "user",
            "body": 'Fix the "bug" in `main()` with special chars: <>&',
        }

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "simple_fix", "reasoning": "bug fix", "proposed_action": "fix it"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        assert len(result.simple_fixes) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_unicode_content(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test handling Unicode content in comments."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comment = {"id": 1, "author": "user", "body": "Great work!"}

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "praise", "proposed_action": "thanks"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        assert len(result.info_comments) == 1

    @pytest.mark.asyncio
    async def test_very_long_comment_body(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test handling very long comment bodies."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        long_body = "x" * 10000  # 10KB comment
        comment = {"id": 1, "author": "user", "body": long_body}

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "info", "reasoning": "long", "proposed_action": "read"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        assert len(result.info_comments) == 1
        assert result.info_comments[0].comment_body == long_body

    @pytest.mark.asyncio
    async def test_invalid_category_in_ai_response(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test handling invalid category from AI response."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comment = {"id": 1, "author": "user", "body": "test"}

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "invalid_category", "reasoning": "ok", "proposed_action": "ack"}',
        }

        with patch("repo_sapiens.utils.comment_analyzer.log"):
            result = await analyzer.analyze_comments(pr_number=42, comments=[comment])

        # Invalid category should cause analysis to fail
        assert result.total_comments == 1
        assert len(result.get_all_analyses()) == 0  # No valid analyses

    def test_parse_ai_response_with_code_block(self, analyzer):
        """Test parsing AI response wrapped in code block."""
        output = """```json
{"category": "simple_fix", "reasoning": "test", "proposed_action": "fix"}
```"""

        result = analyzer._parse_ai_response(output)

        assert result is not None
        assert result["category"] == "simple_fix"

    def test_parse_ai_response_multiple_json_objects_fails(self, analyzer):
        """Test that multiple JSON objects in output cause parse failure.

        The regex `\\{.*\\}` with DOTALL matches greedily, capturing from first { to last },
        which results in invalid JSON when there are multiple objects.
        """
        output = '{"category": "first"} {"category": "second"}'

        with patch("repo_sapiens.utils.comment_analyzer.log"):
            result = analyzer._parse_ai_response(output)

        # The greedy regex matches '{"category": "first"} {"category": "second"}'
        # which is invalid JSON, so it returns None
        assert result is None


class TestReviewAnalysisResultHelpers:
    """Test ReviewAnalysisResult helper methods indirectly."""

    @pytest.mark.asyncio
    async def test_result_has_executable_fixes(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test that result correctly reports executable fixes."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [{"id": 1, "author": "user", "body": "fix typo"}]

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "simple_fix", "reasoning": "typo", "proposed_action": "fix"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        assert result.has_executable_fixes() is True
        assert result.has_controversial_fixes() is False

    @pytest.mark.asyncio
    async def test_result_has_controversial_fixes(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test that result correctly reports controversial fixes."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [{"id": 1, "author": "user", "body": "refactor everything"}]

        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": '{"category": "controversial_fix", "reasoning": "big", "proposed_action": "discuss"}',
        }

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        assert result.has_executable_fixes() is False
        assert result.has_controversial_fixes() is True

    @pytest.mark.asyncio
    async def test_result_get_all_analyses(self, analyzer, mock_git_provider, mock_agent_provider, mock_pr):
        """Test get_all_analyses returns all categorized comments."""
        mock_git_provider.get_pull_request.return_value = mock_pr

        comments = [
            {"id": 1, "author": "u1", "body": "c1"},
            {"id": 2, "author": "u2", "body": "c2"},
        ]

        mock_agent_provider.execute_prompt.side_effect = [
            {"success": True, "output": '{"category": "simple_fix", "reasoning": "r", "proposed_action": "a"}'},
            {"success": True, "output": '{"category": "info", "reasoning": "r", "proposed_action": "a"}'},
        ]

        result = await analyzer.analyze_comments(pr_number=42, comments=comments)

        all_analyses = result.get_all_analyses()
        assert len(all_analyses) == 2
