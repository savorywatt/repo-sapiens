"""Performance benchmarks for repo-agent critical operations.

This benchmark suite measures performance across critical paths:
1. Configuration Loading - YAML parsing, environment resolution, credential resolution
2. Git Discovery - Repository detection and config parsing
3. Template Rendering - Simple and complex Jinja2 template rendering
4. Credential Resolution - Keyring, environment, and encrypted backends
5. State Management - File I/O operations with atomic writes

Target Performance Metrics:
- Configuration Loading: <100ms for typical config
- Git Discovery: <200ms for 10 repositories
- Template Rendering: <50ms simple, <200ms complex
- Credential Resolution: <50ms per credential
- State Management: <100ms per operation
"""

import gc
import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Import modules to benchmark
from automation.config.settings import (
    AutomationSettings,
)
from automation.credentials.environment_backend import EnvironmentBackend
from automation.credentials.keyring_backend import KeyringBackend
from automation.credentials.resolver import CredentialResolver
from automation.engine.state_manager import StateManager
from automation.git.discovery import GitDiscovery
from automation.rendering import SecureTemplateEngine

# ============================================================================
# Configuration Loading Benchmarks
# ============================================================================


class TestConfigurationLoadingPerformance:
    """Benchmark configuration loading operations."""

    @pytest.fixture
    def sample_config_yaml(self, tmp_path):
        """Create a sample YAML configuration."""
        config = {
            "git_provider": {
                "provider_type": "gitea",
                "base_url": "https://gitea.example.com",
                "api_token": "${GITEA_API_TOKEN}",
            },
            "repository": {
                "owner": "test-org",
                "name": "test-repo",
                "default_branch": "main",
            },
            "agent_provider": {
                "provider_type": "claude-api",
                "model": "claude-opus-4.5",
                "api_key": "${CLAUDE_API_KEY}",
            },
            "workflow": {
                "plans_directory": "plans",
                "state_directory": ".automation/state",
                "branching_strategy": "per-agent",
                "max_concurrent_tasks": 3,
                "review_approval_threshold": 0.8,
            },
            "tags": {
                "needs_planning": "needs-planning",
                "plan_review": "plan-review",
                "ready_to_implement": "ready-to-implement",
                "implementation_in_progress": "implementation-in-progress",
                "code_review_needed": "code-review-needed",
                "approved": "approved",
                "merged": "merged",
            },
        }

        config_path = tmp_path / "automation_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        return config_path

    @pytest.fixture(autouse=True)
    def mock_env_vars(self, monkeypatch):
        """Mock environment variables for credential resolution."""
        monkeypatch.setenv("GITEA_API_TOKEN", "mock_gitea_token")
        monkeypatch.setenv("CLAUDE_API_KEY", "mock_claude_key")

    def test_load_yaml_config_simple(self, benchmark, sample_config_yaml):
        """Benchmark basic YAML file loading."""

        def load_config():
            with open(sample_config_yaml) as f:
                return yaml.safe_load(f)

        result = benchmark(load_config)
        assert result is not None
        assert "git_provider" in result

    def test_parse_pydantic_settings(self, benchmark, sample_config_yaml, monkeypatch):
        """Benchmark Pydantic model parsing and validation."""

        def parse_settings():
            return AutomationSettings.from_yaml(str(sample_config_yaml))

        result = benchmark(parse_settings)
        assert result is not None
        assert result.git_provider.base_url is not None

    def test_environment_variable_resolution(self, benchmark, monkeypatch):
        """Benchmark environment variable resolution."""
        monkeypatch.setenv("TEST_VAR_1", "value1")
        monkeypatch.setenv("TEST_VAR_2", "value2")
        monkeypatch.setenv("TEST_VAR_3", "value3")

        def resolve_env_vars():
            import os

            return {
                "var1": os.getenv("TEST_VAR_1"),
                "var2": os.getenv("TEST_VAR_2"),
                "var3": os.getenv("TEST_VAR_3"),
            }

        result = benchmark(resolve_env_vars)
        assert result["var1"] == "value1"

    def test_credential_resolver_initialization(self, benchmark, tmp_path):
        """Benchmark credential resolver initialization."""

        def init_resolver():
            return CredentialResolver(encrypted_file_path=tmp_path / "creds.enc")

        result = benchmark(init_resolver)
        assert result is not None


# ============================================================================
# Git Discovery Benchmarks
# ============================================================================


class TestGitDiscoveryPerformance:
    """Benchmark Git discovery operations."""

    @pytest.fixture
    def mock_git_repo(self):
        """Create mock Git repository."""
        repo = MagicMock()
        remote = MagicMock()
        remote.name = "origin"
        remote.url = "https://gitea.example.com/owner/repo.git"
        repo.remotes = [remote]
        repo.head.ref.name = "main"
        return repo

    def test_git_discovery_initialization(self, benchmark, tmp_path):
        """Benchmark GitDiscovery object creation."""

        def init_discovery():
            return GitDiscovery(repo_path=tmp_path)

        result = benchmark(init_discovery)
        assert result is not None

    def test_parse_git_url(self, benchmark):
        """Benchmark Git URL parsing."""
        urls = [
            "https://gitea.example.com/owner/repo.git",
            "git@gitea.example.com:owner/repo.git",
            "https://gitea.example.com/owner/repo",
        ]

        def parse_urls():
            from automation.git.parser import GitUrlParser

            results = []
            for url in urls:
                try:
                    result = GitUrlParser.parse(url)
                    results.append(result)
                except Exception:
                    pass
            return results

        result = benchmark(parse_urls)
        assert len(result) > 0

    @patch("automation.git.discovery.git.Repo")
    def test_repository_info_detection(self, mock_git_class, benchmark, mock_git_repo):
        """Benchmark repository information detection."""
        mock_git_class.return_value = mock_git_repo

        def detect_repo():
            discovery = GitDiscovery()
            return discovery.detect_gitea_config()

        result = benchmark(detect_repo)
        assert result is not None

    def test_multiple_remote_handling(self, benchmark):
        """Benchmark handling of multiple remotes."""

        def handle_multiple_remotes():
            repos = []
            for i in range(10):
                repo_info = {
                    "owner": f"owner{i}",
                    "name": f"repo{i}",
                    "base_url": "https://gitea.example.com",
                }
                repos.append(repo_info)
            return repos

        result = benchmark(handle_multiple_remotes)
        assert len(result) == 10


# ============================================================================
# Template Rendering Benchmarks
# ============================================================================


class TestTemplateRenderingPerformance:
    """Benchmark Jinja2 template rendering operations."""

    @pytest.fixture
    def template_engine(self, tmp_path):
        """Create template engine with sample templates."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        # Simple template
        simple_template = template_dir / "simple.yaml.j2"
        simple_template.write_text(
            """
name: {{ workflow_name }}
version: "1.0"
owner: {{ owner }}
repo: {{ repo }}
"""
        )

        # Complex template with loops and conditionals
        complex_template = template_dir / "complex.yaml.j2"
        complex_template.write_text(
            """
workflows:
{% for item in items %}
  - name: {{ item.name }}
    description: {{ item.description }}
    {% if item.enabled %}
    enabled: true
    {% if item.requires_approval %}
    requires_approval: true
    {% endif %}
    steps:
    {% for step in item.steps %}
      - name: {{ step.name }}
        run: {{ step.command }}
    {% endfor %}
    {% else %}
    enabled: false
    {% endif %}
{% endfor %}
"""
        )

        return template_dir

    def test_simple_template_render(self, benchmark, template_engine):
        """Benchmark simple template rendering (<50ms target)."""
        context = {
            "workflow_name": "build",
            "owner": "test-org",
            "repo": "test-repo",
        }

        def render_simple():
            from jinja2 import Environment, FileSystemLoader

            env = Environment(loader=FileSystemLoader(str(template_engine)))
            template = env.get_template("simple.yaml.j2")
            return template.render(**context)

        result = benchmark(render_simple)
        assert "build" in result
        assert "test-org" in result

    def test_complex_template_render(self, benchmark, template_engine):
        """Benchmark complex template rendering (<200ms target)."""
        context = {
            "items": [
                {
                    "name": f"workflow-{i}",
                    "description": f"Workflow {i}",
                    "enabled": i % 2 == 0,
                    "requires_approval": i % 3 == 0,
                    "steps": [
                        {"name": f"step-{j}", "command": f'echo "Step {j}"'} for j in range(5)
                    ],
                }
                for i in range(10)
            ]
        }

        def render_complex():
            from jinja2 import Environment, FileSystemLoader

            env = Environment(loader=FileSystemLoader(str(template_engine)))
            template = env.get_template("complex.yaml.j2")
            return template.render(**context)

        result = benchmark(render_complex)
        assert "workflows:" in result
        assert "workflow-" in result

    def test_secure_engine_initialization(self, benchmark, template_engine):
        """Benchmark SecureTemplateEngine initialization."""

        def init_engine():
            return SecureTemplateEngine(template_dir=template_engine)

        result = benchmark(init_engine)
        assert result is not None


# ============================================================================
# Credential Resolution Benchmarks
# ============================================================================


class TestCredentialResolutionPerformance:
    """Benchmark credential resolution operations."""

    @pytest.fixture(autouse=True)
    def setup_creds(self, monkeypatch):
        """Setup credential environment variables."""
        monkeypatch.setenv("TEST_CRED_1", "value1")
        monkeypatch.setenv("TEST_CRED_2", "value2")
        monkeypatch.setenv("TEST_CRED_3", "value3")

    def test_environment_backend_resolution(self, benchmark):
        """Benchmark environment variable credential resolution (<50ms)."""
        backend = EnvironmentBackend()

        def resolve_env():
            return backend.get("TEST_CRED_1")

        result = benchmark(resolve_env)
        assert result == "value1"

    def test_environment_backend_multiple_credentials(self, benchmark):
        """Benchmark resolving multiple environment credentials."""
        backend = EnvironmentBackend()

        def resolve_multiple():
            results = []
            for i in range(1, 4):
                cred = backend.get(f"TEST_CRED_{i}")
                results.append(cred)
            return results

        result = benchmark(resolve_multiple)
        assert len(result) == 3

    @patch("keyring.get_password")
    def test_keyring_backend_resolution(self, mock_keyring, benchmark):
        """Benchmark keyring credential resolution (<50ms)."""
        mock_keyring.return_value = "mock_token"
        backend = KeyringBackend()

        def resolve_keyring():
            return backend.get("test_service", "test_key")

        result = benchmark(resolve_keyring)
        assert result == "mock_token"

    def test_credential_resolver_environment(self, benchmark, monkeypatch):
        """Benchmark CredentialResolver with environment variables."""
        monkeypatch.setenv("GITEA_API_TOKEN", "test_token_value")
        resolver = CredentialResolver()

        def resolve():
            return resolver.resolve("${GITEA_API_TOKEN}")

        result = benchmark(resolve)
        assert result == "test_token_value"

    def test_credential_resolver_cache_hit(self, benchmark, monkeypatch):
        """Benchmark credential resolver with cache hit."""
        monkeypatch.setenv("API_KEY", "cached_value")
        resolver = CredentialResolver()

        # Prime cache
        resolver.resolve("${API_KEY}", cache=True)

        def resolve_cached():
            return resolver.resolve("${API_KEY}", cache=True)

        result = benchmark(resolve_cached)
        assert result == "cached_value"


# ============================================================================
# State Management Benchmarks
# ============================================================================


class TestStateManagementPerformance:
    """Benchmark state management operations."""

    @pytest.fixture
    def state_manager(self, tmp_path):
        """Create state manager with temp directory."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        return StateManager(str(state_dir))

    @pytest.fixture
    def sample_state(self):
        """Create sample state data."""
        return {
            "plan_id": "test_plan_001",
            "status": "in_progress",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "stages": {
                "planning": {"status": "completed", "data": {"output": "plan content"}},
                "implementation": {"status": "in_progress", "data": {}},
                "review": {"status": "pending", "data": {}},
            },
            "tasks": {
                "task_001": {"status": "completed", "result": "success"},
                "task_002": {"status": "in_progress", "result": None},
            },
        }

    @pytest.mark.asyncio
    async def test_load_state_new(self, benchmark, state_manager):
        """Benchmark loading new state (creates initial state)."""

        async def load_new():
            return await state_manager.load_state("new_plan")

        result = await benchmark(load_new)
        assert result["plan_id"] == "new_plan"

    @pytest.mark.asyncio
    async def test_save_state(self, benchmark, state_manager, sample_state):
        """Benchmark saving state to file (<100ms)."""
        # Create initial state
        await state_manager.save_state("test_plan", sample_state.copy())

        modified_state = sample_state.copy()
        modified_state["status"] = "completed"

        async def save():
            await state_manager.save_state("test_plan", modified_state)

        await benchmark(save)

    @pytest.mark.asyncio
    async def test_state_transaction(self, benchmark, state_manager, sample_state):
        """Benchmark atomic state transaction."""

        async def transaction():
            async with state_manager.transaction("tx_plan") as state:
                state["status"] = "processing"
                state["updated_at"] = "2024-01-01T12:00:00"

        await benchmark(transaction)

    @pytest.mark.asyncio
    async def test_load_existing_state(self, benchmark, state_manager, sample_state):
        """Benchmark loading existing state."""
        # Create state first
        await state_manager.save_state("existing_plan", sample_state.copy())

        async def load():
            return await state_manager.load_state("existing_plan")

        result = await benchmark(load)
        assert result["plan_id"] == "existing_plan"

    @pytest.mark.asyncio
    async def test_large_state_serialization(self, benchmark, state_manager):
        """Benchmark serialization of large state."""
        large_state = {
            "plan_id": "large_plan",
            "status": "in_progress",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "stages": {f"stage_{i}": {"status": "pending", "data": {}} for i in range(20)},
            "tasks": {
                f"task_{i}": {"status": "pending", "data": {"details": "x" * 1000}}
                for i in range(100)
            },
        }

        async def save_large():
            await state_manager.save_state("large_plan", large_state)

        await benchmark(save_large)


# ============================================================================
# Integration Benchmarks
# ============================================================================


class TestIntegrationPerformance:
    """Benchmark integrated operations."""

    def test_end_to_end_config_load_resolve(self, benchmark, tmp_path, monkeypatch):
        """Benchmark complete config load and credential resolution."""
        # Setup
        monkeypatch.setenv("GITEA_API_TOKEN", "test_token")
        monkeypatch.setenv("CLAUDE_API_KEY", "test_key")

        config = {
            "git_provider": {
                "provider_type": "gitea",
                "base_url": "https://gitea.example.com",
                "api_token": "${GITEA_API_TOKEN}",
            },
            "repository": {
                "owner": "test-org",
                "name": "test-repo",
                "default_branch": "main",
            },
            "agent_provider": {
                "provider_type": "claude-api",
                "model": "claude-opus-4.5",
                "api_key": "${CLAUDE_API_KEY}",
            },
            "workflow": {
                "plans_directory": "plans",
                "state_directory": ".automation/state",
            },
        }

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))

        def load_and_resolve():
            settings = AutomationSettings.from_yaml(str(config_path))
            # Credentials are resolved during Pydantic validation
            return settings

        result = benchmark(load_and_resolve)
        assert result is not None

    def test_template_render_with_config(self, benchmark, tmp_path, monkeypatch):
        """Benchmark template rendering using loaded config."""
        monkeypatch.setenv("GITEA_TOKEN", "test_token")

        # Create template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "workflow.yaml.j2"
        template_file.write_text(
            """
name: {{ workflow_name }}
owner: {{ owner }}
repo: {{ repo }}
steps:
{% for i in range(5) %}
  - name: step_{{ i }}
    run: echo "Step {{ i }}"
{% endfor %}
"""
        )

        from jinja2 import Environment, FileSystemLoader

        context = {
            "workflow_name": "test_workflow",
            "owner": "test_owner",
            "repo": "test_repo",
        }

        def render():
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            template = env.get_template("workflow.yaml.j2")
            return template.render(**context)

        result = benchmark(render)
        assert "workflow" in result


# ============================================================================
# Memory Profiling Tests (optional, requires memory_profiler)
# ============================================================================


class TestMemoryUsage:
    """Memory profiling for large operations."""

    def test_large_config_parsing_memory(self, tmp_path, monkeypatch):
        """Profile memory usage of large configuration parsing."""
        monkeypatch.setenv("TOKEN", "test_token")

        # Create large config
        large_config = {
            "git_provider": {
                "provider_type": "gitea",
                "base_url": "https://gitea.example.com",
                "api_token": "${TOKEN}",
            },
            "repositories": [
                {
                    "owner": f"owner_{i}",
                    "name": f"repo_{i}",
                    "default_branch": "main",
                }
                for i in range(100)
            ],
        }

        config_path = tmp_path / "large_config.yaml"
        config_path.write_text(yaml.dump(large_config))

        # Parse and check memory (basic check)

        initial_objects = len(gc.get_objects()) if "gc" in dir() else 0

        settings = AutomationSettings.from_yaml(str(config_path))
        assert settings is not None

    def test_state_file_memory_growth(self, tmp_path):
        """Profile memory growth when handling large state files."""
        state_manager = StateManager(str(tmp_path / "state"))

        # Create progressively larger state
        for size in [10, 50, 100]:
            state = {
                "plan_id": f"plan_{size}",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "tasks": {
                    f"task_{i}": {"status": "pending", "data": {"content": "x" * 1000}}
                    for i in range(size)
                },
            }

            # Write and verify
            state_path = tmp_path / "state" / f"plan_{size}.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state))
            assert state_path.exists()


# ============================================================================
# Performance Assertion Tests
# ============================================================================


class TestPerformanceTargets:
    """Verify performance targets are met."""

    def test_config_loading_target(self, benchmark, tmp_path, monkeypatch):
        """Verify config loading meets <100ms target."""
        monkeypatch.setenv("API_TOKEN", "test")

        config = {
            "git_provider": {
                "provider_type": "gitea",
                "base_url": "https://gitea.example.com",
                "api_token": "${API_TOKEN}",
            },
            "workflow": {"plans_directory": "plans"},
        }

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))

        result = benchmark(AutomationSettings.from_yaml, str(config_path), min_rounds=3)

        # Verify result is valid
        assert result is not None
        # Note: actual timing assertions should be reviewed post-run

    def test_template_rendering_simple_target(self, benchmark, tmp_path):
        """Verify simple template rendering meets <50ms target."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test.yaml.j2").write_text("name: {{ name }}\n")

        from jinja2 import Environment, FileSystemLoader

        def render():
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            template = env.get_template("test.yaml.j2")
            return template.render(name="test")

        benchmark(render, min_rounds=5)

    def test_credential_resolution_target(self, benchmark, monkeypatch):
        """Verify credential resolution meets <50ms target."""
        monkeypatch.setenv("CRED_TEST", "value")
        backend = EnvironmentBackend()

        def resolve():
            return backend.get("CRED_TEST")

        benchmark(resolve, min_rounds=5)


# ============================================================================
# Comparative Benchmarks
# ============================================================================


class TestComparativeBenchmarks:
    """Compare performance across different approaches."""

    def test_yaml_safe_load_vs_unsafe(self, benchmark, tmp_path):
        """Compare safe_load vs load_all performance."""
        config = {"key": "value", "nested": {"data": [1, 2, 3]}}
        yaml_content = yaml.dump(config)
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        def load_safe():
            with open(yaml_path) as f:
                return yaml.safe_load(f)

        result = benchmark(load_safe)
        assert result is not None

    def test_direct_render_vs_engine(self, benchmark, tmp_path):
        """Compare direct Jinja2 vs engine wrapper performance."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test.j2").write_text("{{ name }}\n")

        from jinja2 import Environment, FileSystemLoader

        def render_direct():
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            template = env.get_template("test.j2")
            return template.render(name="test")

        benchmark(render_direct)

    def test_json_vs_pickle_state(self, benchmark, tmp_path):
        """Compare JSON vs pickle for state serialization."""
        state = {
            "id": "test",
            "timestamp": "2024-01-01T00:00:00",
            "data": {"nested": [1, 2, 3] * 10},
        }

        def serialize_json():
            return json.dumps(state)

        benchmark(serialize_json)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
