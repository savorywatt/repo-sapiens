# Gitea Automation System - Phase 2: Core Workflow

Complete AI-driven automation system for Gitea with full workflow implementation from issue to pull request.

## Overview

This automation system provides a complete workflow for processing development tasks:

1. **Planning Stage**: Generate development plans from issues
2. **Plan Review Stage**: Break plans into executable tasks
3. **Implementation Stage**: Execute tasks using AI agents
4. **Code Review Stage**: AI-powered code review
5. **Merge Stage**: Create pull requests for completed work

## Features

### Phase 1 & 2 Complete Implementation

- ✅ Configuration management with Pydantic
- ✅ Domain models for all entities
- ✅ Structured logging with structlog
- ✅ MCP client for Gitea integration
- ✅ State management with atomic transactions
- ✅ Provider abstraction (Git & Agent)
- ✅ Full Gitea provider with retry logic
- ✅ Claude local agent provider
- ✅ Dependency tracking system
- ✅ Two branching strategies (per-plan, per-agent)
- ✅ All 5 workflow stages
- ✅ Parallel task execution
- ✅ Error recovery mechanisms
- ✅ Comprehensive CLI
- ✅ Unit and integration tests

## Architecture

```
automation/
├── config/               # Configuration management
│   ├── settings.py      # Pydantic settings
│   └── automation_config.yaml
├── models/              # Domain models
│   └── domain.py       # Issue, Task, Plan, Review, etc.
├── providers/           # Provider implementations
│   ├── base.py         # Abstract base classes
│   ├── git_provider.py # Gitea MCP integration
│   └── agent_provider.py # Claude agent
├── engine/              # Workflow engine
│   ├── orchestrator.py  # Main orchestrator
│   ├── state_manager.py # State management
│   ├── branching.py     # Branching strategies
│   └── stages/          # Workflow stages
│       ├── planning.py
│       ├── plan_review.py
│       ├── implementation.py
│       ├── code_review.py
│       └── merge.py
├── processors/          # Processing utilities
│   └── dependency_tracker.py
└── utils/               # Utility modules
    ├── logging_config.py
    ├── retry.py
    ├── helpers.py
    └── mcp_client.py
```

## Workflow Stages

### 1. Planning Stage

**Trigger**: Issue with `needs-planning` label

**Actions**:
1. Generate development plan using AI agent
2. Commit plan file to repository
3. Create plan review issue
4. Update state

### 2. Plan Review Stage

**Trigger**: Issue with `plan-review` label

**Actions**:
1. Read plan file
2. Generate prompts for each task
3. Create implementation issue per task
4. Track dependencies in state

### 3. Implementation Stage

**Trigger**: Issue with `needs-implementation` label

**Actions**:
1. Check task dependencies
2. Create branch (based on strategy)
3. Execute task using AI agent
4. Commit changes
5. Tag for code review

### 4. Code Review Stage

**Trigger**: Issue with `code-review` label

**Actions**:
1. Get diff between branch and base
2. Run AI code review
3. Post review comments
4. Tag as merge-ready if approved

### 5. Merge Stage

**Trigger**: Issue with `merge-ready` label

**Actions**:
1. Verify all tasks complete
2. Create integration branch
3. Generate PR description
4. Create pull request
5. Close related issues

## Branching Strategies

### Per-Plan Strategy

- Single branch per plan: `plan/42`
- All tasks commit to same branch
- Simpler, but serial execution
- Good for small plans or conflicting changes

### Per-Agent Strategy (Default)

- Dedicated branch per task: `task/42-task-1`
- Parallel task execution
- Integration branch merges all tasks: `integration/plan-42`
- Better for large plans with independent tasks

## Dependency Tracking

The system includes sophisticated dependency tracking:

- **Validation**: Detects circular dependencies and invalid references
- **Execution Order**: Calculates optimal execution batches
- **Blocking Detection**: Identifies tasks blocked by failures
- **Parallel Execution**: Runs independent tasks concurrently

## CLI Usage

### Basic Commands

```bash
# Process a single issue
automation process-issue --issue 42

# Process all issues with specific tag
automation process-all --tag needs-planning

# Process entire plan end-to-end
automation process-plan --plan-id 42

# Run in daemon mode (continuous polling)
automation daemon --interval 60

# List active plans
automation list-plans

# Show plan status
automation show-plan --plan-id 42
```

### Configuration

Configure via `automation/config/automation_config.yaml`:

```yaml
git_provider:
  type: gitea
  mcp_server: gitea-mcp
  base_url: ${GITEA_URL}
  api_token: ${GITEA_TOKEN}

repository:
  owner: ${GITEA_OWNER}
  name: ${GITEA_REPO}
  default_branch: main

agent_provider:
  type: claude
  model: claude-sonnet-4.5
  local: true

workflow:
  branching_strategy: per-agent  # or per-plan
  max_concurrent_tasks: 3
```

## State Management

State files stored in `.automation/state/`:

```json
{
  "plan_id": "42",
  "status": "in_progress",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T12:00:00",
  "stages": {
    "planning": {"status": "completed", "data": {...}},
    "implementation": {"status": "in_progress", "data": {...}}
  },
  "tasks": {
    "task-1": {
      "status": "completed",
      "branch": "task/42-task-1",
      "dependencies": []
    }
  }
}
```

## Error Handling

- **Retry Logic**: All MCP calls have exponential backoff retry
- **State Transactions**: Atomic state updates prevent corruption
- **Stage Error Handling**: Failed stages add comments and labels
- **Dependency Blocking**: Failed tasks block dependent tasks
- **Recovery**: State preserved for manual intervention

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v -m integration

# With coverage
pytest tests/ --cov=automation --cov-report=html
```

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Format code
black automation/ tests/

# Lint
ruff check automation/ tests/

# Type check
mypy automation/
```

## Future Enhancements (Phase 3+)

- Gitea Actions integration
- Webhook support
- Multi-repository orchestration
- Conflict resolution automation
- Performance monitoring
- Web dashboard

## License

See LICENSE file.
