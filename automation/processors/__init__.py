"""Task and workflow processors for the automation engine.

This package provides processors that handle specific aspects of workflow
execution, including dependency tracking and task ordering.

Key Components:
    - DependencyTracker: Track task dependencies and detect cycles
    - TaskScheduler: Intelligent task ordering based on dependencies
    - ParallelProcessor: Handle parallel task execution safely

Features:
    - Dependency graph analysis
    - Cycle detection
    - Topological sorting for task execution order
    - Parallel execution with dependency constraints

Example:
    >>> from automation.processors import DependencyTracker
    >>> tracker = DependencyTracker()
    >>> tracker.add_task("task1", dependencies=[])
    >>> tracker.add_task("task2", dependencies=["task1"])
    >>> order = tracker.get_execution_order()
"""
