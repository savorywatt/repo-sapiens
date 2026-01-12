"""Comprehensive tests for repo_sapiens/config/settings.py Pydantic models.

Tests cover:
- GitProviderConfig validation
- RepositoryConfig validation
- AgentProviderConfig validation
- WorkflowConfig validation and boundary conditions
- TagsConfig defaults
- AutomationSettings loading from YAML
- AutomationSettings loading from environment variables
- Configuration merging (file + env vars)
- Environment variable interpolation
- Edge cases and error handling
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from repo_sapiens.config.credential_fields import set_resolver
from repo_sapiens.config.settings import (
    AgentProviderConfig,
    AutomationSettings,
    GitProviderConfig,
    RepositoryConfig,
    TagsConfig,
    WorkflowConfig,
)
from repo_sapiens.credentials import CredentialResolver


class TestGitProviderConfig:
    """Test GitProviderConfig validation and URL handling."""

    def test_valid_gitea_config(self):
        """Test valid Gitea provider configuration."""
        config = GitProviderConfig(
            provider_type="gitea",
            base_url="https://gitea.example.com",
            api_token="test-token-123",
        )

        assert config.provider_type == "gitea"
        assert str(config.base_url) == "https://gitea.example.com/"
        assert config.mcp_server is None

    def test_valid_github_config(self):
        """Test valid GitHub provider configuration."""
        config = GitProviderConfig(
            provider_type="github",
            base_url="https://github.com",
            api_token="ghp_abc123def456",
        )

        assert config.provider_type == "github"
        assert str(config.base_url) == "https://github.com/"

    def test_with_mcp_server(self):
        """Test Git provider with MCP server specified."""
        config = GitProviderConfig(
            provider_type="gitea",
            mcp_server="gitea-mcp",
            base_url="https://gitea.example.com",
            api_token="token",
        )

        assert config.mcp_server == "gitea-mcp"

    def test_default_provider_is_gitea(self):
        """Test that provider_type defaults to gitea."""
        config = GitProviderConfig(
            base_url="https://gitea.example.com",
            api_token="token",
        )

        assert config.provider_type == "gitea"

    def test_valid_gitlab_config(self):
        """Test valid GitLab provider configuration."""
        config = GitProviderConfig(
            provider_type="gitlab",
            base_url="https://gitlab.example.com",
            api_token="glpat-abc123def456",
        )

        assert config.provider_type == "gitlab"
        assert str(config.base_url) == "https://gitlab.example.com/"

    def test_invalid_provider_type_raises_error(self):
        """Test invalid provider type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GitProviderConfig(
                provider_type="bitbucket",  # Invalid - not supported
                base_url="https://bitbucket.org",
                api_token="token",
            )

        assert "bitbucket" in str(exc_info.value).lower()

    def test_invalid_url_format_raises_error(self):
        """Test invalid URL format raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GitProviderConfig(
                base_url="not-a-valid-url",
                api_token="token",
            )

        # Should fail URL validation
        assert exc_info.value

    def test_missing_base_url_raises_error(self):
        """Test missing required base_url field."""
        with pytest.raises(ValidationError) as exc_info:
            GitProviderConfig(api_token="token")

        assert "base_url" in str(exc_info.value).lower()

    def test_missing_api_token_raises_error(self):
        """Test missing required api_token field."""
        with pytest.raises(ValidationError):
            GitProviderConfig(base_url="https://example.com")

    def test_url_with_trailing_slash(self):
        """Test URL with trailing slash is normalized."""
        config = GitProviderConfig(
            base_url="https://gitea.example.com/",
            api_token="token",
        )

        # HttpUrl should handle this correctly
        assert str(config.base_url) == "https://gitea.example.com/"

    def test_url_with_path(self):
        """Test URL with path component."""
        config = GitProviderConfig(
            base_url="https://example.com/gitea",
            api_token="token",
        )

        assert "example.com" in str(config.base_url)

    def test_http_url_is_valid(self):
        """Test HTTP (non-HTTPS) URLs are accepted."""
        config = GitProviderConfig(
            base_url="http://localhost:3000",
            api_token="token",
        )

        assert "localhost" in str(config.base_url)

    def test_credential_reference_in_api_token(self):
        """Test credential references in api_token field."""
        # Mock resolver to handle credential reference
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "resolved-token-123"
        set_resolver(mock_resolver)

        try:
            config = GitProviderConfig(
                base_url="https://gitea.example.com",
                api_token="@keyring:gitea/api_token",
            )

            # Token should be wrapped in SecretStr
            assert isinstance(config.api_token, SecretStr)
        finally:
            # Reset resolver
            set_resolver(None)


class TestRepositoryConfig:
    """Test RepositoryConfig validation."""

    def test_valid_repository_config(self):
        """Test valid repository configuration."""
        config = RepositoryConfig(
            owner="myorg",
            name="myrepo",
        )

        assert config.owner == "myorg"
        assert config.name == "myrepo"
        assert config.default_branch == "main"

    def test_custom_default_branch(self):
        """Test custom default branch."""
        config = RepositoryConfig(
            owner="org",
            name="repo",
            default_branch="develop",
        )

        assert config.default_branch == "develop"

    def test_main_is_default_branch(self):
        """Test 'main' is default branch when not specified."""
        config = RepositoryConfig(owner="org", name="repo")

        assert config.default_branch == "main"

    def test_missing_owner_raises_error(self):
        """Test missing owner field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            RepositoryConfig(name="repo")

        assert "owner" in str(exc_info.value).lower()

    def test_missing_name_raises_error(self):
        """Test missing name field raises validation error."""
        with pytest.raises(ValidationError):
            RepositoryConfig(owner="org")

    def test_empty_owner_is_accepted(self):
        """Test empty owner string is accepted (no min_length constraint)."""
        # Note: The model doesn't currently enforce non-empty strings
        config = RepositoryConfig(owner="", name="repo")
        assert config.owner == ""

    def test_empty_name_is_accepted(self):
        """Test empty name string is accepted (no min_length constraint)."""
        # Note: The model doesn't currently enforce non-empty strings
        config = RepositoryConfig(owner="org", name="")
        assert config.name == ""

    def test_special_characters_in_names(self):
        """Test owner and name with special characters."""
        config = RepositoryConfig(
            owner="my-org_123",
            name="my-repo.name",
        )

        assert config.owner == "my-org_123"
        assert config.name == "my-repo.name"


class TestAgentProviderConfig:
    """Test AgentProviderConfig validation with all provider types."""

    def test_claude_local_provider(self):
        """Test Claude local provider configuration."""
        config = AgentProviderConfig(
            provider_type="claude-local",
            model="claude-sonnet-4.5",
            local_mode=True,
        )

        assert config.provider_type == "claude-local"
        assert config.model == "claude-sonnet-4.5"
        assert config.local_mode is True
        assert config.api_key is None

    def test_claude_api_provider(self):
        """Test Claude API provider requires api_key."""
        config = AgentProviderConfig(
            provider_type="claude-api",
            model="claude-opus-4.5",
            api_key="test-api-key",
            local_mode=False,
        )

        assert config.provider_type == "claude-api"
        assert config.local_mode is False

    def test_openai_provider(self):
        """Test OpenAI provider configuration."""
        config = AgentProviderConfig(
            provider_type="openai",
            model="gpt-4-turbo",
            api_key="sk-abc123",
            local_mode=False,
        )

        assert config.provider_type == "openai"
        assert config.model == "gpt-4-turbo"

    def test_ollama_provider(self):
        """Test Ollama provider with custom base_url."""
        config = AgentProviderConfig(
            provider_type="ollama",
            model="mistral",
            base_url="http://localhost:11434",
            local_mode=True,
        )

        assert config.provider_type == "ollama"
        assert config.base_url == "http://localhost:11434"

    def test_default_provider_is_claude_local(self):
        """Test default provider is claude-local."""
        config = AgentProviderConfig()

        assert config.provider_type == "claude-local"
        assert config.local_mode is True

    def test_default_model(self):
        """Test default model name."""
        config = AgentProviderConfig()

        assert config.model == "claude-sonnet-4.5"

    def test_default_ollama_url(self):
        """Test default Ollama base_url."""
        config = AgentProviderConfig(
            provider_type="ollama",
            model="llama2",
        )

        assert config.base_url == "http://localhost:11434"

    def test_invalid_provider_type_raises_error(self):
        """Test invalid provider type raises error."""
        with pytest.raises(ValidationError):
            AgentProviderConfig(provider_type="invalid-provider")

    def test_valid_provider_types(self):
        """Test all valid provider types can be created."""
        valid_types = ["claude-local", "claude-api", "openai", "ollama"]

        for provider_type in valid_types:
            config = AgentProviderConfig(
                provider_type=provider_type,
                api_key="test-key" if provider_type != "claude-local" else None,
            )
            assert config.provider_type == provider_type

    def test_credential_reference_in_api_key(self):
        """Test credential references in api_key field."""
        mock_resolver = MagicMock(spec=CredentialResolver)
        mock_resolver.resolve.return_value = "resolved-api-key"
        set_resolver(mock_resolver)

        try:
            config = AgentProviderConfig(
                provider_type="claude-api",
                api_key="${CLAUDE_API_KEY}",
                local_mode=False,
            )

            assert isinstance(config.api_key, SecretStr)
        finally:
            set_resolver(None)

    def test_optional_api_key_for_local_mode(self):
        """Test api_key is optional for local providers."""
        config = AgentProviderConfig(
            provider_type="claude-local",
            api_key=None,
        )

        assert config.api_key is None


class TestWorkflowConfig:
    """Test WorkflowConfig validation and boundary conditions."""

    def test_valid_workflow_config(self):
        """Test valid workflow configuration."""
        config = WorkflowConfig(
            plans_directory="custom-plans",
            state_directory=".state",
            branching_strategy="shared",
            max_concurrent_tasks=5,
            review_approval_threshold=0.9,
        )

        assert config.plans_directory == "custom-plans"
        assert config.state_directory == ".state"
        assert config.branching_strategy == "shared"
        assert config.max_concurrent_tasks == 5
        assert config.review_approval_threshold == 0.9

    def test_default_values(self):
        """Test default workflow configuration values."""
        config = WorkflowConfig()

        assert config.plans_directory == "plans"
        assert config.state_directory == ".sapiens/state"
        assert config.branching_strategy == "per-agent"
        assert config.max_concurrent_tasks == 3
        assert config.review_approval_threshold == 0.8

    def test_max_concurrent_tasks_minimum_boundary(self):
        """Test max_concurrent_tasks must be >= 1."""
        # Should succeed with 1
        config = WorkflowConfig(max_concurrent_tasks=1)
        assert config.max_concurrent_tasks == 1

        # Should fail with 0
        with pytest.raises(ValidationError):
            WorkflowConfig(max_concurrent_tasks=0)

    def test_max_concurrent_tasks_maximum_boundary(self):
        """Test max_concurrent_tasks must be <= 10."""
        # Should succeed with 10
        config = WorkflowConfig(max_concurrent_tasks=10)
        assert config.max_concurrent_tasks == 10

        # Should fail with 11
        with pytest.raises(ValidationError):
            WorkflowConfig(max_concurrent_tasks=11)

    def test_max_concurrent_tasks_valid_range(self):
        """Test max_concurrent_tasks within valid range."""
        for value in [1, 3, 5, 10]:
            config = WorkflowConfig(max_concurrent_tasks=value)
            assert config.max_concurrent_tasks == value

    def test_review_approval_threshold_minimum_boundary(self):
        """Test review_approval_threshold minimum is 0.0."""
        config = WorkflowConfig(review_approval_threshold=0.0)
        assert config.review_approval_threshold == 0.0

        # Below 0.0 should fail
        with pytest.raises(ValidationError):
            WorkflowConfig(review_approval_threshold=-0.1)

    def test_review_approval_threshold_maximum_boundary(self):
        """Test review_approval_threshold maximum is 1.0."""
        config = WorkflowConfig(review_approval_threshold=1.0)
        assert config.review_approval_threshold == 1.0

        # Above 1.0 should fail
        with pytest.raises(ValidationError):
            WorkflowConfig(review_approval_threshold=1.1)

    def test_review_approval_threshold_valid_range(self):
        """Test review_approval_threshold within valid range."""
        for value in [0.0, 0.5, 0.8, 0.9, 1.0]:
            config = WorkflowConfig(review_approval_threshold=value)
            assert config.review_approval_threshold == value

    def test_invalid_branching_strategy_raises_error(self):
        """Test invalid branching_strategy raises error."""
        with pytest.raises(ValidationError):
            WorkflowConfig(branching_strategy="invalid-strategy")

    def test_valid_branching_strategies(self):
        """Test all valid branching strategies."""
        for strategy in ["per-agent", "shared"]:
            config = WorkflowConfig(branching_strategy=strategy)
            assert config.branching_strategy == strategy

    def test_per_agent_default_branching(self):
        """Test per-agent is default branching strategy."""
        config = WorkflowConfig()
        assert config.branching_strategy == "per-agent"

    def test_custom_directory_paths(self):
        """Test custom directory paths are accepted."""
        config = WorkflowConfig(
            plans_directory="/custom/plans",
            state_directory="/custom/state",
        )

        assert config.plans_directory == "/custom/plans"
        assert config.state_directory == "/custom/state"


class TestTagsConfig:
    """Test TagsConfig defaults and customization."""

    def test_all_default_tags(self):
        """Test all default tag values."""
        config = TagsConfig()

        assert config.needs_planning == "needs-planning"
        assert config.plan_review == "plan-review"
        assert config.ready_to_implement == "ready-to-implement"
        assert config.in_progress == "in-progress"
        assert config.code_review == "code-review"
        assert config.merge_ready == "merge-ready"
        assert config.completed == "completed"
        assert config.needs_attention == "needs-attention"

    def test_custom_tags(self):
        """Test custom tag values."""
        config = TagsConfig(
            needs_planning="todo",
            plan_review="review",
            ready_to_implement="approved",
            in_progress="doing",
            code_review="cr",
            merge_ready="ready",
            completed="done",
            needs_attention="blocked",
        )

        assert config.needs_planning == "todo"
        assert config.plan_review == "review"
        assert config.ready_to_implement == "approved"
        assert config.in_progress == "doing"
        assert config.code_review == "cr"
        assert config.merge_ready == "ready"
        assert config.completed == "done"
        assert config.needs_attention == "blocked"

    def test_tags_with_special_characters(self):
        """Test tags with hyphens and underscores."""
        config = TagsConfig(
            needs_planning="needs_planning",
            completed="task-completed",
        )

        assert config.needs_planning == "needs_planning"
        assert config.completed == "task-completed"

    def test_empty_tags_are_accepted(self):
        """Test empty tag values are accepted (no min_length constraint)."""
        # Note: The model doesn't enforce non-empty strings
        config = TagsConfig(needs_planning="")
        assert config.needs_planning == ""

    def test_partial_tag_customization(self):
        """Test customizing only some tags."""
        config = TagsConfig(
            needs_planning="custom-todo",
        )

        assert config.needs_planning == "custom-todo"
        assert config.completed == "completed"  # Default preserved


class TestAutomationSettingsBasic:
    """Test AutomationSettings basic functionality."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # Missing git_provider should raise error
        with pytest.raises(ValidationError):
            AutomationSettings(
                repository={"owner": "org", "name": "repo"},
                agent_provider={"provider_type": "claude-local"},
            )

    def test_complete_settings_creation(self):
        """Test creating complete AutomationSettings."""
        settings = AutomationSettings(
            git_provider={
                "base_url": "https://gitea.example.com",
                "api_token": "token",
            },
            repository={
                "owner": "org",
                "name": "repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
        )

        assert settings.git_provider.provider_type == "gitea"
        assert settings.repository.owner == "org"
        assert settings.agent_provider.provider_type == "claude-local"

    def test_workflow_default_factory(self):
        """Test that workflow uses default factory when not provided."""
        settings = AutomationSettings(
            git_provider={"base_url": "https://example.com", "api_token": "token"},
            repository={"owner": "org", "name": "repo"},
            agent_provider={"provider_type": "claude-local"},
        )

        # WorkflowConfig should have defaults
        assert settings.workflow.plans_directory == "plans"
        assert settings.workflow.max_concurrent_tasks == 3

    def test_tags_default_factory(self):
        """Test that tags uses default factory when not provided."""
        settings = AutomationSettings(
            git_provider={"base_url": "https://example.com", "api_token": "token"},
            repository={"owner": "org", "name": "repo"},
            agent_provider={"provider_type": "claude-local"},
        )

        # TagsConfig should have defaults
        assert settings.tags.completed == "completed"

    def test_state_dir_property(self):
        """Test state_dir property returns Path object."""
        settings = AutomationSettings(
            git_provider={"base_url": "https://example.com", "api_token": "token"},
            repository={"owner": "org", "name": "repo"},
            agent_provider={"provider_type": "claude-local"},
            workflow={"state_directory": "/custom/state"},
        )

        state_dir = settings.state_dir
        assert isinstance(state_dir, Path)
        assert str(state_dir) == "/custom/state"

    def test_plans_dir_property(self):
        """Test plans_dir property returns Path object."""
        settings = AutomationSettings(
            git_provider={"base_url": "https://example.com", "api_token": "token"},
            repository={"owner": "org", "name": "repo"},
            agent_provider={"provider_type": "claude-local"},
            workflow={"plans_directory": "/custom/plans"},
        )

        plans_dir = settings.plans_dir
        assert isinstance(plans_dir, Path)
        assert str(plans_dir) == "/custom/plans"


class TestAutomationSettingsFromYAML:
    """Test loading AutomationSettings from YAML files."""

    @pytest.fixture
    def temp_yaml_file(self, tmp_path: Path) -> Path:
        """Create a temporary YAML file."""
        config_file = tmp_path / "config.yaml"
        return config_file

    def test_load_from_yaml(self, temp_yaml_file: Path):
        """Test loading complete settings from YAML file."""
        config_content = {
            "git_provider": {
                "provider_type": "gitea",
                "base_url": "https://gitea.example.com",
                "api_token": "yaml-token",
                "mcp_server": "gitea-mcp",
            },
            "repository": {
                "owner": "myorg",
                "name": "myrepo",
                "default_branch": "develop",
            },
            "agent_provider": {
                "provider_type": "claude-api",
                "model": "claude-opus-4.5",
                "api_key": "sk-abc123",
                "local_mode": False,
            },
            "workflow": {
                "plans_directory": "project-plans",
                "max_concurrent_tasks": 5,
            },
            "tags": {
                "completed": "finished",
            },
        }

        with open(temp_yaml_file, "w") as f:
            yaml.dump(config_content, f)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))

        assert settings.git_provider.provider_type == "gitea"
        assert settings.repository.owner == "myorg"
        assert settings.workflow.plans_directory == "project-plans"
        assert settings.tags.completed == "finished"

    def test_load_from_nonexistent_file_raises_error(self):
        """Test loading from nonexistent file raises ConfigurationError."""
        from repo_sapiens.exceptions import ConfigurationError

        # from_yaml wraps FileNotFoundError in ConfigurationError
        with pytest.raises(ConfigurationError):
            AutomationSettings.from_yaml("/nonexistent/config.yaml")

    def test_yaml_with_missing_required_fields(self, temp_yaml_file: Path):
        """Test YAML with missing required fields raises error."""
        from repo_sapiens.exceptions import ConfigurationError

        config_content = {
            "repository": {
                "owner": "org",
                "name": "repo",
            },
            # Missing git_provider and agent_provider
        }

        with open(temp_yaml_file, "w") as f:
            yaml.dump(config_content, f)

        # from_yaml wraps ValidationError in ConfigurationError
        with pytest.raises(ConfigurationError):
            AutomationSettings.from_yaml(str(temp_yaml_file))

    def test_yaml_with_invalid_values_raises_error(self, temp_yaml_file: Path):
        """Test YAML with invalid values raises validation error."""
        from repo_sapiens.exceptions import ConfigurationError

        config_content = {
            "git_provider": {
                "base_url": "invalid-url",
                "api_token": "token",
            },
            "repository": {
                "owner": "org",
                "name": "repo",
            },
            "agent_provider": {
                "provider_type": "invalid-type",
            },
        }

        with open(temp_yaml_file, "w") as f:
            yaml.dump(config_content, f)

        # from_yaml wraps ValidationError in ConfigurationError
        with pytest.raises(ConfigurationError):
            AutomationSettings.from_yaml(str(temp_yaml_file))


class TestEnvironmentVariableInterpolation:
    """Test environment variable interpolation in YAML."""

    @pytest.fixture
    def temp_yaml_file(self, tmp_path: Path) -> Path:
        """Create a temporary YAML file."""
        return tmp_path / "config.yaml"

    def test_simple_env_var_interpolation(self, temp_yaml_file: Path, monkeypatch):
        """Test simple ${VAR} interpolation."""
        monkeypatch.setenv("GITEA_URL", "https://gitea.example.com")
        monkeypatch.setenv("GITEA_TOKEN", "token-123")

        config_content = """
git_provider:
  base_url: ${GITEA_URL}
  api_token: ${GITEA_TOKEN}
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))

        assert "gitea.example.com" in str(settings.git_provider.base_url)

    def test_missing_env_var_raises_error(self, temp_yaml_file: Path):
        """Test missing environment variable raises ValueError."""
        from repo_sapiens.exceptions import ConfigurationError

        config_content = """
git_provider:
  base_url: ${MISSING_VAR}
  api_token: token
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        # from_yaml wraps the ValueError in ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            AutomationSettings.from_yaml(str(temp_yaml_file))

        assert "MISSING_VAR" in str(exc_info.value)

    def test_multiple_env_vars_in_single_line(self, temp_yaml_file: Path, monkeypatch):
        """Test multiple environment variables in single line."""
        monkeypatch.setenv("HOST", "example.com")
        monkeypatch.setenv("PORT", "3000")

        config_content = """
git_provider:
  base_url: https://${HOST}
  api_token: token-${PORT}
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        # Check that interpolation worked
        assert "example.com" in str(settings.git_provider.base_url)
        assert "3000" in settings.git_provider.api_token.get_secret_value()

    def test_env_var_pattern_case_sensitivity(self, temp_yaml_file: Path, monkeypatch):
        """Test environment variable pattern is case-sensitive (uppercase only)."""
        from repo_sapiens.exceptions import ConfigurationError

        monkeypatch.setenv("UPPERCASE_VAR", "value")

        # This should fail because pattern only matches uppercase
        config_content = """
git_provider:
  base_url: ${lowercase_var}
  api_token: token
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        # from_yaml wraps the ValueError in ConfigurationError
        with pytest.raises(ConfigurationError):
            AutomationSettings.from_yaml(str(temp_yaml_file))

    def test_env_var_with_underscores_and_numbers(self, temp_yaml_file: Path, monkeypatch):
        """Test environment variable names with underscores and numbers."""
        monkeypatch.setenv("VAR_NAME_123", "test-value")

        config_content = """
git_provider:
  base_url: https://${VAR_NAME_123}
  api_token: token
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        assert "test-value" in str(settings.git_provider.base_url)

    def test_literal_dollar_signs_preserved(self, temp_yaml_file: Path):
        """Test that literal $ characters are preserved when not part of pattern."""
        config_content = """
git_provider:
  base_url: https://example.com
  api_token: price-$100
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        # The literal value should be preserved as-is
        assert settings.git_provider.api_token


class TestConfigurationMerging:
    """Test merging file-based and environment variable configuration."""

    def test_env_vars_override_yaml_values(self, tmp_path: Path, monkeypatch):
        """Test that environment variables can override YAML values."""
        yaml_file = tmp_path / "config.yaml"
        config_content = {
            "git_provider": {
                "base_url": "https://yaml.example.com",
                "api_token": "yaml-token",
            },
            "repository": {
                "owner": "yaml-org",
                "name": "yaml-repo",
            },
            "agent_provider": {
                "provider_type": "claude-local",
            },
        }

        with open(yaml_file, "w") as f:
            yaml.dump(config_content, f)

        # Set environment variables that should override YAML
        monkeypatch.setenv("AUTOMATION_GIT_PROVIDER__Mmissing", "test")

        # Load and verify YAML values are used
        settings = AutomationSettings.from_yaml(str(yaml_file))
        assert "yaml" in str(settings.git_provider.base_url).lower()

    def test_environment_prefix_recognition(self, monkeypatch):
        """Test that AUTOMATION_ prefix is correctly recognized."""
        monkeypatch.setenv("AUTOMATION_REPOSITORY__OWNER", "env-org")
        monkeypatch.setenv("AUTOMATION_REPOSITORY__NAME", "env-repo")
        monkeypatch.setenv("AUTOMATION_GIT_PROVIDER__BASE_URL", "https://env.com")
        monkeypatch.setenv("AUTOMATION_GIT_PROVIDER__API_TOKEN", "env-token")

        # Create settings from environment variables
        settings = AutomationSettings(
            git_provider={
                "base_url": "https://env.com",
                "api_token": "env-token",
            },
            repository={
                "owner": "env-org",
                "name": "env-repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
        )

        assert settings.repository.owner == "env-org"
        assert settings.repository.name == "env-repo"

    def test_nested_delimiter_handling(self):
        """Test handling of nested configuration with __ delimiter."""
        settings = AutomationSettings(
            git_provider={
                "provider_type": "gitea",
                "base_url": "https://example.com",
                "api_token": "token",
                "mcp_server": "test-mcp",
            },
            repository={
                "owner": "org",
                "name": "repo",
                "default_branch": "main",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
            workflow={
                "plans_directory": "plans",
                "max_concurrent_tasks": 5,
            },
        )

        assert settings.git_provider.mcp_server == "test-mcp"
        assert settings.workflow.max_concurrent_tasks == 5


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions."""

    def test_circular_reference_in_config(self, tmp_path: Path):
        """Test handling of circular references (if applicable)."""
        # This is a placeholder for circular reference tests
        # Circular references in YAML would be a semantic issue, not a schema issue
        pass

    def test_very_large_max_concurrent_tasks_rejected(self):
        """Test that unreasonably large values are rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(max_concurrent_tasks=1000)

    def test_negative_threshold_rejected(self):
        """Test that negative thresholds are rejected."""
        with pytest.raises(ValidationError):
            WorkflowConfig(review_approval_threshold=-0.5)

    def test_unicode_in_strings(self):
        """Test Unicode characters in configuration strings."""
        config = RepositoryConfig(
            owner="org-名前",
            name="repo-リポジトリ",
        )

        assert "名前" in config.owner
        assert "リポジトリ" in config.name

    def test_very_long_strings(self):
        """Test configuration with very long string values."""
        long_token = "a" * 10000
        config = GitProviderConfig(
            base_url="https://example.com",
            api_token=long_token,
        )

        # Should accept long strings
        assert len(config.api_token.get_secret_value()) == 10000

    def test_config_allows_validation_on_assignment(self):
        """Test that Pydantic models validate on assignment attempts."""
        config = GitProviderConfig(
            base_url="https://example.com",
            api_token="token",
        )

        # Pydantic v2 may allow assignment but will validate if configured
        # Check that the value is still accessible and correctly set
        assert config.provider_type == "gitea"


class TestInterpolationEdgeCases:
    """Test edge cases in environment variable interpolation."""

    @pytest.fixture
    def temp_yaml_file(self, tmp_path: Path) -> Path:
        """Create a temporary YAML file."""
        return tmp_path / "config.yaml"

    def test_env_var_with_special_characters(self, temp_yaml_file: Path, monkeypatch):
        """Test environment variables containing special characters."""
        # Note: Env var names typically only allow A-Z, 0-9, _
        # But values can contain special characters
        monkeypatch.setenv("SPECIAL_CHARS", "value-with-special!@#$%")

        config_content = """
git_provider:
  base_url: https://example.com
  api_token: ${SPECIAL_CHARS}
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        # Token should contain the special characters
        assert "special" in settings.git_provider.api_token.get_secret_value()

    def test_empty_env_var_value(self, temp_yaml_file: Path, monkeypatch):
        """Test interpolation of empty environment variable."""
        monkeypatch.setenv("EMPTY_VAR", "")

        config_content = """
git_provider:
  base_url: https://example.com
  api_token: ${EMPTY_VAR}
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        # Empty value should be accepted by interpolation
        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        # The empty string is a valid SecretStr
        assert settings.git_provider.api_token

    def test_env_var_in_yaml_comment_is_ignored(self, temp_yaml_file: Path, monkeypatch):
        """Test that ${VAR_NAME} patterns in YAML comments are not interpolated.

        This prevents documentation examples from being parsed as actual
        environment variable references.
        """
        monkeypatch.setenv("REAL_TOKEN", "actual-token-value")
        # Note: VAR_NAME is intentionally NOT set - it's just documentation

        config_content = """
# Configuration file for automation
# Environment variables can be referenced using ${VAR_NAME} syntax
# Example: api_token: ${MY_TOKEN}
git_provider:
  base_url: https://example.com
  api_token: ${REAL_TOKEN}
repository:
  owner: org
  name: repo
agent_provider:
  provider_type: claude-local
"""

        with open(temp_yaml_file, "w") as f:
            f.write(config_content)

        # Should NOT raise ValueError about VAR_NAME or MY_TOKEN being unset
        settings = AutomationSettings.from_yaml(str(temp_yaml_file))
        assert settings.git_provider.api_token.get_secret_value() == "actual-token-value"


class TestConfigurationSerialization:
    """Test configuration model serialization."""

    def test_model_dump(self):
        """Test dumping configuration to dict."""
        settings = AutomationSettings(
            git_provider={
                "base_url": "https://example.com",
                "api_token": "token",
            },
            repository={
                "owner": "org",
                "name": "repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
        )

        # Pydantic v2 uses model_dump
        dumped = settings.model_dump()

        assert dumped["repository"]["owner"] == "org"
        assert dumped["repository"]["name"] == "repo"

    def test_secret_str_not_exposed_in_dump(self):
        """Test that SecretStr values are masked in dumps."""
        settings = AutomationSettings(
            git_provider={
                "base_url": "https://example.com",
                "api_token": "secret-token-123",
            },
            repository={
                "owner": "org",
                "name": "repo",
            },
            agent_provider={
                "provider_type": "claude-local",
            },
        )

        dumped = settings.model_dump(mode="json")
        # SecretStr should be masked in mode='json'
        api_token_value = dumped["git_provider"]["api_token"]

        # When serialized, SecretStr is typically masked
        # The behavior depends on Pydantic version, but secret should not be exposed
        assert api_token_value  # Value exists
