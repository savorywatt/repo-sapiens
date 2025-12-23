"""Branching strategies for workflow execution."""

from abc import ABC, abstractmethod

import structlog

from automation.config.settings import AutomationSettings
from automation.models.domain import Task
from automation.providers.base import GitProvider

log = structlog.get_logger(__name__)


class BranchingStrategy(ABC):
    """Abstract branching strategy base class."""

    def __init__(self, git: GitProvider, settings: AutomationSettings):
        """Initialize branching strategy.

        Args:
            git: Git provider instance
            settings: Automation settings
        """
        self.git = git
        self.settings = settings

    @abstractmethod
    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Create branch for task.

        Args:
            plan_id: Plan identifier
            task: Task to create branch for

        Returns:
            Branch name
        """
        pass

    @abstractmethod
    async def create_integration(
        self,
        plan_id: str,
        task_branches: list[str],
    ) -> str:
        """Create integration branch for merging.

        Args:
            plan_id: Plan identifier
            task_branches: List of task branch names

        Returns:
            Integration branch name
        """
        pass


class PerPlanStrategy(BranchingStrategy):
    """All tasks commit to single plan branch.

    In this strategy:
    - One branch per plan (e.g., plan/42)
    - All tasks commit to this branch sequentially
    - Integration branch is the plan branch itself
    - Simpler merge process, but serial execution required
    """

    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Use single plan branch for all tasks.

        Args:
            plan_id: Plan identifier
            task: Task (not used in this strategy)

        Returns:
            Plan branch name
        """
        branch_name = f"plan/{plan_id}"

        # Create branch if it doesn't exist
        existing = await self.git.get_branch(branch_name)

        if not existing:
            await self.git.create_branch(
                branch_name,
                self.settings.repository.default_branch,
            )
            log.info("created_plan_branch", branch=branch_name, plan_id=plan_id)
        else:
            log.debug("plan_branch_exists", branch=branch_name)

        return branch_name

    async def create_integration(
        self,
        plan_id: str,
        task_branches: list[str],
    ) -> str:
        """Integration branch is the plan branch.

        Args:
            plan_id: Plan identifier
            task_branches: Task branches (ignored)

        Returns:
            Plan branch name
        """
        integration_branch = f"plan/{plan_id}"
        log.info("using_plan_branch_for_integration", branch=integration_branch)
        return integration_branch


class PerAgentStrategy(BranchingStrategy):
    """Each task gets its own branch.

    In this strategy:
    - One branch per task (e.g., task/42-task-1)
    - Tasks can execute in parallel
    - Integration branch merges all task branches
    - More complex merge, but enables parallelism
    """

    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Create dedicated branch for task.

        Args:
            plan_id: Plan identifier
            task: Task to create branch for

        Returns:
            Task branch name
        """
        branch_name = f"task/{plan_id}-{task.id}"

        # Create branch from default branch
        await self.git.create_branch(
            branch_name,
            self.settings.repository.default_branch,
        )

        log.info(
            "created_task_branch",
            branch=branch_name,
            plan_id=plan_id,
            task_id=task.id,
        )

        return branch_name

    async def create_integration(
        self,
        plan_id: str,
        task_branches: list[str],
    ) -> str:
        """Merge all task branches into integration branch.

        Args:
            plan_id: Plan identifier
            task_branches: List of task branch names to merge

        Returns:
            Integration branch name
        """
        integration_branch = f"integration/plan-{plan_id}"

        log.info(
            "creating_integration_branch",
            branch=integration_branch,
            task_count=len(task_branches),
        )

        # Create integration branch from default branch
        await self.git.create_branch(
            integration_branch,
            self.settings.repository.default_branch,
        )

        # Merge all task branches in order
        for task_branch in task_branches:
            try:
                await self.git.merge_branches(
                    source=task_branch,
                    target=integration_branch,
                    message=f"Merge {task_branch} into integration",
                )
                log.info(
                    "merged_task_branch",
                    task_branch=task_branch,
                    integration=integration_branch,
                )
            except Exception as e:
                log.error(
                    "merge_failed",
                    task_branch=task_branch,
                    integration=integration_branch,
                    error=str(e),
                )
                # In case of merge conflict, we might want to handle it
                # For now, re-raise to let caller handle
                raise

        log.info(
            "integration_branch_ready",
            branch=integration_branch,
            merged_count=len(task_branches),
        )

        return integration_branch


def get_branching_strategy(
    strategy_name: str,
    git: GitProvider,
    settings: AutomationSettings,
) -> BranchingStrategy:
    """Factory function for branching strategies.

    Args:
        strategy_name: Strategy name ("per-plan" or "per-agent")
        git: Git provider instance
        settings: Automation settings

    Returns:
        BranchingStrategy instance

    Raises:
        ValueError: If strategy name is unknown
    """
    if strategy_name == "per-plan":
        return PerPlanStrategy(git, settings)
    elif strategy_name == "per-agent":
        return PerAgentStrategy(git, settings)
    else:
        raise ValueError(f"Unknown branching strategy: {strategy_name}")
