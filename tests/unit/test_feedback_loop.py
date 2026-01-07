"""Tests for repo_sapiens/learning/feedback_loop.py."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo_sapiens.learning.feedback_loop import FeedbackLoop


@pytest.fixture
def feedback_dir(tmp_path):
    """Create temporary feedback directory."""
    return tmp_path / "feedback"


@pytest.fixture
def feedback_loop(feedback_dir):
    """Create FeedbackLoop instance with temp directory."""
    return FeedbackLoop(str(feedback_dir))


class TestFeedbackLoopInit:
    """Tests for FeedbackLoop initialization."""

    def test_creates_feedback_directory(self, tmp_path):
        """Should create feedback directory if not exists."""
        feedback_dir = tmp_path / "new_feedback"
        assert not feedback_dir.exists()

        FeedbackLoop(str(feedback_dir))

        assert feedback_dir.exists()

    def test_uses_existing_directory(self, tmp_path):
        """Should use existing directory."""
        feedback_dir = tmp_path / "existing"
        feedback_dir.mkdir()
        (feedback_dir / "existing.json").write_text("{}")

        loop = FeedbackLoop(str(feedback_dir))

        assert loop.feedback_dir == feedback_dir


class TestRecordExecution:
    """Tests for record_execution method."""

    @pytest.mark.asyncio
    async def test_records_basic_execution(self, feedback_loop, feedback_dir):
        """Should record basic execution data."""
        result = MagicMock()
        result.success = True
        result.execution_time = 5.5

        await feedback_loop.record_execution(
            task_id="task-123",
            prompt="Test prompt",
            result=result,
        )

        feedback_file = feedback_dir / "task-123.json"
        assert feedback_file.exists()

        data = json.loads(feedback_file.read_text())
        assert data["task_id"] == "task-123"
        assert data["prompt"] == "Test prompt"
        assert data["success"] is True
        assert data["execution_time"] == 5.5

    @pytest.mark.asyncio
    async def test_records_with_review(self, feedback_loop, feedback_dir):
        """Should record execution with review data."""
        result = MagicMock()
        result.success = True
        result.execution_time = 3.0

        review = MagicMock()
        review.confidence_score = 0.95
        review.issues_found = ["issue1", "issue2"]

        await feedback_loop.record_execution(
            task_id="task-456",
            prompt="Test prompt",
            result=result,
            review=review,
        )

        data = json.loads((feedback_dir / "task-456.json").read_text())
        assert data["review_score"] == 0.95
        assert data["issues_found"] == 2

    @pytest.mark.asyncio
    async def test_records_with_metadata(self, feedback_loop, feedback_dir):
        """Should record execution with metadata."""
        result = MagicMock()
        result.success = False
        result.execution_time = 1.0

        await feedback_loop.record_execution(
            task_id="task-789",
            prompt="Test prompt",
            result=result,
            metadata={"task_type": "bugfix", "priority": "high"},
        )

        data = json.loads((feedback_dir / "task-789.json").read_text())
        assert data["metadata"]["task_type"] == "bugfix"
        assert data["metadata"]["priority"] == "high"


class TestImprovePrompt:
    """Tests for improve_prompt method."""

    @pytest.mark.asyncio
    async def test_returns_default_prompt_no_history(self, feedback_loop):
        """Should return default prompt when no history."""
        task = MagicMock()
        task.id = "task-1"
        task.title = "Implement feature"
        task.description = "Add new feature"

        result = await feedback_loop.improve_prompt(task, "Base prompt")

        assert "Base prompt" in result
        assert "Implement feature" in result
        assert "Add new feature" in result

    def test_builds_default_prompt_format(self, feedback_loop):
        """Should build properly formatted default prompt."""
        task = MagicMock()
        task.id = "task-1"
        task.title = "Fix bug"
        task.description = "Fix the login bug"

        result = feedback_loop._build_default_prompt(task, "You are a developer")

        assert "You are a developer" in result
        assert "Task: Fix bug" in result
        assert "Fix the login bug" in result
        assert "best practices" in result


class TestCalculateSimilarity:
    """Tests for _calculate_similarity method."""

    def test_identical_keywords_high_similarity(self, feedback_loop):
        """Should return high similarity for overlapping keywords."""
        task = MagicMock()
        task.title = "implement user authentication"
        task.description = "add login and signup"

        feedback = {"prompt": "implement user authentication login signup"}

        similarity = feedback_loop._calculate_similarity(task, feedback)

        assert similarity > 0.5

    def test_no_overlap_low_similarity(self, feedback_loop):
        """Should return low similarity for no keyword overlap."""
        task = MagicMock()
        task.title = "database migration"
        task.description = "update schema"

        feedback = {"prompt": "frontend styling css"}

        similarity = feedback_loop._calculate_similarity(task, feedback)

        assert similarity < 0.3

    def test_same_task_type_bonus(self, feedback_loop):
        """Should add bonus for same task type."""
        task = MagicMock()
        task.title = "test"
        task.description = "test"
        task.type = "bugfix"

        feedback = {
            "prompt": "test",
            "metadata": {"task_type": "bugfix"},
        }

        similarity = feedback_loop._calculate_similarity(task, feedback)

        # Should have bonus from task type match
        assert similarity > 0


class TestExtractSuccessfulPatterns:
    """Tests for _extract_successful_patterns method."""

    def test_extracts_from_successful_tasks(self, feedback_loop):
        """Should extract patterns from successful high-score tasks."""
        similar_tasks = [
            {"success": True, "review_score": 0.9, "prompt": "Include test coverage"},
            {"success": True, "review_score": 0.85, "prompt": "Add error handling"},
            {"success": False, "review_score": 0.3, "prompt": "Skip tests"},
        ]

        patterns = feedback_loop._extract_successful_patterns(similar_tasks)

        assert len(patterns) == 2
        assert "Include test coverage" in patterns
        assert "Add error handling" in patterns

    def test_returns_empty_for_no_successful(self, feedback_loop):
        """Should return empty list when no successful tasks."""
        similar_tasks = [
            {"success": False, "review_score": 0.2, "prompt": "Bad approach"},
        ]

        patterns = feedback_loop._extract_successful_patterns(similar_tasks)

        assert patterns == []


class TestAnalyzePatterns:
    """Tests for _analyze_patterns method."""

    def test_extracts_common_phrases(self, feedback_loop):
        """Should extract common successful elements."""
        patterns = [
            "Make sure to include test coverage for all functions",
            "Add proper error handling and logging",
            "Include documentation for public methods",
        ]

        elements = feedback_loop._analyze_patterns(patterns)

        assert len(elements) > 0
        # Should find common phrases
        element_text = " ".join(elements).lower()
        assert "test coverage" in element_text or "error handling" in element_text


class TestGetLearningStats:
    """Tests for get_learning_stats method."""

    @pytest.mark.asyncio
    async def test_empty_stats(self, feedback_loop):
        """Should return zero stats for empty feedback."""
        stats = await feedback_loop.get_learning_stats()

        assert stats["total_executions"] == 0
        assert stats["successful_executions"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_review_score"] == 0.0

    @pytest.mark.asyncio
    async def test_calculates_stats(self, feedback_loop, feedback_dir):
        """Should calculate stats from feedback files."""
        # Create feedback files
        for i in range(5):
            feedback = {
                "task_id": f"task-{i}",
                "success": i < 3,  # 3 successful, 2 failed
                "review_score": 0.8 if i < 3 else 0.4,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            (feedback_dir / f"task-{i}.json").write_text(json.dumps(feedback))

        stats = await feedback_loop.get_learning_stats()

        assert stats["total_executions"] == 5
        assert stats["successful_executions"] == 3
        assert stats["success_rate"] == 0.6


class TestCleanupOldFeedback:
    """Tests for cleanup_old_feedback method."""

    @pytest.mark.asyncio
    async def test_removes_old_feedback(self, feedback_loop, feedback_dir):
        """Should remove feedback older than max_age_days."""
        # Create old feedback
        old_date = datetime.now(UTC) - timedelta(days=100)
        old_feedback = {"task_id": "old", "timestamp": old_date.isoformat()}
        (feedback_dir / "old-task.json").write_text(json.dumps(old_feedback))

        # Create recent feedback
        recent_feedback = {"task_id": "recent", "timestamp": datetime.now(UTC).isoformat()}
        (feedback_dir / "recent-task.json").write_text(json.dumps(recent_feedback))

        deleted = await feedback_loop.cleanup_old_feedback(max_age_days=30)

        assert deleted == 1
        assert not (feedback_dir / "old-task.json").exists()
        assert (feedback_dir / "recent-task.json").exists()

    @pytest.mark.asyncio
    async def test_handles_invalid_files(self, feedback_loop, feedback_dir):
        """Should skip invalid JSON files."""
        (feedback_dir / "invalid.json").write_text("not valid json")

        # Should not raise
        deleted = await feedback_loop.cleanup_old_feedback(max_age_days=0)

        assert deleted == 0
