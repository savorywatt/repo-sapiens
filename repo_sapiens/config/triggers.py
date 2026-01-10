"""
Universal trigger configuration for native CI/CD workflows.

This module defines provider-agnostic trigger configurations that can be
translated to Gitea Actions, GitHub Actions, or GitLab CI syntax.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """Supported trigger types across all providers."""

    LABEL_ADDED = "label_added"  # Issue/PR labeled
    LABEL_REMOVED = "label_removed"  # Issue/PR unlabeled
    ISSUE_OPENED = "issue_opened"  # New issue created
    ISSUE_CLOSED = "issue_closed"  # Issue closed
    PR_OPENED = "pr_opened"  # New PR created
    PR_MERGED = "pr_merged"  # PR merged
    PR_CLOSED = "pr_closed"  # PR closed without merge
    PUSH = "push"  # Push to branch
    SCHEDULE = "schedule"  # Cron schedule
    MANUAL = "manual"  # Manual dispatch
    COMMENT = "comment"  # Issue/PR comment


class LabelTriggerConfig(BaseModel):
    """Configuration for label-based triggers."""

    label_pattern: str = Field(
        ..., description="Label name or glob pattern (e.g., 'sapiens/*', 'needs-*')"
    )
    handler: str = Field(..., description="Handler name to invoke (maps to workflow stage)")
    ai_enabled: bool = Field(default=True, description="Whether this handler requires AI agent")
    remove_on_complete: bool = Field(
        default=True, description="Remove trigger label after successful processing"
    )
    success_label: str | None = Field(
        default=None, description="Label to add on successful completion"
    )
    failure_label: str | None = Field(
        default="needs-attention", description="Label to add on failure"
    )


class ScheduleTriggerConfig(BaseModel):
    """Configuration for scheduled triggers."""

    cron: str = Field(..., description="Cron expression (e.g., '0 8 * * 1-5' for weekdays at 8am)")
    handler: str = Field(..., description="Handler name to invoke")
    task_prompt: str | None = Field(
        default=None, description="Task prompt for AI agent (if ai_enabled)"
    )
    ai_enabled: bool = Field(default=True, description="Whether this handler requires AI agent")


class AutomationModeConfig(BaseModel):
    """Configuration for automation mode selection."""

    mode: Literal["native", "daemon", "hybrid"] = Field(
        default="hybrid",
        description="Automation mode: native (CI/CD only), daemon (polling), hybrid (both)",
    )
    native_enabled: bool = Field(default=True, description="Enable native CI/CD triggers")
    daemon_enabled: bool = Field(default=True, description="Enable polling daemon")
    daemon_fallback_only: bool = Field(
        default=True, description="Only use daemon for tasks native can't handle"
    )
    label_prefix: str = Field(default="sapiens/", description="Prefix for sapiens-managed labels")


class AutomationConfig(BaseModel):
    """Complete automation configuration section.

    This is added to AutomationSettings as the 'automation' field.
    """

    mode: AutomationModeConfig = Field(
        default_factory=AutomationModeConfig, description="Automation mode configuration"
    )
    label_triggers: dict[str, LabelTriggerConfig] = Field(
        default_factory=dict, description="Label-to-handler mappings"
    )
    schedule_triggers: list[ScheduleTriggerConfig] = Field(
        default_factory=list, description="Scheduled automation tasks"
    )


# Provider-specific event mapping
PROVIDER_EVENT_MAP: dict[str, dict[TriggerType, str]] = {
    "gitea": {
        TriggerType.LABEL_ADDED: "issues.labeled",
        TriggerType.LABEL_REMOVED: "issues.unlabeled",
        TriggerType.ISSUE_OPENED: "issues.opened",
        TriggerType.ISSUE_CLOSED: "issues.closed",
        TriggerType.PR_OPENED: "pull_request.opened",
        TriggerType.PR_MERGED: "pull_request.closed",  # Check merged flag
        TriggerType.PR_CLOSED: "pull_request.closed",
        TriggerType.PUSH: "push",
        TriggerType.SCHEDULE: "schedule",
        TriggerType.MANUAL: "workflow_dispatch",
        TriggerType.COMMENT: "issue_comment.created",
    },
    "github": {
        TriggerType.LABEL_ADDED: "issues.labeled",
        TriggerType.LABEL_REMOVED: "issues.unlabeled",
        TriggerType.ISSUE_OPENED: "issues.opened",
        TriggerType.ISSUE_CLOSED: "issues.closed",
        TriggerType.PR_OPENED: "pull_request.opened",
        TriggerType.PR_MERGED: "pull_request.closed",
        TriggerType.PR_CLOSED: "pull_request.closed",
        TriggerType.PUSH: "push",
        TriggerType.SCHEDULE: "schedule",
        TriggerType.MANUAL: "workflow_dispatch",
        TriggerType.COMMENT: "issue_comment.created",
    },
    "gitlab": {
        TriggerType.LABEL_ADDED: "Issue Hook",  # GitLab uses webhooks differently
        TriggerType.ISSUE_OPENED: "Issue Hook",
        TriggerType.PR_OPENED: "Merge Request Hook",
        TriggerType.PR_MERGED: "Merge Request Hook",
        TriggerType.PUSH: "Push Hook",
        TriggerType.SCHEDULE: "Pipeline schedules",
        TriggerType.MANUAL: "pipeline triggers",
    },
}
