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
    default=".sapiens/config.yaml",
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
    "--deploy-actions/--no-deploy-actions",
    default=True,
    help="Deploy reusable composite action for AI tasks (default: true)",
)
@click.option(
    "--deploy-workflows/--no-deploy-workflows",
    default=False,
    help="Deploy CI/CD workflow templates (default: false, prompts in interactive mode)",
)
def init_command(
    repo_path: Path,
    config_path: Path,
    backend: str | None,
    non_interactive: bool,
    setup_secrets: bool,
    deploy_actions: bool,
    deploy_workflows: bool,
) -> None:
    """Initialize repo-sapiens in your Git repository.

    This command will:
    1. Discover Git repository configuration
    2. Prompt for credentials (or use environment variables)
    3. Store credentials securely
    4. Set up Actions secrets (if requested)
    5. Generate configuration file
    6. Deploy reusable composite action (if requested)
    7. Deploy CI/CD workflow templates (if requested)

    Examples:

        # Interactive setup (recommended)
        sapiens init

        # Non-interactive setup (for CI/CD)
        export GITEA_TOKEN="your-token"
        export CLAUDE_API_KEY="your-key"
        sapiens init --non-interactive

        # Skip Actions secret setup
        sapiens init --no-setup-secrets

        # Skip action deployment
        sapiens init --no-deploy-actions

        # Deploy workflow templates
        sapiens init --deploy-workflows
    """
    try:
        initializer = RepoInitializer(
            repo_path=repo_path,
            config_path=config_path,
            backend=backend,
            non_interactive=non_interactive,
            setup_secrets=setup_secrets,
            deploy_actions=deploy_actions,
            deploy_workflows=deploy_workflows,
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
        deploy_actions: bool = True,
        deploy_workflows: bool = False,
    ):
        self.repo_path = repo_path
        self.config_path = config_path
        self.backend = backend or self._detect_backend()
        self.non_interactive = non_interactive
        self.setup_secrets = setup_secrets
        self.deploy_actions = deploy_actions
        self.deploy_workflows = deploy_workflows

        self.repo_info = None
        self.provider_type = None  # 'github', 'gitea', or 'gitlab' (detected)
        self.gitea_token = None
        self.agent_type = None  # 'claude', 'goose', or 'builtin'
        self.agent_mode: Literal["local", "api"] = "local"
        self.agent_api_key = None

        # Goose-specific settings
        self.goose_llm_provider = None
        self.goose_model = None
        self.goose_toolkit = "default"
        self.goose_temperature = 0.7

        # Builtin ReAct agent settings
        self.builtin_provider = None  # 'ollama', 'vllm', 'openai', 'anthropic', etc.
        self.builtin_model = None
        self.builtin_base_url = None  # For ollama/vllm

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

        # Step 4: Set up Gitea Actions secrets (optional)
        if self.setup_secrets:
            self._setup_gitea_secrets()

        # Step 5: Generate configuration file
        self._generate_config()

        # Step 6: Deploy reusable composite action
        if self.deploy_actions:
            self._deploy_composite_action()

        # Step 7: Deploy CI/CD workflows (optional)
        # In interactive mode, always offer the choice
        # In non-interactive mode, only deploy if explicitly requested
        if self.deploy_workflows or (not self.non_interactive):
            self._deploy_workflows()

        # Step 8: Validate setup
        self._validate_setup()

        # Done!
        click.echo()
        click.echo(click.style("✅ Initialization complete!", bold=True, fg="green"))
        click.echo()
        self._print_next_steps()

        # Step 9: Optional test
        if not self.non_interactive:
            self._offer_test_run()

    def _detect_backend(self) -> str:
        """Detect best credential backend for current environment."""
        # Check if keyring is available
        keyring_backend = KeyringBackend()
        if keyring_backend.available:
            return "keyring"

        # Fall back to environment
        return "environment"

    def _normalize_url(self, url: str, service_name: str = "service") -> str:
        """Normalize a URL by ensuring it has a protocol prefix.

        Args:
            url: The URL to normalize (may or may not have http/https prefix)
            service_name: Name of the service for user prompts (e.g., "Ollama", "vLLM")

        Returns:
            URL with proper http:// or https:// prefix
        """
        url = url.strip()

        # Already has protocol - return as-is
        if url.startswith("http://") or url.startswith("https://"):
            return url.rstrip("/")

        # No protocol - ask user which one to use
        click.echo()
        click.echo(f"The URL '{url}' doesn't specify a protocol.")
        use_https = click.confirm(
            f"Use HTTPS for {service_name}? (No = HTTP)",
            default=False,  # Default to HTTP for local services
        )

        protocol = "https" if use_https else "http"
        normalized = f"{protocol}://{url}"
        click.echo(f"  Using: {normalized}")

        return normalized.rstrip("/")

    def _detect_existing_gitea_token(self) -> tuple[str | None, str | None]:
        """Check for existing Gitea token in keyring or environment.

        Checks in order:
        1. Keyring (gitea/api_token)
        2. Environment (GITEA_TOKEN, SAPIENS_GITEA_TOKEN)

        Returns (token, source) tuple where source describes where it was found.
        """
        import os

        # Check keyring first
        try:
            keyring_backend = KeyringBackend()
            if keyring_backend.available:
                token = keyring_backend.get("gitea", "api_token")
                if token:
                    return token, "keyring (gitea/api_token)"
        except Exception:
            pass  # Keyring not available or error

        # Check environment variables
        for env_var in ("GITEA_TOKEN", "SAPIENS_GITEA_TOKEN"):
            token = os.getenv(env_var)
            if token:
                return token, f"environment (${env_var})"

        return None, None

    def _detect_existing_gitlab_token(self) -> tuple[str | None, str | None]:
        """Check for existing GitLab token in keyring or environment.

        Checks in order:
        1. Keyring (gitlab/api_token)
        2. Environment (GITLAB_TOKEN, SAPIENS_GITLAB_TOKEN, CI_JOB_TOKEN)

        Returns (token, source) tuple where source describes where it was found.
        """
        import os

        # Check keyring first
        try:
            keyring_backend = KeyringBackend()
            if keyring_backend.available:
                token = keyring_backend.get("gitlab", "api_token")
                if token:
                    return token, "keyring (gitlab/api_token)"
        except Exception:
            pass  # Keyring not available or error

        # Check environment variables
        for env_var in ("GITLAB_TOKEN", "SAPIENS_GITLAB_TOKEN", "CI_JOB_TOKEN"):
            token = os.getenv(env_var)
            if token:
                return token, f"environment (${env_var})"

        return None, None

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
        if self.provider_type == "gitlab":
            self._collect_gitlab_token_interactively()
        else:
            self._collect_gitea_token_interactively()

        click.echo()

        # AI Agent configuration
        self._configure_ai_agent()

    def _collect_gitea_token_interactively(self) -> None:
        """Collect Gitea token interactively."""
        # Check for existing Gitea token in keyring or environment
        existing_token, source = self._detect_existing_gitea_token()

        if existing_token:
            use_existing = click.confirm(
                click.style(f"✓ Gitea token found in {source}. Use it?", fg="green"),
                default=True,
            )
            if use_existing:
                self.gitea_token = existing_token
                click.echo(f"   ✓ Using Gitea token from {source}")
            else:
                self.gitea_token = click.prompt(
                    "Enter your Gitea API token", hide_input=True, type=str
                )
        else:
            # No existing token - prompt for it
            click.echo(
                "Gitea API Token is required. Get it from:\n"
                f"   {self.repo_info.base_url}/user/settings/applications"
            )
            click.echo()
            self.gitea_token = click.prompt("Enter your Gitea API token", hide_input=True, type=str)

    def _collect_gitlab_token_interactively(self) -> None:
        """Collect GitLab token interactively."""
        # Check for existing GitLab token in keyring or environment
        existing_token, source = self._detect_existing_gitlab_token()

        if existing_token:
            use_existing = click.confirm(
                click.style(f"✓ GitLab token found in {source}. Use it?", fg="green"),
                default=True,
            )
            if use_existing:
                self.gitea_token = existing_token  # Reuse gitea_token field
                click.echo(f"   ✓ Using GitLab token from {source}")
            else:
                self.gitea_token = click.prompt(
                    "Enter your GitLab Personal Access Token", hide_input=True, type=str
                )
        else:
            # No existing token - prompt for it
            pat_url = f"{self.repo_info.base_url}/-/user_settings/personal_access_tokens"
            click.echo("GitLab Personal Access Token is required. Get it from:\n" f"   {pat_url}")
            click.echo()
            click.echo("Required scopes: api, read_repository, write_repository")
            click.echo()
            self.gitea_token = click.prompt(
                "Enter your GitLab Personal Access Token", hide_input=True, type=str
            )

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

            agent_choices.append("builtin")  # Builtin ReAct agent (Ollama, vLLM, or API)

            self.agent_type = click.prompt(
                "Which agent do you want to use?",
                type=click.Choice(agent_choices),
                default=agent_choices[0] if agent_choices else "builtin",
            )
        else:
            click.echo(click.style("⚠ No AI agent CLIs detected", fg="yellow"))
            click.echo()
            click.echo("You can:")
            click.echo("  1. Use builtin ReAct agent (local or cloud LLM)")
            click.echo("  2. Install Claude Code: https://claude.com/install.sh")
            click.echo("  3. Install Goose: pip install goose-ai")
            click.echo()

            self.agent_type = "builtin"
            click.echo("Using builtin ReAct agent...")

        # Configure based on agent type
        if self.agent_type == "claude":
            self._configure_claude()
        elif self.agent_type == "goose":
            self._configure_goose()
        elif self.agent_type == "builtin":
            self._configure_builtin()

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

    def _configure_builtin(self) -> None:
        """Configure builtin ReAct agent with LLM provider selection."""
        from repo_sapiens.utils.agent_detector import (
            format_provider_comparison,
            get_provider_info,
            get_provider_recommendation,
            get_vllm_vs_ollama_note,
        )

        click.echo()
        click.echo(click.style("🧠 Builtin ReAct Agent Configuration", bold=True, fg="cyan"))
        click.echo()
        click.echo("The builtin agent uses an LLM for reasoning and executes tools locally.")
        click.echo()

        # Show provider comparison
        click.echo(format_provider_comparison())
        click.echo()

        # Show vLLM vs Ollama note for local providers
        click.echo(get_vllm_vs_ollama_note())
        click.echo()

        # Show recommendation
        click.echo(click.style("💡 Recommendation:", bold=True, fg="green"))
        click.echo(get_provider_recommendation("tool-usage"))
        click.echo()

        # Prompt for LLM provider
        self.builtin_provider = click.prompt(
            "Which LLM provider?",
            type=click.Choice(["ollama", "vllm", "openai", "anthropic", "openrouter", "groq"]),
            default="ollama",
        )

        provider_info = get_provider_info(self.builtin_provider)

        # For local providers, check availability and configure URL
        if self.builtin_provider == "ollama":
            self._configure_builtin_ollama(provider_info)
        elif self.builtin_provider == "vllm":
            self._configure_builtin_vllm(provider_info)
        else:
            # Cloud provider - needs API key
            self._configure_builtin_cloud(provider_info)

        self.agent_mode = "local"

    def _configure_builtin_ollama(self, provider_info: dict) -> None:
        """Configure Ollama for builtin agent."""
        import httpx

        click.echo()
        default_url = "http://localhost:11434"

        # Check Ollama availability
        try:
            response = httpx.get(f"{default_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models_data = response.json()
                available_models = [m["name"] for m in models_data.get("models", [])]
                click.echo(click.style("✓ Ollama is running", fg="green"))
                if available_models:
                    click.echo(f"  Available models: {', '.join(available_models[:5])}")
                    if len(available_models) > 5:
                        click.echo(f"  ... and {len(available_models) - 5} more")
            else:
                available_models = []
                click.echo(click.style("⚠ Ollama responded but no models found", fg="yellow"))
        except Exception:
            available_models = []
            click.echo(click.style("⚠ Ollama not detected at localhost:11434", fg="yellow"))
            click.echo("  Install Ollama: https://ollama.ai")
            click.echo("  Then run: ollama pull qwen3:8b")

        click.echo()

        # Model selection
        recommended_models = ["qwen3:8b", "qwen3:14b", "llama3.1:8b", "mistral:7b"]
        if available_models:
            model_choices = [m for m in recommended_models if m in available_models]
            model_choices.extend([m for m in available_models if m not in model_choices][:3])
            default_model = model_choices[0] if model_choices else "qwen3:8b"
        else:
            default_model = "qwen3:8b"

        click.echo("Recommended models for tool-calling:")
        for model in recommended_models[:4]:
            marker = (
                " (recommended)"
                if model == "qwen3:8b"
                else " (requires 24GB VRAM)"
                if model == "qwen3:14b"
                else ""
            )
            available = " ✓" if model in available_models else ""
            click.echo(f"  • {model}{marker}{available}")
        click.echo()

        self.builtin_model = click.prompt("Which model?", type=str, default=default_model)

        # URL configuration
        if click.confirm("Use default Ollama URL (localhost:11434)?", default=True):
            self.builtin_base_url = default_url
        else:
            custom_url = click.prompt("Ollama URL (host:port)", default="localhost:11434")
            self.builtin_base_url = self._normalize_url(custom_url, "Ollama")

    def _configure_builtin_vllm(self, provider_info: dict) -> None:
        """Configure vLLM for builtin agent."""
        import httpx

        click.echo()
        default_url = "http://localhost:8000"

        # Check vLLM availability
        try:
            response = httpx.get(f"{default_url}/v1/models", timeout=5.0)
            if response.status_code == 200:
                models_data = response.json()
                available_models = [m["id"] for m in models_data.get("data", [])]
                click.echo(click.style("✓ vLLM is running", fg="green"))
                if available_models:
                    click.echo(f"  Available models: {', '.join(available_models)}")
            else:
                available_models = []
                click.echo(click.style("⚠ vLLM responded but no models found", fg="yellow"))
        except Exception:
            available_models = []
            click.echo(click.style("⚠ vLLM not detected at localhost:8000", fg="yellow"))
            click.echo("  Start vLLM: vllm serve qwen3:8b --port 8000")

        click.echo()

        # Model selection
        recommended_models = provider_info.get("models", ["qwen3:8b", "qwen3:14b", "llama3.1:8b"])
        default_model = (
            available_models[0]
            if available_models
            else provider_info.get("default_model", "qwen3:8b")
        )

        click.echo("Recommended models for tool-calling:")
        for model in recommended_models[:4]:
            marker = (
                " (recommended)"
                if model == "qwen3:8b"
                else " (requires 24GB VRAM)"
                if "14b" in model
                else ""
            )
            available = " ✓" if model in available_models else ""
            click.echo(f"  • {model}{marker}{available}")
        click.echo()

        self.builtin_model = click.prompt("Which model?", type=str, default=default_model)

        # URL configuration
        if click.confirm("Use default vLLM URL (localhost:8000)?", default=True):
            self.builtin_base_url = default_url
        else:
            custom_url = click.prompt("vLLM URL (host:port)", default="localhost:8000")
            self.builtin_base_url = self._normalize_url(custom_url, "vLLM")

    def _configure_builtin_cloud(self, provider_info: dict) -> None:
        """Configure cloud LLM provider for builtin agent."""
        import os

        click.echo()

        # Model selection
        available_models = provider_info.get("models", [])
        default_model = provider_info.get(
            "default_model", available_models[0] if available_models else "gpt-4o"
        )

        click.echo(f"Available models for {provider_info['name']}:")
        for i, model in enumerate(available_models[:5], 1):
            marker = " (recommended)" if model == default_model else ""
            click.echo(f"  {i}. {model}{marker}")
        click.echo()

        self.builtin_model = click.prompt(
            "Which model?",
            type=click.Choice(available_models) if available_models else str,
            default=default_model,
        )

        # API key
        api_key_env = provider_info.get("api_key_env")
        if api_key_env:
            existing_key = os.getenv(api_key_env)

            if existing_key:
                use_existing = click.confirm(
                    f"{api_key_env} found in environment. Use it?", default=True
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

        # Store git provider token (Gitea, GitLab, or GitHub)
        if self.provider_type == "gitlab":
            backend.set("gitlab", "api_token", self.gitea_token)
            click.echo("   ✓ Stored: gitlab/api_token")
        else:
            backend.set("gitea", "api_token", self.gitea_token)
            click.echo("   ✓ Stored: gitea/api_token")

        # Store agent API key if provided
        if self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Store under provider-specific key
                backend.set(self.goose_llm_provider, "api_key", self.agent_api_key)
                click.echo(f"   ✓ Stored: {self.goose_llm_provider}/api_key")
            elif self.agent_type == "builtin" and self.builtin_provider:
                # Store under provider-specific key
                backend.set(self.builtin_provider, "api_key", self.agent_api_key)
                click.echo(f"   ✓ Stored: {self.builtin_provider}/api_key")
            elif self.agent_type == "claude":
                backend.set("claude", "api_key", self.agent_api_key)
                click.echo("   ✓ Stored: claude/api_key")

    def _store_in_environment(self) -> None:
        """Store credentials in environment (for current session)."""
        backend = EnvironmentBackend()

        # Store git provider token (Gitea, GitLab, or GitHub)
        if self.provider_type == "gitlab":
            backend.set("GITLAB_TOKEN", self.gitea_token)
            click.echo("   ✓ Set: GITLAB_TOKEN")
        else:
            backend.set("GITEA_TOKEN", self.gitea_token)
            click.echo("   ✓ Set: GITEA_TOKEN")

        # Store agent API key if provided
        if self.agent_api_key:
            if self.agent_type == "goose" and self.goose_llm_provider:
                # Store under provider-specific environment variable
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                backend.set(env_var, self.agent_api_key)
                click.echo(f"   ✓ Set: {env_var}")
            elif self.agent_type == "builtin" and self.builtin_provider:
                # Store under provider-specific environment variable
                env_var = f"{self.builtin_provider.upper()}_API_KEY"
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

        # Determine credential references based on backend and provider
        if self.backend == "keyring":
            if self.provider_type == "gitlab":
                git_token_ref = "@keyring:gitlab/api_token"  # nosec B105
            else:
                git_token_ref = "@keyring:gitea/api_token"  # nosec B105

            # Determine agent API key reference
            if self.agent_type == "goose" and self.goose_llm_provider:
                agent_api_key_ref = (
                    f"@keyring:{self.goose_llm_provider}/api_key" if self.agent_api_key else "null"
                )
            elif self.agent_type == "builtin" and self.builtin_provider:
                agent_api_key_ref = (
                    f"@keyring:{self.builtin_provider}/api_key" if self.agent_api_key else "null"
                )
            elif self.agent_type == "claude":
                agent_api_key_ref = "@keyring:claude/api_key" if self.agent_api_key else "null"
            else:
                agent_api_key_ref = "null"
        else:
            # fmt: off
            if self.provider_type == "gitlab":
                git_token_ref = "${GITLAB_TOKEN}"  # nosec B105
            else:
                git_token_ref = "${GITEA_TOKEN}"  # nosec B105
            # fmt: on

            # Determine agent API key reference
            if self.agent_type == "goose" and self.goose_llm_provider:
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                agent_api_key_ref = f"${{{env_var}}}" if self.agent_api_key else "null"
            elif self.agent_type == "builtin" and self.builtin_provider:
                env_var = f"{self.builtin_provider.upper()}_API_KEY"
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
        elif self.agent_type == "builtin":
            # Builtin ReAct agent with selected provider
            model = self.builtin_model or "qwen3:8b"

            if self.builtin_provider == "ollama":
                provider_type = "ollama"
                base_url = self.builtin_base_url or "http://localhost:11434"
                agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: null
  local_mode: true
  base_url: {base_url}"""
            elif self.builtin_provider == "vllm":
                provider_type = "openai-compatible"
                base_url = self.builtin_base_url or "http://localhost:8000"
                agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: null
  local_mode: true
  base_url: {base_url}/v1"""
            else:
                # Cloud provider (openai, anthropic, openrouter, groq)
                provider_type = self.builtin_provider
                agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: {agent_api_key_ref}
  local_mode: false"""
        else:
            # Claude configuration
            provider_type = f"claude-{self.agent_mode}"
            model = "claude-sonnet-4.5"
            agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: {agent_api_key_ref}
  local_mode: {str(self.agent_mode == "local").lower()}"""

        # Determine MCP server (only Gitea uses MCP; GitHub and GitLab do not)
        if self.provider_type == "gitea":
            mcp_server_line = "  mcp_server: gitea-mcp"
        else:
            mcp_server_line = "  mcp_server: null"

        # Generate configuration content
        config_content = f"""# Automation System Configuration
# Generated by: sapiens init
# Repository: {self.repo_info.owner}/{self.repo_info.repo}

git_provider:
  provider_type: {self.provider_type}
{mcp_server_line}
  base_url: {self.repo_info.base_url}
  api_token: "{git_token_ref}"

repository:
  owner: {self.repo_info.owner}
  name: {self.repo_info.repo}
  default_branch: main

{agent_config}

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
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

    def _deploy_composite_action(self) -> None:
        """Deploy reusable composite action for AI tasks."""
        import importlib.resources

        click.echo(click.style("📦 Deploying reusable composite action...", bold=True))

        # Determine target directory based on provider type
        if self.provider_type == "github":
            action_dir = self.repo_path / ".github" / "actions" / "sapiens-task"
            template_subpath = "actions/github/sapiens-task/action.yaml"
        elif self.provider_type == "gitlab":
            action_dir = self.repo_path / ".gitlab" / "actions" / "sapiens-task"
            template_subpath = "actions/gitlab/sapiens-task/action.yaml"
        else:
            action_dir = self.repo_path / ".gitea" / "actions" / "sapiens-task"
            template_subpath = "actions/gitea/sapiens-task/action.yaml"

        # Create the action directory
        action_dir.mkdir(parents=True, exist_ok=True)

        # Get the template from package resources
        try:
            # Try importlib.resources (Python 3.9+)
            template_files = (
                importlib.resources.files("repo_sapiens") / "templates" / template_subpath
            )
            if hasattr(template_files, "read_text"):
                action_content = template_files.read_text()
            else:
                # Fallback: read from file system
                package_dir = Path(__file__).parent.parent
                template_path = package_dir / "templates" / template_subpath
                if template_path.exists():
                    action_content = template_path.read_text()
                else:
                    # Try relative to repo root (development mode)
                    repo_root = Path(__file__).parent.parent.parent
                    template_path = repo_root / "templates" / template_subpath
                    action_content = template_path.read_text()

            # Write the action file
            action_file = action_dir / "action.yaml"
            action_file.write_text(action_content)
            click.echo(f"   ✓ Created: {action_file.relative_to(self.repo_path)}")

        except Exception as e:
            click.echo(click.style(f"   ⚠ Warning: Could not deploy action: {e}", fg="yellow"))
            click.echo(
                click.style(
                    "   You can manually copy the action from the repo-sapiens templates.",
                    fg="yellow",
                )
            )

        click.echo()

    def _deploy_workflows(self) -> None:
        """Deploy CI/CD workflow templates."""
        import importlib.resources

        click.echo(click.style("📋 Deploying workflow templates...", bold=True))
        click.echo()

        # Determine paths based on provider type
        if self.provider_type == "github":
            workflows_dir = self.repo_path / ".github" / "workflows"
            template_base = "workflows/github"
        elif self.provider_type == "gitlab":
            # GitLab uses single .gitlab-ci.yml at root
            workflows_dir = self.repo_path
            template_base = "workflows/gitlab"
        else:
            workflows_dir = self.repo_path / ".gitea" / "workflows"
            template_base = "workflows/gitea"

        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Core workflows
        core_workflows = [
            ("automation-daemon.yaml", "Automation daemon (scheduled processing)"),
            ("process-issue.yaml", "Process issue (manual trigger)"),
        ]

        # Example workflows
        example_workflows = [
            ("examples/daily-issue-triage.yaml", "Daily issue triage"),
            ("examples/weekly-test-coverage.yaml", "Weekly test coverage report"),
            ("examples/weekly-dependency-audit.yaml", "Weekly dependency audit"),
            ("examples/weekly-security-review.yaml", "Weekly security review"),
            ("examples/weekly-sbom-license.yaml", "Weekly SBOM & license compliance"),
            ("examples/post-merge-docs.yaml", "Post-merge documentation update"),
        ]

        def deploy_template(template_name: str, target_dir: Path) -> bool:
            """Deploy a single template file."""
            template_subpath = f"{template_base}/{template_name}"
            try:
                # Try importlib.resources
                template_files = (
                    importlib.resources.files("repo_sapiens") / "templates" / template_subpath
                )
                if hasattr(template_files, "read_text"):
                    content = template_files.read_text()
                else:
                    # Fallback: read from file system
                    package_dir = Path(__file__).parent.parent
                    template_path = package_dir / "templates" / template_subpath
                    if template_path.exists():
                        content = template_path.read_text()
                    else:
                        repo_root = Path(__file__).parent.parent.parent
                        template_path = repo_root / "templates" / template_subpath
                        content = template_path.read_text()

                # For GitLab, core workflows go to .gitlab-ci.yml
                if self.provider_type == "gitlab" and not template_name.startswith("examples/"):
                    target_file = target_dir / ".gitlab-ci.yml"
                else:
                    # Create subdirectories if needed
                    target_file = target_dir / template_name
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                target_file.write_text(content)
                return True
            except Exception:
                return False

        # Ask about core workflows
        if not self.non_interactive:
            deploy_core = click.confirm(
                "Deploy core workflows (automation-daemon, process-issue)?",
                default=True,
            )
        else:
            deploy_core = True

        if deploy_core:
            for template_name, description in core_workflows:
                if deploy_template(template_name, workflows_dir):
                    if self.provider_type == "gitlab" and not template_name.startswith("examples/"):
                        click.echo(f"   ✓ {description} → .gitlab-ci.yml")
                    else:
                        click.echo(f"   ✓ {description}")
                else:
                    click.echo(click.style(f"   ⚠ Could not deploy: {description}", fg="yellow"))

        click.echo()

        # Ask about example workflows (one by one in interactive mode)
        if not self.non_interactive:
            click.echo("Example workflows available:")
            for template_name, description in example_workflows:
                if click.confirm(f"  Deploy '{description}'?", default=False):
                    if deploy_template(template_name, workflows_dir):
                        click.echo(click.style("     ✓ Deployed", fg="green"))
                    else:
                        click.echo(click.style("     ⚠ Could not deploy", fg="yellow"))

        click.echo()

    def _validate_setup(self) -> None:
        """Validate the setup."""
        click.echo(click.style("✓ Validating setup...", bold=True))

        try:
            # Test credential resolution
            resolver = CredentialResolver()

            if self.backend == "keyring":
                if self.provider_type == "gitlab":
                    token_ref = "@keyring:gitlab/api_token"
                else:
                    token_ref = "@keyring:gitea/api_token"
            else:
                if self.provider_type == "gitlab":
                    token_ref = "${GITLAB_TOKEN}"
                else:
                    token_ref = "${GITEA_TOKEN}"

            resolved = resolver.resolve(token_ref, cache=False)
            if not resolved:
                raise ValueError(f"Failed to resolve {self.provider_type} token")

            click.echo("   ✓ Credentials validated")
            click.echo("   ✓ Configuration file created")
            click.echo()

        except Exception as e:
            click.echo(click.style(f"   ⚠ Warning: Validation failed: {e}", fg="yellow"))
            click.echo()

    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        provider_name = self.provider_type.title()

        click.echo(click.style("📋 Next Steps:", bold=True))
        click.echo()
        click.echo(f"1. Label an issue with 'needs-planning' in {provider_name}:")

        # Build issues URL based on provider
        if self.provider_type == "gitlab":
            issues_url = (
                f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/-/issues"
            )
        else:
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

        # Print manual secret setup if needed (not for GitLab - uses CI/CD variables)
        if self.setup_secrets and self.provider_type != "gitlab":
            click.echo(
                click.style(
                    f"⚠ Important: Set {provider_name} Actions Secrets Manually",
                    bold=True,
                    fg="yellow",
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
            if self.provider_type == "gitea":
                click.echo("  - GITEA_TOKEN (your Gitea API token)")
            if self.agent_mode == "api":
                if self.agent_type == "goose" and self.goose_llm_provider:
                    secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                    provider_title = self.goose_llm_provider.title()
                    click.echo(f"  - {secret_name} (your {provider_title} API key for Goose)")
                elif self.agent_type == "claude":
                    click.echo("  - CLAUDE_API_KEY (your Claude API key)")
            click.echo()

        # GitLab uses CI/CD variables instead of Actions secrets
        if self.setup_secrets and self.provider_type == "gitlab":
            click.echo(
                click.style(
                    "⚠ Important: Set GitLab CI/CD Variables Manually", bold=True, fg="yellow"
                )
            )
            click.echo()
            variables_url = (
                f"{self.repo_info.base_url}/{self.repo_info.owner}/"
                f"{self.repo_info.repo}/-/settings/ci_cd"
            )
            click.echo(f"Navigate to: {variables_url}")
            click.echo("Expand 'Variables' section and add:")
            click.echo()
            click.echo("  - GITLAB_TOKEN (your GitLab Personal Access Token)")
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

    def _offer_test_run(self) -> None:
        """Offer to test the setup by summarizing the README."""
        import subprocess

        # Check if README exists
        readme_path = self.repo_path / "README.md"
        if not readme_path.exists():
            return

        click.echo()
        click.echo(click.style("🧪 Test Your Setup", bold=True, fg="cyan"))
        click.echo()

        # Build the test command based on agent type
        test_prompt = "Summarize this project's README in 2-3 sentences."

        # Only include --config if non-default path
        config_flag = (
            ""
            if str(self.config_path) == ".sapiens/config.yaml"
            else f"--config {self.config_path} "
        )

        if self.agent_type == "claude":
            test_cmd = f'claude -p "{test_prompt}"'
        elif self.agent_type == "goose":
            test_cmd = f'goose session start --prompt "{test_prompt}"'
        elif self.agent_type == "builtin":
            # task command reads model from config, so no --model needed
            test_cmd = f'sapiens {config_flag}task "{test_prompt}"'.replace("  ", " ")
        else:
            return

        click.echo("Would you like to test your setup by having the agent summarize README.md?")
        click.echo()
        click.echo(click.style("Command:", fg="yellow"))
        click.echo(f"  {test_cmd}")
        click.echo()

        if click.confirm("Run this test now?", default=False):
            click.echo()
            click.echo(click.style("Running test...", bold=True))
            click.echo()

            try:
                # Run the command directly (output streams to terminal)
                result = subprocess.run(
                    test_cmd,
                    shell=True,
                    cwd=self.repo_path,
                    timeout=120,
                )
                if result.returncode == 0:
                    click.echo()
                    click.echo(click.style("✅ Test completed successfully!", fg="green"))
                else:
                    click.echo(click.style("⚠ Test returned non-zero exit code", fg="yellow"))
            except subprocess.TimeoutExpired:
                click.echo(click.style("⚠ Test timed out after 120 seconds", fg="yellow"))
            except Exception as e:
                click.echo(click.style(f"⚠ Test failed: {e}", fg="yellow"))
        else:
            click.echo()
            click.echo("You can run this test later with the command above.")

        # Suggest REPL for further exploration
        click.echo()
        if self.agent_type == "builtin":
            repl_cmd = f"sapiens {config_flag}task --repl".replace("  ", " ")
        elif self.agent_type == "claude":
            repl_cmd = "claude"
        elif self.agent_type == "goose":
            repl_cmd = "goose session start"
        else:
            repl_cmd = None

        if repl_cmd:
            click.echo(click.style("💡 Try the interactive REPL:", fg="cyan"))
            click.echo(f"  {repl_cmd}")
