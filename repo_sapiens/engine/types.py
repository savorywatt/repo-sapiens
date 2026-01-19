"""Type definitions for workflow state management.

This module provides TypedDict definitions for state structures used throughout
the workflow engine, enabling static type checking for state dictionary access.
These types represent the schema for workflow state persisted to YAML files
in the .sapiens/state/ directory.

Example:
    Creating and updating workflow state::

        state: WorkflowState = {
            "plan_id": "plan-issue-42",
            "status": "in_progress",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "original_issue": 42,
            "stages": {
                "proposal": {"status": "completed"},
                "approval": {"status": "in_progress"}
            },
            "tasks": {}
        }

    Updating a stage::

        state["stages"]["approval"]["status"] = "completed"
        state["stages"]["approval"]["completed_at"] = datetime.now().isoformat()
"""

from typing import Any, NotRequired, TypedDict


class StageState(TypedDict):
    """State for a single workflow stage.

    Tracks the execution status and timing of one stage in the workflow
    pipeline. Stages progress linearly through the workflow.

    Example:
        A completed stage::

            stage: StageState = {
                "status": "completed",
                "started_at": "2024-01-15T10:30:00",
                "completed_at": "2024-01-15T10:32:15",
                "data": {"plan_path": ".sapiens/plans/plan-42.yaml"}
            }

        A failed stage::

            stage: StageState = {
                "status": "failed",
                "started_at": "2024-01-15T10:30:00",
                "error": "API rate limit exceeded"
            }
    """

    status: str
    """Stage execution status.

    One of:
    - "pending": Stage has not started yet
    - "in_progress": Stage is currently executing
    - "completed": Stage finished successfully
    - "failed": Stage encountered an error

    Note: This is a string rather than an enum for JSON/YAML serialization.
    """

    started_at: NotRequired[str]
    """ISO 8601 timestamp when stage execution began.

    Set when status changes to "in_progress".
    Example: "2024-01-15T10:30:00.123456"
    """

    completed_at: NotRequired[str]
    """ISO 8601 timestamp when stage execution finished.

    Set when status changes to "completed" or "failed".
    Used to calculate stage duration.
    """

    error: NotRequired[str]
    """Error message if stage failed.

    Contains the exception message or a descriptive error.
    Only present when status is "failed".
    """

    data: NotRequired[dict[str, Any]]
    """Stage-specific output data.

    Contents vary by stage type:
    - proposal: {"plan_path": str, "plan_id": str}
    - approval: {"approved_by": str, "approved_at": str}
    - task_execution: {"branch": str, "commits": list[str]}
    - pr_review: {"approved": bool, "comments": list[str]}
    """


class TaskState(TypedDict):
    """State for a single task within a plan.

    Tracks the execution status of an individual task, including its
    associated issue, branch, and pull request.

    Example:
        A task in progress::

            task: TaskState = {
                "status": "in_progress",
                "issue_number": 43,
                "branch": "sapiens/task-1-add-login",
                "updated_at": "2024-01-15T10:35:00",
                "dependencies": ["task-0"]
            }

        A completed task::

            task: TaskState = {
                "status": "completed",
                "issue_number": 43,
                "branch": "sapiens/task-1-add-login",
                "pr_number": 44,
                "updated_at": "2024-01-15T11:00:00"
            }
    """

    status: str
    """Task execution status.

    One of:
    - "pending": Task is waiting for dependencies or its turn
    - "in_progress": Agent is actively working on the task
    - "completed": Task finished and PR merged (or ready)
    - "failed": Task failed and requires intervention

    Matches TaskStatus enum values from domain.py.
    """

    issue_number: NotRequired[int]
    """Issue number created for this task.

    When tasks are executed, the system may create child issues
    to track individual task progress.
    """

    branch: NotRequired[str]
    """Git branch name where task changes are committed.

    Typically formatted as "sapiens/task-{id}-{slug}".
    Example: "sapiens/task-1-add-user-model"
    """

    pr_number: NotRequired[int]
    """Pull request number created for this task.

    Set after the task creates a PR for its changes.
    Used to track review status and merge the changes.
    """

    updated_at: str
    """ISO 8601 timestamp of the last state update.

    Updated whenever any field in the task state changes.
    Used for debugging and audit trails.
    """

    error: NotRequired[str]
    """Error message if task failed.

    Contains details about what went wrong during execution.
    Only present when status is "failed".
    """

    data: NotRequired[dict[str, Any]]
    """Task-specific metadata and results.

    May include:
    - "commits": List of commit SHAs
    - "files_changed": List of modified file paths
    - "execution_time": Duration in seconds
    - "agent_output": Agent's final response
    """

    dependencies: NotRequired[list[str]]
    """List of task IDs this task depends on.

    Task cannot start until all dependencies have status "completed".
    Example: ["task-0", "task-1"]
    """


# StagesDict is a plain dict to allow dynamic key access in stage iteration.
# This sacrifices some type safety for practical usability when iterating
# over unknown/dynamic stage names.
#
# Type alias for the stages dictionary. Maps stage names (strings) to their
# state objects. Using a plain dict rather than TypedDict allows iteration
# over dynamically-named stages.
#
# Example - Iterating over stages:
#     stages: StagesDict = workflow_state["stages"]
#     for name, stage in stages.items():
#         if stage["status"] == "failed":
#             print(f"Stage {name} failed: {stage.get('error')}")
StagesDict = dict[str, StageState]


# Known stage names (for documentation and validation purposes)
KNOWN_STAGE_NAMES = frozenset(
    {
        # New granular workflow stages
        "proposal",  # AI generates implementation plan from issue
        "approval",  # Human reviews and approves the plan
        "task_execution",  # Agent executes individual tasks
        "pr_review",  # AI or human reviews the pull request
        "pr_fix",  # Address review feedback
        "fix_execution",  # Execute fixes from review
        "qa",  # Quality assurance and final checks
        # Legacy stages (kept for backward compatibility)
        "planning",  # Deprecated: use "proposal"
        "plan_review",  # Deprecated: use "approval"
        "prompts",  # Deprecated: generating task prompts
        "implementation",  # Deprecated: use "task_execution"
        "code_review",  # Deprecated: use "pr_review"
        "merge",  # Deprecated: handled automatically
    }
)
# Set of recognized stage names. Used for validation and documentation.
# The workflow engine will accept any stage name, but these are the standard
# stages used by built-in workflows.
#
# Current workflow stages:
# - proposal: AI analyzes issue and generates implementation plan
# - approval: Human reviews plan, adds/removes tasks, approves
# - task_execution: Agent implements each task on feature branches
# - pr_review: Automated or human review of pull requests
# - pr_fix: Process review feedback and determine fixes
# - fix_execution: Apply fixes from review feedback
# - qa: Final quality checks before merge
#
# Legacy stages are maintained for backward compatibility with existing
# state files but should not be used in new workflows.


class WorkflowState(TypedDict):
    """Complete state for a workflow/plan.

    This represents the full state persisted to disk for each plan_id.
    Stored as YAML in .sapiens/state/{plan_id}.yaml.

    Example:
        Complete workflow state::

            state: WorkflowState = {
                "plan_id": "plan-issue-42",
                "status": "in_progress",
                "created_at": "2024-01-15T10:00:00",
                "updated_at": "2024-01-15T10:45:00",
                "original_issue": 42,
                "stages": {
                    "proposal": {"status": "completed", ...},
                    "approval": {"status": "completed", ...},
                    "task_execution": {"status": "in_progress", ...}
                },
                "tasks": {
                    "task-1": {"status": "completed", ...},
                    "task-2": {"status": "in_progress", ...},
                    "task-3": {"status": "pending", ...}
                },
                "metadata": {
                    "repository": "org/repo",
                    "triggered_by": "label:sapiens:execute"
                }
            }
    """

    plan_id: str
    """Unique identifier for the workflow/plan.

    Typically formatted as "plan-issue-{number}" to link back to
    the originating issue. Used as the filename for state persistence.
    """

    status: str
    """Overall workflow status.

    One of:
    - "pending": Workflow created but not started
    - "in_progress": Workflow is actively executing
    - "completed": All stages and tasks finished successfully
    - "failed": Workflow stopped due to an error

    This is a rollup of stage statuses - workflow is "completed" only
    when all stages are "completed".
    """

    created_at: str
    """ISO 8601 timestamp when the workflow was created.

    Set once when the workflow is initialized and never changed.
    """

    updated_at: str
    """ISO 8601 timestamp of the last state modification.

    Updated whenever any part of the workflow state changes.
    Used for staleness detection and debugging.
    """

    original_issue: NotRequired[int]
    """Issue number that triggered this workflow.

    Links the workflow back to the feature request or bug report
    that initiated the automation.
    """

    stages: StagesDict
    """Dictionary of stage states keyed by stage name.

    Contains state for each stage in the workflow pipeline.
    Stages are processed in order defined by the workflow configuration.
    """

    tasks: NotRequired[dict[str, TaskState]]
    """Dictionary of task states keyed by task ID.

    Contains state for each task in the plan. Tasks may execute
    in parallel if their dependencies allow.
    """

    metadata: NotRequired[dict[str, Any]]
    """Additional workflow metadata.

    Flexible structure for storing context about the workflow:
    - "repository": Repository name
    - "triggered_by": What triggered the workflow
    - "config_version": Version of config used
    - "retry_count": Number of retry attempts
    """


# Type aliases for common patterns
#
# TasksDict: Type alias for the tasks dictionary. Maps task IDs (strings
# like "task-1") to their state objects.
#
# Example - Checking task dependencies:
#     tasks: TasksDict = workflow_state.get("tasks", {})
#     ready_tasks = [
#         task_id for task_id, task in tasks.items()
#         if task["status"] == "pending"
#         and all(
#             tasks.get(dep, {}).get("status") == "completed"
#             for dep in task.get("dependencies", [])
#         )
#     ]
TasksDict = dict[str, TaskState]


__all__ = [
    "StageState",
    "TaskState",
    "StagesDict",
    "WorkflowState",
    "TasksDict",
    "KNOWN_STAGE_NAMES",
]
