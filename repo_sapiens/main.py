"""CLI entry point for automation system."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from repo_sapiens.cli.credentials import credentials_group
from repo_sapiens.cli.health import health_check
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
    default=".sapiens/config.yaml",
    help="Path to configuration file",
)
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def cli(ctx: click.Context, config: str, log_level: str) -> None:
    """repo-sapiens: Intelligent repository automation CLI."""
    # Configure logging
    configure_logging(log_level)

    # Skip config loading for commands that don't need it
    # (init creates the config, credentials manages credentials, update checks templates,
    # health-check handles its own config loading)
    commands_without_config = ["init", "credentials", "update", "health-check"]
    if ctx.invoked_subcommand in commands_without_config:
        ctx.obj = {"settings": None}
        return

    # Task command can optionally use config but doesn't require it
    if ctx.invoked_subcommand == "task":
        config_path = Path(config)
        if config_path.exists():
            try:
                settings = AutomationSettings.from_yaml(str(config_path))
                ctx.obj = {"settings": settings}
                return
            except Exception:
                pass  # Fall through to use defaults
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


@cli.command(name="task")
@click.argument("prompt", required=False)
@click.option("--model", default=None, help="Model to use (default: from config or qwen3:8b)")
@click.option("--ollama-url", default=None, help="Ollama server URL (default: from config)")
@click.option("--max-iterations", default=10, type=int, help="Max ReAct iterations")
@click.option("--working-dir", default=".", help="Working directory for file operations")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed trajectory")
@click.option("--repl", is_flag=True, help="Start interactive REPL mode")
@click.pass_context
def task_command(
    ctx: click.Context,
    prompt: str | None,
    model: str | None,
    ollama_url: str | None,
    max_iterations: int,
    working_dir: str,
    verbose: bool,
    repl: bool,
) -> None:
    """Run a task using the ReAct agent with Ollama/vLLM.

    The ReAct agent reasons step-by-step and uses tools (read/write files,
    run commands) to complete the task.

    Settings are read from the config file (--config). CLI options override config.

    Examples:
        sapiens task "Create a hello.py file that prints Hello World"
        sapiens task --repl  # Start interactive mode
    """
    from repo_sapiens.agents.react import ReActAgentProvider, ReActConfig
    from repo_sapiens.models.domain import Task as DomainTask

    if not prompt and not repl:
        click.echo("Error: Either provide a PROMPT or use --repl for interactive mode", err=True)
        sys.exit(1)

    # Get settings from config (may be None if config doesn't exist)
    settings = ctx.obj.get("settings") if ctx.obj else None

    # Resolve model and URL from config or defaults
    if model is None:
        if settings and settings.agent_provider:
            model = settings.agent_provider.model or "qwen3:8b"
        else:
            model = "qwen3:8b"

    if ollama_url is None:
        if settings and settings.agent_provider and settings.agent_provider.base_url:
            ollama_url = settings.agent_provider.base_url
        else:
            ollama_url = "http://localhost:11434"

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
        click.echo(f"Ollama: {ollama_url}")
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
                    click.style("task", fg="cyan") + click.style("> ", fg="white"),
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
                        click.echo("\nCommands: /help, /models, /model <name>, /pwd, /verbose, /clear, /quit")
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

            except (EOFError, KeyboardInterrupt, click.Abort):
                click.echo("\nGoodbye!")
                break

    async def run() -> None:
        config = ReActConfig(model=model, max_iterations=max_iterations, ollama_url=ollama_url)
        agent = ReActAgentProvider(working_dir=working_dir, config=config)

        click.echo(f"Starting ReAct agent with model: {model}")
        click.echo(f"Ollama server: {ollama_url}")
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
                click.echo(f"Task: {prompt}\n")
                await execute_single_task(agent, prompt)  # type: ignore[arg-type]

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        log.error("react_error", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("task", required=False)
@click.option("--timeout", default=300, type=int, help="Max execution time in seconds")
@click.option("--working-dir", default=".", help="Working directory for execution")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def run(
    ctx: click.Context,
    task: str | None,
    timeout: int,
    working_dir: str,
    verbose: bool,
) -> None:
    """Run a task using the configured AI agent.

    Dispatches to the agent configured in .sapiens/config.yaml:
    - claude-local: Uses Claude CLI (claude -p "task")
    - goose-local: Uses Goose CLI (goose session start)
    - ollama/openai-compatible: Uses builtin ReAct agent with local model
    - openai/anthropic: Uses builtin ReAct agent with API

    Task can be provided as argument or via stdin for long prompts.

    Examples:
        sapiens run "Summarize the codebase structure"
        sapiens run "Fix the bug in auth.py" --timeout 600
        echo "Long task prompt..." | sapiens run
        cat task.txt | sapiens run
    """
    # Support stdin for long prompts
    if not task:
        if not sys.stdin.isatty():
            task = sys.stdin.read().strip()
        if not task:
            click.echo("Error: No task provided. Pass as argument or via stdin.", err=True)
            sys.exit(1)

    settings = ctx.obj.get("settings") if ctx.obj else None

    if not settings:
        click.echo(
            "Error: Configuration required. Run 'sapiens init' first or check your config file.",
            err=True,
        )
        sys.exit(1)

    provider_type = settings.agent_provider.provider_type

    try:
        asyncio.run(_run_task(settings, task, timeout, working_dir, verbose))
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        log.error("run_task_error", provider=provider_type, exc_info=True)
        sys.exit(1)


async def _run_task(
    settings: AutomationSettings,
    task: str,
    timeout: int,
    working_dir: str,
    verbose: bool,
) -> None:
    """Execute task using the configured agent provider.

    Args:
        settings: Automation settings with agent configuration
        task: Task prompt to execute
        timeout: Maximum execution time in seconds
        working_dir: Working directory for file operations
        verbose: Whether to show detailed output
    """
    provider_type = settings.agent_provider.provider_type

    if provider_type == "claude-local":
        await _run_claude_cli(task, timeout, working_dir)
    elif provider_type == "goose-local":
        await _run_goose_cli(task, timeout, working_dir, settings)
    elif provider_type in ("ollama", "openai-compatible"):
        await _run_react_agent(task, timeout, working_dir, verbose, settings)
    else:
        # API-based providers (openai, anthropic, claude-api, goose-api)
        await _run_react_agent(task, timeout, working_dir, verbose, settings)


async def _run_claude_cli(task: str, timeout: int, working_dir: str) -> None:
    """Run task using Claude CLI."""
    import shutil

    claude_path = shutil.which("claude")
    if not claude_path:
        raise RuntimeError("Claude CLI not found. Install it or choose a different agent provider.")

    click.echo("Running task with Claude CLI...")
    click.echo(f"Working directory: {Path(working_dir).resolve()}")
    click.echo("-" * 40)

    # Stream output directly to terminal
    process = await asyncio.create_subprocess_exec(
        claude_path,
        "-p",
        task,
        cwd=working_dir,
        stdout=None,  # Inherit stdout for streaming
        stderr=None,  # Inherit stderr for streaming
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"Task timed out after {timeout} seconds")

    if process.returncode != 0:
        raise RuntimeError(f"Claude CLI exited with code {process.returncode}")


async def _run_goose_cli(
    task: str,
    timeout: int,
    working_dir: str,
    settings: AutomationSettings,
) -> None:
    """Run task using Goose CLI."""
    import shutil

    goose_path = shutil.which("goose")
    if not goose_path:
        raise RuntimeError("Goose CLI not found. Install it or choose a different agent provider.")

    click.echo("Running task with Goose CLI...")
    click.echo(f"Working directory: {Path(working_dir).resolve()}")
    click.echo("-" * 40)

    # Build command with optional config
    cmd = [goose_path, "session", "start", "--prompt", task]

    # Add provider if configured
    if settings.agent_provider.goose_config:
        if settings.agent_provider.goose_config.llm_provider:
            cmd.extend(["--provider", settings.agent_provider.goose_config.llm_provider])

    # Stream output directly to terminal
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=working_dir,
        stdout=None,
        stderr=None,
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"Task timed out after {timeout} seconds")

    if process.returncode != 0:
        raise RuntimeError(f"Goose CLI exited with code {process.returncode}")


async def _run_react_agent(
    task: str,
    timeout: int,
    working_dir: str,
    verbose: bool,
    settings: AutomationSettings,
) -> None:
    """Run task using builtin ReAct agent."""
    from repo_sapiens.agents.react import ReActAgentProvider, ReActConfig
    from repo_sapiens.models.domain import Task as DomainTask

    # Get model and URL from settings
    model = settings.agent_provider.model or "qwen3:8b"
    base_url = settings.agent_provider.base_url or "http://localhost:11434"

    click.echo("Running task with ReAct agent...")
    click.echo(f"Model: {model}")
    click.echo(f"Backend: {base_url}")
    click.echo(f"Working directory: {Path(working_dir).resolve()}")
    click.echo("-" * 40)

    # Calculate max iterations from timeout (rough estimate: 30s per iteration)
    max_iterations = max(3, timeout // 30)

    config = ReActConfig(
        model=model,
        max_iterations=max_iterations,
        ollama_url=base_url,
    )
    agent = ReActAgentProvider(working_dir=working_dir, config=config)

    async with agent:
        try:
            await agent.connect()
        except RuntimeError as e:
            raise RuntimeError(f"Failed to connect to LLM backend: {e}")

        domain_task = DomainTask(
            id="run-task",
            prompt_issue_id=0,
            title=task,
            description=task,
        )

        result = await agent.execute_task(domain_task, {})

        if verbose:
            click.echo("\n--- Trajectory ---")
            for step in agent.get_trajectory():
                click.echo(f"\nStep {step.iteration}:")
                click.echo(f"  THOUGHT: {step.thought[:200]}...")
                click.echo(f"  ACTION: {step.action}")
                click.echo(f"  INPUT: {step.action_input}")
                obs_preview = step.observation[:150].replace("\n", " ")
                click.echo(f"  OBSERVATION: {obs_preview}...")

        click.echo("\n--- Result ---")
        if result.success:
            click.echo("Status: SUCCESS")
            if result.output:
                click.echo(f"\n{result.output}")
        else:
            click.echo(f"Status: FAILED - {result.error}")

        if result.files_changed:
            click.echo(f"\nFiles changed: {', '.join(result.files_changed)}")

        if not result.success:
            raise RuntimeError(result.error or "Task failed")


# Add credentials management command group
cli.add_command(credentials_group)

# Add health-check command
cli.add_command(health_check)

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


if __name__ == "__main__":
    cli()
