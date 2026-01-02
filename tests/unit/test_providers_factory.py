"""Tests for repo_sapiens/providers/factory.py - Git provider factory."""

import pytest
from pydantic import SecretStr

from repo_sapiens.config.settings import (
    AgentProviderConfig,
    AutomationSettings,
    GitProviderConfig,
    RepositoryConfig,
)
from repo_sapiens.providers.factory import create_git_provider, detect_provider_from_url
from repo_sapiens.providers.gitea_rest import GiteaRestProvider
from repo_sapiens.providers.github_rest import GitHubRestProvider


class TestCreateGitProvider:
    """Tests for create_git_provider function."""

    def test_create_gitea_provider(self, tmp_path):
        """Should create GiteaRestProvider when provider_type is 'gitea'."""
        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="gitea",
                base_url="https://gitea.example.com",
                api_token=SecretStr("test-token-123"),
            ),
            repository=RepositoryConfig(
                owner="test-owner",
                name="test-repo",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)

        assert isinstance(provider, GiteaRestProvider)
        assert provider.base_url == "https://gitea.example.com"
        assert provider.token == "test-token-123"
        assert provider.owner == "test-owner"
        assert provider.repo == "test-repo"

    def test_create_github_provider(self, tmp_path):
        """Should create GitHubRestProvider when provider_type is 'github'."""
        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="github",
                base_url="https://api.github.com",
                api_token=SecretStr("ghp_test123"),
            ),
            repository=RepositoryConfig(
                owner="github-user",
                name="repo-name",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)

        assert isinstance(provider, GitHubRestProvider)
        assert provider.base_url == "https://api.github.com"
        assert provider.token == "ghp_test123"
        assert provider.owner == "github-user"
        assert provider.repo == "repo-name"

    def test_create_github_enterprise_provider(self, tmp_path):
        """Should create GitHubRestProvider for GitHub Enterprise."""
        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="github",
                base_url="https://github.enterprise.com/api/v3",
                api_token=SecretStr("ghp_enterprise_token"),
            ),
            repository=RepositoryConfig(
                owner="enterprise-org",
                name="private-repo",
                default_branch="develop",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)

        assert isinstance(provider, GitHubRestProvider)
        assert provider.base_url == "https://github.enterprise.com/api/v3"
        assert provider.owner == "enterprise-org"
        assert provider.repo == "private-repo"

    def test_unsupported_provider_type_raises_error(self, tmp_path):
        """Should raise ValueError for unsupported provider types."""
        # Use model_construct to bypass Pydantic validation and test factory logic
        settings = AutomationSettings.model_construct(
            git_provider=GitProviderConfig.model_construct(
                provider_type="unsupported",
                base_url="https://example.com",
                api_token=SecretStr("token"),
            ),
            repository=RepositoryConfig(
                owner="owner",
                name="repo",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        with pytest.raises(ValueError) as exc_info:
            create_git_provider(settings)

        assert "Unsupported Git provider type: unsupported" in str(exc_info.value)
        assert "Supported types: gitea, github" in str(exc_info.value)

    def test_provider_uses_repository_config(self, tmp_path):
        """Should correctly pass repository owner and name to provider."""
        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="gitea",
                base_url="https://gitea.local",
                api_token=SecretStr("local-token"),
            ),
            repository=RepositoryConfig(
                owner="my-org",
                name="my-special-repo",
                default_branch="staging",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)

        assert provider.owner == "my-org"
        assert provider.repo == "my-special-repo"

    def test_provider_extracts_secret_token(self, tmp_path):
        """Should extract secret value from SecretStr."""
        secret_token = SecretStr("super-secret-token-value")

        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="gitea",
                base_url="https://gitea.test",
                api_token=secret_token,
            ),
            repository=RepositoryConfig(
                owner="test",
                name="test",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)

        # Token should be extracted from SecretStr
        assert provider.token == "super-secret-token-value"


class TestDetectProviderFromUrl:
    """Tests for detect_provider_from_url function."""

    def test_detect_github_https_url(self):
        """Should detect GitHub from HTTPS URL."""
        result = detect_provider_from_url("https://github.com/user/repo.git")
        assert result == "github"

    def test_detect_github_ssh_url(self):
        """Should detect GitHub from SSH URL."""
        result = detect_provider_from_url("git@github.com:user/repo.git")
        assert result == "github"

    def test_detect_github_without_git_suffix(self):
        """Should detect GitHub from URL without .git suffix."""
        result = detect_provider_from_url("https://github.com/org/project")
        assert result == "github"

    def test_detect_github_case_insensitive(self):
        """Should detect GitHub case-insensitively."""
        result = detect_provider_from_url("HTTPS://GITHUB.COM/User/Repo")
        assert result == "github"

    def test_detect_github_enterprise_with_keyword(self):
        """Should detect GitHub Enterprise from URL with 'enterprise' keyword."""
        result = detect_provider_from_url("https://github.enterprise.com/org/repo.git")
        assert result == "github"

    def test_detect_github_enterprise_with_ghe(self):
        """Should detect GitHub Enterprise from URL with 'ghe' keyword."""
        result = detect_provider_from_url("https://ghe.company.com/team/project")
        assert result == "github"

    def test_detect_gitea_from_custom_domain(self):
        """Should default to Gitea for custom domains."""
        result = detect_provider_from_url("https://gitea.example.com/user/repo.git")
        assert result == "gitea"

    def test_detect_gitea_from_localhost(self):
        """Should default to Gitea for localhost."""
        result = detect_provider_from_url("http://localhost:3000/owner/repo")
        assert result == "gitea"

    def test_detect_gitea_from_ip_address(self):
        """Should default to Gitea for IP addresses."""
        result = detect_provider_from_url("https://192.168.1.100/git/project.git")
        assert result == "gitea"

    def test_detect_gitea_from_custom_ssh(self):
        """Should default to Gitea for custom SSH URLs."""
        result = detect_provider_from_url("git@gitea.local:org/repo.git")
        assert result == "gitea"

    def test_detect_gitea_from_unknown_domain(self):
        """Should default to Gitea for unknown domains."""
        result = detect_provider_from_url("https://code.company.internal/team/app")
        assert result == "gitea"

    def test_detect_with_port_number(self):
        """Should handle URLs with port numbers."""
        result = detect_provider_from_url("https://git.local:8443/user/repo")
        assert result == "gitea"

    def test_detect_with_nested_path(self):
        """Should handle URLs with nested paths."""
        result = detect_provider_from_url("https://github.com/organization/team/repo.git")
        assert result == "github"


class TestProviderFactoryIntegration:
    """Integration tests for provider factory."""

    def test_factory_and_detection_work_together_for_github(self, tmp_path):
        """Should create correct provider when detection suggests GitHub."""
        url = "https://github.com/myuser/myrepo.git"
        provider_type = detect_provider_from_url(url)

        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type=provider_type,
                base_url="https://api.github.com",
                api_token=SecretStr("test-token"),
            ),
            repository=RepositoryConfig(
                owner="myuser",
                name="myrepo",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)
        assert isinstance(provider, GitHubRestProvider)

    def test_factory_and_detection_work_together_for_gitea(self, tmp_path):
        """Should create correct provider when detection suggests Gitea."""
        url = "https://gitea.mycompany.com/dev/project.git"
        provider_type = detect_provider_from_url(url)

        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type=provider_type,
                base_url="https://gitea.mycompany.com",
                api_token=SecretStr("test-token"),
            ),
            repository=RepositoryConfig(
                owner="dev",
                name="project",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)
        assert isinstance(provider, GiteaRestProvider)


class TestProviderFactoryEdgeCases:
    """Edge cases and error handling for provider factory."""

    def test_empty_provider_type_raises_error(self, tmp_path):
        """Should raise error for empty provider type."""
        # Use model_construct to bypass Pydantic validation and test factory logic
        settings = AutomationSettings.model_construct(
            git_provider=GitProviderConfig.model_construct(
                provider_type="",
                base_url="https://example.com",
                api_token=SecretStr("token"),
            ),
            repository=RepositoryConfig(
                owner="owner",
                name="repo",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        with pytest.raises(ValueError):
            create_git_provider(settings)

    def test_detect_provider_with_empty_url(self):
        """Should handle empty URL gracefully."""
        # Empty URL defaults to Gitea
        result = detect_provider_from_url("")
        assert result == "gitea"

    def test_detect_provider_with_whitespace_url(self):
        """Should handle whitespace in URL."""
        result = detect_provider_from_url("  https://github.com/user/repo  ")
        # Case-insensitive check should work even with whitespace
        assert result == "github"

    def test_provider_with_special_characters_in_repo_name(self, tmp_path):
        """Should handle repository names with special characters."""
        settings = AutomationSettings(
            git_provider=GitProviderConfig(
                provider_type="gitea",
                base_url="https://gitea.test",
                api_token=SecretStr("token"),
            ),
            repository=RepositoryConfig(
                owner="my-org",
                name="repo-with-hyphens_and_underscores",
                default_branch="main",
            ),
            agent_provider=AgentProviderConfig(
                provider_type="claude-local",
                model="claude-sonnet-4.5",
                api_key=SecretStr("test-key"),
                local_mode=True,
            ),
            workflow={"state_directory": str(tmp_path / "state")},
        )

        provider = create_git_provider(settings)
        assert provider.repo == "repo-with-hyphens_and_underscores"

    def test_detect_enterprise_only_url(self):
        """Should detect GitHub Enterprise from URL with only 'enterprise' keyword.

        This specifically tests the enterprise detection when 'github' is not in URL.
        Covers factory.py line 88-89.
        """
        # URL contains 'enterprise' but not 'github' or 'ghe'
        result = detect_provider_from_url("https://enterprise.company.com/org/repo")
        assert result == "github"

    def test_detect_ghe_hyphen_suffix(self):
        """Should detect GitHub Enterprise from URL with '-ghe' pattern."""
        result = detect_provider_from_url("https://company-ghe.example.com/team/repo")
        assert result == "github"

    def test_detect_ghe_path_pattern(self):
        """Should detect GitHub Enterprise from URL with '/ghe' in path."""
        result = detect_provider_from_url("https://git.company.com/ghe/org/repo")
        assert result == "github"


class TestDetectProviderUrlPatterns:
    """Additional URL pattern tests for provider detection."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            # GitHub variations
            ("https://github.com/user/repo", "github"),
            ("git@github.com:user/repo.git", "github"),
            ("ssh://git@github.com/user/repo", "github"),
            ("https://raw.githubusercontent.com/user/repo/main/file", "github"),
            # GitHub Enterprise patterns
            ("https://ghe.corp.com/org/repo", "github"),
            ("https://corp-ghe.internal/org/repo", "github"),
            ("https://git.corp.com/ghe/org/repo", "github"),
            ("https://enterprise.corp.com/org/repo", "github"),
            # Gitea (default) patterns
            ("https://gitea.io/user/repo", "gitea"),
            ("https://code.company.com/team/project", "gitea"),
            ("http://localhost:3000/user/repo", "gitea"),
            ("https://192.168.1.1:8080/org/repo", "gitea"),
            ("git@code.example.org:user/repo.git", "gitea"),
        ],
    )
    def test_detect_provider_parametrized(self, url, expected):
        """Should detect correct provider type from various URL patterns."""
        result = detect_provider_from_url(url)
        assert result == expected
