"""Integration tests for GitLab provider.

These tests verify the GitLabRestProvider can interact with a real GitLab instance.

There are two types of tests here:
1. Raw API tests (using httpx) - verify the GitLab API works as expected
2. Provider tests (using GitLabRestProvider) - verify sapiens can do these operations

Requires:
- GitLab running at localhost:8080 (or GITLAB_URL)
- GITLAB_TOKEN environment variable set
- A test project created (default: root/test-repo)

Run with: uv run pytest tests/integration/test_gitlab_provider.py -v -m integration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

if TYPE_CHECKING:
    from repo_sapiens.providers.gitlab_rest import GitLabRestProvider


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


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabBranchOperations:
    """Test GitLab branch create/delete operations.

    Required for: approved.yaml, execute-task.yaml, dependency-audit.yaml, security-review.yaml
    """

    @pytest.fixture
    def test_branch(self, gitlab_test_repo: dict) -> dict:
        """Create a test branch and clean up after."""
        import time

        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}
        branch_name = f"test-branch-{int(time.time())}"

        # Create branch from default branch (main)
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches",
            headers=headers,
            json={"branch": branch_name, "ref": "main"},
            timeout=10.0,
        )
        assert response.status_code == 201, f"Failed to create branch: {response.text}"
        branch = response.json()

        yield {"name": branch_name, "data": branch}

        # Cleanup: delete branch
        branch_encoded = branch_name.replace("/", "%2F")
        httpx.delete(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches/{branch_encoded}",
            headers=headers,
            timeout=10.0,
        )

    def test_create_branch(self, test_branch: dict) -> None:
        """Verify branch was created successfully."""
        assert test_branch["name"].startswith("test-branch-")
        assert test_branch["data"]["name"] == test_branch["name"]

    def test_get_branch(self, gitlab_test_repo: dict, test_branch: dict) -> None:
        """Verify branch can be retrieved."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}
        branch_encoded = test_branch["name"].replace("/", "%2F")

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches/{branch_encoded}",
            headers=headers,
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_branch["name"]


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabMergeRequestWorkflow:
    """Test full MR workflow: create branch, commit, create MR, add comments.

    Required for: approved.yaml, needs-review.yaml, needs-fix.yaml, requires-qa.yaml,
                  dependency-audit.yaml, security-review.yaml, test-coverage.yaml
    """

    @pytest.fixture
    def test_mr(self, gitlab_test_repo: dict) -> dict:
        """Create a test MR with a branch and clean up after."""
        import time

        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}
        timestamp = int(time.time())
        branch_name = f"test-mr-branch-{timestamp}"

        # Step 1: Create branch
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches",
            headers=headers,
            json={"branch": branch_name, "ref": "main"},
            timeout=10.0,
        )
        assert response.status_code == 201, f"Failed to create branch: {response.text}"

        # Step 2: Create a file commit on the branch (required for MR)
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/files/test-file-{timestamp}.txt",
            headers=headers,
            json={
                "branch": branch_name,
                "content": f"Test content created at {timestamp}",
                "commit_message": "Add test file for MR integration test",
            },
            timeout=10.0,
        )
        assert response.status_code == 201, f"Failed to create file: {response.text}"

        # Step 3: Create MR
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests",
            headers=headers,
            json={
                "source_branch": branch_name,
                "target_branch": "main",
                "title": f"[TEST] Integration test MR {timestamp}",
                "description": "This MR was created by integration tests and should be deleted.",
                "remove_source_branch": True,
            },
            timeout=10.0,
        )
        assert response.status_code == 201, f"Failed to create MR: {response.text}"
        mr = response.json()

        yield {"iid": mr["iid"], "branch": branch_name, "data": mr}

        # Cleanup: close MR
        httpx.put(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests/{mr['iid']}",
            headers=headers,
            json={"state_event": "close"},
            timeout=10.0,
        )

        # Cleanup: delete branch
        branch_encoded = branch_name.replace("/", "%2F")
        httpx.delete(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/branches/{branch_encoded}",
            headers=headers,
            timeout=10.0,
        )

    def test_create_merge_request(self, test_mr: dict) -> None:
        """Verify MR was created successfully."""
        assert test_mr["iid"] > 0
        assert "[TEST]" in test_mr["data"]["title"]

    def test_get_merge_request(self, gitlab_test_repo: dict, test_mr: dict) -> None:
        """Verify MR can be retrieved."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests/{test_mr['iid']}",
            headers=headers,
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["iid"] == test_mr["iid"]

    def test_add_mr_note(self, gitlab_test_repo: dict, test_mr: dict) -> None:
        """Verify notes (comments) can be added to MRs.

        Required for: needs-review.yaml, needs-fix.yaml, requires-qa.yaml
        """
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests/{test_mr['iid']}/notes",
            headers=headers,
            json={"body": "Integration test comment on MR"},
            timeout=10.0,
        )
        assert response.status_code == 201
        note = response.json()
        assert "Integration test comment" in note["body"]

    def test_add_mr_label(self, gitlab_test_repo: dict, test_mr: dict) -> None:
        """Verify labels can be added to MRs.

        Required for: needs-review.yaml (sapiens/needs-review label)
        """
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        # Ensure label exists
        httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/labels",
            headers=headers,
            json={"name": "test-mr-label", "color": "#00ff00"},
            timeout=10.0,
        )  # Ignore if exists

        # Add label to MR
        response = httpx.put(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests/{test_mr['iid']}",
            headers=headers,
            json={"add_labels": "test-mr-label"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "test-mr-label" in data["labels"]

    def test_get_mr_changes(self, gitlab_test_repo: dict, test_mr: dict) -> None:
        """Verify MR diff/changes can be retrieved.

        Required for: needs-review.yaml (code review needs to see changes)
        """
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/merge_requests/{test_mr['iid']}/changes",
            headers=headers,
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert isinstance(data["changes"], list)


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabFileOperations:
    """Test GitLab file create/update/delete operations.

    Required for: execute-task.yaml, post-merge-docs.yaml
    """

    @pytest.fixture
    def test_file(self, gitlab_test_repo: dict) -> dict:
        """Create a test file and clean up after."""
        import time

        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}
        timestamp = int(time.time())
        file_path = f"test-files/integration-test-{timestamp}.txt"
        file_path_encoded = file_path.replace("/", "%2F")

        # Create file
        response = httpx.post(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/files/{file_path_encoded}",
            headers=headers,
            json={
                "branch": "main",
                "content": f"Test content created at {timestamp}",
                "commit_message": "Add test file for integration test",
            },
            timeout=10.0,
        )
        assert response.status_code == 201, f"Failed to create file: {response.text}"

        yield {"path": file_path, "path_encoded": file_path_encoded}

        # Cleanup: delete file
        httpx.delete(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/files/{file_path_encoded}",
            headers=headers,
            json={"branch": "main", "commit_message": "Delete test file"},
            timeout=10.0,
        )

    def test_create_file(self, test_file: dict) -> None:
        """Verify file was created successfully."""
        assert test_file["path"].startswith("test-files/")

    def test_get_file(self, gitlab_test_repo: dict, test_file: dict) -> None:
        """Verify file content can be retrieved."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/files/{test_file['path_encoded']}",
            headers=headers,
            params={"ref": "main"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == test_file["path"]

    def test_update_file(self, gitlab_test_repo: dict, test_file: dict) -> None:
        """Verify file can be updated."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.put(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/files/{test_file['path_encoded']}",
            headers=headers,
            json={
                "branch": "main",
                "content": "Updated content",
                "commit_message": "Update test file",
            },
            timeout=10.0,
        )
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabIssueFilters:
    """Test GitLab issue listing with filters.

    Required for: process-issue.yaml (scan-labeled-issues), daily-issue-triage.yaml
    """

    @pytest.fixture
    def labeled_issues(self, gitlab_test_repo: dict) -> list[dict]:
        """Create test issues with specific labels and clean up after."""
        import time

        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}
        timestamp = int(time.time())
        issues = []

        # Ensure labels exist
        for label_name, color in [("filter-test-a", "#ff0000"), ("filter-test-b", "#00ff00")]:
            httpx.post(
                f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/labels",
                headers=headers,
                json={"name": label_name, "color": color},
                timeout=10.0,
            )

        # Create issues with different labels
        for i, labels in enumerate([["filter-test-a"], ["filter-test-b"], ["filter-test-a", "filter-test-b"]]):
            response = httpx.post(
                f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
                headers=headers,
                json={
                    "title": f"Filter test issue {i} - {timestamp}",
                    "description": "Test issue for filter integration test",
                    "labels": ",".join(labels),
                },
                timeout=10.0,
            )
            assert response.status_code == 201
            issues.append(response.json())

        yield issues

        # Cleanup: close all test issues
        for issue in issues:
            httpx.put(
                f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues/{issue['iid']}",
                headers=headers,
                json={"state_event": "close"},
                timeout=10.0,
            )

    def test_filter_by_single_label(self, gitlab_test_repo: dict, labeled_issues: list[dict]) -> None:
        """Verify issues can be filtered by a single label.

        Required for: process-issue.yaml scanning for 'needs-planning' issues
        """
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
            headers=headers,
            params={"labels": "filter-test-a", "state": "opened"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        # Should find at least 2 issues (the ones with filter-test-a)
        matching = [i for i in data if "filter-test-a" in i.get("labels", [])]
        assert len(matching) >= 2

    def test_filter_by_multiple_labels(self, gitlab_test_repo: dict, labeled_issues: list[dict]) -> None:
        """Verify issues can be filtered by multiple labels (AND logic)."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
            headers=headers,
            params={"labels": "filter-test-a,filter-test-b", "state": "opened"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        # Should find at least 1 issue (the one with both labels)
        matching = [
            i for i in data if "filter-test-a" in i.get("labels", []) and "filter-test-b" in i.get("labels", [])
        ]
        assert len(matching) >= 1

    def test_filter_no_labels(self, gitlab_test_repo: dict) -> None:
        """Verify issues without labels can be found.

        Required for: daily-issue-triage.yaml (finding untriaged issues)
        """
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        # Note: GitLab doesn't have a direct "no labels" filter,
        # but we can list all and filter client-side
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/issues",
            headers=headers,
            params={"state": "opened", "per_page": 100},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        # Check that filtering is possible (issues have labels field)
        for issue in data:
            assert "labels" in issue


@pytest.mark.integration
@pytest.mark.gitlab
class TestGitLabCommitOperations:
    """Test GitLab commit operations.

    Required for: execute-task.yaml (committing code changes)
    """

    def test_list_commits(self, gitlab_test_repo: dict) -> None:
        """Verify commits can be listed."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/commits",
            headers=headers,
            params={"ref_name": "main", "per_page": 10},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_commit(self, gitlab_test_repo: dict) -> None:
        """Verify a specific commit can be retrieved."""
        headers = {"PRIVATE-TOKEN": gitlab_test_repo["token"]}

        # First get list of commits
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/commits",
            headers=headers,
            params={"ref_name": "main", "per_page": 1},
            timeout=10.0,
        )
        assert response.status_code == 200
        commits = response.json()
        if not commits:
            pytest.skip("No commits in repository")

        # Get specific commit
        commit_sha = commits[0]["id"]
        response = httpx.get(
            f"{gitlab_test_repo['api_base']}/projects/{gitlab_test_repo['project_encoded']}/repository/commits/{commit_sha}",
            headers=headers,
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == commit_sha


# =============================================================================
# SAPIENS PROVIDER TESTS
# These tests use the actual GitLabRestProvider class to verify sapiens
# can perform all required operations against a live GitLab instance.
# =============================================================================


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabProviderConnection:
    """Test sapiens GitLabRestProvider connection."""

    async def test_provider_connects(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify provider can connect to GitLab."""
        # The fixture already connects, so if we get here it worked
        assert gitlab_provider._pool is not None

    async def test_provider_context_manager(self, gitlab_test_repo: dict) -> None:
        """Verify provider works as async context manager."""
        from repo_sapiens.providers.gitlab_rest import GitLabRestProvider

        async with GitLabRestProvider(
            base_url=gitlab_test_repo["url"],
            token=gitlab_test_repo["token"],
            owner=gitlab_test_repo["owner"],
            repo=gitlab_test_repo["name"],
        ) as provider:
            assert provider._pool is not None


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabIssueOperations:
    """Test sapiens GitLabRestProvider issue operations.

    These are the operations sapiens uses for:
    - needs-planning.yaml: get_issues(), create_issue(), update_issue(), add_comment()
    - daily-issue-triage.yaml: get_issues() with label filters
    """

    async def test_get_issues(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can list issues."""
        issues = await gitlab_provider.get_issues(state="all")
        assert isinstance(issues, list)

    async def test_get_issues_with_labels(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can filter issues by labels."""
        # Even if no issues match, should return empty list not error
        issues = await gitlab_provider.get_issues(labels=["nonexistent-label-xyz"])
        assert isinstance(issues, list)

    async def test_create_and_get_issue(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can create and retrieve issues."""
        import time

        # Create issue
        title = f"sapiens-test-issue-{int(time.time())}"
        issue = await gitlab_provider.create_issue(
            title=title,
            body="This issue was created by sapiens integration tests.",
            labels=["test-label"],
        )

        assert issue.number > 0
        assert issue.title == title

        # Get the issue back
        retrieved = await gitlab_provider.get_issue(issue.number)
        assert retrieved.number == issue.number
        assert retrieved.title == title

        # Cleanup: close the issue
        await gitlab_provider.update_issue(issue.number, state="closed")

    async def test_update_issue(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can update issues."""
        import time

        # Create issue first
        issue = await gitlab_provider.create_issue(
            title=f"sapiens-update-test-{int(time.time())}",
            body="Original body",
        )

        # Update it
        updated = await gitlab_provider.update_issue(
            issue.number,
            title="Updated title",
            body="Updated body",
        )

        assert updated.title == "Updated title"
        assert updated.body == "Updated body"

        # Cleanup
        await gitlab_provider.update_issue(issue.number, state="closed")

    async def test_add_comment(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can add comments to issues."""
        import time

        # Create issue first
        issue = await gitlab_provider.create_issue(
            title=f"sapiens-comment-test-{int(time.time())}",
            body="Testing comments",
        )

        # Add comment
        comment = await gitlab_provider.add_comment(issue.number, "Test comment from sapiens")
        assert comment.id > 0
        assert "Test comment" in comment.body

        # Cleanup
        await gitlab_provider.update_issue(issue.number, state="closed")

    async def test_get_comments(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can retrieve comments from issues."""
        import time

        # Create issue with comment
        issue = await gitlab_provider.create_issue(
            title=f"sapiens-get-comments-test-{int(time.time())}",
            body="Testing get_comments",
        )
        await gitlab_provider.add_comment(issue.number, "Comment 1")
        await gitlab_provider.add_comment(issue.number, "Comment 2")

        # Get comments
        comments = await gitlab_provider.get_comments(issue.number)
        assert len(comments) >= 2

        # Cleanup
        await gitlab_provider.update_issue(issue.number, state="closed")


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabBranchOperations:
    """Test sapiens GitLabRestProvider branch operations.

    These are the operations sapiens uses for:
    - approved.yaml: create_branch(), delete_branch()
    - execute-task.yaml: get_branch(), create_branch()
    """

    async def test_get_branch(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can get branch info."""
        branch = await gitlab_provider.get_branch("main")
        assert branch is not None
        assert branch.name == "main"
        assert branch.sha  # Has a commit SHA

    async def test_get_nonexistent_branch(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens handles missing branches gracefully."""
        branch = await gitlab_provider.get_branch("nonexistent-branch-xyz-123")
        assert branch is None

    async def test_create_and_delete_branch(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can create and delete branches."""
        import time

        branch_name = f"sapiens-test-branch-{int(time.time())}"

        # Create branch
        branch = await gitlab_provider.create_branch(branch_name, from_branch="main")
        assert branch.name == branch_name
        assert branch.sha  # Has a commit SHA

        # Verify it exists
        retrieved = await gitlab_provider.get_branch(branch_name)
        assert retrieved is not None
        assert retrieved.name == branch_name

        # Delete it
        deleted = await gitlab_provider.delete_branch(branch_name)
        assert deleted is True

        # Verify it's gone
        gone = await gitlab_provider.get_branch(branch_name)
        assert gone is None


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabFileOperations:
    """Test sapiens GitLabRestProvider file operations.

    These are the operations sapiens uses for:
    - execute-task.yaml: commit_file(), get_file()
    - post-merge-docs.yaml: commit_file()
    """

    async def test_commit_and_get_file(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can commit and retrieve files."""
        import time

        timestamp = int(time.time())
        branch_name = f"sapiens-file-test-{timestamp}"
        file_path = f"test-files/sapiens-test-{timestamp}.txt"

        # Create branch first
        await gitlab_provider.create_branch(branch_name, from_branch="main")

        try:
            # Commit a file
            result = await gitlab_provider.commit_file(
                path=file_path,
                content=f"Test content created at {timestamp}",
                message="Add test file via sapiens",
                branch=branch_name,
            )
            assert result  # Returns commit SHA or file path

            # Get the file back
            content = await gitlab_provider.get_file(file_path, ref=branch_name)
            assert f"Test content created at {timestamp}" in content

            # Update the file
            result = await gitlab_provider.commit_file(
                path=file_path,
                content="Updated content",
                message="Update test file via sapiens",
                branch=branch_name,
            )
            assert result

            # Verify update
            updated_content = await gitlab_provider.get_file(file_path, ref=branch_name)
            assert "Updated content" in updated_content

        finally:
            # Cleanup: delete branch
            await gitlab_provider.delete_branch(branch_name)


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabMergeRequestOperations:
    """Test sapiens GitLabRestProvider merge request operations.

    These are the operations sapiens uses for:
    - approved.yaml: create_pull_request()
    - needs-review.yaml: get_merge_request(), get_diff()
    - needs-fix.yaml: get_merge_request()
    - requires-qa.yaml: get_merge_request()
    """

    async def test_create_and_get_merge_request(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can create and retrieve merge requests."""
        import time

        timestamp = int(time.time())
        branch_name = f"sapiens-mr-test-{timestamp}"

        # Create branch with a change
        await gitlab_provider.create_branch(branch_name, from_branch="main")
        await gitlab_provider.commit_file(
            path=f"test-mr-file-{timestamp}.txt",
            content="Content for MR test",
            message="Add file for MR test",
            branch=branch_name,
        )

        try:
            # Create MR
            mr = await gitlab_provider.create_pull_request(
                title=f"[TEST] Sapiens MR test {timestamp}",
                body="This MR was created by sapiens integration tests.",
                head=branch_name,
                base="main",
                labels=["test-label"],
            )

            assert mr.number > 0
            assert "[TEST]" in mr.title

            # Get the MR back
            retrieved = await gitlab_provider.get_merge_request(mr.number)
            assert retrieved is not None
            assert retrieved.number == mr.number

            # Test get_pull_request alias
            pr = await gitlab_provider.get_pull_request(mr.number)
            assert pr.number == mr.number

        finally:
            # Cleanup: close MR and delete branch
            # Note: We can't easily close an MR via provider, so branch deletion will suffice
            await gitlab_provider.delete_branch(branch_name)

    async def test_get_diff(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can get diffs between branches."""
        import time

        timestamp = int(time.time())
        branch_name = f"sapiens-diff-test-{timestamp}"

        # Create branch with a change
        await gitlab_provider.create_branch(branch_name, from_branch="main")
        await gitlab_provider.commit_file(
            path=f"diff-test-file-{timestamp}.txt",
            content="Content to show in diff",
            message="Add file for diff test",
            branch=branch_name,
        )

        try:
            # Get diff
            diff = await gitlab_provider.get_diff(base="main", head=branch_name)
            assert diff  # Should have content
            assert "diff-test-file" in diff or "Content to show" in diff

        finally:
            await gitlab_provider.delete_branch(branch_name)


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.asyncio
class TestSapiensGitLabLabelOperations:
    """Test sapiens GitLabRestProvider label operations.

    These are the operations sapiens uses for automation setup.
    """

    async def test_setup_automation_labels(self, gitlab_provider: GitLabRestProvider) -> None:
        """Verify sapiens can create automation labels."""
        # Create some labels
        result = await gitlab_provider.setup_automation_labels(labels=["test-sapiens-label-1", "test-sapiens-label-2"])

        assert "test-sapiens-label-1" in result
        assert "test-sapiens-label-2" in result
        # IDs should be positive integers
        assert result["test-sapiens-label-1"] > 0
        assert result["test-sapiens-label-2"] > 0

        # Run again to verify idempotency
        result2 = await gitlab_provider.setup_automation_labels(labels=["test-sapiens-label-1", "test-sapiens-label-2"])
        assert result["test-sapiens-label-1"] == result2["test-sapiens-label-1"]
