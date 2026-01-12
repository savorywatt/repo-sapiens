"""Utility for detecting available AI agents on the system."""

import shutil
from typing import Any, cast

# Agent information registry
AGENT_INFO = {
    "claude": {
        "name": "Claude Code",
        "binary": "claude",
        "install_cmd": "curl -fsSL https://claude.com/install.sh | sh",
        "docs_url": "https://docs.anthropic.com/claude/docs/claude-code",
        "provider": "Anthropic",
        "models": [
            "claude-opus-4.5",
            "claude-sonnet-4.5",
            "claude-haiku-4.5",
        ],
        "supports_local": True,
        "supports_api": True,
    },
    "goose": {
        "name": "Goose AI",
        "binary": "goose",
        "install_cmd": "pip install goose-ai",
        "alt_install_cmd": "uvx goose",
        "docs_url": "https://github.com/block/goose",
        "provider": "Block (Square)",
        "models": [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "claude-3-5-sonnet-20241022",
            "ollama/llama3",
            "ollama/qwen2.5-coder",
        ],
        "llm_providers": ["openai", "anthropic", "ollama", "openrouter", "groq", "databricks"],
        "supports_local": True,
        "supports_api": False,
    },
    "builtin": {
        "name": "Builtin ReAct Agent",
        "binary": None,  # Always available - no external CLI needed
        "description": "Lightweight ReAct agent with tool-calling. Uses Ollama, vLLM, or cloud APIs.",
        "provider": "repo-sapiens",
        "models": ["qwen3:8b", "qwen3:14b", "llama3.1:8b", "gpt-4o", "claude-sonnet-4.5"],
        "llm_providers": ["ollama", "vllm", "openai", "anthropic", "openrouter", "groq"],
        "supports_local": True,
        "supports_api": True,
    },
}


def detect_available_agents() -> list[str]:
    """Detect which AI agent CLIs are installed and available.

    Returns:
        List of agent names that are available (e.g., ['claude', 'goose'])

    Example:
        >>> agents = detect_available_agents()
        >>> print(f"Found agents: {', '.join(agents)}")
        Found agents: claude, goose
    """
    available = []

    # Check for Claude Code
    if shutil.which("claude"):
        available.append("claude")

    # Check for Goose (direct install)
    if shutil.which("goose"):
        available.append("goose")

    # Check for Goose via uvx
    if shutil.which("uvx") and "goose" not in available:
        # Goose can be run via: uvx goose
        # We'll consider this as "goose" being available
        available.append("goose-uvx")

    return available


def is_agent_available(agent_name: str) -> bool:
    """Check if a specific agent is available.

    Args:
        agent_name: Name of the agent ('claude' or 'goose')

    Returns:
        True if agent CLI is available, False otherwise

    Example:
        >>> if is_agent_available('claude'):
        ...     print("Claude Code is installed")
    """
    if agent_name not in AGENT_INFO:
        return False

    binary = AGENT_INFO[agent_name]["binary"]
    assert isinstance(binary, str)  # Type narrowing for mypy
    return shutil.which(binary) is not None


def get_agent_info(agent_name: str) -> dict[str, Any]:
    """Get detailed information about an agent.

    Args:
        agent_name: Name of the agent ('claude' or 'goose')

    Returns:
        Dictionary with agent information including name, installation
        instructions, documentation URL, available models, etc.

    Raises:
        ValueError: If agent_name is not recognized

    Example:
        >>> info = get_agent_info('goose')
        >>> print(f"Install: {info['install_cmd']}")
        Install: pip install goose-ai
    """
    if agent_name not in AGENT_INFO:
        raise ValueError(f"Unknown agent: {agent_name}")

    return cast(dict[str, Any], AGENT_INFO[agent_name]).copy()


def get_install_instructions(agent_name: str) -> str:
    """Get installation instructions for an agent.

    Args:
        agent_name: Name of the agent ('claude' or 'goose')

    Returns:
        Installation command/instructions as a string

    Example:
        >>> print(get_install_instructions('claude'))
        curl -fsSL https://claude.com/install.sh | sh
    """
    info = get_agent_info(agent_name)
    return str(info.get("install_cmd", "See documentation for installation"))


def get_documentation_url(agent_name: str) -> str:
    """Get documentation URL for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        URL to agent documentation

    Example:
        >>> url = get_documentation_url('goose')
        >>> print(url)
        https://github.com/block/goose
    """
    info = get_agent_info(agent_name)
    return str(info.get("docs_url", ""))


def get_available_models(agent_name: str) -> list[str]:
    """Get list of available models for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        List of model identifiers

    Example:
        >>> models = get_available_models('goose')
        >>> print(models)
        ['gpt-4', 'gpt-4-turbo', 'claude-3-5-sonnet-20241022', 'ollama/llama3']
    """
    info = get_agent_info(agent_name)
    result = info.get("models", [])
    return cast(list[str], result)


def get_llm_providers(agent_name: str) -> list[str]:
    """Get list of LLM providers supported by an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        List of LLM provider names (only applicable for Goose)

    Example:
        >>> providers = get_llm_providers('goose')
        >>> print(providers)
        ['openai', 'anthropic', 'ollama']
    """
    info = get_agent_info(agent_name)
    result = info.get("llm_providers", [])
    return cast(list[str], result)


def format_agent_list() -> str:
    """Format list of detected agents for display.

    Returns:
        Formatted string listing available agents with provider hints

    Example:
        >>> print(format_agent_list())
        Available AI Agents:
          - Claude Code (Anthropic) - Claude models via CLI or API
          - Goose AI (Block) - OpenAI, Anthropic, Ollama, OpenRouter, Groq
          - Builtin ReAct Agent - Ollama, vLLM, or cloud APIs (always available)
    """
    available = detect_available_agents()

    lines = ["Available AI Agents:"]

    for agent_key in available:
        # Handle goose-uvx alias
        base_agent = agent_key.replace("-uvx", "")

        if base_agent in AGENT_INFO:
            info = AGENT_INFO[base_agent]
            name = info["name"]
            provider = info["provider"]

            install_note = " (via uvx)" if agent_key == "goose-uvx" else ""

            # Add provider hints
            if base_agent == "claude":
                hint = "Claude models via CLI or API"
            elif base_agent == "goose":
                providers = cast(list[str], info.get("llm_providers", []))
                hint = ", ".join(p.title() for p in providers[:5])
            else:
                hint = ""

            if hint:
                lines.append(f"  - {name} ({provider}){install_note} - {hint}")
            else:
                lines.append(f"  - {name} ({provider}){install_note}")

    # Always show builtin option (no CLI required)
    builtin_info = AGENT_INFO["builtin"]
    builtin_providers = cast(list[str], builtin_info.get("llm_providers", []))
    builtin_hint = ", ".join(p.title() for p in builtin_providers[:4]) + ", etc."
    lines.append(f"  - {builtin_info['name']} - {builtin_hint} (always available)")

    return "\n".join(lines)


def get_missing_agent_message(agent_name: str) -> str:
    """Get helpful error message when agent is not available.

    Args:
        agent_name: Name of the missing agent

    Returns:
        Error message with installation instructions

    Example:
        >>> print(get_missing_agent_message('claude'))
        Claude Code CLI not found.

        Install with:
          curl -fsSL https://claude.com/install.sh | sh

        Documentation:
          https://docs.anthropic.com/claude/docs/claude-code
    """
    if agent_name not in AGENT_INFO:
        return f"Unknown agent: {agent_name}"

    info = AGENT_INFO[agent_name]

    msg = f"{info['name']} CLI not found.\n\n"
    msg += "Install with:\n"
    msg += f"  {info['install_cmd']}\n"

    if "alt_install_cmd" in info:
        msg += f"\nAlternatively:\n  {info['alt_install_cmd']}\n"

    msg += f"\nDocumentation:\n  {info['docs_url']}"

    return msg


def check_agent_or_raise(agent_name: str) -> None:
    """Check if agent is available and raise if not.

    Args:
        agent_name: Name of the agent to check

    Raises:
        RuntimeError: If agent is not available

    Example:
        >>> try:
        ...     check_agent_or_raise('claude')
        ... except RuntimeError as e:
        ...     print(f"Error: {e}")
    """
    if not is_agent_available(agent_name):
        raise RuntimeError(get_missing_agent_message(agent_name))


# LLM Provider information for Goose
LLM_PROVIDER_INFO = {
    "openai": {
        "name": "OpenAI",
        "description": "Industry-leading models with excellent tool use",
        "models": ["gpt-4", "gpt-4-turbo", "gpt-4o"],
        "default_model": "gpt-4o",
        "tool_support": "excellent",
        "cost": "medium",
        "speed": "fast",
        "api_key_env": "OPENAI_API_KEY",
        "pros": [
            "Best-in-class tool/function calling",
            "Fast inference",
            "Reliable API",
            "Excellent coding capabilities",
        ],
        "cons": [
            "Requires API key and credits",
            "Data sent to OpenAI servers",
        ],
        "recommended_for": "Production use, complex tasks requiring tool usage",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "description": "Thoughtful reasoning with strong coding abilities",
        "models": ["claude-3-5-sonnet-20241022", "claude-opus-4.5", "claude-sonnet-4.5"],
        "default_model": "claude-3-5-sonnet-20241022",
        "tool_support": "excellent",
        "cost": "low-medium",
        "speed": "fast",
        "api_key_env": "ANTHROPIC_API_KEY",
        "pros": [
            "Excellent reasoning and planning",
            "Strong coding capabilities",
            "Good tool/function calling",
            "Lower cost than GPT-4",
        ],
        "cons": [
            "Requires API key and credits",
            "Data sent to Anthropic servers",
        ],
        "recommended_for": "Planning tasks, complex reasoning, cost-conscious usage",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Run models locally with complete privacy",
        "models": ["qwen2.5-coder:32b", "deepseek-coder-v2:16b", "llama3.1:70b", "codestral:22b"],
        "default_model": "qwen2.5-coder:32b",
        "tool_support": "limited",
        "cost": "free",
        "speed": "depends-on-hardware",
        "api_key_env": None,
        "requires_install": "brew install ollama (or see ollama.ai)",
        "pros": [
            "100% free (no API costs)",
            "Complete data privacy (runs locally)",
            "No internet required after model download",
            "Good for experimentation",
        ],
        "cons": [
            "Limited or no tool/function calling support",
            "Slower than cloud APIs (depends on hardware)",
            "Requires powerful hardware for larger models",
            "May produce lower quality results",
        ],
        "recommended_for": "Privacy-sensitive work, experimentation, learning, offline use",
        "note": "For tool usage, consider vLLM instead of Ollama",
    },
    "vllm": {
        "name": "vLLM (Local)",
        "description": "High-performance local serving with OpenAI-compatible API",
        "models": ["qwen3:8b", "qwen3:14b", "llama3.1:8b", "mistral:7b"],
        "default_model": "qwen3:8b",
        "tool_support": "good",
        "cost": "free",
        "speed": "fast",
        "api_key_env": None,
        "requires_install": "pip install vllm",
        "pros": [
            "100% free (no API costs)",
            "Complete data privacy (runs locally)",
            "OpenAI-compatible API (better tool support than Ollama)",
            "Excellent GPU utilization",
            "Continuous batching for high throughput",
        ],
        "cons": [
            "Requires powerful GPU (NVIDIA recommended)",
            "More complex setup than Ollama",
            "Linux-only (or WSL2 on Windows)",
        ],
        "recommended_for": "Local tool-calling tasks, privacy-sensitive work with good hardware",
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Access to 100+ models through one API",
        "models": [
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-405b",
            "deepseek/deepseek-coder",
        ],
        "default_model": "openai/gpt-4o",
        "tool_support": "excellent",
        "cost": "varies-by-model",
        "speed": "fast",
        "api_key_env": "OPENROUTER_API_KEY",
        "website": "https://openrouter.ai",
        "pros": [
            "Access to 100+ models with one API key",
            "Flexible model selection",
            "Competitive pricing",
            "Good tool support (model-dependent)",
            "Automatic fallbacks",
        ],
        "cons": [
            "Quality varies by model",
            "Requires API key and credits",
            "Extra layer vs direct provider",
        ],
        "recommended_for": "Experimenting with multiple models, cost optimization",
    },
    "groq": {
        "name": "Groq",
        "description": "Ultra-fast inference with specialized hardware",
        "models": [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
        "default_model": "llama-3.1-70b-versatile",
        "tool_support": "good",
        "cost": "low",
        "speed": "ultra-fast",
        "api_key_env": "GROQ_API_KEY",
        "website": "https://groq.com",
        "pros": [
            "Extremely fast inference (500+ tokens/sec)",
            "Low cost",
            "Good for rapid iteration",
            "Free tier available",
        ],
        "cons": [
            "Limited model selection",
            "Tool support varies by model",
            "Newer service (less proven)",
        ],
        "recommended_for": "Fast prototyping, high-throughput tasks",
    },
    "databricks": {
        "name": "Databricks",
        "description": "Enterprise-grade AI with custom model support",
        "models": ["databricks-meta-llama-3-1-70b-instruct", "databricks-dbrx-instruct"],
        "default_model": "databricks-meta-llama-3-1-70b-instruct",
        "tool_support": "good",
        "cost": "enterprise",
        "speed": "fast",
        "api_key_env": "DATABRICKS_API_KEY",
        "pros": [
            "Enterprise security and compliance",
            "Custom model support",
            "Integration with Databricks platform",
        ],
        "cons": [
            "Requires Databricks account",
            "Enterprise pricing",
            "Overkill for individual use",
        ],
        "recommended_for": "Enterprise users with existing Databricks infrastructure",
    },
}


def get_provider_info(provider_name: str) -> dict[str, Any]:
    """Get detailed information about an LLM provider.

    Args:
        provider_name: Name of the provider (e.g., 'openai', 'ollama')

    Returns:
        Dictionary with provider information

    Raises:
        ValueError: If provider is not recognized
    """
    if provider_name not in LLM_PROVIDER_INFO:
        raise ValueError(f"Unknown LLM provider: {provider_name}")

    return cast(dict[str, Any], LLM_PROVIDER_INFO[provider_name]).copy()


def get_provider_recommendation(use_case: str = "general") -> str:
    """Get provider recommendation based on use case.

    Args:
        use_case: Type of use case ('tool-usage', 'cost', 'privacy', 'speed', 'general')

    Returns:
        Recommended provider name and explanation
    """
    recommendations = {
        "tool-usage": (
            "openai",
            "OpenAI GPT-4o has the best tool/function calling support, "
            "essential for repo-sapiens file operations and git commands.",
        ),
        "cost": (
            "ollama",
            "Ollama is completely free and runs locally, though tool support is limited. "
            "For cloud with good cost/performance, try Anthropic Claude or OpenRouter.",
        ),
        "privacy": (
            "ollama",
            "Ollama runs entirely locally with complete data privacy. " "No code or data leaves your machine.",
        ),
        "speed": (
            "groq",
            "Groq provides ultra-fast inference (500+ tokens/sec) using specialized hardware, "
            "ideal for rapid iteration.",
        ),
        "general": (
            "openai",
            "OpenAI GPT-4o offers the best balance of performance, tool support, "
            "and reliability for general automation tasks.",
        ),
    }

    provider, reason = recommendations.get(use_case, recommendations["general"])
    return f"Recommended: {provider}\nReason: {reason}"


def format_provider_comparison() -> str:
    """Format a comparison table of LLM providers.

    Returns:
        Formatted comparison string for display
    """
    lines = [
        "LLM Provider Comparison:",
        "",
        "Provider      | Tool Support | Cost        | Speed      | Best For",
        "--------------|--------------|-------------|------------|---------------------------",
    ]

    providers = ["openai", "anthropic", "ollama", "vllm", "openrouter", "groq"]

    for provider in providers:
        if provider not in LLM_PROVIDER_INFO:
            continue

        info = cast(dict[str, Any], LLM_PROVIDER_INFO[provider])
        name = str(info["name"]).ljust(13)
        tool = str(info["tool_support"]).ljust(12)
        cost = str(info["cost"]).ljust(11)
        speed = str(info["speed"]).ljust(10)
        best_for = str(info["recommended_for"])[:25]

        lines.append(f"{name} | {tool} | {cost} | {speed} | {best_for}")

    return "\n".join(lines)


def get_vllm_vs_ollama_note() -> str:
    """Get explanation of vLLM vs Ollama for tool usage.

    Returns:
        Formatted explanation string
    """
    return """
📝 Local Serving: vLLM vs Ollama

For local model serving with tool/function calling:

**vLLM (Recommended for Tool Usage)**:
  - Excellent tool/function calling support
  - Faster inference with optimizations
  - Better for production workloads
  - Requires: pip install vllm
  - Use with: --provider vllm

**Ollama (Recommended for Simplicity)**:
  - Easier setup and use
  - Better for experimentation
  - Limited/no tool calling support*
  - Requires: brew install ollama (or see ollama.ai)
  - Use with: --provider ollama

*Note: Ollama may not properly handle tool/function calls, which are
essential for repo-sapiens file operations. For production use with
local models, vLLM is strongly recommended.

**Recommendation**: Start with cloud providers (OpenAI/Anthropic) for
reliability, then experiment with vLLM for local deployment.
"""
