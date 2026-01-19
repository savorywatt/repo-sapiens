"""
Base class for workflow stages.

This module provides the WorkflowStage abstract base class that defines the
interface and common functionality for all workflow stages in the automation
pipeline.

Stage Lifecycle:
    Stages are instantiated once during orchestrator initialization and reused
    for all issues that match their execution criteria. The lifecycle is:

    1. Instantiation: Stage receives git, agent, state, and settings
    2. Execution: ``execute()`` is called with an Issue when triggered
    3. Completion: Stage updates labels, state, and adds comments
    4. Error handling: ``_handle_stage_error()`` for graceful degradation

Stage Responsibilities:
    Each stage implementation is responsible for:
    - Validating that the issue is appropriate for this stage
    - Performing the stage-specific work (planning, implementation, etc.)
    - Updating issue labels to trigger the next stage
    - Persisting relevant data to the state manager
    - Adding informative comments to the issue

Interaction with Orchestrator:
    The orchestrator calls stages based on issue labels. Each stage should:
    - Remove its trigger label on completion
    - Add the appropriate label for the next stage
    - Handle errors gracefully to avoid blocking the workflow

Creating New Stages:
    To create a new stage:
    1. Subclass WorkflowStage
    2. Implement the ``execute()`` method
    3. Register the stage in the orchestrator's stage registry
    4. Add the appropriate label routing in ``_determine_stage()``

Example:
    >>> class MyStage(WorkflowStage):
    ...     async def execute(self, issue: Issue) -> None:
    ...         # Perform stage logic
    ...         await self.git.add_comment(issue.number, "Stage complete")
    ...         # Update labels for next stage
    ...         labels = [l for l in issue.labels if l != "my-trigger"]
    ...         labels.append("next-stage")
    ...         await self.git.update_issue(issue.number, labels=labels)
"""

from abc import ABC, abstractmethod

import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.models.domain import Issue
from repo_sapiens.providers.base import AgentProvider, GitProvider

log = structlog.get_logger(__name__)


class WorkflowStage(ABC):
    """Abstract base class for all workflow stages.

    Each stage represents a major phase in the automation workflow, such as
    planning, implementation, or code review. Stages are responsible for
    executing their specific logic, handling errors appropriately, and
    transitioning issues to the next stage via label updates.

    Stages receive shared resources (git, agent, state, settings) during
    construction and use them to interact with the repository, AI system,
    and persistent state.

    Attributes:
        git: Git provider for repository operations (issues, PRs, branches).
        agent: AI agent provider for code generation, planning, and review.
        state: State manager for persisting workflow progress.
        settings: Configuration including tags, repository settings, etc.

    Subclass Contract:
        Implementations must:
        1. Override ``execute()`` to perform stage-specific work
        2. Handle validation (is this issue appropriate for this stage?)
        3. Update labels to prevent re-execution and trigger next stage
        4. Call ``_handle_stage_error()`` on failure (or let it propagate)
        5. Persist relevant data to state manager

    Example:
        >>> class ValidationStage(WorkflowStage):
        ...     async def execute(self, issue: Issue) -> None:
        ...         if not self._is_valid(issue):
        ...             return  # Skip silently
        ...         try:
        ...             result = await self._validate(issue)
        ...             await self._update_labels(issue, result)
        ...         except Exception as e:
        ...             await self._handle_stage_error(issue, e)
        ...             raise
    """

    def __init__(
        self,
        git: GitProvider,
        agent: AgentProvider,
        state: StateManager,
        settings: AutomationSettings,
    ) -> None:
        """Initialize the workflow stage with required dependencies.

        All stages receive the same set of dependencies, ensuring consistent
        access to system resources. These are stored as instance attributes
        for use in the ``execute()`` method.

        Args:
            git: Git provider for repository operations. Used for creating
                issues, branches, pull requests, and managing labels.
            agent: AI agent provider for intelligent operations. Used for
                plan generation, code review, and task execution.
            state: State manager for persistence. Used to track workflow
                progress and store stage-specific data.
            settings: Configuration object containing workflow settings,
                tag definitions, and repository configuration.

        Note:
            Stages are instantiated once and reused for multiple issues.
            Do not store issue-specific state as instance attributes.
        """
        self.git = git
        self.agent = agent
        self.state = state
        self.settings = settings

    @abstractmethod
    async def execute(self, issue: Issue) -> None:
        """Execute this stage of the workflow for the given issue.

        This is the main entry point called by the orchestrator when an
        issue is routed to this stage. Implementations should:

        1. Validate the issue is appropriate for this stage
        2. Perform the stage-specific work
        3. Update issue labels to trigger the next stage
        4. Persist any relevant data to the state manager
        5. Add comments to keep users informed

        Args:
            issue: The issue being processed. Contains number, title, body,
                labels, and other metadata.

        Raises:
            Exception: Implementations may raise any exception on failure.
                The orchestrator catches these and logs them, but the error
                should also be handled via ``_handle_stage_error()`` to
                notify users.

        Side Effects:
            Varies by implementation, but typically includes:
            - Modifying issue labels
            - Adding comments to the issue
            - Creating/updating branches
            - Creating pull requests
            - Updating state manager

        Note:
            Implementations should be idempotent where possible. The same
            issue may be processed multiple times if the workflow is
            re-triggered.
        """
        pass

    async def _handle_stage_error(self, issue: Issue, error: Exception) -> None:
        """Handle errors consistently across all stages.

        Provides a standard error handling pattern that:
        1. Logs the error with full context
        2. Adds an error comment to the issue
        3. Adds the ``needs-attention`` label for human review

        This method should be called from ``execute()`` implementations
        when an error occurs, before re-raising the exception.

        Args:
            issue: The issue where the error occurred. Used to add the
                error comment and update labels.
            error: The exception that was raised. Its message is included
                in the issue comment.

        Side Effects:
            - Logs error with exc_info for debugging
            - Adds error comment to the issue
            - Adds ``needs-attention`` label to the issue

        Example:
            >>> try:
            ...     await self._do_work(issue)
            ... except SomeError as e:
            ...     await self._handle_stage_error(issue, e)
            ...     raise  # Re-raise after handling
        """
        error_msg = f"Stage execution failed: {str(error)}"
        log.error("stage_error", issue=issue.number, error=error_msg, exc_info=True)

        # Add error comment to issue for visibility
        await self.git.add_comment(issue.number, f"Error: {error_msg}")

        # Add needs-attention label to flag for human review
        # Use set to avoid duplicate labels
        labels = list(set(issue.labels + [self.settings.tags.needs_attention]))
        await self.git.update_issue(issue.number, labels=labels)
