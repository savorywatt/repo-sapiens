"""
Checkpoint management for workflow recovery.
Provides save points to resume workflows after failures.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class CheckpointManager:
    """Manage workflow checkpoints for recovery."""

    def __init__(self, checkpoint_dir: str = ".automation/checkpoints") -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, plan_id: str) -> asyncio.Lock:
        """Get or create lock for plan."""
        if plan_id not in self._locks:
            self._locks[plan_id] = asyncio.Lock()
        return self._locks[plan_id]

    async def create_checkpoint(
        self, plan_id: str, stage: str, checkpoint_data: dict[str, Any]
    ) -> str:
        """Create a recovery checkpoint."""
        checkpoint_id = f"{plan_id}-{stage}-{int(datetime.now().timestamp())}"

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "plan_id": plan_id,
            "stage": stage,
            "created_at": datetime.now().isoformat(),
            "data": checkpoint_data,
        }

        async with self._get_lock(plan_id):
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
            checkpoint_file.write_text(json.dumps(checkpoint, indent=2))

        log.info("checkpoint_created", checkpoint_id=checkpoint_id, stage=stage)
        return checkpoint_id

    async def get_latest_checkpoint(
        self, plan_id: str, stage: str | None = None
    ) -> dict[str, Any] | None:
        """Get the most recent checkpoint for a plan."""
        pattern = f"{plan_id}-{stage}-*" if stage else f"{plan_id}-*"
        checkpoints = sorted(self.checkpoint_dir.glob(f"{pattern}.json"), reverse=True)

        if not checkpoints:
            return None

        checkpoint_data = json.loads(checkpoints[0].read_text())
        log.info("checkpoint_loaded", checkpoint_id=checkpoint_data["checkpoint_id"])
        return checkpoint_data

    async def get_all_checkpoints(self, plan_id: str) -> list[dict[str, Any]]:
        """Get all checkpoints for a plan, ordered by creation time."""
        checkpoints = sorted(self.checkpoint_dir.glob(f"{plan_id}-*.json"), reverse=True)
        return [json.loads(cp.read_text()) for cp in checkpoints]

    async def delete_checkpoints(self, plan_id: str) -> None:
        """Delete all checkpoints for a plan."""
        async with self._get_lock(plan_id):
            for checkpoint_file in self.checkpoint_dir.glob(f"{plan_id}-*.json"):
                checkpoint_file.unlink()
        log.info("checkpoints_deleted", plan_id=plan_id)

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """
        Clean up checkpoints older than max_age_days.
        Returns number of checkpoints deleted.
        """
        cutoff = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        deleted = 0

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                checkpoint = json.loads(checkpoint_file.read_text())
                created_at = datetime.fromisoformat(checkpoint["created_at"])

                if created_at.timestamp() < cutoff:
                    checkpoint_file.unlink()
                    deleted += 1
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                log.warning("invalid_checkpoint_file", file=str(checkpoint_file), error=str(e))
                continue

        if deleted > 0:
            log.info("old_checkpoints_cleaned", count=deleted, max_age_days=max_age_days)

        return deleted
