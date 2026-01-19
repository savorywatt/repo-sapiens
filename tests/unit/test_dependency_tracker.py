"""Tests for dependency tracker."""

import pytest

from repo_sapiens.models.domain import Task
from repo_sapiens.processors.dependency_tracker import DependencyTracker


def _make_task(id: str, title: str, dependencies: list[str] | None = None) -> Task:
    """Helper to create Task with required fields."""
    return Task(
        id=id,
        prompt_issue_id=1,
        title=title,
        description=f"Description for {title}",
        dependencies=dependencies or [],
    )


def test_dependency_tracker_initialization():
    """Test dependency tracker initialization."""
    tracker = DependencyTracker()
    assert len(tracker.tasks) == 0
    assert len(tracker.status) == 0


def test_add_task():
    """Test adding tasks to tracker."""
    tracker = DependencyTracker()
    task = _make_task(id="task-1", title="Test Task")

    tracker.add_task(task)

    assert "task-1" in tracker.tasks
    assert tracker.status["task-1"] == "pending"


def test_is_ready_no_dependencies():
    """Test task with no dependencies is ready."""
    tracker = DependencyTracker()
    task = _make_task(id="task-1", title="Test")

    tracker.add_task(task)

    assert tracker.is_ready("task-1") is True


def test_is_ready_with_dependencies():
    """Test task with dependencies."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1")
    task2 = _make_task(id="task-2", title="Task 2", dependencies=["task-1"])

    tracker.add_task(task1)
    tracker.add_task(task2)

    # task-2 not ready until task-1 complete
    assert tracker.is_ready("task-2") is False

    # Complete task-1
    tracker.mark_complete("task-1")

    # Now task-2 is ready
    assert tracker.is_ready("task-2") is True


def test_get_ready_tasks():
    """Test getting ready tasks."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1")
    task2 = _make_task(id="task-2", title="Task 2", dependencies=["task-1"])
    task3 = _make_task(id="task-3", title="Task 3")

    tracker.add_task(task1)
    tracker.add_task(task2)
    tracker.add_task(task3)

    # Initially task-1 and task-3 are ready
    ready = tracker.get_ready_tasks()
    assert len(ready) == 2
    assert any(t.id == "task-1" for t in ready)
    assert any(t.id == "task-3" for t in ready)

    # Complete task-1
    tracker.mark_complete("task-1")

    # Now task-2 is also ready
    ready = tracker.get_ready_tasks()
    assert len(ready) == 2
    assert any(t.id == "task-2" for t in ready)


def test_validate_dependencies_circular():
    """Test circular dependency detection."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1", dependencies=["task-2"])
    task2 = _make_task(id="task-2", title="Task 2", dependencies=["task-1"])

    tracker.add_task(task1)
    tracker.add_task(task2)

    with pytest.raises(ValueError, match="Circular dependency"):
        tracker.validate_dependencies()


def test_validate_dependencies_invalid_reference():
    """Test invalid dependency reference."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1", dependencies=["task-999"])

    tracker.add_task(task1)

    with pytest.raises(ValueError, match="Invalid dependency"):
        tracker.validate_dependencies()


def test_get_execution_order():
    """Test getting execution order."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1")
    task2 = _make_task(id="task-2", title="Task 2", dependencies=["task-1"])
    task3 = _make_task(id="task-3", title="Task 3", dependencies=["task-1"])
    task4 = _make_task(id="task-4", title="Task 4", dependencies=["task-2", "task-3"])

    tracker.add_task(task1)
    tracker.add_task(task2)
    tracker.add_task(task3)
    tracker.add_task(task4)

    batches = tracker.get_execution_order()

    # Expected:
    # Batch 0: [task-1]
    # Batch 1: [task-2, task-3] (can run in parallel)
    # Batch 2: [task-4]

    assert len(batches) == 3
    assert batches[0] == ["task-1"]
    assert set(batches[1]) == {"task-2", "task-3"}
    assert batches[2] == ["task-4"]


def test_get_blocked_tasks():
    """Test getting blocked tasks."""
    tracker = DependencyTracker()

    task1 = _make_task(id="task-1", title="Task 1")
    task2 = _make_task(id="task-2", title="Task 2", dependencies=["task-1"])

    tracker.add_task(task1)
    tracker.add_task(task2)

    # Mark task-1 as failed
    tracker.mark_failed("task-1")

    blocked = tracker.get_blocked_tasks()
    assert len(blocked) == 1
    assert blocked[0].id == "task-2"
