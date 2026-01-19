"""CLI commands for MCP (Model Context Protocol) server management.

This module provides the ``sapiens mcp`` command group for listing, configuring,
and testing MCP servers that extend AI agent capabilities with external tools.

Commands:
    list: Display available MCP servers from the registry
    status: Show configuration status of enabled servers
    configure: Generate agent-specific MCP configuration files
    install: Install Python-based MCP server packages
    test: Test an MCP server connection by listing its tools

Example:
    List available servers::

        $ sapiens mcp list

    Generate Claude configuration::

        $ sapiens mcp configure --agent claude

    Test a server::

        $ sapiens mcp test fetch
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog

from repo_sapiens.mcp import (
    MCP_REGISTRY,
    AgentType,
    MCPManager,
    get_python_native_servers,
    get_servers_by_category,
)

if TYPE_CHECKING:
    from repo_sapiens.config.mcp import MCPConfig

log = structlog.get_logger(__name__)


@click.group(name="mcp")
def mcp_group() -> None:
    """Manage MCP (Model Context Protocol) servers.

    MCP servers provide extended tool capabilities to AI agents, enabling
    integrations with GitHub, Jira, Linear, and other services.

    Examples:
        sapiens mcp list
        sapiens mcp status
        sapiens mcp configure --agent claude
        sapiens mcp test github
    """
    pass


@mcp_group.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
@click.option(
    "--category",
    type=click.Choice(["ticket", "development", "search"]),
    help="Filter by category",
)
def list_servers(verbose: bool, category: str | None) -> None:
    """List available MCP servers from the registry."""
    click.echo("Available MCP Servers\n")

    if category:
        by_category = get_servers_by_category()
        servers = {name: MCP_REGISTRY[name] for name in by_category.get(category, [])}
    else:
        servers = MCP_REGISTRY

    for name, spec in sorted(servers.items()):
        tags = []
        if spec.python_native:
            tags.append("python-native")
        if spec.official:
            tags.append("official")
        tags_str = f"[{', '.join(tags)}]" if tags else ""

        click.echo(f"  {name:16} - {spec.description} ({spec.install_type}) {tags_str}")

        if verbose:
            if spec.required_env:
                click.echo(f"                   Requires: {', '.join(spec.required_env)}")
            if spec.url:
                click.echo(f"                   URL: {spec.url}")


@mcp_group.command("status")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.pass_context
def status(ctx: click.Context, config: str | None) -> None:
    """Show status of configured MCP servers."""
    # Try to get config from context or load from file
    settings = ctx.obj.get("settings") if ctx.obj else None

    if settings is None and config:
        from repo_sapiens.config.settings import AutomationSettings

        try:
            settings = AutomationSettings.from_yaml(config)
        except Exception as e:
            click.echo(f"Error loading config: {e}", err=True)
            raise SystemExit(1)

    if settings is None:
        # Check default path
        default_path = Path(".sapiens/config.yaml")
        if default_path.exists():
            from repo_sapiens.config.settings import AutomationSettings

            try:
                settings = AutomationSettings.from_yaml(str(default_path))
            except Exception as e:
                click.echo(f"Error loading config: {e}", err=True)
                raise SystemExit(1)

    if settings is None:
        click.echo("No configuration found. Run 'sapiens init' first or specify --config.")
        raise SystemExit(1)

    mcp_config = settings.mcp
    if not mcp_config.enabled:
        click.echo("MCP is disabled in configuration.")
        return

    click.echo("Configured MCP Servers\n")

    for server_cfg in mcp_config.servers:
        spec = MCP_REGISTRY.get(server_cfg.name)

        if not server_cfg.enabled:
            click.echo(f"  {server_cfg.name:16} [DISABLED]")
            continue

        if spec is None:
            click.echo(f"  {server_cfg.name:16} [UNKNOWN] Not in registry")
            continue

        # Check required env vars
        missing = []
        for env_var in spec.required_env:
            # Check env mapping first
            mapped = server_cfg.env_mapping.get(env_var, env_var)
            if mapped.startswith("${") and mapped.endswith("}"):
                mapped = mapped[2:-1]
            if not os.environ.get(mapped):
                missing.append(env_var)

        if missing:
            click.echo(f"  {server_cfg.name:16} [MISSING] {', '.join(missing)}")
        else:
            click.echo(f"  {server_cfg.name:16} [OK]")


@mcp_group.command("configure")
@click.option(
    "--agent",
    type=click.Choice(["claude", "goose"]),
    required=True,
    help="Agent type to generate config for",
)
@click.option("--output", "-o", type=click.Path(), help="Output path (default: auto)")
@click.option("--profile", default="sapiens", help="Profile name for Goose config")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.pass_context
def configure(
    ctx: click.Context,
    agent: str,
    output: str | None,
    profile: str,
    config: str | None,
) -> None:
    """Generate MCP configuration for a specific agent."""
    click.echo(f"Generating MCP Configuration for {agent.upper()}\n")

    # Load settings
    settings = ctx.obj.get("settings") if ctx.obj else None

    if settings is None:
        config_path = config or ".sapiens/config.yaml"
        if not Path(config_path).exists():
            click.echo(f"Configuration file not found: {config_path}", err=True)
            raise SystemExit(1)

        from repo_sapiens.config.settings import AutomationSettings

        try:
            settings = AutomationSettings.from_yaml(config_path)
        except Exception as e:
            click.echo(f"Configuration error: {e}", err=True)
            raise SystemExit(1)

    mcp_config = settings.mcp
    if not mcp_config.enabled:
        click.echo("MCP is disabled in configuration. Enable it first.")
        raise SystemExit(1)

    if not mcp_config.servers:
        click.echo("No MCP servers configured. Add servers to mcp.servers in config.")
        raise SystemExit(1)

    # Determine working directory
    working_dir = Path(output).parent if output else Path.cwd()

    # Create manager and generate config
    manager = MCPManager(mcp_config, working_dir)

    try:
        agent_type = AgentType.CLAUDE if agent == "claude" else AgentType.GOOSE

        if agent_type == AgentType.CLAUDE:
            config_path = manager._generate_claude_config()
        else:
            config_path = manager._generate_goose_config(profile=profile)

        click.echo(f"Generated: {config_path}")
        click.echo(f"Servers: {len(mcp_config.get_enabled_servers())}")
        click.echo("\nConfiguration generated successfully.")

    except Exception as e:
        click.echo(f"Error generating config: {e}", err=True)
        raise SystemExit(1)


@mcp_group.command("install")
@click.option("--server", "-s", multiple=True, help="Specific server(s) to install")
@click.option("--python-only", is_flag=True, help="Only install Python-native servers")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.pass_context
def install(
    ctx: click.Context,
    server: tuple[str, ...],
    python_only: bool,
    config: str | None,
) -> None:
    """Install configured MCP server packages."""
    click.echo("Installing MCP Servers\n")

    # Determine which servers to install
    if server:
        servers_to_install = list(server)
    else:
        # Load from config
        settings = ctx.obj.get("settings") if ctx.obj else None
        if settings is None:
            config_path = config or ".sapiens/config.yaml"
            if Path(config_path).exists():
                from repo_sapiens.config.settings import AutomationSettings

                try:
                    settings = AutomationSettings.from_yaml(config_path)
                except Exception:
                    pass

        if settings and settings.mcp.enabled:
            servers_to_install = [s.name for s in settings.mcp.get_enabled_servers()]
        else:
            # Install all Python-native servers
            servers_to_install = list(get_python_native_servers().keys())

    if python_only:
        python_servers = get_python_native_servers()
        servers_to_install = [s for s in servers_to_install if s in python_servers]

    for name in servers_to_install:
        spec = MCP_REGISTRY.get(name)
        if not spec:
            click.echo(f"  {name}: Unknown server, skipping")
            continue

        if spec.install_type == "pip":
            click.echo(f"  {name}: Installing {spec.package}...")
            try:
                import subprocess

                result = subprocess.run(
                    ["uv", "pip", "install", spec.package],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    click.echo(f"  {name}: Installed successfully")
                else:
                    click.echo(f"  {name}: Failed - {result.stderr}")
            except Exception as e:
                click.echo(f"  {name}: Error - {e}")
        elif spec.install_type == "npm":
            click.echo(f"  {name}: npm package (installed via npx at runtime)")
        elif spec.install_type == "remote":
            click.echo(f"  {name}: Remote server (no installation needed)")
        else:
            click.echo(f"  {name}: {spec.install_type} (skipped)")


@mcp_group.command("test")
@click.argument("server_name")
@click.option("--timeout", default=30, help="Timeout in seconds")
def test_server(server_name: str, timeout: int) -> None:
    """Test an MCP server connection."""
    spec = MCP_REGISTRY.get(server_name)
    if not spec:
        click.echo(f"Unknown server: {server_name}")
        click.echo(f"Available: {', '.join(MCP_REGISTRY.keys())}")
        raise SystemExit(1)

    click.echo(f"Testing MCP Server: {server_name}\n")

    # Check required env vars
    missing = [var for var in spec.required_env if not os.environ.get(var)]
    if missing:
        click.echo(f"Missing environment variables: {', '.join(missing)}")
        raise SystemExit(1)

    async def _test() -> None:
        from repo_sapiens.config.mcp import MCPConfig, MCPServerConfig

        config = MCPConfig(servers=[MCPServerConfig(name=server_name)])
        manager = MCPManager(config, Path.cwd())

        try:
            click.echo("  Starting server...")
            await manager._start_stdio_servers()

            clients = manager.get_stdio_clients()
            if server_name not in clients:
                click.echo("  Failed: Server did not start")
                return

            client = clients[server_name]
            click.echo("  Server running")

            click.echo("  Listing tools...")
            tools = await client.list_tools()
            click.echo(f"  Found {len(tools)} tools:")
            for tool in tools[:5]:  # Show first 5
                click.echo(f"    - {tool.get('name', 'unnamed')}")
            if len(tools) > 5:
                click.echo(f"    ... and {len(tools) - 5} more")

            click.echo(f"\n{server_name} is working correctly.")

        except Exception as e:
            click.echo(f"  Error: {e}")
            raise SystemExit(1)
        finally:
            await manager.teardown()

    asyncio.run(_test())
