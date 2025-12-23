# Credential Management - Quick Start Guide

This guide provides quick examples for using the credential management system in the repo-agent project.

## Table of Contents

1. [First Time Setup](#first-time-setup)
2. [Storing Credentials](#storing-credentials)
3. [Using Credentials in Config](#using-credentials-in-config)
4. [Programmatic Access](#programmatic-access)
5. [Troubleshooting](#troubleshooting)

## First Time Setup

### 1. Check Backend Availability

```bash
builder credentials test
```

Expected output:
```
Testing credential backends...
Keyring backend: Available
Environment backend: Available
Encrypted file backend: Available
```

### 2. Choose Your Backend

- **Developer Workstation**: Use `keyring` (most secure, persistent)
- **CI/CD Pipeline**: Use `environment` (native to most CI systems)
- **Headless Server**: Use `encrypted` (requires master password)

## Storing Credentials

### Option 1: Keyring (Recommended for Workstations)

```bash
# Store Gitea API token
builder credentials set gitea/api_token --backend keyring
# Enter your token when prompted

# Store Claude API key
builder credentials set claude/api_key --backend keyring
# Enter your API key when prompted
```

**Benefits**:
- Secure OS-level storage
- Persists across reboots
- Supports biometric unlock (Touch ID, Windows Hello)
- No configuration files needed

### Option 2: Environment Variables (Recommended for CI/CD)

```bash
# For current session
export GITEA_API_TOKEN="your-token-here"
export CLAUDE_API_KEY="your-api-key-here"

# Or use the CLI
builder credentials set GITEA_API_TOKEN --backend environment
builder credentials set CLAUDE_API_KEY --backend environment
```

**Benefits**:
- Native CI/CD support (GitHub Actions, Gitea Actions)
- No additional tools required
- Automatically cleaned up after session

**Note**: Environment variables set via CLI only persist in current process.

### Option 3: Encrypted File (Fallback)

```bash
# Set master password (one time)
export BUILDER_MASTER_PASSWORD="your-secure-master-password"

# Store credentials
builder credentials set gitea/api_token --backend encrypted
builder credentials set claude/api_key --backend encrypted
```

**Benefits**:
- Works on headless systems
- Persists across reboots
- No OS keyring required

**Caution**: Master password must be protected!

## Using Credentials in Config

### Configuration File Setup

**File**: `automation/config/automation_config.yaml`

```yaml
git_provider:
  provider_type: gitea
  base_url: "https://gitea.example.com"
  api_token: "@keyring:gitea/api_token"  # Uses keyring

repository:
  owner: "myorg"
  name: "myrepo"

agent_provider:
  provider_type: claude-api
  model: claude-sonnet-4.5
  api_key: "${CLAUDE_API_KEY}"  # Uses environment variable
```

### Reference Syntax

| Syntax | Backend | Example |
|--------|---------|---------|
| `@keyring:service/key` | OS Keyring | `@keyring:gitea/api_token` |
| `${VAR_NAME}` | Environment | `${GITEA_API_TOKEN}` |
| `@encrypted:service/key` | Encrypted File | `@encrypted:gitea/api_token` |

### Loading Configuration

Credentials are **automatically resolved** when loading config:

```python
from automation.config.settings import AutomationSettings

# Load configuration
config = AutomationSettings.from_yaml("automation/config/automation_config.yaml")

# Access resolved credentials (not the reference string)
token = config.git_provider.api_token.get_secret_value()
# Returns actual token, not "@keyring:gitea/api_token"
```

## Programmatic Access

### Direct Backend Access

```python
from automation.credentials import KeyringBackend

# Initialize backend
backend = KeyringBackend()

# Store credential
backend.set('myservice', 'api_key', 'secret-value')

# Retrieve credential
api_key = backend.get('myservice', 'api_key')

# Delete credential
backend.delete('myservice', 'api_key')
```

### Using the Resolver

```python
from automation.credentials import CredentialResolver

# Initialize resolver
resolver = CredentialResolver()

# Resolve different reference types
keyring_token = resolver.resolve("@keyring:gitea/api_token")
env_token = resolver.resolve("${GITEA_API_TOKEN}")
encrypted_key = resolver.resolve("@encrypted:claude/api_key")

# Direct values pass through (with warning if they look like tokens)
direct = resolver.resolve("literal-value")
```

### Pydantic Models

```python
from pydantic import BaseModel
from automation.config.credential_fields import CredentialSecret

class MyConfig(BaseModel):
    api_key: CredentialSecret  # Automatically resolves references

# Usage
config = MyConfig(api_key="@keyring:service/key")
actual_key = config.api_key.get_secret_value()  # Returns resolved value
```

## Troubleshooting

### Error: Credential not found in keyring

**Symptom**:
```
CredentialNotFoundError: Credential not found in keyring: gitea/api_token
```

**Solution**:
```bash
# Store the credential
builder credentials set gitea/api_token --backend keyring

# Verify
builder credentials get @keyring:gitea/api_token
```

### Error: Keyring backend is not available

**Symptom**:
```
BackendNotAvailableError: Keyring backend is not available
```

**Solutions**:

**On Linux**:
```bash
# Install keyring backend
sudo apt install gnome-keyring  # Ubuntu/Debian
sudo dnf install gnome-keyring  # Fedora

# Or use environment variables instead
# Change config: api_token: "${GITEA_API_TOKEN}"
```

**Alternative**: Use encrypted file backend
```bash
builder credentials set gitea/api_token --backend encrypted
# Change config: api_token: "@encrypted:gitea/api_token"
```

### Error: Environment variable not set

**Symptom**:
```
CredentialNotFoundError: Environment variable not set: GITEA_API_TOKEN
```

**Solution**:
```bash
# Set the environment variable
export GITEA_API_TOKEN="your-token-here"

# Or add to .env file (for development)
echo "GITEA_API_TOKEN=your-token-here" >> .env
```

### Error: Invalid master password

**Symptom**:
```
EncryptionError: Invalid master password or corrupted credentials file
```

**Solutions**:

1. **Verify password**:
```bash
# Try again with correct password
builder credentials get @encrypted:service/key
```

2. **Reset encrypted file** (WARNING: deletes all stored credentials):
```bash
rm .builder/credentials.enc .builder/credentials.salt
builder credentials set gitea/api_token --backend encrypted
```

### Verify Credential Resolution

```bash
# Test that a credential can be resolved (displays masked value)
builder credentials get @keyring:gitea/api_token

# Show full value (use with caution)
builder credentials get @keyring:gitea/api_token --show-value
```

## Best Practices

### 1. Choose the Right Backend

| Environment | Recommended Backend | Reference Format |
|-------------|---------------------|------------------|
| Developer Laptop | Keyring | `@keyring:service/key` |
| CI/CD Pipeline | Environment | `${VARIABLE_NAME}` |
| Docker Container | Environment | `${VARIABLE_NAME}` |
| Headless Server | Encrypted File | `@encrypted:service/key` |

### 2. Never Commit Secrets

✅ **GOOD**:
```yaml
api_token: "@keyring:gitea/api_token"
```

❌ **BAD**:
```yaml
api_token: "ghp_actual_token_here"
```

### 3. Use SecretStr for Sensitive Values

```python
from pydantic import BaseModel, SecretStr
from automation.config.credential_fields import CredentialSecret

class Config(BaseModel):
    # Good: Uses SecretStr (won't appear in logs)
    api_key: CredentialSecret

    # Avoid: Plain string (may appear in logs/errors)
    # api_key: str
```

### 4. Document Required Credentials

Create a `.env.example` file:
```bash
# Required credentials for development
# DO NOT commit actual values!

# Gitea API token
# Get from: https://gitea.example.com/user/settings/applications
# Store with: builder credentials set gitea/api_token --backend keyring
GITEA_API_TOKEN=your-token-here

# Claude API key
# Get from: https://console.anthropic.com/
# Store with: builder credentials set claude/api_key --backend keyring
CLAUDE_API_KEY=your-api-key-here
```

### 5. Test Credential Access

```bash
# Before deploying, verify all credentials can be resolved
builder credentials get @keyring:gitea/api_token
builder credentials get ${CLAUDE_API_KEY}

# Or test the entire configuration
builder doctor  # (if implemented)
```

## Common Workflows

### Setting Up a New Developer

```bash
# 1. Clone repository
git clone https://gitea.example.com/org/repo-agent.git
cd repo-agent

# 2. Install dependencies
pip install -e .

# 3. Check credential system
builder credentials test

# 4. Store credentials (one-time)
builder credentials set gitea/api_token --backend keyring
builder credentials set claude/api_key --backend keyring

# 5. Verify configuration loads
builder --config automation/config/automation_config.yaml list-plans
```

### CI/CD Pipeline Setup

**GitHub Actions** (`.github/workflows/ci.yml`):
```yaml
env:
  GITEA_API_TOKEN: ${{ secrets.GITEA_API_TOKEN }}
  CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest
```

**Gitea Actions** (`.gitea/workflows/ci.yaml`):
```yaml
env:
  GITEA_API_TOKEN: ${{ secrets.GITEA_API_TOKEN }}
  CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest
```

Configuration uses environment variables:
```yaml
git_provider:
  api_token: "${GITEA_API_TOKEN}"

agent_provider:
  api_key: "${CLAUDE_API_KEY}"
```

### Rotating Credentials

```bash
# 1. Generate new credential on service (e.g., Gitea)

# 2. Update stored credential
builder credentials set gitea/api_token --backend keyring
# Enter new token

# 3. Test access
builder credentials get @keyring:gitea/api_token

# 4. Revoke old credential on service (if not already done)

# 5. No config file changes needed! (reference stays the same)
```

## Advanced Usage

### Custom Resolver Instance

```python
from pathlib import Path
from automation.credentials import CredentialResolver

# Custom encrypted file location
resolver = CredentialResolver(
    encrypted_file_path=Path("/secure/location/credentials.enc"),
    encrypted_master_password="master-password"
)

# Resolve credential
token = resolver.resolve("@encrypted:service/key")
```

### Clear Credential Cache

```python
from automation.credentials import CredentialResolver

resolver = CredentialResolver()

# Credentials are cached for performance
token1 = resolver.resolve("@keyring:service/key")  # Fetches from backend

# ... time passes, credential is updated in backend ...

# Clear cache to force fresh fetch
resolver.clear_cache()

token2 = resolver.resolve("@keyring:service/key")  # Fetches fresh value
```

### Multiple Services

```bash
# Store credentials for different services
builder credentials set gitea/api_token --backend keyring
builder credentials set github/api_token --backend keyring
builder credentials set gitlab/api_token --backend keyring
builder credentials set claude/api_key --backend keyring
builder credentials set openai/api_key --backend keyring

# Each service/key pair is isolated
```

## Security Checklist

- [ ] Never commit `.env` files with actual credentials
- [ ] Use `.gitignore` to exclude credential files
- [ ] Use keyring backend on developer workstations
- [ ] Use environment variables in CI/CD
- [ ] Rotate credentials regularly
- [ ] Use `CredentialSecret` (not plain `str`) in Pydantic models
- [ ] Verify credentials are masked in logs
- [ ] Use `--show-value` flag only when necessary
- [ ] Set file permissions to 0600 for encrypted credential files
- [ ] Protect master password for encrypted backend

## Getting Help

### View Command Help

```bash
# General help
builder credentials --help

# Command-specific help
builder credentials set --help
builder credentials get --help
builder credentials delete --help
builder credentials test --help
```

### Check Backend Status

```bash
builder credentials test
```

### Debugging

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
builder --log-level DEBUG credentials get @keyring:service/key
```

## Additional Resources

- **Implementation Plan**: `/home/ross/Workspace/repo-agent/plans/credential-management-implementation.md`
- **Implementation Summary**: `/home/ross/Workspace/repo-agent/CREDENTIAL_SYSTEM_IMPLEMENTATION_SUMMARY.md`
- **API Documentation**: See docstrings in `automation/credentials/` modules
- **Test Examples**: `/home/ross/Workspace/repo-agent/tests/test_credentials/`

---

**Last Updated**: 2024-12-22
