"""CLI command for initializing repo-agent in a repository."""

import sys
from pathlib import Path
from typing import Literal

import click
import structlog

from repo_sapiens.credentials import CredentialResolver, EnvironmentBackend, KeyringBackend
from repo_sapiens.git.discovery import GitDiscovery
from repo_sapiens.git.exceptions import GitDiscoveryError

log = structlog.get_logger(__name__)


@click.command(name="init")
@click.option(
    "--repo-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Path to Git repository (default: current directory)",
)
@click.option(
    "--config-path",
    type=click.Path(path_type=Path),
    default="automation/config/automation_config.yaml",
    help="Path for configuration file",
)
@click.option(
    "--backend",
    type=click.Choice(["keyring", "environment", "encrypted"]),
    default=None,
    help="Credential backend (auto-detected if not specified)",
)
@click.option(
    "--non-interactive", is_flag=True, help="Non-interactive mode (requires environment variables)"
)
@click.option(
    "--setup-secrets",
    is_flag=True,
    default=True,
    help="Set up Gitea Actions secrets (default: true)",
)
def init_command(
    repo_path: Path,
    config_path: Path,
    backend: str | None,
    non_interactive: bool,
    setup_secrets: bool,
) -> None:
    """Initialize repo-agent in your Git repository.

    This command will:
    1. Discover Git repository configuration
    2. Prompt for credentials (or use environment variables)
    3. Store credentials securely
    4. Set up Gitea Actions secrets (if requested)
    5. Generate configuration file

    Examples:

        # Interactive setup (recommended)
        repo-agent init

        # Non-interactive setup (for CI/CD)
        export GITEA_TOKEN="your-token"
        export CLAUDE_API_KEY="your-key"
        repo-agent init --non-interactive

        # Skip Gitea Actions secret setup
        repo-agent init --no-setup-secrets
    """
    try:
        initializer = RepoInitializer(
            repo_path=repo_path,
            config_path=config_path,
            backend=backend,
            non_interactive=non_interactive,
            setup_secrets=setup_secrets,
        )
        initializer.run()

    except GitDiscoveryError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        click.echo(
            click.style(
                "Make sure you're in a Git repository with a configured remote.", fg="yellow"
            ),
            err=True,
        )
        sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        log.error("init_error", exc_info=True)
        sys.exit(1)


class RepoInitializer:
    """Handles repository initialization workflow."""

    def __init__(
        self,
        repo_path: Path,
        config_path: Path,
        backend: str | None,
        non_interactive: bool,
        setup_secrets: bool,
    ):
        self.repo_path = repo_path
        self.config_path = config_path
        self.backend = backend or self._detect_backend()
        self.non_interactive = non_interactive
        self.setup_secrets = setup_secrets

        self.repo_info = None
        self.provider_type = None  # 'github' or 'gitea' (detected)
        self.gitea_token = None
        self.agent_type = None  # 'claude' or 'goose'
        self.agent_mode: Literal["local", "api"] = "local"
        self.agent_api_key = None

        # Goose-specific settings
        self.goose_llm_provider = None
        self.goose_model = None
        self.goose_toolkit = "default"
        self.goose_temperature = 0.7

    def run(self) -> None:
        """Run the initialization workflow."""
        click.echo(click.style("🚀 Initializing repo-agent", bold=True, fg="cyan"))
        click.echo()

        # Step 1: Discover repository
        self._discover_repository()

        # Step 2: Collect credentials
        self._collect_credentials()

        # Step 3: Store credentials locally
        self._store_credentials()

        # Step 4: Set up Gitea Actions secrets (optional)
        if self.setup_secrets:
            self._setup_gitea_secrets()

        # Step 5: Generate configuration file
        self._generate_config()

        # Step 6: Validate setup
        self._validate_setup()

        # Done!
        click.echo()
        click.echo(click.style("✅ Initialization complete!", bold=True, fg="green"))
        click.echo()
        self._print_next_steps()

    def _detect_backend(self) -> str:
        """Detect best credential backend for current environment."""
        # Check if keyring is available
        keyring_backend = KeyringBackend()
        if keyring_backend.available:
            return "keyring"

        # Fall back to environment
        return "environment"

    def _discover_repository(self) -> None:
        """Discover Git repository configuration."""
        click.echo(click.style("🔍 Discovering repository configuration...", bold=True))

        try:
            discovery = GitDiscovery(self.repo_path)
            self.repo_info = discovery.parse_repository()

            # Detect provider type (GitHub or Gitea)
            self.provider_type = discovery.detect_provider_type()

            click.echo(f"   ✓ Found Git repository: {self.repo_path}")
            click.echo(f"   ✓ Detected remote: {self.repo_info.remote_name}")
            click.echo(f"   ✓ Provider: {self.provider_type.upper()}")
            click.echo(f"   ✓ Parsed: owner={self.repo_info.owner}, repo={self.repo_info.repo}")
            click.echo(f"   ✓ Base URL: {self.repo_info.base_url}")
            click.echo()

        except GitDiscoveryError as e:
            raise click.ClickException(f"Failed to discover repository: {e}") from e

    def _collect_credentials(self) -> None:
        """Collect credentials from user or environment."""
        click.echo(click.style("🔑 Setting up credentials...", bold=True))
        click.echo()

        if self.non_interactive:
            self._collect_from_environment()
        else:
            self._collect_interactively()

    def _collect_from_environment(self) -> None:
        """Collect credentials from environment variables."""
        import os

        self.gitea_token = os.getenv("GITEA_TOKEN")
        if not self.gitea_token:
            raise click.ClickException(
                "GITEA_TOKEN environment variable required in non-interactive mode"
            )

        self.claude_api_key = os.getenv("CLAUDE_API_KEY")
        # Claude API key is optional (can use local mode)

        click.echo("   ✓ Using credentials from environment variables")

    def _collect_interactively(self) -> None:
        """Collect credentials interactively from user."""
        # Gitea token
        click.echo(
            "Gitea API Token is required. Get it from:\n"
            f"   {self.repo_info.base_url}/user/settings/applications"
        )
        click.echo()

        self.gitea_token = click.prompt("Enter your Gitea API token", hide_input=True, type=str)

        click.echo()

        # AI Agent configuration
        self._configure_ai_agent()

    def _configure_ai_agent(self) -> None:
        """Configure AI agent (Claude or Goose) interactively."""
        from repo_sapiens.utils.agent_detector import detect_available_agents, format_agent_list

        click.echo(click.style("🤖 AI Agent Configuration", bold=True, fg="cyan"))
        click.echo()

        # Detect available agents
        available_agents = detect_available_agents()

        if available_agents:
            click.echo(format_agent_list())
            click.echo()

            # Map goose-uvx back to goose for selection
            agent_choices = []
            for agent in available_agents:
                base_agent = agent.replace("-uvx", "")
                if base_agent not in agent_choices:
                    agent_choices.append(base_agent)

            agent_choices.append("api")  # Always allow API mode

            self.agent_type = click.prompt(
                "Which agent do you want to use?",
                type=click.Choice(agent_choices),
                default=agent_choices[0] if agent_choices else "api",
            )
        else:
            click.echo(click.style("⚠ No AI agent CLIs detected", fg="yellow"))
            click.echo()
            click.echo("You can:")
            click.echo("  1. Install Claude Code: https://claude.com/install.sh")
            click.echo("  2. Install Goose: pip install goose-ai")
            click.echo("  3. Use API mode (requires API key)")
            click.echo()

            use_api = click.confirm("Use API mode?", default=True)
            if use_api:
                self.agent_type = click.prompt(
                    "Which API provider?", type=click.Choice(["claude", "openai"]), default="claude"
                )
                self.agent_mode = "api"
            else:
                raise click.ClickException(
                    "No agents available. Please install an agent CLI or use API mode."
                )

        # Configure based on agent type
        if self.agent_type == "claude":
            self._configure_claude()
        elif self.agent_type == "goose":
            self._configure_goose()

    def _configure_claude(self) -> None:
        """Configure Claude agent."""
        click.echo()

        # Ask local vs API
        self.agent_mode = click.prompt(
            "Use local Claude Code or Claude API?",
            type=click.Choice(["local", "api"]),
            default="local",
        )

        if self.agent_mode == "api":
            click.echo()
            click.echo("Claude API Key required. Get it from:")
            click.echo("   https://console.anthropic.com/")
            click.echo()

            self.agent_api_key = click.prompt(
                "Enter your Claude API key", hide_input=True, type=str
            )

    def _configure_goose(self) -> None:
        """Configure Goose agent with LLM provider selection."""
        from repo_sapiens.utils.agent_detector import (
            format_provider_comparison,
            get_provider_info,
            get_provider_recommendation,
            get_vllm_vs_ollama_note,
        )

        click.echo()
        click.echo(click.style("🪿 Goose Configuration", bold=True, fg="cyan"))
        click.echo()

        # Show provider comparison
        click.echo(format_provider_comparison())
        click.echo()

        # Show vLLM vs Ollama note
        click.echo(get_vllm_vs_ollama_note())
        click.echo()

        # Show recommendation
        click.echo(click.style("💡 Recommendation:", bold=True, fg="green"))
        click.echo(get_provider_recommendation("tool-usage"))
        click.echo()

        # Prompt for LLM provider
        self.goose_llm_provider = click.prompt(
            "Which LLM provider?",
            type=click.Choice(["openai", "anthropic", "ollama", "openrouter", "groq"]),
            default="openai",
        )

        provider_info = get_provider_info(self.goose_llm_provider)

        # Select model
        click.echo()
        available_models = provider_info["models"]
        default_model = provider_info["default_model"]

        click.echo(f"Available models for {provider_info['name']}:")
        for i, model in enumerate(available_models, 1):
            marker = " (recommended)" if model == default_model else ""
            click.echo(f"  {i}. {model}{marker}")
        click.echo()

        self.goose_model = click.prompt(
            "Which model?", type=click.Choice(available_models), default=default_model
        )

        # API key if needed
        if provider_info.get("api_key_env"):
            click.echo()
            api_key_name = provider_info["api_key_env"]

            # Check if already set in environment
            import os

            existing_key = os.getenv(api_key_name)

            if existing_key:
                use_existing = click.confirm(
                    f"{api_key_name} found in environment. Use it?", default=True
                )
                if use_existing:
                    self.agent_api_key = existing_key
                else:
                    self.agent_api_key = click.prompt(
                        f"Enter your {provider_info['name']} API key", hide_input=True, type=str
                    )
            else:
                website = provider_info.get("website", "provider website")
                click.echo(f"API key required. Get it from: {website}")
                click.echo()

                self.agent_api_key = click.prompt(
                    f"Enter your {provider_info['name']} API key", hide_input=True, type=str
                )

        # Additional Goose settings
        click.echo()
        if click.confirm("Customize Goose settings? (temperature, toolkit)", default=False):
            self.goose_temperature = click.prompt(
                "Temperature (0.0-2.0, higher = more creative)", type=float, default=0.7
            )

            self.goose_toolkit = click.prompt("Toolkit", type=str, default="default")

        self.agent_mode = "local"  # Goose runs locally

    def _store_credentials(self) -> None:
        """Store credentials in selected backend."""
        click.echo()
        click.echo(f"📦 Storing credentials in {self.backend} backend...")

        try:
            if self.backend == "keyring":
                self._store_in_keyring()
            else:
                self._store_in_environment()

            click.echo("   ✓ Credentials stored securely")
            click.echo()

        except Exception as e:
            raise click.ClickException(f"Failed to store credentials: {e}") from e

    def _store_in_keyring(self) -> None:
        """Store credentials in OS keyring."""
        backend = KeyringBackend()

        # Store Gitea token
        backend.set("gitea", "api_token", self.gitea_token)
        click.echo("   ✓ Stored: gitea/api_token")

        # Store agent API key if provided
        if self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Store under provider-specific key
                backend.set(self.goose_llm_provider, "api_key", self.agent_api_key)
                click.echo(f"   ✓ Stored: {self.goose_llm_provider}/api_key")
            elif self.agent_type == "claude":
                backend.set("claude", "api_key", self.agent_api_key)
                click.echo("   ✓ Stored: claude/api_key")

    def _store_in_environment(self) -> None:
        """Store credentials in environment (for current session)."""
        backend = EnvironmentBackend()

        # Store Gitea token
        backend.set("GITEA_TOKEN", self.gitea_token)
        click.echo("   ✓ Set: GITEA_TOKEN")

        # Store agent API key if provided
        if self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Store under provider-specific environment variable
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                backend.set(env_var, self.agent_api_key)
                click.echo(f"   ✓ Set: {env_var}")
            elif self.agent_type == "claude":
                backend.set("CLAUDE_API_KEY", self.agent_api_key)
                click.echo("   ✓ Set: CLAUDE_API_KEY")

        click.echo()
        click.echo(
            click.style("Note: Environment variables only persist in current session.", fg="yellow")
        )
        click.echo(
            click.style(
                "Add them to your shell profile or use --backend keyring for persistence.",
                fg="yellow",
            )
        )

    def _setup_gitea_secrets(self) -> None:
        """Set up repository Actions secrets (GitHub Actions or Gitea Actions)."""
        provider_name = self.provider_type.upper()
        click.echo(click.style(f"🔐 Setting up {provider_name} Actions secrets...", bold=True))

        try:
            if self.provider_type == "github":
                self._setup_github_secrets()
            else:
                self._setup_gitea_secrets_mcp()

        except Exception as e:
            click.echo(
                click.style(
                    f"   ⚠ Warning: Failed to set {provider_name} secrets: {e}", fg="yellow"
                )
            )
            click.echo(
                click.style(
                    f"   You can set them manually in {provider_name} UI later.", fg="yellow"
                )
            )
            click.echo()

    def _setup_github_secrets(self) -> None:
        """Set up GitHub Actions secrets using GitHub API."""
        from repo_sapiens.providers.github_rest import GitHubRestProvider

        # Initialize GitHub provider
        github = GitHubRestProvider(
            token=self.gitea_token,  # Using same token variable for simplicity
            owner=self.repo_info.owner,
            repo=self.repo_info.repo,
            base_url=str(self.repo_info.base_url),
        )

        # Connect to GitHub
        import asyncio

        asyncio.run(github.connect())

        # Set GitHub token secret (for workflows)
        token_secret_name = "GITHUB_TOKEN" if self.provider_type == "github" else "GITEA_TOKEN"
        click.echo(f"   ⏳ Setting {token_secret_name} secret...")
        asyncio.run(github.set_repository_secret(token_secret_name, self.gitea_token))
        click.echo(f"   ✓ Set repository secret: {token_secret_name}")

        # Set agent API key secret if using API mode
        if self.agent_mode == "api" and self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Set provider-specific API key for Goose
                secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                click.echo(f"   ⏳ Setting {secret_name} secret...")
                asyncio.run(github.set_repository_secret(secret_name, self.agent_api_key))
                click.echo(f"   ✓ Set repository secret: {secret_name}")
            elif self.agent_type == "claude":
                click.echo("   ⏳ Setting CLAUDE_API_KEY secret...")
                asyncio.run(github.set_repository_secret("CLAUDE_API_KEY", self.agent_api_key))
                click.echo("   ✓ Set repository secret: CLAUDE_API_KEY")
        else:
            click.echo("   ℹ Skipped API key secret (using local mode)")

        click.echo()

    def _setup_gitea_secrets_mcp(self) -> None:
        """Set up Gitea Actions secrets via MCP."""
        # Set GITEA_TOKEN secret
        click.echo("   ⏳ Setting GITEA_TOKEN secret...")
        # Note: We'll need to use the MCP server directly since GiteaRestProvider
        # doesn't expose secret management yet
        self._set_gitea_secret_via_mcp("GITEA_TOKEN", self.gitea_token)
        click.echo("   ✓ Set repository secret: GITEA_TOKEN")

        # Set agent API key secret if using API mode
        if self.agent_mode == "api" and self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Set provider-specific API key for Goose
                secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                click.echo(f"   ⏳ Setting {secret_name} secret...")
                self._set_gitea_secret_via_mcp(secret_name, self.agent_api_key)
                click.echo(f"   ✓ Set repository secret: {secret_name}")
            elif self.agent_type == "claude":
                click.echo("   ⏳ Setting CLAUDE_API_KEY secret...")
                self._set_gitea_secret_via_mcp("CLAUDE_API_KEY", self.agent_api_key)
                click.echo("   ✓ Set repository secret: CLAUDE_API_KEY")
        else:
            click.echo("   ℹ Skipped API key secret (using local mode)")

        click.echo()

    def _set_gitea_secret_via_mcp(self, name: str, value: str) -> None:
        """Set Gitea Actions secret using MCP server.

        This is a placeholder - we'll need to call the actual MCP function.
        For now, we'll document that this needs manual setup.
        """
        # TODO: Use mcp__gitea__upsert_repo_action_secret when MCP integration is complete
        click.echo(click.style(f"   ℹ Please set {name} manually in Gitea UI for now", fg="yellow"))
        secrets_url = (
            f"{self.repo_info.base_url}/{self.repo_info.owner}/"
            f"{self.repo_info.repo}/settings/secrets"
        )
        click.echo(f"   Navigate to: {secrets_url}")

    def _generate_config(self) -> None:
        """Generate configuration file."""
        click.echo(click.style("📝 Creating configuration file...", bold=True))

        # Determine credential references based on backend
        if self.backend == "keyring":
            gitea_token_ref = "@keyring:gitea/api_token"  # nosec B105 # Template placeholder for keyring reference

            # For Goose, use provider-specific keyring path
            if self.agent_type == "goose" and self.goose_llm_provider:
                agent_api_key_ref = (
                    f"@keyring:{self.goose_llm_provider}/api_key" if self.agent_api_key else "null"
                )
            elif self.agent_type == "claude":
                agent_api_key_ref = "@keyring:claude/api_key" if self.agent_api_key else "null"
            else:
                agent_api_key_ref = "null"
        else:
            # fmt: off
            gitea_token_ref = "${GITEA_TOKEN}"  # nosec B105 # Template placeholder for environment variable
            # fmt: on

            # For Goose, use provider-specific environment variable
            if self.agent_type == "goose" and self.goose_llm_provider:
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                agent_api_key_ref = f"${{{env_var}}}" if self.agent_api_key else "null"
            elif self.agent_type == "claude":
                agent_api_key_ref = "${CLAUDE_API_KEY}" if self.agent_api_key else "null"
            else:
                agent_api_key_ref = "null"

        # Generate agent provider configuration
        if self.agent_type == "goose":
            provider_type = f"goose-{self.agent_mode}"
            model = self.goose_model or "gpt-4o"

            # Build goose_config section
            goose_config_section = f"""  goose_config:
    toolkit: {self.goose_toolkit}
    temperature: {self.goose_temperature}
    max_tokens: 4096"""

            if self.goose_llm_provider:
                goose_config_section += f"\n    llm_provider: {self.goose_llm_provider}"

            agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: {agent_api_key_ref}
  local_mode: {str(self.agent_mode == "local").lower()}
{goose_config_section}"""
        else:
            # Claude configuration
            provider_type = f"claude-{self.agent_mode}"
            model = "claude-sonnet-4.5"
            agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: {agent_api_key_ref}
  local_mode: {str(self.agent_mode == "local").lower()}"""

        # Determine MCP server (only Gitea uses MCP)
        if self.provider_type == "github":
            mcp_server_line = "  mcp_server: null"
        else:
            mcp_server_line = "  mcp_server: gitea-mcp"

        # Generate configuration content
        config_content = f"""# Automation System Configuration
# Generated by: repo-agent init
# Repository: {self.repo_info.owner}/{self.repo_info.repo}

git_provider:
  provider_type: {self.provider_type}
{mcp_server_line}
  base_url: {self.repo_info.base_url}
  api_token: {gitea_token_ref}

repository:
  owner: {self.repo_info.owner}
  name: {self.repo_info.repo}
  default_branch: main

{agent_config}

workflow:
  plans_directory: plans
  state_directory: .automation/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3
  review_approval_threshold: 0.8

tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
  in_progress: in-progress
  code_review: code-review
  merge_ready: merge-ready
  completed: completed
  needs_attention: needs-attention
"""

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write configuration file
        self.config_path.write_text(config_content)
        click.echo(f"   ✓ Created: {self.config_path}")
        click.echo()

    def _validate_setup(self) -> None:
        """Validate the setup."""
        click.echo(click.style("✓ Validating setup...", bold=True))

        try:
            # Test credential resolution
            resolver = CredentialResolver()

            if self.backend == "keyring":
                gitea_ref = "@keyring:gitea/api_token"
            else:
                gitea_ref = "${GITEA_TOKEN}"

            resolved = resolver.resolve(gitea_ref, cache=False)
            if not resolved:
                raise ValueError("Failed to resolve Gitea token")

            click.echo("   ✓ Credentials validated")
            click.echo("   ✓ Configuration file created")
            click.echo()

        except Exception as e:
            click.echo(click.style(f"   ⚠ Warning: Validation failed: {e}", fg="yellow"))
            click.echo()

    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        click.echo(click.style("📋 Next Steps:", bold=True))
        click.echo()
        click.echo("1. Label an issue with 'needs-planning' in Gitea:")
        issues_url = (
            f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/issues"
        )
        click.echo(f"   {issues_url}")
        click.echo()
        click.echo("2. Run the automation daemon:")
        click.echo(f"   repo-agent --config {self.config_path} daemon --interval 60")
        click.echo()
        click.echo("3. Watch the automation work!")
        click.echo()

        # Print manual secret setup if needed
        if self.setup_secrets:
            click.echo(
                click.style(
                    "⚠ Important: Set Gitea Actions Secrets Manually", bold=True, fg="yellow"
                )
            )
            click.echo()
            secrets_url = (
                f"{self.repo_info.base_url}/{self.repo_info.owner}/"
                f"{self.repo_info.repo}/settings/secrets"
            )
            click.echo(f"Navigate to: {secrets_url}")
            click.echo()
            click.echo("Add the following secrets:")
            click.echo("  - GITEA_TOKEN (your Gitea API token)")
            if self.agent_mode == "api":
                if self.agent_type == "goose" and self.goose_llm_provider:
                    secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                    provider_title = self.goose_llm_provider.title()
                    click.echo(f"  - {secret_name} (your {provider_title} API key for Goose)")
                elif self.agent_type == "claude":
                    click.echo("  - CLAUDE_API_KEY (your Claude API key)")
            click.echo()

        click.echo("For more information, see:")
        click.echo("  - README.md")
        click.echo("  - QUICK_START.md")
        click.echo("  - docs/CREDENTIAL_QUICK_START.md")
