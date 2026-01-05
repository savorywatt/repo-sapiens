"""Comprehensive unit tests for engine/context.py."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from repo_sapiens.engine.context import ExecutionContext
from repo_sapiens.models.domain import Issue, IssueState


@pytest.fixture
def sample_issue() -> Issue:
    """Sample issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Test Issue",
        body="Test body",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://example.com/issues/42",
    )


class TestExecutionContextCreation:
    """Tests for ExecutionContext creation."""

    def test_create_with_required_field_only(self, sample_issue: Issue):
        """Test creating context with only required issue field."""
        ctx = ExecutionContext(issue=sample_issue)

        assert ctx.issue == sample_issue
        assert ctx.plan_id is None
        assert ctx.workspace_path is None
        assert ctx.branch_name is None
        assert ctx.stage_outputs == {}
        assert ctx.dry_run is False

    def test_create_with_all_fields(self, sample_issue: Issue, tmp_path: Path):
        """Test creating context with all fields."""
        outputs: dict[str, Any] = {"planning": {"result": "success"}}
        ctx = ExecutionContext(
            issue=sample_issue,
            plan_id="plan-42",
            workspace_path=tmp_path,
            branch_name="feature/test",
            stage_outputs=outputs,
            dry_run=True,
        )

        assert ctx.issue == sample_issue
        assert ctx.plan_id == "plan-42"
        assert ctx.workspace_path == tmp_path
        assert ctx.branch_name == "feature/test"
        assert ctx.stage_outputs == outputs
        assert ctx.dry_run is True

    def test_stage_outputs_default_is_empty_dict(self, sample_issue: Issue):
        """Test stage_outputs defaults to empty dict, not None."""
        ctx = ExecutionContext(issue=sample_issue)
        assert ctx.stage_outputs == {}
        assert isinstance(ctx.stage_outputs, dict)


class TestGetStageOutput:
    """Tests for get_stage_output method."""

    def test_get_existing_stage_output(self, sample_issue: Issue):
        """Test getting output from completed stage."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={"planning": {"plan_id": "42", "tasks": 5}},
        )

        output = ctx.get_stage_output("planning")
        assert output == {"plan_id": "42", "tasks": 5}

    def test_get_nonexistent_stage_output(self, sample_issue: Issue):
        """Test getting output from non-existent stage returns None."""
        ctx = ExecutionContext(issue=sample_issue)

        output = ctx.get_stage_output("planning")
        assert output is None

    def test_get_stage_output_various_types(self, sample_issue: Issue):
        """Test getting outputs of various types."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={
                "string_output": "hello",
                "int_output": 42,
                "list_output": [1, 2, 3],
                "none_output": None,
            },
        )

        assert ctx.get_stage_output("string_output") == "hello"
        assert ctx.get_stage_output("int_output") == 42
        assert ctx.get_stage_output("list_output") == [1, 2, 3]
        assert ctx.get_stage_output("none_output") is None


class TestSetStageOutput:
    """Tests for set_stage_output method."""

    def test_set_stage_output_new(self, sample_issue: Issue):
        """Test setting output for new stage."""
        ctx = ExecutionContext(issue=sample_issue)

        ctx.set_stage_output("planning", {"plan_id": "42"})

        assert ctx.stage_outputs["planning"] == {"plan_id": "42"}

    def test_set_stage_output_overwrites_existing(self, sample_issue: Issue):
        """Test setting output overwrites existing stage output."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={"planning": {"old": "value"}},
        )

        ctx.set_stage_output("planning", {"new": "value"})

        assert ctx.stage_outputs["planning"] == {"new": "value"}
        assert "old" not in ctx.stage_outputs["planning"]

    def test_set_stage_output_various_types(self, sample_issue: Issue):
        """Test setting outputs of various types."""
        ctx = ExecutionContext(issue=sample_issue)

        ctx.set_stage_output("string", "hello")
        ctx.set_stage_output("int", 42)
        ctx.set_stage_output("list", [1, 2, 3])
        ctx.set_stage_output("dict", {"key": "value"})
        ctx.set_stage_output("none", None)

        assert ctx.stage_outputs["string"] == "hello"
        assert ctx.stage_outputs["int"] == 42
        assert ctx.stage_outputs["list"] == [1, 2, 3]
        assert ctx.stage_outputs["dict"] == {"key": "value"}
        assert ctx.stage_outputs["none"] is None


class TestWithUpdates:
    """Tests for with_updates method."""

    def test_with_updates_returns_new_instance(self, sample_issue: Issue):
        """Test with_updates returns a new context instance."""
        original = ExecutionContext(issue=sample_issue)

        updated = original.with_updates(plan_id="42")

        assert updated is not original
        assert original.plan_id is None
        assert updated.plan_id == "42"

    def test_with_updates_preserves_other_fields(
        self, sample_issue: Issue, tmp_path: Path
    ):
        """Test with_updates preserves unchanged fields."""
        original = ExecutionContext(
            issue=sample_issue,
            plan_id="original",
            workspace_path=tmp_path,
            branch_name="main",
            dry_run=True,
        )

        updated = original.with_updates(plan_id="updated")

        assert updated.issue == sample_issue
        assert updated.plan_id == "updated"
        assert updated.workspace_path == tmp_path
        assert updated.branch_name == "main"
        assert updated.dry_run is True

    def test_with_updates_multiple_fields(self, sample_issue: Issue, tmp_path: Path):
        """Test updating multiple fields at once."""
        original = ExecutionContext(issue=sample_issue)

        updated = original.with_updates(
            plan_id="42",
            workspace_path=tmp_path,
            branch_name="feature/test",
            dry_run=True,
        )

        assert updated.plan_id == "42"
        assert updated.workspace_path == tmp_path
        assert updated.branch_name == "feature/test"
        assert updated.dry_run is True

    def test_with_updates_can_set_to_none(self, sample_issue: Issue):
        """Test with_updates can set fields to None."""
        original = ExecutionContext(
            issue=sample_issue,
            plan_id="42",
        )

        updated = original.with_updates(plan_id=None)

        assert updated.plan_id is None

    def test_with_updates_can_update_issue(self, sample_issue: Issue):
        """Test with_updates can update the issue."""
        new_issue = Issue(
            id=2,
            number=99,
            title="New Issue",
            body="New body",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            author="newuser",
            url="https://example.com/issues/99",
        )

        original = ExecutionContext(issue=sample_issue)
        updated = original.with_updates(issue=new_issue)

        assert updated.issue.number == 99
        assert original.issue.number == 42


class TestHasStageCompleted:
    """Tests for has_stage_completed method."""

    def test_has_stage_completed_true(self, sample_issue: Issue):
        """Test returns True when stage has output."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={"planning": {"result": "success"}},
        )

        assert ctx.has_stage_completed("planning") is True

    def test_has_stage_completed_false(self, sample_issue: Issue):
        """Test returns False when stage has no output."""
        ctx = ExecutionContext(issue=sample_issue)

        assert ctx.has_stage_completed("planning") is False

    def test_has_stage_completed_with_none_output(self, sample_issue: Issue):
        """Test returns True even when stage output is None."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={"planning": None},
        )

        # Stage is in outputs dict, so it's considered completed
        assert ctx.has_stage_completed("planning") is True

    def test_has_stage_completed_empty_outputs(self, sample_issue: Issue):
        """Test returns False when outputs are empty."""
        ctx = ExecutionContext(
            issue=sample_issue,
            stage_outputs={},
        )

        assert ctx.has_stage_completed("planning") is False


class TestDataclassProperties:
    """Tests for dataclass properties and behavior."""

    def test_context_is_immutable_default_factory(self, sample_issue: Issue):
        """Test that default factory creates separate dicts."""
        ctx1 = ExecutionContext(issue=sample_issue)
        ctx2 = ExecutionContext(issue=sample_issue)

        ctx1.stage_outputs["planning"] = "value"

        # ctx2 should not be affected
        assert "planning" not in ctx2.stage_outputs

    def test_context_equality(self, sample_issue: Issue):
        """Test context equality comparison."""
        ctx1 = ExecutionContext(issue=sample_issue, plan_id="42")
        ctx2 = ExecutionContext(issue=sample_issue, plan_id="42")

        # Dataclasses support equality by default
        assert ctx1 == ctx2

    def test_context_hash_not_supported(self, sample_issue: Issue):
        """Test that context is not hashable (has mutable field)."""
        ctx = ExecutionContext(issue=sample_issue)

        # Dataclasses with mutable defaults are not hashable by default
        with pytest.raises(TypeError):
            hash(ctx)


class TestIntegrationScenarios:
    """Integration tests for typical usage patterns."""

    def test_workflow_progression(self, sample_issue: Issue, tmp_path: Path):
        """Test context modification through workflow stages."""
        # Start with minimal context
        ctx = ExecutionContext(issue=sample_issue)

        # Planning stage completes
        ctx.set_stage_output("planning", {"plan_id": "42", "task_count": 3})
        ctx = ctx.with_updates(plan_id="42")

        # Implementation stage starts
        ctx = ctx.with_updates(
            workspace_path=tmp_path,
            branch_name="plan/42",
        )

        # Implementation completes
        ctx.set_stage_output("implementation", {"pr_number": 100})

        # Verify final state
        assert ctx.plan_id == "42"
        assert ctx.workspace_path == tmp_path
        assert ctx.branch_name == "plan/42"
        assert ctx.has_stage_completed("planning")
        assert ctx.has_stage_completed("implementation")
        assert ctx.get_stage_output("planning")["task_count"] == 3
        assert ctx.get_stage_output("implementation")["pr_number"] == 100

    def test_dry_run_mode(self, sample_issue: Issue):
        """Test context in dry run mode."""
        ctx = ExecutionContext(issue=sample_issue, dry_run=True)

        # Dry run should propagate through updates
        updated = ctx.with_updates(plan_id="42")

        assert ctx.dry_run is True
        assert updated.dry_run is True

    def test_chained_updates(self, sample_issue: Issue, tmp_path: Path):
        """Test chaining multiple with_updates calls."""
        ctx = (
            ExecutionContext(issue=sample_issue)
            .with_updates(plan_id="42")
            .with_updates(branch_name="plan/42")
            .with_updates(workspace_path=tmp_path)
        )

        assert ctx.plan_id == "42"
        assert ctx.branch_name == "plan/42"
        assert ctx.workspace_path == tmp_path
