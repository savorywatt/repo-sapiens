# CLI Redesign Implementation Plan: Phase 1-2
**Self-Contained CLI Tool Transformation (Poetry/Pipenv-style)**

**Document Version:** 1.0
**Created:** 2025-12-22
**Target Package:** repo-agent → builder-cli
**Current State:** 54 Python files, 7,321 lines, Pydantic-based config

---

## PROJECT OVERVIEW

### Summary
Transform repo-agent from a system-specific automation tool into a self-contained, portable CLI tool that can be installed via `pip install builder-cli` and initialized in any Git repository with `builder init`. This redesign enables developers to add AI-driven automation to their projects without requiring pre-existing infrastructure.

### Key Architectural Decisions

1. **Package Restructuring**: Rename `automation/` → `builder/` for clarity and brand consistency
2. **TOML-First Configuration**: Replace YAML with pyproject.toml-style config for better Python ecosystem integration
3. **Multi-Layer Credential Management**: Support keyring (secure), environment variables (CI/CD), and encrypted files (shared teams)
4. **Repository Auto-Discovery**: Detect Git origin URLs and infer provider type (Gitea/GitHub)
5. **Template-Based Initialization**: Use Jinja2 templates for workflow files, configs, and documentation

### Technology Stack Selections

- **Configuration**: `tomli` (read) + `tomli-w` (write) for TOML parsing (Python 3.11+)
- **Security**: `keyring` for credential storage, `cryptography` for encrypted file vault
- **Templates**: `jinja2` for workflow and config file generation
- **Validation**: Existing Pydantic models (leverage current investment)
- **CLI Framework**: Existing Click (already in use, mature)
- **Git Operations**: `gitpython` for repository introspection
- **Error Handling**: Custom exception hierarchy with user-friendly messages

### Success Criteria

- [ ] `pip install builder-cli` installs a working CLI tool
- [ ] `builder init` successfully initializes automation in a fresh repo
- [ ] `builder doctor` identifies and reports configuration issues
- [ ] Credentials can be stored in keyring without plaintext exposure
- [ ] Template system generates valid workflow files
- [ ] All existing functionality remains accessible (backward compatibility)

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                       │
│                    (builder/__main__.py)                     │
└────────────┬────────────────────────────────┬───────────────┘
             │                                │
    ┌────────▼────────┐              ┌────────▼─────────┐
    │  Core Commands  │              │  Legacy Commands │
    │  - init         │              │  - process-issue │
    │  - doctor       │              │  - daemon        │
    │  - config       │              │  - list-plans    │
    └────────┬────────┘              └────────┬─────────┘
             │                                │
    ┌────────▼────────────────────────────────▼─────────┐
    │           Configuration System                     │
    │  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
    │  │ TOML Parser  │  │  Pydantic    │  │ Merger  │ │
    │  │ (tomli/w)    │  │  Validators  │  │ (multi) │ │
    │  └──────────────┘  └──────────────┘  └─────────┘ │
    └─────────────────────────┬──────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────┐
    │         Credential Management Layer                │
    │  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
    │  │ Keyring  │  │   Env    │  │ Encrypted File  │  │
    │  │ (secure) │  │  (CI/CD) │  │  (Fernet vault) │  │
    │  └──────────┘  └──────────┘  └─────────────────┘  │
    └─────────────────────────┬──────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────┐
    │          Repository Discovery Module               │
    │  ┌───────────────┐         ┌────────────────────┐  │
    │  │ Git Introspect│         │ Provider Detection │  │
    │  │ (origin URL)  │────────▶│ (Gitea/GitHub/etc) │  │
    │  └───────────────┘         └────────────────────┘  │
    └─────────────────────────┬──────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────┐
    │            Template System (Jinja2)                │
    │  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
    │  │  Workflows   │  │   Configs  │  │    Docs   │  │
    │  │  (.yaml)     │  │  (.toml)   │  │   (.md)   │  │
    │  └──────────────┘  └────────────┘  └───────────┘  │
    └─────────────────────────────────────────────────────┘
                              │
    ┌─────────────────────────▼──────────────────────────┐
    │         Exception Hierarchy                        │
    │  BuilderError (base)                               │
    │   ├─ ConfigurationError                            │
    │   │   ├─ MissingConfigError                        │
    │   │   └─ InvalidConfigError                        │
    │   ├─ CredentialError                               │
    │   │   ├─ MissingCredentialError                    │
    │   │   └─ InvalidCredentialError                    │
    │   ├─ RepositoryError                               │
    │   │   ├─ NotGitRepositoryError                     │
    │   │   └─ UnsupportedProviderError                  │
    │   └─ TemplateError                                 │
    │       ├─ TemplateNotFoundError                     │
    │       └─ TemplateRenderError                       │
    └─────────────────────────────────────────────────────┘
```

**Data Flow for `builder init`:**
1. Detect Git repository and extract origin URL
2. Identify provider type (Gitea/GitHub) and repository details
3. Prompt user for missing credentials
4. Store credentials in keyring (or user-selected backend)
5. Render template files (config, workflows, docs) with repo-specific values
6. Write files to `.builder/` directory
7. Validate configuration with `builder doctor`
8. Display next steps to user

---

## DEVELOPMENT PHASES

## Phase 1: Foundation & Infrastructure

**Objective:** Establish the foundational architecture for the self-contained CLI tool, including package restructuring, configuration system, credential management, and error handling.

**Duration Estimate:** 5-7 days (4 parallel workstreams)

---

### Workstream 1A: Package Restructuring (Can run parallel to 1B, 1C, 1D)

#### Task 1A.1: Rename Package Directory
- **Task ID:** PHASE1-RESTR-001
- **Objective:** Rename `automation/` to `builder/` and update all import statements
- **Prerequisites:** Git branch created, backup of current state
- **Technical Approach:**
  * Use `git mv automation builder` to preserve history
  * Update `pyproject.toml`:
    - Change `[tool.setuptools.packages.find]` to `include = ["builder*"]`
    - Update `[project.scripts]` entry point from `automation.main:cli` to `builder.cli.main:cli`
    - Update `[tool.setuptools.dynamic]` version attribute to `builder.__version__`
  * Run find-replace across codebase: `from automation.` → `from builder.`
  * Update `builder/__init__.py` to export public API
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/automation/` → `/home/ross/Workspace/repo-agent/builder/`
  * `/home/ross/Workspace/repo-agent/pyproject.toml`
  * All 54 Python files with import statements
- **Acceptance Criteria:**
  * All imports resolve without errors
  * `pytest` runs successfully after rename
  * Package builds with `python -m build`
  * Entry point `builder` works when installed locally
- **Estimated Complexity:** Medium
- **Parallel Status:** Can run parallel to 1B, 1C, 1D after initial git mv

#### Task 1A.2: Create New CLI Entry Point Structure
- **Task ID:** PHASE1-RESTR-002
- **Objective:** Establish modern CLI structure with subcommand organization
- **Prerequisites:** Task 1A.1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/cli/` directory
  * Create `/home/ross/Workspace/repo-agent/builder/cli/__init__.py` (empty)
  * Create `/home/ross/Workspace/repo-agent/builder/cli/main.py` with root Click group:
    ```python
    import click
    from builder.__version__ import __version__

    @click.group()
    @click.version_option(version=__version__)
    @click.pass_context
    def cli(ctx):
        """Builder - AI-driven automation for Git workflows."""
        ctx.ensure_object(dict)
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/cli/commands/` directory
  * Create `/home/ross/Workspace/repo-agent/builder/cli/commands/__init__.py`
  * Create placeholder files:
    - `init.py` - for `builder init` command
    - `doctor.py` - for `builder doctor` command
    - `config.py` - for `builder config` command
    - `legacy.py` - for existing commands (process-issue, daemon, etc.)
  * Update `/home/ross/Workspace/repo-agent/builder/__main__.py` to call `cli.main:cli`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/cli/__init__.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/main.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/__init__.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/doctor.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/config.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/legacy.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/__main__.py`
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (update entry point)
- **Acceptance Criteria:**
  * `builder --version` displays correct version
  * `builder --help` shows all subcommands
  * Subcommands are properly namespaced
  * Old commands still work via legacy module
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1A.1

#### Task 1A.3: Migrate Existing Commands to Legacy Module
- **Task ID:** PHASE1-RESTR-003
- **Objective:** Move current CLI commands to `legacy.py` to preserve backward compatibility
- **Prerequisites:** Task 1A.2 completed
- **Technical Approach:**
  * Copy command functions from `/home/ross/Workspace/repo-agent/builder/main.py`:
    - `process_issue()` → `legacy.py`
    - `process_all()` → `legacy.py`
    - `process_plan()` → `legacy.py`
    - `daemon()` → `legacy.py`
    - `list_plans()` → `legacy.py`
    - `show_plan()` → `legacy.py`
  * Preserve all helper functions (`_create_orchestrator`, etc.)
  * Register commands in `legacy.py` module initialization
  * Import and attach to main CLI group in `/home/ross/Workspace/repo-agent/builder/cli/main.py`
  * Add deprecation warnings to legacy commands
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/legacy.py`
  * `/home/ross/Workspace/repo-agent/builder/cli/main.py`
- **Acceptance Criteria:**
  * All existing commands work identically
  * Deprecation warnings display on legacy command usage
  * `builder process-issue --issue 123` still functions
  * `builder daemon` still functions
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1A.2

---

### Workstream 1B: TOML Configuration System (Can run parallel to 1A after initial planning)

#### Task 1B.1: Design TOML Schema
- **Task ID:** PHASE1-CONFIG-001
- **Objective:** Define comprehensive TOML schema for builder configuration
- **Prerequisites:** None (pure design task)
- **Technical Approach:**
  * Create schema document at `/home/ross/Workspace/repo-agent/docs/config-schema.md`
  * Design three-tier configuration:
    1. **System-wide:** `~/.config/builder/config.toml` (user preferences)
    2. **Repository:** `.builder/config.toml` (project-specific)
    3. **Environment:** Environment variables (runtime overrides)
  * Schema structure:
    ```toml
    [builder]
    version = "1.0"

    [repository]
    provider = "gitea"  # or "github"
    url = "http://localhost:3000"
    owner = "myorg"
    name = "myrepo"
    default_branch = "main"

    [agent]
    provider = "claude-local"  # claude-local, claude-api, ollama, openai
    model = "claude-sonnet-4.5"
    local_mode = true

    [workflow]
    plans_directory = "plans"
    state_directory = ".builder/state"
    branching_strategy = "per-agent"
    max_concurrent_tasks = 3

    [tags]
    needs_planning = "needs-planning"
    plan_review = "plan-review"
    # ... (preserve existing tag structure)

    [credentials]
    backend = "keyring"  # keyring, env, encrypted-file
    encrypted_file_path = ".builder/credentials.enc"
    ```
  * Document priority: env vars > repo config > system config > defaults
  * Map existing Pydantic models to TOML structure
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/docs/config-schema.md`
  * `/home/ross/Workspace/repo-agent/builder/config/schema.toml` (example)
- **Acceptance Criteria:**
  * Schema covers all existing YAML configuration options
  * Clear documentation of precedence rules
  * Example configs provided for common scenarios
- **Estimated Complexity:** Simple
- **Parallel Status:** Fully parallel, no dependencies

#### Task 1B.2: Implement TOML Parser and Loader
- **Task ID:** PHASE1-CONFIG-002
- **Objective:** Create robust TOML configuration loader with multi-source merging
- **Prerequisites:** Task 1B.1 completed
- **Technical Approach:**
  * Add dependencies to `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    dependencies = [
        # ... existing ...
        "tomli>=2.0.0; python_version<'3.11'",  # TOML reading
        "tomli-w>=1.0.0",  # TOML writing
    ]
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/config/toml_loader.py`:
    ```python
    from pathlib import Path
    from typing import Dict, Any, Optional
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    import tomli_w

    class TOMLConfigLoader:
        """Multi-source TOML configuration loader with precedence."""

        SYSTEM_CONFIG = Path.home() / ".config" / "builder" / "config.toml"

        def __init__(self, repo_config_path: Optional[Path] = None):
            self.repo_config_path = repo_config_path or Path.cwd() / ".builder" / "config.toml"

        def load(self) -> Dict[str, Any]:
            """Load and merge configs: defaults < system < repo < env."""
            config = self._load_defaults()
            config = self._merge(config, self._load_system())
            config = self._merge(config, self._load_repo())
            config = self._merge(config, self._load_env())
            return config

        def _load_defaults(self) -> Dict[str, Any]:
            """Load default configuration."""
            # Return default config dict
            pass

        def _load_system(self) -> Dict[str, Any]:
            """Load system-wide config."""
            if not self.SYSTEM_CONFIG.exists():
                return {}
            with open(self.SYSTEM_CONFIG, "rb") as f:
                return tomllib.load(f)

        def _load_repo(self) -> Dict[str, Any]:
            """Load repository config."""
            if not self.repo_config_path.exists():
                return {}
            with open(self.repo_config_path, "rb") as f:
                return tomllib.load(f)

        def _load_env(self) -> Dict[str, Any]:
            """Load config from environment variables."""
            # Parse BUILDER_* env vars
            pass

        def _merge(self, base: Dict, override: Dict) -> Dict:
            """Deep merge two config dicts."""
            # Implement recursive merge
            pass

        def save_repo_config(self, config: Dict[str, Any]) -> None:
            """Save configuration to repo config file."""
            self.repo_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.repo_config_path, "wb") as f:
                tomli_w.dump(config, f)
    ```
  * Implement environment variable parsing with `BUILDER_` prefix
  * Support nested keys via double underscore: `BUILDER_REPOSITORY__OWNER=myorg`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/config/toml_loader.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (add dependencies)
- **Acceptance Criteria:**
  * Can load TOML from multiple sources
  * Precedence order enforced correctly
  * Environment variables override file configs
  * Deep merge works for nested structures
  * Save functionality writes valid TOML
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 1B.1

#### Task 1B.3: Integrate with Pydantic Validators
- **Task ID:** PHASE1-CONFIG-003
- **Objective:** Bridge TOML loader with existing Pydantic validation models
- **Prerequisites:** Task 1B.2 completed
- **Technical Approach:**
  * Modify `/home/ross/Workspace/repo-agent/builder/config/settings.py`:
    - Add `from_toml()` class method to `AutomationSettings`
    - Leverage `TOMLConfigLoader` to get merged config dict
    - Pass dict to Pydantic model for validation
    - Preserve existing `from_yaml()` for backward compatibility
  * Update field names to match TOML schema (if needed)
  * Add migration helper to convert old YAML configs to TOML
  * Create `/home/ros/Workspace/repo-agent/builder/config/migration.py`:
    ```python
    def migrate_yaml_to_toml(yaml_path: Path, toml_path: Path) -> None:
        """Convert legacy YAML config to TOML format."""
        # Load YAML, transform, save as TOML
        pass
    ```
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/config/settings.py`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/config/migration.py`
- **Acceptance Criteria:**
  * `AutomationSettings.from_toml()` works correctly
  * All Pydantic validations still apply
  * Migration tool successfully converts test YAML configs
  * Both YAML and TOML formats supported (backward compat)
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 1B.2

---

### Workstream 1C: Credential Management (Can run parallel to 1A, 1B)

#### Task 1C.1: Design Credential Storage Architecture
- **Task ID:** PHASE1-CRED-001
- **Objective:** Define multi-backend credential storage system
- **Prerequisites:** None (pure design task)
- **Technical Approach:**
  * Design three backend types:
    1. **Keyring Backend** (default): Uses OS keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service)
    2. **Environment Backend**: Reads from env vars (for CI/CD)
    3. **Encrypted File Backend**: Uses Fernet encryption for shared team credentials
  * Create abstract interface `CredentialBackend`:
    ```python
    class CredentialBackend(ABC):
        @abstractmethod
        def get(self, key: str) -> Optional[str]: pass

        @abstractmethod
        def set(self, key: str, value: str) -> None: pass

        @abstractmethod
        def delete(self, key: str) -> None: pass

        @abstractmethod
        def list_keys(self) -> List[str]: pass
    ```
  * Design credential key naming: `builder.{repo_owner}.{repo_name}.{credential_type}`
    - Example: `builder.myorg.myrepo.git_token`
  * Document security best practices in `/home/ross/Workspace/repo-agent/docs/security.md`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/docs/security.md`
  * Design document (can be inline in this plan)
- **Acceptance Criteria:**
  * Clear interface defined
  * Security implications documented
  * Key naming convention established
- **Estimated Complexity:** Simple
- **Parallel Status:** Fully parallel, no dependencies

#### Task 1C.2: Implement Keyring Backend
- **Task ID:** PHASE1-CRED-002
- **Objective:** Implement secure OS keyring integration
- **Prerequisites:** Task 1C.1 completed
- **Technical Approach:**
  * Add dependency to `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    dependencies = [
        # ... existing ...
        "keyring>=24.0.0",
    ]
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/credentials/backend.py` with `CredentialBackend` ABC
  * Create `/home/ross/Workspace/repo-agent/builder/credentials/keyring_backend.py`:
    ```python
    import keyring
    from .backend import CredentialBackend

    class KeyringBackend(CredentialBackend):
        """Secure credential storage using OS keyring."""

        SERVICE_NAME = "builder-cli"

        def get(self, key: str) -> Optional[str]:
            return keyring.get_password(self.SERVICE_NAME, key)

        def set(self, key: str, value: str) -> None:
            keyring.set_password(self.SERVICE_NAME, key, value)

        def delete(self, key: str) -> None:
            keyring.delete_password(self.SERVICE_NAME, key)

        def list_keys(self) -> List[str]:
            # Keyring doesn't support listing, return empty or use metadata
            return []
    ```
  * Handle `keyring.errors.NoKeyringError` for headless systems
  * Add graceful fallback to environment backend if keyring unavailable
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/credentials/__init__.py`
  * `/home/ross/Workspace/repo-agent/builder/credentials/backend.py`
  * `/home/ross/Workspace/repo-agent/builder/credentials/keyring_backend.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (add keyring dependency)
- **Acceptance Criteria:**
  * Can store and retrieve credentials from OS keyring
  * Works on Linux, macOS, Windows (test on available platforms)
  * Handles missing keyring gracefully
  * No plaintext credential exposure
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 1C.1

#### Task 1C.3: Implement Environment Variable Backend
- **Task ID:** PHASE1-CRED-003
- **Objective:** Support environment variable credential storage for CI/CD
- **Prerequisites:** Task 1C.1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/credentials/env_backend.py`:
    ```python
    import os
    from .backend import CredentialBackend

    class EnvironmentBackend(CredentialBackend):
        """Read-only credential backend using environment variables."""

        ENV_PREFIX = "BUILDER_CRED_"

        def get(self, key: str) -> Optional[str]:
            env_key = self._to_env_key(key)
            return os.getenv(env_key)

        def set(self, key: str, value: str) -> None:
            raise NotImplementedError("Environment backend is read-only")

        def delete(self, key: str) -> None:
            raise NotImplementedError("Environment backend is read-only")

        def list_keys(self) -> List[str]:
            prefix = self.ENV_PREFIX
            return [
                self._from_env_key(k)
                for k in os.environ.keys()
                if k.startswith(prefix)
            ]

        def _to_env_key(self, key: str) -> str:
            # builder.myorg.myrepo.git_token → BUILDER_CRED_MYORG_MYREPO_GIT_TOKEN
            return self.ENV_PREFIX + key.replace(".", "_").replace("builder_", "").upper()

        def _from_env_key(self, env_key: str) -> str:
            # Reverse of _to_env_key
            pass
    ```
  * Document environment variable naming in security docs
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/credentials/env_backend.py`
- **Acceptance Criteria:**
  * Can read credentials from environment variables
  * Correct env var naming convention
  * Read-only enforcement (raises on set/delete)
  * Lists all available credentials
- **Estimated Complexity:** Simple
- **Parallel Status:** Can run parallel to 1C.2

#### Task 1C.4: Implement Encrypted File Backend
- **Task ID:** PHASE1-CRED-004
- **Objective:** Support encrypted file storage for shared team credentials
- **Prerequisites:** Task 1C.1 completed
- **Technical Approach:**
  * Add dependency to `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    dependencies = [
        # ... existing ...
        "cryptography>=41.0.0",
    ]
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/credentials/encrypted_backend.py`:
    ```python
    from cryptography.fernet import Fernet
    import json
    from pathlib import Path
    from .backend import CredentialBackend

    class EncryptedFileBackend(CredentialBackend):
        """Encrypted file-based credential storage using Fernet."""

        def __init__(self, file_path: Path, key: bytes):
            self.file_path = file_path
            self.fernet = Fernet(key)
            self._credentials = self._load()

        def get(self, key: str) -> Optional[str]:
            return self._credentials.get(key)

        def set(self, key: str, value: str) -> None:
            self._credentials[key] = value
            self._save()

        def delete(self, key: str) -> None:
            self._credentials.pop(key, None)
            self._save()

        def list_keys(self) -> List[str]:
            return list(self._credentials.keys())

        def _load(self) -> Dict[str, str]:
            if not self.file_path.exists():
                return {}
            encrypted_data = self.file_path.read_bytes()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)

        def _save(self) -> None:
            json_data = json.dumps(self._credentials)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_path.write_bytes(encrypted_data)

        @staticmethod
        def generate_key() -> bytes:
            """Generate a new encryption key."""
            return Fernet.generate_key()
    ```
  * Store encryption key in system keyring or prompt user
  * Document key management workflow in security docs
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/credentials/encrypted_backend.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (add cryptography)
  * `/home/ross/Workspace/repo-agent/docs/security.md` (key management)
- **Acceptance Criteria:**
  * Can encrypt and decrypt credential files
  * Fernet encryption properly applied
  * Key generation and storage documented
  * File permissions set to 600 (owner-only read/write)
- **Estimated Complexity:** Medium
- **Parallel Status:** Can run parallel to 1C.2, 1C.3

#### Task 1C.5: Implement Credential Manager Facade
- **Task ID:** PHASE1-CRED-005
- **Objective:** Create unified interface for credential management
- **Prerequisites:** Tasks 1C.2, 1C.3, 1C.4 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/credentials/manager.py`:
    ```python
    from typing import Optional, List
    from .backend import CredentialBackend
    from .keyring_backend import KeyringBackend
    from .env_backend import EnvironmentBackend
    from .encrypted_backend import EncryptedFileBackend
    from ..config.settings import AutomationSettings

    class CredentialManager:
        """Unified credential management with fallback chain."""

        def __init__(self, config: AutomationSettings):
            self.backends = self._initialize_backends(config)

        def _initialize_backends(self, config) -> List[CredentialBackend]:
            """Initialize backends in priority order."""
            backend_type = config.credentials.backend  # from TOML

            if backend_type == "keyring":
                return [KeyringBackend(), EnvironmentBackend()]
            elif backend_type == "env":
                return [EnvironmentBackend()]
            elif backend_type == "encrypted-file":
                key = self._get_encryption_key()
                path = config.credentials.encrypted_file_path
                return [EncryptedFileBackend(path, key), EnvironmentBackend()]
            else:
                raise ValueError(f"Unknown backend: {backend_type}")

        def get(self, key: str) -> Optional[str]:
            """Get credential from first backend that has it."""
            for backend in self.backends:
                value = backend.get(key)
                if value is not None:
                    return value
            return None

        def set(self, key: str, value: str) -> None:
            """Set credential in primary backend."""
            self.backends[0].set(key, value)

        def delete(self, key: str) -> None:
            """Delete credential from all backends."""
            for backend in self.backends:
                try:
                    backend.delete(key)
                except NotImplementedError:
                    pass  # Skip read-only backends

        def list_keys(self) -> List[str]:
            """List all credential keys from all backends."""
            keys = set()
            for backend in self.backends:
                keys.update(backend.list_keys())
            return sorted(keys)

        def _get_encryption_key(self) -> bytes:
            """Get encryption key from keyring or prompt."""
            # Try keyring first, then prompt user
            pass
    ```
  * Add credential prompting with `click.prompt()` for missing credentials
  * Implement credential validation (test API connections)
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/credentials/manager.py`
- **Acceptance Criteria:**
  * Can get credentials with fallback chain
  * Can set credentials in primary backend
  * Lists all available credentials
  * Handles read-only backends gracefully
  * Prompts for missing credentials
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 1C.2, 1C.3, 1C.4

---

### Workstream 1D: Exception Hierarchy (Can run fully parallel)

#### Task 1D.1: Design Exception Hierarchy
- **Task ID:** PHASE1-ERROR-001
- **Objective:** Create comprehensive, user-friendly exception hierarchy
- **Prerequisites:** None (pure design task)
- **Technical Approach:**
  * Design exception tree (see architecture diagram above)
  * Each exception should include:
    - Clear error message
    - Suggested remediation steps
    - Related documentation URL
    - Exit code for CLI
  * Create design document at `/home/ross/Workspace/repo-agent/docs/exceptions.md`
  * Define standard exception attributes:
    ```python
    class BuilderError(Exception):
        """Base exception for all Builder errors."""
        exit_code: int = 1
        docs_url: str = "https://docs.builder-cli.dev/errors"
        remediation: str = ""
    ```
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/docs/exceptions.md`
- **Acceptance Criteria:**
  * Complete exception hierarchy documented
  * Each exception has clear purpose
  * Remediation guidance defined
  * Exit codes assigned (1-10 range)
- **Estimated Complexity:** Simple
- **Parallel Status:** Fully parallel, no dependencies

#### Task 1D.2: Implement Base Exceptions
- **Task ID:** PHASE1-ERROR-002
- **Objective:** Create base exception classes with CLI integration
- **Prerequisites:** Task 1D.1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/exceptions/__init__.py`:
    ```python
    class BuilderError(Exception):
        """Base exception for all Builder errors."""
        exit_code = 1
        docs_url = "https://docs.builder-cli.dev/errors"

        def __init__(self, message: str, remediation: str = ""):
            super().__init__(message)
            self.remediation = remediation

        def format_error(self) -> str:
            """Format error for CLI output."""
            parts = [f"Error: {self}"]
            if self.remediation:
                parts.append(f"\nSuggestion: {self.remediation}")
            parts.append(f"\nDocs: {self.docs_url}")
            return "\n".join(parts)

    class ConfigurationError(BuilderError):
        """Configuration-related errors."""
        exit_code = 2
        docs_url = "https://docs.builder-cli.dev/errors/configuration"

    class MissingConfigError(ConfigurationError):
        """Required configuration is missing."""
        pass

    class InvalidConfigError(ConfigurationError):
        """Configuration is invalid."""
        pass

    class CredentialError(BuilderError):
        """Credential-related errors."""
        exit_code = 3
        docs_url = "https://docs.builder-cli.dev/errors/credentials"

    class MissingCredentialError(CredentialError):
        """Required credential is missing."""
        pass

    class InvalidCredentialError(CredentialError):
        """Credential is invalid or expired."""
        pass

    class RepositoryError(BuilderError):
        """Repository-related errors."""
        exit_code = 4
        docs_url = "https://docs.builder-cli.dev/errors/repository"

    class NotGitRepositoryError(RepositoryError):
        """Not a Git repository."""

        def __init__(self, path: str):
            super().__init__(
                f"Not a Git repository: {path}",
                "Run 'git init' or navigate to a Git repository"
            )

    class UnsupportedProviderError(RepositoryError):
        """Git provider is not supported."""

        def __init__(self, provider: str):
            super().__init__(
                f"Unsupported Git provider: {provider}",
                "Supported providers: Gitea, GitHub"
            )

    class TemplateError(BuilderError):
        """Template-related errors."""
        exit_code = 5
        docs_url = "https://docs.builder-cli.dev/errors/templates"

    class TemplateNotFoundError(TemplateError):
        """Template file not found."""
        pass

    class TemplateRenderError(TemplateError):
        """Template rendering failed."""
        pass
    ```
  * Create global exception handler for CLI
  * Add logging integration for exceptions
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/exceptions/__init__.py`
- **Acceptance Criteria:**
  * All exception classes defined
  * Each has proper exit code and docs URL
  * `format_error()` produces user-friendly output
  * Exceptions inherit correctly
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1D.1

#### Task 1D.3: Integrate Exception Handler in CLI
- **Task ID:** PHASE1-ERROR-003
- **Objective:** Add global exception handling to CLI entry point
- **Prerequisites:** Task 1D.2 completed
- **Technical Approach:**
  * Modify `/home/ross/Workspace/repo-agent/builder/cli/main.py`:
    ```python
    import sys
    import click
    import structlog
    from builder.exceptions import BuilderError

    log = structlog.get_logger(__name__)

    @click.group()
    @click.version_option(version=__version__)
    @click.pass_context
    def cli(ctx):
        """Builder - AI-driven automation for Git workflows."""
        ctx.ensure_object(dict)

    def main():
        """Main entry point with exception handling."""
        try:
            cli()
        except BuilderError as e:
            click.echo(click.style(e.format_error(), fg="red"), err=True)
            log.error("builder_error", error=str(e), exit_code=e.exit_code)
            sys.exit(e.exit_code)
        except KeyboardInterrupt:
            click.echo("\nInterrupted by user", err=True)
            sys.exit(130)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
            log.exception("unexpected_error")
            sys.exit(1)

    if __name__ == "__main__":
        main()
    ```
  * Update entry point in `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    [project.scripts]
    builder = "builder.cli.main:main"
    ```
  * Test exception formatting with sample errors
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/main.py`
  * `/home/ross/Workspace/repo-agent/pyproject.toml`
- **Acceptance Criteria:**
  * All `BuilderError` exceptions formatted nicely
  * Exit codes propagated correctly
  * Unexpected exceptions logged properly
  * KeyboardInterrupt handled gracefully
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1D.2

---

### Workstream 1E: Template System Setup (Can run parallel to all others)

#### Task 1E.1: Design Template Structure
- **Task ID:** PHASE1-TMPL-001
- **Objective:** Define template directory structure and template types
- **Prerequisites:** None (pure design task)
- **Technical Approach:**
  * Create template directory structure:
    ```
    builder/templates/
    ├── init/
    │   ├── config.toml.j2          # Repository config template
    │   ├── gitea-workflow.yaml.j2  # Gitea Actions workflow
    │   ├── github-workflow.yaml.j2 # GitHub Actions workflow
    │   └── README.md.j2            # Builder documentation
    ├── doctor/
    │   └── report.md.j2            # Doctor command output
    └── common/
        └── macros.j2               # Reusable Jinja2 macros
    ```
  * Define template variables:
    - `{{ repository.owner }}` - Repository owner/org
    - `{{ repository.name }}` - Repository name
    - `{{ repository.url }}` - Git remote URL
    - `{{ repository.provider }}` - Provider type (gitea/github)
    - `{{ agent.provider }}` - Agent provider type
    - `{{ agent.model }}` - Agent model name
    - `{{ timestamp }}` - Generation timestamp
  * Document template development guide at `/home/ross/Workspace/repo-agent/docs/templates.md`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/docs/templates.md`
- **Acceptance Criteria:**
  * Template structure documented
  * Template variables defined
  * Template development guide created
- **Estimated Complexity:** Simple
- **Parallel Status:** Fully parallel, no dependencies

#### Task 1E.2: Implement Jinja2 Template Renderer
- **Task ID:** PHASE1-TMPL-002
- **Objective:** Create template rendering engine with proper error handling
- **Prerequisites:** Task 1E.1 completed
- **Technical Approach:**
  * Add dependency to `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    dependencies = [
        # ... existing ...
        "jinja2>=3.1.0",
    ]
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/templates/__init__.py`:
    ```python
    from pathlib import Path
    from typing import Dict, Any
    from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
    from builder.exceptions import TemplateNotFoundError, TemplateRenderError

    class TemplateRenderer:
        """Jinja2-based template renderer."""

        def __init__(self, template_dir: Optional[Path] = None):
            if template_dir is None:
                template_dir = Path(__file__).parent

            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=False,  # We're generating config files, not HTML
                trim_blocks=True,
                lstrip_blocks=True,
            )

        def render(self, template_name: str, context: Dict[str, Any]) -> str:
            """Render a template with given context."""
            try:
                template = self.env.get_template(template_name)
            except TemplateNotFound as e:
                raise TemplateNotFoundError(
                    f"Template not found: {template_name}",
                    f"Available templates: {self.list_templates()}"
                ) from e

            try:
                return template.render(**context)
            except Exception as e:
                raise TemplateRenderError(
                    f"Failed to render template {template_name}: {e}"
                ) from e

        def render_to_file(
            self,
            template_name: str,
            context: Dict[str, Any],
            output_path: Path
        ) -> None:
            """Render template and write to file."""
            content = self.render(template_name, context)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)

        def list_templates(self) -> List[str]:
            """List all available templates."""
            return self.env.list_templates()
    ```
  * Add custom Jinja2 filters for common operations (e.g., `{{ value | to_yaml }}`)
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/templates/__init__.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (add jinja2)
- **Acceptance Criteria:**
  * Can render Jinja2 templates
  * Proper error handling for missing/invalid templates
  * Can write rendered content to files
  * Lists available templates
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1E.1

#### Task 1E.3: Create Initial Template Files
- **Task ID:** PHASE1-TMPL-003
- **Objective:** Create concrete templates for `builder init` command
- **Prerequisites:** Task 1E.2 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/templates/init/config.toml.j2`:
    ```toml
    # Builder Configuration
    # Generated: {{ timestamp }}

    [builder]
    version = "1.0"

    [repository]
    provider = "{{ repository.provider }}"
    url = "{{ repository.url }}"
    owner = "{{ repository.owner }}"
    name = "{{ repository.name }}"
    default_branch = "{{ repository.default_branch }}"

    [agent]
    provider = "{{ agent.provider }}"
    model = "{{ agent.model }}"
    {% if agent.provider == "claude-local" %}
    local_mode = true
    {% endif %}

    [workflow]
    plans_directory = "plans"
    state_directory = ".builder/state"
    branching_strategy = "per-agent"
    max_concurrent_tasks = 3

    [tags]
    needs_planning = "needs-planning"
    plan_review = "plan-review"
    ready_to_implement = "ready-to-implement"
    in_progress = "in-progress"
    code_review = "code-review"
    merge_ready = "merge-ready"
    completed = "completed"
    needs_attention = "needs-attention"

    [credentials]
    backend = "keyring"
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/templates/init/README.md.j2`:
    ```markdown
    # Builder Automation Setup

    This repository has been initialized with Builder automation.

    ## Configuration

    Configuration is stored in `.builder/config.toml`.

    ## Credentials

    Credentials are securely stored in your system keyring.
    To manage credentials: `builder config credentials`

    ## Getting Started

    1. Run health check: `builder doctor`
    2. Create a plan: Add markdown files to `plans/`
    3. Process issues: `builder process-issue --issue <number>`

    ## Learn More

    - [Builder Documentation](https://docs.builder-cli.dev)
    - [Configuration Guide](https://docs.builder-cli.dev/config)
    ```
  * Create workflow templates for Gitea and GitHub (stub for now, full implementation in Phase 2)
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/templates/init/config.toml.j2`
  * `/home/ross/Workspace/repo-agent/builder/templates/init/README.md.j2`
  * `/home/ross/Workspace/repo-agent/builder/templates/init/gitea-workflow.yaml.j2` (stub)
  * `/home/ross/Workspace/repo-agent/builder/templates/init/github-workflow.yaml.j2` (stub)
- **Acceptance Criteria:**
  * Templates render without errors
  * Generated configs are valid TOML
  * Generated docs are well-formatted markdown
  * Templates use proper Jinja2 syntax
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 1E.2

---

### Phase 1 Testing & Integration

#### Task 1F.1: Write Unit Tests for Each Component
- **Task ID:** PHASE1-TEST-001
- **Objective:** Comprehensive unit test coverage for Phase 1 components
- **Prerequisites:** All Phase 1 tasks completed
- **Technical Approach:**
  * Create test files:
    - `/home/ross/Workspace/repo-agent/tests/test_toml_loader.py`
    - `/home/ross/Workspace/repo-agent/tests/test_credentials.py`
    - `/home/ross/Workspace/repo-agent/tests/test_exceptions.py`
    - `/home/ross/Workspace/repo-agent/tests/test_templates.py`
  * Test coverage requirements:
    - TOML loader: multi-source merging, env var parsing, precedence
    - Credentials: all three backends, manager fallback chain
    - Exceptions: formatting, exit codes, remediation
    - Templates: rendering, error handling, file operations
  * Use pytest fixtures for common setup (temp directories, mock configs)
  * Mock external dependencies (keyring, filesystem)
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/tests/test_toml_loader.py`
  * `/home/ross/Workspace/repo-agent/tests/test_credentials.py`
  * `/home/ross/Workspace/repo-agent/tests/test_exceptions.py`
  * `/home/ross/Workspace/repo-agent/tests/test_templates.py`
- **Acceptance Criteria:**
  * All tests pass
  * Code coverage > 80% for new code
  * Edge cases tested (missing files, invalid input, etc.)
  * Mock isolation prevents test flakiness
- **Estimated Complexity:** Medium
- **Parallel Status:** Can start once individual components complete

#### Task 1F.2: Integration Testing
- **Task ID:** PHASE1-TEST-002
- **Objective:** End-to-end integration tests for Phase 1 components
- **Prerequisites:** Task 1F.1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/tests/integration/test_phase1.py`
  * Test scenarios:
    1. Load config from TOML with env overrides
    2. Store and retrieve credentials across backends
    3. Render templates with real context
    4. Exception propagation through CLI
  * Use temporary directories for file operations
  * Test CLI commands with `click.testing.CliRunner`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/tests/integration/test_phase1.py`
- **Acceptance Criteria:**
  * All integration tests pass
  * Components work together correctly
  * No regression in existing functionality
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 1F.1

---

## Phase 2: Core Commands

**Objective:** Implement the essential CLI commands (`builder init`, `builder doctor`) with repository discovery and workflow template rendering.

**Duration Estimate:** 4-6 days (3 parallel workstreams)

---

### Workstream 2A: Repository Discovery (Can run parallel to 2B initially)

#### Task 2A.1: Implement Git Repository Introspection
- **Task ID:** PHASE2-REPO-001
- **Objective:** Detect Git repository and extract metadata
- **Prerequisites:** Phase 1 completed
- **Technical Approach:**
  * Add dependency to `/home/ross/Workspace/repo-agent/pyproject.toml`:
    ```toml
    dependencies = [
        # ... existing ...
        "gitpython>=3.1.40",
    ]
    ```
  * Create `/home/ross/Workspace/repo-agent/builder/repository/discovery.py`:
    ```python
    from pathlib import Path
    from typing import Optional, Dict, Any
    from git import Repo, InvalidGitRepositoryError
    from urllib.parse import urlparse
    from builder.exceptions import NotGitRepositoryError

    class RepositoryDiscovery:
        """Discover and analyze Git repository information."""

        def __init__(self, path: Optional[Path] = None):
            self.path = path or Path.cwd()

        def discover(self) -> Dict[str, Any]:
            """Discover repository information."""
            try:
                repo = Repo(self.path, search_parent_directories=True)
            except InvalidGitRepositoryError:
                raise NotGitRepositoryError(str(self.path))

            remote_url = self._get_remote_url(repo)
            provider_info = self._detect_provider(remote_url)

            return {
                "path": Path(repo.working_dir),
                "remote_url": remote_url,
                "provider": provider_info["provider"],
                "owner": provider_info["owner"],
                "name": provider_info["name"],
                "default_branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "current_branch": repo.active_branch.name,
            }

        def _get_remote_url(self, repo: Repo) -> str:
            """Get remote origin URL."""
            try:
                return repo.remotes.origin.url
            except AttributeError:
                # No origin remote
                return ""

        def _detect_provider(self, remote_url: str) -> Dict[str, str]:
            """Detect provider type from remote URL."""
            if not remote_url:
                return {"provider": "unknown", "owner": "", "name": ""}

            # Parse URL patterns:
            # https://github.com/owner/repo.git
            # git@github.com:owner/repo.git
            # http://localhost:3000/owner/repo.git

            if "github.com" in remote_url:
                return self._parse_github_url(remote_url)
            elif any(marker in remote_url for marker in ["gitea", "localhost", "3000"]):
                return self._parse_gitea_url(remote_url)
            else:
                return {"provider": "unknown", "owner": "", "name": ""}

        def _parse_github_url(self, url: str) -> Dict[str, str]:
            """Parse GitHub URL to extract owner/repo."""
            # Handle both HTTPS and SSH formats
            if url.startswith("git@"):
                # git@github.com:owner/repo.git
                parts = url.split(":")[-1].replace(".git", "").split("/")
            else:
                # https://github.com/owner/repo.git
                parsed = urlparse(url)
                parts = parsed.path.strip("/").replace(".git", "").split("/")

            return {
                "provider": "github",
                "owner": parts[0] if len(parts) > 0 else "",
                "name": parts[1] if len(parts) > 1 else "",
            }

        def _parse_gitea_url(self, url: str) -> Dict[str, str]:
            """Parse Gitea URL to extract owner/repo."""
            # Similar logic to GitHub
            if url.startswith("git@"):
                parts = url.split(":")[-1].replace(".git", "").split("/")
            else:
                parsed = urlparse(url)
                parts = parsed.path.strip("/").replace(".git", "").split("/")

            return {
                "provider": "gitea",
                "owner": parts[0] if len(parts) > 0 else "",
                "name": parts[1] if len(parts) > 1 else "",
            }
    ```
  * Handle edge cases: no remote, multiple remotes, non-standard URLs
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/repository/__init__.py`
  * `/home/ross/Workspace/repo-agent/builder/repository/discovery.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/pyproject.toml` (add gitpython)
- **Acceptance Criteria:**
  * Correctly identifies Git repositories
  * Extracts owner and repo name from remote URLs
  * Detects GitHub vs Gitea providers
  * Handles SSH and HTTPS URL formats
  * Raises appropriate exception for non-Git directories
- **Estimated Complexity:** Medium
- **Parallel Status:** Can run parallel to 2B

#### Task 2A.2: Add Provider Validation
- **Task ID:** PHASE2-REPO-002
- **Objective:** Validate detected provider and test connectivity
- **Prerequisites:** Task 2A.1 completed
- **Technical Approach:**
  * Extend `/home/ross/Workspace/repo-agent/builder/repository/discovery.py`:
    ```python
    import httpx

    class RepositoryDiscovery:
        # ... existing methods ...

        async def validate_provider(
            self,
            provider_info: Dict[str, Any],
            base_url: str,
            token: Optional[str] = None
        ) -> bool:
            """Validate provider connectivity and credentials."""
            if provider_info["provider"] == "gitea":
                return await self._validate_gitea(base_url, token, provider_info)
            elif provider_info["provider"] == "github":
                return await self._validate_github(token, provider_info)
            else:
                return False

        async def _validate_gitea(
            self,
            base_url: str,
            token: Optional[str],
            provider_info: Dict[str, Any]
        ) -> bool:
            """Test Gitea API connectivity."""
            url = f"{base_url}/api/v1/repos/{provider_info['owner']}/{provider_info['name']}"
            headers = {"Authorization": f"token {token}"} if token else {}

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=headers, timeout=5.0)
                    return response.status_code == 200
                except httpx.HTTPError:
                    return False

        async def _validate_github(
            self,
            token: Optional[str],
            provider_info: Dict[str, Any]
        ) -> bool:
            """Test GitHub API connectivity."""
            url = f"https://api.github.com/repos/{provider_info['owner']}/{provider_info['name']}"
            headers = {"Authorization": f"token {token}"} if token else {}

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=headers, timeout=5.0)
                    return response.status_code == 200
                except httpx.HTTPError:
                    return False
    ```
  * Add timeout and retry logic
  * Return detailed error information (auth failure vs network error)
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/repository/discovery.py`
- **Acceptance Criteria:**
  * Can validate Gitea API access
  * Can validate GitHub API access
  * Properly handles auth failures
  * Handles network timeouts gracefully
  * Returns actionable error messages
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 2A.1

---

### Workstream 2B: `builder init` Command (Can run parallel to 2A initially)

#### Task 2B.1: Implement Interactive Initialization
- **Task ID:** PHASE2-INIT-001
- **Objective:** Create interactive `builder init` command
- **Prerequisites:** Phase 1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`:
    ```python
    import click
    from pathlib import Path
    from datetime import datetime
    from builder.repository.discovery import RepositoryDiscovery
    from builder.credentials.manager import CredentialManager
    from builder.templates import TemplateRenderer
    from builder.config.toml_loader import TOMLConfigLoader
    from builder.exceptions import NotGitRepositoryError

    @click.command()
    @click.option(
        "--provider",
        type=click.Choice(["gitea", "github"], case_sensitive=False),
        help="Git provider type (auto-detected if not specified)"
    )
    @click.option(
        "--base-url",
        help="Base URL for Git provider (for Gitea)"
    )
    @click.option(
        "--agent",
        type=click.Choice(["claude-local", "claude-api", "ollama", "openai"]),
        default="claude-local",
        help="AI agent provider"
    )
    @click.option(
        "--model",
        help="AI model to use"
    )
    @click.pass_context
    def init(ctx, provider, base_url, agent, model):
        """Initialize Builder automation in current repository."""
        click.echo("🚀 Initializing Builder automation...\n")

        # Step 1: Discover repository
        click.echo("1. Discovering repository...")
        discovery = RepositoryDiscovery()
        try:
            repo_info = discovery.discover()
        except NotGitRepositoryError as e:
            raise click.ClickException(str(e))

        # Override provider if specified
        if provider:
            repo_info["provider"] = provider

        # Display discovered info
        click.echo(f"   ✓ Repository: {repo_info['owner']}/{repo_info['name']}")
        click.echo(f"   ✓ Provider: {repo_info['provider']}")
        click.echo(f"   ✓ Branch: {repo_info['default_branch']}\n")

        # Step 2: Confirm or prompt for base URL
        if repo_info["provider"] == "gitea":
            if not base_url:
                base_url = click.prompt(
                    "2. Enter Gitea base URL",
                    default="http://localhost:3000"
                )
            else:
                click.echo(f"2. Using Gitea URL: {base_url}\n")
        elif repo_info["provider"] == "github":
            base_url = "https://github.com"
            click.echo("2. Using GitHub.com\n")

        # Step 3: Collect credentials
        click.echo("3. Configuring credentials...")
        token = click.prompt(
            f"   Enter {repo_info['provider']} API token",
            hide_input=True
        )

        # Step 4: Validate connectivity
        click.echo("\n4. Validating provider access...")
        # TODO: Add async validation call
        click.echo("   ✓ Provider access validated\n")

        # Step 5: Configure agent
        click.echo("5. Configuring AI agent...")
        if not model:
            defaults = {
                "claude-local": "claude-sonnet-4.5",
                "claude-api": "claude-sonnet-4.5",
                "ollama": "llama3.1:8b",
                "openai": "gpt-4"
            }
            model = click.prompt(
                f"   Enter model name",
                default=defaults.get(agent, "")
            )

        click.echo(f"   ✓ Using {agent} with {model}\n")

        # Step 6: Store credentials
        click.echo("6. Storing credentials securely...")
        # Initialize config to get credential backend preference
        loader = TOMLConfigLoader()
        config_dict = loader.load()

        # TODO: Store credentials with CredentialManager
        click.echo("   ✓ Credentials stored in system keyring\n")

        # Step 7: Generate configuration
        click.echo("7. Generating configuration...")
        renderer = TemplateRenderer()

        context = {
            "timestamp": datetime.now().isoformat(),
            "repository": {
                "provider": repo_info["provider"],
                "url": base_url,
                "owner": repo_info["owner"],
                "name": repo_info["name"],
                "default_branch": repo_info["default_branch"],
            },
            "agent": {
                "provider": agent,
                "model": model,
            }
        }

        # Create .builder directory
        builder_dir = Path.cwd() / ".builder"
        builder_dir.mkdir(exist_ok=True)

        # Render config.toml
        renderer.render_to_file(
            "init/config.toml.j2",
            context,
            builder_dir / "config.toml"
        )
        click.echo(f"   ✓ Created .builder/config.toml")

        # Render README
        renderer.render_to_file(
            "init/README.md.j2",
            context,
            builder_dir / "README.md"
        )
        click.echo(f"   ✓ Created .builder/README.md")

        # Create plans directory
        plans_dir = Path.cwd() / "plans"
        plans_dir.mkdir(exist_ok=True)
        click.echo(f"   ✓ Created plans/ directory\n")

        # Step 8: Summary
        click.echo("✅ Builder initialization complete!\n")
        click.echo("Next steps:")
        click.echo("  1. Run 'builder doctor' to verify setup")
        click.echo("  2. Add plan files to plans/ directory")
        click.echo("  3. Run 'builder process-issue --issue <number>' to start automation\n")
    ```
  * Register command in `/home/ross/Workspace/repo-agent/builder/cli/main.py`
  * Add `.builder/` to `.gitignore` (or make it optional)
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/main.py` (register command)
- **Acceptance Criteria:**
  * Interactive prompts work correctly
  * Repository auto-detected successfully
  * Credentials collected securely (hidden input)
  * Config files generated correctly
  * Directory structure created
  * User sees clear next steps
- **Estimated Complexity:** Medium
- **Parallel Status:** Can start after Phase 1, parallel to 2A.1

#### Task 2B.2: Add Non-Interactive Mode
- **Task ID:** PHASE2-INIT-002
- **Objective:** Support fully automated initialization for CI/CD
- **Prerequisites:** Task 2B.1 completed
- **Technical Approach:**
  * Extend `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`:
    - Add `--non-interactive` flag
    - Read all values from environment variables or flags
    - Skip prompts, fail fast if required values missing
    - Example: `builder init --non-interactive --provider gitea --base-url $GITEA_URL`
  * Add validation for required parameters
  * Emit structured output for CI/CD parsing (JSON with `--json` flag)
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`
- **Acceptance Criteria:**
  * Non-interactive mode works without prompts
  * All values can be provided via flags or env vars
  * Fails with clear error if required values missing
  * JSON output mode available for CI/CD
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 2B.1

---

### Workstream 2C: `builder doctor` Command (Can run parallel to 2A, 2B)

#### Task 2C.1: Implement Health Check System
- **Task ID:** PHASE2-DOCTOR-001
- **Objective:** Create diagnostic system for configuration validation
- **Prerequisites:** Phase 1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/doctor/__init__.py`:
    ```python
    from typing import List, Dict, Any
    from enum import Enum
    from dataclasses import dataclass

    class CheckStatus(Enum):
        PASS = "pass"
        WARN = "warn"
        FAIL = "fail"
        SKIP = "skip"

    @dataclass
    class CheckResult:
        """Result of a health check."""
        name: str
        status: CheckStatus
        message: str
        remediation: str = ""
        details: Dict[str, Any] = None

    class HealthCheck:
        """Base class for health checks."""

        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description

        async def run(self, context: Dict[str, Any]) -> CheckResult:
            """Run the health check."""
            raise NotImplementedError

    class DoctorRunner:
        """Orchestrates health checks."""

        def __init__(self):
            self.checks: List[HealthCheck] = []

        def register_check(self, check: HealthCheck) -> None:
            """Register a health check."""
            self.checks.append(check)

        async def run_all(self, context: Dict[str, Any]) -> List[CheckResult]:
            """Run all registered health checks."""
            results = []
            for check in self.checks:
                result = await check.run(context)
                results.append(result)
            return results

        def format_results(self, results: List[CheckResult]) -> str:
            """Format results for CLI output."""
            lines = ["Builder Health Check Results", "=" * 40, ""]

            for result in results:
                emoji = {
                    CheckStatus.PASS: "✅",
                    CheckStatus.WARN: "⚠️",
                    CheckStatus.FAIL: "❌",
                    CheckStatus.SKIP: "⏭️",
                }[result.status]

                lines.append(f"{emoji} {result.name}: {result.message}")
                if result.remediation:
                    lines.append(f"   → {result.remediation}")
                lines.append("")

            # Summary
            pass_count = sum(1 for r in results if r.status == CheckStatus.PASS)
            warn_count = sum(1 for r in results if r.status == CheckStatus.WARN)
            fail_count = sum(1 for r in results if r.status == CheckStatus.FAIL)

            lines.append(f"Summary: {pass_count} passed, {warn_count} warnings, {fail_count} failures")

            return "\n".join(lines)
    ```
  * Create specific check implementations in `/home/ross/Workspace/repo-agent/builder/doctor/checks/`
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/doctor/__init__.py`
  * `/home/ross/Workspace/repo-agent/builder/doctor/checks/__init__.py`
- **Acceptance Criteria:**
  * Health check framework implemented
  * Can register and run checks
  * Results formatted nicely
  * Summary statistics calculated
- **Estimated Complexity:** Medium
- **Parallel Status:** Fully parallel after Phase 1

#### Task 2C.2: Implement Core Health Checks
- **Task ID:** PHASE2-DOCTOR-002
- **Objective:** Create essential health checks for common issues
- **Prerequisites:** Task 2C.1 completed
- **Technical Approach:**
  * Create health check implementations:

  `/home/ross/Workspace/repo-agent/builder/doctor/checks/config_check.py`:
  ```python
  from builder.doctor import HealthCheck, CheckResult, CheckStatus
  from builder.config.toml_loader import TOMLConfigLoader
  from pathlib import Path

  class ConfigExistsCheck(HealthCheck):
      """Check if config file exists."""

      def __init__(self):
          super().__init__(
              "Configuration File",
              "Verify .builder/config.toml exists"
          )

      async def run(self, context):
          config_path = Path.cwd() / ".builder" / "config.toml"

          if config_path.exists():
              return CheckResult(
                  self.name,
                  CheckStatus.PASS,
                  "Configuration file found"
              )
          else:
              return CheckResult(
                  self.name,
                  CheckStatus.FAIL,
                  "Configuration file not found",
                  "Run 'builder init' to initialize configuration"
              )

  class ConfigValidCheck(HealthCheck):
      """Check if config is valid."""

      def __init__(self):
          super().__init__(
              "Configuration Validity",
              "Validate configuration schema"
          )

      async def run(self, context):
          try:
              loader = TOMLConfigLoader()
              config = loader.load()
              # Attempt to create AutomationSettings (triggers validation)
              from builder.config.settings import AutomationSettings
              settings = AutomationSettings(**config)

              return CheckResult(
                  self.name,
                  CheckStatus.PASS,
                  "Configuration is valid"
              )
          except Exception as e:
              return CheckResult(
                  self.name,
                  CheckStatus.FAIL,
                  f"Configuration validation failed: {e}",
                  "Check your .builder/config.toml for errors"
              )
  ```

  `/home/ross/Workspace/repo-agent/builder/doctor/checks/credential_check.py`:
  ```python
  class CredentialCheck(HealthCheck):
      """Check if required credentials are present."""

      async def run(self, context):
          from builder.credentials.manager import CredentialManager

          manager = CredentialManager(context["settings"])
          required_creds = ["git_token"]

          missing = []
          for cred in required_creds:
              if not manager.get(f"builder.{cred}"):
                  missing.append(cred)

          if not missing:
              return CheckResult(
                  "Credentials",
                  CheckStatus.PASS,
                  "All required credentials present"
              )
          else:
              return CheckResult(
                  "Credentials",
                  CheckStatus.FAIL,
                  f"Missing credentials: {', '.join(missing)}",
                  "Run 'builder config credentials set <key> <value>'"
              )
  ```

  `/home/ross/Workspace/repo-agent/builder/doctor/checks/repository_check.py`:
  ```python
  class RepositoryCheck(HealthCheck):
      """Check repository status."""

      async def run(self, context):
          from builder.repository.discovery import RepositoryDiscovery

          discovery = RepositoryDiscovery()
          try:
              repo_info = discovery.discover()

              messages = []
              if repo_info["is_dirty"]:
                  messages.append("Working directory has uncommitted changes")

              return CheckResult(
                  "Repository",
                  CheckStatus.PASS if not repo_info["is_dirty"] else CheckStatus.WARN,
                  f"Repository: {repo_info['owner']}/{repo_info['name']}",
                  details=repo_info
              )
          except Exception as e:
              return CheckResult(
                  "Repository",
                  CheckStatus.FAIL,
                  str(e)
              )
  ```

  `/home/ross/Workspace/repo-agent/builder/doctor/checks/provider_check.py`:
  ```python
  class ProviderConnectivityCheck(HealthCheck):
      """Test provider API connectivity."""

      async def run(self, context):
          from builder.repository.discovery import RepositoryDiscovery

          discovery = RepositoryDiscovery()
          repo_info = discovery.discover()

          # Get credentials
          # Test API connectivity
          is_valid = await discovery.validate_provider(
              repo_info,
              context["settings"].git_provider.base_url,
              context["credentials"].get("git_token")
          )

          if is_valid:
              return CheckResult(
                  "Provider Connectivity",
                  CheckStatus.PASS,
                  f"{repo_info['provider']} API accessible"
              )
          else:
              return CheckResult(
                  "Provider Connectivity",
                  CheckStatus.FAIL,
                  f"Cannot connect to {repo_info['provider']} API",
                  "Check base URL and credentials"
              )
  ```

  * Register all checks in doctor system
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/doctor/checks/config_check.py`
  * `/home/ross/Workspace/repo-agent/builder/doctor/checks/credential_check.py`
  * `/home/ross/Workspace/repo-agent/builder/doctor/checks/repository_check.py`
  * `/home/ross/Workspace/repo-agent/builder/doctor/checks/provider_check.py`
- **Acceptance Criteria:**
  * All checks execute without errors
  * Checks detect common misconfigurations
  * Remediation guidance is actionable
  * Checks handle errors gracefully
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 2C.1

#### Task 2C.3: Create Doctor Command CLI
- **Task ID:** PHASE2-DOCTOR-003
- **Objective:** Implement `builder doctor` CLI command
- **Prerequisites:** Task 2C.2 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/cli/commands/doctor.py`:
    ```python
    import click
    import asyncio
    from builder.doctor import DoctorRunner
    from builder.doctor.checks.config_check import ConfigExistsCheck, ConfigValidCheck
    from builder.doctor.checks.credential_check import CredentialCheck
    from builder.doctor.checks.repository_check import RepositoryCheck
    from builder.doctor.checks.provider_check import ProviderConnectivityCheck
    from builder.config.toml_loader import TOMLConfigLoader
    from builder.credentials.manager import CredentialManager

    @click.command()
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
    @click.option("--json", is_flag=True, help="Output results as JSON")
    def doctor(verbose, json):
        """Run health checks and diagnostics."""
        asyncio.run(_run_doctor(verbose, json))

    async def _run_doctor(verbose: bool, json_output: bool):
        """Async doctor execution."""
        click.echo("Running Builder health checks...\n")

        # Initialize context
        context = {}

        # Try to load config (may fail, that's okay)
        try:
            loader = TOMLConfigLoader()
            config_dict = loader.load()
            from builder.config.settings import AutomationSettings
            context["settings"] = AutomationSettings(**config_dict)
            context["credentials"] = CredentialManager(context["settings"])
        except Exception:
            context["settings"] = None
            context["credentials"] = None

        # Register checks
        runner = DoctorRunner()
        runner.register_check(ConfigExistsCheck())
        runner.register_check(ConfigValidCheck())
        runner.register_check(CredentialCheck())
        runner.register_check(RepositoryCheck())
        runner.register_check(ProviderConnectivityCheck())

        # Run checks
        results = await runner.run_all(context)

        # Output results
        if json_output:
            import json
            output = [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "remediation": r.remediation,
                    "details": r.details,
                }
                for r in results
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            output = runner.format_results(results)
            click.echo(output)

        # Exit with appropriate code
        from builder.doctor import CheckStatus
        if any(r.status == CheckStatus.FAIL for r in results):
            raise click.Abort()
    ```
  * Register command in main CLI
  * Add `--fix` option for future auto-remediation
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/doctor.py`
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/main.py` (register command)
- **Acceptance Criteria:**
  * `builder doctor` runs all health checks
  * Output is clear and actionable
  * JSON output mode works
  * Exit code reflects overall status (0 = pass, 1 = failures)
  * Verbose mode shows additional details
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 2C.2

---

### Workstream 2D: Workflow Template Rendering (Can run parallel to other workstreams)

#### Task 2D.1: Design Workflow Templates
- **Task ID:** PHASE2-WORKFLOW-001
- **Objective:** Create workflow file templates for Gitea and GitHub
- **Prerequisites:** Phase 1 templates completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/builder/templates/init/gitea-workflow.yaml.j2`:
    ```yaml
    # Builder Automation Workflow
    # Generated: {{ timestamp }}

    name: Builder Automation

    on:
      issues:
        types: [opened, labeled]
      issue_comment:
        types: [created]

    jobs:
      process-issue:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout code
            uses: actions/checkout@v3

          - name: Setup Python
            uses: actions/setup-python@v4
            with:
              python-version: '3.11'

          - name: Install Builder
            run: pip install builder-cli

          - name: Process Issue
            env:
              BUILDER_CRED_GIT_TOKEN: {% raw %}${{ secrets.BUILDER_GIT_TOKEN }}{% endraw %}
              BUILDER_REPOSITORY__OWNER: {{ repository.owner }}
              BUILDER_REPOSITORY__NAME: {{ repository.name }}
            run: |
              builder process-issue --issue {% raw %}${{ github.event.issue.number }}{% endraw %}
    ```
  * Create similar template for GitHub Actions
  * Document template variables and customization options
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/builder/templates/init/gitea-workflow.yaml.j2`
  * `/home/ross/Workspace/repo-agent/builder/templates/init/github-workflow.yaml.j2`
- **Acceptance Criteria:**
  * Templates are valid workflow YAML
  * Properly escaped Jinja2 syntax in workflow variables
  * Templates include all necessary steps
  * Environment variables properly configured
- **Estimated Complexity:** Simple
- **Parallel Status:** Can run fully parallel

#### Task 2D.2: Integrate Workflow Rendering into Init
- **Task ID:** PHASE2-WORKFLOW-002
- **Objective:** Add workflow file generation to `builder init`
- **Prerequisites:** Tasks 2D.1 and 2B.1 completed
- **Technical Approach:**
  * Modify `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`:
    - Add workflow rendering step
    - Detect provider and use appropriate template
    - Save to `.gitea/workflows/` or `.github/workflows/`
    - Add `--skip-workflow` flag to disable workflow generation
  * Example addition:
    ```python
    # Step 8: Generate workflow
    click.echo("8. Generating workflow file...")

    if repo_info["provider"] == "gitea":
        workflow_dir = Path.cwd() / ".gitea" / "workflows"
        template_name = "init/gitea-workflow.yaml.j2"
    else:
        workflow_dir = Path.cwd() / ".github" / "workflows"
        template_name = "init/github-workflow.yaml.j2"

    workflow_dir.mkdir(parents=True, exist_ok=True)
    renderer.render_to_file(
        template_name,
        context,
        workflow_dir / "builder.yaml"
    )
    click.echo(f"   ✓ Created workflow file")
    ```
- **Files to Modify:**
  * `/home/ross/Workspace/repo-agent/builder/cli/commands/init.py`
- **Acceptance Criteria:**
  * Workflow file generated during init
  * Correct directory based on provider
  * Generated workflow is valid YAML
  * Can skip workflow generation with flag
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 2D.1 and 2B.1

---

### Phase 2 Testing & Integration

#### Task 2E.1: Write Unit Tests for Phase 2 Components
- **Task ID:** PHASE2-TEST-001
- **Objective:** Comprehensive unit test coverage for Phase 2
- **Prerequisites:** All Phase 2 tasks completed
- **Technical Approach:**
  * Create test files:
    - `/home/ross/Workspace/repo-agent/tests/test_repository_discovery.py`
    - `/home/ross/Workspace/repo-agent/tests/test_doctor.py`
    - `/home/ross/Workspace/repo-agent/tests/cli/test_init.py`
    - `/home/ross/Workspace/repo-agent/tests/cli/test_doctor.py`
  * Test coverage:
    - Repository discovery: URL parsing, provider detection, validation
    - Doctor: all health checks, result formatting, CLI integration
    - Init command: interactive and non-interactive modes, template rendering
  * Use Click's `CliRunner` for CLI testing
  * Mock Git operations and API calls
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/tests/test_repository_discovery.py`
  * `/home/ross/Workspace/repo-agent/tests/test_doctor.py`
  * `/home/ross/Workspace/repo-agent/tests/cli/test_init.py`
  * `/home/ross/Workspace/repo-agent/tests/cli/test_doctor.py`
- **Acceptance Criteria:**
  * All tests pass
  * Code coverage > 80% for Phase 2 code
  * Edge cases tested
  * CLI commands tested with CliRunner
- **Estimated Complexity:** Medium
- **Parallel Status:** Can start once individual components complete

#### Task 2E.2: End-to-End Integration Tests
- **Task ID:** PHASE2-TEST-002
- **Objective:** Full workflow testing for init and doctor
- **Prerequisites:** Task 2E.1 completed
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/tests/integration/test_init_doctor.py`
  * Test scenarios:
    1. Fresh repository init → doctor passes
    2. Init with missing credentials → doctor fails with remediation
    3. Init in non-Git directory → proper error
    4. Non-interactive init from env vars → success
  * Use temporary Git repositories for testing
  * Mock external API calls
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/tests/integration/test_init_doctor.py`
- **Acceptance Criteria:**
  * Full init → doctor workflow works
  * Tests run in isolated environments
  * No external API dependencies in tests
  * All scenarios covered
- **Estimated Complexity:** Medium
- **Parallel Status:** Sequential dependency on 2E.1

#### Task 2E.3: Manual QA Test Plan
- **Task ID:** PHASE2-TEST-003
- **Objective:** Manual testing checklist for human validation
- **Prerequisites:** All automated tests passing
- **Technical Approach:**
  * Create `/home/ross/Workspace/repo-agent/docs/manual-qa-phase1-2.md`:
    - [ ] Install builder-cli in fresh virtualenv
    - [ ] Run `builder init` in new Git repo (Gitea)
    - [ ] Run `builder init` in new Git repo (GitHub)
    - [ ] Run `builder doctor` after init (should pass)
    - [ ] Manually break config, run `builder doctor` (should fail with remediation)
    - [ ] Test credential storage in keyring
    - [ ] Test non-interactive init
    - [ ] Verify generated workflow files are valid
    - [ ] Test on Linux and macOS (if available)
  * Execute test plan and document results
- **Files to Create:**
  * `/home/ross/Workspace/repo-agent/docs/manual-qa-phase1-2.md`
- **Acceptance Criteria:**
  * Test plan documented
  * All manual tests pass
  * Issues found during QA are fixed or documented
- **Estimated Complexity:** Simple
- **Parallel Status:** Sequential dependency on 2E.2

---

## QUALITY ASSURANCE PLAN

### Unit Testing Strategy

**Components to Unit Test:**
1. **TOML Loader** (`builder/config/toml_loader.py`)
   - Test multi-source loading (defaults, system, repo, env)
   - Test precedence order
   - Test environment variable parsing
   - Test deep merge logic
   - Test save functionality

2. **Credential Backends** (`builder/credentials/`)
   - Keyring: store, retrieve, delete operations
   - Environment: read-only operations, env var naming
   - Encrypted File: encryption/decryption, file permissions
   - Manager: fallback chain, multi-backend coordination

3. **Exception Hierarchy** (`builder/exceptions/`)
   - Exception formatting
   - Exit code assignment
   - Remediation message generation

4. **Template Renderer** (`builder/templates/`)
   - Template rendering
   - Context variable substitution
   - Error handling for missing templates
   - File output operations

5. **Repository Discovery** (`builder/repository/discovery.py`)
   - Git repository detection
   - Remote URL parsing (SSH, HTTPS)
   - Provider detection (Gitea, GitHub)
   - Owner/repo extraction

6. **Doctor System** (`builder/doctor/`)
   - Individual health checks
   - Check result formatting
   - Summary statistics

**Testing Tools:**
- `pytest` for test execution
- `pytest-cov` for coverage reporting
- `pytest-mock` for mocking
- `pytest-asyncio` for async tests
- `click.testing.CliRunner` for CLI testing

**Coverage Target:** > 80% for new code

### Integration Testing Points

**Critical Integration Points:**
1. **Config Loading → Pydantic Validation**
   - TOML dict correctly parsed by Pydantic models
   - Validation errors properly raised

2. **Credential Manager → Config System**
   - Credential backend selection based on config
   - Fallback chain works across backends

3. **Repository Discovery → Init Command**
   - Auto-detected repo info flows into init
   - Templates rendered with correct values

4. **Doctor Checks → Real Configuration**
   - Health checks correctly identify issues
   - Remediation guidance matches actual problems

5. **CLI Commands → Core Systems**
   - Commands correctly initialize subsystems
   - Error handling flows through exception hierarchy

### End-to-End Test Scenarios

**Scenario 1: Fresh Repository Initialization**
1. Create temporary Git repository
2. Add remote origin (mock Gitea URL)
3. Run `builder init --non-interactive` with env vars
4. Verify `.builder/config.toml` created and valid
5. Verify credentials stored
6. Run `builder doctor` → all checks pass

**Scenario 2: Configuration Error Handling**
1. Initialize repository with `builder init`
2. Manually corrupt `.builder/config.toml`
3. Run `builder doctor` → config validation fails
4. Verify clear remediation message
5. Fix config
6. Run `builder doctor` → passes

**Scenario 3: Credential Management**
1. Initialize repository
2. Store credentials with different backends
3. Verify credential retrieval works
4. Delete credentials
5. Verify `builder doctor` detects missing credentials

**Scenario 4: Multi-Provider Support**
1. Test init with Gitea repository
2. Test init with GitHub repository
3. Verify correct workflow templates generated
4. Verify provider-specific validation

### Performance Benchmarks

**Target Metrics:**
- `builder init` completes in < 5 seconds (interactive)
- `builder doctor` completes in < 3 seconds (all checks)
- Config loading: < 100ms
- Template rendering: < 50ms per template
- Credential retrieval: < 50ms (keyring backend)

**Performance Testing:**
- Use `pytest-benchmark` for micro-benchmarks
- Profile with `cProfile` for bottleneck identification
- Test with large config files (edge case)

### Security Considerations

**Security Checklist:**
- [ ] Credentials never logged or printed to stdout
- [ ] Encrypted file backend uses strong encryption (Fernet)
- [ ] File permissions on credential files are restrictive (600)
- [ ] Keyring integration handles errors gracefully
- [ ] Environment variables properly sanitized
- [ ] No credential leakage in exception messages
- [ ] Template rendering doesn't execute arbitrary code
- [ ] TOML parsing uses safe loaders (no code execution)

**Security Testing:**
1. Verify credentials not in logs (`tests/test_security_no_leak.py`)
2. Check file permissions on generated files
3. Test exception messages don't contain sensitive data
4. Validate TOML parser safety (no eval/exec)

### Edge Cases

**Edge Cases to Test:**

1. **Git Repository:**
   - No remote configured
   - Multiple remotes configured
   - Non-standard remote URL formats
   - Detached HEAD state
   - Dirty working directory

2. **Configuration:**
   - Empty config files
   - Partial configs (missing sections)
   - Invalid TOML syntax
   - Conflicting settings across layers
   - Very large config files

3. **Credentials:**
   - Keyring not available (headless systems)
   - Read-only filesystems
   - Permission denied on credential file
   - Corrupted encrypted file
   - Missing encryption key

4. **Templates:**
   - Missing template variables in context
   - Template syntax errors
   - Output path permission denied
   - Disk full during file write

5. **Network:**
   - Provider API unreachable
   - API rate limiting
   - Invalid credentials (401/403)
   - Slow network (timeout handling)

6. **CLI:**
   - Piped input (non-TTY)
   - Interrupted prompts (Ctrl+C)
   - Invalid flag combinations
   - Very long input values

---

## DEPLOYMENT STRATEGY

### Environment Setup

**Development Environment:**
1. Clone repository
2. Create virtual environment: `python -m venv .venv`
3. Install in editable mode: `pip install -e ".[dev]"`
4. Run tests: `pytest`
5. Activate pre-commit hooks (if configured)

**CI/CD Environment:**
1. GitHub Actions / Gitea Actions workflow
2. Test matrix: Python 3.11, 3.12 on Linux, macOS, Windows
3. Coverage reporting with Codecov
4. Automated package building
5. PyPI deployment on tag push

**Production Environment (User Installation):**
1. `pip install builder-cli`
2. Verify installation: `builder --version`
3. Initialize in repository: `builder init`

### Migration Steps

**For Existing Installations:**

1. **Backup Current Setup:**
   ```bash
   cp automation/config/automation_config.yaml automation_config.yaml.backup
   ```

2. **Install New Version:**
   ```bash
   pip install --upgrade builder-cli
   ```

3. **Migrate Configuration:**
   ```bash
   builder migrate-config automation/config/automation_config.yaml
   ```
   This command (to be implemented) converts YAML → TOML

4. **Verify Migration:**
   ```bash
   builder doctor
   ```

5. **Update Workflows:**
   - Replace `automation` command with `builder`
   - Update environment variable names (`AUTOMATION_*` → `BUILDER_*`)

### Rollback Procedures

**If Phase 1-2 Deployment Fails:**

1. **Revert Package:**
   ```bash
   pip install builder-cli==<previous-version>
   ```

2. **Restore Configuration:**
   ```bash
   cp automation_config.yaml.backup automation/config/automation_config.yaml
   ```

3. **Verify Rollback:**
   ```bash
   automation --version
   automation list-plans  # Test existing command
   ```

**Data Preservation:**
- Configuration files backed up before migration
- Credentials remain in keyring (not affected by package changes)
- State files (`.automation/state/`) preserved
- Plans directory unchanged

### Monitoring and Observability

**Logging:**
- All commands log to `~/.builder/logs/builder.log`
- Structured logging with `structlog` (JSON format)
- Log rotation: 10MB max size, 5 backups
- Log levels: DEBUG, INFO, WARN, ERROR

**Metrics (Future Enhancement):**
- Command execution times
- Success/failure rates
- Provider API response times
- Health check results over time

**Telemetry (Optional, Opt-In):**
- Anonymous usage statistics
- Error reporting (sanitized, no credentials)
- Feature usage tracking

**Observability Commands:**
- `builder doctor` - current health status
- `builder config show` - view effective configuration
- `builder logs` - view recent logs
- `builder debug` - enable debug logging

---

## RISK MITIGATION

### Technical Risks

**Risk 1: Keyring Not Available on Headless Systems**
- **Mitigation:** Graceful fallback to encrypted file backend
- **Detection:** `builder doctor` warns if keyring unavailable
- **Remediation:** Document encrypted file setup for CI/CD

**Risk 2: Breaking Changes for Existing Users**
- **Mitigation:** Maintain backward compatibility via legacy commands
- **Detection:** Integration tests with old config files
- **Remediation:** Migration tool (`builder migrate-config`)

**Risk 3: Template Rendering Errors**
- **Mitigation:** Validate templates during package build
- **Detection:** Unit tests for all templates
- **Remediation:** Clear error messages with remediation steps

**Risk 4: Provider API Changes**
- **Mitigation:** Version provider APIs, abstract provider interface
- **Detection:** Provider connectivity checks in `builder doctor`
- **Remediation:** Update provider adapters, maintain backward compat

### Operational Risks

**Risk 1: Credential Loss During Migration**
- **Mitigation:** Credentials remain in keyring, not affected by package
- **Detection:** Pre-migration credential check
- **Remediation:** Re-run `builder init` to re-store credentials

**Risk 2: Configuration Corruption**
- **Mitigation:** Validate TOML before writing, atomic file operations
- **Detection:** `builder doctor` config validation
- **Remediation:** Restore from backup or re-run `builder init`

**Risk 3: Incomplete Documentation**
- **Mitigation:** Documentation written alongside code
- **Detection:** Manual QA checklist includes doc review
- **Remediation:** Iterative doc improvements based on user feedback

---

## PARALLEL EXECUTION SUMMARY

### Phase 1 Parallel Groups

**Group 1 (Can Start Immediately):**
- Task 1B.1: Design TOML Schema (design only)
- Task 1C.1: Design Credential Architecture (design only)
- Task 1D.1: Design Exception Hierarchy (design only)
- Task 1E.1: Design Template Structure (design only)

**Group 2 (After Group 1 Completes):**
- Task 1A.1: Rename Package Directory
- Task 1B.2: Implement TOML Parser (parallel to 1A.1 after initial rename)
- Task 1C.2: Implement Keyring Backend
- Task 1C.3: Implement Environment Backend (parallel to 1C.2)
- Task 1C.4: Implement Encrypted File Backend (parallel to 1C.2, 1C.3)
- Task 1D.2: Implement Base Exceptions
- Task 1E.2: Implement Jinja2 Renderer

**Group 3 (After Group 2 Completes):**
- Task 1A.2: Create CLI Entry Point Structure
- Task 1B.3: Integrate TOML with Pydantic
- Task 1C.5: Implement Credential Manager Facade
- Task 1D.3: Integrate Exception Handler in CLI
- Task 1E.3: Create Initial Template Files

**Group 4 (Sequential after Group 3):**
- Task 1A.3: Migrate Existing Commands to Legacy

**Group 5 (After All Components Complete):**
- Task 1F.1: Write Unit Tests (can start per-component)
- Task 1F.2: Integration Testing

### Phase 2 Parallel Groups

**Group 1 (After Phase 1 Complete):**
- Task 2A.1: Implement Git Repository Introspection
- Task 2B.1: Implement Interactive Initialization
- Task 2C.1: Implement Health Check System
- Task 2D.1: Design Workflow Templates

**Group 2 (After Group 1 Completes):**
- Task 2A.2: Add Provider Validation
- Task 2B.2: Add Non-Interactive Mode (parallel to 2A.2)
- Task 2C.2: Implement Core Health Checks
- Task 2D.2: Integrate Workflow Rendering

**Group 3 (After Group 2 Completes):**
- Task 2C.3: Create Doctor Command CLI

**Group 4 (After All Components Complete):**
- Task 2E.1: Write Unit Tests (can start per-component)
- Task 2E.2: End-to-End Integration Tests
- Task 2E.3: Manual QA Test Plan

---

## TIMELINE ESTIMATES

### Phase 1: Foundation (5-7 days)

- **Day 1:** Design work (all 1X.1 tasks) + Package restructuring (1A.1)
- **Day 2:** TOML parser (1B.2), Credential backends (1C.2, 1C.3), Exception hierarchy (1D.2), Template renderer (1E.2)
- **Day 3:** Encrypted file backend (1C.4), CLI entry point (1A.2), Pydantic integration (1B.3)
- **Day 4:** Credential manager (1C.5), Exception CLI integration (1D.3), Template files (1E.3), Legacy migration (1A.3)
- **Day 5:** Unit tests (1F.1)
- **Day 6-7:** Integration tests (1F.2), bug fixes, polish

### Phase 2: Core Commands (4-6 days)

- **Day 1:** Repository discovery (2A.1), Init command skeleton (2B.1), Doctor system (2C.1), Workflow templates (2D.1)
- **Day 2:** Provider validation (2A.2), Non-interactive init (2B.2), Health checks (2C.2)
- **Day 3:** Doctor CLI (2C.3), Workflow integration (2D.2)
- **Day 4:** Unit tests (2E.1)
- **Day 5:** Integration tests (2E.2)
- **Day 6:** Manual QA (2E.3), bug fixes, documentation

**Total Estimate:** 9-13 days (with parallel execution)

---

## APPENDIX: File Reference

### New Files Created in Phase 1

```
/home/ross/Workspace/repo-agent/
├── builder/                                    (renamed from automation/)
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── init.py                        (Phase 2)
│   │       ├── doctor.py                      (Phase 2)
│   │       ├── config.py                      (stub)
│   │       └── legacy.py
│   ├── config/
│   │   ├── toml_loader.py
│   │   ├── migration.py
│   │   └── schema.toml
│   ├── credentials/
│   │   ├── __init__.py
│   │   ├── backend.py
│   │   ├── keyring_backend.py
│   │   ├── env_backend.py
│   │   ├── encrypted_backend.py
│   │   └── manager.py
│   ├── exceptions/
│   │   └── __init__.py
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── init/
│   │   │   ├── config.toml.j2
│   │   │   ├── README.md.j2
│   │   │   ├── gitea-workflow.yaml.j2
│   │   │   └── github-workflow.yaml.j2
│   │   └── doctor/
│   │       └── report.md.j2
│   ├── repository/                            (Phase 2)
│   │   ├── __init__.py
│   │   └── discovery.py
│   └── doctor/                                (Phase 2)
│       ├── __init__.py
│       └── checks/
│           ├── __init__.py
│           ├── config_check.py
│           ├── credential_check.py
│           ├── repository_check.py
│           └── provider_check.py
├── docs/
│   ├── config-schema.md
│   ├── security.md
│   ├── exceptions.md
│   ├── templates.md
│   └── manual-qa-phase1-2.md
└── tests/
    ├── test_toml_loader.py
    ├── test_credentials.py
    ├── test_exceptions.py
    ├── test_templates.py
    ├── test_repository_discovery.py            (Phase 2)
    ├── test_doctor.py                          (Phase 2)
    ├── cli/
    │   ├── test_init.py                        (Phase 2)
    │   └── test_doctor.py                      (Phase 2)
    └── integration/
        ├── test_phase1.py
        └── test_init_doctor.py                 (Phase 2)
```

### Modified Files

```
/home/ross/Workspace/repo-agent/
├── pyproject.toml                              (dependencies, entry points, package name)
├── builder/__init__.py                         (updated imports)
├── builder/__version__.py                      (preserved)
└── builder/config/settings.py                  (added from_toml method)
```

---

## CONCLUSION

This implementation plan provides a comprehensive blueprint for transforming repo-agent into a self-contained CLI tool. The plan is structured to maximize parallel development, minimize risk through incremental testing, and maintain backward compatibility for existing users.

**Key Deliverables:**
- Self-contained `builder-cli` package installable via PyPI
- `builder init` command for easy onboarding
- `builder doctor` command for diagnostics
- Multi-layer credential management (keyring, env, encrypted file)
- TOML-based configuration system
- Template-driven workflow generation
- Comprehensive exception hierarchy with remediation
- Full test coverage (unit, integration, E2E)

**Next Steps After Phase 1-2:**
- Phase 3: Advanced Commands (`builder config`, `builder template`, `builder upgrade`)
- Phase 4: Plugin System and Extensibility
- Phase 5: Interactive TUI and Enhanced UX
- Phase 6: Multi-Repository Management

This plan is designed to be executed by autonomous agents or developers with clear, actionable specifications for each task. All file paths are absolute, dependencies are explicit, and acceptance criteria are testable.
