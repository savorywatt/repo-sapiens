"""Factory for creating Git provider instances based on configuration."""

import structlog

from automation.config.settings import AutomationSettings
from automation.providers.base import GitProvider
from automation.providers.gitea_rest import GiteaRestProvider
from automation.providers.github_rest import GitHubRestProvider

log = structlog.get_logger(__name__)


def create_git_provider(settings: AutomationSettings) -> GitProvider:
    """Create appropriate Git provider based on configuration.

    Args:
        settings: Automation settings containing provider configuration

    Returns:
        GitProvider instance (Gitea or GitHub)

    Raises:
        ValueError: If provider type is not supported

    Example:
        >>> settings = AutomationSettings.from_yaml("config.yaml")
        >>> provider = create_git_provider(settings)
        >>> await provider.connect()
        >>> issues = await provider.get_issues()
    """
    provider_type = settings.git_provider.provider_type

    if provider_type == "gitea":
        log.info("creating_gitea_provider", base_url=str(settings.git_provider.base_url))
        return GiteaRestProvider(
            base_url=str(settings.git_provider.base_url),
            token=settings.git_provider.api_token.get_secret_value(),
            owner=settings.repository.owner,
            repo=settings.repository.name,
        )

    elif provider_type == "github":
        log.info("creating_github_provider", base_url=str(settings.git_provider.base_url))
        return GitHubRestProvider(
            token=settings.git_provider.api_token.get_secret_value(),
            owner=settings.repository.owner,
            repo=settings.repository.name,
            base_url=str(settings.git_provider.base_url),
        )

    else:
        raise ValueError(
            f"Unsupported Git provider type: {provider_type}. Supported types: gitea, github"
        )


def detect_provider_from_url(url: str) -> str:
    """Detect provider type from Git remote URL.

    Args:
        url: Git remote URL (HTTP/HTTPS or SSH)

    Returns:
        Provider type: "github" or "gitea"

    Example:
        >>> detect_provider_from_url("https://github.com/user/repo.git")
        'github'
        >>> detect_provider_from_url("git@github.com:user/repo.git")
        'github'
        >>> detect_provider_from_url("https://gitea.example.com/user/repo.git")
        'gitea'
    """
    url_lower = url.lower()

    # Check for GitHub
    if "github.com" in url_lower:
        return "github"

    # Check for GitHub Enterprise (common patterns)
    if "github" in url_lower:
        return "github"

    # "ghe" as hostname component (e.g., ghe.company.com, company-ghe.com)
    if "ghe." in url_lower or "-ghe" in url_lower or "/ghe" in url_lower:
        return "github"

    if "enterprise" in url_lower:
        return "github"

    # Default to Gitea (could be self-hosted)
    return "gitea"
