# Sapiens Workflow Integration

This directory is now deprecated. The repo-sapiens workflow system has been updated to use a reusable workflow pattern.

## New Approach

Instead of copying multiple workflow files, users now create a single thin wrapper workflow (~20 lines) that calls the reusable `sapiens-dispatcher.yaml` from the repo-sapiens repository.

### Quick Setup

Create a single file `.gitea/workflows/sapiens.yaml`:

```yaml
# .gitea/workflows/sapiens.yaml
name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v2
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: gitea
      git_provider_url: ${{ github.server_url }}
      # Configure AI provider:
      # ai_provider_type: openai-compatible
      # ai_base_url: https://openrouter.ai/api/v1
      # ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
```

### Benefits

- **96% less boilerplate**: From ~490 lines to ~20 lines
- **Automatic updates**: Bump `@v2` to `@v2.1.0` for updates
- **Single source of truth**: All workflow logic in repo-sapiens
- **Consistent behavior**: Same workflow works across all repos

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SAPIENS_GITEA_TOKEN` | Your Gitea API token |
| `SAPIENS_AI_API_KEY` | API key for AI provider (not needed for Ollama) |

### Migration

If you were using the old copy-paste templates:

1. Delete `.gitea/workflows/sapiens/` directory
2. Create `.gitea/workflows/sapiens.yaml` with the wrapper above
3. Update your secrets if needed

### Documentation

- [Deployment Guide](../../docs/DEPLOYMENT_GUIDE.md)
- [Workflow Reference](../../docs/WORKFLOW_REFERENCE.md)
- [Main README](../../README.md)

---

*This README is kept for reference. The old workflow templates have been removed.*
