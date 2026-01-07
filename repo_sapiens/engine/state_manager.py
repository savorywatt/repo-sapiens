"""
State management with atomic transactions for workflow persistence.

This module provides the StateManager class which handles persistence of workflow
state to disk with support for atomic updates via transactions.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import aiofiles
import structlog

from repo_sapiens.engine.types import StagesDict, StageState, TaskState, WorkflowState

log = structlog.get_logger(__name__)


class StateManager:
    """Manage workflow state with atomic file operations."""

    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

    async def _get_lock(self, plan_id: str) -> asyncio.Lock:
        """Get or create lock for plan_id (thread-safe)."""
        async with self._locks_lock:
            if plan_id not in self._locks:
                self._locks[plan_id] = asyncio.Lock()
            return self._locks[plan_id]

    def _get_state_path(self, plan_id: str) -> Path:
        """Get path to state file for plan_id."""
        return self.state_dir / f"{plan_id}.json"

    async def _load_state_internal(self, plan_id: str) -> WorkflowState:
        """Load state without acquiring lock (caller must hold lock)."""
        state_path = self._get_state_path(plan_id)

        if not state_path.exists():
            state = self._create_initial_state(plan_id)
            await self._write_state(state_path, state)
            return state

        async with aiofiles.open(state_path) as f:
            content = await f.read()
            return cast(WorkflowState, json.loads(content))

    async def _save_state_internal(self, plan_id: str, state: WorkflowState) -> None:
        """Save state without acquiring lock (caller must hold lock)."""
        state_path = self._get_state_path(plan_id)
        state["updated_at"] = datetime.now(UTC).isoformat()
        state["status"] = self._calculate_overall_status(state)
        await self._write_state(state_path, state)

    async def load_state(self, plan_id: str) -> WorkflowState:
        """Load state for plan_id, creating if doesn't exist."""
        lock = await self._get_lock(plan_id)
        async with lock:
            return await self._load_state_internal(plan_id)

    async def save_state(self, plan_id: str, state: WorkflowState) -> None:
        """Atomically save state for plan_id."""
        lock = await self._get_lock(plan_id)
        async with lock:
            await self._save_state_internal(plan_id, state)

    async def _write_state(self, path: Path, state: WorkflowState) -> None:
        """Write state atomically using tmp file."""
        tmp_path = path.with_suffix(".tmp")

        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(json.dumps(state, indent=2))

        tmp_path.replace(path)

    @asynccontextmanager
    async def transaction(self, plan_id: str) -> AsyncIterator[WorkflowState]:
        """Context manager for atomic state updates."""
        lock = await self._get_lock(plan_id)
        async with lock:
            state = await self._load_state_internal(plan_id)
            try:
                yield state
                await self._save_state_internal(plan_id, state)
            except Exception:
                log.error("state_transaction_failed", plan_id=plan_id)
                raise

    def _create_initial_state(self, plan_id: str) -> WorkflowState:
        """Create initial state structure."""
        now = datetime.now(UTC).isoformat()
        initial_stage: StageState = {"status": "pending", "data": {}}
        stages: StagesDict = {
            "planning": initial_stage.copy(),
            "plan_review": initial_stage.copy(),
            "prompts": initial_stage.copy(),
            "implementation": initial_stage.copy(),
            "code_review": initial_stage.copy(),
            "merge": initial_stage.copy(),
        }
        return {
            "plan_id": plan_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "stages": stages,
            "tasks": {},
            "metadata": {},
        }

    def _calculate_overall_status(self, state: WorkflowState) -> str:
        """Calculate overall workflow status from stage statuses."""
        stages = state.get("stages", {})

        # Check for failures
        if any(s.get("status") == "failed" for s in stages.values()):
            return "failed"

        # Check if all completed
        if all(s.get("status") == "completed" for s in stages.values()):
            return "completed"

        # Check if any in progress
        if any(s.get("status") == "in_progress" for s in stages.values()):
            return "in_progress"

        return "pending"

    async def mark_stage_complete(
        self, plan_id: str, stage: str, data: dict[str, Any] | None = None
    ) -> None:
        """Mark a stage as completed."""
        async with self.transaction(plan_id) as state:
            if stage in state["stages"]:
                state["stages"][stage]["status"] = "completed"
                state["stages"][stage]["completed_at"] = datetime.now(UTC).isoformat()
                if data:
                    state["stages"][stage]["data"] = data

        log.info("stage_completed", plan_id=plan_id, stage=stage)

    async def mark_task_status(
        self, plan_id: str, task_id: str, status: str, data: dict[str, Any] | None = None
    ) -> None:
        """Update task status."""
        async with self.transaction(plan_id) as state:
            if "tasks" not in state:
                state["tasks"] = {}

            now = datetime.now(UTC).isoformat()
            if task_id not in state["tasks"]:
                new_task: TaskState = {"status": status, "updated_at": now}
                state["tasks"][task_id] = new_task
            else:
                state["tasks"][task_id]["status"] = status
                state["tasks"][task_id]["updated_at"] = now

            if data:
                state["tasks"][task_id]["data"] = data

        log.info("task_status_updated", plan_id=plan_id, task_id=task_id, status=status)

    async def get_active_plans(self) -> list[str]:
        """Get list of active plan IDs."""
        active = []
        for state_file in self.state_dir.glob("*.json"):
            plan_id = state_file.stem
            state = await self.load_state(plan_id)
            if state["status"] not in ["completed", "failed"]:
                active.append(plan_id)
        return active
