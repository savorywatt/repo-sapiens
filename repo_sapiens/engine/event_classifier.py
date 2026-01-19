"""
Event classification for native CI/CD triggers.

Classifies incoming webhook events and determines the appropriate handler.
"""

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from typing import Any

import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import LabelTriggerConfig, TriggerType

log = structlog.get_logger(__name__)


class EventSource(str, Enum):
    """Source of the event."""

    GITEA = "gitea"
    GITHUB = "github"
    GITLAB = "gitlab"


@dataclass
class ClassifiedEvent:
    """Result of event classification."""

    trigger_type: TriggerType
    source: EventSource
    handler: str | None
    config: LabelTriggerConfig | None
    issue_number: int | None
    pr_number: int | None
    label: str | None
    raw_event: dict[str, Any]
    should_process: bool = True
    skip_reason: str | None = None


class EventClassifier:
    """Classifies incoming CI/CD events and routes to handlers.

    Supports events from Gitea Actions, GitHub Actions, and GitLab CI.
    """

    def __init__(self, settings: AutomationSettings):
        """Initialize classifier with settings.

        Args:
            settings: Automation settings containing trigger configuration
        """
        self.settings = settings
        self.automation = settings.automation
        self._label_cache: dict[str, LabelTriggerConfig | None] = {}

    def classify(
        self,
        event_type: str,
        event_data: dict[str, Any],
        source: EventSource,
    ) -> ClassifiedEvent:
        """Classify an incoming event.

        Args:
            event_type: Event type string (e.g., "issues.labeled")
            event_data: Raw event payload
            source: Event source (gitea, github, gitlab)

        Returns:
            ClassifiedEvent with routing information
        """
        log.info(
            "classifying_event",
            event_type=event_type,
            source=source.value,
        )

        # Determine trigger type
        trigger_type = self._determine_trigger_type(event_type, event_data, source)

        if trigger_type is None:
            return ClassifiedEvent(
                trigger_type=TriggerType.MANUAL,  # Default
                source=source,
                handler=None,
                config=None,
                issue_number=self._extract_issue_number(event_data, source),
                pr_number=self._extract_pr_number(event_data, source),
                label=None,
                raw_event=event_data,
                should_process=False,
                skip_reason=f"Unknown event type: {event_type}",
            )

        # Extract label if this is a label event
        label = None
        if trigger_type in (TriggerType.LABEL_ADDED, TriggerType.LABEL_REMOVED):
            label = self._extract_label(event_data, source)

        # Find matching handler
        handler, config = self._find_handler(trigger_type, label)

        # Check if we should process this event
        should_process = True
        skip_reason = None

        if not self.automation.mode.native_enabled:
            should_process = False
            skip_reason = "Native triggers disabled in configuration"
        elif handler is None:
            should_process = False
            skip_reason = f"No handler configured for label: {label}"

        return ClassifiedEvent(
            trigger_type=trigger_type,
            source=source,
            handler=handler,
            config=config,
            issue_number=self._extract_issue_number(event_data, source),
            pr_number=self._extract_pr_number(event_data, source),
            label=label,
            raw_event=event_data,
            should_process=should_process,
            skip_reason=skip_reason,
        )

    def _determine_trigger_type(
        self,
        event_type: str,
        event_data: dict[str, Any],
        source: EventSource,
    ) -> TriggerType | None:
        """Determine the trigger type from event string."""
        # Normalize event type
        event_lower = event_type.lower()

        # Label events
        if "labeled" in event_lower and "unlabeled" not in event_lower:
            return TriggerType.LABEL_ADDED
        if "unlabeled" in event_lower:
            return TriggerType.LABEL_REMOVED

        # Issue events
        if "issue" in event_lower:
            if "opened" in event_lower:
                return TriggerType.ISSUE_OPENED
            if "closed" in event_lower:
                return TriggerType.ISSUE_CLOSED

        # PR events
        if "pull_request" in event_lower or "merge_request" in event_lower:
            if "opened" in event_lower:
                return TriggerType.PR_OPENED
            if "closed" in event_lower:
                # Check if merged
                merged = event_data.get("pull_request", {}).get("merged", False)
                if merged or event_data.get("merged", False):
                    return TriggerType.PR_MERGED
                return TriggerType.PR_CLOSED

        # Other events
        if event_lower == "push":
            return TriggerType.PUSH
        if event_lower in ("schedule", "scheduled"):
            return TriggerType.SCHEDULE
        if "workflow_dispatch" in event_lower or "manual" in event_lower:
            return TriggerType.MANUAL
        if "comment" in event_lower:
            return TriggerType.COMMENT

        return None

    def _extract_label(
        self,
        event_data: dict[str, Any],
        source: EventSource,
    ) -> str | None:
        """Extract the label that triggered the event."""
        if source == EventSource.GITLAB:
            # GitLab structure differs
            changes = event_data.get("changes", {})
            labels = changes.get("labels", {})
            current = labels.get("current", [])
            previous = labels.get("previous", [])
            # Find added label
            for label in current:
                if label not in previous:
                    return label.get("title") if isinstance(label, dict) else label
            return None

        # Gitea and GitHub use similar structure
        label_data = event_data.get("label", {})
        return label_data.get("name")

    def _extract_issue_number(
        self,
        event_data: dict[str, Any],
        source: EventSource,
    ) -> int | None:
        """Extract issue number from event."""
        # Try various paths
        if "issue" in event_data:
            return event_data["issue"].get("number")
        if "object_attributes" in event_data:  # GitLab
            return event_data["object_attributes"].get("iid")
        return None

    def _extract_pr_number(
        self,
        event_data: dict[str, Any],
        source: EventSource,
    ) -> int | None:
        """Extract PR number from event."""
        if "pull_request" in event_data:
            return event_data["pull_request"].get("number")
        if "merge_request" in event_data:  # GitLab
            return event_data["merge_request"].get("iid")
        if "object_attributes" in event_data:  # GitLab
            return event_data["object_attributes"].get("iid")
        return None

    def _find_handler(
        self,
        trigger_type: TriggerType,
        label: str | None,
    ) -> tuple[str | None, LabelTriggerConfig | None]:
        """Find handler for the given trigger and label."""
        if trigger_type not in (TriggerType.LABEL_ADDED, TriggerType.LABEL_REMOVED):
            # Non-label triggers not yet implemented
            return None, None

        if not label:
            return None, None

        # Check cache
        if label in self._label_cache:
            config = self._label_cache[label]
            return (config.handler, config) if config else (None, None)

        # Search for matching pattern
        for pattern, config in self.automation.label_triggers.items():
            if fnmatch(label, pattern) or label == pattern:
                self._label_cache[label] = config
                return config.handler, config

        self._label_cache[label] = None
        return None, None
