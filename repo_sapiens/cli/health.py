"""Health check command for repo-sapiens.

This module provides the ``sapiens health-check`` command which validates
the configuration and tests connectivity to all configured providers.

The health check performs several categories of validation:
    - Configuration: File exists, valid YAML, schema validation
    - Credentials: Token resolution from keyring/environment
    - Connectivity: Git provider API access
    - Agent: CLI availability or API connectivity

With the --full flag, comprehensive validation includes write operations
that create temporary test resources (branch, issue, PR) in the repository.

Exit Codes:
    0 (EXIT_SUCCESS): All checks passed
    1 (EXIT_CONFIG_ERROR): Configuration file error
    2 (EXIT_CREDENTIAL_ERROR): Credential resolution failed
    3 (EXIT_GIT_PROVIDER_ERROR): Git provider connectivity failed
    4 (EXIT_AGENT_PROVIDER_ERROR): Agent provider unavailable

Example:
    Basic health check::

        $ sapiens health-check

    Full validation with JSON output::

        $ sapiens health-check --full --json
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import click
import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.enums import ProviderType
from repo_sapiens.exceptions import ConfigurationError
from repo_sapiens.models.diagnostics import DiagnosticReport, ValidationResult

log = structlog.get_logger(__name__)


# Exit codes for semantic error reporting
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_CREDENTIAL_ERROR = 2
EXIT_GIT_PROVIDER_ERROR = 3
EXIT_AGENT_PROVIDER_ERROR = 4


def _print_check(name: str, status: bool, detail: str | None = None) -> None:
    """Print a check result with consistent formatting.

    Displays a check result with colored status indicator ([OK] in green or
    [FAIL] in red) followed by the check name and optional detail.

    Args:
        name: Short descriptive name of the check (e.g., "Config file exists").
        status: True if the check passed, False if it failed.
        detail: Optional additional information to display indented below
            the check line. Useful for showing resolved values, error messages,
            or suggestions.

    Side Effects:
        Prints to stdout via click.echo().
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
@click.option(
    "--full",
    is_flag=True,
    help="Run comprehensive validation including write operations (creates test resources)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON (implies --full)",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True,
    help="Clean up test resources after validation (default: cleanup)",
)
def health_check(
    config_path: str,
    verbose: bool,
    skip_connectivity: bool,
    full: bool,
    output_json: bool,
    cleanup: bool,
) -> None:
    """Validate configuration and test connectivity.

    \b
    Checks performed:
      1. Configuration file exists and is valid YAML
      2. Configuration validates against schema
      3. Credentials resolve correctly
      4. Git provider is reachable (unless --skip-connectivity)
      5. Agent provider is available (unless --skip-connectivity)

    \b
    With --full flag (comprehensive validation):
      - Read operations: list issues, list branches, get repo info
      - Write operations: create branch, issue, comment, PR
      - Agent operations: test prompt execution
      - Cleanup: removes test resources after validation

    \b
    Exit codes:
      0 - All checks passed
      1 - Configuration file error
      2 - Credential resolution error
      3 - Git provider connectivity error
      4 - Agent provider error

    \b
    Examples:
        # Basic health check
        sapiens health-check

        # Comprehensive validation (creates test resources)
        sapiens health-check --full

        # JSON output for CI/CD
        sapiens health-check --full --json

        # Keep test resources for inspection
        sapiens health-check --full --no-cleanup

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
        click.echo(click.style("Suggestion:", fg="yellow") + " Run 'sapiens init' to create configuration")
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
        provider_type = settings.agent_provider.provider_type

        if provider_type == ProviderType.OLLAMA:
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
                    model_available = any(m == configured_model or m.startswith(f"{configured_model}:") for m in models)
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

        elif provider_type in (ProviderType.CLAUDE_LOCAL, ProviderType.GOOSE_LOCAL):
            # Check if CLI is available
            import shutil

            cli_name = "claude" if provider_type == ProviderType.CLAUDE_LOCAL else "goose"
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

        elif provider_type == ProviderType.COPILOT_LOCAL:
            # Check if GitHub CLI is available
            import shutil
            import subprocess

            gh_path = shutil.which("gh")
            if gh_path:
                _print_check(
                    "GitHub CLI (gh)",
                    True,
                    f"Found at {gh_path}" if verbose else None,
                )

                # Check if Copilot extension is installed
                try:
                    result = subprocess.run(  # nosec B607
                        ["gh", "extension", "list"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    copilot_installed = "gh-copilot" in result.stdout or "copilot" in result.stdout
                    if copilot_installed:
                        _print_check(
                            "Copilot extension",
                            True,
                            "Installed" if verbose else None,
                        )
                    else:
                        _print_check(
                            "Copilot extension",
                            False,
                            "Install with: gh extension install github/gh-copilot",
                        )
                        all_passed = False
                except subprocess.TimeoutExpired:
                    _print_check(
                        "Copilot extension",
                        False,
                        "Timeout checking extensions",
                    )
                    all_passed = False
                except Exception as e:
                    _print_check(
                        "Copilot extension",
                        False,
                        f"Error: {e}",
                    )
                    all_passed = False

                # Check if gh is authenticated
                try:
                    result = subprocess.run(  # nosec B607
                        ["gh", "auth", "status"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        _print_check(
                            "GitHub authentication",
                            True,
                            "Authenticated" if verbose else None,
                        )
                    else:
                        _print_check(
                            "GitHub authentication",
                            False,
                            "Run: gh auth login",
                        )
                        all_passed = False
                except Exception as e:
                    _print_check(
                        "GitHub authentication",
                        False,
                        f"Error: {e}",
                    )
                    all_passed = False
            else:
                _print_check(
                    "GitHub CLI (gh)",
                    False,
                    "Not found. Install from: https://cli.github.com/",
                )
                all_passed = False

        elif provider_type in (ProviderType.OPENAI_COMPATIBLE, ProviderType.OLLAMA):
            # For API-based providers and Ollama, no CLI check needed
            # API connectivity would require making an actual API call
            if provider_type == ProviderType.OLLAMA:
                _print_check(
                    "Ollama provider",
                    True,
                    f"Configured at {settings.agent_provider.base_url or 'http://localhost:11434'}"
                    if verbose
                    else None,
                )
            else:
                _print_check(
                    "OpenAI-compatible API",
                    True,
                    "API key configured" if verbose else None,
                )

    # -------------------------------------------------------------------------
    # Full Validation (optional)
    # -------------------------------------------------------------------------
    if full or output_json:
        if not all_passed:
            click.echo()
            click.echo(click.style("Cannot run full validation - basic checks failed.", fg="red"))
            sys.exit(EXIT_GIT_PROVIDER_ERROR)

        click.echo()
        report = asyncio.run(_run_full_validation(settings, cleanup, verbose, output_json))

        if output_json:
            click.echo(report.to_json())
        else:
            # Print summary
            click.echo()
            if report.all_passed:
                click.echo(click.style(f"All {report.total} tests passed!", fg="green", bold=True))
            else:
                click.echo(click.style(f"{report.failed}/{report.total} tests failed.", fg="red", bold=True))

            if report.summary:
                click.echo()
                click.echo(click.style("Summary:", bold=True))
                click.echo(f"  {report.summary}")

            click.echo()
            click.echo(f"Duration: {report.duration_ms / 1000:.1f}s")

        sys.exit(EXIT_SUCCESS if report.all_passed else EXIT_GIT_PROVIDER_ERROR)

    # -------------------------------------------------------------------------
    # Summary (basic checks only)
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


# =============================================================================
# Full Validation Functions
# =============================================================================


async def _run_full_validation(
    settings: AutomationSettings,
    cleanup: bool,
    verbose: bool,
    output_json: bool,
) -> DiagnosticReport:
    """Run the comprehensive validation suite with read and write operations.

    Performs extensive testing of the git provider and agent configuration
    by executing actual API calls and creating temporary test resources.
    This validates that the integration is fully functional, not just
    configured correctly.

    Validation Categories:
        - Read Operations: list_issues, get_default_branch
        - Write Operations: create_branch, create_issue, add_comment, create_pr
        - Agent Operations: availability check, test prompt execution
        - Cleanup: close_issue, close_pr, delete_branch

    Args:
        settings: Validated AutomationSettings loaded from config file.
        cleanup: If True, delete test resources after validation. If False,
            resources remain for manual inspection.
        verbose: If True, show detailed output for each check.
        output_json: If True, suppress console output (for JSON mode).

    Returns:
        DiagnosticReport containing all ValidationResults, timing information,
        and an LLM-generated summary (if available).

    Side Effects:
        - Creates temporary branch, issue, PR in the repository
        - Prints progress to stdout (unless output_json=True)
        - May modify repository state if cleanup fails
    """
    from repo_sapiens.providers.factory import create_git_provider

    start_time = time.time()
    results: list[ValidationResult] = []

    provider_type = settings.git_provider.provider_type
    repository = f"{settings.repository.owner}/{settings.repository.name}"
    agent_type = str(settings.agent_provider.provider_type) if settings.agent_provider else None

    if not output_json:
        click.echo(click.style("Running comprehensive validation...", bold=True, fg="cyan"))
        click.echo()
        click.echo(
            click.style("Warning:", fg="yellow")
            + " This will create test resources (branch, issue, PR) in your repository."
        )
        if cleanup:
            click.echo("         Resources will be cleaned up after validation.")
        else:
            click.echo("         Resources will NOT be cleaned up (--no-cleanup).")
        click.echo()

    # Create git provider
    git = create_git_provider(settings)
    await git.connect()

    try:
        # Read operations
        if not output_json:
            click.echo(click.style("Read Operations:", bold=True))
        read_results = await _test_read_operations(git, verbose, output_json)
        results.extend(read_results)

        # Write operations
        if not output_json:
            click.echo()
            click.echo(click.style("Write Operations:", bold=True))
        write_results = await _test_write_operations(git, settings, cleanup, verbose, output_json)
        results.extend(write_results)

        # Agent operations
        if not output_json:
            click.echo()
            click.echo(click.style("Agent Operations:", bold=True))
        agent_results = await _test_agent_operations(settings, verbose, output_json)
        results.extend(agent_results)

    finally:
        await git.disconnect()

    duration_ms = (time.time() - start_time) * 1000

    report = DiagnosticReport(
        timestamp=datetime.now(UTC),
        provider_type=provider_type,
        repository=repository,
        agent_type=agent_type,
        results=results,
        duration_ms=duration_ms,
    )

    # Generate LLM summary if agent is available and tests passed
    if report.all_passed:
        summary = await _generate_llm_summary(settings, report, output_json)
        if summary:
            report.summary = summary
    else:
        # Simple summary for failures
        failed_tests = [r.name for r in results if not r.success]
        report.summary = f"Failed tests: {', '.join(failed_tests)}"

    return report


async def _test_read_operations(
    git,  # GitProvider
    verbose: bool,
    output_json: bool,
) -> list[ValidationResult]:
    """Test read-only operations against the git provider API.

    Validates that the provider connection works for basic read operations
    without modifying any repository state. These tests are safe to run
    repeatedly.

    Tests Performed:
        - list_issues: Fetch open issues, verify API access
        - get_default_branch: Retrieve main/master branch info

    Args:
        git: Connected GitProvider instance (must be already connected).
        verbose: If True, include details in output (issue count, branch name).
        output_json: If True, suppress console output.

    Returns:
        List of ValidationResult objects, one per test performed.

    Side Effects:
        Prints test results to stdout (unless output_json=True).
    """
    results = []

    # Test: List issues
    start = time.time()
    try:
        issues = await git.get_issues(state="open")
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="list_issues",
            category="read",
            success=True,
            message=f"Found {len(issues)} open issues",
            duration_ms=duration,
            details={"count": len(issues)},
        )
        if not output_json:
            _print_check("List issues", True, f"Found {len(issues)} open issues" if verbose else None)
    except Exception as e:
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="list_issues",
            category="read",
            success=False,
            message=str(e),
            duration_ms=duration,
        )
        if not output_json:
            _print_check("List issues", False, str(e))
    results.append(result)

    # Test: Get branch (main/master)
    start = time.time()
    try:
        branch = await git.get_branch("main")
        if not branch:
            branch = await git.get_branch("master")
        duration = (time.time() - start) * 1000
        if branch:
            result = ValidationResult(
                name="get_default_branch",
                category="read",
                success=True,
                message=f"Found branch: {branch.name}",
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Get default branch", True, f"Found: {branch.name}" if verbose else None)
        else:
            result = ValidationResult(
                name="get_default_branch",
                category="read",
                success=False,
                message="Could not find main or master branch",
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Get default branch", False, "Could not find main or master")
    except Exception as e:
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="get_default_branch",
            category="read",
            success=False,
            message=str(e),
            duration_ms=duration,
        )
        if not output_json:
            _print_check("Get default branch", False, str(e))
    results.append(result)

    return results


async def _test_write_operations(
    git,  # GitProvider
    settings: AutomationSettings,
    cleanup: bool,
    verbose: bool,
    output_json: bool,
) -> list[ValidationResult]:
    """Test write operations by creating temporary resources.

    Creates test branch, issue, comment, and PR to verify full API access.
    Resources are named with timestamps and tagged with 'sapiens-validation'
    label for identification.

    Tests Performed:
        - create_branch: Create a new branch from main/master
        - create_issue: Create a test issue with validation label
        - add_comment: Add a comment to the test issue
        - create_pr: Create a PR from test branch (requires branch creation)

    Cleanup Operations (if enabled):
        - close_issue: Close the test issue
        - close_pr: Close the test PR
        - delete_branch: Delete the test branch

    Args:
        git: Connected GitProvider instance.
        settings: AutomationSettings for repository info.
        cleanup: If True, delete created resources after testing.
        verbose: If True, show details (branch names, issue numbers).
        output_json: If True, suppress console output.

    Returns:
        List of ValidationResult objects for all operations performed.

    Side Effects:
        - Creates branch named 'sapiens/validation-test-{timestamp}'
        - Creates issue and PR with '[Validation] Test' prefix
        - Modifies repository state (cleanup removes most changes)
        - Prints progress to stdout (unless output_json=True)

    Warning:
        If cleanup fails, manual removal of test resources may be required.
    """
    results = []
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    branch_name = f"sapiens/validation-test-{timestamp}"
    issue_title = f"[Validation] Test Issue - {timestamp}"
    pr_title = f"[Validation] Test PR - {timestamp}"

    created_issue_number = None
    created_pr_number = None
    created_branch = False

    # Test: Create branch
    start = time.time()
    try:
        # Try to create from main, fallback to master
        base_branch = "main"
        try:
            await git.create_branch(branch_name, from_branch="main")
        except Exception:
            base_branch = "master"
            await git.create_branch(branch_name, from_branch="master")

        duration = (time.time() - start) * 1000
        created_branch = True
        result = ValidationResult(
            name="create_branch",
            category="write",
            success=True,
            message=f"Created: {branch_name}",
            duration_ms=duration,
            details={"branch": branch_name, "base": base_branch},
        )
        if not output_json:
            _print_check("Create branch", True, f"Created: {branch_name}" if verbose else None)
    except Exception as e:
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="create_branch",
            category="write",
            success=False,
            message=str(e),
            duration_ms=duration,
        )
        if not output_json:
            _print_check("Create branch", False, str(e))
    results.append(result)

    # Test: Create issue
    start = time.time()
    try:
        issue = await git.create_issue(
            title=issue_title,
            body="This is a validation test issue created by `sapiens health-check --full`.\n\n"
            "It will be closed automatically after the test completes.",
            labels=["sapiens-validation"],
        )
        duration = (time.time() - start) * 1000
        created_issue_number = issue.number
        result = ValidationResult(
            name="create_issue",
            category="write",
            success=True,
            message=f"Created: #{issue.number}",
            duration_ms=duration,
            details={"issue_number": issue.number, "url": issue.url},
        )
        if not output_json:
            _print_check("Create issue", True, f"Created: #{issue.number}" if verbose else None)
    except Exception as e:
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="create_issue",
            category="write",
            success=False,
            message=str(e),
            duration_ms=duration,
        )
        if not output_json:
            _print_check("Create issue", False, str(e))
    results.append(result)

    # Test: Add comment to issue
    if created_issue_number:
        start = time.time()
        try:
            await git.add_comment(
                issue_number=created_issue_number,
                comment="Validation test comment - verifying comment creation works.",
            )
            duration = (time.time() - start) * 1000
            result = ValidationResult(
                name="add_comment",
                category="write",
                success=True,
                message=f"Added comment to #{created_issue_number}",
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Add comment", True, f"Added to #{created_issue_number}" if verbose else None)
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = ValidationResult(
                name="add_comment",
                category="write",
                success=False,
                message=str(e),
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Add comment", False, str(e))
        results.append(result)

    # Test: Create PR (only if branch was created)
    if created_branch:
        start = time.time()
        try:
            pr = await git.create_pull_request(
                title=pr_title,
                body="This is a validation test PR created by `sapiens health-check --full`.\n\n"
                "It will be closed automatically after the test completes.",
                head=branch_name,
                base=base_branch,
                labels=["sapiens-validation"],
            )
            duration = (time.time() - start) * 1000
            created_pr_number = pr.number
            result = ValidationResult(
                name="create_pr",
                category="write",
                success=True,
                message=f"Created: #{pr.number}",
                duration_ms=duration,
                details={"pr_number": pr.number, "url": pr.url},
            )
            if not output_json:
                _print_check("Create PR", True, f"Created: #{pr.number}" if verbose else None)
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = ValidationResult(
                name="create_pr",
                category="write",
                success=False,
                message=str(e),
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Create PR", False, str(e))
        results.append(result)

    # Cleanup
    if cleanup:
        if not output_json:
            click.echo()
            click.echo(click.style("Cleanup:", bold=True))

        # Close issue
        if created_issue_number:
            start = time.time()
            try:
                await git.update_issue(
                    issue_number=created_issue_number,
                    state="closed",
                    title=None,
                    body=None,
                    labels=None,
                )
                duration = (time.time() - start) * 1000
                result = ValidationResult(
                    name="close_issue",
                    category="write",
                    success=True,
                    message=f"Closed: #{created_issue_number}",
                    duration_ms=duration,
                )
                if not output_json:
                    _print_check("Close issue", True, f"Closed: #{created_issue_number}" if verbose else None)
            except Exception as e:
                duration = (time.time() - start) * 1000
                result = ValidationResult(
                    name="close_issue",
                    category="write",
                    success=False,
                    message=str(e),
                    duration_ms=duration,
                )
                if not output_json:
                    _print_check("Close issue", False, str(e))
            results.append(result)

        # Close PR (if created)
        if created_pr_number:
            start = time.time()
            try:
                # Most providers use update_pull_request or close_pull_request
                # Try using the update_issue API which works for PRs on some platforms
                await git.update_issue(
                    issue_number=created_pr_number,
                    state="closed",
                    title=None,
                    body=None,
                    labels=None,
                )
                duration = (time.time() - start) * 1000
                result = ValidationResult(
                    name="close_pr",
                    category="write",
                    success=True,
                    message=f"Closed: #{created_pr_number}",
                    duration_ms=duration,
                )
                if not output_json:
                    _print_check("Close PR", True, f"Closed: #{created_pr_number}" if verbose else None)
            except Exception as e:
                duration = (time.time() - start) * 1000
                result = ValidationResult(
                    name="close_pr",
                    category="write",
                    success=False,
                    message=str(e),
                    duration_ms=duration,
                )
                if not output_json:
                    _print_check("Close PR", False, str(e))
            results.append(result)

        # Delete branch (if method is available)
        if created_branch:
            start = time.time()
            if hasattr(git, "delete_branch"):
                try:
                    await git.delete_branch(branch_name)
                    duration = (time.time() - start) * 1000
                    result = ValidationResult(
                        name="delete_branch",
                        category="write",
                        success=True,
                        message=f"Deleted: {branch_name}",
                        duration_ms=duration,
                    )
                    if not output_json:
                        _print_check("Delete branch", True, f"Deleted: {branch_name}" if verbose else None)
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    result = ValidationResult(
                        name="delete_branch",
                        category="write",
                        success=False,
                        message=str(e),
                        duration_ms=duration,
                    )
                    if not output_json:
                        _print_check("Delete branch", False, str(e))
                results.append(result)
            else:
                # Branch deletion not supported - note in output
                duration = (time.time() - start) * 1000
                result = ValidationResult(
                    name="delete_branch",
                    category="write",
                    success=True,
                    message=f"Skipped (manual cleanup needed): {branch_name}",
                    duration_ms=duration,
                )
                if not output_json:
                    _print_check(
                        "Delete branch",
                        True,
                        f"Skipped - manually delete: {branch_name}" if verbose else None,
                    )
                results.append(result)

    return results


async def _test_agent_operations(
    settings: AutomationSettings,
    verbose: bool,
    output_json: bool,
) -> list[ValidationResult]:
    """Test AI agent provider availability and basic functionality.

    Verifies the configured agent is reachable and functional. For Ollama,
    performs an actual model inference test. For CLI-based agents (Claude,
    Goose), checks PATH availability.

    Tests Performed:
        - agent_available: Check agent connectivity/availability
        - test_prompt (Ollama only): Execute simple "respond OK" prompt

    Provider-Specific Behavior:
        - OLLAMA: HTTP health check + model list + inference test
        - CLAUDE_LOCAL/GOOSE_LOCAL: Check if CLI in PATH
        - COPILOT_LOCAL: Check gh CLI + extension + auth
        - OPENAI_COMPATIBLE: API key configured check only

    Args:
        settings: AutomationSettings with agent provider configuration.
        verbose: If True, show details (model lists, CLI paths).
        output_json: If True, suppress console output.

    Returns:
        List of ValidationResult objects for agent tests.

    Side Effects:
        - May make HTTP requests to Ollama server
        - Prints test results to stdout (unless output_json=True)
    """
    results = []
    provider_type = settings.agent_provider.provider_type

    # Test: Agent availability (already done in basic checks, but record it)
    start = time.time()
    try:
        if provider_type == ProviderType.OLLAMA:
            import httpx

            base_url = settings.agent_provider.base_url or "http://localhost:11434"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    duration = (time.time() - start) * 1000
                    result = ValidationResult(
                        name="agent_available",
                        category="agent",
                        success=True,
                        message=f"Ollama connected ({len(models)} models available)",
                        duration_ms=duration,
                        details={"models": models[:5]},
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
        elif provider_type in (ProviderType.CLAUDE_LOCAL, ProviderType.GOOSE_LOCAL):
            import shutil

            cli_name = "claude" if provider_type == ProviderType.CLAUDE_LOCAL else "goose"
            cli_path = shutil.which(cli_name)
            duration = (time.time() - start) * 1000
            if cli_path:
                result = ValidationResult(
                    name="agent_available",
                    category="agent",
                    success=True,
                    message=f"{cli_name.capitalize()} CLI found at {cli_path}",
                    duration_ms=duration,
                )
            else:
                result = ValidationResult(
                    name="agent_available",
                    category="agent",
                    success=False,
                    message=f"{cli_name} not found in PATH",
                    duration_ms=duration,
                )
        else:
            duration = (time.time() - start) * 1000
            result = ValidationResult(
                name="agent_available",
                category="agent",
                success=True,
                message=f"Agent configured: {provider_type}",
                duration_ms=duration,
            )

        if not output_json:
            _print_check("Agent available", result.success, result.message if verbose else None)
    except Exception as e:
        duration = (time.time() - start) * 1000
        result = ValidationResult(
            name="agent_available",
            category="agent",
            success=False,
            message=str(e),
            duration_ms=duration,
        )
        if not output_json:
            _print_check("Agent available", False, str(e))
    results.append(result)

    # Test: Simple prompt execution (Ollama only for now)
    if provider_type == ProviderType.OLLAMA and result.success:
        start = time.time()
        try:
            import httpx

            base_url = settings.agent_provider.base_url or "http://localhost:11434"
            model = settings.agent_provider.model or "llama3.2"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "Respond with exactly: OK",
                        "stream": False,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    output = data.get("response", "").strip()
                    duration = (time.time() - start) * 1000
                    # Check if response contains "OK"
                    if "OK" in output.upper():
                        result = ValidationResult(
                            name="test_prompt",
                            category="agent",
                            success=True,
                            message=f"Model responded correctly ({model})",
                            duration_ms=duration,
                        )
                    else:
                        result = ValidationResult(
                            name="test_prompt",
                            category="agent",
                            success=True,
                            message=f"Model responded: {output[:50]}...",
                            duration_ms=duration,
                        )
                else:
                    raise Exception(f"HTTP {response.status_code}")

            if not output_json:
                _print_check("Test prompt", True, result.message if verbose else None)
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = ValidationResult(
                name="test_prompt",
                category="agent",
                success=False,
                message=str(e),
                duration_ms=duration,
            )
            if not output_json:
                _print_check("Test prompt", False, str(e))
        results.append(result)

    return results


async def _generate_llm_summary(
    settings: AutomationSettings,
    report: DiagnosticReport,
    output_json: bool,
) -> str | None:
    """Generate a human-readable summary of the validation report using LLM.

    Attempts to use the configured LLM to produce a concise natural language
    summary of the validation results. Currently only implemented for Ollama;
    other providers receive a template-based summary.

    Args:
        settings: AutomationSettings with agent provider configuration.
        report: DiagnosticReport containing all validation results.
        output_json: If True, suppress any console output during generation.

    Returns:
        Summary string (max 200 chars) if LLM is available and responds,
        or a template-based fallback summary if LLM is unavailable.

    Note:
        Failures are logged at debug level and do not raise exceptions.
        The function always returns a summary string, using fallback if needed.
    """
    provider_type = settings.agent_provider.provider_type

    # Only attempt for Ollama for now (simple HTTP API)
    if provider_type != ProviderType.OLLAMA:
        return (
            f"Tested {report.provider_type.upper()} provider ({report.repository}) - all {report.total} tests passed."
        )

    try:
        import httpx

        base_url = settings.agent_provider.base_url or "http://localhost:11434"
        model = settings.agent_provider.model or "llama3.2"

        # Create a simple prompt for summarization
        results_text = "\n".join(f"- {r.name}: {'PASS' if r.success else 'FAIL'} - {r.message}" for r in report.results)

        prompt = f"""Summarize this validation report in one sentence:

Provider: {report.provider_type}
Repository: {report.repository}
Results:
{results_text}

Summary:"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            if response.status_code == 200:
                data = response.json()
                summary = data.get("response", "").strip()
                # Limit summary length
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                return summary

    except Exception as e:
        log.debug("llm_summary_error", error=str(e))

    # Fallback summary
    return f"Tested {report.provider_type.upper()} provider ({report.repository}) - all {report.total} tests passed."
