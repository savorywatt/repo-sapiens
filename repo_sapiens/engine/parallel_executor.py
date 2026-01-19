"""
Optimized parallel task execution with dependency management.

This module provides infrastructure for executing tasks in parallel while
respecting dependency constraints and concurrency limits. It implements
intelligent task scheduling with support for:

- Dependency-aware execution ordering
- Configurable concurrency limits via semaphore
- Priority-based task scheduling
- Timeout handling for long-running tasks
- Critical path optimization for minimum execution time

Architecture:
    The module consists of three main components:

    1. ExecutionTask: Data class representing a task with its callable,
       arguments, dependencies, priority, and timeout.

    2. ParallelExecutor: Core executor that manages task execution with
       semaphore-based concurrency control and dependency tracking.

    3. TaskScheduler: Higher-level scheduler that optimizes execution order
       using critical path analysis.

Execution Flow:
    1. Tasks are submitted to the executor with dependencies specified
    2. Executor identifies tasks with satisfied dependencies
    3. Ready tasks are sorted by priority and executed up to max_workers
    4. As tasks complete, dependent tasks become ready
    5. Process continues until all tasks complete or are blocked by failures

Error Handling:
    - Individual task failures don't stop other independent tasks
    - Tasks dependent on failed tasks are marked as failed
    - Deadlocks are detected and reported as RuntimeError

Example:
    >>> executor = ParallelExecutor(max_workers=3)
    >>> tasks = [
    ...     ExecutionTask(id="setup", func=setup_fn),
    ...     ExecutionTask(id="build", func=build_fn, dependencies={"setup"}),
    ...     ExecutionTask(id="test", func=test_fn, dependencies={"build"}),
    ... ]
    >>> results = await executor.execute_tasks(tasks)
    >>> all(r.success for r in results.values())
    True
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class TaskPriority(int, Enum):
    """Priority levels for task execution ordering.

    Higher priority tasks are executed before lower priority tasks when
    multiple tasks are ready for execution. Priority is used as a tie-breaker
    when dependency constraints don't dictate order.

    Attributes:
        LOW: Background tasks that can wait (priority 0).
        NORMAL: Standard priority for most tasks (priority 50).
        HIGH: Elevated priority for important tasks (priority 100).
        CRITICAL: Highest priority for urgent tasks (priority 150).
    """

    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 150


@dataclass
class ExecutionTask:
    """Represents a task for parallel execution.

    Encapsulates all information needed to execute a task, including the
    callable, its arguments, dependencies on other tasks, priority, and
    timeout settings.

    Attributes:
        id: Unique identifier for the task. Used for dependency references.
        func: Async callable to execute. Must return an awaitable.
        args: Positional arguments to pass to the callable.
        kwargs: Keyword arguments to pass to the callable.
        dependencies: Set of task IDs that must complete before this task
            can run.
        priority: Execution priority (higher values = higher priority).
            Use TaskPriority enum values or integers.
        timeout: Maximum execution time in seconds. Task is cancelled if
            it exceeds this limit. Default is 3600 seconds (1 hour).
        metadata: Arbitrary metadata for the task. Not used by the executor
            but available for logging or debugging.

    Example:
        >>> async def my_task(x, y):
        ...     return x + y
        >>> task = ExecutionTask(
        ...     id="sum",
        ...     func=my_task,
        ...     args=(1, 2),
        ...     dependencies={"setup"},
        ...     priority=TaskPriority.HIGH,
        ... )
    """

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
    """Result of a task execution.

    Contains the outcome of executing a task, including success status,
    return value or error, and execution timing.

    Attributes:
        task_id: ID of the task that was executed.
        success: True if the task completed without error or timeout.
        result: Return value of the task callable (if successful).
        error: Exception that caused the task to fail (if unsuccessful).
        execution_time: Actual execution time in seconds.

    Example:
        >>> result = TaskResult(
        ...     task_id="my-task",
        ...     success=True,
        ...     result={"output": "data"},
        ...     execution_time=1.23,
        ... )
    """

    task_id: str
    success: bool
    result: Any = None
    error: Exception | None = None
    execution_time: float = 0.0


class ParallelExecutor:
    """Execute tasks in parallel with dependency management and concurrency control.

    The ParallelExecutor manages the execution of multiple tasks, respecting
    dependency relationships between them and limiting concurrency to avoid
    resource exhaustion.

    Execution proceeds in rounds: in each round, all tasks with satisfied
    dependencies are identified, sorted by priority, and executed up to
    the concurrency limit. As tasks complete, new tasks become ready.

    Attributes:
        max_workers: Maximum number of tasks that can execute concurrently.
        semaphore: Asyncio semaphore for concurrency control.

    Example:
        >>> executor = ParallelExecutor(max_workers=4)
        >>> results = await executor.execute_tasks(task_list)
        >>> failures = [r for r in results.values() if not r.success]
    """

    def __init__(self, max_workers: int = 3) -> None:
        """Initialize the parallel executor with a concurrency limit.

        Args:
            max_workers: Maximum number of tasks to execute concurrently.
                Defaults to 3. Higher values increase parallelism but may
                exhaust system resources.
        """
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_tasks(self, tasks: list[ExecutionTask]) -> dict[str, TaskResult]:
        """Execute all tasks in parallel, respecting dependencies and limits.

        Manages the complete execution lifecycle for a set of tasks:
            1. Tracks pending, in-progress, completed, and failed tasks
            2. Identifies ready tasks (dependencies satisfied)
            3. Executes ready tasks in priority order up to max_workers
            4. Handles task completion and failure propagation
            5. Detects deadlocks and dependency failures

        Args:
            tasks: List of ExecutionTask objects to execute. Each task
                specifies its dependencies, priority, and timeout.

        Returns:
            Dictionary mapping task IDs to their TaskResult objects.
            Contains results for all tasks, including those that failed
            due to dependency failures.

        Raises:
            RuntimeError: If a deadlock is detected (tasks remain pending
                but none can execute, and no tasks are in progress or failed).

        Side Effects:
            - Logs execution progress, completions, and failures
            - Executes task callables with their specified arguments

        Example:
            >>> tasks = [
            ...     ExecutionTask(id="a", func=task_a),
            ...     ExecutionTask(id="b", func=task_b, dependencies={"a"}),
            ... ]
            >>> results = await executor.execute_tasks(tasks)
            >>> results["b"].success
            True
        """
        results: dict[str, TaskResult] = {}
        pending = {task.id: task for task in tasks}
        completed: set[str] = set()
        failed: set[str] = set()
        in_progress: set[str] = set()

        log.info("parallel_execution_started", total_tasks=len(tasks), max_workers=self.max_workers)

        while pending or in_progress:
            # Find ready tasks - those with all dependencies satisfied
            ready = [task for task in pending.values() if not (task.dependencies - completed)]

            if not ready and not in_progress:
                # No tasks ready and none in progress - check for failures or deadlock
                remaining_ids = set(pending.keys())
                blocked_by_failures = any(task.dependencies & failed for task in pending.values())

                if blocked_by_failures:
                    # Tasks are blocked by failed dependencies
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
                    # True deadlock - circular dependencies or invalid graph
                    log.error("dependency_deadlock", remaining_tasks=list(remaining_ids))
                    raise RuntimeError("Dependency deadlock detected")

            # Sort ready tasks by priority (highest first)
            ready.sort(key=lambda t: t.priority, reverse=True)

            # Execute batch of ready tasks up to available slots
            available_slots = self.max_workers - len(in_progress)
            batch = ready[:available_slots]

            if batch:
                # Create asyncio tasks for the batch
                batch_tasks = []
                for task in batch:
                    batch_tasks.append(asyncio.create_task(self._execute_task(task)))
                    in_progress.add(task.id)
                    del pending[task.id]

                # Wait for at least one task to complete before continuing
                # This allows us to immediately start newly-ready tasks
                done, _ = await asyncio.wait(batch_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Process completed tasks and update tracking sets
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
                # No batch to start, wait briefly for in-progress tasks
                await asyncio.sleep(0.1)

        log.info(
            "parallel_execution_complete",
            total=len(tasks),
            completed=len(completed),
            failed=len(failed),
        )

        return results

    async def _execute_task(self, task: ExecutionTask) -> TaskResult:
        """Execute a single task with semaphore control and timeout.

        Wraps the task execution with:
            1. Semaphore acquisition to respect concurrency limits
            2. Timeout enforcement via asyncio.wait_for
            3. Execution timing measurement
            4. Error handling and result packaging

        The semaphore ensures that even if many tasks are started
        concurrently, only max_workers actually execute at any time.

        Args:
            task: The ExecutionTask to execute.

        Returns:
            TaskResult containing success status, result/error, and timing.
            Always returns a result (never raises); errors are captured
            in the TaskResult.

        Side Effects:
            - Logs task start, timeout errors, and exceptions
            - Executes the task's callable
        """
        import time

        start_time = time.time()

        # Semaphore controls actual concurrency (separate from scheduling)
        async with self.semaphore:
            log.info("executing_task", task_id=task.id, priority=task.priority)

            try:
                # Execute the task callable with timeout enforcement
                result = await asyncio.wait_for(task.func(*task.args, **task.kwargs), timeout=task.timeout)

                execution_time = time.time() - start_time

                return TaskResult(
                    task_id=task.id,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                )

            except TimeoutError as e:
                # Task exceeded its timeout limit
                execution_time = time.time() - start_time
                log.error("task_timeout", task_id=task.id, timeout=task.timeout)
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=e,
                    execution_time=execution_time,
                )

            except Exception as e:
                # Task raised an exception during execution
                execution_time = time.time() - start_time
                log.error("task_exception", task_id=task.id, error=str(e), exc_info=True)
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=e,
                    execution_time=execution_time,
                )


class TaskScheduler:
    """Intelligent task scheduling with critical path optimization.

    The TaskScheduler wraps a ParallelExecutor and adds optimization
    logic to improve execution time. It analyzes the dependency graph
    to identify the critical path and boost priority of tasks on that
    path.

    The critical path is the longest chain of dependent tasks, which
    determines the minimum possible execution time. By prioritizing
    these tasks, we ensure they start as early as possible.

    Attributes:
        executor: The ParallelExecutor used for actual task execution.

    Example:
        >>> executor = ParallelExecutor(max_workers=4)
        >>> scheduler = TaskScheduler(executor)
        >>> results = await scheduler.execute_with_optimization(tasks)
    """

    def __init__(self, executor: ParallelExecutor) -> None:
        """Initialize the scheduler with an executor.

        Args:
            executor: ParallelExecutor instance to use for task execution.
        """
        self.executor = executor

    def optimize_execution_order(self, tasks: list[ExecutionTask]) -> list[ExecutionTask]:
        """Optimize task execution order for minimum total time.

        Analyzes the dependency graph to find the critical path and
        increases the priority of tasks on that path by 100. This
        ensures critical path tasks are scheduled first when multiple
        tasks are ready.

        Args:
            tasks: List of tasks to optimize. Tasks are modified in place.

        Returns:
            The same task list with priorities adjusted. Critical path
            tasks have their priority increased by 100.

        Side Effects:
            - Modifies task.priority for tasks on the critical path
            - Logs the critical path length

        Note:
            This is a simplified implementation that doesn't account for
            estimated task durations. A full Critical Path Method (CPM)
            implementation would use duration estimates.
        """
        # Build dependency graph for analysis
        graph = self._build_dependency_graph(tasks)

        # Calculate critical path through the graph
        critical_path = self._find_critical_path(graph)

        # Boost priority of critical path tasks
        for task in tasks:
            if task.id in critical_path:
                task.priority += 100

        log.info("execution_order_optimized", critical_path_length=len(critical_path))

        return tasks

    def _build_dependency_graph(self, tasks: list[ExecutionTask]) -> dict[str, dict[str, Any]]:
        """Build a bidirectional dependency graph from task list.

        Creates a graph structure with both forward (dependencies) and
        reverse (dependents) edges for each task.

        Args:
            tasks: List of tasks to build graph from.

        Returns:
            Dictionary mapping task IDs to node data containing:
                - task: The ExecutionTask object
                - dependencies: Set of task IDs this task depends on
                - dependents: Set of task IDs that depend on this task

        Example:
            >>> graph = scheduler._build_dependency_graph(tasks)
            >>> graph["task-1"]["dependents"]
            {'task-2', 'task-3'}
        """
        graph: dict[str, dict[str, Any]] = {}

        # Build initial nodes with forward edges
        for task in tasks:
            graph[task.id] = {
                "task": task,
                "dependencies": task.dependencies,
                "dependents": set(),
            }

        # Add reverse edges (dependents) by traversing dependencies
        for task_id, node in graph.items():
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    graph[dep_id]["dependents"].add(task_id)

        return graph

    def _find_critical_path(self, graph: dict[str, dict[str, Any]]) -> set[str]:
        """Find the critical path through the task graph.

        Uses a simplified Critical Path Method (CPM) to identify tasks
        on the longest dependency chain. The critical path determines
        the minimum execution time regardless of parallelism.

        Algorithm:
            1. Find all leaf nodes (tasks with no dependents)
            2. For each leaf, trace back through dependencies
            3. Find the longest path from any leaf to a root
            4. Mark all tasks on paths of maximum length

        Args:
            graph: Dependency graph from _build_dependency_graph().

        Returns:
            Set of task IDs that are on the critical path.

        Note:
            This simplified implementation treats all tasks as having
            equal duration. A full CPM would use estimated durations
            for more accurate critical path calculation.
        """
        critical_tasks: set[str] = set()

        # Find leaf nodes (tasks with no dependents - end of chains)
        leaves = [tid for tid, node in graph.items() if not node["dependents"]]

        def find_longest_path(task_id: str, visited: set[str]) -> int:
            """Recursively find the longest path from task_id to a root."""
            if task_id in visited:
                return 0

            visited.add(task_id)
            node = graph[task_id]

            # Root node (no dependencies) has depth 1
            if not node["dependencies"]:
                return 1

            # Find max depth among all dependencies
            max_depth = 0
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    depth = find_longest_path(dep_id, visited.copy())
                    max_depth = max(max_depth, depth)

            return max_depth + 1

        # Find the maximum depth across all leaves
        max_depth = 0
        for leaf_id in leaves:
            depth = find_longest_path(leaf_id, set())
            if depth > max_depth:
                max_depth = depth

        def mark_critical(task_id: str, target_depth: int, current_depth: int) -> None:
            """Mark tasks that are on paths of the target depth."""
            if current_depth == target_depth:
                critical_tasks.add(task_id)
                return

            node = graph[task_id]
            for dep_id in node["dependencies"]:
                if dep_id in graph:
                    mark_critical(dep_id, target_depth, current_depth + 1)

        # Mark tasks on critical paths (those at maximum depth)
        for leaf_id in leaves:
            mark_critical(leaf_id, max_depth, 1)

        return critical_tasks

    async def execute_with_optimization(self, tasks: list[ExecutionTask]) -> dict[str, TaskResult]:
        """Execute tasks with critical path optimization.

        Optimizes the execution order first, then delegates to the
        ParallelExecutor for actual execution.

        Args:
            tasks: List of tasks to execute.

        Returns:
            Dictionary mapping task IDs to TaskResult objects.

        Side Effects:
            - Modifies task priorities (via optimize_execution_order)
            - Executes all task callables
        """
        optimized_tasks = self.optimize_execution_order(tasks)
        return await self.executor.execute_tasks(optimized_tasks)
