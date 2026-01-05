# Deployment Guide - Gitea Actions Integration

This guide walks through deploying repo-sapiens to a Gitea repository with Actions enabled.

## Prerequisites

- Gitea instance with Actions enabled (Gitea v1.19+)
- Gitea runner configured and active
- Repository with admin access
- Git installed locally
- **AI Provider** (choose one):
  - **Ollama** (recommended for testing/development) - Self-hosted, free
  - **Claude API** (recommended for production) - Cloud-based, pay per use

## AI Provider Setup

### Option A: Ollama (Recommended for Testing)

Ollama provides free, local AI inference - perfect for development and testing.

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve

# Pull recommended models (in another terminal)
ollama pull qwen3:latest       # Default model, good balance
ollama pull codellama:13b      # Best for code tasks

# Verify installation
curl http://localhost:11434/api/tags
```

**For CI/CD runners**, ensure Ollama is accessible:
- Same machine: `http://localhost:11434`
- Network server: `http://ollama-server:11434`

### Option B: Claude API (Production)

For production workloads requiring highest quality:

1. Go to https://console.anthropic.com
2. Create account or login
3. Navigate to API Keys
4. Create new key (starts with `sk-ant-`)

## Deployment Steps

### 1. Push Code to Gitea

```bash
# Navigate to project directory
cd /path/to/repo-sapiens

# Verify git remote
git remote -v

# If remote not set:
git remote add origin https://gitea.example.com/your-username/repo-sapiens.git

# Push all code
git add .
git commit -m "Add Phase 3: Gitea Actions Integration"
git push -u origin main
```

### 2. Configure Repository Secrets

**Via Gitea Web UI:**

1. Navigate to your repository in Gitea
2. Go to **Settings** → **Secrets**
3. Click **Add Secret**

#### Required Secrets (All Setups)

**Secret: BUILDER_GITEA_TOKEN**
- Name: `BUILDER_GITEA_TOKEN`
- Value: Your Gitea personal access token
- How to create:
  1. User Settings → Applications → Generate New Token
  2. Name: "repo-sapiens CI/CD"
  3. Scopes: Select `repo`, `write:issue`, `write:pull_request`
  4. Click "Generate Token"
  5. Copy the token

**Secret: BUILDER_GITEA_URL**
- Name: `BUILDER_GITEA_URL`
- Value: Your Gitea instance URL (e.g., `https://gitea.example.com`)

#### For Claude API Setup (Production)

**Secret: BUILDER_CLAUDE_API_KEY**
- Name: `BUILDER_CLAUDE_API_KEY`
- Value: Your Anthropic Claude API key
- How to get:
  1. Go to https://console.anthropic.com
  2. Create account or login
  3. Navigate to API Keys
  4. Create new key
  5. Copy the key (starts with `sk-ant-`)

> **Note:** For local development with Ollama, you can use the ReAct agent directly:
> ```bash
> sapiens react --base-url http://localhost:11434 "your task"
> ```

### 3. Verify Gitea Actions

**Check Actions are enabled:**

1. Repository Settings → Actions
2. Ensure "Enable Actions for this repository" is checked
3. Check "Allow Actions to run workflow files"

**Verify runner is active:**

1. Repository → Actions tab
2. Should see "Runners" section
3. At least one runner should show "online"

If no runner:
```bash
# Install and configure Gitea runner
# See: https://docs.gitea.io/en-us/actions-setup/
```

### 4. Verify Workflows

Check that workflow files are present:

```bash
ls -la .gitea/workflows/
# Should show label-triggered workflows:
# - needs-planning.yaml     # Triggered when 'needs-planning' label added
# - needs-fix.yaml          # Triggered when 'needs-fix' label added
# - needs-review.yaml       # Triggered when 'needs-review' label added
# - requires-qa.yaml        # Triggered when 'requires-qa' label added
# - approved.yaml           # Triggered when 'approved' label added
# - execute-task.yaml       # General task execution
# - automation-daemon.yaml  # Scheduled polling
# - plan-merged.yaml        # Triggered on plan PR merge
# - monitor.yaml            # Health check workflow
# - test.yaml               # Test runner
# - build-artifacts.yaml    # Build and publish artifacts
```

### 5. Test the System

**Option 1: Create Test Issue**

1. Go to Issues tab
2. Click "New Issue"
3. Title: "Test automation system"
4. Body: "This is a test to verify the automation system works"
5. Click "Create Issue"
6. Add label: `needs-planning`
7. Go to Actions tab
8. Should see "Automation Trigger" workflow running
9. Check workflow logs for success

**Option 2: Trigger Manually**

1. Go to Actions tab
2. Select "Automation Daemon"
3. Click "Run workflow"
4. Select branch: main
5. Click "Run"
6. Monitor execution

### 6. Monitor Health

**Check workflow execution:**

```bash
# From local machine with configured environment
export AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token"
export AUTOMATION__GIT_PROVIDER__BASE_URL="https://gitea.example.com"

# List active plans
sapiens list-plans

# Show plan details
sapiens show-plan --plan-id <plan-id>
```

**View in Gitea:**

1. Actions tab shows all workflow runs
2. Click on any run to view logs
3. Download artifacts for debugging

### 7. Configure Webhook (Optional)

For real-time processing instead of cron-based:

1. Deploy webhook server:
   ```bash
   # On server
   uvicorn repo_sapiens.webhook_server:app --host 0.0.0.0 --port 8000

   # Or with systemd service
   sudo systemctl enable repo-sapiens-webhook
   sudo systemctl start repo-sapiens-webhook
   ```

2. Configure in Gitea:
   - Repository Settings → Webhooks
   - Click "Add Webhook" → Gitea
   - Payload URL: `https://your-server.com/webhook/gitea`
   - Content Type: `application/json`
   - Secret: (optional)
   - Events: Select "Issues" and "Push"
   - Active: Checked
   - Click "Add Webhook"

3. Test webhook:
   - Webhook Settings → "Test Delivery"
   - Check webhook server logs

## Verification Checklist

- [ ] Code pushed to Gitea
- [ ] Core secrets configured:
  - [ ] `BUILDER_GITEA_TOKEN` - Gitea API token
  - [ ] `BUILDER_GITEA_URL` - Gitea instance URL
  - [ ] `BUILDER_CLAUDE_API_KEY` - Claude API key (for production)
- [ ] Gitea Actions enabled
- [ ] Runner active and online
- [ ] Workflow files present in `.gitea/workflows/`
- [ ] Test issue created with `needs-planning` label
- [ ] Workflow triggered successfully
- [ ] Workflow logs show no errors
- [ ] `sapiens list-plans` runs successfully
- [ ] (Optional) Webhook configured and tested

## Troubleshooting

### Workflows Not Triggering

**Problem:** Workflow doesn't start when issue is labeled

**Solutions:**
1. Check Actions are enabled in repository settings
2. Verify workflow file syntax is correct
3. Check runner is online and has capacity
4. Review Gitea logs for errors
5. Manually trigger workflow to test

### Authentication Errors

**Problem:** "401 Unauthorized" in workflow logs

**Solutions:**
1. Verify `BUILDER_GITEA_TOKEN` secret is set correctly
2. Check token has correct scopes (`repo`, `write:issue`, `write:pull_request`)
3. Regenerate token if expired
4. Ensure secret name matches exactly (case-sensitive)

### Claude API Errors

**Problem:** "401 Unauthorized" or "Invalid API Key" from Claude

**Solutions:**
1. Verify `BUILDER_CLAUDE_API_KEY` secret is set correctly
2. Check API key starts with `sk-ant-`
3. Verify API key hasn't been revoked in Anthropic console
4. Check API usage limits haven't been exceeded

### Local Ollama Issues (Development)

**Problem:** "Ollama not running" or "Connection refused" errors

**Solutions:**
1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Ensure model is pulled: `ollama pull qwen3:latest`
3. For remote Ollama, check network/firewall settings

```bash
# Debug Ollama connectivity
curl http://localhost:11434/api/tags

# List available models
ollama list

# Pull default model
ollama pull qwen3:latest
```

### Ollama Out of Memory

**Problem:** Model fails to load or runs very slowly

**Solutions:**
1. Use smaller model: `qwen3:latest` instead of larger variants
2. Ensure sufficient RAM (model size + 2GB overhead)
3. Check GPU memory if using GPU acceleration
4. Close other applications using GPU memory

### Permission Errors

**Problem:** "403 Forbidden" when accessing API

**Solutions:**
1. Check token permissions
2. Verify repository access
3. Ensure runner has repository access
4. Check repository is not private (or runner has private repo access)

### Workflow Timeout

**Problem:** Workflow times out before completion

**Solutions:**
1. Increase timeout in workflow file:
   ```yaml
   jobs:
     job-name:
       timeout-minutes: 60  # Increase from default
   ```

2. Reduce max_concurrent_tasks in config
3. Optimize operations

### State File Conflicts

**Problem:** Multiple workflows conflict on state files

**Solutions:**
1. Workflows use file locking (already implemented)
2. Check for stale lock files
3. Reduce workflow concurrency

### Missing Dependencies

**Problem:** "Module not found" errors in workflow

**Solutions:**
1. Check pyproject.toml has all dependencies
2. Verify pip install step runs
3. Check caching is working
4. Add missing dependencies to pyproject.toml

## Production Best Practices

### Security

1. **Rotate secrets regularly:**
   - Every 90 days minimum
   - Immediately if compromised

2. **Use minimal permissions:**
   - `BUILDER_GITEA_TOKEN`: Only required scopes
   - Repository access: Only what's needed

3. **Monitor secret usage:**
   - Check Anthropic dashboard for API usage
   - Review Gitea token usage logs

4. **Enable audit logging:**
   - Gitea audit logs
   - Workflow run logs
   - State change logs

### Performance

1. **Optimize workflow frequency:**
   ```yaml
   # Reduce from every 5 minutes to every 15
   schedule:
     - cron: '*/15 * * * *'
   ```

2. **Use caching:**
   - Pip dependencies cached in workflows
   - State files cached locally

3. **Limit concurrency:**
   ```yaml
   # In config
   workflow:
     max_concurrent_tasks: 2  # Reduce if needed
   ```

4. **Monitor performance:**
   - Workflow execution times
   - API rate limits
   - Runner capacity

### Reliability

1. **Set up monitoring:**
   - Health check workflow every 6 hours
   - Alert on failures
   - Track metrics

2. **Backup state files:**
   - State artifacts uploaded every run
   - Regular backups of `.repo-sapiens/state/`

3. **Error recovery:**
   - Automatic retries configured
   - Manual recovery procedures documented

4. **Testing:**
   - Test workflow runs regularly
   - Verify edge cases
   - Keep test suite up to date

## Monitoring Dashboard

Create a simple dashboard to monitor automation:

```bash
# View active plans
sapiens list-plans

# Show specific plan details
sapiens show-plan --plan-id <plan-id>

# Check workflow runs in Gitea Actions tab
# or use the Gitea API to query workflow status
```

## Next Steps After Deployment

1. **Test with real issues:**
   - Create issues for actual work
   - Monitor execution
   - Verify outputs

2. **Tune configuration:**
   - Adjust concurrency
   - Optimize timeouts
   - Refine scheduling

3. **Expand documentation:**
   - Add team-specific guides
   - Document common issues
   - Create runbooks

4. **Gather feedback:**
   - Team usage patterns
   - Performance metrics
   - Feature requests

## Support

If issues persist:

1. Check documentation in `docs/`
2. Review workflow logs in Gitea Actions
3. Run local diagnostics with CLI
4. Create issue in repository
5. Contact team lead

## Maintenance

Regular maintenance tasks:

**Weekly:**
- Check health reports
- Review failure logs
- Verify runner capacity

**Monthly:**
- Rotate secrets
- Update dependencies
- Review and optimize

**Quarterly:**
- Performance audit
- Security review
- Documentation updates

---

**Deployment Complete!** The automation system is now ready for production use.
