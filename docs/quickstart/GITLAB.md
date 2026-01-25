# Quick Start: GitLab

Get repo-sapiens v0.5.1 running on your GitLab repository in 10 minutes.

---

## Prerequisites

- GitLab project (gitlab.com or self-hosted 16.0+)
- GitLab Personal Access Token with `api`, `read_repository`, `write_repository` scopes
- AI provider API key (OpenRouter, Anthropic, or OpenAI)

---

## Important: GitLab Differences

GitLab works differently from GitHub/Gitea:

| Feature | GitHub/Gitea | GitLab |
|---------|--------------|--------|
| Label triggers | Native workflow triggers | Requires webhook handler OR polling daemon |
| Workflow location | `.github/workflows/` | `.gitlab-ci.yml` (single file) |
| Pull requests | Pull Requests | Merge Requests |
| Reusable workflows | Cross-repo supported | CI/CD Components (16.0+) |

**Two automation approaches:**
1. **Daemon mode** (recommended): Polls for labeled issues on a schedule
2. **Webhook mode**: Instant triggers via external webhook handler

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
1. **Git provider**: Select `gitlab`
2. **GitLab URL**: Enter your instance URL (e.g., `https://gitlab.com`)
3. **AI agent**: Choose your preferred agent
4. **Automation mode**: Select `daemon` (recommended)
5. **Deploy workflows**: Select `essential`

This creates:
- `.sapiens/config.yaml` - Configuration file
- `.gitlab-ci.yml` updates - Automation daemon job

---

## Step 3: Add CI/CD Variables

Go to **Settings** > **CI/CD** > **Variables** and add:

| Variable | Value | Protected | Masked |
|----------|-------|-----------|--------|
| `SAPIENS_GITLAB_TOKEN` | Your GitLab PAT | Yes | Yes |
| `SAPIENS_AI_API_KEY` | Your AI provider API key | Yes | Yes |

### Creating a GitLab PAT

1. Go to **User Settings** > **Access Tokens**
2. Create token with scopes:
   - `api` - Full API access
   - `read_repository` - Read repository
   - `write_repository` - Write repository
3. Copy the token

> **Note**: Use `SAPIENS_GITLAB_TOKEN`, not `GITLAB_TOKEN`. The `GITLAB_` prefix is reserved.

---

## Step 4: Configure the Automation Daemon

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v0.5.1/templates/workflows/gitlab/sapiens/automation-daemon.yaml'

variables:
  SAPIENS_POLL_INTERVAL: "300"  # 5 minutes
  SAPIENS_AI_PROVIDER: "openai-compatible"
  SAPIENS_AI_BASE_URL: "https://openrouter.ai/api/v1"
  SAPIENS_AI_MODEL: "anthropic/claude-3.5-sonnet"
```

Or copy the full daemon configuration:

```yaml
# .gitlab-ci.yml

stages:
  - automation

sapiens-daemon:
  stage: automation
  image: python:3.12-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  script:
    - pip install repo-sapiens==0.5.1
    - sapiens process-all --provider gitlab
  variables:
    SAPIENS_GITLAB_TOKEN: $SAPIENS_GITLAB_TOKEN
    SAPIENS_AI_API_KEY: $SAPIENS_AI_API_KEY
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

Wait for the next scheduled pipeline (or trigger manually from **Build** > **Pipelines** > **Run pipeline**).

The automation will:
1. Find issues with automation labels
2. Generate a development plan
3. Post the plan as a comment
4. Update labels to `plan-review`

---

## Alternative: Webhook Mode (Instant Triggers)

For instant label-triggered automation, deploy a webhook handler. This provides immediate response to label events but requires additional infrastructure.

### Deploy the Comment Webhook Handler

The `gitlab-comment-webhook.py` handler responds to `@sapiens` mentions in issue comments:

```bash
# Using Docker
docker run -d \
  -p 8000:8000 \
  -e GITLAB_URL=https://gitlab.com \
  -e GITLAB_API_TOKEN=$SAPIENS_GITLAB_TOKEN \
  -e GITLAB_WEBHOOK_SECRET=your-secure-secret \
  -e TRIGGER_REF=main \
  ghcr.io/savorywatt/repo-sapiens/gitlab-webhook:0.5.1
```

### Configure GitLab Webhook

1. Go to **Settings** > **Webhooks**
2. URL: `https://your-webhook-handler.example.com/webhook/gitlab/comment`
3. Secret token: Match `GITLAB_WEBHOOK_SECRET`
4. Trigger: Select **Comments** (Note events)
5. Save

### Update `.gitlab-ci.yml` for Webhook Mode

Include the dispatcher for webhook-triggered pipelines:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/savorywatt/repo-sapiens/v0.5.1/templates/workflows/gitlab/sapiens-dispatcher.yaml'
```

Or add the job manually:

```yaml
sapiens-process:
  stage: automation
  image: python:3.12-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "trigger" && $SAPIENS_LABEL && $SAPIENS_ISSUE_NUMBER
  variables:
    AUTOMATION__GIT_PROVIDER__API_TOKEN: $SAPIENS_GITLAB_TOKEN
  script:
    - pip install repo-sapiens==0.5.1
    - sapiens process-label --label "$SAPIENS_LABEL" --issue "$SAPIENS_ISSUE_NUMBER" --source gitlab
```

---

## Configuration Reference

`.sapiens/config.yaml`:

```yaml
git_provider:
  provider_type: gitlab
  base_url: https://gitlab.com
  api_token: "${SAPIENS_GITLAB_TOKEN}"

repository:
  owner: your-group
  name: your-project
  default_branch: main

agent_provider:
  provider_type: openai-compatible
  base_url: https://openrouter.ai/api/v1
  model: anthropic/claude-3.5-sonnet
  api_key: "${SAPIENS_AI_API_KEY}"

automation:
  mode: daemon
  poll_interval: 300
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

### Pipeline not running?

1. Check schedule is active: **Build** > **Pipeline schedules**
2. Verify CI/CD is enabled: **Settings** > **CI/CD**
3. Check for syntax errors in `.gitlab-ci.yml`

### Permission errors?

Ensure your PAT has all three scopes: `api`, `read_repository`, `write_repository`.

### View logs

Go to **Build** > **Pipelines** > click on a pipeline > click on job.

### Test locally

```bash
export SAPIENS_GITLAB_TOKEN="your-token"
export SAPIENS_AI_API_KEY="your-api-key"  # pragma: allowlist secret
sapiens process-all --provider gitlab
```

---

## Next Steps

- [Full GitLab Setup Guide](../GITLAB_SETUP.md)
- [Full Documentation](../GETTING_STARTED.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
