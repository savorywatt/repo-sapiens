"""
Metrics collection for monitoring workflow performance.
Integrates with Prometheus for metrics export.
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from functools import wraps
from typing import Any, Callable
import time
import structlog

log = structlog.get_logger(__name__)

# Define workflow metrics
workflow_executions = Counter(
    "automation_workflow_executions_total",
    "Total workflow executions",
    ["stage", "status"],
)

workflow_duration = Histogram(
    "automation_workflow_duration_seconds",
    "Workflow execution duration",
    ["stage"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

active_workflows = Gauge(
    "automation_active_workflows", "Number of currently active workflows"
)

# API call metrics
api_calls = Counter(
    "automation_api_calls_total", "Total API calls", ["provider", "method", "status"]
)

api_call_duration = Histogram(
    "automation_api_call_duration_seconds",
    "API call duration",
    ["provider", "method"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
)

# Task metrics
task_executions = Counter(
    "automation_task_executions_total",
    "Total task executions",
    ["task_type", "status"],
)

task_duration = Histogram(
    "automation_task_duration_seconds",
    "Task execution duration",
    ["task_type"],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
)

# Error metrics
errors_total = Counter(
    "automation_errors_total", "Total errors", ["error_type", "stage"]
)

recovery_attempts = Counter(
    "automation_recovery_attempts_total",
    "Recovery attempts",
    ["recovery_type", "success"],
)

# Cache metrics
cache_hits = Counter("automation_cache_hits_total", "Cache hits", ["cache_name"])

cache_misses = Counter("automation_cache_misses_total", "Cache misses", ["cache_name"])

# Cost metrics
estimated_cost = Gauge(
    "automation_estimated_cost_dollars", "Estimated cost in dollars", ["component"]
)

token_usage = Counter(
    "automation_token_usage_total", "Total tokens used", ["model", "operation"]
)

# System info
system_info = Info("automation_system", "Automation system information")


class MetricsCollector:
    """Collect and export metrics."""

    @staticmethod
    def record_workflow_execution(stage: str, status: str) -> None:
        """Record workflow execution."""
        workflow_executions.labels(stage=stage, status=status).inc()
        log.debug("metric_recorded", metric="workflow_execution", stage=stage, status=status)

    @staticmethod
    def record_api_call(provider: str, method: str, status: str) -> None:
        """Record API call."""
        api_calls.labels(provider=provider, method=method, status=status).inc()

    @staticmethod
    def record_task_execution(task_type: str, status: str) -> None:
        """Record task execution."""
        task_executions.labels(task_type=task_type, status=status).inc()

    @staticmethod
    def record_error(error_type: str, stage: str) -> None:
        """Record error occurrence."""
        errors_total.labels(error_type=error_type, stage=stage).inc()
        log.warning("error_metric_recorded", error_type=error_type, stage=stage)

    @staticmethod
    def record_recovery_attempt(recovery_type: str, success: bool) -> None:
        """Record recovery attempt."""
        recovery_attempts.labels(
            recovery_type=recovery_type, success=str(success)
        ).inc()

    @staticmethod
    def update_active_workflows(count: int) -> None:
        """Update active workflow count."""
        active_workflows.set(count)

    @staticmethod
    def record_cache_hit(cache_name: str) -> None:
        """Record cache hit."""
        cache_hits.labels(cache_name=cache_name).inc()

    @staticmethod
    def record_cache_miss(cache_name: str) -> None:
        """Record cache miss."""
        cache_misses.labels(cache_name=cache_name).inc()

    @staticmethod
    def update_estimated_cost(component: str, cost: float) -> None:
        """Update estimated cost."""
        estimated_cost.labels(component=component).set(cost)

    @staticmethod
    def record_token_usage(model: str, operation: str, tokens: int) -> None:
        """Record token usage."""
        token_usage.labels(model=model, operation=operation).inc(tokens)

    @staticmethod
    def set_system_info(**kwargs: Any) -> None:
        """Set system information."""
        system_info.info(kwargs)

    @staticmethod
    def get_metrics() -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest()


def measure_duration(stage: str) -> Callable[[Callable], Callable]:
    """Decorator to measure operation duration."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failed"
                raise
            finally:
                duration = time.time() - start
                workflow_duration.labels(stage=stage).observe(duration)
                MetricsCollector.record_workflow_execution(stage, status)
                log.info(
                    "operation_measured",
                    stage=stage,
                    duration=duration,
                    status=status,
                )

        return wrapper

    return decorator


def measure_api_call(provider: str, method: str) -> Callable[[Callable], Callable]:
    """Decorator to measure API call duration."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start
                api_call_duration.labels(provider=provider, method=method).observe(
                    duration
                )
                MetricsCollector.record_api_call(provider, method, status)

        return wrapper

    return decorator


def measure_task(task_type: str) -> Callable[[Callable], Callable]:
    """Decorator to measure task execution."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failed"
                raise
            finally:
                duration = time.time() - start
                task_duration.labels(task_type=task_type).observe(duration)
                MetricsCollector.record_task_execution(task_type, status)

        return wrapper

    return decorator
