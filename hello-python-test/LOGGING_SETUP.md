# Structured Logging Implementation for repo-sapiens

## Overview

This document summarizes the comprehensive structured logging setup implemented for repo-sapiens using `structlog`.

## What Was Implemented

### 1. Core Logging Module: `src/repo_sapiens/logging_config.py`

A production-ready logging configuration module providing:

- **`configure_logging(level, json_logs, context)`**: Initialize structured logging with support for multiple log levels and output formats
- **`get_logger(name)`**: Get a configured logger instance
- **`bind_context(**kwargs)`**: Bind context variables (request ID, user ID, etc.) to all subsequent logs
- **`clear_context()`**: Clear all bound context variables
- **`unbind_context(*keys)`**: Remove specific context variables
- **`redact_sensitive_data()`**: Automatic redaction of sensitive information (tokens, passwords, connection strings)

### 2. Key Features

#### Structured Logging
- Log as dictionaries with typed fields instead of plain text strings
- Supports arbitrary key-value pairs for context
- Thread-safe context propagation using contextvars

#### Flexible Output
- **Development**: Human-readable console output with colors and better tracebacks
- **Production**: JSON output for machine parsing and centralized logging systems

#### Security
- Automatic redaction of:
  - API tokens and keys
  - Passwords
  - Bearer tokens
  - Connection strings with credentials
  - Pattern-based detection with case-insensitive matching

#### Standard Log Levels
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Warning messages for potentially problematic situations
- ERROR: Error messages when operations fail
- CRITICAL: Critical errors that may cause application failure

### 3. Updated Files

#### Core Package (`src/repo_sapiens/`)
- **`__init__.py`**: Exports logging utilities for easy import
- **`core.py`**: Updated from print() to structured logging
- **`logging_config.py`**: New comprehensive logging configuration module

#### Configuration
- **`pyproject.toml`**: Added structlog and pytest-asyncio dependencies

#### Tests
- **`tests/test_logging.py`**: Comprehensive test suite with 40+ tests covering:
  - Configuration and initialization
  - Log level handling
  - Sensitive data redaction
  - Context binding and clearing
  - Output formatting
  - Edge cases and real-world scenarios

#### Documentation
- **`docs/LOGGING.md`**: Complete logging guide with:
  - Configuration examples
  - Common patterns
  - Best practices
  - Integration examples (CLI, async, exceptions)
  - Testing with logs
  - Migration guide from print() and stdlib logging
  - Troubleshooting

#### Examples
- **`examples/cli_with_logging.py`**: Complete CLI example using Click with structured logging
- **`examples/async_with_logging.py`**: Async code patterns with structured logging

## Usage Quick Start

### Basic Configuration

```python
from repo_sapiens import configure_logging, get_logger

# Initialize logging at application startup
configure_logging(level="INFO", json_logs=False)

# Get a logger
logger = get_logger(__name__)

# Log events
logger.info("action_performed", issue_id=42, status="completed")
```

### With Context

```python
from repo_sapiens import bind_context, clear_context, get_logger

# Bind context for correlated logs
bind_context(request_id="req-123", user_id="user-456")

logger = get_logger(__name__)
logger.info("operation_started")  # Automatically includes context

# Clean up
clear_context()
```

### Sensitive Data

```python
logger.info(
    "auth_attempt",
    username="user@example.com",
    password="secretpass123",  # Automatically redacted in output
)
```

## Architecture

### Log Processing Pipeline

```
Event Dictionary
    ↓
[Processors]
    ├─ add_log_level
    ├─ add_logger_name
    ├─ TimeStamper (ISO format)
    ├─ StackInfoRenderer
    ├─ format_exc_info
    ├─ redact_sensitive_data ← Security
    ├─ JSONRenderer or ConsoleRenderer ← Output
    ↓
Stderr/File
```

### Context Propagation

```
bind_context(request_id="123")
    ↓
contextvars.ContextVar
    ↓
Available in all logs within context
    ↓
clear_context()
```

## Dependencies Added

### Main Dependencies
- `structlog>=24.0.0`: Structured logging library

### Dev Dependencies
- `pytest-asyncio>=0.21.0`: For async test support

## Testing

Run the comprehensive test suite:

```bash
# Run all logging tests
pytest tests/test_logging.py -v

# Run with coverage
pytest tests/test_logging.py --cov=repo_sapiens.logging_config

# Run specific test class
pytest tests/test_logging.py::TestSensitiveDataRedaction -v
```

### Test Coverage

The test suite includes:
- Configuration and initialization (5 tests)
- Logger retrieval (3 tests)
- Sensitive data redaction (7 tests)
- Context binding and clearing (5 tests)
- Logger integration (7 tests)
- Log level filtering (2 tests)
- Output formats (3 tests)
- Edge cases (6 tests)
- Real-world scenarios (5 tests)

## Integration Points

### CLI Applications
See `examples/cli_with_logging.py` for a complete example with Click:
- Initialize logging from --log-level flag
- Bind operation context
- Handle errors with full traceback logging

### Async Code
See `examples/async_with_logging.py` for patterns in:
- Concurrent operations with context per task
- Multi-stage pipelines
- Exception handling in async code

### Django/FastAPI
Can integrate by:
1. Calling `configure_logging()` at application startup
2. Using `bind_context()` in middleware for request ID propagation
3. Getting logger in views/handlers with `get_logger(__name__)`

## Best Practices

### 1. Event Names
Use lowercase snake_case for event names:
```python
logger.info("issue_created", issue_id=123)  # Good
logger.info("Event!")  # Avoid
```

### 2. Include Context
Always include relevant IDs and context:
```python
logger.info("processing_started", plan_id="plan-001", repository="owner/repo")
```

### 3. Log at Key Stages
```python
logger.info("operation_started")
# ... work ...
logger.debug("step_complete", step="analysis")
logger.info("operation_completed", status="success")
```

### 4. Use Appropriate Levels
- DEBUG: Details you need when debugging
- INFO: Important milestones
- WARNING: Potentially problematic situations
- ERROR: Recoverable errors
- CRITICAL: Fatal errors

### 5. Avoid Logging Large Objects
```python
logger.info("issue_processed", issue_id=issue.id, title=issue.title)  # Good
logger.info("issue_processed", issue=issue)  # Avoid - logs entire object
```

## Production Deployment

### Environment-Specific Configuration

```python
import os

log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("JSON_LOGS", "false").lower() == "true"

configure_logging(level=log_level, json_logs=json_logs)
```

### Centralized Logging

With JSON output, logs can be aggregated using:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- CloudWatch
- Datadog
- Splunk
- Any JSON-compatible log aggregation service

### Performance

- Lazy evaluation: Logs only rendered if level is enabled
- Context variables are efficient and thread-safe
- No blocking I/O in hot paths
- Suitable for high-throughput applications

## Migration Path

### From print()
```python
# Before
print(f"Processing {issue_id}")

# After
logger.info("processing_started", issue_id=issue_id)
```

### From stdlib logging
```python
# Before
logging.info(f"Processing {issue_id}")

# After
from repo_sapiens import get_logger
logger = get_logger(__name__)
logger.info("processing_started", issue_id=issue_id)
```

## Files Overview

```
repo-sapiens/
├── src/repo_sapiens/
│   ├── __init__.py              # Exports logging utilities
│   ├── logging_config.py        # Core logging configuration
│   └── core.py                  # Updated with structured logging
├── tests/
│   └── test_logging.py          # Comprehensive test suite (40+ tests)
├── examples/
│   ├── cli_with_logging.py      # CLI example
│   └── async_with_logging.py    # Async example
├── docs/
│   └── LOGGING.md               # Complete logging guide
├── LOGGING_SETUP.md             # This file
└── pyproject.toml               # Updated with dependencies
```

## Next Steps

1. **Review**: Check `docs/LOGGING.md` for complete usage guide
2. **Integrate**: Use `get_logger()` and `bind_context()` in new code
3. **Migrate**: Update existing print() and logging calls
4. **Test**: Run test suite and verify logs in development
5. **Deploy**: Configure JSON logs and aggregation for production

## Support

For questions or issues:
1. Check `docs/LOGGING.md` for common patterns
2. Review examples in `examples/` directory
3. Run tests to verify setup
4. Check `logging_config.py` for implementation details

## Technical Details

### Sensitive Data Patterns

Automatically detected and redacted:
- `api_token`, `api_key`, `apikey`: Any case combination
- `password`: Any case combination
- `secret`: Any case combination
- `bearer`: Authentication tokens
- `https://user:pass@host`: Connection strings

### Log Output Examples

**Development (Console)**
```
2024-01-15 10:30:45 [INFO] repo_sapiens.core
  event='greeting_generated'
  name='World'
```

**Production (JSON)**
```json
{
  "event": "greeting_generated",
  "name": "World",
  "timestamp": "2024-01-15T10:30:45.123456+00:00",
  "log_level": "info"
}
```

---

**Implementation Date**: 2024-12-23
**Structlog Version**: 24.0.0+
**Python Version**: 3.8+
