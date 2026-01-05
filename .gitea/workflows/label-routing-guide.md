# Label-Triggered Workflow Guide

This guide explains how the label-triggered Gitea Actions workflows work.

## Workflow Triggers

All workflows trigger when labels are added to issues:

```yaml
on:
  issues:
    types: [labeled]
```

## Available Workflows

### 1. `label-triggered.yaml` - Generic Label Handler
**Triggers:** Any label added
**Action:** Routes to appropriate automation based on the label
**Use case:** Catch-all handler for any labeled issue

### 2. `needs-planning.yaml` - Create Development Plan
**Triggers:** When `needs-planning` label is added
**Action:**
- Analyzes issue description
- Generates development plan using AI
- Creates plan proposal
- Adds `proposed` label

**Example:**
```bash
# User adds label
gh issue edit 123 --add-label "needs-planning"

# Workflow runs automatically:
# 1. Creates plan proposal
# 2. Posts plan as comment
# 3. Updates label to 'proposed'
```

### 3. `approved.yaml` - Create Tasks from Plan
**Triggers:** When `approved` label is added to a `proposed` issue
**Condition:** Issue must have both `proposed` and `approved` labels
**Action:**
- Breaks plan into individual tasks
- Creates task issues
- Links tasks to plan
- Marks tasks with `execute` label

**Example:**
```bash
# After reviewing plan proposal
gh issue edit 123 --add-label "approved"

# Workflow creates:
# - Issue #124: Task 1 (labeled: task, execute)
# - Issue #125: Task 2 (labeled: task, execute)
# - Issue #126: Task 3 (labeled: task, execute)
```

### 4. `execute-task.yaml` - Implement Task
**Triggers:** When `execute` label is added to a `task` issue
**Condition:** Issue must have both `task` and `execute` labels
**Action:**
- Checks out branch
- Implements task using AI
- Commits changes
- Creates/updates PR
- Adds `needs-review` label

**Example:**
```bash
# Tasks are auto-labeled with 'execute', or manually:
gh issue edit 124 --add-label "execute"

# Workflow:
# 1. Creates branch: task/124-feature-name
# 2. Implements changes
# 3. Pushes commits
# 4. Creates PR
# 5. Labels PR with 'needs-review'
```

### 5. `needs-review.yaml` - Code Review
**Triggers:** When `needs-review` label is added
**Action:**
- Fetches PR diff
- Reviews code with AI
- Posts review comments
- Updates label to `qa-passed` or `needs-fix`

**Example:**
```bash
gh pr edit 10 --add-label "needs-review"

# Workflow:
# 1. Analyzes PR diff
# 2. Posts review feedback
# 3. Labels as 'needs-fix' if issues found
# 4. Or 'requires-qa' if approved
```

### 6. `needs-fix.yaml` - Create Fix Proposal
**Triggers:** When `needs-fix` label is added
**Action:**
- Analyzes review feedback
- Generates fix proposal
- Posts proposal as comment
- Waits for `approved` label

**Example:**
```bash
# After code review finds issues
# Label is auto-added, or manually:
gh pr edit 10 --add-label "needs-fix"

# Workflow:
# 1. Creates fix proposal
# 2. Posts proposed changes
# 3. Waits for approval
```

### 7. `requires-qa.yaml` - QA Build & Test
**Triggers:** When `requires-qa` label is added
**Action:**
- Checks out PR branch
- Runs build
- Runs tests (or creates them if missing)
- Reports results
- Updates label to `qa-passed` or `qa-failed`

**Example:**
```bash
gh pr edit 10 --add-label "requires-qa"

# Workflow:
# 1. Checks out branch
# 2. Runs npm build (or equivalent)
# 3. Runs npm test
# 4. Creates tests if missing
# 5. Posts results
# 6. Labels 'qa-passed' or 'qa-failed'
```

## Label Flow Diagram

```
Issue Created
     |
     v
[needs-planning] ──> Plan Proposal Created
     |                       |
     v                       v
[proposed] ──────────> [approved] ──> Tasks Created
                                           |
                                           v
                                      [task, execute] ──> Implementation
                                           |
                                           v
                                      PR Created ──> [needs-review]
                                           |
                                           v
                                    Code Review
                                    /          \
                                   v            v
                            [needs-fix]    [requires-qa]
                                   |            |
                                   v            v
                            Fix Proposal    QA Build/Test
                                   |            |
                                   v            v
                            [approved]      [qa-passed]
                                   |            |
                                   v            v
                            Apply Fixes    Ready to Merge
```

## Manual Triggering

You can manually trigger workflows by adding labels:

```bash
# Trigger planning
gh issue edit 123 --add-label "needs-planning"

# Approve a plan
gh issue edit 123 --add-label "approved"

# Execute a task
gh issue edit 124 --add-label "execute"

# Request code review
gh pr edit 10 --add-label "needs-review"

# Request QA
gh pr edit 10 --add-label "requires-qa"

# Approve fixes
gh issue edit 125 --add-label "approved"
```

## Workflow Conditions

Each workflow has specific conditions to prevent false triggers:

### needs-planning.yaml
```yaml
if: gitea.event.label.name == 'needs-planning'
```

### approved.yaml
```yaml
if: |
  gitea.event.label.name == 'approved' &&
  contains(gitea.event.issue.labels.*.name, 'proposed')
```

### execute-task.yaml
```yaml
if: |
  gitea.event.label.name == 'execute' &&
  contains(gitea.event.issue.labels.*.name, 'task')
```

### needs-review.yaml
```yaml
if: gitea.event.label.name == 'needs-review'
```

### needs-fix.yaml
```yaml
if: gitea.event.label.name == 'needs-fix'
```

### requires-qa.yaml
```yaml
if: gitea.event.label.name == 'requires-qa'
```

## Environment Variables

All workflows use these environment variables:

```yaml
env:
  AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.SAPIENS_GITEA_URL }}
  AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  AUTOMATION__REPOSITORY__OWNER: ${{ gitea.repository_owner }}
  AUTOMATION__REPOSITORY__NAME: ${{ gitea.repository }}
  AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
```

## Required Secrets

Set these in your Gitea repository settings (Settings → Secrets):

- `SAPIENS_GITEA_URL` - Your Gitea instance URL (e.g., `http://gitea:3000`)
- `SAPIENS_GITEA_TOKEN` - Gitea API token with repo permissions
- `SAPIENS_CLAUDE_API_KEY` - Claude API key for AI operations

## Testing Workflows

### Test Single Workflow
```bash
# Add label to trigger specific workflow
gh issue edit 123 --add-label "needs-planning"

# Watch workflow
gh run watch

# Check workflow logs
gh run view --log
```

### Test Complete Flow
```bash
# 1. Create issue
gh issue create --title "Add user authentication" --body "Need to add login/logout"

# 2. Trigger planning
gh issue edit 123 --add-label "needs-planning"
# Wait for plan proposal...

# 3. Approve plan
gh issue edit 123 --add-label "approved"
# Wait for tasks to be created...

# 4. Tasks execute automatically (they're labeled with 'execute')
# PRs are created with 'needs-review' label

# 5. Review triggers automatically
# QA triggers if approved

# 6. Monitor progress
gh issue list --label "task"
gh pr list --label "needs-review"
```

## Debugging

### Check Workflow Runs
```bash
gh run list --workflow=needs-planning.yaml
gh run list --workflow=execute-task.yaml
```

### View Logs
```bash
gh run view <run-id> --log
```

### Check Label Conditions
```bash
# List issue labels
gh issue view 123 --json labels --jq '.labels[].name'

# Verify conditions
gh issue view 123 --json labels --jq '.labels | map(.name) | contains(["proposed", "approved"])'
```

## Best Practices

1. **Label Order Matters**: Follow the label flow diagram
2. **Don't Skip Steps**: Each stage depends on the previous one
3. **Monitor Workflows**: Check workflow status after adding labels
4. **Review Before Approval**: Always review proposals before adding `approved`
5. **Use Artifacts**: Workflows upload logs and results as artifacts

## Common Issues

### Workflow Doesn't Trigger
- Check label name matches exactly (case-sensitive)
- Verify webhook is configured
- Check Actions is enabled in Gitea
- Verify runner is available

### Workflow Fails
- Check secrets are configured
- Verify API token has correct permissions
- Check workflow logs for errors
- Ensure dependencies are available

### Wrong Workflow Triggers
- Check label conditions in workflow
- Verify issue has correct combination of labels
- Review workflow conditions in YAML

## Example: Complete Workflow

```bash
# 1. User creates issue
gh issue create \
  --title "Add dark mode toggle" \
  --body "Users want to switch between light and dark themes"

# 2. Automation: Add needs-planning label
gh issue edit 127 --add-label "needs-planning"
# → Workflow: needs-planning.yaml runs
# → Creates plan proposal
# → Adds 'proposed' label

# 3. User: Review and approve
gh issue view 127  # Review plan
gh issue edit 127 --add-label "approved"
# → Workflow: approved.yaml runs
# → Creates tasks #128, #129, #130
# → Each task labeled: task, execute

# 4. Automation: Tasks execute automatically
# → Workflow: execute-task.yaml runs for each
# → Creates PRs #11, #12, #13
# → Each PR labeled: needs-review

# 5. Automation: Code reviews run automatically
# → Workflow: needs-review.yaml runs for each PR
# → Posts review comments
# → Adds 'requires-qa' if approved

# 6. Automation: QA runs automatically
# → Workflow: requires-qa.yaml runs
# → Builds and tests code
# → Adds 'qa-passed' or 'qa-failed'

# 7. Manual: Merge if all passed
gh pr merge 11 --squash
```

## Summary

Label-triggered workflows enable:
- ✅ Real-time automation (no polling delay)
- ✅ Event-driven architecture
- ✅ Fine-grained control
- ✅ Clear workflow visibility
- ✅ Manual override capability

Each label addition triggers specific automation, creating a smooth, automated development workflow from issue to merged PR.
