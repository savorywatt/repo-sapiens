"""
Analytics dashboard for monitoring automation system.
Provides REST API and HTML dashboard for metrics visualization.
"""

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from typing import Any, Dict, List
from datetime import datetime, timedelta
import structlog
from automation.monitoring.metrics import MetricsCollector

log = structlog.get_logger(__name__)

app = FastAPI(title="Automation Analytics Dashboard", version="0.4.0")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render analytics dashboard."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Automation Analytics</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 3px solid #007bff;
                padding-bottom: 10px;
            }
            .metric-card {
                background: #f8f9fa;
                padding: 20px;
                margin: 15px 0;
                border-radius: 6px;
                border-left: 4px solid #007bff;
            }
            .metric-title {
                font-size: 14px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .metric-value {
                font-size: 32px;
                font-weight: bold;
                color: #333;
                margin-top: 5px;
            }
            .chart {
                margin: 20px 0;
                min-height: 400px;
            }
            .status-badge {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            .status-success {
                background: #d4edda;
                color: #155724;
            }
            .status-warning {
                background: #fff3cd;
                color: #856404;
            }
            .status-error {
                background: #f8d7da;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Automation System Analytics</h1>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                <div class="metric-card">
                    <div class="metric-title">Active Workflows</div>
                    <div class="metric-value" id="active-workflows">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Success Rate</div>
                    <div class="metric-value" id="success-rate">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Avg Duration</div>
                    <div class="metric-value" id="avg-duration">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Cache Hit Rate</div>
                    <div class="metric-value" id="cache-hit-rate">-</div>
                </div>
            </div>

            <div class="chart" id="workflow-timeline"></div>
            <div class="chart" id="success-rate-chart"></div>
            <div class="chart" id="duration-distribution"></div>
            <div class="chart" id="api-calls-chart"></div>
        </div>

        <script>
            // Fetch and update metrics
            async function updateMetrics() {
                try {
                    const response = await fetch('/api/metrics/summary');
                    const data = await response.json();

                    document.getElementById('active-workflows').textContent = data.active_workflows || 0;
                    document.getElementById('success-rate').textContent =
                        (data.success_rate * 100).toFixed(1) + '%';
                    document.getElementById('avg-duration').textContent =
                        data.avg_duration.toFixed(1) + 's';
                    document.getElementById('cache-hit-rate').textContent =
                        (data.cache_hit_rate * 100).toFixed(1) + '%';
                } catch (error) {
                    console.error('Failed to fetch metrics:', error);
                }
            }

            // Update charts
            async function updateCharts() {
                try {
                    const response = await fetch('/api/metrics/workflows');
                    const data = await response.json();

                    // Workflow timeline
                    if (data.timeline && data.timeline.length > 0) {
                        const timelineData = [{
                            x: data.timeline.map(d => d.timestamp),
                            y: data.timeline.map(d => d.count),
                            type: 'scatter',
                            mode: 'lines+markers',
                            name: 'Workflows'
                        }];

                        const timelineLayout = {
                            title: 'Workflow Execution Timeline',
                            xaxis: { title: 'Time' },
                            yaxis: { title: 'Count' }
                        };

                        Plotly.newPlot('workflow-timeline', timelineData, timelineLayout);
                    }

                    // Success rate by stage
                    if (data.by_stage) {
                        const stages = Object.keys(data.by_stage);
                        const successData = stages.map(s => data.by_stage[s].success || 0);
                        const failData = stages.map(s => data.by_stage[s].failed || 0);

                        const successRateData = [
                            {
                                x: stages,
                                y: successData,
                                name: 'Success',
                                type: 'bar',
                                marker: { color: '#28a745' }
                            },
                            {
                                x: stages,
                                y: failData,
                                name: 'Failed',
                                type: 'bar',
                                marker: { color: '#dc3545' }
                            }
                        ];

                        const successRateLayout = {
                            title: 'Success/Failure by Stage',
                            barmode: 'stack',
                            xaxis: { title: 'Stage' },
                            yaxis: { title: 'Count' }
                        };

                        Plotly.newPlot('success-rate-chart', successRateData, successRateLayout);
                    }
                } catch (error) {
                    console.error('Failed to update charts:', error);
                }
            }

            // Initial load and periodic refresh
            updateMetrics();
            updateCharts();
            setInterval(updateMetrics, 10000);  // Update every 10 seconds
            setInterval(updateCharts, 30000);   // Update charts every 30 seconds
        </script>
    </body>
    </html>
    """


@app.get("/api/metrics/summary")
async def metrics_summary() -> Dict[str, Any]:
    """Get summary metrics."""
    # In a real implementation, would fetch from Prometheus or internal state
    return {
        "active_workflows": 3,
        "success_rate": 0.85,
        "avg_duration": 45.2,
        "cache_hit_rate": 0.72,
        "total_workflows": 150,
        "total_tasks": 450,
    }


@app.get("/api/metrics/workflows")
async def workflow_metrics() -> Dict[str, Any]:
    """Get detailed workflow metrics."""
    # Mock data - in production would query actual metrics
    now = datetime.now()

    timeline = [
        {
            "timestamp": (now - timedelta(hours=i)).isoformat(),
            "count": 5 + (i % 3),
        }
        for i in range(24, 0, -1)
    ]

    by_stage = {
        "planning": {"success": 45, "failed": 3},
        "implementation": {"success": 42, "failed": 5},
        "code_review": {"success": 40, "failed": 2},
        "merge": {"success": 38, "failed": 1},
    }

    by_status = {
        "completed": 38,
        "in_progress": 3,
        "failed": 6,
        "pending": 2,
    }

    average_duration = {
        "planning": 120.5,
        "implementation": 450.2,
        "code_review": 180.3,
        "merge": 60.1,
    }

    return {
        "timeline": timeline,
        "by_stage": by_stage,
        "by_status": by_status,
        "average_duration": average_duration,
    }


@app.get("/api/metrics/tasks")
async def task_metrics() -> Dict[str, Any]:
    """Get task execution metrics."""
    return {
        "total_tasks": 450,
        "completed": 410,
        "failed": 25,
        "in_progress": 15,
        "average_duration": 380.5,
        "by_type": {
            "feature": {"count": 200, "avg_duration": 420.0},
            "bugfix": {"count": 150, "avg_duration": 280.0},
            "refactor": {"count": 100, "avg_duration": 450.0},
        },
    }


@app.get("/api/metrics/performance")
async def performance_metrics() -> Dict[str, Any]:
    """Get performance metrics."""
    return {
        "cache_stats": {
            "hits": 5420,
            "misses": 1580,
            "hit_rate": 0.774,
            "total_requests": 7000,
        },
        "api_calls": {
            "total": 2500,
            "average_duration": 1.2,
            "by_provider": {
                "gitea": {"count": 1500, "avg_duration": 0.8},
                "claude": {"count": 1000, "avg_duration": 2.1},
            },
        },
        "parallel_execution": {
            "max_workers": 3,
            "average_concurrency": 2.3,
            "total_task_time": 15000,
            "wall_clock_time": 6500,
            "efficiency": 0.769,
        },
    }


@app.get("/api/metrics/costs")
async def cost_metrics() -> Dict[str, Any]:
    """Get cost metrics."""
    return {
        "total_estimated_cost": 45.50,
        "by_component": {
            "planning": 5.20,
            "implementation": 35.10,
            "review": 5.20,
        },
        "by_model": {
            "claude-haiku-3.5": 2.50,
            "claude-sonnet-4.5": 28.00,
            "claude-opus-4.5": 15.00,
        },
        "token_usage": {
            "total_tokens": 1500000,
            "by_operation": {
                "planning": 200000,
                "implementation": 1000000,
                "review": 300000,
            },
        },
    }


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint."""
    metrics = MetricsCollector.get_metrics()
    return Response(content=metrics, media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
