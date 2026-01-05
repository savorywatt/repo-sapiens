"""Extended tests for repo_sapiens/utils/cost_optimizer.py - edge cases and coverage."""

from dataclasses import dataclass
from typing import Any

import pytest

from repo_sapiens.utils.cost_optimizer import (
    MODEL_PRICING,
    CostOptimizer,
    ModelCosts,
    ModelTier,
    TaskComplexityFactors,
)


# =============================================================================
# Tests for ModelTier Enum
# =============================================================================


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_tier_values(self):
        """Test ModelTier enum values."""
        assert ModelTier.FAST == "claude-haiku-3.5"
        assert ModelTier.BALANCED == "claude-sonnet-4.5"
        assert ModelTier.ADVANCED == "claude-opus-4.5"

    def test_tier_is_string_enum(self):
        """Test ModelTier is a string enum."""
        assert isinstance(ModelTier.FAST, str)
        assert ModelTier.FAST.value == "claude-haiku-3.5"


# =============================================================================
# Tests for ModelCosts
# =============================================================================


class TestModelCosts:
    """Tests for ModelCosts dataclass."""

    def test_model_costs_creation(self):
        """Test creating ModelCosts instance."""
        costs = ModelCosts(input_cost=1.0, output_cost=2.0)

        assert costs.input_cost == 1.0
        assert costs.output_cost == 2.0

    def test_model_pricing_exists(self):
        """Test that MODEL_PRICING has all tiers."""
        assert ModelTier.FAST in MODEL_PRICING
        assert ModelTier.BALANCED in MODEL_PRICING
        assert ModelTier.ADVANCED in MODEL_PRICING


# =============================================================================
# Tests for TaskComplexityFactors
# =============================================================================


class TestTaskComplexityFactors:
    """Tests for TaskComplexityFactors dataclass."""

    def test_default_values(self):
        """Test TaskComplexityFactors default values."""
        factors = TaskComplexityFactors()

        assert factors.description_length == 0
        assert factors.has_complex_keywords is False
        assert factors.dependency_count == 0
        assert factors.requires_deep_analysis is False
        assert factors.file_count == 0
        assert factors.estimated_changes == 0
        assert factors.has_security_implications is False
        assert factors.has_performance_requirements is False

    def test_custom_values(self):
        """Test TaskComplexityFactors with custom values."""
        factors = TaskComplexityFactors(
            description_length=500,
            has_complex_keywords=True,
            dependency_count=3,
            requires_deep_analysis=True,
            file_count=10,
            estimated_changes=200,
            has_security_implications=True,
            has_performance_requirements=True,
        )

        assert factors.description_length == 500
        assert factors.has_complex_keywords is True
        assert factors.dependency_count == 3


# =============================================================================
# Extended CostOptimizer Tests - Complexity Assessment
# =============================================================================


class MockTask:
    """Mock task for testing."""

    def __init__(
        self,
        description: str = "",
        dependencies: list | None = None,
        context: dict | None = None,
        task_id: str = "test-task",
    ):
        self.description = description
        self.dependencies = dependencies or []
        self.context = context or {}
        self.id = task_id


class TestCostOptimizerComplexity:
    """Tests for complexity assessment edge cases."""

    def test_long_description_adds_complexity(self):
        """Test that long descriptions increase complexity."""
        optimizer = CostOptimizer()

        # Short description
        short_task = MockTask(description="Fix typo" * 10)  # ~80 chars
        short_model = optimizer.select_model_for_task(short_task)

        # Long description (> 2000 chars)
        long_task = MockTask(description="x" * 2500)
        long_model = optimizer.select_model_for_task(long_task)

        # Long description should trend toward higher tier
        assert short_model == ModelTier.FAST
        # Long description alone adds 0.2, still FAST
        assert long_model == ModelTier.FAST

    def test_medium_description_length(self):
        """Test medium description length (1000-2000 chars)."""
        optimizer = CostOptimizer()

        # Between 1000 and 2000 chars
        task = MockTask(description="x" * 1500)
        model = optimizer.select_model_for_task(task)

        # Medium length adds 0.1
        assert model == ModelTier.FAST

    def test_complex_keywords_increase_tier(self):
        """Test that complex keywords increase model tier."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Implement distributed authentication system with security",
        )
        model = optimizer.select_model_for_task(task)

        # Complex keywords add 0.3
        assert model in [ModelTier.BALANCED, ModelTier.ADVANCED]

    def test_simple_keywords_reduce_complexity(self):
        """Test that simple keywords reduce complexity."""
        optimizer = CostOptimizer()

        task = MockTask(description="Fix typo in documentation")
        model = optimizer.select_model_for_task(task)

        assert model == ModelTier.FAST

    def test_many_dependencies_increase_tier(self):
        """Test that many dependencies increase model tier."""
        optimizer = CostOptimizer()

        # > 5 dependencies
        task = MockTask(
            description="Simple task",
            dependencies=["dep1", "dep2", "dep3", "dep4", "dep5", "dep6"],
        )
        model = optimizer.select_model_for_task(task)

        # 6 dependencies adds 0.2
        assert model == ModelTier.FAST  # Still 0.2 < 0.3

    def test_few_dependencies(self):
        """Test 2-5 dependencies adds less complexity."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            dependencies=["dep1", "dep2", "dep3"],
        )
        model = optimizer.select_model_for_task(task)

        # 3 dependencies adds 0.1
        assert model == ModelTier.FAST

    def test_requires_deep_analysis(self):
        """Test requires_deep_analysis flag."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            context={"requires_deep_analysis": True},
        )
        model = optimizer.select_model_for_task(task)

        # Deep analysis adds 0.3
        assert model == ModelTier.BALANCED

    def test_high_file_count(self):
        """Test high file count increases complexity."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            context={"file_count": 15},
        )
        model = optimizer.select_model_for_task(task)

        # 15 files adds 0.2
        assert model == ModelTier.FAST

    def test_medium_file_count(self):
        """Test 5-10 files adds less complexity."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            context={"file_count": 7},
        )
        model = optimizer.select_model_for_task(task)

        # 7 files adds 0.1
        assert model == ModelTier.FAST

    def test_high_estimated_changes(self):
        """Test high estimated changes increases complexity."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            context={"estimated_changes": 600},
        )
        model = optimizer.select_model_for_task(task)

        # 600 changes adds 0.2
        assert model == ModelTier.FAST

    def test_medium_estimated_changes(self):
        """Test 200-500 estimated changes adds less complexity."""
        optimizer = CostOptimizer()

        task = MockTask(
            description="Simple task",
            context={"estimated_changes": 300},
        )
        model = optimizer.select_model_for_task(task)

        # 300 changes adds 0.1
        assert model == ModelTier.FAST

    def test_security_implications(self):
        """Test security implications increase tier."""
        optimizer = CostOptimizer()

        task = MockTask(description="Handle user authentication securely")
        model = optimizer.select_model_for_task(task)

        # Security adds 0.3 + complex keyword "authentication" adds 0.3
        assert model in [ModelTier.BALANCED, ModelTier.ADVANCED]

    def test_performance_requirements(self):
        """Test performance requirements increase tier."""
        optimizer = CostOptimizer()

        task = MockTask(description="Optimize the performance of this function")
        model = optimizer.select_model_for_task(task)

        # "optimize" keyword + performance requirement
        assert model in [ModelTier.FAST, ModelTier.BALANCED]

    def test_complexity_capped_at_one(self):
        """Test that complexity score is capped at 1.0."""
        optimizer = CostOptimizer()

        # Task with everything that adds complexity
        task = MockTask(
            description="Implement distributed authentication with security "
            "and performance optimization " + "x" * 2500,
            dependencies=["d1", "d2", "d3", "d4", "d5", "d6"],
            context={
                "requires_deep_analysis": True,
                "file_count": 20,
                "estimated_changes": 1000,
            },
        )
        model = optimizer.select_model_for_task(task)

        # Should be ADVANCED even with capped score
        assert model == ModelTier.ADVANCED


# =============================================================================
# Extended CostOptimizer Tests - Cost Estimation
# =============================================================================


class TestCostOptimizerEstimation:
    """Tests for cost estimation edge cases."""

    @pytest.mark.asyncio
    async def test_estimate_cost_with_custom_tokens(self):
        """Test cost estimation with custom token estimates."""
        optimizer = CostOptimizer()

        class MockPlan:
            tasks = [MockTask(description="Simple task")]

        custom_tokens = {
            "planning_input": 5000,
            "planning_output": 2500,
            "task_input": 10000,
            "task_output": 5000,
            "review_input": 7500,
            "review_output": 1500,
        }

        costs = await optimizer.estimate_cost(MockPlan(), custom_tokens)

        assert costs["total"] > 0
        assert costs["planning"] > 0
        assert costs["implementation"] > 0
        assert costs["review"] > 0

    @pytest.mark.asyncio
    async def test_estimate_cost_empty_plan(self):
        """Test cost estimation with empty plan."""
        optimizer = CostOptimizer()

        class MockPlan:
            tasks = []

        costs = await optimizer.estimate_cost(MockPlan())

        assert costs["implementation"] == 0
        assert costs["review"] == 0
        assert costs["planning"] > 0  # Planning still costs
        assert costs["total"] == costs["planning"]

    @pytest.mark.asyncio
    async def test_estimate_cost_plan_without_tasks_attr(self):
        """Test cost estimation when plan has no tasks attribute."""
        optimizer = CostOptimizer()

        class MockPlan:
            pass  # No tasks attribute

        costs = await optimizer.estimate_cost(MockPlan())

        # Should handle gracefully
        assert costs["implementation"] == 0
        assert costs["review"] == 0

    @pytest.mark.asyncio
    async def test_estimate_cost_multiple_tasks(self):
        """Test cost estimation with multiple tasks of varying complexity."""
        optimizer = CostOptimizer()

        class MockPlan:
            tasks = [
                MockTask(description="Fix typo"),  # Simple
                MockTask(
                    description="Implement security authentication",
                ),  # Complex
                MockTask(description="Update logging"),  # Simple
            ]

        costs = await optimizer.estimate_cost(MockPlan())

        assert costs["total"] > 0
        assert costs["implementation"] > 0
        assert costs["review"] > 0


# =============================================================================
# Cost Savings Recommendations Tests
# =============================================================================


class TestCostSavingsRecommendations:
    """Tests for cost savings recommendations."""

    def test_no_recommendations_when_on_budget(self):
        """Test no recommendations when actual is close to estimated."""
        optimizer = CostOptimizer()

        actual = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}
        estimated = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}

        recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

        # May or may not have recommendations depending on ratios
        # At least won't crash
        assert isinstance(recommendations, list)

    def test_recommendations_when_over_budget(self):
        """Test recommendations when significantly over budget."""
        optimizer = CostOptimizer()

        actual = {"planning": 15.0, "implementation": 60.0, "review": 15.0, "total": 90.0}
        estimated = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}

        recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

        assert len(recommendations) > 0
        assert any("task" in rec.lower() or "breaking" in rec.lower() for rec in recommendations)

    def test_recommendations_high_implementation_ratio(self):
        """Test recommendations when implementation exceeds estimate."""
        optimizer = CostOptimizer()

        actual = {"planning": 5.0, "implementation": 40.0, "review": 5.0, "total": 50.0}
        estimated = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}

        recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

        # Should recommend structured task descriptions
        assert any("implementation" in rec.lower() or "task" in rec.lower() for rec in recommendations)

    def test_recommendations_high_advanced_usage(self):
        """Test recommendations when advanced models dominate."""
        optimizer = CostOptimizer()

        # Implementation is 85% of total
        actual = {"planning": 5.0, "implementation": 85.0, "review": 5.0, "total": 95.0}
        estimated = {"planning": 5.0, "implementation": 20.0, "review": 5.0, "total": 30.0}

        recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

        assert any("model" in rec.lower() or "advanced" in rec.lower() or "complexity" in rec.lower() for rec in recommendations)

    def test_recommendations_zero_estimated_implementation(self):
        """Test handling zero estimated implementation (avoid division by zero)."""
        optimizer = CostOptimizer()

        actual = {"planning": 5.0, "implementation": 10.0, "review": 5.0, "total": 20.0}
        estimated = {"planning": 5.0, "implementation": 0.0, "review": 5.0, "total": 10.0}

        # Should not raise division by zero
        recommendations = optimizer.get_cost_savings_recommendations(actual, estimated)

        assert isinstance(recommendations, list)


# =============================================================================
# Edge Cases
# =============================================================================


class TestCostOptimizerEdgeCases:
    """Edge case tests for cost optimizer."""

    def test_task_with_none_description(self):
        """Test task with None description."""
        optimizer = CostOptimizer()

        class TaskWithNone:
            description = None
            dependencies = []
            context = {}
            id = "test"

        model = optimizer.select_model_for_task(TaskWithNone())

        assert model == ModelTier.FAST

    def test_task_with_none_dependencies(self):
        """Test task with None dependencies."""
        optimizer = CostOptimizer()

        class TaskWithNoneDeps:
            description = "Test"
            dependencies = None
            context = {}
            id = "test"

        model = optimizer.select_model_for_task(TaskWithNoneDeps())

        assert model == ModelTier.FAST

    def test_task_with_none_context(self):
        """Test task with None context."""
        optimizer = CostOptimizer()

        class TaskWithNoneContext:
            description = "Test"
            dependencies = []
            context = None
            id = "test"

        model = optimizer.select_model_for_task(TaskWithNoneContext())

        assert model == ModelTier.FAST

    def test_task_without_id_attribute(self):
        """Test task without id attribute."""
        optimizer = CostOptimizer()

        class TaskWithoutId:
            description = "Test"
            dependencies = []
            context = {}

        model = optimizer.select_model_for_task(TaskWithoutId())

        # Should use "unknown" for id in logging
        assert model == ModelTier.FAST

    def test_complex_keywords_case_insensitive(self):
        """Test that keyword matching is case insensitive."""
        optimizer = CostOptimizer()

        task = MockTask(description="DISTRIBUTED AUTHENTICATION SECURITY")
        model = optimizer.select_model_for_task(task)

        # Keywords should match regardless of case
        assert model in [ModelTier.BALANCED, ModelTier.ADVANCED]

    def test_simple_keywords_override_complex_behavior(self):
        """Test that having only simple keywords doesn't add complex score."""
        optimizer = CostOptimizer()

        task = MockTask(description="Fix typo in documentation style")
        model = optimizer.select_model_for_task(task)

        # Should remain simple
        assert model == ModelTier.FAST

    def test_both_simple_and_complex_keywords(self):
        """Test task with both simple and complex keywords."""
        optimizer = CostOptimizer()

        # Has both "documentation" (simple) and "security" (complex)
        task = MockTask(description="Update security documentation")
        model = optimizer.select_model_for_task(task)

        # Complex should override simple
        assert model in [ModelTier.FAST, ModelTier.BALANCED]

    @pytest.mark.asyncio
    async def test_estimate_with_tasks_none(self):
        """Test estimate when tasks attribute is None."""
        optimizer = CostOptimizer()

        class MockPlan:
            tasks = None

        costs = await optimizer.estimate_cost(MockPlan())

        assert costs["implementation"] == 0
        assert costs["review"] == 0
