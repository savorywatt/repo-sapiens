# Builder CLI Redesign: Self-Contained Automation Tool

## Executive Summary

This plan redesigns the `builder` package from a repository-specific automation system into a self-contained CLI tool (similar to Poetry/Pipenv) that can initialize and manage automation in any Git repository. The tool will support local AI execution via multiple providers (Claude API, Ollama, etc.) and provide both workflow-based (CI/CD) and local execution modes.

## Vision

```bash
# Install builder globally
pip install builder-cli

# Initialize automation in any repo
cd my-project
builder init

# Local workflow runner
builder run --watch

# Health check
builder doctor
```

## Current Architecture

### Existing Structure
```
builder/
├── automation/                    # Main package (54 Python files, 7,321 lines)
│   ├── config/                   # Pydantic-based settings
│   ├── engine/                   # Workflow orchestration
│   ├── providers/                # Git/AI provider implementations
│   ├── models/                   # Domain models
│   └── main.py                   # CLI entry point
├── .gitea/workflows/             # 13 Gitea Actions workflows
└── .automation/                  # Runtime state
```

### Key Components to Leverage
1. **Configuration System**: Pydantic-based settings with YAML + env vars
2. **State Management**: Atomic JSON-based state with file locking
3. **Provider Abstraction**: Clean separation of Git/AI providers
4. **Workflow Engine**: Robust orchestration with stages
5. **CLI Framework**: Click-based command structure

## Redesigned Architecture

### New Directory Structure
```
builder-cli/
├── builder/                      # Renamed from 'automation'
│   ├── cli/                     # CLI commands (NEW)
│   │   ├── main.py              # Entry point
│   │   ├── init.py              # 'builder init' command
│   │   ├── doctor.py            # 'builder doctor' command
│   │   └── run.py               # 'builder run' command
│   ├── core/                    # Renamed from 'engine'
│   │   ├── config/              # Configuration management
│   │   ├── orchestrator.py
│   │   └── stages/
│   ├── providers/               # Keep as-is
│   ├── templates/               # NEW: Workflow templates
│   │   ├── workflows/
│   │   └── config/
│   ├── discovery/               # NEW: Repo discovery
│   │   ├── git.py              # Git remote detection
│   │   └── gitea.py            # Gitea API discovery
│   └── credentials/             # NEW: Credential management
│       └── store.py            # Secure storage
└── pyproject.toml
```

### Target Repository Structure (After `builder init`)
```
my-repo/
├── .builder/                    # Builder-specific directory
│   ├── config.toml             # All configuration
│   ├── state/                  # Workflow state
│   ├── logs/                   # Execution logs
│   ├── cache/                  # AI response cache
│   └── credentials.enc         # Encrypted credentials (optional)
├── .gitea/workflows/           # Generated workflows
│   ├── needs-planning.yaml
│   ├── approved.yaml
│   └── ...
└── [existing repo content]
```

## Core Commands

### 1. `builder init` - Initialize Automation

**Goal**: Initialize builder automation in any repository

**Interactive Flow**:
```bash
$ builder init
🔍 Detected Gitea URL: https://gitea.example.com
Repository owner [myorg]:
Repository name [myrepo]:
AI Provider (claude-api/ollama/openai): claude-api
Gitea API token: ********
Claude API key: ********
Credential storage (keyring/env/file) [keyring]:

✅ Created .builder/config.toml
✅ Created .builder/state/
✅ Stored credentials in keyring
✅ Created .gitea/workflows/needs-planning.yaml
✅ Created .gitea/workflows/approved.yaml
... (11 more workflows)
✅ Labels created on Gitea

Builder automation initialized!
Next steps:
  1. Review configuration: .builder/config.toml
  2. Commit workflows: git add .gitea/workflows && git commit
  3. Push to Gitea: git push
  4. Test locally: builder run --once
```

**What It Does**:
1. Detects git origin and Gitea URL
2. Prompts for AI provider and credentials
3. Creates `.builder/` directory structure
4. Generates `config.toml` configuration
5. Generates all workflow files from templates
6. Creates labels on Gitea
7. Stores credentials securely

**Implementation**:
```python
# builder/cli/init.py
@click.command()
@click.option('--provider', type=click.Choice(['claude-api', 'ollama', 'openai']))
@click.option('--gitea-url', help='Gitea URL (auto-detected if not provided)')
def init(provider: str, gitea_url: str):
    # 1. Verify git repo
    # 2. Detect/prompt for Gitea URL
    # 3. Collect credentials
    # 4. Test API access
    # 5. Create .builder structure
    # 6. Generate config.toml
    # 7. Render workflow templates
    # 8. Create labels on Gitea
    pass
```

### 2. `builder doctor` - Health Check

**Goal**: Comprehensive diagnostics and health checks

**Example Output**:
```bash
$ builder doctor
============================================================
Builder Health Check
============================================================

✅ Configuration file exists
✅ Configuration is valid
✅ Git origin configured: https://gitea.example.com/myorg/myrepo
✅ Gitea credentials accessible
✅ Gitea API accessible (user: myuser)
✅ All required labels exist
✅ Workflows directory exists (11 workflows)
✅ State directory exists (3 state files)
✅ Claude API key configured

============================================================
Results: 9 passed, 0 warnings, 0 failed
============================================================
```

**Checks Performed**:
1. `.builder/config.toml` exists and is valid
2. Git origin configured
3. Credentials accessible
4. Gitea API connectivity
5. Required labels exist on repo
6. Workflows present in `.gitea/workflows/`
7. State directory exists
8. AI provider configured and accessible

**Implementation**:
```python
# builder/cli/doctor.py
@click.command()
@click.option('--verbose', '-v', is_flag=True)
def doctor(verbose: bool):
    checks = []

    # Run all health checks
    # Report results
    # Exit with error code if any checks fail
    pass
```

### 3. `builder run` - Local Workflow Runner

**Goal**: Run automation locally as alternative to CI/CD

**Modes**:

1. **Once mode** (default):
   ```bash
   builder run --once
   # Process pending issues once, then exit
   ```

2. **Watch mode**:
   ```bash
   builder run --watch
   # Continuous polling, like a daemon
   ```

3. **Specific issue**:
   ```bash
   builder run --issue 42
   # Process issue #42 only
   ```

4. **Dangerous mode** 🚨:
   ```bash
   builder run --dangerous --watch
   # Auto-approve everything, keep iterating
   # WARNING: No human review!
   ```

**Example Session**:
```bash
$ builder run --watch
👀 Watch mode enabled (polling every 60s)
   Press Ctrl+C to stop

[1] 🔄 Polling...
    Found 2 issues with automation labels
    Processing issue #42: Add dark mode toggle
    - Created plan proposal
    - Updated labels: needs-planning → proposed
    Processing issue #43: Fix login bug
    - Created fix proposal
[1] ✅ Poll complete
[1] ⏳ Waiting 60s...

[2] 🔄 Polling...
[2] ✅ Poll complete (no pending issues)
[2] ⏳ Waiting 60s...
```

**Implementation**:
```python
# builder/cli/run.py
@click.command()
@click.option('--once', is_flag=True)
@click.option('--watch', is_flag=True)
@click.option('--dangerous', is_flag=True)
@click.option('--issue', type=int)
def run(once: bool, watch: bool, dangerous: bool, issue: int):
    # Load config
    # Initialize providers
    # Run orchestrator in selected mode
    pass
```

## Configuration Schema

### `.builder/config.toml` Structure

```toml
version = "1.0"

[repository]
owner = "myorg"
name = "myrepo"
default_branch = "main"

[git_provider]
type = "gitea"  # gitea, github, gitlab
base_url = "https://gitea.example.com"
# Credential options:
# 1. Keyring: api_token = "@keyring:gitea/api_token"
# 2. Environment: api_token = "${GITEA_TOKEN}"
# 3. Direct (not recommended): api_token = "token_here"
api_token = "@keyring:gitea/api_token"

[ai_provider]
type = "claude-api"  # claude-api, ollama, openai
model = "claude-sonnet-4.5"
api_key = "@keyring:claude/api_key"

# Ollama-specific (when type = "ollama")
[ai_provider.ollama]
base_url = "http://localhost:11434"
model = "llama3.1:8b"

[workflow]
plans_directory = "plans"
state_directory = ".builder/state"
branching_strategy = "per-agent"
max_concurrent_tasks = 3
timeout_minutes = 30

[local_runner]
poll_interval = 60  # seconds
auto_approve = false
max_iterations = 10

[labels]
needs_planning = "needs-planning"
proposed = "proposed"
approved = "approved"
# ... other labels
```

### Python Schema

```python
# builder/core/config/schema.py
from pydantic import BaseModel
from typing import Literal

class RepositoryConfig(BaseModel):
    owner: str
    name: str
    default_branch: str = "main"

class GitProviderConfig(BaseModel):
    type: Literal["gitea", "github", "gitlab"]
    base_url: str
    api_token: str  # Can be @keyring:*, ${ENV}, or direct

class AIProviderConfig(BaseModel):
    type: Literal["claude-api", "ollama", "openai"]
    model: str
    api_key: str | None = None
    base_url: str | None = None

class BuilderConfig(BaseModel):
    version: str = "1.0"
    repository: RepositoryConfig
    git_provider: GitProviderConfig
    ai_provider: AIProviderConfig
    # ... other sections

    @classmethod
    def from_file(cls, path: Path) -> "BuilderConfig":
        """Load config from TOML file with credential resolution."""
        with open(path) as f:
            data = toml.load(f)
        data = cls._resolve_credentials(data)
        return cls(**data)
```

## Credential Management

### Three Storage Options

1. **Keyring** (Recommended - OS-level security):
   ```toml
   api_token = "@keyring:gitea/api_token"
   ```

2. **Environment Variables**:
   ```toml
   api_token = "${GITEA_TOKEN}"
   ```

3. **Encrypted File** (`.builder/credentials.enc`):
   ```toml
   api_token = ""  # Stored in encrypted file
   ```

### Implementation

```python
# builder/credentials/store.py
import keyring
from cryptography.fernet import Fernet

class CredentialStore:
    def __init__(self, backend: str = 'keyring'):
        self.backend = backend  # keyring, env, file

    def store(self, credentials: dict) -> None:
        """Store credentials securely."""
        if self.backend == 'keyring':
            for key, value in credentials.items():
                keyring.set_password('builder', key, value)

    def get(self, key: str) -> str | None:
        """Retrieve credential."""
        if self.backend == 'keyring':
            return keyring.get_password('builder', key)

    def resolve_reference(self, value: str) -> str:
        """Resolve @keyring:* or ${VAR} references."""
        if value.startswith('@keyring:'):
            service, key = value[9:].split('/')
            return keyring.get_password(service, key)
        elif value.startswith('${'):
            var_name = value[2:-1]
            return os.getenv(var_name)
        return value
```

## Template System

### Workflow Templates (Jinja2)

```yaml
# builder/templates/workflows/needs-planning.yaml.j2
name: Needs Planning

on:
  issues:
    types: [labeled]

jobs:
  create-plan:
    if: gitea.event.label.name == '{{ labels.needs_planning }}'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install builder
        run: pip install builder-cli

      - name: Create plan
        env:
          BUILDER_GITEA_TOKEN: ${{ secrets.BUILDER_GITEA_TOKEN }}
          BUILDER_CLAUDE_API_KEY: ${{ secrets.BUILDER_CLAUDE_API_KEY }}
        run: builder run --issue ${{ gitea.event.issue.number }}
```

### Template Rendering

```python
# builder/templates/__init__.py
from jinja2 import Environment, PackageLoader

env = Environment(loader=PackageLoader('builder', 'templates'))

def render_workflows(gitea_url: str, owner: str, repo: str) -> dict:
    """Render all workflow templates."""
    workflows = {}
    for template_name in ['needs-planning.yaml', 'approved.yaml', ...]:
        template = env.get_template(f'workflows/{template_name}.j2')
        workflows[template_name.replace('.j2', '')] = template.render(
            gitea_url=gitea_url,
            owner=owner,
            repo=repo,
        )
    return workflows
```

## Repository Discovery

### Git Discovery

```python
# builder/discovery/git.py
import git
from urllib.parse import urlparse

def detect_git_origin(repo: git.Repo) -> str | None:
    """Detect Gitea URL from git origin."""
    origin_url = repo.remotes.origin.url
    # Parse SSH: git@gitea.com:owner/repo.git
    # Parse HTTPS: https://gitea.com/owner/repo.git
    # Return: https://gitea.com
    pass

def parse_owner_repo(url: str) -> tuple[str, str]:
    """Parse owner and repo name from git URL."""
    # git@gitea.com:owner/repo.git → (owner, repo)
    # https://gitea.com/owner/repo.git → (owner, repo)
    pass
```

### Gitea API Discovery

```python
# builder/discovery/gitea.py
import httpx

class GiteaDiscovery:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.client = httpx.Client(headers={'Authorization': f'token {token}'})

    def test_connection(self) -> bool:
        """Test Gitea API accessibility."""
        pass

    def get_user(self) -> str:
        """Get authenticated user."""
        pass

    def verify_repo_access(self, owner: str, repo: str) -> bool:
        """Verify repository access."""
        pass
```

## Migration Strategy

### From Existing Setup

```bash
$ builder migrate
🔍 Found old automation configuration
📝 Converting automation/config/automation_config.yaml
   → .builder/config.toml

✅ Migration complete
⚠️  Review .builder/config.toml before use
💡 Old configuration preserved
```

### Backward Compatibility

- Keep `automation` package as legacy alias
- Support old config format via adapter
- Provide migration tool
- Document migration path

## Local vs. CI/CD Modes

### Local Mode (`builder run`)
- ✅ Runs on your machine
- ✅ Uses your AI provider credentials
- ✅ Interactive debugging
- ✅ Good for testing

### CI/CD Mode (Gitea Actions)
- ✅ Runs on Gitea runner
- ✅ Uses repository secrets
- ✅ Fully automated
- ✅ Production ready

**You can use both!** Test locally with `builder run --once`, then commit and push for CI/CD.

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
- [ ] Package restructuring (rename automation → builder)
- [ ] Configuration schema (TOML-based)
- [ ] Credential management system
- [ ] Template system setup

### Phase 2: Core Commands (Week 3-4)
- [ ] `builder init` implementation
- [ ] `builder doctor` implementation
- [ ] Repository discovery
- [ ] Workflow template rendering

### Phase 3: Local Runner (Week 5-6)
- [ ] `builder run` command
- [ ] Local orchestrator integration
- [ ] Polling mechanism
- [ ] Dangerous mode implementation

### Phase 4: Polish & Testing (Week 7-8)
- [ ] Migration tools
- [ ] Comprehensive tests
- [ ] Documentation
- [ ] Examples and guides

### Phase 5: Release (Week 9-10)
- [ ] PyPI packaging
- [ ] CI/CD for builder itself
- [ ] Release automation
- [ ] Community feedback

## Benefits

1. **Easy Onboarding**: `builder init` in any repo
2. **Self-Contained**: No manual workflow setup
3. **Local Testing**: `builder run` before pushing
4. **Flexible Deployment**: Local or CI/CD
5. **Secure Credentials**: Keyring integration
6. **Provider Agnostic**: Claude, Ollama, OpenAI support
7. **Health Monitoring**: `builder doctor` diagnostics

## Open Questions

1. **Python version support**: Python 3.11+ only or support 3.9+?
   - Recommendation: 3.11+ (existing codebase requirement)

2. **Workflow updates**: Auto-update or manual?
   - Recommendation: Manual with `builder update` command

3. **State sync**: Local only or sync to Gitea?
   - Recommendation: Local only initially

4. **Multi-repo coordination**: How to handle cross-repo dependencies?
   - Recommendation: Phase 2 feature

5. **Plugin system**: Allow community providers?
   - Recommendation: Yes, but Phase 2

## Success Metrics

1. **Adoption**: 50+ repositories using builder in 3 months
2. **Ease of use**: New user can initialize in < 5 minutes
3. **Reliability**: 95%+ success rate for `builder doctor`
4. **Documentation**: < 10% of issues are "how do I..."

---

**Status**: Ready for implementation
**Priority**: High - Transforms user experience
**Effort**: High (9-10 weeks)
**Risk**: Medium - Significant architectural change
