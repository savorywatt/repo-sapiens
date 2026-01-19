# GitHub Copilot Setup Guide

> ⚠️ **IMPORTANT DISCLAIMER**
>
> This integration uses [`copilot-api`](https://github.com/nicepkg/copilot-api),
> an **unofficial, reverse-engineered API**. By using this:
>
> - You acknowledge this is **NOT endorsed by GitHub**
> - You understand it may **violate GitHub ToS**
> - You accept it could **break at any time**
> - You use it **at your own risk**
>
> For production use, consider Claude Code, Goose, or OpenAI-compatible providers.

## Prerequisites

1. **GitHub Copilot subscription** (Individual, Business, or Enterprise)
2. **GitHub OAuth token** with Copilot access
3. **Node.js 18+** and npm (for copilot-api proxy)

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Sapiens   │────▶│  copilot-api │────▶│  GitHub Copilot │
│             │     │    proxy     │     │      API        │
└─────────────┘     └──────────────┘     └─────────────────┘
```

The `copilot-api` package acts as a local proxy that:
1. Accepts OpenAI-compatible API requests
2. Translates them to GitHub Copilot's internal API
3. Returns responses in OpenAI format

## Quick Start

### 1. Get GitHub OAuth Token

You need a GitHub OAuth token (starts with `gho_`) with Copilot access:

```bash
# Option A: Extract from GitHub CLI (if already authenticated with Copilot)
gh auth token

# Option B: Create via GitHub settings
# Go to: Settings > Developer settings > Personal access tokens
# Required scopes: copilot
```

### 2. Store the Token

```bash
# Using keyring (recommended)
sapiens credentials set github/copilot_token

# Or via environment variable
export COPILOT_GITHUB_TOKEN="gho_your_token_here"
```

### 3. Configure Sapiens

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  copilot_config:
    github_token: "@keyring:github/copilot_token"  # or "${COPILOT_GITHUB_TOKEN}"
    manage_proxy: true        # Auto-start copilot-api
    proxy_port: 4141
    rate_limit: 2.0          # Seconds between requests (recommended)
```

### 4. Verify Setup

```bash
sapiens health-check
```

## Configuration Options

### Managed Proxy (Recommended)

Sapiens automatically starts/stops the copilot-api proxy:

```yaml
copilot_config:
  github_token: "@keyring:github/copilot_token"
  manage_proxy: true
  proxy_port: 4141
  startup_timeout: 30.0
  shutdown_timeout: 5.0
```

### External Proxy

Connect to an existing copilot-api instance:

```yaml
copilot_config:
  github_token: "@keyring:github/copilot_token"
  manage_proxy: false
  proxy_url: "http://localhost:4141/v1"
```

### Rate Limiting

GitHub may detect abuse if requests are too frequent:

```yaml
copilot_config:
  rate_limit: 2.0  # Minimum 2 seconds between requests
```

## Troubleshooting

### "npx not found"

Install Node.js:
```bash
# macOS
brew install node

# Ubuntu
sudo apt install nodejs npm
```

### "Rate limit exceeded" / "Abuse detected"

Add or increase `rate_limit`:
```yaml
copilot_config:
  rate_limit: 5.0  # Increase delay between requests
```

### "Invalid authentication token"

Your GitHub token may be expired or lack Copilot access:
1. Regenerate the token
2. Ensure your GitHub account has an active Copilot subscription
3. Update the stored credential

### Proxy fails to start

Check if the port is already in use:
```bash
lsof -i :4141
```

Use a different port:
```yaml
copilot_config:
  proxy_port: 4142
```

## Limitations

| Aspect | Copilot | Claude Code |
|--------|---------|-------------|
| Official support | No | Yes |
| Reliability | May break | Stable |
| Rate limits | Aggressive | Generous |
| Model choice | gpt-4 only | Claude models |
| ToS compliance | Uncertain | Yes |

## See Also

- [AGENT_COMPARISON.md](./AGENT_COMPARISON.md)
- [CREDENTIALS.md](./CREDENTIALS.md)
- [copilot-api GitHub](https://github.com/nicepkg/copilot-api)
