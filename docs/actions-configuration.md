# Gitea Actions Configuration Guide

This document explains the Gitea Actions workflows and how to configure them for your repository.

## Workflow Files Overview

The system includes workflow files in `.gitea/workflows/`:

### Label-Triggered Workflows

| Workflow | Label Trigger | Purpose |
|----------|---------------|---------|
| `needs-planning.yaml` | `needs-planning` | Generate development plan |
| `approved.yaml` | `approved` | Execute approved plan |
| `execute-task.yaml` | `execute-task` | Run task execution |
| `needs-review.yaml` | `needs-review` | Code review workflow |
| `needs-fix.yaml` | `needs-fix` | Handle fix requests |
| `requires-qa.yaml` | `requires-qa` | QA workflow |
| `build-artifacts.yaml` | `build-artifacts` | Build artifacts |

### test.yaml

**Purpose:** Run tests on pull requests and pushes

**Triggers:**
- Pull requests to main
- Pushes to main

**Process:**
1. Runs linters (black, ruff)
2. Runs type checker (mypy)
3. Runs test suite with coverage
4. Uploads coverage report

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11

**Customization:**
```yaml
# Add more test steps
- name: Security scan
  run: bandit -r repo_sapiens/

- name: Dependency check
  run: safety check
```

## Environment Variables

All workflows use these environment variables:

### Secrets (Required)
```yaml
env:
  SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  SAPIENS_CLAUDE_API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
```

### Gitea Actions Context Variables
```yaml
# Automatically available in Gitea Actions:
# - gitea.event.issue.number
# - gitea.event.repository.owner.login
# - gitea.event.repository.name
# - gitea.server_url
```

## Workflow Dependencies

### Python Dependencies

All workflows install the package:
```yaml
- name: Install dependencies
  run: pip install -e .
```

For development workflows (test.yaml):
```yaml
- name: Install dependencies
  run: pip install -e ".[dev]"
```

### Caching

Workflows use pip caching for faster runs:
```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'  # Cache pip dependencies
```

## Workflow Outputs

### Artifacts

**test.yaml:**
- `coverage-report`: HTML coverage report from `htmlcov/`

### Accessing Artifacts

Via Gitea UI:
1. Go to Actions tab
2. Click on completed workflow run
3. Download artifacts from artifacts section

Via API:
```bash
curl -H "Authorization: token $SAPIENS_GITEA_TOKEN" \
  "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
```

## Custom Workflows

### Creating Custom Workflow

Create `.gitea/workflows/custom.yaml`:

```yaml
name: Custom Workflow

on:
  workflow_dispatch:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  custom-job:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -e .

      - name: Run custom command
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
        run: |
          sapiens custom-command --option value
```

### Adding Custom CLI Command

In `repo_sapiens/main.py`:

```python
@cli.command()
@click.option("--option", required=True)
@click.pass_context
def custom_command(ctx, option):
    """Custom command description."""
    asyncio.run(_custom_command(ctx.obj["settings"], option))

async def _custom_command(settings: AutomationSettings, option: str):
    """Implementation."""
    log.info("custom_command", option=option)
    # Your logic here
```

## Performance Optimization

### Reduce Workflow Runs

**Limit triggers:**
```yaml
on:
  issues:
    types: [labeled]  # Only on label changes
```

**Add path filters:**
```yaml
on:
  push:
    paths:
      - 'repo_sapiens/**'
      - 'tests/**'
```

### Concurrent Jobs

Run independent jobs in parallel:
```yaml
jobs:
  job1:
    runs-on: ubuntu-latest
    steps: [...]

  job2:
    runs-on: ubuntu-latest
    steps: [...]

  job3:
    needs: [job1, job2]  # Wait for job1 and job2
    runs-on: ubuntu-latest
    steps: [...]
```

### Caching Dependencies

Cache more than just pip:
```yaml
- name: Cache all dependencies
  uses: actions/cache@v3
  with:
    path: |
      ~/.cache/pip
      .mypy_cache
      .pytest_cache
    key: ${{ runner.os }}-deps-${{ hashFiles('**/pyproject.toml') }}
```

## Security Best Practices

### Secrets Management

1. **Never log secrets:**
```yaml
- name: Use secret
  run: |
    # DON'T: echo ${{ secrets.SAPIENS_GITEA_TOKEN }}
    # DO: Use secret without logging
    sapiens health-check
  env:
    SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
```

2. **Limit secret scope:**
- Only add secrets that are needed
- Use separate tokens for different purposes
- Rotate secrets regularly

### Workflow Security

1. **Pin action versions:**
```yaml
# DON'T: uses: actions/checkout@v4
# DO: uses: actions/checkout@v4.1.0
```

2. **Restrict triggers:**
```yaml
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize]
```

3. **Use timeout:**
```yaml
jobs:
  job:
    timeout-minutes: 30
    runs-on: ubuntu-latest
```

## Debugging Workflows

### View Logs

1. Go to Actions tab
2. Click on workflow run
3. Click on job name
4. View step logs

### Add Debug Logging

```yaml
- name: Debug info
  run: |
    echo "Gitea ref: ${{ gitea.ref }}"
    echo "Event name: ${{ gitea.event_name }}"
    echo "Working directory:"
    pwd
    ls -la
```

### Manual Trigger

Add to any workflow:
```yaml
on:
  workflow_dispatch:
    inputs:
      debug:
        description: 'Enable debug mode'
        required: false
        default: 'false'
```

Then:
```yaml
- name: Run with debug
  if: ${{ gitea.event.inputs.debug == 'true' }}
  run: sapiens --log-level DEBUG health-check
```

## Monitoring

### Workflow Notifications

Configure in Gitea:
1. Repository Settings → Webhooks
2. Add webhook for workflow status
3. Notify on workflow failures

### Metrics Collection

Add metrics step:
```yaml
- name: Collect metrics
  run: |
    sapiens health-check | tee health.txt
    # Send to monitoring system
```

## Troubleshooting

### Workflow Not Triggering

1. Check workflow file syntax
2. Verify trigger conditions
3. Check runner availability
4. Review event payload in logs

### Workflow Fails

1. View step logs
2. Check secrets are configured
3. Verify permissions
4. Test locally with same commands

### Slow Workflows

1. Enable caching
2. Reduce frequency
3. Parallelize jobs
4. Optimize dependencies

## Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [GitHub Actions Syntax Reference](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Cron Syntax](https://crontab.guru/)
