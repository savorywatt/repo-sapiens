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

    These represent the configuration types that determine how
    the agent is invoked and configured.
    """

    # Claude providers
    CLAUDE_LOCAL = "claude-local"
    CLAUDE_API = "claude-api"

    # Goose provider (CLI only)
    GOOSE_LOCAL = "goose-local"

    # Copilot provider
    COPILOT_LOCAL = "copilot-local"

    # Cloud API providers
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OPENROUTER = "openrouter"

    # Local model providers
    OLLAMA = "ollama"

    def __str__(self) -> str:
        return self.value

    def to_agent_type(self) -> AgentType | None:
        """Convert provider type to corresponding agent type.

        Returns:
            AgentType if this provider maps to an external agent CLI,
            None for providers that use the builtin agent.
        """
        if self in (ProviderType.CLAUDE_LOCAL, ProviderType.CLAUDE_API):
            return AgentType.CLAUDE
        elif self == ProviderType.GOOSE_LOCAL:
            return AgentType.GOOSE
        elif self == ProviderType.COPILOT_LOCAL:
            return AgentType.COPILOT
        else:
            # OPENAI, ANTHROPIC, OLLAMA, etc. use builtin or custom providers
            return None

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
            ProviderType.CLAUDE_API,
            ProviderType.GOOSE_LOCAL,
            ProviderType.COPILOT_LOCAL,
        )
