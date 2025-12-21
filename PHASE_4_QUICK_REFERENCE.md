# Phase 4: Quick Reference Guide

## Installation & Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Verify installation
python -c "from automation.engine.parallel_executor import ParallelExecutor; print('OK')"
```

## Common Tasks

### 1. Start Monitoring Dashboard

```bash
# Start dashboard on port 8000
uvicorn automation.monitoring.dashboard:app --host 0.0.0.0 --port 8000

# Access at http://localhost:8000
```

### 2. Enable Error Recovery

```python
from automation.engine.checkpointing import CheckpointManager
from automation.engine.recovery import AdvancedRecovery

# Initialize
checkpoint = CheckpointManager()
recovery = AdvancedRecovery(state, checkpoint, git, agent)

# Create checkpoint
await checkpoint.create_checkpoint("plan-42", "implementation", checkpoint_data)

# Attempt recovery
success = await recovery.attempt_recovery("plan-42")
```

### 3. Parallel Task Execution

```python
from automation.engine.parallel_executor import ParallelExecutor, ExecutionTask

# Create executor
executor = ParallelExecutor(max_workers=3)

# Define tasks
tasks = [
    ExecutionTask(id="task-1", func=my_async_func, args=(arg1,)),
    ExecutionTask(id="task-2", func=my_async_func2, dependencies={"task-1"}),
]

# Execute
results = await executor.execute_tasks(tasks)
```

### 4. Multi-Repository Workflows

```python
from automation.engine.multi_repo import MultiRepoOrchestrator

# Initialize
orchestrator = MultiRepoOrchestrator(repo_configs)
orchestrator.register_provider("backend", backend_provider)
orchestrator.register_provider("frontend", frontend_provider)

# Execute cross-repo workflow
results = await orchestrator.execute_cross_repo_workflow(
    workflow_name="full-stack-feature",
    trigger_issue=issue,
)
```

### 5. Use Caching

```python
from automation.utils.caching import cached

# Decorator approach
@cached(ttl_seconds=600)
async def expensive_operation(param):
    # ... operation
    return result

# Manual approach
from automation.utils.caching import AsyncCache

cache = AsyncCache(ttl_seconds=300)
await cache.set("key", value)
value = await cache.get("key")
```

### 6. Cost Optimization

```python
from automation.utils.cost_optimizer import CostOptimizer

optimizer = CostOptimizer(enable_optimization=True)

# Select model for task
model = optimizer.select_model_for_task(task)

# Estimate costs
costs = await optimizer.estimate_cost(plan)
print(f"Total: ${costs['total']:.2f}")
```

### 7. Learning System

```python
from automation.learning.feedback_loop import FeedbackLoop

feedback = FeedbackLoop()

# Record execution
await feedback.record_execution(task_id, prompt, result, review)

# Get improved prompt
improved = await feedback.improve_prompt(task, base_prompt)

# Get stats
stats = await feedback.get_learning_stats()
```

## Configuration Examples

### Multi-Repository Config

```yaml
# config/repositories.yaml
repositories:
  - name: backend
    owner: myorg
    repo: backend-service
    automation:
      enabled: true

  - name: frontend
    owner: myorg
    repo: frontend-app
    automation:
      depends_on: [backend]

cross_repo_workflows:
  - name: full-stack-feature
    repositories: [backend, frontend]
    coordination: sequential
```

### Monitoring Config

```yaml
# config/automation_config.yaml
monitoring:
  enable_metrics: true
  dashboard_port: 8000
  prometheus_enabled: true

performance:
  enable_caching: true
  cache_ttl_seconds: 600
  max_workers: 3
  batch_size: 10

cost_optimization:
  enabled: true
  track_usage: true
```

## Metrics & Monitoring

### Prometheus Queries

```promql
# Success rate
rate(automation_workflow_executions_total{status="success"}[5m])
/ rate(automation_workflow_executions_total[5m])

# Average duration
rate(automation_workflow_duration_seconds_sum[5m])
/ rate(automation_workflow_duration_seconds_count[5m])

# Cache hit rate
automation_cache_hits_total
/ (automation_cache_hits_total + automation_cache_misses_total)

# Active workflows
automation_active_workflows

# API call rate
rate(automation_api_calls_total[5m])
```

### Dashboard Endpoints

```
GET  /                          # Interactive dashboard
GET  /api/metrics/summary       # Summary metrics
GET  /api/metrics/workflows     # Workflow details
GET  /api/metrics/performance   # Performance metrics
GET  /api/metrics/costs         # Cost information
GET  /api/health                # Health check
GET  /metrics                   # Prometheus metrics
```

## Testing

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific category
pytest tests/unit/test_parallel_executor.py -v

# With coverage
pytest tests/ --cov=automation --cov-report=html

# Integration tests only
pytest tests/integration/ -v
```

### Test Fixtures

```python
# Available in tests
def test_something(temp_checkpoint_dir, mock_task, mock_result):
    # temp_checkpoint_dir: Temporary checkpoint directory
    # mock_task: MockTask factory
    # mock_result: MockResult factory
    pass
```

## Common Patterns

### Checkpoint Pattern

```python
# Before risky operation
checkpoint_id = await checkpoint.create_checkpoint(
    plan_id, stage, {"state": current_state}
)

try:
    # Risky operation
    await perform_operation()
except Exception as e:
    # Recovery will use checkpoint
    await recovery.attempt_recovery(plan_id)
```

### Parallel with Dependencies

```python
tasks = [
    ExecutionTask(id="a", func=func_a),
    ExecutionTask(id="b", func=func_b, dependencies={"a"}),
    ExecutionTask(id="c", func=func_c, dependencies={"a"}),
    ExecutionTask(id="d", func=func_d, dependencies={"b", "c"}),
]
# Executes: a → (b, c in parallel) → d
```

### Batch Operations

```python
from automation.utils.batch_operations import BatchOperations

batch = BatchOperations(git, batch_size=10, max_concurrent=3)

# Batch create
issues = await batch.create_issues_batch(issues_data)

# Batch update
await batch.update_issues_batch(updates)

# Batch comments
await batch.add_comments_batch(comments)
```

## Troubleshooting

### Issue: Recovery Not Working

```python
# Check checkpoint exists
checkpoint = await checkpoint_manager.get_latest_checkpoint("plan-42")
if checkpoint:
    print(f"Found checkpoint from {checkpoint['created_at']}")

# Check recovery strategies
recovery = AdvancedRecovery(...)
# Enable debug logging
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger("DEBUG"))
```

### Issue: Parallel Tasks Deadlock

```python
# Check for circular dependencies
tasks = [...]
executor = ParallelExecutor(max_workers=3)

try:
    results = await executor.execute_tasks(tasks)
except RuntimeError as e:
    if "deadlock" in str(e):
        # Check task dependencies
        for task in tasks:
            print(f"{task.id} depends on {task.dependencies}")
```

### Issue: High Costs

```python
# Review model selection
optimizer = CostOptimizer()

for task in tasks:
    model = optimizer.select_model_for_task(task)
    complexity = optimizer._assess_complexity(task)
    print(f"{task.id}: {model} (complexity: {complexity:.2f})")

# Get recommendations
recommendations = optimizer.get_cost_savings_recommendations(
    actual_costs, estimated_costs
)
```

### Issue: Cache Not Hitting

```python
# Check cache statistics
@cached(ttl_seconds=600)
async def my_func(...):
    pass

stats = await my_func.cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"TTL: {stats['ttl_seconds']}s")

# Clear cache if needed
await my_func.cache.clear()
```

## Performance Tuning

### Optimize Worker Count

```python
# Start conservative
executor = ParallelExecutor(max_workers=3)

# Monitor performance
# Increase if CPU underutilized
executor = ParallelExecutor(max_workers=5)

# Monitor memory usage
# Decrease if OOM errors occur
```

### Tune Cache Settings

```python
# High-frequency, stable data
cache = AsyncCache(ttl_seconds=3600, max_size=10000)

# Frequently changing data
cache = AsyncCache(ttl_seconds=60, max_size=100)

# Monitor hit rate and adjust
stats = await cache.get_stats()
if stats['hit_rate'] < 0.5:
    # Consider increasing TTL
    pass
```

### Batch Size Tuning

```python
# For rate-limited APIs
batch = BatchOperations(git, batch_size=5, max_concurrent=1)

# For high-throughput APIs
batch = BatchOperations(git, batch_size=50, max_concurrent=5)

# Monitor API errors and adjust
```

## Integration Examples

### With Existing Code

```python
from automation.monitoring.metrics import measure_duration, MetricsCollector

class MyWorkflow:
    @measure_duration("my_stage")
    async def execute_stage(self):
        # Automatically tracked
        pass

    async def custom_operation(self):
        # Manual tracking
        MetricsCollector.record_workflow_execution("custom", "success")
```

### With Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'automation'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
```

### With Grafana

```
Data Source: Prometheus
Dashboard: Import from /docs/grafana-dashboard.json
Metrics: automation_*
```

## Best Practices

1. **Always create checkpoints** before risky operations
2. **Set appropriate timeouts** for long-running tasks
3. **Monitor cache hit rates** and adjust TTL
4. **Review cost reports** weekly
5. **Clean up old checkpoints** monthly
6. **Use batch operations** for multiple API calls
7. **Enable cost optimization** in production
8. **Record feedback** for learning system
9. **Set up monitoring** before deployment
10. **Test recovery** in staging environment

## File Locations

```
Project Root: /home/ross/Workspace/builder/

Key Files:
- Checkpoints:     .automation/checkpoints/*.json
- Feedback:        .automation/feedback/*.json
- State:           .automation/state/*.json
- Config:          automation/config/*.yaml
- Documentation:   docs/phase-4-features.md
```

## Environment Variables

```bash
# Required
export GITEA_TOKEN="your-token"
export ANTHROPIC_API_KEY="your-key"

# Optional
export AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS=5
export AUTOMATION__MONITORING__DASHBOARD_PORT=8000
export AUTOMATION__COST_OPTIMIZATION__ENABLED=true
```

## Quick Commands

```bash
# Check implementation
python -c "from automation.engine.parallel_executor import ParallelExecutor; print('Phase 4 installed')"

# Start dashboard
uvicorn automation.monitoring.dashboard:app --reload

# Run tests
pytest tests/unit/test_parallel_executor.py -v

# Check coverage
pytest --cov=automation --cov-report=term-missing

# View metrics
curl http://localhost:8000/metrics

# Health check
curl http://localhost:8000/api/health
```
