"""CLI command for processing issue comment events."""

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.engine.stages.comment_response import CommentContext, CommentResponseStage
from repo_sapiens.engine.state_manager import StateManager
from repo_sapiens.enums import AgentType, ProviderType
from repo_sapiens.providers.base import AgentProvider
from repo_sapiens.providers.copilot import CopilotProvider
from repo_sapiens.providers.external_agent import ExternalAgentProvider
from repo_sapiens.providers.factory import create_git_provider
from repo_sapiens.providers.openai_compatible import OpenAICompatibleProvider

log = structlog.get_logger(__name__)


@click.command(name="process-comment")
@click.option(
    "--issue",
    type=int,
    required=True,
    help="Issue number where the comment was made",
)
@click.option(
    "--comment-id",
    type=int,
    required=True,
    help="Comment ID",
)
@click.option(
    "--comment-author",
    required=True,
    help="Username of the comment author",
)
@click.option(
    "--comment-body",
    required=True,
    help="Body of the comment",
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
    help="Analyze comment without executing actions",
)
@click.pass_context
def process_comment_command(
    ctx: click.Context,
    issue: int,
    comment_id: int,
    comment_author: str,
    comment_body: str,
    source: str | None,
    dry_run: bool,
) -> None:
    """Process an issue comment event from CI/CD.

    This command is designed to be called from Gitea Actions, GitHub Actions,
    or GitLab CI when an issue comment is created that matches trigger keywords.

    Examples:

        # From Gitea Actions workflow
        sapiens process-comment \\
            --issue 42 \\
            --comment-id 123 \\
            --comment-author "developer" \\
            --comment-body "@sapiens please add the bug label"

        # Dry run to test without executing
        sapiens process-comment \\
            --issue 42 \\
            --comment-id 123 \\
            --comment-author "developer" \\
            --comment-body "@sapiens close this as duplicate" \\
            --dry-run
    """
    settings = ctx.obj.get("settings")
    if not settings:
        click.echo("Error: Configuration required.", err=True)
        sys.exit(1)

    context = CommentContext(
        issue_number=issue,
        comment_id=comment_id,
        comment_author=comment_author,
        comment_body=comment_body,
    )

    try:
        result = asyncio.run(
            _process_comment_event(
                settings=settings,
                context=context,
                source=source,
                dry_run=dry_run,
            )
        )

        if result.get("success"):
            if result.get("skipped"):
                click.echo(f"Comment skipped: {result.get('reason')}")
            else:
                click.echo("Comment processed successfully")
                if result.get("actions_executed"):
                    for action in result["actions_executed"]:
                        click.echo(f"  - {action['type']}: {action['value']}")
            sys.exit(0)
        else:
            click.echo(f"Error: {result.get('error')}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        log.error("process_comment_error", exc_info=True)
        sys.exit(1)


async def _process_comment_event(
    settings: AutomationSettings,
    context: CommentContext,
    source: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Process a comment event.

    Args:
        settings: Automation settings
        context: Comment context
        source: Event source (gitea/github/gitlab)
        dry_run: If True, analyze without executing actions

    Returns:
        Result dictionary
    """
    log.info(
        "processing_comment_event",
        issue=context.issue_number,
        comment_id=context.comment_id,
        author=context.comment_author,
        dry_run=dry_run,
    )

    # Create providers
    git = create_git_provider(settings)
    await git.connect()  # type: ignore[attr-defined]

    # Get the issue
    issue = await git.get_issue(context.issue_number)

    if dry_run:
        # Just check if comment would trigger processing
        from repo_sapiens.config.triggers import CommentTriggerConfig

        config = CommentTriggerConfig()
        if hasattr(settings, "automation") and settings.automation:
            config = settings.automation.comment_triggers

        # Check for bot signature
        if config.ignore_bot_comments and config.bot_signature in context.comment_body:
            click.echo("Comment would be skipped: Bot comment detected")
            return {"success": True, "skipped": True, "reason": "Bot comment", "dry_run": True}

        # Check for keywords
        body_lower = context.comment_body.lower()
        has_keyword = any(kw.lower() in body_lower for kw in config.keywords)

        if not has_keyword:
            click.echo("Comment would be skipped: No trigger keyword")
            return {"success": True, "skipped": True, "reason": "No trigger keyword", "dry_run": True}

        click.echo(f"Comment would be processed for issue #{issue.number}: {issue.title}")
        click.echo(f"Keywords matched: {[kw for kw in config.keywords if kw.lower() in body_lower]}")
        click.echo(f"Allowed actions: {[a.value for a in config.allowed_actions]}")
        return {"success": True, "dry_run": True}

    # Create agent provider
    agent = _create_agent_provider(settings)
    await agent.connect()  # type: ignore[attr-defined]

    state = StateManager(settings.state_dir)

    # Create the stage and process
    stage = CommentResponseStage(git, agent, state, settings)
    result = await stage.process_comment(issue, context)

    return result


def _create_agent_provider(settings: AutomationSettings) -> AgentProvider:
    """Create the appropriate agent provider."""
    from repo_sapiens.utils.interactive import InteractiveQAHandler

    # Create a QA handler (non-interactive in CI)
    qa_handler = InteractiveQAHandler(None, poll_interval=30)
    provider_type = settings.agent_provider.provider_type

    if provider_type == ProviderType.OLLAMA:
        from repo_sapiens.providers.ollama import OllamaProvider

        return OllamaProvider(
            base_url=settings.agent_provider.base_url or "http://localhost:11434",
            model=settings.agent_provider.model,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )

    # Copilot with copilot-api proxy (unofficial)
    if provider_type == ProviderType.COPILOT_LOCAL and settings.agent_provider.copilot_config:
        return CopilotProvider(
            copilot_config=settings.agent_provider.copilot_config,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
        )

    # OpenAI-compatible API (OpenRouter, vLLM, etc.)
    if provider_type == ProviderType.OPENAI_COMPATIBLE:
        api_key = None
        if settings.agent_provider.api_key:
            api_key = settings.agent_provider.api_key.get_secret_value()
        return OpenAICompatibleProvider(
            base_url=settings.agent_provider.base_url or "http://localhost:8000/v1",
            model=settings.agent_provider.model,
            api_key=api_key,
            working_dir=str(Path.cwd()),
            qa_handler=qa_handler,
            strip_thinking_tags=settings.agent_provider.strip_thinking_tags,
        )

    # External agent (Claude, Goose, or Copilot)
    if not provider_type.is_external_cli:
        raise ValueError(f"Unsupported provider type: {provider_type}")

    agent_type = provider_type.to_agent_type()
    if agent_type is None:
        raise ValueError(f"Cannot determine agent type for provider: {provider_type}")

    goose_config = None
    if agent_type == AgentType.GOOSE and settings.agent_provider.goose_config:
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
