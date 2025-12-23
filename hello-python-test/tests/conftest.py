"""Pytest configuration and shared fixtures for CLI tests."""

import asyncio
from pathlib import Path
from typing import Any, Generator

import pytest
from click.testing import CliRunner


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for state files."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Create a sample valid YAML config file."""
    config_file = tmp_path / "config.yaml"
    config_content = """
git_provider:
  provider_type: gitea
  base_url: http://localhost:3000
  api_token: test_token_secret

repository:
  owner: test_owner
  name: test_repo

agent_provider:
  provider_type: external
  model: claude-opus-4.5-20251101
  base_url: http://localhost

state_dir: /tmp/state
default_poll_interval: 60
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def invalid_yaml_config(tmp_path: Path) -> Path:
    """Create an invalid YAML config file."""
    config_file = tmp_path / "invalid.yaml"
    config_content = """
this: is: invalid: yaml: syntax:
  - broken
    structure
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def incomplete_yaml_config(tmp_path: Path) -> Path:
    """Create a config file with missing required fields."""
    config_file = tmp_path / "incomplete.yaml"
    config_content = """
git_provider:
  provider_type: gitea
  base_url: http://localhost:3000
"""
    config_file.write_text(config_content)
    return config_file
