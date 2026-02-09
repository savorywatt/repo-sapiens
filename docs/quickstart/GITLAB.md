# Quick Start: GitLab

Get repo-sapiens running on your GitLab repository in 10 minutes.

---

## Prerequisites

- GitLab project (gitlab.com or self-hosted 16.0+)
- GitLab Personal Access Token with `api`, `read_repository`, `write_repository` scopes
- An AI provider — one of:
  - **Ollama** (local, free) — requires a running Ollama instance
  - **OpenRouter** — proxy to Claude, GPT-4, etc.
  - **Anthropic** — direct Claude API access
  - **OpenAI** — direct OpenAI API access

---

## Important: GitLab Differences

GitLab works differently from GitHub/Gitea:

| Feature | GitHub/Gitea | GitLab |
|---------|--------------|--------|
| Label triggers | Native workflow triggers | Requires polling daemon OR webhook handler |
| Workflow location | Individual `.yaml` files per label | Single `.gitlab-ci.yml` with remote includes |
| Pull requests | Pull Requests | Merge Requests |
| Terminology | Issues + PRs | Issues + MRs |

**Two automation approaches:**
1. **Daemon mode** (recommended): Polls for labeled issues on a schedule — simple setup
2. **Webhook mode**: Instant triggers via external webhook handler — requires additional infrastructure

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
1. **Git provider discovery** — detects GitLab from your remote URL
2. **Credentials** — prompts for your GitLab PAT and AI provider details
3. **AI provider** — choose from `ollama`, `openai-compatible`, `claude-local`, `goose-local`, or `copilot-local`
4. **Automation mode** — select `daemon` (recommended) or `webhook`
5. **Workflow deployment** — updates `.gitlab-ci.yml` with automation jobs

### Non-Interactive Mode

For scripted or CI setups:

```bash
# With Ollama
export GITLAB_PAT="glpat-xxx"
sapiens init --non-interactive \
  --git-token-env GITLAB_PAT \
  --ai-provider ollama \
  --ai-model qwen3:14b \
  --ai-base-url http://localhost:11434

# With OpenRouter
export GITLAB_PAT="glpat-xxx"
export OPENROUTER_API_KEY="sk-or-xxx"
sapiens init --non-interactive \
  --git-token-env GITLAB_PAT \
  --ai-provider openai-compatible \
  --ai-model anthropic/claude-sonnet-4 \
  --ai-base-url https://openrouter.ai/api/v1 \
  --ai-api-key-env OPENROUTER_API_KEY
```

### What Gets Created

```
your-repo/
├── .sapiens/
│   └── config.yaml              # Local configuration
├── sapiens_config.ci.yaml       # CI/CD configuration (uses env vars)
└── .gitlab-ci.yml               # Updated with sapiens automation jobs
```

> **Note:** Unlike GitHub/Gitea, GitLab uses **remote includes** for workflow templates rather than deploying individual files. The `.gitlab-ci.yml` includes templates hosted in the repo-sapiens repository.

---

## Step 3: Add CI/CD Variables

Go to **Settings** > **CI/CD** > **Variables** and add:

| Variable | Value | Protected | Masked |
|----------|-------|-----------|--------|
| `SAPIENS_GITLAB_TOKEN` | GitLab PAT with `api` + `read/write_repository` | Yes | Yes |
| `SAPIENS_AI_API_KEY` | AI provider API key | Yes | Yes |
| `SAPIENS_AI_PROVIDER` | `ollama` or `openai-compatible` (default: `openai-compatible`) | No | No |
| `SAPIENS_AI_MODEL` | Model name (default: `claude-sonnet-4.5`) | No | No |
| `SAPIENS_AI_BASE_URL` | Provider URL (required for Ollama, e.g., `http://ollama:11434`) | No | No |

> **Important**: Use `SAPIENS_GITLAB_TOKEN`, not `GITLAB_TOKEN`. The `GITLAB_` prefix is reserved by GitLab for internal variables.

### Creating a GitLab PAT

1. Go to **User Settings** > **Access Tokens**
2. Create token with scopes:
   - `api` — Full API access
   - `read_repository` — Read repository
   - `write_repository` — Write repository
3. Set an expiration date and copy the token

---

## Step 4: Configure the Automation Daemon

### Option A: Remote Include (Recommended)

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v2/templates/workflows/gitlab/sapiens/automation-daemon.yaml'

# Override AI provider defaults if needed
variables:
  SAPIENS_AI_PROVIDER: "ollama"
  SAPIENS_AI_MODEL: "qwen3:14b"
  SAPIENS_AI_BASE_URL: "http://ollama.internal:11434"
```

### Option B: Inline Configuration

If you prefer the full configuration in your `.gitlab-ci.yml`:

```yaml
stages:
  - sapiens

sapiens-daemon:
  stage: sapiens
  image: python:3.12-slim
  timeout: 45 minutes
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
    - if: $CI_PIPELINE_SOURCE == "api"
  variables:
    AUTOMATION__GIT_PROVIDER__PROVIDER_TYPE: "gitlab"
    AUTOMATION__GIT_PROVIDER__BASE_URL: $CI_SERVER_URL
    AUTOMATION__GIT_PROVIDER__API_TOKEN: $SAPIENS_GITLAB_TOKEN
    AUTOMATION__REPOSITORY__OWNER: $CI_PROJECT_NAMESPACE
    AUTOMATION__REPOSITORY__NAME: $CI_PROJECT_NAME
    AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: $SAPIENS_AI_PROVIDER
    AUTOMATION__AGENT_PROVIDER__API_KEY: $SAPIENS_AI_API_KEY
    AUTOMATION__AGENT_PROVIDER__MODEL: $SAPIENS_AI_MODEL
    AUTOMATION__AGENT_PROVIDER__BASE_URL: $SAPIENS_AI_BASE_URL
  before_script:
    - pip install --quiet --no-cache-dir repo-sapiens
    - git config --global user.name "Sapiens Bot"
    - git config --global user.email "sapiens-bot@users.noreply.gitlab.com"
  script:
    - sapiens process-all --log-level INFO
  resource_group: sapiens-daemon
```

---

## Step 5: Set Up a Pipeline Schedule

1. Go to **Build** > **Pipeline schedules**
2. Click **New schedule**
3. Configure:
   - Description: "Sapiens Automation"
   - Interval: `*/5 * * * *` (every 5 minutes)
   - Target branch: `main`
4. Save

---

## Step 6: Test the Setup

Create an issue with the `needs-planning` label:

1. Go to **Issues** > **New issue**
2. Title: "Add dark mode support"
3. Description: "Implement a dark mode toggle in the settings page."
4. Labels: Add `needs-planning`
5. Create issue

Wait for the next scheduled pipeline, or trigger manually from **Build** > **Pipelines** > **Run pipeline**.

The automation will:
1. Find issues with automation labels
2. Generate a development plan
3. Post the plan as a note (comment) on the issue

---

## How It Works

### Daemon Mode (Polling)

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Pipeline     │────▶│  sapiens         │────▶│  AI generates   │
│  schedule     │     │  process-all     │     │  plan/code      │
│  (every 5m)  │     │  (checks labels) │     │  + posts note   │
└──────────────┘     └──────────────────┘     └─────────────────┘
```

The daemon job runs on a schedule, fetches all open issues, and processes any with sapiens labels.

### Webhook Mode (Real-Time)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Label added  │────▶│  GitLab webhook  │────▶│  Pipeline        │────▶│  AI process │
│  to issue     │     │  → trigger.py    │     │  trigger + vars  │     │  + post note│
└──────────────┘     └──────────────────┘     └──────────────────┘     └─────────────┘
```

---

## Supported Labels

| Label | Action |
|-------|--------|
| `needs-planning` | Generate development plan |
| `approved` | Implement the approved plan (creates branch + MR) |
| `needs-review` | Run AI code review |
| `needs-fix` | Apply suggested fixes |
| `requires-qa` | Run QA validation |
| `execute` | Generic task execution |

> **Note:** The webhook handler also recognises `sapiens/`-prefixed labels (e.g., `sapiens/needs-planning`).

---

## Workflow Tiers (Recipes)

Additional automation recipes are available as remote includes:

```yaml
include:
  # Core automation daemon
  - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v2/templates/workflows/gitlab/sapiens/automation-daemon.yaml'
  # Add recipe includes as needed:
  # - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v2/templates/workflows/gitlab/sapiens/recipes/weekly-security-review.yaml'
  # - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v2/templates/workflows/gitlab/sapiens/recipes/weekly-dependency-audit.yaml'
```

| Tier | Recipes | Purpose |
|------|---------|---------|
| `essential` | `automation-daemon.yaml` | Scheduled label polling |
| `core` | `post-merge-docs`, `weekly-test-coverage` | Repository maintenance |
| `security` | `weekly-security-review`, `dependency-audit`, `sbom-license` | Security audits |
| `support` | `daily-issue-triage` | Issue management |

---

## Alternative: Webhook Mode (Instant Triggers)

For instant label-triggered automation, deploy a webhook handler. This provides immediate response to label events but requires additional infrastructure.

### 1. Deploy the Webhook Handler

The `webhook-trigger.py` handler receives GitLab webhook events and triggers the sapiens-dispatcher pipeline:

```bash
# Install dependencies
pip install flask requests

# Run the webhook handler
GITLAB_URL=https://gitlab.example.com \
GITLAB_API_TOKEN=glpat-xxx \
TRIGGER_TOKEN=your-pipeline-trigger-token \
python webhook-trigger.py
```

The handler script is located at `templates/workflows/gitlab/examples/webhook-trigger.py`.

### 2. Configure GitLab Webhook

1. Go to **Settings** > **Webhooks**
2. URL: `https://your-webhook-handler.example.com/gitlab-webhook`
3. Trigger: **Issues events**, **Merge request events**
4. Save

### 3. Include the Dispatcher in `.gitlab-ci.yml`

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v2/templates/workflows/gitlab/sapiens-dispatcher.yaml'
```

The dispatcher triggers when the webhook handler sends a pipeline trigger with `SAPIENS_LABEL` and `SAPIENS_ISSUE_NUMBER` variables.

See [Full GitLab Setup Guide](../GITLAB_SETUP.md) for detailed webhook configuration.

---

## Configuration Reference

### Local Configuration (`.sapiens/config.yaml`)

Used for `sapiens` CLI commands run on your machine:

```yaml
git_provider:
  provider_type: gitlab
  base_url: https://gitlab.com
  api_token: "@keyring:gitlab/api_token"  # or "${SAPIENS_GITLAB_TOKEN}"

repository:
  owner: your-group
  name: your-project
  default_branch: main

agent_provider:
  provider_type: ollama              # or: openai-compatible, claude-api
  base_url: http://localhost:11434   # for Ollama
  model: qwen3:14b
```

### CI Configuration

In GitLab, CI configuration is passed via `AUTOMATION__*` environment variables in the pipeline jobs (set from CI/CD variables). No separate `sapiens_config.ci.yaml` is required when using the remote include templates — they generate the config at runtime.

---

## Troubleshooting

### Pipeline not running?

1. Check schedule is active: **Build** > **Pipeline schedules**
2. Verify CI/CD is enabled: **Settings** > **CI/CD**
3. Validate `.gitlab-ci.yml` syntax: **Build** > **Pipeline editor**
4. Check the runner is available and online

### Permission errors?

Ensure your PAT has all three scopes: `api`, `read_repository`, `write_repository`.

### View logs

Go to **Build** > **Pipelines** > click on a pipeline > click on the `sapiens-daemon` job.

### Health check

Verify your local configuration is valid:

```bash
sapiens --config .sapiens/config.yaml health-check
```

### Test locally

```bash
export SAPIENS_GITLAB_TOKEN="glpat-xxx"
export SAPIENS_AI_API_KEY="your-api-key"
sapiens --config .sapiens/config.yaml process-all --log-level DEBUG
```

---

## Next Steps

- [Full GitLab Setup Guide](../GITLAB_SETUP.md) — webhook mode, comment handler
- [Full Documentation](../GETTING_STARTED.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
- [Credentials Guide](../CREDENTIALS.md)
