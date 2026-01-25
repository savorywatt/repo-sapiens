"""Unit tests for PRFixStage.

This module provides comprehensive tests for the PR fix stage which handles
dynamic response to review comments when PRs have the 'needs-fix' label.

Coverage targets:
- PRFixStage initialization
- execute method (happy path, edge cases, error handling)
- _post_summary_comment
- _reply_to_comments and _reply_to_single_comment
- _execute_simple_fixes and _execute_single_fix
- _commit_fixes
- _update_labels_after_fixes
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.stages.pr_fix import PRFixStage
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.models.domain import Comment, Issue, IssueState, PullRequest
from repo_sapiens.models.review import CommentAnalysis, CommentCategory, ReviewAnalysisResult

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_git_provider():
    """Create a mock GitProvider with all required methods."""
    mock = AsyncMock()

    mock.get_comments.return_value = []
    mock.add_comment.return_value = Comment(
        id=1,
        body="Test comment",
        author="bot",
        created_at=datetime.now(UTC),
    )
    mock.add_comment_reply.return_value = None
    mock.update_issue.return_value = None
    mock.get_issue.return_value = Issue(
        id=42,
        number=42,
        title="Test PR",
        body="PR body",
        state=IssueState.OPEN,
        labels=["needs-fix"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/42",
    )
    mock.get_pull_request.return_value = PullRequest(
        id=1,
        number=10,
        title="Test PR",
        body="PR body",
        head="feature-branch",
        base="main",
        state="open",
        url="https://gitea.test/pulls/10",
        created_at=datetime.now(UTC),
        mergeable=True,
        merged=False,
    )

    return mock


@pytest.fixture
def mock_agent_provider():
    """Create a mock AgentProvider with all required methods."""
    mock = AsyncMock()

    mock.execute_prompt = AsyncMock(return_value={"success": True, "output": "Fix applied"})
    mock.working_dir = "/tmp/workspace"

    return mock


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager."""
    mock = AsyncMock(spec=StateManager)

    mock.load_state.return_value = {
        "plan_id": "42",
        "status": "in_progress",
        "tasks": {},
        "stages": {},
    }

    mock.save_state.return_value = None
    mock.mark_stage_complete.return_value = None
    mock.mark_task_status.return_value = None

    return mock


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock AutomationSettings."""
    return AutomationSettings(
        git_provider={
            "provider_type": "gitea",
            "mcp_server": "test-mcp",
            "base_url": "https://gitea.test.com",
            "api_token": "test-token",
        },
        repository={
            "owner": "test-owner",
            "name": "test-repo",
            "default_branch": "main",
        },
        agent_provider={
            "provider_type": "claude-local",
            "model": "claude-sonnet-4.5",
            "api_key": "test-key",  # pragma: allowlist secret
            "local_mode": True,
        },
        workflow={
            "plans_directory": str(tmp_path / "plans"),
            "state_directory": str(tmp_path / "state"),
            "branching_strategy": "per-agent",
            "max_concurrent_tasks": 3,
            "review_approval_threshold": 0.8,
        },
        tags={
            "needs_planning": "needs-planning",
            "plan_review": "plan-review",
            "ready_to_implement": "ready-to-implement",
            "in_progress": "in-progress",
            "code_review": "code-review",
            "merge_ready": "merge-ready",
            "completed": "completed",
            "needs_attention": "needs-attention",
        },
    )


@pytest.fixture
def needs_fix_issue():
    """Create an issue with needs-fix label."""
    return Issue(
        id=10,
        number=10,
        title="Test PR Title",
        body="PR description",
        state=IssueState.OPEN,
        labels=["needs-fix"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test/issues/10",
    )


@pytest.fixture
def sample_comments():
    """Create sample review comments."""
    return [
        Comment(
            id=100,
            body="Please fix the typo in variable name",
            author="reviewer1",
            created_at=datetime.now(UTC),
        ),
        Comment(
            id=101,
            body="Consider adding error handling here",
            author="reviewer2",
            created_at=datetime.now(UTC),
        ),
    ]


@pytest.fixture
def sample_analysis():
    """Create a sample ReviewAnalysisResult."""
    simple_fix = CommentAnalysis(
        comment_id=100,
        comment_author="reviewer1",
        comment_body="Please fix the typo in variable name",
        category=CommentCategory.SIMPLE_FIX,
        reasoning="This is a straightforward typo fix",
        proposed_action="Rename variable from 'usr' to 'user'",
        file_path="src/main.py",
        line_number=42,
    )

    controversial_fix = CommentAnalysis(
        comment_id=101,
        comment_author="reviewer2",
        comment_body="Consider changing the architecture",
        category=CommentCategory.CONTROVERSIAL_FIX,
        reasoning="This would require significant refactoring",
        proposed_action="Refactor to use dependency injection",
    )

    question = CommentAnalysis(
        comment_id=102,
        comment_author="reviewer3",
        comment_body="Why did you use this approach?",
        category=CommentCategory.QUESTION,
        reasoning="Clarifying design decision",
        proposed_action="Provide explanation",
        answer="This approach was chosen for performance reasons",
    )

    info_comment = CommentAnalysis(
        comment_id=103,
        comment_author="reviewer1",
        comment_body="Nice implementation!",
        category=CommentCategory.INFO,
        reasoning="Positive feedback, no action needed",
        proposed_action="Acknowledge",
    )

    already_done = CommentAnalysis(
        comment_id=104,
        comment_author="reviewer2",
        comment_body="Add type hints",
        category=CommentCategory.ALREADY_DONE,
        reasoning="Type hints are already present",
        proposed_action="Point out existing type hints",
    )

    wont_fix = CommentAnalysis(
        comment_id=105,
        comment_author="reviewer3",
        comment_body="Use a different library",
        category=CommentCategory.WONT_FIX,
        reasoning="Current library meets requirements",
        proposed_action="Explain why current library is preferred",
    )

    return ReviewAnalysisResult(
        pr_number=10,
        total_comments=6,
        reviewer_comments=6,
        simple_fixes=[simple_fix],
        controversial_fixes=[controversial_fix],
        questions=[question],
        info_comments=[info_comment],
        already_done=[already_done],
        wont_fix=[wont_fix],
    )


# ==============================================================================
# PRFixStage Initialization Tests
# ==============================================================================


class TestPRFixStageInitialization:
    """Tests for PRFixStage initialization."""

    def test_init_with_valid_providers(self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings):
        """Test stage initializes correctly with all required providers."""
        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert stage.git is mock_git_provider
        assert stage.agent is mock_agent_provider
        assert stage.state is mock_state_manager
        assert stage.settings is mock_settings

    def test_inherits_from_workflow_stage(
        self, mock_git_provider, mock_agent_provider, mock_state_manager, mock_settings
    ):
        """Test that PRFixStage is a proper WorkflowStage subclass."""
        from repo_sapiens.engine.stages.base import WorkflowStage

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        assert isinstance(stage, WorkflowStage)


# ==============================================================================
# PRFixStage.execute() Tests
# ==============================================================================


class TestPRFixStageExecute:
    """Tests for PRFixStage.execute method."""

    @pytest.mark.asyncio
    async def test_skip_already_processing(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that issues with fixes-in-progress label are skipped."""
        issue = Issue(
            id=10,
            number=10,
            title="Test PR",
            body="PR body",
            state=IssueState.OPEN,
            labels=["needs-fix", "fixes-in-progress"],  # Already processing
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/10",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(issue)

        # Should not process - no update_issue or get_comments calls
        mock_git_provider.get_comments.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_comments_posts_warning(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        needs_fix_issue,
    ):
        """Test that absence of comments posts a warning and removes labels."""
        mock_git_provider.get_comments.return_value = []

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage.execute(needs_fix_issue)

        # Should add fixes-in-progress then remove both labels
        assert mock_git_provider.update_issue.call_count >= 2

        # Should propose fix when no comments exist (new behavior)
        add_comment_calls = mock_git_provider.add_comment.call_args_list
        assert any("Analyzing Issue for Fix" in str(call) for call in add_comment_calls)

    @pytest.mark.asyncio
    async def test_successful_analysis_flow(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        needs_fix_issue,
        sample_comments,
        sample_analysis,
    ):
        """Test successful comment analysis and processing flow."""
        mock_git_provider.get_comments.return_value = sample_comments

        # Modify analysis to have no executable fixes (skip _execute_simple_fixes)
        analysis_no_fixes = ReviewAnalysisResult(
            pr_number=10,
            total_comments=2,
            reviewer_comments=2,
            questions=[sample_analysis.questions[0]],
            info_comments=[sample_analysis.info_comments[0]],
        )

        with patch("repo_sapiens.engine.stages.pr_fix.CommentAnalyzer") as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.analyze_comments.return_value = analysis_no_fixes
            mock_analyzer_class.return_value = mock_analyzer

            stage = PRFixStage(
                git=mock_git_provider,
                agent=mock_agent_provider,
                state=mock_state_manager,
                settings=mock_settings,
            )

            await stage.execute(needs_fix_issue)

            # Should analyze comments
            mock_analyzer.analyze_comments.assert_called_once()

            # Should post summary comment
            add_comment_calls = mock_git_provider.add_comment.call_args_list
            assert any("Analysis Complete" in str(call) for call in add_comment_calls)

    @pytest.mark.asyncio
    async def test_error_handling_posts_failure_comment(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        needs_fix_issue,
    ):
        """Test that errors result in failure comment and label cleanup."""
        mock_git_provider.get_comments.side_effect = Exception("API Error")

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        with pytest.raises(Exception, match="API Error"):
            await stage.execute(needs_fix_issue)

        # Should post error comment
        add_comment_calls = mock_git_provider.add_comment.call_args_list
        assert any("Fix Processing Failed" in str(call) for call in add_comment_calls)

        # Should remove fixes-in-progress label
        update_calls = mock_git_provider.update_issue.call_args_list
        # Last update should remove fixes-in-progress
        assert len(update_calls) >= 1


# ==============================================================================
# _post_summary_comment Tests
# ==============================================================================


class TestPostSummaryComment:
    """Tests for _post_summary_comment method."""

    @pytest.mark.asyncio
    async def test_summary_with_all_categories(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        sample_analysis,
    ):
        """Test summary includes all comment categories."""
        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._post_summary_comment(10, sample_analysis)

        mock_git_provider.add_comment.assert_called_once()
        comment_text = mock_git_provider.add_comment.call_args[0][1]

        assert "Review Comment Analysis Complete" in comment_text
        assert "6" in comment_text  # reviewer_comments count
        assert "simple fixes" in comment_text
        assert "controversial fixes" in comment_text
        assert "questions" in comment_text
        assert "info comments" in comment_text
        assert "already done" in comment_text
        assert "won't fix" in comment_text

    @pytest.mark.asyncio
    async def test_summary_with_only_simple_fixes(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test summary when only simple fixes exist."""
        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            simple_fixes=[
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Fix typo",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Simple typo",
                    proposed_action="Fix it",
                )
            ],
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._post_summary_comment(10, analysis)

        comment_text = mock_git_provider.add_comment.call_args[0][1]
        assert "simple fixes" in comment_text
        assert "controversial" not in comment_text
        assert "questions" not in comment_text


# ==============================================================================
# _reply_to_comments Tests
# ==============================================================================


class TestReplyToComments:
    """Tests for _reply_to_comments and _reply_to_single_comment methods."""

    @pytest.mark.asyncio
    async def test_reply_to_simple_fix(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for simple fix comments."""
        comment = CommentAnalysis(
            comment_id=100,
            comment_author="reviewer",
            comment_body="Fix the typo",
            category=CommentCategory.SIMPLE_FIX,
            reasoning="Straightforward typo fix",
            proposed_action="Rename variable",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        mock_git_provider.add_comment_reply.assert_called_once()
        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Will fix" in reply_text
        assert "Rename variable" in reply_text
        assert "immediately" in reply_text
        assert comment.reply_posted is True

    @pytest.mark.asyncio
    async def test_reply_to_controversial_fix(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for controversial fix comments."""
        comment = CommentAnalysis(
            comment_id=101,
            comment_author="reviewer",
            comment_body="Refactor the module",
            category=CommentCategory.CONTROVERSIAL_FIX,
            reasoning="Major architectural change",
            proposed_action="Implement dependency injection",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Needs approval" in reply_text
        assert "Implement dependency injection" in reply_text
        assert "approved" in reply_text.lower()

    @pytest.mark.asyncio
    async def test_reply_to_question(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for question comments."""
        comment = CommentAnalysis(
            comment_id=102,
            comment_author="reviewer",
            comment_body="Why this approach?",
            category=CommentCategory.QUESTION,
            reasoning="Design clarification needed",
            proposed_action="Explain reasoning",
            answer="This approach optimizes for performance",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Answer" in reply_text
        assert "optimizes for performance" in reply_text

    @pytest.mark.asyncio
    async def test_reply_to_info_comment(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for info comments."""
        comment = CommentAnalysis(
            comment_id=103,
            comment_author="reviewer",
            comment_body="Good work!",
            category=CommentCategory.INFO,
            reasoning="Positive feedback",
            proposed_action="Acknowledge",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Acknowledged" in reply_text
        assert "Thank you" in reply_text

    @pytest.mark.asyncio
    async def test_reply_to_already_done(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for already_done comments."""
        comment = CommentAnalysis(
            comment_id=104,
            comment_author="reviewer",
            comment_body="Add type hints",
            category=CommentCategory.ALREADY_DONE,
            reasoning="Type hints already present in code",
            proposed_action="Point to existing hints",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Already done" in reply_text
        assert "already addressed" in reply_text

    @pytest.mark.asyncio
    async def test_reply_to_wont_fix(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for wont_fix comments."""
        comment = CommentAnalysis(
            comment_id=105,
            comment_author="reviewer",
            comment_body="Use library X",
            category=CommentCategory.WONT_FIX,
            reasoning="Current library meets requirements",
            proposed_action="Explain library choice",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]

        assert "Won't fix" in reply_text
        assert "Explain library choice" in reply_text

    @pytest.mark.asyncio
    async def test_reply_fallback_on_error(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test fallback to regular comment when reply fails."""
        mock_git_provider.add_comment_reply.side_effect = Exception("Reply failed")

        comment = CommentAnalysis(
            comment_id=100,
            comment_author="reviewer",
            comment_body="Fix typo",
            category=CommentCategory.SIMPLE_FIX,
            reasoning="Simple fix",
            proposed_action="Fix it",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        # Should fall back to add_comment
        mock_git_provider.add_comment.assert_called_once()
        fallback_text = mock_git_provider.add_comment.call_args[0][1]
        assert "@reviewer" in fallback_text

    @pytest.mark.asyncio
    async def test_reply_to_unknown_category(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test reply generation for unknown category (fallback case)."""
        # Create a mock comment with an unhandled category
        # We need to mock the category check since all categories are handled
        comment = MagicMock()
        comment.comment_id = 999
        comment.comment_author = "reviewer"
        comment.category = MagicMock()  # Unknown category
        comment.category.__eq__ = lambda self, other: False  # Never matches
        comment.reasoning = "Unknown reasoning"

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_single_comment(comment)

        reply_text = mock_git_provider.add_comment_reply.call_args[0][1]
        assert "Analyzed" in reply_text


# ==============================================================================
# _execute_simple_fixes Tests
# ==============================================================================


class TestExecuteSimpleFixes:
    """Tests for _execute_simple_fixes method."""

    @pytest.mark.asyncio
    async def test_no_simple_fixes_returns_early(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that empty simple_fixes list returns early."""
        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=0,
            reviewer_comments=0,
            simple_fixes=[],  # No fixes
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._execute_simple_fixes(10, analysis)

        # Should not attempt to get PR or execute anything
        mock_git_provider.get_pull_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_playground_raises_error(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that missing playground directory raises error."""
        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            simple_fixes=[
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Fix typo",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Typo",
                    proposed_action="Fix",
                )
            ],
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        # The playground path is computed relative to the module file
        # This will fail because git checkout fails without a valid repo
        with pytest.raises(Exception, match="(Playground|CalledProcessError|non-zero exit)"):
            await stage._execute_simple_fixes(10, analysis)

    @pytest.mark.asyncio
    async def test_execute_fixes_full_flow(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test full fix execution flow with mocked subprocess."""
        # Create a fake playground directory
        playground = tmp_path / "playground"
        playground.mkdir()

        fix = CommentAnalysis(
            comment_id=100,
            comment_author="reviewer",
            comment_body="Fix typo in variable",
            category=CommentCategory.SIMPLE_FIX,
            reasoning="Simple typo",
            proposed_action="Rename usr to user",
            file_path="src/main.py",
            line_number=42,
        )

        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            simple_fixes=[fix],
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        # Mock the playground path and run_command
        with patch.object(Path, "__truediv__", return_value=playground):
            with patch("repo_sapiens.engine.stages.pr_fix.run_command") as mock_run_command:
                # Set up run_command to return proper values
                mock_run_command.return_value = ("", "", 0)

                # Mock Path existence check
                with patch.object(Path, "exists", return_value=True):
                    # We need to patch at module level
                    with patch("repo_sapiens.engine.stages.pr_fix.Path") as MockPath:
                        mock_playground = MagicMock()
                        mock_playground.exists.return_value = True
                        MockPath.return_value.parent.parent.parent.parent.parent.__truediv__.return_value = (
                            mock_playground
                        )

                        await stage._execute_simple_fixes(10, analysis)

                        # Verify agent was called to execute fix
                        mock_agent_provider.execute_prompt.assert_called()


# ==============================================================================
# _execute_single_fix Tests
# ==============================================================================


class TestExecuteSingleFix:
    """Tests for _execute_single_fix method."""

    @pytest.mark.asyncio
    async def test_execute_single_fix_success(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test successful single fix execution."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": True,
            "output": "Fixed the typo",
        }

        fix = CommentAnalysis(
            comment_id=100,
            comment_author="reviewer",
            comment_body="Fix typo",
            category=CommentCategory.SIMPLE_FIX,
            reasoning="Typo fix",
            proposed_action="Rename variable",
            file_path="src/main.py",
            line_number=42,
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._execute_single_fix(fix, 10)

        # Verify prompt was executed
        mock_agent_provider.execute_prompt.assert_called_once()
        prompt_arg = mock_agent_provider.execute_prompt.call_args[0][0]

        assert "#10" in prompt_arg
        assert "Fix typo" in prompt_arg
        assert "Rename variable" in prompt_arg
        assert "src/main.py" in prompt_arg
        assert "42" in prompt_arg

        # Verify fix was marked as executed
        assert fix.executed is True
        assert fix.execution_result == "success"

    @pytest.mark.asyncio
    async def test_execute_single_fix_failure(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test failed single fix execution."""
        mock_agent_provider.execute_prompt.return_value = {
            "success": False,
            "error": "Could not find file",
        }

        fix = CommentAnalysis(
            comment_id=100,
            comment_author="reviewer",
            comment_body="Fix something",
            category=CommentCategory.SIMPLE_FIX,
            reasoning="Fix",
            proposed_action="Fix it",
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._execute_single_fix(fix, 10)

        assert fix.executed is True
        assert "failed" in fix.execution_result
        assert "Could not find file" in fix.execution_result


# ==============================================================================
# _commit_fixes Tests
# ==============================================================================


class TestCommitFixes:
    """Tests for _commit_fixes method."""

    @pytest.mark.asyncio
    async def test_no_changes_to_commit(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test that no commit is made when there are no changes."""
        mock_run_command = AsyncMock()
        # git add succeeds, git status shows no changes (empty stdout)
        mock_run_command.side_effect = [
            ("", "", 0),  # git add
            ("", "", 0),  # git status (empty = no changes)
        ]

        with patch("repo_sapiens.engine.stages.pr_fix.run_command", mock_run_command):
            stage = PRFixStage(
                git=mock_git_provider,
                agent=mock_agent_provider,
                state=mock_state_manager,
                settings=mock_settings,
            )

            fixes = [
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Fix",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Fix",
                    proposed_action="Fix",
                )
            ]

            await stage._commit_fixes(tmp_path, "feature-branch", fixes)

            # Should only call git add and git status (2 calls), not commit/push
            assert mock_run_command.call_count == 2
            # Verify first call was 'git add'
            first_call_args = mock_run_command.call_args_list[0][0]
            assert first_call_args[0] == "git" and first_call_args[1] == "add"
            # Verify second call was 'git status'
            second_call_args = mock_run_command.call_args_list[1][0]
            assert second_call_args[0] == "git" and second_call_args[1] == "status"

    @pytest.mark.asyncio
    async def test_commit_with_changes(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        tmp_path,
    ):
        """Test successful commit when there are changes."""
        mock_run_command = AsyncMock()
        # git add succeeds, git status shows changes, commit succeeds, push succeeds
        mock_run_command.side_effect = [
            ("", "", 0),  # git add
            ("M src/main.py", "", 0),  # git status (has changes)
            ("", "", 0),  # git commit
            ("", "", 0),  # git push
        ]

        with patch("repo_sapiens.engine.stages.pr_fix.run_command", mock_run_command):
            stage = PRFixStage(
                git=mock_git_provider,
                agent=mock_agent_provider,
                state=mock_state_manager,
                settings=mock_settings,
            )

            fixes = [
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Fix typo",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Typo",
                    proposed_action="Fix",
                ),
                CommentAnalysis(
                    comment_id=101,
                    comment_author="reviewer",
                    comment_body="Add docs",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Docs",
                    proposed_action="Add",
                ),
            ]

            await stage._commit_fixes(tmp_path, "feature-branch", fixes)

            # Should have 4 calls: add, status, commit, push
            assert mock_run_command.call_count == 4

            # Verify commit call (3rd call)
            commit_call_args = mock_run_command.call_args_list[2][0]
            assert commit_call_args[0] == "git" and commit_call_args[1] == "commit"

            # Verify push call (4th call)
            push_call_args = mock_run_command.call_args_list[3][0]
            assert push_call_args[0] == "git" and push_call_args[1] == "push"
            assert "feature-branch" in push_call_args


# ==============================================================================
# _update_labels_after_fixes Tests
# ==============================================================================


class TestUpdateLabelsAfterFixes:
    """Tests for _update_labels_after_fixes method."""

    @pytest.mark.asyncio
    async def test_removes_fix_labels_no_controversial(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that needs-fix and fixes-in-progress labels are removed."""
        mock_git_provider.get_issue.return_value = Issue(
            id=10,
            number=10,
            title="Test PR",
            body="Body",
            state=IssueState.OPEN,
            labels=["needs-fix", "fixes-in-progress", "enhancement"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/10",
        )

        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            simple_fixes=[
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Fix",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Fix",
                    proposed_action="Fix",
                )
            ],
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._update_labels_after_fixes(10, analysis)

        mock_git_provider.update_issue.assert_called_once()
        update_labels = mock_git_provider.update_issue.call_args.kwargs["labels"]

        assert "needs-fix" not in update_labels
        assert "fixes-in-progress" not in update_labels
        assert "enhancement" in update_labels
        assert "needs-approval" not in update_labels

    @pytest.mark.asyncio
    async def test_adds_needs_approval_for_controversial(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
    ):
        """Test that needs-approval is added when controversial fixes exist."""
        mock_git_provider.get_issue.return_value = Issue(
            id=10,
            number=10,
            title="Test PR",
            body="Body",
            state=IssueState.OPEN,
            labels=["needs-fix", "fixes-in-progress"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="testuser",
            url="https://gitea.test/issues/10",
        )

        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            controversial_fixes=[
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Major change",
                    category=CommentCategory.CONTROVERSIAL_FIX,
                    reasoning="Needs discussion",
                    proposed_action="Refactor",
                )
            ],
        )

        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._update_labels_after_fixes(10, analysis)

        update_labels = mock_git_provider.update_issue.call_args.kwargs["labels"]
        assert "needs-approval" in update_labels


# ==============================================================================
# Integration-style Tests
# ==============================================================================


class TestPRFixStageIntegration:
    """Integration-style tests for PRFixStage workflows."""

    @pytest.mark.asyncio
    async def test_full_flow_questions_only(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        needs_fix_issue,
    ):
        """Test complete flow when only questions are present (no fixes)."""
        mock_git_provider.get_comments.return_value = [
            Comment(
                id=100,
                body="Why this approach?",
                author="reviewer",
                created_at=datetime.now(UTC),
            )
        ]

        analysis = ReviewAnalysisResult(
            pr_number=10,
            total_comments=1,
            reviewer_comments=1,
            questions=[
                CommentAnalysis(
                    comment_id=100,
                    comment_author="reviewer",
                    comment_body="Why this approach?",
                    category=CommentCategory.QUESTION,
                    reasoning="Design question",
                    proposed_action="Answer",
                    answer="Performance optimization",
                )
            ],
        )

        with patch("repo_sapiens.engine.stages.pr_fix.CommentAnalyzer") as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.analyze_comments.return_value = analysis
            mock_analyzer_class.return_value = mock_analyzer

            stage = PRFixStage(
                git=mock_git_provider,
                agent=mock_agent_provider,
                state=mock_state_manager,
                settings=mock_settings,
            )

            await stage.execute(needs_fix_issue)

            # Should complete without executing fixes
            mock_agent_provider.execute_prompt.assert_not_called()

            # Should have posted summary and reply
            assert mock_git_provider.add_comment.call_count >= 1
            assert mock_git_provider.add_comment_reply.call_count == 1

    @pytest.mark.asyncio
    async def test_reply_to_all_analysis_types(
        self,
        mock_git_provider,
        mock_agent_provider,
        mock_state_manager,
        mock_settings,
        sample_analysis,
    ):
        """Test that replies are generated for all comment types."""
        stage = PRFixStage(
            git=mock_git_provider,
            agent=mock_agent_provider,
            state=mock_state_manager,
            settings=mock_settings,
        )

        await stage._reply_to_comments(sample_analysis)

        # Should reply to all 6 comments
        assert mock_git_provider.add_comment_reply.call_count == 6
