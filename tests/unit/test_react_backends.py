"""Unit tests for LLM backend abstraction and implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.agents.backends import (
    LLMBackend,
    OllamaBackend,
    OpenAIBackend,
    create_backend,
)
from repo_sapiens.exceptions import AgentError, ProviderConnectionError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def ollama_backend() -> OllamaBackend:
    """Create an OllamaBackend instance with defaults."""
    return OllamaBackend()


@pytest.fixture
def ollama_backend_custom_url() -> OllamaBackend:
    """Create an OllamaBackend with custom URL."""
    return OllamaBackend(base_url="http://custom-host:11434/", timeout=60)


@pytest.fixture
def openai_backend() -> OpenAIBackend:
    """Create an OpenAIBackend instance with defaults."""
    return OpenAIBackend()


@pytest.fixture
def openai_backend_with_key() -> OpenAIBackend:
    """Create an OpenAIBackend with API key."""
    return OpenAIBackend(
        base_url="https://api.openai.com/v1/",
        api_key="sk-test-key-12345",  # pragma: allowlist secret
        timeout=120,
    )


# =============================================================================
# TestOllamaBackend
# =============================================================================


class TestOllamaBackend:
    """Tests for OllamaBackend implementation."""

    def test_init_with_defaults(self, ollama_backend: OllamaBackend) -> None:
        """Test OllamaBackend initializes with correct defaults."""
        assert ollama_backend.base_url == "http://localhost:11434"
        assert ollama_backend.timeout == 300
        assert ollama_backend._client is None

    def test_init_strips_trailing_slashes(self, ollama_backend_custom_url: OllamaBackend) -> None:
        """Test that trailing slashes are stripped from base_url."""
        assert ollama_backend_custom_url.base_url == "http://custom-host:11434"
        assert ollama_backend_custom_url.timeout == 60

    def test_client_property_creates_client(self, ollama_backend: OllamaBackend) -> None:
        """Test that client property creates AsyncClient on first access."""
        assert ollama_backend._client is None
        client = ollama_backend.client
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        # Verify same client is returned on subsequent calls
        assert ollama_backend.client is client

    @pytest.mark.asyncio
    async def test_list_models_parses_ollama_response(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models parses Ollama response format correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3:8b"}, {"name": "qwen:7b"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await ollama_backend.list_models()

        assert models == ["llama3:8b", "qwen:7b"]

    @pytest.mark.asyncio
    async def test_list_models_calls_correct_endpoint(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models calls the correct Ollama API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        mock_get = AsyncMock(return_value=mock_response)
        with patch.object(ollama_backend.client, "get", mock_get):
            await ollama_backend.list_models()

        mock_get.assert_called_once_with("http://localhost:11434/api/tags")

    @pytest.mark.asyncio
    async def test_list_models_handles_empty_models(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models handles response with no models."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await ollama_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_handles_missing_name(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models handles model entries without name field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "model1"}, {"other_field": "value"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await ollama_backend.list_models()

        assert models == ["model1", ""]

    @pytest.mark.asyncio
    async def test_list_models_returns_empty_on_connection_error(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models returns empty list on connection error by default."""
        with patch.object(
            ollama_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            models = await ollama_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_raises_on_connection_error_when_requested(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models raises exception on connection error when raise_on_error=True."""
        with patch.object(
            ollama_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(httpx.ConnectError):
                await ollama_backend.list_models(raise_on_error=True)

    @pytest.mark.asyncio
    async def test_list_models_handles_generic_exception(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models handles generic exceptions gracefully."""
        with patch.object(
            ollama_backend.client,
            "get",
            AsyncMock(side_effect=RuntimeError("Unexpected error")),
        ):
            models = await ollama_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_raises_generic_exception_when_requested(self, ollama_backend: OllamaBackend) -> None:
        """Test list_models raises generic exception when raise_on_error=True."""
        with patch.object(
            ollama_backend.client,
            "get",
            AsyncMock(side_effect=RuntimeError("Unexpected error")),
        ):
            with pytest.raises(RuntimeError, match="Unexpected error"):
                await ollama_backend.list_models(raise_on_error=True)

    @pytest.mark.asyncio
    async def test_chat_calls_correct_endpoint(self, ollama_backend: OllamaBackend) -> None:
        """Test chat calls the correct Ollama API endpoint with correct format."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "response text"}}
        mock_response.raise_for_status = MagicMock()

        captured_args: dict = {}

        async def capture_post(url: str, json: dict | None = None) -> MagicMock:
            captured_args["url"] = url
            captured_args["json"] = json
            return mock_response

        with patch.object(ollama_backend.client, "post", capture_post):
            response = await ollama_backend.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="llama3:8b",
                temperature=0.5,
            )

        assert captured_args["url"] == "http://localhost:11434/api/chat"
        assert captured_args["json"]["model"] == "llama3:8b"
        assert captured_args["json"]["messages"] == [{"role": "user", "content": "Hello"}]
        assert captured_args["json"]["stream"] is False
        assert captured_args["json"]["options"]["temperature"] == 0.5
        assert response == "response text"

    @pytest.mark.asyncio
    async def test_chat_parses_ollama_response(self, ollama_backend: OllamaBackend) -> None:
        """Test chat parses Ollama response format correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "This is the response from Ollama"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "post", AsyncMock(return_value=mock_response)):
            response = await ollama_backend.chat(
                messages=[{"role": "user", "content": "Test"}],
                model="qwen3:latest",
            )

        assert response == "This is the response from Ollama"

    @pytest.mark.asyncio
    async def test_chat_handles_empty_message(self, ollama_backend: OllamaBackend) -> None:
        """Test chat handles response with empty message content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "post", AsyncMock(return_value=mock_response)):
            response = await ollama_backend.chat(
                messages=[{"role": "user", "content": "Test"}],
                model="qwen3:latest",
            )

        assert response == ""

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self, ollama_backend: OllamaBackend) -> None:
        """Test chat raises exception on HTTP errors."""
        with patch.object(
            ollama_backend.client,
            "post",
            AsyncMock(side_effect=httpx.HTTPStatusError("Server error", request=MagicMock(), response=MagicMock())),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await ollama_backend.chat(
                    messages=[{"role": "user", "content": "Test"}],
                    model="qwen3:latest",
                )

    @pytest.mark.asyncio
    async def test_connect_success(self, ollama_backend: OllamaBackend) -> None:
        """Test connect succeeds when Ollama is running."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3:8b"}, {"name": "qwen:7b"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_backend.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise
            await ollama_backend.connect()

    @pytest.mark.asyncio
    async def test_connect_raises_runtime_error_when_server_not_running(self, ollama_backend: OllamaBackend) -> None:
        """Test connect raises ProviderConnectionError when server not running."""
        with patch.object(
            ollama_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(ProviderConnectionError) as exc_info:
                await ollama_backend.connect()

        assert "Ollama not running" in str(exc_info.value)
        assert "ollama serve" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, ollama_backend: OllamaBackend) -> None:
        """Test close properly closes the HTTP client."""
        # Access client to create it
        _ = ollama_backend.client
        assert ollama_backend._client is not None

        await ollama_backend.close()
        assert ollama_backend._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, ollama_backend: OllamaBackend) -> None:
        """Test close handles case when client was never created."""
        assert ollama_backend._client is None
        # Should not raise
        await ollama_backend.close()
        assert ollama_backend._client is None


# =============================================================================
# TestOpenAIBackend
# =============================================================================


class TestOpenAIBackend:
    """Tests for OpenAIBackend implementation."""

    def test_init_with_defaults(self, openai_backend: OpenAIBackend) -> None:
        """Test OpenAIBackend initializes with correct defaults."""
        assert openai_backend.base_url == "http://localhost:8000/v1"
        assert openai_backend.api_key is None
        assert openai_backend.timeout == 300
        assert openai_backend._client is None

    def test_init_strips_trailing_slashes(self, openai_backend_with_key: OpenAIBackend) -> None:
        """Test that trailing slashes are stripped from base_url."""
        assert openai_backend_with_key.base_url == "https://api.openai.com/v1"
        assert openai_backend_with_key.timeout == 120

    def test_init_with_api_key_stores_correctly(self, openai_backend_with_key: OpenAIBackend) -> None:
        """Test that api_key is stored correctly."""
        assert openai_backend_with_key.api_key == "sk-test-key-12345"  # pragma: allowlist secret

    def test_client_property_creates_client(self, openai_backend: OpenAIBackend) -> None:
        """Test that client property creates AsyncClient on first access."""
        assert openai_backend._client is None
        client = openai_backend.client
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        # Verify same client is returned on subsequent calls
        assert openai_backend.client is client

    def test_get_headers_without_api_key(self, openai_backend: OpenAIBackend) -> None:
        """Test _get_headers returns correct headers without API key."""
        headers = openai_backend._get_headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_get_headers_with_api_key(self, openai_backend_with_key: OpenAIBackend) -> None:
        """Test _get_headers includes Authorization header when api_key provided."""
        headers = openai_backend_with_key._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer sk-test-key-12345"

    @pytest.mark.asyncio
    async def test_list_models_parses_openai_response(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models parses OpenAI response format correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await openai_backend.list_models()

        assert models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_list_models_calls_correct_endpoint(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models calls the correct OpenAI API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        captured_args: dict = {}

        async def capture_get(url: str, headers: dict | None = None) -> MagicMock:
            captured_args["url"] = url
            captured_args["headers"] = headers
            return mock_response

        with patch.object(openai_backend.client, "get", capture_get):
            await openai_backend.list_models()

        assert captured_args["url"] == "http://localhost:8000/v1/models"
        assert captured_args["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_list_models_includes_auth_header_when_api_key_provided(
        self, openai_backend_with_key: OpenAIBackend
    ) -> None:
        """Test list_models includes Authorization header when api_key is set."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "gpt-4"}]}
        mock_response.raise_for_status = MagicMock()

        captured_headers: dict | None = None

        async def capture_get(url: str, headers: dict | None = None) -> MagicMock:
            nonlocal captured_headers
            captured_headers = headers
            return mock_response

        with patch.object(openai_backend_with_key.client, "get", capture_get):
            await openai_backend_with_key.list_models()

        assert captured_headers is not None
        assert captured_headers["Authorization"] == "Bearer sk-test-key-12345"

    @pytest.mark.asyncio
    async def test_list_models_handles_empty_data(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models handles response with empty data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await openai_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_handles_api_error_response(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models handles OpenAI-style error response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await openai_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_raises_on_api_error_when_requested(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models raises on API error when raise_on_error=True."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "get", AsyncMock(return_value=mock_response)):
            with pytest.raises(AgentError, match="Invalid API key"):
                await openai_backend.list_models(raise_on_error=True)

    @pytest.mark.asyncio
    async def test_list_models_returns_empty_on_connection_error(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models returns empty list on connection error by default."""
        with patch.object(
            openai_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            models = await openai_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_raises_on_connection_error_when_requested(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models raises on connection error when raise_on_error=True."""
        with patch.object(
            openai_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(httpx.ConnectError):
                await openai_backend.list_models(raise_on_error=True)

    @pytest.mark.asyncio
    async def test_list_models_handles_generic_exception(self, openai_backend: OpenAIBackend) -> None:
        """Test list_models handles generic exceptions gracefully."""
        with patch.object(
            openai_backend.client,
            "get",
            AsyncMock(side_effect=RuntimeError("Unexpected error")),
        ):
            models = await openai_backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_chat_calls_correct_endpoint(self, openai_backend: OpenAIBackend) -> None:
        """Test chat calls the correct OpenAI API endpoint with correct format."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "response"}}]}
        mock_response.raise_for_status = MagicMock()

        captured_args: dict = {}

        async def capture_post(url: str, headers: dict | None = None, json: dict | None = None) -> MagicMock:
            captured_args["url"] = url
            captured_args["headers"] = headers
            captured_args["json"] = json
            return mock_response

        with patch.object(openai_backend.client, "post", capture_post):
            response = await openai_backend.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4",
                temperature=0.3,
            )

        assert captured_args["url"] == "http://localhost:8000/v1/chat/completions"
        assert captured_args["json"]["model"] == "gpt-4"
        assert captured_args["json"]["messages"] == [{"role": "user", "content": "Hello"}]
        assert captured_args["json"]["temperature"] == 0.3
        assert response == "response"

    @pytest.mark.asyncio
    async def test_chat_includes_auth_header_when_api_key_provided(
        self, openai_backend_with_key: OpenAIBackend
    ) -> None:
        """Test chat includes Authorization header when api_key is set."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]}
        mock_response.raise_for_status = MagicMock()

        captured_headers: dict | None = None

        async def capture_post(url: str, headers: dict | None = None, json: dict | None = None) -> MagicMock:
            nonlocal captured_headers
            captured_headers = headers
            return mock_response

        with patch.object(openai_backend_with_key.client, "post", capture_post):
            await openai_backend_with_key.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4",
            )

        assert captured_headers is not None
        assert captured_headers["Authorization"] == "Bearer sk-test-key-12345"

    @pytest.mark.asyncio
    async def test_chat_parses_openai_response(self, openai_backend: OpenAIBackend) -> None:
        """Test chat parses response from choices[0].message.content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is the OpenAI response",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "post", AsyncMock(return_value=mock_response)):
            response = await openai_backend.chat(
                messages=[{"role": "user", "content": "Test"}],
                model="gpt-4",
            )

        assert response == "This is the OpenAI response"

    @pytest.mark.asyncio
    async def test_chat_handles_api_error_response(self, openai_backend: OpenAIBackend) -> None:
        """Test chat raises AgentError on OpenAI-style API error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "post", AsyncMock(return_value=mock_response)):
            with pytest.raises(AgentError, match="Rate limit exceeded"):
                await openai_backend.chat(
                    messages=[{"role": "user", "content": "Test"}],
                    model="gpt-4",
                )

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self, openai_backend: OpenAIBackend) -> None:
        """Test chat raises exception on HTTP errors."""
        with patch.object(
            openai_backend.client,
            "post",
            AsyncMock(side_effect=httpx.HTTPStatusError("Server error", request=MagicMock(), response=MagicMock())),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await openai_backend.chat(
                    messages=[{"role": "user", "content": "Test"}],
                    model="gpt-4",
                )

    @pytest.mark.asyncio
    async def test_connect_success(self, openai_backend: OpenAIBackend) -> None:
        """Test connect succeeds when server is running."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(openai_backend.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise
            await openai_backend.connect()

    @pytest.mark.asyncio
    async def test_connect_raises_runtime_error_when_server_not_running(self, openai_backend: OpenAIBackend) -> None:
        """Test connect raises ProviderConnectionError when server not running."""
        with patch.object(
            openai_backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(ProviderConnectionError) as exc_info:
                await openai_backend.connect()

        assert "OpenAI-compatible server not running" in str(exc_info.value)
        assert "Ensure your server is started" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, openai_backend: OpenAIBackend) -> None:
        """Test close properly closes the HTTP client."""
        # Access client to create it
        _ = openai_backend.client
        assert openai_backend._client is not None

        await openai_backend.close()
        assert openai_backend._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, openai_backend: OpenAIBackend) -> None:
        """Test close handles case when client was never created."""
        assert openai_backend._client is None
        # Should not raise
        await openai_backend.close()
        assert openai_backend._client is None


# =============================================================================
# TestCreateBackendFactory
# =============================================================================


class TestCreateBackendFactory:
    """Tests for create_backend factory function."""

    def test_creates_ollama_backend_for_ollama_type(self) -> None:
        """Test create_backend creates OllamaBackend for 'ollama' type."""
        backend = create_backend("ollama")
        assert isinstance(backend, OllamaBackend)
        assert backend.base_url == "http://localhost:11434"

    def test_creates_ollama_backend_case_insensitive(self) -> None:
        """Test create_backend handles case-insensitive 'ollama' type."""
        backend = create_backend("OLLAMA")
        assert isinstance(backend, OllamaBackend)

        backend = create_backend("Ollama")
        assert isinstance(backend, OllamaBackend)

    def test_creates_openai_backend_for_openai_type(self) -> None:
        """Test create_backend creates OpenAIBackend for 'openai' type."""
        backend = create_backend("openai")
        assert isinstance(backend, OpenAIBackend)
        assert backend.base_url == "http://localhost:8000/v1"

    def test_creates_openai_backend_case_insensitive(self) -> None:
        """Test create_backend handles case-insensitive 'openai' type."""
        backend = create_backend("OPENAI")
        assert isinstance(backend, OpenAIBackend)

        backend = create_backend("OpenAI")
        assert isinstance(backend, OpenAIBackend)

    def test_passes_custom_base_url_to_ollama(self) -> None:
        """Test create_backend passes custom base_url to OllamaBackend."""
        backend = create_backend("ollama", base_url="http://custom:9999")
        assert isinstance(backend, OllamaBackend)
        assert backend.base_url == "http://custom:9999"

    def test_passes_custom_base_url_to_openai(self) -> None:
        """Test create_backend passes custom base_url to OpenAIBackend."""
        backend = create_backend("openai", base_url="https://api.example.com/v1")
        assert isinstance(backend, OpenAIBackend)
        assert backend.base_url == "https://api.example.com/v1"

    def test_passes_api_key_to_openai_backend(self) -> None:
        """Test create_backend passes api_key to OpenAIBackend."""
        backend = create_backend("openai", api_key="sk-my-secret-key")  # pragma: allowlist secret
        assert isinstance(backend, OpenAIBackend)
        assert backend.api_key == "sk-my-secret-key"  # pragma: allowlist secret

    def test_ignores_api_key_for_ollama_backend(self) -> None:
        """Test create_backend ignores api_key for OllamaBackend (no effect)."""
        # OllamaBackend does not use api_key, so it should be created without error
        backend = create_backend("ollama", api_key="sk-ignored")
        assert isinstance(backend, OllamaBackend)
        # OllamaBackend doesn't have api_key attribute
        assert not hasattr(backend, "api_key")

    def test_passes_custom_timeout(self) -> None:
        """Test create_backend passes custom timeout to backends."""
        ollama = create_backend("ollama", timeout=60)
        assert isinstance(ollama, OllamaBackend)
        assert ollama.timeout == 60

        openai = create_backend("openai", timeout=120)
        assert isinstance(openai, OpenAIBackend)
        assert openai.timeout == 120

    def test_raises_value_error_for_unknown_backend_type(self) -> None:
        """Test create_backend raises ValueError for unknown backend type."""
        with pytest.raises(ValueError) as exc_info:
            create_backend("unknown_backend")

        assert "Unknown backend type: unknown_backend" in str(exc_info.value)
        assert "Supported types: 'ollama', 'openai'" in str(exc_info.value)

    def test_raises_value_error_for_empty_backend_type(self) -> None:
        """Test create_backend raises ValueError for empty backend type."""
        with pytest.raises(ValueError):
            create_backend("")

    def test_uses_default_base_url_when_none_provided(self) -> None:
        """Test create_backend uses default base_url when None is passed."""
        ollama = create_backend("ollama", base_url=None)
        assert ollama.base_url == "http://localhost:11434"

        openai = create_backend("openai", base_url=None)
        assert openai.base_url == "http://localhost:8000/v1"


# =============================================================================
# TestLLMBackendAbstraction
# =============================================================================


class TestLLMBackendAbstraction:
    """Tests for LLMBackend abstract base class."""

    def test_llmbackend_is_abstract(self) -> None:
        """Test that LLMBackend cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            LLMBackend()  # type: ignore[abstract]

    def test_backends_implement_abstract_methods(self) -> None:
        """Test that concrete backends implement all abstract methods."""
        # This verifies the abstract methods are properly implemented
        ollama = OllamaBackend()
        openai = OpenAIBackend()

        # Verify they have the required methods
        assert hasattr(ollama, "connect")
        assert hasattr(ollama, "list_models")
        assert hasattr(ollama, "chat")

        assert hasattr(openai, "connect")
        assert hasattr(openai, "list_models")
        assert hasattr(openai, "chat")

        # Verify methods are callable
        assert callable(ollama.connect)
        assert callable(ollama.list_models)
        assert callable(ollama.chat)

        assert callable(openai.connect)
        assert callable(openai.list_models)
        assert callable(openai.chat)


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestBackendEdgeCases:
    """Additional edge case tests for backends."""

    @pytest.mark.asyncio
    async def test_ollama_handles_missing_models_key(self) -> None:
        """Test OllamaBackend handles response without 'models' key."""
        backend = OllamaBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # Missing 'models' key
        mock_response.raise_for_status = MagicMock()

        with patch.object(backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_openai_handles_missing_data_key(self) -> None:
        """Test OpenAIBackend handles response without 'data' key."""
        backend = OpenAIBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # Missing 'data' key
        mock_response.raise_for_status = MagicMock()

        with patch.object(backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await backend.list_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_openai_chat_handles_error_without_message(self) -> None:
        """Test OpenAIBackend chat handles error response without message."""
        backend = OpenAIBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": {"type": "invalid_request"}  # No 'message' key
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(backend.client, "post", AsyncMock(return_value=mock_response)):
            with pytest.raises(AgentError, match="Unknown error"):
                await backend.chat(
                    messages=[{"role": "user", "content": "Test"}],
                    model="gpt-4",
                )

    @pytest.mark.asyncio
    async def test_ollama_uses_default_temperature(self) -> None:
        """Test OllamaBackend uses default temperature of 0.7."""
        backend = OllamaBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "response"}}
        mock_response.raise_for_status = MagicMock()

        captured_json: dict | None = None

        async def capture_post(url: str, json: dict | None = None) -> MagicMock:
            nonlocal captured_json
            captured_json = json
            return mock_response

        with patch.object(backend.client, "post", capture_post):
            await backend.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="llama3:8b",
                # Not specifying temperature - should use default
            )

        assert captured_json is not None
        assert captured_json["options"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_openai_uses_default_temperature(self) -> None:
        """Test OpenAIBackend uses default temperature of 0.7."""
        backend = OpenAIBackend()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "response"}}]}
        mock_response.raise_for_status = MagicMock()

        captured_json: dict | None = None

        async def capture_post(url: str, headers: dict | None = None, json: dict | None = None) -> MagicMock:
            nonlocal captured_json
            captured_json = json
            return mock_response

        with patch.object(backend.client, "post", capture_post):
            await backend.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4",
                # Not specifying temperature - should use default
            )

        assert captured_json is not None
        assert captured_json["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_multiple_trailing_slashes_stripped(self) -> None:
        """Test that multiple trailing slashes are handled correctly."""
        ollama = OllamaBackend(base_url="http://localhost:11434///")
        # rstrip("/") removes all trailing slashes
        assert ollama.base_url == "http://localhost:11434"

        openai = OpenAIBackend(base_url="http://localhost:8000/v1///")
        assert openai.base_url == "http://localhost:8000/v1"
