"""Tests for repo_sapiens/monitoring/metrics.py."""

import pytest

# Skip if prometheus_client not available
pytest.importorskip("prometheus_client")

from repo_sapiens.monitoring.metrics import (
    MetricsCollector,
    measure_api_call,
    measure_duration,
    measure_task,
)


class TestMetricsCollector:
    """Tests for MetricsCollector static methods."""

    def test_record_workflow_execution(self):
        """Should record workflow execution metric."""
        # Should not raise
        MetricsCollector.record_workflow_execution(stage="planning", status="success")
        MetricsCollector.record_workflow_execution(stage="implementation", status="failed")

    def test_record_api_call(self):
        """Should record API call metric."""
        MetricsCollector.record_api_call(provider="gitea", method="get_issues", status="success")
        MetricsCollector.record_api_call(provider="github", method="create_pr", status="error")

    def test_record_task_execution(self):
        """Should record task execution metric."""
        MetricsCollector.record_task_execution(task_type="feature", status="success")
        MetricsCollector.record_task_execution(task_type="bugfix", status="failed")

    def test_record_error(self):
        """Should record error metric."""
        MetricsCollector.record_error(error_type="timeout", stage="implementation")
        MetricsCollector.record_error(error_type="merge_conflict", stage="merge")

    def test_record_recovery_attempt(self):
        """Should record recovery attempt metric."""
        MetricsCollector.record_recovery_attempt(recovery_type="retry", success=True)
        MetricsCollector.record_recovery_attempt(recovery_type="rollback", success=False)

    def test_update_active_workflows(self):
        """Should update active workflow gauge."""
        MetricsCollector.update_active_workflows(5)
        MetricsCollector.update_active_workflows(0)

    def test_record_cache_hit(self):
        """Should record cache hit metric."""
        MetricsCollector.record_cache_hit(cache_name="issues")
        MetricsCollector.record_cache_hit(cache_name="files")

    def test_record_cache_miss(self):
        """Should record cache miss metric."""
        MetricsCollector.record_cache_miss(cache_name="issues")
        MetricsCollector.record_cache_miss(cache_name="files")

    def test_update_estimated_cost(self):
        """Should update estimated cost gauge."""
        MetricsCollector.update_estimated_cost(component="planning", cost=5.50)
        MetricsCollector.update_estimated_cost(component="implementation", cost=25.00)

    def test_record_token_usage(self):
        """Should record token usage metric."""
        MetricsCollector.record_token_usage(model="claude-sonnet", operation="planning", tokens=1000)
        MetricsCollector.record_token_usage(model="claude-haiku", operation="review", tokens=500)

    def test_set_system_info(self):
        """Should set system info."""
        MetricsCollector.set_system_info(version="0.3.0", environment="test")

    def test_get_metrics_returns_bytes(self):
        """Should return metrics in Prometheus format."""
        metrics = MetricsCollector.get_metrics()
        assert isinstance(metrics, bytes)
        # Should contain some metric names
        metrics_str = metrics.decode("utf-8")
        assert "automation_" in metrics_str or "# HELP" in metrics_str


class TestMeasureDurationDecorator:
    """Tests for measure_duration decorator."""

    @pytest.mark.asyncio
    async def test_measure_duration_success(self):
        """Should measure duration of successful async function."""

        @measure_duration("test_stage")
        async def successful_operation():
            return "success"

        result = await successful_operation()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_measure_duration_failure(self):
        """Should measure duration and record failure on exception."""

        @measure_duration("test_stage")
        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_operation()


class TestMeasureApiCallDecorator:
    """Tests for measure_api_call decorator."""

    @pytest.mark.asyncio
    async def test_measure_api_call_success(self):
        """Should measure API call duration on success."""

        @measure_api_call("gitea", "get_issues")
        async def api_call():
            return {"issues": []}

        result = await api_call()
        assert result == {"issues": []}

    @pytest.mark.asyncio
    async def test_measure_api_call_error(self):
        """Should measure API call and record error on exception."""

        @measure_api_call("github", "create_pr")
        async def failing_api_call():
            raise ConnectionError("Network error")

        with pytest.raises(ConnectionError):
            await failing_api_call()


class TestMeasureTaskDecorator:
    """Tests for measure_task decorator."""

    @pytest.mark.asyncio
    async def test_measure_task_success(self):
        """Should measure task execution on success."""

        @measure_task("feature_implementation")
        async def task_execution():
            return {"completed": True}

        result = await task_execution()
        assert result["completed"] is True

    @pytest.mark.asyncio
    async def test_measure_task_failure(self):
        """Should measure task and record failure on exception."""

        @measure_task("bugfix")
        async def failing_task():
            raise RuntimeError("Task failed")

        with pytest.raises(RuntimeError):
            await failing_task()
