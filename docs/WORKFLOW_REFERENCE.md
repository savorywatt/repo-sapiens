# Sapiens Workflow Reference

Complete reference for the `sapiens-dispatcher.yaml` reusable workflow.

---

## Overview

The sapiens-dispatcher is a single reusable GitHub Actions workflow that handles all label-triggered automation. It supports:

- **GitHub** repositories (native)
- **Gitea** repositories (via GitHub Actions compatibility)
- Multiple AI providers (OpenRouter, Ollama, etc.)

Users create a thin wrapper workflow (~20 lines) that references the dispatcher.

---

## Workflow Inputs

All inputs are passed via the `with:` block in your workflow file.

### Required Inputs

| Input | Type | Description |
|-------|------|-------------|
| `label` | string | Label that triggered the workflow. Use `${{ github.event.label.name }}` |
| `issue_number` | number | Issue or PR number. Use `${{ github.event.issue.number \|\| github.event.pull_request.number }}` |

### Optional Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `event_type` | string | `issues.labeled` | Event type for sapiens CLI. Use `${{ github.event_name == 'pull_request' && 'pull_request.labeled' \|\| 'issues.labeled' }}` |
| `git_provider_type` | string | `github` | Git provider: `github` or `gitea` |
| `git_provider_url` | string | `https://api.github.com` | Git provider API URL (required for Gitea) |
| `ai_provider_type` | string | `openai-compatible` | AI provider type (see below) |
| `ai_model` | string | *(empty)* | AI model to use (e.g., `anthropic/claude-3.5-sonnet`) |
| `ai_base_url` | string | *(empty)* | AI provider base URL (required for `openai-compatible` and `ollama`) |

### AI Provider Types

| Type | Description | Requires API Key | Requires Base URL |
|------|-------------|------------------|-------------------|
| `openai-compatible` | Any OpenAI-compatible API (OpenRouter, LiteLLM, vLLM, etc.) | Yes | Yes |
| `ollama` | Local or remote Ollama server | No | Yes |
| `claude-local` | Claude Code CLI (interactive, not for CI) | No | No |

---

## Secrets

Secrets are passed via the `secrets:` block in your workflow file.

| Secret | Required | Description |
|--------|----------|-------------|
| `GIT_TOKEN` | Yes | GitHub or Gitea token for API access and git operations |
| `AI_API_KEY` | No | AI provider API key. Not required for Ollama |

### Mapping Your Secrets

Map your repository secrets to the workflow secrets:

```yaml
secrets:
  GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}  # or SAPIENS_GITEA_TOKEN
  AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}   # or OPENROUTER_API_KEY
```

---

## Examples

### GitHub with OpenRouter

```yaml
# .github/workflows/sapiens.yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
      AI_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

### GitHub with Anthropic API (via LiteLLM proxy)

```yaml
# .github/workflows/sapiens.yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      ai_provider_type: openai-compatible
      ai_base_url: https://api.anthropic.com/v1  # Or your LiteLLM proxy URL
      ai_model: claude-sonnet-4-20250514
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
      AI_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### GitHub with Ollama

```yaml
# .github/workflows/sapiens.yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      ai_provider_type: ollama
      ai_base_url: http://ollama.internal:11434
      ai_model: llama3.1:8b
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
      # AI_API_KEY not required for Ollama
```

### Gitea

```yaml
# .gitea/workflows/sapiens.yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: gitea
      git_provider_url: https://gitea.example.com
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
      AI_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

### GitLab

GitLab uses CI/CD Components instead of GitHub Actions reusable workflows. See [GITLAB_SETUP.md](GITLAB_SETUP.md) for GitLab-specific instructions.

```yaml
# .gitlab-ci.yml
include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v0.5.1
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      event_type: "issues.labeled"
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet

# Note: GitLab requires a webhook handler to trigger pipelines on label events.
# See docs/GITLAB_SETUP.md for webhook configuration.
```

---

## Versioning

### Version Tags

| Reference | Description |
|-----------|-------------|
| `@v0.5.1` | Current stable release (recommended) |
| `@v0.5.0` | Previous release |
| `@main` | Latest development (not recommended) |

### Pinning Versions

For production environments, pin to a specific version:

```yaml
uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
```

For development or testing, you can use a specific version or main (with caution):

```yaml
uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
```

---

## Label Reference

The dispatcher passes all labels to the sapiens CLI, which handles routing internally. Standard labels:

| Label | Action |
|-------|--------|
| `needs-planning` | Generate development plan from issue |
| `proposed` | Plan has been proposed (set automatically) |
| `approved` | Create task issues from approved plan |
| `task` | Marks an issue as a task (set automatically) |
| `execute` | Implement task and create PR |
| `needs-review` | Run AI code review on PR |
| `needs-fix` | Create fix proposal from review feedback |
| `requires-qa` | Run build and tests |
| `qa-passed` | QA passed (set automatically) |
| `qa-failed` | QA failed (set automatically) |
| `completed` | Work completed |

---

## Permissions

The reusable workflow requests these permissions:

```yaml
permissions:
  contents: write      # Push code changes
  issues: write        # Update issues, add comments
  pull-requests: write # Create/update PRs
```

Your calling workflow inherits these permissions automatically.

---

## Troubleshooting

### Workflow not triggering

1. Ensure the workflow file exists at `.github/workflows/sapiens.yaml` (or `.gitea/workflows/`)
2. Check that GitHub/Gitea Actions is enabled for your repository
3. Verify the label name is exactly correct (case-sensitive)
4. For private repos: ensure the runner can access the reusable workflow

### Authentication errors

1. Verify `GIT_TOKEN` secret is set and has required permissions
2. For GitHub: token needs `repo`, `issues`, `pull-requests` scopes
3. For Gitea: token needs repository read/write access

### AI provider errors

1. Verify `AI_API_KEY` secret is set (unless using Ollama)
2. Check `ai_base_url` is correct and accessible
3. Verify `ai_model` is a valid model ID for your provider

### Gitea-specific issues

1. Ensure `git_provider_type: gitea` is set
2. Ensure `git_provider_url` points to your Gitea instance
3. Verify the runner can reach both GitHub (for workflow) and your Gitea instance

---

## Related Documentation

- [GITHUB_OPENROUTER_SETUP.md](GITHUB_OPENROUTER_SETUP.md) - Complete GitHub + OpenRouter setup guide
- [GITEA_NEW_REPO_TUTORIAL.md](GITEA_NEW_REPO_TUTORIAL.md) - Complete Gitea setup tutorial
- [GITLAB_SETUP.md](GITLAB_SETUP.md) - GitLab CI/CD Component setup
- [MIGRATION.md](MIGRATION.md) - Migrating from template workflows
