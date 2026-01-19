"""Tests for repo_sapiens/monitoring/dashboard.py."""

import pytest

# Skip if fastapi not available
pytest.importorskip("fastapi")
pytest.importorskip("prometheus_client")

from fastapi.testclient import TestClient

from repo_sapiens.monitoring.dashboard import app


@pytest.fixture
def client():
    """Create test client for dashboard app."""
    return TestClient(app)


class TestDashboardEndpoints:
    """Tests for dashboard API endpoints."""

    def test_dashboard_html(self, client):
        """Should return HTML dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Automation System Analytics" in response.text
        assert "<script" in response.text  # Has JavaScript

    def test_metrics_summary(self, client):
        """Should return metrics summary."""
        response = client.get("/api/metrics/summary")
        assert response.status_code == 200

        data = response.json()
        assert "active_workflows" in data
        assert "success_rate" in data
        assert "avg_duration" in data
        assert "cache_hit_rate" in data
        assert isinstance(data["success_rate"], float)

    def test_workflow_metrics(self, client):
        """Should return workflow metrics."""
        response = client.get("/api/metrics/workflows")
        assert response.status_code == 200

        data = response.json()
        assert "timeline" in data
        assert "by_stage" in data
        assert "by_status" in data
        assert "average_duration" in data
        assert isinstance(data["timeline"], list)
        assert isinstance(data["by_stage"], dict)

    def test_task_metrics(self, client):
        """Should return task metrics."""
        response = client.get("/api/metrics/tasks")
        assert response.status_code == 200

        data = response.json()
        assert "total_tasks" in data
        assert "completed" in data
        assert "failed" in data
        assert "by_type" in data
        assert isinstance(data["by_type"], dict)

    def test_performance_metrics(self, client):
        """Should return performance metrics."""
        response = client.get("/api/metrics/performance")
        assert response.status_code == 200

        data = response.json()
        assert "cache_stats" in data
        assert "api_calls" in data
        assert "parallel_execution" in data
        assert "hit_rate" in data["cache_stats"]

    def test_cost_metrics(self, client):
        """Should return cost metrics."""
        response = client.get("/api/metrics/costs")
        assert response.status_code == 200

        data = response.json()
        assert "total_estimated_cost" in data
        assert "by_component" in data
        assert "by_model" in data
        assert "token_usage" in data

    def test_health_check(self, client):
        """Should return healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_prometheus_metrics(self, client):
        """Should return Prometheus format metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
