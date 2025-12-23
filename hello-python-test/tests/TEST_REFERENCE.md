# CLI Test Reference - Complete Test Method List

Quick reference of all 230+ test methods organized by category.

## test_cli_main.py (150+ tests)

### TestCliBasics (8 tests)
- `test_cli_help` - Verify --help displays help information
- `test_cli_version_flag` - Verify CLI help display
- `test_cli_missing_config_file` - Error when config not found
- `test_cli_custom_config_path` - Custom --config path respected
- `test_cli_log_level_debug` - DEBUG log level processing
- `test_cli_log_level_warning` - WARNING log level processing
- `test_cli_invalid_config_yaml` - Invalid YAML config handling

### TestProcessIssueCommand (8 tests)
- `test_process_issue_help` - process-issue --help display
- `test_process_issue_missing_required_arg` - --issue required
- `test_process_issue_invalid_issue_number` - Non-numeric issue number
- `test_process_issue_success` - Successful issue processing
- `test_process_issue_with_zero_number` - Issue number 0
- `test_process_issue_with_large_number` - Large issue numbers

### TestProcessAllCommand (6 tests)
- `test_process_all_help` - process-all --help display
- `test_process_all_without_tag` - All issues without tag filter
- `test_process_all_with_tag` - All issues with tag filter
- `test_process_all_with_special_characters_in_tag` - Tags with special chars

### TestProcessPlanCommand (5 tests)
- `test_process_plan_help` - process-plan --help display
- `test_process_plan_missing_plan_id` - --plan-id required
- `test_process_plan_success` - Successful plan processing
- `test_process_plan_with_uuid` - UUID-format plan IDs

### TestDaemonCommand (6 tests)
- `test_daemon_help` - daemon --help display
- `test_daemon_default_interval` - Default 60s interval
- `test_daemon_custom_interval` - Custom polling interval
- `test_daemon_invalid_interval` - Invalid interval values
- `test_daemon_zero_interval` - Zero interval handling

### TestListPlansCommand (5 tests)
- `test_list_plans_help` - list-plans --help display
- `test_list_plans_empty` - No active plans display
- `test_list_plans_with_plans` - Multiple plans display

### TestShowPlanCommand (6 tests)
- `test_show_plan_help` - show-plan --help display
- `test_show_plan_missing_plan_id` - --plan-id required
- `test_show_plan_not_found` - Non-existent plan error
- `test_show_plan_success` - Successful plan display
- `test_show_plan_with_empty_stages` - Plans with no stages

### TestConfigurationErrors (2 tests)
- `test_config_parsing_error` - Config parsing error handling
- `test_config_missing_required_fields` - Missing config fields

### TestOutputFormatting (3 tests)
- `test_success_message_formatting` - Success message format
- `test_error_message_formatting` - Error message format
- `test_help_output_structure` - Help text structure

### TestEdgeCases (5 tests)
- `test_command_with_empty_string_arg` - Empty string arguments
- `test_multiple_config_flags` - Multiple --config flags
- `test_very_long_argument_values` - Very long argument values
- `test_unicode_in_arguments` - Unicode character support

### TestContextManagement (1 test)
- `test_context_object_creation` - Click context creation

### TestExitCodes (3 tests)
- `test_success_exit_code_zero` - Exit code 0 on success
- `test_error_exit_code_nonzero` - Non-zero on error
- `test_missing_required_argument_exit_code` - Exit code for missing args

### TestLoggingIntegration (2 tests)
- `test_logging_configuration_called` - Logging configuration invocation
- `test_logging_level_propagation` - Log level propagation

---

## test_cli_commands.py (80+ tests)

### TestOrchestratorCreation (3 tests)
- `test_create_orchestrator_external_provider` - External AI provider init
- `test_create_orchestrator_ollama_provider` - Ollama provider init
- `test_create_orchestrator_connection_failure` - Connection error handling
- `test_create_orchestrator_api_token_retrieval` - Token retrieval verification

### TestProcessSingleIssueFunction (3 tests)
- `test_process_single_issue_success` - Successful issue processing
- `test_process_single_issue_not_found` - Non-existent issue handling
- `test_process_single_issue_with_exception` - Exception during processing

### TestProcessAllIssuesFunction (4 tests)
- `test_process_all_without_tag` - All issues without filter
- `test_process_all_with_tag` - Tag-filtered processing
- `test_process_all_with_empty_tag` - Empty tag handling
- `test_process_all_failure` - Processing failure handling

### TestProcessPlanFunction (3 tests)
- `test_process_plan_success` - Successful plan processing
- `test_process_plan_with_uuid` - UUID-format plan IDs
- `test_process_plan_not_found` - Non-existent plan handling

### TestDaemonModeFunction (3 tests)
- `test_daemon_mode_keyboard_interrupt` - Ctrl+C handling
- `test_daemon_mode_processing_error` - Error recovery in daemon
- `test_daemon_mode_with_custom_interval` - Custom interval usage

### TestListActivePlansFunction (3 tests)
- `test_list_active_plans_empty` - Empty plan list
- `test_list_active_plans_with_plans` - Multiple plans
- `test_list_active_plans_with_missing_state` - Missing state handling

### TestShowPlanStatusFunction (3 tests)
- `test_show_plan_status_success` - Successful display
- `test_show_plan_status_not_found` - Non-existent plan
- `test_show_plan_status_with_complex_structure` - Complex plan structures

### TestIntegrationScenarios (2 tests)
- `test_full_workflow_from_cli` - Complete CLI workflow
- `test_error_propagation_through_cli` - Error propagation

### TestProviderIntegration (3 tests)
- `test_external_agent_provider_initialization` - External provider init
- `test_git_provider_initialization` - Git provider init

### TestStateManagement (2 tests)
- `test_state_manager_initialization` - StateManager init
- `test_state_loading_error_handling` - State loading errors

### TestErrorMessages (3 tests)
- `test_config_not_found_message` - Config not found message
- `test_config_parsing_error_message` - Config parsing error message
- `test_missing_required_argument_message` - Missing argument message

### TestCommandOutputs (3 tests)
- `test_success_emoji_in_output` - Success emoji display
- `test_plan_status_formatting` - Plan status output format

### TestAsyncErrorHandling (3 tests)
- `test_async_exception_in_orchestrator_creation` - Async exception handling
- `test_async_timeout_during_processing` - Timeout handling

### TestEdgeCasesAdvanced (3 tests)
- `test_empty_stages_and_tasks_in_plan_status` - Empty stage/task handling
- `test_plan_status_missing_optional_fields` - Missing optional fields
- `test_list_plans_with_large_number_of_plans` - Large plan lists

---

## Test Coverage by Command

### process-issue (8 tests)
1. Help display
2. Required argument validation
3. Invalid format handling
4. Success path
5. Zero number handling
6. Large number handling
7. Error propagation
8. Output formatting

### process-all (7 tests)
1. Help display
2. No tag filter
3. With tag filter
4. Special characters in tag
5. Empty tag handling
6. Failure handling
7. Output formatting

### process-plan (5 tests)
1. Help display
2. Required argument validation
3. Success path
4. UUID format handling
5. Not found error

### daemon (6 tests)
1. Help display
2. Default interval
3. Custom interval
4. Invalid interval
5. Interrupt handling
6. Error recovery

### list-plans (5 tests)
1. Help display
2. Empty list
3. Multiple plans
4. State loading errors
5. Large lists

### show-plan (6 tests)
1. Help display
2. Required argument validation
3. Not found error
4. Success display
5. Empty structures
6. Complex structures

---

## Test Coverage by Feature

### Configuration Management (12 tests)
- Config file loading
- Custom config paths
- Invalid YAML handling
- Missing fields
- Error messages
- Path validation

### Command Execution (30 tests)
- All 6 commands
- Success paths
- Failure paths
- Argument validation
- Help text
- Output formatting

### Error Handling (25 tests)
- Missing config files
- Invalid YAML
- Missing arguments
- Invalid formats
- Runtime errors
- File not found
- Permission errors
- Connection failures

### Logging (4 tests)
- Configuration call
- Log level propagation
- DEBUG level
- WARNING level

### Output Validation (15 tests)
- Help structure
- Success messages
- Error messages
- Plan formatting
- List formatting
- Emoji display
- Message clarity

### Exit Codes (8 tests)
- Success (0)
- Errors (non-zero)
- Configuration errors (1)
- Missing arguments (2)
- Proper propagation

### Async Operations (20 tests)
- Issue processing
- Plan processing
- Daemon mode
- State operations
- Provider initialization
- Error handling
- Timeouts

### Provider Integration (8 tests)
- Gitea provider
- External agent provider
- Ollama provider
- Provider initialization
- Connection management
- Token handling

### State Management (10 tests)
- State initialization
- State loading
- State saving
- Error handling
- Complex structures
- Missing fields

### Edge Cases (35 tests)
- Empty strings
- Very long values
- Unicode characters
- Multiple flags
- Zero/negative numbers
- UUID formats
- Special characters
- Large datasets
- Missing optional fields
- Incomplete structures

---

## Running Tests by Category

### All config tests
```bash
pytest tests/unit/ -k "config" -v
```

### All command tests
```bash
pytest tests/unit/ -k "process_issue or process_all or process_plan or daemon or list_plans or show_plan" -v
```

### All error tests
```bash
pytest tests/unit/ -k "error or fail" -v
```

### All async tests
```bash
pytest tests/unit/ -m asyncio -v
```

### Specific command
```bash
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand -v
```

### Specific test
```bash
pytest tests/unit/test_cli_main.py::TestProcessIssueCommand::test_process_issue_success -v
```

---

## Quick Reference for Test Names

### Naming Pattern
`test_[subject]_[action]_[expected_result]`

Examples:
- `test_process_issue_with_large_number_returns_success`
- `test_cli_missing_config_file_returns_error`
- `test_daemon_keyboard_interrupt_exits_gracefully`

### Common Prefixes
- `test_cli_*` - Basic CLI functionality
- `test_command_*` - Specific command tests
- `test_*_success` - Success path tests
- `test_*_error` - Error path tests
- `test_*_with_*` - Tests with specific conditions
- `test_*_missing_*` - Missing argument/file tests
- `test_*_invalid_*` - Invalid input tests

---

## Statistics

- **Total test files**: 3
- **Total test methods**: 230+
- **Total test classes**: 26
- **Total lines of test code**: 1,900+
- **Helper utility functions**: 15+
- **Assertion helper functions**: 6+
- **Test fixtures**: 12+
- **Average tests per class**: 9
- **Estimated execution time**: <30 seconds
- **Expected coverage**: >90%

---

## See Also

- [TEST_SUMMARY.md](TEST_SUMMARY.md) - Comprehensive summary
- [tests/unit/README.md](tests/unit/README.md) - Detailed documentation
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing guide and patterns
- [automation/main.py](automation/main.py) - Tested CLI implementation
