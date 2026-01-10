"""Migration utilities for daemon to native workflow transition."""

from pathlib import Path

import click
import structlog

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.config.triggers import AutomationConfig

log = structlog.get_logger(__name__)


@click.group(name="migrate")
def migrate_group():
    """Migration utilities for automation mode transitions.

    Commands for migrating from daemon-based to native CI/CD automation.
    """
    pass


@migrate_group.command(name="analyze")
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Output file for analysis report",
)
@click.pass_context
def analyze_migration(ctx: click.Context, output: str | None) -> None:
    """Analyze current setup and recommend migration path.

    Examines your current configuration and provides recommendations
    for migrating from daemon-based to native CI/CD automation.
    """
    settings: AutomationSettings | None = ctx.obj.get("settings")
    if not settings:
        click.echo("Error: Configuration required.", err=True)
        return

    report = []
    report.append("=" * 60)
    report.append("Migration Analysis Report")
    report.append("=" * 60)
    report.append("")

    # Check current mode
    automation_config = _get_automation_config(settings)
    mode = automation_config.mode.mode
    report.append(f"Current automation mode: {mode}")
    report.append(f"Native enabled: {automation_config.mode.native_enabled}")
    report.append(f"Daemon enabled: {automation_config.mode.daemon_enabled}")
    report.append("")

    # Analyze label triggers
    report.append("Label Triggers Configured:")
    for label, config in automation_config.label_triggers.items():
        report.append(f"  - {label} -> {config.handler}")
    if not automation_config.label_triggers:
        report.append("  (none)")
    report.append("")

    # Analyze schedule triggers
    report.append("Schedule Triggers Configured:")
    for schedule in automation_config.schedule_triggers:
        report.append(f"  - {schedule.cron} -> {schedule.handler}")
    if not automation_config.schedule_triggers:
        report.append("  (none)")
    report.append("")

    # Check for existing workflows
    provider = settings.git_provider.provider_type
    if provider == "github":
        workflow_dir = Path(".github/workflows")
    elif provider == "gitlab":
        workflow_dir = Path(".")  # .gitlab-ci.yml
    else:
        workflow_dir = Path(".gitea/workflows")

    report.append(f"Workflow directory: {workflow_dir}")
    if workflow_dir.exists():
        workflows = list(workflow_dir.glob("*.yaml")) + list(workflow_dir.glob("*.yml"))
        report.append(f"Existing workflows: {len(workflows)}")
        for w in workflows[:10]:
            report.append(f"  - {w.name}")
    else:
        report.append("Workflow directory does not exist")
    report.append("")

    # Recommendations
    report.append("=" * 60)
    report.append("Recommendations")
    report.append("=" * 60)
    report.append("")

    if mode == "daemon":
        report.append("1. Switch to hybrid mode to enable native triggers while")
        report.append("   keeping daemon as fallback:")
        report.append("   - Set automation.mode.mode: hybrid")
        report.append("   - Set automation.mode.native_enabled: true")
        report.append("")

    if not automation_config.label_triggers:
        report.append("2. Configure label triggers in your config.yaml:")
        report.append("   automation:")
        report.append("     label_triggers:")
        report.append('       "needs-planning":')
        report.append("         handler: proposal")
        report.append("         ai_enabled: true")
        report.append("")

    report.append("3. Generate native workflows:")
    report.append("   sapiens migrate generate")
    report.append("")

    report.append("4. Deploy and test:")
    report.append("   - Commit generated workflow files")
    report.append("   - Test with a sample label")
    report.append("   - Monitor workflow runs")
    report.append("")

    report.append("5. Once stable, disable daemon (optional):")
    report.append("   - Set automation.mode.daemon_enabled: false")
    report.append("")

    # Output report
    report_text = "\n".join(report)

    if output:
        Path(output).write_text(report_text)
        click.echo(f"Report written to: {output}")
    else:
        click.echo(report_text)


@migrate_group.command(name="generate")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing workflow files",
)
@click.pass_context
def generate_workflows(ctx: click.Context, dry_run: bool, force: bool) -> None:
    """Generate native CI/CD workflow files from configuration.

    Creates workflow files for your CI/CD platform based on the
    trigger configuration in your config.yaml.
    """
    settings: AutomationSettings | None = ctx.obj.get("settings")
    if not settings:
        click.echo("Error: Configuration required.", err=True)
        return

    # Import WorkflowGenerator (from Phase 3)
    try:
        from repo_sapiens.generators.workflow_generator import WorkflowGenerator
    except ImportError:
        click.echo(
            "Error: WorkflowGenerator not available. " "Ensure Phase 3 implementation is complete.",
            err=True,
        )
        return

    generator = WorkflowGenerator(settings, Path.cwd())
    automation_config = _get_automation_config(settings)

    if dry_run:
        click.echo("Dry run - would generate the following files:")
        click.echo("")

        # Check what would be generated
        if automation_config.label_triggers:
            provider = settings.git_provider.provider_type
            if provider == "github":
                click.echo("  .github/workflows/process-label.yaml")
            elif provider == "gitlab":
                click.echo("  .gitlab-ci.yml (process-label job)")
            else:
                click.echo("  .gitea/workflows/process-label.yaml")

        for schedule in automation_config.schedule_triggers:
            filename = f"schedule-{schedule.handler.replace('/', '-')}.yaml"
            click.echo(f"  .../{filename}")

        return

    # Check for existing files
    if not force:
        provider = settings.git_provider.provider_type
        if provider == "github":
            existing = Path(".github/workflows/process-label.yaml")
        elif provider == "gitlab":
            existing = Path(".gitlab-ci.yml")
        else:
            existing = Path(".gitea/workflows/process-label.yaml")

        if existing.exists():
            click.echo(f"Workflow file already exists: {existing}")
            click.echo("Use --force to overwrite")
            return

    # Generate workflows
    generated = generator.generate_all()

    if generated:
        click.echo("Generated workflow files:")
        for path in generated:
            click.echo(f"  - {path}")
        click.echo("")
        click.echo("Next steps:")
        click.echo("  1. Review the generated files")
        click.echo("  2. Commit and push to your repository")
        click.echo("  3. Test by adding a configured label to an issue")
    else:
        click.echo("No workflows generated.")
        click.echo("Configure label_triggers or schedule_triggers in your config.yaml")


@migrate_group.command(name="validate")
@click.pass_context
def validate_setup(ctx: click.Context) -> None:
    """Validate native automation setup.

    Checks that all components are correctly configured for
    native CI/CD automation.
    """
    settings: AutomationSettings | None = ctx.obj.get("settings")
    if not settings:
        click.echo("Error: Configuration required.", err=True)
        return

    automation_config = _get_automation_config(settings)
    checks = []
    all_passed = True

    # Check 1: Native mode enabled
    if automation_config.mode.native_enabled:
        checks.append(("Native mode enabled", True, None))
    else:
        checks.append(("Native mode enabled", False, "Set automation.mode.native_enabled: true"))
        all_passed = False

    # Check 2: Label triggers configured
    if automation_config.label_triggers:
        checks.append(
            (
                "Label triggers configured",
                True,
                f"{len(automation_config.label_triggers)} triggers",
            )
        )
    else:
        checks.append(("Label triggers configured", False, "Add label_triggers to config"))
        all_passed = False

    # Check 3: Workflow file exists
    provider = settings.git_provider.provider_type
    if provider == "github":
        workflow_path = Path(".github/workflows/process-label.yaml")
    elif provider == "gitlab":
        workflow_path = Path(".gitlab-ci.yml")
    else:
        workflow_path = Path(".gitea/workflows/process-label.yaml")

    if workflow_path.exists():
        checks.append(("Workflow file exists", True, str(workflow_path)))
    else:
        checks.append(("Workflow file exists", False, "Run: sapiens migrate generate"))
        all_passed = False

    # Check 4: Required secrets documentation
    if provider == "github":
        checks.append(("Required secrets", True, "GITHUB_TOKEN (automatic)"))
    else:
        checks.append(("Required secrets", True, "SAPIENS_GITEA_TOKEN"))

    # Display results
    click.echo("Validation Results")
    click.echo("=" * 50)

    for name, passed, detail in checks:
        status = click.style("[PASS]", fg="green") if passed else click.style("[FAIL]", fg="red")
        click.echo(f"{status} {name}")
        if detail:
            click.echo(f"       {detail}")

    click.echo("")
    if all_passed:
        click.echo(click.style("All checks passed!", fg="green", bold=True))
    else:
        click.echo(click.style("Some checks failed. Address the issues above.", fg="yellow"))


def _get_automation_config(settings: AutomationSettings) -> AutomationConfig:
    """Get automation config from settings, handling backward compatibility.

    Args:
        settings: Automation settings

    Returns:
        AutomationConfig instance
    """
    # The automation field may not exist in older configs
    if hasattr(settings, "automation") and settings.automation is not None:
        return settings.automation
    # Return default config for backward compatibility
    return AutomationConfig()
