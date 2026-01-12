"""CLI command for updating repo-sapiens workflow templates."""

import re
import sys
from pathlib import Path
from typing import Any

import click
import structlog

from repo_sapiens.git.discovery import GitDiscovery
from repo_sapiens.git.exceptions import GitDiscoveryError

log = structlog.get_logger(__name__)

# Template version pattern
VERSION_PATTERN = re.compile(r"^#\s*@version:\s*(\d+\.\d+\.\d+)")
NAME_PATTERN = re.compile(r"^#\s*@name:\s*(.+)")
TEMPLATE_MARKER = "# @repo-sapiens-template"


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a version string into a tuple for comparison."""
    parts = version_str.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def extract_template_info(file_path: Path) -> dict[str, Any] | None:
    """Extract template metadata from a file.

    Returns dict with 'name' and 'version' if file is a repo-sapiens template,
    None otherwise.
    """
    try:
        content = file_path.read_text()
        lines = content.split("\n")[:10]  # Only check first 10 lines

        # Check if this is a repo-sapiens template
        if not any(TEMPLATE_MARKER in line for line in lines):
            return None

        info: dict[str, Any] = {"path": file_path}

        for line in lines:
            version_match = VERSION_PATTERN.match(line)
            if version_match:
                info["version"] = version_match.group(1)

            name_match = NAME_PATTERN.match(line)
            if name_match:
                info["name"] = name_match.group(1).strip()

        if "name" in info and "version" in info:
            return info

        return None
    except Exception:
        return None


def find_installed_templates(repo_path: Path, provider_type: str | None) -> list[dict[str, Any]]:
    """Find all installed repo-sapiens templates in the repository."""
    if provider_type == "github":
        workflows_dir = repo_path / ".github" / "workflows"
    elif provider_type == "gitlab":
        # GitLab uses .gitlab-ci.yml at root, check for it and any includes
        workflows_dir = repo_path
    else:
        workflows_dir = repo_path / ".gitea" / "workflows"

    if not workflows_dir.exists():
        return []

    templates = []

    if provider_type == "gitlab":
        # Check root .gitlab-ci.yml
        gitlab_ci = repo_path / ".gitlab-ci.yml"
        if gitlab_ci.exists():
            info = extract_template_info(gitlab_ci)
            if info:
                templates.append(info)
        # Also check .gitlab directory for includes
        gitlab_dir = repo_path / ".gitlab"
        if gitlab_dir.exists():
            for yaml_file in gitlab_dir.glob("**/*.yaml"):
                info = extract_template_info(yaml_file)
                if info:
                    templates.append(info)
            for yml_file in gitlab_dir.glob("**/*.yml"):
                info = extract_template_info(yml_file)
                if info:
                    templates.append(info)
    else:
        # Scan sapiens/ subdirectory for core workflows
        sapiens_dir = workflows_dir / "sapiens"
        if sapiens_dir.exists():
            for yaml_file in sapiens_dir.glob("*.yaml"):
                info = extract_template_info(yaml_file)
                if info:
                    templates.append(info)
            for yml_file in sapiens_dir.glob("*.yml"):
                info = extract_template_info(yml_file)
                if info:
                    templates.append(info)

        # Scan sapiens/recipes/ subdirectory
        recipes_dir = workflows_dir / "sapiens" / "recipes"
        if recipes_dir.exists():
            for yaml_file in recipes_dir.glob("*.yaml"):
                info = extract_template_info(yaml_file)
                if info:
                    templates.append(info)
            for yml_file in recipes_dir.glob("*.yml"):
                info = extract_template_info(yml_file)
                if info:
                    templates.append(info)

        # Also scan root for backward compatibility (legacy flat structure)
        for yaml_file in workflows_dir.glob("*.yaml"):
            info = extract_template_info(yaml_file)
            if info:
                templates.append(info)
        for yml_file in workflows_dir.glob("*.yml"):
            info = extract_template_info(yml_file)
            if info:
                templates.append(info)

    return templates


def find_available_templates(
    templates_dir: Path, provider_type: str | None
) -> list[dict[str, Any]]:
    """Find all available templates in the package."""
    if provider_type == "github":
        provider_dir = templates_dir / "github"
    elif provider_type == "gitlab":
        provider_dir = templates_dir / "gitlab"
    else:
        provider_dir = templates_dir / "gitea"

    if not provider_dir.exists():
        return []

    templates = []

    # Scan sapiens subdirectory for core templates
    sapiens_dir = provider_dir / "sapiens"
    if sapiens_dir.exists():
        for yaml_file in sapiens_dir.glob("*.yaml"):
            info = extract_template_info(yaml_file)
            if info:
                templates.append(info)

    # Scan sapiens/recipes subdirectory
    recipes_dir = provider_dir / "sapiens" / "recipes"
    if recipes_dir.exists():
        for yaml_file in recipes_dir.glob("*.yaml"):
            info = extract_template_info(yaml_file)
            if info:
                templates.append(info)

    return templates


def find_templates_dir() -> Path | None:
    """Find the workflow templates directory."""
    import repo_sapiens

    package_dir = Path(repo_sapiens.__file__).parent.parent
    templates_dir = package_dir / "templates" / "workflows"

    if templates_dir.exists():
        return templates_dir

    # Try relative to current working directory (for development)
    cwd_templates = Path.cwd() / "templates" / "workflows"
    if cwd_templates.exists():
        return cwd_templates

    return None


def detect_legacy_structure(repo_path: Path, provider_type: str | None) -> bool:
    """Detect if repository uses old flat structure."""
    if provider_type == "github":
        old_location = repo_path / ".github" / "workflows" / "process-label.yaml"
        new_location = repo_path / ".github" / "workflows" / "sapiens" / "process-label.yaml"
    elif provider_type == "gitlab":
        return False  # GitLab doesn't use subdirectories
    else:
        old_location = repo_path / ".gitea" / "workflows" / "process-label.yaml"
        new_location = repo_path / ".gitea" / "workflows" / "sapiens" / "process-label.yaml"

    return old_location.exists() and not new_location.exists()


@click.command(name="update")
@click.option(
    "--repo-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Path to Git repository (default: current directory)",
)
@click.option(
    "--check-only",
    is_flag=True,
    help="Only check for updates, don't apply them",
)
@click.option(
    "--all",
    "update_all",
    is_flag=True,
    help="Update all templates without prompting",
)
def update_command(
    repo_path: Path,
    check_only: bool,
    update_all: bool,
) -> None:
    """Check for and apply updates to repo-sapiens workflow templates.

    This command scans your repository for installed repo-sapiens workflow
    templates and compares their versions against the latest available versions.

    Examples:

        # Check for available updates
        sapiens update --check-only

        # Interactively update templates
        sapiens update

        # Update all templates without prompting
        sapiens update --all
    """
    try:
        updater = TemplateUpdater(
            repo_path=repo_path,
            check_only=check_only,
            update_all=update_all,
        )
        updater.run()

    except GitDiscoveryError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        click.echo(
            click.style("Make sure you're in a Git repository.", fg="yellow"),
            err=True,
        )
        sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        log.error("update_error", exc_info=True)
        sys.exit(1)


class TemplateUpdater:
    """Handles template update workflow."""

    def __init__(
        self,
        repo_path: Path,
        check_only: bool,
        update_all: bool,
    ):
        self.repo_path = repo_path
        self.check_only = check_only
        self.update_all = update_all
        self.provider_type: str | None = None

    def run(self) -> None:
        """Run the update workflow."""
        click.echo(click.style("🔄 Checking for template updates", bold=True, fg="cyan"))
        click.echo()

        # Discover repository type
        self._discover_repository()

        # Check for legacy structure and offer migration
        if detect_legacy_structure(self.repo_path, self.provider_type):
            click.echo(click.style("⚠️  Legacy workflow structure detected", fg="yellow"))
            click.echo("Your workflows are in the old flat structure.")
            click.echo("New structure uses subdirectories:")
            click.echo("  - Core workflows: .gitea/workflows/sapiens/")
            click.echo("  - Recipe workflows: .gitea/workflows/sapiens/recipes/")
            click.echo()
            if click.confirm("Migrate to new structure?", default=True):
                self._migrate_to_subdirectories()
                click.echo(click.style("✓ Migration complete", fg="green"))
                click.echo()

        # Find templates directory
        templates_dir = find_templates_dir()
        if not templates_dir:
            click.echo(
                click.style("Error: Could not find repo-sapiens templates directory.", fg="red")
            )
            sys.exit(1)

        # Find installed templates
        installed = find_installed_templates(self.repo_path, self.provider_type)
        if not installed:
            click.echo("No repo-sapiens templates found in this repository.")
            click.echo()
            click.echo("Use 'sapiens init --setup-examples' to add example workflows.")
            return

        # Find available templates
        available = find_available_templates(templates_dir, self.provider_type)
        available_by_name = {t["name"]: t for t in available}

        # Compare versions
        updates_available = []
        up_to_date = []
        not_found = []

        for template in installed:
            name = template["name"]
            installed_version = template["version"]

            if name in available_by_name:
                latest = available_by_name[name]
                latest_version = latest["version"]

                installed_tuple = parse_version(installed_version)
                latest_tuple = parse_version(latest_version)

                if latest_tuple > installed_tuple:
                    updates_available.append(
                        {
                            "name": name,
                            "installed_version": installed_version,
                            "latest_version": latest_version,
                            "installed_path": template["path"],
                            "source_path": latest["path"],
                        }
                    )
                else:
                    up_to_date.append(template)
            else:
                not_found.append(template)

        # Report status
        self._report_status(updates_available, up_to_date, not_found)

        # Apply updates if not check-only
        if updates_available and not self.check_only:
            self._apply_updates(updates_available)

    def _discover_repository(self) -> None:
        """Discover Git repository configuration."""
        try:
            discovery = GitDiscovery(self.repo_path)
            self.provider_type = discovery.detect_provider_type()
            click.echo(f"   Provider: {self.provider_type.upper()}")
            click.echo()
        except GitDiscoveryError:
            # Default to checking workflow directories if we can't detect
            if (self.repo_path / ".github" / "workflows").exists():
                self.provider_type = "github"
            elif (self.repo_path / ".gitlab-ci.yml").exists():
                self.provider_type = "gitlab"
            elif (self.repo_path / ".gitea" / "workflows").exists():
                self.provider_type = "gitea"
            else:
                raise

    def _migrate_to_subdirectories(self) -> None:
        """Migrate workflows from flat to subdirectory structure."""
        # Determine directories
        if self.provider_type == "github":
            old_dir = self.repo_path / ".github" / "workflows"
        elif self.provider_type == "gitlab":
            return  # No migration needed for GitLab
        else:
            old_dir = self.repo_path / ".gitea" / "workflows"

        sapiens_dir = old_dir / "sapiens"
        recipes_dir = sapiens_dir / "recipes"  # Nested inside sapiens/
        sapiens_dir.mkdir(exist_ok=True)
        recipes_dir.mkdir(exist_ok=True)

        # Move core workflows
        core_patterns = ["automation-daemon.yaml", "process-label.yaml", "process-issue.yaml"]
        for yaml_file in old_dir.glob("*.yaml"):
            if yaml_file.name in core_patterns:
                yaml_file.rename(sapiens_dir / yaml_file.name)
                click.echo(f"  Moved {yaml_file.name} → sapiens/")
            elif any(pattern in yaml_file.name for pattern in ["weekly-", "daily-", "post-merge-"]):
                yaml_file.rename(recipes_dir / yaml_file.name)
                click.echo(f"  Moved {yaml_file.name} → sapiens/recipes/")

    def _report_status(
        self,
        updates_available: list[dict[str, Any]],
        up_to_date: list[dict[str, Any]],
        not_found: list[dict[str, Any]],
    ) -> None:
        """Report the status of installed templates."""
        if up_to_date:
            click.echo(click.style("✓ Up to date:", fg="green"))
            for template in up_to_date:
                click.echo(f"   {template['name']} (v{template['version']})")
            click.echo()

        if updates_available:
            click.echo(click.style("⬆ Updates available:", fg="yellow"))
            for update in updates_available:
                click.echo(
                    f"   {update['name']}: "
                    f"v{update['installed_version']} → v{update['latest_version']}"
                )
            click.echo()

        if not_found:
            click.echo(click.style("? Unknown templates (no matching source):", fg="blue"))
            for template in not_found:
                click.echo(f"   {template['name']} (v{template['version']})")
            click.echo()

        # Summary
        total = len(updates_available) + len(up_to_date) + len(not_found)
        click.echo(f"Found {total} installed template(s):")
        click.echo(f"   {len(up_to_date)} up to date")
        click.echo(f"   {len(updates_available)} with updates available")
        if not_found:
            click.echo(f"   {len(not_found)} unknown/custom")
        click.echo()

    def _apply_updates(self, updates_available: list[dict[str, Any]]) -> None:
        """Apply available updates."""
        click.echo(click.style("Applying updates...", bold=True))
        click.echo()

        updated_count = 0

        for update in updates_available:
            name = update["name"]
            installed_path = update["installed_path"]
            source_path = update["source_path"]

            click.echo(
                f"  {click.style(name, bold=True)}: "
                f"v{update['installed_version']} → v{update['latest_version']}"
            )

            if self.update_all:
                do_update = True
            else:
                do_update = click.confirm("    Update this template?", default=True)

            if do_update:
                # Read new content
                new_content = source_path.read_text()

                # Write to installed location
                installed_path.write_text(new_content)

                click.echo(click.style("    ✓ Updated", fg="green"))
                updated_count += 1
            else:
                click.echo("    ⏭ Skipped")

            click.echo()

        # Summary
        if updated_count > 0:
            click.echo(click.style(f"✓ Updated {updated_count} template(s)", bold=True, fg="green"))
            click.echo()
            click.echo("Remember to commit the updated workflow files:")
            if self.provider_type == "gitlab":
                click.echo("   git add .gitlab-ci.yml .gitlab/")
            elif self.provider_type == "github":
                click.echo("   git add .github/workflows/")
            else:
                click.echo("   git add .gitea/workflows/")
            click.echo("   git commit -m 'chore: Update repo-sapiens workflow templates'")
        else:
            click.echo("No templates were updated.")
