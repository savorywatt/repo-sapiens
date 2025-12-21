# CI/CD Usage Guide

This guide explains how to use the Gitea automation system in CI/CD environments.

## Overview

The automation system provides several workflows that run automatically in response to repository events:

1. **Automation Trigger** - Processes issues based on labels
2. **Plan Merged** - Generates prompts when plans are merged
3. **Automation Daemon** - Periodically processes pending issues
4. **Monitor** - Health checks and failure detection
5. **Tests** - Runs tests on PRs and pushes

## Workflow Files

All workflows are located in `.gitea/workflows/`:

```
.gitea/workflows/
├── automation-trigger.yaml   # Issue event handler
├── plan-merged.yaml          # Plan merge handler
├── automation-daemon.yaml    # Scheduled processor
├── monitor.yaml              # Health monitoring
└── test.yaml                 # Test runner
```

## Automation Trigger Workflow

**File:** `.gitea/workflows/automation-trigger.yaml`

**Triggers:**
- Issue opened
- Issue labeled/unlabeled
- Issue edited
- Issue closed
- Comment created

**How It Works:**

1. Workflow triggers on issue event
2. Examines issue labels to determine stage
3. Calls appropriate `automation` CLI command
4. Reports success/failure

**Label to Stage Mapping:**

| Label | Stage | Action |
|-------|-------|--------|
| `needs-planning` | planning | Generate development plan |
| `plan-review` | plan-review | Review and approve plan |
| `prompts` | prompts | Generate prompt issues |
| `implement` | implementation | Execute task |
| `code-review` | code-review | Review code changes |
| `merge-ready` | merge | Create pull request |

**Example Usage:**

1. Create issue with title "Add user authentication"
2. Add label `needs-planning`
3. Workflow automatically triggers
4. Automation generates plan
5. Plan review issue created

## Plan Merged Workflow

**File:** `.gitea/workflows/plan-merged.yaml`

**Triggers:**
- Push to `main` branch
- Modified files in `plans/` directory

**How It Works:**

1. Detects which plan files changed
2. Extracts plan ID from filename
3. Generates prompt issues for each task
4. Updates workflow state

**Expected Plan Format:**

```
plans/42-feature-name.md
```

Where `42` is the plan ID (usually matches issue number).

**Example Usage:**

1. Create plan file: `plans/42-add-auth.md`
2. Commit and push to feature branch
3. Create PR and merge to main
4. Workflow triggers and generates prompt issues

## Automation Daemon Workflow

**File:** `.gitea/workflows/automation-daemon.yaml`

**Triggers:**
- Scheduled: Every 5 minutes (cron)
- Manual: workflow_dispatch

**How It Works:**

1. Processes all pending issues
2. Checks for stale workflows (>24 hours)
3. Uploads state files as artifacts

**Manual Trigger:**

Via Gitea UI:
1. Go to Actions tab
2. Select "Automation Daemon"
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

1. Generates health report
2. Checks for failures in last 24 hours
3. Uploads reports as artifacts

**Viewing Reports:**

1. Go to Actions tab
2. Find completed "Automation Monitor" run
3. Download "health-report" artifact
4. View `health-report.md`

## Test Workflow

**File:** `.gitea/workflows/test.yaml`

**Triggers:**
- Pull request to `main`
- Push to `main`

**How It Works:**

1. Runs code linters (black, ruff)
2. Runs type checker (mypy)
3. Runs test suite with coverage
4. Uploads coverage report

## CLI Commands for CI/CD

The automation system provides several commands designed for CI/CD:

### process-issue

Process specific issue at given stage.

```bash
automation process-issue --issue 42 --stage planning
```

**Options:**
- `--issue`: Issue number (required)
- `--stage`: Stage to execute (required)
  - Choices: planning, plan-review, prompts, implementation, code-review, merge

**Usage in Workflows:**
```yaml
- name: Process issue
  run: |
    automation process-issue \
      --issue ${{ github.event.issue.number }} \
      --stage planning
```

### generate-prompts

Generate prompt issues from plan file.

```bash
automation generate-prompts --plan-file plans/42-feature.md --plan-id 42
```

**Options:**
- `--plan-file`: Path to plan markdown file (required)
- `--plan-id`: Plan identifier (required)

**Usage in Workflows:**
```yaml
- name: Generate prompts
  run: |
    automation generate-prompts \
      --plan-file "$plan_file" \
      --plan-id "$plan_id"
```

### process-all

Process all pending issues.

```bash
automation process-all
```

**Usage in Workflows:**
```yaml
- name: Process all pending
  run: automation process-all --log-level INFO
```

### list-active-plans

List all active workflow plans.

```bash
automation list-active-plans
```

**Output:**
```
Active Plans:
  - Plan 42: in_progress
    Updated: 2025-12-20T10:30:00
  - Plan 43: pending
    Updated: 2025-12-20T09:15:00
```

### check-stale

Check for stale workflows.

```bash
automation check-stale --max-age-hours 24
```

**Options:**
- `--max-age-hours`: Maximum age before considering stale (default: 24)

### health-check

Generate health check report.

```bash
automation health-check
```

**Output:**
```
# Automation System Health Report
Generated: 2025-12-20T10:30:00

## Active Plans: 2

## Failed Plans: 0

## Provider Health
- Git Provider: Configuration loaded ✓
- Agent Provider: Configuration loaded ✓
- State Manager: Operational ✓
```

### check-failures

Check for workflow failures.

```bash
automation check-failures --since-hours 24
```

**Options:**
- `--since-hours`: Check failures since N hours (default: 24)

## Environment Variables

Workflows use these environment variables:

### Required
- `GITEA_TOKEN`: Gitea API token
- `CLAUDE_API_KEY`: Claude API key

### Automatic (GitHub/Gitea Actions)
- `GITHUB_REPOSITORY_OWNER`: Repository owner
- `GITHUB_REPOSITORY`: Repository name
- `GITHUB_REF_NAME`: Branch name
- `GITHUB_SERVER_URL`: Gitea server URL

### Configuration Overrides
- `AUTOMATION__GIT_PROVIDER__API_TOKEN`: Override git token
- `AUTOMATION__AGENT_PROVIDER__API_KEY`: Override agent key
- `AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS`: Override concurrency

## Monitoring Workflows

### View Workflow Runs

1. Go to repository Actions tab
2. See all workflow runs with status
3. Click run to view details
4. View logs for each step

### Debug Failed Workflows

1. View workflow run logs
2. Look for error messages
3. Check state artifacts (if available)
4. Review secret configuration
5. Verify permissions

### Common Issues

**Workflow doesn't trigger:**
- Check trigger conditions in YAML
- Verify Actions are enabled in repository
- Check runner availability

**Permission denied:**
- Verify GITEA_TOKEN has correct scopes
- Check repository permissions
- Ensure runner has access

**Timeout:**
- Increase timeout in workflow file
- Reduce concurrent tasks
- Optimize operations

## Best Practices

### Workflow Management

1. **Use workflow_dispatch**: Allow manual triggering for debugging
2. **Upload artifacts**: Save state/logs for troubleshooting
3. **Set timeouts**: Prevent workflows from running indefinitely
4. **Use caching**: Cache pip dependencies for faster runs

### Performance

1. **Limit concurrency**: Set max_concurrent_tasks appropriately
2. **Optimize schedule**: Adjust cron frequency based on load
3. **Use conditionals**: Skip unnecessary steps with `if` conditions
4. **Parallel execution**: Run independent tasks in parallel

### Security

1. **Never log secrets**: Avoid echoing sensitive values
2. **Use secrets**: Store tokens in encrypted secrets
3. **Restrict access**: Limit who can trigger workflows
4. **Audit regularly**: Review workflow runs and permissions

## Troubleshooting

### Check Logs

```bash
# View recent workflow runs
curl "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/runs" \
  -H "Authorization: token ${GITEA_TOKEN}"
```

### Manual Execution

Test commands locally:

```bash
# Set up environment
export GITEA_TOKEN="your-token"
export CLAUDE_API_KEY="your-key"

# Run command
automation process-issue --issue 42 --stage planning
```

### State Inspection

Check workflow state:

```bash
# View state files
ls -la .automation/state/

# Read state
cat .automation/state/42.json
```

## Additional Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [GitHub Actions Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Automation System README](../README.md)
