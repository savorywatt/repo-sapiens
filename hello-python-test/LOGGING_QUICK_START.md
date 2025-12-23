# Structured Logging Quick Start Guide

Get up and running with structured logging in repo-sapiens in 5 minutes.

## Installation

The logging system is automatically included with repo-sapiens:

```bash
pip install repo-sapiens[dev]
```

## Basic Usage

### 1. Initialize Logging

At application startup:

```python
from repo_sapiens import configure_logging, get_logger

# Initialize logging
configure_logging(level="INFO", json_logs=False)

# Get a logger
logger = get_logger(__name__)
```

### 2. Log Events

Log structured events with typed fields:

```python
logger.info("issue_processed", issue_id=42, status="completed", duration_ms=1234)
```

### 3. Use Context for Correlated Logs

Bind context that automatically appears in all logs:

```python
from repo_sapiens import bind_context, clear_context

bind_context(request_id="req-123", user_id="user-456")
logger.info("action_performed")  # Includes request_id and user_id
clear_context()
```

## Common Patterns

### CLI with Log Level Flag

```python
import click
from repo_sapiens import configure_logging, get_logger

@click.command()
@click.option("--log-level", default="INFO")
def main(log_level):
    configure_logging(level=log_level)
    logger = get_logger(__name__)
    logger.info("app_started", log_level=log_level)
    # ... your code ...
```

### Function Entry/Exit

```python
def process_issue(issue_id: int):
    logger = get_logger(__name__)
    logger.debug("processing_started", issue_id=issue_id)

    try:
        # ... process ...
        logger.info("processing_completed", issue_id=issue_id)
    except Exception as e:
        logger.error("processing_failed", issue_id=issue_id, error=str(e))
        raise
```

### Batch Operations

```python
logger.info("batch_started", total=100)
for i, item in enumerate(items):
    logger.debug("processing", item_number=i+1)
    # ... process item ...
logger.info("batch_completed", processed=100, duration_ms=1500)
```

## Log Levels

Use these log levels (all lowercase in code):

```python
logger.debug("detailed_info", variable=value)      # Development debugging
logger.info("important_event", action="started")   # Normal operations
logger.warning("deprecated_api", old_param="x")    # Warnings
logger.error("operation_failed", reason="timeout") # Recoverable errors
logger.critical("system_down", component="db")     # Fatal errors
```

## Sensitive Data

Automatically redacted:

```python
# These are redacted in output:
logger.info("login", password="secret123")          # ✓ Redacted
logger.info("auth", api_token="sk-12345")          # ✓ Redacted
logger.info("connect", url="user:pass@host")       # ✓ Redacted
```

## Output Formats

### Development (Human-Readable)

```python
configure_logging(level="DEBUG", json_logs=False)
```

Console output with colors:
```
2024-01-15 10:30:45 [INFO] module.name
  event='action'
  result='success'
```

### Production (JSON)

```python
configure_logging(level="INFO", json_logs=True)
```

JSON output for log aggregation:
```json
{"event":"action","result":"success","timestamp":"2024-01-15T10:30:45Z"}
```

## Testing

Capture logs in tests:

```python
def test_logging(caplog):
    from repo_sapiens import get_logger

    logger = get_logger(__name__)
    logger.info("test_event", value=42)

    assert "test_event" in caplog.text
    assert "value=42" in caplog.text
```

## Tips & Tricks

### 1. Use Descriptive Event Names
```python
# Good
logger.info("issue_created", issue_id=123)

# Avoid
logger.info("created")
```

### 2. Always Include IDs
```python
logger.info("processing_started", plan_id="plan-001", repository="owner/repo")
```

### 3. Log at Key Stages
```python
logger.info("operation_started")
# ... work ...
logger.info("operation_completed", status="success")
```

### 4. Use Numbers, Not Strings
```python
# Good
logger.info("processed", count=42, duration_ms=1500)

# Avoid
logger.info("processed", count="42", duration="1500ms")
```

## Configuration Examples

### Development Setup
```python
configure_logging(
    level="DEBUG",
    json_logs=False,
    context={"environment": "development"}
)
```

### Production Setup
```python
configure_logging(
    level="INFO",
    json_logs=True,
    context={"environment": "production", "version": "1.0.0"}
)
```

### With Initial Context
```python
configure_logging(
    level="INFO",
    json_logs=False,
    context={"app_id": "my-app", "hostname": "server-1"}
)
```

## Troubleshooting

### No Logs Appearing
1. Check that `configure_logging()` is called
2. Try setting level to DEBUG
3. Verify stderr is not redirected

### Too Many Logs
1. Increase log level (INFO, WARNING, etc.)
2. Remove DEBUG logs from hot paths
3. Silence specific modules:
   ```python
   import logging
   logging.getLogger("noisy_module").setLevel(logging.WARNING)
   ```

### Sensitive Data Not Redacted
Check the field name contains: password, token, secret, key, auth, etc.

## API Reference

### `configure_logging(level, json_logs, context)`
Initialize structured logging

### `get_logger(name)`
Get a logger for the current module

### `bind_context(**kwargs)`
Add context variables to all logs

### `clear_context()`
Remove all context variables

### `unbind_context(*keys)`
Remove specific context variables

## Next Steps

1. **Read Full Guide**: See `docs/LOGGING.md` for comprehensive documentation
2. **Check Examples**: Look at `examples/cli_with_logging.py` and `examples/async_with_logging.py`
3. **Run Tests**: `pytest tests/test_logging.py -v`
4. **Integrate**: Use in your code with `get_logger()` and `bind_context()`

## Support

- **Documentation**: `docs/LOGGING.md`
- **Examples**: `examples/` directory
- **Tests**: `tests/test_logging.py`
- **Source**: `src/repo_sapiens/logging_config.py`
