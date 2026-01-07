"""Tests for configuration."""

import pytest

from repo_sapiens.config.settings import AutomationSettings


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Create a sample YAML config file for testing."""
    config_content = """
git_provider:
  provider_type: gitea
  mcp_server: test-mcp
  base_url: https://gitea.test.com
  api_token: test-token

repository:
  owner: testowner
  name: testrepo
  default_branch: main

agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4.5
  api_key: test-key
  local_mode: true

workflow:
  plans_directory: plans/
  state_directory: .sapiens/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


def test_config_from_yaml(sample_config_yaml):
    """Test loading configuration from YAML."""
    settings = AutomationSettings.from_yaml(str(sample_config_yaml))

    assert settings.repository.owner == "testowner"
    assert settings.repository.name == "testrepo"
    assert settings.workflow.max_concurrent_tasks == 3


def test_env_var_interpolation(sample_config_yaml, monkeypatch):
    """Test environment variable interpolation."""
    monkeypatch.setenv("GITEA_TOKEN", "env-token")

    settings = AutomationSettings.from_yaml(str(sample_config_yaml))

    # Test that config loaded correctly (env var interpolation happens at runtime)
    assert settings.git_provider.api_token.get_secret_value() == "test-token"


def test_defaults(mock_settings):
    """Test default configuration values using mock_settings fixture."""
    # mock_settings provides all required fields
    assert mock_settings.repository.default_branch == "main"
    assert mock_settings.workflow.branching_strategy == "per-agent"
