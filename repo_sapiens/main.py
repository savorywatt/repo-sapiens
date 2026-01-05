"""CLI entry point for automation system."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
import structlog

from repo_sapiens.cli.credentials import credentials_group
from repo_sapiens.cli.init import init_command
from repo_sapiens.cli.update import update_command
from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.orchestrator import WorkflowOrchestrator
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.exceptions import ConfigurationError, RepoSapiensError
from repo_sapiens.providers.base import AgentProvider
from repo_sapiens.providers.external_agent import ExternalAgentProvider
from repo_sapiens.providers.factory import create_git_provider
from repo_sapiens.utils.interactive import InteractiveQAHandler
from repo_sapiens.utils.logging_config import configure_logging

log = structlog.get_logger(__name__)


@click.group()
@click.option(
    "--config",
    default="repo_sapiens/config/automation_config.yaml",
    help="Path to configuration file",
)
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def cli(ctx: click.Context, config: str, log_level: str) -> None:
    """repo-sapiens: Intelligent repository automation CLI."""
    # Configure logging
    configure_logging(log_level)

    # Skip config loading for commands that don't need it
    # (init creates the config, credentials manages credentials, react is standalone,
    # update only checks workflow templates)
    commands_without_config = ["init", "credentials", "react", "update"]
    if ctx.invoked_subcommand in commands_without_config:
        ctx.obj = {"settings": None}
        return

    # Load configuration for other commands
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Error: Configuration file not found: {config}", err=True)
        sys.exit(1)

    try:
        settings = AutomationSettings.from_yaml(str(config_path))
    except ConfigurationError as e:
        click.echo(f"Error: {e.message}", err=True)
        log.debug("config_error", exc_info=True)
        sys.exit(1)
    except FileNotFoundError as e:
        raise ConfigurationError(f"Configuration file not found: {config}") from e
    except Exception as e:
        click.echo(f"Unexpected error loading configuration: {e}", err=True)
        log.error("config_error_unexpected", exc_info=True)
        sys.exit(1)

    ctx.obj = {"settings": settings}


@cli.command()
@click.option("--issue", type=int, required=True, help="Issue number to process")
@click.pass_context
def process_issue(ctx: click.Context, issue: int) -> None:
    """Process a single issue manually."""
    try:
        settings = ctx.obj["settings"]
        asyncio.run(_process_single_issue(settings, issue))
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        log.debug("process_issue_error", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        log.error("process_issue_unexpected", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option("--tag", help="Process issues with specific tag")
@click.pass_context
def process_all(ctx: click.Context, tag: str | None) -> None:
    """Process all issues with optional tag filter."""
    try:
        settings = ctx.obj["settings"]
        asyncio.run(_process_all_issues(settings, tag))
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        log.debug("process_all_error", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        log.error("process_all_unexpected", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to process")
@click.pass_context
def process_plan(ctx: click.Context, plan_id: str) -> None:
    """Process entire plan end-to-end."""
    try:
        settings = ctx.obj["settings"]
        asyncio.run(_process_plan(settings, plan_id))
    except RepoSapiensError as e:
        click.echo(f"Error: {e.message}", err=True)
        log.debug("process_plan_error", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        log.error("process_plan_unexpected", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Polling interval in seconds (default: 60)",
)
@click.pass_context
def daemon(ctx: click.Context, interval: int) -> None:
    """Run in daemon mode, polling for new issues."""
    settings = ctx.obj["settings"]
    asyncio.run(_daemon_mode(settings, interval))


@cli.command()
@click.pass_context
def list_plans(ctx: click.Context) -> None:
    """List all active plans."""
    settings = ctx.obj["settings"]
    asyncio.run(_list_active_plans(settings))


@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to show")
@click.pass_context
def show_plan(ctx: click.Context, plan_id: str) -> None:
    """Show detailed plan status."""
    settings = ctx.obj["settings"]
    asyncio.run(_show_plan_status(settings, plan_id))


@cli.command()
@click.option(
    "--max-age-hours", default=24, type=int, help="Max age in hours before considered stale"
)
@click.pass_context
def check_stale(ctx: click.Context, max_age_hours: int) -> None:
    """Check for stale workflows that haven't been updated recently."""
    settings = ctx.obj["settings"]
    asyncio.run(_check_stale_workflows(settings, max_age_hours))


@cli.command()
@click.pass_context
def health_check(ctx: click.Context) -> None:
    """Generate health check report for the automation system."""
    settings = ctx.obj["settings"]
    asyncio.run(_generate_health_report(settings))


@cli.command()
@click.option("--since-hours", default=24, type=int, help="Check failures since N hours ago")
@click.pass_context
def check_failures(ctx: click.Context, since_hours: int) -> None:
    """Check for workflow failures in the specified time period."""
    settings = ctx.obj["settings"]
    asyncio.run(_check_workflow_failures(settings, since_hours))


@cli.command()
@click.argument("task", required=False)
@click.option("--model", default="qwen3:latest", help="Model to use")
@click.option(
    "--backend",
    default="ollama",
    type=click.Choice(["ollama", "openai"]),
    help="LLM backend: ollama or openai-compatible (vLLM, etc.)",
)
@click.option("--base-url", default=None, help="Backend server URL (default: auto-detected)")
@click.option("--api-key", default=None, help="API key for OpenAI-compatible backends")
@click.option("--max-iterations", default=10, type=int, help="Max ReAct iterations")
@click.option("--working-dir", default=".", help="Working directory for file operations")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed trajectory")
@click.option("--repl", is_flag=True, help="Start interactive REPL mode")
def react(
    task: str | None,
    model: str,
    backend: str,
    base_url: str | None,
    api_key: str | None,
    max_iterations: int,
    working_dir: str,
    verbose: bool,
    repl: bool,
) -> None:
    """Run a task using the ReAct agent.

    The ReAct agent reasons step-by-step and uses tools (read/write files,
    run commands) to complete the task. Supports both Ollama and OpenAI-compatible
    backends (vLLM, LMStudio, etc.).

    Examples:
        sapiens react "Create a hello.py file that prints Hello World"
        sapiens react --repl  # Start interactive mode
        sapiens react --backend openai --base-url http://localhost:8000/v1 "task"
    """
    from repo_sapiens.agents.react import ReActAgentProvider, ReActConfig
    from repo_sapiens.models.domain import Task as DomainTask

    if not task and not repl:
        click.echo("Error: Either provide a TASK or use --repl for interactive mode", err=True)
        sys.exit(1)

    async def execute_single_task(agent: ReActAgentProvider, task_text: str) -> bool:
        """Execute a single task and display results. Returns success status."""
        domain_task = DomainTask(
            id="cli-task",
            prompt_issue_id=0,
            title=task_text,
            description=task_text,
        )

        result = await agent.execute_task(domain_task, {})

        if verbose:
            click.echo("\n--- Trajectory ---")
            for step in agent.get_trajectory():
                click.echo(f"\nStep {step.iteration}:")
                click.echo(f"  THOUGHT: {step.thought[:100]}...")
                click.echo(f"  ACTION: {step.action}")
                click.echo(f"  INPUT: {step.action_input}")
                obs_preview = step.observation[:100].replace("\n", " ")
                click.echo(f"  OBSERVATION: {obs_preview}...")

        click.echo("\n--- Result ---")
        if result.success:
            click.echo("Status: SUCCESS")
            if result.output:
                click.echo(f"\nAnswer:\n{result.output}")
        else:
            click.echo(f"Status: FAILED - {result.error}")

        if result.files_changed:
            click.echo(f"\nFiles changed: {', '.join(result.files_changed)}")

        return result.success

    async def run_repl(agent: ReActAgentProvider) -> None:
        """Run interactive REPL loop."""
        # Fetch available models
        available_models = await agent.list_models()

        click.echo("\n" + "=" * 60)
        click.echo("ReAct Agent REPL")
        click.echo("=" * 60)
        click.echo(f"Model: {agent.config.model}")
        click.echo(f"Backend: {agent.config.backend} @ {agent.backend.base_url}")
        click.echo(f"Working directory: {Path(working_dir).resolve()}")
        if available_models:
            click.echo(f"Available models: {', '.join(available_models[:5])}")
            if len(available_models) > 5:
                click.echo(f"  ... and {len(available_models) - 5} more (use /models to list all)")
        click.echo("\nCommands:")
        click.echo("  Type a task to execute it")
        click.echo("  /help          - Show this help")
        click.echo("  /models        - List available models")
        click.echo("  /model <name>  - Switch to a different model")
        click.echo("  /pwd           - Show working directory")
        click.echo("  /verbose       - Toggle verbose mode")
        click.echo("  /clear         - Clear screen")
        click.echo("  /quit          - Exit REPL")
        click.echo("=" * 60 + "\n")

        nonlocal verbose
        task_count = 0

        while True:
            try:
                user_input = click.prompt(
                    click.style("react", fg="cyan") + click.style("> ", fg="white"),
                    prompt_suffix="",
                ).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1] if len(parts) > 1 else None

                    if cmd in ("/quit", "/exit", "/q"):
                        click.echo("Goodbye!")
                        break
                    elif cmd == "/help":
                        click.echo(
                            "\nCommands: /help, /models, /model <name>, "
                            "/pwd, /verbose, /clear, /quit"
                        )
                        click.echo("Or type any task for the agent to execute.\n")
                    elif cmd == "/models":
                        models = await agent.list_models()
                        if models:
                            click.echo("\nAvailable models:")
                            for m in models:
                                marker = " *" if m == agent.config.model else ""
                                click.echo(f"  {m}{marker}")
                            click.echo()
                        else:
                            click.echo("No models found. Is Ollama running?")
                    elif cmd == "/model":
                        if arg:
                            models = await agent.list_models()
                            # Find matching model (partial match)
                            match = next((m for m in models if arg in m), None)
                            if match:
                                agent.set_model(match)
                                click.echo(f"Switched to model: {match}")
                            else:
                                click.echo(f"Model not found: {arg}")
                                click.echo(f"Available: {', '.join(models[:5])}")
                        else:
                            click.echo(f"Current model: {agent.config.model}")
                    elif cmd == "/pwd":
                        click.echo(f"Working directory: {Path(working_dir).resolve()}")
                    elif cmd == "/verbose":
                        verbose = not verbose
                        click.echo(f"Verbose mode: {'ON' if verbose else 'OFF'}")
                    elif cmd == "/clear":
                        click.clear()
                    else:
                        click.echo(f"Unknown command: {user_input}")
                    continue

                # Execute task
                task_count += 1
                click.echo(f"\n[Task #{task_count}] {user_input}\n")
                await execute_single_task(agent, user_input)
                click.echo()

            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!")
                break

    async def run() -> None:
        config = ReActConfig(
            model=model,
            backend=backend,
            base_url=base_url,
            api_key=api_key,
            max_iterations=max_iterations,
        )
        agent = ReActAgentProvider(working_dir=working_dir, config=config)

        click.echo(f"Starting ReAct agent with model: {model}")
        click.echo(f"Backend: {backend}" + (f" @ {base_url}" if base_url else " (default URL)"))
        click.echo(f"Working directory: {Path(working_dir).resolve()}")

        async with agent:
            try:
                await agent.connect()
            except RuntimeError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

            if repl:
                await run_repl(agent)
            else:
                click.echo(f"Task: {task}\n")
                await execute_single_task(agent, task)  # type: ignore[arg-type]

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        log.error("react_error", exc_info=True)
        sys.exit(1)


# Add credentials management command group
cli.add_command(credentials_group)

# Add init command
cli.add_command(init_command)

# Add update command
cli.add_command(update_command)


async def _create_orchestrator(settings: AutomationSettings) -> WorkflowOrchestrator:
    """Create and initialize orchestrator.

    Args:
        settings: Automation settings

    Returns:
        Initialized WorkflowOrchestrator
    """
    # Initialize Git provider (Gitea or GitHub) using factory
    git = create_git_provider(settings)

    # Initialize interactive Q&A handler
    qa_handler = InteractiveQAHandler(git, poll_interval=30)

    # Initialize agent provider based on configuration
    agent: AgentProvider
    if settings.agent_provider.provider_type == "ollama":
        from repo_sapiens.providers.ollama import OllamaProvider

        base_url = settings.agent_provider.base_url or "http://localhost:11434"
        agent = OllamaProvider(
            base_url=base_url,
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )
    elif settings.agent_provider.provider_type == "openai-compatible":
        from repo_sapiens.providers.openai_compatible import OpenAICompatibleProvider

        base_url = settings.agent_provider.base_url or "http://localhost:8000/v1"
        # Resolve API key if it's a credential reference
        api_key = None
        if settings.agent_provider.api_key:
            api_key = settings.agent_provider.api_key.get_secret_value()

        agent = OpenAICompatibleProvider(
            base_url=base_url,
            model=settings.agent_provider.model,
            api_key=api_key,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )
    else:
        # Use external agent provider (claude or goose CLI)
        agent_type = "claude" if "claude" in settings.agent_provider.provider_type else "goose"

        # Extract Goose config if using Goose
        goose_config = None
        if agent_type == "goose" and settings.agent_provider.goose_config:
            goose_config = {
                "toolkit": settings.agent_provider.goose_config.toolkit,
                "temperature": settings.agent_provider.goose_config.temperature,
                "max_tokens": settings.agent_provider.goose_config.max_tokens,
                "llm_provider": settings.agent_provider.goose_config.llm_provider,
            }

        agent = ExternalAgentProvider(
            agent_type=agent_type,
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
            goose_config=goose_config,
        )

    state = StateManager(settings.state_dir)

    # Connect providers
    await git.connect()  # type: ignore[attr-defined]
    await agent.connect()

    # Pass qa_handler to orchestrator
    orchestrator = WorkflowOrchestrator(settings, git, agent, state)
    orchestrator.qa_handler = qa_handler  # type: ignore[attr-defined]

    return orchestrator


async def _process_single_issue(settings: AutomationSettings, issue_number: int) -> None:
    """Process a single issue.

    Args:
        settings: Automation settings
        issue_number: Issue number to process
    """
    log.info("processing_single_issue", issue=issue_number)

    orchestrator = await _create_orchestrator(settings)

    # Get issue
    issue = await orchestrator.git.get_issue(issue_number)

    # Process issue
    await orchestrator.process_issue(issue)

    click.echo(f"✅ Issue #{issue_number} processed successfully")


async def _process_all_issues(
    settings: AutomationSettings,
    tag: str | None,
) -> None:
    """Process all issues.

    Args:
        settings: Automation settings
        tag: Optional tag filter
    """
    log.info("processing_all_issues", tag=tag)

    orchestrator = await _create_orchestrator(settings)

    await orchestrator.process_all_issues(tag)

    click.echo("✅ All issues processed")


async def _process_plan(settings: AutomationSettings, plan_id: str) -> None:
    """Process entire plan.

    Args:
        settings: Automation settings
        plan_id: Plan identifier
    """
    log.info("processing_plan", plan_id=plan_id)

    orchestrator = await _create_orchestrator(settings)

    await orchestrator.process_plan(plan_id)

    click.echo(f"✅ Plan {plan_id} processed successfully")


async def _daemon_mode(settings: AutomationSettings, interval: int) -> None:
    """Run in daemon mode.

    Args:
        settings: Automation settings
        interval: Polling interval in seconds
    """
    log.info("daemon_mode_started", interval=interval)
    click.echo(f"Starting daemon mode (polling every {interval}s)")

    orchestrator = await _create_orchestrator(settings)

    while True:
        try:
            click.echo("Polling for issues...")
            await orchestrator.process_all_issues()
            click.echo(f"Poll complete. Waiting {interval}s...")

        except KeyboardInterrupt:
            click.echo("\nShutting down daemon...")
            break

        except RepoSapiensError as e:
            log.error("daemon_error", error=e.message, exc_info=True)
            click.echo(f"Error: {e.message}", err=True)

        except Exception as e:
            log.error("daemon_error_unexpected", error=str(e), exc_info=True)
            click.echo(f"Unexpected error: {e}", err=True)

        await asyncio.sleep(interval)


async def _list_active_plans(settings: AutomationSettings) -> None:
    """List active plans.

    Args:
        settings: Automation settings
    """
    state = StateManager(settings.state_dir)
    active_plans = await state.get_active_plans()

    if not active_plans:
        click.echo("No active plans found.")
        return

    click.echo(f"Active Plans ({len(active_plans)}):\n")

    for plan_id in active_plans:
        state_data = await state.load_state(plan_id)
        status = state_data.get("status", "unknown")
        click.echo(f"  • Plan {plan_id}: {status}")


async def _show_plan_status(settings: AutomationSettings, plan_id: str) -> None:
    """Show detailed plan status.

    Args:
        settings: Automation settings
        plan_id: Plan identifier
    """
    state = StateManager(settings.state_dir)

    try:
        state_data = await state.load_state(plan_id)
    except FileNotFoundError:
        click.echo(f"Plan {plan_id} not found.", err=True)
        return

    click.echo(f"\n📋 Plan {plan_id} Status\n")
    click.echo(f"Overall Status: {state_data.get('status', 'unknown')}")
    click.echo(f"Created: {state_data.get('created_at', 'unknown')}")
    click.echo(f"Updated: {state_data.get('updated_at', 'unknown')}\n")

    # Show stages
    click.echo("Stages:")
    for stage_name, stage_data in state_data.get("stages", {}).items():
        status = stage_data.get("status", "unknown")
        emoji = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
        click.echo(f"  {emoji} {stage_name}: {status}")

    # Show tasks
    tasks = state_data.get("tasks", {})
    if tasks:
        click.echo(f"\nTasks ({len(tasks)}):")
        for task_id, task_data in tasks.items():
            status = task_data.get("status", "unknown")
            emoji = "✅" if status == "completed" else "⏳" if status == "pending" else "🔄"
            click.echo(f"  {emoji} {task_id}: {status}")


async def _check_stale_workflows(settings: AutomationSettings, max_age_hours: int) -> None:
    """Check for stale workflows that haven't been updated recently.

    Args:
        settings: Automation settings
        max_age_hours: Maximum age in hours before workflow is considered stale
    """
    state = StateManager(settings.state_dir)
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)
    stale_plans = []

    # Check all state files
    for state_file in state.state_dir.glob("*.json"):
        plan_id = state_file.stem
        try:
            state_data = await state.load_state(plan_id)

            # Skip completed or failed workflows
            if state_data.get("status") in ["completed", "failed"]:
                continue

            # Parse updated_at timestamp
            updated_at_str = state_data.get("updated_at", "")
            if updated_at_str:
                # Handle ISO format with timezone
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at < cutoff_time:
                    stale_plans.append(
                        {
                            "plan_id": plan_id,
                            "status": state_data.get("status", "unknown"),
                            "updated_at": updated_at_str,
                            "age_hours": (datetime.now(UTC) - updated_at).total_seconds() / 3600,
                        }
                    )
        except Exception as e:
            log.warning("failed_to_check_plan", plan_id=plan_id, error=str(e))

    if not stale_plans:
        click.echo(f"No stale workflows found (threshold: {max_age_hours} hours)")
        return

    click.echo(f"⚠️  Found {len(stale_plans)} stale workflow(s):\n")
    for plan in stale_plans:
        click.echo(f"  • Plan {plan['plan_id']}")
        click.echo(f"    Status: {plan['status']}")
        click.echo(f"    Last updated: {plan['updated_at']}")
        click.echo(f"    Age: {plan['age_hours']:.1f} hours")
        click.echo()

    # Exit with non-zero status if stale workflows found
    sys.exit(1)


async def _generate_health_report(settings: AutomationSettings) -> None:
    """Generate health check report for the automation system.

    Args:
        settings: Automation settings
    """
    state = StateManager(settings.state_dir)
    now = datetime.now(UTC)

    # Collect statistics
    total_plans = 0
    active_plans = 0
    completed_plans = 0
    failed_plans = 0
    pending_plans = 0

    plan_details = []

    for state_file in state.state_dir.glob("*.json"):
        plan_id = state_file.stem
        try:
            state_data = await state.load_state(plan_id)
            total_plans += 1

            status = state_data.get("status", "unknown")
            if status == "completed":
                completed_plans += 1
            elif status == "failed":
                failed_plans += 1
            elif status in ["in_progress", "pending"]:
                active_plans += 1
                if status == "pending":
                    pending_plans += 1

            plan_details.append(
                {
                    "id": plan_id,
                    "status": status,
                    "updated_at": state_data.get("updated_at", "unknown"),
                }
            )
        except Exception as e:
            log.warning("failed_to_load_plan", plan_id=plan_id, error=str(e))

    # Generate report
    click.echo("# Automation System Health Report")
    click.echo(f"Generated: {now.isoformat()}")
    click.echo()
    click.echo("## Summary")
    click.echo(f"- Total Plans: {total_plans}")
    click.echo(f"- Active Plans: {active_plans}")
    click.echo(f"- Completed Plans: {completed_plans}")
    click.echo(f"- Failed Plans: {failed_plans}")
    click.echo(f"- Pending Plans: {pending_plans}")
    click.echo()
    click.echo("## Configuration")
    click.echo(f"- State Directory: {settings.state_dir}")
    click.echo(f"- Git Provider: {settings.git_provider.provider_type}")
    click.echo(f"- Agent Provider: {settings.agent_provider.provider_type}")
    click.echo()
    click.echo("## Provider Status")
    click.echo("- Git Provider: Configuration loaded ✓")
    click.echo("- Agent Provider: Configuration loaded ✓")
    click.echo("- State Manager: Operational ✓")
    click.echo()

    if failed_plans > 0:
        click.echo("## Failed Plans")
        for plan in plan_details:
            if plan["status"] == "failed":
                click.echo(f"- {plan['id']} (updated: {plan['updated_at']})")
        click.echo()

    if active_plans > 0:
        click.echo("## Active Plans")
        for plan in plan_details:
            if plan["status"] in ["in_progress", "pending"]:
                click.echo(f"- {plan['id']}: {plan['status']} (updated: {plan['updated_at']})")


async def _check_workflow_failures(settings: AutomationSettings, since_hours: int) -> None:
    """Check for workflow failures in the specified time period.

    Args:
        settings: Automation settings
        since_hours: Check failures since N hours ago
    """
    state = StateManager(settings.state_dir)
    cutoff_time = datetime.now(UTC) - timedelta(hours=since_hours)
    recent_failures = []

    for state_file in state.state_dir.glob("*.json"):
        plan_id = state_file.stem
        try:
            state_data = await state.load_state(plan_id)

            # Check if this is a failed workflow
            if state_data.get("status") != "failed":
                continue

            # Check if it failed within the time window
            updated_at_str = state_data.get("updated_at", "")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at >= cutoff_time:
                    # Collect failure details from stages
                    failed_stages = []
                    for stage_name, stage_data in state_data.get("stages", {}).items():
                        if stage_data.get("status") == "failed":
                            failed_stages.append(stage_name)

                    recent_failures.append(
                        {
                            "plan_id": plan_id,
                            "updated_at": updated_at_str,
                            "failed_stages": failed_stages,
                            "metadata": state_data.get("metadata", {}),
                        }
                    )
        except Exception as e:
            log.warning("failed_to_check_plan", plan_id=plan_id, error=str(e))

    if not recent_failures:
        click.echo(f"No workflow failures found in the last {since_hours} hours")
        return

    click.echo(f"❌ Found {len(recent_failures)} failure(s) in the last {since_hours} hours:\n")
    for failure in recent_failures:
        click.echo(f"  • Plan {failure['plan_id']}")
        click.echo(f"    Failed at: {failure['updated_at']}")
        if failure["failed_stages"]:
            click.echo(f"    Failed stages: {', '.join(failure['failed_stages'])}")
        if failure["metadata"].get("error"):
            click.echo(f"    Error: {failure['metadata']['error']}")
        click.echo()

    # Exit with non-zero status if failures found
    sys.exit(1)


if __name__ == "__main__":
    cli()
