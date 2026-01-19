# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-01-19

### Added
- **MCP (Model Context Protocol) Support**: Unified MCP integration across all agent backends
  - `repo_sapiens/mcp/` package with registry, client, adapter, and manager modules
  - `MCPServerSpec` frozen dataclass for immutable server specifications
  - `MCPServerRegistry` protocol with `DefaultMCPRegistry` implementation
  - 9 built-in MCP servers: github, gitlab, jira, linear, taiga, git, filesystem, brave-search, fetch
  - `StdioMCPClient` for JSON-RPC 2.0 communication over stdin/stdout
  - `MCPToolAdapter` bridges MCP tools to sapiens `ToolRegistry`
  - `MCPManager` async context manager for server lifecycle (install, configure, start, teardown)
  - Process group management (`start_new_session=True`, `os.killpg()`) for reliable cleanup
  - Agent-specific config generation: `.claude.json` for Claude, `goose.yaml` for Goose
  - `MCPConfig` and `MCPServerConfig` Pydantic models with env var mapping
  - `sapiens mcp` CLI command group: list, status, configure, install, test
  - Exception hierarchy: `MCPError`, `MCPConfigError`, `MCPInstallError`, `MCPServerError`, `MCPTimeoutError`, `MCPProtocolError`
  - 121 unit tests covering registry, client, adapter, manager, and exceptions
  - Documentation: `docs/mcp-ticket-systems.md` for ticket system integration guide
- **OpenAI Function Calling Support**: ReAct agent now supports native function calling
  - `ChatResponse` and `ToolCall` dataclasses for structured tool call handling
  - `to_openai_format()` method on `ToolRegistry` for OpenAI-compatible tool definitions
  - Backend abstraction with `tools` parameter in `chat()` methods
  - `ReActConfig` extended with `backend_type`, `base_url`, `api_key`, `use_native_tools`
  - Automatic fallback to text-based parsing when native tools unavailable
  - Works with Ollama models that support tool calling (qwen3, llama3.1, etc.)
  - Works with OpenAI-compatible APIs (vLLM, llama.cpp, OpenAI)
- **Reusable Workflow Architecture**: Single dispatcher workflow replaces copy-paste templates
  - `.github/workflows/sapiens-dispatcher.yaml` - Reusable workflow for GitHub and Gitea
  - `gitlab/sapiens-dispatcher/` - GitLab CI/CD Component (requires GitLab 16.0+)
  - User repositories now need only ~20 lines instead of ~490 lines
  - Version-locked via tag reference (e.g., `@v2.1.0` installs `repo-sapiens==2.1.0`)
  - Supports all Git providers: GitHub, Gitea (uses GitHub workflow), GitLab
  - Full documentation: `docs/WORKFLOW_REFERENCE.md`, `docs/GITLAB_SETUP.md`, `docs/MIGRATION.md`
- **GitLab Bootstrap Script**: Automated setup for GitLab integration testing
  - `scripts/bootstrap-gitlab.sh` creates container, waits for health, generates API token
  - Creates test project with automation labels via Rails console
  - Optional GitLab Runner setup with `--with-runner` flag
  - Outputs `.env.gitlab-test` for easy sourcing
- **GitLab Workflow Templates**: Complete GitLab CI/CD workflow templates for all automation stages
  - `approved.yaml`, `needs-planning.yaml`, `needs-review.yaml`, `needs-fix.yaml`, `requires-qa.yaml`, `execute-task.yaml`
  - Recipe templates: `weekly-test-coverage.yaml`, `weekly-sbom-license.yaml`
  - All templates follow SAPIENS_ prefix convention for CI/CD variables
- **Multi-Remote Support**: Interactive provider selection when multiple Git remotes detected
  - Detects GitHub, GitLab, and Gitea from remote URLs during `sapiens init`
  - Uses preferred remotes (origin > upstream > first) in non-interactive mode
  - Prompts user to select provider when multiple are detected
- **GitHub Copilot Integration**: Support for GitHub Copilot as an AI agent provider
  - New `copilot-local` provider type using the official `gh copilot` CLI
  - Automatic detection of GitHub CLI and Copilot extension during `sapiens init`
  - Interactive setup with extension installation prompt
  - Health checks for GitHub CLI, Copilot extension, and authentication status
  - Integration with ExternalAgentProvider for CLI-based execution
  - Support in process-label workflow for label-triggered automation
- **Native Label Trigger System**: Instant automation via CI/CD workflows instead of daemon polling
  - `sapiens process-label` command for handling label events in workflows
  - `sapiens migrate` commands for analyzing and generating native trigger workflows
  - Event classifier for webhook events (issues, PRs, labels)
  - Label-based routing system with pattern matching and handler dispatch
  - Workflow generator for Gitea Actions, GitHub Actions, and GitLab CI
  - Label trigger configuration with customizable handlers, success/failure labels
  - `process-label.yaml` workflow templates for all three platforms
  - Automation modes: native (instant), daemon (polling), hybrid (both)
  - Comprehensive documentation in `docs/automation/native-triggers.md`
- **Automated Release Workflows**: Complete release automation via GitHub Actions-style workflows
  - `prepare-release.yaml` workflow with UI form for version, changelog entries
  - Automated version bumping in `pyproject.toml`
  - Automatic CHANGELOG.md generation and insertion
  - Git commit, tag creation, and push automation
  - `release.yaml` workflow for building and publishing on tags
  - Automatic PyPI publishing with token authentication
  - Gitea release creation with extracted CHANGELOG notes
  - Release artifact uploads (wheel + sdist) to Gitea releases
  - Complete documentation in `docs/RELEASE_PROCESS.md`
- **Enhanced Init Command**: Automation mode selection during setup
  - Interactive prompt for native/daemon/hybrid mode selection
  - Automatic `automation:` section generation in config
  - Label trigger configuration with sensible defaults
  - Deploys correct workflow templates based on selected mode
  - Mode-specific next steps guidance
  - Smart config update mode - prompts which sections to update on re-init
- **Comprehensive Validation System**: `health-check --full` for end-to-end testing
  - Tests read operations (list issues, branches, repository info)
  - Tests write operations (create branch, issue, comment, PR with cleanup)
  - Tests agent operations (connectivity, simple prompt execution)
  - Structured diagnostic reports with `DiagnosticReport` and `ValidationResult` models
  - JSON output with `--json` flag for CI/CD integration
  - LLM-generated summaries when agent is available
  - Validation workflow templates for GitHub Actions, Gitea Actions, GitLab CI
  - Optional deployment during `sapiens init`

### Changed
- **WorkflowGenerator Thin Wrappers**: `WorkflowGenerator` now generates thin wrapper workflows
  - GitHub/Gitea: ~20 line wrapper referencing `sapiens-dispatcher.yaml@vX.Y.Z`
  - GitLab: Include directive referencing CI/CD component
  - Output filename changed from `process-label.yaml` to `sapiens.yaml`
- **Secret Naming Standardization**: All secrets now use `SAPIENS_` prefix
  - `SAPIENS_GITEA_TOKEN` for Gitea (GITEA_ prefix is reserved by Gitea)
  - `SAPIENS_GITHUB_TOKEN` for GitHub (GITHUB_ prefix is reserved for custom secrets)
  - Updated all workflow templates, documentation, and code
- **Goose Agent Simplification**: Removed non-functional `goose-api` provider type
  - Goose is CLI-only, so only `goose-local` is valid
  - Updated documentation and configuration to reflect this
- **Python Requirement**: Now requires Python 3.12+ (was 3.13+)
  - Updated all workflows, Docker images, and configs
  - Better compatibility with stable Python releases
- **CI Performance**: Migrated from pip to uv for 5-10x faster builds
  - All workflows now use `astral-sh/setup-uv@v3`
  - Eliminates pip cache timeout issues (ETIMEDOUT)
  - Faster dependency installation and package builds
  - More reliable CI runs
- **Init Command Workflow Deployment**: Now asks which workflows to deploy based on automation mode
  - Native mode: deploys `process-label.yaml` for label triggers
  - Daemon mode: deploys `automation-daemon.yaml` for polling
  - Hybrid mode: deploys both workflows
  - All modes: includes `process-issue.yaml` for manual triggers
- **Test Coverage**: Improved from 70% to 75% overall
  - Added comprehensive tests for diagnostics, async_subprocess, mcp_client modules (100%)
  - Added tests for comment_analyzer, interactive, rendering modules (100%)
  - Added tests for pr_fix (99%), webhook_server (97%), qa (87%) stages
  - Fixed 16 failing tests across cli_init, config_settings, main_cli modules

### Fixed
- **GitLab `setup_automation_labels`**: Fixed undefined attribute reference in gitlab_rest.py:584
  - Was using `self._project_path_encoded` which doesn't exist
  - Now correctly uses `self.project_path` like other methods
- **GitLab Templates**: Updated all existing templates to use `SAPIENS_GITLAB_TOKEN` instead of `GITLAB_TOKEN`
  - The `GITLAB_` prefix is reserved for GitLab's internal CI/CD variables
- **GitProvider Protocol**: Added missing `get_pull_request` method to base class
  - Implemented in GitHubRestProvider and GitLabRestProvider
  - Added `add_comment_reply` method for threaded comment responses
- **AgentProvider Protocol**: Added missing `execute_prompt` method and `working_dir` attribute
  - Enables interactive AI prompts for comment analysis and fix execution
- **PullRequest Model**: Added `author` field for PR author identification
- **Type Annotations**: Fixed MyPy errors across multiple files
  - Added type parameters to generic `dict` and `list` types
  - Fixed return type annotations in `comment_analyzer.py`
- **Ruff Linting**: Fixed all linting errors
  - Simplified nested if statement in `settings.py`
  - Fixed line length issues in test files
  - Added timezone info to datetime objects in tests
- **Detect Secrets**: Updated baseline and added pragma comments for test API keys
- API token whitespace stripping in all providers (Gitea, GitHub, GitLab)
- Automation mode configuration test mocking
- Automation field default in AutomationSettings (backward compatibility)
- Plan ID extraction regex to handle subdirectories (`plans/archive/42-plan.md`)
- Various mypy type errors and bandit false positives
- Docker build cache connectivity issues in Gitea Actions
- uv binary conflicts with explicit Python environment setup
- CLI `--log-level` option position

### Removed
- **`templates/` directory**: Copy-paste workflow templates replaced by reusable workflows
  - Users who want customization should fork the repo and modify the dispatcher
  - Reduces maintenance burden and ensures consistent behavior
- Docker build from CI workflow (not used by any workflow)
- Conversation history files from repository (moved to local storage)

## [0.3.1] - 2026-01-05

### Added
- **`sapiens run` Command**: New universal command that dispatches to configured agent
  - Reads `agent_provider.provider_type` from config and dispatches appropriately
  - `claude-local`: Runs `claude -p "task"` via Claude CLI
  - `goose-local`: Runs `goose session start --prompt "task"` via Goose CLI
  - `ollama`/`openai-compatible`: Uses builtin ReAct agent with local model
  - `openai`/`anthropic`: Uses builtin ReAct agent with cloud API
  - Supports stdin for long prompts: `cat task.txt | sapiens run`
  - Options: `--timeout`, `--working-dir`, `--verbose`
- **Reusable Composite Actions**: Deployed during `sapiens init`
  - `.github/actions/sapiens-task/action.yaml` for GitHub Actions
  - `.gitea/actions/sapiens-task/action.yaml` for Gitea Actions
  - Direct secret handling (anthropic-api-key, openai-api-key, gitea-token)
  - Use in workflows: `uses: ./.github/actions/sapiens-task`
- **Builtin ReAct Agent**: New "builtin" option in `sapiens init` with full LLM provider selection
  - Supports Ollama, vLLM, OpenAI, Anthropic, OpenRouter, and Groq
  - Shows provider comparison table and recommendations
  - Auto-detects running local servers (Ollama/vLLM)
  - Default: qwen3:8b (qwen3:14b requires 24GB VRAM)
- **vLLM Provider**: Added vLLM to LLM provider options
  - OpenAI-compatible API with better tool support than Ollama
  - Excellent GPU utilization with continuous batching
- **Agent Selection UI**: Enhanced agent listing with provider hints
  - Shows supported providers for each agent (e.g., "Ollama, vLLM, OpenAI, etc.")
  - Builtin agent always shown as "always available" option
- **Setup Test**: Optional test at end of `sapiens init`
  - Offers to summarize README.md with configured agent
  - Shows exact command that will be run for the selected agent
- **React Config Integration**: `sapiens task` now reads settings from config
  - Model and base URL automatically loaded from `agent_provider` config
  - CLI options override config when specified
  - Simple usage: `sapiens task "task"` or `sapiens task --repl`
- **GitLab Support**: Full GitLab REST API v4 integration
  - New `GitLabRestProvider` class for issues, merge requests, branches, and files
  - `sapiens init` now detects and configures GitLab repositories
  - GitLab CI/CD workflow templates (`.gitlab-ci.yml`)
  - GitLab composite action template for reusable AI tasks
  - Supports gitlab.com and self-hosted GitLab instances
  - Uses `PRIVATE-TOKEN` authentication with `api`, `read_repository`, `write_repository` scopes

### Changed
- **Init Command**: Now deploys reusable composite action by default
  - `--deploy-actions/--no-deploy-actions` flag controls action deployment
  - Action enables simplified workflow: `uses: ./.github/actions/sapiens-task`
- **Keyring Namespace**: Migrated from `builder/` to `sapiens/` prefix
  - Credentials now stored under `sapiens/gitea/api_token`, `sapiens/claude/api_key`, etc.
- **Config Location**: Default config path changed from `repo_sapiens/config/automation_config.yaml` to `.sapiens/config.yaml`
- **State Directory**: Changed from `.automation/state` to `.sapiens/state`
- **Encrypted Credentials**: File path changed from `.builder/credentials.enc` to `.sapiens/credentials.enc`
- **CLI Commands**: All documentation and suggestions now use `sapiens credentials` (was `builder credentials`)

### Removed
- **Orphan "api" option**: Removed confusing standalone API mode from agent selection
  - Use "builtin" agent with cloud provider (OpenAI, Anthropic, etc.) instead

### Fixed
- Credential suggestion messages now show correct CLI syntax: `sapiens credentials set service/key --backend keyring`

## [0.3.0] - 2026-01-02

### Changed
- **Module Renamed**: `automation` → `repo_sapiens` for Python best practices
  - Package name now matches module name: `pip install repo-sapiens` → `import repo_sapiens`
  - All 457+ internal imports updated
- **CLI Commands Renamed**: `automation` → `sapiens` (with `repo-sapiens` alias)
  - `sapiens init` - Initialize repository
  - `sapiens task --repl` - Interactive ReAct agent REPL
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
  - Interactive REPL mode (`sapiens task --repl`) with colored prompt
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
  - Updated `AgentProviderConfig` to support goose-local provider type (Goose is CLI-only)
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
