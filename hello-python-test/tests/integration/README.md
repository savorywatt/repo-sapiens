# Integration Test Suite: End-to-End Workflows

Comprehensive integration tests for complete automation workflows including issue processing, credential management, Git operations, template rendering, and error recovery.

## Overview

The integration test suite (`test_workflow_e2e.py`) provides 18 comprehensive tests covering:

- **Complete Workflows**: Issue → Analysis → Planning → Implementation → Merge
- **Credential Management**: Resolution, environment overrides, secret handling
- **Git Operations**: Branch creation, commits, pull requests
- **Template Rendering**: Variable substitution, file generation
- **Configuration**: File loading, environment variable precedence
- **Error Scenarios**: Recovery, rollback, validation
- **State Management**: Persistence, recovery, cleanup
- **Concurrency**: Multi-workflow execution, isolation
- **Advanced Features**: Large file batches, idempotency, logging

## Test Structure

### Fixtures (Core Infrastructure)

#### API Mocks
- **mock_gitea_api**: Mocked Gitea API client with common operations
- **mock_claude_api**: Mocked Claude API for analysis and planning

#### Storage
- **test_config_dir**: Temporary configuration directory
- **test_state_dir**: State management directory
- **test_config**: Standard test configuration dict

#### Managers
- **mock_git_state_manager**: Simple state persistence manager
- **workflow_engine**: Complete workflow orchestration engine

### Test Categories

#### 1. Complete Workflows (test_complete_issue_to_merge_workflow)
Tests the full workflow from issue discovery to merged PR:
- Fetches issue from Git provider
- Analyzes issue with Claude
- Generates implementation plan
- Creates feature branch
- Creates pull request
- Tracks state through all stages

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_issue_to_merge_workflow(
    workflow_engine, mock_gitea_api, mock_claude_api
):
    # Setup API responses
    mock_gitea_api.get_issue.return_value = {...}
    mock_claude_api.analyze_issue.return_value = {...}

    # Execute workflow
    result = await workflow_engine.process_issue(42)

    # Verify completion and state transitions
    assert result["status"] == "completed"
    assert all(stage in result["state"]["stages"] for stage in [
        "fetch", "analysis", "planning", "implementation", "merge"
    ])
```

#### 2. Credential Management (test_credential_resolution_flow)
Tests credential loading from multiple sources:
- Config file credentials
- Environment variable overrides
- Precedence rules (env > config)
- Secret key validation

#### 3. Git Operations (test_git_operations_workflow)
Tests complete Git workflow:
- Branch creation
- Multiple commits
- Pull request creation
- Merge operations
- State verification

#### 4. Template Rendering (test_template_rendering_and_application)
Tests template processing:
- Template parsing and rendering
- Variable substitution
- File generation with directory structure
- Content verification

#### 5. Configuration (test_configuration_loading_from_file_and_env)
Tests configuration system:
- YAML file parsing
- Environment variable loading
- Config merging with precedence
- Type conversion and validation

#### 6. Error Recovery (test_error_recovery_scenario)
Tests error handling:
- API failure detection
- State preservation during errors
- Error message clarity
- Recovery options

#### 7. Rollback (test_rollback_on_partial_failure)
Tests partial failure recovery:
- Partial state cleanup
- Resource deallocation
- State consistency after failure
- Error tracking

#### 8. Concurrency (test_concurrent_workflow_execution)
Tests parallel workflow execution:
- Multiple workflows running simultaneously
- State isolation between workflows
- No race conditions
- Proper async handling

#### 9. State Persistence (test_state_persistence_and_recovery)
Tests state management:
- Serialization to JSON files
- Recovery from disk
- Consistency verification
- Timestamp tracking

#### 10. Resource Cleanup (test_cleanup_of_temporary_resources)
Tests temporary resource management:
- Workspace creation
- File cleanup on success
- File preservation on failure (for debugging)
- Directory removal

#### 11. Multi-Stage Validation (test_multi_stage_workflow_with_validation)
Tests validation at each workflow stage:
- Pre-stage validation
- Stage-specific error handling
- Validation failure recovery
- Data integrity checks

#### 12. Logging & Tracing (test_workflow_logging_and_tracing)
Tests comprehensive logging:
- Stage transition logging
- API call tracing
- Error logging
- Appropriate log levels

#### 13. Large Batch Processing (test_large_workflow_with_many_files)
Tests handling of large-scale operations:
- Batch processing of 100+ files
- Memory efficiency
- API rate limiting handling
- Performance under load

#### 14. Idempotency (test_workflow_idempotency)
Tests safe retry scenarios:
- Running same workflow twice yields same results
- No duplicate resource creation
- Consistent state updates
- Safe to retry failed workflows

#### 15. Network Timeout (test_network_timeout_handling)
Tests timeout scenarios:
- TimeoutError exception handling
- Appropriate error messages
- Retry logic validation

#### 16. Invalid Config (test_invalid_configuration_handling)
Tests configuration validation:
- Missing required field detection
- Type validation
- Clear error messages
- Early failure detection

#### 17. Rate Limiting (test_api_rate_limiting)
Tests API rate limit handling:
- Rate limit error recognition
- Exponential backoff strategy
- Eventual success after backoff
- Request queuing

#### 18. Partial Failure Recovery (test_partial_failure_recovery)
Tests batch operation resilience:
- Some operations succeed despite failures
- Partial results preservation
- Recovery continuation
- Detailed failure tracking

## Running the Tests

### Run All Integration Tests
```bash
pytest tests/integration/test_workflow_e2e.py -v
```

### Run Specific Test Category
```bash
pytest tests/integration/test_workflow_e2e.py::test_complete_issue_to_merge_workflow -v
```

### Run with Coverage
```bash
pytest tests/integration/test_workflow_e2e.py --cov=src --cov-report=html
```

### Run Concurrency Tests
```bash
pytest tests/integration/test_workflow_e2e.py::test_concurrent_workflow_execution -v
```

### Run Large-Scale Tests
```bash
pytest tests/integration/test_workflow_e2e.py::test_large_workflow_with_many_files -v
```

### Mark-Based Selection
```bash
# All integration tests
pytest -m integration

# Exclude slow tests
pytest -m "not slow"
```

## Test Data & Fixtures

### Configuration Example
```python
test_config = {
    "git_provider": {
        "provider_type": "gitea",
        "base_url": "http://localhost:3000",
        "api_token": "test_token_secret",
    },
    "repository": {
        "owner": "test_owner",
        "name": "test_repo",
    },
    "agent_provider": {
        "provider_type": "claude",
        "model": "claude-opus-4.5-20251101",
        "api_key": "test_api_key",
    },
    "state_dir": "/tmp/test_state",
    "default_poll_interval": 60,
}
```

### Sample State Structure
```json
{
    "workflow_id": "issue-42",
    "issue_id": 42,
    "status": "completed",
    "stages": {
        "fetch": {
            "status": "completed",
            "issue": {"id": 42, "title": "Fix bug"}
        },
        "analysis": {
            "status": "completed",
            "analysis": {"analysis": "OAuth integration issue"}
        },
        "planning": {
            "status": "completed",
            "plan": {"steps": [{"name": "analyze"}]}
        },
        "implementation": {
            "status": "completed",
            "branch": {"name": "fix/issue-42"}
        },
        "merge": {
            "status": "completed",
            "pull_request": {"id": 1, "url": "http://..."}
        }
    },
    "updated_at": "2024-01-15T10:30:45.123456+00:00"
}
```

## Mock API Responses

### Gitea API
```python
mock_gitea_api.get_issue.return_value = {
    "id": 42,
    "number": 42,
    "title": "Fix critical bug",
    "body": "Detailed issue description",
}

mock_gitea_api.create_branch.return_value = {
    "name": "fix/issue-42",
    "commit": "abc123def456",
}

mock_gitea_api.create_pull_request.return_value = {
    "id": 1,
    "number": 1,
    "state": "open",
    "mergeable": True,
    "url": "http://localhost:3000/pr/1",
}
```

### Claude API
```python
mock_claude_api.analyze_issue.return_value = {
    "title": "Fix authentication",
    "analysis": "OAuth provider integration failure",
    "approach": "Update OAuth client configuration",
}

mock_claude_api.generate_implementation_plan.return_value = {
    "steps": [
        {"name": "analyze", "description": "Analyze OAuth flow"},
        {"name": "implement", "description": "Fix OAuth integration"},
        {"name": "test", "description": "Test OAuth flow"},
    ]
}
```

## Async Testing with pytest-asyncio

All tests use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow(workflow_engine):
    result = await workflow_engine.process_issue(42)
    assert result["status"] == "completed"
```

Configuration in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
asyncio_default_fixture_loop_scope = "function"
```

## Key Testing Patterns

### 1. State Verification
```python
# Save state
await workflow_engine.state.save_state("workflow-1", state)

# Load and verify
loaded = await workflow_engine.state.load_state("workflow-1")
assert loaded["status"] == "completed"
```

### 2. Mock API Setup
```python
mock_api.method_name.return_value = {"expected": "response"}
mock_api.method_name.side_effect = Exception("error")
```

### 3. Concurrent Execution
```python
results = await asyncio.gather(
    workflow_engine.process_issue(1),
    workflow_engine.process_issue(2),
    workflow_engine.process_issue(3),
)
assert all(r["status"] == "completed" for r in results)
```

### 4. Error Testing
```python
with pytest.raises(ValueError, match="expected pattern"):
    await function_that_fails()
```

### 5. Temporary Files
```python
workspace = await rm.create_temp_workspace("workflow-1")
assert workspace.exists()
await rm.cleanup()
assert not workspace.exists()
```

## Continuous Integration

These tests are designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Integration Tests
  run: pytest tests/integration/test_workflow_e2e.py -v --cov --cov-report=xml
```

## Performance Characteristics

- **Fast Execution**: All 18 tests complete in < 1 second
- **Low Memory**: Minimal temporary file creation
- **Isolated**: No external dependencies required
- **Repeatable**: Deterministic, no flakiness

## Troubleshooting

### Test Fails Due to Temporary Directory
```bash
# Ensure /tmp is writable
ls -ld /tmp
# Should show: drwxrwxrwt
```

### Mock Not Applied
- Verify `@patch` decorator targets correct import path
- Check AsyncMock vs MagicMock usage (async vs sync)
- Confirm return_value is set before test execution

### State File Not Found
- Verify state_dir fixture is properly initialized
- Check that workflow saves state before test accesses it
- Inspect JSON structure for correct workflow_id key

### Async Test Timeout
- Increase timeout: `@pytest.mark.timeout(30)`
- Check for infinite loops in mocked functions
- Verify AsyncMock is returning awaitable

## Extension Points

To add new integration tests:

1. **Create fixture** for new external service/component
2. **Define test scenario** with clear setup, execute, verify steps
3. **Use existing patterns** for mocking and assertions
4. **Document test intent** in docstring
5. **Mark with markers** (`@pytest.mark.integration`, `@pytest.mark.asyncio`)

Example template:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_feature(workflow_engine, mock_api):
    """Test new feature with clear description."""
    # Setup
    mock_api.method.return_value = expected_response

    # Execute
    result = await workflow_engine.new_feature()

    # Verify
    assert result["status"] == "success"
    mock_api.method.assert_called_once()
```

## Dependencies

- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-xdist**: Parallel execution (optional)

Install with:
```bash
pip install -e ".[dev]"
```

## Files

- `/tests/integration/test_workflow_e2e.py`: Main test module (18 tests)
- `/tests/integration/__init__.py`: Package initialization
- `/tests/integration/README.md`: This file

## Related Documentation

- Test summary: `TESTING_GUIDE.md`
- Project structure: `PROJECT_STRUCTURE.md`
- Configuration: `automation/config/settings.py`
- Workflow engine: `automation/engine/`
