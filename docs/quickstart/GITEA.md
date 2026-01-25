# Quick Start: Gitea

Get repo-sapiens running on your Gitea repository in 5 minutes.

---

## Prerequisites

- Gitea instance (1.19+ recommended for Actions support)
- Gitea API token with `repo` scope
- AI provider API key (OpenRouter, Anthropic, or OpenAI)
- Gitea Actions enabled on your instance

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
1. **Git provider**: Select `gitea`
2. **Gitea URL**: Enter your instance URL (e.g., `https://gitea.example.com`)
3. **AI agent**: Choose your preferred agent (Claude, Goose, or Builtin)
4. **Deploy workflows**: Select `essential` (or `all` for full automation)

This creates:
- `.sapiens/config.yaml` - Configuration file
- `.gitea/workflows/sapiens/*.yaml` - Full workflow files for each automation stage
- `.gitea/workflows/sapiens/prompts/*.md` - AI prompt templates for each workflow

---

## Step 3: Add Repository Secrets

Go to **Settings** > **Actions** > **Secrets** and add:

| Secret | Value |
|--------|-------|
| `SAPIENS_GITEA_TOKEN` | Your Gitea API token |
| `SAPIENS_AI_API_KEY` | Your AI provider API key |

### Creating a Gitea API Token

1. Go to **Settings** > **Applications** > **Access Tokens**
2. Create token with scopes: `repo` (or `write:repository`)
3. Copy the token

> **Note**: Use `SAPIENS_GITEA_TOKEN`, not `GITEA_TOKEN`. The `GITEA_` prefix is reserved by Gitea for internal variables.

---

## Step 4: Test the Setup

Create an issue with the `needs-planning` label:

1. Go to **Issues** > **New Issue**
2. Title: "Add dark mode support"
3. Body: "Implement a dark mode toggle in the settings page."
4. Labels: Add `needs-planning`
5. Submit

The workflow will automatically:
1. Trigger on the label
2. Generate a development plan
3. Post the plan as a comment
4. Update labels to `plan-review`

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  Issue Created  │────▶│  .gitea/workflows/   │────▶│  AI generates   │
│  + label added  │     │  sapiens/*.yaml      │     │  plan/code      │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
```

**Important:** Unlike GitHub, **Gitea does not support cross-repository reusable workflows**. This means:

- repo-sapiens deploys **complete workflow files** directly to your repository
- Workflows live in `.gitea/workflows/sapiens/` (not thin wrappers referencing external repos)
- Updates require re-running `sapiens init` or manually updating workflow files
- You have full control to customize workflows for your specific needs

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
| `essential` | `sapiens.yaml`, `process-label.yaml` | Label-triggered AI automation |
| `core` | `post-merge-docs`, `weekly-test-coverage` | Repository maintenance |
| `security` | `weekly-security-review`, `dependency-audit`, `sbom-license` | Security audits |
| `support` | `daily-issue-triage` | Issue management |

---

## Configuration Reference

`.sapiens/config.yaml`:

```yaml
git_provider:
  provider_type: gitea
  base_url: https://gitea.example.com
  api_token: "${SAPIENS_GITEA_TOKEN}"

repository:
  owner: your-org
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

## Enabling Gitea Actions

If Actions aren't enabled on your Gitea instance:

1. Edit `app.ini`:
   ```ini
   [actions]
   ENABLED = true
   ```

2. Restart Gitea

3. Register a runner:
   ```bash
   # Using act_runner
   act_runner register --instance https://gitea.example.com --token <token>
   act_runner daemon
   ```

---

## Troubleshooting

### Workflow not triggering?

1. Check Actions are enabled: **Settings** > **Actions**
2. Verify a runner is registered and online
3. Check workflow files exist in `.gitea/workflows/sapiens/`
4. Ensure the runner can access PyPI to install repo-sapiens

### Permission errors?

Ensure your API token has `repo` or `write:repository` scope.

### View logs

Go to **Actions** tab in your repository to see workflow runs and logs.

---

## Next Steps

- [Full Documentation](../GETTING_STARTED.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
- [Agent Comparison](../AGENT_COMPARISON.md)
