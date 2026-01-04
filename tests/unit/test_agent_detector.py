"""Tests for repo_sapiens/utils/agent_detector.py - AI agent detection utilities."""

from unittest.mock import patch

import pytest

from repo_sapiens.utils.agent_detector import (
    AGENT_INFO,
    LLM_PROVIDER_INFO,
    check_agent_or_raise,
    detect_available_agents,
    format_agent_list,
    format_provider_comparison,
    get_agent_info,
    get_available_models,
    get_documentation_url,
    get_install_instructions,
    get_llm_providers,
    get_missing_agent_message,
    get_provider_info,
    get_provider_recommendation,
    get_vllm_vs_ollama_note,
    is_agent_available,
)


class TestDetectAvailableAgents:
    """Tests for detect_available_agents function."""

    def test_detect_both_agents_available(self):
        """Should detect both Claude and Goose when both are installed."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.side_effect = (
                lambda x: f"/usr/local/bin/{x}" if x in ["claude", "goose"] else None
            )

            agents = detect_available_agents()

            assert "claude" in agents
            assert "goose" in agents
            assert len(agents) == 2

    def test_detect_only_claude_available(self):
        """Should detect only Claude when Goose is not installed."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: "/usr/local/bin/claude" if x == "claude" else None

            agents = detect_available_agents()

            assert agents == ["claude"]

    def test_detect_only_goose_available(self):
        """Should detect only Goose when Claude is not installed."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: "/usr/local/bin/goose" if x == "goose" else None

            agents = detect_available_agents()

            assert agents == ["goose"]

    def test_detect_goose_via_uvx(self):
        """Should detect Goose via uvx when direct install is not available."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            # uvx is available, but goose is not directly installed
            mock_which.side_effect = lambda x: "/usr/local/bin/uvx" if x == "uvx" else None

            agents = detect_available_agents()

            assert "goose-uvx" in agents

    def test_no_goose_uvx_when_goose_already_detected(self):
        """Should not add goose-uvx if goose is already detected."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            # Both goose and uvx are available
            mock_which.side_effect = (
                lambda x: f"/usr/local/bin/{x}" if x in ["goose", "uvx"] else None
            )

            agents = detect_available_agents()

            assert "goose" in agents
            assert "goose-uvx" not in agents

    def test_detect_no_agents_available(self):
        """Should return empty list when no agents are installed."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = None

            agents = detect_available_agents()

            assert agents == []


class TestIsAgentAvailable:
    """Tests for is_agent_available function."""

    def test_claude_available(self):
        """Should return True when Claude CLI is found."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/claude"

            result = is_agent_available("claude")

            assert result is True
            mock_which.assert_called_with("claude")

    def test_claude_not_available(self):
        """Should return False when Claude CLI is not found."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = None

            result = is_agent_available("claude")

            assert result is False

    def test_goose_available(self):
        """Should return True when Goose CLI is found."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/goose"

            result = is_agent_available("goose")

            assert result is True
            mock_which.assert_called_with("goose")

    def test_goose_not_available(self):
        """Should return False when Goose CLI is not found."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = None

            result = is_agent_available("goose")

            assert result is False

    def test_unknown_agent_returns_false(self):
        """Should return False for unknown agent names."""
        result = is_agent_available("unknown-agent")

        assert result is False

    def test_empty_agent_name_returns_false(self):
        """Should return False for empty agent name."""
        result = is_agent_available("")

        assert result is False


class TestGetAgentInfo:
    """Tests for get_agent_info function."""

    def test_get_claude_info(self):
        """Should return Claude agent information."""
        info = get_agent_info("claude")

        assert info["name"] == "Claude Code"
        assert info["binary"] == "claude"
        assert info["provider"] == "Anthropic"
        assert "claude-opus-4.5" in info["models"]
        assert info["supports_local"] is True
        assert info["supports_api"] is True

    def test_get_goose_info(self):
        """Should return Goose agent information."""
        info = get_agent_info("goose")

        assert info["name"] == "Goose AI"
        assert info["binary"] == "goose"
        assert info["provider"] == "Block (Square)"
        assert "ollama/llama3" in info["models"]
        assert "openai" in info["llm_providers"]
        assert info["supports_local"] is True
        assert info["supports_api"] is False

    def test_get_info_returns_copy(self):
        """Should return a copy to prevent mutation of original."""
        info1 = get_agent_info("claude")
        info1["name"] = "Modified"

        info2 = get_agent_info("claude")

        assert info2["name"] == "Claude Code"

    def test_unknown_agent_raises_error(self):
        """Should raise ValueError for unknown agent."""
        with pytest.raises(ValueError) as exc_info:
            get_agent_info("unknown-agent")

        assert "Unknown agent: unknown-agent" in str(exc_info.value)


class TestGetInstallInstructions:
    """Tests for get_install_instructions function."""

    def test_get_claude_install_instructions(self):
        """Should return Claude installation command."""
        instructions = get_install_instructions("claude")

        assert "curl" in instructions
        assert "claude.com/install.sh" in instructions

    def test_get_goose_install_instructions(self):
        """Should return Goose installation command."""
        instructions = get_install_instructions("goose")

        assert "pip install goose-ai" in instructions

    def test_unknown_agent_raises_error(self):
        """Should raise ValueError for unknown agent."""
        with pytest.raises(ValueError):
            get_install_instructions("nonexistent")


class TestGetDocumentationUrl:
    """Tests for get_documentation_url function."""

    def test_get_claude_docs_url(self):
        """Should return Claude documentation URL."""
        url = get_documentation_url("claude")

        assert "anthropic.com" in url
        assert "claude-code" in url

    def test_get_goose_docs_url(self):
        """Should return Goose documentation URL."""
        url = get_documentation_url("goose")

        assert "github.com/block/goose" in url

    def test_unknown_agent_raises_error(self):
        """Should raise ValueError for unknown agent."""
        with pytest.raises(ValueError):
            get_documentation_url("mystery-agent")


class TestGetAvailableModels:
    """Tests for get_available_models function."""

    def test_get_claude_models(self):
        """Should return list of Claude models."""
        models = get_available_models("claude")

        assert isinstance(models, list)
        assert "claude-opus-4.5" in models
        assert "claude-sonnet-4.5" in models
        assert "claude-haiku-4.5" in models

    def test_get_goose_models(self):
        """Should return list of Goose-supported models."""
        models = get_available_models("goose")

        assert isinstance(models, list)
        assert "gpt-4" in models
        assert "ollama/llama3" in models
        assert "ollama/qwen2.5-coder" in models

    def test_unknown_agent_raises_error(self):
        """Should raise ValueError for unknown agent."""
        with pytest.raises(ValueError):
            get_available_models("fake-agent")


class TestGetLLMProviders:
    """Tests for get_llm_providers function."""

    def test_get_goose_llm_providers(self):
        """Should return LLM providers for Goose."""
        providers = get_llm_providers("goose")

        assert isinstance(providers, list)
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
        assert "openrouter" in providers
        assert "groq" in providers
        assert "databricks" in providers

    def test_get_claude_llm_providers_empty(self):
        """Should return empty list for Claude (no external providers)."""
        providers = get_llm_providers("claude")

        assert providers == []

    def test_unknown_agent_raises_error(self):
        """Should raise ValueError for unknown agent."""
        with pytest.raises(ValueError):
            get_llm_providers("imaginary-agent")


class TestFormatAgentList:
    """Tests for format_agent_list function."""

    def test_format_with_both_agents(self):
        """Should format list with both agents available."""
        with patch("repo_sapiens.utils.agent_detector.detect_available_agents") as mock_detect:
            mock_detect.return_value = ["claude", "goose"]

            result = format_agent_list()

            assert "Available AI Agents:" in result
            assert "Claude Code" in result
            assert "Anthropic" in result
            assert "Goose AI" in result
            assert "Block (Square)" in result

    def test_format_with_goose_uvx(self):
        """Should indicate uvx installation method for goose-uvx."""
        with patch("repo_sapiens.utils.agent_detector.detect_available_agents") as mock_detect:
            mock_detect.return_value = ["goose-uvx"]

            result = format_agent_list()

            assert "Goose AI" in result
            assert "(via uvx)" in result

    def test_format_with_no_agents(self):
        """Should return message when no agents detected."""
        with patch("repo_sapiens.utils.agent_detector.detect_available_agents") as mock_detect:
            mock_detect.return_value = []

            result = format_agent_list()

            assert result == "No AI agents detected."

    def test_format_with_single_agent(self):
        """Should format list with single agent."""
        with patch("repo_sapiens.utils.agent_detector.detect_available_agents") as mock_detect:
            mock_detect.return_value = ["claude"]

            result = format_agent_list()

            assert "Available AI Agents:" in result
            assert "Claude Code" in result
            assert "Goose" not in result


class TestGetMissingAgentMessage:
    """Tests for get_missing_agent_message function."""

    def test_missing_claude_message(self):
        """Should return helpful message for missing Claude."""
        msg = get_missing_agent_message("claude")

        assert "Claude Code CLI not found" in msg
        assert "Install with:" in msg
        assert "curl" in msg
        assert "Documentation:" in msg
        assert "anthropic.com" in msg

    def test_missing_goose_message_with_alt_install(self):
        """Should include alternative install method for Goose."""
        msg = get_missing_agent_message("goose")

        assert "Goose AI CLI not found" in msg
        assert "pip install goose-ai" in msg
        assert "Alternatively:" in msg
        assert "uvx goose" in msg
        assert "github.com/block/goose" in msg

    def test_unknown_agent_message(self):
        """Should return simple message for unknown agent."""
        msg = get_missing_agent_message("mystery")

        assert "Unknown agent: mystery" in msg


class TestCheckAgentOrRaise:
    """Tests for check_agent_or_raise function."""

    def test_check_available_agent_succeeds(self):
        """Should not raise when agent is available."""
        with patch("repo_sapiens.utils.agent_detector.is_agent_available") as mock_available:
            mock_available.return_value = True

            # Should not raise
            check_agent_or_raise("claude")

    def test_check_unavailable_agent_raises(self):
        """Should raise RuntimeError when agent is not available."""
        with patch("repo_sapiens.utils.agent_detector.is_agent_available") as mock_available:
            mock_available.return_value = False

            with pytest.raises(RuntimeError) as exc_info:
                check_agent_or_raise("claude")

            assert "Claude Code CLI not found" in str(exc_info.value)

    def test_check_unknown_agent_raises(self):
        """Should raise RuntimeError for unknown agent."""
        with pytest.raises(RuntimeError) as exc_info:
            check_agent_or_raise("nonexistent-agent")

        assert "Unknown agent:" in str(exc_info.value)


class TestGetProviderInfo:
    """Tests for get_provider_info function."""

    def test_get_openai_info(self):
        """Should return OpenAI provider information."""
        info = get_provider_info("openai")

        assert info["name"] == "OpenAI"
        assert "gpt-4o" in info["models"]
        assert info["tool_support"] == "excellent"
        assert info["api_key_env"] == "OPENAI_API_KEY"  # pragma: allowlist secret

    def test_get_anthropic_info(self):
        """Should return Anthropic provider information."""
        info = get_provider_info("anthropic")

        assert info["name"] == "Anthropic (Claude)"
        assert "claude-3-5-sonnet-20241022" in info["models"]
        assert info["api_key_env"] == "ANTHROPIC_API_KEY"  # pragma: allowlist secret

    def test_get_ollama_info(self):
        """Should return Ollama provider information."""
        info = get_provider_info("ollama")

        assert info["name"] == "Ollama (Local)"
        assert info["cost"] == "free"
        assert info["api_key_env"] is None
        assert "requires_install" in info

    def test_get_openrouter_info(self):
        """Should return OpenRouter provider information."""
        info = get_provider_info("openrouter")

        assert info["name"] == "OpenRouter"
        assert "openai/gpt-4o" in info["models"]
        assert info["website"] == "https://openrouter.ai"

    def test_get_groq_info(self):
        """Should return Groq provider information."""
        info = get_provider_info("groq")

        assert info["name"] == "Groq"
        assert info["speed"] == "ultra-fast"
        assert info["api_key_env"] == "GROQ_API_KEY"  # pragma: allowlist secret

    def test_get_databricks_info(self):
        """Should return Databricks provider information."""
        info = get_provider_info("databricks")

        assert info["name"] == "Databricks"
        assert info["cost"] == "enterprise"

    def test_provider_info_returns_copy(self):
        """Should return a copy to prevent mutation of original."""
        info1 = get_provider_info("openai")
        info1["name"] = "Modified"

        info2 = get_provider_info("openai")

        assert info2["name"] == "OpenAI"

    def test_unknown_provider_raises_error(self):
        """Should raise ValueError for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            get_provider_info("unknown-provider")

        assert "Unknown LLM provider: unknown-provider" in str(exc_info.value)


class TestGetProviderRecommendation:
    """Tests for get_provider_recommendation function."""

    def test_tool_usage_recommendation(self):
        """Should recommend OpenAI for tool usage."""
        result = get_provider_recommendation("tool-usage")

        assert "openai" in result.lower()
        assert "tool" in result.lower() or "function" in result.lower()

    def test_cost_recommendation(self):
        """Should recommend Ollama for cost-conscious usage."""
        result = get_provider_recommendation("cost")

        assert "ollama" in result.lower()
        assert "free" in result.lower()

    def test_privacy_recommendation(self):
        """Should recommend Ollama for privacy."""
        result = get_provider_recommendation("privacy")

        assert "ollama" in result.lower()
        assert "local" in result.lower()

    def test_speed_recommendation(self):
        """Should recommend Groq for speed."""
        result = get_provider_recommendation("speed")

        assert "groq" in result.lower()
        assert "fast" in result.lower()

    def test_general_recommendation(self):
        """Should provide balanced recommendation for general use."""
        result = get_provider_recommendation("general")

        assert "Recommended:" in result
        assert "Reason:" in result

    def test_unknown_use_case_defaults_to_general(self):
        """Should default to general recommendation for unknown use case."""
        result = get_provider_recommendation("unknown-use-case")

        general_result = get_provider_recommendation("general")
        assert result == general_result


class TestFormatProviderComparison:
    """Tests for format_provider_comparison function."""

    def test_format_includes_header(self):
        """Should include comparison header."""
        result = format_provider_comparison()

        assert "LLM Provider Comparison:" in result

    def test_format_includes_column_headers(self):
        """Should include column headers."""
        result = format_provider_comparison()

        assert "Provider" in result
        assert "Tool Support" in result
        assert "Cost" in result
        assert "Speed" in result
        assert "Best For" in result

    def test_format_includes_all_main_providers(self):
        """Should include main providers in comparison."""
        result = format_provider_comparison()

        assert "OpenAI" in result
        assert "Anthropic" in result
        assert "Ollama" in result
        assert "OpenRouter" in result
        assert "Groq" in result

    def test_format_has_table_structure(self):
        """Should have proper table structure with separators."""
        result = format_provider_comparison()

        # Check for separator line
        assert "----" in result
        # Check for pipe separators
        assert "|" in result


class TestGetVllmVsOllamaNote:
    """Tests for get_vllm_vs_ollama_note function."""

    def test_note_includes_vllm_section(self):
        """Should include vLLM information."""
        result = get_vllm_vs_ollama_note()

        assert "vLLM" in result
        assert "tool" in result.lower()

    def test_note_includes_ollama_section(self):
        """Should include Ollama information."""
        result = get_vllm_vs_ollama_note()

        assert "Ollama" in result
        assert "local" in result.lower()

    def test_note_includes_recommendation(self):
        """Should include recommendation."""
        result = get_vllm_vs_ollama_note()

        assert "Recommend" in result


class TestAgentInfoRegistry:
    """Tests for AGENT_INFO constant registry."""

    def test_all_agents_have_required_fields(self):
        """Should ensure all agents have required fields."""
        required_fields = ["name", "binary", "install_cmd", "docs_url", "provider", "models"]

        for agent_key, info in AGENT_INFO.items():
            for field in required_fields:
                assert field in info, f"Agent '{agent_key}' missing required field '{field}'"

    def test_all_agents_have_boolean_flags(self):
        """Should ensure all agents have support flags."""
        for _agent_key, info in AGENT_INFO.items():
            assert "supports_local" in info
            assert isinstance(info["supports_local"], bool)

    def test_models_are_lists(self):
        """Should ensure models are lists of strings."""
        for _agent_key, info in AGENT_INFO.items():
            assert isinstance(info["models"], list)
            for model in info["models"]:
                assert isinstance(model, str)


class TestLLMProviderInfoRegistry:
    """Tests for LLM_PROVIDER_INFO constant registry."""

    def test_all_providers_have_required_fields(self):
        """Should ensure all providers have required fields."""
        required_fields = [
            "name",
            "description",
            "models",
            "default_model",
            "tool_support",
            "cost",
            "speed",
        ]

        for provider_key, info in LLM_PROVIDER_INFO.items():
            for field in required_fields:
                assert field in info, f"Provider '{provider_key}' missing required field '{field}'"

    def test_all_providers_have_pros_and_cons(self):
        """Should ensure all providers have pros and cons lists."""
        for _provider_key, info in LLM_PROVIDER_INFO.items():
            assert "pros" in info
            assert "cons" in info
            assert isinstance(info["pros"], list)
            assert isinstance(info["cons"], list)

    def test_all_providers_have_recommended_for(self):
        """Should ensure all providers have recommended_for field."""
        for _provider_key, info in LLM_PROVIDER_INFO.items():
            assert "recommended_for" in info
            assert isinstance(info["recommended_for"], str)

    def test_api_key_env_field_exists(self):
        """Should ensure all providers have api_key_env field (can be None for local)."""
        for _provider_key, info in LLM_PROVIDER_INFO.items():
            assert "api_key_env" in info


class TestEdgeCases:
    """Edge cases and boundary condition tests."""

    def test_shutil_which_called_with_correct_binary(self):
        """Should call shutil.which with the correct binary name from registry."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            mock_which.return_value = None

            is_agent_available("claude")

            # Verify it used the binary from AGENT_INFO
            mock_which.assert_called_with("claude")

    def test_agent_info_values_are_not_mutated_by_get_functions(self):
        """Should ensure get functions don't mutate the global registries."""
        original_claude_name = AGENT_INFO["claude"]["name"]
        original_openai_name = LLM_PROVIDER_INFO["openai"]["name"]

        # Get info and modify it
        agent_info = get_agent_info("claude")
        agent_info["name"] = "Modified Claude"

        provider_info = get_provider_info("openai")
        provider_info["name"] = "Modified OpenAI"

        # Verify original is unchanged
        assert AGENT_INFO["claude"]["name"] == original_claude_name
        assert LLM_PROVIDER_INFO["openai"]["name"] == original_openai_name

    def test_format_agent_list_with_unknown_agent_in_list(self):
        """Should handle gracefully if an unknown agent key appears."""
        with patch("repo_sapiens.utils.agent_detector.detect_available_agents") as mock_detect:
            mock_detect.return_value = ["claude", "unknown-agent"]

            result = format_agent_list()

            # Should still include Claude
            assert "Claude Code" in result
            # Should not crash, unknown agent just won't appear

    def test_multiple_calls_to_detect_are_independent(self):
        """Should not cache detection results between calls."""
        with patch("repo_sapiens.utils.agent_detector.shutil.which") as mock_which:
            # First call: Claude available
            mock_which.side_effect = lambda x: "/bin/claude" if x == "claude" else None
            result1 = detect_available_agents()

            # Second call: Different availability
            mock_which.side_effect = lambda x: "/bin/goose" if x == "goose" else None
            result2 = detect_available_agents()

            assert result1 == ["claude"]
            assert result2 == ["goose"]
