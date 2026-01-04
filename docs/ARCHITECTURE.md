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
- `CredentialResolver`: Main resolver with centralized pattern matching
- `EnvironmentBackend`: Simple storage for environment variables
- `KeyringBackend`: Simple storage for system keyring
- `EncryptedFileBackend`: Simple storage for encrypted credential files
- `CredentialBackend`: Protocol defining the storage interface

**Design Pattern**: **Strategy Pattern with Centralized Routing**
- The `CredentialResolver` owns all pattern matching logic (regex-based)
- Each backend implements a simple storage interface (`get`, `set`, `delete`)
- Backends don't need to understand reference formats--they only store/retrieve
- See [Design Decisions](#credential-backend-interface) for rationale

**Usage**:
```python
from repo_sapiens.credentials.resolver import CredentialResolver

resolver = CredentialResolver()

# Resolve from environment variable
token = resolver.resolve("${GITHUB_TOKEN}")

# Resolve from keyring
password = resolver.resolve("@keyring:github/password")

# Resolve from encrypted storage
secret = resolver.resolve("@encrypted:api/secret_key")
```

### 3. Git Operations

**Purpose**: Abstracted Git provider interface for multiple hosting platforms.

**Key Classes**:
- `GitProvider`: Abstract base class for Git providers (`repo_sapiens/providers/base.py`)
- `GiteaRestProvider`: Gitea-specific implementation using REST API (`repo_sapiens/providers/gitea_rest.py`)
- `GitDiscovery`: Discovers repositories and metadata (`repo_sapiens/git/`)
- `GitParser`: Parses Git operations and configurations (`repo_sapiens/git/`)

**Note:** Git providers are in `repo_sapiens/providers/` alongside agent providers,
while Git utilities (discovery, parsing) remain in `repo_sapiens/git/`.

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
- `SecureTemplateEngine`: Jinja2 template processor
- `TemplateValidator`: Validates template syntax and security
- `SecurityFilter`: Prevents template injection attacks
- Custom filters: `truncate_lines`, `format_code`, `escape_*`

**Features**:
- Custom filters and functions
- Security sandboxing
- Escape handling for multiple output formats
- Template caching for performance

**Note:** The engine is named `SecureTemplateEngine` to emphasize its
sandboxed, security-focused design using Jinja2's `SandboxedEnvironment`.

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

The orchestrator uses explicit dependency injection, requiring a Git provider, agent provider, and state manager to be passed at construction time. This design promotes testability and allows flexible composition of different provider implementations.

**Example**:
```python
from repo_sapiens.engine.orchestrator import WorkflowOrchestrator
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.providers.factory import create_git_provider, create_agent_provider

settings = AutomationSettings.from_yaml("config.yaml")

# Create dependencies (orchestrator uses dependency injection)
git = create_git_provider(settings)
agent = create_agent_provider(settings)
state = StateManager(settings.state_dir)

# Create orchestrator
orchestrator = WorkflowOrchestrator(settings, git, agent, state)

# Process all issues with a specific label
await orchestrator.process_all_issues(tag="needs-planning")

# Or process a single issue
issue = await git.get_issue(42)
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
    # Inject mock backend for keyring
    mock_keyring = Mock(spec=CredentialBackend)
    mock_keyring.available = True
    mock_keyring.get.return_value = "test-token"

    resolver = CredentialResolver()
    resolver.keyring_backend = mock_keyring
    result = resolver.resolve("@keyring:service/key")

    assert result == "test-token"
    mock_keyring.get.assert_called_once_with("service", "key")
```

### 2. Strategy Pattern (Credential Backends)

Credential backends implement a simple storage Protocol. The resolver handles
pattern matching centrally, then delegates to the appropriate backend.

```python
# Protocol interface (simple storage operations)
class CredentialBackend(Protocol):
    @property
    def name(self) -> str:
        """Backend identifier (e.g., 'keyring', 'environment')."""
        ...

    @property
    def available(self) -> bool:
        """Check if this backend is available on the current system."""
        ...

    def get(self, service: str, key: str) -> str | None:
        """Retrieve a credential."""
        ...

    def set(self, service: str, key: str, value: str) -> None:
        """Store a credential."""
        ...

    def delete(self, service: str, key: str) -> bool:
        """Delete a credential."""
        ...

# Resolver handles pattern matching centrally
class CredentialResolver:
    KEYRING_PATTERN = re.compile(r"^@keyring:([^/]+)/(.+)$")
    ENV_PATTERN = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")
    ENCRYPTED_PATTERN = re.compile(r"^@encrypted:([^/]+)/(.+)$")

    def resolve(self, value: str) -> str:
        if match := self.KEYRING_PATTERN.match(value):
            return self.keyring_backend.get(match.group(1), match.group(2))
        # ... other patterns
```

Note: This design intentionally keeps backends simple (just storage operations) while
centralizing reference format parsing. See [Design Decisions](#credential-backend-interface)
for the rationale.

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
Match against patterns (centralized in resolver):
    ├─ ENV_PATTERN matches "${...}"?
    │   └─ Yes → EnvironmentBackend.get(var_name)
    │              ↓
    │              Return value
    │
    ├─ KEYRING_PATTERN matches "@keyring:..."?
    │   └─ Yes → KeyringBackend.get(service, key)
    │              ↓
    │              Return value
    │
    └─ ENCRYPTED_PATTERN matches "@encrypted:..."?
        └─ Yes → EncryptedBackend.get(service, key)
                   ↓
                   Return value
    ↓
No pattern match → Return as literal value
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

Create a custom credential backend that implements the `CredentialBackend` Protocol:

```python
# myapp/credentials/s3_backend.py
import boto3
from repo_sapiens.credentials.backend import CredentialBackend

class S3CredentialBackend:
    """Store and retrieve credentials from AWS S3."""

    def __init__(self, bucket: str):
        self.bucket = bucket
        self._s3 = boto3.client("s3")

    @property
    def name(self) -> str:
        return "s3"

    @property
    def available(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def get(self, service: str, key: str) -> str | None:
        """Retrieve credential from S3."""
        try:
            path = f"{service}/{key}"
            response = self._s3.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read().decode("utf-8")
        except self._s3.exceptions.NoSuchKey:
            return None

    def set(self, service: str, key: str, value: str) -> None:
        """Store credential in S3."""
        path = f"{service}/{key}"
        self._s3.put_object(Bucket=self.bucket, Key=path, Body=value.encode())

    def delete(self, service: str, key: str) -> bool:
        """Delete credential from S3."""
        path = f"{service}/{key}"
        try:
            self._s3.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False
```

To use a custom backend, you'll also need to add pattern matching in the
resolver. See the existing resolver implementation for the pattern.

### 2. Adding New Git Providers

Create a provider for a new Git hosting service:

```python
# repo_sapiens/providers/gitlab_provider.py
from repo_sapiens.providers.base import GitProvider

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
# repo_sapiens/rendering/custom_filters.py
def markdown_to_html(value: str) -> str:
    """Convert Markdown to HTML."""
    import markdown
    return markdown.markdown(value)

def count_occurrences(value: str, substring: str) -> int:
    """Count substring occurrences."""
    return value.count(substring)

# Register in engine
from repo_sapiens.rendering.engine import TemplateEngine

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

---

## Design Decisions

This section documents intentional architectural choices and their rationale.

### Credential Backend Interface

**Choice:** Use `get(service, key)` with pattern matching in resolver, rather
than `async resolve(reference)` with `can_handle()` in backends.

**Rationale:**
- Simpler backend interface (just storage operations)
- Pattern matching logic centralized and testable
- Backends don't need to understand reference formats
- Easier to add new reference formats without modifying backends

### Provider Module Structure

**Choice:** Group Git and Agent providers in `repo_sapiens/providers/` rather
than separate `git/` and `agents/` directories.

**Rationale:**
- Both are external service integrations with similar patterns
- Shared base classes and utilities
- Simpler import structure
- Single location for all provider-related code

### Template Engine Naming

**Choice:** Name the template engine `SecureTemplateEngine` rather than just
`TemplateEngine`.

**Rationale:**
- Communicates the sandboxed, security-focused nature
- Distinguishes from standard Jinja2 usage
- Reminds developers of the security constraints

### State Persistence

**Choice:** Use file-based state persistence via `StateManager` rather than
database or in-memory stores.

**Rationale:**
- Simple to inspect and debug (human-readable files)
- No external dependencies
- Git-friendly (can be committed for reproducibility)
- Sufficient for single-process execution
