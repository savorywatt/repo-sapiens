# GitHub Copilot Setup Guide

This guide shows you how to use GitHub Copilot CLI as an agent for repo-sapiens automation.

## What is GitHub Copilot CLI?

GitHub Copilot CLI (`gh copilot`) is an official GitHub CLI extension that provides AI-powered command suggestions. It uses the same models that power GitHub Copilot in IDEs.

**Important Limitations:**
- Copilot CLI is designed for **command suggestions**, not full code generation
- It has **limited capabilities** compared to Claude Code or Goose
- Requires an active **GitHub Copilot subscription**
- Best suited for simple automation tasks and shell command generation

## When to Use Copilot

**Use Copilot if you:**
- Already have a GitHub Copilot subscription
- Need simple shell command suggestions
- Want to stay within the GitHub ecosystem
- Are doing lightweight automation tasks

**Use Claude Code or Goose instead if you:**
- Need complex multi-file code generation
- Want full agentic capabilities (planning, reasoning, tool use)
- Require fine-grained control over the LLM

## Prerequisites

1. **GitHub CLI** installed
2. **GitHub Copilot subscription** (Individual, Business, or Enterprise)
3. **Authenticated** with GitHub CLI

## Quick Start

### 1. Install GitHub CLI

```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Windows
winget install GitHub.cli

# Verify installation
gh --version
```

### 2. Authenticate with GitHub

```bash
gh auth login
# Follow the prompts to authenticate via browser
```

### 3. Install Copilot Extension

```bash
gh extension install github/gh-copilot

# Verify installation
gh copilot --version
```

### 4. Initialize repo-sapiens with Copilot

```bash
cd /path/to/your/repo
sapiens init
```

When prompted, select **copilot** as your agent:

```
Available AI Agents:
  - Claude Code (Anthropic)
  - Goose AI (Block)
  - GitHub Copilot (GitHub)

Which agent do you want to use? [claude/goose/copilot]: copilot

GitHub Copilot Configuration

 GitHub CLI found at /usr/bin/gh
 Copilot extension installed
 GitHub CLI authenticated

Note:
GitHub Copilot CLI has limited capabilities compared to Claude/Goose.
It's primarily designed for command suggestions, not full code generation.
A GitHub Copilot subscription is required.

Continue with Copilot? [Y/n]: y
```

## Configuration

### Generated Config

After initialization, your config will look like:

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  api_key: null
  local_mode: true
```

### No API Key Required

Copilot uses your GitHub CLI authentication. No separate API key is needed.

## Health Check

Verify your setup:

```bash
sapiens health-check
```

Expected output:
```
Agent Provider:
   GitHub CLI (gh)     Found at /usr/bin/gh
   Copilot extension    Installed
   GitHub auth          Authenticated
```

## How It Works

When repo-sapiens uses Copilot, it:

1. Sends prompts to `gh copilot suggest -t shell`
2. Receives shell command suggestions
3. Parses and executes the suggested commands

This is different from Claude/Goose which have full agentic capabilities with tool calling.

## Limitations

| Feature | Copilot | Claude/Goose |
|---------|---------|--------------|
| Shell commands | Yes | Yes |
| Multi-file edits | Limited | Yes |
| Complex reasoning | Limited | Yes |
| Tool/function calling | No | Yes |
| Context awareness | Limited | Extensive |
| Cost | Subscription | Per-token |

## Troubleshooting

### GitHub CLI not found

```
Error: GitHub CLI (gh) not found
```

**Solution:** Install GitHub CLI (see Quick Start above)

### Copilot extension not installed

```
Warning: Copilot extension not installed
```

**Solution:**
```bash
gh extension install github/gh-copilot
```

### Not authenticated

```
Warning: GitHub CLI not authenticated
```

**Solution:**
```bash
gh auth login
```

### No Copilot subscription

```
Error: GitHub Copilot is not enabled for your account
```

**Solution:** Subscribe to GitHub Copilot at https://github.com/features/copilot

## Comparison with Other Agents

| Aspect | Copilot | Claude Code | Goose |
|--------|---------|-------------|-------|
| **Setup** | Easy (if you have subscription) | Easy | Medium |
| **Cost** | $10-39/month subscription | Per-token (~$0.15/1K) | Per-token (varies) |
| **Capabilities** | Basic | Excellent | Excellent |
| **Best for** | Simple tasks | Complex coding | Flexibility |
| **LLM choice** | GitHub's models | Anthropic only | Multiple providers |

## When to Upgrade

Consider switching to Claude Code or Goose if you need:

- Complex multi-step tasks
- Full code generation (not just commands)
- Better reasoning and planning
- Custom tool integrations

```bash
# Switch to Claude Code
npm install -g @anthropic-ai/claude-code
sapiens init --force

# Or switch to Goose
pip install goose-ai
sapiens init --force
```

## See Also

- [AGENT_COMPARISON.md](./AGENT_COMPARISON.md) - Compare all agent options
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Copy-paste configurations
- [GitHub Copilot CLI Docs](https://docs.github.com/en/copilot/github-copilot-in-the-cli)
