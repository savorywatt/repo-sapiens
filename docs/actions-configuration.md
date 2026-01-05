# Gitea Actions Configuration Guide

This document explains the Gitea Actions workflows and how to configure them for your repository.

## Workflow Architecture Overview

The system uses a **label-driven architecture** where workflows are triggered by adding specific labels to issues. This provides fine-grained control over the automation pipeline.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Issue Created                                                           │
│       │                                                                  │
│       ▼                                                                  │
│  [needs-planning] ──► needs-planning.yaml ──► Plan Proposal              │
│       │                                                                  │
│       ▼                                                                  │
│  [approved] ──► approved.yaml ──► Task Creation                          │
│       │                                                                  │
│       ▼                                                                  │
│  [execute] ──► execute-task.yaml ──► Implementation                      │
│       │                                                                  │
│       ▼                                                                  │
│  [needs-review] ──► needs-review.yaml ──► Code Review                    │
│       │                                                                  │
│       ├──► [requires-qa] ──► requires-qa.yaml ──► QA Testing             │
│       │                                                                  │
│       └──► [needs-fix] ──► needs-fix.yaml ──► Fix Proposal               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Workflow Files

The system includes **11 workflow files** in `.gitea/workflows/`:

### Label-Triggered Workflows (6)

#### 1. needs-planning.yaml

**Purpose:** Creates a development plan when an issue needs planning

**Trigger:** `needs-planning` label added to issue

**Process:**
1. Checks out repository
2. Installs sapiens (prefers pre-built wheel if available)
3. Calls `sapiens process-issue` to generate plan proposal
4. Comments success/failure status on issue

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Timeout: 30 minutes

**Next step:** Add `approved` label to proceed with task creation

---

#### 2. approved.yaml

**Purpose:** Creates executable tasks from an approved plan

**Trigger:** `approved` label added to issue that also has `proposed` label

**Process:**
1. Checks out repository
2. Calls `sapiens process-issue` to break plan into tasks
3. Comments completion status

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Timeout: 20 minutes

**Next step:** Tasks are created and can be executed with `execute` label

---

#### 3. execute-task.yaml

**Purpose:** Executes a task implementation

**Trigger:** `execute` label added to issue that also has `task` label

**Process:**
1. Checks out repository with full history
2. Configures git for commits (Builder Bot)
3. Calls `sapiens process-issue` to implement the task
4. Uploads state artifacts

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Timeout: 45 minutes
- Artifacts: `task-state-{issue}` (7 days retention)

**Next step:** Add `needs-review` label for code review

---

#### 4. needs-review.yaml

**Purpose:** Performs automated code review

**Trigger:** `needs-review` label added to issue

**Process:**
1. Checks out repository with full history
2. Calls `sapiens process-issue` to review code changes
3. Uploads review artifacts

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Timeout: 30 minutes
- Artifacts: `review-artifacts-{issue}` (30 days retention)

**Next step:** Either `requires-qa` for testing or `needs-fix` for corrections

---

#### 5. requires-qa.yaml

**Purpose:** Runs QA build and tests

**Trigger:** `requires-qa` label added to issue

**Process:**
1. Checks out repository with full history
2. Sets up Python 3.11 and Node.js 20
3. Configures git for commits
4. Calls `sapiens process-issue` to run QA
5. Uploads test results and coverage

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Node.js: 20
- Timeout: 30 minutes
- Artifacts: `qa-results-{issue}` (30 days retention)

---

#### 6. needs-fix.yaml

**Purpose:** Generates fix proposals after code review

**Trigger:** `needs-fix` label added to issue

**Process:**
1. Checks out repository with full history
2. Calls `sapiens process-issue` to create fix proposal
3. Comments completion status

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Timeout: 20 minutes

**Next step:** Add `approved` label to apply fixes

---

### Scheduled/Push Workflows (5)

#### 7. automation-daemon.yaml

**Purpose:** Periodically processes all pending issues

**Triggers:**
- Schedule: Every 5 minutes (cron)
- Manual: workflow_dispatch

**Process:**
1. Checks for recent activity (commits or issues updated in last 10 minutes)
2. **Skips processing if no recent activity** (optimization)
3. If active: processes all pending issues
4. Checks for stale workflows
5. Uploads state artifacts

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Schedule: `*/5 * * * *`
- Activity window: 10 minutes
- Artifact retention: 7 days

**Customization:**
```yaml
# Change schedule frequency
schedule:
  - cron: '*/15 * * * *'  # Every 15 minutes

# Change activity window (in check step)
cutoff_time=$((current_time - 1200))  # 20 minutes
```

---

#### 8. plan-merged.yaml

**Purpose:** Generates prompts when plan files are merged to main

**Triggers:**
- Push to main branch
- Modified files in `plans/**/*.md`

**Process:**
1. Detects changed plan files (compares with previous commit)
2. Extracts plan ID from filename (e.g., `plans/42-feature.md` → `42`)
3. Calls `sapiens generate-prompts` for each plan
4. Lists active plans for visibility

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Fetch depth: 2 (to compare with previous commit)

**Customization:**
```yaml
# Add additional branches
branches:
  - main
  - develop
```

---

#### 9. monitor.yaml

**Purpose:** System health monitoring and failure detection

**Triggers:**
- Schedule: Every 6 hours
- Manual: workflow_dispatch

**Process:**
1. Generates health report via `sapiens health-check`
2. Checks for failures in last 24 hours
3. Uploads report as artifact

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Schedule: `0 */6 * * *`

**Customization:**
```yaml
# Check different time window
- name: Check for failures
  run: sapiens check-failures --since-hours 48
```

---

#### 10. test.yaml

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

**Note:** All checks use `|| true` to prevent failures from blocking - review logs for actual issues.

---

#### 11. build-artifacts.yaml

**Purpose:** Builds reusable Python package and Docker image

**Triggers:**
- Push to main (changes to `repo_sapiens/`, `pyproject.toml`, `Dockerfile`)
- Pull requests to main
- Manual: workflow_dispatch
- Schedule: Daily at 2 AM (keeps artifacts fresh)

**Process:**
1. **build-package job:**
   - Builds Python wheel and source distribution
   - Uploads `sapiens-wheel` and `sapiens-sdist` artifacts
   - Creates package metadata JSON

2. **build-docker job:**
   - Builds Docker image with buildx
   - Tags as `latest` and commit SHA
   - Uploads `docker-image` artifact

3. **test-artifacts job:**
   - Downloads and tests wheel installation
   - Verifies package imports
   - Loads and tests Docker image

**Configuration:**
- Runs on: `ubuntu-latest`
- Python: 3.11
- Wheel retention: 30 days
- Docker image retention: 7 days

**Usage in other workflows:**
```yaml
- name: Download pre-built wheel (if available)
  uses: actions/download-artifact@v3
  with:
    name: sapiens-wheel
    path: dist/
  continue-on-error: true

- name: Install sapiens
  run: |
    if [ -f dist/*.whl ]; then
      pip install dist/*.whl
    else
      pip install -e .
    fi
```

---

## Environment Variables

### Required Secrets

All workflows require these secrets to be configured in repository settings:

```yaml
secrets:
  SAPIENS_GITEA_TOKEN: # Gitea API token with repo access
  SAPIENS_CLAUDE_API_KEY: # Claude API key for AI operations
  SAPIENS_GITEA_URL: # Gitea server URL (e.g., http://gitea.local:3000)
```

### Environment Variable Mapping

Workflows map secrets to automation config environment variables:

```yaml
env:
  # Direct usage
  GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  CLAUDE_API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}

  # Automation config mapping
  AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.SAPIENS_GITEA_URL }}
  AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  AUTOMATION__REPOSITORY__OWNER: ${{ gitea.repository_owner }}
  AUTOMATION__REPOSITORY__NAME: ${{ gitea.repository }}
  AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
```

### Gitea Context Variables

Automatically available in workflows:

```yaml
${{ gitea.repository_owner }}  # Repository owner
${{ gitea.repository }}        # Repository name
${{ gitea.ref_name }}          # Branch/tag name
${{ gitea.sha }}               # Commit SHA
${{ gitea.event.issue.number }} # Issue number (for issue events)
${{ gitea.event.label.name }}  # Label that triggered the event
```

---

## Workflow Dependencies

### Python Installation

Standard workflows install from source:
```yaml
- name: Install sapiens
  run: pip install -e .
```

Optimized workflows try pre-built wheel first:
```yaml
- name: Download pre-built wheel (if available)
  uses: actions/download-artifact@v3
  with:
    name: sapiens-wheel
    path: dist/
  continue-on-error: true

- name: Install sapiens
  run: |
    pip install --upgrade pip
    if [ -f dist/*.whl ]; then
      echo "✅ Using pre-built wheel"
      pip install dist/*.whl
    else
      echo "⚠️ Building from source"
      pip install -e .
    fi
```

### Git Configuration

Workflows that make commits configure git identity:
```yaml
- name: Configure git
  run: |
    git config --global user.name "Builder Bot"
    git config --global user.email "bot@builder.local"
```

### Caching

Workflows use pip caching for faster runs:
```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
```

---

## Workflow Outputs

### Artifacts by Workflow

| Workflow | Artifact Name | Contents | Retention |
|----------|---------------|----------|-----------|
| automation-daemon | `workflow-state` | `.automation/state/` | 7 days |
| execute-task | `task-state-{issue}` | `.automation/state/` | 7 days |
| needs-review | `review-artifacts-{issue}` | `.automation/reviews/` | 30 days |
| requires-qa | `qa-results-{issue}` | QA results, coverage | 30 days |
| monitor | `health-report` | `health-report.md` | default |
| test | `coverage-report` | `htmlcov/` | default |
| build-artifacts | `sapiens-wheel` | Python wheel | 30 days |
| build-artifacts | `sapiens-sdist` | Source distribution | 30 days |
| build-artifacts | `docker-image` | Docker tar | 7 days |
| build-artifacts | `package-metadata` | `package-info.json` | 30 days |
| build-artifacts | `docker-metadata` | `image-info.json` | 7 days |

### Accessing Artifacts

Via Gitea UI:
1. Go to Actions tab
2. Click on completed workflow run
3. Download artifacts from artifacts section

Via API:
```bash
curl -H "Authorization: token $GITEA_TOKEN" \
  "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
```

---

## Custom Workflows

### Creating a Label-Triggered Workflow

Create `.gitea/workflows/custom-label.yaml`:

```yaml
name: Custom Label Handler

on:
  issues:
    types: [labeled]

jobs:
  handle-custom:
    name: Handle Custom Label
    if: gitea.event.label.name == 'custom-label'
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.SAPIENS_GITEA_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install sapiens
        run: pip install -e .

      - name: Process issue
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.SAPIENS_GITEA_URL }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ gitea.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ gitea.repository }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
        run: |
          sapiens process-issue --issue ${{ gitea.event.issue.number }}

      - name: Comment on completion
        if: success()
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '✅ Custom processing complete!\n\n🤖 Posted by Builder Automation'
            })
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

---

## Performance Optimization

### Activity Check (Daemon)

The daemon workflow includes an activity check to avoid unnecessary runs:

```yaml
- name: Check for recent activity
  id: check_changes
  run: |
    current_time=$(date +%s)
    cutoff_time=$((current_time - 600))  # 10 minutes ago

    # Check latest commit
    latest_commit_time=$(git log -1 --format=%ct origin/main 2>/dev/null || echo 0)

    # Check for recently updated issues via API
    recent_issues=$(curl -s -H "Authorization: token $GITEA_TOKEN" \
      "$GITEA_URL/api/v1/repos/$OWNER/$REPO/issues?state=open&since=..." \
      | jq length 2>/dev/null || echo 0)

    if [ "$latest_commit_time" -gt "$cutoff_time" ] || [ "$recent_issues" -gt 0 ]; then
      echo "has_recent_changes=true" >> $GITHUB_OUTPUT
    else
      echo "has_recent_changes=false" >> $GITHUB_OUTPUT
    fi
```

### Pre-built Artifacts

Use `build-artifacts.yaml` outputs to speed up installations:
- Wheel artifacts avoid recompiling on every run
- Docker images provide consistent environments

### Path Filters

Limit triggers to relevant file changes:
```yaml
on:
  push:
    paths:
      - 'repo_sapiens/**'
      - 'tests/**'
      - 'pyproject.toml'
```

### Parallel Jobs

Run independent jobs concurrently:
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  build:
    needs: [lint, test]  # Wait for both
    runs-on: ubuntu-latest
    steps: [...]
```

---

## Security Best Practices

### Secrets Management

1. **Never log secrets:**
```yaml
- name: Use secret
  run: |
    # DON'T: echo ${{ secrets.SAPIENS_GITEA_TOKEN }}
    # DO: Use secret without logging
    sapiens process-issue --issue 42
  env:
    GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
```

2. **Use dedicated tokens:**
   - `SAPIENS_GITEA_TOKEN`: Repository access for automation
   - `SAPIENS_CLAUDE_API_KEY`: AI provider access
   - Separate concerns, rotate regularly

### Workflow Security

1. **Pin action versions:**
```yaml
# Recommended: use specific versions
uses: actions/checkout@v4
uses: actions/setup-python@v5
```

2. **Use timeouts:**
```yaml
jobs:
  job:
    timeout-minutes: 30
    runs-on: ubuntu-latest
```

3. **Validate label conditions:**
```yaml
# Require multiple labels for sensitive operations
if: gitea.event.label.name == 'execute' && contains(gitea.event.issue.labels.*.name, 'task')
```

---

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
    echo "Event: ${{ gitea.event_name }}"
    echo "Label: ${{ gitea.event.label.name }}"
    echo "Issue: ${{ gitea.event.issue.number }}"
    echo "Labels: ${{ join(gitea.event.issue.labels.*.name, ', ') }}"
```

### Manual Trigger

All scheduled workflows support `workflow_dispatch`:
```yaml
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:  # Enable manual trigger
```

### Debug Mode

```yaml
- name: Run with debug
  run: sapiens --log-level DEBUG process-issue --issue ${{ gitea.event.issue.number }}
```

---

## Troubleshooting

### Workflow Not Triggering

1. **Check label name:** Label must exactly match (case-sensitive)
2. **Check conditions:** Some workflows require multiple labels (e.g., `approved` + `proposed`)
3. **Check runner:** Ensure runner is available and connected
4. **Check secrets:** Verify all required secrets are configured

### Workflow Fails

1. View step logs for error messages
2. Check secrets are configured correctly
3. Verify repository permissions
4. Test commands locally first

### Activity Check Skipping

The daemon skips processing when no activity is detected. Check:
1. Recent commits in last 10 minutes
2. Recently updated issues
3. Manual trigger bypasses the check

### Slow Workflows

1. Use pre-built wheel artifacts
2. Enable pip caching
3. Reduce timeout if appropriate
4. Check for network issues

---

## Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [GitHub Actions Syntax Reference](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Cron Syntax](https://crontab.guru/)
