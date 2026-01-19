"""Diagnostic models for validation and health checks.

This module defines data models for representing validation results
and diagnostic reports from the health-check --full command. These models
capture the outcome of testing configuration, credentials, and provider
connectivity.

Example:
    Running a validation and processing results::

        report = DiagnosticReport(
            timestamp=datetime.now(timezone.utc),
            provider_type="github",
            repository="org/repo"
        )
        report.results.append(ValidationResult(
            name="list_issues",
            category="read",
            success=True,
            message="Found 15 open issues",
            duration_ms=234.5,
            details={"count": 15}
        ))
        print(report.to_markdown())
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ValidationResult:
    """Result of a single validation test.

    Each validation test checks one specific aspect of the system configuration
    or provider connectivity. Results are aggregated into a DiagnosticReport.

    Example:
        Creating a validation result::

            result = ValidationResult(
                name="create_branch",
                category="write",
                success=False,
                message="Permission denied: requires push access",
                duration_ms=156.2
            )
    """

    name: str
    """Short identifier for the test.

    Examples: "list_issues", "create_branch", "api_token_valid".
    Used for programmatic access and displayed in reports.
    """

    category: str
    """Test category grouping related validations.

    Standard categories:
    - "config": Configuration file validation
    - "credentials": API token and authentication tests
    - "read": Read-only API operations (list issues, get PR)
    - "write": Write API operations (create branch, post comment)
    - "agent": Agent provider connectivity and capabilities
    """

    success: bool
    """Whether the test passed.

    True indicates the tested functionality works correctly.
    False indicates a problem that may block normal operation.
    """

    message: str
    """Human-readable result description.

    For successful tests, describes what was verified (e.g., "Found 15 open issues").
    For failures, explains what went wrong and may suggest fixes.
    """

    duration_ms: float
    """Test execution duration in milliseconds.

    Useful for identifying slow API calls or network issues.
    Values over 5000ms may indicate connectivity problems.
    """

    details: dict[str, Any] | None = None
    """Optional additional details about the test result.

    May include counts, IDs, or other data useful for debugging.
    Examples: {"count": 15}, {"branch_name": "test-branch-abc123"}.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON encoding.
            The details field is omitted if None.
        """
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
    """Complete diagnostic report from a validation run.

    Aggregates all validation results from a health check, providing
    summary statistics and multiple output formats (JSON, Markdown).

    Example:
        Generating and displaying a report::

            report = await run_full_validation(config)
            if report.all_passed:
                print("All systems operational")
            else:
                print(f"{report.failed} of {report.total} tests failed")
                print(report.to_markdown())
    """

    timestamp: datetime
    """When the validation run started.

    Should be in UTC for consistency across time zones.
    """

    provider_type: str
    """Git provider type being validated.

    One of: "github", "gitlab", "gitea".
    Determines which provider-specific tests are run.
    """

    repository: str
    """Repository identifier in owner/repo format.

    The repository used for validation tests. Write tests may create
    and delete test resources in this repository.
    """

    results: list[ValidationResult] = field(default_factory=list)
    """List of individual validation results.

    Results are typically added in execution order. Use results_by_category()
    to group them for display.
    """

    agent_type: str | None = None
    """Agent provider type if configured.

    Examples: "claude-api", "openai", "ollama".
    None if no agent provider is configured or agent tests were skipped.
    """

    summary: str | None = None
    """LLM-generated summary of the validation results.

    When available, provides a natural language interpretation of the
    results, highlighting key issues and suggested fixes.
    """

    duration_ms: float = 0.0
    """Total validation run duration in milliseconds.

    Includes all individual tests plus any setup/teardown time.
    """

    @property
    def passed(self) -> int:
        """Count of tests that passed.

        Returns:
            Number of ValidationResults where success is True.
        """
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        """Count of tests that failed.

        Returns:
            Number of ValidationResults where success is False.
        """
        return sum(1 for r in self.results if not r.success)

    @property
    def total(self) -> int:
        """Total number of tests run.

        Returns:
            Length of the results list.
        """
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        """Whether all tests passed.

        Returns:
            True if no tests failed, False otherwise.
            Also returns True if no tests were run.
        """
        return self.failed == 0

    def results_by_category(self) -> dict[str, list[ValidationResult]]:
        """Group results by their category.

        Returns:
            Dictionary mapping category names to lists of results.
            Categories appear in the order their first result was added.

        Example:
            Iterating over categories::

                for category, results in report.results_by_category().items():
                    print(f"{category}: {sum(r.success for r in results)}/{len(results)}")
        """
        grouped: dict[str, list[ValidationResult]] = {}
        for result in self.results:
            if result.category not in grouped:
                grouped[result.category] = []
            grouped[result.category].append(result)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Complete dictionary representation including all results
            and computed summary statistics.
        """
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
        """Convert to JSON string.

        Args:
            indent: Number of spaces for indentation. Use 0 or None
                for compact output.

        Returns:
            JSON-formatted string representation of the report.
        """
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Convert to markdown format for display or reporting.

        Generates a structured markdown document with:
        - Header with metadata (timestamp, provider, repository)
        - Results grouped by category with pass/fail icons
        - LLM summary if available
        - Total duration

        Returns:
            Markdown-formatted string suitable for display in terminals
            or rendering in documentation.
        """
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
