# Secure Jinja2 Template System for Workflow Generation

## Overview

This module implements a **security-hardened Jinja2 template system** for generating Gitea Actions workflow files. The system addresses template injection vulnerabilities identified in the technical review while providing a flexible, maintainable architecture.

## Security Features

### Core Security Measures

1. **Sandboxed Environment** (`SandboxedEnvironment`)
   - Prevents arbitrary code execution
   - Blocks access to private attributes and methods
   - Restricts dangerous operations

2. **Strict Undefined Variables** (`StrictUndefined`)
   - Fails immediately on undefined variables
   - Prevents silent failures and unexpected behavior

3. **Path Validation**
   - Prevents directory traversal attacks
   - Validates all template paths are within the template directory

4. **Input Validation**
   - Pydantic models for strong type checking
   - Validates all context variables before rendering
   - Checks for null bytes, excessive lengths, and dangerous patterns

5. **Custom Security Filters**
   - `safe_url`: Validates URLs (only https/http schemes)
   - `safe_identifier`: Validates identifiers (repo names, owners)
   - `safe_label`: Validates label names
   - `yaml_string/list/dict`: Safe YAML serialization

6. **Output Validation**
   - Checks rendered output for dangerous YAML patterns
   - Detects Python object deserialization attempts
   - Prevents YAML anchor/alias attacks

## Directory Structure

```
automation/
├── templates/
│   ├── workflows/
│   │   ├── base.yaml.j2              # Base template with reusable macros
│   │   ├── ci/
│   │   │   ├── build.yaml.j2         # CI build and test workflow
│   │   │   ├── test.yaml.j2          # Test suite workflow
│   │   │   └── lint.yaml.j2          # Linting workflow
│   │   ├── release/
│   │   │   ├── pypi-publish.yaml.j2  # PyPI publishing workflow
│   │   │   └── github-release.yaml.j2 # GitHub release workflow
│   │   ├── automation/
│   │   │   ├── label-sync.yaml.j2    # Label synchronization
│   │   │   ├── pr-labels.yaml.j2     # Auto-label PRs
│   │   │   ├── issue-labels.yaml.j2  # Auto-label issues
│   │   │   └── stale-issues.yaml.j2  # Mark stale issues
│   │   └── docs/
│   │       └── build-docs.yaml.j2    # Documentation build
│   ├── macros/                        # Reusable Jinja2 macros
│   └── schemas/                       # JSON validation schemas
│       └── workflow-config.schema.json
└── rendering/
    ├── __init__.py                    # High-level rendering API
    ├── engine.py                      # SecureTemplateEngine
    ├── filters.py                     # Custom security filters
    ├── validators.py                  # Pydantic validation models
    └── security.py                    # Security utilities
```

## Installation

### Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    "jinja2>=3.1.3",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
]
```

Install:

```bash
pip install -e .[dev]
```

## Usage

### Quick Start

```python
from automation.rendering import render_workflow

# Render a workflow with minimal configuration
workflow = render_workflow(
    "ci/build",
    gitea_url="https://gitea.example.com",
    gitea_owner="my-org",
    gitea_repo="my-repo",
)

print(workflow)
```

### Advanced Configuration

```python
from pathlib import Path
from automation.rendering import WorkflowRenderer
from automation.rendering.validators import CIBuildConfig

# Create renderer
renderer = WorkflowRenderer()

# Configure workflow with full options
config = CIBuildConfig(
    gitea_url="https://gitea.example.com",
    gitea_owner="my-org",
    gitea_repo="my-repo",
    workflow_name="Custom Build Pipeline",
    python_versions=["3.11", "3.12", "3.13"],
    linters=["ruff", "mypy", "pylint"],
    fail_fast=True,
    artifact_retention_days=30,
    package_name="my-package",
)

# Render to file
output_path = Path(".gitea/workflows/build.yaml")
renderer.render_workflow("ci/build", config, output_path)
```

### Batch Generation

```python
from pathlib import Path
from automation.rendering import WorkflowRenderer
from automation.rendering.validators import (
    CIBuildConfig,
    LabelSyncConfig,
    PyPIPublishConfig,
)

renderer = WorkflowRenderer()

# Configure all workflows
configs = {
    "ci/build": CIBuildConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
        package_name="my-package",
    ),
    "automation/label-sync": LabelSyncConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
    ),
    "release/pypi-publish": PyPIPublishConfig(
        gitea_url="https://gitea.example.com",
        gitea_owner="my-org",
        gitea_repo="my-repo",
        package_name="my-package",
    ),
}

# Render all workflows
output_dir = Path(".gitea/workflows")
results = renderer.render_all_workflows(configs, output_dir)

for template, output_file in results.items():
    print(f"Generated {template} -> {output_file}")
```

## Available Templates

| Category | Template | Purpose |
|----------|----------|---------|
| CI | `ci/build` | Build and test Python package |
| CI | `ci/test` | Run test suite with coverage |
| CI | `ci/lint` | Run linters (ruff, mypy, black, isort) |
| Release | `release/pypi-publish` | Publish to PyPI with trusted publishing |
| Release | `release/github-release` | Create GitHub release with changelog |
| Automation | `automation/label-sync` | Sync repository labels from config |
| Automation | `automation/pr-labels` | Auto-label pull requests |
| Automation | `automation/issue-labels` | Auto-label issues |
| Automation | `automation/stale-issues` | Mark stale issues and PRs |
| Docs | `docs/build-docs` | Build documentation (Sphinx/MkDocs) |

## Configuration Models

### WorkflowConfig (Base)

Required fields:
- `gitea_url`: Gitea instance URL (https:// or http://)
- `gitea_owner`: Repository owner (alphanumeric, hyphens, underscores)
- `gitea_repo`: Repository name (alphanumeric, hyphens, underscores)

Optional fields:
- `workflow_name`: Custom workflow name
- `runner`: GitHub Actions runner (default: "ubuntu-latest")
- `python_version`: Python version (default: "3.11")
- `trigger_branches`: Branches that trigger workflow (default: ["main"])
- `labels_file`: Path to labels config (default: ".github/labels.yaml")

### CIBuildConfig

Extends `WorkflowConfig` with:
- `python_versions`: List of Python versions to test (default: ["3.11", "3.12"])
- `linters`: List of linters to run (default: ["ruff", "mypy"])
- `fail_fast`: Fail fast in matrix builds (default: False)
- `artifact_retention_days`: Days to retain artifacts (default: 7, max: 90)
- `package_name`: Python package name (required for coverage)

### PyPIPublishConfig

Extends `WorkflowConfig` with:
- `package_name`: Package name for PyPI (required)
- `environment`: GitHub environment name (default: "release")
- `use_trusted_publishing`: Use PyPI trusted publishing (default: True)
- `test_pypi`: Publish to Test PyPI (default: False)

### LabelSyncConfig

Extends `WorkflowConfig` with:
- `main_branch`: Branch to trigger sync (default: "main")
- `dry_run`: Run in dry-run mode (default: False)

## Security Guidelines

### For Template Authors

1. **Always use security filters** on user-provided values:
   ```yaml
   name: {{ workflow_name | safe_label }}
   repo: {{ gitea_repo | safe_identifier }}
   url: {{ gitea_url | safe_url }}
   ```

2. **Use macros for common patterns**:
   ```yaml
   {% import 'workflows/base.yaml.j2' as base %}
   {{ base.checkout_step() }}
   {{ base.setup_python_step() }}
   ```

3. **Validate assumptions in templates**:
   ```yaml
   {% if package_name is not defined %}
   {{ raise("package_name is required for this workflow") }}
   {% endif %}
   ```

4. **Document required variables**:
   ```yaml
   {# Required variables:
      - package_name: Python package name
      - python_version: Python version to use
   #}
   ```

### For Template Users

1. **Validate input before rendering**:
   - Use Pydantic models for type safety
   - Check for null bytes and dangerous characters
   - Validate URL schemes and identifiers

2. **Never load templates from user input**:
   - Template names should be hardcoded or from a whitelist
   - Never accept template paths from untrusted sources

3. **Review rendered output**:
   - Check for unexpected YAML constructs
   - Validate against YAML schema if possible

## Testing

### Run Tests

```bash
# All tests
pytest tests/templates/ -v

# Security tests only
pytest tests/templates/test_security.py -v

# With coverage
pytest tests/templates/ --cov=automation.rendering --cov-report=term-missing
```

### Test Coverage

The test suite includes:
- **Security filter tests**: Validate all security filters work correctly
- **Injection prevention tests**: Ensure code execution is blocked
- **Path validation tests**: Verify directory traversal is prevented
- **Integration tests**: End-to-end workflow rendering
- **Validation tests**: Pydantic model validation
- **Output validation tests**: Dangerous YAML pattern detection

## Maintenance

### Security Updates

1. **Monitor Jinja2 security advisories**: https://github.com/pallets/jinja/security
2. **Pin Jinja2 version** in `pyproject.toml`
3. **Run security audits** quarterly
4. **Automated dependency scanning** (Dependabot/Renovate)

### Template Versioning

- Version templates using semantic versioning
- Maintain changelog for template changes
- Support migration paths for breaking changes
- Deprecate templates gracefully

## Threat Model

### Identified Threats

1. **Template Injection**
   - **Risk**: Malicious code in template variables
   - **Mitigation**: Sandboxed environment + input validation

2. **Directory Traversal**
   - **Risk**: Access to files outside template directory
   - **Mitigation**: Path validation in `validate_template_path()`

3. **YAML Injection**
   - **Risk**: Malicious YAML constructs in output
   - **Mitigation**: Output validation + character whitelisting

4. **DoS via Anchors**
   - **Risk**: Billion laughs attack with YAML anchors
   - **Mitigation**: Output pattern detection

5. **Secret Exposure**
   - **Risk**: Accidental inclusion of secrets
   - **Mitigation**: Template review + secret scanning

## References

- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [Jinja2 Sandbox](https://jinja.palletsprojects.com/en/3.1.x/sandbox/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OWASP Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html)

## License

MIT License - see LICENSE file in the repo-sapiens repository.
