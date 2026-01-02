"""Configuration system for automation platform.

This package provides type-safe configuration management using Pydantic,
including settings for Git providers, repositories, agents, workflows, and tags.

Key Components:
    - Settings: Main configuration container with YAML loading support
    - GitProviderConfig: Git provider configuration (Gitea, GitHub)
    - RepositoryConfig: Repository settings
    - AgentProviderConfig: AI agent configuration
    - WorkflowConfig: Workflow behavior settings
    - TagsConfig: Issue tag/label configuration

Example:
    >>> from repo_sapiens.config import AutomationSettings
    >>> settings = AutomationSettings.from_yaml("config.yaml")
    >>> git_url = settings.git_provider.base_url
"""
