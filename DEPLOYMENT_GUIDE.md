# Deployment Guide - Gitea Actions Integration

This guide walks through deploying the automation system to a Gitea repository with Actions enabled.

## Prerequisites

- Gitea instance with Actions enabled (Gitea v1.19+)
- Gitea runner configured and active
- Repository with admin access
- Anthropic Claude API key
- Git installed locally

## Deployment Steps

### 1. Push Code to Gitea

```bash
# Navigate to project directory
cd /home/ross/Workspace/builder

# Verify git remote
git remote -v

# If remote not set:
git remote add origin https://gitea.example.com/your-username/builder.git

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

Add these secrets:

**Secret 1: GITEA_TOKEN**
- Name: `GITEA_TOKEN`
- Value: Your Gitea personal access token
- How to create:
  1. User Settings → Applications → Generate New Token
  2. Name: "Automation CI/CD"
  3. Scopes: Select `repo`, `write:issue`, `write:pull_request`
  4. Click "Generate Token"
  5. Copy the token

**Secret 2: CLAUDE_API_KEY**
- Name: `CLAUDE_API_KEY`
- Value: Your Anthropic Claude API key
- How to get:
  1. Go to https://console.anthropic.com
  2. Create account or login
  3. Navigate to API Keys
  4. Create new key
  5. Copy the key (starts with `sk-ant-`)

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
# Should show:
# - automation-trigger.yaml
# - plan-merged.yaml
# - automation-daemon.yaml
# - monitor.yaml
# - test.yaml
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
# From local machine with configured tokens
export GITEA_TOKEN="your-token"
export CLAUDE_API_KEY="your-key"

# Run health check
automation health-check

# List active plans
automation list-active-plans
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
   uvicorn automation.webhook_server:app --host 0.0.0.0 --port 8000
   
   # Or with systemd service
   sudo systemctl enable automation-webhook
   sudo systemctl start automation-webhook
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
- [ ] Secrets configured (GITEA_TOKEN, CLAUDE_API_KEY)
- [ ] Gitea Actions enabled
- [ ] Runner active and online
- [ ] Workflow files present in `.gitea/workflows/`
- [ ] Test issue created with label
- [ ] Workflow triggered successfully
- [ ] Workflow logs show no errors
- [ ] Health check passes
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
1. Verify GITEA_TOKEN secret is set
2. Check token has correct scopes
3. Regenerate token if expired
4. Ensure secret name matches exactly (case-sensitive)

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
   - GITEA_TOKEN: Only required scopes
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
   - Regular backups of `.automation/state/`

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
# View recent activity
automation list-active-plans

# Check for issues
automation check-stale --max-age-hours 12
automation check-failures --since-hours 24

# Generate report
automation health-check > /tmp/health.txt
cat /tmp/health.txt
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
