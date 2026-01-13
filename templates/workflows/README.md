# Sapiens Workflows

Ready-to-use CI/CD workflow templates for repo-sapiens automated issue processing and task management.

## Quick Setup

### For Gitea

```bash
# Copy core workflows to your repo
mkdir -p .gitea/workflows/sapiens
cp templates/workflows/gitea/sapiens/*.yaml .gitea/workflows/sapiens/

# Optionally copy recipe workflows
mkdir -p .gitea/workflows/sapiens/recipes
cp templates/workflows/gitea/sapiens/recipes/*.yaml .gitea/workflows/sapiens/recipes/
```

### For GitHub

```bash
# Copy core workflows to your repo
mkdir -p .github/workflows/sapiens
cp templates/workflows/github/sapiens/*.yaml .github/workflows/sapiens/

# Optionally copy recipe workflows
mkdir -p .github/workflows/sapiens/recipes
cp templates/workflows/github/sapiens/recipes/*.yaml .github/workflows/sapiens/recipes/
```

## Configuration

### Understanding Agents vs LLM Providers

**Agent Providers** (execute tasks, use tools):
- `claude-local` - Claude Code CLI agent (local)
- `claude-api` - Claude Code API agent
- `goose-local` - Goose CLI agent (supports multiple LLM backends)
- `ollama` - Builtin ReAct agent with Ollama
- `openai` - Builtin ReAct agent with OpenAI
- `openai-compatible` - Builtin ReAct agent with compatible API

**LLM Providers** (the actual models):
- Ollama (local models: llama3.1, qwen3, etc.)
- Claude API (Anthropic's API)
- OpenAI (GPT-4, etc.)
- Groq, OpenRouter, vLLM, etc.

Example: `goose-local` agent configured with OpenAI LLM = Goose CLI using OpenAI models

### Required Secrets

Go to your repository settings and add these secrets:

| Secret | Required | Description |
|--------|----------|-------------|
| `SAPIENS_GITEA_TOKEN` | Gitea only | Your Gitea API token (note: GITEA_ prefix is reserved) |
| `SAPIENS_GITHUB_TOKEN` | GitHub only | GitHub PAT for full functionality (note: GITHUB_ prefix is reserved for custom secrets) |
| `SAPIENS_CLAUDE_API_KEY` | If using API agents | API key for claude-api, openai, anthropic, etc. |
| `OPENAI_API_KEY` | If using OpenAI models | OpenAI API key (for Goose or builtin agent) |
| `CLAUDE_API_KEY` | If using Claude API | Anthropic API key (for claude-api agent) |
| `ANTHROPIC_API_KEY` | If using Claude API | Alternative name for Claude API key |

**Note on GitHub tokens:** GitHub provides an automatic `GITHUB_TOKEN` for basic operations, but you cannot create custom secrets with the `GITHUB_` prefix. Use `SAPIENS_GITHUB_TOKEN` for a PAT with elevated permissions.

**Note:** API key secrets are only needed if your `.sapiens/config.yaml` uses an API-based agent provider. If using local agents like `claude-local`, `ollama`, or `goose-local`, these secrets are optional.

### Multi-Environment Setup

Create two configs for different environments:

```bash
# Local development (builtin agent + Ollama - free, runs locally)
sapiens init --config-path .sapiens/config.yaml
# Agent: builtin
# LLM Provider: Ollama
# Model: llama3.1:8b

# CI/CD (builtin agent + OpenAI - better quality, costs money)
sapiens init --config-path .sapiens/config.ci.yaml
# Agent: builtin
# LLM Provider: OpenAI
# Model: gpt-4o
```

Then update the workflows to use the CI config by editing the `CONFIG_FILE` environment variable:

```yaml
env:
  CONFIG_FILE: .sapiens/config.ci.yaml
```

**Note**: The builtin ReAct agent is recommended for CI/CD as it's lightweight and works directly with any LLM API.

## How It Works

These workflows are triggered by **issue labels**. When you add a specific label to an issue or PR, the corresponding workflow automatically processes it using the AI agent configured in `.sapiens/config.yaml`.

### Adding Labels

**On Issues:**
1. Navigate to your issue
2. Click the "Labels" section on the right sidebar
3. Select the appropriate label (e.g., `needs-planning`, `execute`)

**On Pull Requests:**
1. Navigate to your pull request
2. Click the "Labels" section on the right sidebar
3. Select labels like `needs-review` or `requires-qa` to trigger automated review/testing

Labels can be added at any time and workflows will trigger automatically.

## Label Reference

### `sapiens/triage`
**When to use:** New issues that need initial analysis and categorization.

**What it does:**
- Analyzes the issue description
- Categorizes the issue (bug, feature, question, etc.)
- Adds appropriate labels
- Assigns priority if applicable
- Comments with analysis results

**Use on:** Issues (not PRs)

---

### `needs-planning`
**When to use:** You have a new feature request or complex task that needs a development plan.

**What it does:**
- Analyzes the issue description and requirements
- Researches the codebase to understand existing patterns
- Generates a detailed implementation plan with steps
- Posts the plan as a comment on the issue

**Use on:** Issues (not PRs)

**Next step:** Review the plan and add `approved` label if it looks good.

---

### `approved`
**When to use:** A plan has been generated and reviewed, ready for implementation.

**What it does:**
- Converts the approved plan into executable task issues
- Creates sub-issues for each step in the plan
- Links tasks back to the parent issue
- Each task can be executed independently

**Use on:** Issues with completed plans

**Next step:** Add `execute` label to individual task issues.

---

### `execute`
**When to use:** A task issue is ready to be implemented.

**What it does:**
- Reads the task description and acceptance criteria
- Implements the required code changes
- Creates a new branch for the changes
- Opens a pull request with the implementation
- Links the PR back to the task issue

**Use on:** Task issues created by the `approved` workflow

**Next step:** Add `needs-review` to the created PR.

---

### `needs-review`
**When to use:** A pull request is ready for automated code review.

**What it does:**
- Analyzes the PR diff and all changed files
- Uses your configured AI agent to review for:
  - Code quality and best practices
  - Potential bugs or issues
  - Performance concerns
  - Security vulnerabilities
  - Maintainability and readability
- Posts inline comments with specific feedback
- Updates label based on review results

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:** Address feedback, then add `requires-qa` for testing.

---

### `requires-qa`
**When to use:** A pull request has passed review and needs QA validation.

**What it does:**
- Checks out the PR branch
- Runs build commands (npm build, make, python build, etc.)
- Runs test commands (pytest, npm test, go test, etc.)
- If no tests exist: Creates tests using AI, commits them
- Posts QA results as a comment
- Updates label to `qa-passed` or `qa-failed`

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:** If passing, merge the PR. If failing, add `needs-fix`.

---

### `needs-fix`
**When to use:** Issues were found during review or QA that need to be addressed.

**What it does:**
- Reads ALL comments from reviewers/maintainers
- AI analyzes each comment and categorizes it:
  - **Simple fix**: Implements immediately (typos, formatting, simple refactors)
  - **Controversial fix**: Posts plan and waits for approval
  - **Question**: Answers the question
  - **Info**: Acknowledges the feedback
  - **Already done**: Confirms it's in the code
  - **Won't fix**: Explains why not
- Replies to EACH comment with planned action
- Batch executes simple fixes and commits to the PR branch
- Removes `needs-fix` label when done
- Adds `needs-approval` if controversial fixes need approval

**How to approve controversial fixes:**
When the agent identifies a controversial fix (significant change), it will:
1. Reply to the review comment with the proposed action and reasoning
2. Add `needs-approval` label to the PR
3. Wait for your approval before implementing

To approve a controversial fix:
- React with 👍 (thumbs up) to the agent's reply comment, OR
- Reply to the comment with "approved"

Once approved, the agent will implement the fix on the next run.

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:**
- If fixes implemented: Re-add `needs-review` or `requires-qa` to re-validate
- If waiting for approval: Approve controversial fixes, then re-run by removing and re-adding `needs-fix` label

---

## Workflow Triggers Summary

| Workflow | Label | Use On | Description |
|----------|-------|--------|-------------|
| `process-label.yaml` | `sapiens/triage` | Issues | Triage and categorize issues |
| `process-label.yaml` | `needs-planning` | Issues | Generate implementation plan |
| `process-label.yaml` | `approved` | Issues | Create executable tasks |
| `process-label.yaml` | `execute` | Issues | Implement code changes |
| `process-label.yaml` | `needs-review` | Pull Requests | Automated code review |
| `requires-qa.yaml` | `requires-qa` | Pull Requests | Run tests and QA |
| `process-label.yaml` | `needs-fix` | Pull Requests | Address review feedback |

### Automation Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `automation-daemon.yaml` | Schedule (every 5 min) | Periodic processor for pending issues |
| `process-issue.yaml` | Manual dispatch | Process a single issue on-demand |

## Quick Start

### 1. Create an Issue

Create a new issue describing what you want to build:

```
Title: Add user authentication feature

Description:
We need to add user authentication to the application.
Users should be able to sign up, log in, and log out.
Use JWT tokens for session management.
```

### 2. Add a Label

Add the `needs-planning` label to trigger the planning workflow.

### 3. Review the Plan

The workflow will:
- Analyze your requirements
- Research the codebase
- Generate a detailed implementation plan
- Post the plan as a comment on the issue

### 4. Approve the Plan

Review the generated plan. If it looks good:
- Add the `approved` label to create executable tasks

### 5. Execute Tasks

For each task created:
- Add the `execute` label to trigger implementation
- The workflow will write the code and create a PR

### 6. Review & QA

- Add `needs-review` for automated code review
- Add `requires-qa` for testing and validation
- Add `needs-fix` if issues are found (AI will respond to all comments)

## Label Workflow

```
Issue Creation
    ↓
Add: needs-planning
    ↓
Plan Generated
    ↓
Add: approved
    ↓
Tasks Created
    ↓
Add: execute (on each task)
    ↓
PR Created
    ↓
Add: needs-review (on PR)
    ↓
Review Complete
    ↓
Add: requires-qa (on PR)
    ↓
QA Complete
    ↓
Add: needs-fix (if issues found)
    ↓
Merge!
```

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
# custom-workflow.yaml
on:
  issues:
    types: [labeled]

jobs:
  process:
    if: gitea.event.label.name == 'my-custom-label'
    # ... rest of workflow
```

## Recipe Workflows

The `recipes/` subdirectory contains additional example workflows for:
- Daily issue triage
- Weekly test coverage reports
- Security scans and SBOM generation
- Dependency audits
- Post-merge documentation updates
- And more...

These are optional and can be customized for your project.

## Troubleshooting

### Workflow doesn't trigger

- Check that Actions are enabled in repository settings
- Verify the label name matches exactly (case-sensitive)
- Check runner availability
- Check workflow logs in Actions tab

### Permission denied

- Verify `SAPIENS_GITEA_TOKEN` or `GITHUB_TOKEN` has correct permissions
- Token needs: `repo`, `read:org`, `write:issue`
- For GitHub, you may need a PAT instead of `GITHUB_TOKEN`

### AI Agent Errors

- Check that your `.sapiens/config.yaml` is valid and accessible
- If using API-based agents, verify the appropriate API key secret is set
- Check API quota/limits for your AI provider
- For local agents (Ollama, Claude Code), ensure they're running and accessible
- Check workflow logs in Actions tab for specific error messages
- Verify your agent provider configuration matches your installed tools

### Config file not found

- Ensure you committed your `.sapiens/config.yaml` to the repo
- Check the `CONFIG_FILE` path is correct in the workflow

## Learn More

- **Documentation**: https://github.com/savorywatt/repo-sapiens#readme
- **Getting Started**: See `docs/GETTING_STARTED.md`
- **Full Guide**: See `docs/DEPLOYMENT_GUIDE.md`

---

*These workflows were generated by repo-sapiens. To update them, run `sapiens update`.*
