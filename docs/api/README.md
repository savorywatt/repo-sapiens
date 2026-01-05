# API Reference

This directory contains comprehensive API documentation for the repo-sapiens project.

## Core Modules

### Configuration & Credentials
- [Configuration Management](./configuration.md) - Settings, config loading, and validation
- [Credential Management](./credentials.md) - Secure credential storage and resolution

### Git & Provider Integration
- [Git Discovery](./git-discovery.md) - Repository detection and parsing
- [Git Providers](./git-providers.md) - GitHub and Gitea provider interfaces
- [Agent Providers](./agent-providers.md) - AI agent integrations

### Template & Rendering
- [Template Engine](./template-engine.md) - Secure Jinja2 template rendering
- [Template Filters](./template-filters.md) - Custom filters and validators
- [Security](./security.md) - Security utilities and validation

### Automation Engine
- [Orchestrator](./orchestrator.md) - Workflow orchestration
- [Workflow Stages](./workflow-stages.md) - Individual workflow stages
- [State Management](./state-management.md) - Persistence and recovery

## Quick Links

### Most Commonly Used APIs

#### Loading Configuration
```python
from repo_sapiens.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("repo_sapiens/config/automation_config.yaml")
```

#### Resolving Credentials
```python
from repo_sapiens.credentials import CredentialResolver

resolver = CredentialResolver()
token = resolver.resolve("@keyring:gitea/api_token")
api_key = resolver.resolve("${CLAUDE_API_KEY}")
```

#### Git Repository Discovery
```python
from repo_sapiens.git.discovery import GitDiscovery

discovery = GitDiscovery()
info = discovery.parse_repository()
provider_type = discovery.detect_provider_type()  # "github" or "gitea"
```

#### Creating Git Providers
```python
from repo_sapiens.providers.factory import create_git_provider

provider = create_git_provider(settings)
await provider.connect()

issues = await provider.get_issues(labels=["needs-planning"])
pr = await provider.create_pull_request(title="...", body="...", head="feature", base="main")
```

#### Template Rendering
```python
from repo_sapiens.rendering.engine import SecureTemplateEngine

engine = SecureTemplateEngine()
rendered = engine.render("workflows/ci/build.yaml.j2", context={
    "gitea_url": "https://gitea.example.com",
    "gitea_owner": "myorg",
    "gitea_repo": "myrepo",
})
```

## Module Index

| Module | Description |
|--------|-------------|
| `repo_sapiens.config` | Configuration management with Pydantic models |
| `repo_sapiens.credentials` | Secure credential storage (keyring, env, encrypted) |
| `repo_sapiens.git` | Git repository operations and discovery |
| `repo_sapiens.providers` | Git and AI agent provider abstractions |
| `repo_sapiens.rendering` | Secure Jinja2 template rendering |
| `repo_sapiens.engine` | Workflow orchestration and execution |
| `repo_sapiens.cli` | Command-line interface |
| `repo_sapiens.utils` | Utility functions and helpers |

## Navigation

- [← Back to Docs](../)
- [Architecture Overview](../ARCHITECTURE.md)
- [Contributing Guide](../CONTRIBUTING.md)

## Generating Documentation

To generate HTML documentation from docstrings:

```bash
# Install Sphinx
pip install sphinx sphinx-rtd-theme

# Generate documentation
cd docs/
sphinx-quickstart
sphinx-apidoc -o api/ ../repo_sapiens/
make html
```

The generated documentation will be in `docs/_build/html/`.
