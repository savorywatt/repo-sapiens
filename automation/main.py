"""CLI entry point for automation system."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from automation.config.settings import AutomationSettings
from automation.engine.orchestrator import WorkflowOrchestrator
from automation.engine.state_manager import StateManager
from automation.providers.external_agent import ExternalAgentProvider
from automation.providers.gitea_rest import GiteaRestProvider
from automation.utils.interactive import InteractiveQAHandler
from automation.utils.logging_config import configure_logging

log = structlog.get_logger(__name__)


@click.group()
@click.option(
    "--config",
    default="automation/config/automation_config.yaml",
    help="Path to configuration file",
)
@click.option("--log-level", default="INFO", help="Logging level")
@click.pass_context
def cli(ctx: click.Context, config: str, log_level: str) -> None:
    """Gitea automation system CLI."""
    # Configure logging
    configure_logging(log_level)

    # Load configuration
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Error: Configuration file not found: {config}", err=True)
        sys.exit(1)

    try:
        settings = AutomationSettings.from_yaml(str(config_path))
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)

    ctx.obj = {"settings": settings}


@cli.command()
@click.option("--issue", type=int, required=True, help="Issue number to process")
@click.pass_context
def process_issue(ctx: click.Context, issue: int) -> None:
    """Process a single issue manually."""
    settings = ctx.obj["settings"]
    asyncio.run(_process_single_issue(settings, issue))


@cli.command()
@click.option("--tag", help="Process issues with specific tag")
@click.pass_context
def process_all(ctx: click.Context, tag: str) -> None:
    """Process all issues with optional tag filter."""
    settings = ctx.obj["settings"]
    asyncio.run(_process_all_issues(settings, tag))


@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to process")
@click.pass_context
def process_plan(ctx: click.Context, plan_id: str) -> None:
    """Process entire plan end-to-end."""
    settings = ctx.obj["settings"]
    asyncio.run(_process_plan(settings, plan_id))


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


async def _create_orchestrator(settings: AutomationSettings) -> WorkflowOrchestrator:
    """Create and initialize orchestrator.

    Args:
        settings: Automation settings

    Returns:
        Initialized WorkflowOrchestrator
    """
    # Initialize Gitea REST API provider
    git = GiteaRestProvider(
        base_url=str(settings.git_provider.base_url),
        token=settings.git_provider.api_token.get_secret_value(),
        owner=settings.repository.owner,
        repo=settings.repository.name,
    )

    # Initialize interactive Q&A handler
    qa_handler = InteractiveQAHandler(git, poll_interval=30)

    # Initialize agent provider based on configuration
    if settings.agent_provider.provider_type == "ollama":
        from automation.providers.ollama import OllamaProvider
        agent = OllamaProvider(
            base_url=settings.agent_provider.base_url,
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )
    else:
        # Use external agent provider (claude or goose CLI)
        agent_type = "claude" if "claude" in settings.agent_provider.provider_type else "goose"
        agent = ExternalAgentProvider(
            agent_type=agent_type,
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )

    state = StateManager(settings.state_dir)

    # Connect providers
    await git.connect()
    await agent.connect()

    # Pass qa_handler to orchestrator
    orchestrator = WorkflowOrchestrator(settings, git, agent, state)
    orchestrator.qa_handler = qa_handler

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
    click.echo(f"🤖 Starting daemon mode (polling every {interval}s)")

    orchestrator = await _create_orchestrator(settings)

    while True:
        try:
            click.echo(f"🔄 Polling for issues...")
            await orchestrator.process_all_issues()
            click.echo(f"✅ Poll complete. Waiting {interval}s...")

        except KeyboardInterrupt:
            click.echo("\n👋 Shutting down daemon...")
            break

        except Exception as e:
            log.error("daemon_error", error=str(e), exc_info=True)
            click.echo(f"❌ Error: {e}", err=True)

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
