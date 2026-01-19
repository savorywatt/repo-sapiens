"""Agents subpackage for repo-sapiens.

This package contains agent implementations for automated task execution.
"""

from repo_sapiens.agents.backends import (
    ChatResponse,
    LLMBackend,
    OllamaBackend,
    OpenAIBackend,
    ToolCall,
    create_backend,
)
from repo_sapiens.agents.react import (
    ReActAgentProvider,
    ReActConfig,
    TrajectoryStep,
    run_react_task,
)
from repo_sapiens.agents.tools import ToolDefinition, ToolExecutionError, ToolRegistry

__all__ = [
    # React agent
    "ReActAgentProvider",
    "ReActConfig",
    "TrajectoryStep",
    "run_react_task",
    # Tools
    "ToolRegistry",
    "ToolDefinition",
    "ToolExecutionError",
    # Backends
    "LLMBackend",
    "OllamaBackend",
    "OpenAIBackend",
    "ChatResponse",
    "ToolCall",
    "create_backend",
]
