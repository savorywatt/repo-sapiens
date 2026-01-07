"""Tests for state manager."""

import asyncio

import pytest

from repo_sapiens.engine.state_manager import StateManager


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


@pytest.mark.asyncio
async def test_concurrent_transactions_no_deadlock(temp_state_dir):
    """Test that concurrent transactions don't deadlock."""
    state_mgr = StateManager(str(temp_state_dir))
    plan_id = "concurrent-test"

    # Initialize state
    await state_mgr.load_state(plan_id)

    results = []

    async def update_state(value: int) -> None:
        async with state_mgr.transaction(plan_id) as state:
            # Simulate some async work
            await asyncio.sleep(0.01)
            if "values" not in state:
                state["values"] = []
            state["values"].append(value)
            results.append(value)

    # Run concurrent transactions with timeout to detect deadlock
    try:
        await asyncio.wait_for(
            asyncio.gather(*[update_state(i) for i in range(5)]),
            timeout=5.0,
        )
    except TimeoutError:
        pytest.fail("Deadlock detected: concurrent transactions timed out")

    # All transactions should complete
    assert len(results) == 5

    # Verify final state contains all values (order may vary due to concurrency)
    final_state = await state_mgr.load_state(plan_id)
    assert len(final_state["values"]) == 5
    assert sorted(final_state["values"]) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_get_lock_returns_same_lock_for_same_plan_id(temp_state_dir):
    """Test that _get_lock returns the same lock for the same plan_id."""
    state_mgr = StateManager(str(temp_state_dir))
    plan_id = "lock-test"

    # Get locks concurrently
    locks = await asyncio.gather(
        state_mgr._get_lock(plan_id),
        state_mgr._get_lock(plan_id),
        state_mgr._get_lock(plan_id),
    )

    # All should be the same lock instance
    assert locks[0] is locks[1]
    assert locks[1] is locks[2]


@pytest.mark.asyncio
async def test_get_lock_different_plan_ids_different_locks(temp_state_dir):
    """Test that different plan_ids get different locks."""
    state_mgr = StateManager(str(temp_state_dir))

    lock1 = await state_mgr._get_lock("plan-1")
    lock2 = await state_mgr._get_lock("plan-2")

    assert lock1 is not lock2


@pytest.mark.asyncio
async def test_transaction_saves_state_on_exit(temp_state_dir):
    """Test that transaction context manager properly saves state on exit."""
    state_mgr = StateManager(str(temp_state_dir))
    plan_id = "save-test"

    async with state_mgr.transaction(plan_id) as state:
        state["custom_field"] = "test_value"
        state["stages"]["planning"]["status"] = "completed"

    # Verify state was saved (reload from disk)
    state_mgr2 = StateManager(str(temp_state_dir))
    loaded = await state_mgr2.load_state(plan_id)

    assert loaded["custom_field"] == "test_value"
    assert loaded["stages"]["planning"]["status"] == "completed"
    assert "updated_at" in loaded


@pytest.mark.asyncio
async def test_transaction_does_not_save_on_exception(temp_state_dir):
    """Test that transaction does not save state if exception occurs."""
    state_mgr = StateManager(str(temp_state_dir))
    plan_id = "exception-test"

    # First, create initial state
    await state_mgr.load_state(plan_id)

    # Attempt transaction that raises
    with pytest.raises(ValueError, match="intentional"):
        async with state_mgr.transaction(plan_id) as state:
            state["should_not_exist"] = "value"
            raise ValueError("intentional error")

    # Verify state was NOT saved
    loaded = await state_mgr.load_state(plan_id)
    assert "should_not_exist" not in loaded


@pytest.mark.asyncio
async def test_nested_load_within_transaction_no_deadlock(temp_state_dir):
    """Test that we can call mark_stage_complete which uses transaction internally."""
    state_mgr = StateManager(str(temp_state_dir))
    plan_id = "nested-test"

    # mark_stage_complete uses transaction internally
    # This should not deadlock
    try:
        await asyncio.wait_for(
            state_mgr.mark_stage_complete(plan_id, "planning", {"test": "data"}),
            timeout=2.0,
        )
    except TimeoutError:
        pytest.fail("Deadlock detected in mark_stage_complete")

    state = await state_mgr.load_state(plan_id)
    assert state["stages"]["planning"]["status"] == "completed"
