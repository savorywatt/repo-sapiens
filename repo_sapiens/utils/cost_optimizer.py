"""
Cost optimization for AI model selection.
Intelligently selects models based on task complexity to minimize costs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class ModelTier(str, Enum):
    """AI model tiers by cost and capability."""

    FAST = "claude-haiku-3.5"  # Cheapest, fastest - simple tasks
    BALANCED = "claude-sonnet-4.5"  # Balanced cost/performance
    ADVANCED = "claude-opus-4.5"  # Most capable, expensive - complex tasks


@dataclass
class ModelCosts:
    """Model pricing information (per 1M tokens)."""

    input_cost: float
    output_cost: float


# Current pricing as of 2025 (example values)
MODEL_PRICING: dict[ModelTier, ModelCosts] = {
    ModelTier.FAST: ModelCosts(input_cost=0.25, output_cost=1.25),
    ModelTier.BALANCED: ModelCosts(input_cost=3.00, output_cost=15.00),
    ModelTier.ADVANCED: ModelCosts(input_cost=15.00, output_cost=75.00),
}


@dataclass
class TaskComplexityFactors:
    """Factors that contribute to task complexity."""

    description_length: int = 0
    has_complex_keywords: bool = False
    dependency_count: int = 0
    requires_deep_analysis: bool = False
    file_count: int = 0
    estimated_changes: int = 0
    has_security_implications: bool = False
    has_performance_requirements: bool = False


class CostOptimizer:
    """Optimize AI model selection based on task complexity."""

    # Keywords that indicate complex tasks
    COMPLEX_KEYWORDS = {
        "architecture",
        "security",
        "performance",
        "distributed",
        "concurrency",
        "scalability",
        "algorithm",
        "optimization",
        "cryptography",
        "authentication",
        "authorization",
    }

    SIMPLE_KEYWORDS = {
        "typo",
        "documentation",
        "comment",
        "formatting",
        "style",
        "rename",
        "logging",
    }

    def __init__(self, enable_optimization: bool = True) -> None:
        self.enable_optimization = enable_optimization
        self.model_costs = MODEL_PRICING

    def select_model_for_task(self, task: Any) -> ModelTier:
        """
        Select appropriate model tier for task.

        Args:
            task: Task object with description, dependencies, context

        Returns:
            Selected model tier
        """
        if not self.enable_optimization:
            return ModelTier.BALANCED

        complexity = self._assess_complexity(task)

        log.info("model_selection", task_id=getattr(task, "id", "unknown"), complexity=complexity)

        if complexity < 0.3:
            return ModelTier.FAST
        elif complexity < 0.7:
            return ModelTier.BALANCED
        else:
            return ModelTier.ADVANCED

    def _assess_complexity(self, task: Any) -> float:
        """
        Assess task complexity on 0-1 scale.

        Args:
            task: Task object

        Returns:
            Complexity score (0.0 = simple, 1.0 = very complex)
        """
        factors = self._extract_complexity_factors(task)
        score = 0.0

        # Description length (longer = more complex)
        if factors.description_length > 2000:
            score += 0.2
        elif factors.description_length > 1000:
            score += 0.1

        # Complex keywords
        if factors.has_complex_keywords:
            score += 0.3

        # Dependencies (more = more complex)
        if factors.dependency_count > 5:
            score += 0.2
        elif factors.dependency_count > 2:
            score += 0.1

        # Deep analysis required
        if factors.requires_deep_analysis:
            score += 0.3

        # File count (more files = more complex)
        if factors.file_count > 10:
            score += 0.2
        elif factors.file_count > 5:
            score += 0.1

        # Estimated changes
        if factors.estimated_changes > 500:
            score += 0.2
        elif factors.estimated_changes > 200:
            score += 0.1

        # Security implications
        if factors.has_security_implications:
            score += 0.3

        # Performance requirements
        if factors.has_performance_requirements:
            score += 0.2

        return min(score, 1.0)

    def _extract_complexity_factors(self, task: Any) -> TaskComplexityFactors:
        """Extract complexity factors from task."""
        description = getattr(task, "description", "") or ""
        description_lower = description.lower()

        # Check for keywords
        has_complex = any(kw in description_lower for kw in self.COMPLEX_KEYWORDS)
        has_simple = any(kw in description_lower for kw in self.SIMPLE_KEYWORDS)

        # If has simple keywords and no complex ones, reduce complexity
        if has_simple and not has_complex:
            has_complex = False

        dependencies = getattr(task, "dependencies", []) or []
        context = getattr(task, "context", {}) or {}

        return TaskComplexityFactors(
            description_length=len(description),
            has_complex_keywords=has_complex,
            dependency_count=len(dependencies),
            requires_deep_analysis=context.get("requires_deep_analysis", False),
            file_count=context.get("file_count", 0),
            estimated_changes=context.get("estimated_changes", 0),
            has_security_implications=any(kw in description_lower for kw in ["security", "auth", "crypto"]),
            has_performance_requirements=any(kw in description_lower for kw in ["performance", "optimize", "fast"]),
        )

    async def estimate_cost(self, plan: Any, estimated_tokens: dict[str, int] | None = None) -> dict[str, float]:
        """
        Estimate total cost for plan execution.

        Args:
            plan: Plan object with tasks
            estimated_tokens: Optional token estimates per stage

        Returns:
            Cost breakdown by stage
        """
        costs = {"planning": 0.0, "implementation": 0.0, "review": 0.0, "total": 0.0}

        # Default token estimates if not provided
        if estimated_tokens is None:
            estimated_tokens = {
                "planning_input": 10000,
                "planning_output": 5000,
                "task_input": 20000,
                "task_output": 10000,
                "review_input": 15000,
                "review_output": 3000,
            }

        # Planning cost (usually balanced model)
        planning_model = ModelTier.BALANCED
        planning_pricing = self.model_costs[planning_model]
        costs["planning"] = (
            estimated_tokens["planning_input"] * planning_pricing.input_cost / 1_000_000
            + estimated_tokens["planning_output"] * planning_pricing.output_cost / 1_000_000
        )

        # Implementation costs (varies by task complexity)
        tasks = getattr(plan, "tasks", []) or []
        for task in tasks:
            model = self.select_model_for_task(task)
            pricing = self.model_costs[model]
            costs["implementation"] += (
                estimated_tokens["task_input"] * pricing.input_cost / 1_000_000
                + estimated_tokens["task_output"] * pricing.output_cost / 1_000_000
            )

        # Review costs (usually fast model)
        review_model = ModelTier.FAST
        review_pricing = self.model_costs[review_model]
        costs["review"] = len(tasks) * (
            estimated_tokens["review_input"] * review_pricing.input_cost / 1_000_000
            + estimated_tokens["review_output"] * review_pricing.output_cost / 1_000_000
        )

        costs["total"] = costs["planning"] + costs["implementation"] + costs["review"]

        log.info(
            "cost_estimated",
            total=costs["total"],
            planning=costs["planning"],
            implementation=costs["implementation"],
            review=costs["review"],
            task_count=len(tasks),
        )

        return costs

    def get_cost_savings_recommendations(
        self, actual_costs: dict[str, float], estimated_costs: dict[str, float]
    ) -> list[str]:
        """
        Generate cost savings recommendations.

        Args:
            actual_costs: Actual costs incurred
            estimated_costs: Originally estimated costs

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check if we're over budget
        if actual_costs["total"] > estimated_costs["total"] * 1.2:
            recommendations.append("Consider breaking down complex tasks into smaller subtasks")
            recommendations.append("Review task descriptions for clarity")

        # Check implementation costs
        impl_ratio = (
            actual_costs["implementation"] / estimated_costs["implementation"]
            if estimated_costs["implementation"] > 0
            else 0
        )

        if impl_ratio > 1.5:
            recommendations.append(
                "Implementation tasks are exceeding estimates - " "consider using more structured task descriptions"
            )

        # Check if we're using expensive models too often
        if actual_costs["implementation"] > actual_costs["total"] * 0.8:
            recommendations.append("High proportion of advanced model usage - review task complexity assessments")

        return recommendations
