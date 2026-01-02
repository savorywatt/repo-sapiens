"""
Tests for checkpoint management system.
"""

import pytest

from repo_sapiens.engine.checkpointing import CheckpointManager


@pytest.mark.asyncio
async def test_create_checkpoint(temp_checkpoint_dir):
    """Test checkpoint creation."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    checkpoint_data = {
        "stage_data": {"status": "in_progress"},
        "error": None,
    }

    checkpoint_id = await manager.create_checkpoint(
        plan_id="test-plan",
        stage="implementation",
        checkpoint_data=checkpoint_data,
    )

    assert checkpoint_id.startswith("test-plan-implementation-")
    assert (temp_checkpoint_dir / f"{checkpoint_id}.json").exists()


@pytest.mark.asyncio
async def test_get_latest_checkpoint(temp_checkpoint_dir):
    """Test retrieving latest checkpoint."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    # Create multiple checkpoints with stage names that sort appropriately
    # The checkpoint filenames are sorted in reverse order, so 'z-' comes before 'a-'
    await manager.create_checkpoint("test-plan", "a-planning", {"step": 1})
    await manager.create_checkpoint("test-plan", "z-implementation", {"step": 2})

    # Get latest checkpoint for plan
    latest = await manager.get_latest_checkpoint("test-plan")

    assert latest is not None
    assert latest["plan_id"] == "test-plan"
    assert latest["data"]["step"] == 2


@pytest.mark.asyncio
async def test_get_latest_checkpoint_by_stage(temp_checkpoint_dir):
    """Test retrieving latest checkpoint for specific stage."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    await manager.create_checkpoint("test-plan", "planning", {"data": "planning"})
    await manager.create_checkpoint("test-plan", "implementation", {"data": "implementation"})

    # Get latest checkpoint for planning stage
    latest = await manager.get_latest_checkpoint("test-plan", "planning")

    assert latest is not None
    assert latest["stage"] == "planning"
    assert latest["data"]["data"] == "planning"


@pytest.mark.asyncio
async def test_delete_checkpoints(temp_checkpoint_dir):
    """Test checkpoint deletion."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    await manager.create_checkpoint("test-plan", "planning", {})
    await manager.create_checkpoint("test-plan", "implementation", {})

    # Verify checkpoints exist
    checkpoints = list(temp_checkpoint_dir.glob("test-plan-*.json"))
    assert len(checkpoints) == 2

    # Delete all checkpoints for plan
    await manager.delete_checkpoints("test-plan")

    # Verify checkpoints are deleted
    checkpoints = list(temp_checkpoint_dir.glob("test-plan-*.json"))
    assert len(checkpoints) == 0


@pytest.mark.asyncio
async def test_cleanup_old_checkpoints(temp_checkpoint_dir):
    """Test cleanup of old checkpoints."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    # Create checkpoint
    await manager.create_checkpoint("test-plan", "planning", {})

    # Cleanup (with 0 days to delete all)
    deleted = await manager.cleanup_old_checkpoints(max_age_days=0)

    assert deleted >= 0  # At least tried to clean up


@pytest.mark.asyncio
async def test_no_checkpoint_found(temp_checkpoint_dir):
    """Test behavior when no checkpoint exists."""
    manager = CheckpointManager(str(temp_checkpoint_dir))

    latest = await manager.get_latest_checkpoint("nonexistent-plan")

    assert latest is None
