"""CLI command for processing label-triggered events."""

import asyncio
import json
import sys

import click
import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.event_classifier import EventClassifier, EventSource
from repo_sapiens.engine.label_router import LabelRouter
from repo_sapiens.engine.orchestrator import WorkflowOrchestrator
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.providers.base import AgentProvider
from repo_sapiens.providers.external_agent import ExternalAgentProvider
from repo_sapiens.providers.factory import create_git_provider

log = structlog.get_logger(__name__)


@click.command(name="process-label")
@click.option(
    "--event-type",
    required=True,
    help="Event type (e.g., 'issues.labeled')",
)
@click.option(
    "--event-data",
    required=False,
    help="JSON event payload (or pass via stdin)",
)
@click.option(
    "--label",
    required=False,
    help="Label name (shortcut for simple invocations)",
)
@click.option(
    "--issue",
    type=int,
    required=False,
    help="Issue number (shortcut for simple invocations)",
)
@click.option(
    "--source",
    type=click.Choice(["gitea", "github", "gitlab"]),
    default=None,
    help="Event source (auto-detected from config if not specified)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Classify event without executing handler",
)
@click.pass_context
def process_label_command(
    ctx: click.Context,
    event_type: str,
    event_data: str | None,
    label: str | None,
    issue: int | None,
    source: str | None,
    dry_run: bool,
) -> None:
    """Process a label-triggered event from CI/CD.

    This command is designed to be called from Gitea Actions, GitHub Actions,
    or GitLab CI when an issue or PR is labeled.

    Examples:

        # From Gitea Actions workflow
        sapiens process-label --event-type issues.labeled \\
            --label "needs-planning" --issue 42

        # With full event payload
        sapiens process-label --event-type issues.labeled \\
            --event-data '{"label": {"name": "sapiens/triage"}, "issue": {"number": 42}}'

        # Dry run to see classification
        sapiens process-label --event-type issues.labeled \\
            --label "sapiens/review/security" --issue 42 --dry-run
    """
    settings = ctx.obj.get("settings")
    if not settings:
        click.echo("Error: Configuration required.", err=True)
        sys.exit(1)

    # Parse event data
    if event_data:
        try:
            event_payload = json.loads(event_data)
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON in --event-data: {e}", err=True)
            sys.exit(1)
    elif not sys.stdin.isatty():
        # Read from stdin
        try:
            event_payload = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON from stdin: {e}", err=True)
            sys.exit(1)
    else:
        # Build minimal event payload from options
        event_payload = {}
        if label:
            event_payload["label"] = {"name": label}
        if issue:
            event_payload["issue"] = {"number": issue}

    # Determine source
    if source:
        event_source = EventSource(source)
    else:
        event_source = EventSource(settings.git_provider.provider_type)

    try:
        result = asyncio.run(
            _process_label_event(
                settings=settings,
                event_type=event_type,
                event_payload=event_payload,
                event_source=event_source,
                dry_run=dry_run,
            )
        )

        if result.get("success"):
            click.echo("Label event processed successfully")
            sys.exit(0)
        elif result.get("skipped"):
            click.echo(f"Event skipped: {result.get('reason')}")
            sys.exit(0)  # Not an error
        else:
            click.echo(f"Error: {result.get('error')}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        log.error("process_label_error", exc_info=True)
        sys.exit(1)


async def _process_label_event(
    settings: AutomationSettings,
    event_type: str,
    event_payload: dict,
    event_source: EventSource,
    dry_run: bool,
) -> dict:
    """Process a label event.

    Args:
        settings: Automation settings
        event_type: Event type string
        event_payload: Event payload dictionary
        event_source: Event source
        dry_run: If True, only classify without executing

    Returns:
        Result dictionary
    """
    # Classify the event
    classifier = EventClassifier(settings)
    classified = classifier.classify(event_type, event_payload, event_source)

    log.info(
        "event_classified",
        trigger_type=classified.trigger_type.value,
        handler=classified.handler,
        should_process=classified.should_process,
    )

    if dry_run:
        click.echo(f"Trigger type: {classified.trigger_type.value}")
        click.echo(f"Handler: {classified.handler or 'none'}")
        click.echo(f"Should process: {classified.should_process}")
        if classified.skip_reason:
            click.echo(f"Skip reason: {classified.skip_reason}")
        return {"success": True, "dry_run": True}

    if not classified.should_process:
        return {
            "success": False,
            "skipped": True,
            "reason": classified.skip_reason,
        }

    # Create providers and orchestrator
    git = create_git_provider(settings)
    await git.connect()

    # Create agent provider
    agent = _create_agent_provider(settings)
    await agent.connect()

    state = StateManager(settings.state_dir)
    orchestrator = WorkflowOrchestrator(settings, git, agent, state)

    # Route the event
    router = LabelRouter(settings, git, orchestrator)
    result = await router.route(classified)

    return result


def _create_agent_provider(settings: AutomationSettings) -> AgentProvider:
    """Create the appropriate agent provider."""
    from pathlib import Path

    from repo_sapiens.utils.interactive import InteractiveQAHandler

    # Create a QA handler (non-interactive in CI)
    qa_handler = InteractiveQAHandler(None, poll_interval=30)

    if settings.agent_provider.provider_type == "ollama":
        from repo_sapiens.providers.ollama import OllamaProvider

        return OllamaProvider(
            base_url=settings.agent_provider.base_url or "http://localhost:11434",
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )

    # External agent (Claude or Goose)
    agent_type = "claude" if "claude" in settings.agent_provider.provider_type else "goose"

    goose_config = None
    if agent_type == "goose" and settings.agent_provider.goose_config:
        goose_config = {
            "toolkit": settings.agent_provider.goose_config.toolkit,
            "temperature": settings.agent_provider.goose_config.temperature,
            "max_tokens": settings.agent_provider.goose_config.max_tokens,
            "llm_provider": settings.agent_provider.goose_config.llm_provider,
        }

    return ExternalAgentProvider(
        agent_type=agent_type,
        model=settings.agent_provider.model,
        working_dir=str(Path.cwd()),
        qa_handler=qa_handler,
        goose_config=goose_config,
    )
