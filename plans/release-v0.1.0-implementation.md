# repo-sapiens v0.1.0 Production Release - Implementation Plan

**Project**: repo-sapiens (AI-driven Git workflow automation)
**Current Version**: 0.1.0 (code), 0.0.2 (PyPI placeholder)
**Target**: Production-ready v0.1.0 release
**Timeline**: 6-8 weeks (realistic for production readiness)
**Created**: 2025-12-23
**Python Expert Review**: APPROVED with modifications

---

## Executive Summary

This implementation plan prepares repo-sapiens for a production-ready v0.1.0 release on PyPI. Based on Python expert review of the existing codebase and prior plans, this plan addresses critical gaps in security, testing, documentation, and packaging while maintaining the package's innovative AI-driven automation capabilities.

**Current State Assessment**:
- Package name: `repo-sapiens` (PyPI) / `automation` (import)
- 77 Python files in automation package
- 24 test files across credentials, git, templates, and integration
- Core infrastructure: COMPLETE (credentials, git discovery, templates, CLI)
- PyPI packaging: FUNCTIONAL but needs validation
- Security: IMPLEMENTED but needs audit
- Testing: PARTIAL coverage (~30-40% estimated)
- Documentation: BASIC (needs expansion)

**Critical Success Factors**:
1. Comprehensive security audit of credential system
2. Test coverage target: 75%+ (up from ~35% current)
3. Complete API documentation and user guides
4. Production-ready error handling and logging
5. Performance benchmarking and optimization
6. Automated release pipeline

---

## Python Expert Review Findings

### Architecture Assessment: STRONG

**Strengths**:
- Excellent use of Pydantic for configuration and validation
- Clean separation of concerns (credentials, git, templates, config)
- Proper type hints with `py.typed` marker (PEP 561)
- Credential system with multiple backends (keyring, encrypted, environment)
- Modern async support where appropriate

**Areas for Improvement**:
1. **Security Hardening**: Credential system needs penetration testing
2. **Test Coverage**: Current ~35% is insufficient for production
3. **Error Handling**: Inconsistent exception handling across modules
4. **Performance**: No benchmarks for large repository operations
5. **Documentation**: Missing comprehensive API docs and examples

### Packaging Assessment: GOOD

**Correct Implementations**:
- ✅ Version management via `automation.__version__`
- ✅ SPDX license identifier
- ✅ Split dependencies (core + optional)
- ✅ PEP 561 compliance with `py.typed`
- ✅ Proper MANIFEST.in for source distributions

**Remaining Issues**:
- ⚠️ Need to verify package builds and installs cleanly
- ⚠️ TestPyPI validation not performed
- ⚠️ Missing automated release workflow

### Code Quality Assessment: SATISFACTORY

**Good Patterns**:
- Consistent use of dataclasses and Pydantic models
- Structured logging with structlog
- Configuration via environment variables and files

**Anti-Patterns to Address**:
- Some bare `except` clauses without specific exception types
- Inconsistent docstring coverage (some modules excellent, others minimal)
- Limited input validation in some CLI commands

---

## Architecture & Component Overview

```
repo-sapiens/
├── automation/                 # Main package (import name)
│   ├── __init__.py            # Exports __version__
│   ├── __version__.py         # Single source of truth: "0.1.0"
│   ├── py.typed               # PEP 561 type marker
│   ├── main.py                # CLI entry point
│   ├── config/                # Configuration system
│   │   ├── settings.py        # Pydantic settings
│   │   └── credential_fields.py
│   ├── credentials/           # Multi-backend credential management
│   │   ├── backend.py         # Abstract base
│   │   ├── keyring_backend.py # OS keyring integration
│   │   ├── encrypted_backend.py # Encrypted file storage
│   │   ├── environment_backend.py # Environment variables
│   │   └── resolver.py        # Credential reference resolution
│   ├── git/                   # Git operations
│   │   ├── discovery.py       # Repository discovery
│   │   ├── parser.py          # Config parsing
│   │   └── models.py
│   ├── rendering/             # Jinja2 template system
│   │   └── engine.py
│   ├── templates/             # Template library
│   │   ├── github-actions/
│   │   ├── gitea-workflows/
│   │   └── docker/
│   ├── cli/                   # CLI commands
│   ├── engine/                # Workflow engine
│   ├── models/                # Domain models
│   └── providers/             # Git/AI provider integrations
├── tests/                     # Test suite (24 files)
│   ├── unit/
│   ├── integration/
│   ├── test_credentials/      # Credential tests
│   ├── git/                   # Git discovery tests
│   └── templates/             # Template tests
├── docs/                      # Documentation
├── plans/                     # Development plans
├── pyproject.toml             # PEP 621 metadata
├── MANIFEST.in                # Source distribution manifest
├── README.md                  # PyPI landing page
└── LICENSE                    # MIT license
```

**Key Design Decisions**:
1. **Package Naming**: `repo-sapiens` (PyPI) vs `automation` (import) - avoids breaking changes
2. **Credential Security**: Multi-backend with encryption, keyring, and env var support
3. **Type Safety**: Full type hints with mypy strict mode
4. **Configuration**: Pydantic-based with environment variable overrides
5. **Testing**: pytest with async support, coverage tracking

---

## Release Phases & Task Breakdown

### PHASE 1: Security Audit & Hardening (Week 1-2)

**Objective**: Ensure credential system and sensitive operations are production-ready

#### Task 1.1: Security Audit - Credential System
**Agent Type**: Python Security Expert
**Priority**: CRITICAL
**Estimated Time**: 8 hours

**Prompt for Agent**:
```
Perform a comprehensive security audit of the credential management system in
/home/ross/Workspace/repo-agent/automation/credentials/. Focus on:

1. Review all files in automation/credentials/:
   - backend.py (abstract base)
   - keyring_backend.py (OS keyring integration)
   - encrypted_backend.py (encryption implementation)
   - environment_backend.py (env var handling)
   - resolver.py (credential resolution)

2. Security checks:
   - Encryption key derivation (PBKDF2 usage in encrypted_backend.py)
   - Secret storage and retrieval paths
   - Memory handling (ensure secrets not logged or leaked)
   - Input validation and sanitization
   - Exception handling (no secret leakage in tracebacks)
   - File permissions on credential storage
   - Timing attack vulnerabilities

3. Code review for:
   - Use of cryptography library (current: Fernet with PBKDF2)
   - Keyring integration security
   - Environment variable handling
   - SecretStr usage in Pydantic models

4. Create security report at:
   /home/ross/Workspace/repo-agent/docs/SECURITY_AUDIT.md

5. Include:
   - Findings (critical, high, medium, low)
   - Proof-of-concept for any vulnerabilities
   - Remediation recommendations with code examples
   - Security best practices compliance checklist

6. If critical issues found, create patches in a security-fixes branch

Tools available: Read, Edit, Write, Bash (for testing), Grep
```

**Acceptance Criteria**:
- [ ] Complete security audit report generated
- [ ] All critical and high severity issues identified
- [ ] Remediation plan with code examples
- [ ] No secrets logged or exposed in error messages
- [ ] Encryption implementation validated against best practices

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/SECURITY_AUDIT.md`
- Security fixes branch (if needed)

---

#### Task 1.2: Input Validation & Sanitization Audit
**Agent Type**: Python Security Expert
**Priority**: HIGH
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Audit input validation and sanitization across the repo-sapiens codebase:

1. Review all CLI command handlers in:
   - automation/main.py
   - automation/cli/*.py

2. Check for:
   - Path traversal vulnerabilities in file operations
   - Command injection in subprocess calls
   - SQL injection (if any database operations)
   - YAML/JSON deserialization vulnerabilities
   - Unsafe use of eval() or exec()
   - Unvalidated user input passed to shell commands

3. Review template rendering in automation/rendering/:
   - Check for template injection vulnerabilities
   - Validate Jinja2 autoescape settings
   - Ensure user input is properly escaped

4. Review HTTP client usage:
   - Check httpx usage for SSRF vulnerabilities
   - Validate SSL/TLS certificate verification
   - Check for credential leakage in URLs/headers

5. Create report at:
   /home/ross/Workspace/repo-agent/docs/INPUT_VALIDATION_AUDIT.md

6. For each finding:
   - Provide vulnerable code snippet
   - Explain attack vector
   - Provide secure replacement code

Tools: Read, Grep, Edit
```

**Acceptance Criteria**:
- [ ] All input validation gaps identified
- [ ] Path traversal vulnerabilities addressed
- [ ] Template injection risks mitigated
- [ ] No command injection vectors
- [ ] Documented secure coding guidelines

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/INPUT_VALIDATION_AUDIT.md`

---

#### Task 1.3: Secrets Scanning & .gitignore Validation
**Agent Type**: DevOps/Security Expert
**Priority**: CRITICAL
**Estimated Time**: 2 hours

**Prompt for Agent**:
```
Scan the repo-sapiens codebase for accidentally committed secrets and validate
.gitignore configuration:

1. Scan for common secret patterns:
   - API keys (look for patterns like /[A-Za-z0-9_-]{20,}/)
   - Tokens (ghp_, sk_, pk_, etc.)
   - Private keys (BEGIN PRIVATE KEY)
   - Credentials in configuration files

2. Check committed files for:
   - .env files (should be .gitignore'd)
   - Configuration files with hardcoded secrets
   - Test files with real credentials
   - Database connection strings

3. Validate .gitignore includes:
   - .env (all variants: .env, .env.local, .env.production)
   - Credential storage files
   - State files with sensitive data
   - IDE/editor files

4. Check for secrets in git history:
   git log -S "password" --source --all
   git log -S "api_key" --source --all
   git log -S "secret" --source --all

5. Create report at:
   /home/ross/Workspace/repo-agent/docs/SECRETS_SCAN.md

6. If secrets found in history:
   - Document commit hashes
   - Provide git filter-repo or BFG instructions
   - List secrets that need rotation

Tools: Bash, Read, Write, Grep
```

**Acceptance Criteria**:
- [ ] No secrets found in current codebase
- [ ] .gitignore properly configured
- [ ] Git history scanned for leaked secrets
- [ ] Documentation for secret rotation (if needed)
- [ ] Example .env.example file validated

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/SECRETS_SCAN.md`
- Updated `.gitignore` (if needed)

---

### PHASE 2: Test Coverage Expansion (Week 2-3)

**Objective**: Achieve 75%+ test coverage with comprehensive unit and integration tests

#### Task 2.1: Test Coverage Baseline & Gap Analysis
**Agent Type**: Python Testing Expert
**Priority**: HIGH
**Estimated Time**: 3 hours

**Prompt for Agent**:
```
Establish test coverage baseline for repo-sapiens and identify gaps:

1. Run pytest with coverage:
   cd /home/ross/Workspace/repo-agent
   pytest tests/ -v --cov=automation --cov-report=html --cov-report=term-missing

2. Analyze coverage by module:
   - Overall coverage percentage
   - Per-module breakdown
   - Identify modules with <50% coverage
   - Identify critical paths with no coverage

3. Review existing test structure:
   - tests/unit/ - unit tests
   - tests/integration/ - integration tests
   - tests/test_credentials/ - credential tests (8 files)
   - tests/git/ - git discovery tests (3 files)
   - tests/templates/ - template tests (5 files)

4. Identify missing test categories:
   - CLI command tests
   - Configuration loading tests
   - Error handling tests
   - Edge case tests
   - Performance tests

5. Create detailed report at:
   /home/ross/Workspace/repo-agent/docs/TEST_COVERAGE_ANALYSIS.md

   Include:
   - Current coverage percentage by module
   - Critical uncovered paths
   - Prioritized list of modules needing tests
   - Test strategy for each module
   - Estimated effort (hours) per module

6. Generate prioritized test task list

Tools: Bash (pytest), Read, Write
```

**Acceptance Criteria**:
- [ ] Coverage report generated and analyzed
- [ ] Current coverage baseline documented
- [ ] Gaps identified and prioritized
- [ ] Test strategy defined per module
- [ ] Task list for test implementation

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/TEST_COVERAGE_ANALYSIS.md`
- Coverage HTML report in `htmlcov/`

---

#### Task 2.2: Core Module Tests - Configuration System
**Agent Type**: Python Testing Expert
**Priority**: HIGH
**Estimated Time**: 6 hours

**Prompt for Agent**:
```
Write comprehensive tests for the configuration system in automation/config/:

1. Test files to create:
   - tests/unit/test_config_settings.py
   - tests/unit/test_config_credential_fields.py

2. Test coverage for automation/config/settings.py:
   - Test all Pydantic model validation
   - Test GitProviderConfig with valid/invalid URLs
   - Test RepositoryConfig validation
   - Test AgentProviderConfig with all provider types
   - Test WorkflowConfig boundary conditions
   - Test TagsConfig defaults
   - Test environment variable interpolation
   - Test AutomationSettings loading from YAML
   - Test AutomationSettings loading from env vars
   - Test configuration merging (file + env vars)

3. Test coverage for automation/config/credential_fields.py:
   - Test CredentialSecret validation
   - Test credential reference patterns:
     * @keyring:service/key
     * ${ENV_VAR}
     * @encrypted:service/key
     * Plain text credentials (should work but warn?)
   - Test invalid patterns (should raise validation error)

4. Test edge cases:
   - Missing required fields
   - Invalid URL formats
   - Out-of-range integer values
   - Invalid literal choices
   - Circular references

5. Use pytest fixtures from tests/conftest.py
6. Aim for 90%+ coverage of config module
7. Include docstrings explaining what each test validates

Tools: Read, Write, Bash (pytest)
```

**Acceptance Criteria**:
- [ ] Configuration tests written and passing
- [ ] 90%+ coverage of automation/config/
- [ ] All Pydantic validation tested
- [ ] Environment variable handling tested
- [ ] Edge cases covered

**Dependencies**: Task 2.1 (baseline)
**Deliverables**:
- `tests/unit/test_config_settings.py`
- `tests/unit/test_config_credential_fields.py`

---

#### Task 2.3: Core Module Tests - CLI Commands
**Agent Type**: Python Testing Expert
**Priority**: HIGH
**Estimated Time**: 8 hours

**Prompt for Agent**:
```
Write comprehensive tests for CLI commands in automation/main.py and automation/cli/:

1. Test file to create:
   - tests/unit/test_cli_main.py
   - tests/unit/test_cli_commands.py (if cli/ directory has multiple files)

2. Use Click testing utilities:
   from click.testing import CliRunner

3. Test automation/main.py CLI commands:
   - Test 'automation --help'
   - Test 'automation --version'
   - Test each subcommand with valid args
   - Test each subcommand with invalid args
   - Test exit codes (0 for success, non-zero for errors)
   - Test output formatting
   - Test --config flag for custom config
   - Test --log-level flag

4. Test command integration:
   - Mock external dependencies (git provider, AI provider)
   - Test configuration loading
   - Test error handling and error messages
   - Test user-friendly error messages

5. Test edge cases:
   - Missing required arguments
   - Invalid file paths
   - Permission errors
   - Network errors (mocked)
   - Configuration errors

6. Use pytest-mock for mocking external services
7. Capture stdout/stderr and validate output
8. Test both success and failure paths

Example structure:
```python
def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Usage:' in result.output

def test_cli_invalid_config(tmp_path):
    runner = CliRunner()
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: content:")
    result = runner.invoke(cli, ['--config', str(config_file), 'list-active-plans'])
    assert result.exit_code != 0
    assert 'configuration error' in result.output.lower()
```

Tools: Read, Write, Bash (pytest)
```

**Acceptance Criteria**:
- [ ] All CLI commands tested
- [ ] Success and failure paths covered
- [ ] Error messages validated
- [ ] Help text validated
- [ ] Exit codes correct

**Dependencies**: Task 2.1 (baseline)
**Deliverables**:
- `tests/unit/test_cli_main.py`
- `tests/unit/test_cli_commands.py`

---

#### Task 2.4: Integration Tests - End-to-End Workflows
**Agent Type**: Python Testing Expert
**Priority**: MEDIUM
**Estimated Time**: 10 hours

**Prompt for Agent**:
```
Write integration tests for end-to-end workflows:

1. Test file to create:
   - tests/integration/test_workflow_e2e.py

2. Test scenarios (using mocked external services):
   - Complete workflow: issue → planning → implementation → merge
   - Credential resolution flow
   - Git operations (branch creation, commits, PRs)
   - Template rendering and application
   - Configuration loading from file + env vars
   - Error recovery scenarios

3. Setup test infrastructure:
   - Mock Gitea API responses (httpx mock)
   - Mock Claude API responses
   - Temporary directories for state management
   - Test configuration fixtures

4. Test the workflow engine:
   - State transitions
   - Task execution
   - Error handling
   - Rollback scenarios

5. Use pytest-asyncio for async tests
6. Use pytest fixtures for complex setup
7. Clean up resources after tests (tmp directories, etc.)

Example structure:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_workflow(tmp_path, mock_gitea, mock_claude):
    # Setup
    config = create_test_config(tmp_path)
    workflow = WorkflowEngine(config)

    # Execute workflow
    result = await workflow.process_issue(issue_id=42)

    # Verify
    assert result.status == "completed"
    assert mock_gitea.pull_request_created
    assert state_file_exists(tmp_path / ".automation/state/42.json")
```

Tools: Read, Write, Bash (pytest)
```

**Acceptance Criteria**:
- [ ] End-to-end workflow tests passing
- [ ] Critical paths tested
- [ ] Error scenarios covered
- [ ] Cleanup properly implemented
- [ ] Tests run in isolation

**Dependencies**: Task 2.1 (baseline)
**Deliverables**:
- `tests/integration/test_workflow_e2e.py`

---

#### Task 2.5: Achieve 75% Coverage Target
**Agent Type**: Python Testing Expert
**Priority**: HIGH
**Estimated Time**: 12 hours

**Prompt for Agent**:
```
Write tests to achieve 75%+ overall coverage for repo-sapiens:

1. Re-run coverage analysis:
   pytest tests/ -v --cov=automation --cov-report=html --cov-report=term-missing

2. Identify modules below 75% coverage from coverage report

3. Prioritize by criticality:
   - Critical: main.py, engine/*, credentials/*
   - High: config/*, git/*, rendering/*
   - Medium: providers/*, models/*
   - Low: utils/*

4. Write tests for uncovered modules, focusing on:
   - Branch coverage (all if/else paths)
   - Exception handling paths
   - Edge cases and boundary conditions
   - Integration between modules

5. For each module below 75%:
   - Create or expand test file
   - Focus on uncovered lines (see htmlcov/ report)
   - Add tests until module reaches 75%+

6. Use pytest-cov exclude patterns for:
   - Type stubs
   - Test files themselves
   - Generated code (if any)

7. Update pytest configuration in pyproject.toml:
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   addopts = "--cov=automation --cov-report=html --cov-report=term-missing --cov-fail-under=75"

8. Generate final coverage report at:
   /home/ross/Workspace/repo-agent/docs/COVERAGE_REPORT.md

Tools: Read, Write, Edit, Bash (pytest)
```

**Acceptance Criteria**:
- [ ] Overall coverage ≥ 75%
- [ ] Critical modules ≥ 80%
- [ ] High priority modules ≥ 75%
- [ ] Coverage report generated
- [ ] CI configuration updated to enforce 75% minimum

**Dependencies**: Tasks 2.1-2.4
**Deliverables**:
- Multiple test files (varies by module)
- `/home/ross/Workspace/repo-agent/docs/COVERAGE_REPORT.md`
- Updated `pyproject.toml`

---

### PHASE 3: Documentation & API Reference (Week 3-4)

**Objective**: Create comprehensive documentation for users and developers

#### Task 3.1: API Documentation - Docstrings Audit
**Agent Type**: Python Documentation Expert
**Priority**: HIGH
**Estimated Time**: 8 hours

**Prompt for Agent**:
```
Audit and enhance docstrings across the repo-sapiens codebase:

1. Review all public APIs in automation/ for docstring coverage:
   - All public classes
   - All public functions and methods
   - Module-level docstrings

2. Enforce Google-style docstrings (current standard):
   ```python
   def function(arg1: str, arg2: int) -> bool:
       """Brief one-line summary.

       Longer description if needed. Explain what the function does,
       not how it does it (implementation details in code).

       Args:
           arg1: Description of arg1
           arg2: Description of arg2

       Returns:
           Description of return value

       Raises:
           ValueError: When arg1 is empty
           TypeError: When arg2 is negative

       Examples:
           >>> function("test", 42)
           True
       """
   ```

3. Prioritize documentation for:
   - Public APIs in automation/__init__.py
   - Configuration classes in automation/config/
   - Credential system in automation/credentials/
   - CLI commands in automation/main.py
   - Core models in automation/models/

4. Check for common docstring issues:
   - Missing Args/Returns sections
   - Undocumented exceptions
   - Outdated documentation
   - Unclear descriptions
   - Missing type hints in docstring

5. Generate audit report at:
   /home/ross/Workspace/repo-agent/docs/DOCSTRING_AUDIT.md

   Include:
   - Modules missing docstrings
   - Functions/classes needing improvement
   - Docstring quality score (% documented)

6. Update docstrings using Edit tool (don't rewrite entire files)

Tools: Read, Edit, Write, Grep
```

**Acceptance Criteria**:
- [ ] All public APIs have docstrings
- [ ] Google-style docstring format consistent
- [ ] Args, Returns, Raises sections complete
- [ ] Examples provided for complex functions
- [ ] Audit report generated

**Dependencies**: None
**Deliverables**:
- Updated docstrings across codebase
- `/home/ross/Workspace/repo-agent/docs/DOCSTRING_AUDIT.md`

---

#### Task 3.2: User Guide - Getting Started
**Agent Type**: Technical Writer (Python-savvy)
**Priority**: HIGH
**Estimated Time**: 6 hours

**Prompt for Agent**:
```
Create a comprehensive Getting Started guide for repo-sapiens users:

1. Create file at:
   /home/ross/Workspace/repo-agent/docs/GETTING_STARTED.md

2. Structure:

   # Getting Started with repo-sapiens

   ## Introduction
   - What is repo-sapiens?
   - Key features
   - Use cases

   ## Installation
   - Prerequisites (Python 3.11+, git)
   - Installing from PyPI: pip install repo-sapiens
   - Installing from source
   - Optional dependencies: [monitoring], [analytics], [dev]

   ## Quick Start (5 minutes)
   - Setting up credentials
   - Creating first configuration file
   - Running first command
   - Expected output

   ## Configuration
   - Configuration file structure
   - Environment variables
   - Credential management options:
     * Keyring (recommended for desktop)
     * Environment variables (CI/CD)
     * Encrypted file (self-hosted)

   ## Basic Workflows
   - Automating issue processing
   - Using the daemon mode
   - Webhook integration

   ## Common Tasks
   - List active plans
   - Process a specific issue
   - Check system health
   - View logs

   ## Troubleshooting
   - Common errors and solutions
   - Debug logging
   - Getting help

   ## Next Steps
   - Advanced configuration
   - CI/CD integration
   - Template customization

3. Include code examples for every section
4. Add command output examples
5. Use clear, beginner-friendly language
6. Cross-reference other docs (CI_CD_GUIDE.md, etc.)

Tools: Read, Write
```

**Acceptance Criteria**:
- [ ] Getting started guide complete
- [ ] All installation methods documented
- [ ] Configuration examples provided
- [ ] Troubleshooting section comprehensive
- [ ] Beginner-friendly language

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/GETTING_STARTED.md`

---

#### Task 3.3: API Reference Documentation
**Agent Type**: Python Documentation Expert
**Priority**: MEDIUM
**Estimated Time**: 10 hours

**Prompt for Agent**:
```
Generate comprehensive API reference documentation using Sphinx or mkdocs:

1. Choose documentation tool:
   - Sphinx (recommended for Python projects)
   - mkdocs with mkdocstrings plugin

2. Set up documentation infrastructure:
   - Create docs/source/ directory structure
   - Configure Sphinx/mkdocs
   - Set up auto-API generation from docstrings
   - Configure theme (ReadTheDocs or Material for mkdocs)

3. Generate API reference for:
   - automation.config (Settings, CredentialSecret)
   - automation.credentials (all backends, resolver)
   - automation.git (discovery, parser, models)
   - automation.rendering (template engine)
   - automation.cli (CLI interface)
   - automation.models (domain models)

4. Create documentation structure:
   ```
   docs/
   ├── index.md (main landing page)
   ├── getting-started.md (link to existing)
   ├── user-guide/
   │   ├── installation.md
   │   ├── configuration.md
   │   └── workflows.md
   ├── api/
   │   ├── config.md
   │   ├── credentials.md
   │   ├── git.md
   │   ├── rendering.md
   │   └── models.md
   └── developer-guide/
       ├── contributing.md
       ├── architecture.md
       └── testing.md
   ```

5. Set up documentation build:
   - Add dev dependency: sphinx or mkdocs
   - Create build script
   - Test local build: make html or mkdocs serve
   - Verify all docstrings rendered correctly

6. Configure ReadTheDocs or GitHub Pages for hosting

7. Update README.md with link to documentation

Tools: Write, Bash, Edit
```

**Acceptance Criteria**:
- [ ] Documentation infrastructure set up
- [ ] API reference generated from docstrings
- [ ] All modules documented
- [ ] Documentation builds without errors
- [ ] Hosted documentation link working

**Dependencies**: Task 3.1 (docstrings)
**Deliverables**:
- `docs/` directory with Sphinx/mkdocs setup
- Generated API documentation
- Build scripts and configuration

---

#### Task 3.4: Developer Guide & Contributing
**Agent Type**: Technical Writer (Python-savvy)
**Priority**: MEDIUM
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Create developer documentation and contributing guidelines:

1. Create CONTRIBUTING.md in repository root:

   # Contributing to repo-sapiens

   ## Development Setup
   - Fork and clone
   - Virtual environment setup
   - Install development dependencies
   - Run tests

   ## Code Style
   - PEP 8 compliance
   - Type hints required
   - Docstring format (Google style)
   - Black formatting (line length 100)
   - Ruff linting

   ## Testing Requirements
   - Write tests for new features
   - Maintain 75%+ coverage
   - Run full test suite before PR

   ## Pull Request Process
   - Create feature branch
   - Write descriptive commit messages
   - Update documentation
   - Update CHANGELOG.md

   ## Code Review Guidelines
   - What reviewers look for
   - Common feedback

   ## Release Process
   - Version numbering (semver)
   - Changelog updates
   - Tag creation

2. Create docs/ARCHITECTURE.md:

   # Architecture Overview

   ## System Components
   - Configuration system
   - Credential management
   - Git operations
   - Template rendering
   - Workflow engine

   ## Design Patterns
   - Dependency injection
   - Strategy pattern (credential backends)
   - Factory pattern (provider creation)

   ## Data Flow
   - Configuration loading
   - Credential resolution
   - Workflow execution

   ## Extension Points
   - Adding new credential backends
   - Adding new Git providers
   - Custom templates

3. Include architecture diagrams (text/ASCII or links to images)

Tools: Write, Read
```

**Acceptance Criteria**:
- [ ] CONTRIBUTING.md complete
- [ ] Architecture documented
- [ ] Extension points documented
- [ ] Developer setup instructions clear
- [ ] Code review guidelines defined

**Dependencies**: None
**Deliverables**:
- `/home/ross/Workspace/repo-agent/CONTRIBUTING.md`
- `/home/ross/Workspace/repo-agent/docs/ARCHITECTURE.md`

---

### PHASE 4: Performance & Quality (Week 4-5)

**Objective**: Optimize performance and ensure production-grade quality

#### Task 4.1: Performance Benchmarking
**Agent Type**: Python Performance Expert
**Priority**: MEDIUM
**Estimated Time**: 8 hours

**Prompt for Agent**:
```
Create performance benchmarks for repo-sapiens critical paths:

1. Install benchmarking tools:
   pip install pytest-benchmark memory_profiler

2. Create benchmark suite at:
   tests/benchmarks/test_performance.py

3. Benchmark critical operations:

   a) Configuration Loading
      - Load from YAML file
      - Environment variable resolution
      - Credential resolution
      - Target: <100ms for typical config

   b) Git Discovery
      - Repository detection
      - Config parsing
      - Target: <200ms for 10 repositories

   c) Template Rendering
      - Simple template (no logic)
      - Complex template (loops, conditionals)
      - Target: <50ms for simple, <200ms for complex

   d) Credential Resolution
      - Keyring backend
      - Environment backend
      - Encrypted backend
      - Target: <50ms per credential

   e) State Management
      - Read state file
      - Update state file (atomic)
      - Target: <100ms per operation

4. Create benchmark runner:
   ```python
   import pytest

   def test_config_loading_benchmark(benchmark):
       result = benchmark(load_config, 'test_config.yaml')
       assert result is not None
   ```

5. Run benchmarks and collect baseline:
   pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmark_results.json

6. Create performance report at:
   /home/ross/Workspace/repo-agent/docs/PERFORMANCE_BENCHMARKS.md

   Include:
   - Benchmark results table
   - Performance targets vs actuals
   - Bottlenecks identified
   - Optimization recommendations

7. Memory profiling for large operations:
   - Large repository discovery (100+ repos)
   - Template rendering with large data
   - State file management

Tools: Write, Bash, Read
```

**Acceptance Criteria**:
- [ ] Benchmark suite created
- [ ] Critical paths benchmarked
- [ ] Performance baseline established
- [ ] Bottlenecks identified
- [ ] Report with recommendations

**Dependencies**: None
**Deliverables**:
- `tests/benchmarks/test_performance.py`
- `/home/ross/Workspace/repo-agent/docs/PERFORMANCE_BENCHMARKS.md`
- `benchmark_results.json`

---

#### Task 4.2: Error Handling Standardization
**Agent Type**: Python Expert
**Priority**: HIGH
**Estimated Time**: 6 hours

**Prompt for Agent**:
```
Standardize error handling across the repo-sapiens codebase:

1. Create custom exception hierarchy at:
   automation/exceptions.py

   ```python
   """Custom exceptions for repo-sapiens."""

   class RepoSapiensError(Exception):
       """Base exception for all repo-sapiens errors."""
       pass

   class ConfigurationError(RepoSapiensError):
       """Configuration-related errors."""
       pass

   class CredentialError(RepoSapiensError):
       """Credential-related errors."""
       pass

   class GitOperationError(RepoSapiensError):
       """Git operation errors."""
       pass

   class TemplateError(RepoSapiensError):
       """Template rendering errors."""
       pass

   class WorkflowError(RepoSapiensError):
       """Workflow execution errors."""
       pass
   ```

2. Audit all exception handling:
   - Find bare `except:` clauses (anti-pattern)
   - Find `except Exception:` without re-raising
   - Find missing exception handling in critical paths

3. Implement error handling best practices:

   a) Specific exception types:
      ```python
      # Bad
      try:
          config = load_config(path)
      except Exception as e:
          print(f"Error: {e}")

      # Good
      try:
          config = load_config(path)
      except FileNotFoundError:
          raise ConfigurationError(f"Config file not found: {path}")
      except yaml.YAMLError as e:
          raise ConfigurationError(f"Invalid YAML in {path}: {e}")
      ```

   b) Context preservation:
      ```python
      try:
          credential = resolve_credential(ref)
      except KeyError as e:
          raise CredentialError(f"Credential not found: {ref}") from e
      ```

   c) User-friendly error messages:
      ```python
      raise ConfigurationError(
          f"Invalid configuration: {field} must be a valid URL. "
          f"Got: {value}. Example: https://gitea.example.com"
      )
      ```

4. Add error handling to CLI:
   - Catch RepoSapiensError exceptions
   - Display user-friendly messages
   - Exit with appropriate codes
   - Log full traceback at DEBUG level

5. Update existing code to use new exception hierarchy

6. Document error handling in:
   /home/ross/Workspace/repo-agent/docs/ERROR_HANDLING.md

Tools: Read, Edit, Write, Grep
```

**Acceptance Criteria**:
- [ ] Custom exception hierarchy created
- [ ] All bare except clauses replaced
- [ ] Specific exception types used
- [ ] User-friendly error messages
- [ ] CLI error handling improved

**Dependencies**: None
**Deliverables**:
- `automation/exceptions.py`
- Updated error handling across codebase
- `/home/ross/Workspace/repo-agent/docs/ERROR_HANDLING.md`

---

#### Task 4.3: Logging Standardization
**Agent Type**: Python Expert
**Priority**: MEDIUM
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Standardize logging across repo-sapiens using structlog:

1. Audit current logging usage:
   - Find all logging calls
   - Check for print() statements (should use logger)
   - Verify structlog configuration

2. Create logging configuration module:
   automation/logging_config.py

   ```python
   """Logging configuration for repo-sapiens."""
   import structlog
   from typing import Optional

   def configure_logging(
       level: str = "INFO",
       json_logs: bool = False,
       context: Optional[dict] = None
   ) -> None:
       """Configure structured logging.

       Args:
           level: Logging level (DEBUG, INFO, WARNING, ERROR)
           json_logs: Output logs as JSON (for production)
           context: Additional context to include in all logs
       """
       processors = [
           structlog.stdlib.add_log_level,
           structlog.stdlib.add_logger_name,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.StackInfoRenderer(),
           structlog.processors.format_exc_info,
       ]

       if json_logs:
           processors.append(structlog.processors.JSONRenderer())
       else:
           processors.append(structlog.dev.ConsoleRenderer())

       structlog.configure(processors=processors, ...)
   ```

3. Standardize log levels:
   - DEBUG: Detailed diagnostic information
   - INFO: General informational messages
   - WARNING: Warning messages (deprecated features, etc.)
   - ERROR: Error messages (but application continues)
   - CRITICAL: Critical errors (application may stop)

4. Add context to logs:
   ```python
   logger = structlog.get_logger()
   logger.info(
       "processing_issue",
       issue_id=42,
       repository="owner/repo",
       stage="planning"
   )
   ```

5. Ensure no sensitive data in logs:
   - Redact credentials
   - Redact API tokens
   - Redact file contents with secrets

6. Replace print() statements with logger calls

7. Update CLI to initialize logging based on --log-level flag

Tools: Read, Edit, Grep
```

**Acceptance Criteria**:
- [ ] Logging configuration centralized
- [ ] All print() statements replaced
- [ ] Structured logging with context
- [ ] No sensitive data in logs
- [ ] CLI logging initialization

**Dependencies**: None
**Deliverables**:
- `automation/logging_config.py`
- Updated logging across codebase

---

#### Task 4.4: Type Checking with mypy
**Agent Type**: Python Type Expert
**Priority**: MEDIUM
**Estimated Time**: 8 hours

**Prompt for Agent**:
```
Ensure full type checking compliance with mypy strict mode:

1. Run mypy on codebase:
   cd /home/ross/Workspace/repo-agent
   mypy automation/ --strict

2. Fix all mypy errors:
   - Add missing type hints
   - Fix Any types (use specific types)
   - Add # type: ignore only when necessary with explanation
   - Fix incompatible types
   - Add Protocol types for duck typing

3. Common fixes needed:

   a) Function signatures:
      ```python
      # Before
      def process_issue(issue_id, config):
          ...

      # After
      def process_issue(issue_id: int, config: AutomationSettings) -> ProcessResult:
          ...
      ```

   b) Optional types:
      ```python
      # Before
      def get_credential(key: str) -> str:
          return self.credentials.get(key)  # Could be None!

      # After
      def get_credential(key: str) -> Optional[str]:
          return self.credentials.get(key)
      ```

   c) Generic types:
      ```python
      from typing import Dict, List, Any

      # Before
      def parse_config(data: dict) -> dict:

      # After
      def parse_config(data: Dict[str, Any]) -> Dict[str, Any]:
      ```

4. Verify py.typed is in automation/ root

5. Run mypy in CI:
   Update GitHub Actions / Gitea Actions workflow

6. Document type checking guidelines in:
   /home/ross/Workspace/repo-agent/docs/TYPE_CHECKING.md

Tools: Bash (mypy), Read, Edit
```

**Acceptance Criteria**:
- [ ] mypy --strict passes with zero errors
- [ ] All functions have type hints
- [ ] Optional types properly used
- [ ] Generic types specified
- [ ] Type checking in CI

**Dependencies**: None
**Deliverables**:
- Type hints added across codebase
- `/home/ross/Workspace/repo-agent/docs/TYPE_CHECKING.md`
- Updated CI configuration

---

### PHASE 5: PyPI Publication (Week 5-6)

**Objective**: Publish to PyPI following validation on TestPyPI

#### Task 5.1: Package Build & Validation
**Agent Type**: Python Packaging Expert
**Priority**: CRITICAL
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Build and validate repo-sapiens package for PyPI publication:

1. Verify pyproject.toml configuration:
   - name = "repo-sapiens"
   - version = {attr = "automation.__version__"} (not double attr)
   - license = "MIT" (SPDX identifier)
   - All metadata fields complete
   - Dependencies correctly specified

2. Build package:
   cd /home/ross/Workspace/repo-agent
   python -m build --sdist --wheel

3. Verify build artifacts:
   ls -lh dist/
   # Should see:
   # repo_sapiens-0.1.0-py3-none-any.whl
   # repo_sapiens-0.1.0.tar.gz

4. Inspect wheel contents:
   unzip -l dist/repo_sapiens-0.1.0-py3-none-any.whl
   # Verify includes:
   # - automation/ package
   # - automation/py.typed
   # - automation/templates/
   # - automation/config/*.yaml
   # - No test files
   # - No .env files

5. Inspect source distribution:
   tar -tzf dist/repo_sapiens-0.1.0.tar.gz
   # Verify includes:
   # - All source files
   # - pyproject.toml
   # - README.md
   # - LICENSE
   # - MANIFEST.in

6. Run twine check:
   twine check dist/*
   # Must pass with no warnings

7. Test installation in clean venv:
   python -m venv /tmp/test-install
   source /tmp/test-install/bin/activate
   pip install dist/repo_sapiens-0.1.0-py3-none-any.whl

   # Verify:
   python -c "from automation import __version__; print(__version__)"
   # Should print: 0.1.0

   automation --version
   # Should print: automation, version 0.1.0

   python -c "import automation.credentials"
   python -c "import automation.config"
   python -c "import automation.git"

   # No import errors = success

8. Test with optional dependencies:
   pip install dist/repo_sapiens-0.1.0-py3-none-any.whl[monitoring]
   python -c "import prometheus_client"

   pip install dist/repo_sapiens-0.1.0-py3-none-any.whl[all]
   # All optional deps should install

9. Create validation report at:
   /home/ross/Workspace/repo-agent/docs/PACKAGE_VALIDATION.md

Tools: Bash, Read, Write
```

**Acceptance Criteria**:
- [ ] Package builds without errors
- [ ] Wheel and sdist created
- [ ] twine check passes
- [ ] Clean install works
- [ ] All imports succeed
- [ ] CLI commands work
- [ ] Optional dependencies work

**Dependencies**: All previous phases (quality gates)
**Deliverables**:
- `dist/repo_sapiens-0.1.0-py3-none-any.whl`
- `dist/repo_sapiens-0.1.0.tar.gz`
- `/home/ross/Workspace/repo-agent/docs/PACKAGE_VALIDATION.md`

---

#### Task 5.2: TestPyPI Publication & Validation
**Agent Type**: Python Packaging Expert
**Priority**: CRITICAL
**Estimated Time**: 2 hours

**Prompt for Agent**:
```
Upload package to TestPyPI and validate installation:

1. Register on TestPyPI (if not done):
   https://test.pypi.org/account/register/

2. Create API token on TestPyPI:
   https://test.pypi.org/manage/account/token/
   Scope: Entire account (or specific to repo-sapiens)

3. Configure credentials:
   # Option 1: Interactive
   twine upload --repository testpypi dist/*

   # Option 2: Token via environment variable
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=pypi-...
   twine upload --repository testpypi dist/*

4. Upload to TestPyPI:
   twine upload --repository testpypi dist/*

   # Expected output:
   # Uploading distributions to https://test.pypi.org/legacy/
   # Uploading repo_sapiens-0.1.0-py3-none-any.whl
   # Uploading repo_sapiens-0.1.0.tar.gz

5. Verify upload:
   https://test.pypi.org/project/repo-sapiens/

   Check:
   - Version 0.1.0 appears
   - README renders correctly
   - Metadata is correct
   - Download links work

6. Test installation from TestPyPI:
   python -m venv /tmp/testpypi-install
   source /tmp/testpypi-install/bin/activate

   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ \
               repo-sapiens

   # Note: --extra-index-url needed for dependencies

7. Smoke test installation:
   python -c "from automation import __version__; print(__version__)"
   automation --help
   automation --version

8. Test with optional dependencies:
   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ \
               repo-sapiens[all]

9. Create TestPyPI validation report at:
   /home/ross/Workspace/repo-agent/docs/TESTPYPI_VALIDATION.md

Tools: Bash, Write
```

**Acceptance Criteria**:
- [ ] Package uploaded to TestPyPI
- [ ] TestPyPI page displays correctly
- [ ] Installation from TestPyPI works
- [ ] All smoke tests pass
- [ ] Optional dependencies work
- [ ] No errors or warnings

**Dependencies**: Task 5.1 (package build)
**Deliverables**:
- Package published to TestPyPI
- `/home/ross/Workspace/repo-agent/docs/TESTPYPI_VALIDATION.md`

---

#### Task 5.3: Production PyPI Publication
**Agent Type**: Python Packaging Expert
**Priority**: CRITICAL
**Estimated Time**: 2 hours

**Prompt for Agent**:
```
Upload package to production PyPI after TestPyPI validation:

1. Prerequisites verification:
   - [ ] TestPyPI validation completed (Task 5.2)
   - [ ] All tests passing (75%+ coverage)
   - [ ] Security audit completed
   - [ ] Documentation complete
   - [ ] CHANGELOG.md updated

2. Create PyPI account (if not done):
   https://pypi.org/account/register/

3. Create API token on PyPI:
   https://pypi.org/manage/account/token/
   Scope: Entire account initially (narrow after first upload)

4. Final pre-flight checks:
   # Re-run tests
   pytest tests/ -v --cov=automation --cov-fail-under=75

   # Re-run type checking
   mypy automation/ --strict

   # Re-run linting
   ruff check automation/
   black --check automation/

   # Re-validate package
   twine check dist/*

5. Upload to PyPI:
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=pypi-...
   twine upload dist/*

   # Expected output:
   # Uploading distributions to https://upload.pypi.org/legacy/
   # Uploading repo_sapiens-0.1.0-py3-none-any.whl
   # Uploading repo_sapiens-0.1.0.tar.gz
   # View at: https://pypi.org/project/repo-sapiens/0.1.0/

6. Verify PyPI page:
   https://pypi.org/project/repo-sapiens/

   Check:
   - README renders correctly
   - All metadata correct
   - Links work
   - License displayed
   - Classifiers correct

7. Test installation from PyPI:
   python -m venv /tmp/pypi-install
   source /tmp/pypi-install/bin/activate

   pip install repo-sapiens

   # Verify version
   python -c "from automation import __version__; print(__version__)"
   # Should output: 0.1.0

8. Test CLI:
   automation --version
   automation --help
   # Verify all commands listed

9. Test optional dependencies:
   pip install repo-sapiens[monitoring]
   pip install repo-sapiens[all]

10. Create announcement content for:
    - GitHub release notes
    - Project README
    - Social media (if applicable)

11. Create publication report at:
    /home/ross/Workspace/repo-agent/docs/PYPI_PUBLICATION.md

Tools: Bash, Write
```

**Acceptance Criteria**:
- [ ] Package uploaded to PyPI
- [ ] PyPI page displays correctly
- [ ] Installation from PyPI works
- [ ] All CLI commands accessible
- [ ] Optional dependencies work
- [ ] Version 0.1.0 publicly available

**Dependencies**: Task 5.2 (TestPyPI validation)
**Deliverables**:
- Package published to PyPI
- `/home/ross/Workspace/repo-agent/docs/PYPI_PUBLICATION.md`
- Announcement content

---

### PHASE 6: Release Automation & CI/CD (Week 6-7)

**Objective**: Automate release process for future versions

#### Task 6.1: Automated Testing in CI
**Agent Type**: DevOps/Python Expert
**Priority**: HIGH
**Estimated Time**: 6 hours

**Prompt for Agent**:
```
Set up comprehensive automated testing in Gitea Actions:

1. Create workflow file:
   .gitea/workflows/tests.yaml

2. Workflow structure:
   ```yaml
   name: Tests

   on:
     push:
       branches: [main]
     pull_request:
       branches: [main]

   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: ['3.11', '3.12']

       steps:
         - uses: actions/checkout@v4

         - name: Set up Python ${{ matrix.python-version }}
           uses: actions/setup-python@v4
           with:
             python-version: ${{ matrix.python-version }}

         - name: Install dependencies
           run: |
             python -m pip install --upgrade pip
             pip install -e .[dev]

         - name: Run tests with coverage
           run: |
             pytest tests/ -v \
               --cov=automation \
               --cov-report=term-missing \
               --cov-report=xml \
               --cov-fail-under=75

         - name: Type checking
           run: mypy automation/ --strict

         - name: Linting
           run: |
             ruff check automation/
             black --check automation/

         - name: Security scanning
           run: |
             pip install bandit safety
             bandit -r automation/ -f json -o bandit-report.json
             safety check --json

         - name: Upload coverage
           uses: codecov/codecov-action@v3
           with:
             file: ./coverage.xml
   ```

3. Add additional workflows:

   a) .gitea/workflows/security.yaml
      - Dependency scanning (safety, pip-audit)
      - SAST scanning (bandit)
      - Secret scanning (truffleHog)

   b) .gitea/workflows/docs.yaml
      - Build documentation
      - Deploy to GitHub Pages
      - Check for broken links

4. Configure branch protection:
   - Require tests to pass
   - Require type checking
   - Require code review

5. Test workflows locally with act (if available):
   act -l
   act push

6. Document CI/CD setup in:
   /home/ross/Workspace/repo-agent/docs/CI_CD_SETUP.md

Tools: Write, Read
```

**Acceptance Criteria**:
- [ ] Test workflow created and working
- [ ] Matrix testing (Python 3.11, 3.12)
- [ ] Coverage enforcement (75%+)
- [ ] Type checking in CI
- [ ] Linting in CI
- [ ] Security scanning in CI

**Dependencies**: None
**Deliverables**:
- `.gitea/workflows/tests.yaml`
- `.gitea/workflows/security.yaml`
- `.gitea/workflows/docs.yaml`
- `/home/ross/Workspace/repo-agent/docs/CI_CD_SETUP.md`

---

#### Task 6.2: Automated Release Workflow
**Agent Type**: DevOps/Python Expert
**Priority**: HIGH
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Create automated release workflow for publishing to PyPI:

1. Create workflow file:
   .gitea/workflows/release.yaml

2. Workflow structure:
   ```yaml
   name: Release to PyPI

   on:
     push:
       tags:
         - 'v*'

   jobs:
     release:
       runs-on: ubuntu-latest

       steps:
         - uses: actions/checkout@v4

         - name: Set up Python
           uses: actions/setup-python@v4
           with:
             python-version: '3.11'

         - name: Install dependencies
           run: |
             python -m pip install --upgrade pip
             pip install build twine

         - name: Verify version matches tag
           run: |
             TAG_VERSION=${GITHUB_REF#refs/tags/v}
             PKG_VERSION=$(python -c "from automation import __version__; print(__version__)")
             if [ "$TAG_VERSION" != "$PKG_VERSION" ]; then
               echo "Tag version ($TAG_VERSION) != package version ($PKG_VERSION)"
               exit 1
             fi

         - name: Run tests
           run: |
             pip install -e .[dev]
             pytest tests/ -v --cov-fail-under=75

         - name: Build package
           run: python -m build

         - name: Check package
           run: twine check dist/*

         - name: Publish to TestPyPI
           env:
             TWINE_USERNAME: __token__
             TWINE_PASSWORD: ${{ secrets.TEST_PYPI_TOKEN }}
           run: |
             twine upload --repository testpypi dist/*

         - name: Wait for TestPyPI propagation
           run: sleep 30

         - name: Test install from TestPyPI
           run: |
             python -m venv /tmp/test-install
             /tmp/test-install/bin/pip install \
               --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ \
               repo-sapiens==$TAG_VERSION

         - name: Publish to PyPI
           env:
             TWINE_USERNAME: __token__
             TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
           run: |
             twine upload dist/*

         - name: Create GitHub Release
           uses: actions/create-release@v1
           env:
             GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
           with:
             tag_name: ${{ github.ref }}
             release_name: Release ${{ github.ref }}
             body_path: CHANGELOG.md
             draft: false
             prerelease: false
   ```

3. Configure secrets in Gitea:
   - TEST_PYPI_TOKEN
   - PYPI_TOKEN
   - GITHUB_TOKEN (if using GitHub releases)

4. Create release checklist:
   /home/ross/Workspace/repo-agent/docs/RELEASE_CHECKLIST.md

   ```markdown
   # Release Checklist

   Before creating a release tag:

   - [ ] All tests passing
   - [ ] Coverage ≥ 75%
   - [ ] Type checking passes (mypy --strict)
   - [ ] Linting passes (ruff, black)
   - [ ] Security scans pass
   - [ ] CHANGELOG.md updated
   - [ ] Version bumped in automation/__version__.py
   - [ ] Documentation updated
   - [ ] README.md updated

   Create release:

   1. Update version: automation/__version__.py
   2. Update CHANGELOG.md
   3. Commit: git commit -m "chore: Release v0.X.Y"
   4. Tag: git tag v0.X.Y
   5. Push: git push && git push --tags
   6. Automated workflow handles PyPI publication
   7. Verify on PyPI: https://pypi.org/project/repo-sapiens/
   8. Test install: pip install repo-sapiens==0.X.Y
   ```

5. Test workflow with a pre-release tag:
   git tag v0.1.0-rc1
   git push --tags

Tools: Write, Read
```

**Acceptance Criteria**:
- [ ] Release workflow created
- [ ] Version verification implemented
- [ ] TestPyPI validation before production
- [ ] Secrets configured
- [ ] Release checklist documented

**Dependencies**: Task 6.1 (CI setup)
**Deliverables**:
- `.gitea/workflows/release.yaml`
- `/home/ross/Workspace/repo-agent/docs/RELEASE_CHECKLIST.md`

---

#### Task 6.3: Version Bump Automation
**Agent Type**: DevOps/Python Expert
**Priority**: LOW
**Estimated Time**: 3 hours

**Prompt for Agent**:
```
Create tooling to automate version bumping and release preparation:

1. Create version management script:
   scripts/bump_version.py

   ```python
   #!/usr/bin/env python3
   """Bump version and prepare for release."""

   import re
   import sys
   from pathlib import Path
   from datetime import date

   def bump_version(current: str, part: str) -> str:
       """Bump semantic version.

       Args:
           current: Current version (e.g., "0.1.0")
           part: Part to bump ("major", "minor", "patch")

       Returns:
           New version string
       """
       major, minor, patch = map(int, current.split('.'))

       if part == 'major':
           return f"{major + 1}.0.0"
       elif part == 'minor':
           return f"{major}.{minor + 1}.0"
       elif part == 'patch':
           return f"{major}.{minor}.{patch + 1}"
       else:
           raise ValueError(f"Invalid part: {part}")

   def update_version_file(new_version: str) -> None:
       """Update automation/__version__.py"""
       version_file = Path("automation/__version__.py")
       content = version_file.read_text()
       updated = re.sub(
           r'__version__ = "[^"]+"',
           f'__version__ = "{new_version}"',
           content
       )
       version_file.write_text(updated)

   def update_changelog(new_version: str) -> None:
       """Update CHANGELOG.md with new version."""
       changelog = Path("CHANGELOG.md")
       content = changelog.read_text()

       today = date.today().isoformat()
       release_header = f"\n## [{new_version}] - {today}\n"

       # Replace [Unreleased] with version
       updated = content.replace(
           "## [Unreleased]",
           f"## [Unreleased]\n{release_header}"
       )

       changelog.write_text(updated)

   if __name__ == "__main__":
       if len(sys.argv) != 2 or sys.argv[1] not in ['major', 'minor', 'patch']:
           print("Usage: python scripts/bump_version.py [major|minor|patch]")
           sys.exit(1)

       part = sys.argv[1]

       # Read current version
       version_file = Path("automation/__version__.py")
       match = re.search(r'__version__ = "([^"]+)"', version_file.read_text())
       current = match.group(1)

       # Bump version
       new_version = bump_version(current, part)

       print(f"Bumping version: {current} → {new_version}")

       # Update files
       update_version_file(new_version)
       update_changelog(new_version)

       print(f"\nVersion bumped to {new_version}")
       print("\nNext steps:")
       print(f"  1. Review changes: git diff")
       print(f"  2. Commit: git commit -am 'chore: Release v{new_version}'")
       print(f"  3. Tag: git tag v{new_version}")
       print(f"  4. Push: git push && git push --tags")
   ```

2. Make script executable:
   chmod +x scripts/bump_version.py

3. Test version bumping:
   python scripts/bump_version.py patch
   # Should bump 0.1.0 → 0.1.1

4. Create pre-commit hook (optional):
   .git/hooks/pre-commit

   ```bash
   #!/bin/bash
   # Verify version format before commit

   VERSION=$(python -c "from automation import __version__; print(__version__)")

   if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
     echo "Error: Invalid version format: $VERSION"
     exit 1
   fi
   ```

5. Document version management in:
   /home/ross/Workspace/repo-agent/docs/VERSION_MANAGEMENT.md

Tools: Write, Bash
```

**Acceptance Criteria**:
- [ ] Version bump script created
- [ ] Script updates __version__.py
- [ ] Script updates CHANGELOG.md
- [ ] Script tested and working
- [ ] Documentation complete

**Dependencies**: None
**Deliverables**:
- `scripts/bump_version.py`
- `/home/ross/Workspace/repo-agent/docs/VERSION_MANAGEMENT.md`

---

### PHASE 7: Final Validation & Launch (Week 7-8)

**Objective**: Final validation and production launch

#### Task 7.1: Complete Security Review
**Agent Type**: Security Expert
**Priority**: CRITICAL
**Estimated Time**: 4 hours

**Prompt for Agent**:
```
Perform final comprehensive security review before v0.1.0 release:

1. Review all security audit reports from Phase 1:
   - docs/SECURITY_AUDIT.md
   - docs/INPUT_VALIDATION_AUDIT.md
   - docs/SECRETS_SCAN.md

2. Verify all critical and high severity issues resolved:
   - Re-run security scans
   - Verify fixes implemented
   - Test remediation effectiveness

3. Additional security checks:

   a) Dependency vulnerabilities:
      pip install safety pip-audit
      safety check
      pip-audit

   b) SAST scanning:
      bandit -r automation/ -ll -f screen

   c) License compliance:
      pip install pip-licenses
      pip-licenses --format=markdown --with-urls

   d) Secrets in build artifacts:
      unzip -l dist/repo_sapiens-0.1.0-py3-none-any.whl | grep -i secret

4. Review README and documentation:
   - No hardcoded credentials in examples
   - Security best practices documented
   - Responsible disclosure policy

5. Create final security sign-off:
   /home/ross/Workspace/repo-agent/docs/SECURITY_SIGN_OFF.md

   Include:
   - All audits completed
   - All critical issues resolved
   - Remaining known issues (with mitigation)
   - Security testing results
   - Sign-off statement

Tools: Bash, Read, Write
```

**Acceptance Criteria**:
- [ ] All security audits reviewed
- [ ] Critical issues resolved
- [ ] Dependency vulnerabilities addressed
- [ ] No secrets in build artifacts
- [ ] Security sign-off documented

**Dependencies**: Phase 1 (Security audits)
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/SECURITY_SIGN_OFF.md`
- Updated security reports

---

#### Task 7.2: Release Candidate Testing
**Agent Type**: QA/Testing Expert
**Priority**: CRITICAL
**Estimated Time**: 6 hours

**Prompt for Agent**:
```
Test release candidate thoroughly across different environments:

1. Create test plan:
   /home/ross/Workspace/repo-agent/docs/RELEASE_TESTING_PLAN.md

2. Test matrix:

   | Platform | Python | Install Method | Test Type |
   |----------|--------|----------------|-----------|
   | Ubuntu 22.04 | 3.11 | pip | Smoke |
   | Ubuntu 22.04 | 3.12 | pip | Full |
   | Ubuntu 22.04 | 3.11 | source | Full |
   | macOS | 3.11 | pip | Smoke |
   | Windows | 3.11 | pip | Smoke |

3. Test scenarios for each environment:

   a) Installation tests:
      - Install from wheel
      - Install from source
      - Install with optional dependencies
      - Uninstall and reinstall

   b) Smoke tests:
      - Import all modules
      - Run --help for all commands
      - Run --version
      - Load example configuration

   c) Functional tests:
      - Credential resolution (all backends)
      - Configuration loading
      - Git discovery
      - Template rendering
      - CLI commands execution

   d) Integration tests:
      - Full workflow simulation
      - Error handling
      - Logging output

4. Performance tests:
   - Startup time (<2 seconds for --help)
   - Configuration loading (<500ms)
   - Credential resolution (<100ms)

5. Compatibility tests:
   - Python 3.11 and 3.12
   - Different OS (Linux, macOS, Windows)
   - Different shells (bash, zsh, powershell)

6. Document test results:
   /home/ross/Workspace/repo-agent/docs/RELEASE_TEST_RESULTS.md

   For each test:
   - Environment details
   - Test executed
   - Result (PASS/FAIL)
   - Issues found
   - Screenshots/logs (if applicable)

7. Create issues for any bugs found

Tools: Bash, Write, Read
```

**Acceptance Criteria**:
- [ ] Test plan complete
- [ ] All test scenarios executed
- [ ] Results documented
- [ ] Critical issues resolved
- [ ] RC approved for release

**Dependencies**: Task 5.1 (package build)
**Deliverables**:
- `/home/ross/Workspace/repo-agent/docs/RELEASE_TESTING_PLAN.md`
- `/home/ross/Workspace/repo-agent/docs/RELEASE_TEST_RESULTS.md`

---

#### Task 7.3: Production Release
**Agent Type**: Release Manager (DevOps Expert)
**Priority**: CRITICAL
**Estimated Time**: 2 hours

**Prompt for Agent**:
```
Execute production release of repo-sapiens v0.1.0:

1. Pre-release checklist verification:

   - [ ] All tests passing (75%+ coverage)
   - [ ] Security audits complete and signed off
   - [ ] Documentation complete
   - [ ] CHANGELOG.md updated
   - [ ] README.md updated
   - [ ] Release testing complete
   - [ ] Version bumped to 0.1.0 in automation/__version__.py
   - [ ] All CI/CD workflows passing
   - [ ] TestPyPI validation complete

2. Create release commit:
   git add automation/__version__.py CHANGELOG.md README.md
   git commit -m "chore: Release v0.1.0"

3. Create release tag:
   git tag -a v0.1.0 -m "Release v0.1.0 - Production-ready AI-driven Git workflow automation"

   Tag message should include:
   - Major features
   - Breaking changes (if any)
   - Migration notes (if any)

4. Push to repository:
   git push origin main
   git push origin v0.1.0

5. Verify automated release workflow:
   - Monitor Gitea Actions / GitHub Actions
   - Verify TestPyPI upload
   - Verify PyPI upload
   - Check for any errors

6. Manual verification (if automated workflow fails):
   # Build
   python -m build

   # Check
   twine check dist/*

   # Upload to PyPI
   twine upload dist/*

7. Verify PyPI publication:
   - Visit https://pypi.org/project/repo-sapiens/
   - Check version 0.1.0 is live
   - Verify README renders correctly
   - Test installation: pip install repo-sapiens

8. Create GitHub/Gitea release:
   - Use tag v0.1.0
   - Title: "v0.1.0 - Production-Ready Release"
   - Description: Extract from CHANGELOG.md
   - Attach build artifacts (wheel, tar.gz)

9. Update documentation links:
   - README.md (if hosted docs)
   - Project website (if applicable)

10. Announce release:
    - GitHub/Gitea discussions
    - Project blog/website
    - Social media (if applicable)

11. Monitor for issues:
    - Watch PyPI download stats
    - Monitor GitHub/Gitea issues
    - Respond to user feedback

12. Create post-release report:
    /home/ross/Workspace/repo-agent/docs/RELEASE_v0.1.0_REPORT.md

    Include:
    - Release timeline
    - Issues encountered
    - Lessons learned
    - Next steps for v0.2.0

Tools: Bash, Write
```

**Acceptance Criteria**:
- [ ] Version 0.1.0 tagged
- [ ] Package published to PyPI
- [ ] GitHub/Gitea release created
- [ ] Installation verified
- [ ] Announcement published
- [ ] Post-release report complete

**Dependencies**: All previous tasks
**Deliverables**:
- v0.1.0 tag in git
- Package published to PyPI
- GitHub/Gitea release
- `/home/ross/Workspace/repo-agent/docs/RELEASE_v0.1.0_REPORT.md`

---

## Summary of Agent Assignments

### Security Expert Tasks
- Task 1.1: Security Audit - Credential System
- Task 1.2: Input Validation & Sanitization Audit
- Task 1.3: Secrets Scanning & .gitignore Validation
- Task 7.1: Complete Security Review

### Testing Expert Tasks
- Task 2.1: Test Coverage Baseline & Gap Analysis
- Task 2.2: Core Module Tests - Configuration System
- Task 2.3: Core Module Tests - CLI Commands
- Task 2.4: Integration Tests - End-to-End Workflows
- Task 2.5: Achieve 75% Coverage Target
- Task 7.2: Release Candidate Testing

### Documentation Expert Tasks
- Task 3.1: API Documentation - Docstrings Audit
- Task 3.2: User Guide - Getting Started
- Task 3.3: API Reference Documentation
- Task 3.4: Developer Guide & Contributing

### Python Expert Tasks
- Task 4.1: Performance Benchmarking
- Task 4.2: Error Handling Standardization
- Task 4.3: Logging Standardization
- Task 4.4: Type Checking with mypy

### Packaging Expert Tasks
- Task 5.1: Package Build & Validation
- Task 5.2: TestPyPI Publication & Validation
- Task 5.3: Production PyPI Publication

### DevOps Expert Tasks
- Task 6.1: Automated Testing in CI
- Task 6.2: Automated Release Workflow
- Task 6.3: Version Bump Automation
- Task 7.3: Production Release

---

## Dependencies Map

```
Phase 1 (Security) → No dependencies, can run in parallel
├── Task 1.1 ──┐
├── Task 1.2 ──┼─→ Task 7.1 (Final security review)
└── Task 1.3 ──┘

Phase 2 (Testing) → No dependencies, can run after Task 2.1
├── Task 2.1 (Baseline) ──┬─→ Task 2.2
│                          ├─→ Task 2.3
│                          ├─→ Task 2.4
│                          └─→ Task 2.5 (depends on 2.2-2.4)
└── Task 2.5 ──→ Task 7.2 (RC Testing)

Phase 3 (Documentation)
├── Task 3.1 ──→ Task 3.3 (API docs depend on docstrings)
├── Task 3.2 ──→ No dependencies
├── Task 3.3 ──→ Depends on Task 3.1
└── Task 3.4 ──→ No dependencies

Phase 4 (Quality)
├── Task 4.1 ──→ No dependencies
├── Task 4.2 ──→ No dependencies
├── Task 4.3 ──→ No dependencies
└── Task 4.4 ──→ No dependencies

Phase 5 (PyPI)
├── Task 5.1 ──→ Depends on Phases 1-4 completion
├── Task 5.2 ──→ Depends on Task 5.1
└── Task 5.3 ──→ Depends on Task 5.2

Phase 6 (Automation)
├── Task 6.1 ──→ No dependencies
├── Task 6.2 ──→ Depends on Task 6.1
└── Task 6.3 ──→ No dependencies

Phase 7 (Launch)
├── Task 7.1 ──→ Depends on Phase 1
├── Task 7.2 ──→ Depends on Task 5.1, Phase 2
└── Task 7.3 ──→ Depends on all tasks (final release)
```

---

## Priority Matrix

### CRITICAL (Must complete for v0.1.0)
1. Task 1.1: Security Audit - Credential System
2. Task 1.3: Secrets Scanning
3. Task 2.5: Achieve 75% Coverage Target
4. Task 5.1: Package Build & Validation
5. Task 5.2: TestPyPI Publication
6. Task 5.3: Production PyPI Publication
7. Task 7.1: Complete Security Review
8. Task 7.2: Release Candidate Testing
9. Task 7.3: Production Release

### HIGH (Strongly recommended)
1. Task 1.2: Input Validation Audit
2. Task 2.1: Test Coverage Baseline
3. Task 2.2: Configuration System Tests
4. Task 2.3: CLI Command Tests
5. Task 3.1: API Documentation Audit
6. Task 3.2: User Guide
7. Task 4.2: Error Handling Standardization
8. Task 6.1: Automated Testing in CI
9. Task 6.2: Automated Release Workflow

### MEDIUM (Nice to have)
1. Task 2.4: Integration Tests
2. Task 3.3: API Reference Documentation
3. Task 3.4: Developer Guide
4. Task 4.1: Performance Benchmarking
5. Task 4.3: Logging Standardization
6. Task 4.4: Type Checking with mypy

### LOW (Can defer to v0.2.0)
1. Task 6.3: Version Bump Automation

---

## Timeline Estimate

### Week 1-2: Security Foundation
- Days 1-3: Tasks 1.1, 1.2, 1.3 (parallel execution)
- Days 4-5: Security fixes from audits
- Days 6-7: Security validation

### Week 2-3: Test Coverage
- Days 8-9: Task 2.1 (baseline)
- Days 10-12: Tasks 2.2, 2.3 (parallel)
- Days 13-15: Tasks 2.4, 2.5
- Days 16-17: Test refinement

### Week 3-4: Documentation
- Days 18-19: Task 3.1 (docstrings)
- Days 20-21: Tasks 3.2, 3.4 (parallel)
- Days 22-24: Task 3.3 (API docs)
- Days 25-26: Documentation review

### Week 4-5: Quality & Performance
- Days 27-28: Task 4.1 (benchmarks)
- Days 29-30: Task 4.2 (error handling)
- Days 31-32: Tasks 4.3, 4.4 (parallel)
- Days 33-34: Quality validation

### Week 5-6: PyPI Publication
- Days 35-36: Task 5.1 (build & validate)
- Day 37: Task 5.2 (TestPyPI)
- Day 38: Validation from TestPyPI
- Day 39: Task 5.3 (PyPI)
- Day 40: Smoke testing

### Week 6-7: Automation
- Days 41-42: Task 6.1 (CI setup)
- Days 43-44: Task 6.2 (release workflow)
- Day 45: Task 6.3 (version automation)
- Days 46-47: CI/CD testing

### Week 7-8: Final Validation & Launch
- Days 48-49: Task 7.1 (security review)
- Days 50-52: Task 7.2 (RC testing)
- Day 53: Final fixes
- Day 54: Task 7.3 (production release)
- Days 55-56: Post-release monitoring

**Total: 8 weeks (56 days)**

---

## Success Metrics

### Code Quality
- [ ] Test coverage ≥ 75%
- [ ] mypy --strict passes with 0 errors
- [ ] ruff check passes with 0 errors
- [ ] black formatting consistent
- [ ] No critical security vulnerabilities

### Documentation
- [ ] All public APIs documented
- [ ] Getting started guide complete
- [ ] API reference generated
- [ ] Contributing guide available
- [ ] Architecture documented

### Package Quality
- [ ] PyPI package builds cleanly
- [ ] Installation from PyPI works
- [ ] CLI commands accessible
- [ ] Optional dependencies work
- [ ] No broken links in README

### Release Readiness
- [ ] Automated CI/CD pipeline working
- [ ] Release workflow tested
- [ ] Security audits complete
- [ ] Performance benchmarks established
- [ ] Monitoring in place

---

## Risk Mitigation

### High-Risk Items
1. **Security vulnerabilities in credential system**
   - Mitigation: Comprehensive audit in Task 1.1, expert review
   - Fallback: Delay release until fixed

2. **Test coverage target not met**
   - Mitigation: Dedicated tasks (2.2-2.5), coverage enforcement
   - Fallback: Lower target to 70% with plan for 75% in v0.1.1

3. **PyPI publication issues**
   - Mitigation: TestPyPI validation first (Task 5.2)
   - Fallback: Manual publication if automation fails

### Medium-Risk Items
1. **Documentation incomplete**
   - Mitigation: Prioritize critical docs (Tasks 3.1, 3.2)
   - Fallback: Defer API reference (Task 3.3) to v0.1.1

2. **CI/CD workflow failures**
   - Mitigation: Test thoroughly in Task 6.1
   - Fallback: Manual release process documented

3. **Performance issues**
   - Mitigation: Benchmarking in Task 4.1
   - Fallback: Document known performance limitations

---

## Post-Release Plan

### Immediate (Week 8-9)
- Monitor PyPI download statistics
- Respond to user issues on GitHub/Gitea
- Fix critical bugs in v0.1.1 patch release
- Gather user feedback

### Short-term (Month 2-3)
- Address documentation gaps
- Improve test coverage to 80%+
- Performance optimizations
- Additional credential backends

### Long-term (v0.2.0 and beyond)
- New features based on user feedback
- Support additional Git providers (GitHub, GitLab)
- Enhanced AI agent capabilities
- Web UI for configuration

---

## Conclusion

This implementation plan provides a realistic, 6-8 week roadmap to a production-ready v0.1.0 release of repo-sapiens. The plan prioritizes security, testing, and documentation while maintaining the package's innovative AI-driven automation capabilities.

Each task is designed to be agent-executable with clear prompts, acceptance criteria, and deliverables. The phased approach allows for parallel work where possible while respecting dependencies between tasks.

The plan has been reviewed from a Python expert perspective and incorporates best practices for packaging, security, testing, and documentation. Following this plan will result in a high-quality, production-ready package suitable for PyPI publication and real-world use.

**Estimated Total Effort**: 200-250 hours across all tasks
**Timeline**: 6-8 weeks with 1-2 developers (or AI agents)
**Confidence Level**: HIGH (based on current codebase assessment)
