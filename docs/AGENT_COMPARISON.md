# Agent Comparison Guide

This guide compares all AI agent options available in repo-sapiens, helping you choose the right one for your use case.

## Overview

repo-sapiens supports five agent options:

| Agent | Type | LLM Providers | Best For |
|-------|------|---------------|----------|
| [Claude Code](#claude-code) | External CLI | Anthropic only | Best coding performance, simplicity |
| [Goose](#goose-ai) | External CLI | OpenAI, Anthropic, Ollama, OpenRouter, Groq | Flexibility, cloud providers |
| [Built-in ReAct](#built-in-react-agent) | Built-in | Ollama, vLLM | Simple tasks, experimentation, local inference |
| [Ollama Provider](#ollama-provider) | Built-in | Ollama (local) | Automation workflows, local inference |
| [GitHub Copilot](#github-copilot) | External Proxy | GitHub's models | Existing subscribers (unofficial) |

---

## Quick Decision Guide

```
Do you need cloud LLM providers (OpenAI, Anthropic API)?
├── Yes → Do you want the best coding performance?
│         ├── Yes → Use Claude Code
│         └── No  → Use Goose (choose your provider)
└── No (local only) → Do you need full automation workflows?
                      ├── Yes → Use Ollama Provider
                      └── No  → Use Built-in ReAct Agent
```

---

## Built-in ReAct Agent

The ReAct (Reasoning + Acting) agent is built directly into repo-sapiens. It supports Ollama and can also connect to OpenAI-compatible backends (vLLM, LMStudio, etc.) via the `--ollama-url` option. It includes a curated set of tools for file operations and shell commands.

### Pros
- **Zero installation**: No external CLI needed
- **Multiple backends**: Ollama, vLLM, and other OpenAI-compatible servers via `--ollama-url`
- **Transparent reasoning**: See step-by-step thinking with `--verbose`
- **Interactive REPL**: Experiment with tasks interactively
- **Privacy**: Local execution with Ollama or vLLM
- **Simple**: Minimal configuration

### Cons
- **Fixed toolset**: Cannot extend with custom tools
- **Standalone**: Not integrated into daemon/automation workflows (yet)

### When to Use
- Quick local tasks and experimentation
- Learning how agents work (verbose mode shows reasoning)
- Using vLLM for better tool support than Ollama
- Privacy-sensitive environments
- Simple file operations and code generation

### Quick Start

**With Ollama:**
```bash
ollama serve
ollama pull qwen3:8b
sapiens task "Create a Python script that sorts a list"
```

**With vLLM (OpenAI-compatible):**
```bash
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 8000
sapiens task --ollama-url http://localhost:8000/v1 "Create hello.py"
```

### Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--model` | `qwen3:8b` | Model to use |
| `--ollama-url` | `http://localhost:11434` | Ollama or OpenAI-compatible server URL |
| `--max-iterations` | `10` | Maximum reasoning steps |
| `--working-dir` | `.` | Working directory |
| `-v, --verbose` | `false` | Show reasoning trajectory |
| `--repl` | `false` | Interactive mode |

### Available Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Create/overwrite files |
| `edit_file` | Surgical text replacement |
| `list_directory` | List directory contents |
| `find_files` | Glob pattern file search |
| `search_files` | Grep-like content search |
| `tree` | Directory tree view |
| `run_command` | Execute shell commands |

---

## Goose AI

[Goose](https://github.com/block/goose) is an open-source AI developer agent by Block (Square). It supports multiple LLM providers and offers specialized toolkits.

### Pros
- **Provider flexibility**: OpenAI, Anthropic, Ollama, OpenRouter, Groq
- **Cost optimization**: Switch providers based on cost/performance
- **Specialized toolkits**: Developer, researcher, writer modes
- **Active development**: Growing ecosystem
- **Native tool calling**: Uses LLM function calling

### Cons
- **External dependency**: Requires `pip install goose-ai`
- **Configuration complexity**: More options to configure
- **Tool support varies**: Depends on LLM provider

### When to Use
- Production automation with cloud providers
- Cost-sensitive workloads (use cheaper models)
- Need to switch between different LLM providers
- Want specialized toolkits

### Quick Start

```bash
# Install Goose
pip install goose-ai

# Initialize with Goose
sapiens init
# Select: goose → openai → gpt-4o

# Run automation
sapiens daemon --interval 60
```

### Configuration

```yaml
# sapiens_config.yaml
agent_provider:
  provider_type: goose-local
  model: gpt-4o
  api_key: @keyring:openai/api_key
  goose_config:
    toolkit: developer
    temperature: 0.7
    max_tokens: 4096
    llm_provider: openai
```

### Supported Providers

| Provider | Tool Support | Cost | Speed | Best For |
|----------|--------------|------|-------|----------|
| OpenAI | Excellent | Medium | Fast | Production, complex tasks |
| Anthropic | Excellent | Low-Medium | Fast | Planning, reasoning |
| Ollama | Limited | Free | Varies | Privacy, experimentation |
| OpenRouter | Excellent | Varies | Fast | Model experimentation |
| Groq | Good | Low | Ultra-fast | Rapid prototyping |

---

## Claude Code

[Claude Code](https://claude.ai/claude-code) is Anthropic's official CLI for Claude. It provides the best coding performance with Claude models.

### Pros
- **Best-in-class coding**: Optimized for software engineering
- **Simple setup**: One choice (Anthropic), minimal config
- **Battle-tested**: Mature, reliable tool
- **Excellent tool use**: Native function calling support
- **Rich context**: Large context windows

### Cons
- **Anthropic only**: No other LLM providers
- **Cost**: Requires Anthropic API credits
- **Cloud dependency**: Data sent to Anthropic

### When to Use
- Maximum coding quality is priority
- Production automation with proven reliability
- Already using Anthropic/Claude
- Complex multi-file refactoring

### Quick Start

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Initialize with Claude
sapiens init
# Select: claude → claude-sonnet-4-20250514

# Run automation
sapiens daemon --interval 60
```

### Configuration

```yaml
# sapiens_config.yaml
agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4-20250514
  api_key: @keyring:anthropic/api_key
```

### Available Models

| Model | Best For | Cost |
|-------|----------|------|
| `claude-opus-4-20250514` | Complex reasoning, large codebases | Higher |
| `claude-sonnet-4-20250514` | Balanced performance/cost | Medium |
| `claude-sonnet-4-5-20251022` | Fast, cost-effective | Lower |

---

## Ollama Provider

The Ollama Provider is a built-in integration that uses Ollama for local inference within repo-sapiens automation workflows.

### Pros
- **Full automation**: Works with daemon mode, issue processing
- **Local inference**: 100% private, no API costs
- **Built-in**: No external CLI installation
- **Flexible models**: Any Ollama-compatible model

### Cons
- **Limited tool support**: Ollama models may not handle tools well
- **Hardware requirements**: Large models need significant RAM/GPU
- **Quality varies**: Depends heavily on model choice

### When to Use
- Full automation workflows with local models
- Privacy requirements prevent cloud usage
- Cost-free operation is essential
- Have capable local hardware

### Quick Start

```bash
# Start Ollama
ollama serve
ollama pull qwen2.5-coder:32b

# Initialize with Ollama
sapiens init
# Select provider_type: ollama

# Run automation
sapiens daemon --interval 60
```

### Configuration

```yaml
# sapiens_config.yaml
agent_provider:
  provider_type: ollama
  model: qwen2.5-coder:32b
  base_url: http://localhost:11434
```

### Recommended Models

| Model | Size | RAM Required | Quality |
|-------|------|--------------|---------|
| `qwen2.5-coder:7b` | 7B | ~8GB | Good |
| `qwen2.5-coder:32b` | 32B | ~20GB | Excellent |
| `codellama:34b` | 34B | ~22GB | Very Good |
| `deepseek-coder:33b` | 33B | ~21GB | Excellent |

---

## GitHub Copilot

> **WARNING: Unofficial Integration**
>
> This integration uses [`copilot-api`](https://github.com/nicepkg/copilot-api),
> an **unofficial, reverse-engineered API proxy**. This integration:
>
> - Is **NOT endorsed or supported by GitHub**
> - May **violate GitHub's Terms of Service**
> - Could **stop working at any time** without notice
> - Requires aggressive rate limiting to avoid detection
>
> **Use at your own risk.** For production use, consider Claude Code, Goose, or
> OpenAI-compatible providers instead.

The Copilot integration uses a third-party proxy that translates OpenAI-compatible
API requests to GitHub Copilot's internal API.

### Pros
- **Familiar models**: Uses the same models as Copilot in your IDE
- **Subscription-based**: Predictable monthly cost if you already subscribe
- **No separate API key**: Uses GitHub OAuth token

### Cons
- **Unofficial**: Not endorsed by GitHub, may violate ToS
- **Unreliable**: Could break at any time without notice
- **Rate limited**: Requires aggressive rate limiting (`rate_limit: 2.0` or higher)
- **Subscription required**: $10-39/month
- **Limited model choice**: Restricted to Copilot's available models

### When to Use
- You already have a GitHub Copilot subscription
- You understand and accept the risks of using an unofficial integration
- You have configured appropriate rate limiting
- Other providers are not an option for your use case

### Quick Start

```bash
# Requires Node.js for the copilot-api proxy
node --version  # Ensure Node.js 18+ is installed

# Get a GitHub OAuth token with Copilot access
gh auth token

# Store the token
sapiens credentials set github/copilot_token

# Initialize with Copilot
sapiens init
# Select: copilot (and accept the disclaimer)
```

### Configuration

```yaml
# sapiens_config.yaml
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  copilot_config:
    github_token: "@keyring:github/copilot_token"
    manage_proxy: true        # Auto-start copilot-api
    proxy_port: 4141
    rate_limit: 2.0           # Seconds between requests (recommended)
```

### Limitations

| Aspect | Copilot | Claude Code |
|--------|---------|-------------|
| Official support | No | Yes |
| Reliability | May break | Stable |
| Rate limits | Aggressive | Generous |
| Model choice | Limited | Multiple Claude models |
| ToS compliance | Uncertain | Yes |

For detailed setup instructions, see [COPILOT_SETUP.md](./COPILOT_SETUP.md).

---

## Feature Comparison Matrix

| Feature | Claude Code | Goose | ReAct Agent | Ollama Provider | Copilot |
|---------|-------------|-------|-------------|-----------------|---------|
| **Installation** | `curl ...` | `pip install goose-ai` | None | None | Node.js + proxy |
| **Cloud Providers** | Anthropic | OpenAI, Anthropic, OpenRouter, Groq | - | - | GitHub (unofficial) |
| **Local Models** | - | Ollama | Ollama, vLLM | Ollama | - |
| **Tool Calling** | Native LLM | Native LLM | Custom | Prompt-based | Limited |
| **REPL Mode** | Yes | Yes | Yes | - | - |
| **Daemon Mode** | Yes | Yes | - | Yes | Yes |
| **Issue Processing** | Yes | Yes | - | Yes | Yes |
| **Verbose/Debug** | Yes | Yes | Yes | Yes | - |
| **Custom Toolkits** | - | Yes | - | - | - |
| **Multi-file Edits** | Excellent | Excellent | Good | Fair | Limited |
| **Official Support** | Yes | Yes | Yes | Yes | No |
| **Reliability** | Stable | Stable | Stable | Stable | May break |
| **ToS Compliance** | Yes | Yes | Yes | Yes | Uncertain |
| **Cost** | $0.15/1K | Free-$0.30/1K | Free | Free | $10-39/mo |

---

## Performance Comparison

### Coding Quality (subjective, based on typical use)

| Agent + Model | Code Quality | Reasoning | Tool Use | Speed |
|---------------|--------------|-----------|----------|-------|
| Claude Code + Opus 4 | Excellent | Excellent | Excellent | Medium |
| Claude Code + Sonnet 4 | Very Good | Very Good | Excellent | Fast |
| Goose + GPT-4o | Very Good | Very Good | Excellent | Fast |
| Goose + Claude 3.5 | Very Good | Excellent | Very Good | Fast |
| ReAct + qwen2.5-coder:32b | Good | Good | Good | Slow |
| Ollama + qwen2.5-coder:32b | Fair | Fair | Limited | Slow |

### Cost Comparison (approximate, per 1000 tasks)

| Setup | Cost |
|-------|------|
| Local (ReAct/Ollama) | $0 (electricity only) |
| Goose + Groq | ~$0.05 |
| Goose + Anthropic | ~$0.10 |
| Claude Code | ~$0.15 |
| Goose + OpenAI | ~$0.20 |

---

## Migration Paths

### From ReAct to Goose
If you outgrow the ReAct agent and need cloud providers:

```bash
pip install goose-ai
sapiens init --force
# Select: goose → your preferred provider
```

### From Goose to Claude Code
If you want maximum coding quality:

```bash
npm install -g @anthropic-ai/claude-code
sapiens init --force
# Select: claude
```

### From Claude Code to Goose
If you need provider flexibility or cost optimization:

```bash
pip install goose-ai
sapiens init --force
# Select: goose → openrouter (for flexibility)
```

---

## Recommendations by Use Case

### Personal Projects / Learning
**Recommendation**: Built-in ReAct Agent
- Free, simple, transparent reasoning
- Great for understanding how AI agents work

### Startup / Cost-Conscious
**Recommendation**: Goose with OpenRouter or Groq
- Flexible pricing, can switch models
- Good balance of cost and quality

### Enterprise / Production
**Recommendation**: Claude Code or Goose with OpenAI/Anthropic
- Best reliability and quality
- Consistent performance

### Privacy-Critical
**Recommendation**: Built-in ReAct Agent or Ollama Provider
- 100% local, no data leaves your machine
- Use qwen2.5-coder:32b for best local quality

### Experimentation / Research
**Recommendation**: Goose with OpenRouter
- Access to 100+ models
- Easy to compare different models

---

## See Also

- [GOOSE_SETUP.md](./GOOSE_SETUP.md) - Detailed Goose configuration guide
- [COPILOT_SETUP.md](./COPILOT_SETUP.md) - Copilot setup (unofficial integration)
- [Ollama Documentation](https://ollama.ai/docs) - Local model setup
- [Claude Code](https://claude.ai/claude-code) - Official Claude CLI
- [Goose AI](https://github.com/block/goose) - Goose repository
- [copilot-api](https://github.com/nicepkg/copilot-api) - Unofficial Copilot proxy (third-party)
