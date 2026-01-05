"""Comprehensive unit tests for engine/state_manager.py."""

import asyncio
import json
from pathlib import Path

import pytest

from repo_sapiens.engine.state_manager import StateManager


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    def test_initialization_creates_directory(self, tmp_path: Path):
        """Test that initialization creates state directory."""
        state_dir = tmp_path / "new_state"
        manager = StateManager(str(state_dir))

        assert state_dir.exists()
        assert manager.state_dir == state_dir

    def test_initialization_with_existing_directory(self, tmp_path: Path):
        """Test initialization with existing directory doesn't error."""
        state_dir = tmp_path / "existing_state"
        state_dir.mkdir()

        manager = StateManager(str(state_dir))
        assert manager.state_dir == state_dir

    def test_initialization_creates_nested_directories(self, tmp_path: Path):
        """Test initialization creates nested directories."""
        state_dir = tmp_path / "nested" / "path" / "state"
        manager = StateManager(str(state_dir))

        assert state_dir.exists()
        assert manager.state_dir == state_dir


class TestStateManagerLock:
    """Tests for lock management."""

    def test_get_lock_creates_new_lock(self, state_manager: StateManager):
        """Test lock creation for new plan_id."""
        lock1 = state_manager._get_lock("plan-1")
        assert isinstance(lock1, asyncio.Lock)

    def test_get_lock_reuses_existing_lock(self, state_manager: StateManager):
        """Test lock reuse for same plan_id."""
        lock1 = state_manager._get_lock("plan-1")
        lock2 = state_manager._get_lock("plan-1")
        assert lock1 is lock2

    def test_get_lock_different_plans_have_different_locks(self, state_manager: StateManager):
        """Test different plans get different locks."""
        lock1 = state_manager._get_lock("plan-1")
        lock2 = state_manager._get_lock("plan-2")
        assert lock1 is not lock2


class TestStateManagerPaths:
    """Tests for path management."""

    def test_get_state_path(self, state_manager: StateManager):
        """Test state path construction."""
        path = state_manager._get_state_path("plan-42")
        assert path == state_manager.state_dir / "plan-42.json"

    def test_get_state_path_special_characters(self, state_manager: StateManager):
        """Test state path with special characters."""
        path = state_manager._get_state_path("plan_123-abc")
        assert path == state_manager.state_dir / "plan_123-abc.json"


class TestStateManagerLoadSave:
    """Tests for load and save operations."""

    @pytest.mark.asyncio
    async def test_load_state_creates_initial_state(self, state_manager: StateManager):
        """Test loading creates initial state if not exists."""
        state = await state_manager.load_state("new-plan")

        assert state["plan_id"] == "new-plan"
        assert state["status"] == "pending"
        assert "created_at" in state
        assert "updated_at" in state
        assert "stages" in state
        assert "tasks" in state

    @pytest.mark.asyncio
    async def test_load_state_reads_existing_state(self, state_manager: StateManager):
        """Test loading reads existing state file."""
        # Create a state file first
        state_path = state_manager._get_state_path("existing-plan")
        existing_state = {"plan_id": "existing-plan", "status": "in_progress", "custom": "data"}
        state_path.write_text(json.dumps(existing_state))

        state = await state_manager.load_state("existing-plan")

        assert state["plan_id"] == "existing-plan"
        assert state["status"] == "in_progress"
        assert state["custom"] == "data"

    @pytest.mark.asyncio
    async def test_save_state_updates_timestamp(self, state_manager: StateManager):
        """Test saving updates the updated_at timestamp."""
        state = await state_manager.load_state("plan-1")
        original_updated = state["updated_at"]

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        await state_manager.save_state("plan-1", state)
        saved_state = await state_manager.load_state("plan-1")

        assert saved_state["updated_at"] != original_updated

    @pytest.mark.asyncio
    async def test_save_state_calculates_status(self, state_manager: StateManager):
        """Test saving calculates overall status."""
        state = await state_manager.load_state("plan-1")
        state["stages"]["planning"]["status"] = "completed"
        state["stages"]["implementation"]["status"] = "in_progress"

        await state_manager.save_state("plan-1", state)
        saved_state = await state_manager.load_state("plan-1")

        assert saved_state["status"] == "in_progress"


class TestCalculateOverallStatus:
    """Tests for status calculation."""

    def test_calculate_status_failed(self, state_manager: StateManager):
        """Test failed status when any stage fails."""
        state = {
            "stages": {
                "planning": {"status": "completed"},
                "implementation": {"status": "failed"},
            }
        }
        assert state_manager._calculate_overall_status(state) == "failed"

    def test_calculate_status_completed(self, state_manager: StateManager):
        """Test completed status when all stages complete."""
        state = {
            "stages": {
                "planning": {"status": "completed"},
                "implementation": {"status": "completed"},
            }
        }
        assert state_manager._calculate_overall_status(state) == "completed"

    def test_calculate_status_in_progress(self, state_manager: StateManager):
        """Test in_progress status when any stage in progress."""
        state = {
            "stages": {
                "planning": {"status": "completed"},
                "implementation": {"status": "in_progress"},
            }
        }
        assert state_manager._calculate_overall_status(state) == "in_progress"

    def test_calculate_status_pending(self, state_manager: StateManager):
        """Test pending status when no stages started."""
        state = {
            "stages": {
                "planning": {"status": "pending"},
                "implementation": {"status": "pending"},
            }
        }
        assert state_manager._calculate_overall_status(state) == "pending"

    def test_calculate_status_empty_stages(self, state_manager: StateManager):
        """Test status with empty stages."""
        state = {"stages": {}}
        # All empty means all completed (vacuously true)
        assert state_manager._calculate_overall_status(state) == "completed"


class TestTransaction:
    """Tests for transaction context manager."""

    @pytest.mark.asyncio
    async def test_transaction_success(self, state_manager: StateManager):
        """Test successful transaction commits changes."""
        async with state_manager.transaction("plan-1") as state:
            state["custom_field"] = "custom_value"

        # Verify changes were saved
        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["custom_field"] == "custom_value"

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, state_manager: StateManager):
        """Test transaction does not save on error."""
        # First create the state
        initial_state = await state_manager.load_state("plan-1")
        initial_status = initial_state["status"]

        with pytest.raises(ValueError):
            async with state_manager.transaction("plan-1") as state:
                state["status"] = "modified"
                raise ValueError("Test error")

        # Verify state was not modified
        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["status"] == initial_status

    @pytest.mark.asyncio
    async def test_transaction_nested_not_supported(self, state_manager: StateManager):
        """Test nested transactions block correctly (single lock)."""
        # This test verifies that the same plan_id uses the same lock
        lock = state_manager._get_lock("plan-1")

        # Acquire the lock manually first
        await lock.acquire()

        try:
            # The transaction should wait for the lock
            # We can't really test blocking without threads, but we can verify lock reuse
            lock2 = state_manager._get_lock("plan-1")
            assert lock is lock2
        finally:
            lock.release()


class TestMarkStageComplete:
    """Tests for mark_stage_complete method."""

    @pytest.mark.asyncio
    async def test_mark_stage_complete_updates_status(self, state_manager: StateManager):
        """Test marking stage as complete updates status."""
        await state_manager.load_state("plan-1")  # Create initial state

        await state_manager.mark_stage_complete("plan-1", "planning")

        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["stages"]["planning"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_mark_stage_complete_adds_timestamp(self, state_manager: StateManager):
        """Test marking stage complete adds timestamp."""
        await state_manager.load_state("plan-1")

        await state_manager.mark_stage_complete("plan-1", "planning")

        saved_state = await state_manager.load_state("plan-1")
        assert "completed_at" in saved_state["stages"]["planning"]

    @pytest.mark.asyncio
    async def test_mark_stage_complete_with_data(self, state_manager: StateManager):
        """Test marking stage complete with data."""
        await state_manager.load_state("plan-1")

        await state_manager.mark_stage_complete("plan-1", "planning", data={"result": "success"})

        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["stages"]["planning"]["data"]["result"] == "success"

    @pytest.mark.asyncio
    async def test_mark_stage_complete_unknown_stage(self, state_manager: StateManager):
        """Test marking unknown stage is silently ignored."""
        await state_manager.load_state("plan-1")

        # Should not raise, just skip
        await state_manager.mark_stage_complete("plan-1", "unknown_stage")

        saved_state = await state_manager.load_state("plan-1")
        assert "unknown_stage" not in saved_state["stages"]


class TestMarkTaskStatus:
    """Tests for mark_task_status method."""

    @pytest.mark.asyncio
    async def test_mark_task_status_creates_task(self, state_manager: StateManager):
        """Test marking task creates it if not exists."""
        await state_manager.load_state("plan-1")

        await state_manager.mark_task_status("plan-1", "task-1", "in_progress")

        saved_state = await state_manager.load_state("plan-1")
        assert "task-1" in saved_state["tasks"]
        assert saved_state["tasks"]["task-1"]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_mark_task_status_updates_existing(self, state_manager: StateManager):
        """Test marking task updates existing task."""
        await state_manager.load_state("plan-1")
        await state_manager.mark_task_status("plan-1", "task-1", "pending")

        await state_manager.mark_task_status("plan-1", "task-1", "completed")

        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["tasks"]["task-1"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_mark_task_status_adds_timestamp(self, state_manager: StateManager):
        """Test marking task adds updated_at."""
        await state_manager.load_state("plan-1")

        await state_manager.mark_task_status("plan-1", "task-1", "in_progress")

        saved_state = await state_manager.load_state("plan-1")
        assert "updated_at" in saved_state["tasks"]["task-1"]

    @pytest.mark.asyncio
    async def test_mark_task_status_with_data(self, state_manager: StateManager):
        """Test marking task with additional data."""
        await state_manager.load_state("plan-1")

        await state_manager.mark_task_status(
            "plan-1", "task-1", "completed", data={"pr_number": 123}
        )

        saved_state = await state_manager.load_state("plan-1")
        assert saved_state["tasks"]["task-1"]["data"]["pr_number"] == 123


class TestGetActivePlans:
    """Tests for get_active_plans method."""

    @pytest.mark.asyncio
    async def test_get_active_plans_empty(self, state_manager: StateManager):
        """Test getting active plans when none exist."""
        active = await state_manager.get_active_plans()
        assert active == []

    @pytest.mark.asyncio
    async def test_get_active_plans_filters_completed(self, state_manager: StateManager):
        """Test completed plans are filtered out."""
        # Create an active plan
        state1 = await state_manager.load_state("active-plan")
        state1["status"] = "in_progress"
        await state_manager.save_state("active-plan", state1)

        # Create a completed plan
        state2 = await state_manager.load_state("completed-plan")
        state2["status"] = "completed"
        await state_manager.save_state("completed-plan", state2)

        active = await state_manager.get_active_plans()

        assert "active-plan" in active
        assert "completed-plan" not in active

    @pytest.mark.asyncio
    async def test_get_active_plans_filters_failed(self, state_manager: StateManager):
        """Test failed plans are filtered out."""
        # Create a failed plan
        state = await state_manager.load_state("failed-plan")
        state["status"] = "failed"
        await state_manager.save_state("failed-plan", state)

        active = await state_manager.get_active_plans()

        assert "failed-plan" not in active

    @pytest.mark.asyncio
    async def test_get_active_plans_includes_pending(self, state_manager: StateManager):
        """Test pending plans are included."""
        await state_manager.load_state("pending-plan")

        active = await state_manager.get_active_plans()

        assert "pending-plan" in active


class TestAtomicWrite:
    """Tests for atomic write operations."""

    @pytest.mark.asyncio
    async def test_write_uses_tmp_file(self, state_manager: StateManager):
        """Test atomic write uses temporary file."""
        state_path = state_manager._get_state_path("plan-1")
        state = {"plan_id": "plan-1", "status": "pending"}

        await state_manager._write_state(state_path, state)

        # Verify tmp file doesn't exist after write
        tmp_path = state_path.with_suffix(".tmp")
        assert not tmp_path.exists()
        assert state_path.exists()

    @pytest.mark.asyncio
    async def test_write_creates_valid_json(self, state_manager: StateManager):
        """Test write creates valid JSON file."""
        state_path = state_manager._get_state_path("plan-1")
        state = {"plan_id": "plan-1", "nested": {"key": "value"}}

        await state_manager._write_state(state_path, state)

        # Verify JSON is valid
        loaded = json.loads(state_path.read_text())
        assert loaded == state


class TestConcurrentAccess:
    """Tests for concurrent access handling."""

    @pytest.mark.asyncio
    async def test_concurrent_loads_same_plan(self, state_manager: StateManager):
        """Test concurrent loads of the same plan work correctly."""

        async def load_plan():
            return await state_manager.load_state("plan-1")

        results = await asyncio.gather(*[load_plan() for _ in range(5)])

        # All results should be valid states
        for result in results:
            assert result["plan_id"] == "plan-1"

    @pytest.mark.asyncio
    async def test_concurrent_saves_same_plan(self, state_manager: StateManager):
        """Test concurrent saves don't corrupt state."""
        await state_manager.load_state("plan-1")

        async def update_plan(value: int):
            async with state_manager.transaction("plan-1") as state:
                state["counter"] = value
                await asyncio.sleep(0.001)  # Small delay to increase chance of race

        await asyncio.gather(*[update_plan(i) for i in range(5)])

        # State should be valid (one of the values)
        state = await state_manager.load_state("plan-1")
        assert "counter" in state
        assert state["counter"] in range(5)
