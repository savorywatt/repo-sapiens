# Gitea Label-Based Automation Research Report

**Date**: 2026-01-07
**Purpose**: Inform architectural decision for repo-sapiens automation system

---

## Executive Summary

Gitea Actions **does support** label-based triggers for both issues and pull requests via the `labeled` and `unlabeled` activity types. This eliminates the need for a polling daemon in most automation scenarios. However, several limitations and quirks exist that may require fallback mechanisms for complex use cases.

---

## 1. Gitea Actions Label Triggers

### Supported Events and Activity Types

Gitea Actions supports the following workflow trigger events with label-related activity types:

| Event | Label Activity Types | Status |
|-------|---------------------|--------|
| `issues` | `labeled`, `unlabeled` | ✅ Fully Supported |
| `pull_request` | `labeled`, `unlabeled` | ✅ Fully Supported |

**Source**: [Gitea Actions FAQ](https://docs.gitea.com/usage/actions/faq)

### Complete Event Support Table

```yaml
# All issues event types
on:
  issues:
    types: [opened, edited, closed, reopened, assigned, unassigned,
            milestoned, demilestoned, labeled, unlabeled]

# All pull_request event types
on:
  pull_request:
    types: [opened, edited, closed, reopened, assigned, unassigned,
            synchronize, labeled, unlabeled]
```

### Basic Workflow Example

```yaml
# .gitea/workflows/label-automation.yaml
name: Label-Based Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  process-label:
    runs-on: ubuntu-latest
    steps:
      - name: Check which label was added
        run: |
          echo "Label added: ${{ gitea.event.label.name }}"
          echo "Event type: ${{ gitea.event_name }}"

      - name: Handle specific label
        if: gitea.event.label.name == 'needs-review'
        run: |
          echo "Processing needs-review label..."
```

---

## 2. Accessing Label Information in Workflows

### The Label That Triggered the Event

When a `labeled` event fires, access the triggering label via:

```yaml
${{ gitea.event.label.name }}    # Label name
${{ gitea.event.label.id }}      # Label ID
${{ gitea.event.label.color }}   # Hex color (e.g., "00aabb")
```

### All Labels on the Issue/PR

To access all labels currently on the issue or pull request:

```yaml
# For pull requests
${{ gitea.event.pull_request.labels[0].name }}  # First label
${{ join(gitea.event.pull_request.labels.*.name, ', ') }}  # All labels

# For issues
${{ gitea.event.issue.labels[0].name }}
${{ join(gitea.event.issue.labels.*.name, ', ') }}
```

**Important**: Direct access to `gitea.event.label.*` works for the triggering label, but iterating through multiple labels requires accessing the `labels` array on the issue/PR object.

**Source**: [Gitea Forum Discussion](https://forum.gitea.com/t/getting-the-label-info-on-pull-request-labeled-workflow/9660)

---

## 3. Conditional Logic Based on Labels

### Simple Label Check

```yaml
jobs:
  deploy:
    if: gitea.event.label.name == 'deploy-to-staging'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying..."
```

### Multiple Label Check Using `contains()`

```yaml
jobs:
  handle-priority:
    # Check if added label is one of several
    if: contains(fromJSON('["priority/high", "priority/critical"]'), gitea.event.label.name)
    runs-on: ubuntu-latest
    steps:
      - run: echo "High priority item detected"
```

**Note**: Array literals cannot be used directly in `contains()`. Use `fromJSON()` to create arrays from JSON strings.

### Check if Issue/PR Has a Specific Label

```yaml
jobs:
  check-existing:
    runs-on: ubuntu-latest
    steps:
      - name: Check for bug label
        if: contains(gitea.event.issue.labels.*.name, 'bug')
        run: echo "This is a bug report"
```

---

## 4. Gitea Webhooks for Labels

### Available Webhook Events

Gitea supports dedicated webhook events for label changes:

| Webhook Event | JSON Key | Fires When |
|--------------|----------|------------|
| Issue Label | `issue_label` | Labels added/removed from issues |
| Pull Request Label | `pull_request_label` | Labels added/removed from PRs |

### Webhook Payload Structure

```json
{
  "action": "labeled",
  "number": 42,
  "issue": {
    "id": 12345,
    "number": 42,
    "title": "Issue title",
    "labels": [
      {
        "id": 1,
        "name": "bug",
        "color": "d73a4a",
        "description": "Something isn't working"
      }
    ]
  },
  "label": {
    "id": 1,
    "name": "bug",
    "color": "d73a4a",
    "description": "Something isn't working"
  },
  "repository": { ... },
  "sender": { ... }
}
```

### Webhook Headers

```
X-Gitea-Delivery: <unique-delivery-id>
X-Gitea-Event: issues (or pull_request)
X-Gitea-Event-Type: issue_label
```

**Source**: [Gitea Webhooks Documentation](https://docs.gitea.com/usage/webhooks)

---

## 5. Gitea Actions vs GitHub Actions Differences

### Compatibility Summary

| Feature | GitHub Actions | Gitea Actions | Notes |
|---------|---------------|---------------|-------|
| `labeled` trigger | ✅ | ✅ | Fully compatible |
| `unlabeled` trigger | ✅ | ✅ | Fully compatible |
| `github.event.label` | ✅ | ✅ | Use `gitea.event.label` (both work) |
| PR ref | `refs/pull/:n/merge` | `refs/pull/:n/head` | Gitea uses head, not merge preview |
| `repository_dispatch` | ✅ | ❌ | Not available in Gitea |
| `workflow_dispatch` | ✅ | ✅ | Supported since 1.23, API since 1.24 |
| Custom action URLs | ❌ | ✅ | Gitea allows `uses: https://...` |
| TZ in cron | ❌ | ✅ | Gitea extension: `TZ=Europe/London 0 9 * * *` |

### Unsupported Workflow Syntax

These GitHub Actions features are **ignored** in Gitea:

- `concurrency` - Job concurrency control
- `permissions` and `jobs.<job_id>.permissions`
- `jobs.<job_id>.timeout-minutes`
- `jobs.<job_id>.continue-on-error`
- `jobs.<job_id>.environment`
- Complex `runs-on` syntax (only `runs-on: xyz` or `runs-on: [xyz]`)

**Source**: [Gitea Actions Comparison](https://docs.gitea.com/usage/actions/comparison)

---

## 6. Real-World Examples

### Auto-Triage Based on Label

```yaml
name: Auto-Triage Issues

on:
  issues:
    types: [labeled]

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - name: Assign based on label
        if: gitea.event.label.name == 'needs-review'
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
        run: |
          curl -X PATCH \
            -H "Authorization: token $SAPIENS_GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"assignees": ["reviewer-bot"]}' \
            "${{ gitea.server_url }}/api/v1/repos/${{ gitea.repository }}/issues/${{ gitea.event.issue.number }}"
```

### Multi-Label Automation Workflow

```yaml
name: Label-Driven Automation

on:
  issues:
    types: [labeled, unlabeled]
  pull_request:
    types: [labeled, unlabeled]

jobs:
  # High priority handling
  priority-alert:
    if: |
      gitea.event.action == 'labeled' &&
      contains(fromJSON('["priority/critical", "priority/high"]'), gitea.event.label.name)
    runs-on: ubuntu-latest
    steps:
      - name: Send alert
        run: echo "High priority item needs attention!"

  # Ready for merge handling
  ready-to-merge:
    if: |
      gitea.event_name == 'pull_request' &&
      gitea.event.action == 'labeled' &&
      gitea.event.label.name == 'ready-to-merge'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger merge workflow
        run: echo "PR is ready for merge"
```

### Deploy on Label

```yaml
name: Deploy Preview

on:
  pull_request:
    types: [labeled]

jobs:
  deploy-preview:
    if: gitea.event.label.name == 'deploy-preview'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy preview environment
        run: |
          echo "Deploying PR #${{ gitea.event.pull_request.number }}"
          # deployment commands here

      - name: Post comment with URL
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
        run: |
          curl -X POST \
            -H "Authorization: token $SAPIENS_GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"body": "Preview deployed to https://preview-${{ gitea.event.pull_request.number }}.example.com"}' \
            "${{ gitea.server_url }}/api/v1/repos/${{ gitea.repository }}/issues/${{ gitea.event.pull_request.number }}/comments"
```

---

## 7. Limitations Requiring Daemon Fallback

### What Gitea Actions Cannot Do

| Limitation | Description | Workaround |
|------------|-------------|------------|
| **No `repository_dispatch`** | Cannot trigger workflows from external events | Use webhooks + external service |
| **API dispatch (pre-1.24)** | Cannot programmatically trigger workflows via API | Upgrade to 1.24+ or use schedule/push triggers |
| **Cross-repo triggers** | Cannot directly trigger workflow in another repo | Use API calls within workflow |
| **Conditional workflow files** | Cannot enable/disable workflow files dynamically | Use `if` conditions on all jobs |
| **Webhook-to-Actions bridge** | Cannot have webhooks trigger Actions directly | External service required |
| **Label filter on event** | Cannot limit workflow trigger to specific labels | Must use `if` conditions |

### When a Polling Daemon Is Still Needed

1. **External Event Sources**: When automation needs to react to events outside Gitea (external APIs, scheduled external checks)

2. **Complex Multi-Repo Orchestration**: Coordinating actions across multiple repositories that can't be achieved with workflow_call

3. **State Machines**: When automation requires maintaining state between events (e.g., "wait for label A, then label B, then do X")

4. **Rate-Limited Operations**: When you need to batch or throttle operations that would otherwise trigger too many workflows

5. **Fallback for Unreliable Triggers**: As a backup mechanism if webhook/Actions delivery fails

6. **Pre-1.21.6 Gitea Versions**: Older versions have bugs with `assigned`, `milestoned`, and `issue_comment` triggers

---

## 8. Triggering Workflows Programmatically

### Via API (Gitea 1.24+)

```bash
# Trigger workflow_dispatch via API
curl -X POST \
  -H "Authorization: token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "main",
    "inputs": {
      "environment": "staging"
    }
  }' \
  "https://gitea.example.com/api/v1/repos/owner/repo/actions/workflows/deploy.yaml/dispatches"
```

**Note**: This API was merged in PR #33545 for Gitea 1.24.0.

### Workflow with `workflow_dispatch`

```yaml
name: Manual Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying to ${{ inputs.environment }}"
```

---

## 9. Recommendations for repo-sapiens

### Primary Approach: Native Actions Triggers

For most label-based automation, use Gitea Actions directly:

```yaml
# .gitea/workflows/process-automation-label.yaml
name: Process Automation Labels

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  process:
    # Only process labels starting with "sapiens/"
    if: startsWith(gitea.event.label.name, 'sapiens/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run sapiens processor
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          sapiens process-label \
            --label "${{ gitea.event.label.name }}" \
            --issue "${{ gitea.event.issue.number || gitea.event.pull_request.number }}" \
            --repo "${{ gitea.repository }}"
```

### When to Keep Daemon

Retain daemon for:

1. **Scheduled cleanup/maintenance** - Though `on: schedule` works, a daemon offers more reliability
2. **External integrations** - Reacting to non-Gitea events
3. **Complex state machines** - Multi-step processes requiring state persistence
4. **Audit/monitoring** - Centralized logging and observability

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Event Sources                         │
├─────────────────────────────────────────────────────────┤
│  Label Added/Removed ──► Gitea Actions (direct trigger) │
│  Schedule ──────────────► Gitea Actions (cron)          │
│  Push/PR ───────────────► Gitea Actions (native)        │
│  External Events ───────► Daemon (webhook receiver)     │
│  Complex State ─────────► Daemon (orchestrator)         │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Version Compatibility Notes

| Feature | Minimum Version | Notes |
|---------|----------------|-------|
| `labeled`/`unlabeled` triggers | 1.19+ | Basic support |
| `assigned`/`milestoned` triggers | 1.21.6+ | Fixed in PR #29173 |
| `issue_comment` on PRs | 1.21.6+ | Fixed in PR #29277 |
| `workflow_dispatch` | 1.23+ | Manual UI trigger |
| `workflow_dispatch` API | 1.24+ | Programmatic trigger |
| TZ in cron schedules | 1.21.4+ | Gitea extension |

---

## Sources

- [Gitea Actions FAQ](https://docs.gitea.com/usage/actions/faq)
- [Gitea Actions Comparison](https://docs.gitea.com/usage/actions/comparison)
- [Gitea Webhooks Documentation](https://docs.gitea.com/usage/webhooks)
- [Gitea Forum: Label Info in Workflows](https://forum.gitea.com/t/getting-the-label-info-on-pull-request-labeled-workflow/9660)
- [Gitea Forum: Action to Label PRs](https://forum.gitea.com/t/action-to-label-prs/9702)
- [GitHub Issue #29166: PR assign/review triggers](https://github.com/go-gitea/gitea/issues/29166)
- [GitHub Issue #29175: issue_comment bug](https://github.com/go-gitea/gitea/issues/29175)
- [GitHub PR #32059: Workflow dispatch API](https://github.com/go-gitea/gitea/pull/32059)
- [Gitea Blog: Release 1.23.0](https://blog.gitea.com/release-of-1.23.0/)
