# Quick Start: Gitea

Get repo-sapiens running on your Gitea repository in 5 minutes.

---

## Prerequisites

- Gitea instance (1.21+ recommended for reliable Actions label triggers)
- Gitea API token with `repo` or `write:repository` scope
- Gitea Actions enabled with a registered runner
- An AI provider — one of:
  - **Ollama** (local, free) — the default for Gitea templates
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
1. **Git provider discovery** — detects Gitea from your remote URL
2. **Credentials** — prompts for your Gitea API token and AI provider details
3. **AI provider** — choose from `ollama`, `openai-compatible`, `claude-local`, `goose-local`, or `copilot-local`
4. **Repository secrets** — optionally sets up Gitea Actions secrets via the API
5. **Workflow deployment** — deploys CI/CD workflow templates to `.gitea/workflows/sapiens/`

### Non-Interactive Mode

For scripted or CI setups:

```bash
# With Ollama (typical self-hosted setup)
export GITEA_TOKEN="your-gitea-token"
sapiens init --non-interactive \
  --git-token-env GITEA_TOKEN \
  --ai-provider ollama \
  --ai-model qwen3:14b \
  --ai-base-url http://localhost:11434

# With OpenRouter
export GITEA_TOKEN="your-gitea-token"
export OPENROUTER_API_KEY="sk-or-xxx"
sapiens init --non-interactive \
  --git-token-env GITEA_TOKEN \
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
└── .gitea/
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
            ├── automation-daemon.yaml       # Polling daemon (optional)
            └── prompts/                     # System prompts for each stage
                ├── needs-planning.md
                ├── approved.md
                ├── needs-review.md
                └── ...
```

> **Note:** Unlike GitHub, Gitea does not support cross-repository reusable workflows. repo-sapiens deploys **complete workflow files** directly into your repository. Updates require re-running `sapiens init --deploy-workflows` or manually updating the files.

---

## Step 3: Add Repository Secrets

If you skipped secret setup during init, add them manually:

Go to **Settings** > **Actions** > **Secrets** and add:

| Secret | Value | Required |
|--------|-------|----------|
| `SAPIENS_GITEA_TOKEN` | Gitea API token with `repo` scope | Always |
| `SAPIENS_OLLAMA_URL` | Ollama base URL (e.g., `http://192.168.1.100:11434`) | For Ollama |
| `SAPIENS_CLAUDE_API_KEY` | AI provider API key | For cloud AI providers |

> **Important**: Use `SAPIENS_GITEA_TOKEN`, not `GITEA_TOKEN`. The `GITEA_` prefix is reserved by Gitea for internal variables.

### Creating a Gitea API Token

1. Go to **Settings** > **Applications** > **Access Tokens**
2. Enter a token name (e.g., `sapiens-automation`)
3. Select permissions: **`repo`** or **`write:repository`**
4. Generate and copy the token

---

## Step 4: Test the Setup

Create an issue with the `needs-planning` label:

1. Go to **Issues** > **New Issue**
2. Title: "Add dark mode support"
3. Body: "Implement a dark mode toggle in the settings page."
4. Labels: Add `needs-planning`
5. Submit

The workflow will automatically:
1. Trigger on the `needs-planning` label
2. Install repo-sapiens in the Actions runner
3. Generate a development plan using your configured AI provider
4. Post the plan as a comment on the issue

---

## How It Works

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│  Issue Created   │────▶│  .gitea/workflows/       │────▶│  AI generates   │
│  + label added   │     │  sapiens/<label>.yaml     │     │  plan/code      │
└─────────────────┘     └──────────────────────────┘     └─────────────────┘
```

Each label has a dedicated workflow file in `.gitea/workflows/sapiens/`. When a label is added to an issue or PR, the matching workflow:

1. Checks out your repository
2. Installs repo-sapiens
3. Runs the appropriate `sapiens` CLI command with a stage-specific system prompt
4. Posts results back as a comment via the Gitea API

**Gitea quirk:** Gitea sets `github.event.label` to `null` on label events, so workflows detect labels via `contains(github.event.issue.labels.*.name, '<label>')` instead.

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
  provider_type: gitea
  base_url: https://gitea.example.com
  api_token: "@keyring:gitea/api_token"  # or "${GITEA_TOKEN}"

repository:
  owner: your-org
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: ollama
  base_url: http://localhost:11434
  model: qwen3:14b
```

### CI Configuration (`sapiens_config.ci.yaml`)

Used by Gitea Actions — credentials come from environment variables set by secrets:

```yaml
git_provider:
  provider_type: gitea
  base_url: "${AUTOMATION__GIT_PROVIDER__BASE_URL}"
  api_token: "${SAPIENS_GITEA_TOKEN}"

repository:
  owner: your-org
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: ollama
  base_url: "${AUTOMATION__AGENT_PROVIDER__BASE_URL}"
  model: qwen3:14b
```

> **Tip:** The Gitea templates pass configuration via `AUTOMATION__*` environment variables in the workflow files, which override the config file values. The `sapiens_config.ci.yaml` is the base, and environment variables provide the runtime values.

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

4. Verify the runner is online: **Site Administration** > **Runners**

---

## Troubleshooting

### Workflow not triggering?

1. Check Actions are enabled: **Settings** > **Actions**
2. Verify a runner is registered and online
3. Check workflow files exist in `.gitea/workflows/sapiens/`
4. Confirm the label name matches exactly (case-sensitive)
5. Ensure the runner can access PyPI (or your Ollama instance)

### Permission errors?

Ensure your API token has `repo` or `write:repository` scope.

### Ollama not reachable from runner?

If your Ollama instance is on a different machine from the Actions runner, ensure:
- The `SAPIENS_OLLAMA_URL` secret points to a routable address (not `localhost`)
- Firewall allows traffic on port 11434
- Ollama is bound to `0.0.0.0`, not just `127.0.0.1` (`OLLAMA_HOST=0.0.0.0`)

### View logs

Go to the **Actions** tab in your repository to see workflow runs and logs.

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
