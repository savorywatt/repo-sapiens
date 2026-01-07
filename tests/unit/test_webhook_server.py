"""Tests for repo_sapiens/webhook_server.py."""

import pytest

# Skip if fastapi not available
pytest.importorskip("fastapi")

from repo_sapiens.webhook_server import extract_plan_id


class TestExtractPlanId:
    """Tests for extract_plan_id function."""

    def test_extract_simple_plan_id(self):
        """Should extract plan ID from standard path."""
        assert extract_plan_id("plans/42-feature.md") == "42"

    def test_extract_plan_id_with_longer_number(self):
        """Should extract multi-digit plan ID."""
        assert extract_plan_id("plans/12345-big-feature.md") == "12345"

    def test_extract_plan_id_with_subdirectory(self):
        """Should extract plan ID from nested path."""
        assert extract_plan_id("plans/archive/99-old-plan.md") == "99"

    def test_no_plan_id_in_path(self):
        """Should return None for paths without plan ID pattern."""
        assert extract_plan_id("src/main.py") is None
        assert extract_plan_id("plans/readme.md") is None

    def test_non_plans_directory(self):
        """Should return None for non-plans directories."""
        assert extract_plan_id("docs/42-guide.md") is None

    def test_plan_id_with_complex_name(self):
        """Should extract ID regardless of feature name complexity."""
        assert extract_plan_id("plans/123-some-complex-feature-name.md") == "123"
