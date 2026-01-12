# Secrets Setup Guide

This document describes how to configure secrets for the Gitea automation system in CI/CD environments.

## Required Secrets

The automation system requires two main secrets:

### 1. SAPIENS_GITEA_TOKEN

**Purpose:** Personal access token for Gitea API access

**Permissions Required:**
- `repo`: Full repository access
- `write:issue`: Create and update issues
- `write:pull_request`: Create pull requests

**How to Create:**

1. Go to your Gitea instance
2. Navigate to Settings → Applications → Generate New Token
3. Name: `Automation CI/CD Token`
4. Select required scopes: `repo`, `write:issue`, `write:pull_request`
5. Click "Generate Token"
6. Copy the token immediately (it won't be shown again)

### 2. CLAUDE_API_KEY

**Purpose:** Anthropic Claude API key for AI agent operations

**How to Obtain:**

1. Sign up at https://console.anthropic.com
2. Navigate to API Keys section
3. Create a new API key
4. Copy the key (starts with `sk-ant-`)

**Note:** If using Claude Code locally instead of API, this may not be required depending on your configuration.

## Setting Up Secrets in Gitea

### Via Gitea Web UI

1. Navigate to your repository
2. Go to Settings → Secrets
3. Click "Add Secret"
4. For each secret:
   - Name: `SAPIENS_GITEA_TOKEN` or `CLAUDE_API_KEY`
   - Value: Paste the token/key
   - Click "Add Secret"

### Via Gitea API

You can also add secrets programmatically:

```bash
# Set SAPIENS_GITEA_TOKEN secret
curl -X PUT "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/secrets/SAPIENS_GITEA_TOKEN" \
  -H "Authorization: token ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "data": "your-gitea-token-here"
  }'

# Set CLAUDE_API_KEY secret
curl -X PUT "https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/secrets/CLAUDE_API_KEY" \
  -H "Authorization: token ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "data": "your-claude-api-key-here"
  }'
```

## Environment Variable Mapping

The workflow files map secrets to environment variables:

```yaml
env:
  SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
  AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
  AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

The automation system reads configuration in this order:
1. Environment variables (highest priority)
2. Configuration YAML file
3. Default values (lowest priority)

## Security Best Practices

### Token Management

1. **Rotate Regularly**: Change tokens every 90 days
2. **Minimal Permissions**: Only grant required scopes
3. **Never Commit**: Never commit secrets to repository
4. **Audit Access**: Review secret access logs regularly

### Secret Storage

1. **Use Repository Secrets**: Store in Gitea's encrypted secret storage
2. **Avoid Logging**: Never log secret values
3. **Restrict Access**: Limit who can view/modify secrets

### API Key Protection

1. **Monitor Usage**: Check Anthropic dashboard for unexpected usage
2. **Set Limits**: Configure usage limits in Anthropic console
3. **Revoke if Compromised**: Immediately revoke and regenerate if exposed

## Verifying Secret Configuration

After setting up secrets, verify they're working:

```bash
# Trigger a workflow manually
# Check the workflow logs for:
# - Successful authentication
# - No "missing secret" errors
# - Proper API connectivity
```

## Troubleshooting

### "Missing SAPIENS_GITEA_TOKEN" Error

**Cause:** Secret not set or workflow doesn't have access

**Solution:**
1. Verify secret exists in repository settings
2. Check secret name matches exactly (case-sensitive)
3. Ensure workflow file references correct secret name

### "Authentication Failed" Error

**Cause:** Invalid or expired token

**Solution:**
1. Generate new token with correct permissions
2. Update secret in repository settings
3. Retry workflow

### "API Rate Limit" Error

**Cause:** Too many API calls

**Solution:**
1. Increase rate limit in Gitea settings
2. Reduce workflow frequency
3. Implement backoff/retry logic

## Local Development

For local development without CI/CD:

1. Create `.env` file (never commit):
   ```bash
   SAPIENS_GITEA_TOKEN=your-token-here
   CLAUDE_API_KEY=your-key-here
   ```

2. Export environment variables:
   ```bash
   export SAPIENS_GITEA_TOKEN="your-token"
   export CLAUDE_API_KEY="your-key"
   ```

3. Or modify `automation_config.yaml` (not recommended):
   ```yaml
   git_provider:
     api_token: your-token-here  # DON'T COMMIT THIS
   ```

## Additional Resources

- [Gitea Actions Documentation](https://docs.gitea.io/en-us/actions/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets) (similar concepts)
