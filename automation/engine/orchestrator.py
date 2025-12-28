"""Workflow orchestrator for managing automation pipeline."""

import asyncio

import structlog

from automation.config.settings import AutomationSettings
from automation.engine.stages.approval import ApprovalStage
from automation.engine.stages.code_review import CodeReviewStage
from automation.engine.stages.execution import TaskExecutionStage
from automation.engine.stages.fix_execution import FixExecutionStage
from automation.engine.stages.implementation import ImplementationStage
from automation.engine.stages.merge import MergeStage
from automation.engine.stages.plan_review import PlanReviewStage
from automation.engine.stages.planning import PlanningStage
from automation.engine.stages.pr_fix import PRFixStage
from automation.engine.stages.pr_review import PRReviewStage
from automation.engine.stages.proposal import ProposalStage
from automation.engine.stages.qa import QAStage
from automation.engine.state_manager import StateManager
from automation.models.domain import Issue, Task
from automation.processors.dependency_tracker import DependencyTracker
from automation.providers.base import AgentProvider, GitProvider

log = structlog.get_logger(__name__)


class WorkflowOrchestrator:
    """Orchestrate the complete automation workflow.

    Manages issue processing, stage routing, parallel task execution,
    and error handling across the entire workflow pipeline.
    """

    def __init__(
        self,
        settings: AutomationSettings,
        git: GitProvider,
        agent: AgentProvider,
        state: StateManager,
    ):
        """Initialize orchestrator.

        Args:
            settings: Automation settings
            git: Git provider instance
            agent: Agent provider instance
            state: State manager instance
        """
        self.settings = settings
        self.git = git
        self.agent = agent
        self.state = state

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

        Args:
            tag: Optional tag filter
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
        """Process a single issue.

        Determines which stage to execute based on issue labels.

        Args:
            issue: Issue to process
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
        """Process entire plan end-to-end.

        Executes all stages for a plan, including parallel task execution.

        Args:
            plan_id: Plan identifier
        """
        log.info("processing_plan", plan_id=plan_id)

        # Load plan state
        state = await self.state.load_state(plan_id)

        # Get planning issue
        planning_stage = state.get("stages", {}).get("planning", {})
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
        """Execute tasks in parallel respecting dependencies.

        Uses dependency tracker to determine execution order and runs
        tasks concurrently when possible.

        Args:
            tasks: List of tasks to execute
            plan_id: Plan identifier
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
        """Execute a single task.

        Args:
            task: Task to execute
            plan_id: Plan identifier
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
        """Determine which stage to execute based on issue labels.

        Args:
            issue: Issue to check

        Returns:
            Stage name or None if no matching stage
        """
        tags = self.settings.tags

        # New granular workflow routing
        if "proposed" in issue.labels:
            # Proposal issue waiting for approval
            return "approval"
        elif "execute" in issue.labels and "task" in issue.labels:
            # Task ready for execution
            return "task_execution"
        elif tags.needs_planning in issue.labels:
            # New issue needing plan proposal
            return "proposal"
        # PR review workflow
        elif "needs-review" in issue.labels:
            # PR needs code review
            return "pr_review"
        elif "needs-fix" in issue.labels:
            # PR review complete, create fix proposal
            return "pr_fix"
        elif "approved" in issue.labels and "fix-proposal" in issue.labels:
            # Fix proposal approved, execute fixes
            return "fix_execution"
        # QA workflow
        elif "requires-qa" in issue.labels:
            # PR/issue needs QA (build and test)
            return "qa"
        # Legacy workflow routing (kept for compatibility)
        elif tags.plan_review in issue.labels:
            return "plan_review"
        elif tags.code_review in issue.labels:
            return "code_review"
        elif tags.merge_ready in issue.labels:
            return "merge"

        return None
