"""Tests for configuration."""

from repo_sapiens.config.settings import AutomationSettings


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

    # Should use environment variable if set in YAML as ${GITEA_TOKEN}
    assert settings.git_provider.api_token.get_secret_value() == "test-token"


def test_defaults():
    """Test default configuration values."""
    settings = AutomationSettings()

    assert settings.repository.default_branch == "main"
    assert settings.workflow.branching_strategy == "per-agent"
    assert settings.cicd.timeout_minutes == 30
