"""Diagnostic models for validation and health checks.

This module defines data models for representing validation results
and diagnostic reports from the health-check --full command.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ValidationResult:
    """Result of a single validation test.

    Attributes:
        name: Short identifier for the test (e.g., "list_issues", "create_branch")
        category: Test category ("config", "credentials", "read", "write", "agent")
        success: Whether the test passed
        message: Human-readable result message
        duration_ms: Test duration in milliseconds
        details: Optional additional details (e.g., count of issues found)
    """

    name: str
    category: str
    success: bool
    message: str
    duration_ms: float
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "category": self.category,
            "success": self.success,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class DiagnosticReport:
    """Complete diagnostic report from validation run.

    Attributes:
        timestamp: When the validation was run
        provider_type: Git provider type ("github", "gitlab", "gitea")
        repository: Repository identifier (owner/repo)
        agent_type: Agent provider type if configured
        results: List of individual validation results
        summary: LLM-generated summary if available
        duration_ms: Total validation duration in milliseconds
    """

    timestamp: datetime
    provider_type: str
    repository: str
    results: list[ValidationResult] = field(default_factory=list)
    agent_type: str | None = None
    summary: str | None = None
    duration_ms: float = 0.0

    @property
    def passed(self) -> int:
        """Count of passed tests."""
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        """Count of failed tests."""
        return sum(1 for r in self.results if not r.success)

    @property
    def total(self) -> int:
        """Total number of tests."""
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        """Whether all tests passed."""
        return self.failed == 0

    def results_by_category(self) -> dict[str, list[ValidationResult]]:
        """Group results by category."""
        grouped: dict[str, list[ValidationResult]] = {}
        for result in self.results:
            if result.category not in grouped:
                grouped[result.category] = []
            grouped[result.category].append(result)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "provider_type": self.provider_type,
            "repository": self.repository,
            "agent_type": self.agent_type,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "duration_ms": round(self.duration_ms, 2),
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Convert to markdown format for display or reporting."""
        lines = [
            "# Validation Report",
            "",
            f"**Timestamp:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Provider:** {self.provider_type.upper()}",
            f"**Repository:** {self.repository}",
        ]

        if self.agent_type:
            lines.append(f"**Agent:** {self.agent_type}")

        lines.extend(
            [
                "",
                f"## Results: {self.passed}/{self.total} passed",
                "",
            ]
        )

        # Group by category
        category_order = ["config", "credentials", "read", "write", "agent"]
        category_names = {
            "config": "Configuration",
            "credentials": "Credentials",
            "read": "Read Operations",
            "write": "Write Operations",
            "agent": "Agent Operations",
        }

        grouped = self.results_by_category()

        for category in category_order:
            if category not in grouped:
                continue

            lines.append(f"### {category_names.get(category, category.title())}")
            lines.append("")

            for result in grouped[category]:
                icon = "\u2713" if result.success else "\u2717"
                lines.append(f"- {icon} **{result.name}**: {result.message} ({result.duration_ms:.0f}ms)")

            lines.append("")

        if self.summary:
            lines.extend(
                [
                    "## Summary",
                    "",
                    self.summary,
                    "",
                ]
            )

        lines.append(f"*Total duration: {self.duration_ms / 1000:.1f}s*")

        return "\n".join(lines)
