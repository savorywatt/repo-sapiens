"""Monitoring and observability for the automation system.

This package provides metrics collection, analytics dashboards, and performance
monitoring for the entire automation pipeline.

Key Components:
    - MetricsCollector: Central metrics collection and aggregation
    - Dashboard: REST API and HTML dashboard for visualization
    - Prometheus Integration: Direct Prometheus metrics export

Metrics Tracked:
    - Workflow execution duration and success rates
    - Task execution times and failure rates
    - API call latencies and error rates
    - Resource utilization

Features:
    - Real-time metrics collection
    - Historical data aggregation
    - Performance analytics and reporting
    - Alerts and anomaly detection

Example:
    >>> from automation.monitoring import MetricsCollector
    >>> metrics = MetricsCollector()
    >>> metrics.record_task_duration("planning", 5.2)
    >>> stats = metrics.get_stats("planning")
"""
