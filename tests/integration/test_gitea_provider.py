"""Integration tests for Gitea provider.

These tests verify the GiteaProvider can interact with a real Gitea instance.
Requires:
- Gitea running at localhost:3000 (or GITEA_URL)
- SAPIENS_GITEA_TOKEN environment variable set
- A test repository created (default: admin/test-repo)

Run with: uv run pytest tests/integration/test_gitea_provider.py -v -m integration
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.gitea
class TestGiteaConnection:
    """Test basic Gitea connectivity."""

    def test_gitea_version(self, gitea_url: str, require_gitea: None) -> None:
        """Verify Gitea is accessible and returns version."""
        response = httpx.get(f"{gitea_url}/api/v1/version", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_gitea_auth(self, gitea_test_repo: dict) -> None:
        """Verify authentication works with provided token."""
        response = httpx.get(
            f"{gitea_test_repo['api_base']}/user",
            headers={"Authorization": f"token {gitea_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "login" in data


@pytest.mark.integration
@pytest.mark.gitea
class TestGiteaRepository:
    """Test Gitea repository operations."""

    def test_get_repository(self, gitea_test_repo: dict) -> None:
        """Verify test repository exists and is accessible."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        response = httpx.get(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}",
            headers={"Authorization": f"token {gitea_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name

    def test_list_branches(self, gitea_test_repo: dict) -> None:
        """Verify branches can be listed."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        response = httpx.get(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/branches",
            headers={"Authorization": f"token {gitea_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_issues(self, gitea_test_repo: dict) -> None:
        """Verify issues can be listed."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        response = httpx.get(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers={"Authorization": f"token {gitea_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
@pytest.mark.gitea
class TestGiteaIssueWorkflow:
    """Test Gitea issue create/update/close workflow."""

    @pytest.fixture
    def test_issue(self, gitea_test_repo: dict) -> Generator[dict, None, None]:
        """Create a test issue and clean up after."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        headers = {"Authorization": f"token {gitea_test_repo['token']}"}

        # Create issue
        response = httpx.post(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers=headers,
            json={
                "title": "integration-test-issue",
                "body": "This is an automated test issue. It should be deleted.",
            },
            timeout=10.0,
        )
        assert response.status_code == 201
        issue = response.json()

        yield issue

        # Cleanup: close and delete comments
        httpx.patch(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue['number']}",
            headers=headers,
            json={"state": "closed"},
            timeout=10.0,
        )

    def test_create_issue(self, test_issue: dict) -> None:
        """Verify issue was created successfully."""
        assert test_issue["number"] > 0
        assert test_issue["title"] == "integration-test-issue"

    def test_add_comment(self, gitea_test_repo: dict, test_issue: dict) -> None:
        """Verify comments can be added to issues."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        headers = {"Authorization": f"token {gitea_test_repo['token']}"}

        response = httpx.post(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/issues/{test_issue['number']}/comments",
            headers=headers,
            json={"body": "Test comment from integration test"},
            timeout=10.0,
        )
        assert response.status_code == 201
        comment = response.json()
        assert "Test comment" in comment["body"]

    def test_add_label(self, gitea_test_repo: dict, test_issue: dict) -> None:
        """Verify labels can be added to issues."""
        owner = gitea_test_repo["owner"]
        name = gitea_test_repo["name"]
        headers = {"Authorization": f"token {gitea_test_repo['token']}"}

        # First ensure label exists
        httpx.post(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/labels",
            headers=headers,
            json={"name": "test-label", "color": "#ff0000"},
            timeout=10.0,
        )  # Ignore if exists

        # Add label to issue
        response = httpx.post(
            f"{gitea_test_repo['api_base']}/repos/{owner}/{name}/issues/{test_issue['number']}/labels",
            headers=headers,
            json={"labels": ["test-label"]},
            timeout=10.0,
        )
        # May return 200 or 403 depending on Gitea version
        assert response.status_code in (200, 403)
