"""GitHub Copilot provider using copilot-api proxy for AI inference.

WARNING: This integration uses an unofficial, reverse-engineered API.
- NOT endorsed or supported by GitHub
- May violate GitHub Terms of Service
- Could stop working at any time without notice
- Use at your own risk

The provider supports two deployment modes:
1. Managed proxy: Automatically starts/stops the copilot-api subprocess
2. External proxy: Connects to an existing copilot-api instance

Uses composition pattern with OpenAICompatibleProvider for API delegation.
"""

import asyncio
import contextlib
import os
import shutil
import signal
import time
from types import TracebackType
from typing import Any

import httpx
import structlog

from repo_sapiens.config.settings import CopilotConfig
from repo_sapiens.credentials import CredentialResolver
from repo_sapiens.models.domain import Issue, Plan, Review, Task, TaskResult
from repo_sapiens.providers.base import AgentProvider
from repo_sapiens.providers.openai_compatible import OpenAICompatibleProvider

log = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# Custom Exceptions
# -----------------------------------------------------------------------------


class CopilotError(Exception):
    """Base exception for Copilot provider errors."""

    pass


class CopilotAuthenticationError(CopilotError):
    """Raised when GitHub token is invalid or lacks Copilot access."""

    pass


class CopilotRateLimitError(CopilotError):
    """Raised when API rate limit is exceeded (HTTP 429)."""

    pass


class CopilotAbuseDetectedError(CopilotError):
    """Raised when GitHub detects potential abuse (HTTP 403 with abuse message)."""

    pass


class CopilotProxyError(CopilotError):
    """Raised when proxy lifecycle operations fail."""

    pass


# -----------------------------------------------------------------------------
# CopilotProvider Implementation
# -----------------------------------------------------------------------------


class CopilotProvider(AgentProvider):
    """Agent provider for GitHub Copilot via copilot-api proxy.

    WARNING: This uses an unofficial, reverse-engineered API. See module
    docstring for important disclaimers.

    Uses composition pattern: delegates API calls to OpenAICompatibleProvider.

    Example (managed proxy):
        >>> config = CopilotConfig(
        ...     github_token="@keyring:github/oauth_token",
        ...     manage_proxy=True,
        ...     proxy_port=4141,
        ... )
        >>> async with CopilotProvider(config) as provider:
        ...     plan = await provider.generate_plan(issue)

    Example (external proxy):
        >>> config = CopilotConfig(
        ...     github_token="@keyring:github/oauth_token",
        ...     manage_proxy=False,
        ...     proxy_url="http://localhost:4141/v1",
        ... )
        >>> async with CopilotProvider(config) as provider:
        ...     result = await provider.execute_task(task, context)
    """

    def __init__(
        self,
        copilot_config: CopilotConfig,
        working_dir: str | None = None,
        qa_handler: Any | None = None,
    ) -> None:
        """Initialize Copilot provider.

        Args:
            copilot_config: Copilot-specific configuration including token
                and proxy settings.
            working_dir: Working directory for file operations.
            qa_handler: Interactive Q&A handler for user prompts.
        """
        self.config = copilot_config
        self.working_dir = working_dir
        self.qa_handler = qa_handler

        # Proxy process management
        self._proxy_process: asyncio.subprocess.Process | None = None
        self._drain_task: asyncio.Task[None] | None = None

        # Delegated OpenAI-compatible client
        self._openai_client: OpenAICompatibleProvider | None = None

        # Rate limiting state
        self._last_request_time: float = 0.0

    async def connect(self) -> None:
        """Connect to Copilot API, optionally starting managed proxy.

        This method:
        1. Starts the copilot-api proxy if manage_proxy is True
        2. Waits for the proxy to become ready
        3. Resolves GitHub token from credential reference
        4. Creates and connects the OpenAI-compatible client

        Raises:
            CopilotProxyError: If proxy startup fails.
            CopilotAuthenticationError: If token is invalid.
        """
        # Start managed proxy if configured
        if self.config.manage_proxy:
            await self._start_proxy()
            await self._wait_for_proxy_ready()

        # Resolve GitHub token
        resolver = CredentialResolver()
        github_token = resolver.resolve(str(self.config.github_token))

        # Create OpenAI-compatible client with Copilot endpoint
        self._openai_client = OpenAICompatibleProvider(
            base_url=self.config.effective_url,
            model=self.config.model,
            api_key=github_token,
            working_dir=self.working_dir,
            qa_handler=self.qa_handler,
            timeout=300.0,
        )

        await self._openai_client.connect()

        log.info(
            "copilot_provider_connected",
            model=self.config.model,
            managed_proxy=self.config.manage_proxy,
            url=self.config.effective_url,
        )

    async def _start_proxy(self) -> None:
        """Start the copilot-api proxy subprocess.

        Uses npx to run the latest copilot-api package with the configured port.

        Raises:
            CopilotProxyError: If npx is not available or process fails to start.
        """
        # Verify npx is available
        npx_path = shutil.which("npx")
        if npx_path is None:
            raise CopilotProxyError("npx is not available. Install Node.js and npm to use managed proxy.")

        # Resolve GitHub token and prepare environment
        resolver = CredentialResolver()
        github_token = resolver.resolve(str(self.config.github_token))

        env = os.environ.copy()
        env["GITHUB_TOKEN"] = github_token

        log.info(
            "starting_copilot_proxy",
            port=self.config.proxy_port,
            command="npx copilot-api@latest start",
        )

        try:
            # Start proxy process in new session for process group management
            self._proxy_process = await asyncio.create_subprocess_exec(
                "npx",
                "copilot-api@latest",
                "start",
                "--port",
                str(self.config.proxy_port),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            # Start background task to drain output and prevent pipe deadlock
            self._drain_task = asyncio.create_task(self._drain_proxy_output())

            log.info(
                "copilot_proxy_started",
                pid=self._proxy_process.pid,
                port=self.config.proxy_port,
            )

        except OSError as e:
            raise CopilotProxyError(f"Failed to start copilot-api proxy: {e}") from e

    async def _drain_proxy_output(self) -> None:
        """Drain stdout and stderr from proxy process to prevent deadlock.

        Runs as background task until cancelled. Logs output at debug level.
        """
        if self._proxy_process is None:
            return

        async def drain_stream(stream: asyncio.StreamReader | None, stream_name: str) -> None:
            """Drain a single stream."""
            if stream is None:
                return
            try:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    log.debug(
                        "copilot_proxy_output",
                        stream=stream_name,
                        line=line.decode("utf-8", errors="replace").rstrip(),
                    )
            except asyncio.CancelledError:
                pass

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(
                drain_stream(self._proxy_process.stdout, "stdout"),
                drain_stream(self._proxy_process.stderr, "stderr"),
            )

    async def _wait_for_proxy_ready(self) -> None:
        """Wait for proxy to become ready by polling the models endpoint.

        Uses exponential backoff with configurable timeout.

        Raises:
            CopilotProxyError: If proxy doesn't become ready within timeout.
        """
        backoff_intervals = [0.5, 1.0, 2.0, 4.0, 8.0]
        url = f"http://localhost:{self.config.proxy_port}/v1/models"
        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=5.0) as client:
            attempt = 0
            while True:
                elapsed = time.monotonic() - start_time
                if elapsed > self.config.startup_timeout:
                    raise CopilotProxyError(f"Proxy failed to become ready within {self.config.startup_timeout}s")

                # Check if process has died
                if self._proxy_process is not None and self._proxy_process.returncode is not None:
                    raise CopilotProxyError(
                        f"Proxy process exited unexpectedly with code {self._proxy_process.returncode}"
                    )

                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        log.info(
                            "copilot_proxy_ready",
                            elapsed_seconds=round(elapsed, 2),
                            attempts=attempt + 1,
                        )
                        return
                except httpx.ConnectError:
                    pass  # Expected while proxy is starting
                except httpx.TimeoutException:
                    pass  # Also expected during startup

                # Exponential backoff
                delay = backoff_intervals[min(attempt, len(backoff_intervals) - 1)]
                await asyncio.sleep(delay)
                attempt += 1

    async def _stop_proxy(self) -> None:
        """Stop the managed proxy subprocess gracefully.

        Sends SIGTERM to process group, waits for graceful shutdown,
        then sends SIGKILL if necessary.
        """
        # Cancel drain task
        if self._drain_task is not None:
            self._drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._drain_task
            self._drain_task = None

        # Stop proxy process
        if self._proxy_process is not None and self._proxy_process.returncode is None:
            pid = self._proxy_process.pid
            log.info("stopping_copilot_proxy", pid=pid)

            try:
                # Send SIGTERM to process group
                if pid is not None:
                    os.killpg(pid, signal.SIGTERM)

                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(
                        self._proxy_process.wait(),
                        timeout=self.config.shutdown_timeout,
                    )
                    log.info("copilot_proxy_stopped_gracefully", pid=pid)
                except TimeoutError:
                    # Force kill if graceful shutdown times out
                    log.warning("copilot_proxy_force_killing", pid=pid)
                    if pid is not None:
                        os.killpg(pid, signal.SIGKILL)
                    await self._proxy_process.wait()
                    log.info("copilot_proxy_killed", pid=pid)

            except ProcessLookupError:
                # Process already exited
                log.debug("copilot_proxy_already_exited", pid=pid)

        self._proxy_process = None

    async def _apply_rate_limit(self) -> None:
        """Apply configured rate limiting between requests.

        Sleeps if necessary to maintain minimum interval between API calls.
        """
        if self.config.rate_limit is None:
            return

        now = time.monotonic()
        elapsed = now - self._last_request_time

        if elapsed < self.config.rate_limit:
            delay = self.config.rate_limit - elapsed
            log.debug("applying_rate_limit", delay_seconds=round(delay, 3))
            await asyncio.sleep(delay)

        self._last_request_time = time.monotonic()

    def _handle_copilot_errors(self, e: httpx.HTTPStatusError) -> None:
        """Convert HTTP errors to Copilot-specific exceptions.

        Args:
            e: The HTTP status error to handle.

        Raises:
            CopilotAuthenticationError: For 401 errors.
            CopilotRateLimitError: For 429 errors.
            CopilotAbuseDetectedError: For 403 errors with "abuse" in message.
            httpx.HTTPStatusError: For other HTTP errors (re-raised).
        """
        status_code = e.response.status_code

        # Try to extract error message from response
        try:
            error_body = e.response.json()
            error_message = error_body.get("error", {}).get("message", str(e))
        except Exception:
            error_message = str(e)

        if status_code == 401:
            raise CopilotAuthenticationError(f"GitHub token is invalid or lacks Copilot access: {error_message}") from e

        if status_code == 429:
            raise CopilotRateLimitError(
                f"Rate limit exceeded. Consider setting rate_limit in config: {error_message}"
            ) from e

        if status_code == 403 and "abuse" in error_message.lower():
            raise CopilotAbuseDetectedError(
                f"GitHub detected potential abuse. Add rate limiting: {error_message}"
            ) from e

        # Re-raise unhandled HTTP errors
        raise

    def _ensure_connected(self) -> OpenAICompatibleProvider:
        """Ensure client is connected and return it.

        Returns:
            The connected OpenAI-compatible client.

        Raises:
            CopilotError: If provider is not connected.
        """
        if self._openai_client is None:
            raise CopilotError(
                "Provider is not connected. Use 'async with CopilotProvider(...)' "
                "or call 'await provider.connect()' first."
            )
        return self._openai_client

    # -------------------------------------------------------------------------
    # AgentProvider Interface Implementation (Delegated)
    # -------------------------------------------------------------------------

    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue.

        Args:
            issue: Issue to plan for.

        Returns:
            Generated Plan object with tasks.

        Raises:
            CopilotError: If not connected.
            CopilotAuthenticationError: If token is invalid.
            CopilotRateLimitError: If rate limited.
            CopilotAbuseDetectedError: If abuse is detected.
        """
        client = self._ensure_connected()
        await self._apply_rate_limit()

        try:
            return await client.generate_plan(issue)
        except httpx.HTTPStatusError as e:
            self._handle_copilot_errors(e)
            raise  # Unreachable but satisfies type checker

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        Args:
            plan: Plan to break down.

        Returns:
            List of Task objects with dependencies.

        Raises:
            CopilotError: If not connected.
            CopilotAuthenticationError: If token is invalid.
            CopilotRateLimitError: If rate limited.
            CopilotAbuseDetectedError: If abuse is detected.
        """
        client = self._ensure_connected()
        await self._apply_rate_limit()

        try:
            return await client.generate_prompts(plan)
        except httpx.HTTPStatusError as e:
            self._handle_copilot_errors(e)
            raise

    async def execute_task(self, task: Task, context: dict[str, Any]) -> TaskResult:
        """Execute a development task.

        Args:
            task: Task to execute.
            context: Execution context (workspace, branch, dependencies, etc.).

        Returns:
            TaskResult with execution details.

        Raises:
            CopilotError: If not connected.
            CopilotAuthenticationError: If token is invalid.
            CopilotRateLimitError: If rate limited.
            CopilotAbuseDetectedError: If abuse is detected.
        """
        client = self._ensure_connected()
        await self._apply_rate_limit()

        try:
            return await client.execute_task(task, context)
        except httpx.HTTPStatusError as e:
            self._handle_copilot_errors(e)
            raise

    async def review_code(self, diff: str, context: dict[str, Any]) -> Review:
        """Review code changes.

        Args:
            diff: Code diff to review.
            context: Review context (plan, task, etc.).

        Returns:
            Review object with approval status and comments.

        Raises:
            CopilotError: If not connected.
            CopilotAuthenticationError: If token is invalid.
            CopilotRateLimitError: If rate limited.
            CopilotAbuseDetectedError: If abuse is detected.
        """
        client = self._ensure_connected()
        await self._apply_rate_limit()

        try:
            return await client.review_code(diff, context)
        except httpx.HTTPStatusError as e:
            self._handle_copilot_errors(e)
            raise

    async def resolve_conflict(self, conflict_info: dict[str, Any]) -> str:
        """Resolve merge conflict.

        Args:
            conflict_info: Information about the conflict.

        Returns:
            Resolved file content.

        Raises:
            CopilotError: If not connected.
            CopilotAuthenticationError: If token is invalid.
            CopilotRateLimitError: If rate limited.
            CopilotAbuseDetectedError: If abuse is detected.
        """
        client = self._ensure_connected()
        await self._apply_rate_limit()

        try:
            return await client.resolve_conflict(conflict_info)
        except httpx.HTTPStatusError as e:
            self._handle_copilot_errors(e)
            raise

    # -------------------------------------------------------------------------
    # Async Context Manager
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "CopilotProvider":
        """Async context manager entry. Connects to Copilot API.

        Returns:
            Self for use in 'async with' statement.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit. Cleans up resources.

        Closes resources in reverse order:
        1. Close OpenAI-compatible client
        2. Stop managed proxy (if applicable)

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        # Close client first (reverse order of initialization)
        if self._openai_client is not None:
            await self._openai_client.client.aclose()
            self._openai_client = None

        # Stop managed proxy
        if self.config.manage_proxy:
            await self._stop_proxy()

        log.info("copilot_provider_disconnected")
