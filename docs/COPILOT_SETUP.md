# GitHub Copilot Setup Guide

> ⚠️ **IMPORTANT DISCLAIMER**
>
> GitHub Copilot integration uses **unofficial, reverse-engineered APIs**. By using this:
>
> - You acknowledge this is **NOT endorsed by GitHub**
> - You understand it may **violate GitHub ToS**
> - You accept it could **break at any time**
> - You use it **at your own risk**
>
> For production use, consider official providers like Claude API or OpenAI API.

## Two Approaches

| Approach | Use Case | Provider Type | Requires |
|----------|----------|---------------|----------|
| [Direct API](#direct-api-for-cicd) | CI/CD, headless | `openai-compatible` | OAuth token from IDE |
| [copilot-api Proxy](#copilot-api-proxy-for-local-dev) | Local development | `copilot-local` | Node.js, interactive auth |

---

## Direct API (for CI/CD)

GitHub Copilot exposes an OpenAI-compatible endpoint at `https://api.githubcopilot.com`. This works in CI/CD environments without interactive authentication.

### Prerequisites

1. **GitHub Copilot subscription** (Individual, Business, or Enterprise)
2. **OAuth token** extracted from an IDE (one-time local setup)

### Step 1: Get OAuth Token (One-Time)

Authenticate via a JetBrains IDE (PyCharm, GoLand, etc.) or VS Code with the Copilot extension, then extract the token:

```bash
# macOS/Linux
cat ~/.config/github-copilot/apps.json | jq -r '.[].oauth_token'

# Windows PowerShell
Get-Content "$env:LOCALAPPDATA\github-copilot\apps.json" | ConvertFrom-Json | Select-Object -ExpandProperty oauth_token
```

> **Note:** Tokens from Neovim's copilot.lua may lack required scopes. Use a JetBrains IDE if you see "access forbidden" errors.

### Step 2: Store Token in CI/CD

Add the token as a CI/CD secret:

- **GitLab:** Settings → CI/CD → Variables → `COPILOT_OAUTH_TOKEN`
- **GitHub Actions:** Settings → Secrets → `COPILOT_OAUTH_TOKEN`

### Step 3: Configure Sapiens

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: openai-compatible
  base_url: "https://api.githubcopilot.com"
  model: "gpt-4o"
  api_key: "@env:COPILOT_OAUTH_TOKEN"
```

### GitLab CI Example

```yaml
# .gitlab-ci.yml
variables:
  AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: "openai-compatible"
  AUTOMATION__AGENT_PROVIDER__BASE_URL: "https://api.githubcopilot.com"
  AUTOMATION__AGENT_PROVIDER__MODEL: "gpt-4o"

sapiens:
  stage: automation
  script:
    - pip install repo-sapiens
    - sapiens process-label --label "$SAPIENS_LABEL" --issue "$SAPIENS_ISSUE" --source gitlab
  variables:
    AUTOMATION__AGENT_PROVIDER__API_KEY: $COPILOT_OAUTH_TOKEN
```

### GitHub Actions Example

```yaml
# .github/workflows/sapiens.yaml
jobs:
  sapiens:
    runs-on: ubuntu-latest
    env:
      AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: openai-compatible
      AUTOMATION__AGENT_PROVIDER__BASE_URL: https://api.githubcopilot.com
      AUTOMATION__AGENT_PROVIDER__MODEL: gpt-4o
      AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.COPILOT_OAUTH_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - run: pip install repo-sapiens
      - run: sapiens process-label --label "${{ github.event.label.name }}" --issue "${{ github.event.issue.number }}"
```

### Available Models

Query available models with your token:

```bash
curl -s https://api.githubcopilot.com/models \
  -H "Authorization: Bearer $COPILOT_OAUTH_TOKEN" \
  -H "Copilot-Integration-Id: vscode-chat" | jq -r '.data[].id'
```

Common models: `gpt-4o`, `gpt-4o-mini`, `claude-3.7-sonnet-thought`, `gemini-2.5-pro`

### Using with Goose

Goose also supports OpenAI-compatible backends:

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: goose-local
  model: "gpt-4o"
  base_url: "https://api.githubcopilot.com"
  api_key: "@env:COPILOT_OAUTH_TOKEN"
```

---

## copilot-api Proxy (for Local Dev)

For local development, the [`copilot-api`](https://github.com/ericc-ch/copilot-api) proxy provides a simpler setup with device-flow authentication.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Sapiens   │────▶│  copilot-api │────▶│  GitHub Copilot │
│             │     │    proxy     │     │      API        │
└─────────────┘     └──────────────┘     └─────────────────┘
```

### Prerequisites

1. **GitHub Copilot subscription**
2. **Node.js 18+** and npm

### Quick Start

```bash
# 1. Start the proxy (will prompt for device auth)
npx copilot-api@latest --port 4141

# 2. Follow the device auth prompt in your browser
#    Visit https://github.com/login/device and enter the code

# 3. Configure sapiens to use external proxy
cat > .sapiens/config.yaml << 'EOF'
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  copilot_config:
    github_token: "unused"  # Device flow doesn't use this
    manage_proxy: false
    proxy_url: "http://localhost:4141/v1"
    rate_limit: 2.0
EOF

# 4. Verify
sapiens health-check
```

### Managed Proxy Mode

Sapiens can auto-start the proxy, but this requires completing device auth each time:

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  copilot_config:
    github_token: "@keyring:github/copilot_token"
    manage_proxy: true
    proxy_port: 4141
    startup_timeout: 30.0
    rate_limit: 2.0
```

### Rate Limiting

GitHub aggressively rate-limits Copilot API usage. Always configure rate limiting:

```yaml
copilot_config:
  rate_limit: 2.0  # Minimum 2 seconds between requests
```

---

## Troubleshooting

### "Access to this endpoint is forbidden"

Your OAuth token may lack required scopes. Regenerate by:
1. Sign out of Copilot in your IDE
2. Delete `~/.config/github-copilot/apps.json`
3. Re-authenticate via a JetBrains IDE (not Neovim)

### "Rate limit exceeded" / "Abuse detected"

Increase the delay between requests:
```yaml
copilot_config:
  rate_limit: 5.0
```

Or for direct API:
```yaml
agent_provider:
  # Add custom timeout/retry logic in your workflow
```

### "npx not found" (proxy mode only)

Install Node.js:
```bash
# macOS
brew install node

# Ubuntu
sudo apt install nodejs npm
```

### Token Expiration

OAuth tokens may expire. If requests start failing:
1. Re-authenticate in your IDE
2. Extract the new token from `apps.json`
3. Update your CI/CD secret

---

## Comparison

| Aspect | Direct API | copilot-api Proxy |
|--------|------------|-------------------|
| CI/CD compatible | ✅ Yes | ❌ No (interactive auth) |
| Local dev | ✅ Yes | ✅ Yes |
| Setup complexity | Medium (token extraction) | Low (device flow) |
| Node.js required | No | Yes |
| Provider type | `openai-compatible` | `copilot-local` |
| Model selection | Many (GPT-4o, Claude, etc.) | gpt-4 only |

---

## See Also

- [AGENT_COMPARISON.md](./AGENT_COMPARISON.md) - Compare all agent providers
- [CREDENTIALS.md](./CREDENTIALS.md) - Credential storage options
- [Aider Copilot Docs](https://aider.chat/docs/llms/github.html) - Community documentation
- [copilot-api GitHub](https://github.com/ericc-ch/copilot-api) - Proxy project
