"""
Tests for parallel executor and task scheduler.
"""

import pytest
import asyncio
from automation.engine.parallel_executor import (
    ParallelExecutor,
    ExecutionTask,
    TaskScheduler,
    TaskPriority,
)


async def simple_task(value: int) -> int:
    """Simple async task for testing."""
    await asyncio.sleep(0.01)
    return value * 2


async def failing_task() -> None:
    """Task that always fails."""
    await asyncio.sleep(0.01)
    raise ValueError("Task failed")


@pytest.mark.asyncio
async def test_execute_single_task():
    """Test executing a single task."""
    executor = ParallelExecutor(max_workers=1)

    task = ExecutionTask(
        id="task-1",
        func=simple_task,
        args=(5,),
    )

    results = await executor.execute_tasks([task])

    assert len(results) == 1
    assert results["task-1"].success is True
    assert results["task-1"].result == 10


@pytest.mark.asyncio
async def test_execute_parallel_tasks():
    """Test executing multiple tasks in parallel."""
    executor = ParallelExecutor(max_workers=3)

    tasks = [
        ExecutionTask(id=f"task-{i}", func=simple_task, args=(i,))
        for i in range(5)
    ]

    results = await executor.execute_tasks(tasks)

    assert len(results) == 5
    for i in range(5):
        assert results[f"task-{i}"].success is True
        assert results[f"task-{i}"].result == i * 2


@pytest.mark.asyncio
async def test_task_dependencies():
    """Test task execution with dependencies."""
    executor = ParallelExecutor(max_workers=2)

    tasks = [
        ExecutionTask(id="task-1", func=simple_task, args=(1,)),
        ExecutionTask(
            id="task-2",
            func=simple_task,
            args=(2,),
            dependencies={"task-1"},
        ),
        ExecutionTask(
            id="task-3",
            func=simple_task,
            args=(3,),
            dependencies={"task-1", "task-2"},
        ),
    ]

    results = await executor.execute_tasks(tasks)

    assert len(results) == 3
    assert all(result.success for result in results.values())


@pytest.mark.asyncio
async def test_task_priority():
    """Test task priority ordering."""
    executor = ParallelExecutor(max_workers=1)

    tasks = [
        ExecutionTask(id="low", func=simple_task, args=(1,), priority=TaskPriority.LOW),
        ExecutionTask(id="high", func=simple_task, args=(2,), priority=TaskPriority.HIGH),
        ExecutionTask(id="normal", func=simple_task, args=(3,), priority=TaskPriority.NORMAL),
    ]

    results = await executor.execute_tasks(tasks)

    assert len(results) == 3
    assert all(result.success for result in results.values())


@pytest.mark.asyncio
async def test_task_failure():
    """Test handling of task failure."""
    executor = ParallelExecutor(max_workers=2)

    tasks = [
        ExecutionTask(id="success", func=simple_task, args=(1,)),
        ExecutionTask(id="failure", func=failing_task),
    ]

    results = await executor.execute_tasks(tasks)

    assert len(results) == 2
    assert results["success"].success is True
    assert results["failure"].success is False
    assert results["failure"].error is not None


@pytest.mark.asyncio
async def test_dependency_failure_blocks_dependents():
    """Test that dependent tasks are blocked when dependency fails."""
    executor = ParallelExecutor(max_workers=2)

    tasks = [
        ExecutionTask(id="failing", func=failing_task),
        ExecutionTask(
            id="dependent",
            func=simple_task,
            args=(1,),
            dependencies={"failing"},
        ),
    ]

    results = await executor.execute_tasks(tasks)

    assert len(results) == 2
    assert results["failing"].success is False
    assert results["dependent"].success is False  # Blocked by dependency


@pytest.mark.asyncio
async def test_task_timeout():
    """Test task timeout handling."""

    async def slow_task() -> None:
        await asyncio.sleep(10)

    executor = ParallelExecutor(max_workers=1)

    task = ExecutionTask(
        id="slow",
        func=slow_task,
        timeout=0.1,  # Very short timeout
    )

    results = await executor.execute_tasks([task])

    assert results["slow"].success is False
    assert isinstance(results["slow"].error, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_task_scheduler_optimization():
    """Test task scheduler optimization."""
    executor = ParallelExecutor(max_workers=3)
    scheduler = TaskScheduler(executor)

    tasks = [
        ExecutionTask(id="task-1", func=simple_task, args=(1,)),
        ExecutionTask(id="task-2", func=simple_task, args=(2,), dependencies={"task-1"}),
        ExecutionTask(id="task-3", func=simple_task, args=(3,), dependencies={"task-2"}),
    ]

    optimized = scheduler.optimize_execution_order(tasks)

    # Critical path tasks should have higher priority
    assert any(task.priority > TaskPriority.NORMAL for task in optimized)


@pytest.mark.asyncio
async def test_circular_dependency_detection():
    """Test detection of circular dependencies."""
    executor = ParallelExecutor(max_workers=2)

    tasks = [
        ExecutionTask(id="task-1", func=simple_task, args=(1,), dependencies={"task-2"}),
        ExecutionTask(id="task-2", func=simple_task, args=(2,), dependencies={"task-1"}),
    ]

    with pytest.raises(RuntimeError, match="deadlock"):
        await executor.execute_tasks(tasks)
