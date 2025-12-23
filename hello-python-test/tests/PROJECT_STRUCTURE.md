# CLI Test Suite - Project Structure

## File Organization

```
tests/
├── __init__.py                          # Test package marker
├── conftest.py                          # Shared pytest configuration and fixtures
├── TEST_SUMMARY.md                      # Comprehensive test suite summary
├── TEST_REFERENCE.md                    # Complete reference of all test methods
├── PROJECT_STRUCTURE.md                 # This file
│
└── unit/                                # Unit tests for CLI
    ├── __init__.py                      # Unit test package marker
    ├── README.md                        # Detailed test documentation
    ├── test_cli_main.py                 # Main CLI command tests (998 lines)
    ├── test_cli_commands.py             # Integration tests (815 lines)
    └── test_helpers.py                  # Helper utilities and custom assertions
```

## Root-Level Test Documentation

```
root/
├── TESTING_GUIDE.md                    # Quick reference and best practices
├── tests/                              # Test directory
│   ├── TEST_SUMMARY.md                 # This directory's summary
│   ├── TEST_REFERENCE.md               # Reference of test methods
│   └── ...
```

## File Descriptions

### Core Test Files

#### tests/conftest.py (90 lines)
**Purpose**: Shared pytest configuration and fixtures

**Contains**:
- Event loop management
- CliRunner fixture
- Temporary directory fixtures
- Sample config file fixtures
- Invalid config file fixtures

**Key Fixtures**:
- `cli_runner` - Click test runner
- `tmp_config_dir` - Temporary config directory
- `tmp_state_dir` - Temporary state directory
- `sample_yaml_config` - Valid YAML config
- `invalid_yaml_config` - Invalid YAML config

#### tests/unit/test_cli_main.py (998 lines)
**Purpose**: Main CLI command tests

**Contains**:
- 12 test classes
- ~150 test methods
- Tests for all CLI commands
- Exit code validation
- Output formatting tests

**Test Classes**:
1. TestCliBasics (8 tests) - Basic CLI functionality
2. TestProcessIssueCommand (8 tests) - process-issue command
3. TestProcessAllCommand (6 tests) - process-all command
4. TestProcessPlanCommand (5 tests) - process-plan command
5. TestDaemonCommand (6 tests) - daemon command
6. TestListPlansCommand (5 tests) - list-plans command
7. TestShowPlanCommand (6 tests) - show-plan command
8. TestConfigurationErrors (2 tests) - Config error handling
9. TestOutputFormatting (3 tests) - Output validation
10. TestEdgeCases (5 tests) - Edge cases and boundaries
11. TestContextManagement (1 test) - Click context
12. TestExitCodes (3 tests) - Exit code validation

#### tests/unit/test_cli_commands.py (815 lines)
**Purpose**: Integration and advanced CLI tests

**Contains**:
- 14 test classes
- ~80 test methods
- Provider integration tests
- Async function testing
- Error handling and recovery

**Test Classes**:
1. TestOrchestratorCreation (4 tests) - Orchestrator initialization
2. TestProcessSingleIssueFunction (3 tests) - Issue processing
3. TestProcessAllIssuesFunction (4 tests) - Bulk processing
4. TestProcessPlanFunction (3 tests) - Plan processing
5. TestDaemonModeFunction (3 tests) - Daemon mode async
6. TestListActivePlansFunction (3 tests) - Plan listing
7. TestShowPlanStatusFunction (3 tests) - Plan status display
8. TestIntegrationScenarios (2 tests) - Full workflows
9. TestProviderIntegration (3 tests) - Provider mocking
10. TestStateManagement (2 tests) - State operations
11. TestErrorMessages (3 tests) - Error message quality
12. TestCommandOutputs (3 tests) - Output formatting
13. TestAsyncErrorHandling (3 tests) - Async error handling
14. TestEdgeCasesAdvanced (3 tests) - Advanced edge cases

#### tests/unit/test_helpers.py (260+ lines)
**Purpose**: Helper utilities and custom assertions

**Contains**:
- Mock creation helpers (6 functions)
  - create_mock_settings()
  - create_mock_issue()
  - create_mock_orchestrator()
  - create_mock_state_manager()
  - create_mock_git_provider()
  - create_mock_agent_provider()
  
- Assertion helpers (5 functions)
  - assert_successful_exit()
  - assert_failed_exit()
  - assert_output_contains()
  - assert_output_not_contains()
  - assert_help_output()
  
- Utility functions (2 functions)
  - create_mock_plan_state()
  - format_mock_call_info()

### Documentation Files

#### tests/unit/README.md
**Purpose**: Detailed test documentation

**Sections**:
- Overview of test suite
- Test file descriptions
- Test coverage details
- Running tests guide
- Test fixtures reference
- Mock strategy
- Error testing
- Integration testing
- Edge cases
- Best practices
- Future enhancements
- Debugging guide
- Contributing guide

#### TESTING_GUIDE.md (root)
**Purpose**: Quick reference and best practices

**Sections**:
- Quick start
- Test structure
- Common test commands
- Test fixture reference
- Helper functions reference
- Test patterns (3 common patterns)
- Environment-specific instructions
- Expected test results
- Troubleshooting guide
- Adding new tests
- Best practices
- CI/CD integration
- Performance optimization
- Resources

#### TEST_SUMMARY.md
**Purpose**: Comprehensive test suite summary

**Sections**:
- Overview
- Deliverables listing
- Test coverage by command
- Feature coverage table
- Test classes listing
- Mocking strategy
- Test fixtures
- Test quality metrics
- Running the tests guide
- Key features
- Best practices
- Future enhancements
- Troubleshooting
- Documentation
- Conclusion

#### TEST_REFERENCE.md
**Purpose**: Complete reference of all test methods

**Sections**:
- Complete test method listing by file
- Test coverage by command
- Test coverage by feature
- Running tests by category
- Naming pattern reference
- Statistics

## Dependencies

### Testing Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
]
```

### Test Requirements

- Python 3.11+
- pytest
- pytest-asyncio
- pytest-mock
- click (for CliRunner)

## Test Statistics

| Metric | Value |
|--------|-------|
| Test files | 2 |
| Test classes | 26 |
| Test methods | 230+ |
| Helper functions | 15+ |
| Helper utilities | 260+ lines |
| Core test code | 1,813 lines |
| Total test code | 1,900+ lines |
| Documentation | 3,500+ lines |
| Average tests/class | 9 |
| Avg execution time | <30 seconds |
| Coverage target | >90% |

## How Tests Map to Code

### CLI Commands Tested

- `automation.main.cli` - Main CLI group
  - `process-issue` command
  - `process-all` command
  - `process-plan` command
  - `daemon` command
  - `list-plans` command
  - `show-plan` command

### Functions Tested

- `automation.main._create_orchestrator`
- `automation.main._process_single_issue`
- `automation.main._process_all_issues`
- `automation.main._process_plan`
- `automation.main._daemon_mode`
- `automation.main._list_active_plans`
- `automation.main._show_plan_status`

### Configuration Tested

- `automation.config.settings.AutomationSettings.from_yaml`
- Config file loading
- Config validation
- Config error handling

### Providers Mocked

- `automation.providers.gitea_rest.GiteaRestProvider`
- `automation.providers.external_agent.ExternalAgentProvider`
- `automation.providers.ollama.OllamaProvider`

### Utilities Mocked

- `automation.engine.orchestrator.WorkflowOrchestrator`
- `automation.engine.state_manager.StateManager`
- `automation.utils.interactive.InteractiveQAHandler`
- `automation.utils.logging_config.configure_logging`

## Test Execution Flow

```
1. Pytest discovery
   ↓
2. Load conftest.py
   - Set up fixtures
   - Configure event loop
   ↓
3. Load test modules
   - test_cli_main.py
   - test_cli_commands.py
   ↓
4. Create test instances
   - 26 test classes
   ↓
5. Run test methods
   - 230+ tests
   - Each with setup/teardown
   ↓
6. Collect results
   - Pass/fail status
   - Coverage data
   ↓
7. Report results
   - Console output
   - Coverage report (if requested)
   - XML report (if requested)
```

## Fixture Dependency Graph

```
event_loop (session scope)
    ↓
cli_runner → test methods
    ↓
mock_config_path (used in CLI runner invoke calls)
    ↓
mock_settings (used in mock patches)
    ↓
test method assertions
```

## Mocking Architecture

```
automation.main (tested)
    ↓
Mocked dependencies:
- AutomationSettings.from_yaml
- _create_orchestrator
- GiteaRestProvider
- ExternalAgentProvider
- OllamaProvider
- StateManager
- InteractiveQAHandler
- WorkflowOrchestrator
- configure_logging
```

## Running Tests Workflow

```
Setup
├── pip install -e ".[dev]"
├── Navigate to repo root
└── Verify pytest is available

Execution
├── pytest tests/unit/test_cli_*.py -v
├── Monitor output
└── Check coverage (optional)

Results
├── Test report (console)
├── Coverage report (html)
├── JUnit XML (for CI/CD)
└── Success/failure summary
```

## Key Design Decisions

1. **Two-file structure**: Main tests + Integration tests for clarity
2. **Helper utilities**: DRY principle with reusable test functions
3. **Mock-heavy approach**: No external API calls or network access
4. **Comprehensive documentation**: Tests are well-documented for maintenance
5. **Fast execution**: All mocks and no I/O for <30 second runtime
6. **Clear naming**: Test names describe exactly what's being tested
7. **Organized by command**: Easy to find tests for specific commands
8. **Fixture-based**: DRY setup using conftest.py

## Maintenance Considerations

### Adding New Tests
1. Identify command/function to test
2. Find appropriate test class
3. Use helper functions and fixtures
4. Follow naming pattern
5. Test both success and failure
6. Update TEST_REFERENCE.md

### Updating Existing Tests
1. Locate test in test class
2. Update test logic
3. Update docstring if behavior changed
4. Run tests to verify
5. Check coverage impact

### Debugging Tests
1. Use `pytest -s` to see output
2. Use `pytest -l` to see local variables
3. Use `--pdb` for interactive debugging
4. Use `format_mock_call_info()` helper
5. Check test docstring for intent

## CI/CD Integration

### GitHub Actions
```yaml
- run: pip install -e ".[dev]"
- run: pytest tests/unit/ --cov
```

### GitLab CI
```yaml
script:
  - pip install -e ".[dev]"
  - pytest tests/unit/ --cov
```

### Local Pre-commit
```bash
pytest tests/unit/ --cov --cov-report=term
```

## Related Documentation

- [automation/main.py](../automation/main.py) - Tested CLI code
- [tests/unit/README.md](tests/unit/README.md) - Detailed test docs
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing guide
- [TEST_SUMMARY.md](TEST_SUMMARY.md) - Test summary
- [TEST_REFERENCE.md](TEST_REFERENCE.md) - Method reference

---

**Generated**: December 23, 2024
**Total Project Test Files**: 5 documentation files + 3 test files
**Total Documentation**: 3,500+ lines
**Total Test Code**: 1,900+ lines
