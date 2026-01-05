# Goose AI Agent Setup Guide

This guide shows you how to use [Goose AI](https://github.com/block/goose) as the agent for repo-sapiens automation.

> **💡 Alternative: Built-in ReAct Agent**
>
> Before setting up Goose, consider using repo-sapiens' **built-in ReAct agent**—a simpler alternative that requires no external CLI installation. It uses Ollama directly and includes all essential tools (file operations, shell commands, search). See [Built-in ReAct Agent](#built-in-react-agent) below for details.

## What is Goose AI?

Goose is an open-source AI developer agent created by Block (Square). Unlike Claude Code which is tied to Anthropic's models, Goose supports **multiple LLM backends**:

- **OpenAI** (GPT-4, GPT-4 Turbo, GPT-4o)
- **Anthropic** (Claude 3.5 Sonnet, Claude Opus 4.5)
- **Ollama** (Local models: Llama 3.1, Qwen 2.5 Coder, DeepSeek Coder)
- **OpenRouter** (100+ models through one API)
- **Groq** (Ultra-fast inference)
- **Databricks** (Enterprise models)

## Why Use Goose?

**Use Goose if you want**:
- **Flexibility**: Switch between different LLM providers
- **Cost optimization**: Use cheaper models or free local models
- **Privacy**: Run 100% locally with Ollama
- **Speed**: Ultra-fast inference with Groq
- **Choice**: Access to 100+ models via OpenRouter

**Use Claude Code if you want**:
- **Simplicity**: One-click setup, zero configuration
- **Reliability**: Battle-tested with Anthropic's models
- **Performance**: Best-in-class coding with Claude Opus 4.5

## Quick Start

### 1. Install Goose

```bash
# Option 1: Install via pip
pip install goose-ai

# Option 2: Install via uvx (recommended for isolated environments)
uvx goose

# Verify installation
goose --version
```

### 2. Initialize repo-sapiens with Goose

```bash
cd /path/to/your/repo
sapiens init
```

When prompted:
1. Select **goose** as your agent
2. Choose your LLM provider (see [Provider Selection](#provider-selection) below)
3. Enter your API key (if needed)
4. Optionally customize temperature and toolkit

Example session:
```
🤖 AI Agent Configuration

Available AI Agents:
  - Goose AI (Block)

Which agent do you want to use? [goose/api]: goose

🪿 Goose Configuration

LLM Provider Comparison:

Provider      | Tool Support | Cost        | Speed      | Best For
--------------|--------------|-------------|------------|---------------------------
OpenAI        | excellent    | medium      | fast       | Production use, complex...
Anthropic     | excellent    | low-medium  | fast       | Planning tasks, complex...
Ollama        | limited      | free        | depends... | Privacy-sensitive work...
OpenRouter    | excellent    | varies...   | fast       | Experimenting with mult...
Groq          | good         | low         | ultra-fast | Fast prototyping, high-...

💡 Recommendation:
Recommended: openai
Reason: OpenAI GPT-4o has the best tool/function calling support, essential for automation file operations and git commands.

Which LLM provider? [openai/anthropic/ollama/openrouter/groq]: openai

Available models for OpenAI:
  1. gpt-4 (recommended)
  2. gpt-4-turbo
  3. gpt-4o

Which model? [gpt-4o]: gpt-4o

Enter your OpenAI API key: ••••••••••••••••

Customize Goose settings? (temperature, toolkit) [y/N]: n
```

### 3. Run the Automation

```bash
# Label an issue with "needs-planning" in Gitea
# Then start the daemon:
sapiens daemon --interval 60
```

That's it! Goose will now handle your issues using the selected LLM provider.

---

## Provider Selection

### OpenAI (Recommended for Tool Usage)

**Best for**: Production automation, complex tasks requiring tool/function calling

**Pros**:
- Excellent tool/function calling (essential for automation)
- Fast inference
- Reliable API
- Best coding capabilities

**Cons**:
- Requires API key and credits
- Data sent to OpenAI servers

**Setup**:
```bash
sapiens init
# Select: goose → openai → gpt-4o
# Enter API key from: https://platform.openai.com/api-keys
```

**Pricing**: ~$0.10-0.30 per 1K tasks (varies by model and usage)

---

### Anthropic Claude (Best for Reasoning)

**Best for**: Planning tasks, complex reasoning, cost-conscious usage

**Pros**:
- Excellent reasoning and planning
- Strong coding capabilities
- Good tool/function calling
- Lower cost than GPT-4

**Cons**:
- Requires API key and credits
- Data sent to Anthropic servers

**Setup**:
```bash
sapiens init
# Select: goose → anthropic → claude-3-5-sonnet-20241022
# Enter API key from: https://console.anthropic.com/
```

**Pricing**: ~$0.05-0.15 per 1K tasks

---

### Ollama (Best for Privacy & Free)

**Best for**: Privacy-sensitive work, experimentation, offline use

**Pros**:
- 100% free (no API costs)
- Complete data privacy (runs locally)
- No internet required after model download
- Good for experimentation

**Cons**:
- **Limited or no tool/function calling support** ⚠️
- Slower than cloud APIs (depends on hardware)
- Requires powerful hardware for larger models
- May produce lower quality results

**Setup**:
```bash
# 1. Install Ollama
brew install ollama  # macOS
# OR see https://ollama.ai for other platforms

# 2. Start Ollama server
ollama serve

# 3. Pull a coding model
ollama pull qwen2.5-coder:32b

# 4. Initialize repo-sapiens
sapiens init
# Select: goose → ollama → ollama/qwen2.5-coder:32b
```

**⚠️ Important Note**: Ollama may not properly handle tool/function calls, which are essential for automation file operations. For production use with local models, **vLLM is strongly recommended** instead.

**Alternative: vLLM (Recommended for Local Tool Usage)**

If you need tool/function calling with local models, use vLLM instead:

```bash
# Install vLLM
pip install vllm

# Start vLLM server with a coding model
vllm serve qwen2.5-coder:32b --enable-tools

# Configure Goose to use vLLM endpoint
# (Goose can connect to vLLM via OpenAI-compatible API)
```

---

### OpenRouter (Best for Experimentation)

**Best for**: Experimenting with multiple models, cost optimization

**Pros**:
- Access to 100+ models with one API key
- Flexible model selection
- Competitive pricing
- Automatic fallbacks
- Good tool support (model-dependent)

**Cons**:
- Quality varies by model
- Extra layer vs direct provider

**Setup**:
```bash
sapiens init
# Select: goose → openrouter → openai/gpt-4o
# Enter API key from: https://openrouter.ai
```

**Popular models**:
- `openai/gpt-4o` - Best tool support
- `anthropic/claude-3.5-sonnet` - Great reasoning
- `google/gemini-pro-1.5` - Fast and capable
- `meta-llama/llama-3.1-405b` - Powerful open model

**Pricing**: Varies by model ($0.01-0.50 per 1K tasks)

---

### Groq (Best for Speed)

**Best for**: Fast prototyping, high-throughput tasks

**Pros**:
- Extremely fast inference (500+ tokens/sec)
- Low cost
- Good for rapid iteration
- Free tier available

**Cons**:
- Limited model selection
- Tool support varies by model
- Newer service (less proven)

**Setup**:
```bash
sapiens init
# Select: goose → groq → llama-3.1-70b-versatile
# Enter API key from: https://groq.com
```

**Models**:
- `llama-3.1-70b-versatile` (recommended)
- `llama-3.1-8b-instant` (ultra-fast)
- `mixtral-8x7b-32768` (long context)

---

## Configuration Examples

### Example 1: OpenAI with Custom Settings

```yaml
# sapiens/config/sapiens_config.yaml
agent_provider:
  provider_type: goose-local
  model: gpt-4o
  api_key: @keyring:openai/api_key
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: openai
```

### Example 2: Anthropic Claude via Goose

```yaml
agent_provider:
  provider_type: goose-local
  model: claude-3-5-sonnet-20241022
  api_key: @keyring:anthropic/api_key
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: anthropic
```

### Example 3: Local Ollama (No API Key)

```yaml
agent_provider:
  provider_type: goose-local
  model: ollama/qwen2.5-coder:32b
  api_key: null
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: ollama
```

### Example 4: OpenRouter Multi-Model

```yaml
agent_provider:
  provider_type: goose-local
  model: openai/gpt-4o  # via OpenRouter
  api_key: @keyring:openrouter/api_key
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.8
    max_tokens: 4096
    llm_provider: openrouter
```

---

## Credential Management

### Keyring Backend (Recommended)

Store credentials securely in your OS keyring:

```bash
# During init, credentials are automatically stored
sapiens init --backend keyring

# Manual credential management
sapiens credentials set openai api_key
# Enter your OpenAI API key: ••••••••••••••••

sapiens credentials get openai api_key
# sk-proj-...

sapiens credentials list
# openai/api_key: ••••••••...
# gitea/api_token: ••••••••...
```

### Environment Variables Backend

Store in environment (less secure, good for CI/CD):

```bash
# Set in your shell profile (~/.bashrc, ~/.zshrc)
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENROUTER_API_KEY="sk-or-..."
export GROQ_API_KEY="gsk_..."

# Then run init
sapiens init --backend environment
```

### Gitea Actions Secrets

For automated workflows, set secrets in Gitea:

1. Navigate to: `https://your-gitea.com/owner/repo/settings/secrets`
2. Add secrets:
   - `GITEA_TOKEN` (your Gitea API token)
   - `OPENAI_API_KEY` (or whichever provider you use)

Or let `sapiens init` set them automatically with `--setup-secrets`.

---

## Switching LLM Providers

You can change providers at any time by editing your config file:

```yaml
# Switch from OpenAI to Anthropic
agent_provider:
  provider_type: goose-local
  model: claude-3-5-sonnet-20241022  # Changed
  api_key: @keyring:anthropic/api_key  # Changed
  goose_config:
    llm_provider: anthropic  # Changed
```

Or re-run init:
```bash
sapiens init --force  # Regenerate config
```

---

## Troubleshooting

### Goose not found

```
Error: goose CLI not found in PATH
```

**Solution**: Install Goose:
```bash
pip install goose-ai
# or
uvx goose
```

### API key not working

```
Error: Failed to authenticate with OpenAI
```

**Solution**: Verify your API key:
```bash
# Check if key is set
sapiens credentials get openai api_key

# Update key
sapiens credentials set openai api_key
```

### Tool calling not working with Ollama

```
Warning: Tool/function calls not being made
```

**Solution**: Ollama has limited tool support. Switch to:
- **OpenAI/Anthropic** for cloud-based tool calling
- **vLLM** for local tool calling
- Check [vLLM vs Ollama comparison](#ollama-best-for-privacy--free)

### Slow responses with local models

```
Task taking 5+ minutes to complete
```

**Solutions**:
1. Use a smaller model: `ollama/qwen2.5-coder:7b` instead of `:32b`
2. Ensure you have enough RAM (32B models need ~20GB)
3. Use GPU acceleration if available
4. Consider cloud providers (OpenAI, Groq) for faster inference

### Rate limiting

```
Error: Rate limit exceeded
```

**Solutions**:
- **OpenAI**: Upgrade to higher tier at https://platform.openai.com/account/limits
- **Groq**: Wait or upgrade to paid tier
- **OpenRouter**: Has automatic fallbacks
- **Local (Ollama/vLLM)**: No rate limits

---

## Best Practices

### For Production Use

✅ **Use**: OpenAI GPT-4o or Anthropic Claude 3.5 Sonnet
- Best tool/function calling support
- Reliable and fast
- Good cost/performance balance

### For Development/Testing

✅ **Use**: Ollama with local models
- Free and private
- Good for experimentation
- No API costs

⚠️ **But**: Switch to cloud for production (tool support issues)

### For Cost Optimization

✅ **Use**: OpenRouter or Anthropic
- Lower cost than OpenAI
- Still good tool support
- Flexible model selection

### For Privacy-Sensitive Projects

✅ **Use**: vLLM with local models (not Ollama)
- 100% local execution
- Good tool support
- Complete data privacy

### For Maximum Speed

✅ **Use**: Groq
- 500+ tokens/sec
- Low latency
- Good for rapid iteration

---

## Advanced Configuration

### Custom Toolkits

Goose supports custom toolkits for specialized tasks:

```yaml
agent_provider:
  goose_config:
    toolkit: developer  # or: researcher, writer, custom
```

Available toolkits:
- `default` - General purpose
- `developer` - Enhanced coding tools
- `researcher` - Web search and analysis
- `writer` - Document generation

### Temperature Tuning

Adjust creativity vs determinism:

```yaml
agent_provider:
  goose_config:
    temperature: 0.0  # Deterministic (code generation)
    # temperature: 0.7  # Balanced (default)
    # temperature: 1.5  # Creative (brainstorming)
```

### Token Limits

Control response length:

```yaml
agent_provider:
  goose_config:
    max_tokens: 2048   # Short responses
    # max_tokens: 4096   # Default
    # max_tokens: 8192   # Long responses (if model supports)
```

---

## Comparison with Claude Code

| Feature | Goose | Claude Code |
|---------|-------|-------------|
| **LLM Providers** | 6+ (OpenAI, Anthropic, Ollama, etc.) | Anthropic only |
| **Local Execution** | ✅ (with Ollama/vLLM) | ✅ |
| **API Mode** | ✅ | ✅ |
| **Tool/Function Calling** | ✅ (provider-dependent) | ✅✅ (excellent) |
| **Cost** | $0 (local) to $0.30/1K (cloud) | $0 (local) or $0.15/1K (API) |
| **Setup Complexity** | Medium (choose provider) | Easy (one choice) |
| **Best For** | Flexibility, choice, cost optimization | Simplicity, reliability |

**Bottom line**:
- Choose **Goose** for flexibility and choice
- Choose **Claude Code** for simplicity and reliability
- You can use **both** in different repos or switch as needed!

---

## Built-in ReAct Agent

repo-sapiens includes a **built-in ReAct (Reasoning + Acting) agent** that provides a simpler alternative to Goose. It uses Ollama directly without requiring any external CLI installation.

### Why Use the Built-in ReAct Agent?

**Use the ReAct agent if you want**:
- **Zero dependencies**: No external CLI to install—just Ollama
- **Simplicity**: Minimal configuration, works out of the box
- **Transparency**: See the agent's reasoning with `--verbose` mode
- **Interactive mode**: Built-in REPL for experimenting with tasks
- **Privacy**: Runs 100% locally with Ollama

**Use Goose if you want**:
- **Cloud providers**: Access to OpenAI, Anthropic, OpenRouter, Groq
- **Advanced toolkits**: Goose's specialized toolkits (developer, researcher, etc.)
- **Enterprise features**: More mature ecosystem with additional integrations

### Quick Start with ReAct

#### 1. Ensure Ollama is Running

```bash
# Install Ollama if needed
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# Start the server
ollama serve

# Pull a coding model (recommended models below)
ollama pull qwen3:latest
```

#### 2. Run a Task

```bash
# Single task execution
sapiens react "Create a hello.py file that prints Hello World"

# With verbose mode (shows reasoning steps)
sapiens react -v "List all Python files in this project"

# Specify a different model
sapiens react --model codellama:latest "Explain what main.py does"
```

#### 3. Interactive REPL Mode

```bash
sapiens react --repl
```

This starts an interactive session where you can:
- Execute multiple tasks
- Switch models on the fly (`/model qwen3:8b`)
- Toggle verbose mode (`/verbose`)
- List available models (`/models`)

Example session:
```
============================================================
ReAct Agent REPL
============================================================
Model: qwen3:latest
Ollama: http://localhost:11434
Working directory: /path/to/project
Available models: qwen3:latest, codellama:latest, llama3.1:latest

Commands:
  Type a task to execute it
  /help          - Show this help
  /models        - List available models
  /model <name>  - Switch to a different model
  /pwd           - Show working directory
  /verbose       - Toggle verbose mode
  /clear         - Clear screen
  /quit          - Exit REPL
============================================================

react> List all Python files in src/
```

### Available Tools

The ReAct agent has access to these tools:

| Tool | Description |
|------|-------------|
| `read_file` | Read contents of a file |
| `write_file` | Create or overwrite a file |
| `edit_file` | Replace specific text in a file (surgical edits) |
| `list_directory` | List files in a directory |
| `find_files` | Find files matching a glob pattern (e.g., `**/*.py`) |
| `search_files` | Search for patterns in file contents (like grep) |
| `tree` | Display directory structure as a tree |
| `run_command` | Execute shell commands (git, npm, python, etc.) |
| `finish` | Mark task complete and return the answer |

### Recommended Models

| Model | Size | Best For | Command |
|-------|------|----------|---------|
| `qwen3:latest` | ~8B | General coding, good balance | `ollama pull qwen3:latest` |
| `qwen2.5-coder:7b` | 7B | Code-specific tasks | `ollama pull qwen2.5-coder:7b` |
| `qwen2.5-coder:32b` | 32B | Complex coding (needs ~20GB RAM) | `ollama pull qwen2.5-coder:32b` |
| `codellama:latest` | 7B | Code completion, debugging | `ollama pull codellama:latest` |
| `deepseek-coder:6.7b` | 6.7B | Fast code generation | `ollama pull deepseek-coder:6.7b` |

### CLI Options

```bash
sapiens react [OPTIONS] [TASK]

Options:
  --model TEXT                Model to use (default: qwen3:latest)
  --backend [ollama|openai]   LLM backend (default: ollama)
  --base-url TEXT             Backend server URL (auto-detected if omitted)
  --api-key TEXT              API key for OpenAI-compatible backends
  --max-iterations INT        Max ReAct iterations (default: 10)
  --working-dir TEXT          Working directory for file operations (default: .)
  -v, --verbose               Show detailed trajectory (reasoning steps)
  --repl                      Start interactive REPL mode
```

### Using with vLLM (OpenAI-Compatible)

The ReAct agent also supports vLLM and other OpenAI-compatible servers:

```bash
# Start vLLM server
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 8000

# Run ReAct with vLLM
sapiens react --backend openai --base-url http://localhost:8000/v1 "Create hello.py"

# With API key (if required)
sapiens react --backend openai --base-url http://localhost:8000/v1 --api-key token "task"

# Interactive mode with vLLM
sapiens react --backend openai --base-url http://localhost:8000/v1 --repl
```

**Supported OpenAI-compatible servers:**
- vLLM
- LMStudio
- text-generation-inference (TGI)
- LocalAI
- Any server implementing the OpenAI API

### Example Use Cases

**Code Generation:**
```bash
sapiens react "Create a Python script that reads a CSV file and outputs JSON"
```

**Code Analysis:**
```bash
sapiens react -v "Find all TODO comments in the codebase"
```

**Refactoring:**
```bash
sapiens react "Rename the function 'getData' to 'fetch_user_data' in all files"
```

**Documentation:**
```bash
sapiens react "Add docstrings to all functions in src/utils.py"
```

### ReAct vs Goose Comparison

| Feature | Built-in ReAct | Goose |
|---------|---------------|-------|
| **Installation** | None (built-in) | Requires `pip install goose-ai` |
| **LLM Providers** | Ollama, vLLM, OpenAI-compatible | OpenAI, Anthropic, Ollama, OpenRouter, Groq |
| **Cloud Support** | ✅ (via OpenAI-compatible) | ✅ |
| **Tool Calling** | Custom implementation | LLM native function calling |
| **Toolkits** | Fixed set of tools | Multiple specialized toolkits |
| **REPL Mode** | ✅ | ✅ |
| **Verbose/Debug** | ✅ (trajectory view) | ✅ |
| **Best For** | Simple local tasks, experimentation | Production, cloud providers, advanced use |

### Integration with repo-sapiens Automation

Currently, the ReAct agent is available as a standalone CLI command (`sapiens react`). For full automation workflows (daemon mode, issue processing), use Goose or the Ollama provider.

To use the ReAct agent in automation workflows, you can:

1. **Script it**: Call `sapiens react` from shell scripts or CI/CD pipelines
2. **Use programmatically**: Import `ReActAgentProvider` in Python code

```python
from repo_sapiens.agents.react import ReActAgentProvider, ReActConfig
from repo_sapiens.models.domain import Task

async def run_task():
    config = ReActConfig(model="qwen3:latest", max_iterations=10)
    agent = ReActAgentProvider(working_dir="/path/to/project", config=config)

    task = Task(id="1", prompt_issue_id=1, title="Task", description="Do something")

    async with agent:
        await agent.connect()
        result = await agent.execute_task(task, {})
        print(result.output)
```

---

## Getting Help

- **Goose Issues**: https://github.com/block/goose/issues
- **repo-sapiens Issues**: https://github.com/savorywatt/repo-sapiens/issues
- **Provider Documentation**:
  - OpenAI: https://platform.openai.com/docs
  - Anthropic: https://docs.anthropic.com
  - Ollama: https://ollama.ai/docs
  - OpenRouter: https://openrouter.ai/docs
  - Groq: https://console.groq.com/docs

---

**Next Steps**:
- Try the [Built-in ReAct Agent](#built-in-react-agent) for a zero-installation local option
- See [AGENT_COMPARISON.md](./AGENT_COMPARISON.md) for a detailed comparison of all agent options
