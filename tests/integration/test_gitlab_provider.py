"""Integration tests for GitLab provider.

These tests verify the GitLabProvider can interact with a real GitLab instance.
Requires:
- GitLab running at localhost:8080 (or GITLAB_URL)
- GITLAB_TOKEN environment variable set
- A test project created (default: root/test-repo)

Run with: uv run pytest tests/integration/test_gitlab_provider.py -v -m integration
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabConnection:
    """Test basic GitLab connectivity."""

    def test_gitlab_health(self, gitlab_url: str, require_gitlab: None) -> None:
        """Verify GitLab is accessible and healthy."""
        response = httpx.get(f"{gitlab_url}/-/health", timeout=10.0)
        assert response.status_code == 200

    def test_gitlab_auth(self, gitlab_test_repo: dict) -> None:
        """Verify authentication works with provided token."""
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/user",
            headers={"PRIVATE-TOKEN": gitlab_test_repo["token"]},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "username" in data


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabProject:
    """Test GitLab project operations."""

    def test_get_project(self, gitlab_test_repo: dict) -> None:
        """Verify test project exists and is accessible."""
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}",
            headers={"PRIVATE-TOKEN": gitlab_test_repo["token"]},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == gitlab_test_repo["name"]

    def test_list_branches(self, gitlab_test_repo: dict) -> None:
        """Verify branches can be listed."""
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches",
            headers={"PRIVATE-TOKEN": gitlab_test_repo["token"]},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_issues(self, gitlab_test_repo: dict) -> None:
        """Verify issues can be listed."""
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
            headers={"PRIVATE-TOKEN": gitlab_test_repo["token"]},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabIssueWorkflow:
    """Test GitLab issue create/update/close workflow."""

    @pytest.fixture
    def test_issue(self, gitlab_test_repo: dict) -> dict:
        """Create a test issue and clean up after."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        # Create issue
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
            headers=headers,
            json={
                "title": "integration-test-issue",
                "description": "This is an automated test issue. It should be deleted.",
            },
            timeout=10.0,
        )
        assert response.status_code == 201
        issue = response.json()

        yield issue

        # Cleanup: close issue
        httpx.put(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues/{issue['iid']}",
            headers=headers,
            json={"state_event": "close"},
            timeout=10.0,
        )

    def test_create_issue(self, test_issue: dict) -> None:
        """Verify issue was created successfully."""
        assert test_issue["iid"] > 0
        assert test_issue["title"] == "integration-test-issue"

    def test_add_note(self, gitlab_test_repo: dict, test_issue: dict) -> None:
        """Verify notes (comments) can be added to issues."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues/{test_issue['iid']}/notes",
            headers=headers,
            json={"body": "Test comment from integration test"},
            timeout=10.0,
        )
        assert response.status_code == 201
        note = response.json()
        assert "Test comment" in note["body"]

    def test_add_label(self, gitlab_test_repo: dict, test_issue: dict) -> None:
        """Verify labels can be added to issues."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        # First ensure label exists
        httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/labels",
            headers=headers,
            json={"name": "test-label", "color": "#ff0000"},
            timeout=10.0,
        )  # Ignore if exists

        # Update issue with label
        response = httpx.put(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues/{test_issue['iid']}",
            headers=headers,
            json={"labels": "test-label"},
            timeout=10.0,
        )
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabMergeRequest:
    """Test GitLab merge request operations."""

    def test_list_merge_requests(self, gitlab_test_repo: dict) -> None:
        """Verify merge requests can be listed."""
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests",
            headers={"PRIVATE-TOKEN": gitlab_test_repo["token"]},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
