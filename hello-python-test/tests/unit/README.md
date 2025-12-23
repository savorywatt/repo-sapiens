# CLI Command Tests

Comprehensive test suite for the automation CLI commands in `automation/main.py`.

## Overview

This test suite provides thorough coverage of CLI functionality including:

- **Basic CLI operations** (help, version, config loading)
- **Command execution** with valid and invalid arguments
- **Error handling** and user-friendly messages
- **Exit codes** validation
- **Configuration management**
- **Logging integration**
- **Async operations** and state management
- **Provider integration** (Git, AI agents)
- **Edge cases** and error conditions

## Test Files

### `test_cli_main.py`
Main CLI command tests covering:

- **TestCliBasics**: Basic CLI functionality (help, version, config)
- **TestProcessIssueCommand**: `process-issue` command tests
- **TestProcessAllCommand**: `process-all` command tests
- **TestProcessPlanCommand**: `process-plan` command tests
- **TestDaemonCommand**: `daemon` command tests
- **TestListPlansCommand**: `list-plans` command tests
- **TestShowPlanCommand**: `show-plan` command tests
- **TestConfigurationErrors**: Configuration loading error handling
- **TestOutputFormatting**: Output message formatting
- **TestEdgeCases**: Edge cases and boundary conditions
- **TestContextManagement**: Click context handling
- **TestExitCodes**: Exit code validation
- **TestLoggingIntegration**: Logging configuration

### `test_cli_commands.py`
Integration and advanced tests covering:

- **TestOrchestratorCreation**: Orchestrator initialization
- **TestProcessSingleIssueFunction**: `_process_single_issue` async function
- **TestProcessAllIssuesFunction**: `_process_all_issues` async function
- **TestProcessPlanFunction**: `_process_plan` async function
- **TestDaemonModeFunction**: `_daemon_mode` async function
- **TestListActivePlansFunction**: `_list_active_plans` async function
- **TestShowPlanStatusFunction**: `_show_plan_status` async function
- **TestIntegrationScenarios**: Full workflow integration
- **TestProviderIntegration**: Git and Agent provider integration
- **TestStateManagement**: State manager interactions
- **TestErrorMessages**: Error message quality
- **TestCommandOutputs**: Output formatting and content
- **TestAsyncErrorHandling**: Async error handling and recovery
- **TestEdgeCasesAdvanced**: Advanced edge cases

## Test Coverage

### Commands Tested

1. **process-issue**
   - Success path with valid issue number
   - Missing required `--issue` argument
   - Invalid issue number format
   - Non-existent issues
   - Edge cases (zero, large numbers)

2. **process-all**
   - Processing without tag filter
   - Processing with tag filter
   - Special characters in tags
   - Empty tags

3. **process-plan**
   - Success path with valid plan ID
   - Missing required `--plan-id` argument
   - Non-existent plans
   - UUID-style plan IDs

4. **daemon**
   - Default polling interval (60s)
   - Custom polling intervals
   - Invalid intervals
   - Keyboard interrupt handling
   - Processing errors

5. **list-plans**
   - Empty plan list
   - Multiple plans
   - Missing state files
   - Large number of plans

6. **show-plan**
   - Successful plan status display
   - Non-existent plans
   - Plans with empty stages/tasks
   - Plans with complex structures

### Global Options Tested

- **--config**: Custom config file paths
- **--log-level**: DEBUG, INFO, WARNING, ERROR levels

## Running Tests

### Run all CLI tests
```bash
pytest tests/unit/test_cli_main.py tests/unit/test_cli_commands.py -v
```

### Run specific test class
```bash
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand -v
```

### Run specific test
```bash
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand::test_process_issue_success -v
```

### Run with coverage
```bash
pytest tests/unit/ --cov=automation --cov-report=html --cov-report=term
```

### Run with markers
```bash
pytest tests/unit/ -m asyncio -v
```

### Run in watch mode (requires pytest-watch)
```bash
ptw tests/unit/
```

## Test Fixtures

### Provided by `conftest.py`

- **cli_runner**: Click CliRunner instance for testing
- **tmp_config_dir**: Temporary directory for config files
- **tmp_state_dir**: Temporary directory for state files
- **sample_yaml_config**: Valid YAML config file
- **invalid_yaml_config**: Invalid YAML config file
- **incomplete_yaml_config**: Config with missing fields

### Test-specific fixtures

Each test class has its own fixtures:

- **mock_config_path**: Temporary config file for testing
- **mock_settings**: Mock AutomationSettings object
- **mock_config_invalid**: Invalid YAML config file

## Mock Strategy

Tests use comprehensive mocking of external dependencies:

### Mocked Components

- **AutomationSettings.from_yaml**: Config loading
- **GiteaRestProvider**: Git provider operations
- **ExternalAgentProvider**: External AI agent operations
- **OllamaProvider**: Local AI model operations
- **StateManager**: State persistence
- **InteractiveQAHandler**: Interactive Q&A handling
- **WorkflowOrchestrator**: Main workflow orchestration

### AsyncMock Usage

Async functions are mocked with `AsyncMock` to properly test async code paths:

```python
mock_orch = AsyncMock()
mock_orch.process_issue = AsyncMock()
await _process_single_issue(settings, 42)
```

## Error Testing

### Configuration Errors
- Missing config file
- Invalid YAML syntax
- Missing required fields
- YAML parsing errors

### Command Errors
- Missing required arguments
- Invalid argument types
- Invalid argument values
- Out-of-range numbers

### Operational Errors
- Connection failures
- File not found errors
- Permission errors
- Timeout errors (simulated)

## Exit Code Testing

Tests verify proper exit codes:

- **Exit code 0**: Success
- **Exit code 1**: Configuration errors
- **Exit code 2**: Missing required arguments (Click default)
- **Non-zero**: Any error condition

## Output Validation

Tests validate:

- Help text structure
- Success messages (including emojis)
- Error messages (informative and user-friendly)
- Plan status formatting
- List output structure

## Integration Testing

Full integration tests verify:

1. CLI invocation → config loading → command execution
2. Error propagation through CLI layers
3. Async operation completion
4. State persistence and retrieval
5. Provider initialization and connection
6. Output formatting and display

## Edge Cases Covered

- Empty arguments and strings
- Very long argument values
- Unicode characters in arguments
- Multiple flags (last one wins)
- Missing optional fields in state
- Large number of plans
- Zero and negative numbers
- UUID-format identifiers
- Special characters in tags

## Dependencies

The test suite requires:

- `pytest>=7.4.0`
- `pytest-asyncio>=0.21.0`
- `pytest-mock>=3.12.0`
- `pytest-cov>=4.1.0` (for coverage)
- `click>=8.1.0` (for CliRunner)

Install development dependencies:
```bash
pip install -e ".[dev]"
```

## Performance Considerations

- Tests use temporary files to avoid filesystem pollution
- Mocking prevents actual network calls
- AsyncMock handles async operations efficiently
- Test isolation through fixtures

## Best Practices

1. **Use appropriate mocking**: Don't test external systems
2. **Test both success and failure paths**: Each command has positive and negative tests
3. **Validate exit codes**: Important for CLI reliability
4. **Check error messages**: Users see these
5. **Test async properly**: Use AsyncMock and pytest-asyncio
6. **Isolate tests**: Each test is independent
7. **Use descriptive names**: Test names clearly indicate what's tested

## Future Enhancements

Potential additions to the test suite:

- [ ] Performance benchmarks for long-running operations
- [ ] Stress tests with large numbers of issues/plans
- [ ] Network error simulation tests
- [ ] Configuration file migration tests
- [ ] Concurrent command execution tests
- [ ] Memory usage validation
- [ ] Integration with actual test Git provider
- [ ] E2E tests with real daemon mode

## Debugging Tests

### Enable verbose output
```bash
pytest -vv tests/unit/test_cli_main.py
```

### Show local variables on failure
```bash
pytest -l tests/unit/test_cli_main.py
```

### Drop into debugger on failure
```bash
pytest --pdb tests/unit/test_cli_main.py
```

### Show print statements
```bash
pytest -s tests/unit/test_cli_main.py
```

### Run with logging
```bash
pytest --log-cli-level=DEBUG tests/unit/test_cli_main.py
```

## Contributing

When adding new CLI commands:

1. Add command tests to `test_cli_main.py`
2. Add integration tests to `test_cli_commands.py`
3. Test both success and error paths
4. Include edge case tests
5. Validate exit codes
6. Test output formatting
7. Update this README

## Test Statistics

As of the latest run:

- **Total test classes**: 26
- **Total test methods**: 150+
- **Coverage target**: >90%
- **Estimated execution time**: <30 seconds

## See Also

- [automation/main.py](../../automation/main.py) - Tested CLI implementation
- [pytest documentation](https://docs.pytest.org/)
- [Click testing guide](https://click.palletsprojects.com/testing/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
