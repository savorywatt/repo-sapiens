"""CLI command for initializing repo-sapiens in a repository."""

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
    default="repo_sapiens/config/automation_config.yaml",
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
@click.option(
    "--setup-workflows/--no-setup-workflows",
    default=None,
    help="Set up CI/CD workflow files (prompts if not specified)",
)
@click.option(
    "--setup-examples/--no-setup-examples",
    default=None,
    help="Set up example recurring task workflows (prompts if not specified)",
)
def init_command(
    repo_path: Path,
    config_path: Path,
    backend: str | None,
    non_interactive: bool,
    setup_secrets: bool,
    setup_workflows: bool | None,
    setup_examples: bool | None,
) -> None:
    """Initialize repo-sapiens in your Git repository.

    This command will:
    1. Discover Git repository configuration
    2. Prompt for credentials (or use environment variables)
    3. Store credentials securely
    4. Set up Gitea/GitHub Actions secrets (if requested)
    5. Generate configuration file
    6. Set up CI/CD workflow files (if requested)
    7. Set up example recurring task workflows (if requested)

    Examples:

        # Interactive setup (recommended)
        sapiens init

        # Non-interactive setup (for CI/CD)
        export GITEA_TOKEN="your-token"
        export CLAUDE_API_KEY="your-key"  # pragma: allowlist secret
        sapiens init --non-interactive

        # Skip Gitea Actions secret setup
        sapiens init --no-setup-secrets

        # Include workflow files
        sapiens init --setup-workflows

        # Include example recurring task workflows
        sapiens init --setup-examples

        # Create CI-specific config
        sapiens init --config-path sapiens_config.ci.yaml
    """
    try:
        initializer = RepoInitializer(
            repo_path=repo_path,
            config_path=config_path,
            backend=backend,
            non_interactive=non_interactive,
            setup_secrets=setup_secrets,
            setup_workflows=setup_workflows,
            setup_examples=setup_examples,
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
        setup_workflows: bool | None,
        setup_examples: bool | None,
    ):
        self.repo_path = repo_path
        self.config_path = config_path
        self.backend = backend or self._detect_backend()
        self.non_interactive = non_interactive
        self.setup_secrets = setup_secrets
        self.setup_workflows = setup_workflows  # None means prompt
        self.setup_examples = setup_examples  # None means prompt

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

        # Ollama/vLLM settings
        self.ollama_base_url = "http://localhost:11434"
        self.ollama_model = "qwen3:latest"
        self.vllm_base_url = "http://localhost:8000/v1"
        self.vllm_model = None
        self.vllm_api_key = None

    def run(self) -> None:
        """Run the initialization workflow."""
        click.echo(click.style("🚀 Initializing repo-sapiens", bold=True, fg="cyan"))
        click.echo()

        # Step 1: Discover repository
        self._discover_repository()

        # Step 2: Collect credentials
        self._collect_credentials()

        # Step 3: Store credentials locally
        self._store_credentials()

        # Step 4: Set up Gitea/GitHub Actions secrets (optional)
        if self.setup_secrets:
            self._setup_gitea_secrets()

        # Step 5: Generate configuration file
        self._generate_config()

        # Step 6: Set up CI/CD workflow files (optional)
        self._setup_workflow_files()

        # Step 7: Set up example recurring task workflows (optional)
        self._setup_example_workflows()

        # Step 8: Validate setup
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
        """Configure AI agent interactively."""
        from repo_sapiens.utils.agent_detector import detect_available_agents, format_agent_list

        click.echo(click.style("🤖 AI Agent Configuration", bold=True, fg="cyan"))
        click.echo()

        # Detect available agents
        available_agents = detect_available_agents()

        # Build choices: detected CLI agents + self-hosted options + API
        agent_choices = []

        if available_agents:
            click.echo(format_agent_list())
            click.echo()

            # Map goose-uvx back to goose for selection
            for agent in available_agents:
                base_agent = agent.replace("-uvx", "")
                if base_agent not in agent_choices:
                    agent_choices.append(base_agent)

        # Always offer self-hosted and API options
        agent_choices.extend(["ollama", "vllm", "api"])

        # Show options
        click.echo("Available options:")
        for choice in agent_choices:
            if choice == "ollama":
                click.echo("  • ollama - Self-hosted Ollama (free, local)")
            elif choice == "vllm":
                click.echo("  • vllm - vLLM/OpenAI-compatible server")
            elif choice == "api":
                click.echo("  • api - Cloud API (Claude, OpenAI)")
            elif choice == "claude":
                click.echo("  • claude - Claude Code CLI")
            elif choice == "goose":
                click.echo("  • goose - Goose CLI")
        click.echo()

        self.agent_type = click.prompt(
            "Which agent do you want to use?",
            type=click.Choice(agent_choices),
            default=agent_choices[0] if agent_choices else "ollama",
        )

        # Configure based on agent type
        if self.agent_type == "claude":
            self._configure_claude()
        elif self.agent_type == "goose":
            self._configure_goose()
        elif self.agent_type == "ollama":
            self._configure_ollama()
        elif self.agent_type == "vllm":
            self._configure_vllm()
        elif self.agent_type == "api":
            self._configure_api()

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

    def _configure_ollama(self) -> None:
        """Configure Ollama as the AI provider."""
        click.echo()
        click.echo(click.style("🦙 Ollama Configuration", bold=True, fg="cyan"))
        click.echo()

        # Base URL
        self.ollama_base_url = click.prompt(
            "Ollama server URL",
            default="http://localhost:11434",
        )

        # Try to discover available models
        models = self._discover_ollama_models()

        if models:
            click.echo()
            click.echo("Available models:")
            for i, model in enumerate(models[:10], 1):  # Show first 10
                click.echo(f"  {i}. {model}")
            if len(models) > 10:
                click.echo(f"  ... and {len(models) - 10} more")
            click.echo()

            # Suggest good models for coding
            recommended = ["qwen3:14b", "qwen3:latest", "qwen3:8b", "llama3.1:8b", "codellama:7b"]
            default_model = next((m for m in recommended if m in models), models[0])

            self.ollama_model = click.prompt(
                "Which model?",
                default=default_model,
            )
        else:
            click.echo()
            click.echo(click.style("⚠ Could not connect to Ollama", fg="yellow"))
            click.echo("Make sure Ollama is running: ollama serve")
            click.echo()
            click.echo("Recommended models for code tasks:")
            click.echo("  • qwen3:14b - Best quality (requires 16GB+ RAM)")
            click.echo("  • qwen3:8b - Good balance")
            click.echo("  • llama3.1:8b - General purpose")
            click.echo("  • codellama:7b - Fast, code-focused")
            click.echo()

            self.ollama_model = click.prompt(
                "Which model? (will be pulled if not present)",
                default="qwen3:latest",
            )

        self.agent_mode = "local"
        click.echo()
        click.echo(
            click.style("💡 Tip:", fg="green")
            + f" Pull the model with: ollama pull {self.ollama_model}"
        )

    def _configure_vllm(self) -> None:
        """Configure vLLM or OpenAI-compatible server as the AI provider."""
        click.echo()
        click.echo(click.style("⚡ vLLM / OpenAI-Compatible Configuration", bold=True, fg="cyan"))
        click.echo()
        click.echo("This works with vLLM, LMStudio, text-generation-inference, and other")
        click.echo("servers that expose an OpenAI-compatible API endpoint.")
        click.echo()

        # Base URL
        self.vllm_base_url = click.prompt(
            "Server URL (including /v1 if needed)",
            default="http://localhost:8000/v1",
        )

        # Model name
        click.echo()
        click.echo("Enter the model name as it appears on your server.")
        click.echo("Examples: Qwen/Qwen3-14B-AWQ, meta-llama/Llama-3.1-8B-Instruct")
        click.echo()

        self.vllm_model = click.prompt(
            "Model name",
            default="Qwen/Qwen3-14B-AWQ",
        )

        # API key (optional for some deployments)
        click.echo()
        needs_key = click.confirm("Does your server require an API key?", default=False)
        if needs_key:
            self.vllm_api_key = click.prompt(
                "Enter API key",
                hide_input=True,
                default="",
            )
            self.agent_api_key = self.vllm_api_key  # Store for credential management

        self.agent_mode = "local"

    def _configure_api(self) -> None:
        """Configure cloud API provider (Claude or OpenAI)."""
        click.echo()
        click.echo(click.style("☁️ Cloud API Configuration", bold=True, fg="cyan"))
        click.echo()

        provider = click.prompt(
            "Which cloud provider?",
            type=click.Choice(["claude", "openai"]),
            default="claude",
        )

        if provider == "claude":
            self.agent_type = "claude"
            self.agent_mode = "api"
            click.echo()
            click.echo("Claude API Key required. Get it from:")
            click.echo("   https://console.anthropic.com/")
            click.echo()
            self.agent_api_key = click.prompt(
                "Enter your Claude API key",
                hide_input=True,
            )
        else:
            # OpenAI - use openai-compatible provider
            self.agent_type = "vllm"  # Reuse vllm config for OpenAI
            self.vllm_base_url = "https://api.openai.com/v1"
            self.vllm_model = click.prompt(
                "Which model?",
                type=click.Choice(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]),
                default="gpt-4o",
            )
            click.echo()
            click.echo("OpenAI API Key required. Get it from:")
            click.echo("   https://platform.openai.com/api-keys")
            click.echo()
            self.vllm_api_key = click.prompt(
                "Enter your OpenAI API key",
                hide_input=True,
            )
            self.agent_api_key = self.vllm_api_key
            self.agent_mode = "api"

    def _discover_ollama_models(self) -> list[str]:
        """Try to fetch available models from Ollama server."""
        import json
        import urllib.request

        try:
            url = f"{self.ollama_base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310
                data = json.loads(response.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

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
            elif self.agent_type == "vllm" and self.vllm_api_key:
                backend.set("vllm", "api_key", self.vllm_api_key)
                click.echo("   ✓ Stored: vllm/api_key")

        # Note: Ollama doesn't require API key storage

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
            elif self.agent_type == "vllm" and self.vllm_api_key:
                backend.set("VLLM_API_KEY", self.vllm_api_key)
                click.echo("   ✓ Set: VLLM_API_KEY")

        # Note: Ollama doesn't require API key

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
        token_secret_name = (  # pragma: allowlist secret
            "GITHUB_TOKEN" if self.provider_type == "github" else "GITEA_TOKEN"
        )
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

            # Determine API key reference based on agent type
            if self.agent_type == "goose" and self.goose_llm_provider:
                agent_api_key_ref = (
                    f"@keyring:{self.goose_llm_provider}/api_key" if self.agent_api_key else "null"
                )
            elif self.agent_type == "claude" and self.agent_api_key:
                agent_api_key_ref = "@keyring:claude/api_key"
            elif self.agent_type == "vllm" and self.vllm_api_key:
                agent_api_key_ref = "@keyring:vllm/api_key"
            else:
                agent_api_key_ref = "null"  # pragma: allowlist secret
        else:
            # fmt: off
            gitea_token_ref = "${GITEA_TOKEN}"  # nosec B105 # Template placeholder for environment variable
            # fmt: on

            # Determine API key reference based on agent type
            if self.agent_type == "goose" and self.goose_llm_provider:
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                agent_api_key_ref = f"${{{env_var}}}" if self.agent_api_key else "null"
            elif self.agent_type == "claude" and self.agent_api_key:
                agent_api_key_ref = "${CLAUDE_API_KEY}"  # pragma: allowlist secret
            elif self.agent_type == "vllm" and self.vllm_api_key:
                agent_api_key_ref = "${VLLM_API_KEY}"  # pragma: allowlist secret
            else:
                agent_api_key_ref = "null"  # pragma: allowlist secret

        # Generate agent provider configuration based on type
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

        elif self.agent_type == "ollama":
            # Ollama configuration
            agent_config = f"""agent_provider:
  provider_type: ollama
  model: {self.ollama_model}
  base_url: {self.ollama_base_url}
  local_mode: true"""

        elif self.agent_type == "vllm":
            # vLLM / OpenAI-compatible configuration
            agent_config = f"""agent_provider:
  provider_type: openai-compatible
  model: {self.vllm_model}
  base_url: {self.vllm_base_url}
  api_key: {agent_api_key_ref}
  local_mode: {str(self.agent_mode == "local").lower()}"""

        else:
            # Claude configuration (default)
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
# Generated by: sapiens init
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

    def _setup_workflow_files(self) -> None:
        """Set up CI/CD workflow files for Gitea or GitHub Actions."""
        # Determine if we should set up workflows
        should_setup = self.setup_workflows

        if should_setup is None and not self.non_interactive:
            # Prompt user
            click.echo()
            provider_name = "GitHub" if self.provider_type == "github" else "Gitea"
            click.echo(click.style(f"📦 {provider_name} Actions Workflows", bold=True, fg="cyan"))
            click.echo()
            click.echo(f"Would you like to add {provider_name} Actions workflow files?")
            click.echo("This will add ready-to-use CI/CD workflows for automated issue processing.")
            click.echo()
            should_setup = click.confirm("Add workflow files?", default=True)

        if not should_setup:
            return

        click.echo()
        click.echo(click.style("📦 Setting up workflow files...", bold=True))

        # Determine source and destination directories
        templates_dir = self._find_templates_dir()
        if not templates_dir:
            click.echo(
                click.style(
                    "   ⚠ Warning: Could not find workflow templates. Skipping.", fg="yellow"
                )
            )
            return

        if self.provider_type == "github":
            source_dir = templates_dir / "github"
            dest_dir = self.repo_path / ".github" / "workflows"
        else:
            source_dir = templates_dir / "gitea"
            dest_dir = self.repo_path / ".gitea" / "workflows"

        if not source_dir.exists():
            click.echo(
                click.style(
                    f"   ⚠ Warning: Template directory not found: {source_dir}", fg="yellow"
                )
            )
            return

        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy workflow files
        copied_files = []
        for src_file in source_dir.glob("*.yaml"):
            dest_file = dest_dir / src_file.name

            # Check if file already exists
            if dest_file.exists():
                if not self.non_interactive:
                    overwrite = click.confirm(
                        f"   {src_file.name} already exists. Overwrite?", default=False
                    )
                    if not overwrite:
                        click.echo(f"   ⏭ Skipped: {src_file.name}")
                        continue
                else:
                    click.echo(f"   ⏭ Skipped (exists): {src_file.name}")
                    continue

            # Copy and customize the file
            content = src_file.read_text()

            # Replace CONFIG_FILE with actual config path
            config_filename = self.config_path.name
            content = content.replace(
                "CONFIG_FILE: sapiens_config.yaml",
                f"CONFIG_FILE: {config_filename}",
            )

            dest_file.write_text(content)
            copied_files.append(src_file.name)
            click.echo(f"   ✓ Created: {dest_file.relative_to(self.repo_path)}")

        if copied_files:
            click.echo()
            click.echo(click.style(f"   ✓ Added {len(copied_files)} workflow file(s)", fg="green"))
        click.echo()

    # Supported languages for security workflow
    SECURITY_LANGUAGES = [
        ("python", "Python", "bandit, pip-audit, safety"),
        ("go", "Go", "gosec, govulncheck"),
        ("java", "Java", "SpotBugs, OWASP Dependency-Check"),
        ("kotlin", "Kotlin", "detekt, OWASP Dependency-Check"),
        ("rust", "Rust", "cargo-audit, cargo-deny"),
        ("cpp", "C/C++", "cppcheck, flawfinder"),
        ("csharp", "C#", "dotnet package audit"),
        ("clojure", "Clojure", "nvd-clojure"),
        ("typescript", "TypeScript", "npm audit, eslint-plugin-security"),
        ("javascript", "JavaScript", "npm audit, eslint-plugin-security"),
    ]

    def _setup_example_workflows(self) -> None:
        """Set up example recurring task workflows (cron-style automation)."""
        # Available example workflows with descriptions
        example_workflows = [
            (
                "post-merge-docs.yaml",
                "Post-merge documentation updates",
                "Automatically updates docs after merges to main",
            ),
            (
                "weekly-test-coverage.yaml",
                "Weekly test coverage improvement",
                "Analyzes coverage and writes tests for under-covered code",
            ),
            (
                "weekly-dependency-audit.yaml",
                "Weekly dependency audit",
                "Checks for outdated/vulnerable dependencies, creates update PRs",
            ),
            (
                "weekly-security-review.yaml",
                "Weekly security review",
                "Multi-language security scans with auto-fix support",
            ),
            (
                "daily-issue-triage.yaml",
                "Daily issue triage",
                "Labels and categorizes new issues, adds initial assessments",
            ),
        ]

        # Determine if we should prompt for examples
        should_prompt = self.setup_examples

        if should_prompt is None and not self.non_interactive:
            # Ask if user wants to see example workflows
            click.echo()
            click.echo(click.style("📅 Example Recurring Task Workflows", bold=True, fg="cyan"))
            click.echo()
            click.echo("repo-sapiens includes example workflows for common recurring tasks.")
            click.echo("These demonstrate how to automate tasks with scheduled CI/CD jobs.")
            click.echo()
            should_prompt = click.confirm(
                "Would you like to select example workflows to add?", default=False
            )

        if not should_prompt:
            return

        # Find templates directory
        templates_dir = self._find_templates_dir()
        if not templates_dir:
            click.echo(
                click.style(
                    "   ⚠ Warning: Could not find workflow templates. Skipping.", fg="yellow"
                )
            )
            return

        if self.provider_type == "github":
            source_dir = templates_dir / "github" / "examples"
            dest_dir = self.repo_path / ".github" / "workflows"
        else:
            source_dir = templates_dir / "gitea" / "examples"
            dest_dir = self.repo_path / ".gitea" / "workflows"

        if not source_dir.exists():
            click.echo(
                click.style(f"   ⚠ Warning: Example templates not found: {source_dir}", fg="yellow")
            )
            return

        click.echo()
        click.echo(click.style("Select which example workflows to add:", bold=True))
        click.echo()

        # Ask about each workflow individually
        selected_workflows = []
        for filename, title, description in example_workflows:
            src_file = source_dir / filename
            if not src_file.exists():
                continue

            dest_file = dest_dir / filename
            exists_note = " (already exists)" if dest_file.exists() else ""

            click.echo(f"  {click.style(title, bold=True)}{exists_note}")
            click.echo(f"    {description}")

            if self.non_interactive:
                # In non-interactive mode with --setup-examples, add all
                if not dest_file.exists():
                    selected_workflows.append((src_file, dest_file, filename))
                    click.echo("    → Adding (non-interactive mode)")
            else:
                if dest_file.exists():
                    add_it = click.confirm("    Add (overwrite existing)?", default=False)
                else:
                    add_it = click.confirm("    Add this workflow?", default=False)

                if add_it:
                    selected_workflows.append((src_file, dest_file, filename))

            click.echo()

        if not selected_workflows:
            click.echo("   No example workflows selected.")
            return

        # Check if security workflow is selected and prompt for languages
        security_languages = None
        security_workflow_selected = any(
            f == "weekly-security-review.yaml" for _, _, f in selected_workflows
        )

        if security_workflow_selected:
            security_languages = self._prompt_security_languages()

        # Create destination directory and copy selected workflows
        dest_dir.mkdir(parents=True, exist_ok=True)

        click.echo(click.style("📅 Adding selected example workflows...", bold=True))

        copied_files = []
        for src_file, dest_file, filename in selected_workflows:
            content = src_file.read_text()

            # Replace security languages placeholder if this is the security workflow
            if filename == "weekly-security-review.yaml" and security_languages:
                content = content.replace("{{SECURITY_LANGUAGES}}", security_languages)

            dest_file.write_text(content)
            copied_files.append(filename)
            click.echo(f"   ✓ Created: {dest_file.relative_to(self.repo_path)}")

        if copied_files:
            click.echo()
            click.echo(
                click.style(f"   ✓ Added {len(copied_files)} example workflow(s)", fg="green")
            )
            click.echo()
            click.echo("   See templates/workflows/examples-README.md for customization tips.")
        click.echo()

    def _prompt_security_languages(self) -> str:
        """Prompt user to select project languages for security scanning."""
        click.echo()
        click.echo(click.style("🔒 Security Workflow Configuration", bold=True, fg="cyan"))
        click.echo()
        click.echo("Select the programming languages used in your project.")
        click.echo("The security workflow will run appropriate scanners for each language.")
        click.echo()

        if self.non_interactive:
            # Default to Python in non-interactive mode
            click.echo("   Using default: python (non-interactive mode)")
            return "python"

        click.echo("Available languages:")
        for lang_id, lang_name, tools in self.SECURITY_LANGUAGES:
            click.echo(f"  • {lang_id:12} - {lang_name} ({tools})")
        click.echo()

        # Prompt for languages
        click.echo("Enter languages separated by spaces (e.g., 'python go rust'):")
        click.echo("Or press Enter for 'python' (default)")
        click.echo()

        selected = click.prompt(
            "Languages",
            default="python",
            show_default=True,
        )

        # Validate selection
        valid_langs = {lang[0] for lang in self.SECURITY_LANGUAGES}
        selected_list = selected.lower().split()
        validated = [lang for lang in selected_list if lang in valid_langs]

        if not validated:
            click.echo(click.style("   ⚠ No valid languages selected, using 'python'", fg="yellow"))
            validated = ["python"]

        result = " ".join(validated)
        click.echo()
        click.echo(f"   ✓ Security scanning configured for: {result}")
        click.echo()

        return result

    def _find_templates_dir(self) -> Path | None:
        """Find the workflow templates directory."""
        # Try relative to package
        import repo_sapiens

        package_dir = Path(repo_sapiens.__file__).parent.parent
        templates_dir = package_dir / "templates" / "workflows"

        if templates_dir.exists():
            return templates_dir

        # Try relative to current working directory (for development)
        cwd_templates = Path.cwd() / "templates" / "workflows"
        if cwd_templates.exists():
            return cwd_templates

        # Try relative to repo path
        repo_templates = self.repo_path / "templates" / "workflows"
        if repo_templates.exists():
            return repo_templates

        return None

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
        click.echo(f"   sapiens --config {self.config_path} daemon --interval 60")
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
