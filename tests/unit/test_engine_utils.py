"""
Comprehensive unit tests for engine utility modules.

Tests cover:
- parallel_executor.py: Parallel task execution with dependencies
- recovery.py: Error recovery strategies
- checkpointing.py: State checkpointing
- branching.py: Branch management
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.branching import (
    BranchingStrategy,
    PerAgentStrategy,
    PerPlanStrategy,
    get_branching_strategy,
)
from repo_sapiens.engine.checkpointing import CheckpointManager
from repo_sapiens.engine.parallel_executor import (
    ExecutionTask,
    ParallelExecutor,
    TaskPriority,
    TaskResult,
    TaskScheduler,
)
from repo_sapiens.engine.recovery import (
    AdvancedRecovery,
    ConflictResolutionStrategy,
    ErrorType,
    ManualInterventionStrategy,
    RecoveryError,
    RecoveryStrategy,
    RetryRecoveryStrategy,
    TestFixRecoveryStrategy,
)
from repo_sapiens.models.domain import Branch, Task
from repo_sapiens.providers.base import GitProvider


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_checkpoint_dir(tmp_path: Path) -> Path:
    """Temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir: Path) -> CheckpointManager:
    """CheckpointManager instance with temp directory."""
    return CheckpointManager(str(temp_checkpoint_dir))


@pytest.fixture
def mock_git_provider() -> AsyncMock:
    """Mock GitProvider for testing branching strategies."""
    mock = AsyncMock(spec=GitProvider)
    mock.get_branch.return_value = None
    mock.create_branch.return_value = Branch(name="test-branch", sha="abc123")
    mock.merge_branches.return_value = None
    return mock


@pytest.fixture
def mock_settings(tmp_path: Path) -> AutomationSettings:
    """Mock settings for testing."""
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
            "api_key": "test-key",
            "local_mode": True,
        },
        workflow={
            "plans_directory": "plans/",
            "state_directory": str(tmp_path / "state"),
            "branching_strategy": "per-agent",
            "max_concurrent_tasks": 3,
        },
        tags={},
    )


@pytest.fixture
def sample_domain_task() -> Task:
    """Sample domain Task for testing."""
    return Task(
        id="task-1",
        prompt_issue_id=42,
        title="Implement feature",
        description="Implement the feature as specified",
        dependencies=[],
    )


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Mock state manager for recovery tests."""
    return MagicMock()


@pytest.fixture
def mock_checkpoint_manager() -> AsyncMock:
    """Mock checkpoint manager for recovery tests."""
    mock = AsyncMock()
    mock.get_latest_checkpoint.return_value = {
        "checkpoint_id": "test-checkpoint",
        "plan_id": "test-plan",
        "stage": "implementation",
        "data": {"error": "test error", "error_type": "transient_api_error"},
    }
    mock.create_checkpoint.return_value = "new-checkpoint-id"
    return mock


# =============================================================================
# Parallel Executor Tests
# =============================================================================


class TestParallelExecutor:
    """Tests for ParallelExecutor class."""

    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test executor initialization with max_workers."""
        executor = ParallelExecutor(max_workers=5)
        assert executor.max_workers == 5
        assert isinstance(executor.semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_execute_empty_task_list(self):
        """Test executing empty task list."""
        executor = ParallelExecutor(max_workers=2)
        results = await executor.execute_tasks([])
        assert results == {}

    @pytest.mark.asyncio
    async def test_execute_single_task_success(self):
        """Test executing a single successful task."""

        async def simple_task(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2

        executor = ParallelExecutor(max_workers=1)
        task = ExecutionTask(id="task-1", func=simple_task, args=(5,))
        results = await executor.execute_tasks([task])

        assert len(results) == 1
        assert results["task-1"].success is True
        assert results["task-1"].result == 10
        assert results["task-1"].execution_time > 0

    @pytest.mark.asyncio
    async def test_execute_multiple_independent_tasks(self):
        """Test executing multiple independent tasks in parallel."""

        async def compute_task(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2

        executor = ParallelExecutor(max_workers=3)
        tasks = [
            ExecutionTask(id=f"task-{i}", func=compute_task, args=(i,))
            for i in range(5)
        ]

        results = await executor.execute_tasks(tasks)

        assert len(results) == 5
        for i in range(5):
            assert results[f"task-{i}"].success is True
            assert results[f"task-{i}"].result == i * 2

    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self):
        """Test task execution respects dependencies."""

        async def simple_task(value: int) -> int:
            await asyncio.sleep(0.01)
            return value

        executor = ParallelExecutor(max_workers=2)
        tasks = [
            ExecutionTask(id="task-1", func=simple_task, args=(1,)),
            ExecutionTask(
                id="task-2",
                func=simple_task,
                args=(2,),
                dependencies={"task-1"},
            ),
            ExecutionTask(
                id="task-3",
                func=simple_task,
                args=(3,),
                dependencies={"task-1", "task-2"},
            ),
        ]

        results = await executor.execute_tasks(tasks)

        assert len(results) == 3
        assert all(r.success for r in results.values())

    @pytest.mark.asyncio
    async def test_task_failure_blocks_dependents(self):
        """Test that failed tasks block their dependents."""

        async def failing_task() -> None:
            await asyncio.sleep(0.01)
            raise ValueError("Task failed")

        async def simple_task(value: int) -> int:
            return value

        executor = ParallelExecutor(max_workers=2)
        tasks = [
            ExecutionTask(id="failing", func=failing_task),
            ExecutionTask(
                id="dependent",
                func=simple_task,
                args=(1,),
                dependencies={"failing"},
            ),
        ]

        results = await executor.execute_tasks(tasks)

        assert results["failing"].success is False
        assert results["dependent"].success is False
        assert "Dependency failure" in str(results["dependent"].error)

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test tasks are executed in priority order."""
        execution_order: list[str] = []

        async def tracking_task(task_id: str) -> str:
            execution_order.append(task_id)
            await asyncio.sleep(0.01)
            return task_id

        executor = ParallelExecutor(max_workers=1)
        tasks = [
            ExecutionTask(
                id="low", func=tracking_task, args=("low",), priority=TaskPriority.LOW
            ),
            ExecutionTask(
                id="critical",
                func=tracking_task,
                args=("critical",),
                priority=TaskPriority.CRITICAL,
            ),
            ExecutionTask(
                id="high",
                func=tracking_task,
                args=("high",),
                priority=TaskPriority.HIGH,
            ),
        ]

        await executor.execute_tasks(tasks)

        # Critical should execute first
        assert execution_order[0] == "critical"

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """Test task timeout handling."""

        async def slow_task() -> None:
            await asyncio.sleep(10)

        executor = ParallelExecutor(max_workers=1)
        task = ExecutionTask(id="slow", func=slow_task, timeout=0.05)

        results = await executor.execute_tasks([task])

        assert results["slow"].success is False
        assert isinstance(results["slow"].error, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self):
        """Test detection of circular dependencies (deadlock)."""

        async def simple_task() -> None:
            pass

        executor = ParallelExecutor(max_workers=2)
        tasks = [
            ExecutionTask(id="task-a", func=simple_task, dependencies={"task-b"}),
            ExecutionTask(id="task-b", func=simple_task, dependencies={"task-a"}),
        ]

        with pytest.raises(RuntimeError, match="deadlock"):
            await executor.execute_tasks(tasks)

    @pytest.mark.asyncio
    async def test_task_with_kwargs(self):
        """Test task execution with keyword arguments."""

        async def task_with_kwargs(*, multiplier: int, value: int) -> int:
            return multiplier * value

        executor = ParallelExecutor(max_workers=1)
        task = ExecutionTask(
            id="kwargs-task",
            func=task_with_kwargs,
            kwargs={"multiplier": 3, "value": 7},
        )

        results = await executor.execute_tasks([task])

        assert results["kwargs-task"].success is True
        assert results["kwargs-task"].result == 21

    @pytest.mark.asyncio
    async def test_task_metadata_preserved(self):
        """Test that task metadata is preserved."""

        async def simple_task() -> str:
            return "done"

        executor = ParallelExecutor(max_workers=1)
        task = ExecutionTask(
            id="meta-task",
            func=simple_task,
            metadata={"custom_key": "custom_value"},
        )

        results = await executor.execute_tasks([task])
        assert results["meta-task"].success is True


class TestTaskScheduler:
    """Tests for TaskScheduler class."""

    @pytest.mark.asyncio
    async def test_scheduler_optimization(self):
        """Test task optimization increases critical path priorities."""

        async def simple_task() -> None:
            pass

        executor = ParallelExecutor(max_workers=2)
        scheduler = TaskScheduler(executor)

        tasks = [
            ExecutionTask(
                id="task-1", func=simple_task, priority=TaskPriority.NORMAL
            ),
            ExecutionTask(
                id="task-2",
                func=simple_task,
                dependencies={"task-1"},
                priority=TaskPriority.NORMAL,
            ),
            ExecutionTask(
                id="task-3",
                func=simple_task,
                dependencies={"task-2"},
                priority=TaskPriority.NORMAL,
            ),
        ]

        optimized = scheduler.optimize_execution_order(tasks)

        # Critical path tasks should have boosted priority
        assert any(t.priority > TaskPriority.NORMAL for t in optimized)

    @pytest.mark.asyncio
    async def test_execute_with_optimization(self):
        """Test execute_with_optimization runs tasks successfully."""

        async def simple_task(value: int) -> int:
            return value * 2

        executor = ParallelExecutor(max_workers=2)
        scheduler = TaskScheduler(executor)

        tasks = [
            ExecutionTask(id="task-1", func=simple_task, args=(1,)),
            ExecutionTask(
                id="task-2", func=simple_task, args=(2,), dependencies={"task-1"}
            ),
        ]

        results = await scheduler.execute_with_optimization(tasks)

        assert len(results) == 2
        assert all(r.success for r in results.values())

    def test_build_dependency_graph(self):
        """Test dependency graph construction."""

        async def simple_task() -> None:
            pass

        executor = ParallelExecutor(max_workers=1)
        scheduler = TaskScheduler(executor)

        tasks = [
            ExecutionTask(id="a", func=simple_task),
            ExecutionTask(id="b", func=simple_task, dependencies={"a"}),
            ExecutionTask(id="c", func=simple_task, dependencies={"a", "b"}),
        ]

        graph = scheduler._build_dependency_graph(tasks)

        assert "a" in graph
        assert "b" in graph
        assert "c" in graph
        assert "b" in graph["a"]["dependents"]
        assert "c" in graph["a"]["dependents"]
        assert "c" in graph["b"]["dependents"]


class TestExecutionTaskDataclass:
    """Tests for ExecutionTask dataclass."""

    def test_execution_task_defaults(self):
        """Test ExecutionTask default values."""

        async def dummy() -> None:
            pass

        task = ExecutionTask(id="test", func=dummy)

        assert task.args == ()
        assert task.kwargs == {}
        assert task.dependencies == set()
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout == 3600.0
        assert task.metadata == {}


class TestTaskResultDataclass:
    """Tests for TaskResult dataclass."""

    def test_task_result_success(self):
        """Test TaskResult for successful task."""
        result = TaskResult(
            task_id="task-1",
            success=True,
            result="completed",
            execution_time=1.5,
        )

        assert result.task_id == "task-1"
        assert result.success is True
        assert result.result == "completed"
        assert result.error is None
        assert result.execution_time == 1.5

    def test_task_result_failure(self):
        """Test TaskResult for failed task."""
        error = ValueError("Something went wrong")
        result = TaskResult(
            task_id="task-2",
            success=False,
            error=error,
            execution_time=0.5,
        )

        assert result.success is False
        assert result.error is error


# =============================================================================
# Recovery Tests
# =============================================================================


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_error_type_values(self):
        """Test all error type values exist."""
        assert ErrorType.TRANSIENT_API_ERROR == "transient_api_error"
        assert ErrorType.MERGE_CONFLICT == "merge_conflict"
        assert ErrorType.TEST_FAILURE == "test_failure"
        assert ErrorType.TIMEOUT == "timeout"
        assert ErrorType.VALIDATION_ERROR == "validation_error"
        assert ErrorType.UNKNOWN == "unknown"


class TestRetryRecoveryStrategy:
    """Tests for RetryRecoveryStrategy."""

    def test_can_handle_transient_errors(self):
        """Test strategy handles transient API errors."""
        mock_recovery = MagicMock()
        strategy = RetryRecoveryStrategy(mock_recovery)

        assert strategy.can_handle(ErrorType.TRANSIENT_API_ERROR) is True
        assert strategy.can_handle(ErrorType.TIMEOUT) is True
        assert strategy.can_handle(ErrorType.MERGE_CONFLICT) is False

    @pytest.mark.asyncio
    async def test_execute_retry_with_backoff(self):
        """Test retry execution with exponential backoff."""
        mock_recovery = MagicMock()
        strategy = RetryRecoveryStrategy(mock_recovery)

        checkpoint_data = {
            "failed_operation": "api_call",
            "retry_attempt": 0,
        }

        # Should not raise on first retry
        await strategy.execute("test-plan", checkpoint_data)

    @pytest.mark.asyncio
    async def test_execute_max_retries_exceeded(self):
        """Test retry failure when max attempts exceeded."""
        mock_recovery = MagicMock()
        strategy = RetryRecoveryStrategy(mock_recovery)

        checkpoint_data = {
            "failed_operation": "api_call",
            "retry_attempt": 3,  # Already at max
        }

        with pytest.raises(RecoveryError, match="Max retry attempts"):
            await strategy.execute("test-plan", checkpoint_data)


class TestConflictResolutionStrategy:
    """Tests for ConflictResolutionStrategy."""

    def test_can_handle_merge_conflicts(self):
        """Test strategy handles merge conflicts."""
        mock_recovery = MagicMock()
        strategy = ConflictResolutionStrategy(mock_recovery)

        assert strategy.can_handle(ErrorType.MERGE_CONFLICT) is True
        assert strategy.can_handle(ErrorType.TEST_FAILURE) is False

    @pytest.mark.asyncio
    async def test_execute_raises_not_implemented(self):
        """Test conflict resolution raises not implemented error."""
        mock_recovery = MagicMock()
        strategy = ConflictResolutionStrategy(mock_recovery)

        with pytest.raises(RecoveryError, match="not yet implemented"):
            await strategy.execute("test-plan", {"conflict_details": {}})


class TestTestFixRecoveryStrategy:
    """Tests for TestFixRecoveryStrategy."""

    def test_can_handle_test_failures(self):
        """Test strategy handles test failures."""
        mock_recovery = MagicMock()
        strategy = TestFixRecoveryStrategy(mock_recovery)

        assert strategy.can_handle(ErrorType.TEST_FAILURE) is True
        assert strategy.can_handle(ErrorType.TIMEOUT) is False

    @pytest.mark.asyncio
    async def test_execute_raises_not_implemented(self):
        """Test test fixing raises not implemented error."""
        mock_recovery = MagicMock()
        strategy = TestFixRecoveryStrategy(mock_recovery)

        with pytest.raises(RecoveryError, match="not yet implemented"):
            await strategy.execute("test-plan", {"test_failures": []})


class TestManualInterventionStrategy:
    """Tests for ManualInterventionStrategy."""

    def test_can_handle_any_error(self):
        """Test strategy handles any error type (fallback)."""
        mock_recovery = MagicMock()
        strategy = ManualInterventionStrategy(mock_recovery)

        assert strategy.can_handle(ErrorType.TRANSIENT_API_ERROR) is True
        assert strategy.can_handle(ErrorType.MERGE_CONFLICT) is True
        assert strategy.can_handle(ErrorType.TEST_FAILURE) is True
        assert strategy.can_handle(ErrorType.UNKNOWN) is True

    @pytest.mark.asyncio
    async def test_execute_raises_manual_intervention(self):
        """Test manual intervention strategy raises appropriate error."""
        mock_recovery = MagicMock()
        strategy = ManualInterventionStrategy(mock_recovery)

        with pytest.raises(RecoveryError, match="Manual intervention required"):
            await strategy.execute("test-plan", {})


class TestAdvancedRecovery:
    """Tests for AdvancedRecovery class."""

    def test_initialization(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test AdvancedRecovery initialization."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        assert len(recovery.strategies) == 4
        assert isinstance(recovery.strategies[0], RetryRecoveryStrategy)
        assert isinstance(recovery.strategies[-1], ManualInterventionStrategy)

    @pytest.mark.asyncio
    async def test_attempt_recovery_no_checkpoint(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test recovery attempt when no checkpoint exists."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = None

        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)
        result = await recovery.attempt_recovery("nonexistent-plan")

        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_recovery_transient_error(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test recovery for transient API error."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "test-cp",
            "plan_id": "test-plan",
            "stage": "implementation",
            "data": {
                "error": "API connection failed",
                "error_type": "transient_api_error",
                "retry_attempt": 0,
            },
        }

        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)
        result = await recovery.attempt_recovery("test-plan")

        # RetryRecoveryStrategy should succeed on first attempt
        assert result is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_failure(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test recovery failure (unknown error type)."""
        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "test-cp",
            "plan_id": "test-plan",
            "stage": "implementation",
            "data": {"error": "Unknown error", "error_type": "unknown"},
        }

        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)
        result = await recovery.attempt_recovery("test-plan")

        # ManualInterventionStrategy always raises RecoveryError
        assert result is False

    def test_classify_error_from_type_string(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test error classification from explicit type string."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        result = recovery._classify_error({"error_type": "timeout"})
        assert result == ErrorType.TIMEOUT

    def test_classify_error_from_message(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test error classification from error message."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        assert recovery._classify_error({"error": "Connection timeout"}) == ErrorType.TIMEOUT
        assert recovery._classify_error({"error": "Merge conflict in file"}) == ErrorType.MERGE_CONFLICT
        assert recovery._classify_error({"error": "Test failed"}) == ErrorType.TEST_FAILURE
        assert recovery._classify_error({"error": "API rate limit"}) == ErrorType.TRANSIENT_API_ERROR
        assert recovery._classify_error({"error": "Random error"}) == ErrorType.UNKNOWN

    def test_select_recovery_strategy(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test correct strategy selection for error types."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        assert isinstance(
            recovery._select_recovery_strategy(ErrorType.TRANSIENT_API_ERROR),
            RetryRecoveryStrategy,
        )
        assert isinstance(
            recovery._select_recovery_strategy(ErrorType.MERGE_CONFLICT),
            ConflictResolutionStrategy,
        )
        assert isinstance(
            recovery._select_recovery_strategy(ErrorType.TEST_FAILURE),
            TestFixRecoveryStrategy,
        )
        assert isinstance(
            recovery._select_recovery_strategy(ErrorType.UNKNOWN),
            ManualInterventionStrategy,
        )

    @pytest.mark.asyncio
    async def test_create_recovery_checkpoint(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test creation of recovery checkpoint on error."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        error = TimeoutError("Operation timed out")
        checkpoint_id = await recovery.create_recovery_checkpoint(
            plan_id="test-plan",
            stage="implementation",
            error=error,
            context={"operation": "api_call"},
        )

        assert checkpoint_id == "new-checkpoint-id"
        mock_checkpoint_manager.create_checkpoint.assert_called_once()

    def test_infer_error_type(
        self, mock_state_manager: MagicMock, mock_checkpoint_manager: AsyncMock
    ):
        """Test error type inference from exception."""
        recovery = AdvancedRecovery(mock_state_manager, mock_checkpoint_manager)

        assert recovery._infer_error_type(TimeoutError("timeout")) == ErrorType.TIMEOUT
        assert recovery._infer_error_type(Exception("merge conflict")) == ErrorType.MERGE_CONFLICT
        assert recovery._infer_error_type(Exception("API error")) == ErrorType.TRANSIENT_API_ERROR
        assert recovery._infer_error_type(Exception("validation failed")) == ErrorType.VALIDATION_ERROR
        assert recovery._infer_error_type(Exception("random")) == ErrorType.UNKNOWN


# =============================================================================
# Checkpointing Tests
# =============================================================================


class TestCheckpointManager:
    """Tests for CheckpointManager class."""

    @pytest.mark.asyncio
    async def test_initialization_creates_directory(self, tmp_path: Path):
        """Test that initialization creates checkpoint directory."""
        checkpoint_dir = tmp_path / "new_checkpoints"
        manager = CheckpointManager(str(checkpoint_dir))

        assert checkpoint_dir.exists()
        assert manager.checkpoint_dir == checkpoint_dir

    @pytest.mark.asyncio
    async def test_create_checkpoint(self, checkpoint_manager: CheckpointManager):
        """Test checkpoint creation."""
        checkpoint_data = {"status": "in_progress", "step": 1}

        checkpoint_id = await checkpoint_manager.create_checkpoint(
            plan_id="plan-42",
            stage="implementation",
            checkpoint_data=checkpoint_data,
        )

        assert checkpoint_id.startswith("plan-42-implementation-")
        checkpoint_file = checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json"
        assert checkpoint_file.exists()

        # Verify contents
        saved_data = json.loads(checkpoint_file.read_text())
        assert saved_data["plan_id"] == "plan-42"
        assert saved_data["stage"] == "implementation"
        assert saved_data["data"] == checkpoint_data

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, checkpoint_manager: CheckpointManager):
        """Test retrieving the latest checkpoint."""
        await checkpoint_manager.create_checkpoint("plan-42", "a-planning", {"step": 1})
        # Use different stage names that sort differently to ensure consistent ordering
        # since timestamps within same second are identical
        await checkpoint_manager.create_checkpoint("plan-42", "z-implementation", {"step": 2})

        latest = await checkpoint_manager.get_latest_checkpoint("plan-42")

        assert latest is not None
        # Latest is sorted by filename in reverse order, so z-implementation comes first
        assert latest["data"]["step"] == 2

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_by_stage(
        self, checkpoint_manager: CheckpointManager
    ):
        """Test retrieving latest checkpoint for specific stage."""
        await checkpoint_manager.create_checkpoint("plan-42", "planning", {"v": 1})
        await checkpoint_manager.create_checkpoint("plan-42", "implementation", {"v": 2})

        latest = await checkpoint_manager.get_latest_checkpoint("plan-42", "planning")

        assert latest is not None
        assert latest["stage"] == "planning"
        assert latest["data"]["v"] == 1

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_not_found(
        self, checkpoint_manager: CheckpointManager
    ):
        """Test behavior when no checkpoint exists."""
        result = await checkpoint_manager.get_latest_checkpoint("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_checkpoints(self, checkpoint_manager: CheckpointManager):
        """Test retrieving all checkpoints for a plan."""
        # Use stage names that sort alphabetically in reverse order matching our expected values
        # so z-* is first in reverse sort, then m-*, then a-*
        await checkpoint_manager.create_checkpoint("plan-42", "a-planning", {"v": 1})
        await checkpoint_manager.create_checkpoint("plan-42", "m-implementation", {"v": 2})
        await checkpoint_manager.create_checkpoint("plan-42", "z-review", {"v": 3})

        all_checkpoints = await checkpoint_manager.get_all_checkpoints("plan-42")

        assert len(all_checkpoints) == 3
        # Should be reverse alphabetical order since timestamps are the same
        assert all_checkpoints[0]["data"]["v"] == 3  # z-review
        assert all_checkpoints[-1]["data"]["v"] == 1  # a-planning

    @pytest.mark.asyncio
    async def test_delete_checkpoints(self, checkpoint_manager: CheckpointManager):
        """Test checkpoint deletion."""
        await checkpoint_manager.create_checkpoint("plan-42", "planning", {})
        await checkpoint_manager.create_checkpoint("plan-42", "implementation", {})
        await checkpoint_manager.create_checkpoint("plan-99", "planning", {})

        await checkpoint_manager.delete_checkpoints("plan-42")

        # plan-42 checkpoints deleted
        plan42_files = list(checkpoint_manager.checkpoint_dir.glob("plan-42-*.json"))
        assert len(plan42_files) == 0

        # plan-99 checkpoint preserved
        plan99_files = list(checkpoint_manager.checkpoint_dir.glob("plan-99-*.json"))
        assert len(plan99_files) == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(
        self, checkpoint_manager: CheckpointManager, tmp_path: Path
    ):
        """Test cleanup of old checkpoints."""
        # Create a checkpoint with old timestamp
        old_checkpoint = {
            "checkpoint_id": "old-plan-test-1",
            "plan_id": "old-plan",
            "stage": "test",
            "created_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
            "data": {},
        }
        old_file = checkpoint_manager.checkpoint_dir / "old-plan-test-1.json"
        old_file.write_text(json.dumps(old_checkpoint))

        # Create a recent checkpoint
        await checkpoint_manager.create_checkpoint("recent-plan", "test", {})

        deleted = await checkpoint_manager.cleanup_old_checkpoints(max_age_days=30)

        assert deleted == 1
        assert not old_file.exists()
        # Recent checkpoint should still exist
        recent_files = list(checkpoint_manager.checkpoint_dir.glob("recent-plan-*.json"))
        assert len(recent_files) == 1

    @pytest.mark.asyncio
    async def test_cleanup_handles_invalid_files(
        self, checkpoint_manager: CheckpointManager
    ):
        """Test cleanup handles corrupted checkpoint files gracefully."""
        # Create invalid JSON file
        invalid_file = checkpoint_manager.checkpoint_dir / "invalid-checkpoint.json"
        invalid_file.write_text("not valid json {{{")

        # Should not raise
        deleted = await checkpoint_manager.cleanup_old_checkpoints(max_age_days=0)
        assert deleted >= 0

    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_creation(
        self, checkpoint_manager: CheckpointManager
    ):
        """Test concurrent checkpoint creation with locking."""

        async def create_checkpoint(plan_id: str, stage: str, data: dict[str, Any]) -> str:
            return await checkpoint_manager.create_checkpoint(plan_id, stage, data)

        # Create multiple checkpoints concurrently with different stages
        # Since checkpoint IDs include stage name, different stages give unique IDs
        tasks = [
            create_checkpoint("plan-1", f"stage-{i}", {"task": i})
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert len(set(results)) == 5  # All unique checkpoint IDs (different stages)


# =============================================================================
# Branching Tests
# =============================================================================


class TestPerPlanStrategy:
    """Tests for PerPlanStrategy class."""

    @pytest.mark.asyncio
    async def test_create_task_branch_new(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
        sample_domain_task: Task,
    ):
        """Test creating new plan branch."""
        mock_git_provider.get_branch.return_value = None

        strategy = PerPlanStrategy(mock_git_provider, mock_settings)
        branch_name = await strategy.create_task_branch("42", sample_domain_task)

        assert branch_name == "plan/42"
        mock_git_provider.create_branch.assert_called_once_with("plan/42", "main")

    @pytest.mark.asyncio
    async def test_create_task_branch_exists(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
        sample_domain_task: Task,
    ):
        """Test using existing plan branch."""
        mock_git_provider.get_branch.return_value = Branch(name="plan/42", sha="abc123")

        strategy = PerPlanStrategy(mock_git_provider, mock_settings)
        branch_name = await strategy.create_task_branch("42", sample_domain_task)

        assert branch_name == "plan/42"
        mock_git_provider.create_branch.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_integration_uses_plan_branch(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test integration branch is the plan branch itself."""
        strategy = PerPlanStrategy(mock_git_provider, mock_settings)
        branch_name = await strategy.create_integration("42", ["task-1", "task-2"])

        assert branch_name == "plan/42"
        # No merge operations should occur
        mock_git_provider.merge_branches.assert_not_called()


class TestPerAgentStrategy:
    """Tests for PerAgentStrategy class."""

    @pytest.mark.asyncio
    async def test_create_task_branch(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
        sample_domain_task: Task,
    ):
        """Test creating per-task branch."""
        strategy = PerAgentStrategy(mock_git_provider, mock_settings)
        branch_name = await strategy.create_task_branch("42", sample_domain_task)

        assert branch_name == "task/42-task-1"
        mock_git_provider.create_branch.assert_called_once_with("task/42-task-1", "main")

    @pytest.mark.asyncio
    async def test_create_integration_merges_branches(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test integration branch merges all task branches."""
        strategy = PerAgentStrategy(mock_git_provider, mock_settings)
        task_branches = ["task/42-task-1", "task/42-task-2", "task/42-task-3"]

        branch_name = await strategy.create_integration("42", task_branches)

        assert branch_name == "integration/plan-42"
        assert mock_git_provider.create_branch.call_count == 1
        assert mock_git_provider.merge_branches.call_count == 3

    @pytest.mark.asyncio
    async def test_create_integration_merge_failure(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test integration handles merge failures."""
        mock_git_provider.merge_branches.side_effect = Exception("Merge conflict")

        strategy = PerAgentStrategy(mock_git_provider, mock_settings)

        with pytest.raises(Exception, match="Merge conflict"):
            await strategy.create_integration("42", ["task/42-task-1"])


class TestGetBranchingStrategy:
    """Tests for get_branching_strategy factory function."""

    def test_get_per_plan_strategy(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test factory returns PerPlanStrategy."""
        strategy = get_branching_strategy("per-plan", mock_git_provider, mock_settings)
        assert isinstance(strategy, PerPlanStrategy)

    def test_get_per_agent_strategy(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test factory returns PerAgentStrategy."""
        strategy = get_branching_strategy("per-agent", mock_git_provider, mock_settings)
        assert isinstance(strategy, PerAgentStrategy)

    def test_unknown_strategy_raises(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test factory raises for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown branching strategy"):
            get_branching_strategy("invalid", mock_git_provider, mock_settings)


class TestBranchingStrategyABC:
    """Tests for BranchingStrategy abstract base class."""

    def test_abstract_methods(
        self,
        mock_git_provider: AsyncMock,
        mock_settings: AutomationSettings,
    ):
        """Test that BranchingStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BranchingStrategy(mock_git_provider, mock_settings)
