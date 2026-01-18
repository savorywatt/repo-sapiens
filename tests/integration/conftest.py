"""Pytest fixtures for integration tests.

These fixtures provide access to real external services for testing.
Set environment variables before running:
- SAPIENS_GITEA_TOKEN: Gitea API token
- GITLAB_TOKEN: GitLab API token
- SAPIENS_GITHUB_TOKEN: GitHub API token (optional)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Generator

import httpx
import pytest

if TYPE_CHECKING:
    from python_on_whales import DockerClient


# Skip markers for missing services
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow (actual LLM calls)")
    config.addinivalue_line("markers", "gitea: requires Gitea service")
    config.addinivalue_line("markers", "gitlab: requires GitLab service")
    config.addinivalue_line("markers", "ollama: requires Ollama service")


@pytest.fixture(scope="session")
def gitea_url() -> str:
    """Gitea base URL."""
    return os.environ.get("GITEA_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def gitea_token() -> str | None:
    """Gitea API token from environment."""
    return os.environ.get("SAPIENS_GITEA_TOKEN")


@pytest.fixture(scope="session")
def gitlab_url() -> str:
    """GitLab base URL."""
    return os.environ.get("GITLAB_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def gitlab_token() -> str | None:
    """GitLab API token from environment."""
    return os.environ.get("GITLAB_TOKEN")


@pytest.fixture(scope="session")
def ollama_url() -> str:
    """Ollama base URL."""
    return os.environ.get("OLLAMA_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def gitea_available(gitea_url: str, gitea_token: str | None) -> bool:
    """Check if Gitea is available and configured."""
    if not gitea_token:
        return False
    try:
        response = httpx.get(f"{gitea_url}/api/v1/version", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False


@pytest.fixture(scope="session")
def gitlab_available(gitlab_url: str, gitlab_token: str | None) -> bool:
    """Check if GitLab is available and configured."""
    if not gitlab_token:
        return False
    try:
        response = httpx.get(f"{gitlab_url}/-/health", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False


@pytest.fixture(scope="session")
def ollama_available(ollama_url: str) -> bool:
    """Check if Ollama is available."""
    try:
        response = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False


@pytest.fixture
def require_gitea(gitea_available: bool) -> None:
    """Skip test if Gitea is not available."""
    if not gitea_available:
        pytest.skip("Gitea not available (check SAPIENS_GITEA_TOKEN and service)")


@pytest.fixture
def require_gitlab(gitlab_available: bool) -> None:
    """Skip test if GitLab is not available."""
    if not gitlab_available:
        pytest.skip("GitLab not available (check GITLAB_TOKEN and service)")


@pytest.fixture
def require_ollama(ollama_available: bool) -> None:
    """Skip test if Ollama is not available."""
    if not ollama_available:
        pytest.skip("Ollama not available (start with: ollama serve)")


@pytest.fixture(scope="session")
def docker() -> Generator[DockerClient, None, None]:
    """Docker client using python-on-whales."""
    try:
        from python_on_whales import DockerClient

        client = DockerClient()
        yield client
    except ImportError:
        pytest.skip("python-on-whales not installed")


@pytest.fixture
def gitea_test_repo(gitea_url: str, gitea_token: str | None, require_gitea: None) -> dict:
    """Get test repository info for Gitea."""
    owner = os.environ.get("GITEA_OWNER", "admin")
    repo = os.environ.get("GITEA_REPO", "test-repo")
    return {
        "url": gitea_url,
        "token": gitea_token,
        "owner": owner,
        "name": repo,
        "api_base": f"{gitea_url}/api/v1",
    }


@pytest.fixture
def gitlab_test_repo(gitlab_url: str, gitlab_token: str | None, require_gitlab: None) -> dict:
    """Get test repository info for GitLab."""
    project = os.environ.get("GITLAB_PROJECT", "root/test-repo")
    owner, name = project.split("/", 1)
    return {
        "url": gitlab_url,
        "token": gitlab_token,
        "owner": owner,
        "name": name,
        "project": project,
        "project_encoded": project.replace("/", "%2F"),
        "api_base": f"{gitlab_url}/api/v4",
    }


@pytest.fixture
def ollama_config(ollama_url: str, require_ollama: None) -> dict:
    """Get Ollama configuration."""
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    return {
        "url": ollama_url,
        "model": model,
    }
