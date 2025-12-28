"""Tests for domain models."""

from datetime import UTC, datetime

from automation.models.domain import (
    Issue,
    IssueState,
    Plan,
    Review,
    Task,
)


def test_issue_creation():
    """Test creating an Issue."""
    issue = Issue(
        id=1,
        number=42,
        title="Test Issue",
        body="Description",
        state=IssueState.OPEN,
        labels=["bug", "priority-high"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://gitea.test.com/issues/42",
    )

    assert issue.number == 42
    assert issue.state == IssueState.OPEN
    assert "bug" in issue.labels


def test_task_with_dependencies():
    """Test creating a Task with dependencies."""
    task = Task(
        id="task-1",
        prompt_issue_id=10,
        title="Implement feature",
        description="Feature description",
        dependencies=["task-0"],
        context={"plan_id": "42"},
    )

    assert task.id == "task-1"
    assert "task-0" in task.dependencies
    assert task.context["plan_id"] == "42"


def test_plan_creation():
    """Test creating a Plan."""
    tasks = [
        Task(
            id="task-1",
            prompt_issue_id=10,
            title="Task 1",
            description="First task",
        ),
        Task(
            id="task-2",
            prompt_issue_id=11,
            title="Task 2",
            description="Second task",
            dependencies=["task-1"],
        ),
    ]

    plan = Plan(
        id="42",
        title="Feature Plan",
        description="Plan description",
        tasks=tasks,
        file_path="plans/42-feature.md",
        created_at=datetime.now(UTC),
    )

    assert plan.id == "42"
    assert len(plan.tasks) == 2
    assert plan.tasks[1].dependencies == ["task-1"]


def test_review_creation():
    """Test creating a Review."""
    review = Review(
        approved=True,
        comments=["Looks good"],
        issues_found=[],
        suggestions=["Add more tests"],
        confidence_score=0.95,
    )

    assert review.approved is True
    assert review.confidence_score == 0.95
    assert len(review.suggestions) == 1
