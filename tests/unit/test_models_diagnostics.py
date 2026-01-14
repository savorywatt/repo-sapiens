"""Unit tests for repo_sapiens.models.diagnostics module."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from repo_sapiens.models.diagnostics import DiagnosticReport, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creating ValidationResult with required fields only."""
        result = ValidationResult(
            name="test_connection",
            category="config",
            success=True,
            message="Connection successful",
            duration_ms=150.5,
        )

        assert result.name == "test_connection"
        assert result.category == "config"
        assert result.success is True
        assert result.message == "Connection successful"
        assert result.duration_ms == 150.5
        assert result.details is None

    def test_creation_with_details(self) -> None:
        """Test creating ValidationResult with optional details."""
        details = {"issues_found": 42, "status": "active"}
        result = ValidationResult(
            name="list_issues",
            category="read",
            success=True,
            message="Found 42 issues",
            duration_ms=234.7,
            details=details,
        )

        assert result.details == details
        assert result.details["issues_found"] == 42

    def test_to_dict_without_details(self) -> None:
        """Test to_dict() excludes details when None."""
        result = ValidationResult(
            name="test_auth",
            category="credentials",
            success=False,
            message="Authentication failed",
            duration_ms=50.123,
        )

        data = result.to_dict()

        assert data == {
            "name": "test_auth",
            "category": "credentials",
            "success": False,
            "message": "Authentication failed",
            "duration_ms": 50.12,  # Rounded to 2 decimal places
        }
        assert "details" not in data

    def test_to_dict_with_details(self) -> None:
        """Test to_dict() includes details when present."""
        result = ValidationResult(
            name="create_branch",
            category="write",
            success=True,
            message="Branch created",
            duration_ms=1234.567,
            details={"branch_name": "test-branch"},
        )

        data = result.to_dict()

        assert data["details"] == {"branch_name": "test-branch"}
        assert data["duration_ms"] == 1234.57  # Rounded

    def test_to_dict_duration_rounding(self) -> None:
        """Test that duration_ms is rounded to 2 decimal places."""
        result = ValidationResult(
            name="test",
            category="config",
            success=True,
            message="OK",
            duration_ms=99.999,
        )

        data = result.to_dict()
        assert data["duration_ms"] == 100.0


class TestDiagnosticReport:
    """Tests for DiagnosticReport dataclass."""

    @pytest.fixture
    def sample_timestamp(self) -> datetime:
        """Return a fixed timestamp for testing."""
        return datetime(2025, 6, 15, 10, 30, 45)

    @pytest.fixture
    def sample_results(self) -> list[ValidationResult]:
        """Return a list of sample validation results."""
        return [
            ValidationResult(
                name="config_valid",
                category="config",
                success=True,
                message="Configuration is valid",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="token_valid",
                category="credentials",
                success=True,
                message="Token is valid",
                duration_ms=20.0,
            ),
            ValidationResult(
                name="list_issues",
                category="read",
                success=True,
                message="Found 5 issues",
                duration_ms=150.0,
                details={"count": 5},
            ),
            ValidationResult(
                name="create_branch",
                category="write",
                success=False,
                message="Permission denied",
                duration_ms=100.0,
            ),
        ]

    def test_creation_minimal(self, sample_timestamp: datetime) -> None:
        """Test creating DiagnosticReport with required fields only."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        assert report.timestamp == sample_timestamp
        assert report.provider_type == "github"
        assert report.repository == "owner/repo"
        assert report.results == []
        assert report.agent_type is None
        assert report.summary is None
        assert report.duration_ms == 0.0

    def test_creation_full(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test creating DiagnosticReport with all fields."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="gitea",
            repository="org/project",
            results=sample_results,
            agent_type="claude-api",
            summary="All critical tests passed.",
            duration_ms=5000.0,
        )

        assert report.agent_type == "claude-api"
        assert report.summary == "All critical tests passed."
        assert report.duration_ms == 5000.0
        assert len(report.results) == 4

    def test_passed_property(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test passed property counts successful results."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
        )

        assert report.passed == 3

    def test_failed_property(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test failed property counts unsuccessful results."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
        )

        assert report.failed == 1

    def test_total_property(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test total property returns result count."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
        )

        assert report.total == 4

    def test_total_property_empty(self, sample_timestamp: datetime) -> None:
        """Test total property with no results."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        assert report.total == 0

    def test_all_passed_true(self, sample_timestamp: datetime) -> None:
        """Test all_passed returns True when all tests pass."""
        results = [
            ValidationResult(
                name="test1",
                category="config",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="test2",
                category="read",
                success=True,
                message="OK",
                duration_ms=20.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
        )

        assert report.all_passed is True

    def test_all_passed_false(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test all_passed returns False when any test fails."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
        )

        assert report.all_passed is False

    def test_all_passed_empty(self, sample_timestamp: datetime) -> None:
        """Test all_passed returns True when no results (vacuous truth)."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        assert report.all_passed is True

    def test_results_by_category(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test results_by_category groups results correctly."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
        )

        grouped = report.results_by_category()

        assert len(grouped) == 4
        assert len(grouped["config"]) == 1
        assert len(grouped["credentials"]) == 1
        assert len(grouped["read"]) == 1
        assert len(grouped["write"]) == 1
        assert grouped["config"][0].name == "config_valid"

    def test_results_by_category_empty(self, sample_timestamp: datetime) -> None:
        """Test results_by_category with no results."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        grouped = report.results_by_category()

        assert grouped == {}

    def test_results_by_category_multiple_same_category(
        self, sample_timestamp: datetime
    ) -> None:
        """Test results_by_category with multiple results in same category."""
        results = [
            ValidationResult(
                name="test1",
                category="read",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="test2",
                category="read",
                success=True,
                message="OK",
                duration_ms=20.0,
            ),
            ValidationResult(
                name="test3",
                category="read",
                success=False,
                message="Failed",
                duration_ms=30.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
        )

        grouped = report.results_by_category()

        assert len(grouped) == 1
        assert len(grouped["read"]) == 3

    def test_to_dict(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test to_dict() serialization."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="gitea",
            repository="org/project",
            results=sample_results,
            agent_type="claude-local",
            summary="Test summary",
            duration_ms=5000.123,
        )

        data = report.to_dict()

        assert data["timestamp"] == "2025-06-15T10:30:45"
        assert data["provider_type"] == "gitea"
        assert data["repository"] == "org/project"
        assert data["agent_type"] == "claude-local"
        assert data["passed"] == 3
        assert data["failed"] == 1
        assert data["total"] == 4
        assert data["duration_ms"] == 5000.12  # Rounded
        assert data["summary"] == "Test summary"
        assert len(data["results"]) == 4
        assert data["results"][0]["name"] == "config_valid"

    def test_to_dict_none_values(self, sample_timestamp: datetime) -> None:
        """Test to_dict() includes None values for optional fields."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        data = report.to_dict()

        assert data["agent_type"] is None
        assert data["summary"] is None

    def test_to_json(
        self, sample_timestamp: datetime, sample_results: list[ValidationResult]
    ) -> None:
        """Test to_json() produces valid JSON."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=sample_results,
            duration_ms=1000.0,
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["provider_type"] == "github"
        assert parsed["total"] == 4
        assert len(parsed["results"]) == 4

    def test_to_json_indent(self, sample_timestamp: datetime) -> None:
        """Test to_json() respects indent parameter."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
        )

        json_default = report.to_json()
        json_no_indent = report.to_json(indent=0)

        # Default indent (2) should have more characters due to formatting
        assert len(json_default) > len(json_no_indent)

    def test_to_markdown_basic(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() produces expected structure."""
        results = [
            ValidationResult(
                name="config_check",
                category="config",
                success=True,
                message="Configuration valid",
                duration_ms=50.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
            duration_ms=1000.0,
        )

        md = report.to_markdown()

        assert "# Validation Report" in md
        assert "**Timestamp:**" in md
        assert "2025-06-15" in md
        assert "**Provider:** GITHUB" in md
        assert "**Repository:** owner/repo" in md
        assert "## Results: 1/1 passed" in md
        assert "### Configuration" in md
        assert "\u2713 **config_check**" in md  # Checkmark
        assert "*Total duration: 1.0s*" in md

    def test_to_markdown_with_agent(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() includes agent type when present."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="gitea",
            repository="org/project",
            agent_type="claude-api",
            duration_ms=500.0,
        )

        md = report.to_markdown()

        assert "**Agent:** claude-api" in md

    def test_to_markdown_without_agent(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() excludes agent line when not present."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            duration_ms=500.0,
        )

        md = report.to_markdown()

        assert "**Agent:**" not in md

    def test_to_markdown_failed_result(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() shows X for failed results."""
        results = [
            ValidationResult(
                name="auth_check",
                category="credentials",
                success=False,
                message="Token expired",
                duration_ms=25.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
            duration_ms=100.0,
        )

        md = report.to_markdown()

        assert "\u2717 **auth_check**" in md  # X mark
        assert "## Results: 0/1 passed" in md

    def test_to_markdown_with_summary(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() includes summary section when present."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            summary="All tests passed successfully. The system is healthy.",
            duration_ms=2000.0,
        )

        md = report.to_markdown()

        assert "## Summary" in md
        assert "All tests passed successfully" in md

    def test_to_markdown_without_summary(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() excludes summary section when not present."""
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            duration_ms=500.0,
        )

        md = report.to_markdown()

        assert "## Summary" not in md

    def test_to_markdown_category_order(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() orders categories correctly."""
        # Create results in reverse order
        results = [
            ValidationResult(
                name="agent_test",
                category="agent",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="write_test",
                category="write",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="read_test",
                category="read",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="cred_test",
                category="credentials",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="config_test",
                category="config",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
            duration_ms=100.0,
        )

        md = report.to_markdown()

        # Check order of category headings
        config_pos = md.find("### Configuration")
        cred_pos = md.find("### Credentials")
        read_pos = md.find("### Read Operations")
        write_pos = md.find("### Write Operations")
        agent_pos = md.find("### Agent Operations")

        assert config_pos < cred_pos < read_pos < write_pos < agent_pos

    def test_to_markdown_unknown_category(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() handles unknown categories gracefully."""
        results = [
            ValidationResult(
                name="custom_test",
                category="custom",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
            duration_ms=50.0,
        )

        md = report.to_markdown()

        # Unknown category should NOT appear since it's not in category_order
        assert "### Custom" not in md
        # But wait - it should be skipped entirely in the output
        assert "custom_test" not in md

    def test_to_markdown_all_categories(self, sample_timestamp: datetime) -> None:
        """Test to_markdown() renders all standard categories."""
        results = [
            ValidationResult(
                name="t1",
                category="config",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="t2",
                category="credentials",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="t3",
                category="read",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="t4",
                category="write",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
            ValidationResult(
                name="t5",
                category="agent",
                success=True,
                message="OK",
                duration_ms=10.0,
            ),
        ]
        report = DiagnosticReport(
            timestamp=sample_timestamp,
            provider_type="github",
            repository="owner/repo",
            results=results,
            duration_ms=100.0,
        )

        md = report.to_markdown()

        assert "### Configuration" in md
        assert "### Credentials" in md
        assert "### Read Operations" in md
        assert "### Write Operations" in md
        assert "### Agent Operations" in md
