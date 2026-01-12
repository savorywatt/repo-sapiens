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
@click.option("--non-interactive", is_flag=True, help="Non-interactive mode (requires environment variables)")
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
        export SAPIENS_GITEA_TOKEN="your-token"
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
            click.style("Make sure you're in a Git repository with a configured remote.", fg="yellow"),
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

        # Automation mode settings
        self.automation_mode = "native"  # 'native', 'daemon', or 'hybrid'
        self.label_prefix = "sapiens/"

        # Configuration mode settings
        self.run_mode: Literal["local", "cicd", "both"] = "local"  # What to configure
        self.config_target: Literal["local", "cicd"] = "local"  # Current configuration pass
        self.cicd_config_path: Path | None = None  # Custom CI/CD config path

        # Existing config tracking
        self.existing_config: dict | None = None
        self.update_git_provider = True
        self.update_agent_provider = True
        self.update_credentials = True
        self.update_automation = True

    def _load_existing_config(self) -> bool:
        """Load existing configuration if present.

        Returns True if config exists and was loaded.
        """
        import yaml

        # Determine which config file to load
        if self.config_target == "cicd" and self.cicd_config_path:
            config_file = self.repo_path / self.cicd_config_path
        else:
            config_file = self.repo_path / self.config_path

        if not config_file.exists():
            return False

        try:
            with open(config_file) as f:
                self.existing_config = yaml.safe_load(f)
            return True
        except Exception:
            return False

    def _show_existing_config(self) -> None:
        """Display current configuration summary."""
        if not self.existing_config:
            return

        click.echo(click.style("📋 Existing configuration found:", bold=True, fg="yellow"))
        click.echo()

        # Git provider section
        git = self.existing_config.get("git_provider", {})
        if git:
            click.echo(click.style("  Git Provider:", bold=True))
            click.echo(f"    Type: {git.get('provider_type', 'unknown')}")
            click.echo(f"    URL: {git.get('base_url', 'unknown')}")
            click.echo()

        # Repository section
        repo = self.existing_config.get("repository", {})
        if repo:
            click.echo(click.style("  Repository:", bold=True))
            click.echo(f"    {repo.get('owner', '?')}/{repo.get('name', '?')}")
            click.echo()

        # Agent provider section
        agent = self.existing_config.get("agent_provider", {})
        if agent:
            click.echo(click.style("  Agent Provider:", bold=True))
            click.echo(f"    Type: {agent.get('provider_type', 'unknown')}")
            click.echo(f"    Model: {agent.get('model', 'unknown')}")
            if agent.get("base_url"):
                click.echo(f"    URL: {agent.get('base_url')}")
            click.echo()

    def _prompt_update_sections(self) -> None:
        """Ask user which sections to update."""
        if self.non_interactive:
            # In non-interactive mode, update everything
            return

        click.echo(click.style("What would you like to update?", bold=True))
        click.echo()

        self.update_git_provider = click.confirm("  Update git provider settings?", default=False)
        self.update_agent_provider = click.confirm("  Update agent provider settings?", default=False)
        self.update_credentials = click.confirm("  Update stored credentials?", default=False)
        self.update_automation = click.confirm("  Update automation mode settings?", default=False)

        # If nothing selected, offer to start fresh
        if not any(
            [self.update_git_provider, self.update_agent_provider, self.update_credentials, self.update_automation]
        ):
            click.echo()
            if click.confirm("No updates selected. Start fresh with new configuration?", default=False):
                self.update_git_provider = True
                self.update_agent_provider = True
                self.update_credentials = True
                self.update_automation = True
                self.existing_config = None  # Treat as fresh install
            else:
                click.echo()
                click.echo("No changes made. Exiting.")
                raise SystemExit(0)

        click.echo()

    def _load_agent_type_from_config(self) -> None:
        """Load agent type from existing config for downstream steps."""
        if not self.existing_config:
            return

        agent = self.existing_config.get("agent_provider", {})
        provider_type = agent.get("provider_type", "")

        if provider_type.startswith("claude"):
            self.agent_type = "claude"
            self.agent_mode = "api" if provider_type == "claude-api" else "local"
        elif provider_type.startswith("goose"):
            self.agent_type = "goose"
            self.agent_mode = "api" if provider_type == "goose-api" else "local"
            goose_config = agent.get("goose_config", {})
            self.goose_llm_provider = goose_config.get("llm_provider")
            self.goose_model = agent.get("model")
        elif provider_type in ("ollama", "openai-compatible"):
            self.agent_type = "builtin"
            self.builtin_provider = "ollama" if provider_type == "ollama" else "vllm"
            self.builtin_model = agent.get("model")
            self.builtin_base_url = agent.get("base_url")
        else:
            self.agent_type = "builtin"
            self.builtin_provider = provider_type
            self.builtin_model = agent.get("model")

    def _load_automation_from_config(self) -> None:
        """Load automation settings from existing config."""
        if not self.existing_config:
            return

        automation = self.existing_config.get("automation", {})
        mode_config = automation.get("mode", {})

        self.automation_mode = mode_config.get("mode", "native")
        self.label_prefix = mode_config.get("label_prefix", "sapiens/")

    def _prompt_configuration_mode(self) -> None:
        """Ask user whether to configure for local, CI/CD, or both."""
        if self.non_interactive:
            # In non-interactive mode, use command-line specified config path
            self.run_mode = "local"  # Default to local
            self.config_target = "local"
            return

        click.echo(click.style("Configuration Target", bold=True))
        click.echo()
        click.echo("Where will sapiens run?")
        click.echo("  1. Local only (development, testing)")
        click.echo("  2. CI/CD only (Gitea Actions, GitHub Actions)")
        click.echo("  3. Both (create separate configs)")
        click.echo()

        choice = click.prompt(
            "Select configuration target",
            type=click.Choice(["1", "2", "3"]),
            default="1",
            show_choices=False,
        )

        if choice == "1":
            self.run_mode = "local"
            self.config_target = "local"
        elif choice == "2":
            self.run_mode = "cicd"
            self.config_target = "cicd"
        else:
            self.run_mode = "both"
            self.config_target = "local"  # Start with local

        click.echo()

    def _prompt_cicd_config_path(self) -> None:
        """Ask for CI/CD config file path."""
        if self.non_interactive:
            self.cicd_config_path = Path("sapiens_config.ci.yaml")
            return

        default_path = "sapiens_config.ci.yaml"
        click.echo(click.style("CI/CD Configuration Path", bold=True))
        click.echo()
        click.echo("Where should the CI/CD config be saved?")
        click.echo(f"(Default: {default_path} in project root)")
        click.echo()

        path_str = click.prompt(
            "Config path",
            default=default_path,
            type=str,
        )

        self.cicd_config_path = Path(path_str)
        click.echo()

    def run(self) -> None:
        """Run the initialization workflow."""
        click.echo(click.style("🚀 Initializing repo-sapiens", bold=True, fg="cyan"))
        click.echo()

        # Ask what to configure (local, CI/CD, or both)
        self._prompt_configuration_mode()

        # If configuring both, we'll loop through twice
        if self.run_mode == "both":
            # First pass: local configuration
            click.echo(click.style("=== Configuring for Local Development ===", bold=True, fg="cyan"))
            click.echo()
            self.config_target = "local"
            self._run_configuration_pass()

            # Reset update flags for second pass
            self.existing_config = None
            self.update_git_provider = True
            self.update_agent_provider = True
            self.update_credentials = True
            self.update_automation = True

            # Second pass: CI/CD configuration
            click.echo()
            click.echo(click.style("=== Configuring for CI/CD ===", bold=True, fg="cyan"))
            click.echo()
            self.config_target = "cicd"
            self._prompt_cicd_config_path()
            self._run_configuration_pass()
        else:
            # Single pass configuration
            if self.config_target == "cicd":
                self._prompt_cicd_config_path()
            self._run_configuration_pass()

        # Done!
        click.echo()
        click.echo(click.style("✅ Initialization complete!", bold=True, fg="green"))
        click.echo()
        self._print_next_steps()

        # Optional test (only for local config)
        if not self.non_interactive and (self.run_mode == "local" or self.run_mode == "both"):
            self._offer_test_run()

    def _run_configuration_pass(self) -> None:
        """Run a single configuration pass (local or CI/CD)."""
        # For CI/CD config, force environment backend
        if self.config_target == "cicd":
            self.backend = "environment"
            click.echo(click.style("   Using environment backend for CI/CD configuration", fg="yellow"))
            click.echo()

        # Check for existing configuration
        has_existing = self._load_existing_config()
        if has_existing and not self.non_interactive:
            self._show_existing_config()
            self._prompt_update_sections()

        # Step 1: Discover repository (always needed for repo_info)
        self._discover_repository()

        # Step 2: Collect credentials (only if updating)
        if self.update_git_provider or self.update_agent_provider or self.update_credentials:
            self._collect_credentials()
        else:
            # Load agent type from existing config for downstream steps
            self._load_agent_type_from_config()

        # Step 3: Store credentials locally (only if updating and local config)
        if self.update_credentials and self.config_target == "local":
            self._store_credentials()

        # Step 4: Set up Gitea Actions secrets (optional, only if updating credentials and local)
        if self.setup_secrets and self.update_credentials and self.config_target == "local":
            self._setup_gitea_secrets()

        # Step 5: Generate configuration file
        self._generate_config()

        # Step 6: Deploy reusable composite action (only for local)
        if self.deploy_actions and self.config_target == "local":
            self._deploy_composite_action()

        # Step 7: Deploy CI/CD workflows (optional, only for local)
        # In interactive mode, always offer the choice
        # In non-interactive mode, only deploy if explicitly requested
        if self.config_target == "local" and (self.deploy_workflows or (not self.non_interactive)):
            self._deploy_workflows()

        # Step 8: Validate setup
        self._validate_setup()

    def _detect_backend(self) -> str:
        """Detect best credential backend for current environment."""
        # Check if keyring is available
        keyring_backend = KeyringBackend()
        if keyring_backend.available:
            return "keyring"

        # Fall back to environment
        return "environment"

    def _normalize_url(self, url: str, service_name: str = "service") -> str:
        """Normalize a URL by ensuring it has a protocol prefix and verify connectivity.

        Args:
            url: The URL to normalize (may or may not have http/https prefix)
            service_name: Name of the service for user prompts (e.g., "Ollama", "vLLM")

        Returns:
            URL with proper http:// or https:// prefix
        """
        url = url.strip()

        # Already has protocol - just verify
        if url.startswith("http://") or url.startswith("https://"):
            normalized = url.rstrip("/")
            return self._verify_url_connectivity(normalized, service_name)

        # No protocol - ask user which one to use
        click.echo()
        click.echo(f"The URL '{url}' doesn't specify a protocol.")
        use_https = click.confirm(
            f"Use HTTPS for {service_name}? (No = HTTP)",
            default=False,  # Default to HTTP for local services
        )

        protocol = "https" if use_https else "http"
        normalized = f"{protocol}://{url}".rstrip("/")
        click.echo(f"  Using: {normalized}")

        return self._verify_url_connectivity(normalized, service_name)

    def _verify_url_connectivity(self, url: str, service_name: str) -> str:
        """Verify URL is reachable, allow user to retry or save anyway.

        Args:
            url: Full URL with protocol
            service_name: Name of the service for display

        Returns:
            The URL (possibly modified by user)
        """
        import socket
        import urllib.parse

        if self.non_interactive:
            return url

        # Parse the URL to get host and port
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        click.echo(f"  Checking connectivity to {host}:{port}...", nl=False)

        try:
            # Quick socket check (2 second timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                click.echo(click.style(" ✓ reachable", fg="green"))
                return url
            else:
                click.echo(click.style(" ✗ unreachable", fg="red"))
        except socket.gaierror:
            click.echo(click.style(" ✗ hostname not found", fg="red"))
        except TimeoutError:
            click.echo(click.style(" ✗ timeout", fg="yellow"))
        except Exception as e:
            click.echo(click.style(f" ✗ error: {e}", fg="red"))

        # URL not reachable - ask user what to do
        click.echo()
        choice = click.prompt(
            f"  {service_name} at {url} is not reachable. What would you like to do?",
            type=click.Choice(["save", "retry", "edit"]),
            default="save",
        )

        if choice == "save":
            click.echo("  Saving URL anyway (you can update it later)")
            return url
        elif choice == "retry":
            return self._verify_url_connectivity(url, service_name)
        else:  # edit
            new_url = click.prompt("  Enter new URL", default=url)
            return self._normalize_url(new_url, service_name)

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

        self.gitea_token = os.getenv("SAPIENS_GITEA_TOKEN") or os.getenv("GITEA_TOKEN")
        if not self.gitea_token:
            raise click.ClickException("SAPIENS_GITEA_TOKEN environment variable required in non-interactive mode")

        self.claude_api_key = os.getenv("CLAUDE_API_KEY")
        # Claude API key is optional (can use local mode)

        click.echo("   ✓ Using credentials from environment variables")

    def _collect_interactively(self) -> None:
        """Collect credentials interactively from user."""
        # Only collect git provider token if updating git provider or credentials
        if self.update_git_provider or self.update_credentials:
            if self.provider_type == "gitlab":
                self._collect_gitlab_token_interactively()
            else:
                self._collect_gitea_token_interactively()
            click.echo()

        # AI Agent configuration (only if updating agent provider)
        if self.update_agent_provider:
            self._configure_ai_agent()
        else:
            # Load agent settings from existing config
            self._load_agent_type_from_config()

        # Automation mode configuration (only if updating automation settings)
        if self.update_automation:
            self._configure_automation_mode()
        else:
            # Load automation settings from existing config
            self._load_automation_from_config()

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
                self.gitea_token = click.prompt("Enter your Gitea API token", hide_input=True, type=str)
        else:
            # No existing token - prompt for it
            click.echo(
                "Gitea API Token is required. Get it from:\n" f"   {self.repo_info.base_url}/user/settings/applications"
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
                self.gitea_token = click.prompt("Enter your GitLab Personal Access Token", hide_input=True, type=str)
        else:
            # No existing token - prompt for it
            pat_url = f"{self.repo_info.base_url}/-/user_settings/personal_access_tokens"
            click.echo("GitLab Personal Access Token is required. Get it from:\n" f"   {pat_url}")
            click.echo()
            click.echo("Required scopes: api, read_repository, write_repository")
            click.echo()
            self.gitea_token = click.prompt("Enter your GitLab Personal Access Token", hide_input=True, type=str)

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

            self.agent_api_key = click.prompt("Enter your Claude API key", hide_input=True, type=str)

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

        self.goose_model = click.prompt("Which model?", type=click.Choice(available_models), default=default_model)

        # API key if needed
        if provider_info.get("api_key_env"):
            click.echo()
            api_key_name = provider_info["api_key_env"]

            # Check if already set in environment
            import os

            existing_key = os.getenv(api_key_name)

            if existing_key:
                use_existing = click.confirm(f"{api_key_name} found in environment. Use it?", default=True)
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

        # URL configuration FIRST
        if click.confirm("Use default Ollama URL (localhost:11434)?", default=True):
            self.builtin_base_url = default_url
        else:
            custom_url = click.prompt("Ollama URL (host:port)", default="localhost:11434")
            self.builtin_base_url = self._normalize_url(custom_url, "Ollama")

        # NOW check Ollama availability using the configured URL
        available_models = []
        try:
            response = httpx.get(f"{self.builtin_base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models_data = response.json()
                available_models = [m["name"] for m in models_data.get("models", [])]
                click.echo(click.style(f"✓ Ollama is running at {self.builtin_base_url}", fg="green"))
                if available_models:
                    click.echo(f"  Available models: {', '.join(available_models[:5])}")
                    if len(available_models) > 5:
                        click.echo(f"  ... and {len(available_models) - 5} more")
            else:
                click.echo(
                    click.style(f"⚠ Ollama responded but no models found at {self.builtin_base_url}", fg="yellow")
                )
        except Exception:
            click.echo(click.style(f"⚠ Ollama not detected at {self.builtin_base_url}", fg="yellow"))
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
                " (recommended)" if model == "qwen3:8b" else " (requires 24GB VRAM)" if model == "qwen3:14b" else ""
            )
            available = " ✓" if model in available_models else ""
            click.echo(f"  • {model}{marker}{available}")
        click.echo()

        self.builtin_model = click.prompt("Which model?", type=str, default=default_model)

    def _configure_builtin_vllm(self, provider_info: dict) -> None:
        """Configure vLLM for builtin agent."""
        import httpx

        click.echo()
        default_url = "http://localhost:8000"

        # URL configuration FIRST
        if click.confirm("Use default vLLM URL (localhost:8000)?", default=True):
            self.builtin_base_url = default_url
        else:
            custom_url = click.prompt("vLLM URL (host:port)", default="localhost:8000")
            self.builtin_base_url = self._normalize_url(custom_url, "vLLM")

        # NOW check vLLM availability using the configured URL
        available_models = []
        try:
            response = httpx.get(f"{self.builtin_base_url}/v1/models", timeout=5.0)
            if response.status_code == 200:
                models_data = response.json()
                available_models = [m["id"] for m in models_data.get("data", [])]
                click.echo(click.style(f"✓ vLLM is running at {self.builtin_base_url}", fg="green"))
                if available_models:
                    click.echo(f"  Available models: {', '.join(available_models)}")
            else:
                click.echo(click.style(f"⚠ vLLM responded but no models found at {self.builtin_base_url}", fg="yellow"))
        except Exception:
            click.echo(click.style(f"⚠ vLLM not detected at {self.builtin_base_url}", fg="yellow"))
            click.echo("  Start vLLM: vllm serve qwen3:8b --port 8000")

        click.echo()

        # Model selection
        recommended_models = provider_info.get("models", ["qwen3:8b", "qwen3:14b", "llama3.1:8b"])
        default_model = available_models[0] if available_models else provider_info.get("default_model", "qwen3:8b")

        click.echo("Recommended models for tool-calling:")
        for model in recommended_models[:4]:
            marker = " (recommended)" if model == "qwen3:8b" else " (requires 24GB VRAM)" if "14b" in model else ""
            available = " ✓" if model in available_models else ""
            click.echo(f"  • {model}{marker}{available}")
        click.echo()

        self.builtin_model = click.prompt("Which model?", type=str, default=default_model)

    def _configure_builtin_cloud(self, provider_info: dict) -> None:
        """Configure cloud LLM provider for builtin agent."""
        import os

        click.echo()

        # Model selection
        available_models = provider_info.get("models", [])
        default_model = provider_info.get("default_model", available_models[0] if available_models else "gpt-4o")

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
                use_existing = click.confirm(f"{api_key_env} found in environment. Use it?", default=True)
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

    def _configure_automation_mode(self) -> None:
        """Configure automation mode (native/daemon/hybrid) interactively."""
        click.echo()
        click.echo(click.style("🔧 Automation Mode Configuration", bold=True, fg="cyan"))
        click.echo()

        # Show mode options with explanations
        click.echo("Available modes:")
        click.echo()
        click.echo(click.style("  native", bold=True) + " (recommended)")
        click.echo("    • Instant response via CI/CD workflows")
        click.echo("    • Triggers on label events")
        click.echo("    • No daemon process needed")
        click.echo("    • Uses Gitea/GitHub Actions runners")
        click.echo()
        click.echo(click.style("  daemon", bold=True))
        click.echo("    • Polling-based (checks every N minutes)")
        click.echo("    • Requires continuous process")
        click.echo("    • Works without CI/CD")
        click.echo()
        click.echo(click.style("  hybrid", bold=True))
        click.echo("    • Native triggers + daemon fallback")
        click.echo("    • Best of both worlds")
        click.echo()

        self.automation_mode = click.prompt(
            "Which mode?",
            type=click.Choice(["native", "daemon", "hybrid"]),
            default="native",
        )

        # Configure label prefix for native/hybrid modes
        if self.automation_mode in ("native", "hybrid"):
            click.echo()
            click.echo(click.style("Label Prefix Configuration:", bold=True))
            click.echo()
            click.echo("The label prefix determines which labels trigger automation:")
            click.echo(
                "  • With prefix 'sapiens/', labels like 'sapiens/triage' or 'sapiens/review' will trigger workflows"
            )
            click.echo("  • Other labels like 'bug' or 'enhancement' will be ignored by automation")
            click.echo("  • This helps you control which labels activate AI agents")
            click.echo()
            self.label_prefix = click.prompt(
                "Label prefix for automation triggers",
                type=str,
                default="sapiens/",
            )

        click.echo()
        click.echo(f"   ✓ Configured {self.automation_mode} mode")
        if self.automation_mode in ("native", "hybrid"):
            click.echo(f"   ✓ Label prefix: {self.label_prefix}")

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
            backend.set("SAPIENS_GITEA_TOKEN", self.gitea_token)
            click.echo("   ✓ Set: SAPIENS_GITEA_TOKEN")

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
        click.echo(click.style("Note: Environment variables only persist in current session.", fg="yellow"))
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
            click.echo(click.style(f"   ⚠ Warning: Failed to set {provider_name} secrets: {e}", fg="yellow"))
            click.echo(click.style(f"   You can set them manually in {provider_name} UI later.", fg="yellow"))
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
        token_secret_name = "GITHUB_TOKEN" if self.provider_type == "github" else "SAPIENS_GITEA_TOKEN"
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
        # Set SAPIENS_GITEA_TOKEN secret (note: GITEA_ prefix is reserved by Gitea)
        click.echo("   ⏳ Setting SAPIENS_GITEA_TOKEN secret...")
        # Note: We'll need to use the MCP server directly since GiteaRestProvider
        # doesn't expose secret management yet
        self._set_gitea_secret_via_mcp("SAPIENS_GITEA_TOKEN", self.gitea_token)
        click.echo("   ✓ Set repository secret: SAPIENS_GITEA_TOKEN")

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
        secrets_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/" f"{self.repo_info.repo}/settings/secrets"
        click.echo(f"   Navigate to: {secrets_url}")

    def _generate_config(self) -> None:
        """Generate configuration file."""
        click.echo(
            click.style(
                "📝 Updating configuration file..." if self.existing_config else "📝 Creating configuration file...",
                bold=True,
            )
        )

        # Determine credential references based on backend and provider
        if self.backend == "keyring":
            if self.provider_type == "gitlab":
                git_token_ref = "@keyring:gitlab/api_token"  # nosec B105
            else:
                git_token_ref = "@keyring:gitea/api_token"  # nosec B105

            # Determine agent API key reference
            if self.agent_type == "goose" and self.goose_llm_provider:
                agent_api_key_ref = f"@keyring:{self.goose_llm_provider}/api_key" if self.agent_api_key else "null"
            elif self.agent_type == "builtin" and self.builtin_provider:
                agent_api_key_ref = f"@keyring:{self.builtin_provider}/api_key" if self.agent_api_key else "null"
            elif self.agent_type == "claude":
                agent_api_key_ref = "@keyring:claude/api_key" if self.agent_api_key else "null"
            else:
                agent_api_key_ref = "null"
        else:
            # fmt: off
            if self.provider_type == "gitlab":
                git_token_ref = "${GITLAB_TOKEN}"  # nosec B105
            else:
                git_token_ref = "${SAPIENS_GITEA_TOKEN}"  # nosec B105
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

        # Build git_provider section (use existing if not updating)
        if not self.update_git_provider and self.existing_config:
            existing_git = self.existing_config.get("git_provider", {})
            git_provider_section = "git_provider:\n"
            for key, value in existing_git.items():
                if isinstance(value, str) and (value.startswith("@") or value.startswith("$")):
                    git_provider_section += f'  {key}: "{value}"\n'
                else:
                    git_provider_section += f"  {key}: {value}\n"
            git_provider_section = git_provider_section.rstrip("\n")
        else:
            git_provider_section = f"""git_provider:
  provider_type: {self.provider_type}
{mcp_server_line}
  base_url: {self.repo_info.base_url}
  api_token: "{git_token_ref}\""""

        # Build agent_provider section (use existing if not updating)
        if not self.update_agent_provider and self.existing_config:
            existing_agent = self.existing_config.get("agent_provider", {})
            agent_config = "agent_provider:\n"
            for key, value in existing_agent.items():
                if isinstance(value, dict):
                    agent_config += f"  {key}:\n"
                    for subkey, subval in value.items():
                        agent_config += f"    {subkey}: {subval}\n"
                elif isinstance(value, str) and (value.startswith("@") or value.startswith("$")):
                    agent_config += f'  {key}: "{value}"\n'
                elif value is None:
                    agent_config += f"  {key}: null\n"
                else:
                    agent_config += f"  {key}: {value}\n"
            agent_config = agent_config.rstrip("\n")

        # Build automation section (use existing if not updating)
        if not self.update_automation and self.existing_config:
            existing_automation = self.existing_config.get("automation", {})
            if existing_automation:
                # Preserve existing automation config
                import yaml

                automation_section = "automation:\n"
                automation_yaml = yaml.safe_dump(existing_automation, default_flow_style=False, sort_keys=False)
                for line in automation_yaml.split("\n"):
                    if line:
                        automation_section += f"  {line}\n"
                automation_section = automation_section.rstrip("\n")
            else:
                # No existing automation, generate default native mode
                automation_section = self._generate_automation_section()
        else:
            # Generate new automation section based on selected mode
            automation_section = self._generate_automation_section()

        # Generate configuration content
        config_content = f"""# Automation System Configuration
# Generated by: sapiens init
# Repository: {self.repo_info.owner}/{self.repo_info.repo}

{git_provider_section}

repository:
  owner: {self.repo_info.owner}
  name: {self.repo_info.repo}
  default_branch: main

{agent_config}

{automation_section}

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

        # Determine which config file to write
        if self.config_target == "cicd" and self.cicd_config_path:
            config_file = self.repo_path / self.cicd_config_path
        else:
            config_file = self.repo_path / self.config_path

        # Ensure directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Write configuration file
        config_file.write_text(config_content)
        click.echo(f"   ✓ Created: {config_file.relative_to(self.repo_path)}")
        click.echo()

    def _generate_automation_section(self) -> str:
        """Generate automation section based on selected mode."""
        # Determine enabled flags based on mode
        if self.automation_mode == "native":
            native_enabled = "true"
            daemon_enabled = "false"
        elif self.automation_mode == "daemon":
            native_enabled = "false"
            daemon_enabled = "true"
        else:  # hybrid
            native_enabled = "true"
            daemon_enabled = "true"

        # Build the automation section
        automation_section = f"""automation:
  mode:
    mode: {self.automation_mode}
    native_enabled: {native_enabled}
    daemon_enabled: {daemon_enabled}
    label_prefix: "{self.label_prefix}\""""

        # Add label triggers for native/hybrid modes
        if self.automation_mode in ("native", "hybrid"):
            automation_section += """

  label_triggers:
    "sapiens/triage":
      label_pattern: "sapiens/triage"
      handler: triage
      ai_enabled: true
      remove_on_complete: true
      success_label: triaged

    "needs-planning":
      label_pattern: "needs-planning"
      handler: proposal
      ai_enabled: true
      remove_on_complete: false
      success_label: plan-ready

    "execute":
      label_pattern: "execute"
      handler: task_execution
      ai_enabled: true
      remove_on_complete: true
      success_label: implemented"""

        return automation_section

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
            template_files = importlib.resources.files("repo_sapiens") / "templates" / template_subpath
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
            template_base = "workflows/github/sapiens"
        elif self.provider_type == "gitlab":
            # GitLab uses single .gitlab-ci.yml at root
            workflows_dir = self.repo_path
            template_base = "workflows/gitlab/sapiens"
        else:
            workflows_dir = self.repo_path / ".gitea" / "workflows"
            template_base = "workflows/gitea/sapiens"

        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Core workflows based on automation mode
        core_workflows = []

        if self.automation_mode in ("native", "hybrid"):
            # Native/hybrid modes use label triggers
            core_workflows.append(("process-label.yaml", "Process label (native triggers)"))

        if self.automation_mode in ("daemon", "hybrid"):
            # Daemon/hybrid modes use the daemon
            core_workflows.append(("automation-daemon.yaml", "Automation daemon (scheduled processing)"))

        # Process issue is useful for manual triggers in all modes
        core_workflows.append(("process-issue.yaml", "Process issue (manual trigger)"))

        # Label-specific workflows
        label_workflows = [
            ("needs-planning.yaml", "Planning workflow"),
            ("approved.yaml", "Approved plan workflow"),
            ("execute-task.yaml", "Task execution workflow"),
            ("needs-review.yaml", "Code review workflow"),
            ("requires-qa.yaml", "QA testing workflow"),
            ("needs-fix.yaml", "Fix proposal workflow"),
        ]

        # Recipe workflows
        recipe_workflows = [
            ("recipes/daily-issue-triage.yaml", "Daily issue triage"),
            ("recipes/weekly-test-coverage.yaml", "Weekly test coverage report"),
            ("recipes/weekly-dependency-audit.yaml", "Weekly dependency audit"),
            ("recipes/weekly-security-review.yaml", "Weekly security review"),
            ("recipes/weekly-sbom-license.yaml", "Weekly SBOM & license compliance"),
            ("recipes/post-merge-docs.yaml", "Post-merge documentation update"),
        ]

        def deploy_template(template_name: str, target_dir: Path) -> bool:
            """Deploy a single template file."""
            template_subpath = f"{template_base}/{template_name}"
            content = None

            try:
                # First try: repo root templates/ directory (development mode)
                repo_root = Path(__file__).parent.parent.parent
                template_path = repo_root / "templates" / template_subpath
                if template_path.exists():
                    content = template_path.read_text()

                # Second try: package templates directory
                if content is None:
                    package_dir = Path(__file__).parent.parent
                    template_path = package_dir / "templates" / template_subpath
                    if template_path.exists():
                        content = template_path.read_text()

                # Third try: importlib.resources (installed package)
                if content is None:
                    template_files = importlib.resources.files("repo_sapiens") / "templates" / template_subpath
                    if template_files.is_file():
                        content = template_files.read_text()

                if content is None:
                    return False

                # Determine target file path
                is_recipe = template_name.startswith("recipes/")

                if self.provider_type == "gitlab":
                    if not is_recipe:
                        # Core workflows go to .gitlab-ci.yml
                        target_file = target_dir / ".gitlab-ci.yml"
                    else:
                        # Recipes go to .gitlab/sapiens/recipes/
                        gitlab_dir = self.repo_path / ".gitlab" / "sapiens" / "recipes"
                        gitlab_dir.mkdir(parents=True, exist_ok=True)
                        target_file = gitlab_dir / template_name.replace("recipes/", "")
                else:
                    # GitHub/Gitea: use subdirectory structure - recipes nested inside sapiens
                    sapiens_dir = target_dir / "sapiens"
                    if is_recipe:
                        target_file = sapiens_dir / "recipes" / template_name.replace("recipes/", "")
                    else:
                        target_file = sapiens_dir / template_name
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                target_file.write_text(content)
                return True
            except Exception:
                return False

        # Ask about core workflows
        if not self.non_interactive:
            # Build workflow list description
            workflow_names = ", ".join([desc for _, desc in core_workflows])
            deploy_core = click.confirm(
                f"Deploy core workflows ({workflow_names})?",
                default=True,
            )
        else:
            deploy_core = True

        if deploy_core:
            for template_name, description in core_workflows:
                if deploy_template(template_name, workflows_dir):
                    if self.provider_type == "gitlab":
                        click.echo(f"   ✓ {description} → .gitlab-ci.yml")
                    else:
                        click.echo(f"   ✓ {description} → sapiens/")
                else:
                    click.echo(click.style(f"   ⚠ Could not deploy: {description}", fg="yellow"))

        click.echo()

        # Ask about label-specific workflows
        if not self.non_interactive:
            deploy_labels = click.confirm(
                "Deploy label-specific workflows "
                "(needs-planning, approved, execute-task, needs-review, requires-qa, needs-fix)?",
                default=True,
            )
        else:
            deploy_labels = True

        if deploy_labels:
            for template_name, description in label_workflows:
                if deploy_template(template_name, workflows_dir):
                    if self.provider_type == "gitlab":
                        click.echo(f"   ✓ {description} → .gitlab-ci.yml")
                    else:
                        click.echo(f"   ✓ {description} → sapiens/")
                else:
                    click.echo(click.style(f"   ⚠ Could not deploy: {description}", fg="yellow"))

        click.echo()

        # Deploy README to sapiens directory
        if deploy_core and self.provider_type != "gitlab":
            readme_content = None
            try:
                # Try to read README from templates
                repo_root = Path(__file__).parent.parent.parent
                readme_path = repo_root / "templates" / "workflows" / "sapiens-README.md"
                if readme_path.exists():
                    readme_content = readme_path.read_text()

                # Try package templates
                if readme_content is None:
                    package_dir = Path(__file__).parent.parent
                    readme_path = package_dir / "templates" / "workflows" / "sapiens-README.md"
                    if readme_path.exists():
                        readme_content = readme_path.read_text()

                # Try importlib.resources
                if readme_content is None:
                    readme_files = (
                        importlib.resources.files("repo_sapiens") / "templates" / "workflows" / "sapiens-README.md"
                    )
                    if readme_files.is_file():
                        readme_content = readme_files.read_text()

                if readme_content:
                    sapiens_dir = workflows_dir / "sapiens"
                    readme_file = sapiens_dir / "README.md"
                    readme_file.write_text(readme_content)
                    click.echo("   ✓ Documentation → sapiens/README.md")
            except Exception:
                pass  # Non-critical, skip if fails

        # Deploy prompts directory
        if (deploy_core or deploy_labels) and self.provider_type != "gitlab":
            try:
                import shutil

                # Determine source prompts directory
                repo_root = Path(__file__).parent.parent.parent
                source_prompts = repo_root / "templates" / template_base / "prompts"

                if not source_prompts.exists():
                    # Try package templates
                    package_dir = Path(__file__).parent.parent
                    source_prompts = package_dir / "templates" / template_base / "prompts"

                if source_prompts.exists():
                    # Determine target directory
                    sapiens_dir = workflows_dir / "sapiens"
                    target_prompts = sapiens_dir / "prompts"

                    # Copy prompts directory
                    if target_prompts.exists():
                        shutil.rmtree(target_prompts)
                    shutil.copytree(source_prompts, target_prompts)

                    click.echo("   ✓ Workflow prompts → sapiens/prompts/")
            except Exception:
                pass  # Non-critical, skip if fails

        click.echo()

        # Ask about recipe workflows (one by one in interactive mode)
        if not self.non_interactive:  # nosec B105
            click.echo("Recipe workflows available:")
            for template_name, description in recipe_workflows:  # nosec B105
                if click.confirm(f"  Deploy '{description}'?", default=False):
                    if deploy_template(template_name, workflows_dir):
                        if self.provider_type == "gitlab":
                            click.echo(click.style("     ✓ Deployed → .gitlab/sapiens/recipes/", fg="green"))  # nosec B105
                        else:
                            click.echo(click.style("     ✓ Deployed → sapiens/recipes/", fg="green"))  # nosec B105
                    else:
                        click.echo(click.style("     ⚠ Could not deploy", fg="yellow"))  # nosec B105

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
                    token_ref = "${SAPIENS_GITEA_TOKEN}"

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
            issues_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/-/issues"
        else:
            issues_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/issues"
        click.echo(f"   {issues_url}")
        click.echo()

        # Mode-specific instructions
        if self.automation_mode == "native":
            click.echo("2. Workflows will trigger automatically when you add labels!")
            click.echo()
            click.echo("   • Label triggers are active immediately")
            click.echo("   • No daemon process needed")
            click.echo(f"   • Check workflows: {issues_url.rsplit('/', 1)[0]}/actions")
        elif self.automation_mode == "daemon":
            click.echo("2. Run the automation daemon:")
            click.echo(f"   sapiens --config {self.config_path} daemon --interval 60")
            click.echo()
            click.echo("3. Watch the automation work!")
        else:  # hybrid
            click.echo("2. Automation runs in hybrid mode:")
            click.echo("   • Label triggers work instantly via workflows")
            click.echo(f"   • Check workflows: {issues_url.rsplit('/', 1)[0]}/actions")
            click.echo()
            click.echo("   • Optional: Run daemon for additional automation:")
            click.echo(f"     sapiens --config {self.config_path} daemon --interval 60")

        click.echo()

        # Print manual secret setup if needed (not for GitLab - uses CI/CD variables)
        # Only needed for native/hybrid modes that use workflows
        if self.setup_secrets and self.provider_type != "gitlab" and self.automation_mode in ("native", "hybrid"):
            click.echo(
                click.style(
                    f"⚠ Important: Set {provider_name} Actions Secrets Manually",
                    bold=True,
                    fg="yellow",
                )
            )
            click.echo("   (Required for workflow automation)")

            click.echo()
            secrets_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/" f"{self.repo_info.repo}/settings/secrets"
            click.echo(f"Navigate to: {secrets_url}")
            click.echo()
            click.echo("Add the following secrets:")
            if self.provider_type == "gitea":
                click.echo("  - SAPIENS_GITEA_TOKEN (your Gitea API token)")
            if self.agent_mode == "api":
                if self.agent_type == "goose" and self.goose_llm_provider:
                    secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                    provider_title = self.goose_llm_provider.title()
                    click.echo(f"  - {secret_name} (your {provider_title} API key for Goose)")
                elif self.agent_type == "claude":
                    click.echo("  - CLAUDE_API_KEY (your Claude API key)")
            click.echo()

        # GitLab uses CI/CD variables instead of Actions secrets
        # Only needed for native/hybrid modes that use workflows
        if self.setup_secrets and self.provider_type == "gitlab" and self.automation_mode in ("native", "hybrid"):
            click.echo(click.style("⚠ Important: Set GitLab CI/CD Variables Manually", bold=True, fg="yellow"))
            click.echo("   (Required for workflow automation)")
            click.echo()
            variables_url = (
                f"{self.repo_info.base_url}/{self.repo_info.owner}/" f"{self.repo_info.repo}/-/settings/ci_cd"
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
        config_flag = "" if str(self.config_path) == ".sapiens/config.yaml" else f"--config {self.config_path} "

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
