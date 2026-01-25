"""
Workflow orchestrator for managing automation pipeline.

This module provides the WorkflowOrchestrator class, which serves as the central
coordination point for the entire automation workflow. The orchestrator manages:

- Issue discovery and routing to appropriate stages
- Stage lifecycle and execution
- Parallel task execution with dependency management
- Error handling and recovery across the workflow

Architecture Overview:
    The orchestrator follows a hub-and-spoke pattern where it sits at the center
    and coordinates between multiple specialized stages. Each stage handles a
    specific phase of the workflow (planning, execution, review, merge).

Stage Lifecycle:
    1. Issue arrives with specific labels indicating required action
    2. Orchestrator determines appropriate stage via label matching
    3. Stage executes its logic, updating issue labels and state
    4. Control returns to orchestrator for next action

Typical Workflow Flow:
    needs-planning -> proposal -> approval -> task_execution -> pr_review -> merge

Example:
    >>> orchestrator = WorkflowOrchestrator(settings, git, agent, state)
    >>> await orchestrator.process_all_issues(tag="automation")
"""

import asyncio

import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.stages.approval import ApprovalStage
from repo_sapiens.engine.stages.code_review import CodeReviewStage
from repo_sapiens.engine.stages.execution import TaskExecutionStage
from repo_sapiens.engine.stages.fix_execution import FixExecutionStage
from repo_sapiens.engine.stages.implementation import ImplementationStage
from repo_sapiens.engine.stages.merge import MergeStage
from repo_sapiens.engine.stages.plan_review import PlanReviewStage
from repo_sapiens.engine.stages.planning import PlanningStage
from repo_sapiens.engine.stages.pr_fix import PRFixStage
from repo_sapiens.engine.stages.pr_review import PRReviewStage
from repo_sapiens.engine.stages.proposal import ProposalStage
from repo_sapiens.engine.stages.qa import QAStage
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.engine.types import StageState, WorkflowState
from repo_sapiens.models.domain import Issue, Task
from repo_sapiens.processors.dependency_tracker import DependencyTracker
from repo_sapiens.providers.base import AgentProvider, GitProvider

log = structlog.get_logger(__name__)


class WorkflowOrchestrator:
    """Orchestrate the complete automation workflow.

    The WorkflowOrchestrator is the central coordination point for the entire
    automation system. It manages issue discovery, stage routing, parallel task
    execution, and error handling across the workflow pipeline.

    The orchestrator maintains a registry of all available stages and routes
    issues to the appropriate stage based on their labels. It also handles
    parallel task execution with dependency management for complex plans.

    Attributes:
        settings: Configuration for the automation system.
        git: Git provider for repository operations (issues, PRs, branches).
        agent: AI agent provider for code generation and review.
        state: State manager for workflow persistence.
        stages: Registry mapping stage names to their implementations.

    Stage Registry:
        The orchestrator initializes both the new granular workflow stages
        and legacy stages for backward compatibility:

        New Workflow Stages:
            - proposal: Generate implementation proposals for issues
            - approval: Handle proposal approval workflow
            - task_execution: Execute individual tasks
            - pr_review: AI-assisted pull request review
            - pr_fix: Create fix proposals based on review feedback
            - fix_execution: Execute approved fixes
            - qa: Quality assurance (build and test verification)

        Legacy Stages (for compatibility):
            - planning: Generate development plans
            - plan_review: Review generated plans
            - implementation: Implement approved plans
            - code_review: AI code review
            - merge: Create and merge pull requests

    Example:
        >>> settings = AutomationSettings.load("config.yaml")
        >>> git = GiteaProvider(settings.git_provider)
        >>> agent = ClaudeProvider(settings.agent_provider)
        >>> state = StateManager(".sapiens/state")
        >>> orchestrator = WorkflowOrchestrator(settings, git, agent, state)
        >>> await orchestrator.process_all_issues()
    """

    def __init__(
        self,
        settings: AutomationSettings,
        git: GitProvider,
        agent: AgentProvider,
        state: StateManager,
    ) -> None:
        """Initialize the workflow orchestrator with required dependencies.

        Sets up the stage registry with all available workflow stages. Each stage
        receives the same set of dependencies (git, agent, state, settings) to
        ensure consistent access to system resources.

        Args:
            settings: Automation configuration including workflow settings,
                repository configuration, and tag definitions.
            git: Git provider instance for repository operations such as
                creating issues, branches, and pull requests.
            agent: AI agent provider for code generation, planning, and review
                operations.
            state: State manager for persisting workflow state across runs.

        Note:
            The stage registry is initialized eagerly, meaning all stages are
            instantiated during orchestrator construction. This ensures any
            configuration issues are caught early.
        """
        self.settings = settings
        self.git = git
        self.agent = agent
        self.state = state
        self.custom_system_prompt: str | None = None

        # Initialize stages
        self.stages = {
            # New granular workflow stages
            "proposal": ProposalStage(git, agent, state, settings),
            "approval": ApprovalStage(git, agent, state, settings),
            "task_execution": TaskExecutionStage(git, agent, state, settings),
            "pr_review": PRReviewStage(git, agent, state, settings),
            "pr_fix": PRFixStage(git, agent, state, settings),
            "fix_execution": FixExecutionStage(git, agent, state, settings),
            "qa": QAStage(git, agent, state, settings),
            # Legacy stages (kept for compatibility)
            "planning": PlanningStage(git, agent, state, settings),
            "plan_review": PlanReviewStage(git, agent, state, settings),
            "implementation": ImplementationStage(git, agent, state, settings),
            "code_review": CodeReviewStage(git, agent, state, settings),
            "merge": MergeStage(git, agent, state, settings),
        }

    async def process_all_issues(self, tag: str | None = None) -> None:
        """Process all open issues, optionally filtered by tag.

        Fetches all open issues from the git provider, optionally filtering
        by a specific label/tag. Issues are processed in ascending order by
        issue number to ensure deterministic behavior and respect for issue
        creation order.

        Each issue is processed independently with its own error handling,
        allowing the workflow to continue even if individual issues fail.

        Args:
            tag: Optional label to filter issues. When provided, only issues
                with this label will be processed. When None, all open issues
                are considered for processing.

        Raises:
            No exceptions are raised directly. Individual issue failures are
            logged and execution continues with remaining issues.

        Side Effects:
            - Issues may have labels added/removed based on stage execution
            - Comments may be added to issues
            - State files may be created/updated in the state directory
            - Branches may be created in the repository
            - Pull requests may be created

        Example:
            >>> # Process all issues with the 'automation' label
            >>> await orchestrator.process_all_issues(tag="automation")
            >>> # Process all open issues
            >>> await orchestrator.process_all_issues()
        """
        log.info("processing_all_issues", tag=tag)

        # Get open issues
        issues = await self.git.get_issues(
            labels=[tag] if tag else None,
            state="open",
        )

        log.info("found_issues", count=len(issues))

        # Sort issues by number in ascending order
        # (so tasks are processed 1, 2, 3... not 9, 8, 7...)
        issues.sort(key=lambda issue: issue.number)

        # Process each issue
        for issue in issues:
            try:
                await self.process_issue(issue)
            except Exception as e:
                log.error(
                    "issue_processing_failed",
                    issue=issue.number,
                    error=str(e),
                    exc_info=True,
                )

    async def process_issue(self, issue: Issue) -> None:
        """Process a single issue through the workflow pipeline.

        Examines the issue's labels to determine which workflow stage should
        handle it, then delegates execution to that stage. If no matching
        stage is found (i.e., the issue has no workflow-related labels),
        the issue is skipped.

        The stage determination uses a priority-based matching system where
        certain label combinations take precedence over others. See
        ``_determine_stage()`` for the full routing logic.

        Args:
            issue: Issue to process. Must have ``number``, ``labels``, and
                ``title`` attributes populated.

        Raises:
            Exception: Re-raises any exception from stage execution after
                logging. The caller (typically ``process_all_issues``)
                handles error recovery.

        Side Effects:
            - Stage-specific side effects (varies by stage type)
            - Error comment added to issue if stage execution fails
            - ``needs-attention`` label added on failure

        Example:
            >>> issue = await git.get_issue(42)
            >>> await orchestrator.process_issue(issue)
        """
        log.info("processing_issue", issue=issue.number, labels=issue.labels)

        # Determine stage from labels
        stage = self._determine_stage(issue)

        if not stage:
            log.debug("no_matching_stage", issue=issue.number)
            return

        log.info("executing_stage", issue=issue.number, stage=stage)

        try:
            await self.stages[stage].execute(issue)
        except Exception as e:
            log.error(
                "stage_execution_failed",
                issue=issue.number,
                stage=stage,
                error=str(e),
                exc_info=True,
            )
            raise

    async def process_plan(self, plan_id: str) -> None:
        """Process an entire plan end-to-end with parallel task execution.

        Loads the plan state from disk and executes all tasks within the plan.
        Tasks are executed in parallel where dependencies allow, respecting
        the ``max_concurrent_tasks`` setting.

        The plan must have completed its planning stage before tasks can be
        executed. If the planning stage is not complete, this method returns
        early without error.

        Workflow:
            1. Load plan state from state manager
            2. Verify planning stage is complete
            3. Build Task objects from stored task state
            4. Execute tasks in parallel via ``execute_parallel_tasks()``

        Args:
            plan_id: Unique identifier for the plan. This corresponds to
                the state file name (e.g., "plan-123" -> "plan-123.json").

        Raises:
            ValueError: If dependency validation fails during parallel execution.
            RuntimeError: If a deadlock is detected in task dependencies.

        Side Effects:
            - State file updated with task execution results
            - Implementation branches created
            - Pull requests created
            - Issue labels and comments updated

        Example:
            >>> await orchestrator.process_plan("plan-42")
        """
        log.info("processing_plan", plan_id=plan_id)

        # Load plan state (typed as WorkflowState)
        state: WorkflowState = await self.state.load_state(plan_id)

        # Get planning issue
        stages = state.get("stages", {})
        planning_stage: StageState = stages.get("planning", {"status": "pending"})
        if planning_stage.get("status") != "completed":
            log.warning("plan_not_ready", plan_id=plan_id)
            return

        # Get all tasks
        tasks_state = state.get("tasks", {})
        if not tasks_state:
            log.warning("no_tasks_found", plan_id=plan_id)
            return

        # Build task objects
        tasks = []
        for task_id, task_data in tasks_state.items():
            task = Task(
                id=task_id,
                prompt_issue_id=task_data.get("issue_number"),
                title=f"Task {task_id}",
                description="",
                dependencies=task_data.get("dependencies", []),
                plan_id=plan_id,
            )
            tasks.append(task)

        # Execute tasks in parallel respecting dependencies
        await self.execute_parallel_tasks(tasks, plan_id)

        log.info("plan_processing_completed", plan_id=plan_id)

    async def execute_parallel_tasks(self, tasks: list[Task], plan_id: str) -> None:
        """Execute tasks in parallel while respecting dependency constraints.

        Uses a DependencyTracker to build a directed acyclic graph (DAG) of
        task dependencies and executes tasks in topological order. Tasks
        without dependencies or with satisfied dependencies run concurrently,
        up to the ``max_concurrent_tasks`` limit.

        Execution Algorithm:
            1. Add all tasks to the dependency tracker
            2. Validate the dependency graph (detect cycles, missing deps)
            3. While tasks remain:
               a. Get all tasks ready for execution (dependencies satisfied)
               b. Execute ready tasks in batches up to max_concurrent_tasks
               c. Mark completed/failed tasks in tracker
               d. Repeat until no pending tasks

        Error Handling:
            - If a task fails, dependent tasks are blocked and marked as
              failed due to dependency failure
            - Execution continues for tasks not dependent on failed ones
            - A summary is logged at completion showing success/failure counts

        Args:
            tasks: List of Task objects to execute. Each task must have an
                ``id``, ``dependencies`` list, and ``prompt_issue_id``.
            plan_id: Plan identifier for logging and state grouping.

        Raises:
            ValueError: If dependencies reference non-existent tasks or
                contain cycles.
            RuntimeError: If a deadlock is detected (no ready tasks but
                tasks still pending, after validation passed).

        Side Effects:
            - Each task executes its implementation and code review stages
            - State updated for each task (in_progress, completed, failed)
            - Branches created for task implementations
            - Comments added to task issues

        Example:
            >>> tasks = [
            ...     Task(id="task-1", dependencies=[]),
            ...     Task(id="task-2", dependencies=["task-1"]),
            ... ]
            >>> await orchestrator.execute_parallel_tasks(tasks, "plan-42")
        """
        log.info("executing_parallel_tasks", plan_id=plan_id, task_count=len(tasks))

        tracker = DependencyTracker()

        # Add all tasks to tracker
        for task in tasks:
            tracker.add_task(task)

        # Validate dependencies
        try:
            tracker.validate_dependencies()
        except ValueError as e:
            log.error("dependency_validation_failed", plan_id=plan_id, error=str(e))
            raise

        # Execute tasks as dependencies complete
        while tracker.has_pending_tasks():
            ready_tasks = tracker.get_ready_tasks()

            if not ready_tasks:
                # Check for blocked tasks
                blocked = tracker.get_blocked_tasks()
                if blocked:
                    log.error(
                        "tasks_blocked_by_failures",
                        plan_id=plan_id,
                        blocked=[t.id for t in blocked],
                    )
                    break

                # No ready tasks but still pending - shouldn't happen after validation
                raise RuntimeError(f"Deadlock detected in task execution for plan {plan_id}")

            # Execute ready tasks in parallel (up to max_concurrent_tasks)
            max_concurrent = self.settings.workflow.max_concurrent_tasks

            for i in range(0, len(ready_tasks), max_concurrent):
                batch = ready_tasks[i : i + max_concurrent]

                log.info(
                    "executing_task_batch",
                    plan_id=plan_id,
                    batch_size=len(batch),
                    tasks=[t.id for t in batch],
                )

                # Mark tasks as in progress
                for task in batch:
                    tracker.mark_in_progress(task.id)

                # Execute batch
                results = await asyncio.gather(
                    *[self._execute_single_task(task, plan_id) for task in batch],
                    return_exceptions=True,
                )

                # Update tracker based on results
                for task, result in zip(batch, results, strict=False):
                    if isinstance(result, Exception):
                        tracker.mark_failed(task.id)
                        log.error(
                            "task_execution_failed",
                            task_id=task.id,
                            error=str(result),
                        )
                    else:
                        tracker.mark_complete(task.id)
                        log.info("task_completed", task_id=task.id)

        # Log final summary
        summary = tracker.get_summary()
        log.info("parallel_execution_completed", plan_id=plan_id, summary=summary)

    async def _execute_single_task(self, task: Task, plan_id: str) -> None:
        """Execute a single task through implementation and code review stages.

        Runs the task through its full lifecycle: retrieving the associated
        issue, executing the implementation stage, waiting for state updates,
        and then running the code review stage.

        This method is designed to be called concurrently via asyncio.gather()
        and handles its own error propagation. Errors are not caught here;
        they propagate to the caller (execute_parallel_tasks) for handling.

        Execution Flow:
            1. Validate task has an associated issue
            2. Fetch the issue from the git provider
            3. Execute the implementation stage
            4. Brief pause for state synchronization (1 second)
            5. Execute the code review stage

        Args:
            task: Task object containing the task details. Must have a
                ``prompt_issue_id`` referencing a valid issue number.
            plan_id: Plan identifier for context and logging.

        Raises:
            ValueError: If the task has no associated issue (prompt_issue_id
                is None or empty).
            Exception: Any exception from stage execution propagates up.

        Side Effects:
            - Implementation branch created with task changes
            - Code committed and pushed to the branch
            - Pull request created or updated
            - Issue labels updated (execute -> review)
            - Review comments added to the issue

        Note:
            The 1-second sleep between stages is a workaround to ensure
            state updates from the implementation stage are visible to the
            code review stage. This may be improved in future versions.
        """
        if not task.prompt_issue_id:
            raise ValueError(f"Task {task.id} has no associated issue")

        # Get task issue
        issue = await self.git.get_issue(task.prompt_issue_id)

        # Execute implementation stage
        await self.stages["implementation"].execute(issue)

        # Wait a bit for state to update
        await asyncio.sleep(1)

        # Execute code review stage
        await self.stages["code_review"].execute(issue)

    def _determine_stage(self, issue: Issue) -> str | None:
        """Determine which workflow stage should handle this issue.

        Examines the issue's labels and matches them against known workflow
        triggers. The matching follows a priority order where more specific
        label combinations are checked before general ones.

        Label Matching Priority (checked in order):
            1. New Granular Workflow:
               - "proposed" -> approval (awaiting approval)
               - "execute" + "task" -> task_execution
               - needs_planning tag -> proposal

            2. PR Review Workflow:
               - "needs-review" -> pr_review
               - "needs-fix" -> pr_fix
               - "approved" + "fix-proposal" -> fix_execution

            3. QA Workflow:
               - "requires-qa" -> qa

            4. Legacy Workflow (backward compatibility):
               - plan_review tag -> plan_review
               - code_review tag -> code_review
               - merge_ready tag -> merge

        Args:
            issue: Issue to analyze. Must have ``labels`` attribute populated.

        Returns:
            The name of the stage that should handle this issue (e.g.,
            "approval", "task_execution"), or None if no matching stage
            is found.

        Note:
            This method is purely deterministic and has no side effects.
            The tags used for matching are configured in ``settings.tags``.

        Example:
            >>> issue.labels = ["execute", "task", "plan-42"]
            >>> orchestrator._determine_stage(issue)
            'task_execution'
        """
        tags = self.settings.tags

        # New granular workflow routing
        # Check for proposal waiting for approval
        if "proposed" in issue.labels:
            return "approval"

        # Check for task ready for execution (requires both labels)
        if "execute" in issue.labels and "task" in issue.labels:
            return "task_execution"

        # Check for new issue needing plan proposal
        if tags.needs_planning in issue.labels:
            return "proposal"

        # PR review workflow
        # Check for PR needing code review (supports both "needs-review" and "sapiens/needs-review")
        if "needs-review" in issue.labels or "sapiens/needs-review" in issue.labels:
            return "pr_review"

        # Check for PR review complete, needs fix proposal (supports both patterns)
        if "needs-fix" in issue.labels or "sapiens/needs-fix" in issue.labels:
            return "pr_fix"

        # Check for approved fix proposal ready for execution
        if "approved" in issue.labels and "fix-proposal" in issue.labels:
            return "fix_execution"

        # QA workflow - check for QA requirement (supports both patterns)
        if "requires-qa" in issue.labels or "sapiens/requires-qa" in issue.labels:
            return "qa"

        # Legacy workflow routing (kept for compatibility)
        if tags.plan_review in issue.labels:
            return "plan_review"

        if tags.code_review in issue.labels:
            return "code_review"

        if tags.merge_ready in issue.labels:
            return "merge"

        return None
