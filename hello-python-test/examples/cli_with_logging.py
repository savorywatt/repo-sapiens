"""Example: CLI application using structured logging with repo-sapiens.

This example demonstrates best practices for using structured logging in a CLI
application with Click.
"""

import click
from repo_sapiens import bind_context, clear_context, configure_logging, get_logger


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    help="Set logging level (default: INFO)",
)
@click.option(
    "--json-logs",
    is_flag=True,
    help="Output logs as JSON (for production)",
)
@click.pass_context
def cli(ctx: click.Context, log_level: str, json_logs: bool) -> None:
    """Intelligent repository automation tool with structured logging."""
    # Initialize logging
    configure_logging(level=log_level.upper(), json_logs=json_logs)

    logger = get_logger(__name__)
    logger.info("cli_startup", log_level=log_level, json_output=json_logs)

    # Store settings in context for use by subcommands
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["json_logs"] = json_logs


@cli.command()
@click.option("--issue", type=int, required=True, help="Issue ID to process")
@click.pass_context
def process_issue(ctx: click.Context, issue: int) -> None:
    """Process a single issue."""
    logger = get_logger(__name__)

    # Bind request-level context
    bind_context(issue_id=issue, operation="process_issue")

    logger.info("processing_started")

    try:
        logger.debug("fetching_issue", issue_id=issue)

        # Simulate fetching the issue
        if issue <= 0:
            raise ValueError(f"Invalid issue ID: {issue}")

        issue_data = {"id": issue, "title": f"Issue #{issue}", "status": "open"}
        logger.debug("issue_fetched", issue=issue_data)

        # Simulate processing
        logger.info("analyzing_issue", issue_id=issue)

        logger.debug("step_1_complete", step="analysis")
        logger.debug("step_2_complete", step="planning")
        logger.debug("step_3_complete", step="implementation")

        logger.info("processing_completed", issue_id=issue, status="success")
        click.echo(f"Successfully processed issue #{issue}")

    except ValueError as e:
        logger.error("invalid_input", error=str(e), issue_id=issue)
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        logger.error("processing_failed", issue_id=issue, error=str(e), exc_info=True)
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    finally:
        # Clean up context
        clear_context()


@cli.command()
@click.option("--count", type=int, default=10, help="Number of issues to process")
@click.option("--tag", type=str, help="Filter by tag")
@click.pass_context
def process_batch(ctx: click.Context, count: int, tag: str) -> None:
    """Process multiple issues in batch."""
    logger = get_logger(__name__)

    bind_context(operation="process_batch")

    logger.info("batch_processing_started", total_count=count, filter_tag=tag)

    try:
        processed = 0
        failed = 0

        for i in range(1, count + 1):
            try:
                bind_context(issue_number=i)
                logger.debug("processing_issue", iteration=i)

                # Simulate processing
                if i % 7 == 0:  # Simulate occasional failures
                    raise ValueError(f"Simulated failure for issue {i}")

                processed += 1
                logger.debug("issue_processed", issue_number=i)

            except Exception as e:
                failed += 1
                logger.warning("issue_skipped", issue_number=i, error=str(e))

        logger.info(
            "batch_processing_completed",
            total=count,
            processed=processed,
            failed=failed,
            success_rate=f"{(processed / count * 100):.1f}%",
        )

        click.echo(f"Batch processing complete: {processed}/{count} successful")

    except Exception as e:
        logger.error("batch_processing_failed", error=str(e), exc_info=True)
        click.echo(f"Batch processing failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        clear_context()


@cli.command()
@click.option("--repository", required=True, help="Repository name (owner/repo)")
@click.pass_context
def analyze_repo(ctx: click.Context, repository: str) -> None:
    """Analyze a repository."""
    logger = get_logger(__name__)

    bind_context(operation="analyze_repo", repository=repository)

    logger.info("analysis_started", repository=repository)

    try:
        parts = repository.split("/")
        if len(parts) != 2:
            raise ValueError(f"Repository must be in format 'owner/repo', got: {repository}")

        owner, repo_name = parts
        logger.debug("repository_validated", owner=owner, repo=repo_name)

        # Simulate analysis steps
        logger.debug("step_1_cloning", repository=repository)
        logger.debug("step_2_scanning", repository=repository, files_found=42)
        logger.debug("step_3_analyzing", repository=repository, issues_found=5)

        logger.info(
            "analysis_completed",
            repository=repository,
            status="success",
            issues_found=5,
        )

        click.echo(f"Analysis complete for {repository}: 5 issues found")

    except ValueError as e:
        logger.error("invalid_repository", error=str(e))
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        logger.error("analysis_failed", repository=repository, error=str(e), exc_info=True)
        click.echo(f"Analysis failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        clear_context()


@cli.command()
def status() -> None:
    """Show system status."""
    logger = get_logger(__name__)

    logger.info("status_check_started")

    try:
        logger.debug("checking_component", component="git_provider")
        logger.debug("checking_component", component="database")
        logger.debug("checking_component", component="cache")

        status_info = {
            "git": "OK",
            "database": "OK",
            "cache": "OK",
        }

        logger.info("status_check_completed", status=status_info, all_ok=True)

        click.echo("System Status:")
        for component, status_val in status_info.items():
            click.echo(f"  {component}: {status_val}")

    except Exception as e:
        logger.error("status_check_failed", error=str(e), exc_info=True)
        click.echo(f"Status check failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
