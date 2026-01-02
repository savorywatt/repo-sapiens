# Credential Management API

The credential management system provides secure storage and retrieval of sensitive data like API tokens, passwords, and secrets.

## Overview

The system supports three storage backends:
1. **Keyring Backend**: OS-level credential storage (macOS Keychain, Windows Credential Manager, Linux Secret Service)
2. **Environment Backend**: Environment variables
3. **Encrypted Backend**: AES-256 encrypted JSON file with master password

## Module Structure

```
repo_sapiens/credentials/
├── __init__.py          # Public API exports
├── backend.py           # Abstract base class
├── resolver.py          # Main credential resolver
├── keyring_backend.py   # System keyring integration
├── environment_backend.py # Environment variable backend
├── encrypted_backend.py # Encrypted file storage
└── exceptions.py        # Credential-specific exceptions
```

## CredentialResolver

Main class for resolving credential references.

### Class: `CredentialResolver`

```python
class CredentialResolver:
    """Resolve credential references to actual values.

    Supports three reference formats:
    1. @keyring:service/key - OS keyring
    2. ${VAR_NAME} - Environment variable
    3. @encrypted:service/key - Encrypted file
    4. Direct value - Returned as-is (not recommended)
    """
```

### Constructor

```python
def __init__(
    self,
    encrypted_file_path: Path | None = None,
    encrypted_master_password: str | None = None,
) -> None:
    """Initialize credential resolver.

    Args:
        encrypted_file_path: Path to encrypted credentials file
        encrypted_master_password: Master password for encrypted backend
    """
```

### Methods

#### `resolve(value: str, cache: bool = True) -> str`

Resolve a credential reference to its actual value.

```python
resolver = CredentialResolver()

# Resolve from keyring
token = resolver.resolve("@keyring:gitea/api_token")

# Resolve from environment
api_key = resolver.resolve("${CLAUDE_API_KEY}")

# Resolve from encrypted file
secret = resolver.resolve("@encrypted:github/webhook_secret")

# Direct value (not recommended, but supported)
value = resolver.resolve("literal-value")
```

**Parameters:**
- `value` (str): Credential reference or direct value
- `cache` (bool): Whether to cache the resolved value (default: True)

**Returns:**
- str: Resolved credential value

**Raises:**
- `CredentialNotFoundError`: If credential doesn't exist
- `CredentialFormatError`: If reference format is invalid
- `BackendNotAvailableError`: If required backend is unavailable

#### `clear_cache() -> None`

Clear the credential cache.

```python
resolver.clear_cache()
```

Use this when credentials may have been updated and you want to force re-resolution.

## Backends

### KeyringBackend

Stores credentials in the operating system's secure credential storage.

```python
from repo_sapiens.credentials import KeyringBackend

backend = KeyringBackend()

# Check availability
if backend.available:
    # Store credential
    backend.set("service", "account", "password123")

    # Retrieve credential
    password = backend.get("service", "account")

    # Delete credential
    backend.delete("service", "account")
```

**Methods:**

- `get(service: str, key: str) -> str | None`: Retrieve credential
- `set(service: str, key: str, value: str) -> None`: Store credential
- `delete(service: str, key: str) -> bool`: Delete credential
- `available: bool`: Property indicating if keyring is available

**Platform Support:**
- macOS: Uses Keychain
- Windows: Uses Credential Manager
- Linux: Uses Secret Service API (requires `gnome-keyring` or `kwallet`)

### EnvironmentBackend

Retrieves credentials from environment variables.

```python
from repo_sapiens.credentials import EnvironmentBackend
import os

backend = EnvironmentBackend()

# Set environment variable (for current process)
backend.set("API_TOKEN", "secret-value")

# Get environment variable
token = backend.get("API_TOKEN")

# Delete environment variable
backend.delete("API_TOKEN")
```

**Methods:**

- `get(var_name: str) -> str | None`: Get environment variable
- `set(var_name: str, value: str) -> None`: Set environment variable (current process only)
- `delete(var_name: str) -> bool`: Delete environment variable

**Note:** Setting environment variables only affects the current process. For persistent storage, export in your shell profile.

### EncryptedFileBackend

Stores credentials in an AES-256 encrypted JSON file.

```python
from repo_sapiens.credentials import EncryptedFileBackend
from pathlib import Path

backend = EncryptedFileBackend(
    file_path=Path(".repo-sapiens/credentials.enc"),
    master_password="secure-master-password"
)

# Check availability
if backend.available:
    # Store credential
    backend.set("github", "api_token", "ghp_...")

    # Retrieve credential
    token = backend.get("github", "api_token")

    # Delete credential
    backend.delete("github", "api_token")
```

**Constructor:**

```python
def __init__(
    self,
    file_path: Path,
    master_password: str | None = None
) -> None:
    """Initialize encrypted file backend.

    Args:
        file_path: Path to encrypted credentials file
        master_password: Master password for encryption/decryption
    """
```

**Methods:**

- `get(service: str, key: str) -> str | None`: Retrieve credential
- `set(service: str, key: str, value: str) -> None`: Store credential
- `delete(service: str, key: str) -> bool`: Delete credential
- `available: bool`: Property indicating if cryptography library is installed

**Security:**
- Uses AES-256-GCM encryption
- Master password is hashed with PBKDF2
- Each credential is individually encrypted
- Requires `cryptography` library

## Exceptions

### `CredentialError`

Base exception for all credential-related errors.

```python
class CredentialError(Exception):
    """Base exception for credential operations.

    Attributes:
        message: Error message
        reference: Original credential reference that failed
        suggestion: Optional suggestion for resolution
    """
```

### `CredentialNotFoundError`

Raised when a credential cannot be found in the specified backend.

```python
try:
    token = resolver.resolve("@keyring:missing/credential")
except CredentialNotFoundError as e:
    print(f"Error: {e.message}")
    print(f"Suggestion: {e.suggestion}")
```

### `BackendNotAvailableError`

Raised when a required backend is not available (e.g., keyring not installed).

```python
try:
    token = resolver.resolve("@keyring:service/key")
except BackendNotAvailableError as e:
    print(f"Backend not available: {e.message}")
    print(f"Solution: {e.suggestion}")
```

### `CredentialFormatError`

Raised when a credential reference has an invalid format.

```python
try:
    token = resolver.resolve("@invalid:format")
except CredentialFormatError as e:
    print(f"Invalid format: {e.message}")
```

## Reference Formats

### Keyring Reference

Format: `@keyring:service/key`

```python
# Examples
"@keyring:gitea/api_token"
"@keyring:github/personal_access_token"
"@keyring:anthropic/api_key"
```

### Environment Variable Reference

Format: `${VARIABLE_NAME}`

```python
# Examples
"${GITEA_TOKEN}"
"${CLAUDE_API_KEY}"
"${DATABASE_PASSWORD}"
```

**Requirements:**
- Variable name must be uppercase
- Can contain letters, numbers, and underscores
- Must start with a letter or underscore

### Encrypted File Reference

Format: `@encrypted:service/key`

```python
# Examples
"@encrypted:gitea/api_token"
"@encrypted:production/database_url"
"@encrypted:api/webhook_secret"
```

## Usage in Configuration

Credentials can be referenced in YAML configuration files:

```yaml
# repo_sapiens/config/automation_config.yaml
git_provider:
  provider_type: gitea
  base_url: https://gitea.example.com
  api_token: @keyring:gitea/api_token  # From keyring

agent_provider:
  provider_type: claude-api
  api_key: ${CLAUDE_API_KEY}  # From environment

repository:
  webhook_secret: @encrypted:webhooks/secret  # From encrypted file
```

When the configuration is loaded, all credential references are automatically resolved:

```python
from repo_sapiens.config.settings import AutomationSettings

settings = AutomationSettings.from_yaml("repo_sapiens/config/automation_config.yaml")

# api_token is automatically resolved from keyring
print(settings.git_provider.api_token)  # "actual-token-value"
```

## CLI Usage

The `sapiens credentials` command provides CLI access to credential management:

### Set a Credential

```bash
# Store in keyring
sapiens credentials set gitea/api_token --backend keyring

# Store in environment (current session only)
sapiens credentials set GITEA_TOKEN --backend environment

# Store in encrypted file
sapiens credentials set gitea/api_token --backend encrypted
```

### Get a Credential

```bash
# Retrieve and display (masked)
sapiens credentials get @keyring:gitea/api_token

# Show full value
sapiens credentials get @keyring:gitea/api_token --show-value
```

### Delete a Credential

```bash
# Delete from keyring
sapiens credentials delete gitea/api_token --backend keyring

# Delete from environment
sapiens credentials delete GITEA_TOKEN --backend environment
```

### Test Backends

```bash
# Check which backends are available
sapiens credentials test
```

## Best Practices

### 1. Never Commit Credentials

```python
# ❌ BAD: Hardcoded credentials
api_token = "ghp_1234567890abcdef"

# ✅ GOOD: Reference to credential backend
api_token = resolver.resolve("@keyring:github/api_token")
```

### 2. Use Appropriate Backend

- **Workstation**: Use `keyring` backend for persistent, secure storage
- **CI/CD**: Use environment variables (`${VAR}`)
- **Shared environments**: Use encrypted files (`@encrypted:`)

### 3. Clear Cache After Updates

```python
resolver = CredentialResolver()

# If credentials are updated externally
backend.set("service", "key", "new-value")

# Clear cache to get new value
resolver.clear_cache()
value = resolver.resolve("@keyring:service/key")  # Gets new value
```

### 4. Handle Missing Credentials Gracefully

```python
from repo_sapiens.credentials.exceptions import CredentialNotFoundError

try:
    token = resolver.resolve("@keyring:optional/token")
except CredentialNotFoundError:
    # Use default or prompt user
    token = click.prompt("Enter API token")
```

### 5. Secure Master Passwords

For encrypted backend:

```python
# ❌ BAD: Hardcoded master password
backend = EncryptedFileBackend(
    file_path=Path(".credentials.enc"),
    master_password="hardcoded-password"  # Never do this
)

# ✅ GOOD: Master password from environment or prompt
import os

master_password = os.getenv("MASTER_PASSWORD")
if not master_password:
    master_password = getpass.getpass("Master password: ")

backend = EncryptedFileBackend(
    file_path=Path(".credentials.enc"),
    master_password=master_password
)
```

## Examples

### Example 1: Multi-Backend Resolution

```python
from repo_sapiens.credentials import CredentialResolver

resolver = CredentialResolver()

# Resolve from multiple backends
config = {
    "gitea_token": resolver.resolve("@keyring:gitea/api_token"),
    "claude_key": resolver.resolve("${CLAUDE_API_KEY}"),
    "webhook_secret": resolver.resolve("@encrypted:webhooks/secret"),
}
```

### Example 2: Custom Backend Fallback

```python
from repo_sapiens.credentials.exceptions import BackendNotAvailableError

resolver = CredentialResolver()

try:
    token = resolver.resolve("@keyring:gitea/api_token")
except BackendNotAvailableError:
    # Fallback to environment if keyring not available
    token = resolver.resolve("${GITEA_TOKEN}")
```

### Example 3: Rotating Credentials

```python
from repo_sapiens.credentials import KeyringBackend

backend = KeyringBackend()

# Rotate API token
old_token = backend.get("gitea", "api_token")
new_token = generate_new_token()

# Update in backend
backend.set("gitea", "api_token", new_token)

# Verify rotation
resolver = CredentialResolver()
resolver.clear_cache()  # Clear old cached value
current_token = resolver.resolve("@keyring:gitea/api_token")
assert current_token == new_token
```

## See Also

- [Configuration API](./configuration.md)
- [Security Best Practices](../SECURITY.md)
- [CLI Reference](../guides/cli-reference.md)
