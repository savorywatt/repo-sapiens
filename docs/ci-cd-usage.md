# CI/CD Usage Guide

This guide explains how to use repo-sapiens in CI/CD environments.

## Overview

The automation system provides several workflows that run automatically in response to repository events:

1. **Label-Triggered Workflows** - Process issues when specific labels are added
2. **Plan Merged** - Generates tasks when plans are merged
3. **Automation Daemon** - Periodically processes pending issues
4. **Monitor** - Health checks and failure detection
5. **Tests** - Runs tests on PRs and pushes
6. **Build Artifacts** - Builds wheel for faster workflow execution

## Workflow Files

All workflows are located in `.gitea/workflows/`:

```
.gitea/workflows/
├── needs-planning.yaml       # Triggers on 'needs-planning' label
├── approved.yaml             # Triggers on 'approved' label
├── execute-task.yaml         # Triggers on 'execute' label
├── needs-review.yaml         # Triggers on 'needs-review' label
├── needs-fix.yaml            # Triggers on 'needs-fix' label
├── requires-qa.yaml          # Triggers on 'requires-qa' label
├── plan-merged.yaml          # Triggers on push to main with plan files
├── automation-daemon.yaml    # Scheduled processor (every 5 min)
├── monitor.yaml              # Health monitoring (every 6 hours)
├── test.yaml                 # Test runner
└── build-artifacts.yaml      # Pre-build wheel for workflows
```

## Label-Triggered Workflows

Each label has its own dedicated workflow file that triggers when the label is added to an issue.

### needs-planning.yaml

**Triggers:** When `needs-planning` label is added to an issue

**What it does:**
1. Checks out the repository
2. Installs sapiens (from wheel or source)
3. Runs `sapiens process-issue --issue <number>`
4. Comments on the issue with success/failure status

**Usage:**
1. Create an issue describing what you want to build
2. Add the `needs-planning` label
3. Workflow generates a development plan
4. Review the plan and add `approved` label to proceed

### approved.yaml

**Triggers:** When `approved` label is added to an issue with `proposed` label

**What it does:**
1. Processes the approved plan
2. Creates task issues from the plan
3. Comments on the issue with task creation status

### execute-task.yaml

**Triggers:** When `execute` label is added to an issue with `task` label

**What it does:**
1. Executes the task implementation
2. Creates commits and potentially pull requests
3. Uploads state artifacts for debugging

### Other Label Workflows

| Workflow | Label | Description |
|----------|-------|-------------|
| `needs-review.yaml` | `needs-review` | Triggers code review |
| `needs-fix.yaml` | `needs-fix` | Triggers fix for review feedback |
| `requires-qa.yaml` | `requires-qa` | Triggers QA verification |

## Plan Merged Workflow

**File:** `.gitea/workflows/plan-merged.yaml`

**Triggers:**
- Push to `main` branch
- Modified files in `plans/` directory

**How It Works:**

1. Detects which plan files changed
2. Extracts plan ID from filename
3. Generates task issues for each task in the plan

**Expected Plan Format:**

```
plans/42-feature-name.md
```

Where `42` is the plan ID (usually matches issue number).

## Automation Daemon Workflow

**File:** `.gitea/workflows/automation-daemon.yaml`

**Triggers:**
- Scheduled: Every 5 minutes (cron)
- Manual: workflow_dispatch

**How It Works:**

1. Checks for recent activity (commits or issue updates in last 10 minutes)
2. If activity detected, processes all pending issues
3. Checks for stale workflows (>24 hours)
4. Uploads state files as artifacts

**Manual Trigger:**

Via Gitea UI:
1. Go to Actions tab
2. Select "Sapiens Daemon"
3. Click "Run workflow"

Via CLI:
```bash
curl -X POST "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/workflows/automation-daemon.yaml/dispatches" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"ref": "main"}'
```

## Monitor Workflow

**File:** `.gitea/workflows/monitor.yaml`

**Triggers:**
- Scheduled: Every 6 hours
- Manual: workflow_dispatch

**How It Works:**

1. Generates health report with `sapiens health-check`
2. Checks for failures in last 24 hours with `sapiens check-failures`
3. Uploads reports as artifacts

**Viewing Reports:**

1. Go to Actions tab
2. Find completed "Sapiens Monitor" run
3. Download "health-report" artifact
4. View `health-report.md`

## Test Workflow

**File:** `.gitea/workflows/test.yaml`

**Triggers:**
- Pull request to `main`
- Push to `main`

**How It Works:**

1. Runs code linters (ruff)
2. Runs type checker (mypy)
3. Runs test suite with coverage
4. Uploads coverage report

## CLI Commands for CI/CD

The automation system provides several commands designed for CI/CD:

### process-issue

Process a specific issue.

```bash
sapiens process-issue --issue 42
```

**Options:**
- `--issue`: Issue number (required)

**Usage in Workflows:**
```yaml
- name: Process issue
  run: |
    sapiens process-issue --issue ${{ gitea.event.issue.number }}
```

### process-all

Process all issues with optional tag filter.

```bash
sapiens process-all
sapiens process-all --tag needs-planning
```

**Options:**
- `--tag`: Optional tag filter

**Usage in Workflows:**
```yaml
- name: Process all pending
  run: sapiens process-all --log-level INFO
```

### process-plan

Process an entire plan end-to-end.

```bash
sapiens process-plan --plan-id 42
```

**Options:**
- `--plan-id`: Plan identifier (required)

### list-plans

List all active workflow plans.

```bash
sapiens list-plans
```

**Output:**
```
Active Plans (2):

  • Plan 42: in_progress
  • Plan 43: pending
```

### show-plan

Show detailed status for a specific plan.

```bash
sapiens show-plan --plan-id 42
```

**Output:**
```
📋 Plan 42 Status

Overall Status: in_progress
Created: 2025-12-20T10:30:00+00:00
Updated: 2025-12-20T14:15:00+00:00

Stages:
  ✅ planning: completed
  ✅ plan_review: completed
  ⏳ prompts: pending
  ⏳ implementation: pending
  ⏳ code_review: pending
  ⏳ merge: pending

Tasks (3):
  ✅ task-1: completed
  🔄 task-2: in_progress
  ⏳ task-3: pending
```

### check-stale

Check for stale workflows that haven't been updated recently.

```bash
sapiens check-stale --max-age-hours 24
```

**Options:**
- `--max-age-hours`: Maximum age before considering stale (default: 24)

**Exit Codes:**
- 0: No stale workflows found
- 1: Stale workflows detected

**Usage in Workflows:**
```yaml
- name: Check for stale workflows
  run: sapiens check-stale --max-age-hours 24
```

### health-check

Generate health check report.

```bash
sapiens health-check
```

**Output:**
```markdown
# Automation System Health Report
Generated: 2025-12-20T10:30:00+00:00

## Summary
- Total Plans: 5
- Active Plans: 2
- Completed Plans: 2
- Failed Plans: 1
- Pending Plans: 0

## Configuration
- State Directory: .automation/state
- Git Provider: gitea
- Agent Provider: claude

## Provider Status
- Git Provider: Configuration loaded ✓
- Agent Provider: Configuration loaded ✓
- State Manager: Operational ✓

## Failed Plans
- plan-99 (updated: 2025-12-19T08:00:00+00:00)

## Active Plans
- plan-42: in_progress (updated: 2025-12-20T10:00:00+00:00)
- plan-43: pending (updated: 2025-12-20T09:15:00+00:00)
```

### check-failures

Check for workflow failures in a time period.

```bash
sapiens check-failures --since-hours 24
```

**Options:**
- `--since-hours`: Check failures since N hours (default: 24)

**Exit Codes:**
- 0: No failures found
- 1: Failures detected

**Usage in Workflows:**
```yaml
- name: Check for failures
  run: sapiens check-failures --since-hours 24
```

### daemon

Run in daemon mode, polling for new issues.

```bash
sapiens daemon --interval 60
```

**Options:**
- `--interval`: Polling interval in seconds (default: 60)

## Environment Variables

Workflows use these environment variables:

### Required Secrets

Configure these as repository secrets:

| Secret | Description |
|--------|-------------|
| `BUILDER_GITEA_TOKEN` | Gitea API token with repo access |
| `BUILDER_GITEA_URL` | Gitea server URL |
| `BUILDER_CLAUDE_API_KEY` | Claude API key for agent |

### Configuration Overrides

Environment variables for sapiens configuration:

| Variable | Description |
|----------|-------------|
| `AUTOMATION__GIT_PROVIDER__BASE_URL` | Git provider URL |
| `AUTOMATION__GIT_PROVIDER__API_TOKEN` | Git provider token |
| `AUTOMATION__REPOSITORY__OWNER` | Repository owner |
| `AUTOMATION__REPOSITORY__NAME` | Repository name |
| `AUTOMATION__AGENT_PROVIDER__API_KEY` | Agent API key |
| `AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS` | Override concurrency |

### Gitea Actions Context Variables

These are automatically available in Gitea Actions:

| Variable | Description |
|----------|-------------|
| `gitea.repository_owner` | Repository owner |
| `gitea.repository` | Repository name |
| `gitea.event.issue.number` | Issue number (for issue events) |
| `gitea.event.label.name` | Label that triggered the workflow |

## Monitoring Workflows

### View Workflow Runs

1. Go to repository Actions tab
2. See all workflow runs with status
3. Click run to view details
4. View logs for each step

### Debug Failed Workflows

1. View workflow run logs
2. Look for error messages
3. Download state artifacts (if available)
4. Review secret configuration
5. Verify permissions

### Common Issues

**Workflow doesn't trigger:**
- Check that the label matches exactly (case-sensitive)
- Verify Actions are enabled in repository settings
- Check runner availability
- Ensure the workflow file syntax is valid

**Permission denied:**
- Verify token has correct scopes (repo, write:issue)
- Check repository permissions
- Ensure runner has access to secrets

**Timeout:**
- Increase timeout in workflow file
- Reduce concurrent tasks
- Check for infinite loops in processing

**"pre-commit not found":**
- Ensure virtual environment is activated
- Check that dependencies are installed correctly

## Best Practices

### Workflow Management

1. **Use workflow_dispatch**: Allow manual triggering for debugging
2. **Upload artifacts**: Save state/logs for troubleshooting
3. **Set timeouts**: Prevent workflows from running indefinitely
4. **Use pre-built wheels**: Build wheel artifact for faster workflow execution

### Performance

1. **Check for recent activity**: Skip processing if no recent changes (daemon does this)
2. **Limit concurrency**: Set max_concurrent_tasks appropriately
3. **Optimize schedule**: Adjust cron frequency based on load
4. **Use conditionals**: Skip unnecessary steps with `if` conditions

### Security

1. **Never log secrets**: Avoid echoing sensitive values
2. **Use secrets**: Store tokens in encrypted repository secrets
3. **Restrict access**: Limit who can trigger workflows
4. **Audit regularly**: Review workflow runs and permissions
5. **Pin action versions**: Use specific versions of actions (e.g., `actions/checkout@v4`)

## Troubleshooting

### Check Logs

```bash
# View recent workflow runs via API
curl "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/runs" \
  -H "Authorization: token ${GITEA_TOKEN}"
```

### Manual Execution

Test commands locally:

```bash
# Set up environment
export AUTOMATION__GIT_PROVIDER__BASE_URL="https://gitea.example.com"
export AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token"
export AUTOMATION__REPOSITORY__OWNER="your-org"
export AUTOMATION__REPOSITORY__NAME="your-repo"
export AUTOMATION__AGENT_PROVIDER__API_KEY="your-claude-key"  # pragma: allowlist secret

# Run command
sapiens process-issue --issue 42
```

### State Inspection

Check workflow state:

```bash
# View state files
ls -la .automation/state/

# Read state
cat .automation/state/42.json | jq .
```

### Health Check

Run health check locally:

```bash
sapiens health-check
```

## Additional Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [GitHub Actions Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [repo-sapiens README](../README.md)
- [Configuration Guide](./configuration.md)
