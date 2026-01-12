# Example Recurring Task Workflows

These example workflows demonstrate how to use repo-sapiens for automated, recurring tasks in your repository. Each workflow is available for both **Gitea Actions** and **GitHub Actions**.

## Available Recipes

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `post-merge-docs.yaml` | On push to main | Reviews changes and updates documentation automatically |
| `weekly-test-coverage.yaml` | Mondays 9am UTC | Analyzes coverage and writes tests for under-covered code |
| `weekly-dependency-audit.yaml` | Wednesdays 10am UTC | Checks for outdated/vulnerable dependencies, creates update PRs |
| `weekly-security-review.yaml` | Fridays 2pm UTC | Runs security scans (Bandit, Semgrep, pip-audit) and auto-fixes vulnerabilities |
| `weekly-sbom-license.yaml` | Mondays 6am UTC | Generates SBOM, scans for CVEs, checks license compliance |
| `daily-issue-triage.yaml` | Daily 8am UTC | Labels and categorizes new issues, adds initial assessments |

## Quick Setup

### For Gitea

```bash
# Copy desired workflow to your repo
cp templates/workflows/gitea/recipes/weekly-test-coverage.yaml \
   .gitea/workflows/weekly-test-coverage.yaml

# Set required secrets in Gitea repo settings:
# - SAPIENS_GITEA_TOKEN
# - SAPIENS_CLAUDE_API_KEY
```

### For GitHub

```bash
# Copy desired workflow to your repo
cp templates/workflows/github/recipes/weekly-test-coverage.yaml \
   .github/workflows/weekly-test-coverage.yaml

# Set required secrets in GitHub repo settings:
# - ANTHROPIC_API_KEY
```

### For GitLab

```bash
# Copy desired workflow to your repo
cp templates/workflows/gitlab/recipes/weekly-test-coverage.yaml \
   .gitlab/workflows/weekly-test-coverage.yaml

# Set required secrets in GitLab repo settings (Settings > CI/CD > Variables):
# - SAPIENS_GITLAB_TOKEN
# - SAPIENS_CLAUDE_API_KEY
```

## Customization

### Changing Schedules

All scheduled workflows use cron syntax:

```yaml
on:
  schedule:
    - cron: '0 9 * * 1'  # Mondays at 9am UTC
```

Common patterns:
- `'0 9 * * 1'` - Weekly on Monday at 9am
- `'0 8 * * *'` - Daily at 8am
- `'0 0 1 * *'` - Monthly on the 1st
- `'*/30 * * * *'` - Every 30 minutes

### Customizing Task Prompts

Each workflow includes a `sapiens task` command with a task prompt. Modify the prompt to fit your project's needs:

```yaml
- name: Update documentation
  run: |
    sapiens task "YOUR CUSTOM PROMPT HERE

    Be specific about:
    - What files to check
    - What changes to make
    - Commit message format"
```

### Using Different AI Backends

The recipes use Claude by default. For Ollama:

```yaml
- name: Run task with Ollama
  run: |
    sapiens task --backend ollama --base-url http://localhost:11434 "Your task"
```

## Required Secrets

### Gitea

| Secret | Description |
|--------|-------------|
| `SAPIENS_GITEA_TOKEN` | Gitea API token with repo/issue/PR write access |
| `SAPIENS_CLAUDE_API_KEY` | Anthropic Claude API key |

### GitHub

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |

Note: GitHub Actions provides `GITHUB_TOKEN` automatically with appropriate permissions.

### GitLab

| Secret | Description |
|--------|-------------|
| `SAPIENS_GITLAB_TOKEN` | GitLab personal access token with `api` scope |
| `SAPIENS_CLAUDE_API_KEY` | Anthropic Claude API key |

Note: Configure these as CI/CD variables in Settings > CI/CD > Variables. Mark them as "Protected" and "Masked" for security.

## Tips

1. **Start with manual triggers** - All workflows include `workflow_dispatch` so you can test them manually before enabling schedules.

2. **Check the logs** - Review workflow run logs to see what the AI agent did and adjust prompts accordingly.

3. **Use skip patterns** - The doc update workflow checks for `[skip docs]` in commit messages to prevent loops.

4. **Adjust conservatism** - For critical repos, modify prompts to be more conservative (e.g., "only update patch versions").

5. **Monitor costs** - Scheduled workflows that use Claude API will incur costs. Adjust frequency as needed.

## Workflow Details

### Post-Merge Documentation

Triggers after every push to main. Reviews recent commits and:
- Updates README if features changed
- Adds CHANGELOG entries
- Fixes broken links
- Updates API docs

### Weekly Test Coverage

Runs coverage analysis and:
- Identifies lowest-covered modules
- Writes new unit tests
- Creates a PR with improvements
- Targets configurable coverage threshold

### Weekly Dependency Audit

Checks package health and:
- Lists outdated packages
- Runs security vulnerability scans
- Updates safe dependencies
- Creates PR with changes

### Weekly Security Review

Runs comprehensive security scans and:
- Bandit for Python security issues (SQL injection, command injection, etc.)
- pip-audit for dependency vulnerabilities
- Semgrep for multi-language static analysis
- Secret detection for hardcoded credentials
- Auto-fixes vulnerabilities where safe to do so
- Creates a PR with fixes or an issue with the report

### Weekly SBOM & License Compliance

Generates Software Bill of Materials and checks compliance:
- Creates SBOM in CycloneDX and SPDX formats using [Syft](https://github.com/anchore/syft)
- Scans for vulnerabilities using [Grype](https://github.com/anchore/grype)
- Analyzes licenses for copyleft/incompatible licenses
- Creates issues for critical vulnerabilities or license conflicts
- AI analyzes findings and prioritizes by actual risk
- Commits SBOM to `.sbom/` directory for tracking

Configure by setting:
- `PROJECT_LICENSE`: Your project's license (e.g., "MIT", "Apache-2.0")
- `DENY_LICENSES`: Comma-separated licenses to flag (e.g., "GPL-3.0,AGPL-3.0")

### Daily Issue Triage

Reviews new issues and:
- Adds appropriate labels (bug, enhancement, question)
- Assesses priority
- Adds initial comments for high-priority items
- Flags stale issues
