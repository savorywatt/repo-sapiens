"""Dependency tracking for task execution order management."""

import structlog

from automation.models.domain import Task

log = structlog.get_logger(__name__)


class DependencyTracker:
    """Track and resolve task dependencies.

    Manages task execution order based on dependencies, detects circular
    dependencies, and determines which tasks are ready to execute.
    """

    def __init__(self) -> None:
        """Initialize dependency tracker."""
        self.tasks: dict[str, Task] = {}
        self.status: dict[str, str] = {}

    def add_task(self, task: Task) -> None:
        """Add task to tracker.

        Args:
            task: Task to track
        """
        self.tasks[task.id] = task
        self.status[task.id] = "pending"
        log.debug("task_added", task_id=task.id)

    def is_ready(self, task_id: str) -> bool:
        """Check if task is ready to execute (all dependencies complete).

        Args:
            task_id: Task identifier

        Returns:
            True if task can be executed, False otherwise
        """
        if task_id not in self.tasks:
            log.warning("task_not_found", task_id=task_id)
            return False

        task = self.tasks[task_id]

        # Check all dependencies are completed
        for dep_id in task.dependencies:
            if dep_id not in self.status:
                log.warning("dependency_not_tracked", task_id=task_id, dependency=dep_id)
                return False

            if self.status[dep_id] != "completed":
                log.debug(
                    "dependency_not_ready",
                    task_id=task_id,
                    dependency=dep_id,
                    status=self.status[dep_id],
                )
                return False

        return True

    def mark_complete(self, task_id: str) -> None:
        """Mark task as completed.

        Args:
            task_id: Task identifier
        """
        if task_id not in self.status:
            log.warning("marking_unknown_task_complete", task_id=task_id)
            return

        self.status[task_id] = "completed"
        log.info("task_completed", task_id=task_id)

    def mark_failed(self, task_id: str) -> None:
        """Mark task as failed.

        Args:
            task_id: Task identifier
        """
        if task_id not in self.status:
            log.warning("marking_unknown_task_failed", task_id=task_id)
            return

        self.status[task_id] = "failed"
        log.error("task_failed", task_id=task_id)

    def mark_in_progress(self, task_id: str) -> None:
        """Mark task as in progress.

        Args:
            task_id: Task identifier
        """
        if task_id not in self.status:
            log.warning("marking_unknown_task_in_progress", task_id=task_id)
            return

        self.status[task_id] = "in_progress"
        log.info("task_in_progress", task_id=task_id)

    def get_ready_tasks(self) -> list[Task]:
        """Get all tasks ready for execution.

        Returns:
            List of tasks that can be executed now
        """
        ready = []
        for task_id, task in self.tasks.items():
            if self.status[task_id] == "pending" and self.is_ready(task_id):
                ready.append(task)

        log.debug("ready_tasks_identified", count=len(ready))
        return ready

    def has_pending_tasks(self) -> bool:
        """Check if there are any pending tasks.

        Returns:
            True if pending tasks exist
        """
        return any(status == "pending" for status in self.status.values())

    def get_blocked_tasks(self) -> list[Task]:
        """Get tasks that are blocked by failed dependencies.

        Returns:
            List of blocked tasks
        """
        blocked = []
        for task_id, task in self.tasks.items():
            if self.status[task_id] == "pending":
                # Check if any dependency failed
                for dep_id in task.dependencies:
                    if self.status.get(dep_id) == "failed":
                        blocked.append(task)
                        break

        if blocked:
            log.warning("blocked_tasks_found", count=len(blocked))

        return blocked

    def get_in_progress_tasks(self) -> list[Task]:
        """Get tasks currently in progress.

        Returns:
            List of in-progress tasks
        """
        in_progress = []
        for task_id, task in self.tasks.items():
            if self.status[task_id] == "in_progress":
                in_progress.append(task)

        return in_progress

    def validate_dependencies(self) -> bool:
        """Check for circular dependencies and invalid references.

        Returns:
            True if dependencies are valid, False otherwise

        Raises:
            ValueError: If circular dependency or invalid reference detected
        """

        def has_cycle(
            task_id: str,
            visited: set[str],
            rec_stack: set[str],
        ) -> bool:
            """Detect cycles using DFS with recursion stack."""
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks[task_id]
            for dep_id in task.dependencies:
                # Check for invalid dependency reference
                if dep_id not in self.tasks:
                    raise ValueError(
                        f"Invalid dependency: {dep_id} referenced by {task_id} but not found"
                    )

                if dep_id not in visited:
                    if has_cycle(dep_id, visited, rec_stack):
                        return True
                elif dep_id in rec_stack:
                    # Cycle detected
                    log.error(
                        "circular_dependency_detected",
                        task_id=task_id,
                        dependency=dep_id,
                    )
                    return True

            rec_stack.remove(task_id)
            return False

        visited: set[str] = set()

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id, visited, set()):
                    raise ValueError(f"Circular dependency detected involving task {task_id}")

        log.info("dependencies_validated", task_count=len(self.tasks))
        return True

    def get_execution_order(self) -> list[list[str]]:
        """Get task execution order as list of batches.

        Each batch contains tasks that can be executed in parallel.

        Returns:
            List of batches, where each batch is a list of task IDs

        Example:
            [
                ["task-1", "task-2"],  # Can execute in parallel
                ["task-3"],             # Depends on task-1 and task-2
                ["task-4", "task-5"],   # Can execute in parallel after task-3
            ]
        """
        # Validate first
        self.validate_dependencies()

        batches: list[list[str]] = []
        completed: set[str] = set()
        remaining = set(self.tasks.keys())

        while remaining:
            # Find tasks ready to execute
            ready_in_batch = []

            for task_id in remaining:
                task = self.tasks[task_id]
                # Check if all dependencies are completed
                if all(dep in completed for dep in task.dependencies):
                    ready_in_batch.append(task_id)

            if not ready_in_batch:
                # This shouldn't happen if validation passed, but just in case
                log.error("execution_order_deadlock", remaining=list(remaining))
                raise RuntimeError(f"Deadlock in execution order. Remaining tasks: {remaining}")

            # Add batch
            batches.append(ready_in_batch)

            # Mark as completed and remove from remaining
            completed.update(ready_in_batch)
            remaining -= set(ready_in_batch)

        log.info("execution_order_calculated", batches=len(batches))
        return batches

    def get_task_status(self, task_id: str) -> str:
        """Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Status string ("pending", "in_progress", "completed", "failed")
        """
        return self.status.get(task_id, "unknown")

    def get_summary(self) -> dict[str, int]:
        """Get summary of task statuses.

        Returns:
            Dictionary mapping status to count
        """
        summary: dict[str, int] = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
        }

        for status in self.status.values():
            if status in summary:
                summary[status] += 1

        return summary
