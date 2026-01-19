"""
State management with atomic transactions for workflow persistence.

This module provides the StateManager class which handles persistence of workflow
state to disk with support for atomic updates via transactions. The state manager
ensures data integrity through:

- Atomic file writes using temporary files and rename operations
- Per-plan locking to prevent concurrent modification
- Automatic status calculation based on stage states

State File Structure:
    State is persisted as JSON files in a configurable directory. Each plan
    gets its own file named ``{plan_id}.json`` with the following structure::

        {
            "plan_id": "plan-42",
            "status": "in_progress",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T11:45:00Z",
            "stages": {
                "planning": {"status": "completed", "data": {...}},
                "implementation": {"status": "in_progress", "data": {...}},
                ...
            },
            "tasks": {
                "task-1": {"status": "completed", "updated_at": "..."},
                ...
            },
            "metadata": {}
        }

Transaction Support:
    The ``transaction()`` context manager provides atomic state updates::

        async with state_manager.transaction("plan-42") as state:
            state["metadata"]["key"] = "value"
            # Changes are saved atomically on context exit

Concurrency Model:
    Each plan has its own asyncio lock to prevent concurrent modifications.
    Multiple plans can be accessed concurrently, but each individual plan
    is accessed serially.

Example:
    >>> state = StateManager(".sapiens/state")
    >>> workflow = await state.load_state("plan-42")
    >>> workflow["metadata"]["foo"] = "bar"
    >>> await state.save_state("plan-42", workflow)
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
    """Manage workflow state with atomic file operations.

    Provides persistent storage for workflow state with support for atomic
    updates, concurrent access control, and automatic status calculation.
    State is stored as JSON files, one per plan.

    Attributes:
        state_dir: Directory where state files are stored.

    Thread Safety:
        This class is designed for single-threaded asyncio usage. Each plan
        has its own lock, but the lock management itself uses a meta-lock
        to ensure thread-safe lock creation.

    Example:
        >>> manager = StateManager("/path/to/state")
        >>> state = await manager.load_state("plan-1")
        >>> state["metadata"]["key"] = "value"
        >>> await manager.save_state("plan-1", state)
    """

    def __init__(self, state_dir: str | Path) -> None:
        """Initialize the state manager with a storage directory.

        Creates the state directory if it does not exist. The directory
        will be used to store JSON state files for each plan.

        Args:
            state_dir: Path to the directory for storing state files.
                Can be a string or Path object. Will be created if it
                does not exist, including any necessary parent directories.

        Side Effects:
            Creates the state directory and any parent directories if
            they do not exist.

        Example:
            >>> manager = StateManager(".sapiens/state")
            >>> # Directory .sapiens/state/ now exists
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Per-plan locks to prevent concurrent modification of the same plan
        self._locks: dict[str, asyncio.Lock] = {}
        # Meta-lock for thread-safe lock creation
        self._locks_lock = asyncio.Lock()

    async def _get_lock(self, plan_id: str) -> asyncio.Lock:
        """Get or create an asyncio lock for the specified plan.

        Locks are created lazily on first access and cached for reuse.
        The lock creation is protected by a meta-lock to ensure thread
        safety when multiple coroutines try to access a new plan
        simultaneously.

        Args:
            plan_id: Unique identifier for the plan requiring a lock.

        Returns:
            An asyncio.Lock instance dedicated to this plan. The same
            lock instance is returned for subsequent calls with the
            same plan_id.

        Note:
            Locks are never cleaned up during the lifetime of the
            StateManager instance. For long-running processes with
            many plans, this could lead to memory growth.
        """
        async with self._locks_lock:
            if plan_id not in self._locks:
                self._locks[plan_id] = asyncio.Lock()
            return self._locks[plan_id]

    def _get_state_path(self, plan_id: str) -> Path:
        """Compute the filesystem path for a plan's state file.

        Args:
            plan_id: Unique identifier for the plan.

        Returns:
            Path to the JSON state file for this plan.

        Example:
            >>> manager._get_state_path("plan-42")
            Path(".sapiens/state/plan-42.json")
        """
        return self.state_dir / f"{plan_id}.json"

    async def _load_state_internal(self, plan_id: str) -> WorkflowState:
        """Load state from disk without acquiring the plan lock.

        This is an internal method that assumes the caller already holds
        the lock for this plan. Use ``load_state()`` for lock-safe access.

        If no state file exists, creates an initial state structure and
        persists it before returning.

        Args:
            plan_id: Unique identifier for the plan.

        Returns:
            WorkflowState dictionary containing the plan's current state.

        Raises:
            json.JSONDecodeError: If the state file contains invalid JSON.
            IOError: If the state file cannot be read.

        Warning:
            Caller MUST hold the plan lock before calling this method.
            Failure to do so may result in race conditions.
        """
        state_path = self._get_state_path(plan_id)

        if not state_path.exists():
            # Create initial state for new plans
            state = self._create_initial_state(plan_id)
            await self._write_state(state_path, state)
            return state

        async with aiofiles.open(state_path) as f:
            content = await f.read()
            return cast(WorkflowState, json.loads(content))

    async def _save_state_internal(self, plan_id: str, state: WorkflowState) -> None:
        """Save state to disk without acquiring the plan lock.

        This is an internal method that assumes the caller already holds
        the lock for this plan. Use ``save_state()`` for lock-safe access.

        Automatically updates the ``updated_at`` timestamp and recalculates
        the overall status based on stage states.

        Args:
            plan_id: Unique identifier for the plan.
            state: WorkflowState dictionary to persist.

        Raises:
            IOError: If the state file cannot be written.

        Side Effects:
            - Updates ``state["updated_at"]`` to current UTC time
            - Updates ``state["status"]`` based on stage statuses
            - Writes state to disk atomically

        Warning:
            Caller MUST hold the plan lock before calling this method.
        """
        state_path = self._get_state_path(plan_id)
        state["updated_at"] = datetime.now(UTC).isoformat()
        state["status"] = self._calculate_overall_status(state)
        await self._write_state(state_path, state)

    async def load_state(self, plan_id: str) -> WorkflowState:
        """Load the current state for a plan, creating initial state if needed.

        Acquires the plan lock before reading to ensure consistency. If no
        state file exists for this plan, an initial state structure is
        created and persisted.

        Args:
            plan_id: Unique identifier for the plan.

        Returns:
            WorkflowState dictionary containing the plan's current state,
            including stages, tasks, and metadata.

        Raises:
            json.JSONDecodeError: If the state file contains invalid JSON.
            IOError: If the state file cannot be read.

        Example:
            >>> state = await manager.load_state("plan-42")
            >>> print(state["status"])
            'pending'
        """
        lock = await self._get_lock(plan_id)
        async with lock:
            return await self._load_state_internal(plan_id)

    async def save_state(self, plan_id: str, state: WorkflowState) -> None:
        """Atomically save state for a plan.

        Acquires the plan lock before writing to ensure consistency. The
        write is atomic: state is first written to a temporary file, then
        renamed to the target path.

        The ``updated_at`` timestamp and ``status`` field are automatically
        updated before saving.

        Args:
            plan_id: Unique identifier for the plan.
            state: WorkflowState dictionary to persist.

        Raises:
            IOError: If the state file cannot be written.

        Side Effects:
            - Updates ``state["updated_at"]`` in place
            - Updates ``state["status"]`` in place
            - Writes state to disk

        Example:
            >>> state = await manager.load_state("plan-42")
            >>> state["metadata"]["key"] = "value"
            >>> await manager.save_state("plan-42", state)
        """
        lock = await self._get_lock(plan_id)
        async with lock:
            await self._save_state_internal(plan_id, state)

    async def _write_state(self, path: Path, state: WorkflowState) -> None:
        """Write state to disk atomically using a temporary file.

        The atomic write pattern prevents partial writes from corrupting
        the state file. State is written to a .tmp file first, then
        renamed to the target path. On POSIX systems, rename is atomic
        when source and destination are on the same filesystem.

        Args:
            path: Target path for the state file.
            state: WorkflowState dictionary to write.

        Raises:
            IOError: If writing or renaming fails.

        Note:
            The temporary file is created in the same directory as the
            target to ensure they are on the same filesystem.
        """
        tmp_path = path.with_suffix(".tmp")

        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(json.dumps(state, indent=2))

        # Atomic rename - safe on POSIX when same filesystem
        tmp_path.replace(path)

    @asynccontextmanager
    async def transaction(self, plan_id: str) -> AsyncIterator[WorkflowState]:
        """Context manager for atomic state updates.

        Provides a convenient way to read, modify, and save state in a
        single atomic operation. The state is loaded when entering the
        context, and any modifications are saved when exiting.

        If an exception occurs within the context, the state is NOT saved
        and the exception is re-raised after logging.

        Args:
            plan_id: Unique identifier for the plan.

        Yields:
            WorkflowState dictionary that can be modified in place.
            Changes are automatically saved on successful context exit.

        Raises:
            Exception: Re-raises any exception that occurs within the
                context after logging the failure.

        Example:
            >>> async with manager.transaction("plan-42") as state:
            ...     state["metadata"]["processed"] = True
            ...     state["stages"]["planning"]["status"] = "completed"
            >>> # Changes are now persisted

        Note:
            The lock is held for the entire duration of the context.
            Keep transactions short to avoid blocking other operations.
        """
        lock = await self._get_lock(plan_id)
        async with lock:
            state = await self._load_state_internal(plan_id)
            try:
                yield state
                # Only save if no exception occurred
                await self._save_state_internal(plan_id, state)
            except Exception:
                log.error("state_transaction_failed", plan_id=plan_id)
                raise

    def _create_initial_state(self, plan_id: str) -> WorkflowState:
        """Create the initial state structure for a new plan.

        Initializes all standard workflow stages with pending status.
        This provides a consistent starting point for all new plans.

        Args:
            plan_id: Unique identifier for the new plan.

        Returns:
            WorkflowState dictionary with all fields initialized to
            their default values.

        Note:
            The initial stages are: planning, plan_review, prompts,
            implementation, code_review, and merge. All start with
            status "pending" and empty data dictionaries.
        """
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
        """Calculate the overall workflow status from individual stage statuses.

        Applies the following priority rules:
            1. If ANY stage has failed -> "failed"
            2. If ALL stages are completed -> "completed"
            3. If ANY stage is in_progress -> "in_progress"
            4. Otherwise -> "pending"

        Args:
            state: WorkflowState dictionary containing stage information.

        Returns:
            One of: "failed", "completed", "in_progress", or "pending".

        Example:
            >>> state = {"stages": {
            ...     "planning": {"status": "completed"},
            ...     "implementation": {"status": "in_progress"},
            ... }}
            >>> manager._calculate_overall_status(state)
            'in_progress'
        """
        stages = state.get("stages", {})

        # Check for failures - any failure means workflow failed
        if any(s.get("status") == "failed" for s in stages.values()):
            return "failed"

        # Check if all completed - all must be complete for workflow to be complete
        if all(s.get("status") == "completed" for s in stages.values()):
            return "completed"

        # Check if any in progress - active work happening
        if any(s.get("status") == "in_progress" for s in stages.values()):
            return "in_progress"

        # Default to pending if no work has started
        return "pending"

    async def mark_stage_complete(self, plan_id: str, stage: str, data: dict[str, Any] | None = None) -> None:
        """Mark a workflow stage as completed.

        Updates the stage status to "completed", records the completion
        timestamp, and optionally stores additional data with the stage.

        Args:
            plan_id: Unique identifier for the plan.
            stage: Name of the stage to mark complete (e.g., "planning",
                "implementation").
            data: Optional dictionary of data to store with the stage.
                This typically includes results or metadata from the
                stage execution.

        Side Effects:
            - Updates stage status to "completed"
            - Sets ``completed_at`` timestamp on the stage
            - Stores provided data in stage's ``data`` field
            - Logs completion event

        Example:
            >>> await manager.mark_stage_complete(
            ...     "plan-42",
            ...     "planning",
            ...     {"plan_path": "plans/issue-1.md", "review_issue": 5}
            ... )
        """
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
        """Update the status of a task within a plan.

        Creates the task entry if it doesn't exist, or updates an existing
        task's status. Also updates the task's ``updated_at`` timestamp
        and optionally stores additional data.

        Args:
            plan_id: Unique identifier for the plan containing the task.
            task_id: Unique identifier for the task within the plan.
            status: New status for the task. Common values include:
                "pending", "in_progress", "completed", "failed",
                "merge_ready".
            data: Optional dictionary of data to store with the task.
                This typically includes execution results or error details.

        Side Effects:
            - Creates task entry if it doesn't exist
            - Updates task status and ``updated_at`` timestamp
            - Stores provided data in task's ``data`` field
            - Logs status update event

        Example:
            >>> await manager.mark_task_status(
            ...     "plan-42",
            ...     "task-1",
            ...     "completed",
            ...     {"branch": "feature/task-1", "pr_number": 15}
            ... )
        """
        async with self.transaction(plan_id) as state:
            if "tasks" not in state:
                state["tasks"] = {}

            now = datetime.now(UTC).isoformat()
            if task_id not in state["tasks"]:
                # Create new task entry
                new_task: TaskState = {"status": status, "updated_at": now}
                state["tasks"][task_id] = new_task
            else:
                # Update existing task
                state["tasks"][task_id]["status"] = status
                state["tasks"][task_id]["updated_at"] = now

            if data:
                state["tasks"][task_id]["data"] = data

        log.info("task_status_updated", plan_id=plan_id, task_id=task_id, status=status)

    async def get_active_plans(self) -> list[str]:
        """Get a list of all plans that are still in progress.

        Scans the state directory for all plan state files and returns
        the IDs of plans that are not yet completed or failed.

        Returns:
            List of plan IDs that have status other than "completed"
            or "failed". Returns an empty list if no active plans exist.

        Note:
            This method loads each plan's state to check its status,
            which could be slow for directories with many plans.

        Example:
            >>> active = await manager.get_active_plans()
            >>> print(active)
            ['plan-42', 'plan-55']
        """
        active = []
        for state_file in self.state_dir.glob("*.json"):
            plan_id = state_file.stem
            state = await self.load_state(plan_id)
            if state["status"] not in ["completed", "failed"]:
                active.append(plan_id)
        return active
