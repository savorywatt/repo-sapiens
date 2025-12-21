# Phase 2: Core Workflow - Implementation Guide

## Overview

Build the complete workflow pipeline from issue to pull request. This phase implements all remaining workflow stages, dependency tracking, branching strategies, and end-to-end integration tests.

## Prerequisites

- Phase 1 completed successfully
- All Phase 1 tests passing
- Basic planning workflow functional

## Implementation Steps

### Step 1: Complete Git Provider Implementation

**Files to Modify:**
- `/home/ross/Workspace/builder/automation/providers/git_provider.py`

**Actions:**

Implement all remaining `GitProvider` methods in `GiteaProvider`:

1. **Issue Operations:**
   - `get_issue(issue_number)`: Get single issue by number
   - `update_issue(issue_number, **kwargs)`: Update issue fields (title, body, labels, state)
   - `get_comments(issue_number)`: Retrieve all comments for an issue

2. **Branch Operations:**
   - `get_branch(branch_name)`: Get branch information
   - `get_diff(base, head)`: Get diff between two branches
   - `merge_branches(source, target, message)`: Merge source into target

3. **Pull Request Operations:**
   - `create_pull_request(title, body, head, base, labels)`: Create PR

4. **File Operations:**
   - `get_file(path, ref)`: Read file contents from repository

Implementation notes:
- Use MCP client for all operations
- Handle API errors gracefully (404, 403, rate limits)
- Add retry logic using the `@async_retry` decorator
- Log all API calls with structured logging
- Parse API responses into domain models

Example with retry:
```python
from automation.utils.retry import async_retry

@async_retry(max_attempts=3, backoff_factor=2.0)
async def update_issue(
    self,
    issue_number: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    labels: Optional[List[str]] = None,
    state: Optional[str] = None
) -> Issue:
    """Update issue via MCP with retry."""
    log.info("update_issue", issue=issue_number)

    params = {
        "owner": self.owner,
        "repo": self.repo,
        "number": issue_number
    }

    if title is not None:
        params["title"] = title
    if body is not None:
        params["body"] = body
    if labels is not None:
        params["labels"] = labels
    if state is not None:
        params["state"] = state

    result = await self.mcp.call_tool("gitea_update_issue", **params)
    return self._parse_issue(result)
```

**Testing:**
- Create unit tests with mocked MCP client
- Test error handling and retries
- Test all CRUD operations

### Step 2: Complete Agent Provider Implementation

**Files to Modify:**
- `/home/ross/Workspace/builder/automation/providers/agent_provider.py`

**Actions:**

Implement remaining `AgentProvider` methods:

1. **`generate_prompts(plan)`:**
   - Read plan file content
   - Parse markdown to extract tasks
   - Identify dependencies between tasks
   - Create `Task` objects with proper metadata
   - Return list of tasks in dependency order

2. **`execute_task(task, context)`:**
   - Build comprehensive prompt from task and context
   - Checkout the correct branch
   - Execute Claude Code with the prompt
   - Parse execution output
   - Extract commits and files changed
   - Return `TaskResult` with success/failure info

3. **`review_code(diff, context)`:**
   - Build review prompt with diff and context
   - Execute Claude Code for review
   - Parse review output (expect JSON response)
   - Return `Review` object with approval status and comments

4. **Helper methods:**
   - `_extract_tasks_from_plan(content)`: Parse markdown plan
     - Look for task sections (e.g., "## Tasks", numbered lists)
     - Extract task title and description
     - Parse dependency markers (e.g., "Depends on: Task 1")
   - `_parse_claude_output(output)`: Parse Claude CLI output
     - Extract generated content
     - Identify what files were changed
     - Parse git log for new commits
   - `_checkout_branch(branch)`: Switch git branches safely

Example task extraction:
```python
def _extract_tasks_from_plan(self, plan_content: str) -> List[Dict]:
    """Parse tasks from plan markdown content."""
    import re

    tasks = []

    # Look for task sections (e.g., ### Task 1: ...)
    task_pattern = r'###\s+Task\s+(\d+):\s+(.+?)\n(.+?)(?=###|$)'
    matches = re.finditer(task_pattern, plan_content, re.DOTALL)

    for match in matches:
        task_num = int(match.group(1))
        title = match.group(2).strip()
        description = match.group(3).strip()

        # Look for dependency markers
        deps = []
        dep_pattern = r'Depends on:\s*(?:Task\s*)?(\d+(?:,\s*\d+)*)'
        dep_match = re.search(dep_pattern, description)
        if dep_match:
            deps = [f"task-{d.strip()}" for d in dep_match.group(1).split(',')]

        tasks.append({
            "id": f"task-{task_num}",
            "title": title,
            "description": description,
            "dependencies": deps
        })

    return tasks
```

**Testing:**
- Test plan parsing with various markdown formats
- Test task execution with mocked Claude output
- Test code review with sample diffs
- Test error handling for Claude failures

### Step 3: Dependency Tracking

**Files to Create:**
- `/home/ross/Workspace/builder/automation/processors/dependency_tracker.py`

**Implementation:**

Create dependency tracker for managing task execution order:

```python
from typing import List, Dict, Set
from automation.models.domain import Task
import structlog

log = structlog.get_logger(__name__)

class DependencyTracker:
    """Track and resolve task dependencies."""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.status: Dict[str, str] = {}

    def add_task(self, task: Task) -> None:
        """Add task to tracker."""
        self.tasks[task.id] = task
        self.status[task.id] = "pending"

    def is_ready(self, task_id: str) -> bool:
        """Check if task is ready to execute (all dependencies complete)."""
        task = self.tasks[task_id]

        for dep_id in task.dependencies:
            if self.status.get(dep_id) != "completed":
                return False

        return True

    def mark_complete(self, task_id: str) -> None:
        """Mark task as completed."""
        self.status[task_id] = "completed"
        log.info("task_completed", task_id=task_id)

    def mark_failed(self, task_id: str) -> None:
        """Mark task as failed."""
        self.status[task_id] = "failed"
        log.error("task_failed", task_id=task_id)

    def get_ready_tasks(self) -> List[Task]:
        """Get all tasks ready for execution."""
        ready = []
        for task_id, task in self.tasks.items():
            if self.status[task_id] == "pending" and self.is_ready(task_id):
                ready.append(task)
        return ready

    def has_pending_tasks(self) -> bool:
        """Check if there are any pending tasks."""
        return any(status == "pending" for status in self.status.values())

    def get_blocked_tasks(self) -> List[Task]:
        """Get tasks that are blocked by failed dependencies."""
        blocked = []
        for task_id, task in self.tasks.items():
            if self.status[task_id] == "pending":
                for dep_id in task.dependencies:
                    if self.status.get(dep_id) == "failed":
                        blocked.append(task)
                        break
        return blocked

    def validate_dependencies(self) -> bool:
        """Check for circular dependencies and invalid references."""
        def has_cycle(task_id: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks[task_id]
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    raise ValueError(f"Invalid dependency: {dep_id} not found")

                if dep_id not in visited:
                    if has_cycle(dep_id, visited, rec_stack):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        visited = set()
        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id, visited, set()):
                    return False

        return True
```

**Testing:**
- Test simple dependency chains (A → B → C)
- Test parallel tasks (A → C, B → C)
- Test circular dependency detection
- Test invalid dependency references

### Step 4: Remaining Workflow Stages

**Files to Create:**
- `/home/ross/Workspace/builder/automation/engine/stages/plan_review.py`
- `/home/ross/Workspace/builder/automation/engine/stages/implementation.py`
- `/home/ross/Workspace/builder/automation/engine/stages/code_review.py`
- `/home/ross/Workspace/builder/automation/engine/stages/merge.py`

**Implementation:**

1. **Plan Review Stage** (`plan_review.py`):
```python
class PlanReviewStage(WorkflowStage):
    """Review plan and generate prompt issues."""

    async def execute(self, issue: Issue) -> None:
        """Execute plan review stage."""
        # 1. Extract plan_id from issue (from original planning issue reference)
        # 2. Read plan file from repository
        # 3. Use agent to generate prompts from plan
        # 4. Create issue for each prompt with appropriate labels
        # 5. Store dependencies in state
        # 6. Close plan review issue
        # 7. Update state
```

2. **Implementation Stage** (`implementation.py`):
```python
class ImplementationStage(WorkflowStage):
    """Execute implementation tasks."""

    async def execute(self, issue: Issue) -> None:
        """Execute implementation stage."""
        # 1. Get task details from issue
        # 2. Check dependencies are complete
        # 3. Create/checkout branch based on strategy
        # 4. Build task context (plan file, dependencies, etc.)
        # 5. Execute task using agent
        # 6. Commit changes to branch
        # 7. Update issue with results
        # 8. Tag issue for code review
        # 9. Update state
```

3. **Code Review Stage** (`code_review.py`):
```python
class CodeReviewStage(WorkflowStage):
    """Review implemented code."""

    async def execute(self, issue: Issue) -> None:
        """Execute code review stage."""
        # 1. Get task branch from state
        # 2. Get diff between branch and base
        # 3. Use agent to review code
        # 4. Post review comments on issue
        # 5. If approved: tag as merge-ready
        # 6. If changes needed: create follow-up issues
        # 7. Update state
```

4. **Merge Stage** (`merge.py`):
```python
class MergeStage(WorkflowStage):
    """Merge completed tasks."""

    async def execute(self, issue: Issue) -> None:
        """Execute merge stage."""
        # 1. Get plan_id from issue
        # 2. Check all tasks are merge-ready
        # 3. Based on branching strategy:
        #    - Per-Plan: Create PR from plan branch
        #    - Per-Agent: Create integration branch, merge all task branches, create PR
        # 4. Generate PR description with all task details
        # 5. Create PR
        # 6. Update all related issues
        # 7. Mark plan as completed in state
```

Implementation notes for each stage:
- Follow the same pattern as `PlanningStage`
- Use structured logging throughout
- Handle errors with `_handle_stage_error()`
- Update state after each major operation
- Add detailed docstrings

### Step 5: Branching Strategies

**Files to Create:**
- `/home/ross/Workspace/builder/automation/engine/branching.py`

**Implementation:**

Create branching strategy implementations:

```python
from abc import ABC, abstractmethod
from typing import List
from automation.models.domain import Task
from automation.providers.base import GitProvider
from automation.config.settings import AutomationSettings
import structlog

log = structlog.get_logger(__name__)

class BranchingStrategy(ABC):
    """Abstract branching strategy."""

    def __init__(self, git: GitProvider, settings: AutomationSettings):
        self.git = git
        self.settings = settings

    @abstractmethod
    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Create branch for task. Returns branch name."""
        pass

    @abstractmethod
    async def create_integration(self, plan_id: str, task_branches: List[str]) -> str:
        """Create integration branch. Returns branch name."""
        pass

class PerPlanStrategy(BranchingStrategy):
    """All tasks commit to single plan branch."""

    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Use single plan branch for all tasks."""
        branch_name = f"plan/{plan_id}"

        # Create branch if it doesn't exist
        existing = await self.git.get_branch(branch_name)
        if not existing:
            await self.git.create_branch(
                branch_name,
                self.settings.repository.default_branch
            )
            log.info("created_plan_branch", branch=branch_name)

        return branch_name

    async def create_integration(self, plan_id: str, task_branches: List[str]) -> str:
        """Integration branch is the plan branch."""
        return f"plan/{plan_id}"

class PerAgentStrategy(BranchingStrategy):
    """Each task gets its own branch."""

    async def create_task_branch(self, plan_id: str, task: Task) -> str:
        """Create dedicated branch for task."""
        branch_name = f"task/{plan_id}-{task.id}"

        await self.git.create_branch(
            branch_name,
            self.settings.repository.default_branch
        )
        log.info("created_task_branch", branch=branch_name, task=task.id)

        return branch_name

    async def create_integration(self, plan_id: str, task_branches: List[str]) -> str:
        """Merge all task branches into integration branch."""
        integration_branch = f"integration/plan-{plan_id}"

        # Create integration branch from main
        await self.git.create_branch(
            integration_branch,
            self.settings.repository.default_branch
        )

        # Merge all task branches
        for task_branch in task_branches:
            await self.git.merge_branches(
                source=task_branch,
                target=integration_branch,
                message=f"Merge {task_branch} into integration"
            )
            log.info("merged_task_branch",
                    task_branch=task_branch,
                    integration=integration_branch)

        return integration_branch

def get_branching_strategy(
    strategy_name: str,
    git: GitProvider,
    settings: AutomationSettings
) -> BranchingStrategy:
    """Factory function for branching strategies."""
    if strategy_name == "per-plan":
        return PerPlanStrategy(git, settings)
    elif strategy_name == "per-agent":
        return PerAgentStrategy(git, settings)
    else:
        raise ValueError(f"Unknown branching strategy: {strategy_name}")
```

### Step 6: Orchestrator Enhancement

**Files to Modify:**
- `/home/ross/Workspace/builder/automation/engine/orchestrator.py`

**Actions:**

Enhance orchestrator to handle all stages:

1. Add all stage imports and initialization
2. Update `_determine_stage()` to handle all tags
3. Add `process_plan()` method to process entire plan
4. Add parallel task execution support:

```python
async def execute_parallel_tasks(self, tasks: List[Task], plan_id: str) -> None:
    """Execute tasks in parallel respecting dependencies."""
    tracker = DependencyTracker()

    for task in tasks:
        tracker.add_task(task)

    # Validate dependencies
    if not tracker.validate_dependencies():
        raise ValueError("Circular dependencies detected")

    # Execute tasks as dependencies complete
    while tracker.has_pending_tasks():
        ready_tasks = tracker.get_ready_tasks()

        if not ready_tasks:
            # Check for blocked tasks
            blocked = tracker.get_blocked_tasks()
            if blocked:
                log.error("tasks_blocked", blocked=[t.id for t in blocked])
                break
            # No ready tasks but still pending - shouldn't happen
            raise RuntimeError("Deadlock detected in task execution")

        # Execute ready tasks in parallel (up to max_concurrent_tasks)
        max_concurrent = self.settings.workflow.max_concurrent_tasks
        for i in range(0, len(ready_tasks), max_concurrent):
            batch = ready_tasks[i:i+max_concurrent]

            results = await asyncio.gather(
                *[self._execute_single_task(task, plan_id) for task in batch],
                return_exceptions=True
            )

            # Update tracker based on results
            for task, result in zip(batch, results):
                if isinstance(result, Exception):
                    tracker.mark_failed(task.id)
                    log.error("task_execution_failed", task=task.id, error=str(result))
                else:
                    tracker.mark_complete(task.id)

async def _execute_single_task(self, task: Task, plan_id: str) -> None:
    """Execute a single task."""
    # Create implementation issue if not exists
    # Execute implementation stage
    # Wait for code review stage
    # Return result
```

### Step 7: CLI Enhancements

**Files to Modify:**
- `/home/ross/Workspace/builder/automation/main.py`

**Actions:**

Add new CLI commands:

```python
@cli.command()
@click.option("--tag", help="Process issues with specific tag")
@click.pass_context
def process_all(ctx, tag):
    """Process all issues with optional tag filter."""
    asyncio.run(_process_all_issues(ctx.obj["settings"], tag))

@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to process")
@click.pass_context
def process_plan(ctx, plan_id):
    """Process entire plan end-to-end."""
    asyncio.run(_process_plan(ctx.obj["settings"], plan_id))

@cli.command()
@click.pass_context
def daemon(ctx):
    """Run in daemon mode, polling for new issues."""
    asyncio.run(_daemon_mode(ctx.obj["settings"]))

async def _daemon_mode(settings: AutomationSettings):
    """Daemon mode: poll for issues continuously."""
    log.info("daemon_started", interval=60)

    # Initialize orchestrator
    orchestrator = await _create_orchestrator(settings)

    while True:
        try:
            await orchestrator.process_all_issues()
        except Exception as e:
            log.error("daemon_error", error=str(e), exc_info=True)

        await asyncio.sleep(60)  # Poll every minute
```

### Step 8: Integration Tests

**Files to Create:**
- `/home/ross/Workspace/builder/tests/integration/test_full_workflow.py`
- `/home/ross/Workspace/builder/tests/integration/test_branching_strategies.py`

**Implementation:**

Create end-to-end integration tests:

```python
# tests/integration/test_full_workflow.py
import pytest
from automation.engine.orchestrator import WorkflowOrchestrator
from automation.models.domain import Issue, IssueState
from datetime import datetime

@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_workflow(mock_git, mock_agent, state_manager, settings):
    """Test complete workflow from planning to PR."""

    # 1. Create planning issue
    planning_issue = Issue(
        id=1, number=1, title="Test Feature",
        body="Implement test feature",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="testuser",
        url="https://example.com/issues/1"
    )

    orchestrator = WorkflowOrchestrator(settings, mock_git, mock_agent, state_manager)

    # 2. Process planning stage
    await orchestrator.process_issue(planning_issue)

    # Verify plan created
    state = await state_manager.load_state("1")
    assert state["stages"]["planning"]["status"] == "completed"

    # 3. Get plan review issue and process
    # 4. Get prompt issues and process
    # 5. Execute implementation
    # 6. Run code review
    # 7. Merge and create PR

    # Verify final state
    final_state = await state_manager.load_state("1")
    assert final_state["status"] == "completed"

    # Verify PR was created
    # Verify all issues are closed
```

Additional integration tests:
- Test dependency resolution
- Test parallel task execution
- Test error recovery
- Test both branching strategies
- Test merge conflict handling

### Step 9: Error Recovery

**Files to Create:**
- `/home/ross/Workspace/builder/automation/engine/recovery.py`

**Implementation:**

Create error recovery system:

```python
from typing import Optional
from automation.engine.state_manager import StateManager
from automation.providers.base import GitProvider
import structlog

log = structlog.get_logger(__name__)

class WorkflowRecovery:
    """Handle workflow failures and recovery."""

    def __init__(self, state: StateManager, git: GitProvider):
        self.state = state
        self.git = git

    async def recover_failed_workflow(self, plan_id: str) -> bool:
        """Attempt to recover a failed workflow."""
        state = await self.state.load_state(plan_id)

        if state["status"] != "failed":
            log.warning("workflow_not_failed", plan_id=plan_id)
            return False

        # Determine which stage failed
        failed_stage = self._find_failed_stage(state)

        if not failed_stage:
            log.error("cannot_determine_failed_stage", plan_id=plan_id)
            return False

        # Attempt recovery based on stage
        recovery_method = getattr(self, f"_recover_{failed_stage}", None)
        if recovery_method:
            return await recovery_method(plan_id, state)

        log.error("no_recovery_method", stage=failed_stage)
        return False

    def _find_failed_stage(self, state: dict) -> Optional[str]:
        """Find which stage failed."""
        for stage_name, stage_data in state["stages"].items():
            if stage_data.get("status") == "failed":
                return stage_name
        return None

    async def _recover_planning(self, plan_id: str, state: dict) -> bool:
        """Recover from planning stage failure."""
        # Delete partial plan file
        # Reset state
        # Create recovery issue
        pass

    # Implement recovery methods for other stages...
```

### Step 10: Documentation

**Files to Create:**
- `/home/ross/Workspace/builder/automation/README.md`
- `/home/ross/Workspace/builder/docs/workflow-stages.md`
- `/home/ross/Workspace/builder/docs/branching-strategies.md`

**Content:**

Document:
- Complete workflow process
- Each stage's responsibilities
- Branching strategies and when to use each
- Error handling and recovery
- Configuration options
- CLI usage examples
- State file format

## Success Criteria

At the end of Phase 2, you should be able to:

1. **Process Complete Workflow:**
   ```bash
   automation process-plan --plan-id 42
   # Executes all stages from planning to PR
   ```

2. **Handle Dependencies:**
   - Tasks execute in correct order
   - Parallel tasks execute concurrently
   - Blocked tasks wait for dependencies

3. **Both Branching Strategies Work:**
   ```yaml
   # Test per-plan strategy
   workflow:
     branching_strategy: per-plan

   # Test per-agent strategy
   workflow:
     branching_strategy: per-agent
   ```

4. **Integration Tests Pass:**
   ```bash
   pytest tests/integration/ -v
   # All integration tests pass
   ```

5. **Error Recovery:**
   - Failed tasks are detected
   - State preserved on failure
   - Recovery mechanisms work

6. **Code Quality:**
   ```bash
   pytest tests/ --cov=automation --cov-report=html
   # Coverage > 80%

   mypy automation/
   # No type errors
   ```

## Common Issues and Solutions

**Issue: Task deadlock (no ready tasks but still pending)**
- Solution: Check dependency validation in `DependencyTracker`
- Ensure no circular dependencies
- Log detailed dependency state

**Issue: Merge conflicts in integration branch**
- Solution: Implement conflict detection in `merge_branches()`
- Create conflict-resolution issue
- Fallback to manual resolution

**Issue: Parallel task execution fails**
- Solution: Use `asyncio.gather(..., return_exceptions=True)`
- Handle exceptions individually
- Don't let one failure crash all tasks

**Issue: State file corruption**
- Solution: Implement state validation on load
- Keep backup of previous state
- Add state recovery command

## Next Steps

After completing Phase 2:
1. Thoroughly test with real Gitea instance
2. Test with various plan complexities
3. Document any limitations discovered
4. Move on to Phase 3: Gitea Actions Integration

Phase 3 will add:
- Automated execution via Gitea Actions
- Event-based triggers
- Webhook support
- Production deployment
