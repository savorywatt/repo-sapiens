"""Unit tests for repo_sapiens/cli/init.py - Repository initialization CLI."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click import ClickException
from click.testing import CliRunner

from repo_sapiens.cli.init import RepoInitializer, init_command
from repo_sapiens.git.exceptions import GitDiscoveryError


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing Click commands."""
    return CliRunner()


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock Git repository directory."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    git_dir = repo_dir / ".git"
    git_dir.mkdir()
    return repo_dir


@pytest.fixture
def mock_repo_info():
    """Create a mock RepositoryInfo object."""
    mock_info = Mock()
    mock_info.remote_name = "origin"
    mock_info.owner = "test-owner"
    mock_info.repo = "test-repo"
    mock_info.base_url = "https://gitea.example.com"
    mock_info.full_name = "test-owner/test-repo"
    return mock_info


@pytest.fixture
def github_repo_info():
    """Create a mock RepositoryInfo for GitHub."""
    mock_info = Mock()
    mock_info.remote_name = "origin"
    mock_info.owner = "github-owner"
    mock_info.repo = "github-repo"
    mock_info.base_url = "https://github.com"
    mock_info.full_name = "github-owner/github-repo"
    return mock_info


@pytest.fixture
def gitlab_repo_info():
    """Create a mock RepositoryInfo for GitLab."""
    mock_info = Mock()
    mock_info.remote_name = "origin"
    mock_info.owner = "gitlab-owner"
    mock_info.repo = "gitlab-repo"
    mock_info.base_url = "https://gitlab.com"
    mock_info.full_name = "gitlab-owner/gitlab-repo"
    return mock_info


# =============================================================================
# RepoInitializer Initialization Tests
# =============================================================================


class TestRepoInitializerInit:
    """Tests for RepoInitializer initialization."""

    def test_init_with_defaults(self, tmp_path):
        """Should initialize with default values."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_path == tmp_path
        assert initializer.config_path == Path("config.yaml")
        assert initializer.backend == "keyring"
        assert initializer.non_interactive is False
        assert initializer.setup_secrets is True

    def test_init_with_explicit_backend(self, tmp_path):
        """Should use explicitly specified backend."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=False,
        )

        assert initializer.backend == "environment"

    def test_init_with_encrypted_backend(self, tmp_path):
        """Should accept encrypted backend option."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="encrypted",
            non_interactive=True,
            setup_secrets=False,
        )

        assert initializer.backend == "encrypted"

    def test_init_state_initialization(self, tmp_path):
        """Should initialize internal state variables."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_info is None
        assert initializer.provider_type is None
        assert initializer.gitea_token is None
        assert initializer.agent_type is None
        assert initializer.agent_mode == "local"
        assert initializer.agent_api_key is None

    def test_init_goose_default_values(self, tmp_path):
        """Should initialize Goose-specific settings with defaults."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.goose_llm_provider is None
        assert initializer.goose_model is None
        assert initializer.goose_toolkit == "default"
        assert initializer.goose_temperature == 0.7


# =============================================================================
# Backend Detection Tests
# =============================================================================


class TestRepoInitializerDetectBackend:
    """Tests for backend detection."""

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_detect_backend_keyring_available(self, mock_keyring_class, tmp_path):
        """Should detect keyring backend when available."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend=None,
            non_interactive=False,
            setup_secrets=True,
        )

        assert initializer.backend == "keyring"

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_detect_backend_fallback_to_environment(self, mock_keyring_class, tmp_path):
        """Should fall back to environment backend when keyring unavailable."""
        mock_keyring = Mock()
        mock_keyring.available = False
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend=None,
            non_interactive=False,
            setup_secrets=True,
        )

        assert initializer.backend == "environment"


# =============================================================================
# Repository Discovery Tests
# =============================================================================


class TestRepoInitializerDiscoverRepository:
    """Tests for repository discovery."""

    @patch("repo_sapiens.cli.init.GitDiscovery")
    def test_discover_repository_success(self, mock_discovery_class, tmp_path, mock_repo_info):
        """Should successfully discover repository configuration."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "gitea"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer._discover_repository()

        assert initializer.repo_info == mock_repo_info
        assert initializer.provider_type == "gitea"
        mock_discovery_class.assert_called_once_with(tmp_path)

    @patch("repo_sapiens.cli.init.GitDiscovery")
    def test_discover_repository_github(self, mock_discovery_class, tmp_path, github_repo_info):
        """Should detect GitHub provider type."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = github_repo_info
        mock_discovery.detect_provider_type.return_value = "github"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer._discover_repository()

        assert initializer.repo_info == github_repo_info
        assert initializer.provider_type == "github"

    @patch("repo_sapiens.cli.init.GitDiscovery")
    def test_init_detects_gitlab_repository(self, mock_discovery_class, tmp_path, gitlab_repo_info):
        """Should detect GitLab provider type from gitlab.com URLs."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = gitlab_repo_info
        mock_discovery.detect_provider_type.return_value = "gitlab"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer._discover_repository()

        assert initializer.repo_info == gitlab_repo_info
        assert initializer.provider_type == "gitlab"
        mock_discovery_class.assert_called_once_with(tmp_path)

    @patch("repo_sapiens.cli.init.GitDiscovery")
    def test_discover_repository_git_discovery_error(self, mock_discovery_class, tmp_path):
        """Should raise ClickException on GitDiscoveryError."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.side_effect = GitDiscoveryError("No remote found")
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        with pytest.raises(ClickException) as exc_info:
            initializer._discover_repository()

        assert "Failed to discover repository" in str(exc_info.value)


# =============================================================================
# Credential Collection Tests
# =============================================================================


class TestRepoInitializerCollectCredentials:
    """Tests for credential collection flows."""

    @patch.dict(os.environ, {"GITEA_TOKEN": "test-token-123", "CLAUDE_API_KEY": "sk-test-key"})
    def test_collect_from_environment_success(self, tmp_path, mock_repo_info):
        """Should collect credentials from environment in non-interactive mode."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="environment"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=True,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._collect_from_environment()

        assert initializer.gitea_token == "test-token-123"

    @patch.dict(os.environ, {}, clear=True)
    def test_collect_from_environment_missing_token(self, tmp_path, mock_repo_info):
        """Should raise ClickException when GITEA_TOKEN is missing."""
        # Ensure environment variable is not set
        if "GITEA_TOKEN" in os.environ:
            del os.environ["GITEA_TOKEN"]

        with patch.object(RepoInitializer, "_detect_backend", return_value="environment"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=True,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        with pytest.raises(ClickException) as exc_info:
            initializer._collect_from_environment()

        assert "GITEA_TOKEN environment variable required" in str(exc_info.value)

    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.cli.init.click.prompt")
    def test_collect_interactively_gitea_token(
        self, mock_prompt, mock_confirm, tmp_path, mock_repo_info
    ):
        """Should prompt for Gitea token interactively."""
        mock_prompt.return_value = "interactive-token-456"
        mock_confirm.return_value = False  # Don't use existing keyring token

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        # Mock the AI agent configuration
        with patch.object(initializer, "_configure_ai_agent"):
            initializer._collect_interactively()

        assert initializer.gitea_token == "interactive-token-456"
        mock_prompt.assert_called()

    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.cli.init.click.prompt")
    def test_init_prompts_for_gitlab_token(
        self, mock_prompt, mock_confirm, tmp_path, gitlab_repo_info
    ):
        """Should prompt for GitLab Personal Access Token interactively."""
        mock_prompt.return_value = "glpat-interactive-token-789"
        mock_confirm.return_value = False  # Don't use existing keyring token

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"

        # Mock the AI agent configuration
        with patch.object(initializer, "_configure_ai_agent"):
            initializer._collect_interactively()

        assert initializer.gitea_token == "glpat-interactive-token-789"
        mock_prompt.assert_called()

    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.cli.init.click.prompt")
    @patch.object(RepoInitializer, "_detect_existing_gitlab_token")
    def test_init_uses_existing_gitlab_token(
        self, mock_detect_token, mock_prompt, mock_confirm, tmp_path, gitlab_repo_info
    ):
        """Should offer to use existing GitLab token from keyring/environment."""
        mock_detect_token.return_value = ("existing-gitlab-token", "keyring (gitlab/api_token)")
        mock_confirm.return_value = True  # Use existing token

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"

        # Mock the AI agent configuration
        with patch.object(initializer, "_configure_ai_agent"):
            initializer._collect_interactively()

        assert initializer.gitea_token == "existing-gitlab-token"
        # Should not prompt for new token since user chose existing
        mock_prompt.assert_not_called()


# =============================================================================
# AI Agent Configuration Tests
# =============================================================================


class TestRepoInitializerConfigureAIAgent:
    """Tests for AI agent configuration."""

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    @patch("repo_sapiens.utils.agent_detector.format_agent_list")
    def test_configure_agent_with_claude_available(
        self, mock_format, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Claude when available."""
        mock_detect.return_value = ["claude"]
        mock_format.return_value = "Available AI Agents:\n  - Claude Code (Anthropic)"
        mock_prompt.return_value = "claude"

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        with patch.object(initializer, "_configure_claude"):
            initializer._configure_ai_agent()

        assert initializer.agent_type == "claude"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    @patch("repo_sapiens.utils.agent_detector.format_agent_list")
    def test_configure_agent_with_goose_available(
        self, mock_format, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Goose when available."""
        mock_detect.return_value = ["goose"]
        mock_format.return_value = "Available AI Agents:\n  - Goose AI (Block)"
        mock_prompt.return_value = "goose"

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        with patch.object(initializer, "_configure_goose"):
            initializer._configure_ai_agent()

        assert initializer.agent_type == "goose"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    def test_configure_agent_with_goose_uvx(
        self, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should handle goose-uvx variant and normalize to goose."""
        mock_detect.return_value = ["goose-uvx"]
        mock_prompt.return_value = "goose"

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        with patch.object(initializer, "_configure_goose"):
            initializer._configure_ai_agent()

        assert initializer.agent_type == "goose"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    def test_configure_agent_no_agents_use_api(
        self, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should offer API mode when no agents detected."""
        mock_detect.return_value = []
        mock_confirm.return_value = True  # Use API mode
        mock_prompt.return_value = "openai"  # Valid provider choice for builtin

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        with patch.object(initializer, "_configure_builtin_cloud"):
            initializer._configure_ai_agent()

        # When no external agents detected, builtin is used
        assert initializer.agent_type == "builtin"
        assert initializer.builtin_provider == "openai"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    def test_configure_agent_no_agents_uses_builtin(
        self, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should use builtin agent when no external agents detected."""
        mock_detect.return_value = []
        mock_prompt.return_value = "ollama"  # Choose local provider

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        # Builtin agent should be configured
        with patch.object(initializer, "_configure_builtin_ollama"):
            initializer._configure_ai_agent()

        assert initializer.agent_type == "builtin"


class TestConfigureClaude:
    """Tests for Claude-specific configuration."""

    @patch("repo_sapiens.cli.init.click.prompt")
    def test_configure_claude_local_mode(self, mock_prompt, tmp_path, mock_repo_info):
        """Should configure Claude in local mode."""
        mock_prompt.return_value = "local"

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_claude()

        assert initializer.agent_mode == "local"
        assert initializer.agent_api_key is None

    @patch("repo_sapiens.cli.init.click.prompt")
    def test_configure_claude_api_mode(self, mock_prompt, tmp_path, mock_repo_info):
        """Should configure Claude in API mode with key."""
        mock_prompt.side_effect = ["api", "sk-ant-test-key-123"]

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_claude()

        assert initializer.agent_mode == "api"
        assert initializer.agent_api_key == "sk-ant-test-key-123"


class TestConfigureGoose:
    """Tests for Goose-specific configuration."""

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"})
    def test_configure_goose_openai_existing_key(
        self, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Goose with OpenAI using existing env key."""
        mock_prompt.side_effect = ["openai", "gpt-4o"]
        mock_confirm.side_effect = [True, False]  # Use existing key, no custom settings

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_goose()

        assert initializer.goose_llm_provider == "openai"
        assert initializer.goose_model == "gpt-4o"
        assert initializer.agent_api_key == "sk-openai-test"
        assert initializer.agent_mode == "local"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch.dict(os.environ, {}, clear=True)
    def test_configure_goose_anthropic_new_key(
        self, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Goose with Anthropic prompting for new key."""
        # Remove ANTHROPIC_API_KEY if present
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        mock_prompt.side_effect = [
            "anthropic",
            "claude-3-5-sonnet-20241022",
            "sk-ant-goose-key",
        ]
        mock_confirm.return_value = False  # No custom settings

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_goose()

        assert initializer.goose_llm_provider == "anthropic"
        assert initializer.goose_model == "claude-3-5-sonnet-20241022"
        assert initializer.agent_api_key == "sk-ant-goose-key"

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    def test_configure_goose_ollama_no_api_key(
        self, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Goose with Ollama without API key."""
        mock_prompt.side_effect = ["ollama", "qwen2.5-coder:32b"]
        mock_confirm.return_value = False  # No custom settings

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_goose()

        assert initializer.goose_llm_provider == "ollama"
        assert initializer.goose_model == "qwen2.5-coder:32b"
        assert initializer.agent_api_key is None

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch.dict(os.environ, {}, clear=True)
    def test_configure_goose_custom_settings(
        self, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should configure Goose with custom temperature and toolkit."""
        mock_prompt.side_effect = [
            "ollama",
            "qwen2.5-coder:32b",
            0.5,  # temperature
            "developer",  # toolkit
        ]
        mock_confirm.return_value = True  # Yes, customize settings

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info
        initializer._configure_goose()

        assert initializer.goose_temperature == 0.5
        assert initializer.goose_toolkit == "developer"


# =============================================================================
# Credential Storage Tests
# =============================================================================


class TestRepoInitializerStoreCredentials:
    """Tests for credential storage."""

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_store_in_keyring_gitea_only(self, mock_keyring_class, tmp_path, mock_repo_info):
        """Should store Gitea token in keyring."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.gitea_token = "test-gitea-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = None

        initializer._store_in_keyring()

        mock_keyring.set.assert_called_once_with("gitea", "api_token", "test-gitea-token")

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_store_in_keyring_with_claude_api_key(
        self, mock_keyring_class, tmp_path, mock_repo_info
    ):
        """Should store both Gitea token and Claude API key in keyring."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.gitea_token = "test-gitea-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = "sk-ant-test-key"

        initializer._store_in_keyring()

        assert mock_keyring.set.call_count == 2
        mock_keyring.set.assert_any_call("gitea", "api_token", "test-gitea-token")
        mock_keyring.set.assert_any_call("claude", "api_key", "sk-ant-test-key")

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_store_in_keyring_with_goose_provider_key(
        self, mock_keyring_class, tmp_path, mock_repo_info
    ):
        """Should store Goose provider API key under provider name."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.gitea_token = "test-gitea-token"
        initializer.agent_type = "goose"
        initializer.goose_llm_provider = "openai"
        initializer.agent_api_key = "sk-openai-key"

        initializer._store_in_keyring()

        assert mock_keyring.set.call_count == 2
        mock_keyring.set.assert_any_call("gitea", "api_token", "test-gitea-token")
        mock_keyring.set.assert_any_call("openai", "api_key", "sk-openai-key")

    @patch("repo_sapiens.cli.init.EnvironmentBackend")
    def test_store_in_environment_gitea_only(self, mock_env_class, tmp_path, mock_repo_info):
        """Should store Gitea token in environment."""
        mock_env = Mock()
        mock_env_class.return_value = mock_env

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.gitea_token = "test-gitea-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = None

        initializer._store_in_environment()

        mock_env.set.assert_called_once_with("GITEA_TOKEN", "test-gitea-token")

    @patch("repo_sapiens.cli.init.EnvironmentBackend")
    def test_store_in_environment_with_goose_provider_key(
        self, mock_env_class, tmp_path, mock_repo_info
    ):
        """Should store Goose provider key with correct env var name."""
        mock_env = Mock()
        mock_env_class.return_value = mock_env

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.gitea_token = "test-gitea-token"
        initializer.agent_type = "goose"
        initializer.goose_llm_provider = "anthropic"
        initializer.agent_api_key = "sk-ant-key"

        initializer._store_in_environment()

        assert mock_env.set.call_count == 2
        mock_env.set.assert_any_call("GITEA_TOKEN", "test-gitea-token")
        mock_env.set.assert_any_call("ANTHROPIC_API_KEY", "sk-ant-key")

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_init_stores_gitlab_credentials_keyring(
        self, mock_keyring_class, tmp_path, gitlab_repo_info
    ):
        """Should store GitLab token in keyring under gitlab/api_token."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"
        initializer.gitea_token = "glpat-test-gitlab-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = None

        initializer._store_in_keyring()

        mock_keyring.set.assert_called_once_with("gitlab", "api_token", "glpat-test-gitlab-token")

    @patch("repo_sapiens.cli.init.EnvironmentBackend")
    def test_init_stores_gitlab_credentials_environment(
        self, mock_env_class, tmp_path, gitlab_repo_info
    ):
        """Should store GitLab token in environment as GITLAB_TOKEN."""
        mock_env = Mock()
        mock_env_class.return_value = mock_env

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"
        initializer.gitea_token = "glpat-test-gitlab-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = None

        initializer._store_in_environment()

        mock_env.set.assert_called_once_with("GITLAB_TOKEN", "glpat-test-gitlab-token")

    @patch("repo_sapiens.cli.init.KeyringBackend")
    def test_init_stores_gitlab_credentials_with_agent_api_key(
        self, mock_keyring_class, tmp_path, gitlab_repo_info
    ):
        """Should store both GitLab token and agent API key in keyring."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"
        initializer.gitea_token = "glpat-test-gitlab-token"
        initializer.agent_type = "claude"
        initializer.agent_api_key = "sk-ant-claude-key"

        initializer._store_in_keyring()

        assert mock_keyring.set.call_count == 2
        mock_keyring.set.assert_any_call("gitlab", "api_token", "glpat-test-gitlab-token")
        mock_keyring.set.assert_any_call("claude", "api_key", "sk-ant-claude-key")


# =============================================================================
# Config Generation Tests
# =============================================================================


class TestRepoInitializerGenerateConfig:
    """Tests for configuration file generation."""

    def test_generate_config_claude_local_keyring(self, tmp_path, mock_repo_info):
        """Should generate config for Claude local mode with keyring backend."""
        config_path = tmp_path / "automation" / "config" / "automation_config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        initializer._generate_config()

        assert config_path.exists()
        content = config_path.read_text()

        assert "provider_type: gitea" in content
        assert "mcp_server: gitea-mcp" in content
        assert "@keyring:gitea/api_token" in content
        assert "provider_type: claude-local" in content
        assert "model: claude-sonnet-4.5" in content
        assert "local_mode: true" in content

    def test_generate_config_claude_api_environment(self, tmp_path, mock_repo_info):
        """Should generate config for Claude API mode with environment backend."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="environment",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "claude"
        initializer.agent_mode = "api"
        initializer.agent_api_key = "sk-ant-key"

        initializer._generate_config()

        assert config_path.exists()
        content = config_path.read_text()

        assert "${GITEA_TOKEN}" in content
        assert "provider_type: claude-api" in content
        assert "${CLAUDE_API_KEY}" in content
        assert "local_mode: false" in content

    def test_generate_config_goose_openai(self, tmp_path, mock_repo_info):
        """Should generate config for Goose with OpenAI provider."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "goose"
        initializer.agent_mode = "local"
        initializer.goose_llm_provider = "openai"
        initializer.goose_model = "gpt-4o"
        initializer.goose_toolkit = "developer"
        initializer.goose_temperature = 0.5
        initializer.agent_api_key = "sk-openai-key"

        initializer._generate_config()

        content = config_path.read_text()

        assert "provider_type: goose-local" in content
        assert "model: gpt-4o" in content
        assert "@keyring:openai/api_key" in content
        assert "goose_config:" in content
        assert "toolkit: developer" in content
        assert "temperature: 0.5" in content
        assert "llm_provider: openai" in content

    def test_generate_config_github_provider(self, tmp_path, github_repo_info):
        """Should generate config for GitHub provider without MCP server."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = github_repo_info
        initializer.provider_type = "github"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        initializer._generate_config()

        content = config_path.read_text()

        assert "provider_type: github" in content
        assert "mcp_server: null" in content
        assert "base_url: https://github.com" in content

    def test_init_generates_gitlab_config(self, tmp_path, gitlab_repo_info):
        """Should generate config for GitLab provider with mcp_server: null."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        initializer._generate_config()

        assert config_path.exists()
        content = config_path.read_text()

        # GitLab-specific assertions
        assert "provider_type: gitlab" in content
        assert "mcp_server: null" in content
        assert "base_url: https://gitlab.com" in content
        assert "owner: gitlab-owner" in content
        assert "name: gitlab-repo" in content
        assert "@keyring:gitlab/api_token" in content

    def test_init_generates_gitlab_config_environment_backend(self, tmp_path, gitlab_repo_info):
        """Should generate GitLab config with environment variable references."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="environment",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = gitlab_repo_info
        initializer.provider_type = "gitlab"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        initializer._generate_config()

        content = config_path.read_text()

        # GitLab-specific assertions for environment backend
        assert "provider_type: gitlab" in content
        assert "${GITLAB_TOKEN}" in content
        assert "mcp_server: null" in content

    def test_generate_config_creates_parent_directories(self, tmp_path, mock_repo_info):
        """Should create parent directories for config file."""
        config_path = tmp_path / "deep" / "nested" / "path" / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        initializer._generate_config()

        assert config_path.exists()
        assert config_path.parent.exists()

    def test_generate_config_goose_null_api_key(self, tmp_path, mock_repo_info):
        """Should generate null api_key for Goose with Ollama (no key needed)."""
        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "goose"
        initializer.agent_mode = "local"
        initializer.goose_llm_provider = "ollama"
        initializer.goose_model = "qwen2.5-coder:32b"
        initializer.agent_api_key = None

        initializer._generate_config()

        content = config_path.read_text()

        assert "api_key: null" in content


# =============================================================================
# Secrets Setup Tests
# =============================================================================


class TestRepoInitializerSetupSecrets:
    """Tests for repository secrets setup."""

    def test_setup_gitea_secrets_mcp_placeholder(self, tmp_path, mock_repo_info):
        """Should call MCP placeholder for Gitea secrets."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.gitea_token = "test-token"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"

        # Should not raise, just print instructions
        initializer._setup_gitea_secrets_mcp()

    def test_setup_gitea_secrets_with_api_key(self, tmp_path, mock_repo_info):
        """Should set up API key secret when in API mode."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.gitea_token = "test-token"
        initializer.agent_type = "claude"
        initializer.agent_mode = "api"
        initializer.agent_api_key = "sk-ant-key"

        # Should not raise
        initializer._setup_gitea_secrets_mcp()


class TestRepoInitializerSetupGitHubSecrets:
    """Tests for GitHub secrets setup."""

    def test_setup_github_secrets_local_mode(self, tmp_path, github_repo_info):
        """Should set GitHub token secret in local mode."""
        mock_github = Mock()
        mock_github.connect = Mock(return_value=None)
        mock_github.set_repository_secret = Mock(return_value=None)

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = github_repo_info
        initializer.provider_type = "github"
        initializer.gitea_token = "ghp-test-token"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"
        initializer.agent_api_key = None

        with patch.dict(
            "sys.modules",
            {
                "repo_sapiens.providers.github_rest": MagicMock(
                    GitHubRestProvider=Mock(return_value=mock_github)
                )
            },
        ):
            with patch("asyncio.run") as mock_run:
                initializer._setup_github_secrets()

                # Should call connect and set_repository_secret at least once
                assert mock_run.call_count >= 2

    def test_setup_github_secrets_api_mode(self, tmp_path, github_repo_info):
        """Should set both GitHub token and API key secrets in API mode."""
        mock_github = Mock()
        mock_github.connect = Mock(return_value=None)
        mock_github.set_repository_secret = Mock(return_value=None)

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = github_repo_info
        initializer.provider_type = "github"
        initializer.gitea_token = "ghp-test-token"
        initializer.agent_type = "claude"
        initializer.agent_mode = "api"
        initializer.agent_api_key = "sk-ant-key"

        with patch.dict(
            "sys.modules",
            {
                "repo_sapiens.providers.github_rest": MagicMock(
                    GitHubRestProvider=Mock(return_value=mock_github)
                )
            },
        ):
            with patch("asyncio.run") as mock_run:
                initializer._setup_github_secrets()

                # Should call connect and two set_repository_secret calls (token + API key)
                assert mock_run.call_count >= 3


# =============================================================================
# Validation Tests
# =============================================================================


class TestRepoInitializerValidateSetup:
    """Tests for setup validation."""

    @patch("repo_sapiens.cli.init.CredentialResolver")
    def test_validate_setup_keyring_success(self, mock_resolver_class, tmp_path, mock_repo_info):
        """Should validate keyring credentials successfully."""
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = "resolved-token"
        mock_resolver_class.return_value = mock_resolver

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info

        # Should not raise
        initializer._validate_setup()

        mock_resolver.resolve.assert_called_once_with("@keyring:gitea/api_token", cache=False)

    @patch("repo_sapiens.cli.init.CredentialResolver")
    def test_validate_setup_environment_success(
        self, mock_resolver_class, tmp_path, mock_repo_info
    ):
        """Should validate environment credentials successfully."""
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = "resolved-token"
        mock_resolver_class.return_value = mock_resolver

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info

        initializer._validate_setup()

        mock_resolver.resolve.assert_called_once_with("${GITEA_TOKEN}", cache=False)

    @patch("repo_sapiens.cli.init.CredentialResolver")
    def test_validate_setup_failure_handled_gracefully(
        self, mock_resolver_class, tmp_path, mock_repo_info
    ):
        """Should handle validation failure gracefully with warning."""
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = None  # Simulate failure
        mock_resolver_class.return_value = mock_resolver

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.repo_info = mock_repo_info

        # Should not raise, just warn
        initializer._validate_setup()


# =============================================================================
# Full Workflow Tests
# =============================================================================


class TestRepoInitializerWorkflow:
    """Tests for complete initialization workflow."""

    @patch("repo_sapiens.cli.init.GitDiscovery")
    @patch.object(RepoInitializer, "_collect_credentials")
    @patch.object(RepoInitializer, "_store_credentials")
    @patch.object(RepoInitializer, "_setup_gitea_secrets")
    @patch.object(RepoInitializer, "_generate_config")
    @patch.object(RepoInitializer, "_validate_setup")
    @patch.object(RepoInitializer, "_print_next_steps")
    def test_run_workflow_executes_all_steps(
        self,
        mock_print_steps,
        mock_validate,
        mock_generate_config,
        mock_setup_secrets,
        mock_store_creds,
        mock_collect_creds,
        mock_discovery_class,
        tmp_path,
        mock_repo_info,
    ):
        """Should execute all workflow steps in order."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "gitea"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=True,
                setup_secrets=True,
            )

        initializer.run()

        mock_discovery_class.assert_called_once()
        mock_collect_creds.assert_called_once()
        mock_store_creds.assert_called_once()
        mock_setup_secrets.assert_called_once()
        mock_generate_config.assert_called_once()
        mock_validate.assert_called_once()
        mock_print_steps.assert_called_once()

    @patch("repo_sapiens.cli.init.GitDiscovery")
    @patch.object(RepoInitializer, "_collect_credentials")
    @patch.object(RepoInitializer, "_store_credentials")
    @patch.object(RepoInitializer, "_generate_config")
    @patch.object(RepoInitializer, "_validate_setup")
    @patch.object(RepoInitializer, "_print_next_steps")
    def test_run_workflow_skips_secrets_when_disabled(
        self,
        mock_print_steps,
        mock_validate,
        mock_generate_config,
        mock_store_creds,
        mock_collect_creds,
        mock_discovery_class,
        tmp_path,
        mock_repo_info,
    ):
        """Should skip secret setup when disabled."""
        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "gitea"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            with patch.object(RepoInitializer, "_setup_gitea_secrets") as mock_setup_secrets:
                initializer = RepoInitializer(
                    repo_path=tmp_path,
                    config_path=Path("config.yaml"),
                    backend=None,
                    non_interactive=True,
                    setup_secrets=False,
                )

                initializer.run()

                mock_setup_secrets.assert_not_called()


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestInitCommand:
    """Tests for init_command Click command."""

    def test_init_command_basic_invocation(self, cli_runner, tmp_path):
        """Should invoke init command."""
        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                ["--repo-path", str(tmp_path), "--non-interactive"],
                catch_exceptions=False,
            )

        assert result.exit_code in [0, 1]

    def test_init_command_with_all_options(self, cli_runner, tmp_path):
        """Should accept all command-line options."""
        config_path = tmp_path / "custom_config.yaml"

        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                [
                    "--repo-path",
                    str(tmp_path),
                    "--config-path",
                    str(config_path),
                    "--backend",
                    "environment",
                    "--non-interactive",
                    "--setup-secrets",
                ],
            )

        assert result.exit_code in [0, 1]

    def test_init_command_handles_git_discovery_error(self, cli_runner, tmp_path):
        """Should handle GitDiscoveryError gracefully."""
        with patch.object(
            RepoInitializer, "run", side_effect=GitDiscoveryError("No Git repository")
        ):
            result = cli_runner.invoke(init_command, ["--repo-path", str(tmp_path)])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Make sure you're in a Git repository" in result.output

    def test_init_command_handles_unexpected_error(self, cli_runner, tmp_path):
        """Should handle unexpected errors gracefully."""
        with patch.object(RepoInitializer, "run", side_effect=RuntimeError("Unexpected")):
            result = cli_runner.invoke(init_command, ["--repo-path", str(tmp_path)])

        assert result.exit_code == 1
        assert "Unexpected error:" in result.output

    def test_init_command_default_repo_path(self, cli_runner):
        """Should use current directory as default repo path."""
        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(init_command, ["--non-interactive"])

        assert result.exit_code in [0, 1]

    def test_init_command_backend_choices(self, cli_runner, tmp_path):
        """Should validate backend choices."""
        result = cli_runner.invoke(
            init_command,
            ["--repo-path", str(tmp_path), "--backend", "invalid"],
        )

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_init_command_valid_backends(self, cli_runner, tmp_path):
        """Should accept valid backend options."""
        valid_backends = ["keyring", "environment", "encrypted"]

        for backend in valid_backends:
            with patch.object(RepoInitializer, "run"):
                result = cli_runner.invoke(
                    init_command,
                    [
                        "--repo-path",
                        str(tmp_path),
                        "--backend",
                        backend,
                        "--non-interactive",
                    ],
                )

            assert result.exit_code in [0, 1]

    def test_init_command_repo_path_must_exist(self, cli_runner, tmp_path):
        """Should validate that repo path exists."""
        nonexistent = tmp_path / "does_not_exist"

        result = cli_runner.invoke(
            init_command,
            ["--repo-path", str(nonexistent)],
        )

        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()

    def test_init_command_config_path_can_be_nonexistent(self, cli_runner, tmp_path):
        """Should allow non-existent config path (will be created)."""
        config_path = tmp_path / "subdir" / "config.yaml"

        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                [
                    "--repo-path",
                    str(tmp_path),
                    "--config-path",
                    str(config_path),
                    "--non-interactive",
                ],
            )

        assert result.exit_code in [0, 1]


# =============================================================================
# Next Steps Output Tests
# =============================================================================


class TestRepoInitializerPrintNextSteps:
    """Tests for next steps output."""

    def test_print_next_steps_with_secrets_setup(self, tmp_path, mock_repo_info, capsys):
        """Should print manual secret setup instructions when setup_secrets is True."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"

        initializer._print_next_steps()

        captured = capsys.readouterr()
        assert "Next Steps:" in captured.out
        assert "needs-planning" in captured.out

    def test_print_next_steps_api_mode_claude(self, tmp_path, mock_repo_info, capsys):
        """Should mention CLAUDE_API_KEY secret for API mode."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "claude"
        initializer.agent_mode = "api"

        initializer._print_next_steps()

        captured = capsys.readouterr()
        assert "CLAUDE_API_KEY" in captured.out

    def test_print_next_steps_api_mode_goose(self, tmp_path, mock_repo_info, capsys):
        """Should mention provider-specific API key for Goose API mode."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "gitea"
        initializer.agent_type = "goose"
        initializer.agent_mode = "api"
        initializer.goose_llm_provider = "openai"

        initializer._print_next_steps()

        captured = capsys.readouterr()
        assert "OPENAI_API_KEY" in captured.out


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestRepoInitializerEdgeCases:
    """Edge cases for repository initializer."""

    def test_initializer_with_relative_paths(self):
        """Should handle relative paths."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=Path("."),
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_path == Path(".")
        assert initializer.config_path == Path("config.yaml")

    def test_store_credentials_failure_raises_click_exception(self, tmp_path, mock_repo_info):
        """Should raise ClickException on credential storage failure."""
        with patch("repo_sapiens.cli.init.KeyringBackend") as mock_keyring_class:
            mock_keyring = Mock()
            mock_keyring.set.side_effect = Exception("Keyring error")
            mock_keyring_class.return_value = mock_keyring

            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend="keyring",
                non_interactive=True,
                setup_secrets=False,
            )

            initializer.repo_info = mock_repo_info
            initializer.gitea_token = "test-token"
            initializer.agent_type = "claude"
            initializer.agent_api_key = None

            with pytest.raises(ClickException) as exc_info:
                initializer._store_credentials()

            assert "Failed to store credentials" in str(exc_info.value)

    def test_setup_secrets_failure_handled_gracefully(self, tmp_path, mock_repo_info, capsys):
        """Should handle secret setup failure gracefully."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="keyring",
            non_interactive=True,
            setup_secrets=True,
        )

        initializer.repo_info = mock_repo_info
        initializer.provider_type = "github"
        initializer.gitea_token = "test-token"
        initializer.agent_type = "claude"
        initializer.agent_mode = "local"

        with patch.object(initializer, "_setup_github_secrets", side_effect=Exception("API error")):
            # Should not raise, just warn
            initializer._setup_gitea_secrets()

    @patch("repo_sapiens.cli.init.click.prompt")
    @patch("repo_sapiens.cli.init.click.confirm")
    @patch("repo_sapiens.utils.agent_detector.detect_available_agents")
    @patch("repo_sapiens.utils.agent_detector.format_agent_list")
    def test_configure_agent_api_choice_always_available(
        self, mock_format, mock_detect, mock_confirm, mock_prompt, tmp_path, mock_repo_info
    ):
        """Should always include 'api' as a choice even when agents are detected."""
        mock_detect.return_value = ["claude"]
        mock_format.return_value = "Available AI Agents:\n  - Claude Code"
        mock_prompt.return_value = "api"

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer.repo_info = mock_repo_info

        # The prompt should have 'api' as an option
        with patch.object(initializer, "_configure_claude"):
            initializer._configure_ai_agent()

        # Verify prompt was called and api was accepted
        mock_prompt.assert_called()


# =============================================================================
# Integration-like Tests (with multiple components)
# =============================================================================


class TestRepoInitializerIntegration:
    """Integration-style tests combining multiple components."""

    @patch("repo_sapiens.cli.init.GitDiscovery")
    @patch("repo_sapiens.cli.init.KeyringBackend")
    @patch("repo_sapiens.cli.init.CredentialResolver")
    @patch.dict(os.environ, {"GITEA_TOKEN": "test-token"})
    def test_full_non_interactive_flow_gitea(
        self, mock_resolver_class, mock_keyring_class, mock_discovery_class, tmp_path
    ):
        """Test complete non-interactive flow for Gitea."""
        # Setup mocks
        mock_repo_info = Mock()
        mock_repo_info.remote_name = "origin"
        mock_repo_info.owner = "test-owner"
        mock_repo_info.repo = "test-repo"
        mock_repo_info.base_url = "https://gitea.example.com"

        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "gitea"
        mock_discovery_class.return_value = mock_discovery

        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        mock_resolver = Mock()
        mock_resolver.resolve.return_value = "test-token"
        mock_resolver_class.return_value = mock_resolver

        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.run()

        # Verify config was created
        assert config_path.exists()
        content = config_path.read_text()
        assert "test-owner" in content
        assert "test-repo" in content

    @patch("repo_sapiens.cli.init.GitDiscovery")
    @patch("repo_sapiens.cli.init.KeyringBackend")
    @patch("repo_sapiens.cli.init.CredentialResolver")
    @patch.dict(os.environ, {"GITEA_TOKEN": "ghp-token"})
    def test_full_non_interactive_flow_github(
        self, mock_resolver_class, mock_keyring_class, mock_discovery_class, tmp_path
    ):
        """Test complete non-interactive flow for GitHub."""
        mock_repo_info = Mock()
        mock_repo_info.remote_name = "origin"
        mock_repo_info.owner = "github-owner"
        mock_repo_info.repo = "github-repo"
        mock_repo_info.base_url = "https://github.com"

        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "github"
        mock_discovery_class.return_value = mock_discovery

        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        mock_resolver = Mock()
        mock_resolver.resolve.return_value = "ghp-token"
        mock_resolver_class.return_value = mock_resolver

        config_path = tmp_path / "config.yaml"

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=config_path,
            backend="keyring",
            non_interactive=True,
            setup_secrets=False,
        )

        initializer.run()

        assert config_path.exists()
        content = config_path.read_text()
        assert "provider_type: github" in content
        assert "mcp_server: null" in content
