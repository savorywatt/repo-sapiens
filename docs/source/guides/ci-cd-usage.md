# CI/CD Usage Guide

This guide explains how to use repo-sapiens automation in CI/CD environments across GitHub Actions, Gitea Actions, and GitLab CI.

## Overview

The automation system provides workflows that run automatically in response to repository events:

1. **Needs Planning** - Processes issues labeled for planning
2. **Approved** - Handles approved plans
3. **Execute Task** - Runs task execution
4. **Needs Review** - Code review workflow
5. **Needs Fix** - Handles issues requiring fixes
6. **Requires QA** - QA workflow
7. **Automation Daemon** - Scheduled processing

## Configuration Files

### Local vs CI/CD Configuration

repo-sapiens uses different config files for local development vs CI/CD:

| File | Location | Purpose | Commit? |
|------|----------|---------|---------|
| `sapiens_config.yaml` | Project root | Local development config | ✅ Yes |
| `sapiens_config.ci.yaml` | Project root | CI/CD-specific config | ✅ Yes |
| `.sapiens/` | Project root | Runtime state/cache | ❌ No (add to .gitignore) |

**Why separate configs?**
- **Local**: Uses Ollama, local file paths, keyring credentials
- **CI/CD**: Uses API keys from secrets, remote backends, environment variables

**Example local config (`sapiens_config.yaml`):**
```yaml
git_provider:
  provider_type: gitea
  base_url: http://localhost:3000
  api_token: "@keyring:gitea/api_token"  # From OS keyring

agent_provider:
  provider_type: ollama
  model: qwen3:latest
  base_url: http://localhost:11434  # Local Ollama

workflow:
  state_directory: .sapiens/state
```

**Example CI/CD config (`sapiens_config.ci.yaml`):**
```yaml
git_provider:
  provider_type: gitea
  base_url: ${GITEA_BASE_URL}
  api_token: ${SAPIENS_GITEA_TOKEN}  # From CI secrets

agent_provider:
  provider_type: claude-api
  model: claude-sonnet-4-5
  api_key: ${CLAUDE_API_KEY}  # From CI secrets

workflow:
  state_directory: .sapiens/state
```

## Workflow Templates

### Directory Structure by Platform

**Gitea Actions:**
```
.gitea/workflows/
└── sapiens/
    ├── needs-planning.yaml
    ├── approved.yaml
    ├── execute-task.yaml
    ├── needs-review.yaml
    ├── needs-fix.yaml
    ├── requires-qa.yaml
    ├── automation-daemon.yaml
    ├── process-issue.yaml
    ├── process-label.yaml
    ├── prompts/              # Custom system prompts
    │   ├── needs-planning.md
    │   ├── approved.md
    │   └── ...
    └── recipes/              # Optional workflows
        ├── daily-issue-triage.yaml
        └── ...
```

**GitHub Actions:**
```
.github/workflows/
└── sapiens/
    ├── needs-planning.yaml
    ├── approved.yaml
    ├── execute-task.yaml
    ├── needs-review.yaml
    ├── needs-fix.yaml
    ├── requires-qa.yaml
    ├── automation-daemon.yaml
    ├── process-issue.yaml
    ├── prompts/              # Custom system prompts
    └── recipes/              # Optional workflows
```

**GitLab CI:**
```
.gitlab-ci.yml               # Main pipeline file
.gitlab/
└── sapiens/
    ├── prompts/             # Custom system prompts
    │   ├── needs-planning.md
    │   └── ...
    └── recipes/             # Included pipeline jobs
        ├── daily-issue-triage.yaml
        └── ...
```

### System Prompts

All workflows support custom system prompts to guide AI behavior:

**Location:** `.{gitea,github}/workflows/sapiens/prompts/`

**Usage in workflows:**
```yaml
- name: Process issue
  run: |
    sapiens --config sapiens_config.ci.yaml \
      process-issue --issue ${{ issue.number }} \
      --system-prompt .gitea/workflows/sapiens/prompts/needs-planning.md
```

**Example prompt (`prompts/needs-planning.md`):**
```markdown
You are a senior software architect creating a development plan.

## Your Task
Analyze the issue and create a detailed, actionable development plan.

## Guidelines
- Break down into 3-10 discrete tasks
- Each task should be independently testable
- Include testing requirements
- Consider edge cases
- Specify acceptance criteria

## Output Format
Generate a markdown plan with:
1. Overview
2. Tasks (numbered, with descriptions)
3. Dependencies
4. Testing strategy
```

## Platform-Specific Workflows

### Gitea Actions

**Trigger:** Issue labeled with `needs-planning`

**Workflow:** `.gitea/workflows/sapiens/needs-planning.yaml`

```yaml
name: Needs Planning

on:
  issues:
    types: [labeled]

jobs:
  create-plan:
    name: Create Development Plan
    if: gitea.event.label.name == 'needs-planning'
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install sapiens
        run: pip install repo-sapiens

      - name: Create plan proposal
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ gitea.server_url }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ gitea.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ gitea.event.repository.name }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
        run: |
          sapiens --config sapiens_config.ci.yaml \
            process-issue --issue ${{ gitea.event.issue.number }} \
            --system-prompt .gitea/workflows/sapiens/prompts/needs-planning.md
```

**Required Secrets (Gitea):**
- `SAPIENS_GITEA_TOKEN` - Gitea API token (note: Gitea reserves `GITEA_*` prefix)
- `SAPIENS_CLAUDE_API_KEY` - AI provider API key

### GitHub Actions

**Trigger:** Issue labeled with `needs-planning`

**Workflow:** `.github/workflows/sapiens/needs-planning.yaml`

```yaml
name: Needs Planning

on:
  issues:
    types: [labeled]

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  create-plan:
    name: Create Development Plan
    if: github.event.label.name == 'needs-planning'
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install sapiens
        run: pip install repo-sapiens

      - name: Create plan proposal
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: https://github.com
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ github.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ github.event.repository.name }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          sapiens --config sapiens_config.ci.yaml \
            process-issue --issue ${{ github.event.issue.number }} \
            --system-prompt .github/workflows/sapiens/prompts/needs-planning.md
```

**Required Secrets (GitHub):**
- `SAPIENS_GITHUB_TOKEN` - Automatically provided by GitHub Actions
- `CLAUDE_API_KEY` - AI provider API key (set in repository secrets)

### GitLab CI

**Note:** GitLab doesn't have native label event triggers like GitHub/Gitea. repo-sapiens supports two automation modes:

1. **Daemon mode** (recommended): Scheduled pipeline polls for labeled issues
2. **Webhook mode**: External webhook handler triggers pipelines instantly

**Pipeline:** `.gitlab-ci.yml`

```yaml
variables:
  CONFIG_FILE: sapiens_config.ci.yaml
  PYTHON_VERSION: "3.12"

stages:
  - process

# Daemon mode: Scan for labeled issues (scheduled)
sapiens-daemon:
  stage: process
  image: python:${PYTHON_VERSION}-slim
  timeout: 45 minutes
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
  variables:
    AUTOMATION__GIT_PROVIDER__API_TOKEN: $SAPIENS_GITLAB_TOKEN
    AUTOMATION__AGENT_PROVIDER__API_KEY: $SAPIENS_AI_API_KEY
  before_script:
    - pip install repo-sapiens==0.5.1
  script:
    - sapiens process-all --log-level INFO

# Process a specific issue (triggered manually or via webhook)
process-issue:
  stage: process
  image: python:${PYTHON_VERSION}-slim
  timeout: 30 minutes
  rules:
    - if: $ISSUE_NUMBER != ""
  variables:
    AUTOMATION__GIT_PROVIDER__API_TOKEN: $SAPIENS_GITLAB_TOKEN
  before_script:
    - pip install repo-sapiens==0.5.1
  script:
    - |
      sapiens --config $CONFIG_FILE \
        process-issue --issue $ISSUE_NUMBER \
        --system-prompt .gitlab/sapiens/prompts/needs-planning.md
```

**Required CI/CD Variables (GitLab):**
- `SAPIENS_GITLAB_TOKEN` - GitLab Personal Access Token
- `SAPIENS_AI_API_KEY` - AI provider API key

> **Note**: Use `SAPIENS_GITLAB_TOKEN`, not `GITLAB_TOKEN`. The `GITLAB_` prefix is reserved by GitLab for system variables.

**GitLab-specific notes:**
- Uses merge requests (MRs) instead of pull requests
- Uses `PRIVATE-TOKEN` header for API authentication
- Required token scopes: `api`, `read_repository`, `write_repository`

## Label to Workflow Mapping

| Label | Workflow | Action |
|-------|----------|--------|
| `needs-planning` | needs-planning.yaml | Generate development plan |
| `approved` | approved.yaml | Execute approved plan |
| `needs-review` | needs-review.yaml | Review code changes |
| `needs-fix` | needs-fix.yaml | Handle fix requests |
| `requires-qa` | requires-qa.yaml | Run QA checks |
| `execute` | execute-task.yaml | Execute task implementation |

## Environment Variables

### Required Secrets/Variables

**Gitea:**
- `SAPIENS_GITEA_TOKEN` - API token (Gitea reserves `GITEA_*` prefix)
- `SAPIENS_CLAUDE_API_KEY` - AI provider key

**GitHub:**
- `SAPIENS_GITHUB_TOKEN` - Automatically provided
- `CLAUDE_API_KEY` - AI provider key

**GitLab:**
- `SAPIENS_GITLAB_TOKEN` - Personal Access Token (note: `GITLAB_` prefix is reserved)
- `SAPIENS_AI_API_KEY` - AI provider key

### Configuration Override

Use `AUTOMATION__*` prefix to override config values:

```yaml
env:
  AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ server_url }}
  AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.TOKEN }}
  AUTOMATION__REPOSITORY__OWNER: ${{ repository_owner }}
  AUTOMATION__REPOSITORY__NAME: ${{ repository_name }}
  AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.API_KEY }}
```

## Monitoring Workflows

### View Workflow Runs

**Gitea:** Navigate to repository → Actions tab
**GitHub:** Navigate to repository → Actions tab
**GitLab:** Navigate to CI/CD → Pipelines

### Debug Failed Workflows

1. View workflow/pipeline run logs
2. Look for error messages
3. Check state artifacts (if uploaded)
4. Review secret/variable configuration
5. Verify token permissions

### Common Issues

**Workflow doesn't trigger:**
- Check trigger conditions in YAML
- Verify Actions/CI is enabled
- Check runner availability
- For GitLab: Ensure pipeline trigger is configured

**Permission denied:**
- Verify token has correct scopes
- Check repository permissions
- Ensure runner has access

**Timeout:**
- Increase timeout in workflow file
- Reduce concurrent tasks
- Optimize operations

## Best Practices

### Workflow Management

1. **Use workflow_dispatch/manual triggers**: Allow manual triggering for debugging
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
2. **Use secrets/variables**: Store tokens encrypted
3. **Restrict access**: Limit who can trigger workflows
4. **Audit regularly**: Review workflow runs and permissions

## Troubleshooting

### Check Logs

**Gitea/GitHub:**
```bash
# View recent workflow runs via API
curl "https://api.github.com/repos/{owner}/{repo}/actions/runs" \
  -H "Authorization: token ${SAPIENS_GITHUB_TOKEN}"
```

**GitLab:**
```bash
# View pipeline jobs
curl --header "PRIVATE-TOKEN: ${SAPIENS_GITLAB_TOKEN}" \
  "${CI_API_V4_URL}/projects/${PROJECT_ID}/pipelines"
```

### Manual Execution

Test commands locally:

```bash
# Set up environment
export SAPIENS_GITEA_TOKEN="your-token"
export CLAUDE_API_KEY="your-key"

# Run command
sapiens --config sapiens_config.ci.yaml process-issue --issue 42
```

### State Inspection

Check workflow state:

```bash
# View state files
ls -la .sapiens/state/

# Read state
cat .sapiens/state/42.json
```

## Additional Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [GitHub Actions Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [repo-sapiens README](../README.md)
