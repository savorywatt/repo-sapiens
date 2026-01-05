# Workflow Templates

Ready-to-use CI/CD workflow templates for repo-sapiens.

## Quick Setup

### For Gitea

```bash
# Copy workflows to your repo
mkdir -p .gitea/workflows
cp templates/workflows/gitea/*.yaml .gitea/workflows/
```

### For GitHub

```bash
# Copy workflows to your repo
mkdir -p .github/workflows
cp templates/workflows/github/*.yaml .github/workflows/
```

## Configuration

### 1. Set Repository Secrets

Go to your repository settings and add these secrets:

| Secret | Required | Description |
|--------|----------|-------------|
| `GITEA_TOKEN` | Gitea only | Your Gitea API token |
| `OPENAI_API_KEY` | If using Goose+OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Claude | Anthropic API key |

### 2. Choose Your Config File

The workflows use `CONFIG_FILE` environment variable. Edit the workflow to use your config:

```yaml
env:
  # For local Ollama config:
  CONFIG_FILE: sapiens_config.yaml

  # For CI/CD with cloud provider:
  CONFIG_FILE: sapiens_config.ci.yaml
```

### 3. Multi-Environment Setup

Create two configs for different environments:

```bash
# Local development (Ollama - free)
sapiens init --config-path sapiens_config.yaml
# Choose: Ollama

# CI/CD (Goose with OpenAI - better quality)
sapiens init --config-path sapiens_config.ci.yaml
# Choose: Goose → OpenAI
```

Then update the workflow to use the CI config:

```yaml
env:
  CONFIG_FILE: sapiens_config.ci.yaml
```

## Available Workflows

### automation-daemon.yaml

Runs periodically (every 5 minutes) to process pending issues automatically.

- Triggers: Schedule, Manual
- Processes all issues with automation labels
- Uploads state artifacts for debugging

### process-issue.yaml

Processes a single issue when labeled with `needs-planning`.

- Triggers: Issue labeled
- Generates development plan
- Comments on the issue with status

## Customization

### Change the Schedule

Edit the cron expression in `automation-daemon.yaml`:

```yaml
on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
    - cron: '0 * * * *'     # Every hour
    - cron: '0 9 * * 1-5'   # 9 AM weekdays
```

### Add More Label Triggers

Create additional workflow files for other labels:

```yaml
# approved.yaml
on:
  issues:
    types: [labeled]

jobs:
  process:
    if: github.event.label.name == 'approved'
    # ... rest of workflow
```

## Troubleshooting

### Workflow doesn't trigger

- Check that Actions are enabled in repository settings
- Verify the label name matches exactly (case-sensitive)
- Check runner availability

### Permission denied

- Verify token has correct scopes
- For GitHub, you may need a PAT instead of `GITHUB_TOKEN`

### Config file not found

- Ensure you committed your `sapiens_config.yaml` to the repo
- Check the `CONFIG_FILE` path is correct
