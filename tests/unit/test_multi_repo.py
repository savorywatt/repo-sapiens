"""Tests for repo_sapiens/engine/multi_repo.py."""

from unittest.mock import MagicMock

import pytest

from repo_sapiens.engine.multi_repo import (
    CoordinationMode,
    MultiRepoOrchestrator,
    RepositoryStatus,
)


class TestCoordinationMode:
    """Tests for CoordinationMode enum."""

    def test_sequential_mode(self):
        """Should have sequential mode."""
        assert CoordinationMode.SEQUENTIAL == "sequential"

    def test_parallel_mode(self):
        """Should have parallel mode."""
        assert CoordinationMode.PARALLEL == "parallel"


class TestRepositoryStatus:
    """Tests for RepositoryStatus enum."""

    def test_all_statuses_exist(self):
        """Should have all expected statuses."""
        assert RepositoryStatus.PENDING == "pending"
        assert RepositoryStatus.IN_PROGRESS == "in_progress"
        assert RepositoryStatus.COMPLETED == "completed"
        assert RepositoryStatus.FAILED == "failed"
        assert RepositoryStatus.SKIPPED == "skipped"


class TestMultiRepoOrchestrator:
    """Tests for MultiRepoOrchestrator class."""

    def test_initialization(self):
        """Should initialize with repository configs."""
        configs = [
            {"name": "repo1", "url": "https://github.com/org/repo1"},
            {"name": "repo2", "url": "https://github.com/org/repo2"},
        ]
        orchestrator = MultiRepoOrchestrator(configs)

        assert len(orchestrator.repositories) == 2
        assert "repo1" in orchestrator.repositories
        assert "repo2" in orchestrator.repositories
        assert orchestrator.repositories["repo1"]["status"] == RepositoryStatus.PENDING

    def test_register_provider_success(self):
        """Should register provider for known repository."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)
        mock_provider = MagicMock()

        orchestrator.register_provider("repo1", mock_provider)

        assert orchestrator.providers["repo1"] == mock_provider

    def test_register_provider_unknown_repo(self):
        """Should raise error for unknown repository."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)
        mock_provider = MagicMock()

        with pytest.raises(ValueError, match="Unknown repository"):
            orchestrator.register_provider("unknown", mock_provider)

    @pytest.mark.asyncio
    async def test_get_repository_status(self):
        """Should return repository status."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        status = await orchestrator.get_repository_status("repo1")

        assert status["name"] == "repo1"
        assert status["status"] == "pending"
        assert "config" in status

    @pytest.mark.asyncio
    async def test_get_repository_status_unknown(self):
        """Should raise error for unknown repository."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        with pytest.raises(ValueError, match="Unknown repository"):
            await orchestrator.get_repository_status("unknown")

    @pytest.mark.asyncio
    async def test_get_overall_status_pending(self):
        """Should return overall status as in_progress when pending."""
        configs = [
            {"name": "repo1", "url": "https://github.com/org/repo1"},
            {"name": "repo2", "url": "https://github.com/org/repo2"},
        ]
        orchestrator = MultiRepoOrchestrator(configs)

        status = await orchestrator.get_overall_status()

        assert status["overall_status"] == "in_progress"
        assert "repo1" in status["repositories"]
        assert "repo2" in status["repositories"]

    @pytest.mark.asyncio
    async def test_get_overall_status_returns_status_dict(self):
        """Should return status dict with repositories."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        status = await orchestrator.get_overall_status()

        assert "overall_status" in status
        assert "repositories" in status
        assert "repo1" in status["repositories"]
        # Initial status is pending, which means in_progress overall
        assert status["repositories"]["repo1"] == "pending"

    def test_is_workflow_complete_closed_issue(self):
        """Should detect completed workflow from closed issue."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.state = "closed"
        issue.labels = []

        assert orchestrator._is_workflow_complete(issue) is True

    def test_is_workflow_complete_completed_label(self):
        """Should detect completed workflow from label."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.state = "open"
        issue.labels = ["completed"]

        assert orchestrator._is_workflow_complete(issue) is True

    def test_is_workflow_complete_merged_label(self):
        """Should detect completed workflow from merged label."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.state = "open"
        issue.labels = ["merged"]

        assert orchestrator._is_workflow_complete(issue) is True

    def test_is_workflow_complete_open_issue(self):
        """Should not detect completed for open issue without labels."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.state = "open"
        issue.labels = ["in-progress"]

        assert orchestrator._is_workflow_complete(issue) is False

    def test_is_workflow_failed_with_failed_label(self):
        """Should detect failed workflow from label."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.labels = ["failed"]

        assert orchestrator._is_workflow_failed(issue) is True

    def test_is_workflow_failed_with_needs_attention(self):
        """Should detect failed workflow from needs-attention label."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.labels = ["needs-attention"]

        assert orchestrator._is_workflow_failed(issue) is True

    def test_is_workflow_failed_normal_issue(self):
        """Should not detect failed for normal issue."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        issue = MagicMock()
        issue.labels = ["in-progress"]

        assert orchestrator._is_workflow_failed(issue) is False

    def test_get_workflow_config_returns_none(self):
        """Should return None for workflow config (not implemented)."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        result = orchestrator._get_workflow_config("any-workflow")

        assert result is None

    def test_create_cross_repo_issue_body(self):
        """Should format cross-repo issue body correctly."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)

        trigger_issue = MagicMock()
        trigger_issue.title = "Test Feature"
        trigger_issue.number = 42
        trigger_issue.body = "Feature description"

        context = {
            "source_repo": "main-repo",
            "additional_context": "Extra info",
        }

        body = orchestrator._create_cross_repo_issue_body(trigger_issue, "repo1", context)

        assert "Cross-Repository Workflow" in body
        assert "Test Feature" in body
        assert "#42" in body
        assert "main-repo" in body
        assert "Feature description" in body
        assert "Extra info" in body

    @pytest.mark.asyncio
    async def test_execute_cross_repo_workflow_unknown(self):
        """Should raise error for unknown workflow."""
        configs = [{"name": "repo1", "url": "https://github.com/org/repo1"}]
        orchestrator = MultiRepoOrchestrator(configs)
        trigger_issue = MagicMock()

        with pytest.raises(ValueError, match="Unknown workflow"):
            await orchestrator.execute_cross_repo_workflow("unknown-workflow", trigger_issue)
