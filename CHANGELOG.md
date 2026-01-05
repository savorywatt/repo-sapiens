# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-01-04

### Added
- **Enhanced Init Command**: Major improvements to `sapiens init`
  - `--setup-workflows` flag to install CI/CD workflow files
  - `--setup-examples` flag to install example recurring task workflows
  - `--non-interactive` mode for CI/CD environments
  - Automatic Gitea/GitHub Actions secret configuration
  - Support for multiple AI providers (Claude, Goose, Ollama, vLLM)
- **Workflow Templates**: New `templates/workflows/` directory
  - Base templates for Gitea and GitHub Actions
  - Example recurring task workflows:
    - `daily-issue-triage.yaml` - Automated issue classification
    - `post-merge-docs.yaml` - Documentation updates after merge
    - `weekly-dependency-audit.yaml` - Dependency version checking
    - `weekly-security-review.yaml` - Security audit workflow
    - `weekly-test-coverage.yaml` - Test coverage monitoring
- **CLI Health Commands**: New monitoring commands
  - `sapiens check-stale` - Find workflows not updated within threshold
  - `sapiens health-check` - Generate system health report
  - `sapiens check-failures` - Find failed workflows in time window
- **ExecutionContext Pattern**: New dataclass for workflow stage state management
  - `ExecutionContext` in `repo_sapiens/engine/context.py` with issue, plan_id, workspace_path, branch_name, stage_outputs
  - Enables inter-stage communication via `get_stage_output()` and `set_stage_output()`
  - Immutable updates via `with_updates()` method
- **CredentialResolver Dependency Injection**: Backends can now be injected for testing
  - New `backends` parameter in `CredentialResolver.__init__()`
  - `backends` property returns custom or default backends in resolution order
  - 6 new unit tests for backend injection behavior
- **Design Decisions Section**: New ARCHITECTURE.md section documenting intentional choices
  - Credential backend interface rationale
  - Provider module structure explanation
  - Template engine naming justification
  - State persistence approach
- **Makefile**: Development convenience commands
  - `make test`, `make lint`, `make format`, `make type-check`
  - `make repl` for interactive ReAct agent
  - `make docker-build`, `make docker-run`
- **Agent Comparison Guide**: New `docs/AGENT_COMPARISON.md`
  - Decision flowchart for choosing between agents
  - Detailed comparison of ReAct, Goose, Claude Code, Ollama Provider
- **ReAct Agent Documentation**: Extended GOOSE_SETUP.md
  - Full built-in ReAct agent usage guide
  - Model recommendations and configuration
  - Interactive REPL commands reference

### Changed
- **WorkflowStage Interface**: Updated from `execute(issue)` to `execute(context)`
  - All 12 stage implementations migrated to new signature
  - Orchestrator creates ExecutionContext and passes to stages
  - Error handling updated to use context
- **CredentialResolver.resolve()**: Now iterates over `self.backends` property
  - Enables custom backend ordering for testing
  - Maintains backward compatibility with existing code
- **Code Quality**: Applied Ruff formatting and linting across codebase
  - Removed unused imports
  - Consistent string formatting
  - Improved type hints (forward references → direct types)
- **Test Suite**: Refactored unit tests for clarity
  - Reduced code duplication in test fixtures
  - Simplified mock setups
- **.gitignore**: Added `plans/*` to ignore plan working files

### Documentation
- **GETTING_STARTED.md**: Complete rewrite with Quick Start guide
  - New credential management guide (keyring, environment, encrypted)
  - Basic workflows and common tasks
  - Troubleshooting section
- **GITEA_NEW_REPO_TUTORIAL.md**: Comprehensive setup tutorial
  - Multi-provider AI setup (Claude, Ollama, vLLM)
  - Full workflow file setup
  - Label creation and configuration reference
- **ERROR_HANDLING.md**: Expanded error handling guide
  - Exception hierarchy documentation
  - CLI error handling patterns
  - ReAct agent error handling
- **ci-cd-usage.md**: Updated to reflect actual implementation
  - Correct workflow file listings
  - Accurate CLI commands
  - Label-to-workflow mappings
- **workflow-diagram.md**: Rewritten with accurate label-driven flow
  - Per-label workflow architecture
  - Fix flow documentation
  - CLI commands reference

### Fixed
- **ARCHITECTURE.md Accuracy**: Documentation now matches actual implementation
  - Corrected `CredentialBackend` interface (ABC with get/set/delete, not Protocol with resolve/can_handle)
  - Fixed Git provider paths (`repo_sapiens/providers/` not `repo_sapiens/git/`)
  - Updated template engine name (`SecureTemplateEngine` not `TemplateEngine`)
  - Fixed WorkflowOrchestrator example with correct DI pattern
  - Updated Strategy Pattern section with centralized pattern matching approach

## [0.3.0] - 2026-01-02

### Changed
- **Module Renamed**: `automation` → `repo_sapiens` for Python best practices
  - Package name now matches module name: `pip install repo-sapiens` → `import repo_sapiens`
  - All 457+ internal imports updated
- **CLI Commands Renamed**: `automation` → `sapiens` (with `repo-sapiens` alias)
  - `sapiens init` - Initialize repository
  - `sapiens react --repl` - Interactive ReAct agent REPL
  - `sapiens daemon` - Run automation daemon
  - `sapiens credentials` - Manage credentials
- **Default Ollama Model**: Changed from `llama3.1:8b` to `qwen3:latest`
- **Environment Variables**: Standardized to `SAPIENS__*` prefix (legacy `AUTOMATION__*` still supported)

### Fixed
- Documentation updated to reflect new CLI commands and module paths
- All workflow YAML files updated to use `sapiens` command
- Test coverage paths updated to `--cov=repo_sapiens`
- Default config path updated from `automation/config/` to `repo_sapiens/config/`
- Dockerfile updated: module paths, user name (`sapiens`), entrypoint
- Pre-commit config updated to target `repo_sapiens/` directory
- Docker Compose volume mounts and uvicorn module path corrected

## [0.2.0] - 2025-12-28

### Added
- **ReAct Agent**: Local AI agent using Ollama for autonomous coding tasks
  - ReAct (Reasoning + Acting) pattern with thought-action-observation loop
  - 9 built-in tools: read_file, write_file, list_directory, run_command, search_files, find_files, edit_file, tree, finish
  - Interactive REPL mode (`sapiens react --repl`) with colored prompt
  - Remote Ollama support via `--ollama-url` for running on separate GPU servers
  - Model discovery and switching (`/models`, `/model <name>` commands)
  - Path sandboxing for security - all file operations restricted to working directory
  - Trajectory tracking for debugging agent behavior
- **GitHub Support**: Full platform support for GitHub in addition to Gitea
  - Auto-detection of GitHub vs Gitea from repository remote URL
  - `GitHubRestProvider` implementation using PyGithub library
  - Provider factory pattern for automatic provider instantiation
  - GitHub Actions secret encryption support (PyNaCl)
  - Provider-agnostic workflow templates (works with both GitHub Actions and Gitea Actions)
  - Updated Git discovery module with `detect_provider_type()` and `detect_git_config()` methods
  - Enhanced init command to auto-detect GitHub and configure accordingly
  - GitHub API URL handling (api.github.com for public GitHub)
  - Support for GitHub Enterprise servers
- **Goose AI Agent Support**: Full integration with Block's Goose AI agent as an alternative to Claude
  - Multi-provider LLM backend support (OpenAI, Anthropic, Ollama, OpenRouter, Groq, Databricks)
  - Agent detection utility (`repo_sapiens/utils/agent_detector.py`) with automatic CLI discovery
  - Comprehensive provider comparison and recommendation system
  - Provider-specific credential management (keyring and environment backends)
  - Interactive configuration in init command with provider guidance
  - Support for vLLM vs Ollama local serving with tool usage recommendations
- **Enhanced Init Command**: Extended `sapiens init` to support Goose configuration
  - Interactive agent selection (Claude Code or Goose)
  - LLM provider selection with comparison table
  - Model selection from provider-specific model lists
  - Automatic credential storage with provider-specific paths
  - Gitea Actions secret setup for provider-specific API keys
- **Configuration System Updates**: Enhanced Pydantic models for multi-agent support
  - New `GooseConfig` model with toolkit, temperature, max_tokens, llm_provider
  - Updated `AgentProviderConfig` to support goose-local, goose-api provider types
  - Provider-specific credential references (@keyring:openai/api_key, ${OPENAI_API_KEY})
- **External Agent Provider**: Updated to support Goose CLI invocation
  - Correct `goose session start` command with provider, model, toolkit flags
  - Provider-specific configuration passing to Goose CLI
  - Enhanced file change detection from agent output

### Changed
- Major repository cleanup: removed 94,000+ lines of cruft (implementation notes, test scripts, unused directories)
- Added `__main__.py` for `python -m automation` support
- Static version in pyproject.toml for Poetry compatibility
- Expanded test coverage from 11% to 63% with 936 unit tests
  - ReAct agent: 100% coverage
  - Provider factory: 100% coverage
  - Ollama provider: 100% coverage
  - Gitea provider: comprehensive coverage
  - CLI credentials: 100% coverage
  - CLI init: 95% coverage
  - Main CLI: 64% coverage
  - Git discovery: comprehensive coverage
  - Engine orchestrator: 97% coverage
  - Engine stages: 87%+ coverage
  - Credential backends: 90%+ coverage
  - Agent detector: 99% coverage
  - Utils (retry, helpers, status_reporter): 100% coverage
- Rebranded package from "repo-agent" to "repo-sapiens"
- Updated all GitHub repository URLs to https://github.com/savorywatt/repo-sapiens
- Updated package maintainer to @savorywatt
- Published placeholder package to PyPI (v0.0.1 and v0.0.2)
- Refactored credential storage to support multiple LLM providers
- Enhanced agent provider configuration with goose_config section
- Updated workflow templates to be provider-agnostic (GitHub/Gitea)
- Modified `main.py` to use provider factory instead of hardcoded GiteaRestProvider
- Added new dependencies: `PyGithub>=2.1.1` and `PyNaCl>=1.5.0` for GitHub support

## [0.1.0] - 2025-12-22

### Added
- PyPI packaging with proper metadata and structure
- PEP 561 type hints support via py.typed marker file
- Split dependencies (core vs optional: monitoring, analytics, dev)
- Initial public release
- CLI commands: `automation daemon`, `automation process-issue`, `automation process-all`
- Gitea integration via REST API
- AI agent support (Claude API, Ollama)
- Workflow orchestration with state management
- Label-based issue automation
- Daemon optimization with recent activity checking
- Support for multiple AI providers
- Comprehensive logging with structlog
- Docker support for containerized deployment
- Pydantic-based configuration system
- State persistence with atomic file operations
- HTTP client with retry logic

### Fixed
- Daemon now skips execution when no recent activity detected (10-minute window)
- Label-triggered workflows now properly execute from main branch
- Virtual environment usage to avoid externally-managed-environment errors
- Duplicate workflow triggering by organizing example workflows
- PyPI packaging: Added py.typed to MANIFEST.in for source distribution support
- PyPI packaging: Verified correct version dynamic reference syntax
- PyPI packaging: Ensured MIT license properly specified (SPDX identifier)

### Validated
- Package builds successfully with python-build (wheel + source distribution)
- Both wheel and source distribution include py.typed marker file (PEP 561)
- Package metadata passes twine validation (PyPI compliance verified)
- Clean virtual environment installations work correctly
- Core dependencies install without optional dependencies (correct split)
- Version extraction works: repo_sapiens.__version__ = "0.1.0"

[0.3.0]: https://github.com/savorywatt/repo-sapiens/releases/tag/v0.3.0
[0.2.0]: https://github.com/savorywatt/repo-sapiens/releases/tag/v0.2.0
[0.1.0]: https://github.com/savorywatt/repo-sapiens/releases/tag/v0.1.0
