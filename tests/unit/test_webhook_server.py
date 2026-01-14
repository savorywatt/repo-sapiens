"""Tests for repo_sapiens/webhook_server.py."""

from unittest.mock import MagicMock, patch

import pytest

# Skip if fastapi not available
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from repo_sapiens.webhook_server import (
    app,
    extract_plan_id,
    handle_issue_event,
    handle_push_event,
)


class TestExtractPlanId:
    """Tests for extract_plan_id function."""

    def test_extract_simple_plan_id(self):
        """Should extract plan ID from standard path."""
        assert extract_plan_id("plans/42-feature.md") == "42"

    def test_extract_plan_id_with_longer_number(self):
        """Should extract multi-digit plan ID."""
        assert extract_plan_id("plans/12345-big-feature.md") == "12345"

    def test_extract_plan_id_with_subdirectory(self):
        """Should extract plan ID from nested path."""
        assert extract_plan_id("plans/archive/99-old-plan.md") == "99"

    def test_no_plan_id_in_path(self):
        """Should return None for paths without plan ID pattern."""
        assert extract_plan_id("src/main.py") is None
        assert extract_plan_id("plans/readme.md") is None

    def test_non_plans_directory(self):
        """Should return None for non-plans directories."""
        assert extract_plan_id("docs/42-guide.md") is None

    def test_plan_id_with_complex_name(self):
        """Should extract ID regardless of feature name complexity."""
        assert extract_plan_id("plans/123-some-complex-feature-name.md") == "123"

    def test_extract_plan_id_deeply_nested(self):
        """Should extract plan ID from deeply nested path."""
        assert extract_plan_id("plans/2024/q1/sprint-1/7-task.md") == "7"

    def test_extract_plan_id_single_digit(self):
        """Should extract single-digit plan ID."""
        assert extract_plan_id("plans/1-simple.md") == "1"

    def test_extract_plan_id_no_dash(self):
        """Should return None when no dash after number."""
        assert extract_plan_id("plans/42.md") is None
        assert extract_plan_id("plans/42_feature.md") is None


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self):
        """Should return healthy status."""
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "automation-webhook"


class TestGiteaWebhookEndpoint:
    """Tests for /webhook/gitea endpoint."""

    def test_webhook_missing_event_header(self):
        """Should return 400 when X-Gitea-Event header is missing."""
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/webhook/gitea", json={"action": "opened"})

        assert response.status_code == 400
        assert "Missing X-Gitea-Event header" in response.json()["detail"]

    def test_webhook_issues_event(self):
        """Should handle issues event successfully."""
        client = TestClient(app, raise_server_exceptions=False)

        payload = {
            "action": "opened",
            "issue": {"number": 42, "title": "Test issue"},
        }

        response = client.post(
            "/webhook/gitea",
            json=payload,
            headers={"X-Gitea-Event": "issues"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["event_type"] == "issues"

    def test_webhook_push_event(self):
        """Should handle push event successfully."""
        client = TestClient(app, raise_server_exceptions=False)

        payload = {
            "ref": "refs/heads/main",
            "commits": [{"modified": ["src/main.py"]}],
        }

        response = client.post(
            "/webhook/gitea",
            json=payload,
            headers={"X-Gitea-Event": "push"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["event_type"] == "push"

    def test_webhook_unhandled_event_type(self):
        """Should handle unrecognized event types gracefully."""
        client = TestClient(app, raise_server_exceptions=False)

        payload = {"data": "test"}

        response = client.post(
            "/webhook/gitea",
            json=payload,
            headers={"X-Gitea-Event": "pull_request"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["event_type"] == "pull_request"

    def test_webhook_repo_sapiens_error(self):
        """Should return 422 for RepoSapiensError."""
        from repo_sapiens.exceptions import RepoSapiensError

        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "repo_sapiens.webhook_server.handle_issue_event",
            side_effect=RepoSapiensError("Test error"),
        ):
            payload = {"action": "opened", "issue": {"number": 1}}

            response = client.post(
                "/webhook/gitea",
                json=payload,
                headers={"X-Gitea-Event": "issues"},
            )

            assert response.status_code == 422
            assert "Test error" in response.json()["detail"]

    def test_webhook_unexpected_error(self):
        """Should return 500 for unexpected errors."""
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "repo_sapiens.webhook_server.handle_issue_event",
            side_effect=RuntimeError("Unexpected error"),
        ):
            payload = {"action": "opened", "issue": {"number": 1}}

            response = client.post(
                "/webhook/gitea",
                json=payload,
                headers={"X-Gitea-Event": "issues"},
            )

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]


class TestHandleIssueEvent:
    """Tests for handle_issue_event function."""

    @pytest.mark.asyncio
    async def test_handle_issue_event_basic(self):
        """Should process issue event without error."""
        payload = {
            "action": "opened",
            "issue": {
                "number": 42,
                "title": "Test issue",
                "body": "Issue body",
            },
        }

        # Should not raise any exception
        await handle_issue_event(payload)

    @pytest.mark.asyncio
    async def test_handle_issue_event_missing_action(self):
        """Should handle missing action gracefully."""
        payload = {
            "issue": {"number": 42},
        }

        # Should not raise, action will be None
        await handle_issue_event(payload)

    @pytest.mark.asyncio
    async def test_handle_issue_event_missing_issue(self):
        """Should handle missing issue data gracefully."""
        payload = {"action": "opened"}

        # Should not raise, issue will be empty dict
        await handle_issue_event(payload)

    @pytest.mark.asyncio
    async def test_handle_issue_event_closed_action(self):
        """Should handle closed action."""
        payload = {
            "action": "closed",
            "issue": {"number": 42},
        }

        await handle_issue_event(payload)

    @pytest.mark.asyncio
    async def test_handle_issue_event_labeled_action(self):
        """Should handle labeled action."""
        payload = {
            "action": "labeled",
            "issue": {"number": 42},
            "label": {"name": "needs-review"},
        }

        await handle_issue_event(payload)


class TestHandlePushEvent:
    """Tests for handle_push_event function."""

    @pytest.mark.asyncio
    async def test_handle_push_event_basic(self):
        """Should process push event without error."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "modified": ["src/main.py"],
                },
            ],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_with_plan_modification(self):
        """Should detect plan file modifications."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "modified": ["plans/42-new-feature.md"],
                },
            ],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_multiple_commits(self):
        """Should handle multiple commits."""
        payload = {
            "ref": "refs/heads/feature",
            "commits": [
                {"id": "commit1", "modified": ["file1.py"]},
                {"id": "commit2", "modified": ["plans/1-task.md"]},
                {"id": "commit3", "modified": ["plans/2-task.md"]},
            ],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_no_commits(self):
        """Should handle empty commits list."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_missing_ref(self):
        """Should handle missing ref gracefully."""
        payload = {
            "commits": [{"modified": ["file.py"]}],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_no_modified_files(self):
        """Should handle commit with no modified files."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {"id": "abc123", "added": ["new_file.py"]},
            ],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_non_plan_files(self):
        """Should ignore non-plan file modifications."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "modified": [
                        "src/main.py",
                        "tests/test_main.py",
                        "docs/readme.md",
                    ],
                },
            ],
        }

        await handle_push_event(payload)

    @pytest.mark.asyncio
    async def test_handle_push_event_archived_plan(self):
        """Should handle archived plan modifications."""
        payload = {
            "ref": "refs/heads/main",
            "commits": [
                {
                    "id": "abc123",
                    "modified": ["plans/archive/42-old-feature.md"],
                },
            ],
        }

        await handle_push_event(payload)


class TestStartupEvent:
    """Tests for startup event handler."""

    @pytest.mark.asyncio
    async def test_startup_configuration_error(self):
        """Should handle ConfigurationError on startup."""
        from repo_sapiens.exceptions import ConfigurationError
        from repo_sapiens.webhook_server import startup

        with patch(
            "repo_sapiens.webhook_server.AutomationSettings.from_yaml",
            side_effect=ConfigurationError("Config not found"),
        ):
            with pytest.raises(ConfigurationError):
                await startup()

    @pytest.mark.asyncio
    async def test_startup_unexpected_error(self):
        """Should handle unexpected errors on startup."""
        from repo_sapiens.webhook_server import startup

        with patch(
            "repo_sapiens.webhook_server.AutomationSettings.from_yaml",
            side_effect=FileNotFoundError("File not found"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await startup()

            assert "Webhook startup failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_startup_success(self):
        """Should initialize settings on successful startup."""
        import repo_sapiens.webhook_server as ws
        from repo_sapiens.webhook_server import startup

        mock_settings = MagicMock()

        with patch(
            "repo_sapiens.webhook_server.AutomationSettings.from_yaml",
            return_value=mock_settings,
        ):
            await startup()

            assert ws.settings == mock_settings


class TestAppConfiguration:
    """Tests for FastAPI app configuration."""

    def test_app_title(self):
        """Should have correct app title."""
        assert app.title == "Gitea Automation Webhook Server"

    def test_app_routes_exist(self):
        """Should have expected routes configured."""
        routes = [route.path for route in app.routes]

        assert "/webhook/gitea" in routes
        assert "/health" in routes
