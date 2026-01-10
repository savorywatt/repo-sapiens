# Native Label-Triggered Automation

This document explains how to use native CI/CD platforms (Gitea Actions, GitHub Actions, GitLab CI) to trigger repo-sapiens automation workflows based on labels.

## Overview

Native label triggers allow you to run repo-sapiens automation directly from your CI/CD platform when labels are added to issues or pull requests. This approach offers several advantages over the polling-based daemon:

| Feature | Native Triggers | Daemon Polling |
|---------|----------------|----------------|
| Response time | Instant (seconds) | Polling interval (minutes) |
| Resource usage | On-demand only | Continuous process |
| Infrastructure | Uses CI/CD runners | Requires daemon host |
| Scalability | Platform-managed | Self-managed |
| Cost | Per-execution | Fixed (server costs) |

## Quick Start

### 1. Configure Label Triggers

Add the `automation` section to your `.sapiens/config.yaml`:

```yaml
# .sapiens/config.yaml
automation:
  mode:
    mode: native           # or "hybrid" to keep daemon as fallback
    native_enabled: true
    daemon_enabled: false
    label_prefix: "sapiens/"

  label_triggers:
    "sapiens/triage":
      handler: triage
      ai_enabled: true
      remove_on_complete: true
      success_label: triaged

    "needs-planning":
      handler: proposal
      ai_enabled: true
      remove_on_complete: false
      success_label: planned

    "sapiens/review/security":
      handler: security_review
      ai_enabled: true
      remove_on_complete: true
      success_label: security-reviewed
      failure_label: needs-attention
```

### 2. Generate Workflow Files

Run the migration tool to generate platform-specific workflow files:

```bash
# Preview what will be generated
sapiens migrate generate --dry-run

# Generate the files
sapiens migrate generate
```

### 3. Commit and Push

Commit the generated workflow files to your repository:

```bash
git add .gitea/workflows/  # or .github/workflows/
git commit -m "feat: Add native label-triggered automation"
git push
```

### 4. Test

Add a configured label to an issue and watch the workflow run.

## Supported Labels and Handlers

### Built-in Handlers

These handlers map to existing workflow stages:

| Handler | Description | Stage |
|---------|-------------|-------|
| `proposal` | Generate implementation proposal | proposal |
| `approval` | Process approval workflow | approval |
| `task_execution` | Execute approved task | task_execution |
| `pr_review` | Review pull request | pr_review |
| `pr_fix` | Apply PR review fixes | pr_fix |
| `fix_execution` | Execute fix implementation | fix_execution |
| `qa` | Quality assurance checks | qa |
| `triage` | Issue triage and categorization | triage |
| `security_review` | Security-focused review | security_review |
| `docs_generation` | Generate documentation | docs_generation |
| `test_coverage` | Analyze and improve test coverage | test_coverage |
| `dependency_audit` | Audit dependencies | dependency_audit |

### Custom Handlers

For handlers not in the built-in list, repo-sapiens will invoke the AI agent with a task prompt constructed from the handler name and issue content.

## Label Trigger Configuration

Each label trigger supports these options:

```yaml
"label-name":
  handler: string           # Required: Handler name to invoke
  ai_enabled: bool          # Default: true - Whether handler requires AI
  remove_on_complete: bool  # Default: true - Remove trigger label on success
  success_label: string     # Optional: Label to add on success
  failure_label: string     # Default: "needs-attention" - Label to add on failure
```

### Label Pattern Matching

Labels can use glob patterns for flexible matching:

```yaml
label_triggers:
  # Exact match
  "needs-planning":
    handler: proposal

  # Prefix match (matches sapiens/triage, sapiens/review, etc.)
  "sapiens/*":
    handler: auto_dispatch

  # More specific patterns take precedence when listed first
  "sapiens/review/security":
    handler: security_review
  "sapiens/review/*":
    handler: generic_review
```

## Platform-Specific Configuration

### Gitea Actions

Generated workflow location: `.gitea/workflows/process-label.yaml`

Required secrets:
- `SAPIENS_GITEA_TOKEN` - Gitea API token with repo access

Workflow triggers on:
- `issues.labeled`
- `pull_request.labeled`

### GitHub Actions

Generated workflow location: `.github/workflows/process-label.yaml`

Required secrets:
- `GITHUB_TOKEN` - Automatically provided by GitHub

Workflow triggers on:
- `issues.labeled`
- `pull_request.labeled`

### GitLab CI

Generated workflow location: `.gitlab-ci.yml` (process-label job)

Required variables:
- `GITLAB_TOKEN` - GitLab API token

**Note**: GitLab CI has limited support for label-specific triggers. The workflow runs on merge request events and filters by labels at runtime.

## Migration Commands

### Analyze Current Setup

```bash
sapiens migrate analyze
```

Outputs a report showing:
- Current automation mode
- Configured triggers
- Existing workflow files
- Migration recommendations

### Generate Workflows

```bash
# Preview changes
sapiens migrate generate --dry-run

# Generate files
sapiens migrate generate

# Overwrite existing files
sapiens migrate generate --force
```

### Validate Setup

```bash
sapiens migrate validate
```

Checks:
- Native mode is enabled in config
- Label triggers are configured
- Workflow files exist
- Required secrets (documentation)

## Automation Modes

### Native Mode

All automation runs through CI/CD workflows. No daemon required.

```yaml
automation:
  mode:
    mode: native
    native_enabled: true
    daemon_enabled: false
```

### Daemon Mode (Legacy)

Traditional polling-based daemon. Native triggers disabled.

```yaml
automation:
  mode:
    mode: daemon
    native_enabled: false
    daemon_enabled: true
```

### Hybrid Mode

Best of both worlds. Native triggers for supported events, daemon for everything else.

```yaml
automation:
  mode:
    mode: hybrid
    native_enabled: true
    daemon_enabled: true
    daemon_fallback_only: true  # Daemon only handles what native can't
```

## Requirements

### Gitea

- Gitea version 1.19+ (Actions support)
- Actions runner configured and active
- Repository secrets configured

### GitHub

- GitHub Actions enabled on repository
- No additional setup required (GITHUB_TOKEN automatic)

### GitLab

- GitLab CI/CD enabled
- Pipeline variables configured
- Runner available

## Example: Complete Configuration

```yaml
# .sapiens/config.yaml
git_provider:
  provider_type: gitea
  base_url: "https://git.example.com"
  api_token: "@keyring:gitea/api_token"

repository:
  owner: myorg
  name: myrepo

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4-20250514

automation:
  mode:
    mode: hybrid
    native_enabled: true
    daemon_enabled: true
    daemon_fallback_only: true
    label_prefix: "sapiens/"

  label_triggers:
    "sapiens/triage":
      handler: triage
      ai_enabled: true
      remove_on_complete: true
      success_label: triaged

    "needs-planning":
      handler: proposal
      ai_enabled: true
      remove_on_complete: false
      success_label: plan-ready

    "execute":
      handler: task_execution
      ai_enabled: true
      remove_on_complete: true
      success_label: implemented

    "sapiens/review/security":
      handler: security_review
      ai_enabled: true
      remove_on_complete: true
      success_label: security-approved
      failure_label: security-concern

  schedule_triggers:
    - cron: "0 8 * * 1-5"
      handler: daily_triage
      ai_enabled: true
      task_prompt: "Triage all unlabeled issues opened in the last 24 hours"
```

## Troubleshooting

### Workflow Not Triggering

1. Check that the label matches a configured pattern
2. Verify the workflow file is in the correct location
3. Confirm the workflow file is on the default branch
4. Check CI/CD runner availability

### Handler Not Found

1. Verify the handler name is spelled correctly
2. Check that it matches a built-in handler or is meant for AI dispatch
3. Review logs in the workflow run output

### Label Not Removed After Success

1. Confirm `remove_on_complete: true` is set
2. Check that the API token has write permissions
3. Review workflow logs for API errors

### Secrets Not Available

For Gitea:
```bash
# Set repository secret
# Repository Settings > Actions > Secrets > Add Secret
# Name: SAPIENS_GITEA_TOKEN
# Value: <your-token>
```

For GitLab:
```bash
# Set CI/CD variable
# Settings > CI/CD > Variables > Add Variable
# Key: GITLAB_TOKEN
# Value: <your-token>
# Protected: Yes (if only used on protected branches)
```

## See Also

- [CI/CD Usage Guide](../ci-cd-usage.md)
- [Actions Configuration](../actions-configuration.md)
- [Getting Started](../GETTING_STARTED.md)
