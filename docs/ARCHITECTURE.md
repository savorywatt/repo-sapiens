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

### 1. Configuration System (`repo_sapiens/config/`)

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
from repo_sapiens.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("config.yaml")
git_config = settings.git_provider
api_token = git_config.api_token  # Automatically resolved from credentials
```

### 2. Credential Management (`repo_sapiens/credentials/`)

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
from repo_sapiens.credentials.resolver import CredentialResolver

resolver = CredentialResolver()

# Resolve from environment variable
token = resolver.resolve("${SAPIENS_GITHUB_TOKEN}")

# Resolve from keyring
password = resolver.resolve("@keyring:github/password")

# Resolve from encrypted storage
secret = resolver.resolve("@encrypted:api/secret_key")
```

### 3. Git Operations (`repo_sapiens/git/`)

**Purpose**: Abstracted Git provider interface for multiple hosting platforms.

**Key Classes**:
- `GitProvider`: Abstract base class for Git providers
- `GiteaRestProvider`: Gitea-specific implementation using REST API
- `GitHubRestProvider`: GitHub-specific implementation using REST API
- `GitLabRestProvider`: GitLab-specific implementation using REST API v4
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
from repo_sapiens.providers.gitea_rest import GiteaRestProvider

provider = GiteaRestProvider(base_url="https://git.example.com", token="token")

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

**GitLab Provider Example**:
```python
from repo_sapiens.providers.gitlab_rest import GitLabRestProvider

# GitLab uses PRIVATE-TOKEN header for authentication
provider = GitLabRestProvider(
    base_url="https://gitlab.com",  # or self-hosted
    token="your-personal-access-token",
    owner="namespace",  # can be nested: "group/subgroup"
    repo="project-name"
)

async with provider:
    # Get issues (GitLab uses 'iid' internally, mapped to 'number')
    issues = await provider.get_issues(labels=["needs-planning"])

    # Create merge request (GitLab terminology for PR)
    mr = await provider.create_pull_request(
        title="Feature: New capability",
        body="Description here",
        head="feature-branch",
        base="main"
    )
```

**GitLab API Differences**:
- Uses `iid` (internal ID) for project-scoped issue/MR numbers
- Uses `description` instead of `body` for issue content
- Uses `opened`/`closed` states instead of `open`/`closed`
- Uses `notes` for comments (system notes are filtered out)
- Uses `merge_requests` instead of `pull_requests`
- Project path must be URL-encoded in API calls

### 4. Agent Providers (`repo_sapiens/providers/`)

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
from repo_sapiens.providers.external_agent import ExternalAgentProvider

agent = ExternalAgentProvider(api_key="key", model="claude-3-sonnet")

# Request code review
review = await agent.request(
    prompt="Review this code for bugs",
    context={"code": "..."},
    temperature=0.5
)
```

### 5. Template Rendering (`repo_sapiens/rendering/`)

**Purpose**: Safe, secure Jinja2 template rendering for code generation and configuration.

**Key Classes**:
- `SecureTemplateEngine`: Jinja2 template processor with security sandboxing
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
from repo_sapiens.rendering.engine import SecureTemplateEngine

engine = SecureTemplateEngine()

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

### 6. Workflow Engine (`repo_sapiens/engine/`)

**Purpose**: Orchestrates multi-stage automated workflows with state management.

**Key Classes**:
- `WorkflowOrchestrator`: Coordinates overall workflow execution
- `StateManager`: Persists and manages execution state
- `PipelineStages`: Individual workflow stages (proposal, planning, implementation, review, etc.)
- `ParallelExecutor`: Handles parallel task execution
- `CheckpointManager`: Saves checkpoints for recovery

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
from repo_sapiens.engine.orchestrator import WorkflowOrchestrator
from repo_sapiens.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("config.yaml")
orchestrator = WorkflowOrchestrator(settings)

# Process an issue through the workflow
await orchestrator.process_issue(issue)
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
                return GitHubRestProvider(
                    base_url=config.base_url,
                    api_token=config.api_token
                )
            case "gitlab":
                return GitLabRestProvider(
                    base_url=config.base_url,
                    token=config.api_token,
                    owner=config.owner,
                    repo=config.repo
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
(e.g., "${SAPIENS_GITHUB_TOKEN}")
    ↓
CredentialResolver.resolve()
    ↓
Try each backend in order:
    ├─ EnvironmentBackend.can_handle("${...}") → Yes
    │   │
    │   └─ Extract VAR_NAME
    │       │
    │       └─ os.environ["SAPIENS_GITHUB_TOKEN"]
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
WorkflowOrchestrator.process_issue()
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
from repo_sapiens.credentials.backend import CredentialBackend

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
from repo_sapiens.credentials.resolver import CredentialResolver
from myapp.credentials.s3_backend import S3CredentialBackend

resolver = CredentialResolver(backends=[
    EnvironmentBackend(),
    KeyringBackend(),
    S3CredentialBackend(bucket="secrets-bucket"),
])
```

### 2. Adding New Git Providers

Create a provider for a new Git hosting service. The existing `GitLabRestProvider` serves as a good example:

```python
# repo_sapiens/providers/your_provider.py
from repo_sapiens.providers.base import GitProvider

class YourGitProvider(GitProvider):
    """Your custom Git provider implementation."""

    def __init__(self, base_url: str, token: str, owner: str, repo: str):
        self.base_url = base_url
        self.token = token
        self.owner = owner
        self.repo = repo

    async def connect(self) -> None:
        """Initialize connection and verify connectivity."""
        # Set up HTTP client with authentication headers
        ...

    async def get_issues(self, labels: list[str] | None = None, state: str = "open") -> list[Issue]:
        """Retrieve issues from the provider."""
        # Provider-specific API implementation
        ...

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> PullRequest:
        """Create a pull/merge request."""
        # Provider-specific implementation
        ...
```

**Existing providers for reference**:
- `GiteaRestProvider`: Gitea REST API
- `GitHubRestProvider`: GitHub REST API
- `GitLabRestProvider`: GitLab REST API v4 (demonstrates handling of terminology differences like merge requests vs pull requests)

### 3. Custom Template Filters

Add custom Jinja2 filters:

```python
# repo_sapiens/rendering/custom_filters.py
def markdown_to_html(value: str) -> str:
    """Convert Markdown to HTML."""
    import markdown
    return markdown.markdown(value)

def count_occurrences(value: str, substring: str) -> int:
    """Count substring occurrences."""
    return value.count(substring)

# Register filters by creating a custom engine with additional filters
from repo_sapiens.rendering.engine import SecureTemplateEngine

# Custom filters are registered in the engine's Jinja2 environment
engine = SecureTemplateEngine()
# Access the underlying Jinja2 environment to add custom filters:
engine.env.filters["markdown"] = markdown_to_html
engine.env.filters["count"] = count_occurrences

# Use in templates
template = "{{ content | markdown }}"
result = engine.render(template, context={"content": "# Hello"})
```

### 4. Custom Workflow Stages

Create specialized workflow stages:

```python
# repo_sapiens/engine/stages/custom_stage.py
from repo_sapiens.engine.stages.base import WorkflowStage

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
# repo_sapiens/config/automation_config.yaml
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
from repo_sapiens.config.settings import AutomationSettings

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
