# API Reference

This directory contains API documentation for the repo-sapiens project.

> **Note:** Full API documentation is auto-generated via Sphinx autodoc from source code docstrings.
> To build the HTML documentation, run `cd docs && make html`.

## Quick Links

### Most Commonly Used APIs

#### Loading Configuration
```python
from repo_sapiens.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml(".sapiens/config.yaml")
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
provider_type = discovery.detect_provider_type()  # "github", "gitea", or "gitlab"

# Optional parameters:
# - remote_name: specify which remote to use (default: "origin")
# - allow_multiple: enable parsing repos with multiple remotes
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

## Building Documentation

Sphinx is already configured in `docs/source/conf.py`. To build HTML documentation:

```bash
cd docs && make html
```

The generated documentation will be in `docs/build/html/`.
