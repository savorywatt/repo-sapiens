# Structured Logging Guide for repo-sapiens

This document explains how to use the structured logging system in repo-sapiens, which uses `structlog` for consistent, production-ready logging.

## Overview

repo-sapiens uses `structlog` for structured logging, which provides:

- **Structured logging**: Log as dictionaries with typed fields, not plain text
- **Context propagation**: Automatically includes request IDs, user info, etc. in all logs
- **Flexible output**: Human-readable console output in development, JSON in production
- **Security**: Automatic redaction of sensitive data (tokens, passwords, etc.)
- **Performance**: Lazy evaluation and efficient processors

## Configuration

### Basic Setup

```python
from repo_sapiens import configure_logging, get_logger

# Initialize logging at application startup
configure_logging(level="INFO", json_logs=False)

# Get a logger
logger = get_logger(__name__)
```

### Log Levels

Use the appropriate log level for different types of messages:

- **DEBUG**: Detailed diagnostic information
  ```python
  logger.debug("variable_state", variable_name="x", value=42)
  ```

- **INFO**: General informational messages about application flow
  ```python
  logger.info("processing_started", issue_id=123, repository="owner/repo")
  ```

- **WARNING**: Warning messages for potentially problematic situations
  ```python
  logger.warning("deprecated_feature", feature="old_api", replacement="new_api")
  ```

- **ERROR**: Error messages when something goes wrong
  ```python
  logger.error("processing_failed", issue_id=123, error="timeout")
  ```

- **CRITICAL**: Critical errors that may cause application failure
  ```python
  logger.critical("database_unavailable", host="db.example.com")
  ```

## Common Patterns

### 1. Logging Function Entry/Exit

```python
def process_issue(issue_id: int) -> Result:
    logger = get_logger(__name__)
    logger.debug("processing_started", issue_id=issue_id)

    try:
        result = _do_processing(issue_id)
        logger.info("processing_completed", issue_id=issue_id, result_status="success")
        return result
    except Exception as e:
        logger.error("processing_failed", issue_id=issue_id, error=str(e))
        raise
```

### 2. Logging with Context

```python
from repo_sapiens import bind_context, clear_context

# Bind context for all subsequent logs in this request
bind_context(request_id="req-123", user_id="user-456")

logger.info("action_performed", action="issue_update")
# Automatically includes: request_id="req-123", user_id="user-456"

# Clean up after request
clear_context()
```

### 3. Logging Structured Data

```python
logger.info(
    "issue_processed",
    issue_id=42,
    repository="owner/repo",
    stage="planning",
    duration_ms=1234,
    success=True,
)
```

### 4. Logging Exceptions

```python
try:
    risky_operation()
except TimeoutError as e:
    logger.error(
        "operation_timeout",
        operation="git_clone",
        timeout_seconds=30,
        exc_info=True,  # Includes full traceback
    )
```

### 5. Performance Monitoring

```python
import time

start = time.time()
logger.debug("processing_started", stage="analysis")

# ... do work ...

duration = time.time() - start
logger.info("processing_completed", stage="analysis", duration_ms=int(duration * 1000))
```

### 6. Batch Operations

```python
issues = get_issues()
logger.info("batch_processing_started", total_issues=len(issues))

for i, issue in enumerate(issues, 1):
    try:
        process_issue(issue)
        logger.debug("issue_processed", issue_number=issue.number, progress=f"{i}/{len(issues)}")
    except Exception as e:
        logger.error("issue_failed", issue_number=issue.number, error=str(e))

logger.info("batch_processing_completed", total_issues=len(issues))
```

## Sensitive Data Handling

The logging system automatically redacts sensitive information:

### Automatically Redacted Patterns

- API tokens and keys
- Passwords
- Authentication headers
- Connection strings with credentials

### Examples

```python
# These are automatically redacted in logs:
logger.info("auth_attempt", password="secret123")
# Output: auth_attempt password=***REDACTED***

logger.info("api_call", api_token="sk-xyz...")
# Output: api_call api_token=***REDACTED***

logger.info("connection", url="https://user:pass@host:port")
# Output: connection url=https://***REDACTED***@host:port
```

## Output Formats

### Development (Human-Readable)

```python
configure_logging(level="DEBUG", json_logs=False)
```

Output:
```
2024-01-15 10:30:45 [INFO] repo_sapiens.core
  event='greeting_generated'
  name='World'
```

### Production (JSON)

```python
configure_logging(level="INFO", json_logs=True)
```

Output:
```json
{
  "event": "greeting_generated",
  "name": "World",
  "timestamp": "2024-01-15T10:30:45.123456+00:00",
  "log_level": "info"
}
```

## Best Practices

### 1. Use Event Names as First Argument

Event names should be lowercase with underscores (snake_case) and describe what happened:

```python
# Good
logger.info("issue_created", issue_id=123)
logger.error("database_connection_failed", host="db.example.com")

# Avoid
logger.info("Event!")
logger.error(f"Failed to connect to {host}")
```

### 2. Include Context for Debugging

Always include IDs and relevant context:

```python
# Good
logger.info("plan_started", plan_id="plan-001", repository="owner/repo")

# Less useful
logger.info("starting plan")
```

### 3. Log at Consistent Stages

Log at key stages of operations:

```python
logger.info("operation_started", operation="issue_analysis")
# ... do work ...
logger.debug("analyzing_description", description_length=500)
logger.debug("generating_plan", issue_type="bug")
logger.info("operation_completed", operation="issue_analysis", status="success")
```

### 4. Use Appropriate Data Types

Pass actual values, not stringified:

```python
# Good
logger.info("processing", count=42, duration_ms=1500, success=True)

# Avoid
logger.info("processing", count="42", duration_ms="1500", success="True")
```

### 5. Avoid Logging Large Objects

Log specific fields, not entire objects:

```python
# Good
logger.info("issue_processed", issue_id=issue.id, title=issue.title)

# Avoid
logger.info("issue_processed", issue=issue)  # Logs entire object
```

### 6. Use Contextual Binding for Correlated Logs

For operations that span multiple functions:

```python
@app.route("/issues/<int:issue_id>")
def handle_issue(issue_id):
    bind_context(issue_id=issue_id, request_id=get_request_id())

    result = process_issue(issue_id)

    clear_context()
    return result

def process_issue(issue_id):
    logger = get_logger(__name__)
    logger.info("step_1_complete")  # Automatically includes issue_id, request_id
    # ...
    logger.info("step_2_complete")  # Also includes context
```

## Integration Examples

### With Click CLI

```python
import click
from repo_sapiens import configure_logging, get_logger

@click.command()
@click.option("--log-level", default="INFO", help="Logging level")
def cli(log_level):
    configure_logging(level=log_level)
    logger = get_logger(__name__)
    logger.info("cli_started", log_level=log_level)
    # ... CLI logic ...
```

### With Async Code

```python
import asyncio
from repo_sapiens import get_logger, bind_context

async def process_issues(issues):
    logger = get_logger(__name__)
    tasks = []

    for issue in issues:
        tasks.append(process_one(issue.id))

    logger.info("batch_processing_started", count=len(issues))
    results = await asyncio.gather(*tasks)
    logger.info("batch_processing_completed", count=len(results))

    return results

async def process_one(issue_id):
    bind_context(issue_id=issue_id)
    logger = get_logger(__name__)
    logger.info("processing_started")
    # ... do async work ...
    logger.info("processing_completed")
```

### With Exception Handling

```python
from repo_sapiens import get_logger

logger = get_logger(__name__)

try:
    result = risky_operation()
except ValueError as e:
    logger.error(
        "validation_failed",
        error_type="ValueError",
        error_message=str(e),
        exc_info=True,  # Include full traceback
    )
except Exception as e:
    logger.critical(
        "unexpected_error",
        error_type=type(e).__name__,
        error_message=str(e),
        exc_info=True,
    )
    raise
```

## Testing with Logs

### Capturing Logs in Tests

```python
import pytest
from repo_sapiens import get_logger

def test_with_logs(caplog):
    logger = get_logger(__name__)

    logger.info("test_event", value=42)

    # Check logs were emitted
    assert "test_event" in caplog.text
    assert "value=42" in caplog.text
```

### Mocking Logs in Tests

```python
from unittest.mock import patch, MagicMock

def test_error_logging():
    with patch("repo_sapiens.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Run code that uses logger
        my_function()

        # Verify logging calls
        mock_logger.error.assert_called()
        mock_logger.error.assert_called_with("error_event", ...)
```

## Migration from print() and logging

### Before (with print)

```python
def process(item):
    print(f"Processing item {item.id}")
    result = _process_item(item)
    print(f"Completed: {item.id}")
    return result
```

### After (with structlog)

```python
def process(item):
    logger = get_logger(__name__)
    logger.info("processing_started", item_id=item.id)
    result = _process_item(item)
    logger.info("processing_completed", item_id=item.id)
    return result
```

### Before (with stdlib logging)

```python
import logging

logger = logging.getLogger(__name__)

def process(item):
    logger.info(f"Processing item {item.id}")
    result = _process_item(item)
    logger.info(f"Completed: {item.id}")
    return result
```

### After (with structlog)

```python
from repo_sapiens import get_logger

logger = get_logger(__name__)

def process(item):
    logger.info("processing_started", item_id=item.id)
    result = _process_item(item)
    logger.info("processing_completed", item_id=item.id)
    return result
```

## Performance Considerations

### 1. Use Debug Logs for Verbose Output

```python
# Debug logs are only processed if DEBUG level is enabled
logger.debug("detailed_state", state_var=expensive_function())
```

### 2. Avoid String Formatting

```python
# Good - evaluated only if log level is DEBUG
logger.debug("value", x=x, y=y)

# Avoid - always evaluates f-string
logger.debug(f"value x={x} y={y}")
```

### 3. Context Variables are Efficient

```python
# Efficient - set once, used in all subsequent logs
bind_context(request_id="req-123")
logger.info("event1")
logger.info("event2")  # Also includes request_id
```

## Troubleshooting

### No Logs Appearing

1. Ensure `configure_logging()` is called before using logger
2. Check log level isn't too high (try DEBUG)
3. Verify stderr isn't redirected

### Too Many Logs

1. Increase log level to WARNING or ERROR
2. Remove DEBUG log calls from hot paths
3. Disable logs for noisy modules:
   ```python
   logging.getLogger("module.to.silence").setLevel(logging.WARNING)
   ```

### Sensitive Data Not Redacted

1. Check redaction patterns in `logging_config.py`
2. Add custom pattern if needed
3. Never store secrets in variable names

## API Reference

### `configure_logging(level, json_logs, context)`

Configure structured logging at application startup.

**Parameters:**
- `level` (str): Logging level - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `json_logs` (bool): Output JSON format for production
- `context` (dict): Initial context variables

### `get_logger(name)`

Get a configured logger instance.

**Parameters:**
- `name` (str, optional): Logger name, defaults to caller's module name

**Returns:**
- `structlog.stdlib.BoundLogger`: Configured logger

### `bind_context(**kwargs)`

Bind context variables to all subsequent logs.

**Parameters:**
- `**kwargs`: Context key-value pairs

### `clear_context()`

Clear all bound context variables.

### `unbind_context(*keys)`

Remove specific context variables.

**Parameters:**
- `*keys`: Names of context variables to remove
