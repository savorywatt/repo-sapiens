"""
Configuration system using Pydantic for type-safe settings management.

This module provides configuration classes for all aspects of the automation system,
including Git providers, agents, workflows, and tags.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from repo_sapiens.config.credential_fields import CredentialSecret
from repo_sapiens.config.mcp import MCPConfig
from repo_sapiens.config.triggers import AutomationConfig
from repo_sapiens.enums import ProviderType
from repo_sapiens.exceptions import ConfigurationError


class GitProviderConfig(BaseModel):
    """Git provider configuration (Gitea, GitHub, or GitLab).

    Supports credential references:
    - api_token: "@keyring:gitea/api_token"
    - api_token: "${GITEA_API_TOKEN}"
    - api_token: "@encrypted:gitea/api_token"
    """

    provider_type: Literal["gitea", "github", "gitlab"] = Field(default="gitea", description="Type of Git provider")
    mcp_server: str | None = Field(default=None, description="Name of MCP server for Git operations")
    base_url: HttpUrl = Field(..., description="Base URL of the Git provider")
    api_token: CredentialSecret = Field(
        ..., description="API token for authentication (supports @keyring:, ${ENV}, @encrypted:)"
    )


class RepositoryConfig(BaseModel):
    """Repository configuration."""

    owner: str = Field(..., description="Repository owner/organization")
    name: str = Field(..., description="Repository name")
    default_branch: str = Field(default="main", description="Default branch name")


class GooseConfig(BaseModel):
    """Goose-specific configuration options."""

    toolkit: str = Field(default="default", description="Goose toolkit to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=4096, ge=1, description="Maximum tokens for response")
    llm_provider: str | None = Field(default=None, description="LLM provider (openai, anthropic, ollama, etc.)")


class CopilotConfig(BaseModel):
    """Configuration for GitHub Copilot provider using copilot-api proxy.

    WARNING: This integration uses an unofficial, reverse-engineered API.
    - Not endorsed or supported by GitHub
    - May violate GitHub Terms of Service
    - Could stop working at any time
    - Use at your own risk

    Supports two deployment modes:
    - Managed: Auto-starts copilot-api proxy subprocess
    - External: Connects to existing copilot-api instance
    """

    github_token: CredentialSecret = Field(
        ...,
        description="GitHub OAuth token (gho_xxx) with Copilot access. "
        "Supports @keyring:, ${ENV}, @encrypted: references.",
    )
    manage_proxy: bool = Field(
        default=True,
        description="If true, auto-start/stop copilot-api subprocess. " "If false, connect to external proxy_url.",
    )
    proxy_port: int = Field(
        default=4141,
        ge=1024,
        le=65535,
        description="Port for managed proxy (only used when manage_proxy=true).",
    )
    proxy_url: str | None = Field(
        default=None,
        description="URL of external copilot-api instance "
        "(required when manage_proxy=false, e.g., http://localhost:4141/v1).",
    )
    account_type: Literal["individual", "business", "enterprise"] = Field(
        default="individual",
        description="GitHub Copilot subscription type.",
    )
    rate_limit: float | None = Field(
        default=None,
        ge=0.1,
        description="Seconds between API requests (recommended: 2.0 to avoid abuse detection).",
    )
    model: str = Field(
        default="gpt-4",
        description="Model to request from Copilot API.",
    )
    startup_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Maximum seconds to wait for proxy startup.",
    )
    shutdown_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Maximum seconds to wait for graceful proxy shutdown.",
    )

    @model_validator(mode="after")
    def validate_proxy_config(self) -> CopilotConfig:
        """Enforce mutually exclusive proxy configuration."""
        if self.manage_proxy:
            if self.proxy_url is not None:
                raise ValueError("proxy_url must not be set when manage_proxy=true. " "Use proxy_port instead.")
        else:
            if self.proxy_url is None:
                raise ValueError("proxy_url is required when manage_proxy=false. " "Example: http://localhost:4141/v1")
            if not (self.proxy_url.startswith("http://") or self.proxy_url.startswith("https://")):
                raise ValueError(f"proxy_url must start with http:// or https://, " f"got: {self.proxy_url}")
        return self

    @property
    def effective_url(self) -> str:
        """Get the effective proxy URL based on configuration."""
        if self.manage_proxy:
            return f"http://localhost:{self.proxy_port}/v1"
        return self.proxy_url or ""


class AgentProviderConfig(BaseModel):
    """AI agent configuration.

    Supports credential references for api_key:
    - api_key: "@keyring:claude/api_key"
    - api_key: "${CLAUDE_API_KEY}"
    - api_key: "@encrypted:claude/api_key"
    - api_key: "@keyring:openai/api_key" (for Goose with OpenAI)
    """

    provider_type: ProviderType = Field(default=ProviderType.CLAUDE_LOCAL, description="Type of agent provider")
    model: str = Field(default="claude-sonnet-4.5", description="Model identifier")
    api_key: CredentialSecret | None = Field(
        default=None,
        description="API key for cloud providers (supports @keyring:, ${ENV}, @encrypted:)",
    )
    local_mode: bool = Field(default=True, description="Whether to use local CLI (Claude Code or Goose)")
    base_url: str | None = Field(
        default="http://localhost:11434", description="Base URL for Ollama or custom API endpoints"
    )
    goose_config: GooseConfig | None = Field(
        default=None,
        description="Goose-specific configuration (only used with goose-local)",
    )
    copilot_config: CopilotConfig | None = Field(
        default=None,
        description="Copilot-specific configuration (required for provider_type='copilot-local')",
    )

    @model_validator(mode="after")
    def validate_provider_config(self) -> AgentProviderConfig:
        """Ensure required configs are present for each provider type."""
        if self.provider_type == ProviderType.COPILOT_LOCAL and self.copilot_config is None:
            raise ValueError("copilot_config is required when provider_type='copilot-local'")
        return self


class WorkflowConfig(BaseModel):
    """Workflow behavior configuration."""

    plans_directory: str = Field(default="plans", description="Directory for plan files")
    state_directory: str = Field(default=".sapiens/state", description="Directory for state files")
    branching_strategy: Literal["per-agent", "shared"] = Field(
        default="per-agent", description="Branch creation strategy"
    )
    max_concurrent_tasks: int = Field(default=3, ge=1, le=10, description="Maximum concurrent agent tasks")
    review_approval_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum confidence for auto-approval"
    )


class TagsConfig(BaseModel):
    """Issue tag/label configuration for workflow stages."""

    needs_planning: str = Field(default="needs-planning", description="Issue needs planning")
    plan_review: str = Field(default="plan-review", description="Plan is under review")
    ready_to_implement: str = Field(default="ready-to-implement", description="Plan approved, ready for implementation")
    in_progress: str = Field(default="in-progress", description="Implementation in progress")
    code_review: str = Field(default="code-review", description="Code is under review")
    merge_ready: str = Field(default="merge-ready", description="Ready to merge")
    completed: str = Field(default="completed", description="Task completed")
    needs_attention: str = Field(default="needs-attention", description="Requires human intervention")


class AutomationSettings(BaseSettings):
    """Main automation system settings.

    This class combines all configuration sections and provides methods
    for loading from YAML files with environment variable interpolation.
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTOMATION_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    git_provider: GitProviderConfig
    repository: RepositoryConfig
    agent_provider: AgentProviderConfig
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    tags: TagsConfig = Field(default_factory=TagsConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP server configuration")

    @property
    def state_dir(self) -> Path:
        """Get state directory as Path object."""
        return Path(self.workflow.state_directory)

    @property
    def plans_dir(self) -> Path:
        """Get plans directory as Path object."""
        return Path(self.workflow.plans_directory)

    @classmethod
    def from_yaml(cls, config_path: str) -> AutomationSettings:
        """Load settings from YAML file with environment variable interpolation.

        Supports ${VAR_NAME} syntax for environment variable substitution.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            AutomationSettings instance

        Raises:
            ConfigurationError: If config file is invalid or missing required fields
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            # Read YAML content
            with open(config_file) as f:
                yaml_content = f.read()
        except OSError as e:
            raise ConfigurationError(f"Cannot read configuration file: {config_path}") from e

        try:
            # Interpolate environment variables
            yaml_content = cls._interpolate_env_vars(yaml_content)
        except ValueError as e:
            raise ConfigurationError(f"Invalid environment variable reference in config: {e}") from e

        try:
            # Parse YAML
            config_dict = yaml.safe_load(yaml_content)
            if not isinstance(config_dict, dict):
                raise ConfigurationError("Configuration must be a YAML object, not a list or scalar")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML syntax in {config_path}: {e}") from e

        try:
            # Create settings instance
            return cls(**config_dict)
        except TypeError as e:
            raise ConfigurationError(f"Missing or invalid configuration fields: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to validate configuration: {e}") from e

    @staticmethod
    def _interpolate_env_vars(content: str) -> str:
        """Interpolate ${VAR_NAME} placeholders with environment variables.

        Supports two syntaxes:
        - ${VAR_NAME} - Required environment variable (raises if not set)
        - ${VAR_NAME:-default} - Optional with default value

        Args:
            content: String content with placeholders

        Returns:
            Content with environment variables substituted

        Raises:
            ValueError: If a required environment variable is not set

        Note:
            YAML comment lines (starting with #) are preserved unchanged,
            allowing documentation examples like ${VAR_NAME} in comments.
        """
        # Pattern matches ${VAR_NAME} or ${VAR_NAME:-default}
        # Group 1: variable name, Group 2: optional default value (including the :-)
        pattern = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")

        def replace_var(match: re.Match[str]) -> str:
            """Replace matched placeholder with environment variable value.

            Args:
                match: Regex match object containing the variable name and optional default

            Returns:
                Environment variable value or default

            Raises:
                ValueError: If the environment variable is not set and no default provided
            """
            var_name = match.group(1)
            default_value = match.group(2)  # None if no default specified
            value = os.getenv(var_name)

            if value is not None:
                return value
            elif default_value is not None:
                return default_value
            else:
                raise ValueError(f"Environment variable {var_name} is not set")

        def process_line(line: str) -> str:
            """Process a single line, skipping YAML comments."""
            stripped = line.lstrip()
            if stripped.startswith("#"):
                return line
            return pattern.sub(replace_var, line)

        lines = content.split("\n")
        return "\n".join(process_line(line) for line in lines)
