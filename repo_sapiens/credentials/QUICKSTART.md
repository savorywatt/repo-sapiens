# Credential Management - Quick Start

## Installation

```bash
pip install keyring cryptography
```

## Store Credentials

```bash
# OS Keyring (recommended)
sapiens credentials set gitea/api_token --backend keyring

# Environment Variable
sapiens credentials set GITEA_TOKEN --backend environment

# Encrypted File
sapiens credentials set gitea/api_token --backend encrypted
```

## Use in Config

```yaml
# repo_sapiens/config/automation_config.yaml

git_provider:
  api_token: "@keyring:gitea/api_token"
  # OR: "${GITEA_API_TOKEN}"
  # OR: "@encrypted:gitea/api_token"

agent_provider:
  api_key: "@keyring:claude/api_key"
```

## Test

```bash
# Test resolution
sapiens credentials get @keyring:gitea/api_token

# Check backends
sapiens credentials test
```

## Reference Syntax

| Backend | Syntax | Example |
|---------|--------|---------|
| Keyring | `@keyring:service/key` | `@keyring:gitea/api_token` |
| Environment | `${VARIABLE_NAME}` | `${GITEA_API_TOKEN}` |
| Encrypted | `@encrypted:service/key` | `@encrypted:gitea/api_token` |

## Common Commands

```bash
# Store
sapiens credentials set service/key --backend keyring

# Retrieve (masked)
sapiens credentials get @keyring:service/key

# Retrieve (full value)
sapiens credentials get @keyring:service/key --show-value

# Delete
sapiens credentials delete service/key --backend keyring

# Test backends
sapiens credentials test
```

## Migration from Direct Values

```bash
# 1. Store credential
sapiens credentials set gitea/api_token --backend keyring

# 2. Update config file
# Change: api_token: "ghp_actual_value"
# To:     api_token: "@keyring:gitea/api_token"

# 3. Test
sapiens credentials get @keyring:gitea/api_token

# 4. Commit (safe - no secrets)
git add repo_sapiens/config/automation_config.yaml
git commit -m "chore: Use keyring for credentials"
```

## Troubleshooting

### Keyring not available
```bash
# Linux
sudo apt install gnome-keyring

# Or use environment variables
api_token: "${GITEA_API_TOKEN}"
```

### Environment variable not set
```bash
export GITEA_API_TOKEN="your-token"
```

### Wrong encrypted file password
```bash
rm .builder/credentials.enc .builder/credentials.salt
sapiens credentials set gitea/api_token --backend encrypted
```

## Security Best Practices

1. Never commit direct credentials
2. Use keyring on workstations
3. Use environment variables in CI/CD
4. Rotate credentials regularly
5. Restrict file permissions (0600)

## Full Documentation

See [README.md](./README.md) for complete documentation.
