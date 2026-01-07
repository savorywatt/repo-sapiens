"""Type definitions for workflow state management.

This module provides TypedDict definitions for state structures used throughout
the workflow engine, enabling static type checking for state dictionary access.
"""

from typing import Any, NotRequired, TypedDict


class StageState(TypedDict):
    """State for a single workflow stage.

    Attributes:
        status: Stage execution status (pending, in_progress, completed, failed)
        started_at: ISO timestamp when stage started
        completed_at: ISO timestamp when stage completed
        error: Error message if stage failed
        data: Stage-specific data (e.g., generated plan, review comments)
    """

    status: str  # "pending" | "in_progress" | "completed" | "failed"
    started_at: NotRequired[str]
    completed_at: NotRequired[str]
    error: NotRequired[str]
    data: NotRequired[dict[str, Any]]


class TaskState(TypedDict):
    """State for a single task within a plan.

    Attributes:
        status: Task execution status (pending, in_progress, completed, failed)
        issue_number: Associated issue number
        branch: Git branch name for task
        pr_number: Associated pull request number
        updated_at: ISO timestamp of last update
        error: Error message if task failed
        data: Task-specific data
        dependencies: List of task IDs this task depends on
    """

    status: str  # "pending" | "in_progress" | "completed" | "failed"
    issue_number: NotRequired[int]
    branch: NotRequired[str]
    pr_number: NotRequired[int]
    updated_at: str
    error: NotRequired[str]
    data: NotRequired[dict[str, Any]]
    dependencies: NotRequired[list[str]]


# StagesDict is a plain dict to allow dynamic key access in stage iteration.
# This sacrifices some type safety for practical usability when iterating
# over unknown/dynamic stage names.
StagesDict = dict[str, StageState]


# Known stage names (for documentation and validation purposes)
KNOWN_STAGE_NAMES = frozenset({
    # New granular workflow stages
    "proposal",
    "approval",
    "task_execution",
    "pr_review",
    "pr_fix",
    "fix_execution",
    "qa",
    # Legacy stages (kept for compatibility)
    "planning",
    "plan_review",
    "prompts",
    "implementation",
    "code_review",
    "merge",
})


class WorkflowState(TypedDict):
    """Complete state for a workflow/plan.

    This represents the full state persisted to disk for each plan_id.

    Attributes:
        plan_id: Unique identifier for the workflow/plan
        status: Overall workflow status (pending, in_progress, completed, failed)
        created_at: ISO timestamp when workflow was created
        updated_at: ISO timestamp of last update
        original_issue: Issue number that triggered this workflow
        stages: Dictionary of stage states
        tasks: Dictionary of task states by task_id
        metadata: Additional workflow metadata (flexible structure)
    """

    plan_id: str
    status: str  # "pending" | "in_progress" | "completed" | "failed"
    created_at: str
    updated_at: str
    original_issue: NotRequired[int]
    stages: StagesDict
    tasks: NotRequired[dict[str, TaskState]]
    metadata: NotRequired[dict[str, Any]]


# Type aliases for common patterns
TasksDict = dict[str, TaskState]


__all__ = [
    "StageState",
    "TaskState",
    "StagesDict",
    "WorkflowState",
    "TasksDict",
]
