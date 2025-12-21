# Quickstart Guide

Get the Gitea automation system up and running in 10 minutes.

## Prerequisites

- Python 3.11 or higher
- Git
- Access to a Gitea instance with Actions enabled
- Anthropic Claude API key (or Claude Code CLI)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://gitea.example.com/owner/builder.git
cd builder

# Run setup script
./scripts/setup.sh

# Or manual setup:
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Step 2: Configure Secrets

### For CI/CD (Gitea Actions)

1. Go to your repository in Gitea
2. Navigate to Settings → Secrets
3. Add two secrets:
   - `GITEA_TOKEN`: Your Gitea personal access token
   - `CLAUDE_API_KEY`: Your Anthropic API key

See [Secrets Setup Guide](secrets-setup.md) for detailed instructions.

### For Local Development

```bash
# Set environment variables
export GITEA_TOKEN="your-gitea-token"
export CLAUDE_API_KEY="your-claude-api-key"

# Or create .env file (don't commit!)
echo "GITEA_TOKEN=your-token" > .env
echo "CLAUDE_API_KEY=your-key" >> .env
```

## Step 3: Configure Settings

Edit `automation/config/automation_config.yaml`:

```yaml
git_provider:
  type: gitea
  base_url: https://your-gitea-instance.com
  api_token: ${GITEA_TOKEN}

repository:
  owner: your-username
  name: your-repo
  default_branch: main

agent_provider:
  type: claude
  model: claude-sonnet-4.5
  api_key: ${CLAUDE_API_KEY}
  local: false  # Set to true if using Claude Code CLI
```

## Step 4: Verify Setup

```bash
# Check configuration
automation --config automation/config/automation_config.yaml list-active-plans

# Run health check
automation health-check

# Run tests (if dev dependencies installed)
pytest tests/ -v
```

## Step 5: Create Your First Automated Workflow

### Via Gitea UI

1. Create a new issue in your repository
2. Title: "Add user authentication system"
3. Body: Describe what you want built
4. Add label: `needs-planning`
5. Wait for automation to trigger

The system will:
- Generate a development plan
- Create a plan review issue
- Once approved and merged, generate task issues
- Execute tasks automatically
- Review code
- Create a pull request

### Via CLI (Manual)

```bash
# Process a planning issue
automation process-issue --issue 42 --stage planning

# Generate prompts from a plan
automation generate-prompts --plan-file plans/42-feature.md --plan-id 42

# Check what's happening
automation list-active-plans
```

## Step 6: Monitor Progress

### Via Gitea Actions

1. Go to Actions tab in your repository
2. View running workflows
3. Check logs for any issues

### Via CLI

```bash
# List active plans
automation list-active-plans

# Check for stale workflows
automation check-stale --max-age-hours 24

# Check for failures
automation check-failures --since-hours 24

# Generate health report
automation health-check
```

## Workflow Labels

The system uses these labels to track workflow stages:

| Label | Stage | What Happens |
|-------|-------|--------------|
| `needs-planning` | Planning | AI generates development plan |
| `plan-review` | Review | Team reviews plan |
| `prompts` | Prompts | Generate task issues from plan |
| `implement` | Implementation | AI executes task |
| `code-review` | Review | AI reviews code changes |
| `merge-ready` | Merge | Create pull request |

## Common Commands

```bash
# List all CLI commands
automation --help

# Process specific issue
automation process-issue --issue 42 --stage planning

# Process all pending issues
automation process-all

# List active workflows
automation list-active-plans

# Check system health
automation health-check

# Check for stale workflows
automation check-stale --max-age-hours 24

# Check for failures
automation check-failures --since-hours 24
```

## Troubleshooting

### "Module not found" error

```bash
# Reinstall package
pip install -e .
```

### "Configuration file not found"

```bash
# Check file exists
ls automation/config/automation_config.yaml

# Use full path
automation --config /full/path/to/automation_config.yaml list-active-plans
```

### "Authentication failed"

```bash
# Verify tokens are set
echo $GITEA_TOKEN
echo $CLAUDE_API_KEY

# Check token permissions in Gitea
```

### Workflows don't trigger

1. Check Gitea Actions is enabled in repository
2. Verify workflow files exist in `.gitea/workflows/`
3. Check secrets are configured
4. Verify runner is active

## Next Steps

- Read [CI/CD Usage Guide](ci-cd-usage.md) for workflow details
- Review [Secrets Setup Guide](secrets-setup.md) for security
- Check [Workflow Diagram](workflow-diagram.md) for architecture
- Explore example plan in `plans/example-plan.md`

## Support

- Check the logs in `.automation/state/` for state information
- Review Gitea Actions logs for workflow issues
- Run `automation health-check` to diagnose problems
- Create an issue in the repository for bugs

## Example End-to-End Flow

```bash
# 1. Create issue via Gitea UI with "needs-planning" label
# 2. Automation triggers and generates plan

# 3. Check plan was created
ls plans/

# 4. Review plan in Gitea
# 5. Approve and merge plan to main
# 6. Automation generates task issues

# 7. Monitor progress
automation list-active-plans

# 8. Check specific plan state
cat .automation/state/42.json | jq .

# 9. Wait for tasks to complete
# 10. Pull request created automatically!
```

Happy automating!
