# Quick Start: GitHub

Get repo-sapiens running on your GitHub repository in 5 minutes.

---

## Prerequisites

- GitHub repository (public or private)
- GitHub Personal Access Token with `repo` scope
- AI provider API key (OpenRouter, Anthropic, or OpenAI)

---

## Step 1: Install repo-sapiens

```bash
pip install repo-sapiens==0.5.1
```

---

## Step 2: Initialize Your Repository

```bash
cd your-repo
sapiens init
```

Follow the prompts:
1. **Git provider**: Select `github`
2. **AI agent**: Choose your preferred agent (Claude, Goose, or Builtin)
3. **Deploy workflows**: Select `essential` (or `all` for full automation)

This creates:
- `.sapiens/config.yaml` - Configuration file
- `.github/workflows/sapiens.yaml` - Workflow that calls the reusable dispatcher

---

## Step 3: Add Repository Secrets

Go to **Settings** > **Secrets and variables** > **Actions** and add:

| Secret | Value |
|--------|-------|
| `SAPIENS_GITHUB_TOKEN` | Your GitHub PAT with `repo` scope |
| `SAPIENS_AI_API_KEY` | Your AI provider API key |

### Creating a GitHub PAT

1. Go to https://github.com/settings/tokens/new
2. Select scopes: `repo` (full control)
3. Generate and copy the token

---

## Step 4: Test the Setup

Create an issue with the `needs-planning` label:

```bash
gh issue create --title "Add dark mode support" \
  --body "Implement a dark mode toggle in the settings page." \
  --label "needs-planning"
```

The workflow will automatically:
1. Trigger on the label
2. Generate a development plan
3. Post the plan as a comment
4. Update labels to `plan-review`

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  Issue Created  │────▶│  sapiens.yaml        │────▶│  AI generates   │
│  + label added  │     │  (calls dispatcher)  │     │  plan/code      │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
```

The thin wrapper `.github/workflows/sapiens.yaml` calls the reusable dispatcher hosted at `savorywatt/repo-sapiens`. This means:
- Minimal code in your repo (~20 lines)
- Automatic updates when you bump the version
- Consistent behavior across all repos

---

## Workflow Tiers

Deploy additional automation with workflow tiers:

```bash
# Deploy security scanning workflows
sapiens init --deploy-workflows security

# Deploy all available workflows
sapiens init --deploy-workflows all
```

| Tier | Workflows | Purpose |
|------|-----------|---------|
| `essential` | `sapiens.yaml` | Label-triggered AI automation |
| `core` | `post-merge-docs`, `weekly-test-coverage` | Repository maintenance |
| `security` | `weekly-security-review`, `dependency-audit`, `sbom-license` | Security audits |
| `support` | `daily-issue-triage` | Issue management |

---

## Configuration Reference

`.sapiens/config.yaml`:

```yaml
git_provider:
  provider_type: github
  base_url: https://api.github.com
  api_token: "${SAPIENS_GITHUB_TOKEN}"

repository:
  owner: your-username
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: openai-compatible
  base_url: https://openrouter.ai/api/v1
  model: anthropic/claude-3.5-sonnet
  api_key: "${SAPIENS_AI_API_KEY}"
```

---

## Supported Labels

| Label | Action |
|-------|--------|
| `needs-planning` | Generate development plan |
| `approved` | Implement the approved plan |
| `needs-review` | Run code review |
| `needs-fix` | Apply suggested fixes |
| `requires-qa` | Run QA validation |

---

## Troubleshooting

### Workflow not triggering?

1. Check Actions are enabled: **Settings** > **Actions** > **General**
2. Verify secrets are set correctly
3. Check workflow runs: **Actions** tab

### Permission errors?

Ensure your PAT has `repo` scope and the workflow has proper permissions:

```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
```

### View logs

```bash
gh run list --workflow sapiens.yaml
gh run view <run-id> --log
```

---

## Next Steps

- [Full Documentation](../GETTING_STARTED.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
- [Agent Comparison](../AGENT_COMPARISON.md)
