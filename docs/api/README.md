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
from automation.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("automation/config/automation_config.yaml")
```

#### Resolving Credentials
```python
from automation.credentials import CredentialResolver

resolver = CredentialResolver()
token = resolver.resolve("@keyring:gitea/api_token")
api_key = resolver.resolve("${CLAUDE_API_KEY}")
```

#### Git Repository Discovery
```python
from automation.git.discovery import GitDiscovery

discovery = GitDiscovery()
info = discovery.parse_repository()
provider_type = discovery.detect_provider_type()  # "github" or "gitea"
```

#### Creating Git Providers
```python
from automation.providers.factory import create_git_provider

provider = create_git_provider(settings)
await provider.connect()

issues = await provider.get_issues(labels=["needs-planning"])
pr = await provider.create_pull_request(title="...", body="...", head="feature", base="main")
```

#### Template Rendering
```python
from automation.rendering.engine import SecureTemplateEngine

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
| `automation.config` | Configuration management with Pydantic models |
| `automation.credentials` | Secure credential storage (keyring, env, encrypted) |
| `automation.git` | Git repository operations and discovery |
| `automation.providers` | Git and AI agent provider abstractions |
| `automation.rendering` | Secure Jinja2 template rendering |
| `automation.engine` | Workflow orchestration and execution |
| `automation.cli` | Command-line interface |
| `automation.utils` | Utility functions and helpers |

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
sphinx-apidoc -o api/ ../automation/
make html
```

The generated documentation will be in `docs/_build/html/`.
