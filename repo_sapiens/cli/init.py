"""CLI command for initializing repo-sapiens in a repository.

This module provides the ``sapiens init`` command which guides users through
the complete setup process for integrating repo-sapiens into a Git repository.

The initialization process handles:
    - Git repository discovery and provider detection (GitHub, GitLab, Gitea)
    - Credential collection and secure storage (keyring, environment, encrypted)
    - AI agent configuration (Claude, Goose, Copilot, builtin ReAct)
    - Automation mode selection (native CI/CD, daemon, or hybrid)
    - Configuration file generation
    - Optional workflow template deployment

User Interaction Flow:
    1. Configuration target selection (local, CI/CD, or both)
    2. Repository discovery (auto-detect remotes and provider type)
    3. Credential collection (interactive prompts or environment variables)
    4. AI agent configuration (provider selection, model choice, API keys)
    5. Automation mode configuration (native triggers, daemon polling, hybrid)
    6. Credential storage (write to keyring or environment)
    7. Actions secrets setup (optional, provider-specific)
    8. Configuration file generation
    9. Composite action deployment (optional)
    10. Workflow template deployment (optional)
    11. Setup validation
    12. Next steps guidance

Example:
    Interactive setup::

        $ sapiens init

    Non-interactive CI/CD setup::

        $ export SAPIENS_GITEA_TOKEN="your-token"
        $ sapiens init --non-interactive --backend environment
"""

import sys
from pathlib import Path
from typing import Literal

import click
import structlog

from repo_sapiens.credentials import CredentialResolver, EnvironmentBackend, KeyringBackend
from repo_sapiens.enums import AgentType
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
    "--setup-secrets/--no-setup-secrets",
    default=True,
    help="Set up repository Actions secrets (default: true)",
)
@click.option(
    "--deploy-actions/--no-deploy-actions",
    default=True,
    help="Deploy reusable composite action for AI tasks (default: true)",
)
@click.option(
    "--deploy-workflows",
    multiple=True,
    type=click.Choice(["essential", "core", "security", "support", "all"]),
    help="Deploy workflow tiers: essential, core, security, support, or all",
)
@click.option(
    "--remove-workflows",
    multiple=True,
    type=click.Choice(["essential", "core", "security", "support", "all"]),
    help="Remove workflow tiers from repository",
)
@click.option(
    "--run-mode",
    type=click.Choice(["local", "cicd", "both"]),
    default=None,
    help="Configuration target mode (default: prompts in interactive mode, 'local' in non-interactive)",
)
@click.option(
    "--git-token-env",
    type=str,
    default=None,
    help="Environment variable name containing git provider token (e.g., GITHUB_TOKEN)",
)
@click.option(
    "--ai-provider",
    type=click.Choice(["ollama", "openai-compatible", "claude-local", "goose-local", "copilot-local"]),
    default=None,
    help="AI provider type for the builtin ReAct agent",
)
@click.option(
    "--ai-model",
    type=str,
    default=None,
    help="AI model to use (e.g., llama3.1, gpt-4o, claude-sonnet-4)",
)
@click.option(
    "--ai-base-url",
    type=str,
    default=None,
    help="Base URL for AI provider (e.g., http://localhost:11434 for Ollama)",
)
@click.option(
    "--ai-api-key-env",
    type=str,
    default=None,
    help="Environment variable name containing AI API key (e.g., OPENROUTER_API_KEY)",
)
@click.option(
    "--daemon-interval",
    type=int,
    default=None,
    help="Polling interval in minutes for daemon/hybrid mode (default: 5)",
)
def init_command(
    repo_path: Path,
    config_path: Path,
    backend: str | None,
    non_interactive: bool,
    setup_secrets: bool,
    deploy_actions: bool,
    deploy_workflows: tuple[str, ...],
    remove_workflows: tuple[str, ...],
    run_mode: str | None,
    git_token_env: str | None,
    ai_provider: str | None,
    ai_model: str | None,
    ai_base_url: str | None,
    ai_api_key_env: str | None,
    daemon_interval: int | None,
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

        # Non-interactive with Ollama (local LLM)
        export GITHUB_TOKEN="ghp_xxx"
        sapiens init --non-interactive \\
            --git-token-env GITHUB_TOKEN \\
            --ai-provider ollama \\
            --ai-model llama3.1 \\
            --ai-base-url http://localhost:11434

        # Non-interactive with OpenRouter
        export GITHUB_TOKEN="ghp_xxx"
        export OPENROUTER_API_KEY="sk-or-xxx"
        sapiens init --non-interactive \\
            --git-token-env GITHUB_TOKEN \\
            --ai-provider openai-compatible \\
            --ai-model anthropic/claude-sonnet-4 \\
            --ai-base-url https://openrouter.ai/api/v1 \\
            --ai-api-key-env OPENROUTER_API_KEY

        # Skip Actions secret setup
        sapiens init --no-setup-secrets

        # Deploy workflow templates (tiers: essential, core, security, support, all)
        sapiens init --deploy-workflows essential
        sapiens init --deploy-workflows essential core security
        sapiens init --deploy-workflows all

        # Remove workflow templates
        sapiens init --remove-workflows essential
        sapiens init --remove-workflows all
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
            remove_workflows=remove_workflows,
            run_mode=run_mode,
            git_token_env=git_token_env,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_base_url=ai_base_url,
            ai_api_key_env=ai_api_key_env,
            daemon_interval=daemon_interval,
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
    """Orchestrates the complete repository initialization workflow.

    This class encapsulates all the logic for setting up repo-sapiens in a
    Git repository, handling everything from repository discovery to workflow
    deployment. It supports both interactive and non-interactive modes.

    The initialization is stateful - instance attributes are populated
    progressively as the user provides input or as values are auto-detected.

    Attributes:
        repo_path: Path to the Git repository root.
        config_path: Relative path for the configuration file.
        backend: Credential storage backend ('keyring', 'environment', 'encrypted').
        non_interactive: If True, skip prompts and use environment variables.
        setup_secrets: If True, configure repository Actions secrets.
        deploy_actions: If True, deploy the reusable composite action.
        deploy_workflows: If True, deploy CI/CD workflow templates.
        repo_info: Discovered repository information (owner, name, URL).
        provider_type: Detected Git provider ('github', 'gitlab', 'gitea').
        gitea_token: Git provider API token (used for all providers despite name).
        agent_type: Selected AI agent type (CLAUDE, GOOSE, COPILOT, BUILTIN).
        agent_mode: Agent execution mode ('local' or 'api').
        agent_api_key: API key for cloud-based agent providers.
        automation_mode: Workflow trigger mode ('native', 'daemon', 'hybrid').
        label_prefix: Prefix for automation trigger labels (e.g., 'sapiens/').

    Example:
        >>> initializer = RepoInitializer(
        ...     repo_path=Path("."),
        ...     config_path=Path(".sapiens/config.yaml"),
        ...     backend="keyring",
        ...     non_interactive=False,
        ...     setup_secrets=True,
        ... )
        >>> initializer.run()
    """

    def __init__(
        self,
        repo_path: Path,
        config_path: Path,
        backend: str | None,
        non_interactive: bool,
        setup_secrets: bool,
        deploy_actions: bool = True,
        deploy_workflows: tuple[str, ...] = (),
        remove_workflows: tuple[str, ...] = (),
        run_mode: str | None = None,
        git_token_env: str | None = None,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        ai_base_url: str | None = None,
        ai_api_key_env: str | None = None,
        daemon_interval: int | None = None,
    ) -> None:
        """Initialize the repository initializer with configuration options.

        Sets up the initial state for the initialization workflow. Most attributes
        start as None and are populated during the run() execution.

        Args:
            repo_path: Path to the Git repository root directory.
            config_path: Relative path where the config file will be created.
            backend: Credential backend to use. If None, auto-detects based on
                system capabilities (prefers keyring if available).
            non_interactive: If True, skip all interactive prompts and require
                credentials via environment variables.
            setup_secrets: If True, attempt to configure repository Actions
                secrets via the provider's API.
            deploy_actions: If True, deploy the reusable sapiens-task composite
                action to the repository.
            deploy_workflows: Tuple of workflow tiers to deploy ('essential', 'core',
                'security', 'support', 'all'). Essential is always implied.
            remove_workflows: Tuple of workflow tiers to remove ('essential', 'core',
                'security', 'support', 'all'). Removes files from repository.
            run_mode: Configuration target ('local', 'cicd', 'both'). Defaults to
                'local' in non-interactive mode.
            git_token_env: Name of environment variable containing git token.
            ai_provider: AI provider type ('ollama', 'openai-compatible', etc.).
            ai_model: AI model name to use.
            ai_base_url: Base URL for AI provider (for ollama/openai-compatible).
            ai_api_key_env: Name of environment variable containing AI API key.
            daemon_interval: Polling interval in minutes for daemon/hybrid mode.
                Defaults to 5 if not specified.
        """
        self.repo_path = repo_path
        self.config_path = config_path
        self.backend = backend or self._detect_backend()
        self.non_interactive = non_interactive
        self.setup_secrets = setup_secrets
        self.deploy_actions = deploy_actions
        self.deploy_workflows = deploy_workflows
        self.remove_workflows = remove_workflows

        # CLI-provided configuration for non-interactive mode
        self.cli_run_mode = run_mode
        self.cli_git_token_env = git_token_env
        self.cli_ai_provider = ai_provider
        self.cli_ai_model = ai_model
        self.cli_ai_base_url = ai_base_url
        self.cli_ai_api_key_env = ai_api_key_env
        self.cli_daemon_interval = daemon_interval

        self.repo_info = None
        self.provider_type = None  # 'github', 'gitea', or 'gitlab' (detected)
        self.gitea_token = None
        self.agent_type: AgentType | None = None
        self.agent_mode: Literal["local", "api"] = "local"
        self.agent_api_key = None

        # Goose-specific settings
        self.goose_llm_provider = None
        self.goose_model = None
        self.goose_toolkit = "default"
        self.goose_temperature = 0.7

        # Copilot API settings (for copilot-api proxy)
        self.copilot_github_token = None
        self.copilot_manage_proxy = True
        self.copilot_proxy_port = 4141
        self.copilot_proxy_url = None
        self.copilot_account_type = "individual"
        self.copilot_rate_limit = None
        self.copilot_model = "gpt-4"

        # Builtin ReAct agent settings
        self.builtin_provider = None  # 'ollama', 'vllm', 'openai', 'anthropic', etc.
        self.builtin_model = None
        self.builtin_base_url = None  # For ollama/vllm

        # Automation mode settings
        self.automation_mode = "native"  # 'native', 'daemon', or 'hybrid'
        self.daemon_interval = 5  # Polling interval in minutes for daemon/hybrid mode
        self.label_prefix = "sapiens/"
        self.is_cicd_setup = False  # True if setting up for CI/CD workflows

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
        """Load existing configuration file if present.

        Attempts to read and parse the YAML configuration file. For CI/CD mode,
        uses the CI/CD-specific config path if set. The loaded configuration is
        stored in self.existing_config for use by other methods.

        Updates:
            self.existing_config: Populated with parsed YAML dict if file exists.

        Returns:
            True if a valid configuration file was found and loaded,
            False if file doesn't exist or couldn't be parsed.
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
        """Display a summary of the current configuration to the user.

        Prints a formatted overview of the existing configuration including
        git provider details, repository information, and agent provider settings.
        This helps users understand what's already configured before deciding
        what to update.

        Side Effects:
            Prints configuration summary to stdout via click.echo().

        Note:
            Returns early without output if self.existing_config is not set.
        """
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
        """Prompt the user to select which configuration sections to update.

        When an existing configuration is found, this method asks the user which
        parts they want to modify. This enables partial updates without requiring
        a complete reconfiguration.

        In non-interactive mode, all sections are updated by default.

        Updates:
            self.update_git_provider: True if user wants to update git settings.
            self.update_agent_provider: True if user wants to update agent settings.
            self.update_credentials: True if user wants to update stored credentials.
            self.update_automation: True if user wants to update automation mode.
            self.existing_config: Set to None if user chooses to start fresh.

        Raises:
            SystemExit: If user selects nothing and declines to start fresh.

        Side Effects:
            Prints prompts and reads user input via click.confirm().
        """
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
        """Load agent configuration from existing config file.

        Parses the agent_provider section of the existing configuration and
        populates the corresponding instance attributes. This is used when the
        user opts not to update the agent provider settings, but downstream
        steps still need to know which agent is configured.

        Updates:
            self.agent_type: The AgentType enum value.
            self.agent_mode: 'local' or 'api' based on provider_type suffix.
            self.goose_llm_provider: LLM provider if using Goose.
            self.goose_model: Model name if using Goose.
            self.builtin_provider: Backend provider if using builtin agent.
            self.builtin_model: Model name if using builtin agent.
            self.builtin_base_url: Base URL for local LLM servers.

        Note:
            Returns early without changes if self.existing_config is not set.
        """
        if not self.existing_config:
            return

        agent = self.existing_config.get("agent_provider", {})
        provider_type = agent.get("provider_type", "")

        if provider_type.startswith("claude"):
            self.agent_type = AgentType.CLAUDE
            self.agent_mode = "api" if provider_type == "claude-api" else "local"
        elif provider_type == "goose-local":
            self.agent_type = AgentType.GOOSE
            self.agent_mode = "local"  # Goose is CLI-only
            goose_config = agent.get("goose_config", {})
            self.goose_llm_provider = goose_config.get("llm_provider")
            self.goose_model = agent.get("model")
        elif provider_type.startswith("copilot"):
            self.agent_type = AgentType.COPILOT
            self.agent_mode = "local"
        elif provider_type in ("ollama", "openai-compatible"):
            self.agent_type = AgentType.BUILTIN
            self.builtin_provider = "ollama" if provider_type == "ollama" else "vllm"
            self.builtin_model = agent.get("model")
            self.builtin_base_url = agent.get("base_url")
        else:
            self.agent_type = AgentType.BUILTIN
            self.builtin_provider = provider_type
            self.builtin_model = agent.get("model")

    def _load_automation_from_config(self) -> None:
        """Load automation mode settings from existing configuration.

        Reads the automation.mode section from the existing config and populates
        the corresponding instance attributes. Used when the user opts not to
        update automation settings.

        Updates:
            self.automation_mode: 'native', 'daemon', or 'hybrid'.
            self.label_prefix: Prefix string for automation trigger labels.

        Note:
            Returns early without changes if self.existing_config is not set.
        """
        if not self.existing_config:
            return

        automation = self.existing_config.get("automation", {})
        mode_config = automation.get("mode", {})

        self.automation_mode = mode_config.get("mode", "native")
        self.label_prefix = mode_config.get("label_prefix", "sapiens/")

    def _prompt_configuration_mode(self) -> None:
        """Prompt the user to select the configuration target environment.

        Displays options for where sapiens will run:
        1. Local only - for development/testing on the developer's machine
        2. CI/CD only - for Gitea/GitHub/GitLab Actions environments
        3. Both - creates separate configuration files for each environment

        In non-interactive mode, defaults to 'local' configuration.

        Updates:
            self.run_mode: 'local', 'cicd', or 'both'.
            self.config_target: Current pass target ('local' or 'cicd').

        Side Effects:
            Prints menu options and reads user selection via click.prompt().
        """
        # Use CLI-provided run mode if available
        if self.cli_run_mode:
            self.run_mode = self.cli_run_mode  # type: ignore[assignment]
            self.config_target = "local" if self.cli_run_mode != "cicd" else "cicd"
            return

        if self.non_interactive:
            # In non-interactive mode, default to local
            self.run_mode = "local"
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
        """Prompt the user for the CI/CD configuration file path.

        Asks where to save the CI/CD-specific configuration file. The default
        location is '.sapiens/config.yaml' which is the standard config path
        that the workflow dispatcher expects.

        In non-interactive mode, uses the default path without prompting.

        Updates:
            self.cicd_config_path: Path object for the CI/CD config file.

        Side Effects:
            Prints prompt and reads user input via click.prompt().
        """
        if self.non_interactive:
            # Use standard config path so dispatcher can find it
            self.cicd_config_path = Path(".sapiens/config.yaml")
            return

        default_path = ".sapiens/config.yaml"
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
        """Execute the complete initialization workflow.

        This is the main entry point that orchestrates the entire setup process.
        Handles both single-pass (local or CI/CD only) and dual-pass (both)
        configuration modes.

        User Interaction Flow:
            1. Prompt for configuration target (local/cicd/both)
            2. For 'both' mode, run two configuration passes sequentially
            3. For single mode, run one configuration pass
            4. Display completion message and next steps
            5. Optionally offer a test run of the configured agent

        Side Effects:
            - Creates configuration file(s) in the repository
            - Stores credentials in the selected backend
            - May deploy workflow files to .github/, .gitea/, or .gitlab/
            - Prints progress and instructions to stdout

        Raises:
            click.ClickException: On configuration or validation errors.
            SystemExit: If user cancels during interactive prompts.
        """
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
        """Execute a single configuration pass for the current target.

        Performs all configuration steps for either local or CI/CD setup.
        The behavior varies based on self.config_target:
        - 'local': Uses selected backend, stores credentials, deploys actions
        - 'cicd': Forces environment backend, skips local credential storage

        Configuration Steps:
            1. Load existing config (if any) and prompt for update selections
            2. Discover Git repository and detect provider type
            3. Collect credentials (from user prompts or environment)
            4. Store credentials locally (local mode only)
            5. Set up Actions secrets (if enabled, local mode only)
            6. Generate the configuration YAML file
            7. Deploy composite action (if enabled, local mode only)
            8. Deploy workflow templates (if requested, local mode only)
            9. Validate the completed setup

        Side Effects:
            - Modifies self.backend and self.is_cicd_setup for CI/CD mode
            - Creates files in the repository
            - Stores credentials
            - Prints progress to stdout
        """
        # For CI/CD config, force environment backend and set is_cicd_setup flag
        if self.config_target == "cicd":
            self.backend = "environment"
            self.is_cicd_setup = True
            click.echo(click.style("   Using environment backend for CI/CD configuration", fg="yellow"))
            click.echo()
        else:
            self.is_cicd_setup = False

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

        # Step 7a: Remove CI/CD workflows (if requested)
        if self.config_target == "local" and self.remove_workflows:
            self._remove_workflows(self.remove_workflows)

        # Step 7b: Deploy CI/CD workflows (optional, only for local)
        # In interactive mode, always offer the choice
        # In non-interactive mode, only deploy if tiers were explicitly specified
        if self.config_target == "local" and (self.deploy_workflows or (not self.non_interactive)):
            self._deploy_workflows(self.deploy_workflows)

        # Step 8: Validate setup
        self._validate_setup()

    def _detect_backend(self) -> str:
        """Auto-detect the best credential backend for the current environment.

        Checks system capabilities to determine the most suitable credential
        storage backend. Prefers keyring (OS-level secure storage) when available,
        falls back to environment variables otherwise.

        Returns:
            Backend identifier string: 'keyring' or 'environment'.

        Note:
            The encrypted file backend requires explicit selection and is not
            auto-detected since it needs a master password.
        """
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

        Searches common locations for a previously stored Gitea API token.
        Used to offer reuse of existing credentials during interactive setup.

        Search Order:
            1. Keyring (gitea/api_token)
            2. Environment (GITEA_TOKEN, SAPIENS_GITEA_TOKEN)

        Returns:
            Tuple of (token, source) where:
            - token: The token string or None if not found.
            - source: Description of where token was found (e.g.,
                "keyring (gitea/api_token)") or None if not found.
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

        Searches common locations for a previously stored GitLab API token.
        Used to offer reuse of existing credentials during interactive setup.

        Search Order:
            1. Keyring (gitlab/api_token)
            2. Environment (GITLAB_TOKEN, SAPIENS_GITLAB_TOKEN, CI_JOB_TOKEN)

        Returns:
            Tuple of (token, source) where:
            - token: The token string or None if not found.
            - source: Description of where token was found (e.g.,
                "keyring (gitlab/api_token)") or None if not found.
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
        """Discover and configure Git repository settings.

        Scans the repository for Git remotes, detects the provider type
        (GitHub, GitLab, Gitea) from URLs, and prompts the user to select
        which remote to use if multiple providers are found.

        Updates:
            self.repo_info: Populated with GitRepoInfo (owner, repo, URL).
            self.provider_type: Set to 'github', 'gitlab', or 'gitea'.

        Raises:
            click.ClickException: If no Git repository found, no remotes
                configured, or repository parsing fails.

        Side Effects:
            Prints discovery progress and results to stdout.
            May prompt user to select a remote in interactive mode.
        """
        click.echo(click.style("🔍 Discovering repository configuration...", bold=True))

        try:
            discovery = GitDiscovery(self.repo_path)
            remotes = discovery.list_remotes()

            if not remotes:
                raise click.ClickException("No Git remotes configured")

            # Group remotes by provider type
            remotes_by_provider: dict[str, list[tuple[str, str]]] = {}
            for remote in remotes:
                provider = self._detect_provider_from_url(remote.url)
                if provider not in remotes_by_provider:
                    remotes_by_provider[provider] = []
                remotes_by_provider[provider].append((remote.name, remote.url))

            # If multiple providers detected and interactive, ask user to choose
            selected_remote_name = None
            if len(remotes_by_provider) > 1 and not self.non_interactive:
                click.echo()
                click.echo(click.style("   Multiple Git providers detected:", fg="yellow"))
                click.echo()

                # Build choices with remote details
                choices = []
                choice_map = {}
                idx = 1
                for provider, provider_remotes in remotes_by_provider.items():
                    for remote_name, remote_url in provider_remotes:
                        label = f"{idx}. {provider.upper()} - {remote_name} ({remote_url})"
                        click.echo(f"   {label}")
                        choices.append(str(idx))
                        choice_map[str(idx)] = (provider, remote_name)
                        idx += 1

                click.echo()
                choice = click.prompt(
                    "   Select which remote to use",
                    type=click.Choice(choices),
                    default="1",
                    show_choices=False,
                )
                self.provider_type, selected_remote_name = choice_map[choice]
                click.echo()
            elif len(remotes) == 1:
                # Single remote - use it
                selected_remote_name = remotes[0].name
                self.provider_type = list(remotes_by_provider.keys())[0]
            else:
                # Multiple remotes but same provider, or non-interactive
                # Use preferred remote (origin > upstream > first)
                self.provider_type = list(remotes_by_provider.keys())[0]
                for preferred in ["origin", "upstream"]:
                    for remote in remotes:
                        if remote.name == preferred:
                            selected_remote_name = remote.name
                            break
                    if selected_remote_name:
                        break
                if not selected_remote_name:
                    selected_remote_name = remotes[0].name

            # Parse the selected remote
            self.repo_info = discovery.parse_repository(remote_name=selected_remote_name)

            click.echo(f"   ✓ Found Git repository: {self.repo_path}")
            click.echo(f"   ✓ Selected remote: {self.repo_info.remote_name}")
            click.echo(f"   ✓ Provider: {self.provider_type.upper()}")
            click.echo(f"   ✓ Parsed: owner={self.repo_info.owner}, repo={self.repo_info.repo}")
            click.echo(f"   ✓ Base URL: {self.repo_info.base_url}")

            # Set smart defaults for GitLab (no native label triggers)
            if self.provider_type == "gitlab" and self.non_interactive:
                # Use CLI-provided daemon interval or default to 5 minutes
                if self.cli_daemon_interval is not None:
                    self.daemon_interval = self.cli_daemon_interval
                # Default to daemon mode for GitLab in non-interactive
                self.automation_mode = "daemon"
                click.echo(f"   ✓ Automation: daemon mode (GitLab default, {self.daemon_interval}m interval)")

            click.echo()

        except GitDiscoveryError as e:
            raise click.ClickException(f"Failed to discover repository: {e}") from e

    def _detect_provider_from_url(self, url: str) -> str:
        """Detect provider type from a Git URL.

        Args:
            url: Git remote URL

        Returns:
            Provider type: "github", "gitlab", or "gitea"
        """
        url_lower = url.lower()

        if "github.com" in url_lower:
            return "github"
        if "github" in url_lower and ("enterprise" in url_lower or "ghe" in url_lower):
            return "github"
        if "gitlab.com" in url_lower:
            return "gitlab"
        if "gitlab" in url_lower:
            return "gitlab"

        return "gitea"

    def _collect_credentials(self) -> None:
        """Collect all required credentials for the configuration.

        Dispatches to the appropriate collection method based on whether
        we're in interactive or non-interactive mode. Handles collection
        of git provider tokens, AI agent API keys, and automation settings.

        Side Effects:
            - Calls _collect_from_environment() or _collect_interactively()
            - Populates credential-related instance attributes
            - Prints progress and prompts to stdout
        """
        click.echo(click.style("🔑 Setting up credentials...", bold=True))
        click.echo()

        if self.non_interactive:
            self._collect_from_environment()
        else:
            self._collect_interactively()

    def _collect_from_environment(self) -> None:
        """Collect credentials from environment variables for non-interactive mode.

        Reads required credentials from standard environment variables or from
        CLI-specified environment variable names. This is the primary method for
        CI/CD pipeline setup where interactive prompts are not available.

        Environment Variables Checked (in order):
            - CLI-specified via --git-token-env (if provided)
            - SAPIENS_GITEA_TOKEN, GITEA_TOKEN, GITHUB_TOKEN, GITLAB_TOKEN

        AI Configuration (from CLI args):
            - --ai-provider: Provider type (ollama, openai-compatible, etc.)
            - --ai-model: Model name
            - --ai-base-url: Base URL for provider
            - --ai-api-key-env: Name of env var containing API key

        Updates:
            self.gitea_token: Set from environment variable.
            self.agent_type: Set from CLI if --ai-provider specified.
            self.builtin_provider: Set from CLI if using builtin agent.
            self.builtin_model: Set from CLI if --ai-model specified.
            self.builtin_base_url: Set from CLI if --ai-base-url specified.
            self.agent_api_key: Set from env var specified by --ai-api-key-env.

        Raises:
            click.ClickException: If git token not found in environment.

        Side Effects:
            Prints confirmation message to stdout.
        """
        import os

        # Collect git provider token
        if self.cli_git_token_env:
            self.gitea_token = os.getenv(self.cli_git_token_env)
            if not self.gitea_token:
                raise click.ClickException(f"{self.cli_git_token_env} environment variable not set")
            click.echo(f"   ✓ Git token from ${self.cli_git_token_env}")
        else:
            # Try standard environment variables
            for env_var in ["SAPIENS_GITEA_TOKEN", "GITEA_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN"]:
                self.gitea_token = os.getenv(env_var)
                if self.gitea_token:
                    click.echo(f"   ✓ Git token from ${env_var}")
                    break
            if not self.gitea_token:
                raise click.ClickException(
                    "Git token required. Set via --git-token-env or one of: "
                    "SAPIENS_GITEA_TOKEN, GITEA_TOKEN, GITHUB_TOKEN, GITLAB_TOKEN"
                )

        # Configure AI agent from CLI args if provided
        if self.cli_ai_provider:
            # Map provider to agent type
            if self.cli_ai_provider in ("claude-local", "goose-local", "copilot-local"):
                if self.cli_ai_provider == "claude-local":
                    self.agent_type = AgentType.CLAUDE
                elif self.cli_ai_provider == "goose-local":
                    self.agent_type = AgentType.GOOSE
                else:
                    self.agent_type = AgentType.COPILOT
            else:
                # ollama, openai-compatible use builtin agent
                self.agent_type = AgentType.BUILTIN
                self.builtin_provider = self.cli_ai_provider

            click.echo(f"   ✓ AI provider: {self.cli_ai_provider}")

        if self.cli_ai_model:
            self.builtin_model = self.cli_ai_model
            click.echo(f"   ✓ AI model: {self.cli_ai_model}")

        if self.cli_ai_base_url:
            self.builtin_base_url = self.cli_ai_base_url
            click.echo(f"   ✓ AI base URL: {self.cli_ai_base_url}")

        # Get AI API key from specified env var
        if self.cli_ai_api_key_env:
            self.agent_api_key = os.getenv(self.cli_ai_api_key_env)
            if self.agent_api_key:
                click.echo(f"   ✓ AI API key from ${self.cli_ai_api_key_env}")
            else:
                click.echo(f"   ⚠ ${self.cli_ai_api_key_env} not set (may be OK for local providers)")
        else:
            # Try standard AI key env vars
            self.agent_api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("OPENAI_API_KEY")

        click.echo("   ✓ Non-interactive configuration complete")

    def _collect_interactively(self) -> None:
        """Collect credentials through interactive user prompts.

        Guides the user through credential collection with prompts, validation,
        and helpful information. Handles different paths based on which
        configuration sections the user chose to update.

        Collection Sequence:
            1. Git provider token (Gitea/GitLab/GitHub) if updating git/credentials
            2. AI agent configuration (type, mode, API key) if updating agent
            3. Automation mode settings if updating automation

        Side Effects:
            - Calls provider-specific token collection methods
            - Calls _configure_ai_agent() for agent setup
            - Calls _configure_automation_mode() for automation settings
            - Prints prompts and reads user input
        """
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
        """Collect Gitea API token through interactive prompts.

        For CI/CD mode, guides the user to set up repository secrets and confirms
        they've done so. For local mode, checks for existing tokens in keyring
        or environment before prompting for a new one.

        Token Discovery Order:
            1. Keyring (gitea/api_token)
            2. Environment (GITEA_TOKEN, SAPIENS_GITEA_TOKEN)
            3. Interactive prompt

        Updates:
            self.gitea_token: Set to the collected or discovered token,
                or None for CI/CD mode.

        Raises:
            click.ClickException: If user cancels CI/CD secret setup.

        Side Effects:
            Prints instructions and prompts, reads user input.
        """
        # CI/CD mode: just confirm env var is set
        if self.is_cicd_setup:
            click.echo("For CI/CD workflows, you need to set repository secrets:")
            click.echo()
            click.echo("   • SAPIENS_GITEA_TOKEN - Your Gitea API token")
            click.echo(f"   • Get it from: {self.repo_info.base_url}/user/settings/applications")
            click.echo()
            confirmed = click.confirm("Did you set SAPIENS_GITEA_TOKEN in repository secrets?", default=False)
            if not confirmed:
                secrets_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/settings/secrets"
                click.echo()
                click.echo(f"Set it at: {secrets_url}")
                click.echo()
                if not click.confirm("Continue anyway?", default=False):
                    raise click.ClickException("Setup cancelled - please set repository secrets first")
            # Don't store actual token for CI/CD
            self.gitea_token = None
            return

        # Local mode: collect token
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
                f"Gitea API Token is required. Get it from:\n   {self.repo_info.base_url}/user/settings/applications"
            )
            click.echo()
            self.gitea_token = click.prompt("Enter your Gitea API token", hide_input=True, type=str)

    def _collect_gitlab_token_interactively(self) -> None:
        """Collect GitLab Personal Access Token through interactive prompts.

        Similar to _collect_gitea_token_interactively but for GitLab. For CI/CD
        mode, guides the user to set up CI/CD variables. For local mode, checks
        for existing tokens before prompting.

        Required GitLab Token Scopes:
            - api
            - read_repository
            - write_repository

        Token Discovery Order:
            1. Keyring (gitlab/api_token)
            2. Environment (GITLAB_TOKEN, SAPIENS_GITLAB_TOKEN, CI_JOB_TOKEN)
            3. Interactive prompt

        Updates:
            self.gitea_token: Set to the collected token (reuses field name).

        Raises:
            click.ClickException: If user cancels CI/CD secret setup.

        Side Effects:
            Prints instructions and prompts, reads user input.
        """
        # CI/CD mode: just confirm env var is set
        if self.is_cicd_setup:
            click.echo("For CI/CD workflows, you need to set repository secrets:")
            click.echo()
            click.echo("   • SAPIENS_GITLAB_TOKEN - Your GitLab Personal Access Token")
            pat_url = f"{self.repo_info.base_url}/-/user_settings/personal_access_tokens"
            click.echo(f"   • Get it from: {pat_url}")
            click.echo("   • Required scopes: api, read_repository, write_repository")
            click.echo()
            confirmed = click.confirm("Did you set SAPIENS_GITLAB_TOKEN in repository secrets?", default=False)
            if not confirmed:
                secrets_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/-/settings/ci_cd"
                click.echo()
                click.echo(f"Set it at: {secrets_url}")
                click.echo()
                if not click.confirm("Continue anyway?", default=False):
                    raise click.ClickException("Setup cancelled - please set repository secrets first")
            # Don't store actual token for CI/CD
            self.gitea_token = None
            return

        # Local mode: collect token
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
            click.echo(f"GitLab Personal Access Token is required. Get it from:\n   {pat_url}")
            click.echo()
            click.echo("Required scopes: api, read_repository, write_repository")
            click.echo()
            self.gitea_token = click.prompt("Enter your GitLab Personal Access Token", hide_input=True, type=str)

    def _configure_ai_agent(self) -> None:
        """Configure the AI agent provider through interactive prompts.

        Detects available AI agent CLIs on the system and prompts the user to
        select one. Then delegates to the appropriate configuration method
        based on the selected agent type.

        Supported Agents:
            - Claude (local CLI or API)
            - Goose (local CLI with various LLM backends)
            - Copilot (GitHub CLI extension or copilot-api proxy)
            - Builtin (ReAct agent with Ollama, vLLM, or cloud LLMs)

        Updates:
            self.agent_type: Set to the selected AgentType enum value.
            Additional attributes set by delegated configuration methods.

        Side Effects:
            - Prints agent detection results and selection menu
            - Calls agent-specific configuration methods
            - Reads user selections via click.prompt()
        """
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

            selected = click.prompt(
                "Which agent do you want to use?",
                type=click.Choice(agent_choices),
                default=agent_choices[0] if agent_choices else "builtin",
            )
            self.agent_type = AgentType(selected)

            # Show warning for Copilot selection
            if selected == "copilot":
                click.echo()
                click.secho("WARNING: Unofficial Integration", fg="yellow", bold=True)
                click.echo("The Copilot integration uses an unofficial, reverse-engineered API.")
                click.echo("This is NOT endorsed by GitHub and may violate their ToS.")
                click.echo("It could stop working at any time without notice.")
                click.echo()
                if not click.confirm("Do you understand and accept these risks?", default=False):
                    click.echo("Copilot setup cancelled. Consider using Claude Code or Goose instead.")
                    return
        else:
            click.echo(click.style("⚠ No AI agent CLIs detected", fg="yellow"))
            click.echo()
            click.echo("You can:")
            click.echo("  1. Use builtin ReAct agent (local or cloud LLM)")
            click.echo("  2. Install Claude Code: https://claude.com/install.sh")
            click.echo("  3. Install Goose: pip install goose-ai")
            click.echo("  4. Install GitHub Copilot CLI: gh extension install github/gh-copilot")
            click.echo()

            self.agent_type = AgentType.BUILTIN
            click.echo("Using builtin ReAct agent...")

        # Configure based on agent type
        if self.agent_type == AgentType.CLAUDE:
            self._configure_claude()
        elif self.agent_type == AgentType.GOOSE:
            self._configure_goose()
        elif self.agent_type == AgentType.COPILOT:
            # Offer choice between gh CLI and copilot-api
            click.echo()
            click.echo("GitHub Copilot integration options:")
            click.echo("  cli - Use gh-copilot CLI (limited, command suggestions)")
            click.echo("  api - Use copilot-api proxy (full code generation, unofficial)")
            click.echo()
            copilot_mode = click.prompt(
                "Which integration?",
                type=click.Choice(["cli", "api"]),
                default="cli",
            )
            if copilot_mode == "api":
                self._configure_copilot_api()
                self.agent_type = AgentType.COPILOT  # Keep as COPILOT but use copilot_config
            else:
                self._configure_copilot()  # Existing gh CLI configuration
        elif self.agent_type == AgentType.BUILTIN:
            self._configure_builtin()

    def _configure_claude(self) -> None:
        """Configure Claude agent settings.

        Prompts the user to choose between local Claude CLI or Claude API mode.
        For API mode, collects the API key. For CI/CD setups, only API mode is
        available (local CLI cannot run in CI/CD environment).

        Updates:
            self.agent_mode: Set to 'local' or 'api'.
            self.agent_api_key: Set if API mode selected (local mode only).

        Raises:
            click.ClickException: If user cancels CI/CD API key setup.

        Side Effects:
            Prints configuration options and reads user input.
        """
        click.echo()

        # CI/CD mode: Force API mode and confirm env var
        if self.is_cicd_setup:
            click.echo("For CI/CD workflows, Claude API is required.")
            click.echo()
            click.echo("You need to set repository secrets:")
            click.echo("   • SAPIENS_CLAUDE_API_KEY - Your Claude API key")
            click.echo("   • Get it from: https://console.anthropic.com/")
            click.echo()
            confirmed = click.confirm("Did you set SAPIENS_CLAUDE_API_KEY in repository secrets?", default=False)
            if not confirmed:
                click.echo()
                click.echo("Set it in your repository's CI/CD secrets settings.")
                click.echo()
                if not click.confirm("Continue anyway?", default=False):
                    raise click.ClickException("Setup cancelled - please set repository secrets first")
            self.agent_mode = "api"
            self.agent_api_key = None
            return

        # Local mode: Ask local vs API
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
        """Configure Goose agent with LLM provider and model selection.

        Goose is a local CLI that uses various LLM backends. This method guides
        the user through selecting an LLM provider (OpenAI, Anthropic, Ollama,
        etc.) and model, then collects any required API keys.

        For CI/CD mode, only API-based providers are supported.

        Supported LLM Providers:
            - openai: GPT-4, GPT-3.5 (requires API key)
            - anthropic: Claude models (requires API key)
            - ollama: Local models (no API key needed)
            - openrouter: Various models via router (requires API key)
            - groq: Fast inference (requires API key)

        Updates:
            self.goose_llm_provider: Selected LLM provider name.
            self.goose_model: Selected model identifier.
            self.goose_temperature: Temperature setting (default 0.7).
            self.goose_toolkit: Toolkit name (default 'default').
            self.agent_api_key: Provider API key if required.
            self.agent_mode: Always 'local' (Goose runs locally).

        Raises:
            click.ClickException: If user cancels CI/CD API key setup.

        Side Effects:
            Prints provider comparison, recommendations, and prompts.
        """
        from repo_sapiens.utils.agent_detector import (
            format_provider_comparison,
            get_provider_info,
            get_provider_recommendation,
            get_vllm_vs_ollama_note,
        )

        click.echo()
        click.echo(click.style("🪿 Goose Configuration", bold=True, fg="cyan"))
        click.echo()

        # CI/CD mode: Simplified setup
        if self.is_cicd_setup:
            click.echo("For CI/CD workflows, you need to:")
            click.echo("   1. Choose an LLM provider (API-based)")
            click.echo("   2. Set the provider's API key in repository secrets")
            click.echo()

            self.goose_llm_provider = click.prompt(
                "Which LLM provider?",
                type=click.Choice(["openai", "anthropic", "groq", "openrouter"]),
                default="anthropic",
            )

            provider_info = get_provider_info(self.goose_llm_provider)
            click.echo()
            click.echo(f"Available models for {provider_info['name']}:")
            for model in provider_info["models"][:3]:  # Show top 3
                click.echo(f"  • {model}")

            self.goose_model = click.prompt(
                "Which model?", type=click.Choice(provider_info["models"]), default=provider_info["default_model"]
            )

            if provider_info.get("api_key_env"):
                api_key_env = provider_info["api_key_env"]
                click.echo()
                click.echo("You need to set repository secrets:")
                click.echo(f"   • {api_key_env} - Your {provider_info['name']} API key")
                click.echo(f"   • Get it from: {provider_info.get('website', 'provider website')}")
                click.echo()

                confirmed = click.confirm(f"Did you set {api_key_env} in repository secrets?", default=False)
                if not confirmed:
                    click.echo()
                    click.echo("Set it in your repository's CI/CD secrets settings.")
                    click.echo()
                    if not click.confirm("Continue anyway?", default=False):
                        raise click.ClickException("Setup cancelled - please set repository secrets first")

                self.agent_api_key = None

            self.agent_mode = "local"  # Goose runs locally (but with API-based LLM)
            return

        # Local mode: Full configuration
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

    def _configure_copilot(self) -> None:
        """Configure GitHub Copilot CLI integration.

        Sets up the gh-copilot extension for GitHub CLI. Checks for gh CLI
        availability, Copilot extension installation, and GitHub authentication.
        Offers to install the Copilot extension if not present.

        Note:
            GitHub Copilot CLI has limited capabilities compared to other agents.
            It's primarily designed for command suggestions, not full code
            generation. Requires an active GitHub Copilot subscription.

        Dependency Checks:
            1. GitHub CLI (gh) installed and in PATH
            2. gh-copilot extension installed
            3. gh authenticated with GitHub

        Updates:
            self.agent_mode: Set to 'local'.
            self.agent_api_key: Set to None (uses gh auth).

        Raises:
            click.ClickException: If user declines to continue without gh CLI
                or declines to use Copilot after warnings.

        Side Effects:
            - May install gh-copilot extension via subprocess
            - Prints status checks and warnings
        """
        import shutil
        import subprocess

        click.echo()
        click.echo(click.style("🐙 GitHub Copilot Configuration", bold=True, fg="cyan"))
        click.echo()

        # Check if gh CLI is available
        gh_path = shutil.which("gh")
        if not gh_path:
            click.echo(click.style("⚠ GitHub CLI (gh) not found", fg="red"))
            click.echo("Install from: https://cli.github.com/")
            click.echo()
            if not click.confirm("Continue anyway?", default=False):
                raise click.ClickException("GitHub CLI required for Copilot. Install it first.")
        else:
            click.echo(click.style(f"✓ GitHub CLI found at {gh_path}", fg="green"))

        # Check if Copilot extension is installed
        copilot_installed = False
        if gh_path:
            try:
                result = subprocess.run(  # nosec B607
                    ["gh", "extension", "list"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                copilot_installed = "gh-copilot" in result.stdout or "copilot" in result.stdout
            except Exception:
                pass

        if copilot_installed:
            click.echo(click.style("✓ Copilot extension installed", fg="green"))
        else:
            click.echo(click.style("⚠ Copilot extension not installed", fg="yellow"))
            click.echo("Install with: gh extension install github/gh-copilot")
            click.echo()
            if gh_path and click.confirm("Install Copilot extension now?", default=True):
                try:
                    result = subprocess.run(  # nosec B607
                        ["gh", "extension", "install", "github/gh-copilot"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode == 0:
                        click.echo(click.style("✓ Copilot extension installed", fg="green"))
                        copilot_installed = True
                    else:
                        click.echo(click.style(f"✗ Installation failed: {result.stderr}", fg="red"))
                except subprocess.TimeoutExpired:
                    click.echo(click.style("✗ Installation timed out", fg="red"))
                except Exception as e:
                    click.echo(click.style(f"✗ Installation failed: {e}", fg="red"))

        # Check if gh is authenticated
        if gh_path:
            click.echo()
            try:
                result = subprocess.run(  # nosec B607
                    ["gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    click.echo(click.style("✓ GitHub CLI authenticated", fg="green"))
                else:
                    click.echo(click.style("⚠ GitHub CLI not authenticated", fg="yellow"))
                    click.echo("Run: gh auth login")
            except Exception:
                pass

        click.echo()
        click.echo(click.style("Note:", bold=True, fg="yellow"))
        click.echo("GitHub Copilot CLI has limited capabilities compared to Claude/Goose.")
        click.echo("It's primarily designed for command suggestions, not full code generation.")
        click.echo("A GitHub Copilot subscription is required.")
        click.echo()

        if not click.confirm("Continue with Copilot?", default=True):
            raise click.ClickException("Setup cancelled")

        self.agent_mode = "local"  # Copilot runs locally via gh CLI
        self.agent_api_key = None  # No separate API key needed - uses gh auth

    def _configure_copilot_api(self) -> None:
        """Configure GitHub Copilot API provider using copilot-api proxy.

        This is an alternative Copilot integration that uses the unofficial
        copilot-api proxy to access Copilot's full code generation capabilities.
        Requires a GitHub OAuth token with Copilot scope.

        Warning:
            This uses an unofficial, reverse-engineered API that:
            - Is not endorsed or supported by GitHub
            - May violate GitHub's Terms of Service
            - Could stop working at any time

        Configuration Options:
            - Proxy mode: 'managed' (auto-start npx) or 'external' (connect to existing)
            - Account type: 'individual', 'business', or 'enterprise'
            - Rate limiting: Optional delay between requests
            - Model: GPT-4 or other available models

        Updates:
            self.copilot_github_token: GitHub OAuth token (gho_xxx).
            self.copilot_manage_proxy: True for managed mode.
            self.copilot_proxy_port: Port for managed proxy.
            self.copilot_proxy_url: URL for external proxy.
            self.copilot_account_type: Subscription type.
            self.copilot_rate_limit: Seconds between requests.
            self.copilot_model: Model to use.
            self.agent_mode: Set to 'local'.

        Raises:
            click.ClickException: If user declines risk acceptance or
                declines to continue without Node.js for managed mode.

        Side Effects:
            Prints warnings, configuration options, and prompts.
        """
        import shutil

        click.echo()
        click.echo(click.style("GitHub Copilot API Configuration", bold=True, fg="cyan"))
        click.echo()

        # Security warning
        click.echo(click.style("WARNING:", bold=True, fg="red"))
        click.echo("This integration uses an unofficial, reverse-engineered API.")
        click.echo("  - Not endorsed or supported by GitHub")
        click.echo("  - May violate GitHub Terms of Service")
        click.echo("  - Could stop working at any time")
        click.echo()
        click.echo("You accept full responsibility for compliance with GitHub's ToS.")
        click.echo()

        if not click.confirm("Do you understand and accept these risks?", default=False):
            raise click.ClickException("Setup cancelled - risks not accepted")

        # Check for existing GitHub token
        existing_token, source = self._detect_existing_github_copilot_token()

        if existing_token:
            use_existing = click.confirm(
                click.style(f"GitHub token found in {source}. Use it?", fg="green"),
                default=True,
            )
            if use_existing:
                self.copilot_github_token = existing_token
                click.echo(f"   Using GitHub token from {source}")
            else:
                self.copilot_github_token = self._prompt_github_copilot_token()
        else:
            self.copilot_github_token = self._prompt_github_copilot_token()

        # Proxy mode selection
        click.echo()
        click.echo("Proxy Management Mode:")
        click.echo("  managed  - Auto-start/stop copilot-api (requires Node.js/npm)")
        click.echo("  external - Connect to existing copilot-api instance")
        click.echo()

        proxy_mode = click.prompt(
            "Proxy mode",
            type=click.Choice(["managed", "external"]),
            default="managed",
        )

        self.copilot_manage_proxy = proxy_mode == "managed"

        if self.copilot_manage_proxy:
            # Check Node.js availability
            npx_path = shutil.which("npx")
            if npx_path:
                click.echo(click.style(f"   npx found at {npx_path}", fg="green"))
            else:
                click.echo(click.style("   npx not found", fg="yellow"))
                click.echo("   Install Node.js from: https://nodejs.org/")
                if not click.confirm("   Continue anyway?", default=False):
                    raise click.ClickException("Node.js required for managed proxy mode")

            self.copilot_proxy_port = click.prompt(
                "Proxy port",
                type=int,
                default=4141,
            )
            self.copilot_proxy_url = None
        else:
            self.copilot_proxy_url = click.prompt(
                "Proxy URL",
                type=str,
                default="http://localhost:4141/v1",
            )
            self.copilot_proxy_port = 4141  # Not used, but set default

        # Account type
        click.echo()
        self.copilot_account_type = click.prompt(
            "Copilot account type",
            type=click.Choice(["individual", "business", "enterprise"]),
            default="individual",
        )

        # Rate limiting (recommended)
        click.echo()
        click.echo("Rate limiting helps avoid GitHub abuse detection.")
        if click.confirm("Enable rate limiting?", default=True):
            self.copilot_rate_limit = click.prompt(
                "Seconds between requests",
                type=float,
                default=2.0,
            )
        else:
            self.copilot_rate_limit = None

        # Model selection
        click.echo()
        self.copilot_model = click.prompt(
            "Model to use",
            type=str,
            default="gpt-4",
        )

        self.agent_mode = "local"  # Copilot API runs via local proxy

        click.echo()
        click.echo(click.style("Copilot API configuration complete", fg="green"))

    def _detect_existing_github_copilot_token(self) -> tuple[str | None, str | None]:
        """Check for existing GitHub Copilot OAuth token.

        Searches keyring and environment variables for a GitHub OAuth token
        suitable for Copilot API access.

        Search Order:
            1. Keyring (github/copilot_token)
            2. Environment (GITHUB_COPILOT_TOKEN, GITHUB_TOKEN with gho_ prefix)

        Returns:
            Tuple of (token, source) where:
            - token: The OAuth token string or None if not found.
            - source: Description of where token was found (e.g.,
                "keyring (github/copilot_token)") or None if not found.
        """
        import os

        # Check keyring
        try:
            keyring_backend = KeyringBackend()
            if keyring_backend.available:
                token = keyring_backend.get("github", "copilot_token")
                if token:
                    return token, "keyring (github/copilot_token)"
        except Exception:
            pass

        # Check environment variables
        for env_var in ("GITHUB_COPILOT_TOKEN", "GITHUB_TOKEN"):
            token = os.getenv(env_var)
            if token and token.startswith("gho_"):
                return token, f"environment (${env_var})"

        return None, None

    def _prompt_github_copilot_token(self) -> str:
        """Prompt the user to enter a GitHub Copilot OAuth token.

        Displays instructions for obtaining a token and prompts for input
        with hidden echo (for security).

        Returns:
            The OAuth token string entered by the user.

        Side Effects:
            Prints instructions and reads user input.
        """
        click.echo()
        click.echo("GitHub OAuth token (gho_xxx) required.")
        click.echo("Generate one at: https://github.com/settings/tokens")
        click.echo("Required scope: copilot")
        click.echo()
        return click.prompt("GitHub OAuth token", hide_input=True, type=str)

    def _configure_builtin(self) -> None:
        """Configure the builtin ReAct agent with LLM provider selection.

        The builtin agent uses a ReAct (Reasoning + Acting) loop with an LLM
        for reasoning and local tool execution. Supports both local LLM servers
        (Ollama, vLLM) and cloud providers (OpenAI, Anthropic, etc.).

        For CI/CD mode, only API-based cloud providers are supported.

        Supported Providers:
            - ollama: Local Ollama server (free, requires GPU for best performance)
            - vllm: Local vLLM server (free, optimized for production)
            - openai: OpenAI API (requires API key)
            - anthropic: Anthropic Claude API (requires API key)
            - openrouter: Multi-provider router (requires API key)
            - groq: Groq inference (requires API key)

        Updates:
            self.builtin_provider: Selected provider name.
            self.builtin_model: Selected model identifier.
            self.builtin_base_url: Server URL for local providers.
            self.agent_api_key: API key for cloud providers.
            self.agent_mode: Always 'local' (agent runs locally).

        Side Effects:
            - Prints provider comparison and recommendations
            - Calls provider-specific configuration methods
            - Reads user selections via click.prompt()
        """
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

        # CI/CD mode: Only cloud providers are supported
        if self.is_cicd_setup:
            click.echo("For CI/CD workflows, only API-based providers are supported.")
            click.echo()

            self.builtin_provider = click.prompt(
                "Which LLM provider?",
                type=click.Choice(["openai", "anthropic", "groq", "openrouter"]),
                default="anthropic",
            )

            provider_info = get_provider_info(self.builtin_provider)
            self._configure_builtin_cloud(provider_info)
            self.agent_mode = "local"
            return

        # Local mode: Full configuration
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
        """Configure Ollama as the LLM backend for the builtin agent.

        Prompts for Ollama server URL, checks server availability, lists
        available models, and prompts for model selection. Recommends
        qwen3:8b for tool-calling tasks.

        Args:
            provider_info: Dictionary with provider metadata from agent_detector.

        Updates:
            self.builtin_base_url: Set to Ollama server URL.
            self.builtin_model: Set to selected model name.

        Side Effects:
            - Tests Ollama server connectivity via HTTP
            - Lists available models from server
            - Prints recommendations and prompts
        """
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
        """Configure vLLM as the LLM backend for the builtin agent.

        Prompts for vLLM server URL, checks server availability via the
        OpenAI-compatible API, lists available models, and prompts for
        model selection.

        Args:
            provider_info: Dictionary with provider metadata from agent_detector.

        Updates:
            self.builtin_base_url: Set to vLLM server URL.
            self.builtin_model: Set to selected model name.

        Side Effects:
            - Tests vLLM server connectivity via HTTP (/v1/models)
            - Lists available models from server
            - Prints recommendations and prompts
        """
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
        """Configure a cloud LLM provider for the builtin agent.

        Handles model selection and API key collection for cloud-based LLM
        providers like OpenAI, Anthropic, OpenRouter, and Groq.

        Args:
            provider_info: Dictionary with provider metadata including:
                - name: Display name
                - models: List of available model identifiers
                - default_model: Recommended model
                - api_key_env: Environment variable name for API key
                - website: URL for obtaining API keys

        Updates:
            self.builtin_model: Set to selected model name.
            self.agent_api_key: Set to collected API key (local mode only).

        Raises:
            click.ClickException: If user cancels CI/CD API key setup.

        Side Effects:
            - Prints model options and prompts
            - Checks for existing API key in environment
        """
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
            # CI/CD mode: Just confirm env var is set
            if self.is_cicd_setup:
                click.echo()
                click.echo("You need to set repository secrets:")
                click.echo(f"   • {api_key_env} - Your {provider_info['name']} API key")
                click.echo(f"   • Get it from: {provider_info.get('website', 'provider website')}")
                click.echo()

                confirmed = click.confirm(f"Did you set {api_key_env} in repository secrets?", default=False)
                if not confirmed:
                    click.echo()
                    click.echo("Set it in your repository's CI/CD secrets settings.")
                    click.echo()
                    if not click.confirm("Continue anyway?", default=False):
                        raise click.ClickException("Setup cancelled - please set repository secrets first")

                self.agent_api_key = None
                return

            # Local mode: Collect API key
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
        """Configure the automation trigger mode through interactive prompts.

        Presents the three automation modes with explanations and prompts the
        user to select one. For native/hybrid modes, also configures the label
        prefix used to trigger workflows.

        Automation Modes:
            - native: Instant response via CI/CD workflows triggered by labels.
                No daemon process needed. Uses Gitea/GitHub/GitLab Actions.
            - daemon: Polling-based processing at configurable intervals.
                Requires a continuously running process. Works without CI/CD.
            - hybrid: Combines native triggers with daemon fallback.
                Best reliability, more complex setup.

        Updates:
            self.automation_mode: Set to 'native', 'daemon', or 'hybrid'.
            self.daemon_interval: Set to polling interval in minutes for daemon/hybrid.
            self.label_prefix: Set to user-specified prefix (e.g., 'sapiens/').

        Side Effects:
            Prints mode descriptions and prompts for selection.
        """
        click.echo()
        click.echo(click.style("🔧 Automation Mode Configuration", bold=True, fg="cyan"))
        click.echo()

        # GitLab-specific warning about lack of native label triggers
        is_gitlab = self.provider_type == "gitlab"
        if is_gitlab:
            click.echo(click.style("⚠️  GitLab Note:", fg="yellow", bold=True))
            click.echo("   GitLab does not have native label-triggered pipelines like GitHub/Gitea.")
            click.echo("   For GitLab, sapiens uses scheduled pipelines that poll for labeled issues.")
            click.echo("   The 'daemon' mode is recommended for GitLab repositories.")
            click.echo()

        # Show mode options with explanations
        click.echo("Available modes:")
        click.echo()
        if is_gitlab:
            # For GitLab, daemon is recommended
            click.echo(click.style("  daemon", bold=True) + " (recommended for GitLab)")
            click.echo("    • Scheduled pipeline polls for labeled issues")
            click.echo("    • Configure schedule in GitLab CI/CD settings")
            click.echo("    • Simple setup, no external services needed")
            click.echo()
            click.echo(click.style("  native", bold=True) + " (requires webhook handler)")
            click.echo("    • Real-time response to label changes")
            click.echo("    • Requires deploying webhook-trigger.py service")
            click.echo("    • More complex but instant reactions")
            click.echo()
            click.echo(click.style("  hybrid", bold=True))
            click.echo("    • Webhook handler + scheduled fallback")
            click.echo("    • Best reliability if webhook handler goes down")
        else:
            # For GitHub/Gitea, native is recommended
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

        # Set default based on provider
        default_mode = "daemon" if is_gitlab else "native"

        self.automation_mode = click.prompt(
            "Which mode?",
            type=click.Choice(["native", "daemon", "hybrid"]),
            default=default_mode,
        )

        # Warn GitLab users who select native mode - they need webhook handler
        if is_gitlab and self.automation_mode == "native":
            click.echo()
            click.echo(click.style("⚠️  GitLab Native Mode Setup Required:", fg="yellow", bold=True))
            click.echo()
            click.echo("   GitLab lacks native label-triggered pipelines. To use 'native' mode,")
            click.echo("   you MUST deploy a webhook handler to bridge label events to pipelines.")
            click.echo()
            click.echo(click.style("   Required Setup:", bold=True))
            click.echo("   1. Deploy the webhook handler script:")
            click.echo("      templates/workflows/gitlab/examples/webhook-trigger.py")
            click.echo()
            click.echo("   2. Configure GitLab webhook:")
            click.echo("      Settings → Webhooks → Add webhook")
            click.echo("      URL: https://your-handler/gitlab-webhook")
            click.echo("      Triggers: Issues events, Merge request events")
            click.echo()
            click.echo("   3. Set environment variables on the handler:")
            click.echo("      GITLAB_URL, GITLAB_TOKEN, TRIGGER_TOKEN")
            click.echo()
            click.echo("   See webhook-trigger.py for deployment options (Flask, serverless, etc.)")
            click.echo()
            if not click.confirm("I understand and will set up the webhook handler. Continue?", default=False):
                self.automation_mode = "daemon"
                click.echo("   → Switched to daemon mode (no webhook setup needed)")

        # Configure daemon interval for daemon/hybrid modes
        if self.automation_mode in ("daemon", "hybrid"):
            click.echo()
            click.echo(click.style("Daemon Polling Interval:", bold=True))
            click.echo()
            click.echo("How often should the daemon check for issues with sapiens labels?")
            click.echo("  • Shorter intervals = faster response, more API calls")
            click.echo("  • Longer intervals = fewer resources, delayed response")
            click.echo()
            # Use CLI value if provided, otherwise prompt
            if self.cli_daemon_interval is not None:
                self.daemon_interval = self.cli_daemon_interval
            else:
                self.daemon_interval = click.prompt(
                    "Polling interval (minutes)",
                    type=int,
                    default=5,
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
        if self.automation_mode in ("daemon", "hybrid"):
            click.echo(f"   ✓ Polling interval: {self.daemon_interval} minutes")
        if self.automation_mode in ("native", "hybrid"):
            click.echo(f"   ✓ Label prefix: {self.label_prefix}")

    def _store_credentials(self) -> None:
        """Store collected credentials in the selected backend.

        Dispatches to the appropriate storage method (keyring or environment)
        based on self.backend setting. This persists the credentials for
        later use by sapiens commands.

        Side Effects:
            - Calls _store_in_keyring() or _store_in_environment()
            - Prints progress messages to stdout

        Raises:
            click.ClickException: If credential storage fails.
        """
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
        """Store credentials in the OS keyring for secure persistence.

        Stores git provider tokens and agent API keys in the system keyring
        using the KeyringBackend. Keys are stored under service/key paths
        that match the credential reference format used in config files.

        Storage Locations:
            - gitea/api_token or gitlab/api_token: Git provider token
            - claude/api_key: Claude API key (if using Claude)
            - {provider}/api_key: LLM provider API key (for Goose/builtin)
            - github/copilot_token: Copilot OAuth token (if using Copilot API)

        Side Effects:
            Writes to system keyring, prints confirmation messages.
        """
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
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                # Store under provider-specific key
                backend.set(self.goose_llm_provider, "api_key", self.agent_api_key)
                click.echo(f"   ✓ Stored: {self.goose_llm_provider}/api_key")
            elif self.agent_type == AgentType.BUILTIN and self.builtin_provider:
                # Store under provider-specific key
                backend.set(self.builtin_provider, "api_key", self.agent_api_key)
                click.echo(f"   ✓ Stored: {self.builtin_provider}/api_key")
            elif self.agent_type == AgentType.CLAUDE:
                backend.set("claude", "api_key", self.agent_api_key)
                click.echo("   ✓ Stored: claude/api_key")

        # Store Copilot token if configured
        if self.copilot_github_token:
            backend.set("github", "copilot_token", self.copilot_github_token)
            click.echo("   ✓ Stored: github/copilot_token")

    def _store_in_environment(self) -> None:
        """Store credentials as environment variables for the current session.

        Sets environment variables for the current process. Note that these
        variables only persist for the current shell session. Users should
        add them to their shell profile for persistence.

        Environment Variables Set:
            - SAPIENS_GITEA_TOKEN or GITLAB_TOKEN: Git provider token
            - CLAUDE_API_KEY: Claude API key (if using Claude)
            - {PROVIDER}_API_KEY: LLM provider API key (for Goose/builtin)
            - GITHUB_COPILOT_TOKEN: Copilot OAuth token (if using Copilot API)

        Side Effects:
            Modifies os.environ, prints confirmation and persistence warning.
        """
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
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                # Store under provider-specific environment variable
                env_var = f"{self.goose_llm_provider.upper()}_API_KEY"
                backend.set(env_var, self.agent_api_key)
                click.echo(f"   ✓ Set: {env_var}")
            elif self.agent_type == AgentType.BUILTIN and self.builtin_provider:
                # Store under provider-specific environment variable
                env_var = f"{self.builtin_provider.upper()}_API_KEY"
                backend.set(env_var, self.agent_api_key)
                click.echo(f"   ✓ Set: {env_var}")
            elif self.agent_type == AgentType.CLAUDE:
                backend.set("CLAUDE_API_KEY", self.agent_api_key)
                click.echo("   ✓ Set: CLAUDE_API_KEY")

        # Store Copilot token if configured
        if self.copilot_github_token:
            backend.set("GITHUB_COPILOT_TOKEN", self.copilot_github_token)
            click.echo("   ✓ Set: GITHUB_COPILOT_TOKEN")

        click.echo()
        click.echo(click.style("Note: Environment variables only persist in current session.", fg="yellow"))
        click.echo(
            click.style(
                "Add them to your shell profile or use --backend keyring for persistence.",
                fg="yellow",
            )
        )

    def _setup_gitea_secrets(self) -> None:
        """Set up repository Actions secrets via the provider's API.

        Configures secrets in the repository's CI/CD system for use by
        workflow files. Dispatches to provider-specific methods based on
        self.provider_type.

        Secrets Configured:
            - SAPIENS_GITEA_TOKEN or SAPIENS_GITHUB_TOKEN: Git provider token
            - CLAUDE_API_KEY or {PROVIDER}_API_KEY: Agent API key (API mode)

        Side Effects:
            - Makes API calls to create/update repository secrets
            - Prints progress and status messages

        Note:
            Failures are caught and logged as warnings. Secret setup is not
            critical to the init process and can be done manually later.
        """
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
        """Set up GitHub Actions secrets using the GitHub REST API.

        Creates repository secrets for GitHub Actions workflows. Uses the
        GitHubRestProvider to handle the encrypted secret upload process
        required by GitHub's API.

        Side Effects:
            - Creates/updates repository secrets via GitHub API
            - Prints progress messages

        Note:
            Requires the git provider token to have 'repo' scope for secrets access.
        """
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
        # Note: Both GitHub and Gitea reserve their respective prefixes for secrets
        token_secret_name = "SAPIENS_GITHUB_TOKEN" if self.provider_type == "github" else "SAPIENS_GITEA_TOKEN"
        click.echo(f"   ⏳ Setting {token_secret_name} secret...")
        asyncio.run(github.set_repository_secret(token_secret_name, self.gitea_token))
        click.echo(f"   ✓ Set repository secret: {token_secret_name}")

        # Set agent API key secret if using API mode
        if self.agent_mode == "api" and self.agent_api_key:
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                # Set provider-specific API key for Goose
                secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                click.echo(f"   ⏳ Setting {secret_name} secret...")
                asyncio.run(github.set_repository_secret(secret_name, self.agent_api_key))
                click.echo(f"   ✓ Set repository secret: {secret_name}")
            elif self.agent_type == AgentType.CLAUDE:
                click.echo("   ⏳ Setting CLAUDE_API_KEY secret...")
                asyncio.run(github.set_repository_secret("CLAUDE_API_KEY", self.agent_api_key))
                click.echo("   ✓ Set repository secret: CLAUDE_API_KEY")
        else:
            click.echo("   ℹ Skipped API key secret (using local mode)")

        click.echo()

    def _setup_gitea_secrets_mcp(self) -> None:
        """Set up Gitea Actions secrets via MCP server integration.

        Attempts to configure Gitea repository secrets. Currently delegates
        to _set_gitea_secret_via_mcp which displays manual setup instructions.

        Side Effects:
            Prints instructions for manual secret setup.

        Note:
            Full MCP integration for secret management is pending. For now,
            users must configure secrets manually in the Gitea web UI.
        """
        # Set SAPIENS_GITEA_TOKEN secret (note: GITEA_ prefix is reserved by Gitea)
        click.echo("   ⏳ Setting SAPIENS_GITEA_TOKEN secret...")
        # Note: We'll need to use the MCP server directly since GiteaRestProvider
        # doesn't expose secret management yet
        self._set_gitea_secret_via_mcp("SAPIENS_GITEA_TOKEN", self.gitea_token)
        click.echo("   ✓ Set repository secret: SAPIENS_GITEA_TOKEN")

        # Set agent API key secret if using API mode
        if self.agent_mode == "api" and self.agent_api_key:
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                # Set provider-specific API key for Goose
                secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                click.echo(f"   ⏳ Setting {secret_name} secret...")
                self._set_gitea_secret_via_mcp(secret_name, self.agent_api_key)
                click.echo(f"   ✓ Set repository secret: {secret_name}")
            elif self.agent_type == AgentType.CLAUDE:
                click.echo("   ⏳ Setting CLAUDE_API_KEY secret...")
                self._set_gitea_secret_via_mcp("CLAUDE_API_KEY", self.agent_api_key)
                click.echo("   ✓ Set repository secret: CLAUDE_API_KEY")
        else:
            click.echo("   ℹ Skipped API key secret (using local mode)")

        click.echo()

    def _set_gitea_secret_via_mcp(self, name: str, value: str) -> None:
        """Set a Gitea Actions secret (placeholder for MCP integration).

        Currently displays manual setup instructions since full MCP integration
        for secret management is not yet implemented.

        Args:
            name: Secret name (e.g., 'SAPIENS_GITEA_TOKEN').
            value: Secret value to store (unused in current implementation).

        Side Effects:
            Prints manual setup instructions with URL to Gitea secrets page.

        Todo:
            Implement actual MCP call to upsert_repo_action_secret when
            MCP integration is complete.
        """
        # TODO: Use mcp__gitea__upsert_repo_action_secret when MCP integration is complete
        click.echo(click.style(f"   ℹ Please set {name} manually in Gitea UI for now", fg="yellow"))
        secrets_url = f"{self.repo_info.base_url}/{self.repo_info.owner}/{self.repo_info.repo}/settings/secrets"
        click.echo(f"   Navigate to: {secrets_url}")

    def _generate_config(self) -> None:
        """Generate the YAML configuration file.

        Creates or updates the sapiens configuration file based on collected
        settings. Handles credential references, agent provider configuration,
        and automation mode settings.

        Configuration Sections Generated:
            - git_provider: Provider type, base URL, API token reference
            - repository: Owner, name, default branch
            - agent_provider: Agent type, model, API key reference, mode settings
            - automation: Mode, label triggers, workflow configuration
            - workflow: Plans directory, state directory, branching strategy
            - tags: Label names for workflow states

        File Locations:
            - Local mode: self.repo_path / self.config_path
            - CI/CD mode: self.repo_path / self.cicd_config_path

        Side Effects:
            - Creates parent directories if they don't exist
            - Writes YAML configuration file
            - Prints confirmation message
        """
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
            elif self.provider_type == "github":
                git_token_ref = "@keyring:github/api_token"  # nosec B105
            else:
                git_token_ref = "@keyring:gitea/api_token"  # nosec B105

            # Determine agent API key reference
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                agent_api_key_ref = f"@keyring:{self.goose_llm_provider}/api_key" if self.agent_api_key else "null"
            elif self.agent_type == AgentType.BUILTIN and self.builtin_provider:
                agent_api_key_ref = f"@keyring:{self.builtin_provider}/api_key" if self.agent_api_key else "null"
            elif self.agent_type == AgentType.CLAUDE:
                agent_api_key_ref = "@keyring:claude/api_key" if self.agent_api_key else "null"
            else:
                agent_api_key_ref = "null"
        else:
            # Environment backend - use Pydantic env var format for CICD compatibility
            # The dispatcher sets AUTOMATION__GIT_PROVIDER__API_TOKEN and
            # AUTOMATION__AGENT_PROVIDER__API_KEY which get interpolated by from_yaml()
            git_token_ref = "${AUTOMATION__GIT_PROVIDER__API_TOKEN}"  # nosec B105

            # Agent API key - use unified env var for CICD
            agent_api_key_ref = "${AUTOMATION__AGENT_PROVIDER__API_KEY}" if self.agent_api_key else "null"

        # Generate agent provider configuration
        if self.agent_type == AgentType.GOOSE:
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
        elif self.agent_type == AgentType.BUILTIN:
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
        elif self.agent_type == AgentType.COPILOT:
            # Check for Copilot API configuration (has copilot_github_token set)
            if self.copilot_github_token is not None:
                # Copilot API mode
                if self.backend == "keyring":
                    token_ref = "@keyring:github/copilot_token"
                else:
                    token_ref = "${GITHUB_COPILOT_TOKEN}"

                rate_limit_line = (
                    f"    rate_limit: {self.copilot_rate_limit}"
                    if self.copilot_rate_limit
                    else "    # rate_limit: 2.0  # Recommended"
                )
                if self.copilot_manage_proxy:
                    proxy_line = f"    proxy_port: {self.copilot_proxy_port}"
                else:
                    proxy_line = f'    proxy_url: "{self.copilot_proxy_url}"'

                agent_config = f'''agent_provider:
  provider_type: copilot-local
  copilot_config:
    github_token: "{token_ref}"
    manage_proxy: {str(self.copilot_manage_proxy).lower()}
{proxy_line}
    account_type: {self.copilot_account_type}
{rate_limit_line}
    model: "{self.copilot_model}"'''
            else:
                # Copilot CLI mode (existing gh-copilot)
                provider_type = "copilot-local"
                model = "gpt-4"  # Default model for Copilot
                agent_config = f"""agent_provider:
  provider_type: {provider_type}
  model: {model}
  api_key: null
  local_mode: true"""
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
        """Generate the automation section of the configuration file.

        Creates YAML content for the automation configuration based on the
        selected mode. Includes mode flags and, for native/hybrid modes,
        predefined label trigger definitions.

        Returns:
            YAML string for the automation section, ready to be included
            in the full configuration file.

        Label Triggers Generated (native/hybrid modes):
            - sapiens/triage: AI-powered issue triage
            - needs-planning: Generate implementation proposals
            - execute: Execute approved plans
        """
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
    daemon_interval: {self.daemon_interval}
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
        """Deploy the reusable sapiens-task composite action to the repository.

        Copies the appropriate composite action template (GitHub, GitLab, or
        Gitea) to the repository's actions directory. This action is used by
        the workflow templates to run sapiens tasks.

        Target Directories:
            - GitHub: .github/actions/sapiens-task/action.yaml
            - GitLab: .gitlab/actions/sapiens-task/action.yaml
            - Gitea: .gitea/actions/sapiens-task/action.yaml

        Template Sources (in order of precedence):
            1. importlib.resources (installed package)
            2. Package directory (development)
            3. Repository root templates/ (development)

        Side Effects:
            - Creates action directory and file
            - Prints confirmation or warning message
        """
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

    def _deploy_workflows(self, requested_tiers: tuple[str, ...]) -> None:
        """Deploy CI/CD workflow templates based on selected tiers.

        Workflow Tiers:
            - essential: process-label.yaml (label-triggered AI work)
            - core: post-merge-docs.yaml, weekly-test-coverage.yaml (repo maintenance)
            - security: weekly-security-review.yaml, weekly-dependency-audit.yaml,
                weekly-sbom-license.yaml (security audits)
            - support: daily-issue-triage.yaml (issue management)

        Provider Behavior:
            - GitHub: Essential tier deploys thin wrapper → dispatcher; other tiers
                deploy actual workflow files
            - Gitea/GitLab: All tiers deploy actual workflow files

        Args:
            requested_tiers: Tuple of tier names to deploy. Empty tuple triggers
                interactive selection. 'all' deploys everything. Essential is
                always implied when other tiers are specified.

        Side Effects:
            - Creates workflow directories and files
            - Prints progress and confirmation messages
            - Prompts user for tier selection (interactive mode, if no tiers specified)
        """
        import importlib.resources

        # Define tier mappings
        workflow_tiers = {
            "essential": [
                ("process-label.yaml", "Process label (label-triggered AI work)"),
            ],
            "core": [
                ("recipes/post-merge-docs.yaml", "Post-merge documentation update"),
                ("recipes/weekly-test-coverage.yaml", "Weekly test coverage report"),
            ],
            "security": [
                ("recipes/weekly-security-review.yaml", "Weekly security review"),
                ("recipes/weekly-dependency-audit.yaml", "Weekly dependency audit"),
                ("recipes/weekly-sbom-license.yaml", "Weekly SBOM & license compliance"),
            ],
            "support": [
                ("recipes/daily-issue-triage.yaml", "Daily issue triage"),
            ],
        }

        click.echo(click.style("📋 Deploying workflow templates...", bold=True))
        click.echo()

        # Determine which tiers to deploy
        tiers_to_deploy: set[str] = set()

        if "all" in requested_tiers:
            tiers_to_deploy = {"essential", "core", "security", "support"}
        elif requested_tiers:
            # Add requested tiers plus essential (always implied)
            tiers_to_deploy = set(requested_tiers) | {"essential"}
        elif not self.non_interactive:
            # Interactive tier selection
            click.echo("Select workflow tiers to deploy:")
            click.echo()
            click.echo("  essential - Label-triggered AI work (process-label)")
            click.echo("  core      - Repo maintenance (post-merge docs, test coverage)")
            click.echo("  security  - Security audits (dependency, code, SBOM)")
            click.echo("  support   - Issue management (daily triage)")
            click.echo()

            # Essential is always deployed
            tiers_to_deploy.add("essential")
            click.echo("   ✓ essential (always included)")

            if click.confirm("Deploy 'core' tier (post-merge docs, test coverage)?", default=True):
                tiers_to_deploy.add("core")
            if click.confirm("Deploy 'security' tier (security audits)?", default=False):
                tiers_to_deploy.add("security")
            if click.confirm("Deploy 'support' tier (daily issue triage)?", default=False):
                tiers_to_deploy.add("support")
            click.echo()
        else:
            # Non-interactive with no tiers specified - skip
            click.echo("   No workflow tiers specified, skipping deployment.")
            click.echo("   Use --deploy-workflows essential|core|security|support|all")
            return

        # Determine paths based on provider type
        if self.provider_type == "github":
            workflows_dir = self.repo_path / ".github" / "workflows"
            template_base = "workflows/github/sapiens"
        elif self.provider_type == "gitlab":
            workflows_dir = self.repo_path
            template_base = "workflows/gitlab/sapiens"
        else:  # gitea
            workflows_dir = self.repo_path / ".github" / "workflows"
            template_base = "workflows/gitea/sapiens"

        workflows_dir.mkdir(parents=True, exist_ok=True)

        def deploy_template(template_name: str) -> bool:
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
                    if is_recipe:
                        gitlab_dir = self.repo_path / ".gitlab" / "sapiens" / "recipes"
                        gitlab_dir.mkdir(parents=True, exist_ok=True)
                        target_file = gitlab_dir / template_name.replace("recipes/", "")
                    else:
                        target_file = workflows_dir / ".gitlab-ci.yml"
                else:
                    # GitHub/Gitea: use subdirectory structure
                    sapiens_dir = workflows_dir / "sapiens"
                    if is_recipe:
                        target_file = sapiens_dir / "recipes" / template_name.replace("recipes/", "")
                    else:
                        target_file = sapiens_dir / template_name
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                target_file.write_text(content)
                return True
            except Exception:
                return False

        def deploy_github_wrapper() -> bool:
            """Deploy thin wrapper for GitHub that calls the dispatcher."""
            # Use the CLI-specified AI API key env var name as the secret name
            # Default to SAPIENS_AI_API_KEY if not specified
            ai_secret_name = self.cli_ai_api_key_env or "SAPIENS_AI_API_KEY"

            # Get AI provider configuration from CLI options or defaults
            ai_provider_type = self.cli_ai_provider or "openai-compatible"
            ai_model = self.cli_ai_model or ""
            ai_base_url = self.cli_ai_base_url or ""

            # Build optional AI config lines (only include if values are set)
            ai_config_lines = []
            if ai_provider_type:
                ai_config_lines.append(f"      ai_provider_type: '{ai_provider_type}'")
            if ai_model:
                ai_config_lines.append(f"      ai_model: '{ai_model}'")
            if ai_base_url:
                ai_config_lines.append(f"      ai_base_url: '{ai_base_url}'")
            ai_config = "\n".join(ai_config_lines)

            wrapper_content = f"""# Sapiens Automation - GitHub Workflow
# This thin wrapper calls the reusable sapiens-dispatcher workflow
# See: https://github.com/savorywatt/repo-sapiens

name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

# Required for cross-repo reusable workflows - grants permissions to the called workflow
permissions:
  contents: write
  issues: write
  pull-requests: write

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v2
    with:
      label: ${{{{ github.event.label.name }}}}
      issue_number: ${{{{ github.event.issue.number || github.event.pull_request.number }}}}
      event_type: ${{{{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}}}
{ai_config}
    secrets:
      GIT_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
      AI_API_KEY: ${{{{ secrets.{ai_secret_name} }}}}
"""
            try:
                target_file = workflows_dir / "sapiens.yaml"
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(wrapper_content)
                return True
            except Exception:
                return False

        # Deploy workflows for each selected tier
        click.echo(f"Deploying tiers: {', '.join(sorted(tiers_to_deploy))}")
        click.echo()

        for tier in sorted(tiers_to_deploy):
            workflows = workflow_tiers.get(tier, [])

            for template_name, description in workflows:
                # For GitHub essential tier, deploy thin wrapper instead
                if self.provider_type == "github" and tier == "essential" and template_name == "process-label.yaml":
                    if deploy_github_wrapper():
                        click.echo(f"   ✓ {description} → sapiens.yaml (dispatcher wrapper)")
                    else:
                        click.echo(click.style(f"   ⚠ Could not deploy: {description}", fg="yellow"))
                else:
                    if deploy_template(template_name):
                        if self.provider_type == "gitlab":
                            if template_name.startswith("recipes/"):
                                click.echo(f"   ✓ {description} → .gitlab/sapiens/recipes/")
                            else:
                                click.echo(f"   ✓ {description} → .gitlab-ci.yml")
                        else:
                            if template_name.startswith("recipes/"):
                                click.echo(f"   ✓ {description} → sapiens/recipes/")
                            else:
                                click.echo(f"   ✓ {description} → sapiens/")
                    else:
                        click.echo(click.style(f"   ⚠ Could not deploy: {description}", fg="yellow"))

        click.echo()

    def _remove_workflows(self, requested_tiers: tuple[str, ...]) -> None:
        """Remove CI/CD workflow templates based on selected tiers.

        Workflow Tiers:
            - essential: process-label.yaml (label-triggered AI work)
            - core: post-merge-docs.yaml, weekly-test-coverage.yaml (repo maintenance)
            - security: weekly-security-review.yaml, weekly-dependency-audit.yaml,
                weekly-sbom-license.yaml (security audits)
            - support: daily-issue-triage.yaml (issue management)

        Args:
            requested_tiers: Tuple of tier names to remove. 'all' removes everything.

        Side Effects:
            - Deletes workflow files from the repository
            - Cleans up empty directories (sapiens/, recipes/)
            - Prints progress and confirmation messages
        """
        # Define tier mappings (same as _deploy_workflows)
        workflow_tiers = {
            "essential": [
                ("process-label.yaml", "Process label (label-triggered AI work)"),
            ],
            "core": [
                ("recipes/post-merge-docs.yaml", "Post-merge documentation update"),
                ("recipes/weekly-test-coverage.yaml", "Weekly test coverage report"),
            ],
            "security": [
                ("recipes/weekly-security-review.yaml", "Weekly security review"),
                ("recipes/weekly-dependency-audit.yaml", "Weekly dependency audit"),
                ("recipes/weekly-sbom-license.yaml", "Weekly SBOM & license compliance"),
            ],
            "support": [
                ("recipes/daily-issue-triage.yaml", "Daily issue triage"),
            ],
        }

        click.echo(click.style("🗑️  Removing workflow templates...", bold=True))
        click.echo()

        # Determine which tiers to remove
        tiers_to_remove: set[str] = set()

        if "all" in requested_tiers:
            tiers_to_remove = {"essential", "core", "security", "support"}
        else:
            tiers_to_remove = set(requested_tiers)

        # Determine paths based on provider type
        if self.provider_type == "github":
            workflows_dir = self.repo_path / ".github" / "workflows"
        elif self.provider_type == "gitlab":
            workflows_dir = self.repo_path / ".gitlab" / "sapiens"
        else:  # gitea
            workflows_dir = self.repo_path / ".github" / "workflows"

        sapiens_dir = workflows_dir / "sapiens" if self.provider_type != "gitlab" else workflows_dir

        def remove_file(file_path: Path, description: str) -> bool:
            """Remove a single file and report status."""
            if file_path.exists():
                try:
                    file_path.unlink()
                    click.echo(f"   ✓ Removed: {description}")
                    return True
                except Exception as e:
                    click.echo(click.style(f"   ⚠ Could not remove {description}: {e}", fg="yellow"))
                    return False
            else:
                click.echo(f"   - Not present: {description}")
                return False

        # Remove workflows for each selected tier
        click.echo(f"Removing tiers: {', '.join(sorted(tiers_to_remove))}")
        click.echo()

        removed_count = 0

        for tier in sorted(tiers_to_remove):
            workflows = workflow_tiers.get(tier, [])

            for template_name, description in workflows:
                is_recipe = template_name.startswith("recipes/")

                # Handle essential tier's thin wrapper for GitHub
                if self.provider_type == "github" and tier == "essential" and template_name == "process-label.yaml":
                    wrapper_file = workflows_dir / "sapiens.yaml"
                    if remove_file(wrapper_file, f"{description} (sapiens.yaml)"):
                        removed_count += 1
                else:
                    # Determine target file path
                    if self.provider_type == "gitlab":
                        if is_recipe:
                            target_file = sapiens_dir / "recipes" / template_name.replace("recipes/", "")
                        else:
                            # GitLab main workflow is .gitlab-ci.yml
                            target_file = self.repo_path / ".gitlab-ci.yml"
                    else:
                        # GitHub/Gitea
                        if is_recipe:
                            target_file = sapiens_dir / "recipes" / template_name.replace("recipes/", "")
                        else:
                            target_file = sapiens_dir / template_name

                    if remove_file(target_file, description):
                        removed_count += 1

        # Clean up empty directories
        click.echo()
        click.echo("Cleaning up empty directories...")

        directories_to_check = [
            sapiens_dir / "recipes",
            sapiens_dir,
        ]

        for directory in directories_to_check:
            if directory.exists() and directory.is_dir():
                try:
                    # Check if directory is empty
                    if not any(directory.iterdir()):
                        directory.rmdir()
                        rel_path = directory.relative_to(self.repo_path)
                        click.echo(f"   ✓ Removed empty directory: {rel_path}")
                except Exception:
                    pass  # Directory not empty or other issue

        click.echo()
        click.echo(f"Removed {removed_count} workflow file(s)")
        click.echo()

    def _deploy_validation_workflow(self, workflows_dir: Path, deploy_fn) -> None:
        """Deploy a validation workflow for testing sapiens configuration.

        Creates a provider-specific validation workflow that can be run
        manually or on a schedule to verify the sapiens setup is working
        correctly. The workflow runs health-check and produces a diagnostic
        report.

        Args:
            workflows_dir: Target directory for workflow files.
            deploy_fn: Deployment function (unused, content is generated).

        Side Effects:
            - Creates validation workflow file
            - Prints confirmation or error message
        """
        # Create validation workflow content based on provider
        if self.provider_type == "github":
            workflow_content = self._generate_github_validation_workflow()
            target_file = workflows_dir / "sapiens" / "validate.yaml"
        elif self.provider_type == "gitlab":
            workflow_content = self._generate_gitlab_validation_workflow()
            target_file = self.repo_path / ".gitlab" / "sapiens" / "validate.yaml"
        else:  # gitea
            workflow_content = self._generate_gitea_validation_workflow()
            target_file = workflows_dir / "sapiens" / "validate.yaml"

        target_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            target_file.write_text(workflow_content)
            click.echo(f"   ✓ Validation workflow → {target_file.relative_to(self.repo_path)}")
        except Exception as e:
            click.echo(click.style(f"   ⚠ Could not deploy validation workflow: {e}", fg="yellow"))

    def _generate_github_validation_workflow(self) -> str:
        """Generate GitHub Actions validation workflow YAML content.

        Creates a workflow that runs sapiens health-check with full validation,
        produces a JSON report, and uploads it as an artifact. Runs weekly
        and can be triggered manually.

        Returns:
            Complete YAML content for the GitHub Actions workflow file.
        """
        return """name: Sapiens Validation

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6am UTC

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install sapiens
        run: |
          pip install uv
          uv pip install --system repo-sapiens

      - name: Run validation
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SAPIENS_GITHUB_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          sapiens health-check --full --json > validation-report.json
        continue-on-error: true

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: validation-report.json

      - name: Check results
        run: |
          if grep -q '"failed": 0' validation-report.json; then
            echo "All validation tests passed!"
          else
            echo "Some validation tests failed. Check the report."
            exit 1
          fi
"""

    def _generate_gitea_validation_workflow(self) -> str:
        """Generate Gitea Actions validation workflow YAML content.

        Creates a workflow compatible with Gitea Actions that runs sapiens
        health-check with full validation. Similar to the GitHub version but
        uses Gitea-specific secret names.

        Returns:
            Complete YAML content for the Gitea Actions workflow file.
        """
        return """name: Sapiens Validation

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6am UTC

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install sapiens
        run: |
          pip install uv
          uv pip install --system repo-sapiens

      - name: Run validation
        env:
          SAPIENS_GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          SAPIENS_CLAUDE_API_KEY: ${{ secrets.SAPIENS_CLAUDE_API_KEY }}
        run: |
          sapiens health-check --full --json > validation-report.json
        continue-on-error: true

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: validation-report.json

      - name: Check results
        run: |
          if grep -q '"failed": 0' validation-report.json; then
            echo "All validation tests passed!"
          else
            echo "Some validation tests failed. Check the report."
            exit 1
          fi
"""

    def _generate_gitlab_validation_workflow(self) -> str:
        """Generate GitLab CI validation workflow YAML content.

        Creates a GitLab CI job that runs sapiens health-check with full
        validation. Uses GitLab's pipeline source rules for scheduling
        and manual triggering.

        Returns:
            Complete YAML content for the GitLab CI validation job.
        """
        return """# Sapiens Validation Pipeline
# Run manually or on schedule to validate sapiens configuration

validate-sapiens:
  stage: test
  image: python:3.12
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  before_script:
    - pip install uv
    - uv pip install --system repo-sapiens
  script:
    - sapiens health-check --full --json > validation-report.json || true
    - |
      if grep -q '"failed": 0' validation-report.json; then
        echo "All validation tests passed!"
      else
        echo "Some validation tests failed. Check the report."
        cat validation-report.json
        exit 1
      fi
  artifacts:
    paths:
      - validation-report.json
    when: always
    expire_in: 1 week
"""

    def _validate_setup(self) -> None:
        """Validate the completed setup by testing credential resolution.

        Performs a basic validation by attempting to resolve the git provider
        token using the configured credential reference. This confirms that
        credentials are properly stored and accessible.

        Side Effects:
            - Prints validation status messages
            - Logs warning if validation fails (non-fatal)
        """
        click.echo(click.style("✓ Validating setup...", bold=True))

        try:
            # Test credential resolution
            resolver = CredentialResolver()

            if self.backend == "keyring":
                if self.provider_type == "gitlab":
                    token_ref = "@keyring:gitlab/api_token"
                elif self.provider_type == "github":
                    token_ref = "@keyring:github/api_token"
                else:
                    token_ref = "@keyring:gitea/api_token"
            else:
                # Environment backend uses Pydantic env var format for CICD compatibility
                # Skip validation - env vars are set by the dispatcher at runtime
                click.echo("   ✓ Environment backend configured (credentials resolved at runtime)")
                click.echo("   ✓ Configuration file created")
                click.echo()
                return

            resolved = resolver.resolve(token_ref, cache=False)
            if not resolved:
                raise ValueError(f"Failed to resolve {self.provider_type} token")

            click.echo("   ✓ Credentials validated")
            click.echo("   ✓ Configuration file created")
            click.echo()

        except Exception as e:
            click.echo(click.style(f"   ⚠ Warning: Validation failed: {e}", fg="yellow"))
            click.echo()

    def _get_provider_urls(self) -> dict[str, str]:
        """Generate provider-specific URLs for settings and documentation.

        Builds URLs for various provider-specific pages based on the detected
        provider type and repository information. Used by _print_next_steps
        and _print_secrets_setup for user guidance.

        Returns:
            Dictionary containing URLs for:
            - issues: Issue tracker page
            - actions/pipelines: Workflow/pipeline runs
            - secrets/variables: Secret configuration page
            - token: Token generation page
            - token_name: Display name for token type
            - token_scopes: Required token scopes/permissions
        """
        base = str(self.repo_info.base_url).rstrip("/")
        owner = self.repo_info.owner
        repo = self.repo_info.repo

        if self.provider_type == "github":
            # GitHub URLs
            if "github.com" in base:
                token_url = "https://github.com/settings/tokens/new?scopes=repo,read:org,workflow"
            else:
                # GitHub Enterprise
                token_url = f"{base}/settings/tokens/new?scopes=repo,read:org,workflow"

            return {
                "issues": f"{base}/{owner}/{repo}/issues",
                "actions": f"{base}/{owner}/{repo}/actions",
                "secrets": f"{base}/{owner}/{repo}/settings/secrets/actions",
                "token": token_url,
                "token_name": "Personal Access Token (Classic)",
                "token_scopes": "repo, read:org, workflow",
            }

        elif self.provider_type == "gitlab":
            return {
                "issues": f"{base}/{owner}/{repo}/-/issues",
                "pipelines": f"{base}/{owner}/{repo}/-/pipelines",
                "variables": f"{base}/{owner}/{repo}/-/settings/ci_cd#js-cicd-variables-settings",
                "token": f"{base}/-/user_settings/personal_access_tokens",
                "token_name": "Personal Access Token",
                "token_scopes": "api, read_repository, write_repository",
            }

        else:  # gitea
            return {
                "issues": f"{base}/{owner}/{repo}/issues",
                "actions": f"{base}/{owner}/{repo}/actions",
                "secrets": f"{base}/{owner}/{repo}/settings/secrets",
                "token": f"{base}/user/settings/applications",
                "token_name": "Access Token",
                "token_scopes": "repo (read/write), issue (read/write)",
            }

    def _get_required_secrets(self) -> list[tuple[str, str, str | None]]:
        """Get the list of secrets required for the configured setup.

        Builds a list of required CI/CD secrets based on the git provider
        and agent configuration. Used by _print_secrets_setup to show
        users what secrets they need to configure.

        Returns:
            List of tuples, each containing:
            - secret_name: Name of the required secret
            - description: Human-readable description of what it's for
            - token_url: URL where the token can be obtained (or None)
        """
        secrets = []
        urls = self._get_provider_urls()

        # Git provider token
        if self.provider_type == "github":
            secrets.append(
                (
                    "GITHUB_TOKEN or SAPIENS_GITHUB_TOKEN",
                    f"GitHub {urls['token_name']} with scopes: {urls['token_scopes']}",
                    urls["token"],
                )
            )
        elif self.provider_type == "gitlab":
            secrets.append(
                (
                    "SAPIENS_GITLAB_TOKEN",
                    f"GitLab {urls['token_name']} with scopes: {urls['token_scopes']}",
                    urls["token"],
                )
            )
        else:  # gitea
            secrets.append(
                (
                    "SAPIENS_GITEA_TOKEN",
                    f"Gitea {urls['token_name']} with permissions: {urls['token_scopes']}",
                    urls["token"],
                )
            )

        # Agent API key (if using API mode)
        if self.agent_mode == "api":
            if self.agent_type == AgentType.GOOSE and self.goose_llm_provider:
                secret_name = f"{self.goose_llm_provider.upper()}_API_KEY"
                if self.goose_llm_provider == "anthropic":
                    secrets.append(
                        (
                            secret_name,
                            "Anthropic API key for Goose",
                            "https://console.anthropic.com/settings/keys",
                        )
                    )
                elif self.goose_llm_provider == "openai":
                    secrets.append(
                        (
                            secret_name,
                            "OpenAI API key for Goose",
                            "https://platform.openai.com/api-keys",
                        )
                    )
                else:
                    secrets.append((secret_name, f"{self.goose_llm_provider.title()} API key for Goose", None))
            elif self.agent_type == AgentType.CLAUDE:
                secrets.append(
                    (
                        "CLAUDE_API_KEY or ANTHROPIC_API_KEY",
                        "Anthropic API key for Claude",
                        "https://console.anthropic.com/settings/keys",
                    )
                )
            elif self.agent_type == AgentType.BUILTIN:
                if self.builtin_provider == "anthropic":
                    secrets.append(
                        (
                            "ANTHROPIC_API_KEY",
                            "Anthropic API key",
                            "https://console.anthropic.com/settings/keys",
                        )
                    )
                elif self.builtin_provider == "openai":
                    secrets.append(
                        (
                            "OPENAI_API_KEY",
                            "OpenAI API key",
                            "https://platform.openai.com/api-keys",
                        )
                    )

        return secrets

    def _print_next_steps(self) -> None:
        """Print post-initialization guidance for the user.

        Displays a summary of next steps the user should take to complete
        their setup and start using sapiens. Includes secrets setup
        instructions, workflow testing guidance, and mode-specific tips.

        Side Effects:
            Prints formatted guidance to stdout with URLs and commands.
        """
        provider_name = self.provider_type.title()
        urls = self._get_provider_urls()

        click.echo(click.style("📋 Next Steps:", bold=True))
        click.echo()

        # Step 1: Set up secrets/variables for CI/CD workflows
        if self.setup_secrets and self.automation_mode in ("native", "hybrid"):
            self._print_secrets_setup(urls)

        # Step 2: Try the workflow
        step_num = 2 if self.setup_secrets and self.automation_mode in ("native", "hybrid") else 1
        click.echo(f"{step_num}. Label an issue with '{self.label_prefix}needs-planning' in {provider_name}:")
        click.echo(f"   {urls['issues']}")
        click.echo()

        # Mode-specific instructions
        step_num += 1
        if self.automation_mode == "native":
            click.echo(f"{step_num}. Workflows will trigger automatically when you add labels!")
            click.echo()
            click.echo("   • Label triggers are active immediately")
            click.echo("   • No daemon process needed")
            if self.provider_type == "gitlab":
                click.echo(f"   • Check pipelines: {urls['pipelines']}")
            else:
                click.echo(f"   • Check workflows: {urls['actions']}")
        elif self.automation_mode == "daemon":
            daemon_seconds = self.daemon_interval * 60
            click.echo(f"{step_num}. Run the automation daemon:")
            click.echo(f"   sapiens --config {self.config_path} daemon --interval {daemon_seconds}")
            click.echo()
            click.echo(f"{step_num + 1}. Watch the automation work!")
        else:  # hybrid
            daemon_seconds = self.daemon_interval * 60
            click.echo(f"{step_num}. Automation runs in hybrid mode:")
            click.echo("   • Label triggers work instantly via workflows")
            if self.provider_type == "gitlab":
                click.echo(f"   • Check pipelines: {urls['pipelines']}")
            else:
                click.echo(f"   • Check workflows: {urls['actions']}")
            click.echo()
            click.echo("   • Optional: Run daemon for additional automation:")
            click.echo(f"     sapiens --config {self.config_path} daemon --interval {daemon_seconds}")

        click.echo()
        click.echo("For more information, see:")
        click.echo("  - README.md")
        click.echo("  - QUICK_START.md")
        click.echo("  - docs/CREDENTIAL_QUICK_START.md")

    def _print_secrets_setup(self, urls: dict[str, str]) -> None:
        """Print detailed instructions for setting up CI/CD secrets.

        Displays provider-specific instructions for configuring repository
        secrets or CI/CD variables. Includes URLs and required values.

        Args:
            urls: Dictionary of provider URLs from _get_provider_urls().

        Side Effects:
            Prints formatted secret setup instructions to stdout.
        """
        provider_name = self.provider_type.title()
        secrets = self._get_required_secrets()

        if self.provider_type == "gitlab":
            click.echo(click.style("1. Set GitLab CI/CD Variables", bold=True, fg="yellow"))
            click.echo("   (Required for workflow automation)")
            click.echo()
            click.echo(f"   Navigate to: {urls['variables']}")
            click.echo("   Expand 'Variables' section and add:")
        else:
            click.echo(click.style(f"1. Set {provider_name} Actions Secrets", bold=True, fg="yellow"))
            click.echo("   (Required for workflow automation)")
            click.echo()
            click.echo(f"   Navigate to: {urls['secrets']}")
            click.echo("   Add the following secrets:")

        click.echo()

        for secret_name, description, token_url in secrets:
            click.echo(f"   • {click.style(secret_name, bold=True)}")
            click.echo(f"     {description}")
            if token_url:
                click.echo(f"     Get it here: {token_url}")
            click.echo()

        # Add note about marking as protected/masked for GitLab
        if self.provider_type == "gitlab":
            click.echo(click.style("   Tip:", fg="cyan") + " Mark variables as 'Protected' and 'Masked' for security")
            click.echo()

    def _offer_test_run(self) -> None:
        """Offer to run a test command to verify the agent setup.

        Prompts the user to run a simple test that uses the configured agent
        to summarize the repository's README file. This helps verify the
        agent is working correctly.

        Test Commands by Agent Type:
            - Claude: claude -p "Summarize..."
            - Goose: goose session start --prompt "Summarize..."
            - Builtin: sapiens task "Summarize..."

        Side Effects:
            - Prompts user for confirmation
            - Runs test command via subprocess (if confirmed)
            - Prints test results and REPL suggestion

        Note:
            Only offered if README.md exists and agent type has a test command.
        """
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

        if self.agent_type == AgentType.CLAUDE:
            test_cmd = f'claude -p "{test_prompt}"'
        elif self.agent_type == AgentType.GOOSE:
            test_cmd = f'goose session start --prompt "{test_prompt}"'
        elif self.agent_type == AgentType.BUILTIN:
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
        if self.agent_type == AgentType.BUILTIN:
            repl_cmd = f"sapiens {config_flag}task --repl".replace("  ", " ")
        elif self.agent_type == AgentType.CLAUDE:
            repl_cmd = "claude"
        elif self.agent_type == AgentType.GOOSE:
            repl_cmd = "goose session start"
        else:
            repl_cmd = None

        if repl_cmd:
            click.echo(click.style("💡 Try the interactive REPL:", fg="cyan"))
            click.echo(f"  {repl_cmd}")
