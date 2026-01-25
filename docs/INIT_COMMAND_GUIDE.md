# `sapiens init` Command Guide

Complete guide to using the `sapiens init` command for automated repository setup.

## Overview

The `init` command provides a streamlined, interactive way to set up repo-sapiens in your Git repository. It handles:

1. **Repository Discovery**: Auto-detects Git configuration (GitHub, Gitea, or GitLab)
2. **Credential Management**: Securely stores API tokens
3. **Configuration Generation**: Creates automation_config.yaml
4. **CI/CD Setup**: Guides you through setting up repository secrets (GitHub Actions, Gitea Actions, or GitLab CI/CD)

## Quick Start

```bash
# Navigate to your Git repository
cd /path/to/your/repo

# Run init (interactive)
sapiens init
```

## What Happens During Init

### 1. Repository Discovery

The command automatically detects:
- Git remote URL (origin, upstream, or first available)
- Repository owner and name (supports GitLab nested groups like `group/subgroup`)
- Provider base URL (GitHub, Gitea, or GitLab)
- Remote type (SSH or HTTPS)
- Provider type based on URL patterns

Example output (Gitea):
```
🔍 Discovering repository configuration...
   ✓ Found Git repository: /home/user/my-project
   ✓ Detected remote: origin
   ✓ Parsed: owner=myuser, repo=my-project
   ✓ Base URL: https://gitea.example.com
   ✓ Provider: gitea
```

Example output (GitLab):
```
🔍 Discovering repository configuration...
   ✓ Found Git repository: /home/user/my-project
   ✓ Detected remote: origin
   ✓ Parsed: owner=mygroup/subgroup, repo=my-project
   ✓ Base URL: https://gitlab.com
   ✓ Provider: gitlab
```

### 2. Credential Collection

**Interactive Mode** (default):
```
🔑 Setting up credentials...

Gitea API Token is required. Get it from:
   https://gitea.example.com/user/settings/applications

Enter your Gitea API token: ●●●●●●●●

Do you want to use Claude API or local Claude Code? [local/api]: local
```

**For GitLab** (interactive mode):
```
🔑 Setting up credentials...

GitLab Personal Access Token is required. Get it from:
   https://gitlab.com/-/user_settings/personal_access_tokens

Required scopes: api, read_repository, write_repository

Enter your GitLab token: ●●●●●●●●

Do you want to use Claude API or local Claude Code? [local/api]: local
```

**Non-Interactive Mode** (CI/CD):
```bash
# For Gitea
export SAPIENS_GITEA_TOKEN="your-token-here"
# For GitHub
export SAPIENS_GITHUB_TOKEN="your-token-here"
# For GitLab (note: GITLAB_ prefix is reserved by GitLab)
export SAPIENS_GITLAB_TOKEN="your-token-here"
export CLAUDE_API_KEY="your-key-here"  # optional
sapiens init --non-interactive
```

### 3. Credential Storage

Credentials are stored based on your environment:

**Workstation** (default: keyring):
```
📦 Storing credentials in keyring backend...
   ✓ Stored: gitea/api_token
   ✓ Credentials stored securely
```

**CI/CD** (environment variables):
```bash
sapiens init --backend environment
```

**Headless Server** (encrypted file):
```bash
export SAPIENS_MASTER_PASSWORD="secure-password"  # Legacy: SAPIENS_MASTER_PASSWORD also supported
sapiens init --backend encrypted
```

### 4. CI/CD Secrets

The command guides you through setting up repository secrets for your CI/CD platform:

**For Gitea Actions**:
```
🔐 Setting up Gitea Actions secrets...
   ℹ Please set SAPIENS_GITEA_TOKEN manually in Gitea UI for now
   Navigate to: https://gitea.example.com/myuser/my-project/settings/secrets
```

**For GitLab CI/CD**:
```
🔐 Setting up GitLab CI/CD variables...
   ℹ Please set SAPIENS_GITLAB_TOKEN manually in GitLab UI
   Navigate to: https://gitlab.com/mygroup/my-project/-/settings/ci_cd
   Expand "Variables" section and add your tokens
```

**What secrets to set**:

| Provider | Secret Name | Description |
|----------|-------------|-------------|
| Gitea | `SAPIENS_GITEA_TOKEN` | Gitea API token (required) |
| GitHub | `SAPIENS_GITHUB_TOKEN` | GitHub personal access token (often auto-provided) |
| GitLab | `SAPIENS_GITLAB_TOKEN` | GitLab personal access token with `api`, `read_repository`, `write_repository` scopes |
| All | `CLAUDE_API_KEY` or `SAPIENS_AI_API_KEY` | AI API key (only if using API mode)

> **Note for GitLab**: Use `SAPIENS_GITLAB_TOKEN`, not `GITLAB_TOKEN`. The `GITLAB_` prefix is reserved by GitLab for system variables.

**How to set them**:

**Gitea**:
1. Navigate to: `https://gitea.example.com/<owner>/<repo>/settings/secrets`
2. Click "Add Secret"
3. Add `SAPIENS_GITEA_TOKEN` and `CLAUDE_API_KEY`

**GitHub**:
1. Navigate to: `https://github.com/<owner>/<repo>/settings/secrets/actions`
2. Click "New repository secret"
3. Add `SAPIENS_GITHUB_TOKEN` (if not using the default) and `CLAUDE_API_KEY`

**GitLab**:
1. Navigate to: `https://gitlab.com/<namespace>/<project>/-/settings/ci_cd`
2. Expand "Variables" section
3. Click "Add variable"
4. Add `SAPIENS_GITLAB_TOKEN` and `SAPIENS_AI_API_KEY`
5. Recommended: Check "Mask variable" to hide values in job logs

**Why these secrets are needed**:

CI/CD workflows need these secrets to:
- Access the Git provider API to read issues, create PRs/MRs, etc.
- Call the Claude API for AI-powered code generation

The secrets are stored securely and are only accessible to workflow runs.

### 5. Configuration File Generation

A `automation_config.yaml` file is created based on the detected provider:

**Gitea Example**:
```yaml
# Automation System Configuration
# Generated by: sapiens init
# Repository: myuser/my-project

git_provider:
  provider_type: gitea
  mcp_server: gitea-mcp
  base_url: https://gitea.example.com
  api_token: "@keyring:gitea/api_token"  # Secure reference

repository:
  owner: myuser
  name: my-project
  default_branch: main

agent_provider:
  provider_type: claude-local  # or claude-api
  model: claude-sonnet-4.5
  api_key: null  # or @keyring:claude/api_key
  local_mode: true

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3
  review_approval_threshold: 0.8

tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
  in_progress: in-progress
  code_review: code-review
  merge_ready: merge-ready
  completed: completed
  needs_attention: needs-attention
```

**GitLab Example**:
```yaml
# Automation System Configuration
# Generated by: sapiens init
# Repository: mygroup/subgroup/my-project

git_provider:
  provider_type: gitlab
  base_url: https://gitlab.com
  api_token: "@keyring:gitlab/api_token"  # Uses PRIVATE-TOKEN header

repository:
  owner: mygroup/subgroup  # GitLab supports nested namespaces
  name: my-project
  default_branch: main

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4.5
  api_key: null
  local_mode: true

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3
  review_approval_threshold: 0.8

# Note: GitLab uses merge requests (MRs) instead of pull requests
# The automation handles this terminology difference automatically
```

### 6. Validation

The command validates that everything is set up correctly:

```
✓ Validating setup...
   ✓ Credentials validated
   ✓ Configuration file created

✅ Initialization complete!
```

## Command Options

### Basic Options

```bash
sapiens init [OPTIONS]
```

**`--repo-path DIRECTORY`**
- Path to Git repository
- Default: current directory
- Example: `sapiens init --repo-path /path/to/repo`

**`--config-path PATH`**
- Where to save configuration file
- Default: `.sapiens/config.yaml`
- Example: `sapiens init --config-path config/my_config.yaml`

**`--backend [keyring|environment|encrypted]`**
- Credential storage backend
- Auto-detected if not specified
- Example: `sapiens init --backend keyring`

**`--non-interactive`**
- Skip interactive prompts
- Requires `SAPIENS_GITEA_TOKEN` and optionally `CLAUDE_API_KEY` env vars
- Example: `sapiens init --non-interactive`

**`--setup-secrets` / `--no-setup-secrets`**
- Whether to set up Gitea Actions secrets
- Default: true
- Example: `sapiens init --no-setup-secrets`

## Usage Examples

### Example 1: Standard Interactive Setup

```bash
cd my-repo
sapiens init
```

Output:
```
🚀 Initializing repo-sapiens

🔍 Discovering repository configuration...
   ✓ Found Git repository: /home/user/my-repo
   ✓ Detected remote: origin
   ✓ Parsed: owner=myuser, repo=my-repo
   ✓ Base URL: https://gitea.example.com

🔑 Setting up credentials...

Gitea API Token is required. Get it from:
   https://gitea.example.com/user/settings/applications

Enter your Gitea API token: ●●●●●●●●●●●●

Do you want to use Claude API or local Claude Code? [local/api]: local

📦 Storing credentials in keyring backend...
   ✓ Stored: gitea/api_token
   ✓ Credentials stored securely

🔐 Setting up Gitea Actions secrets...
   ℹ Please set SAPIENS_GITEA_TOKEN manually in Gitea UI for now
   Navigate to: https://gitea.example.com/myuser/my-repo/settings/secrets

📝 Creating configuration file...
   ✓ Created: .sapiens/config.yaml

✓ Validating setup...
   ✓ Credentials validated
   ✓ Configuration file created

✅ Initialization complete!

📋 Next Steps:

1. Label an issue with 'needs-planning' in Gitea:
   https://gitea.example.com/myuser/my-repo/issues

2. Run the sapiens daemon:
   sapiens --config .sapiens/config.yaml daemon --interval 60

3. Watch the automation work!
```

### Example 2: CI/CD Non-Interactive Setup

```bash
# In your CI/CD pipeline
export SAPIENS_GITEA_TOKEN="${SECRETS_SAPIENS_GITEA_TOKEN}"
export CLAUDE_API_KEY="${SECRETS_CLAUDE_API_KEY}"

sapiens init --non-interactive --backend environment
```

### Example 3: Custom Config Location

```bash
sapiens init --config-path config/production.yaml
```

### Example 4: Skip Gitea Secrets Setup

```bash
# If you want to set up secrets manually later
sapiens init --no-setup-secrets
```

### Example 5: Force Keyring Backend

```bash
# Explicitly use keyring even if environment would work
sapiens init --backend keyring
```

### Example 6: GitLab Repository Setup

```bash
cd my-gitlab-project
sapiens init
```

Output:
```
🚀 Initializing repo-sapiens

🔍 Discovering repository configuration...
   ✓ Found Git repository: /home/user/my-gitlab-project
   ✓ Detected remote: origin
   ✓ Parsed: owner=mygroup/subgroup, repo=my-project
   ✓ Base URL: https://gitlab.com
   ✓ Provider: gitlab

🔑 Setting up credentials...

GitLab Personal Access Token is required. Get it from:
   https://gitlab.com/-/user_settings/personal_access_tokens

Required scopes: api, read_repository, write_repository

Enter your GitLab token: ●●●●●●●●●●●●

Do you want to use Claude API or local Claude Code? [local/api]: local

📦 Storing credentials in keyring backend...
   ✓ Stored: gitlab/api_token
   ✓ Credentials stored securely

🔐 Setting up GitLab CI/CD variables...
   ℹ Please set SAPIENS_GITLAB_TOKEN manually in GitLab UI
   Navigate to: https://gitlab.com/mygroup/subgroup/my-project/-/settings/ci_cd

📝 Creating configuration file...
   ✓ Created: .sapiens/config.yaml

✓ Validating setup...
   ✓ Credentials validated
   ✓ Configuration file created

✅ Initialization complete!

📋 Next Steps:

1. Label an issue with 'needs-planning' in GitLab:
   https://gitlab.com/mygroup/subgroup/my-project/-/issues

2. Run the sapiens daemon:
   sapiens --config .sapiens/config.yaml daemon --interval 60

3. Watch the automation create merge requests!
```

### Example 7: GitLab CI/CD Non-Interactive Setup

```bash
# In your .gitlab-ci.yml pipeline
export SAPIENS_GITLAB_TOKEN="${SAPIENS_GITLAB_TOKEN}"
export SAPIENS_AI_API_KEY="${SAPIENS_AI_API_KEY}"

sapiens init --non-interactive --backend environment
```

## CI/CD Secrets Setup (Detailed)

### Why Secrets Are Needed

CI/CD workflows run in isolated environments and need credentials to:

1. **Access Git Provider API** (`SAPIENS_GITEA_TOKEN` / `SAPIENS_GITHUB_TOKEN` / `SAPIENS_GITLAB_TOKEN`):
   - Read issues and comments
   - Create branches and pull/merge requests
   - Update issue labels and status
   - Post automation results

2. **Access Claude API** (`CLAUDE_API_KEY`):
   - Generate development plans
   - Implement code changes
   - Review pull/merge requests
   - Only needed if using `claude-api` mode

### Local vs CI/CD Credentials

**Local Development**:
- Credentials stored in OS keyring or encrypted file
- Used when you run `sapiens` commands locally
- Never committed to Git

**CI/CD**:
- Credentials stored as repository secrets/variables
- Injected as environment variables during workflow runs
- Accessible only to workflow runs, not to code

### Setting Secrets by Provider

#### Gitea

1. Navigate to: `https://gitea.example.com/<org>/<repo>/settings/secrets`
2. Click "Add Secret"
3. Add `SAPIENS_GITEA_TOKEN` with your API token
4. Add `CLAUDE_API_KEY` if using API mode

#### GitHub

1. Navigate to: `https://github.com/<org>/<repo>/settings/secrets/actions`
2. Click "New repository secret"
3. Add `SAPIENS_GITHUB_TOKEN` (if not using the default)
4. Add `CLAUDE_API_KEY` if using API mode

#### GitLab

1. Navigate to: `https://gitlab.com/<namespace>/<project>/-/settings/ci_cd`
2. Expand "Variables" section
3. Click "Add variable"
4. Add `SAPIENS_GITLAB_TOKEN`:
   - Key: `SAPIENS_GITLAB_TOKEN`
   - Value: Your personal access token
   - Check "Mask variable" to hide in logs
   - Required scopes: `api`, `read_repository`, `write_repository`

   > **Note**: Use `SAPIENS_GITLAB_TOKEN`, not `GITLAB_TOKEN`. The `GITLAB_` prefix is reserved by GitLab.
5. Add `CLAUDE_API_KEY` if using API mode

### Using Secrets in Workflows

Gitea Actions workflows access secrets via `${{ secrets.SECRET_NAME }}`:

```yaml
# .gitea/workflows/sapiens/automation-daemon.yaml
name: Automation Daemon

on:
  schedule:
    - cron: '*/5 * * * *'

jobs:
  process:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install repo-sapiens
        run: pip install repo-sapiens

      - name: Process Issues
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          sapiens --config .sapiens/config.yaml process-all
```

The workflow uses environment variable references in the config:

```yaml
# .sapiens/config.yaml
git_provider:
  api_token: ${SAPIENS_GITEA_TOKEN}  # Resolved from env var

agent_provider:
  api_key: ${CLAUDE_API_KEY}  # Resolved from env var
```

## Troubleshooting

### Error: Not a Git repository

```
Error: /path/to/dir is not a Git repository
```

**Solution**: Navigate to a directory with a `.git` folder or initialize Git:
```bash
cd /path/to/your/repo
# or
git init
git remote add origin git@gitea.example.com:owner/repo.git
```

### Error: No remotes configured

```
Error: No Git remotes found
```

**Solution**: Add a Git remote:
```bash
git remote add origin https://gitea.example.com/owner/repo.git
```

### Error: Keyring backend not available

```
Keyring backend: Not available
  Install with: pip install keyring
```

**Solution**: Install keyring or use environment backend:
```bash
pip install keyring
# or
sapiens init --backend environment
```

### Error: Failed to parse repository URL

```
Error: Failed to parse repository URL
```

**Solution**: Ensure your remote URL is valid:
```bash
# Check current remote
git remote -v

# Update if needed
git remote set-url origin git@gitea.example.com:owner/repo.git
```

### Credential Not Resolved

**Symptom**: Configuration file exists but credentials fail to resolve.

**Solution**: Verify credentials are stored:
```bash
# Test credential resolution
sapiens credentials get @keyring:gitea/api_token

# Re-store if needed
sapiens credentials set gitea/api_token --backend keyring
```

## Advanced Usage

### Custom Encrypted Backend Password

```bash
export SAPIENS_MASTER_PASSWORD="my-secure-password"  # Legacy: SAPIENS_MASTER_PASSWORD also supported
sapiens init --backend encrypted
```

### Multiple Repositories

Run `init` in each repository directory:

```bash
cd ~/projects/repo1
sapiens init --config-path config/repo1.yaml

cd ~/projects/repo2
sapiens init --config-path config/repo2.yaml
```

### Organization-Level Setup

For multiple repositories in the same organization:

```bash
# First repo (interactive)
cd ~/org/repo1
sapiens init

# Subsequent repos (reuse credentials)
cd ~/org/repo2
sapiens init  # Uses same keyring credentials

cd ~/org/repo3
sapiens init  # Uses same keyring credentials
```

## Next Steps After Init

1. **Label an issue** with `needs-planning`:
   ```
   https://gitea.example.com/<owner>/<repo>/issues
   ```

2. **Run the daemon**:
   ```bash
   sapiens daemon --interval 60
   ```

3. **Monitor progress**:
   ```bash
   sapiens list-plans
   sapiens show-plan --plan-id <id>
   ```

4. **Set up Gitea Actions workflows** (optional):
   - Copy example workflows from `.gitea/workflows/`
   - Customize as needed
   - Commit and push to repository

## Related Documentation

- [QUICK_START.md](../QUICK_START.md) - Quick setup guide
- [CREDENTIAL_QUICK_START.md](CREDENTIAL_QUICK_START.md) - Credential management
- [CI_CD_GUIDE.md](../CI_CD_GUIDE.md) - CI/CD integration
- [README.md](../README.md) - Full documentation

## Getting Help

```bash
# View init command help
sapiens init --help

# View credentials help
sapiens credentials --help

# General help
sapiens --help
```

For issues or questions:
- GitHub Issues: https://github.com/savorywatt/repo-sapiens/issues
- Documentation: Check the `docs/` directory
