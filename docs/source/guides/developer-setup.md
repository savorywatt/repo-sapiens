# Developer Setup Guide

## Quick Start (10 Minutes)

This guide covers setting up your development environment, including AI provider configuration and pre-commit hooks.

### 1. Install Development Dependencies

```bash
# Clone the repository
git clone https://github.com/savorywatt/repo-sapiens.git
cd repo-sapiens

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package with dev dependencies
uv sync --group dev
```

### 2. Set Up Ollama (Recommended for Testing)

Ollama provides free, local AI inference - perfect for development and testing without API costs.

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# On macOS with Homebrew
brew install ollama

# Start Ollama server (runs in background)
ollama serve &

# Pull recommended models
ollama pull qwen3:latest       # Best for code generation (recommended)
ollama pull llama3.1:8b        # Good general purpose, smaller

# Verify installation
ollama list
curl http://localhost:11434/api/tags
```

**Recommended Models for Development:**

| Model | Size | RAM | Use Case |
|-------|------|-----|----------|
| `qwen3:latest` | 5GB | 10GB | Best balance (recommended) |
| `codellama:7b` | 4GB | 8GB | Fast iteration, basic tasks |
| `llama3.1:8b` | 5GB | 10GB | General + code |
| `deepseek-coder:6.7b` | 4GB | 8GB | Code-focused, efficient |

### 3. Configure for Local Development

Create a local configuration file:

```bash
cat > .sapiens/config.yaml << 'EOF'
git_provider:
  provider_type: gitea
  base_url: ${SAPIENS_GITEA_URL:-http://localhost:3000}
  api_token: ${SAPIENS_GITEA_TOKEN}

repository:
  owner: ${REPO_OWNER:-your-username}
  name: ${REPO_NAME:-your-repo}
  default_branch: main

agent_provider:
  provider_type: ollama
  model: ${OLLAMA_MODEL:-qwen3:latest}
  base_url: ${OLLAMA_BASE_URL:-http://localhost:11434}
  local_mode: true

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
  branching_strategy: per-agent
  max_concurrent_tasks: 1
  review_approval_threshold: 0.7

tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
EOF
```

Set environment variables:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export SAPIENS_GITEA_URL="http://localhost:3000"
export SAPIENS_GITEA_TOKEN="your-gitea-token"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="qwen3:latest"
```

### 4. Test Your Setup

```bash
# Verify Ollama is working
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3:latest",
  "prompt": "Write a Python hello world function",
  "stream": false
}' | jq .response

# Run the sapiens health check
sapiens --config .sapiens/config.yaml health-check

# Process a test issue (if you have a Gitea instance)
sapiens --config .sapiens/config.yaml process-issue --issue 1 --log-level DEBUG
```

---

## Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality.

### Install Pre-commit Hooks

```bash
# Install the git hooks (one-time setup)
pre-commit install

# Verify installation
pre-commit --version
```

### Verify Pre-commit Setup

```bash
# Run all hooks on all files to verify everything works
pre-commit run --all-files
```

**Note**: First run will take a few minutes to download and install hook environments. Subsequent runs are much faster.

## What Happens When You Commit

When you run `git commit`, pre-commit automatically:

1. **Formats your code** with Black (auto-fixes)
2. **Organizes imports** with Ruff (auto-fixes)
3. **Checks code quality** with Ruff linter
4. **Validates types** with MyPy (on repo_sapiens/ only)
5. **Scans for security issues** with Bandit
6. **Checks file formats** (YAML, JSON, TOML)
7. **Detects secrets** (API keys, passwords)
8. **Fixes common issues** (trailing whitespace, EOF)

If any check fails or modifies files:
- Review the changes
- Stage any auto-fixed files: `git add -u`
- Commit again: `git commit -m "your message"`

## Daily Workflow

### Normal Commit Flow

```bash
# Make your changes
vim repo_sapiens/some_file.py

# Stage changes
git add repo_sapiens/some_file.py

# Commit (hooks run automatically)
git commit -m "Add new feature"

# If hooks modified files
git add -u
git commit -m "Add new feature"
```

### Manual Hook Runs

```bash
# Run hooks on staged files before committing
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run ruff
pre-commit run mypy
```

### Fixing Issues

```bash
# Auto-fix formatting
black repo_sapiens/ tests/

# Auto-fix linting issues
ruff check --fix repo_sapiens/ tests/

# Check types
mypy repo_sapiens/

# Security scan
bandit -c pyproject.toml -r repo_sapiens/
```

## Common Scenarios

### Scenario 1: Files Modified by Hook

```
$ git commit -m "Add feature"
black................................................Failed
- files were modified by this hook
```

**Solution**: Stage the changes and commit again
```bash
git add -u
git commit -m "Add feature"
```

### Scenario 2: Type Errors

```
mypy.............................................Failed
repo_sapiens/main.py:42: error: Argument 1 has incompatible type
```

**Solution**: Fix the type hint based on error message
```python
# Before
def process(data):
    return data.upper()

# After
def process(data: str) -> str:
    return data.upper()
```

### Scenario 3: Linting Errors

```
ruff.............................................Failed
repo_sapiens/main.py:10:5: F841 Local variable is assigned but never used
```

**Solution**: Fix the issue or suppress if necessary
```python
# Fix: Remove unused variable
# Or suppress: Add # noqa: F841 at end of line
```

### Scenario 4: Emergency Bypass

```bash
# Only when absolutely necessary (hotfix, etc.)
git commit --no-verify -m "emergency fix"
```

**Warning**: CI/CD will still run all checks!

## IDE Integration

### VS Code

Install extensions:
- Python
- Black Formatter
- Ruff
- Pylance

Add to `.vscode/settings.json`:
```json
{
  "python.formatting.provider": "black",
  "python.linting.ruffEnabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Settings → Tools → Black → Enable
2. Settings → Tools → External Tools → Add Ruff
3. Settings → Inspections → Python → Enable MyPy
4. Settings → Editor → Code Style → Python → Set line length to 100

## Performance Tips

1. **Commit smaller changesets** - Hooks only check changed files
2. **Stage incrementally** - `git add` specific files
3. **Use `--no-verify` for WIP** - But fix before PR!
4. **Update hooks periodically** - `pre-commit autoupdate`

## Troubleshooting

### Slow Hooks

MyPy can be slow on large changesets. For local development:

```bash
# Skip hooks for quick iterations
git commit --no-verify -m "WIP"

# Run hooks before pushing
pre-commit run --all-files
```

### Hook Installation Issues

```bash
# Clear cache and reinstall
pre-commit clean
pre-commit install --install-hooks
```

### Python Version Mismatch

```bash
# Check Python version
python --version  # Should be 3.11+

# Reinstall with correct version
pre-commit uninstall
pre-commit install
```

### Permission Issues

```bash
# Make sure git hooks are executable
chmod +x .git/hooks/pre-commit
```

## Documentation

- **Contributing Guide**: See `CONTRIBUTING.md`

## Getting Help

1. Ask in pull request comments
2. Open an issue

## Pre-commit Cheat Sheet

```bash
# Installation
pre-commit install                    # Install hooks
pre-commit uninstall                  # Remove hooks

# Running
pre-commit run                        # Staged files
pre-commit run --all-files            # All files
pre-commit run black                  # Specific hook
pre-commit run --files file.py        # Specific files

# Maintenance
pre-commit autoupdate                 # Update hooks
pre-commit clean                      # Clean cache
pre-commit --version                  # Check version

# Bypass (emergency only)
git commit --no-verify                # Skip hooks
```

## What's Checked

| Tool | Purpose | Speed | Auto-fix |
|------|---------|-------|----------|
| Black | Code formatting | Fast | Yes |
| Ruff | Linting + imports | Very Fast | Partial |
| MyPy | Type checking | Slow | No |
| Bandit | Security | Medium | No |
| pyupgrade | Modern syntax | Fast | Yes |
| File checks | Syntax/formatting | Fast | Yes |
| detect-secrets | Secret detection | Fast | No |

## Configuration Files

- `.pre-commit-config.yaml` - Hook configuration
- `pyproject.toml` - Tool settings (black, ruff, mypy, bandit)
- `.secrets.baseline` - Known false positives

## Next Steps

1. ✅ Install pre-commit: `pre-commit install`
2. ✅ Run first check: `pre-commit run --all-files`
3. ✅ Make a test commit to see hooks in action
4. ✅ Configure your IDE for better experience
5. ✅ Read `CONTRIBUTING.md` for full guidelines

Happy coding! 🚀
