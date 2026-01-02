"""
Optimized parallel task execution with dependency management.
Implements intelligent task scheduling with concurrency controls.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 150


@dataclass
class ExecutionTask:
    """Task for parallel execution."""

    id: str
    func: Callable[..., Any]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    dependencies: set[str] = field(default_factory=set)
    priority: int = TaskPriority.NORMAL
    timeout: float = 3600.0  # 1 hour default timeout
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of task execution."""

    task_id: str
    success: bool
    result: Any = None
    error: Exception | None = None
    execution_time: float = 0.0


class ParallelExecutor:
    """Optimized parallel task execution with dependency management."""

    def __init__(self, max_workers: int = 3) -> None:
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_tasks(self, tasks: list[ExecutionTask]) -> dict[str, TaskResult]:
        """Execute tasks in parallel respecting dependencies and limits."""
        results: dict[str, TaskResult] = {}
        pending = {task.id: task for task in tasks}
        completed: set[str] = set()
        failed: set[str] = set()
        in_progress: set[str] = set()

        log.info("parallel_execution_started", total_tasks=len(tasks), max_workers=self.max_workers)

        while pending or in_progress:
            # Find ready tasks (no unmet dependencies)
            ready = [task for task in pending.values() if not (task.dependencies - completed)]

            if not ready and not in_progress:
                # Check if we're deadlocked or have failed dependencies
                remaining_ids = set(pending.keys())
                blocked_by_failures = any(task.dependencies & failed for task in pending.values())

                if blocked_by_failures:
                    log.error(
                        "tasks_blocked_by_failures",
                        blocked_tasks=list(remaining_ids),
                        failed_tasks=list(failed),
                    )
                    # Mark remaining tasks as failed due to dependency failure
                    for task_id in remaining_ids:
                        results[task_id] = TaskResult(
                            task_id=task_id,
                            success=False,
                            error=Exception("Dependency failure"),
                        )
                    break
                else:
                    log.error("dependency_deadlock", remaining_tasks=list(remaining_ids))
                    raise RuntimeError("Dependency deadlock detected")

            # Sort ready tasks by priority
            ready.sort(key=lambda t: t.priority, reverse=True)

            # Execute batch of ready tasks
            available_slots = self.max_workers - len(in_progress)
            batch = ready[:available_slots]

            if batch:
                batch_tasks = []
                for task in batch:
                    batch_tasks.append(asyncio.create_task(self._execute_task(task)))
                    in_progress.add(task.id)
                    del pending[task.id]

                # Wait for at least one task to complete
                done, _ = await asyncio.wait(batch_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Process completed tasks
                for completed_task in done:
                    result = await completed_task
                    in_progress.discard(result.task_id)

                    if result.success:
                        log.info(
                            "task_completed",
                            task_id=result.task_id,
                            execution_time=result.execution_time,
                        )
                        completed.add(result.task_id)
                    else:
                        log.error(
                            "task_failed",
                            task_id=result.task_id,
                            error=str(result.error),
                        )
                        failed.add(result.task_id)

                    results[result.task_id] = result
            else:
                # Wait a bit for in-progress tasks
                await asyncio.sleep(0.1)

        log.info(
            "parallel_execution_complete",
            total=len(tasks),
            completed=len(completed),
            failed=len(failed),
        )

        return results

    async def _execute_task(self, task: ExecutionTask) -> TaskResult:
        """Execute a single task with semaphore control and timeout."""
        import time

        start_time = time.time()

        async with self.semaphore:
            log.info("executing_task", task_id=task.id, priority=task.priority)

            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    task.func(*task.args, **task.kwargs), timeout=task.timeout
                )

                execution_time = time.time() - start_time

                return TaskResult(
                    task_id=task.id,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                )

            except TimeoutError as e:
                execution_time = time.time() - start_time
                log.error("task_timeout", task_id=task.id, timeout=task.timeout)
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=e,
                    execution_time=execution_time,
                )

            except Exception as e:
                execution_time = time.time() - start_time
                log.error("task_exception", task_id=task.id, error=str(e), exc_info=True)
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=e,
                    execution_time=execution_time,
                )


class TaskScheduler:
    """Intelligent task scheduling with cost optimization."""

    def __init__(self, executor: ParallelExecutor) -> None:
        self.executor = executor

    def optimize_execution_order(self, tasks: list[ExecutionTask]) -> list[ExecutionTask]:
        """Optimize task execution order for minimum cost and time."""
        # Build dependency graph
        graph = self._build_dependency_graph(tasks)

        # Calculate critical path
        critical_path = self._find_critical_path(graph)

        # Prioritize critical path tasks
        for task in tasks:
            if task.id in critical_path:
                task.priority += 100

        log.info("execution_order_optimized", critical_path_length=len(critical_path))

        return tasks

    def _build_dependency_graph(self, tasks: list[ExecutionTask]) -> dict[str, dict[str, Any]]:
        """Build dependency graph from tasks."""
        graph: dict[str, dict[str, Any]] = {}

        for task in tasks:
            graph[task.id] = {
                "task": task,
                "dependencies": task.dependencies,
                "dependents": set(),
            }

        # Add reverse edges (dependents)
        for task_id, node in graph.items():
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    graph[dep_id]["dependents"].add(task_id)

        return graph

    def _find_critical_path(self, graph: dict[str, dict[str, Any]]) -> set[str]:
        """
        Find critical path through task graph using Critical Path Method (CPM).
        Returns set of task IDs on the critical path.
        """
        # For simplicity, we'll use a basic implementation
        # In production, would implement full CPM with estimated task durations

        critical_tasks: set[str] = set()

        # Find leaf nodes (no dependents)
        leaves = [tid for tid, node in graph.items() if not node["dependents"]]

        # For each leaf, trace back to find longest path
        def find_longest_path(task_id: str, visited: set[str]) -> int:
            if task_id in visited:
                return 0

            visited.add(task_id)
            node = graph[task_id]

            if not node["dependencies"]:
                return 1

            max_depth = 0
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    depth = find_longest_path(dep_id, visited.copy())
                    max_depth = max(max_depth, depth)

            return max_depth + 1

        # Find the deepest path
        max_depth = 0
        for leaf_id in leaves:
            depth = find_longest_path(leaf_id, set())
            if depth > max_depth:
                max_depth = depth

        # Mark tasks on critical paths
        def mark_critical(task_id: str, target_depth: int, current_depth: int) -> None:
            if current_depth == target_depth:
                critical_tasks.add(task_id)
                return

            node = graph[task_id]
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    mark_critical(dep_id, target_depth, current_depth + 1)

        for leaf_id in leaves:
            mark_critical(leaf_id, max_depth, 1)

        return critical_tasks

    async def execute_with_optimization(self, tasks: list[ExecutionTask]) -> dict[str, TaskResult]:
        """Execute tasks with optimization."""
        optimized_tasks = self.optimize_execution_order(tasks)
        return await self.executor.execute_tasks(optimized_tasks)
