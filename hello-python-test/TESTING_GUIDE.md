# CLI Testing Guide

This guide covers how to run, understand, and extend the comprehensive CLI test suite.

## Quick Start

### Install Test Dependencies
```bash
pip install -e ".[dev]"
```

### Run All CLI Tests
```bash
pytest tests/unit/test_cli_main.py tests/unit/test_cli_commands.py -v
```

### Run Tests with Coverage
```bash
pytest tests/unit/ --cov=automation --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Structure

### File Organization
```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── unit/
│   ├── test_cli_main.py        # Main CLI command tests (150+ tests)
│   ├── test_cli_commands.py    # Integration tests (80+ tests)
│   ├── test_helpers.py         # Helper utilities for tests
│   └── README.md               # Detailed test documentation
```

### Test Coverage by Command

| Command | Tests | Coverage |
|---------|-------|----------|
| process-issue | 8 | All paths, edge cases |
| process-all | 6 | Tag filtering, special chars |
| process-plan | 5 | UUID IDs, not found |
| daemon | 6 | Intervals, errors, interrupt |
| list-plans | 5 | Empty, multiple, large lists |
| show-plan | 6 | Found, not found, complex structures |
| Global flags | 8 | Config, log-level, errors |

## Common Test Commands

### Run Specific Test Class
```bash
# Test process-issue command
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand -v

# Test daemon mode
pytest tests/unit/test_cli_main.py::TestDaemonCommand -v
```

### Run Single Test
```bash
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand::test_process_issue_success -v
```

### Run Tests Matching Pattern
```bash
# All tests with "config" in name
pytest tests/unit/ -k config -v

# All async tests
pytest tests/unit/ -m asyncio -v
```

### Run with Detailed Output
```bash
# Show all output, including print statements
pytest tests/unit/ -s -v

# Show local variables on failure
pytest tests/unit/ -l -v

# Verbose + all output
pytest tests/unit/ -vv -s
```

### Run with Coverage Report
```bash
# HTML report
pytest tests/unit/ --cov=automation --cov-report=html

# Terminal report
pytest tests/unit/ --cov=automation --cov-report=term-missing

# Both
pytest tests/unit/ --cov=automation --cov-report=html --cov-report=term
```

### Debug Failing Tests
```bash
# Drop into debugger on first failure
pytest tests/unit/ --pdb

# Drop into debugger on every failure
pytest tests/unit/ --pdb --lf

# Show print statements
pytest tests/unit/ -s

# Increase log level
pytest tests/unit/ --log-cli-level=DEBUG
```

## Test Fixture Reference

### Global Fixtures (from `conftest.py`)

```python
# Click test runner
@pytest.fixture
def cli_runner() -> CliRunner:
    """Creates a CliRunner for testing Click commands."""

# Temporary directories
@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Creates temporary config directory."""

@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Creates temporary state directory."""

# Sample config files
@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Creates valid YAML config file."""

@pytest.fixture
def invalid_yaml_config(tmp_path: Path) -> Path:
    """Creates invalid YAML config file."""
```

### Test-Specific Fixtures

Each test class has access to:
- `mock_config_path`: Valid config file
- `mock_settings`: Pre-configured mock settings
- `cli_runner`: Click CLI runner

## Helper Functions (from `test_helpers.py`)

### Mock Creators
```python
# Create mock settings
settings = create_mock_settings(repo_owner="custom_owner")

# Create mock issue
issue = create_mock_issue(number=42, title="Bug Fix")

# Create mock orchestrator
orch = create_mock_orchestrator()

# Create mock state
state = create_mock_plan_state(status="in_progress")
```

### Assertion Helpers
```python
# Assert success/failure
assert_successful_exit(result)
assert_failed_exit(result)

# Assert output content
assert_output_contains(result, "Plan", "status")
assert_output_not_contains(result, "Error")

# Assert help text
assert_help_output(result)
```

## Test Patterns

### Pattern 1: Testing Successful Command
```python
def test_command_success(cli_runner, mock_config_path, mock_settings):
    """Test successful command execution."""
    with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
        mock_from_yaml.return_value = mock_settings

        with patch("automation.main._create_orchestrator") as mock_orch:
            mock_orch.return_value = AsyncMock()

            result = cli_runner.invoke(
                cli,
                ["--config", str(mock_config_path), "command-name"]
            )

            assert_successful_exit(result)
            assert_output_contains(result, "success message")
```

### Pattern 2: Testing Error Handling
```python
def test_command_error(cli_runner, mock_config_path):
    """Test command error handling."""
    with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
        mock_from_yaml.return_value = MagicMock()

        result = cli_runner.invoke(
            cli,
            ["--config", str(mock_config_path), "command-name"]
        )

        assert_failed_exit(result)
        assert_output_contains(result, "error message")
```

### Pattern 3: Testing Async Function
```python
@pytest.mark.asyncio
async def test_async_function(mock_settings):
    """Test async function."""
    with patch("automation.main._create_orchestrator") as mock_orch:
        mock_orch.return_value = AsyncMock()

        await _async_function(mock_settings, arg1, arg2)

        # Verify behavior
        mock_orch.assert_called_once()
```

## Running Tests in Different Environments

### Local Development
```bash
# Run all tests
pytest tests/unit/

# Run with watch mode (requires pytest-watch)
ptw tests/unit/

# Run with coverage
pytest tests/unit/ --cov
```

### Continuous Integration
```bash
# Run tests with coverage and report
pytest tests/unit/ \
    --cov=automation \
    --cov-report=xml \
    --cov-report=term \
    --junitxml=test-results.xml
```

### Docker
```bash
# Build with test environment
docker build -t repo-agent-test .

# Run tests in container
docker run repo-agent-test pytest tests/unit/
```

## Expected Test Results

### Test Count Summary
- **test_cli_main.py**: ~150 test methods
- **test_cli_commands.py**: ~80 test methods
- **Total**: ~230 test methods

### Expected Coverage
- **automation/main.py**: >95%
- **automation/**: >90% (overall)

### Expected Runtime
- **Local execution**: <30 seconds
- **With coverage**: <45 seconds
- **CI/CD**: <60 seconds

## Troubleshooting

### Common Issues

#### Tests Import Errors
**Problem**: `ModuleNotFoundError: No module named 'automation'`

**Solution**:
```bash
pip install -e .
```

#### Async Test Issues
**Problem**: `RuntimeError: Event loop is closed`

**Solution**: Ensure pytest-asyncio is installed and configured:
```bash
pip install pytest-asyncio>=0.21.0
```

The `conftest.py` includes proper event loop fixture setup.

#### Mock Not Called
**Problem**: Mock was never called but test expects it

**Solution**: Check the execution path:
```python
# Debug: Print what was actually called
print(format_mock_call_info(mock_object))

# Verify mock was passed correctly
assert mock_object.called, "Mock was not called"
```

#### Fixture Not Found
**Problem**: `fixture 'mock_config_path' not found`

**Solution**: Ensure you're in the correct test class that has the fixture defined:
```python
# Fixtures must be method parameters
def test_something(self, mock_config_path):  # Correct
    pass

def test_something(self):  # Wrong - missing fixture
    pass
```

## Adding New Tests

### Checklist for New Test

- [ ] **Name clearly describes what's tested**: `test_command_with_feature_should_result`
- [ ] **Tests both success and failure paths**: Positive and negative cases
- [ ] **Mocks external dependencies**: No actual API calls
- [ ] **Uses appropriate fixtures**: Leverages conftest fixtures
- [ ] **Validates exit codes**: Check `result.exit_code`
- [ ] **Validates output**: Use `assert_output_contains`
- [ ] **Tests edge cases**: Empty, None, large values, etc.
- [ ] **Includes docstring**: Explains what's being tested
- [ ] **Is isolated**: No dependencies on other tests
- [ ] **Runs in <1 second**: No unnecessary delays

### Template for New Test

```python
def test_new_feature(cli_runner: CliRunner, mock_config_path: Path, mock_settings: MagicMock) -> None:
    """Test description of what's being tested.

    Expected behavior: Clear description of expected result.
    """
    # Arrange: Set up mocks and fixtures
    with patch("automation.config.settings.AutomationSettings.from_yaml") as mock_from_yaml:
        mock_from_yaml.return_value = mock_settings

        # Act: Execute the command/function
        result = cli_runner.invoke(
            cli,
            ["--config", str(mock_config_path), "command", "--flag", "value"]
        )

        # Assert: Verify results
        assert_successful_exit(result)
        assert_output_contains(result, "expected text")
        assert mock_from_yaml.called
```

## Best Practices

1. **Keep tests small and focused**: One concept per test
2. **Use descriptive names**: Test name should explain what's tested
3. **Mock external calls**: Never make real API calls in tests
4. **Test both paths**: Success and failure for each command
5. **Validate output**: Check messages users see
6. **Use fixtures**: Leverage conftest for common setup
7. **Clean up after tests**: Use tmp_path for temporary files
8. **Document edge cases**: Comment on unusual test scenarios

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

### GitLab CI Example
```yaml
test:
  image: python:3.11
  script:
    - pip install -e ".[dev]"
    - pytest tests/unit/ --cov --cov-report=term
```

## Performance Optimization

### Speed Up Tests Locally
```bash
# Use fewer workers but faster collection
pytest tests/unit/ -n auto --dist=loadgroup

# Run only changed tests
pytest tests/unit/ --lf

# Run failed tests first
pytest tests/unit/ --ff
```

### Profile Slow Tests
```bash
# Show slowest 10 tests
pytest tests/unit/ --durations=10

# Show all tests with duration > 1s
pytest tests/unit/ --durations=0 -k "duration > 1000"
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Click Testing Guide](https://click.palletsprojects.com/testing/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Test Code Organization](https://docs.pytest.org/organizing/)

## Support

For issues or questions about tests:

1. Check the test README: `tests/unit/README.md`
2. Review test helper functions: `tests/unit/test_helpers.py`
3. Check conftest fixtures: `tests/conftest.py`
4. Run with `--vv -s` for detailed output
5. Use `--pdb` to debug failing tests
