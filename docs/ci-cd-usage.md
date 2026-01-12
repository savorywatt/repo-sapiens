# CI/CD Usage Guide

This guide explains how to use the Gitea automation system in CI/CD environments.

## Overview

The automation system provides several workflows that run automatically in response to repository events:

1. **Needs Planning** - Processes issues labeled for planning
2. **Approved** - Handles approved plans
3. **Execute Task** - Runs task execution
4. **Needs Review** - Code review workflow
5. **Needs Fix** - Handles issues requiring fixes
6. **Requires QA** - QA workflow
7. **Build Artifacts** - Artifact building
8. **Tests** - Runs tests on PRs and pushes

## Workflow Files

All workflows are located in `.gitea/workflows/`:

```
.gitea/workflows/
├── needs-planning.yaml    # Issue planning handler
├── approved.yaml          # Approved plan handler
├── execute-task.yaml      # Task execution
├── needs-review.yaml      # Code review workflow
├── needs-fix.yaml         # Fix workflow
├── requires-qa.yaml       # QA workflow
├── build-artifacts.yaml   # Build artifacts
└── test.yaml              # Test runner
```

## Needs Planning Workflow

**File:** `.gitea/workflows/sapiens/needs-planning.yaml`

**Triggers:**
- Issue labeled with `needs-planning`

**How It Works:**

1. Workflow triggers on label event
2. Calls `sapiens` CLI to generate plan
3. Reports success/failure

**Label to Workflow Mapping:**

| Label | Workflow | Action |
|-------|----------|--------|
| `needs-planning` | needs-planning.yaml | Generate development plan |
| `approved` | approved.yaml | Execute approved plan |
| `needs-review` | needs-review.yaml | Review code changes |
| `needs-fix` | needs-fix.yaml | Handle fix requests |
| `requires-qa` | requires-qa.yaml | Run QA checks |

**Example Usage:**

1. Create issue with title "Add user authentication"
2. Add label `needs-planning`
3. Workflow automatically triggers
4. Automation generates plan

## Test Workflow

**File:** `.gitea/workflows/sapiens/test.yaml`

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

### health-check

Generate health check report.

```bash
sapiens health-check
```

**Output:**
```
# Automation System Health Report
Generated: 2025-12-20T10:30:00

## Provider Health
- Git Provider: Configuration loaded
- Agent Provider: Configuration loaded
- State Manager: Operational
```

### list-plans

List all workflow plans.

```bash
sapiens list-plans
```

**Output:**
```
Active Plans:
  - Plan 42: in_progress
    Updated: 2025-12-20T10:30:00
  - Plan 43: pending
    Updated: 2025-12-20T09:15:00
```

## Environment Variables

Workflows use these environment variables:

### Required Secrets
- `SAPIENS_GITEA_TOKEN`: Gitea API token
- `SAPIENS_CLAUDE_API_KEY`: Claude API key

### Gitea Actions Context Variables
For Gitea workflows, use the `gitea.event.*` context:
- `gitea.event.issue.number`: Issue number
- `gitea.event.repository.owner.login`: Repository owner
- `gitea.event.repository.name`: Repository name
- `gitea.server_url`: Gitea server URL

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
sapiens process-issue --issue 42 --stage planning
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
