# Error Handling in Repo-Sapiens

This document describes the error handling strategy, exception hierarchy, and best practices for the repo-sapiens automation system.

## Exception Hierarchy

All repo-sapiens exceptions inherit from a base `RepoSapiensError` class, enabling:
- Precise error handling and recovery
- User-friendly error messages
- Proper logging and debugging
- Consistent error behavior across the system

```
RepoSapiensError (base)
├── ConfigurationError
│   └── Configuration file issues (missing, invalid YAML, validation failures)
├── CredentialError (see repo_sapiens.credentials.exceptions)
│   ├── CredentialNotFoundError
│   ├── CredentialFormatError
│   ├── BackendNotAvailableError
│   └── EncryptionError
├── GitOperationError (see repo_sapiens.git.exceptions)
│   ├── NotGitRepositoryError
│   ├── NoRemotesError
│   ├── MultipleRemotesError
│   ├── InvalidGitUrlError
│   └── UnsupportedHostError
├── TemplateError
│   └── Template rendering/validation failures
├── WorkflowError
│   └── Workflow execution/orchestration failures
└── ExternalServiceError
    └── HTTP errors, API failures, timeouts, rate limiting
```

## Exception Handling Patterns

### Pattern 1: Specific Exception Types

Always catch specific exceptions rather than broad `Exception` catches. This enables proper recovery and logging.

```python
from repo_sapiens.exceptions import ConfigurationError

try:
    config = load_config(path)
except FileNotFoundError as e:
    raise ConfigurationError(f"Config file not found: {path}") from e
except yaml.YAMLError as e:
    raise ConfigurationError(f"Invalid YAML in {path}: {e}") from e
except ValueError as e:
    raise ConfigurationError(f"Invalid config values: {e}") from e
```

**Why:** Specific catches allow targeted error recovery, proper logging, and communicating intent.

### Pattern 2: Context Preservation

Always use `raise ... from e` to preserve the exception chain for debugging.

```python
try:
    credential = resolve_credential(ref)
except KeyError as e:
    raise CredentialError(f"Credential not found: {ref}") from e
```

**Why:** The original exception provides context for debugging, visible in tracebacks.

### Pattern 3: Never Bare Except

Never use bare `except:` clauses - they hide bugs and prevent KeyboardInterrupt handling.

```python
# BAD - Catches KeyboardInterrupt, SystemExit, etc.
try:
    do_something()
except:
    pass

# GOOD - Specific exception types
try:
    do_something()
except (ValueError, TypeError) as e:
    log.debug("expected_error", error=str(e))
```

**Why:** Bare except clauses hide bugs, catch unintended exceptions (like KeyboardInterrupt), and make code hard to debug.

### Pattern 4: Exception Re-raising

If catching an exception only to add context, re-raise with the original as the cause:

```python
try:
    parse_config(path)
except yaml.YAMLError as e:
    raise ConfigurationError(
        f"Invalid YAML in {path}: {e}"
    ) from e
```

**Why:** Preserves the exception chain and provides helpful context to callers.

### Pattern 5: User-Friendly Messages

Design exception messages for end users, not developers:

```python
# BAD
raise ConfigurationError("KeyError: 'api_token'")

# GOOD
raise ConfigurationError(
    f"Missing required field 'api_token' in {section}"
)
```

**Why:** Users need to understand what went wrong and how to fix it.

## CLI Error Handling

The CLI should catch `RepoSapiensError` exceptions and display user-friendly messages:

```python
from repo_sapiens.exceptions import RepoSapiensError

@cli.command()
def my_command():
    try:
        # command logic
        pass
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        log.debug("command_error", exc_info=True)  # Full trace at DEBUG level
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)  # Standard Unix interrupt exit code
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        log.error("command_error_unexpected", exc_info=True)
        sys.exit(1)
```

**Error Codes:**
- `0`: Success
- `1`: Expected error (configuration, credential, workflow)
- `2`: CLI usage error (Click handles this)
- `130`: Interrupted by user (SIGINT)

## Configuration Error Handling

Configuration errors should be caught early with clear messages:

```python
from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.exceptions import ConfigurationError

try:
    settings = AutomationSettings.from_yaml("config.yaml")
except ConfigurationError as e:
    click.echo(f"Configuration error: {e.message}", err=True)
    sys.exit(1)
except FileNotFoundError:
    click.echo("Configuration file not found: config.yaml", err=True)
    sys.exit(1)
```

The `from_yaml()` method automatically:
- Checks file existence
- Validates YAML syntax
- Interpolates environment variables
- Validates required fields
- Raises `ConfigurationError` with helpful messages

## Credential Error Handling

Credential errors include helpful suggestions for resolution:

```python
from repo_sapiens.credentials.exceptions import (
    CredentialNotFoundError,
    BackendNotAvailableError,
)

try:
    token = resolver.resolve("@keyring:gitea/api_token")
except CredentialNotFoundError as e:
    print(e)  # Includes suggestion on how to store the credential
except BackendNotAvailableError as e:
    print(e)  # Includes suggestion to install required package
```

Example output:
```
Credential not found: @keyring:gitea/api_token (reference: @keyring:gitea/api_token)
Suggestion: Store the credential with:
  automation credentials set --keyring gitea/api_token
```

## Git Operation Error Handling

Git errors include helpful hints for resolution:

```python
from repo_sapiens.git.exceptions import NotGitRepositoryError

try:
    discover_git_info(path)
except NotGitRepositoryError as e:
    print(e)  # Includes helpful hint
```

Example output:
```
Not a Git repository: /tmp/not-a-repo

Hint: Run 'git init' or navigate to a Git repository directory.
```

## External Service Error Handling

External service errors capture HTTP status codes and response details:

```python
from repo_sapiens.exceptions import ExternalServiceError

try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    raise ExternalServiceError(
        f"API request failed: {url}",
        status_code=e.response.status_code,
        response_text=e.response.text,
    ) from e
```

## Logging Best Practices

### Log Levels

- **DEBUG**: Expected error conditions, full exception tracebacks for troubleshooting
- **INFO**: Normal operation milestones
- **WARNING**: Unexpected but non-critical conditions (e.g., direct token values in config)
- **ERROR**: Error conditions that require attention but don't stop execution

### Log Messages

Use structured logging with context:

```python
import structlog

log = structlog.get_logger(__name__)

try:
    process_issue(issue)
except CredentialError as e:
    log.error(
        "credential_error",
        issue=issue.id,
        error=e.message,
        exc_info=True,
    )
except Exception as e:
    log.error(
        "process_issue_error",
        issue=issue.id,
        error=str(e),
        exc_info=True,
    )
```

## Audit Findings

The following patterns were found and fixed:

### Bare Except Clauses

**Found in:** `repo_sapiens/providers/gitea_rest.py:285`

**Problem:** Silently catches all exceptions including KeyboardInterrupt and SystemExit.

**Fix:**
```python
# Before
except:
    pass

# After
except (httpx.HTTPError, ValueError) as e:
    log.debug("file_not_exists", url=url, error=str(e))
```

### Broad Exception Catches

**Found in:** Multiple files

**Pattern:** `except Exception as e:` without re-raising or context preservation.

**Improvements:**
1. Use specific exception types when possible
2. Log at appropriate level (DEBUG for expected, ERROR for unexpected)
3. Re-raise with `from e` to preserve chain
4. Provide helpful context in error messages

### Missing Error Handling

**Critical Paths:**
1. Configuration loading - Now catches FileNotFoundError, YAML errors, validation errors
2. Credential resolution - Catches specific credential errors with suggestions
3. CLI commands - All command handlers wrap in try/except with proper exit codes

## Testing Error Handling

When writing tests, verify both successful and error paths:

```python
import pytest
from repo_sapiens.exceptions import ConfigurationError

def test_missing_config_file():
    """Test handling of missing configuration file."""
    with pytest.raises(ConfigurationError, match="not found"):
        AutomationSettings.from_yaml("nonexistent.yaml")

def test_invalid_yaml_config():
    """Test handling of invalid YAML syntax."""
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        AutomationSettings.from_yaml("invalid.yaml")

def test_missing_required_field():
    """Test handling of missing required configuration field."""
    with pytest.raises(ConfigurationError, match="required"):
        AutomationSettings.from_yaml("incomplete.yaml")
```

## Migration Guide

### Updating Existing Code

**Before:**
```python
try:
    process_something()
except Exception as e:
    print(f"Error: {e}")
```

**After:**
```python
from repo_sapiens.exceptions import RepoSapiensError

try:
    process_something()
except RepoSapiensError as e:
    log.error("process_error", error=e.message, exc_info=True)
    raise  # or handle specifically
except Exception as e:
    log.error("unexpected_error", exc_info=True)
    raise
```

### Creating New Exception Types

If a new subsystem needs custom exceptions:

```python
from repo_sapiens.exceptions import RepoSapiensError

class MySubsystemError(RepoSapiensError):
    """Base exception for my subsystem."""
    pass

class SpecificError(MySubsystemError):
    """Specific error condition."""
    pass
```

## Troubleshooting

### "Unexpected error" in logs but no user message

**Cause:** An exception type that's not caught specifically.

**Solution:** Add a specific except clause or improve exception messages in the code raising the error.

### Application exiting without error message

**Cause:** Exception during CLI initialization (before try/except block).

**Solution:** Move error handling earlier or add a top-level exception handler.

### No full traceback in logs

**Cause:** Not passing `exc_info=True` to log.error().

**Solution:** Always include `exc_info=True` when logging errors:
```python
log.error("something_failed", exc_info=True)
```

## Summary

The repo-sapiens exception hierarchy provides:
- **Structure:** Clear exception inheritance for precise error handling
- **Context:** Exception chaining preserves debugging information
- **UX:** User-friendly messages with helpful suggestions
- **Logging:** Structured logging with appropriate levels
- **Standards:** Follows Python exception handling best practices

Key principles:
1. Use specific exception types, never bare `except:`
2. Always preserve exception chains with `raise ... from e`
3. Design messages for end users, not developers
4. Log at DEBUG for expected errors, ERROR for unexpected
5. Exit with appropriate codes (0, 1, 130)
