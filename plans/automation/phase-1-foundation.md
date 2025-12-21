# Phase 1: Foundation (MVP) - Implementation Guide

## Overview

Build the foundational components of the automation system. By the end of this phase, you'll have a working CLI that can process a planning issue and generate a plan file, with proper configuration, state management, and basic provider implementations.

## Prerequisites

- Python 3.11 or higher installed
- Git installed and configured
- Access to a Gitea instance (or GitHub for testing)
- MCP server for Gitea configured (or use REST API fallback)

## Implementation Steps

### Step 1: Project Setup

**Files to Create:**
- `/home/ross/Workspace/builder/pyproject.toml`
- `/home/ross/Workspace/builder/automation/__init__.py`
- `/home/ross/Workspace/builder/.gitignore`

**Actions:**

1. Create the project structure:
```bash
mkdir -p automation/{config,models,providers,engine/stages,processors,utils}
mkdir -p tests/{unit,integration,fixtures}
mkdir -p plans .automation/state
touch automation/__init__.py
touch automation/{config,models,providers,engine,processors,utils}/__init__.py
```

2. Create `pyproject.toml` with dependencies:
```toml
[project]
name = "gitea-automation"
version = "0.1.0"
description = "AI-driven automation system for Gitea"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.25.0",
    "structlog>=23.2.0",
    "click>=8.1.0",
    "pyyaml>=6.0",
    "aiofiles>=23.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "black>=23.12.0",
    "ruff>=0.1.8",
    "mypy>=1.7.0",
]

[project.scripts]
automation = "automation.main:cli"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "C4", "DTZ", "T10", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
```

3. Create `.gitignore`:
```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.env
.automation/state/*.json
.automation/state/*.tmp
*.log
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
```

4. Install dependencies:
```bash
pip install -e ".[dev]"
```

### Step 2: Configuration System

**Files to Create:**
- `/home/ross/Workspace/builder/automation/config/settings.py`
- `/home/ross/Workspace/builder/automation/config/automation_config.yaml`

**Implementation:**

1. Create `automation/config/settings.py`:

Implement Pydantic settings classes with:
- `GitProviderConfig`: Git provider configuration (type, MCP server, base URL, token)
- `RepositoryConfig`: Repository details (owner, name, default branch)
- `AgentProviderConfig`: Agent configuration (type, model, API key, local flag)
- `WorkflowConfig`: Workflow settings (plans directory, branching strategy, thresholds)
- `TagsConfig`: Issue tag names for each stage
- `AutomationSettings`: Main settings class that combines all configs

Key features:
- Use `pydantic.SecretStr` for API tokens
- Use `pydantic.HttpUrl` for URLs
- Use `Literal` types for enums (e.g., `Literal["gitea", "github"]`)
- Implement `from_yaml()` classmethod with environment variable interpolation
- Use `SettingsConfigDict` with `env_prefix="AUTOMATION_"`

2. Create `automation/config/automation_config.yaml`:

Sample configuration file with:
- Gitea provider settings
- Repository configuration
- Claude local provider settings
- Workflow defaults (per-agent strategy, 3 concurrent tasks)
- Tag names for all stages
- Environment variable placeholders (e.g., `${GITEA_TOKEN}`)

**Testing:**
```bash
# Test configuration loading
python -c "from automation.config.settings import AutomationSettings; \
           config = AutomationSettings.from_yaml('automation/config/automation_config.yaml'); \
           print(config.repository.owner)"
```

### Step 3: Domain Models

**Files to Create:**
- `/home/ross/Workspace/builder/automation/models/domain.py`

**Implementation:**

Create dataclasses for domain objects:

1. **Enums:**
   - `IssueState(str, Enum)`: OPEN, CLOSED
   - `TaskStatus(str, Enum)`: PENDING, IN_PROGRESS, CODE_REVIEW, MERGE_READY, COMPLETED, FAILED

2. **Data Classes:**
   - `Issue`: id, number, title, body, state, labels, created_at, updated_at, author, url
   - `Comment`: id, body, author, created_at
   - `Branch`: name, sha, protected
   - `PullRequest`: id, number, title, body, head, base, state, url, created_at
   - `Task`: id, prompt_issue_id, title, description, dependencies, context
   - `TaskResult`: success, branch, commits, files_changed, error, execution_time
   - `Plan`: id, title, description, tasks, file_path, created_at
   - `Review`: approved, comments, issues_found, suggestions, confidence_score

Key requirements:
- Use `@dataclass` decorator
- Use `field(default_factory=list)` for mutable defaults
- Use `Optional[T]` for nullable fields
- Use `datetime` for timestamps
- All fields should have type annotations

**Testing:**
```python
# Create test in tests/unit/test_models.py
from automation.models.domain import Issue, IssueState
from datetime import datetime

def test_issue_creation():
    issue = Issue(
        id=1, number=42, title="Test", body="Description",
        state=IssueState.OPEN, labels=["test"],
        created_at=datetime.now(), updated_at=datetime.now(),
        author="testuser", url="https://example.com/issues/42"
    )
    assert issue.number == 42
    assert issue.state == IssueState.OPEN
```

### Step 4: Structured Logging

**Files to Create:**
- `/home/ross/Workspace/builder/automation/utils/logging_config.py`

**Implementation:**

Create logging configuration using `structlog`:

```python
import structlog
from typing import Any

def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with JSON output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str = None) -> Any:
    """Get a logger instance."""
    return structlog.get_logger(name)
```

Usage pattern:
```python
log = get_logger(__name__)
log.info("operation_started", issue_id=42, stage="planning")
log.error("operation_failed", issue_id=42, error=str(e), exc_info=True)
```

### Step 5: MCP Client

**Files to Create:**
- `/home/ross/Workspace/builder/automation/utils/mcp_client.py`

**Implementation:**

Create MCP client for communicating with MCP servers:

```python
from typing import Dict, Any, Optional
import asyncio
import json
import structlog

log = structlog.get_logger(__name__)

class MCPClient:
    """Client for interacting with MCP servers via JSON-RPC."""

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0

    async def connect(self) -> None:
        """Establish connection to MCP server."""
        # Start MCP server process
        # This is simplified - actual implementation depends on MCP server
        log.info("mcp_connect", server=self.server_name)

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an MCP tool with arguments."""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }

        log.debug("mcp_request", tool=tool_name, request_id=self._request_id)
        response = await self._send_request(request)

        if "error" in response:
            raise MCPError(response["error"])

        return response.get("result", {})

    async def _send_request(self, request: Dict) -> Dict:
        """Send JSON-RPC request to MCP server."""
        # Actual implementation would communicate via stdio or HTTP
        # For now, this is a placeholder
        raise NotImplementedError("MCP communication not yet implemented")

    async def close(self) -> None:
        """Close connection to MCP server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            log.info("mcp_closed", server=self.server_name)


class MCPError(Exception):
    """MCP protocol error."""
    pass
```

**Note:** For Phase 1, you may want to create a mock MCP client for testing, and implement real MCP communication in Phase 2.

### Step 6: State Manager

**Files to Create:**
- `/home/ross/Workspace/builder/automation/engine/state_manager.py`

**Implementation:**

Create state manager with transaction support:

Key methods to implement:
- `__init__(state_dir)`: Initialize with state directory
- `transaction(plan_id)`: Async context manager for atomic updates
- `load_state(plan_id)`: Load state from JSON file
- `save_state(plan_id, state)`: Atomically save state
- `mark_stage_complete(plan_id, stage, data)`: Mark stage as complete
- `mark_task_status(plan_id, task_id, status, data)`: Update task status
- `get_active_plans()`: Get all active plan IDs
- `_create_initial_state(plan_id)`: Create new state structure
- `_calculate_overall_status(state)`: Determine overall workflow status

Critical features:
- Use `asyncio.Lock` per plan_id to prevent concurrent writes
- Atomic file writes: write to `.tmp` file, then rename
- Transaction pattern: load → modify → save (or rollback on error)
- State structure matches the JSON schema from main plan

**Testing:**
```python
# tests/unit/test_state_manager.py
import pytest
from automation.engine.state_manager import StateManager

@pytest.mark.asyncio
async def test_state_creation(tmp_path):
    state_mgr = StateManager(str(tmp_path))
    state = await state_mgr.load_state("test-plan")
    assert state["plan_id"] == "test-plan"
    assert state["status"] == "pending"

@pytest.mark.asyncio
async def test_state_transaction(tmp_path):
    state_mgr = StateManager(str(tmp_path))
    async with state_mgr.transaction("test-plan") as state:
        state["status"] = "in_progress"

    loaded = await state_mgr.load_state("test-plan")
    assert loaded["status"] == "in_progress"
```

### Step 7: Provider Base Classes

**Files to Create:**
- `/home/ross/Workspace/builder/automation/providers/base.py`

**Implementation:**

Create abstract base classes using `abc.ABC`:

1. **GitProvider ABC:**
   - `get_issues(labels, state)`: List issues
   - `get_issue(issue_number)`: Get single issue
   - `create_issue(title, body, labels)`: Create issue
   - `update_issue(issue_number, **kwargs)`: Update issue
   - `add_comment(issue_number, comment)`: Add comment
   - `get_comments(issue_number)`: Get comments
   - `create_branch(branch_name, from_branch)`: Create branch
   - `get_branch(branch_name)`: Get branch info
   - `create_pull_request(title, body, head, base, labels)`: Create PR
   - `get_diff(base, head)`: Get diff between branches
   - `get_file(path, ref)`: Read file from repo
   - `commit_file(path, content, message, branch)`: Commit file
   - `merge_branches(source, target, message)`: Merge branches

2. **AgentProvider ABC:**
   - `execute_task(task, context)`: Execute development task
   - `generate_plan(issue)`: Generate plan from issue
   - `generate_prompts(plan)`: Break plan into tasks
   - `review_code(diff, context)`: Review code changes
   - `resolve_conflict(conflict_info)`: Resolve merge conflict

All methods should:
- Be decorated with `@abstractmethod`
- Have proper type hints
- Return appropriate domain model types
- Be async (`async def`)

### Step 8: Gitea Provider (Simplified)

**Files to Create:**
- `/home/ross/Workspace/builder/automation/providers/git_provider.py`

**Implementation:**

For Phase 1, create a simplified Gitea provider:

```python
from typing import List, Optional
from automation.providers.base import GitProvider
from automation.models.domain import Issue, Comment, Branch, PullRequest
from automation.utils.mcp_client import MCPClient
import structlog

log = structlog.get_logger(__name__)

class GiteaProvider(GitProvider):
    """Gitea implementation using MCP (simplified for Phase 1)."""

    def __init__(self, mcp_server: str, base_url: str, token: str,
                 owner: str, repo: str):
        self.mcp = MCPClient(mcp_server)
        self.base_url = base_url
        self.token = token
        self.owner = owner
        self.repo = repo

    async def get_issues(
        self,
        labels: Optional[List[str]] = None,
        state: str = "open"
    ) -> List[Issue]:
        """Retrieve issues via MCP."""
        log.info("get_issues", labels=labels, state=state)
        result = await self.mcp.call_tool(
            "gitea_list_issues",
            owner=self.owner,
            repo=self.repo,
            state=state,
            labels=",".join(labels) if labels else None
        )
        return [self._parse_issue(issue) for issue in result.get("issues", [])]

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None
    ) -> Issue:
        """Create issue via MCP."""
        log.info("create_issue", title=title)
        result = await self.mcp.call_tool(
            "gitea_create_issue",
            owner=self.owner,
            repo=self.repo,
            title=title,
            body=body,
            labels=labels or []
        )
        return self._parse_issue(result)

    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str
    ) -> str:
        """Commit file via MCP."""
        log.info("commit_file", path=path, branch=branch)
        result = await self.mcp.call_tool(
            "gitea_commit_file",
            owner=self.owner,
            repo=self.repo,
            path=path,
            content=content,
            message=message,
            branch=branch
        )
        return result.get("sha")

    def _parse_issue(self, data: dict) -> Issue:
        """Parse issue data from API response."""
        from datetime import datetime
        from automation.models.domain import IssueState

        return Issue(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=IssueState(data["state"]),
            labels=[label["name"] for label in data.get("labels", [])],
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            ),
            author=data["user"]["login"],
            url=data["html_url"]
        )

    # Implement remaining methods with NotImplementedError for Phase 1
    async def get_issue(self, issue_number: int) -> Issue:
        raise NotImplementedError("Phase 2")

    async def update_issue(self, issue_number: int, **kwargs) -> Issue:
        raise NotImplementedError("Phase 2")

    # ... etc for other methods
```

**For Phase 1**, only implement methods needed for planning stage:
- `get_issues()`
- `create_issue()`
- `add_comment()`
- `commit_file()`

### Step 9: Claude Local Provider (Simplified)

**Files to Create:**
- `/home/ross/Workspace/builder/automation/providers/agent_provider.py`

**Implementation:**

Create Claude provider that executes via subprocess:

Key methods for Phase 1:
- `generate_plan(issue)`: Generate development plan
- `_run_claude(prompt, branch)`: Execute Claude CLI
- `_build_prompt(task, context)`: Build prompt from task
- `_extract_tasks_from_plan(content)`: Parse tasks from plan markdown
- `_slugify(text)`: Convert text to URL slug

Implementation notes:
- Use `asyncio.create_subprocess_exec()` for running Claude
- Parse Claude output to extract plan content
- For Phase 1, simple task extraction (look for numbered lists or task sections)
- Handle errors gracefully and log them

Stub out remaining methods:
- `execute_task()`: NotImplementedError (Phase 2)
- `generate_prompts()`: NotImplementedError (Phase 2)
- `review_code()`: NotImplementedError (Phase 2)
- `resolve_conflict()`: NotImplementedError (Phase 4)

### Step 10: Planning Stage

**Files to Create:**
- `/home/ross/Workspace/builder/automation/engine/stages/__init__.py`
- `/home/ross/Workspace/builder/automation/engine/stages/base.py`
- `/home/ross/Workspace/builder/automation/engine/stages/planning.py`

**Implementation:**

1. Create base class (`base.py`):
```python
from abc import ABC, abstractmethod
from automation.models.domain import Issue
from automation.providers.base import GitProvider, AgentProvider
from automation.engine.state_manager import StateManager
from automation.config.settings import AutomationSettings
import structlog

log = structlog.get_logger(__name__)

class WorkflowStage(ABC):
    """Base class for workflow stages."""

    def __init__(
        self,
        git: GitProvider,
        agent: AgentProvider,
        state: StateManager,
        settings: AutomationSettings
    ):
        self.git = git
        self.agent = agent
        self.state = state
        self.settings = settings

    @abstractmethod
    async def execute(self, issue: Issue) -> None:
        """Execute this stage of the workflow."""
        pass

    async def _handle_stage_error(self, issue: Issue, error: Exception) -> None:
        """Common error handling for all stages."""
        error_msg = f"Stage execution failed: {str(error)}"
        await self.git.add_comment(issue.number, error_msg)

        labels = list(set(issue.labels + [self.settings.tags.needs_attention]))
        await self.git.update_issue(issue.number, labels=labels)
```

2. Create planning stage (`planning.py`):

Implement:
- `execute(issue)`: Main execution method
  1. Generate plan using agent
  2. Commit plan file to repository
  3. Create plan review issue
  4. Add comment to original issue
  5. Update state
- `_format_plan(plan)`: Convert Plan object to markdown
- `_create_review_body(issue, plan)`: Create review issue body

Error handling:
- Wrap in try/except
- Log errors with context
- Call `_handle_stage_error()` on failure
- Re-raise exception

### Step 11: CLI Entry Point

**Files to Create:**
- `/home/ross/Workspace/builder/automation/main.py`

**Implementation:**

Create Click-based CLI:

```python
import asyncio
import click
from pathlib import Path
from automation.config.settings import AutomationSettings
from automation.utils.logging_config import configure_logging
from automation.engine.state_manager import StateManager
from automation.providers.git_provider import GiteaProvider
from automation.providers.agent_provider import ClaudeLocalProvider
from automation.engine.stages.planning import PlanningStage
import structlog

log = structlog.get_logger(__name__)

@click.group()
@click.option("--config", default="automation/config/automation_config.yaml",
              help="Path to configuration file")
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def cli(ctx, config, log_level):
    """Gitea automation system CLI."""
    configure_logging(log_level)

    # Load configuration
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Configuration file not found: {config}")
        ctx.exit(1)

    settings = AutomationSettings.from_yaml(str(config_path))
    ctx.obj = {"settings": settings}

@cli.command()
@click.option("--issue", type=int, required=True, help="Issue number to process")
@click.pass_context
def process_planning_issue(ctx, issue):
    """Process a planning issue manually."""
    asyncio.run(_process_planning_issue(ctx.obj["settings"], issue))

async def _process_planning_issue(settings: AutomationSettings, issue_number: int):
    """Async implementation of planning issue processing."""
    log.info("processing_planning_issue", issue=issue_number)

    # Initialize providers
    git = GiteaProvider(
        mcp_server=settings.git_provider.mcp_server,
        base_url=str(settings.git_provider.base_url),
        token=settings.git_provider.api_token.get_secret_value(),
        owner=settings.repository.owner,
        repo=settings.repository.name
    )

    agent = ClaudeLocalProvider(
        model=settings.agent_provider.model,
        workspace=Path.cwd()
    )

    state = StateManager(settings.state_dir)

    # Initialize planning stage
    planning = PlanningStage(git, agent, state, settings)

    # Get issue
    issue = await git.get_issue(issue_number)

    # Execute planning stage
    await planning.execute(issue)

    log.info("planning_complete", issue=issue_number)

if __name__ == "__main__":
    cli()
```

### Step 12: Testing

**Files to Create:**
- `/home/ross/Workspace/builder/tests/conftest.py`
- `/home/ross/Workspace/builder/tests/unit/test_config.py`
- `/home/ross/Workspace/builder/tests/unit/test_state_manager.py`
- `/home/ross/Workspace/builder/tests/unit/test_planning_stage.py`

**Implementation:**

1. Create `conftest.py` with fixtures:
```python
import pytest
from pathlib import Path
from automation.config.settings import AutomationSettings
from automation.engine.state_manager import StateManager
from automation.models.domain import Issue, IssueState
from datetime import datetime

@pytest.fixture
def temp_state_dir(tmp_path):
    """Temporary state directory."""
    return tmp_path / "state"

@pytest.fixture
def state_manager(temp_state_dir):
    """StateManager instance with temp directory."""
    return StateManager(str(temp_state_dir))

@pytest.fixture
def sample_issue():
    """Sample issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Implement user authentication",
        body="We need login, signup, and password reset",
        state=IssueState.OPEN,
        labels=["needs-planning"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author="testuser",
        url="https://gitea.example.com/owner/repo/issues/42"
    )

@pytest.fixture
def mock_settings(tmp_path):
    """Mock settings for testing."""
    # Create minimal settings for testing
    pass
```

2. Write unit tests for each component:
   - Configuration loading and validation
   - State manager operations
   - Model creation and serialization
   - Planning stage execution (with mocked providers)

3. Use `pytest-asyncio` for async tests:
```python
@pytest.mark.asyncio
async def test_planning_stage_execution(sample_issue, mock_git, mock_agent, state_manager, mock_settings):
    planning = PlanningStage(mock_git, mock_agent, state_manager, mock_settings)
    await planning.execute(sample_issue)
    # Assert plan was created, issue was updated, etc.
```

Run tests:
```bash
pytest tests/ -v
pytest tests/ --cov=automation --cov-report=html
```

## Success Criteria

At the end of Phase 1, you should be able to:

1. **Load Configuration:**
   ```bash
   python -c "from automation.config.settings import AutomationSettings; \
              s = AutomationSettings.from_yaml('automation/config/automation_config.yaml'); \
              print(s.repository.owner)"
   ```

2. **Process a Planning Issue:**
   ```bash
   automation process-planning-issue --issue 42
   ```

3. **Verify Output:**
   - Plan file created in `plans/42-{slug}.md`
   - Plan review issue created in Gitea
   - State file created in `.automation/state/42.json`
   - Original issue has comment with link to plan

4. **Run Tests:**
   ```bash
   pytest tests/ -v
   # All tests pass
   # Coverage > 70%
   ```

5. **Code Quality:**
   ```bash
   black automation/ tests/
   ruff check automation/ tests/
   mypy automation/
   # All checks pass
   ```

## Common Issues and Solutions

**Issue: MCP server not responding**
- Solution: For Phase 1, create a mock MCP client that returns hardcoded responses
- Implement real MCP communication in Phase 2

**Issue: Claude Code not installed**
- Solution: Install Claude Code CLI or create a mock agent provider for testing
- Mock provider can return a sample plan for testing

**Issue: Pydantic validation errors**
- Solution: Check that all required fields are present in YAML config
- Use `SecretStr.get_secret_value()` to access secret values
- Ensure environment variables are set

**Issue: State file locking errors**
- Solution: Ensure only one process accesses state files at a time
- Use separate test state directories for parallel tests

## Next Steps

After completing Phase 1:
1. Review and refactor based on learnings
2. Ensure all tests pass and coverage is adequate
3. Document any deviations from the plan
4. Move on to Phase 2: Core Workflow

Phase 2 will build on this foundation by:
- Implementing remaining workflow stages
- Adding dependency tracking
- Implementing both branching strategies
- Creating integration tests for the full workflow
