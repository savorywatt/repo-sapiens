# Phase 4: Advanced Features Documentation

## Table of Contents

1. [Error Recovery](#error-recovery)
2. [Parallel Execution](#parallel-execution)
3. [Multi-Repository Support](#multi-repository-support)
4. [Performance Optimizations](#performance-optimizations)
5. [Monitoring & Analytics](#monitoring--analytics)
6. [Cost Optimization](#cost-optimization)
7. [Learning System](#learning-system)

## Error Recovery

### Overview

Phase 4 introduces a sophisticated error recovery system with checkpoint-based recovery and multiple recovery strategies.

### Checkpoint System

Checkpoints are save points created during workflow execution:

```python
from automation.engine.checkpointing import CheckpointManager

checkpoint = CheckpointManager(".automation/checkpoints")

# Create checkpoint before risky operation
checkpoint_id = await checkpoint.create_checkpoint(
    plan_id="plan-42",
    stage="implementation",
    checkpoint_data={
        "current_task": "task-3",
        "completed_files": ["file1.py", "file2.py"],
        "pending_files": ["file3.py"]
    }
)

# Retrieve latest checkpoint if failure occurs
latest = await checkpoint.get_latest_checkpoint("plan-42")
```

### Recovery Strategies

#### 1. Retry Recovery

For transient errors (API timeouts, network issues):

```python
from automation.engine.recovery import RetryRecoveryStrategy

# Automatically retries with exponential backoff
# Attempt 1: immediate
# Attempt 2: 2 second delay
# Attempt 3: 4 second delay
```

#### 2. Conflict Resolution

For merge conflicts:

```python
from automation.engine.recovery import ConflictResolutionStrategy

# Uses AI to analyze and resolve conflicts
# Falls back to manual intervention if complex
```

#### 3. Test Fix Recovery

For test failures:

```python
from automation.engine.recovery import TestFixRecoveryStrategy

# Analyzes test failures
# Generates fixes using AI
# Re-runs tests to verify
```

### Usage Example

```python
from automation.engine.recovery import AdvancedRecovery

recovery = AdvancedRecovery(state, checkpoint, git, agent)

# Automatic recovery attempt
if await recovery.attempt_recovery("plan-42"):
    print("Recovery successful!")
else:
    print("Manual intervention required")
```

## Parallel Execution

### Task Scheduling

Execute multiple tasks concurrently with dependency management:

```python
from automation.engine.parallel_executor import (
    ParallelExecutor,
    ExecutionTask,
    TaskPriority
)

executor = ParallelExecutor(max_workers=3)

tasks = [
    ExecutionTask(
        id="db-schema",
        func=create_schema,
        priority=TaskPriority.HIGH
    ),
    ExecutionTask(
        id="api-endpoints",
        func=create_api,
        dependencies={"db-schema"},  # Wait for schema
        priority=TaskPriority.NORMAL
    ),
    ExecutionTask(
        id="tests",
        func=create_tests,
        dependencies={"api-endpoints"},
        priority=TaskPriority.NORMAL
    )
]

results = await executor.execute_tasks(tasks)
```

### Dependency Resolution

The executor automatically:
- Resolves dependencies
- Detects circular dependencies
- Executes tasks in correct order
- Maximizes parallelization

### Critical Path Optimization

```python
from automation.engine.parallel_executor import TaskScheduler

scheduler = TaskScheduler(executor)

# Analyzes dependency graph
# Identifies critical path
# Prioritizes critical tasks
optimized_tasks = scheduler.optimize_execution_order(tasks)

results = await scheduler.execute_with_optimization(optimized_tasks)
```

### Performance Tuning

```python
# Configure worker pool
executor = ParallelExecutor(max_workers=5)

# Set task timeouts
task = ExecutionTask(
    id="long-running",
    func=complex_operation,
    timeout=3600.0  # 1 hour
)

# Set task metadata
task = ExecutionTask(
    id="tracked",
    func=operation,
    metadata={
        "cost_estimate": 5.0,
        "priority_reason": "blocking other tasks"
    }
)
```

## Multi-Repository Support

### Configuration

Define repositories in `config/repositories.yaml`:

```yaml
repositories:
  - name: backend
    owner: myorg
    repo: backend-service
    primary: true
    automation:
      enabled: true
      auto_deploy: true

  - name: frontend
    owner: myorg
    repo: frontend-app
    automation:
      enabled: true
      depends_on:
        - backend

  - name: infrastructure
    owner: myorg
    repo: infra
    automation:
      enabled: true
      triggers:
        - backend
        - frontend

cross_repo_workflows:
  - name: full-stack-feature
    repositories:
      - backend
      - frontend
    coordination: sequential

  - name: infrastructure-update
    repositories:
      - backend
      - frontend
      - infrastructure
    coordination: parallel
```

### Usage

```python
from automation.engine.multi_repo import MultiRepoOrchestrator

orchestrator = MultiRepoOrchestrator(repo_configs)

# Register providers for each repository
orchestrator.register_provider("backend", backend_git)
orchestrator.register_provider("frontend", frontend_git)

# Execute cross-repo workflow
results = await orchestrator.execute_cross_repo_workflow(
    workflow_name="full-stack-feature",
    trigger_issue=issue,
    context={
        "source_repo": "backend",
        "feature_flag": "new-feature-v2"
    }
)

# Check status
status = await orchestrator.get_overall_status()
print(f"Overall: {status['overall_status']}")
```

### Coordination Modes

#### Sequential

Tasks execute one repository at a time:
```yaml
coordination: sequential
```

Benefits:
- Easier debugging
- Clear dependency chain
- Lower resource usage

#### Parallel

Tasks execute across repositories simultaneously:
```yaml
coordination: parallel
```

Benefits:
- Faster completion
- Better resource utilization
- Independent failures don't block others

## Performance Optimizations

### Caching

#### Function-Level Caching

```python
from automation.utils.caching import cached

@cached(ttl_seconds=600)  # Cache for 10 minutes
async def get_issue(issue_number: int) -> Issue:
    return await git.get_issue(issue_number)

# Clear cache when needed
await get_issue.cache.clear()

# Get cache statistics
stats = await get_issue.cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

#### Manual Caching

```python
from automation.utils.caching import AsyncCache

cache = AsyncCache(ttl_seconds=300, max_size=1000)

# Store value
await cache.set("key", value)

# Retrieve value
value = await cache.get("key")

# Delete value
await cache.delete("key")
```

### Connection Pooling

```python
from automation.utils.connection_pool import HTTPConnectionPool

# Create pool
pool = HTTPConnectionPool(
    base_url="https://api.example.com",
    max_connections=10,
    max_keepalive_connections=5,
    timeout=30.0
)

# Use pool
async with pool:
    response = await pool.get("/api/v1/data")
    data = response.json()

# Or manual lifecycle
await pool.initialize()
response = await pool.get("/api/v1/data")
await pool.close()
```

### Batch Operations

```python
from automation.utils.batch_operations import BatchOperations

batch_ops = BatchOperations(
    git_provider=git,
    batch_size=10,
    max_concurrent=3
)

# Create multiple issues
issues_data = [
    {"title": "Task 1", "body": "Description 1", "labels": ["task"]},
    {"title": "Task 2", "body": "Description 2", "labels": ["task"]},
    # ... 50 more issues
]

issues = await batch_ops.create_issues_batch(issues_data)

# Update multiple issues
updates = [
    {"issue_number": 1, "fields": {"labels": ["completed"]}},
    {"issue_number": 2, "fields": {"labels": ["completed"]}},
]

await batch_ops.update_issues_batch(updates)
```

## Monitoring & Analytics

### Metrics Collection

```python
from automation.monitoring.metrics import (
    MetricsCollector,
    measure_duration,
    measure_api_call
)

# Automatic measurement with decorator
@measure_duration("planning")
async def execute_planning(issue):
    # Planning logic
    pass

# Manual metrics
MetricsCollector.record_workflow_execution("planning", "success")
MetricsCollector.record_api_call("gitea", "create_issue", "success")
MetricsCollector.update_active_workflows(5)
```

### Dashboard

Start the dashboard server:

```bash
python -m automation.monitoring.dashboard
# or
uvicorn automation.monitoring.dashboard:app --port 8000
```

Access at: http://localhost:8000

### Available Endpoints

- `GET /` - Interactive dashboard
- `GET /api/metrics/summary` - Summary metrics
- `GET /api/metrics/workflows` - Workflow details
- `GET /api/metrics/tasks` - Task statistics
- `GET /api/metrics/performance` - Performance metrics
- `GET /api/metrics/costs` - Cost information
- `GET /api/health` - Health check
- `GET /metrics` - Prometheus metrics

### Prometheus Integration

Scrape metrics:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'automation'
    static_configs:
      - targets: ['localhost:8000']
```

Example queries:

```promql
# Success rate by stage
rate(automation_workflow_executions_total{status="success"}[5m])
  /
rate(automation_workflow_executions_total[5m])

# Average workflow duration
rate(automation_workflow_duration_seconds_sum[5m])
  /
rate(automation_workflow_duration_seconds_count[5m])

# Cache hit rate
automation_cache_hits_total
  /
(automation_cache_hits_total + automation_cache_misses_total)
```

## Cost Optimization

### Automatic Model Selection

```python
from automation.utils.cost_optimizer import CostOptimizer, ModelTier

optimizer = CostOptimizer(enable_optimization=True)

# Analyzes task complexity
model = optimizer.select_model_for_task(task)

# Returns:
# - ModelTier.FAST for simple tasks (typos, docs)
# - ModelTier.BALANCED for medium tasks (features)
# - ModelTier.ADVANCED for complex tasks (architecture, security)
```

### Complexity Factors

The optimizer considers:

1. **Description Length**: Longer = more complex
2. **Keywords**: Security, performance, distributed, etc.
3. **Dependencies**: More dependencies = more complex
4. **File Count**: More files = more complex
5. **Estimated Changes**: Larger changes = more complex
6. **Security Implications**: Security tasks = more complex
7. **Performance Requirements**: Optimization tasks = more complex

### Cost Estimation

```python
# Estimate costs before execution
costs = await optimizer.estimate_cost(plan)

print(f"Planning: ${costs['planning']:.2f}")
print(f"Implementation: ${costs['implementation']:.2f}")
print(f"Review: ${costs['review']:.2f}")
print(f"Total: ${costs['total']:.2f}")
```

### Cost Tracking

```python
from automation.monitoring.metrics import MetricsCollector

# Track actual costs
MetricsCollector.update_estimated_cost("implementation", 35.50)
MetricsCollector.record_token_usage("claude-sonnet-4.5", "planning", 15000)
```

## Learning System

### Recording Executions

```python
from automation.learning.feedback_loop import FeedbackLoop

feedback = FeedbackLoop(".automation/feedback")

await feedback.record_execution(
    task_id="task-42",
    prompt="Implement user authentication...",
    result=task_result,
    review=review_result,
    metadata={
        "task_type": "feature",
        "complexity": 0.7
    }
)
```

### Prompt Improvement

```python
# Get improved prompt based on historical success
base_prompt = "Implement the following feature:"

improved_prompt = await feedback.improve_prompt(task, base_prompt)

# improved_prompt now includes learned patterns like:
# - "Include test coverage"
# - "Include error handling"
# - "Include documentation"
```

### Learning Statistics

```python
stats = await feedback.get_learning_stats()

print(f"Total executions: {stats['total_executions']}")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Average review score: {stats['average_review_score']:.2f}")
```

### Cleanup

```python
# Clean up old feedback (keep last 90 days)
deleted = await feedback.cleanup_old_feedback(max_age_days=90)
print(f"Deleted {deleted} old feedback entries")
```

## Best Practices

### Error Recovery

1. **Create Checkpoints Frequently**: Before any risky operation
2. **Include Context**: Store enough data to resume
3. **Clean Up**: Delete old checkpoints regularly
4. **Monitor**: Track recovery success rates

### Parallel Execution

1. **Declare Dependencies**: Be explicit about task dependencies
2. **Set Timeouts**: Prevent tasks from running indefinitely
3. **Prioritize**: Use priorities for critical path tasks
4. **Tune Workers**: Adjust based on available resources

### Performance

1. **Cache Aggressively**: Cache expensive operations
2. **Batch Operations**: Group API calls when possible
3. **Monitor**: Track cache hit rates and API performance
4. **Optimize**: Use connection pooling for HTTP requests

### Cost Management

1. **Enable Optimization**: Use intelligent model selection
2. **Monitor Costs**: Track actual vs estimated costs
3. **Review Patterns**: Check which tasks use expensive models
4. **Adjust Complexity**: Refine complexity assessment as needed

### Learning

1. **Record Everything**: Capture all execution data
2. **Review Feedback**: Analyze successful patterns
3. **Iterate Prompts**: Continuously improve based on data
4. **Clean Up**: Remove old data to keep system performant
