# Architecture Overview

repo-sapiens is an intelligent repository automation and management tool designed for Gitea, GitHub, and other Git providers. This document describes the system architecture, core components, design patterns, and data flow.

## Table of Contents

- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Design Patterns](#design-patterns)
- [Data Flow](#data-flow)
- [Extension Points](#extension-points)
- [Configuration System](#configuration-system)
- [Deployment Architecture](#deployment-architecture)

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Interface                           │
│  (automation command with various subcommands)               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│            Configuration & Credentials Layer                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ AutomationSettings - Pydantic-based configuration    │   │
│  │ CredentialResolver - Multi-backend credential mgmt  │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│           Workflow Orchestration Engine                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ WorkflowOrchestrator - Orchestrates workflow stages  │   │
│  │ StateManager - Tracks execution state                │   │
│  │ PipelineStages - Individual processing stages        │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬──────────────┐
        │            │            │              │
┌───────▼──┐ ┌──────▼──┐ ┌──────▼──┐ ┌────────▼────┐
│    Git   │ │ Agent   │ │Template │ │  Credential │
│ Provider │ │Provider │ │Rendering│ │   Backends  │
│          │ │         │ │         │ │             │
└──────────┘ └─────────┘ └─────────┘ └─────────────┘
```

## Core Components

### 1. Configuration System (`automation/config/`)

**Purpose**: Type-safe, centralized configuration management using Pydantic.

**Key Classes**:
- `AutomationSettings`: Main configuration container
- `GitProviderConfig`: Git provider settings (Gitea, GitHub, etc.)
- `AgentConfig`: AI agent configuration
- `WorkflowConfig`: Workflow definitions
- `TagConfig`: Repository tag definitions

**Features**:
- YAML-based configuration files
- Credential reference support (`@keyring:`, `${ENV}`, `@encrypted:`)
- Type validation with Pydantic
- Environment variable interpolation

**Example**:
```python
from automation.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("config.yaml")
git_config = settings.git_provider
api_token = git_config.api_token  # Automatically resolved from credentials
```

### 2. Credential Management (`automation/credentials/`)

**Purpose**: Secure, flexible credential storage and retrieval with multiple backends.

**Architecture**:

```
┌──────────────────────────────────────────┐
│     CredentialResolver (Interface)       │
└────────────┬─────────────────────────────┘
             │
    ┌────────┼────────┬─────────────┐
    │        │        │             │
┌───▼──┐ ┌──▼───┐ ┌──▼──┐ ┌──────▼──┐
│Env   │ │Key-  │ │Encr.│ │Custom  │
│Var   │ │ring  │ │Cred │ │Backend │
└──────┘ └──────┘ └─────┘ └────────┘
```

**Key Classes**:
- `CredentialResolver`: Main resolver coordinating multiple backends
- `EnvironmentBackend`: Resolves from environment variables (`${VAR}`)
- `KeyringBackend`: Resolves from system keyring (`@keyring:service/account`)
- `EncryptedBackend`: Resolves from encrypted config files (`@encrypted:key`)
- `CredentialBackend`: Abstract base for custom implementations

**Design Pattern**: **Strategy Pattern**
- Each backend implements the same interface
- Resolver uses appropriate backend based on credential reference format
- Easy to add new backends by extending `CredentialBackend`

**Usage**:
```python
from automation.credentials.resolver import CredentialResolver

resolver = CredentialResolver()

# Resolve from environment variable
token = resolver.resolve("${GITHUB_TOKEN}")

# Resolve from keyring
password = resolver.resolve("@keyring:github/password")

# Resolve from encrypted storage
secret = resolver.resolve("@encrypted:api/secret_key")
```

### 3. Git Operations (`automation/git/`)

**Purpose**: Abstracted Git provider interface for multiple hosting platforms.

**Key Classes**:
- `GitProvider`: Abstract base class for Git providers
- `GiteaRestProvider`: Gitea-specific implementation using REST API
- `GitDiscovery`: Discovers repositories and metadata
- `GitParser`: Parses Git operations and configurations

**Features**:
- Unified interface across multiple providers
- Async/await support for non-blocking operations
- Repository discovery and enumeration
- Branch and tag management
- Pull request operations

**Example**:
```python
from automation.providers.gitea_rest import GiteaRestProvider

provider = GiteaRestProvider(base_url="https://git.example.com", token="token")

# Discover repositories
repos = await provider.discover_repositories(owner="team")

# Fetch repository details
repo = await provider.get_repository("owner", "repo-name")

# Create pull request
pr = await provider.create_pull_request(
    owner="owner",
    repo="repo",
    title="Feature: New capability",
    description="...",
    head="feature-branch",
    base="main"
)
```

### 4. Agent Providers (`automation/providers/`)

**Purpose**: Interface with AI agents for intelligent automation decisions.

**Key Classes**:
- `AgentProvider`: Abstract base for agent implementations
- `ExternalAgentProvider`: Communicates with external AI services
- `OllamaProvider`: Integration with Ollama local LLMs
- `MCP Client`: Communicates with Claude/other MCP servers

**Features**:
- Multiple agent backends
- Request/response formatting
- Streaming support
- Error handling and retry logic

**Example**:
```python
from automation.providers.external_agent import ExternalAgentProvider

agent = ExternalAgentProvider(api_key="key", model="claude-3-sonnet")

# Request code review
review = await agent.request(
    prompt="Review this code for bugs",
    context={"code": "..."},
    temperature=0.5
)
```

### 5. Template Rendering (`automation/rendering/`)

**Purpose**: Safe, secure Jinja2 template rendering for code generation and configuration.

**Key Classes**:
- `TemplateEngine`: Jinja2 template processor
- `TemplateValidator`: Validates template syntax and security
- `SecurityFilter`: Prevents template injection attacks
- Custom filters: `truncate_lines`, `format_code`, `escape_*`

**Features**:
- Custom filters and functions
- Security sandboxing
- Escape handling for multiple output formats
- Template caching for performance

**Example**:
```python
from automation.rendering.engine import TemplateEngine

engine = TemplateEngine()

template = """
// Generated by repo-sapiens
function {{ function_name }}({{ parameters }}) {
  // Implementation
  return {{ return_value }};
}
"""

rendered = engine.render(template, context={
    "function_name": "getUserData",
    "parameters": "userId: string",
    "return_value": "{}"
})
```

### 6. Workflow Engine (`automation/engine/`)

**Purpose**: Orchestrates multi-stage automated workflows with state management.

**Key Classes**:
- `WorkflowOrchestrator`: Coordinates overall workflow execution
- `StateManager`: Persists and manages execution state
- `PipelineStages`: Individual workflow stages (proposal, planning, implementation, review, etc.)
- `ParallelExecutor`: Handles parallel task execution
- `CheckpointingManager`: Saves checkpoints for recovery

**Architecture**:

```
WorkflowOrchestrator
  │
  ├─ Stage: Proposal       (Create initial plan)
  ├─ Stage: Planning       (Develop detailed plan)
  ├─ Stage: Implementation (Execute changes)
  ├─ Stage: Code Review    (AI code review)
  ├─ Stage: PR Review      (Handle PR feedback)
  ├─ Stage: QA             (Quality assurance)
  ├─ Stage: Approval       (Wait for approval)
  └─ Stage: Merge          (Merge to main branch)
```

**Features**:
- Async workflow execution
- Error recovery with checkpointing
- State persistence
- Parallel execution where possible
- Approval workflows

**Example**:
```python
from automation.engine.orchestrator import WorkflowOrchestrator
from automation.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("config.yaml")
orchestrator = WorkflowOrchestrator(settings)

# Execute workflow
result = await orchestrator.execute_workflow(
    task="Implement feature X",
    repository="owner/repo",
    target_branch="main"
)
```

## Design Patterns

### 1. Dependency Injection

The system uses explicit dependency injection to promote testability and loose coupling.

**Example**:
```python
class CredentialResolver:
    def __init__(self, backends: list[CredentialBackend] | None = None):
        """Initialize resolver with backends.

        If no backends provided, uses sensible defaults.
        """
        self.backends = backends or [
            EnvironmentBackend(),
            KeyringBackend(),
            EncryptedBackend(),
        ]
```

**Testing**:
```python
from unittest.mock import Mock

def test_credential_resolution():
    # Inject mock backend
    mock_backend = Mock(spec=CredentialBackend)
    mock_backend.resolve.return_value = "test-token"

    resolver = CredentialResolver(backends=[mock_backend])
    result = resolver.resolve("@test:key")

    assert result == "test-token"
    mock_backend.resolve.assert_called_once()
```

### 2. Strategy Pattern (Credential Backends)

Each credential backend implements the same interface, allowing runtime selection.

```python
# Abstract interface
class CredentialBackend(ABC):
    @abstractmethod
    async def resolve(self, reference: str) -> str:
        """Resolve credential reference."""
        pass

    @abstractmethod
    def can_handle(self, reference: str) -> bool:
        """Check if this backend can handle the reference."""
        pass

# Concrete implementations
class EnvironmentBackend(CredentialBackend):
    def can_handle(self, reference: str) -> bool:
        return reference.startswith("${") and reference.endswith("}")

    async def resolve(self, reference: str) -> str:
        # ${VAR_NAME} → os.environ["VAR_NAME"]
        ...

class KeyringBackend(CredentialBackend):
    def can_handle(self, reference: str) -> bool:
        return reference.startswith("@keyring:")

    async def resolve(self, reference: str) -> str:
        # @keyring:service/account → keyring.get_password(...)
        ...
```

### 3. Factory Pattern (Provider Creation)

Providers are created based on configuration without exposing implementation details.

```python
class ProviderFactory:
    @staticmethod
    def create_git_provider(config: GitProviderConfig) -> GitProvider:
        """Create appropriate Git provider from configuration."""
        match config.provider_type:
            case "gitea":
                return GiteaRestProvider(
                    base_url=config.base_url,
                    api_token=config.api_token
                )
            case "github":
                return GitHubProvider(
                    base_url=config.base_url,
                    api_token=config.api_token
                )
            case _:
                raise ValueError(f"Unknown provider: {config.provider_type}")
```

### 4. Pipeline/Chain of Responsibility

Workflows execute as a series of stages, each responsible for one aspect.

```python
class WorkflowStage(ABC):
    @abstractmethod
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        """Execute this stage, returning updated context."""
        pass

    @abstractmethod
    async def validate_preconditions(self, context: ExecutionContext) -> bool:
        """Check if stage can execute."""
        pass

# Orchestrator chains stages
stages = [
    ProposalStage(),
    PlanningStage(),
    ImplementationStage(),
    CodeReviewStage(),
    ApprovalStage(),
    MergeStage(),
]

for stage in stages:
    if await stage.validate_preconditions(context):
        context = await stage.execute(context)
    else:
        break  # Cannot continue workflow
```

## Data Flow

### 1. Configuration Loading

```
YAML File
    ↓
AutomationSettings.from_yaml()
    ↓
Pydantic Validation
    ↓
CredentialResolver resolves references
    │
    ├─ ${VAR} → Environment Variables
    ├─ @keyring:service/account → System Keyring
    └─ @encrypted:key → Encrypted Storage
    ↓
AutomationSettings Object
(with all credentials resolved)
    ↓
Application Use
```

**Example Flow**:
```yaml
# config.yaml
git_provider:
  provider_type: gitea
  base_url: https://git.example.com
  api_token: ${GITEA_API_TOKEN}

agent:
  model: claude-3-sonnet
  api_key: @keyring:anthropic/api_key
```

```python
# Load and resolve
settings = AutomationSettings.from_yaml("config.yaml")
# settings.git_provider.api_token → environment value
# settings.agent.api_key → keyring value
```

### 2. Credential Resolution Flow

```
Reference String
(e.g., "${GITHUB_TOKEN}")
    ↓
CredentialResolver.resolve()
    ↓
Try each backend in order:
    ├─ EnvironmentBackend.can_handle("${...}") → Yes
    │   │
    │   └─ Extract VAR_NAME
    │       │
    │       └─ os.environ["GITHUB_TOKEN"]
    │           ↓
    │           Return value
    │
    ├─ OR KeyringBackend.can_handle("@keyring:...") → Yes
    │   │
    │   └─ keyring.get_password("service", "account")
    │       ↓
    │       Return value
    │
    └─ OR EncryptedBackend.can_handle("@encrypted:...") → Yes
        │
        └─ Decrypt from storage
            ↓
            Return value
```

### 3. Workflow Execution Flow

```
Trigger
(Manual/Webhook/Scheduled)
    ↓
WorkflowOrchestrator.execute_workflow()
    ↓
StateManager: Load previous state if recovering
    ↓
ProposalStage
    ├─ Analyze task
    ├─ Consult agent
    └─ Create initial plan
    ↓ (save checkpoint)
    ↓
PlanningStage
    ├─ Refine plan
    ├─ Break down tasks
    └─ Estimate effort
    ↓ (save checkpoint)
    ↓
ImplementationStage
    ├─ Clone repository
    ├─ Create feature branch
    ├─ Make changes
    └─ Commit and push
    ↓ (save checkpoint)
    ↓
CodeReviewStage
    ├─ Request AI code review
    ├─ Process feedback
    └─ Make corrections if needed
    ↓ (save checkpoint)
    ↓
ApprovalStage
    ├─ Create pull request
    └─ Wait for approval (or auto-approve)
    ↓ (save checkpoint)
    ↓
MergeStage
    ├─ Merge pull request
    ├─ Delete feature branch
    └─ Update documentation
    ↓
Complete
(Notify user)
```

### 4. Template Rendering Flow

```
Template Source
(Jinja2 string)
    ↓
TemplateEngine.render()
    ↓
Parse template syntax
    ↓
Validate for injection vulnerabilities
    ↓
Compile template with custom filters/functions
    ↓
Execute with context data
    │
    ├─ Filter: truncate_lines
    ├─ Filter: format_code
    └─ Filter: escape_html/sql/python
    ↓
Rendered Output
(e.g., Python code, documentation)
```

## Extension Points

### 1. Adding New Credential Backends

Create a custom credential backend:

```python
# myapp/credentials/s3_backend.py
from automation.credentials.backend import CredentialBackend

class S3CredentialBackend(CredentialBackend):
    """Resolve credentials stored in AWS S3."""

    def __init__(self, bucket: str):
        self.bucket = bucket

    def can_handle(self, reference: str) -> bool:
        """Handle @s3:path/to/secret format."""
        return reference.startswith("@s3:")

    async def resolve(self, reference: str) -> str:
        """Fetch credential from S3."""
        path = reference[4:]  # Remove "@s3:" prefix

        import boto3
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=self.bucket, Key=path)
        return response["Body"].read().decode("utf-8")
```

Register in your application:

```python
from automation.credentials.resolver import CredentialResolver
from myapp.credentials.s3_backend import S3CredentialBackend

resolver = CredentialResolver(backends=[
    EnvironmentBackend(),
    KeyringBackend(),
    S3CredentialBackend(bucket="secrets-bucket"),
])
```

### 2. Adding New Git Providers

Create a provider for a new Git hosting service:

```python
# automation/providers/gitlab_provider.py
from automation.providers.base import GitProvider

class GitLabProvider(GitProvider):
    """GitLab-specific Git operations."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.api_token = api_token

    async def get_repository(self, owner: str, repo: str) -> RepositoryInfo:
        """Fetch repository details from GitLab."""
        # GitLab API implementation
        ...

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        description: str,
        head: str,
        base: str,
    ) -> PullRequestInfo:
        """Create merge request on GitLab."""
        # GitLab MR creation
        ...
```

### 3. Custom Template Filters

Add custom Jinja2 filters:

```python
# automation/rendering/custom_filters.py
def markdown_to_html(value: str) -> str:
    """Convert Markdown to HTML."""
    import markdown
    return markdown.markdown(value)

def count_occurrences(value: str, substring: str) -> int:
    """Count substring occurrences."""
    return value.count(substring)

# Register in engine
from automation.rendering.engine import TemplateEngine

engine = TemplateEngine()
engine.add_filter("markdown", markdown_to_html)
engine.add_filter("count", count_occurrences)

# Use in templates
template = "{{ content | markdown }}"
result = engine.render(template, context={"content": "# Hello"})
```

### 4. Custom Workflow Stages

Create specialized workflow stages:

```python
# automation/engine/stages/custom_stage.py
from automation.engine.stages.base import WorkflowStage

class DatabaseMigrationStage(WorkflowStage):
    """Handle database migration checks before merge."""

    async def validate_preconditions(self, context: ExecutionContext) -> bool:
        """Check if database changes are present."""
        changes = context.get("file_changes", [])
        return any(f.startswith("migrations/") for f in changes)

    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        """Validate and document database changes."""
        # Check migration syntax
        # Generate migration rollback plan
        # Document schema changes

        context["migration_validated"] = True
        return context
```

## Configuration System

### Configuration File Structure

```yaml
# automation/config/automation_config.yaml
git_provider:
  provider_type: gitea
  base_url: https://git.example.com
  api_token: ${GITEA_API_TOKEN}
  mcp_server: gitea-mcp

agent:
  provider: external
  model: claude-3-sonnet
  api_key: @keyring:anthropic/api_key
  temperature: 0.5
  max_tokens: 4096

workflow:
  auto_approve: false
  auto_merge: false
  approval_timeout_hours: 24
  enable_recovery: true

tags:
  - name: "automated"
    description: "Changes made by repo-sapiens"
    color: "#0366d6"
  - name: "needs-review"
    description: "Requires manual review"
    color: "#fb8500"

repositories:
  - owner: myorg
    names:
      - repo1
      - repo2
    exclude:
      - repo-template
```

### Type-Safe Access

```python
from automation.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("config.yaml")

# Typed access
git_provider = settings.git_provider  # GitProviderConfig
agent_config = settings.agent  # AgentConfig
workflow_config = settings.workflow  # WorkflowConfig

# IDE autocomplete and type checking
base_url: HttpUrl = git_provider.base_url
api_token: str = git_provider.api_token
model: str = agent_config.model
```

## Deployment Architecture

### Development Environment

```
Source Code
    ↓
Virtual Environment (.venv/)
    ↓
Editable Install (pip install -e .)
    ↓
Local Testing & Development
```

### Production Deployment

```
Docker Image / Package Installation
    ↓
Configuration Files (YAML)
    ↓
Credential Backends (Keyring/Encrypted/ENV)
    ↓
Running Instance
    ├─ CLI mode (one-off commands)
    ├─ Webhook server mode (listening for triggers)
    └─ Scheduled mode (periodic execution)
    ↓
Git Provider (Gitea/GitHub/GitLab)
    ↓
Agent Service (Claude/Ollama/etc.)
```

### Environment Variables

Key environment variables:

```bash
# Logging
LOG_LEVEL=INFO

# Git Provider
GITEA_API_TOKEN=<token>
GITEA_BASE_URL=https://git.example.com

# Agent API
ANTHROPIC_API_KEY=<key>

# Credentials
ENCRYPTION_KEY=<base64-encoded-key>

# Runtime
WORKER_THREADS=4
CACHE_SIZE_MB=512
```

---

## Summary

repo-sapiens is built on a foundation of:

- **Separation of Concerns**: Each component handles one responsibility
- **Dependency Injection**: Loose coupling enables testing and flexibility
- **Strategy Pattern**: Multiple implementations of the same interface
- **Async-First Design**: Non-blocking I/O for scalability
- **Type Safety**: Full type hints throughout
- **Configurability**: Flexible configuration with credential management

This architecture enables:

- Easy testing with mock dependencies
- Simple addition of new providers and backends
- Parallel execution of independent tasks
- Secure credential management
- Clear data flow and lifecycle management
- Production-ready error handling and recovery
