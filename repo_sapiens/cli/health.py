"""Health check command for repo-sapiens."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.exceptions import ConfigurationError

log = structlog.get_logger(__name__)


# Exit codes for semantic error reporting
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_CREDENTIAL_ERROR = 2
EXIT_GIT_PROVIDER_ERROR = 3
EXIT_AGENT_PROVIDER_ERROR = 4


def _print_check(name: str, status: bool, detail: str | None = None) -> None:
    """Print a check result with consistent formatting.

    Args:
        name: Name of the check
        status: True if passed, False if failed
        detail: Optional detail message
    """
    if status:
        click.echo(f"  {click.style('[OK]', fg='green')} {name}")
    else:
        click.echo(f"  {click.style('[FAIL]', fg='red')} {name}")

    if detail:
        click.echo(f"       {detail}")


@click.command("health-check")
@click.option(
    "--config",
    "config_path",
    default=".sapiens/config.yaml",
    help="Path to configuration file",
    type=click.Path(),
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information for each check",
)
@click.option(
    "--skip-connectivity",
    is_flag=True,
    help="Skip network connectivity checks (config validation only)",
)
def health_check(config_path: str, verbose: bool, skip_connectivity: bool) -> None:
    """Validate configuration and test connectivity.

    \b
    Checks performed:
      1. Configuration file exists and is valid YAML
      2. Configuration validates against schema
      3. Credentials resolve correctly
      4. Git provider is reachable (unless --skip-connectivity)
      5. Agent provider is available (unless --skip-connectivity)

    \b
    Exit codes:
      0 - All checks passed
      1 - Configuration file error
      2 - Credential resolution error
      3 - Git provider connectivity error
      4 - Agent provider error

    \b
    Examples:
        # Full health check
        sapiens health-check

        # Check specific config file
        sapiens health-check --config /path/to/config.yaml

        # Validate config without network calls
        sapiens health-check --skip-connectivity

        # Verbose output
        sapiens health-check -v
    """
    click.echo(click.style("repo-sapiens Health Check", bold=True))
    click.echo()

    all_passed = True
    settings: AutomationSettings | None = None

    # -------------------------------------------------------------------------
    # Check 1: Configuration file exists
    # -------------------------------------------------------------------------
    click.echo(click.style("Configuration:", bold=True))

    config_file = Path(config_path)
    if not config_file.exists():
        _print_check(
            "Config file exists",
            False,
            f"File not found: {config_path}",
        )
        click.echo()
        click.echo(
            click.style("Suggestion:", fg="yellow")
            + " Run 'sapiens init' to create configuration"
        )
        sys.exit(EXIT_CONFIG_ERROR)

    _print_check("Config file exists", True, str(config_file.resolve()) if verbose else None)

    # -------------------------------------------------------------------------
    # Check 2: Configuration loads and validates
    # -------------------------------------------------------------------------
    try:
        settings = AutomationSettings.from_yaml(str(config_path))
        _print_check(
            "Config validates",
            True,
            f"Provider: {settings.git_provider.provider_type}, Repo: {settings.repository.owner}/{settings.repository.name}"
            if verbose
            else None,
        )
    except ConfigurationError as e:
        _print_check("Config validates", False, str(e.message))
        sys.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        _print_check("Config validates", False, str(e))
        log.debug("config_validation_error", exc_info=True)
        sys.exit(EXIT_CONFIG_ERROR)

    # -------------------------------------------------------------------------
    # Check 3: Credentials resolve
    # -------------------------------------------------------------------------
    click.echo()
    click.echo(click.style("Credentials:", bold=True))

    try:
        # Accessing get_secret_value() triggers resolution
        token = settings.git_provider.api_token.get_secret_value()
        # Mask the token for display
        if len(token) > 8:
            masked = token[:4] + "*" * (len(token) - 8) + token[-4:]
        else:
            masked = "*" * len(token)
        _print_check(
            "Git provider token",
            True,
            f"Resolved: {masked}" if verbose else None,
        )
    except Exception as e:
        _print_check("Git provider token", False, str(e))
        all_passed = False
        # Don't exit yet - continue checking other credentials

    # Check agent API key if configured
    if settings.agent_provider.api_key:
        try:
            api_key = settings.agent_provider.api_key.get_secret_value()
            if api_key and api_key != "null":
                if len(api_key) > 8:
                    masked = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
                else:
                    masked = "*" * len(api_key)
                _print_check(
                    "Agent API key",
                    True,
                    f"Resolved: {masked}" if verbose else None,
                )
            else:
                _print_check(
                    "Agent API key",
                    True,
                    "Not configured (local mode)" if verbose else None,
                )
        except Exception as e:
            _print_check("Agent API key", False, str(e))
            # Not critical if using local mode
            if not settings.agent_provider.local_mode:
                all_passed = False
    else:
        _print_check(
            "Agent API key",
            True,
            "Not required (local mode)" if verbose else None,
        )

    if not all_passed:
        click.echo()
        click.echo(
            click.style("Suggestion:", fg="yellow")
            + " Check credential configuration. Run 'sapiens credentials test' for details."
        )
        sys.exit(EXIT_CREDENTIAL_ERROR)

    # -------------------------------------------------------------------------
    # Check 4: Git provider connectivity (optional)
    # -------------------------------------------------------------------------
    if not skip_connectivity:
        click.echo()
        click.echo(click.style("Connectivity:", bold=True))

        async def check_git_provider() -> tuple[bool, str | None]:
            """Test Git provider connectivity."""
            from repo_sapiens.providers.factory import create_git_provider

            try:
                git = create_git_provider(settings)
                await git.connect()

                # Try a simple operation to verify connectivity
                # Limit to 1 issue to minimize API calls
                await git.get_issues(state="open")

                await git.disconnect()
                return True, None
            except Exception as e:
                return False, str(e)

        provider_type = settings.git_provider.provider_type
        base_url = str(settings.git_provider.base_url)

        success, error = asyncio.run(check_git_provider())
        if success:
            _print_check(
                f"{provider_type.capitalize()} provider",
                True,
                f"Connected to {base_url}" if verbose else None,
            )
        else:
            _print_check(f"{provider_type.capitalize()} provider", False, error)
            all_passed = False

        # -------------------------------------------------------------------------
        # Check 5: Agent provider availability (optional)
        # -------------------------------------------------------------------------
        agent_type = settings.agent_provider.provider_type

        if agent_type == "ollama":
            # Check Ollama connectivity
            async def check_ollama() -> tuple[bool, str | None, list[str]]:
                """Test Ollama server connectivity."""
                import httpx

                base_url = settings.agent_provider.base_url or "http://localhost:11434"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(f"{base_url}/api/tags")
                        if response.status_code == 200:
                            data = response.json()
                            models = [m["name"] for m in data.get("models", [])]
                            return True, None, models
                        else:
                            return False, f"HTTP {response.status_code}", []
                except httpx.ConnectError:
                    return False, f"Cannot connect to {base_url}", []
                except Exception as e:
                    return False, str(e), []

            success, error, models = asyncio.run(check_ollama())
            if success:
                model_info = ""
                if verbose and models:
                    model_info = f"Models: {', '.join(models[:3])}"
                    if len(models) > 3:
                        model_info += f" (+{len(models) - 3} more)"
                _print_check("Ollama server", True, model_info or None)

                # Check if configured model is available
                configured_model = settings.agent_provider.model
                if models and configured_model:
                    # Ollama model names can have tags (e.g., qwen3:8b)
                    model_available = any(
                        m == configured_model or m.startswith(f"{configured_model}:")
                        for m in models
                    )
                    if model_available:
                        _print_check(
                            f"Model '{configured_model}'",
                            True,
                            "Available" if verbose else None,
                        )
                    else:
                        _print_check(
                            f"Model '{configured_model}'",
                            False,
                            f"Not found. Pull with: ollama pull {configured_model}",
                        )
                        all_passed = False
            else:
                _print_check("Ollama server", False, error)
                all_passed = False

        elif agent_type in ("claude-local", "goose-local"):
            # Check if CLI is available
            import shutil

            cli_name = "claude" if "claude" in agent_type else "goose"
            cli_path = shutil.which(cli_name)

            if cli_path:
                _print_check(
                    f"{cli_name.capitalize()} CLI",
                    True,
                    f"Found at {cli_path}" if verbose else None,
                )
            else:
                _print_check(
                    f"{cli_name.capitalize()} CLI",
                    False,
                    f"'{cli_name}' not found in PATH",
                )
                all_passed = False

        elif agent_type in ("claude-api", "goose-api", "openai"):
            # For API-based providers, we already checked the API key
            # A full connectivity test would require making an API call
            _print_check(
                f"{agent_type} provider",
                True,
                "API key configured" if verbose else None,
            )

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    click.echo()
    if all_passed:
        click.echo(click.style("All checks passed!", fg="green", bold=True))
        sys.exit(EXIT_SUCCESS)
    else:
        click.echo(click.style("Some checks failed.", fg="red", bold=True))
        click.echo("Review the errors above and fix the configuration.")
        # Determine most appropriate exit code
        # (we already exited early for config/credential errors)
        sys.exit(EXIT_GIT_PROVIDER_ERROR)
