"""
Base class for workflow stages.

This module provides the WorkflowStage abstract base class that defines the
interface and common functionality for all workflow stages.
"""

from abc import ABC, abstractmethod

import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.models.domain import Issue
from repo_sapiens.providers.base import AgentProvider, GitProvider

log = structlog.get_logger(__name__)


class WorkflowStage(ABC):
    """Base class for workflow stages.

    Each stage represents a major phase in the automation workflow, such as
    planning, implementation, or code review. Stages are responsible for
    executing their specific logic and handling errors appropriately.
    """

    def __init__(
        self,
        git: GitProvider,
        agent: AgentProvider,
        state: StateManager,
        settings: AutomationSettings,
    ) -> None:
        """Initialize workflow stage.

        Args:
            git: Git provider for repository operations
            agent: AI agent provider for code generation and review
            state: State manager for persistence
            settings: Automation system settings
        """
        self.git = git
        self.agent = agent
        self.state = state
        self.settings = settings

    @abstractmethod
    async def execute(self, issue: Issue) -> None:
        """Execute this stage of the workflow.

        Args:
            issue: Issue being processed

        Raises:
            Exception: If stage execution fails
        """
        pass

    async def _handle_stage_error(self, issue: Issue, error: Exception) -> None:
        """Common error handling for all stages.

        Adds a comment to the issue describing the error and adds the
        needs-attention label.

        Args:
            issue: Issue that encountered an error
            error: Exception that occurred
        """
        error_msg = f"Stage execution failed: {str(error)}"
        log.error("stage_error", issue=issue.number, error=error_msg, exc_info=True)

        # Add comment to issue
        await self.git.add_comment(issue.number, f"Error: {error_msg}")

        # Add needs-attention label
        labels = list(set(issue.labels + [self.settings.tags.needs_attention]))
        await self.git.update_issue(issue.number, labels=labels)
