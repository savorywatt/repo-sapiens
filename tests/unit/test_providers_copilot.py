"""Tests for repo_sapiens/providers/copilot.py - GitHub Copilot provider implementation."""

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.config.settings import CopilotConfig
from repo_sapiens.models.domain import Issue, IssueState, Plan, Review, Task, TaskResult
from repo_sapiens.providers.copilot import (
    CopilotAbuseDetectedError,
    CopilotAuthenticationError,
    CopilotError,
    CopilotProvider,
    CopilotProxyError,
    CopilotRateLimitError,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def managed_config():
    """Config for managed proxy mode."""
    return CopilotConfig(
        github_token="gho_test_token_12345",
        manage_proxy=True,
        proxy_port=4141,
        account_type="individual",
        rate_limit=None,
        model="gpt-4",
    )


@pytest.fixture
def external_config():
    """Config for external proxy mode."""
    return CopilotConfig(
        github_token="gho_test_token_12345",
        manage_proxy=False,
        proxy_url="http://localhost:4141/v1",
        account_type="business",
        rate_limit=2.0,
        model="gpt-4",
    )


@pytest.fixture
def connected_provider(external_config):
    """Provider with mocked OpenAI client."""
    provider = CopilotProvider(copilot_config=external_config)
    provider._openai_client = AsyncMock()
    return provider


@pytest.fixture
def sample_issue():
    """Create a sample Issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Add authentication middleware",
        body="We need to implement JWT-based authentication.",
        state=IssueState.OPEN,
        labels=["feature", "security"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://github.com/example/repo/issues/42",
    )


@pytest.fixture
def sample_task():
    """Create a sample Task for testing."""
    return Task(
        id="task-1",
        prompt_issue_id=42,
        title="Create JWT token handler",
        description="Implement token generation and validation logic",
        dependencies=[],
    )


@pytest.fixture
def sample_plan():
    """Create a sample Plan for testing."""
    return Plan(
        id="42",
        title="Plan for issue #42: Add authentication middleware",
        description="Implementation plan for JWT authentication",
        tasks=[
            Task(
                id="task-1",
                prompt_issue_id=42,
                title="Create token handler",
                description="Handle JWT tokens",
                dependencies=[],
            )
        ],
    )


@pytest.fixture
def sample_review():
    """Create a sample Review for testing."""
    return Review(
        approved=True,
        comments=["Clean implementation", "Good error handling"],
        confidence_score=0.85,
    )


# -----------------------------------------------------------------------------
# TestCopilotConfig - Configuration validation
# -----------------------------------------------------------------------------


class TestCopilotConfig:
    """Tests for CopilotConfig validation."""

    def test_managed_mode_valid(self):
        """Managed mode with port is valid."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=True,
            proxy_port=4141,
        )
        assert config.manage_proxy is True
        assert config.proxy_port == 4141
        assert config.proxy_url is None

    def test_external_mode_valid(self):
        """External mode with URL is valid."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="http://localhost:4141/v1",
        )
        assert config.manage_proxy is False
        assert config.proxy_url == "http://localhost:4141/v1"

    def test_managed_mode_rejects_proxy_url(self):
        """Managed mode should reject proxy_url."""
        with pytest.raises(ValueError) as exc_info:
            CopilotConfig(
                github_token="gho_test_token",
                manage_proxy=True,
                proxy_port=4141,
                proxy_url="http://localhost:4141/v1",
            )
        assert "proxy_url must not be set when manage_proxy=true" in str(exc_info.value)

    def test_external_mode_requires_proxy_url(self):
        """External mode requires proxy_url."""
        with pytest.raises(ValueError) as exc_info:
            CopilotConfig(
                github_token="gho_test_token",
                manage_proxy=False,
            )
        assert "proxy_url is required when manage_proxy=false" in str(exc_info.value)

    def test_external_mode_validates_url_format(self):
        """External mode validates URL format."""
        with pytest.raises(ValueError) as exc_info:
            CopilotConfig(
                github_token="gho_test_token",
                manage_proxy=False,
                proxy_url="localhost:4141/v1",  # Missing http://
            )
        assert "proxy_url must start with http:// or https://" in str(exc_info.value)

    def test_external_mode_accepts_https_url(self):
        """External mode accepts HTTPS URLs."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="https://secure-proxy.example.com/v1",
        )
        assert config.proxy_url == "https://secure-proxy.example.com/v1"

    def test_effective_url_managed(self):
        """effective_url returns localhost:port for managed mode."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=True,
            proxy_port=5555,
        )
        assert config.effective_url == "http://localhost:5555/v1"

    def test_effective_url_external(self):
        """effective_url returns proxy_url for external mode."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="http://external-proxy:8080/v1",
        )
        assert config.effective_url == "http://external-proxy:8080/v1"

    def test_default_values(self):
        """Test default configuration values."""
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=True,
        )
        assert config.proxy_port == 4141
        assert config.account_type == "individual"
        assert config.rate_limit is None
        assert config.model == "gpt-4"
        assert config.startup_timeout == 30.0
        assert config.shutdown_timeout == 5.0

    def test_rate_limit_validation(self):
        """Test rate_limit minimum value validation."""
        with pytest.raises(ValueError):
            CopilotConfig(
                github_token="gho_test_token",
                manage_proxy=True,
                rate_limit=0.05,  # Below 0.1 minimum
            )


# -----------------------------------------------------------------------------
# TestCopilotProvider - Provider lifecycle
# -----------------------------------------------------------------------------


class TestCopilotProvider:
    """Tests for CopilotProvider lifecycle management."""

    def test_init(self, external_config):
        """Provider initialization stores config."""
        provider = CopilotProvider(copilot_config=external_config)

        assert provider.config is external_config
        assert provider.working_dir is None
        assert provider.qa_handler is None
        assert provider._proxy_process is None
        assert provider._openai_client is None
        assert provider._last_request_time == 0.0

    def test_init_with_options(self, external_config):
        """Provider initialization with optional parameters."""
        qa_handler = MagicMock()
        provider = CopilotProvider(
            copilot_config=external_config,
            working_dir="/workspace/project",
            qa_handler=qa_handler,
        )

        assert provider.working_dir == "/workspace/project"
        assert provider.qa_handler is qa_handler

    @pytest.mark.asyncio
    async def test_connect_external_mode(self, external_config):
        """External mode skips proxy start."""
        provider = CopilotProvider(copilot_config=external_config)

        with patch("repo_sapiens.providers.copilot.CredentialResolver") as mock_resolver_cls, patch(
            "repo_sapiens.providers.copilot.OpenAICompatibleProvider"
        ) as mock_openai_cls:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve.return_value = "resolved_token"

            mock_openai = AsyncMock()
            mock_openai_cls.return_value = mock_openai

            await provider.connect()

            # Should not start proxy in external mode
            assert provider._proxy_process is None

            # Should create OpenAI client with correct URL
            mock_openai_cls.assert_called_once_with(
                base_url="http://localhost:4141/v1",
                model="gpt-4",
                api_key="resolved_token",  # pragma: allowlist secret
                working_dir=None,
                qa_handler=None,
                timeout=300.0,
            )
            mock_openai.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_managed_mode_starts_proxy(self, managed_config):
        """Managed mode starts proxy."""
        provider = CopilotProvider(copilot_config=managed_config)

        with patch("repo_sapiens.providers.copilot.CredentialResolver") as mock_resolver_cls, patch(
            "repo_sapiens.providers.copilot.OpenAICompatibleProvider"
        ) as mock_openai_cls, patch.object(provider, "_start_proxy", AsyncMock()) as mock_start, patch.object(
            provider, "_wait_for_proxy_ready", AsyncMock()
        ) as mock_wait:
            mock_resolver = mock_resolver_cls.return_value
            mock_resolver.resolve.return_value = "resolved_token"

            mock_openai = AsyncMock()
            mock_openai_cls.return_value = mock_openai

            await provider.connect()

            # Should start proxy in managed mode
            mock_start.assert_called_once()
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, external_config, sample_issue):
        """Rate limiting delays requests."""
        # Create provider with rate limit
        config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="http://localhost:4141/v1",
            rate_limit=0.2,  # 0.2 seconds between requests
        )
        provider = CopilotProvider(copilot_config=config)

        # Set up the mocked client
        provider._openai_client = AsyncMock()
        mock_plan = MagicMock(spec=Plan)
        provider._openai_client.generate_plan = AsyncMock(return_value=mock_plan)

        # Set last request time to now to force rate limiting
        provider._last_request_time = time.monotonic()

        # Track sleep calls to verify rate limiting
        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            await original_sleep(delay)

        with patch("asyncio.sleep", mock_sleep):
            await provider.generate_plan(sample_issue)

        # Should have called sleep with approximately 0.2 seconds
        assert len(sleep_calls) == 1
        assert sleep_calls[0] >= 0.15, f"Expected sleep ~0.2s, got {sleep_calls[0]:.2f}s"

    @pytest.mark.asyncio
    async def test_rate_limiting_no_delay_when_none(self, connected_provider, sample_issue):
        """No rate limiting when rate_limit is None."""
        # Ensure rate_limit is None (default in external_config fixture is 2.0)
        connected_provider.config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="http://localhost:4141/v1",
            rate_limit=None,
        )

        mock_plan = MagicMock(spec=Plan)
        connected_provider._openai_client.generate_plan = AsyncMock(return_value=mock_plan)

        start_time = time.monotonic()
        await connected_provider.generate_plan(sample_issue)
        elapsed = time.monotonic() - start_time

        # Should complete quickly with no delay
        assert elapsed < 0.5, f"Expected quick completion, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_auth_error_handling(self, connected_provider, sample_issue):
        """401 errors raise CopilotAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid authentication token"}}

        http_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(CopilotAuthenticationError) as exc_info:
            await connected_provider.generate_plan(sample_issue)

        assert "Invalid authentication token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, connected_provider, sample_issue):
        """429 errors raise CopilotRateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded. Try again later."}}

        http_error = httpx.HTTPStatusError(
            "Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(CopilotRateLimitError) as exc_info:
            await connected_provider.generate_plan(sample_issue)

        assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_abuse_detection_error_handling(self, connected_provider, sample_issue):
        """403 with 'abuse' raises CopilotAbuseDetectedError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": {"message": "Abuse detection triggered. Slow down requests."}}

        http_error = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(CopilotAbuseDetectedError) as exc_info:
            await connected_provider.generate_plan(sample_issue)

        assert "abuse" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_403_without_abuse_reraises(self, connected_provider, sample_issue):
        """403 without 'abuse' keyword re-raises original error."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": {"message": "Access denied to this resource."}}

        http_error = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(httpx.HTTPStatusError):
            await connected_provider.generate_plan(sample_issue)

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self, external_config):
        """Context manager cleans up properly."""
        provider = CopilotProvider(copilot_config=external_config)

        mock_openai = AsyncMock()
        mock_openai.client = AsyncMock()
        mock_openai.client.aclose = AsyncMock()

        with patch("repo_sapiens.providers.copilot.CredentialResolver") as mock_resolver_cls, patch(
            "repo_sapiens.providers.copilot.OpenAICompatibleProvider"
        ) as mock_openai_cls:
            mock_resolver_cls.return_value.resolve.return_value = "resolved_token"
            mock_openai_cls.return_value = mock_openai

            async with provider:
                assert provider._openai_client is mock_openai

            # After exit, client should be closed and cleared
            mock_openai.client.aclose.assert_called_once()
            assert provider._openai_client is None

    @pytest.mark.asyncio
    async def test_context_manager_cleanup_on_exception(self, external_config):
        """Context manager cleans up even on exception."""
        provider = CopilotProvider(copilot_config=external_config)

        mock_openai = AsyncMock()
        mock_openai.client = AsyncMock()
        mock_openai.client.aclose = AsyncMock()

        with patch("repo_sapiens.providers.copilot.CredentialResolver") as mock_resolver_cls, patch(
            "repo_sapiens.providers.copilot.OpenAICompatibleProvider"
        ) as mock_openai_cls:
            mock_resolver_cls.return_value.resolve.return_value = "resolved_token"
            mock_openai_cls.return_value = mock_openai

            with pytest.raises(ValueError):
                async with provider:
                    raise ValueError("Test exception")

            # Should still clean up
            mock_openai.client.aclose.assert_called_once()
            assert provider._openai_client is None

    @pytest.mark.asyncio
    async def test_context_manager_managed_mode_stops_proxy(self, managed_config):
        """Context manager stops proxy in managed mode."""
        provider = CopilotProvider(copilot_config=managed_config)

        mock_openai = AsyncMock()
        mock_openai.client = AsyncMock()
        mock_openai.client.aclose = AsyncMock()

        with patch("repo_sapiens.providers.copilot.CredentialResolver") as mock_resolver_cls, patch(
            "repo_sapiens.providers.copilot.OpenAICompatibleProvider"
        ) as mock_openai_cls, patch.object(provider, "_start_proxy", AsyncMock()), patch.object(
            provider, "_wait_for_proxy_ready", AsyncMock()
        ), patch.object(provider, "_stop_proxy", AsyncMock()) as mock_stop:
            mock_resolver_cls.return_value.resolve.return_value = "resolved_token"
            mock_openai_cls.return_value = mock_openai

            async with provider:
                pass

            mock_stop.assert_called_once()


# -----------------------------------------------------------------------------
# TestCopilotProviderProxy - Proxy lifecycle management
# -----------------------------------------------------------------------------


class TestCopilotProviderProxy:
    """Tests for proxy lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_proxy_checks_npx_available(self, managed_config):
        """Start proxy checks if npx is available."""
        provider = CopilotProvider(copilot_config=managed_config)

        with patch("shutil.which", return_value=None):
            with pytest.raises(CopilotProxyError) as exc_info:
                await provider._start_proxy()

            assert "npx is not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_proxy_creates_subprocess(self, managed_config):
        """Start proxy creates subprocess with correct arguments."""
        provider = CopilotProvider(copilot_config=managed_config)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        with patch("shutil.which", return_value="/usr/bin/npx"), patch(
            "repo_sapiens.providers.copilot.CredentialResolver"
        ) as mock_resolver_cls, patch(
            "asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)
        ) as mock_exec, patch.object(provider, "_drain_proxy_output", AsyncMock()):
            mock_resolver_cls.return_value.resolve.return_value = "resolved_token"

            await provider._start_proxy()

            # Verify subprocess call
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert call_args[0][0] == "npx"
            assert "copilot-api@latest" in call_args[0]
            assert "--port" in call_args[0]
            assert str(managed_config.proxy_port) in call_args[0]

    @pytest.mark.asyncio
    async def test_start_proxy_handles_os_error(self, managed_config):
        """Start proxy handles OSError during subprocess creation."""
        provider = CopilotProvider(copilot_config=managed_config)

        with patch("shutil.which", return_value="/usr/bin/npx"), patch(
            "repo_sapiens.providers.copilot.CredentialResolver"
        ) as mock_resolver_cls, patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=OSError("Failed to start process")),
        ):
            mock_resolver_cls.return_value.resolve.return_value = "resolved_token"

            with pytest.raises(CopilotProxyError) as exc_info:
                await provider._start_proxy()

            assert "Failed to start copilot-api proxy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_proxy_ready_success(self, managed_config):
        """Wait for proxy ready succeeds when endpoint responds."""
        provider = CopilotProvider(copilot_config=managed_config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await provider._wait_for_proxy_ready()

    @pytest.mark.asyncio
    async def test_wait_for_proxy_ready_timeout(self, managed_config):
        """Wait for proxy ready raises error on timeout."""
        # Use very short timeout for testing
        managed_config.startup_timeout = 0.1
        provider = CopilotProvider(copilot_config=managed_config)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(CopilotProxyError) as exc_info:
                await provider._wait_for_proxy_ready()

            assert "failed to become ready" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_proxy_ready_process_died(self, managed_config):
        """Wait for proxy ready raises error if process exits."""
        provider = CopilotProvider(copilot_config=managed_config)
        provider._proxy_process = MagicMock()
        provider._proxy_process.returncode = 1  # Process exited

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client

            with pytest.raises(CopilotProxyError) as exc_info:
                await provider._wait_for_proxy_ready()

            assert "exited unexpectedly" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stop_proxy_graceful_shutdown(self, managed_config):
        """Stop proxy performs graceful shutdown."""
        provider = CopilotProvider(copilot_config=managed_config)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.wait = AsyncMock()

        provider._proxy_process = mock_process
        # Use a real asyncio.Task for _drain_task that completes when cancelled
        provider._drain_task = asyncio.create_task(asyncio.sleep(10))

        with patch("os.killpg") as mock_killpg:
            await provider._stop_proxy()

            # Should send SIGTERM to process group
            mock_killpg.assert_called()

        assert provider._proxy_process is None

    @pytest.mark.asyncio
    async def test_stop_proxy_force_kill_on_timeout(self, managed_config):
        """Stop proxy force kills process on timeout."""
        import signal

        provider = CopilotProvider(copilot_config=managed_config)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None

        # Track wait calls
        wait_calls = []

        async def wait_impl():
            wait_calls.append(len(wait_calls) + 1)

        mock_process.wait = wait_impl

        provider._proxy_process = mock_process
        provider._drain_task = None

        # Mock wait_for to simulate timeout on first call
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, timeout):
            # Execute the coroutine so wait_impl is called
            await coro
            # If this is the first wait call (after SIGTERM), raise TimeoutError
            if len(wait_calls) == 1:
                raise TimeoutError()
            # Second call (after SIGKILL) completes normally

        with patch("os.killpg") as mock_killpg, patch("asyncio.wait_for", mock_wait_for):
            await provider._stop_proxy()

            # Should have called killpg twice (SIGTERM then SIGKILL)
            calls = mock_killpg.call_args_list
            assert len(calls) == 2
            # First call should be SIGTERM
            assert calls[0][0][1] == signal.SIGTERM
            # Second call should be SIGKILL
            assert calls[1][0][1] == signal.SIGKILL


# -----------------------------------------------------------------------------
# TestCopilotProviderDelegation - Method delegation
# -----------------------------------------------------------------------------


class TestCopilotProviderDelegation:
    """Tests for method delegation to OpenAI client."""

    @pytest.mark.asyncio
    async def test_generate_plan_delegates(self, connected_provider, sample_issue):
        """generate_plan delegates to OpenAI client."""
        expected_plan = MagicMock(spec=Plan)
        connected_provider._openai_client.generate_plan = AsyncMock(return_value=expected_plan)

        result = await connected_provider.generate_plan(sample_issue)

        assert result is expected_plan
        connected_provider._openai_client.generate_plan.assert_called_once_with(sample_issue)

    @pytest.mark.asyncio
    async def test_execute_task_delegates(self, connected_provider, sample_task):
        """execute_task delegates to OpenAI client."""
        expected_result = MagicMock(spec=TaskResult)
        connected_provider._openai_client.execute_task = AsyncMock(return_value=expected_result)

        context = {"branch": "feature/test", "workspace": "/workspace"}
        result = await connected_provider.execute_task(sample_task, context)

        assert result is expected_result
        connected_provider._openai_client.execute_task.assert_called_once_with(sample_task, context)

    @pytest.mark.asyncio
    async def test_review_code_delegates(self, connected_provider):
        """review_code delegates to OpenAI client."""
        expected_review = MagicMock(spec=Review)
        connected_provider._openai_client.review_code = AsyncMock(return_value=expected_review)

        diff = "+def new_function():\n+    return True"
        context = {"description": "Add new function"}
        result = await connected_provider.review_code(diff, context)

        assert result is expected_review
        connected_provider._openai_client.review_code.assert_called_once_with(diff, context)

    @pytest.mark.asyncio
    async def test_generate_prompts_delegates(self, connected_provider, sample_plan):
        """generate_prompts delegates to OpenAI client."""
        expected_tasks = [MagicMock(spec=Task), MagicMock(spec=Task)]
        connected_provider._openai_client.generate_prompts = AsyncMock(return_value=expected_tasks)

        result = await connected_provider.generate_prompts(sample_plan)

        assert result is expected_tasks
        connected_provider._openai_client.generate_prompts.assert_called_once_with(sample_plan)

    @pytest.mark.asyncio
    async def test_resolve_conflict_delegates(self, connected_provider):
        """resolve_conflict delegates to OpenAI client."""
        expected_content = "resolved content"
        connected_provider._openai_client.resolve_conflict = AsyncMock(return_value=expected_content)

        conflict_info = {"file": "test.py", "content": "conflict markers"}
        result = await connected_provider.resolve_conflict(conflict_info)

        assert result == expected_content
        connected_provider._openai_client.resolve_conflict.assert_called_once_with(conflict_info)

    @pytest.mark.asyncio
    async def test_methods_raise_if_not_connected(self, external_config):
        """Methods raise CopilotError if not connected."""
        provider = CopilotProvider(copilot_config=external_config)
        # Provider is not connected (_openai_client is None)

        with pytest.raises(CopilotError) as exc_info:
            await provider.generate_plan(
                Issue(
                    id=1,
                    number=1,
                    title="Test",
                    body="Test",
                    state=IssueState.OPEN,
                    labels=[],
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    author="test",
                    url="http://test",
                )
            )

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_task_raises_if_not_connected(self, external_config, sample_task):
        """execute_task raises CopilotError if not connected."""
        provider = CopilotProvider(copilot_config=external_config)

        with pytest.raises(CopilotError) as exc_info:
            await provider.execute_task(sample_task, {})

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_code_raises_if_not_connected(self, external_config):
        """review_code raises CopilotError if not connected."""
        provider = CopilotProvider(copilot_config=external_config)

        with pytest.raises(CopilotError) as exc_info:
            await provider.review_code("+code", {})

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_prompts_raises_if_not_connected(self, external_config, sample_plan):
        """generate_prompts raises CopilotError if not connected."""
        provider = CopilotProvider(copilot_config=external_config)

        with pytest.raises(CopilotError) as exc_info:
            await provider.generate_prompts(sample_plan)

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_conflict_raises_if_not_connected(self, external_config):
        """resolve_conflict raises CopilotError if not connected."""
        provider = CopilotProvider(copilot_config=external_config)

        with pytest.raises(CopilotError) as exc_info:
            await provider.resolve_conflict({"file": "test.py", "content": ""})

        assert "not connected" in str(exc_info.value)


# -----------------------------------------------------------------------------
# TestCopilotProviderErrorHandling - Error handling edge cases
# -----------------------------------------------------------------------------


class TestCopilotProviderErrorHandling:
    """Tests for error handling edge cases."""

    @pytest.mark.asyncio
    async def test_handle_copilot_errors_json_parse_failure(self, connected_provider, sample_issue):
        """Error handler handles non-JSON response body."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.side_effect = ValueError("Not JSON")

        http_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(CopilotAuthenticationError):
            await connected_provider.generate_plan(sample_issue)

    @pytest.mark.asyncio
    async def test_handle_copilot_errors_500_reraises(self, connected_provider, sample_issue):
        """500 errors are re-raised without conversion."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal error"}}

        http_error = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        connected_provider._openai_client.generate_plan = AsyncMock(side_effect=http_error)

        with pytest.raises(httpx.HTTPStatusError):
            await connected_provider.generate_plan(sample_issue)

    @pytest.mark.asyncio
    async def test_rate_limit_applies_before_each_request(self, connected_provider, sample_issue):
        """Rate limit is applied before each delegated method."""
        connected_provider.config = CopilotConfig(
            github_token="gho_test_token",
            manage_proxy=False,
            proxy_url="http://localhost:4141/v1",
            rate_limit=0.5,
        )

        mock_plan = MagicMock(spec=Plan)
        connected_provider._openai_client.generate_plan = AsyncMock(return_value=mock_plan)

        # First call - should update last_request_time
        await connected_provider.generate_plan(sample_issue)
        first_time = connected_provider._last_request_time

        # Short sleep
        await asyncio.sleep(0.1)

        # Second call - should wait and update last_request_time
        await connected_provider.generate_plan(sample_issue)
        second_time = connected_provider._last_request_time

        # Verify time was updated
        assert second_time > first_time


# -----------------------------------------------------------------------------
# TestCopilotProviderExceptions - Custom exception tests
# -----------------------------------------------------------------------------


class TestCopilotProviderExceptions:
    """Tests for custom exception classes."""

    def test_copilot_error_base(self):
        """CopilotError is base exception."""
        error = CopilotError("Base error message")
        assert str(error) == "Base error message"
        assert isinstance(error, Exception)

    def test_copilot_authentication_error(self):
        """CopilotAuthenticationError inherits from CopilotError."""
        error = CopilotAuthenticationError("Auth failed")
        assert isinstance(error, CopilotError)
        assert "Auth failed" in str(error)

    def test_copilot_rate_limit_error(self):
        """CopilotRateLimitError inherits from CopilotError."""
        error = CopilotRateLimitError("Too many requests")
        assert isinstance(error, CopilotError)
        assert "Too many requests" in str(error)

    def test_copilot_abuse_detected_error(self):
        """CopilotAbuseDetectedError inherits from CopilotError."""
        error = CopilotAbuseDetectedError("Abuse detected")
        assert isinstance(error, CopilotError)
        assert "Abuse detected" in str(error)

    def test_copilot_proxy_error(self):
        """CopilotProxyError inherits from CopilotError."""
        error = CopilotProxyError("Proxy failed")
        assert isinstance(error, CopilotError)
        assert "Proxy failed" in str(error)
