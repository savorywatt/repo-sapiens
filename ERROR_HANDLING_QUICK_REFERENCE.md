# Error Handling Quick Reference

## Exception Types

```python
from automation.exceptions import (
    RepoSapiensError,           # Base - catches all errors
    ConfigurationError,          # Config file/parsing errors
    CredentialError,             # Credential resolution errors
    GitOperationError,           # Git operation errors
    TemplateError,               # Template rendering errors
    WorkflowError,               # Workflow execution errors
    ExternalServiceError,        # HTTP/API errors
)
```

## Common Patterns

### Pattern 1: Basic Error Handling

```python
try:
    do_something()
except ConfigurationError as e:
    print(f"Configuration error: {e.message}")
    sys.exit(1)
except Exception as e:
    log.error("unexpected_error", exc_info=True)
    sys.exit(1)
```

### Pattern 2: Catching All App Errors

```python
try:
    process_workflow()
except RepoSapiensError as e:
    # Catch ALL repo-sapiens errors with one handler
    log.error("workflow_error", error=e.message, exc_info=True)
    return None
```

### Pattern 3: Re-raising with Context

```python
try:
    load_config(path)
except FileNotFoundError as e:
    raise ConfigurationError(
        f"Config file not found: {path}"
    ) from e  # Preserves original exception
```

### Pattern 4: Specific + General Handler

```python
try:
    resolve_credential(ref)
except CredentialNotFoundError as e:
    # Handle missing credential specifically
    log.warning(f"Credential missing: {e.suggestion}")
except CredentialError as e:
    # Handle other credential errors
    log.error(f"Credential error: {e.message}")
except Exception as e:
    # Catch unexpected errors
    log.error("unexpected_error", exc_info=True)
```

## CLI Error Handling

```python
@cli.command()
def my_command():
    try:
        # do work
        click.echo("Success!")
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        log.error("error", exc_info=True)
        sys.exit(1)
```

## Exit Codes

- `0` - Success
- `1` - Expected error (configuration, credentials, workflow)
- `2` - CLI usage error (Click handles this)
- `130` - User interruption (Ctrl+C)

## HTTP Status Codes (for APIs)

- `400` - Bad request (missing data)
- `422` - Unprocessable entity (validation error)
- `500` - Internal server error (unexpected)

## Logging

```python
import structlog

log = structlog.get_logger(__name__)

# Expected errors - debug level
log.debug("expected_error", error=str(e))

# Unexpected errors - error level with full trace
log.error("unexpected_error", error=str(e), exc_info=True)

# With context
log.error("process_failed", issue=issue_id, error=e.message, exc_info=True)
```

## Creating New Exceptions

```python
from automation.exceptions import RepoSapiensError

class MySubsystemError(RepoSapiensError):
    """Base error for my subsystem."""
    pass

class SpecificProblem(MySubsystemError):
    """Specific error condition."""
    pass

# Raise with helpful message
raise SpecificProblem("What happened and how to fix it")
```

## Error Messages

Good error messages:
- Explain what went wrong
- Suggest how to fix it
- Include relevant context

```python
# Bad
raise ConfigurationError("KeyError")

# Good
raise ConfigurationError(
    f"Missing required field 'api_token' in git_provider section"
)
```

## What NOT to Do

```python
# ❌ Bare except - catches KeyboardInterrupt, SystemExit!
try:
    do_work()
except:
    pass

# ❌ Catch Exception and silently pass
try:
    process()
except Exception:
    pass

# ❌ No exception context
try:
    do_work()
except Exception as e:
    print(e)

# ❌ Generic error messages
raise ConfigurationError("Error")
```

## What TO Do

```python
# ✅ Specific exception types
try:
    do_work()
except ValueError as e:
    log.debug("expected_error", error=str(e))

# ✅ Preserve exception chain
try:
    do_work()
except IOError as e:
    raise ConfigurationError("Cannot read config") from e

# ✅ Log with full context
try:
    process()
except Exception as e:
    log.error("process_failed", exc_info=True)

# ✅ Helpful error messages
raise ConfigurationError(
    f"Missing 'api_token' in git_provider configuration"
)
```

## Testing Error Paths

```python
import pytest
from automation.exceptions import ConfigurationError

def test_missing_config():
    with pytest.raises(ConfigurationError, match="not found"):
        load_config("nonexistent.yaml")

def test_invalid_yaml():
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_config("invalid.yaml")
```

## Exception Attributes

### RepoSapiensError
- `message: str` - Error description

### CredentialError (and subclasses)
- `message: str` - Error description
- `reference: str` - Credential reference (e.g., "@keyring:service/key")
- `suggestion: str` - How to fix it

### GitDiscoveryError (and subclasses)
- `message: str` - Error description
- `hint: str` - Helpful hint for resolution

### ExternalServiceError
- `message: str` - Error description
- `status_code: int` - HTTP status (if applicable)
- `response_text: str` - Response body (if applicable)

## Common Scenarios

### Loading Configuration

```python
from automation.config.settings import AutomationSettings
from automation.exceptions import ConfigurationError

try:
    settings = AutomationSettings.from_yaml("config.yaml")
except ConfigurationError as e:
    click.echo(f"Configuration error: {e.message}", err=True)
    sys.exit(1)
```

### Resolving Credentials

```python
from automation.credentials.resolver import CredentialResolver
from automation.credentials.exceptions import CredentialNotFoundError

resolver = CredentialResolver()

try:
    token = resolver.resolve("@keyring:gitea/api_token")
except CredentialNotFoundError as e:
    click.echo(f"Error: {e.suggestion}", err=True)
    sys.exit(1)
```

### Git Operations

```python
from automation.git.discovery import discover_git_info
from automation.git.exceptions import NotGitRepositoryError

try:
    git_info = discover_git_info(path)
except NotGitRepositoryError as e:
    click.echo(f"Error: {e.hint}", err=True)
    sys.exit(1)
```

### API Requests

```python
from automation.exceptions import ExternalServiceError

try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    raise ExternalServiceError(
        f"API request failed",
        status_code=e.response.status_code,
        response_text=e.response.text,
    ) from e
```

## Documentation

- Full guide: `/home/ross/Workspace/repo-agent/docs/ERROR_HANDLING.md`
- Implementation report: `/home/ross/Workspace/repo-agent/ERROR_HANDLING_IMPLEMENTATION.md`
- Exception definitions: `/home/ross/Workspace/repo-agent/automation/exceptions.py`

## Key Takeaways

1. **Use specific exception types** - enables precise error handling
2. **Preserve exception chains** - use `raise ... from e`
3. **Write helpful messages** - for users, not developers
4. **Log with context** - include `exc_info=True` for full traces
5. **Exit with proper codes** - 0 for success, 1 for errors, 130 for interrupt
6. **Never bare except** - always specify exception types

---

**Version:** 1.0
**Last Updated:** 2025-12-23
