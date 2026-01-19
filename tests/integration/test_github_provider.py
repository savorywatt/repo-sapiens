"""Integration tests for GitHub provider.

These tests verify the GitHubRestProvider can interact with GitHub's API
and that all operations required by Sapiens workflow templates work correctly.

Requires:
- SAPIENS_GITHUB_TOKEN environment variable set
- A test repository created (default: savorywatt/sapiens-test-repo)

Run with: uv run pytest tests/integration/test_github_provider.py -v -m integration

Workflow Coverage:
- needs-planning: create issue, add comment, update labels
- approved: read issue, create tasks, update labels
- execute-task: create branch, commit file, create PR, update labels
- needs-review: get diff, add review comment
- needs-fix: read issue, create comment, update labels
- requires-qa: read issue, post results comment
"""

from __future__ import annotations

import base64
import subprocess
import time
from collections.abc import Generator

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.github
class TestGitHubConnection:
    """Test basic GitHub connectivity."""

    def test_github_rate_limit(self, github_url: str, require_github: None) -> None:
        """Verify GitHub API is accessible via rate_limit endpoint."""
        response = httpx.get(f"{github_url}/rate_limit", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "rate" in data

    def test_github_auth(self, github_test_repo: dict) -> None:
        """Verify authentication works with provided token."""
        response = httpx.get(
            f"{github_test_repo['api_base']}/user",
            headers={"Authorization": f"Bearer {github_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "login" in data


@pytest.mark.integration
@pytest.mark.github
class TestGitHubRepository:
    """Test GitHub repository operations."""

    def test_get_repository(self, github_test_repo: dict) -> None:
        """Verify test repository exists and is accessible."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}",
            headers={"Authorization": f"Bearer {github_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name

    def test_list_branches(self, github_test_repo: dict) -> None:
        """Verify branches can be listed."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/branches",
            headers={"Authorization": f"Bearer {github_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_issues(self, github_test_repo: dict) -> None:
        """Verify issues can be listed."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers={"Authorization": f"Bearer {github_test_repo['token']}"},
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
@pytest.mark.github
class TestGitHubIssueWorkflow:
    """Test GitHub issue create/update/close workflow."""

    @pytest.fixture
    def test_issue(self, github_test_repo: dict) -> Generator[dict, None, None]:
        """Create a test issue and clean up after."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Create issue
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
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

        # Cleanup: close the issue
        httpx.patch(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue['number']}",
            headers=headers,
            json={"state": "closed"},
            timeout=10.0,
        )

    def test_create_issue(self, test_issue: dict) -> None:
        """Verify issue was created successfully."""
        assert test_issue["number"] > 0
        assert test_issue["title"] == "integration-test-issue"

    def test_add_comment(self, github_test_repo: dict, test_issue: dict) -> None:
        """Verify comments can be added to issues."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{test_issue['number']}/comments",
            headers=headers,
            json={"body": "Test comment from integration test"},
            timeout=10.0,
        )
        assert response.status_code == 201
        comment = response.json()
        assert "Test comment" in comment["body"]

    def test_add_label(self, github_test_repo: dict, test_issue: dict) -> None:
        """Verify labels can be added to issues."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # First ensure label exists (create if not)
        httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/labels",
            headers=headers,
            json={"name": "test-label", "color": "ff0000"},
            timeout=10.0,
        )  # Ignore if exists (422 error)

        # Add label to issue
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{test_issue['number']}/labels",
            headers=headers,
            json={"labels": ["test-label"]},
            timeout=10.0,
        )
        # GitHub returns 200 for adding labels
        assert response.status_code == 200

    def test_create_branch(self, github_test_repo: dict) -> None:
        """Verify branches can be created."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}
        branch_name = f"test-branch-{int(time.time())}"

        # Get the SHA of the default branch (main or master)
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/main",
            headers=headers,
            timeout=10.0,
        )
        if response.status_code == 404:
            # Try master instead
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/master",
                headers=headers,
                timeout=10.0,
            )

        if response.status_code != 200:
            pytest.skip("Could not find default branch")

        sha = response.json()["object"]["sha"]

        # Create the branch
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            timeout=10.0,
        )
        assert response.status_code == 201

        # Cleanup: delete the branch
        httpx.delete(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs/heads/{branch_name}",
            headers=headers,
            timeout=10.0,
        )


@pytest.mark.integration
@pytest.mark.github
class TestGitHubLabelManagement:
    """Test label operations required by Sapiens workflows.

    Workflows like needs-planning and approved need to:
    - Add labels (needs-planning, awaiting-approval, etc.)
    - Remove labels after processing
    """

    def test_remove_label(self, github_test_repo: dict) -> None:
        """Verify labels can be removed from issues."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Create a test issue
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers=headers,
            json={"title": "label-removal-test", "body": "Testing label removal"},
            timeout=10.0,
        )
        assert response.status_code == 201
        issue = response.json()
        issue_number = issue["number"]

        try:
            # Ensure label exists
            httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/labels",
                headers=headers,
                json={"name": "test-remove-label", "color": "0000ff"},
                timeout=10.0,
            )

            # Add label to issue
            response = httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/labels",
                headers=headers,
                json={"labels": ["test-remove-label"]},
                timeout=10.0,
            )
            assert response.status_code == 200

            # Remove label from issue
            response = httpx.delete(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/labels/test-remove-label",
                headers=headers,
                timeout=10.0,
            )
            # 200 on success, 404 if label wasn't on issue
            assert response.status_code in [200, 404]

            # Verify label is gone
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                timeout=10.0,
            )
            labels = [lbl["name"] for lbl in response.json().get("labels", [])]
            assert "test-remove-label" not in labels

        finally:
            # Cleanup
            httpx.patch(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                json={"state": "closed"},
                timeout=10.0,
            )

    def test_replace_labels(self, github_test_repo: dict) -> None:
        """Verify labels can be replaced (used when transitioning workflow states)."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Create test issue
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers=headers,
            json={"title": "label-replace-test", "body": "Testing label replacement"},
            timeout=10.0,
        )
        assert response.status_code == 201
        issue_number = response.json()["number"]

        try:
            # Ensure labels exist
            for label_name, color in [("state-a", "ff0000"), ("state-b", "00ff00")]:
                httpx.post(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/labels",
                    headers=headers,
                    json={"name": label_name, "color": color},
                    timeout=10.0,
                )

            # Add initial label
            httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/labels",
                headers=headers,
                json={"labels": ["state-a"]},
                timeout=10.0,
            )

            # Replace with new label (PUT replaces all labels)
            response = httpx.put(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/labels",
                headers=headers,
                json={"labels": ["state-b"]},
                timeout=10.0,
            )
            assert response.status_code == 200

            # Verify replacement
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                timeout=10.0,
            )
            labels = [lbl["name"] for lbl in response.json().get("labels", [])]
            assert "state-b" in labels
            assert "state-a" not in labels

        finally:
            httpx.patch(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                json={"state": "closed"},
                timeout=10.0,
            )


@pytest.mark.integration
@pytest.mark.github
class TestGitHubIssueDetails:
    """Test reading issue details required by Sapiens workflows.

    All workflows need to read issue details to understand the task.
    """

    def test_get_single_issue(self, github_test_repo: dict) -> None:
        """Verify a single issue can be fetched with full details."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Create test issue with body
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers=headers,
            json={
                "title": "detailed-issue-test",
                "body": "## Task\nImplement feature X\n\n## Acceptance Criteria\n- Works correctly",
            },
            timeout=10.0,
        )
        assert response.status_code == 201
        issue_number = response.json()["number"]

        try:
            # Fetch the issue
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                timeout=10.0,
            )
            assert response.status_code == 200
            issue = response.json()

            # Verify all fields needed by workflows
            assert issue["number"] == issue_number
            assert issue["title"] == "detailed-issue-test"
            assert "## Task" in issue["body"]
            assert "state" in issue
            assert "labels" in issue
            assert "user" in issue

        finally:
            httpx.patch(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                json={"state": "closed"},
                timeout=10.0,
            )

    def test_get_issue_comments(self, github_test_repo: dict) -> None:
        """Verify issue comments can be fetched (needed for reading plans/proposals)."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Create test issue
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
            headers=headers,
            json={"title": "comments-test", "body": "Testing comment retrieval"},
            timeout=10.0,
        )
        issue_number = response.json()["number"]

        try:
            # Add a comment
            httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/comments",
                headers=headers,
                json={"body": "## Plan Proposal\n\n1. Step one\n2. Step two"},
                timeout=10.0,
            )

            # Fetch comments
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/comments",
                headers=headers,
                timeout=10.0,
            )
            assert response.status_code == 200
            comments = response.json()
            assert len(comments) >= 1
            assert "## Plan Proposal" in comments[0]["body"]

        finally:
            httpx.patch(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                headers=headers,
                json={"state": "closed"},
                timeout=10.0,
            )


@pytest.mark.integration
@pytest.mark.github
class TestGitHubCodeReview:
    """Test operations required by needs-review workflow.

    Code review needs to:
    - Get diff between branches
    - Read file contents
    - Post review comments
    """

    def test_get_compare_diff(self, github_test_repo: dict) -> None:
        """Verify branch comparison works (needed for code review)."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}
        branch_name = f"test-diff-{int(time.time())}"

        # Get default branch SHA
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/main",
            headers=headers,
            timeout=10.0,
        )
        if response.status_code == 404:
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/master",
                headers=headers,
                timeout=10.0,
            )
        base_branch = "main" if "main" in response.url.path else "master"
        sha = response.json()["object"]["sha"]

        # Create test branch
        httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            timeout=10.0,
        )

        try:
            # Add a file to the branch
            file_content = base64.b64encode(b"# Test file\nprint('hello')").decode()
            httpx.put(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/contents/test-diff-file.py",
                headers=headers,
                json={
                    "message": "Add test file for diff",
                    "content": file_content,
                    "branch": branch_name,
                },
                timeout=10.0,
            )

            # Compare branches
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/compare/{base_branch}...{branch_name}",
                headers=headers,
                timeout=10.0,
            )
            assert response.status_code == 200
            comparison = response.json()

            # Verify comparison has expected fields
            assert "files" in comparison
            assert "commits" in comparison
            assert len(comparison["files"]) >= 1
            assert comparison["files"][0]["filename"] == "test-diff-file.py"

        finally:
            # Cleanup: delete branch
            httpx.delete(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs/heads/{branch_name}",
                headers=headers,
                timeout=10.0,
            )

    def test_get_file_contents(self, github_test_repo: dict) -> None:
        """Verify file contents can be read (needed for code analysis)."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}

        # Try to get README or any existing file
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/contents/README.md",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            content_data = response.json()
            assert "content" in content_data
            assert content_data["encoding"] == "base64"
            # Decode and verify it's readable
            decoded = base64.b64decode(content_data["content"]).decode("utf-8")
            assert len(decoded) > 0
        else:
            # No README, that's ok - test passes if API works
            assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.github
class TestGitHubPullRequest:
    """Test PR operations required by execute-task workflow.

    Execute-task needs to:
    - Create branch
    - Commit files
    - Create PR
    - Get PR details
    """

    def test_full_pr_workflow(self, github_test_repo: dict) -> None:
        """Test complete PR creation workflow (branch → commit → PR)."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}
        timestamp = int(time.time())
        branch_name = f"test-pr-workflow-{timestamp}"

        # Get default branch
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}",
            headers=headers,
            timeout=10.0,
        )
        default_branch = response.json().get("default_branch", "main")

        # Get SHA
        response = httpx.get(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/{default_branch}",
            headers=headers,
            timeout=10.0,
        )
        sha = response.json()["object"]["sha"]

        # Create branch
        response = httpx.post(
            f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            timeout=10.0,
        )
        assert response.status_code == 201

        pr_number = None
        try:
            # Commit a file
            file_content = base64.b64encode(f"# Auto-generated test file\nTimestamp: {timestamp}\n".encode()).decode()
            response = httpx.put(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/contents/.sapiens/test-{timestamp}.txt",
                headers=headers,
                json={
                    "message": f"test: Add test file ({timestamp})",
                    "content": file_content,
                    "branch": branch_name,
                },
                timeout=10.0,
            )
            assert response.status_code == 201

            # Create PR
            response = httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls",
                headers=headers,
                json={
                    "title": f"[Test] PR workflow test {timestamp}",
                    "body": "Automated test PR - will be closed immediately",
                    "head": branch_name,
                    "base": default_branch,
                },
                timeout=10.0,
            )
            assert response.status_code == 201
            pr = response.json()
            pr_number = pr["number"]

            # Verify PR details
            assert pr["state"] == "open"
            assert pr["head"]["ref"] == branch_name
            assert pr["base"]["ref"] == default_branch

            # Get PR (verify we can fetch it)
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls/{pr_number}",
                headers=headers,
                timeout=10.0,
            )
            assert response.status_code == 200

        finally:
            # Cleanup: close PR if created
            if pr_number:
                httpx.patch(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls/{pr_number}",
                    headers=headers,
                    json={"state": "closed"},
                    timeout=10.0,
                )

            # Delete branch
            httpx.delete(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs/heads/{branch_name}",
                headers=headers,
                timeout=10.0,
            )


@pytest.mark.integration
@pytest.mark.github
class TestSapiensProcessLabel:
    """Test sapiens process-label command classification.

    This verifies the CLI can correctly classify label events
    that would trigger different workflows.
    """

    @pytest.fixture
    def github_config_file(self, github_test_repo: dict, tmp_path) -> str:
        """Create a temporary config file for GitHub."""
        config_content = f"""
git_provider:
  provider_type: github
  base_url: "{github_test_repo['api_base']}"
  api_token: "{github_test_repo['token']}"

repository:
  owner: "{github_test_repo['owner']}"
  name: "{github_test_repo['name']}"
  default_branch: main

agent_provider:
  provider_type: ollama
  base_url: "http://localhost:11434"
  model: "qwen3:8b"

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(config_content)
        return str(config_path)

    def test_process_label_needs_planning(self, github_config_file: str) -> None:
        """Test process-label classifies needs-planning correctly."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "sapiens",
                "--config",
                github_config_file,
                "process-label",
                "--event-type",
                "issues.labeled",
                "--label",
                "needs-planning",
                "--issue",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,  # Prevent stdin reading
        )

        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Should process: True" in result.stdout or "Trigger type:" in result.stdout

    def test_process_label_approved(self, github_config_file: str) -> None:
        """Test process-label classifies approved correctly."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "sapiens",
                "--config",
                github_config_file,
                "process-label",
                "--event-type",
                "issues.labeled",
                "--label",
                "approved",
                "--issue",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )

        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Trigger type:" in result.stdout

    def test_process_label_execute(self, github_config_file: str) -> None:
        """Test process-label classifies execute correctly."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "sapiens",
                "--config",
                github_config_file,
                "process-label",
                "--event-type",
                "issues.labeled",
                "--label",
                "execute",
                "--issue",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )

        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Trigger type:" in result.stdout

    def test_process_label_needs_review(self, github_config_file: str) -> None:
        """Test process-label classifies needs-review correctly."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "sapiens",
                "--config",
                github_config_file,
                "process-label",
                "--event-type",
                "issues.labeled",
                "--label",
                "needs-review",
                "--issue",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )

        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Trigger type:" in result.stdout

    def test_process_label_unknown_skipped(self, github_config_file: str) -> None:
        """Test process-label skips unknown labels."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "sapiens",
                "--config",
                github_config_file,
                "process-label",
                "--event-type",
                "issues.labeled",
                "--label",
                "random-unrelated-label",
                "--issue",
                "1",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )

        # Should succeed but indicate skip or no handler
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


@pytest.mark.integration
@pytest.mark.github
class TestSapiensWorkflowReadiness:
    """Comprehensive test that validates all operations needed by workflows.

    This test creates resources and validates the full sequence of operations
    that would be performed by the Sapiens workflow templates.
    """

    def test_workflow_operations_checklist(self, github_test_repo: dict) -> None:
        """Validate all GitHub API operations required by Sapiens workflows."""
        owner = github_test_repo["owner"]
        name = github_test_repo["name"]
        headers = {"Authorization": f"Bearer {github_test_repo['token']}"}
        timestamp = int(time.time())

        results = {}
        branch_name = f"workflow-test-{timestamp}"
        issue_number = None
        pr_number = None

        try:
            # 1. Create issue (needs-planning trigger)
            response = httpx.post(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues",
                headers=headers,
                json={
                    "title": f"[Workflow Test] {timestamp}",
                    "body": "Testing all workflow operations",
                    "labels": ["needs-planning"],
                },
                timeout=10.0,
            )
            results["create_issue"] = response.status_code == 201
            issue_number = response.json()["number"] if response.status_code == 201 else None

            # 2. Read issue details
            if issue_number:
                response = httpx.get(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                    headers=headers,
                    timeout=10.0,
                )
                results["read_issue"] = response.status_code == 200

            # 3. Add comment (plan proposal)
            if issue_number:
                response = httpx.post(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/comments",
                    headers=headers,
                    json={"body": "## Plan Proposal\n\n- [ ] Task 1\n- [ ] Task 2"},
                    timeout=10.0,
                )
                results["add_comment"] = response.status_code == 201

            # 4. Update labels (transition to awaiting-approval)
            if issue_number:
                # Ensure label exists
                httpx.post(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/labels",
                    headers=headers,
                    json={"name": "awaiting-approval", "color": "fbca04"},
                    timeout=10.0,
                )
                response = httpx.put(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}/labels",
                    headers=headers,
                    json={"labels": ["awaiting-approval"]},
                    timeout=10.0,
                )
                results["update_labels"] = response.status_code == 200

            # 5. Get default branch SHA
            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}",
                headers=headers,
                timeout=10.0,
            )
            default_branch = response.json().get("default_branch", "main")

            response = httpx.get(
                f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/ref/heads/{default_branch}",
                headers=headers,
                timeout=10.0,
            )
            results["get_branch_sha"] = response.status_code == 200
            sha = response.json()["object"]["sha"] if response.status_code == 200 else None

            # 6. Create branch (execute-task)
            if sha:
                response = httpx.post(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs",
                    headers=headers,
                    json={"ref": f"refs/heads/{branch_name}", "sha": sha},
                    timeout=10.0,
                )
                results["create_branch"] = response.status_code == 201

            # 7. Commit file
            if results.get("create_branch"):
                content = base64.b64encode(f"# Test {timestamp}".encode()).decode()
                response = httpx.put(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/contents/.sapiens/workflow-test-{timestamp}.txt",
                    headers=headers,
                    json={
                        "message": f"feat: Implement feature ({timestamp})",
                        "content": content,
                        "branch": branch_name,
                    },
                    timeout=10.0,
                )
                results["commit_file"] = response.status_code == 201

            # 8. Create PR
            if results.get("commit_file"):
                response = httpx.post(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls",
                    headers=headers,
                    json={
                        "title": f"feat: Workflow test {timestamp}",
                        "body": f"Closes #{issue_number}" if issue_number else "Test PR",
                        "head": branch_name,
                        "base": default_branch,
                    },
                    timeout=10.0,
                )
                results["create_pr"] = response.status_code == 201
                pr_number = response.json()["number"] if response.status_code == 201 else None

            # 9. Get diff (needs-review)
            if results.get("create_branch"):
                response = httpx.get(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/compare/{default_branch}...{branch_name}",
                    headers=headers,
                    timeout=10.0,
                )
                results["get_diff"] = response.status_code == 200

            # 10. Close PR
            if pr_number:
                response = httpx.patch(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls/{pr_number}",
                    headers=headers,
                    json={"state": "closed"},
                    timeout=10.0,
                )
                results["close_pr"] = response.status_code == 200

            # 11. Delete branch
            if results.get("create_branch"):
                response = httpx.delete(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs/heads/{branch_name}",
                    headers=headers,
                    timeout=10.0,
                )
                results["delete_branch"] = response.status_code == 204

            # 12. Close issue
            if issue_number:
                response = httpx.patch(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                    headers=headers,
                    json={"state": "closed"},
                    timeout=10.0,
                )
                results["close_issue"] = response.status_code == 200

        finally:
            # Ensure cleanup even if tests fail
            if pr_number:
                httpx.patch(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/pulls/{pr_number}",
                    headers=headers,
                    json={"state": "closed"},
                    timeout=10.0,
                )
            if results.get("create_branch"):
                httpx.delete(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/git/refs/heads/{branch_name}",
                    headers=headers,
                    timeout=10.0,
                )
            if issue_number:
                httpx.patch(
                    f"{github_test_repo['api_base']}/repos/{owner}/{name}/issues/{issue_number}",
                    headers=headers,
                    json={"state": "closed"},
                    timeout=10.0,
                )

        # Assert all operations succeeded
        print("\n=== Workflow Operations Results ===")
        for op, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {op}")

        failed = [op for op, success in results.items() if not success]
        assert not failed, f"Failed operations: {failed}"
