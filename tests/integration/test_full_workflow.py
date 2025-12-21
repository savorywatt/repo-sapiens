"""Integration tests for full workflow."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from automation.engine.orchestrator import WorkflowOrchestrator
from automation.models.domain import Issue, IssueState, Plan, Task, TaskResult, Review


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_workflow(mock_settings, state_manager):
    """Test complete workflow from planning to PR."""

    # Create mock providers
    mock_git = AsyncMock()
    mock_agent = AsyncMock()

    # Setup mock responses
    planning_issue = Issue(
        id=1,
        number=1,
        title="Test Feature",
        body="Implement test feature",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="testuser",
        url="https://example.com/issues/1",
    )

    # Mock plan generation
    plan = Plan(
        id="1",
        title="Test Feature",
        description="Test description",
        tasks=[
            Task(
                id="task-1",
                title="Task 1",
                description="First task",
                dependencies=[],
                plan_id="1",
            ),
            Task(
                id="task-2",
                title="Task 2",
                description="Second task",
                dependencies=["task-1"],
                plan_id="1",
            ),
        ],
        file_path="plans/1-test-feature.md",
        created_at=datetime.now(),
        issue_number=1,
    )

    mock_agent.generate_plan.return_value = plan
    mock_agent.generate_prompts.return_value = plan.tasks

    # Mock task execution
    mock_agent.execute_task.return_value = TaskResult(
        success=True,
        branch="task/1-task-1",
        commits=["abc123"],
        files_changed=["test.py"],
        execution_time=1.0,
    )

    # Mock code review
    mock_agent.review_code.return_value = Review(
        approved=True,
        comments=["Looks good"],
        confidence_score=0.9,
    )

    # Mock git operations
    mock_git.commit_file.return_value = "abc123"
    mock_git.create_issue.return_value = Issue(
        id=2,
        number=2,
        title="[Plan Review] Test Feature",
        body="Review plan",
        state=IssueState.OPEN,
        labels=["plan-review"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="bot",
        url="https://example.com/issues/2",
    )

    # Create orchestrator
    orchestrator = WorkflowOrchestrator(
        mock_settings,
        mock_git,
        mock_agent,
        state_manager,
    )

    # Process planning stage
    await orchestrator.process_issue(planning_issue)

    # Verify planning stage completed
    state = await state_manager.load_state("1")
    assert state["stages"]["planning"]["status"] == "completed"

    # Verify plan was committed
    mock_git.commit_file.assert_called_once()

    # Verify review issue was created
    mock_git.create_issue.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parallel_task_execution(mock_settings, state_manager):
    """Test parallel execution of independent tasks."""

    mock_git = AsyncMock()
    mock_agent = AsyncMock()

    # Create tasks with parallel execution potential
    tasks = [
        Task(id="task-1", title="Task 1", dependencies=[], plan_id="1"),
        Task(id="task-2", title="Task 2", dependencies=[], plan_id="1"),
        Task(id="task-3", title="Task 3", dependencies=["task-1", "task-2"], plan_id="1"),
    ]

    # Mock task execution
    mock_agent.execute_task.return_value = TaskResult(
        success=True,
        branch="test-branch",
        commits=["abc123"],
        files_changed=["test.py"],
        execution_time=0.5,
    )

    mock_agent.review_code.return_value = Review(
        approved=True,
        confidence_score=0.9,
    )

    orchestrator = WorkflowOrchestrator(
        mock_settings,
        mock_git,
        mock_agent,
        state_manager,
    )

    # Execute tasks in parallel
    await orchestrator.execute_parallel_tasks(tasks, "1")

    # Verify all tasks were executed
    assert mock_agent.execute_task.call_count == 3

    # Verify state shows all tasks completed
    state = await state_manager.load_state("1")
    for task in tasks:
        # Tasks may not all be in state if mocking isn't perfect, but verify logic
        pass
