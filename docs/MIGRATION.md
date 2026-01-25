# Migrating from Template Workflows to Reusable Workflows

This guide helps you migrate from the old template-based workflow approach to the new reusable workflow approach.

---

## What Changed

### Before (Template Approach)

Previously, repo-sapiens required copying multiple workflow files to your repository:

```
.github/workflows/sapiens/
├── needs-planning.yaml    (80 lines)
├── approved.yaml          (60 lines)
├── execute-task.yaml      (70 lines)
├── needs-review.yaml      (65 lines)
├── needs-fix.yaml         (55 lines)
├── requires-qa.yaml       (90 lines)
└── process-label.yaml     (70 lines)

Total: ~490 lines of YAML across 7 files
```

Each file contained the full workflow logic, which meant:
- Updates required manually updating all files
- Configuration was duplicated across files
- Customization was error-prone

### After (Reusable Workflow Approach)

Now, you create a single thin wrapper:

```
.github/workflows/sapiens.yaml   (20 lines)
```

This wrapper references the official dispatcher workflow, which:
- Handles all label routing internally
- Gets automatic updates when you bump the version tag
- Centralizes configuration in one place

**96% reduction in boilerplate.**

---

## Why Migrate?

| Benefit | Description |
|---------|-------------|
| Less maintenance | Single file to maintain instead of 7+ |
| Automatic updates | Bump version tag (e.g., `@v0.5.1`) to get new features |
| Consistency | Same workflow logic across all your repositories |
| Easier debugging | One workflow, one set of logs |
| Simpler configuration | All settings in one place |

---

## Migration Steps

### Step 1: Delete Old Workflow Files

Remove the old template workflows from your repository:

**For GitHub:**
```bash
rm -rf .github/workflows/sapiens/
# or if workflows were at root level:
rm -f .github/workflows/needs-planning.yaml
rm -f .github/workflows/approved.yaml
rm -f .github/workflows/execute-task.yaml
rm -f .github/workflows/needs-review.yaml
rm -f .github/workflows/needs-fix.yaml
rm -f .github/workflows/requires-qa.yaml
rm -f .github/workflows/process-label.yaml
```

**For Gitea:**
```bash
rm -rf .gitea/workflows/sapiens/
# or if workflows were at root level:
rm -f .gitea/workflows/needs-planning.yaml
rm -f .gitea/workflows/approved.yaml
rm -f .gitea/workflows/execute-task.yaml
rm -f .gitea/workflows/needs-review.yaml
rm -f .gitea/workflows/needs-fix.yaml
rm -f .gitea/workflows/requires-qa.yaml
rm -f .gitea/workflows/process-label.yaml
```

### Step 2: Create the New Wrapper Workflow

Create a single workflow file:

**For GitHub (`.github/workflows/sapiens.yaml`):**
```yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
```

**For Gitea (`.gitea/workflows/sapiens.yaml`):**
```yaml
name: Sapiens

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: gitea
      git_provider_url: https://gitea.example.com  # Your Gitea URL
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
```

### Step 3: Verify Secrets

Your existing secrets should work with minimal changes:

| Old Secret | New Secret Mapping | Notes |
|------------|-------------------|-------|
| `SAPIENS_GITHUB_TOKEN` | Maps to `GIT_TOKEN` | No change needed |
| `SAPIENS_GITEA_TOKEN` | Maps to `GIT_TOKEN` | No change needed |
| `SAPIENS_AI_API_KEY` | Maps to `AI_API_KEY` | No change needed |
| `SAPIENS_CLAUDE_API_KEY` | Maps to `AI_API_KEY` | Rename if desired |
| `OPENROUTER_API_KEY` | Maps to `AI_API_KEY` | Use whichever name you prefer |

The secrets mapping in the workflow handles the translation:
```yaml
secrets:
  GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}  # Your existing secret name
  AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}   # Your existing secret name
```

### Step 4: Commit and Push

```bash
git add -A
git commit -m "chore: Migrate to reusable sapiens workflow"
git push
```

### Step 5: Test

1. Go to your repository
2. Create or open an existing issue
3. Add the `needs-planning` label
4. Check the Actions tab to verify the workflow runs

---

## What Stays the Same

The following do **not** need to change:

- **Labels**: Same label names (`needs-planning`, `approved`, etc.)
- **Repository settings**: No changes needed
- **Issue/PR structure**: Works exactly as before
- **Automation flow**: Same stages and transitions
- **Local configuration**: `.sapiens/config.yaml` remains unchanged

---

## Configuration Mapping

If you had custom environment variables in your old workflows, here's how to migrate them:

### Old: Environment Variables in Workflow

```yaml
# Old approach - in each workflow file
env:
  AUTOMATION__GIT_PROVIDER__PROVIDER_TYPE: github
  AUTOMATION__GIT_PROVIDER__BASE_URL: https://api.github.com
  AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: openai-compatible
  AUTOMATION__AGENT_PROVIDER__BASE_URL: https://openrouter.ai/api/v1
  AUTOMATION__AGENT_PROVIDER__MODEL: anthropic/claude-3.5-sonnet
```

### New: Workflow Inputs

```yaml
# New approach - in the wrapper workflow
with:
  git_provider_type: github                      # Was AUTOMATION__GIT_PROVIDER__PROVIDER_TYPE
  git_provider_url: https://api.github.com       # Was AUTOMATION__GIT_PROVIDER__BASE_URL
  ai_provider_type: openai-compatible            # Was AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE
  ai_base_url: https://openrouter.ai/api/v1      # Was AUTOMATION__AGENT_PROVIDER__BASE_URL
  ai_model: anthropic/claude-3.5-sonnet          # Was AUTOMATION__AGENT_PROVIDER__MODEL
```

---

## Troubleshooting Migration

### Workflow not triggering after migration

1. Verify old workflow files are deleted
2. Ensure new `sapiens.yaml` is in the correct location
3. Check the workflow file was pushed to your default branch
4. Verify Actions is enabled for your repository

### "Workflow does not exist" error

1. Ensure you're using the correct workflow reference:
   ```yaml
   uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
   ```
2. For private repos: check if you have access to the repo-sapiens repository

### Old and new workflows both running

You likely have both old and new workflow files. Delete the old ones:
```bash
rm -rf .github/workflows/sapiens/
git add -A && git commit -m "Remove old workflow files" && git push
```

### Different behavior after migration

The reusable workflow should behave identically. If you notice differences:
1. Check the workflow inputs match your previous environment variables
2. Review the [WORKFLOW_REFERENCE.md](WORKFLOW_REFERENCE.md) for input details
3. Open an issue if you find a bug

---

## Rolling Back

If you need to revert to the old approach temporarily:

1. Delete the new wrapper: `rm .github/workflows/sapiens.yaml`
2. Restore old workflows from git history or re-copy from templates
3. Push the changes

However, we recommend reporting any issues rather than rolling back, as the template approach will be deprecated in future versions.

---

## Getting Help

- **Documentation**: See [WORKFLOW_REFERENCE.md](WORKFLOW_REFERENCE.md) for complete input reference
- **Issues**: Report problems at https://github.com/savorywatt/repo-sapiens/issues
- **Examples**: See the setup guides for complete examples:
  - [GITHUB_OPENROUTER_SETUP.md](GITHUB_OPENROUTER_SETUP.md)
  - [GITEA_NEW_REPO_TUTORIAL.md](GITEA_NEW_REPO_TUTORIAL.md)
  - [GITLAB_SETUP.md](GITLAB_SETUP.md)
