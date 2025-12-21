"""Tests for state manager."""

import pytest

from automation.engine.state_manager import StateManager


@pytest.mark.asyncio
async def test_state_manager_initialization(temp_state_dir):
    """Test state manager initialization."""
    state_mgr = StateManager(str(temp_state_dir))
    assert state_mgr.state_dir.exists()


@pytest.mark.asyncio
async def test_load_state_creates_initial(temp_state_dir):
    """Test loading non-existent state creates initial state."""
    state_mgr = StateManager(str(temp_state_dir))

    state = await state_mgr.load_state("test-plan")

    assert state["plan_id"] == "test-plan"
    assert state["status"] == "pending"
    assert "created_at" in state
    assert "stages" in state


@pytest.mark.asyncio
async def test_save_and_load_state(temp_state_dir):
    """Test saving and loading state."""
    state_mgr = StateManager(str(temp_state_dir))

    # Load initial state
    state = await state_mgr.load_state("test-plan")
    state["custom_field"] = "test_value"

    # Save state
    await state_mgr.save_state("test-plan", state)

    # Load again
    loaded = await state_mgr.load_state("test-plan")

    assert loaded["custom_field"] == "test_value"


@pytest.mark.asyncio
async def test_transaction(temp_state_dir):
    """Test transaction context manager."""
    state_mgr = StateManager(str(temp_state_dir))

    async with state_mgr.transaction("test-plan") as state:
        state["test_field"] = "test_value"

    # Verify state was saved
    loaded = await state_mgr.load_state("test-plan")
    assert loaded["test_field"] == "test_value"


@pytest.mark.asyncio
async def test_mark_stage_complete(temp_state_dir):
    """Test marking stage as complete."""
    state_mgr = StateManager(str(temp_state_dir))

    await state_mgr.mark_stage_complete(
        "test-plan",
        "planning",
        {"plan_path": "plans/test.md"},
    )

    state = await state_mgr.load_state("test-plan")

    assert state["stages"]["planning"]["status"] == "completed"
    assert "completed_at" in state["stages"]["planning"]
    assert state["stages"]["planning"]["data"]["plan_path"] == "plans/test.md"


@pytest.mark.asyncio
async def test_mark_task_status(temp_state_dir):
    """Test updating task status."""
    state_mgr = StateManager(str(temp_state_dir))

    await state_mgr.mark_task_status(
        "test-plan",
        "task-1",
        "completed",
        {"branch": "task/test-plan-task-1"},
    )

    state = await state_mgr.load_state("test-plan")

    assert state["tasks"]["task-1"]["status"] == "completed"
    assert "updated_at" in state["tasks"]["task-1"]
