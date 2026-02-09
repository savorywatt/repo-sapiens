# Quick Start: GitHub

Get repo-sapiens running on your GitHub repository in 5 minutes.

---

## Prerequisites

- GitHub repository (public or private)
- GitHub Personal Access Token (classic) with `repo` scope
- An AI provider — one of:
  - **Ollama** (local, free) — requires a running Ollama instance
  - **OpenRouter** — proxy to Claude, GPT-4, etc.
  - **Anthropic** — direct Claude API access
  - **OpenAI** — direct OpenAI API access

---

## Step 1: Install repo-sapiens

```bash
pip install repo-sapiens
```

Verify the installation:

```bash
sapiens --version
```

---

## Step 2: Initialize Your Repository

### Interactive Mode (Recommended)

```bash
cd your-repo
sapiens init
```

The wizard will walk you through:
1. **Git provider discovery** — detects GitHub from your remote URL
2. **Credentials** — prompts for your GitHub PAT and AI API key
3. **AI provider** — choose from `ollama`, `openai-compatible`, `claude-local`, `goose-local`, or `copilot-local`
4. **Repository secrets** — optionally sets up GitHub Actions secrets via the `gh` CLI
5. **Workflow deployment** — deploys CI/CD workflow templates to `.github/workflows/sapiens/`

### Non-Interactive Mode

For scripted or CI setups:

```bash
# With Ollama (local LLM, no AI API key needed)
export GITHUB_TOKEN="ghp_xxx"
sapiens init --non-interactive \
  --git-token-env GITHUB_TOKEN \
  --ai-provider ollama \
  --ai-model qwen3:14b \
  --ai-base-url http://localhost:11434

# With OpenRouter
export GITHUB_TOKEN="ghp_xxx"
export OPENROUTER_API_KEY="sk-or-xxx"
sapiens init --non-interactive \
  --git-token-env GITHUB_TOKEN \
  --ai-provider openai-compatible \
  --ai-model anthropic/claude-sonnet-4 \
  --ai-base-url https://openrouter.ai/api/v1 \
  --ai-api-key-env OPENROUTER_API_KEY
```

### What Gets Created

```
your-repo/
├── .sapiens/
│   └── config.yaml                          # Local configuration
├── sapiens_config.ci.yaml                   # CI/CD configuration (uses env vars)
└── .github/
    └── workflows/
        └── sapiens/
            ├── process-label.yaml           # Label-triggered dispatcher
            ├── needs-planning.yaml          # Planning workflow
            ├── approved.yaml                # Implementation workflow
            ├── needs-review.yaml            # Code review workflow
            ├── needs-fix.yaml               # Fix workflow
            ├── requires-qa.yaml             # QA validation workflow
            ├── process-issue.yaml           # Direct issue processing
            ├── process-comment.yaml         # Comment-triggered actions
            ├── execute-task.yaml            # Task execution
            └── prompts/                     # System prompts for each stage
                ├── needs-planning.md
                ├── approved.md
                ├── needs-review.md
                └── ...
```

---

## Step 3: Add Repository Secrets

If you skipped `--setup-secrets` during init, add them manually:

Go to **Settings** > **Secrets and variables** > **Actions** and add:

| Secret | Value | Required |
|--------|-------|----------|
| `SAPIENS_GITHUB_TOKEN` | GitHub PAT with `repo` scope | Always |
| `SAPIENS_CLAUDE_API_KEY` | AI provider API key | For cloud AI providers |

> **Note**: If using Ollama or another local AI provider in your Actions runner, you only need `SAPIENS_GITHUB_TOKEN`.

### Creating a GitHub PAT (Classic)

1. Go to [github.com/settings/tokens/new](https://github.com/settings/tokens/new)
2. Set an expiration (90 days recommended)
3. Select scopes: **`repo`** (full control of private repositories)
4. Generate and copy the token

---

## Step 4: Test the Setup

Create an issue with the `needs-planning` label:

```bash
gh issue create --title "Add dark mode support" \
  --body "Implement a dark mode toggle in the settings page." \
  --label "needs-planning"
```

The workflow will automatically:
1. Trigger on the `needs-planning` label
2. Install repo-sapiens in the Actions runner
3. Generate a development plan using your configured AI provider
4. Post the plan as a comment on the issue

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│  Issue Created   │────▶│  .github/workflows/      │────▶│  AI generates   │
│  + label added   │     │  sapiens/<label>.yaml     │     │  plan/code      │
└─────────────────┘     └──────────────────────────┘     └─────────────────┘
```

Each label has a dedicated workflow file in `.github/workflows/sapiens/`. When a label is added to an issue or PR, the matching workflow:

1. Checks out your repository
2. Installs repo-sapiens
3. Runs the appropriate `sapiens` CLI command with a stage-specific system prompt
4. Posts results back as a comment

---

## Supported Labels

| Label | Workflow | Action |
|-------|----------|--------|
| `needs-planning` | `needs-planning.yaml` | Generate a development plan from the issue |
| `approved` | `approved.yaml` | Implement the approved plan (creates branch + PR) |
| `needs-review` | `needs-review.yaml` | Run AI code review on the changes |
| `needs-fix` | `needs-fix.yaml` | Apply suggested fixes from review |
| `requires-qa` | `requires-qa.yaml` | Run QA validation |
| `execute` | `process-label.yaml` | Generic task execution |

---

## Workflow Tiers

Deploy additional automation with workflow tiers:

```bash
# Deploy security scanning workflows
sapiens init --deploy-workflows security

# Deploy all available workflows
sapiens init --deploy-workflows all

# Remove workflows you don't need
sapiens init --remove-workflows support
```

| Tier | Workflows | Purpose |
|------|-----------|---------|
| `essential` | Label-triggered workflows (above) | Core AI automation |
| `core` | `post-merge-docs`, `weekly-test-coverage` | Repository maintenance |
| `security` | `weekly-security-review`, `dependency-audit`, `sbom-license` | Security audits |
| `support` | `daily-issue-triage` | Issue management |

---

## Configuration Reference

### Local Configuration (`.sapiens/config.yaml`)

Used for `sapiens` CLI commands run on your machine:

```yaml
git_provider:
  provider_type: github
  base_url: https://github.com
  api_token: "@keyring:github/api_token"  # or "${GITHUB_TOKEN}"

repository:
  owner: your-username
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: ollama              # or: openai-compatible, claude-api
  base_url: http://localhost:11434   # for Ollama
  model: qwen3:14b
```

### CI Configuration (`sapiens_config.ci.yaml`)

Used by GitHub Actions — credentials come from environment variables set by secrets:

```yaml
git_provider:
  provider_type: github
  base_url: https://github.com
  api_token: "${SAPIENS_GITHUB_TOKEN}"

repository:
  owner: your-username
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: openai-compatible
  base_url: https://openrouter.ai/api/v1
  model: anthropic/claude-sonnet-4
  api_key: "${SAPIENS_CLAUDE_API_KEY}"
```

---

## Troubleshooting

### Workflow not triggering?

1. Check Actions are enabled: **Settings** > **Actions** > **General**
2. Verify secrets are set: **Settings** > **Secrets and variables** > **Actions**
3. Confirm the label name matches exactly (case-sensitive)
4. Check workflow runs: **Actions** tab > filter by workflow name

### Permission errors?

Ensure your PAT has `repo` scope. The workflow templates include the necessary permissions:

```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
```

### View logs

```bash
# List recent workflow runs
gh run list --workflow sapiens/process-label.yaml

# View logs for a specific run
gh run view <run-id> --log
```

### Health check

Verify your local configuration is valid:

```bash
sapiens --config .sapiens/config.yaml health-check
```

---

## Next Steps

- [Full Documentation](../GETTING_STARTED.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
- [Agent Comparison](../AGENT_COMPARISON.md)
- [Credentials Guide](../CREDENTIALS.md)
