"""Execution context for workflow stages.

This module provides the ExecutionContext dataclass that carries state
through the workflow pipeline, enabling richer inter-stage communication.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from repo_sapiens.models.domain import Issue


@dataclass
class ExecutionContext:
    """Context passed through workflow stages.

    Attributes:
        issue: The issue being processed (required)
        plan_id: Optional plan identifier for multi-task workflows
        workspace_path: Path to the working directory for file operations
        branch_name: Current git branch name
        stage_outputs: Dictionary of outputs from completed stages
        dry_run: If True, stages should simulate but not execute changes
    """

    # Required fields (no default)
    issue: Issue

    # Optional identifiers
    plan_id: str | None = None

    # Execution environment
    workspace_path: Path | None = None
    branch_name: str | None = None

    # Stage communication
    stage_outputs: dict[str, Any] = field(default_factory=dict)

    # Flags
    dry_run: bool = False

    def get_stage_output(self, stage: str) -> Any | None:
        """Get output from a previous stage."""
        return self.stage_outputs.get(stage)

    def set_stage_output(self, stage: str, output: Any) -> None:
        """Record output from a completed stage."""
        self.stage_outputs[stage] = output

    def with_updates(self, **kwargs: Any) -> "ExecutionContext":
        """Create a new context with updated fields."""
        return replace(self, **kwargs)

    def has_stage_completed(self, stage: str) -> bool:
        """Check if a stage has recorded output."""
        return stage in self.stage_outputs
