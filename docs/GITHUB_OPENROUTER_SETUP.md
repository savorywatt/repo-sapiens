# Setting Up repo-sapiens with GitHub and OpenRouter

A complete, step-by-step guide for configuring repo-sapiens automation on a GitHub repository using OpenRouter as the AI provider.

---

## Overview

This guide covers:
- Using **GitHub** as your Git provider
- Using **OpenRouter** (OpenAI-compatible API) for AI agent operations
- Deploying workflow templates from this project
- Full automation from issue planning to PR creation

---

## Prerequisites

Before you begin, ensure you have:

- [ ] A GitHub account with permission to create repositories
- [ ] Python 3.11 or higher installed locally
- [ ] Git installed and configured
- [ ] An **OpenRouter API key** from https://openrouter.ai/

---

## Part 1: GitHub Setup

### Step 1.1: Create or Choose a Repository

You can use an existing repository or create a new one:

1. Go to https://github.com/new
2. Fill in the details:
   - **Repository name**: e.g., `my-project`
   - **Visibility**: Private or Public
   - **Initialize**: Check "Add a README file"
3. Click **Create repository**

### Step 1.2: Clone the Repository Locally

```bash
git clone https://github.com/your-username/my-project.git
cd my-project
```

### Step 1.3: Create a GitHub Personal Access Token (PAT)

The automation needs a token with repository and workflow permissions:

1. Go to **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Configure the token:
   - **Token name**: `repo-sapiens-automation`
   - **Expiration**: Choose appropriate duration (90 days recommended)
   - **Repository access**: Select the specific repository or "All repositories"
   - **Permissions**:
     - **Repository permissions**:
       - Contents: Read and write
       - Issues: Read and write
       - Pull requests: Read and write
       - Workflows: Read and write (if deploying workflows)
4. Click **Generate token**
5. **Copy and save the token immediately** - you won't see it again!

> **Classic tokens** also work. Select scopes: `repo`, `workflow`

---

## Part 2: OpenRouter Setup

OpenRouter provides access to multiple AI models through an OpenAI-compatible API.

### Step 2.1: Create an OpenRouter Account

1. Go to https://openrouter.ai/
2. Sign up or log in
3. Add credits to your account

### Step 2.2: Get Your API Key

1. Navigate to **Keys** in the OpenRouter dashboard
2. Click **Create Key**
3. Copy your API key (starts with `sk-or-`)

### Step 2.3: Choose a Model

OpenRouter provides access to many models. Recommended options for code tasks:

| Model | ID | Quality | Cost |
|-------|-----|---------|------|
| Claude 3.5 Sonnet | `anthropic/claude-3.5-sonnet` | Excellent | $$ |
| Claude 3 Haiku | `anthropic/claude-3-haiku` | Good | $ |
| GPT-4o | `openai/gpt-4o` | Excellent | $$$ |
| GPT-4o mini | `openai/gpt-4o-mini` | Good | $ |
| Llama 3.1 70B | `meta-llama/llama-3.1-70b-instruct` | Very Good | $$ |
| DeepSeek Coder V2 | `deepseek/deepseek-coder` | Good | $ |

For this guide, we'll use `anthropic/claude-3.5-sonnet` as it provides excellent code understanding.

---

## Part 3: Install and Initialize repo-sapiens

### Step 3.1: Install repo-sapiens

```bash
# Option A: Install from PyPI (recommended)
pip install repo-sapiens

# Option B: Using uv
uv tool install repo-sapiens
```

Verify the installation:

```bash
sapiens --help
```

### Step 3.2: Initialize in Your Repository

Navigate to your repository and run the init wizard:

```bash
cd /path/to/my-project
sapiens init
```

When prompted:
1. **Git provider**: Select `github`
2. **GitHub token**: Enter your PAT
3. **AI provider**: Select `openai-compatible` (OpenRouter uses OpenAI-compatible API)
4. **Base URL**: Enter `https://openrouter.ai/api/v1`
5. **API Key**: Enter your OpenRouter key
6. **Model**: Enter `anthropic/claude-3.5-sonnet` (or your preferred model)

This creates `.sapiens/config.yaml` with your configuration.

---

## Part 4: Configure GitHub Repository Secrets

The GitHub Actions workflows need access to your credentials via repository secrets.

### Step 4.1: Navigate to Repository Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Step 4.2: Add Required Secrets

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SAPIENS_GITHUB_TOKEN` | Your GitHub PAT | Token for Git operations and API calls |
| `SAPIENS_AI_API_KEY` | Your OpenRouter key | Token for AI model access |

To add each secret:
1. Click **New repository secret**
2. Enter the **Name** exactly as shown
3. Paste the **Value**
4. Click **Add secret**

### Step 4.3: Verify Secrets

Your secrets page should show:
```
SAPIENS_GITHUB_TOKEN    Updated just now
SAPIENS_AI_API_KEY      Updated just now
```

---

## Part 5: Create Workflow File

repo-sapiens uses a **reusable workflow** approach. Instead of copying multiple workflow files, you create a single thin wrapper that references the official dispatcher workflow.

### Step 5.1: Create the Workflow File

Create a single workflow file at `.github/workflows/sapiens.yaml`:

```bash
mkdir -p .github/workflows
```

Create the file with the following content:

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
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
```

This single file (~20 lines) replaces the need for multiple workflow files.

### Step 5.2: Customize the Model (Optional)

Change `ai_model` to use a different OpenRouter model:

```yaml
# For faster, cheaper operations
ai_model: anthropic/claude-3-haiku

# For GPT-4
ai_model: openai/gpt-4o

# For budget-friendly option
ai_model: openai/gpt-4o-mini
```

### Step 5.3: Commit and Push

```bash
git add .github/workflows/sapiens.yaml
git commit -m "Add repo-sapiens automation workflow"
git push origin main
```

**Benefits of the reusable workflow approach:**

- Single file instead of 7+ workflow files
- Automatic updates when you bump the version tag
- Less maintenance overhead
- Consistent behavior across all repositories

---

## Part 6: Create Required Labels

The automation uses labels to track workflow state.

### Step 6.1: Navigate to Labels

1. Go to your repository
2. Click **Issues** → **Labels**
3. Click **New label** for each label below

### Step 6.2: Create Labels

| Label Name | Color | Description |
|------------|-------|-------------|
| `needs-planning` | `#0052CC` (blue) | Issue needs a development plan |
| `proposed` | `#36B37E` (green) | Plan has been proposed |
| `approved` | `#00875A` (dark green) | Plan approved, ready for tasks |
| `task` | `#6554C0` (purple) | This is a task issue |
| `execute` | `#FF5630` (red) | Task ready to execute |
| `needs-review` | `#FFAB00` (yellow) | PR needs code review |
| `needs-fix` | `#FF8B00` (orange) | Changes needed based on review |
| `requires-qa` | `#00B8D9` (cyan) | Ready for QA/testing |
| `qa-passed` | `#36B37E` (green) | QA passed |
| `qa-failed` | `#FF5630` (red) | QA failed |
| `completed` | `#6B778C` (gray) | Work completed |

**Quick creation via GitHub CLI:**

```bash
# Using gh CLI
gh label create "needs-planning" --color "0052CC" --description "Issue needs a development plan"
gh label create "proposed" --color "36B37E" --description "Plan has been proposed"
gh label create "approved" --color "00875A" --description "Plan approved, ready for tasks"
gh label create "task" --color "6554C0" --description "This is a task issue"
gh label create "execute" --color "FF5630" --description "Task ready to execute"
gh label create "needs-review" --color "FFAB00" --description "PR needs code review"
gh label create "needs-fix" --color "FF8B00" --description "Changes needed based on review"
gh label create "requires-qa" --color "00B8D9" --description "Ready for QA/testing"
gh label create "qa-passed" --color "36B37E" --description "QA passed"
gh label create "qa-failed" --color "FF5630" --description "QA failed"
gh label create "completed" --color "6B778C" --description "Work completed"
```

---

## Part 7: Test Your Setup

### Step 7.1: Verify GitHub Actions Is Enabled

1. Go to your repository → **Actions** tab
2. If prompted, enable Actions for your repository
3. You should see your workflows listed

### Step 7.2: Create a Test Issue

1. Go to **Issues** → **New issue**
2. Create an issue:
   - **Title**: `Add a hello world function`
   - **Body**:
     ```
     Create a simple Python function that prints "Hello, World!"

     Requirements:
     - Create a file called `hello.py`
     - Add a function `greet()` that prints the greeting
     - Include a docstring
     ```

### Step 7.3: Trigger the Automation

1. On the issue page, click **Labels** (right sidebar)
2. Add the `needs-planning` label
3. Watch the automation run!

### Step 7.4: Monitor Progress

1. Go to the **Actions** tab
2. You should see the "Needs Planning" workflow running
3. Click on it to view logs
4. When complete, check the issue for the plan comment

---

## Part 8: Configuration Reference

### Local Configuration File

After `sapiens init`, your config is at `.sapiens/config.yaml`:

```yaml
# .sapiens/config.yaml for GitHub + OpenRouter

git_provider:
  provider_type: github
  base_url: https://api.github.com
  api_token: "@keyring:github/api_token"  # Secure reference

repository:
  owner: your-username
  name: my-project
  default_branch: main

agent_provider:
  provider_type: openai-compatible
  base_url: https://openrouter.ai/api/v1
  model: anthropic/claude-3.5-sonnet
  api_key: "@keyring:openrouter/api_key"

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3
```

### Environment Variable Overrides

For CI/CD (GitHub Actions), all configuration is passed via environment variables:

```bash
# Git provider
AUTOMATION__GIT_PROVIDER__PROVIDER_TYPE=github
AUTOMATION__GIT_PROVIDER__BASE_URL=https://api.github.com
AUTOMATION__GIT_PROVIDER__API_TOKEN=ghp_xxxx

# Repository
AUTOMATION__REPOSITORY__OWNER=your-username
AUTOMATION__REPOSITORY__NAME=my-project

# Agent provider (OpenRouter)
AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE=openai-compatible
AUTOMATION__AGENT_PROVIDER__BASE_URL=https://openrouter.ai/api/v1
AUTOMATION__AGENT_PROVIDER__API_KEY=sk-or-xxxx
AUTOMATION__AGENT_PROVIDER__MODEL=anthropic/claude-3.5-sonnet
```

### Alternative AI Providers

You can use other providers by changing the agent configuration:

#### Direct Claude API

```yaml
agent_provider:
  provider_type: claude-api
  model: claude-sonnet-4.5
  api_key: "@keyring:claude/api_key"
```

Secrets needed: `SAPIENS_AI_API_KEY` = Anthropic API key

#### Ollama (Self-Hosted)

```yaml
agent_provider:
  provider_type: ollama
  base_url: http://localhost:11434
  model: llama3.1:8b
```

Secrets needed: None (Ollama doesn't require authentication)

Environment variables:
```bash
AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE=ollama
AUTOMATION__AGENT_PROVIDER__BASE_URL=http://your-ollama-server:11434
AUTOMATION__AGENT_PROVIDER__MODEL=llama3.1:8b
```

---

## Part 9: Workflow Reference

### How It Works

The single `sapiens.yaml` workflow file triggers on any label event and passes it to the sapiens dispatcher. The dispatcher handles all label routing internally:

| Label | Action |
|-------|--------|
| `needs-planning` | Generate development plan from issue |
| `approved` | Create task issues from approved plan |
| `execute` | Implement task and create PR |
| `needs-review` | Run AI code review on PR |
| `needs-fix` | Create fix proposal from review feedback |
| `requires-qa` | Run build and tests |

For the complete workflow reference including all inputs and configuration options, see [WORKFLOW_REFERENCE.md](WORKFLOW_REFERENCE.md).

### Automation Flow

```
Issue Created
    ↓
[needs-planning] → Plan generated → [proposed]
    ↓
User reviews plan
    ↓
[approved] → Tasks created → [task] + [execute]
    ↓
Task executes → PR created → [needs-review]
    ↓
AI review runs
    ↓
[needs-fix] ← Issues found    OR    Approved → [requires-qa]
    ↓                                     ↓
Fix applied                          QA runs
    ↓                                     ↓
[needs-review]                    [qa-passed] or [qa-failed]
                                          ↓
                                   Ready to merge!
```

---

## Part 10: Troubleshooting

### Workflow Doesn't Trigger

**Checklist:**
1. Are GitHub Actions enabled for the repository?
2. Does `.github/workflows/sapiens.yaml` exist?
3. Did you push the workflow to the `main` branch?
4. Is the label name exactly correct (case-sensitive)?
5. Can the workflow access the reusable workflow? (Public repos work automatically; private repos may need additional permissions)

**Debug:**
```bash
# Verify workflow is present
ls -la .github/workflows/sapiens.yaml

# Check Actions tab for any errors
```

### Authentication Errors

**Symptoms:** `401 Unauthorized` or `403 Forbidden`

**Checklist:**
1. Is `SAPIENS_GITHUB_TOKEN` secret set?
2. Does the PAT have the required permissions?
3. Has the token expired?

**Debug:**
```bash
# Test token locally
curl -H "Authorization: token YOUR_TOKEN" \
  "https://api.github.com/user"
```

### OpenRouter API Errors

**Symptoms:** `401 Invalid API Key` or model errors

**Checklist:**
1. Is `SAPIENS_AI_API_KEY` secret set correctly?
2. Is the API key valid (starts with `sk-or-`)?
3. Does your account have credits?
4. Is the model ID correct?

**Debug:**
```bash
# Test OpenRouter API
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer sk-or-your-key"
```

### "Module not found" Error

**Symptoms:** `ModuleNotFoundError: No module named 'repo_sapiens'`

**Solution:** Ensure the install step uses `pip install repo-sapiens`:

```yaml
- name: Install sapiens
  run: pip install repo-sapiens
```

### Rate Limiting

**GitHub:** 5,000 requests/hour for authenticated requests

**OpenRouter:** Varies by model and plan

**Solutions:**
- Reduce workflow frequency
- Implement retries with backoff
- Upgrade API plan if needed

---

## Quick Reference

### Required Secrets

| Secret | Value | Required For |
|--------|-------|--------------|
| `SAPIENS_GITHUB_TOKEN` | GitHub PAT | All workflows |
| `SAPIENS_AI_API_KEY` | OpenRouter API key | AI operations |

### CLI Commands

```bash
# Initialize repo-sapiens
sapiens init

# Process single issue
sapiens process-issue --issue 42

# Run health check
sapiens health-check

# Process label event
sapiens process-label --label needs-planning --issue 42

# Run as daemon (local)
sapiens daemon --interval 60
```

### OpenRouter Model IDs

```
anthropic/claude-3.5-sonnet      # Recommended
anthropic/claude-3-haiku         # Faster, cheaper
openai/gpt-4o                    # Alternative
openai/gpt-4o-mini               # Budget option
meta-llama/llama-3.1-70b-instruct
deepseek/deepseek-coder
```

---

## Support

- **Documentation**: See the `docs/` directory
- **Issues**: https://github.com/savorywatt/repo-sapiens/issues
- **OpenRouter**: https://openrouter.ai/docs

Happy automating!
