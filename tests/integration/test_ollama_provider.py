"""Integration tests for Ollama provider.

These tests verify the OllamaProvider can interact with a real Ollama instance.
Requires:
- Ollama running at localhost:11434 (or OLLAMA_URL)
- A model pulled (default: qwen3:8b)

Run with: uv run pytest tests/integration/test_ollama_provider.py -v -m integration
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaConnection:
    """Test basic Ollama connectivity."""

    def test_ollama_tags(self, ollama_url: str, require_ollama: None) -> None:
        """Verify Ollama is accessible and can list models."""
        response = httpx.get(f"{ollama_url}/api/tags", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "models" in data

    def test_ollama_version(self, ollama_url: str, require_ollama: None) -> None:
        """Verify Ollama returns version info."""
        response = httpx.get(f"{ollama_url}/api/version", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaModels:
    """Test Ollama model operations."""

    def test_model_available(self, ollama_config: dict, ollama_url: str) -> None:
        """Verify the configured model is available."""
        response = httpx.get(f"{ollama_url}/api/tags", timeout=10.0)
        assert response.status_code == 200
        data = response.json()

        model_names = [m["name"] for m in data.get("models", [])]
        # Check if model or model:latest is available
        model = ollama_config["model"]
        model_base = model.split(":")[0]

        found = any(
            m == model or m.startswith(f"{model_base}:")
            for m in model_names
        )

        if not found:
            pytest.skip(f"Model {model} not available. Pull with: ollama pull {model}")


@pytest.mark.integration
@pytest.mark.ollama
@pytest.mark.slow
class TestOllamaGeneration:
    """Test Ollama text generation (slow tests)."""

    def test_simple_generation(self, ollama_config: dict, ollama_url: str) -> None:
        """Test basic text generation."""
        response = httpx.post(
            f"{ollama_url}/api/generate",
            json={
                "model": ollama_config["model"],
                "prompt": "Say 'hello' and nothing else.",
                "stream": False,
                "options": {
                    "num_predict": 10,
                    "temperature": 0.0,
                },
            },
            timeout=60.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_chat_completion(self, ollama_config: dict, ollama_url: str) -> None:
        """Test chat completion API."""
        response = httpx.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_config["model"],
                "messages": [
                    {"role": "user", "content": "Say 'hello' and nothing else."}
                ],
                "stream": False,
                "options": {
                    "num_predict": 10,
                    "temperature": 0.0,
                },
            },
            timeout=60.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "content" in data["message"]


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaOpenAICompatibility:
    """Test Ollama's OpenAI-compatible API endpoint."""

    def test_openai_models_endpoint(self, ollama_url: str, require_ollama: None) -> None:
        """Test /v1/models endpoint."""
        response = httpx.get(f"{ollama_url}/v1/models", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.slow
    def test_openai_chat_completions(self, ollama_config: dict, ollama_url: str) -> None:
        """Test /v1/chat/completions endpoint."""
        response = httpx.post(
            f"{ollama_url}/v1/chat/completions",
            json={
                "model": ollama_config["model"],
                "messages": [
                    {"role": "user", "content": "Say 'hello' and nothing else."}
                ],
                "max_tokens": 10,
                "temperature": 0.0,
            },
            timeout=60.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
