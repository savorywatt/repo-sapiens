# Gitea-Driven Automation System

## Overview

An intelligent automation system that uses Gitea issues and tags to orchestrate a multi-stage AI-driven development workflow. The system transforms a single planning issue into a complete development cycle: planning → prompt generation → implementation → code review → PR creation.

## System Architecture

### Core Components

#### 1. Configuration Layer
**File**: `automation/config/settings.py`

Using Pydantic for configuration validation with environment variable support:

```python
from pydantic import BaseModel, Field, SecretStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class GitProviderConfig(BaseModel):
    type: Literal["gitea", "github"] = "gitea"
    mcp_server: str = Field(..., description="MCP server name")
    base_url: HttpUrl
    api_token: SecretStr

class RepositoryConfig(BaseModel):
    owner: str
    name: str
    default_branch: str = "main"

class AgentProviderConfig(BaseModel):
    type: Literal["claude", "openai", "anthropic-api"] = "claude"
    model: str = "claude-sonnet-4.5"
    api_key: SecretStr | None = None
    local: bool = True

class WorkflowConfig(BaseModel):
    plans_directory: str = "plans/"
    branching_strategy: Literal["per-agent", "per-plan"] = "per-agent"
    auto_merge_threshold: float = Field(0.95, ge=0.0, le=1.0)
    max_concurrent_tasks: int = Field(3, ge=1)
    parallel_execution: bool = True

class TagsConfig(BaseModel):
    planning: str = "needs-planning"
    plan_review: str = "plan-review"
    prompt_generation: str = "prompts"
    implementation: str = "implement"
    code_review: str = "code-review"
    merge_ready: str = "merge-ready"
    needs_attention: str = "needs-attention"
    conflict_resolution: str = "conflict-resolution"

class AutomationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOMATION_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    git_provider: GitProviderConfig
    repository: RepositoryConfig
    agent_provider: AgentProviderConfig
    workflow: WorkflowConfig
    tags: TagsConfig

    # Operational settings
    log_level: str = "INFO"
    state_dir: str = ".automation/state"
    retry_max_attempts: int = 3
    retry_backoff_factor: float = 2.0

    @classmethod
    def from_yaml(cls, path: str) -> "AutomationSettings":
        """Load settings from YAML file with env var interpolation."""
        import yaml
        import os

        with open(path) as f:
            data = yaml.safe_load(f)

        # Interpolate environment variables
        def interpolate(obj):
            if isinstance(obj, dict):
                return {k: interpolate(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [interpolate(v) for v in obj]
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.getenv(var_name, obj)
            return obj

        return cls(**interpolate(data))
```

**Alternative YAML config**: `automation/config/automation_config.yaml`

```yaml
git_provider:
  type: gitea
  mcp_server: gitea-mcp
  base_url: https://gitea.example.com
  api_token: ${GITEA_TOKEN}

repository:
  owner: myorg
  name: myproject
  default_branch: main

agent_provider:
  type: claude
  model: claude-sonnet-4.5
  api_key: ${CLAUDE_API_KEY}
  local: true

workflow:
  plans_directory: plans/
  branching_strategy: per-agent
  auto_merge_threshold: 0.95
  max_concurrent_tasks: 3
  parallel_execution: true

tags:
  planning: needs-planning
  plan_review: plan-review
  prompt_generation: prompts
  implementation: implement
  code_review: code-review
  merge_ready: merge-ready
  needs_attention: needs-attention
  conflict_resolution: conflict-resolution
```

#### 2. Data Models

**Module**: `automation/models/`

```python
# automation/models/domain.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional

class IssueState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CODE_REVIEW = "code_review"
    MERGE_READY = "merge_ready"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Issue:
    id: int
    number: int
    title: str
    body: str
    state: IssueState
    labels: List[str]
    created_at: datetime
    updated_at: datetime
    author: str
    url: str

@dataclass
class Comment:
    id: int
    body: str
    author: str
    created_at: datetime

@dataclass
class Branch:
    name: str
    sha: str
    protected: bool = False

@dataclass
class PullRequest:
    id: int
    number: int
    title: str
    body: str
    head: str
    base: str
    state: str
    url: str
    created_at: datetime

@dataclass
class Task:
    """Represents a discrete unit of work to be executed."""
    id: str
    prompt_issue_id: int
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, any] = field(default_factory=dict)

@dataclass
class TaskResult:
    """Result of task execution."""
    success: bool
    branch: Optional[str] = None
    commits: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0

@dataclass
class Plan:
    """Structured representation of a development plan."""
    id: str
    title: str
    description: str
    tasks: List[Dict[str, any]]
    file_path: str
    created_at: datetime

@dataclass
class Review:
    """Code review result."""
    approved: bool
    comments: List[str]
    issues_found: List[Dict[str, str]]
    suggestions: List[str]
    confidence_score: float
```

#### 3. Provider Abstraction Layer

**Module**: `automation/providers/`

```python
# automation/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncIterator
from automation.models.domain import (
    Issue, Comment, Branch, PullRequest,
    Task, TaskResult, Plan, Review
)

class GitProvider(ABC):
    """Abstract interface for Git hosting providers (Gitea, GitHub, etc.)."""

    @abstractmethod
    async def get_issues(
        self,
        labels: Optional[List[str]] = None,
        state: str = "open"
    ) -> List[Issue]:
        """Retrieve issues filtered by labels and state."""
        pass

    @abstractmethod
    async def get_issue(self, issue_number: int) -> Issue:
        """Get a specific issue by number."""
        pass

    @abstractmethod
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None
    ) -> Issue:
        """Create a new issue."""
        pass

    @abstractmethod
    async def update_issue(
        self,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        state: Optional[str] = None
    ) -> Issue:
        """Update an existing issue."""
        pass

    @abstractmethod
    async def add_comment(self, issue_number: int, comment: str) -> Comment:
        """Add a comment to an issue."""
        pass

    @abstractmethod
    async def get_comments(self, issue_number: int) -> List[Comment]:
        """Get all comments for an issue."""
        pass

    @abstractmethod
    async def create_branch(self, branch_name: str, from_branch: str = "main") -> Branch:
        """Create a new branch."""
        pass

    @abstractmethod
    async def get_branch(self, branch_name: str) -> Optional[Branch]:
        """Get branch information."""
        pass

    @abstractmethod
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: Optional[List[str]] = None
    ) -> PullRequest:
        """Create a pull request."""
        pass

    @abstractmethod
    async def get_diff(self, base: str, head: str) -> str:
        """Get diff between two branches."""
        pass

    @abstractmethod
    async def get_file(self, path: str, ref: str = "main") -> str:
        """Read file contents from repository."""
        pass

    @abstractmethod
    async def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str
    ) -> str:
        """Commit a file to the repository. Returns commit SHA."""
        pass

    @abstractmethod
    async def merge_branches(
        self,
        source: str,
        target: str,
        message: Optional[str] = None
    ) -> str:
        """Merge source branch into target. Returns merge commit SHA."""
        pass


class AgentProvider(ABC):
    """Abstract interface for AI agent providers."""

    @abstractmethod
    async def execute_task(self, task: Task, context: Dict) -> TaskResult:
        """Execute a development task."""
        pass

    @abstractmethod
    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate a development plan from an issue."""
        pass

    @abstractmethod
    async def generate_prompts(self, plan: Plan) -> List[Task]:
        """Break down a plan into discrete prompts/tasks."""
        pass

    @abstractmethod
    async def review_code(self, diff: str, context: Dict) -> Review:
        """Perform code review on a diff."""
        pass

    @abstractmethod
    async def resolve_conflict(self, conflict_info: Dict) -> str:
        """Attempt to resolve merge conflicts."""
        pass
```

```python
# automation/providers/git_provider.py
from typing import List, Dict, Optional
import httpx
from automation.providers.base import GitProvider
from automation.models.domain import Issue, Comment, Branch, PullRequest
from automation.utils.mcp_client import MCPClient

class GiteaProvider(GitProvider):
    """Gitea implementation using MCP."""

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

    def _parse_issue(self, data: Dict) -> Issue:
        """Parse issue data from API response."""
        from datetime import datetime
        return Issue(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            author=data["user"]["login"],
            url=data["html_url"]
        )

    # Implement remaining abstract methods...


class GitHubProvider(GitProvider):
    """GitHub implementation for portability."""
    # Similar implementation using GitHub MCP or REST API
    pass
```

```python
# automation/providers/agent_provider.py
from typing import Dict, List
import asyncio
import subprocess
import json
from pathlib import Path
from automation.providers.base import AgentProvider
from automation.models.domain import Issue, Task, TaskResult, Plan, Review

class ClaudeLocalProvider(AgentProvider):
    """Execute tasks using local Claude Code CLI."""

    def __init__(self, model: str = "claude-sonnet-4.5", workspace: Path = None):
        self.model = model
        self.workspace = workspace or Path.cwd()

    async def execute_task(self, task: Task, context: Dict) -> TaskResult:
        """Execute task by invoking Claude Code CLI."""
        import time
        start_time = time.time()

        try:
            # Construct prompt with context
            prompt = self._build_prompt(task, context)

            # Execute via subprocess
            result = await self._run_claude(prompt, task.context.get("branch"))

            return TaskResult(
                success=result["success"],
                branch=task.context.get("branch"),
                commits=result.get("commits", []),
                files_changed=result.get("files_changed", []),
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue."""
        from datetime import datetime

        prompt = f"""
        Create a detailed development plan for the following request:

        Title: {issue.title}
        Description: {issue.body}

        Generate a structured plan with:
        1. Overview and objectives
        2. Technical approach
        3. Discrete tasks with dependencies
        4. Testing strategy
        5. Success criteria

        Format the plan in markdown with clear sections.
        """

        result = await self._run_claude(prompt)

        # Parse plan content and extract tasks
        plan_content = result["output"]
        tasks = self._extract_tasks_from_plan(plan_content)

        plan_id = f"{issue.number}"
        file_path = f"plans/{plan_id}-{self._slugify(issue.title)}.md"

        return Plan(
            id=plan_id,
            title=issue.title,
            description=issue.body,
            tasks=tasks,
            file_path=file_path,
            created_at=datetime.now()
        )

    async def generate_prompts(self, plan: Plan) -> List[Task]:
        """Break down plan into executable tasks."""
        tasks = []
        for idx, task_data in enumerate(plan.tasks, 1):
            task = Task(
                id=f"{plan.id}-{idx}",
                prompt_issue_id=0,  # Will be set when issue is created
                title=task_data["title"],
                description=task_data["description"],
                dependencies=task_data.get("dependencies", [])
            )
            tasks.append(task)
        return tasks

    async def review_code(self, diff: str, context: Dict) -> Review:
        """Perform AI code review."""
        prompt = f"""
        Review the following code changes:

        {diff}

        Context:
        - Plan: {context.get('plan_file')}
        - Task: {context.get('task_title')}

        Provide:
        1. Overall assessment (approve/request changes)
        2. Specific issues found (bugs, security, style)
        3. Suggestions for improvement
        4. Confidence score (0.0-1.0)

        Return response as JSON with keys: approved, comments, issues_found, suggestions, confidence_score
        """

        result = await self._run_claude(prompt)
        review_data = json.loads(result["output"])

        return Review(**review_data)

    async def _run_claude(self, prompt: str, branch: Optional[str] = None) -> Dict:
        """Execute Claude Code CLI command."""
        # This is a simplified version - actual implementation would use
        # proper subprocess management, output parsing, etc.
        cmd = ["claude", "code", "--model", self.model]

        if branch:
            # Ensure we're on the correct branch
            await self._checkout_branch(branch)

        # Run Claude with the prompt
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace
        )

        stdout, stderr = await proc.communicate(prompt.encode())

        if proc.returncode == 0:
            return {
                "success": True,
                "output": stdout.decode(),
                "commits": [],  # Would parse from git log
                "files_changed": []  # Would parse from git status
            }
        else:
            raise RuntimeError(f"Claude execution failed: {stderr.decode()}")

    def _build_prompt(self, task: Task, context: Dict) -> str:
        """Build comprehensive prompt for task execution."""
        return f"""
        {task.description}

        Context:
        - Plan: {context.get('plan_file')}
        - Branch: {context.get('branch')}
        - Dependencies: {', '.join(task.dependencies) if task.dependencies else 'None'}

        Implementation Guidelines:
        1. Follow the plan specifications
        2. Write clean, well-documented code
        3. Include appropriate tests
        4. Commit changes with clear messages

        When complete, ensure all changes are committed to the current branch.
        """

    def _extract_tasks_from_plan(self, plan_content: str) -> List[Dict]:
        """Parse tasks from plan markdown content."""
        # Simplified - would use more sophisticated parsing
        tasks = []
        # Look for task sections, numbered lists, etc.
        # Extract task title, description, dependencies
        return tasks

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]

    async def _checkout_branch(self, branch: str):
        """Checkout git branch."""
        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", branch,
            cwd=self.workspace
        )
        await proc.wait()


class ClaudeAPIProvider(AgentProvider):
    """Execute tasks using Claude API directly."""
    # Implementation using httpx to call Anthropic API
    pass


class OpenAIProvider(AgentProvider):
    """Execute tasks using OpenAI API."""
    # Implementation for OpenAI compatibility
    pass
```

#### 4. Workflow Engine

**Module**: `automation/engine/`

```python
# automation/engine/orchestrator.py
from typing import Dict, List, Optional
import structlog
from automation.config.settings import AutomationSettings
from automation.providers.base import GitProvider, AgentProvider
from automation.engine.state_manager import StateManager
from automation.engine.stages import (
    PlanningStage, PlanReviewStage, ImplementationStage,
    CodeReviewStage, MergeStage
)
from automation.models.domain import Issue

log = structlog.get_logger()

class WorkflowOrchestrator:
    """Coordinates the multi-stage workflow execution."""

    def __init__(
        self,
        settings: AutomationSettings,
        git_provider: GitProvider,
        agent_provider: AgentProvider,
        state_manager: StateManager
    ):
        self.settings = settings
        self.git = git_provider
        self.agent = agent_provider
        self.state = state_manager

        # Initialize stages
        self.stages = {
            "planning": PlanningStage(self.git, self.agent, self.state, settings),
            "plan_review": PlanReviewStage(self.git, self.agent, self.state, settings),
            "implementation": ImplementationStage(self.git, self.agent, self.state, settings),
            "code_review": CodeReviewStage(self.git, self.agent, self.state, settings),
            "merge": MergeStage(self.git, self.agent, self.state, settings),
        }

    async def process_issue(self, issue: Issue) -> None:
        """Route issue to appropriate stage based on labels."""
        log.info("processing_issue", issue_number=issue.number, labels=issue.labels)

        try:
            # Determine which stage to execute
            stage = self._determine_stage(issue)

            if stage:
                log.info("executing_stage", stage=stage, issue=issue.number)
                await self.stages[stage].execute(issue)
            else:
                log.warning("no_matching_stage", issue=issue.number, labels=issue.labels)

        except Exception as e:
            log.error("workflow_error", issue=issue.number, error=str(e), exc_info=True)
            await self._handle_error(issue, e)

    async def process_all_issues(self, tag: Optional[str] = None) -> None:
        """Process all issues with optional tag filter."""
        labels = [tag] if tag else None
        issues = await self.git.get_issues(labels=labels)

        log.info("processing_batch", count=len(issues), tag=tag)

        for issue in issues:
            await self.process_issue(issue)

    def _determine_stage(self, issue: Issue) -> Optional[str]:
        """Determine which stage should handle this issue."""
        tags = self.settings.tags

        if tags.planning in issue.labels:
            return "planning"
        elif tags.plan_review in issue.labels:
            return "plan_review"
        elif tags.implementation in issue.labels:
            return "implementation"
        elif tags.code_review in issue.labels:
            return "code_review"
        elif tags.merge_ready in issue.labels:
            return "merge"

        return None

    async def _handle_error(self, issue: Issue, error: Exception) -> None:
        """Handle workflow errors by creating attention-needed issues."""
        error_msg = f"""
        Automation workflow failed for issue #{issue.number}

        Error: {str(error)}

        Please review and take manual action.
        """

        await self.git.add_comment(issue.number, error_msg)

        # Add needs-attention label
        labels = issue.labels + [self.settings.tags.needs_attention]
        await self.git.update_issue(issue.number, labels=labels)
```

```python
# automation/engine/state_manager.py
from pathlib import Path
from typing import Dict, Optional
import json
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

class StateManager:
    """Manages workflow state persistence and recovery."""

    def __init__(self, state_dir: str = ".automation/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def transaction(self, plan_id: str):
        """Atomic state updates with locking."""
        if plan_id not in self._locks:
            self._locks[plan_id] = asyncio.Lock()

        async with self._locks[plan_id]:
            state = await self.load_state(plan_id)
            try:
                yield state
                await self.save_state(plan_id, state)
            except Exception as e:
                # State is not saved on exception
                raise

    async def load_state(self, plan_id: str) -> Dict:
        """Load workflow state for a plan."""
        state_file = self.state_dir / f"{plan_id}.json"

        if not state_file.exists():
            return self._create_initial_state(plan_id)

        # Use asyncio for file I/O in production
        content = state_file.read_text()
        return json.loads(content)

    async def save_state(self, plan_id: str, state: Dict) -> None:
        """Save workflow state atomically."""
        state["updated_at"] = datetime.now().isoformat()

        state_file = self.state_dir / f"{plan_id}.json"
        temp_file = state_file.with_suffix(".tmp")

        # Atomic write: write to temp, then rename
        temp_file.write_text(json.dumps(state, indent=2))
        temp_file.replace(state_file)

    async def get_active_plans(self) -> List[str]:
        """Get all plans currently in progress."""
        active = []
        for state_file in self.state_dir.glob("*.json"):
            state = json.loads(state_file.read_text())
            if state["status"] != "completed":
                active.append(state["plan_id"])
        return active

    async def mark_stage_complete(
        self,
        plan_id: str,
        stage: str,
        data: Dict
    ) -> None:
        """Mark a workflow stage as complete."""
        async with self.transaction(plan_id) as state:
            state["stages"][stage] = {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                **data
            }

            # Update overall status
            state["status"] = self._calculate_overall_status(state)

    async def mark_task_status(
        self,
        plan_id: str,
        task_id: str,
        status: str,
        data: Optional[Dict] = None
    ) -> None:
        """Update individual task status."""
        async with self.transaction(plan_id) as state:
            tasks = state["stages"]["implementation"]["tasks"]

            for task in tasks:
                if task["issue_id"] == task_id or task.get("task_id") == task_id:
                    task["status"] = status
                    if data:
                        task.update(data)
                    break

    def _create_initial_state(self, plan_id: str) -> Dict:
        """Create initial state structure for new plan."""
        return {
            "plan_id": plan_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "stages": {
                "planning": {"status": "pending"},
                "plan_review": {"status": "pending"},
                "prompts": {"status": "pending"},
                "implementation": {"status": "pending", "tasks": []},
                "code_review": {"status": "pending"},
                "merge": {"status": "pending"}
            },
            "dependencies": {}
        }

    def _calculate_overall_status(self, state: Dict) -> str:
        """Calculate overall workflow status from stage statuses."""
        stages = state["stages"]

        if all(s.get("status") == "completed" for s in stages.values()):
            return "completed"
        elif any(s.get("status") == "failed" for s in stages.values()):
            return "failed"
        elif any(s.get("status") == "in_progress" for s in stages.values()):
            return "in_progress"
        else:
            return "pending"
```

#### 5. Workflow Stages

**Module**: `automation/engine/stages/`

```python
# automation/engine/stages/base.py
from abc import ABC, abstractmethod
from automation.models.domain import Issue
from automation.providers.base import GitProvider, AgentProvider
from automation.engine.state_manager import StateManager
from automation.config.settings import AutomationSettings

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

```python
# automation/engine/stages/planning.py
import structlog
from automation.engine.stages.base import WorkflowStage
from automation.models.domain import Issue

log = structlog.get_logger()

class PlanningStage(WorkflowStage):
    """Generates development plan from planning issue."""

    async def execute(self, issue: Issue) -> None:
        """Execute planning stage."""
        log.info("planning_stage_start", issue=issue.number)

        try:
            # Generate plan using agent
            plan = await self.agent.generate_plan(issue)

            # Save plan to repository
            await self.git.commit_file(
                path=plan.file_path,
                content=self._format_plan(plan),
                message=f"Add plan for issue #{issue.number}: {issue.title}",
                branch=self.settings.repository.default_branch
            )

            # Create plan review issue
            review_issue = await self.git.create_issue(
                title=f"Review plan: {issue.title}",
                body=self._create_review_body(issue, plan),
                labels=[self.settings.tags.plan_review]
            )

            # Update original issue
            await self.git.add_comment(
                issue.number,
                f"Plan created: {plan.file_path}\n"
                f"Review issue: #{review_issue.number}"
            )

            # Update state
            await self.state.mark_stage_complete(
                plan_id=plan.id,
                stage="planning",
                data={
                    "issue_id": issue.number,
                    "plan_file": plan.file_path,
                    "review_issue_id": review_issue.number
                }
            )

            log.info("planning_stage_complete",
                    issue=issue.number,
                    plan=plan.file_path)

        except Exception as e:
            log.error("planning_stage_failed", issue=issue.number, error=str(e))
            await self._handle_stage_error(issue, e)
            raise

    def _format_plan(self, plan) -> str:
        """Format plan as markdown."""
        # Implementation would format the plan object as markdown
        pass

    def _create_review_body(self, issue: Issue, plan) -> str:
        """Create body for plan review issue."""
        return f"""
        This issue tracks the review of the plan for: #{issue.number}

        **Plan file**: `{plan.file_path}`

        **Original request**: {issue.title}

        Please review the plan and approve or request changes.

        Once approved, this will be broken down into implementation tasks.
        """
```

Implementation of remaining stages (plan_review, implementation, code_review, merge) follows similar patterns...

#### 6. Utilities

**Module**: `automation/utils/`

```python
# automation/utils/mcp_client.py
from typing import Dict, Any, Optional
import asyncio
import json

class MCPClient:
    """Client for interacting with MCP servers."""

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._process: Optional[asyncio.subprocess.Process] = None

    async def connect(self) -> None:
        """Establish connection to MCP server."""
        # Implementation depends on MCP protocol
        pass

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an MCP tool with arguments."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }

        # Send request and get response
        response = await self._send_request(request)
        return response.get("result", {})

    async def _send_request(self, request: Dict) -> Dict:
        """Send JSON-RPC request to MCP server."""
        # Actual implementation would use stdio or HTTP
        pass

    async def close(self) -> None:
        """Close connection to MCP server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
```

```python
# automation/utils/retry.py
import asyncio
from typing import TypeVar, Callable, Any
from functools import wraps
import structlog

log = structlog.get_logger()

T = TypeVar('T')

def async_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for retrying async functions with exponential backoff."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = backoff_factor ** attempt
                        log.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e)
                        )
                        await asyncio.sleep(delay)
                    else:
                        log.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e)
                        )

            raise last_exception

        return wrapper
    return decorator
```

## Project Structure

```
builder/
├── automation/
│   ├── __init__.py
│   ├── main.py                      # CLI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # Pydantic settings
│   │   └── automation_config.yaml   # Default config
│   ├── models/
│   │   ├── __init__.py
│   │   └── domain.py                # Data models
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract interfaces
│   │   ├── git_provider.py          # Gitea/GitHub implementations
│   │   └── agent_provider.py        # Claude/OpenAI implementations
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── orchestrator.py          # Workflow coordinator
│   │   ├── state_manager.py         # State persistence
│   │   └── stages/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── planning.py
│   │       ├── plan_review.py
│   │       ├── implementation.py
│   │       ├── code_review.py
│   │       └── merge.py
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── issue_handler.py         # Issue routing
│   │   ├── tag_resolver.py          # Tag validation
│   │   └── dependency_tracker.py    # Task dependencies
│   └── utils/
│       ├── __init__.py
│       ├── git_helpers.py           # Git operations
│       ├── mcp_client.py            # MCP protocol client
│       ├── retry.py                 # Retry utilities
│       └── logging_config.py        # Structured logging setup
├── plans/                           # Generated plans
├── .automation/                     # State and metadata
│   └── state/
├── .gitea/
│   └── workflows/
│       ├── automation-trigger.yaml
│       └── plan-merged.yaml
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── test_providers.py
│   │   ├── test_stages.py
│   │   └── test_state_manager.py
│   ├── integration/
│   │   └── test_workflow.py
│   └── fixtures/
│       └── sample_issues.json
├── pyproject.toml                   # Project metadata & dependencies
├── requirements.txt                 # Pinned dependencies
├── requirements-dev.txt             # Development dependencies
└── README.md
```

## Dependencies

**pyproject.toml**:
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

## Implementation Phases

### Phase 1: Foundation (MVP)
**Goal**: Basic end-to-end workflow with manual triggers

**Deliverables**:
- Configuration system with validation
- Gitea MCP provider (core methods)
- Claude local provider (basic execution)
- State manager with JSON persistence
- Planning stage (issue → plan file)
- CLI for manual execution
- Structured logging
- Unit tests for core components

**Success Criteria**:
- Can process a planning issue manually
- Generates valid plan file
- State is persisted correctly
- All tests pass

### Phase 2: Core Workflow
**Goal**: Complete automated workflow pipeline

**Deliverables**:
- All workflow stages implemented
- Branching strategies (per-plan, per-agent)
- Dependency tracking
- Issue routing by tags
- Code review integration
- PR creation
- Integration tests

**Success Criteria**:
- Complete issue → plan → implement → review → PR flow
- Handles dependencies correctly
- Both branching strategies work
- Integration tests pass

### Phase 3: Gitea Actions Integration
**Goal**: Automated execution via Gitea Actions

**Deliverables**:
- Gitea Actions workflow files
- Event-based triggers
- Secrets management
- Action execution mode
- Webhook support (optional)

**Success Criteria**:
- Workflows trigger automatically on issue events
- Secrets are secure
- Actions complete successfully
- Manual intervention only for final merge

### Phase 4: Advanced Features
**Goal**: Production-ready with monitoring and recovery

**Deliverables**:
- Failure recovery and retry logic
- Parallel task execution
- Monitoring dashboard
- Metrics collection
- Multi-repository support
- Additional providers (GitHub, OpenAI)
- Performance optimizations

**Success Criteria**:
- Handles failures gracefully
- Parallel execution works correctly
- Monitoring provides visibility
- Production-ready reliability

## Key Improvements from Python Expert Review

### Architecture Improvements

1. **Pydantic for Configuration**: Using `pydantic-settings` instead of raw YAML provides:
   - Automatic validation with clear error messages
   - Type safety throughout the application
   - Environment variable interpolation
   - IDE autocomplete support

2. **Proper Data Models**: Using `@dataclass` for domain models provides:
   - Type hints for all attributes
   - Immutability options
   - Built-in serialization support
   - Clear documentation through types

3. **Async-First Design**: All I/O operations use `async/await`:
   - Properly handles concurrent operations
   - Efficient resource usage
   - Non-blocking MCP calls
   - Scalable to many parallel tasks

4. **State Management with Transactions**:
   - Atomic state updates using context managers
   - File-level locking prevents race conditions
   - Atomic writes (write-to-temp, then rename)
   - Crash-safe state persistence

5. **Structured Logging**: Using `structlog` provides:
   - Consistent log format
   - Easy filtering and analysis
   - Context-aware logging
   - JSON output for log aggregation

6. **Proper Error Handling**:
   - Retry decorator with exponential backoff
   - Graceful degradation
   - Error context preserved
   - Recovery mechanisms

7. **Type Safety**: Full type annotations for:
   - Better IDE support
   - Early error detection with mypy
   - Self-documenting code
   - Refactoring safety

### Testing Strategy

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test workflow stages together
3. **Fixtures**: Reusable test data and mocks
4. **Async Testing**: Using `pytest-asyncio`
5. **Coverage**: Aim for >80% code coverage

### Code Quality Tools

1. **Black**: Automatic code formatting
2. **Ruff**: Fast Python linter (replaces flake8, isort, etc.)
3. **Mypy**: Static type checking
4. **Pytest**: Modern testing framework

### Best Practices Applied

1. **Dependency Injection**: Providers injected into stages
2. **Abstract Base Classes**: Clear contracts for providers
3. **Single Responsibility**: Each module has one clear purpose
4. **DRY Principle**: Common functionality in base classes
5. **Explicit is Better than Implicit**: Clear parameter names, no magic
6. **Fail Fast**: Validate configuration at startup
7. **Logging not Printing**: Structured logs for production
8. **Context Managers**: For resource management (locks, transactions)
9. **Type Hints**: Throughout the codebase
10. **Docstrings**: For public APIs

### Potential Issues Addressed

1. **Race Conditions**: State locking prevents concurrent writes
2. **Partial Failures**: Transaction-based state updates
3. **Resource Leaks**: Proper async context managers
4. **Error Context Loss**: Structured logging preserves context
5. **Configuration Errors**: Pydantic validation catches issues early
6. **Type Errors**: Mypy catches type mismatches
7. **Merge Conflicts**: Explicit handling in merge stage
8. **MCP Failures**: Retry logic with backoff

## Security Considerations

1. **Secrets Management**:
   - Use Pydantic `SecretStr` for sensitive values
   - Never log secret values
   - Environment variables for all tokens
   - Gitea Actions secrets for CI/CD

2. **Code Execution**:
   - Sandboxed agent execution
   - Validate all git operations
   - Review PRs before merge
   - Audit trail in git history

3. **Input Validation**:
   - Pydantic validates all configuration
   - Validate issue content before processing
   - Sanitize file paths
   - Prevent directory traversal

4. **Rate Limiting**:
   - Respect API rate limits
   - Exponential backoff on errors
   - Queue management for tasks
   - Monitor API usage

## Monitoring & Observability

### Structured Logging

```python
# automation/utils/logging_config.py
import structlog

def configure_logging(log_level: str = "INFO"):
    """Configure structured logging."""
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
```

### Metrics to Track

- Workflow duration by stage
- Success/failure rates
- Task execution time
- API call counts and latency
- Queue depth
- Active workflows
- Error frequency by type

### Observability Tools

- Structured logs → Log aggregation (e.g., Loki, Elasticsearch)
- Metrics → Prometheus/Grafana
- Tracing → OpenTelemetry (future enhancement)
- Health checks → HTTP endpoint

## Future Enhancements

- **Multi-Repository**: Handle workflows across multiple repos
- **Cross-Plan Dependencies**: Plans that depend on other plans
- **Cost Optimization**: Use cheaper models for simple tasks
- **Learning System**: Improve prompts based on review feedback
- **Web Dashboard**: React/Vue UI for workflow visualization
- **Notifications**: Slack/Discord/Email integration
- **Advanced Scheduling**: Priority queues, SLA tracking
- **A/B Testing**: Compare different agent providers
- **Observability**: Full OpenTelemetry integration
- **Performance**: Caching, connection pooling, batch operations
