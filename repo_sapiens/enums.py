"""Enumerations for repo-sapiens agent and provider types."""

from enum import Enum


class AgentType(str, Enum):
    """Types of AI agent CLIs supported by repo-sapiens.

    These represent the actual CLI tools that execute prompts.
    """

    CLAUDE = "claude"
    GOOSE = "goose"
    COPILOT = "copilot"
    BUILTIN = "builtin"

    def __str__(self) -> str:
        return self.value


class ProviderType(str, Enum):
    """Types of agent providers supported by repo-sapiens.

    Supported configurations:
    - claude-local: Claude Code CLI (local execution)
    - goose-local: Goose CLI (supports multiple LLM backends)
    - copilot-local: GitHub Copilot CLI
    - ollama: Local Ollama server (runs llama3.1, qwen3, etc.)
    - openai-compatible: Any OpenAI-compatible API endpoint
      (OpenAI, Groq, OpenRouter, vLLM, LM Studio, Fireworks, etc.)
    """

    # External CLI agents
    CLAUDE_LOCAL = "claude-local"
    GOOSE_LOCAL = "goose-local"
    COPILOT_LOCAL = "copilot-local"

    # Local model server
    OLLAMA = "ollama"

    # OpenAI-compatible API (covers all OpenAI API-compatible services)
    OPENAI_COMPATIBLE = "openai-compatible"

    def __str__(self) -> str:
        return self.value

    def to_agent_type(self) -> AgentType | None:
        """Convert provider type to corresponding agent type.

        Returns:
            AgentType if this provider maps to an external agent CLI,
            None for providers that use the builtin agent.
        """
        if self == ProviderType.CLAUDE_LOCAL:
            return AgentType.CLAUDE
        elif self == ProviderType.GOOSE_LOCAL:
            return AgentType.GOOSE
        elif self == ProviderType.COPILOT_LOCAL:
            return AgentType.COPILOT
        else:
            # OLLAMA, OPENAI_COMPATIBLE use builtin ReAct agent
            return AgentType.BUILTIN

    @property
    def is_local(self) -> bool:
        """Check if this provider runs locally (vs cloud API)."""
        return self in (
            ProviderType.CLAUDE_LOCAL,
            ProviderType.GOOSE_LOCAL,
            ProviderType.COPILOT_LOCAL,
            ProviderType.OLLAMA,
        )

    @property
    def is_external_cli(self) -> bool:
        """Check if this provider uses an external CLI tool."""
        return self in (
            ProviderType.CLAUDE_LOCAL,
            ProviderType.GOOSE_LOCAL,
            ProviderType.COPILOT_LOCAL,
        )
