"""
Tests for cost optimization system.
"""

import pytest

from repo_sapiens.utils.cost_optimizer import CostOptimizer, ModelTier


def test_select_model_simple_task(mock_task):
    """Test model selection for simple task."""
    optimizer = CostOptimizer()

    task = mock_task(
        description="Fix typo in documentation",
        context={"file_count": 1},
    )

    model = optimizer.select_model_for_task(task)

    assert model == ModelTier.FAST


def test_select_model_complex_task(mock_task):
    """Test model selection for complex task."""
    optimizer = CostOptimizer()

    task = mock_task(
        description="Implement distributed authentication system with security hardening",
        context={
            "file_count": 15,
            "estimated_changes": 800,
            "requires_deep_analysis": True,
        },
    )

    model = optimizer.select_model_for_task(task)

    assert model == ModelTier.ADVANCED


def test_select_model_balanced_task(mock_task):
    """Test model selection for medium complexity task."""
    optimizer = CostOptimizer()

    task = mock_task(
        description="Add user profile page with basic CRUD operations",
        dependencies=["task-1", "task-2"],
        context={"file_count": 5, "estimated_changes": 200},
    )

    model = optimizer.select_model_for_task(task)

    assert model in [ModelTier.FAST, ModelTier.BALANCED]


@pytest.mark.asyncio
async def test_estimate_cost(mock_task):
    """Test cost estimation for a plan."""
    optimizer = CostOptimizer()

    class MockPlan:
        def __init__(self, tasks):
            self.tasks = tasks

    # Create plan with mock tasks
    tasks = [
        mock_task(description="Implement user model", context={"file_count": 2}),
        mock_task(description="Add authentication endpoints", context={"file_count": 3}),
        mock_task(description="Write tests", context={"file_count": 2}),
    ]
    plan = MockPlan(tasks)

    costs = await optimizer.estimate_cost(plan)

    assert "planning" in costs
    assert "implementation" in costs
    assert "review" in costs
    assert "total" in costs
    assert costs["total"] > 0
    assert costs["total"] == costs["planning"] + costs["implementation"] + costs["review"]


def test_optimization_disabled(mock_task):
    """Test that optimization can be disabled."""
    optimizer = CostOptimizer(enable_optimization=False)

    task = mock_task(description="Fix typo")

    model = optimizer.select_model_for_task(task)

    # Should always return balanced when optimization disabled
    assert model == ModelTier.BALANCED


def test_cost_savings_recommendations():
    """Test generation of cost savings recommendations."""
    optimizer = CostOptimizer()

    actual = {"planning": 10.0, "implementation": 50.0, "review": 10.0, "total": 70.0}
    estimated = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}

    recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

    assert len(recommendations) > 0
    assert any("task" in rec.lower() for rec in recommendations)
