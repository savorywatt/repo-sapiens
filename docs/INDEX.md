# Documentation Index

## Core Implementation

### Exception System
- **File:** `/home/ross/Workspace/repo-agent/automation/exceptions.py`
- **Description:** Custom exception hierarchy for the repo-sapiens application
- **Contains:** 7 exception classes with base `RepoSapiensError` and 6 specialized types
- **Status:** Production ready

### Error Handling Guide
- **File:** `/home/ross/Workspace/repo-agent/docs/ERROR_HANDLING.md`
- **Description:** Comprehensive error handling documentation
- **Contents:**
  - Exception hierarchy with visualization
  - 5 error handling patterns with examples
  - Best practices for logging, testing, and migration
  - Troubleshooting guide
  - Common scenarios

### Implementation Report
- **File:** `/home/ross/Workspace/repo-agent/ERROR_HANDLING_IMPLEMENTATION.md`
- **Description:** Detailed implementation report
- **Contents:**
  - Changes made per file with line numbers
  - Audit findings and fixes
  - Integration notes and backward compatibility
  - Recommended next steps

### Quick Reference
- **File:** `/home/ross/Workspace/repo-agent/ERROR_HANDLING_QUICK_REFERENCE.md`
- **Description:** Quick lookup guide for common patterns
- **Contents:**
  - Exception types reference
  - 10+ common patterns
  - What TO do vs. What NOT to do
  - Testing examples
  - CLI and logging best practices

## Exception Hierarchy

```
RepoSapiensError (base)
├── ConfigurationError
├── CredentialError
│   ├── CredentialNotFoundError
│   ├── CredentialFormatError
│   ├── BackendNotAvailableError
│   └── EncryptionError
├── GitOperationError
│   ├── NotGitRepositoryError
│   ├── NoRemotesError
│   ├── MultipleRemotesError
│   ├── InvalidGitUrlError
│   └── UnsupportedHostError
├── TemplateError
├── WorkflowError
└── ExternalServiceError
```

## Modified Files

### Core Modules
1. **automation/main.py** - CLI error handling
2. **automation/config/settings.py** - Configuration error handling
3. **automation/providers/gitea_rest.py** - Fixed bare except clause
4. **automation/webhook_server.py** - Webhook error handling

### Exception Modules
1. **automation/credentials/exceptions.py** - Inherits from base
2. **automation/git/exceptions.py** - Inherits from base

## Common Usage Patterns

### Pattern 1: Catch Specific Errors
```python
from automation.exceptions import ConfigurationError

try:
    config = load_config(path)
except ConfigurationError as e:
    print(f"Error: {e.message}")
```

### Pattern 2: Catch All App Errors
```python
from automation.exceptions import RepoSapiensError

try:
    do_work()
except RepoSapiensError as e:
    log.error("work_failed", error=e.message, exc_info=True)
```

### Pattern 3: Preserve Exception Chain
```python
try:
    load_config(path)
except FileNotFoundError as e:
    raise ConfigurationError(f"Not found: {path}") from e
```

### Pattern 4: CLI Error Handling
```python
@cli.command()
def my_command():
    try:
        do_work()
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted", err=True)
        sys.exit(130)
```

## Exit Codes

- **0** - Success
- **1** - Expected error (configuration, credentials, workflow)
- **2** - CLI usage error (handled by Click)
- **130** - User interruption (SIGINT/Ctrl+C)

## Log Levels

- **DEBUG** - Expected error conditions, full tracebacks
- **INFO** - Normal operation milestones
- **WARNING** - Unexpected but non-critical conditions
- **ERROR** - Errors requiring attention

## HTTP Status Codes

- **400** - Bad request (missing data)
- **422** - Unprocessable entity (validation error)
- **500** - Internal server error (unexpected)

## Key Principles

1. **Never bare except** - Always specify exception types
2. **Preserve chains** - Use `raise ... from e` for context
3. **Be helpful** - Messages explain what went wrong and how to fix it
4. **Log properly** - Use DEBUG for expected, ERROR for unexpected
5. **Exit cleanly** - Use proper exit codes

## Testing Error Handling

```python
import pytest
from automation.exceptions import ConfigurationError

def test_missing_config():
    with pytest.raises(ConfigurationError, match="not found"):
        load_config("nonexistent.yaml")
```

## Recommended Next Steps

1. Add error handling to remaining subsystems:
   - `automation/templates/` → TemplateError
   - `automation/engine/` → WorkflowError
   - `automation/learning/` → Custom errors

2. Add comprehensive error handling tests

3. Monitor production for error patterns

4. Refine error messages based on user feedback

## Document Map

| Document | Purpose | Audience |
|----------|---------|----------|
| ERROR_HANDLING.md | Comprehensive guide | Developers implementing error handling |
| ERROR_HANDLING_QUICK_REFERENCE.md | Quick lookup | Developers using the system |
| ERROR_HANDLING_IMPLEMENTATION.md | Implementation details | Code reviewers, maintainers |
| automation/exceptions.py | Code reference | All developers |

## Support

For questions about error handling:
1. Check the quick reference guide
2. Read the full ERROR_HANDLING.md guide
3. Review the implementation report
4. Check exception docstrings in automation/exceptions.py

---

**Last Updated:** 2025-12-23
**Status:** Production Ready
