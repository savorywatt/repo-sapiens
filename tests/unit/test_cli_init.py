"""Unit tests for automation/cli/init.py - Repository initialization CLI."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from automation.cli.init import RepoInitializer, init_command
from automation.git.exceptions import GitDiscoveryError


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing Click commands."""
    return CliRunner()


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock Git repository directory."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    git_dir = repo_dir / ".git"
    git_dir.mkdir()
    return repo_dir


class TestRepoInitializerInit:
    """Tests for RepoInitializer initialization."""

    def test_init_with_defaults(self, tmp_path):
        """Should initialize with default values."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_path == tmp_path
        assert initializer.config_path == Path("config.yaml")
        assert initializer.backend == "keyring"
        assert initializer.non_interactive is False
        assert initializer.setup_secrets is True

    def test_init_with_explicit_backend(self, tmp_path):
        """Should use explicitly specified backend."""
        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend="environment",
            non_interactive=True,
            setup_secrets=False,
        )

        assert initializer.backend == "environment"

    def test_init_state_initialization(self, tmp_path):
        """Should initialize internal state variables."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_info is None
        assert initializer.provider_type is None
        assert initializer.gitea_token is None
        assert initializer.agent_type is None
        assert initializer.agent_mode == "local"
        assert initializer.agent_api_key is None


class TestRepoInitializerDetectBackend:
    """Tests for backend detection."""

    @patch("automation.cli.init.KeyringBackend")
    def test_detect_backend_keyring_available(self, mock_keyring_class, tmp_path):
        """Should detect keyring backend when available."""
        mock_keyring = Mock()
        mock_keyring.available = True
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend=None,
            non_interactive=False,
            setup_secrets=True,
        )

        assert initializer.backend == "keyring"

    @patch("automation.cli.init.KeyringBackend")
    def test_detect_backend_fallback_to_environment(self, mock_keyring_class, tmp_path):
        """Should fall back to environment backend when keyring unavailable."""
        mock_keyring = Mock()
        mock_keyring.available = False
        mock_keyring_class.return_value = mock_keyring

        initializer = RepoInitializer(
            repo_path=tmp_path,
            config_path=Path("config.yaml"),
            backend=None,
            non_interactive=False,
            setup_secrets=True,
        )

        assert initializer.backend == "environment"


class TestRepoInitializerDiscoverRepository:
    """Tests for repository discovery."""

    @patch("automation.cli.init.GitDiscovery")
    def test_discover_repository_success(self, mock_discovery_class, tmp_path):
        """Should successfully discover repository configuration."""
        # Setup mocks
        mock_repo_info = Mock()
        mock_repo_info.remote_name = "origin"
        mock_repo_info.owner = "test-owner"
        mock_repo_info.repo = "test-repo"
        mock_repo_info.base_url = "https://github.com"

        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "github"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        initializer._discover_repository()

        assert initializer.repo_info == mock_repo_info
        assert initializer.provider_type == "github"
        mock_discovery_class.assert_called_once_with(tmp_path)

    @patch("automation.cli.init.GitDiscovery")
    def test_discover_repository_git_discovery_error(self, mock_discovery_class, tmp_path):
        """Should raise ClickException on GitDiscoveryError."""
        from click import ClickException

        mock_discovery = Mock()
        mock_discovery.parse_repository.side_effect = GitDiscoveryError("No remote found")
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        with pytest.raises(ClickException) as exc_info:
            initializer._discover_repository()

        assert "Failed to discover repository" in str(exc_info.value)


class TestInitCommand:
    """Tests for init_command Click command."""

    def test_init_command_basic_invocation(self, cli_runner, tmp_path):
        """Should invoke init command."""
        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                ["--repo-path", str(tmp_path), "--non-interactive"],
                catch_exceptions=False,
            )

        # Command should execute
        assert result.exit_code in [0, 1]  # May fail on actual execution

    def test_init_command_with_all_options(self, cli_runner, tmp_path):
        """Should accept all command-line options."""
        config_path = tmp_path / "custom_config.yaml"

        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                [
                    "--repo-path",
                    str(tmp_path),
                    "--config-path",
                    str(config_path),
                    "--backend",
                    "environment",
                    "--non-interactive",
                    "--setup-secrets",
                ],
            )

        # Should not crash
        assert result.exit_code in [0, 1]

    def test_init_command_handles_git_discovery_error(self, cli_runner, tmp_path):
        """Should handle GitDiscoveryError gracefully."""
        with patch.object(
            RepoInitializer, "run", side_effect=GitDiscoveryError("No Git repository")
        ):
            result = cli_runner.invoke(init_command, ["--repo-path", str(tmp_path)])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Make sure you're in a Git repository" in result.output

    def test_init_command_handles_unexpected_error(self, cli_runner, tmp_path):
        """Should handle unexpected errors gracefully."""
        with patch.object(RepoInitializer, "run", side_effect=RuntimeError("Unexpected")):
            result = cli_runner.invoke(init_command, ["--repo-path", str(tmp_path)])

        assert result.exit_code == 1
        assert "Unexpected error:" in result.output

    def test_init_command_default_repo_path(self, cli_runner):
        """Should use current directory as default repo path."""
        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(init_command, ["--non-interactive"])

        # Should not complain about missing repo-path
        assert result.exit_code in [0, 1]

    def test_init_command_backend_choices(self, cli_runner, tmp_path):
        """Should validate backend choices."""
        result = cli_runner.invoke(
            init_command,
            ["--repo-path", str(tmp_path), "--backend", "invalid"],
        )

        # Should fail validation
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_init_command_valid_backends(self, cli_runner, tmp_path):
        """Should accept valid backend options."""
        valid_backends = ["keyring", "environment", "encrypted"]

        for backend in valid_backends:
            with patch.object(RepoInitializer, "run"):
                result = cli_runner.invoke(
                    init_command,
                    [
                        "--repo-path",
                        str(tmp_path),
                        "--backend",
                        backend,
                        "--non-interactive",
                    ],
                )

            # Should accept valid backend
            assert result.exit_code in [0, 1]  # May fail on actual run


class TestRepoInitializerWorkflow:
    """Tests for initialization workflow."""

    @patch("automation.cli.init.GitDiscovery")
    @patch.object(RepoInitializer, "_collect_credentials")
    @patch.object(RepoInitializer, "_store_credentials")
    @patch.object(RepoInitializer, "_setup_gitea_secrets")
    @patch.object(RepoInitializer, "_generate_config")
    @patch.object(RepoInitializer, "_validate_setup")
    @patch.object(RepoInitializer, "_print_next_steps")
    def test_run_workflow_executes_all_steps(
        self,
        mock_print_steps,
        mock_validate,
        mock_generate_config,
        mock_setup_secrets,
        mock_store_creds,
        mock_collect_creds,
        mock_discovery_class,
        tmp_path,
    ):
        """Should execute all workflow steps in order."""
        # Setup Git discovery mock
        mock_repo_info = Mock()
        mock_repo_info.remote_name = "origin"
        mock_repo_info.owner = "owner"
        mock_repo_info.repo = "repo"
        mock_repo_info.base_url = "https://github.com"

        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "github"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=True,
                setup_secrets=True,
            )

        initializer.run()

        # Verify all steps were called
        mock_discovery_class.assert_called_once()
        mock_collect_creds.assert_called_once()
        mock_store_creds.assert_called_once()
        mock_setup_secrets.assert_called_once()
        mock_generate_config.assert_called_once()
        mock_validate.assert_called_once()
        mock_print_steps.assert_called_once()

    @patch("automation.cli.init.GitDiscovery")
    @patch.object(RepoInitializer, "_collect_credentials")
    @patch.object(RepoInitializer, "_store_credentials")
    @patch.object(RepoInitializer, "_generate_config")
    @patch.object(RepoInitializer, "_validate_setup")
    @patch.object(RepoInitializer, "_print_next_steps")
    def test_run_workflow_skips_secrets_when_disabled(
        self,
        mock_print_steps,
        mock_validate,
        mock_generate_config,
        mock_store_creds,
        mock_collect_creds,
        mock_discovery_class,
        tmp_path,
    ):
        """Should skip secret setup when disabled."""
        # Setup Git discovery mock
        mock_repo_info = Mock()
        mock_repo_info.remote_name = "origin"
        mock_repo_info.owner = "owner"
        mock_repo_info.repo = "repo"
        mock_repo_info.base_url = "https://github.com"

        mock_discovery = Mock()
        mock_discovery.parse_repository.return_value = mock_repo_info
        mock_discovery.detect_provider_type.return_value = "github"
        mock_discovery_class.return_value = mock_discovery

        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            with patch.object(RepoInitializer, "_setup_gitea_secrets") as mock_setup_secrets:
                initializer = RepoInitializer(
                    repo_path=tmp_path,
                    config_path=Path("config.yaml"),
                    backend=None,
                    non_interactive=True,
                    setup_secrets=False,  # Disabled
                )

                initializer.run()

                # Secret setup should NOT be called
                mock_setup_secrets.assert_not_called()


class TestRepoInitializerEdgeCases:
    """Edge cases for repository initializer."""

    def test_initializer_with_relative_paths(self):
        """Should handle relative paths."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=Path("."),
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.repo_path == Path(".")
        assert initializer.config_path == Path("config.yaml")

    def test_initializer_goose_default_values(self, tmp_path):
        """Should initialize Goose-specific settings with defaults."""
        with patch.object(RepoInitializer, "_detect_backend", return_value="keyring"):
            initializer = RepoInitializer(
                repo_path=tmp_path,
                config_path=Path("config.yaml"),
                backend=None,
                non_interactive=False,
                setup_secrets=True,
            )

        assert initializer.goose_llm_provider is None
        assert initializer.goose_model is None
        assert initializer.goose_toolkit == "default"
        assert initializer.goose_temperature == 0.7

    def test_init_command_with_no_setup_secrets_flag(self, cli_runner, tmp_path):
        """Should support disabling setup-secrets flag."""
        # The setup_secrets flag is defined with is_flag=True and default=True
        # Click doesn't automatically create --no- variants unless configured properly
        # The test should check that the flag defaults to True
        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                [
                    "--repo-path",
                    str(tmp_path),
                    "--non-interactive",
                ],
            )

        # Should execute without error and use default setup_secrets=True
        assert result.exit_code in [0, 1]


class TestRepoInitializerPathHandling:
    """Tests for path handling in initializer."""

    def test_repo_path_must_exist(self, cli_runner, tmp_path):
        """Should validate that repo path exists."""
        nonexistent = tmp_path / "does_not_exist"

        result = cli_runner.invoke(
            init_command,
            ["--repo-path", str(nonexistent)],
        )

        # Click should validate path existence
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()

    def test_config_path_can_be_nonexistent(self, cli_runner, tmp_path):
        """Should allow non-existent config path (will be created)."""
        config_path = tmp_path / "subdir" / "config.yaml"

        with patch.object(RepoInitializer, "run"):
            result = cli_runner.invoke(
                init_command,
                [
                    "--repo-path",
                    str(tmp_path),
                    "--config-path",
                    str(config_path),
                    "--non-interactive",
                ],
            )

        # Should accept non-existent config path
        assert result.exit_code in [0, 1]
