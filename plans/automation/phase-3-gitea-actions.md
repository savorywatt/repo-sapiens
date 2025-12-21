# Phase 3: Gitea Actions Integration - Implementation Guide

## Overview

Automate the workflow execution using Gitea Actions (or GitHub Actions). This phase transforms the system from manually triggered CLI tool to fully automated CI/CD pipeline that responds to issue events in real-time.

## Prerequisites

- Phase 2 completed successfully
- Full workflow functional via CLI
- Access to Gitea instance with Actions enabled
- Gitea runner configured (or GitHub Actions for testing)

## Implementation Steps

### Step 1: Gitea Actions Workflow for Issue Events

**Files to Create:**
- `/home/ross/Workspace/builder/.gitea/workflows/automation-trigger.yaml`

**Implementation:**

Create workflow that triggers on issue events:

```yaml
name: Automation Trigger

on:
  issues:
    types: [opened, labeled, unlabeled, edited, closed]
  issue_comment:
    types: [created]

jobs:
  process-issue:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git operations

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -e .

      - name: Determine action needed
        id: determine
        run: |
          # Check issue labels to determine which stage to trigger
          python -c "
          import json
          import sys

          event = json.loads('''${{ toJSON(github.event) }}''')
          issue = event.get('issue', {})
          labels = [label['name'] for label in issue.get('labels', [])]

          # Determine stage based on labels
          if 'needs-planning' in labels:
              print('stage=planning')
          elif 'plan-review' in labels:
              print('stage=plan-review')
          elif 'prompts' in labels:
              print('stage=prompts')
          elif 'implement' in labels:
              print('stage=implementation')
          elif 'code-review' in labels:
              print('stage=code-review')
          elif 'merge-ready' in labels:
              print('stage=merge')
          else:
              print('stage=none')
          " >> $GITHUB_OUTPUT

      - name: Run automation
        if: steps.determine.outputs.stage != 'none'
        env:
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          automation process-issue \
            --issue ${{ github.event.issue.number }} \
            --stage ${{ steps.determine.outputs.stage }} \
            --log-level INFO

      - name: Report status
        if: always()
        run: |
          if [ $? -eq 0 ]; then
            echo "✅ Automation completed successfully"
          else
            echo "❌ Automation failed"
            exit 1
          fi
```

**Key features:**
- Triggers on issue events (opened, labeled, etc.)
- Determines which stage to run based on labels
- Uses secrets for API tokens
- Reports success/failure
- Full git history for branch operations

### Step 2: Workflow for Plan Merges

**Files to Create:**
- `/home/ross/Workspace/builder/.gitea/workflows/plan-merged.yaml`

**Implementation:**

Create workflow that triggers when plans are merged:

```yaml
name: Plan Merged - Generate Prompts

on:
  push:
    branches:
      - main
    paths:
      - 'plans/**/*.md'

jobs:
  generate-prompts:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 2  # Need previous commit to detect changes

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -e .

      - name: Detect changed plans
        id: detect-plans
        run: |
          # Get list of changed plan files
          CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD | grep '^plans/.*\.md$' || true)

          if [ -z "$CHANGED_FILES" ]; then
            echo "No plan files changed"
            echo "has_changes=false" >> $GITHUB_OUTPUT
          else
            echo "Changed plans:"
            echo "$CHANGED_FILES"
            echo "has_changes=true" >> $GITHUB_OUTPUT
            echo "plan_files<<EOF" >> $GITHUB_OUTPUT
            echo "$CHANGED_FILES" >> $GITHUB_OUTPUT
            echo "EOF" >> $GITHUB_OUTPUT
          fi

      - name: Generate prompts from plans
        if: steps.detect-plans.outputs.has_changes == 'true'
        env:
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          # Process each changed plan file
          echo "${{ steps.detect-plans.outputs.plan_files }}" | while read -r plan_file; do
            if [ -n "$plan_file" ]; then
              echo "Processing plan: $plan_file"

              # Extract plan ID from filename (e.g., plans/42-feature.md -> 42)
              plan_id=$(basename "$plan_file" | sed 's/^\([0-9]*\)-.*/\1/')

              automation generate-prompts \
                --plan-file "$plan_file" \
                --plan-id "$plan_id"
            fi
          done

      - name: Report results
        if: always()
        run: |
          echo "Prompt generation completed"
          automation list-active-plans
```

**Key features:**
- Triggers on pushes to main that modify plan files
- Detects which plan files changed
- Generates prompts for each changed plan
- Lists active plans for visibility

### Step 3: Continuous Workflow Execution

**Files to Create:**
- `/home/ross/Workspace/builder/.gitea/workflows/automation-daemon.yaml`

**Implementation:**

Create scheduled workflow for continuous processing:

```yaml
name: Automation Daemon

on:
  schedule:
    # Run every 5 minutes
    - cron: '*/5 * * * *'
  workflow_dispatch:  # Allow manual triggering

jobs:
  process-pending:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -e .

      - name: Process all pending issues
        env:
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          automation process-all --log-level INFO

      - name: Check for stale workflows
        run: |
          automation check-stale --max-age-hours 24

      - name: Upload state artifacts
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-state
          path: .automation/state/
          retention-days: 7
```

**Key features:**
- Runs every 5 minutes via cron schedule
- Processes all pending issues
- Checks for stale workflows
- Uploads state files as artifacts for debugging

### Step 4: CLI Enhancements for CI/CD

**Files to Modify:**
- `/home/ross/Workspace/builder/automation/main.py`

**Actions:**

Add new CLI commands for CI/CD operations:

```python
@cli.command()
@click.option("--issue", type=int, required=True)
@click.option("--stage", required=True,
              type=click.Choice(["planning", "plan-review", "prompts",
                                "implementation", "code-review", "merge"]))
@click.pass_context
def process_issue(ctx, issue, stage):
    """Process specific issue at given stage (for CI/CD)."""
    asyncio.run(_process_issue_stage(ctx.obj["settings"], issue, stage))

@cli.command()
@click.option("--plan-file", required=True)
@click.option("--plan-id", required=True)
@click.pass_context
def generate_prompts(ctx, plan_file, plan_id):
    """Generate prompt issues from plan file (for CI/CD)."""
    asyncio.run(_generate_prompts_from_file(ctx.obj["settings"], plan_file, plan_id))

@cli.command()
@click.pass_context
def list_active_plans(ctx):
    """List all active workflow plans."""
    asyncio.run(_list_active_plans(ctx.obj["settings"]))

@cli.command()
@click.option("--max-age-hours", type=int, default=24)
@click.pass_context
def check_stale(ctx, max_age_hours):
    """Check for stale workflows that haven't progressed."""
    asyncio.run(_check_stale_workflows(ctx.obj["settings"], max_age_hours))

async def _process_issue_stage(settings: AutomationSettings, issue_number: int, stage: str):
    """Process issue at specific stage."""
    log.info("process_issue_stage", issue=issue_number, stage=stage)

    orchestrator = await _create_orchestrator(settings)
    issue = await orchestrator.git.get_issue(issue_number)

    # Route to specific stage
    stage_handler = orchestrator.stages.get(stage.replace("-", "_"))
    if not stage_handler:
        raise ValueError(f"Unknown stage: {stage}")

    await stage_handler.execute(issue)
    log.info("stage_complete", issue=issue_number, stage=stage)

async def _generate_prompts_from_file(
    settings: AutomationSettings,
    plan_file: str,
    plan_id: str
):
    """Generate prompts from plan file."""
    log.info("generate_prompts", plan_file=plan_file, plan_id=plan_id)

    # Read plan file
    from pathlib import Path
    plan_content = Path(plan_file).read_text()

    # Initialize providers
    orchestrator = await _create_orchestrator(settings)

    # Generate prompts
    # Create issues for each prompt
    # Update state

    log.info("prompts_generated", plan_id=plan_id)

async def _list_active_plans(settings: AutomationSettings):
    """List active plans."""
    state_manager = StateManager(settings.state_dir)
    active = await state_manager.get_active_plans()

    print("Active Plans:")
    for plan_id in active:
        state = await state_manager.load_state(plan_id)
        print(f"  - Plan {plan_id}: {state['status']}")

async def _check_stale_workflows(settings: AutomationSettings, max_age_hours: int):
    """Check for stale workflows."""
    from datetime import datetime, timedelta

    state_manager = StateManager(settings.state_dir)
    active = await state_manager.get_active_plans()

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    stale_plans = []

    for plan_id in active:
        state = await state_manager.load_state(plan_id)
        updated = datetime.fromisoformat(state["updated_at"])

        if updated < cutoff:
            stale_plans.append((plan_id, state))
            log.warning("stale_workflow", plan_id=plan_id, age_hours=(datetime.now() - updated).total_seconds() / 3600)

    if stale_plans:
        print(f"Found {len(stale_plans)} stale workflows")
        for plan_id, state in stale_plans:
            print(f"  - Plan {plan_id}: {state['status']} (last updated: {state['updated_at']})")
    else:
        print("No stale workflows found")
```

### Step 5: Secrets Management

**Files to Create:**
- `/home/ross/Workspace/builder/docs/secrets-setup.md`

**Implementation:**

Document how to set up secrets in Gitea:

1. **Repository Secrets:**
   - `GITEA_TOKEN`: Personal access token with repo access
   - `CLAUDE_API_KEY`: Anthropic API key (if using API mode)

2. **Environment Variables:**
   - `AUTOMATION__GIT_PROVIDER__API_TOKEN`: Mapped from GITEA_TOKEN
   - `AUTOMATION__AGENT_PROVIDER__API_KEY`: Mapped from CLAUDE_API_KEY

3. **Security Best Practices:**
   - Never commit secrets to repository
   - Rotate tokens regularly
   - Use minimal required permissions
   - Audit secret access

**Gitea Secrets Setup:**
```bash
# Via Gitea UI:
# 1. Go to repository Settings → Secrets
# 2. Add GITEA_TOKEN with repo scope
# 3. Add CLAUDE_API_KEY for AI operations

# Via API (if needed):
curl -X POST "https://gitea.example.com/api/v1/repos/{owner}/{repo}/secrets" \
  -H "Authorization: token ${GITEA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GITEA_TOKEN",
    "data": "your-token-here"
  }'
```

### Step 6: Webhook Support (Optional)

**Files to Create:**
- `/home/ross/Workspace/builder/automation/webhook_server.py`

**Implementation:**

Create webhook server for real-time event processing:

```python
from fastapi import FastAPI, Request, HTTPException
from typing import Dict
import structlog
from automation.config.settings import AutomationSettings
from automation.engine.orchestrator import WorkflowOrchestrator

log = structlog.get_logger(__name__)

app = FastAPI(title="Gitea Automation Webhook Server")

# Global state
settings: AutomationSettings = None
orchestrator: WorkflowOrchestrator = None

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global settings, orchestrator
    settings = AutomationSettings.from_yaml("automation/config/automation_config.yaml")
    orchestrator = await create_orchestrator(settings)
    log.info("webhook_server_started")

@app.post("/webhook/gitea")
async def gitea_webhook(request: Request):
    """Handle Gitea webhook events."""
    event_type = request.headers.get("X-Gitea-Event")

    if not event_type:
        raise HTTPException(status_code=400, detail="Missing X-Gitea-Event header")

    payload = await request.json()

    log.info("webhook_received", event_type=event_type)

    try:
        if event_type == "issues":
            await handle_issue_event(payload)
        elif event_type == "push":
            await handle_push_event(payload)
        else:
            log.warning("unhandled_event_type", event_type=event_type)

        return {"status": "success", "event_type": event_type}

    except Exception as e:
        log.error("webhook_processing_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def handle_issue_event(payload: Dict):
    """Handle issue event from webhook."""
    action = payload.get("action")
    issue_data = payload.get("issue", {})
    issue_number = issue_data.get("number")

    if action in ["opened", "labeled"]:
        # Fetch full issue and process
        issue = await orchestrator.git.get_issue(issue_number)
        await orchestrator.process_issue(issue)

    log.info("issue_event_processed", issue=issue_number, action=action)

async def handle_push_event(payload: Dict):
    """Handle push event from webhook."""
    ref = payload.get("ref")
    commits = payload.get("commits", [])

    # Check if any commits modified plan files
    for commit in commits:
        modified = commit.get("modified", [])
        for file_path in modified:
            if file_path.startswith("plans/") and file_path.endswith(".md"):
                # Extract plan ID and generate prompts
                plan_id = extract_plan_id(file_path)
                # Process plan

    log.info("push_event_processed", ref=ref)

def extract_plan_id(file_path: str) -> str:
    """Extract plan ID from file path."""
    import re
    match = re.search(r'plans/(\d+)-', file_path)
    return match.group(1) if match else None

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "automation-webhook"}
```

**Deployment:**
```bash
# Run webhook server
uvicorn automation.webhook_server:app --host 0.0.0.0 --port 8000

# Or with gunicorn for production
gunicorn automation.webhook_server:app -w 4 -k uvicorn.workers.UvicornWorker
```

**Gitea Webhook Configuration:**
```
URL: https://your-server.com/webhook/gitea
Content Type: application/json
Secret: (optional webhook secret)
Events: Issues, Push
```

### Step 7: Action-Specific Configuration

**Files to Create:**
- `/home/ross/Workspace/builder/automation/config/actions_config.yaml`

**Implementation:**

Create configuration optimized for CI/CD:

```yaml
# Inherit from main config but override for Actions
git_provider:
  type: gitea
  mcp_server: gitea-mcp
  base_url: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY_OWNER}
  api_token: ${GITEA_TOKEN}

repository:
  owner: ${GITHUB_REPOSITORY_OWNER}
  name: ${GITHUB_REPOSITORY#*/}  # Extract repo name
  default_branch: ${GITHUB_REF_NAME}

agent_provider:
  type: claude
  model: claude-sonnet-4.5
  api_key: ${CLAUDE_API_KEY}
  local: false  # Use API in CI/CD

workflow:
  plans_directory: plans/
  branching_strategy: per-agent
  max_concurrent_tasks: 2  # Limit for CI/CD
  parallel_execution: true

# CI/CD specific settings
cicd:
  timeout_minutes: 30
  retry_on_failure: true
  max_retries: 2
  report_status_to_issue: true
```

### Step 8: Status Reporting

**Files to Create:**
- `/home/ross/Workspace/builder/automation/utils/status_reporter.py`

**Implementation:**

Create status reporter for posting updates to issues:

```python
from typing import Optional
from automation.providers.base import GitProvider
from automation.models.domain import Issue
import structlog

log = structlog.get_logger(__name__)

class StatusReporter:
    """Report workflow status back to issues."""

    def __init__(self, git: GitProvider):
        self.git = git

    async def report_stage_start(self, issue: Issue, stage: str) -> None:
        """Report that stage has started."""
        message = f"""
        🤖 **Automation Update**

        Stage: **{stage}**
        Status: ⏳ In Progress
        Started: {datetime.now().isoformat()}
        """
        await self.git.add_comment(issue.number, message.strip())
        log.info("status_reported", issue=issue.number, stage=stage, status="started")

    async def report_stage_complete(
        self,
        issue: Issue,
        stage: str,
        details: Optional[str] = None
    ) -> None:
        """Report that stage completed successfully."""
        message = f"""
        🤖 **Automation Update**

        Stage: **{stage}**
        Status: ✅ Completed
        Completed: {datetime.now().isoformat()}

        {details or ''}
        """
        await self.git.add_comment(issue.number, message.strip())
        log.info("status_reported", issue=issue.number, stage=stage, status="completed")

    async def report_stage_failed(
        self,
        issue: Issue,
        stage: str,
        error: str
    ) -> None:
        """Report that stage failed."""
        message = f"""
        🤖 **Automation Update**

        Stage: **{stage}**
        Status: ❌ Failed
        Failed: {datetime.now().isoformat()}

        **Error:**
        ```
        {error}
        ```

        A team member will need to investigate and resolve this issue.
        """
        await self.git.add_comment(issue.number, message.strip())
        log.error("status_reported", issue=issue.number, stage=stage, status="failed")
```

Integrate into workflow stages:
```python
# In each stage's execute method:
class PlanningStage(WorkflowStage):
    async def execute(self, issue: Issue) -> None:
        reporter = StatusReporter(self.git)

        await reporter.report_stage_start(issue, "Planning")

        try:
            # ... stage logic ...

            await reporter.report_stage_complete(
                issue,
                "Planning",
                f"Plan created: {plan.file_path}"
            )
        except Exception as e:
            await reporter.report_stage_failed(issue, "Planning", str(e))
            raise
```

### Step 9: Monitoring and Observability

**Files to Create:**
- `/home/ross/Workspace/builder/.gitea/workflows/monitor.yaml`

**Implementation:**

Create monitoring workflow:

```yaml
name: Automation Monitor

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e .

      - name: Generate health report
        env:
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
        run: |
          automation health-check > health-report.md

      - name: Check for failures
        run: |
          automation check-failures --since-hours 24

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: health-report
          path: health-report.md
```

Add health check command:
```python
@cli.command()
@click.pass_context
def health_check(ctx):
    """Generate health check report."""
    asyncio.run(_health_check(ctx.obj["settings"]))

async def _health_check(settings: AutomationSettings):
    """Generate comprehensive health check."""
    report = []
    report.append("# Automation System Health Report\n")
    report.append(f"Generated: {datetime.now().isoformat()}\n\n")

    # Check active plans
    state_manager = StateManager(settings.state_dir)
    active = await state_manager.get_active_plans()
    report.append(f"## Active Plans: {len(active)}\n")

    # Check for failures
    failed_count = 0
    for plan_id in active:
        state = await state_manager.load_state(plan_id)
        if state["status"] == "failed":
            failed_count += 1
            report.append(f"- ❌ Plan {plan_id}: FAILED\n")

    report.append(f"\n## Failed Plans: {failed_count}\n")

    # Check provider health
    report.append("\n## Provider Health\n")
    # Test Gitea connectivity
    # Test agent availability

    print("".join(report))
```

### Step 10: Testing in CI/CD

**Files to Create:**
- `/home/ross/Workspace/builder/.gitea/workflows/test.yaml`

**Implementation:**

Create test workflow that runs on PRs:

```yaml
name: Tests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run linters
        run: |
          black --check automation/ tests/
          ruff check automation/ tests/
          mypy automation/

      - name: Run tests
        run: |
          pytest tests/ -v --cov=automation --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

      - name: Upload coverage report
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report
          path: htmlcov/
```

## Success Criteria

At the end of Phase 3, you should have:

1. **Automated Workflow Execution:**
   - Creating an issue with `needs-planning` label triggers automation
   - All stages execute automatically
   - Status updates posted to issues
   - PR created when complete

2. **CI/CD Integration:**
   - Gitea Actions workflows configured
   - Secrets properly set up
   - All workflows execute successfully
   - Tests run on every PR

3. **Monitoring:**
   - Health checks run periodically
   - Stale workflows detected
   - Failures reported
   - Metrics collected

4. **Documentation:**
   - CI/CD setup guide
   - Secrets management documentation
   - Troubleshooting guide
   - Workflow diagrams

5. **Testing:**
   ```bash
   # Create test issue in Gitea
   # Verify automation triggers automatically
   # Check all stages complete
   # Verify PR is created
   ```

## Common Issues and Solutions

**Issue: Workflow doesn't trigger**
- Solution: Check webhook configuration in Gitea
- Verify secrets are set correctly
- Check Gitea Actions runner is active

**Issue: Permission denied errors**
- Solution: Ensure GITEA_TOKEN has correct scopes
- Check repository permissions
- Verify runner has access

**Issue: Timeout in CI/CD**
- Solution: Increase timeout in workflow file
- Reduce concurrent tasks
- Optimize agent execution

**Issue: State conflicts in parallel runs**
- Solution: Ensure atomic state updates
- Use file locking correctly
- Consider distributed locking for multi-runner setups

## Next Steps

After completing Phase 3:
1. Monitor automation in production
2. Gather metrics on performance
3. Identify areas for optimization
4. Move on to Phase 4: Advanced Features

Phase 4 will add:
- Advanced error recovery
- Performance optimizations
- Multi-repository support
- Enhanced monitoring and analytics
