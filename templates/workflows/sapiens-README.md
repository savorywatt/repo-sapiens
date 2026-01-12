# Sapiens Workflows

This directory contains workflows managed by [repo-sapiens](https://github.com/savorywatt/repo-sapiens) for automated issue processing and task management.

## How It Works

These workflows are triggered by **issue labels**. When you add a specific label to an issue or PR, the corresponding workflow automatically processes it using the AI agent configured in `.sapiens/config.yaml`.

### Adding Labels

**On Issues:**
1. Navigate to your issue
2. Click the "Labels" section on the right sidebar
3. Select the appropriate label (e.g., `needs-planning`, `execute-task`)

**On Pull Requests:**
1. Navigate to your pull request
2. Click the "Labels" section on the right sidebar
3. Select labels like `needs-review` or `requires-qa` to trigger automated review/testing

Labels can be added at any time and workflows will trigger automatically.

## Label Reference

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

**Next step:** Add `execute-task` label to individual task issues.

---

### `execute-task`
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
- Updates label to `approved` (if clean) or `reviewed` (if issues found)

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:** Address feedback, then add `requires-qa` for testing.

---

### `requires-qa`
**When to use:** A pull request has passed review and needs QA validation.

**What it does:**
- Runs automated tests and validation
- Checks code coverage
- Performs integration testing
- Posts QA results as a comment
- Updates label based on results

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:** If passing, merge the PR. If failing, add `needs-fix`.

---

### `needs-fix`
**When to use:** Issues were found during review or QA that need to be addressed.

**What it does:**
- Analyzes the review feedback or QA failures
- Implements fixes for the identified issues
- Updates the existing PR with fixes
- Re-triggers validation

**Use on:** Pull requests **only** (does nothing on regular issues)

**Next step:** Re-add `needs-review` or `requires-qa` to re-validate.

---

## Workflow Triggers Summary

| Workflow | Label | Use On | Agent Used |
|----------|-------|--------|------------|
| `needs-planning.yaml` | `needs-planning` | Issues | Your configured agent |
| `approved.yaml` | `approved` | Issues | Your configured agent |
| `execute-task.yaml` | `execute-task` | Issues | Your configured agent |
| `needs-review.yaml` | `needs-review` | Pull Requests | Your configured agent |
| `requires-qa.yaml` | `requires-qa` | Pull Requests | Your configured agent |
| `needs-fix.yaml` | `needs-fix` | Pull Requests | Your configured agent |

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
- Add the `execute-task` label to trigger implementation
- The workflow will write the code and create a PR

### 6. Review & QA

- Add `needs-review` for automated code review
- Add `requires-qa` for testing and validation
- Add `needs-fix` if issues are found

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
Add: execute-task (on each task)
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

## Configuration

### Required Secrets

Configure these secrets in your repository settings:

| Secret | Description |
|--------|-------------|
| `SAPIENS_GITEA_TOKEN` | Gitea API token with repo/issue access (required for Gitea) |
| `SAPIENS_GITHUB_TOKEN` | GitHub token (required for GitHub) |
| `SAPIENS_GITLAB_TOKEN` | GitLab personal access token with `api` scope (required for GitLab) |
| `SAPIENS_CLAUDE_API_KEY` | AI provider API key (only required if using API-based agents) |

**Note:** `SAPIENS_CLAUDE_API_KEY` is only needed if your `.sapiens/config.yaml` uses an API-based agent provider like `claude-api`, `goose-api`, `openai`, `anthropic`, etc. If using local agents like `claude-local`, `ollama`, or `goose-local`, this secret is optional.

### Config File

Each workflow uses the config file at `.sapiens/config.yaml` in your repository.

**Important:** The AI agent used by all workflows is determined by your config file's `agent_provider` section. This can be:
- `claude-local` or `claude-api` - Claude Code or Claude API
- `goose-local` or `goose-api` - Goose agent with various LLM backends
- `ollama` - Local Ollama models (e.g., qwen3, codellama)
- `openai`, `anthropic`, `groq`, `openrouter` - Cloud AI providers
- `openai-compatible` - vLLM or compatible servers

The secret `SAPIENS_CLAUDE_API_KEY` in the workflows is only used if your config specifies an API-based agent that requires it.

You can also customize:
- Model selection
- Workflow behavior
- Automation settings

Run `sapiens init` to create or update your config.

## Customization

### Modify Schedules

Edit `automation-daemon.yaml` to change processing frequency:

```yaml
on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
```

### Add Custom Labels

Create new workflow files following the pattern for your platform:

**Gitea/GitHub:**
```yaml
name: My Custom Workflow
on:
  issues:
    types: [labeled]
jobs:
  process:
    if: gitea.event.label.name == 'my-custom-label'  # or github.event.label.name
    # ... your steps
```

**GitLab:**
```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "issue_label"

my-custom-job:
  script:
    - # ... your steps
  rules:
    - if: $CI_ISSUE_LABEL == "my-custom-label"
```

## Troubleshooting

### Workflow Not Triggering

- Verify the label name matches exactly (case-sensitive)
- Check that Gitea Actions is enabled
- Ensure a runner is active and online
- Check workflow logs in Actions tab

### Permission Errors

- Verify your platform token has correct permissions:
  - **Gitea**: `SAPIENS_GITEA_TOKEN` needs `repo`, `read:org`, `write:issue`
  - **GitHub**: `SAPIENS_GITHUB_TOKEN` or `GITHUB_TOKEN` needs `repo`, `read:org`, `write:issue`
  - **GitLab**: `SAPIENS_GITLAB_TOKEN` needs `api` scope for full functionality

### AI Agent Errors

- Check that your `.sapiens/config.yaml` is valid and accessible
- If using API-based agents, verify `SAPIENS_CLAUDE_API_KEY` is set correctly
- Check API quota/limits for your AI provider
- For local agents (Ollama, Claude Code), ensure they're running and accessible
- Check workflow logs in Actions tab for specific error messages
- Verify your agent provider configuration matches your installed tools

## Recipe Workflows

The `recipes/` subdirectory contains additional example workflows for:
- Daily issue triage
- Weekly test coverage reports
- Security scans
- Dependency audits
- And more...

These are optional and can be customized for your project.

## Learn More

- **Documentation**: https://github.com/savorywatt/repo-sapiens#readme
- **Getting Started**: See `docs/GETTING_STARTED.md`
- **Full Guide**: See `docs/DEPLOYMENT_GUIDE.md`

---

*These workflows were generated by repo-sapiens. To update them, run `sapiens update`.*
