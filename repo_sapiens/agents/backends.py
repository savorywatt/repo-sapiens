"""LLM backend abstraction layer for the ReAct agent.

This module provides a unified interface for different LLM backends,
allowing the ReAct agent to work with Ollama, OpenAI-compatible APIs,
or other LLM providers through a consistent interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
import structlog

from repo_sapiens.exceptions import AgentError, ProviderConnectionError

log = structlog.get_logger()


class LLMBackend(ABC):
    """Abstract base class for LLM backends.

    Provides a unified interface for interacting with different LLM providers.
    Implementations must handle connection verification, model listing, and
    chat completions.

    Example usage:
        backend = OllamaBackend()
        await backend.connect()
        models = await backend.list_models()
        response = await backend.chat(messages, model="qwen3:latest")
    """

    @abstractmethod
    async def connect(self) -> None:
        """Verify connection to the backend server.

        Raises:
            ProviderConnectionError: If the server is not reachable or not properly configured.
        """

    @abstractmethod
    async def list_models(self, raise_on_error: bool = False) -> list[str]:
        """List available models from the backend.

        Args:
            raise_on_error: If True, raise exceptions on connection errors.
                If False, return an empty list on errors.

        Returns:
            List of available model names/identifiers.
        """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        """Send chat messages and return the response.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            model: The model identifier to use.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            The assistant's response content as a string.

        Raises:
            httpx.HTTPError: On HTTP request failures.
            AgentError: On backend-specific errors.
        """


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLM inference.

    Connects to a local Ollama server for model inference. Ollama provides
    an easy way to run open-source LLMs locally.

    Attributes:
        base_url: The Ollama API base URL.
        timeout: Request timeout in seconds.

    Example:
        backend = OllamaBackend(base_url="http://localhost:11434")
        await backend.connect()
        response = await backend.chat(
            messages=[{"role": "user", "content": "Hello!"}],
            model="qwen3:latest"
        )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
    ):
        """Initialize the Ollama backend.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434).
            timeout: Request timeout in seconds (default: 300).
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def connect(self) -> None:
        """Verify Ollama is running and accessible.

        Raises:
            ProviderConnectionError: If Ollama server is not reachable.
        """
        try:
            models = await self.list_models(raise_on_error=True)
            log.info("ollama_connected", available_models=len(models))
        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                "Ollama not running",
                provider_url=self.base_url,
                suggestion="Start it with: ollama serve",
                agent_type="ollama",
            ) from e

    async def list_models(self, raise_on_error: bool = False) -> list[str]:
        """List available models from Ollama server.

        Args:
            raise_on_error: If True, raise exceptions on connection errors.

        Returns:
            List of model names available in Ollama.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m.get("name", "") for m in models]
        except httpx.ConnectError:
            log.warning("ollama_not_reachable", url=self.base_url)
            if raise_on_error:
                raise
            return []
        except Exception as e:
            log.error("ollama_list_models_failed", error=str(e))
            if raise_on_error:
                raise
            return []

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        """Send chat messages to Ollama and return the response.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            model: The Ollama model to use (e.g., "qwen3:latest").
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            The assistant's response content.

        Raises:
            httpx.HTTPError: On HTTP request failures.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except Exception as e:
            log.error("ollama_chat_failed", error=str(e), model=model)
            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class OpenAIBackend(LLMBackend):
    """OpenAI-compatible backend for LLM inference.

    Supports any OpenAI-compatible API, including:
    - OpenAI's official API
    - Local servers like vLLM, llama.cpp server, text-generation-webui
    - Cloud services with OpenAI-compatible endpoints

    Attributes:
        base_url: The API base URL.
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds.

    Example:
        # Local server without authentication
        backend = OpenAIBackend(base_url="http://localhost:8000/v1")

        # OpenAI API with authentication
        backend = OpenAIBackend(
            base_url="https://api.openai.com/v1",
            api_key="sk-..."  # pragma: allowlist secret
        )
        await backend.connect()
        response = await backend.chat(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gpt-4"
        )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: str | None = None,
        timeout: int = 300,
    ):
        """Initialize the OpenAI-compatible backend.

        Args:
            base_url: API base URL (default: http://localhost:8000/v1).
            api_key: Optional API key for authentication.
            timeout: Request timeout in seconds (default: 300).
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get request headers, including authorization if api_key is set.

        Returns:
            Dictionary of HTTP headers.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def connect(self) -> None:
        """Verify the OpenAI-compatible server is accessible.

        Raises:
            ProviderConnectionError: If the server is not reachable.
        """
        try:
            models = await self.list_models(raise_on_error=True)
            log.info("openai_backend_connected", available_models=len(models))
        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                "OpenAI-compatible server not running",
                provider_url=self.base_url,
                suggestion="Ensure your server is started and accessible.",
                agent_type="openai",
            ) from e

    async def list_models(self, raise_on_error: bool = False) -> list[str]:
        """List available models from the OpenAI-compatible server.

        Args:
            raise_on_error: If True, raise exceptions on connection errors.

        Returns:
            List of model IDs available on the server.
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Handle OpenAI-style error responses
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                log.error("openai_api_error", error=error_msg)
                if raise_on_error:
                    raise AgentError(f"OpenAI API error: {error_msg}", agent_type="openai")
                return []

            return [m["id"] for m in data.get("data", [])]
        except httpx.ConnectError:
            log.warning("openai_backend_not_reachable", url=self.base_url)
            if raise_on_error:
                raise
            return []
        except Exception as e:
            log.error("openai_list_models_failed", error=str(e))
            if raise_on_error:
                raise
            return []

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        """Send chat messages to the OpenAI-compatible server and return the response.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            model: The model ID to use.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            The assistant's response content.

        Raises:
            httpx.HTTPError: On HTTP request failures.
            AgentError: On OpenAI API errors.
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            result = response.json()

            # Handle OpenAI-style error responses
            if "error" in result:
                error_msg = result["error"].get("message", "Unknown error")
                log.error("openai_chat_error", error=error_msg, model=model)
                raise AgentError(f"OpenAI API error: {error_msg}", agent_type="openai")

            return result["choices"][0]["message"]["content"]
        except AgentError:
            # Re-raise AgentError (API errors)
            raise
        except Exception as e:
            log.error("openai_chat_failed", error=str(e), model=model)
            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def create_backend(
    backend_type: str,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 300,
) -> LLMBackend:
    """Create an LLM backend based on the specified type.

    This factory function creates the appropriate backend instance based on
    the backend_type parameter. It simplifies backend creation by providing
    sensible defaults while allowing full customization.

    Args:
        backend_type: The type of backend to create. Supported values:
            - "ollama": Ollama backend for local inference
            - "openai": OpenAI-compatible backend
        base_url: Optional custom base URL. If not provided, uses the default
            for each backend type.
        api_key: Optional API key (only used for OpenAI backend).
        timeout: Request timeout in seconds (default: 300).

    Returns:
        An LLMBackend instance of the appropriate type.

    Raises:
        ValueError: If backend_type is not recognized.

    Example:
        # Create Ollama backend with defaults
        backend = create_backend("ollama")

        # Create OpenAI backend with custom URL and API key
        backend = create_backend(
            "openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-..."  # pragma: allowlist secret
        )
    """
    backend_type_lower = backend_type.lower()

    if backend_type_lower == "ollama":
        return OllamaBackend(
            base_url=base_url or "http://localhost:11434",
            timeout=timeout,
        )
    elif backend_type_lower == "openai":
        return OpenAIBackend(
            base_url=base_url or "http://localhost:8000/v1",
            api_key=api_key,
            timeout=timeout,
        )
    else:
        raise ValueError(f"Unknown backend type: {backend_type}. " f"Supported types: 'ollama', 'openai'")
