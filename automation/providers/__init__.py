"""Provider implementations for Git and AI agent integrations.

This package provides pluggable implementations for interacting with Git
platforms (Gitea, GitHub) and AI agents (Claude, OpenAI, Ollama).

Key Components:
    - GitProvider: Abstract base for Git platform providers
    - AgentProvider: Abstract base for AI agent providers
    - GiteaRestProvider: Gitea REST API implementation
    - GiteaProvider: Gitea MCP-based implementation
    - ClaudeLocalProvider: Local Claude Code CLI
    - ExternalAgentProvider: External Claude/Goose CLI
    - OllamaProvider: Ollama local inference

Git Providers Support:
    - Issue management (create, read, update, comment)
    - Pull request operations
    - Branch management
    - Commit operations
    - Webhook support

Agent Providers Support:
    - Task execution
    - Output streaming
    - Error handling
    - Cancelation

Example:
    >>> from automation.providers import GiteaRestProvider, ClaudeLocalProvider
    >>> git = GiteaRestProvider(base_url="...", token="...", owner="...", repo="...")
    >>> agent = ClaudeLocalProvider(model="claude-opus", working_dir=".")
"""
