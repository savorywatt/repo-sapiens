# Quick Reference: Recommended Setups

Copy-paste configurations for common repo-sapiens setups. Pick the one that matches your needs.

---

## At a Glance

| Setup | Cost | Quality | Privacy | Best For |
|-------|------|---------|---------|----------|
| [Claude Code](#1-claude-code-best-quality) | ~$0.15/1K tasks | Excellent | Cloud | Production, complex code |
| [Goose + OpenRouter](#2-goose--openrouter-best-flexibility) | ~$0.05-0.20/1K | Very Good | Cloud | Flexibility, experimentation |
| [Goose + Groq](#3-goose--groq-best-speed) | ~$0.02/1K | Good | Cloud | Fast iteration, prototyping |
| [Builtin + Ollama](#4-builtin--ollama-best-privacy) | Free | Good | Local | Privacy, offline, free |
| [Builtin + vLLM](#5-builtin--vllm-best-local-quality) | Free | Very Good | Local | Local + tool support |
| [Copilot](#6-github-copilot-simplest) | $10-39/mo | Basic | Cloud | Simple tasks, GitHub users |

---

## 1. Claude Code (Best Quality)

**Best for:** Production automation, complex multi-file refactoring, maximum code quality

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: claude-local
  model: claude-sonnet-4-20250514
  api_key: "@keyring:anthropic/api_key"
  local_mode: true
```

**Setup:**
```bash
# Install Claude Code
curl -fsSL https://claude.ai/install.sh | sh

# Store API key
sapiens credentials set anthropic api_key
# Get key from: https://console.anthropic.com/

# Initialize
sapiens init
# Select: claude
```

**Models:**
| Model | Use Case | Cost |
|-------|----------|------|
| `claude-sonnet-4-20250514` | Balanced (recommended) | ~$3/1M tokens |
| `claude-opus-4-20250514` | Complex reasoning | ~$15/1M tokens |
| `claude-haiku-4-20250514` | Fast, simple tasks | ~$0.25/1M tokens |

---

## 2. Goose + OpenRouter (Best Flexibility)

**Best for:** Experimenting with models, accessing open-weight models, cost optimization

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: goose-local
  model: anthropic/claude-3.5-sonnet
  api_key: "@keyring:openrouter/api_key"
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: openrouter
```

**Setup:**
```bash
pip install goose-ai
sapiens credentials set openrouter api_key
# Get key from: https://openrouter.ai/keys
sapiens init
# Select: goose → openrouter
```

### Recommended OpenRouter Models

#### Proprietary Models (Best Tool Support)
| Model | Cost/1M tokens | Tool Support | Notes |
|-------|----------------|--------------|-------|
| `openai/gpt-4o` | ~$5 | Excellent | Best all-around |
| `anthropic/claude-3.5-sonnet` | ~$3 | Excellent | Great reasoning |
| `google/gemini-pro-1.5` | ~$3.50 | Very Good | Long context |

#### Open-Weight Models (Community/Self-Hostable)
| Model | Cost/1M tokens | Tool Support | Notes |
|-------|----------------|--------------|-------|
| `meta-llama/llama-3.1-405b-instruct` | ~$3 | Very Good | Best open model |
| `meta-llama/llama-3.1-70b-instruct` | ~$0.50 | Good | Great value |
| `qwen/qwen-2.5-72b-instruct` | ~$0.30 | Good | Strong coding |
| `mistralai/mixtral-8x22b-instruct` | ~$0.65 | Good | Fast, capable |
| `deepseek/deepseek-coder-33b-instruct` | ~$0.15 | Fair | Coding specialist |
| `mistralai/codestral-latest` | ~$0.30 | Good | Code generation |
| `google/gemma-2-27b-it` | ~$0.15 | Fair | Efficient |
| `meta-llama/llama-3.2-90b-vision-instruct` | ~$0.50 | Good | Multimodal |

**Open-weight config example:**
```yaml
agent_provider:
  provider_type: goose-local
  model: meta-llama/llama-3.1-70b-instruct
  api_key: "@keyring:openrouter/api_key"
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: openrouter
```

---

## 3. Goose + Groq (Best Speed)

**Best for:** Rapid prototyping, high-throughput tasks, fast iteration

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: goose-local
  model: llama-3.1-70b-versatile
  api_key: "@keyring:groq/api_key"
  local_mode: true
  goose_config:
    toolkit: default
    temperature: 0.7
    max_tokens: 4096
    llm_provider: groq
```

**Setup:**
```bash
pip install goose-ai
sapiens credentials set groq api_key
# Get key from: https://console.groq.com/keys (free tier available)
sapiens init
# Select: goose → groq
```

**Models:**
| Model | Speed | Quality | Notes |
|-------|-------|---------|-------|
| `llama-3.1-70b-versatile` | 300 tok/s | Very Good | Recommended |
| `llama-3.1-8b-instant` | 750 tok/s | Good | Ultra-fast |
| `mixtral-8x7b-32768` | 500 tok/s | Good | Long context |
| `llama-3.3-70b-versatile` | 275 tok/s | Excellent | Latest Llama |

---

## 4. Builtin + Ollama (Best Privacy)

**Best for:** Privacy-sensitive projects, offline use, zero cost

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: ollama
  model: qwen2.5-coder:14b
  api_key: null
  local_mode: true
  base_url: http://localhost:11434
```

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start server
ollama serve

# Pull a model (see VRAM guide below)
ollama pull qwen2.5-coder:14b

# Initialize
sapiens init
# Select: builtin → ollama
```

### VRAM Requirements by GPU

Choose your model based on available VRAM:

#### NVIDIA RTX 4000 Series

| GPU | VRAM | Recommended Models | Notes |
|-----|------|-------------------|-------|
| RTX 4060 | 8GB | `qwen2.5-coder:7b`, `codellama:7b`, `deepseek-coder:6.7b` | Entry-level, good for simple tasks |
| RTX 4060 Ti | 8-16GB | `qwen2.5-coder:14b`, `codellama:13b`, `deepseek-coder:16b` | Sweet spot for coding |
| RTX 4070 | 12GB | `qwen2.5-coder:14b`, `codellama:13b`, `mistral:7b` | Good balance |
| RTX 4070 Ti | 12GB | `qwen2.5-coder:14b`, `deepseek-coder:16b` | Same as 4070 |
| RTX 4080 | 16GB | `qwen2.5-coder:32b-q4`, `codellama:34b-q4`, `mixtral:8x7b-q4` | Quantized large models |
| RTX 4090 | 24GB | `qwen2.5-coder:32b`, `codellama:34b`, `deepseek-coder:33b` | Full large models |

#### NVIDIA RTX 5000 Series

| GPU | VRAM | Recommended Models | Notes |
|-----|------|-------------------|-------|
| RTX 5070 | 12GB | `qwen2.5-coder:14b`, `codellama:13b` | Similar to 4070 |
| RTX 5070 Ti | 16GB | `qwen2.5-coder:32b-q4`, `mixtral:8x7b-q4` | Quantized 32B models |
| RTX 5080 | 16GB | `qwen2.5-coder:32b-q4`, `codellama:34b-q4` | Same as 5070 Ti |
| RTX 5090 | 32GB | `qwen2.5-coder:32b`, `codellama:34b`, `llama3.1:70b-q4` | Full 32B, quantized 70B |

#### Model Size to VRAM Mapping

| Model Size | Min VRAM (Q4) | Recommended VRAM (Q8/FP16) |
|------------|---------------|---------------------------|
| 7B | 4-6GB | 8GB |
| 13-14B | 8-10GB | 14-16GB |
| 32-34B | 18-20GB | 24-32GB |
| 70B | 35-40GB | 48GB+ |

### Recommended Ollama Models by Task

| Model | Size | Best For | Pull Command |
|-------|------|----------|--------------|
| `qwen2.5-coder:7b` | 7B | Quick tasks, 8GB GPUs | `ollama pull qwen2.5-coder:7b` |
| `qwen2.5-coder:14b` | 14B | Balanced (recommended) | `ollama pull qwen2.5-coder:14b` |
| `qwen2.5-coder:32b` | 32B | Best local quality | `ollama pull qwen2.5-coder:32b` |
| `deepseek-coder-v2:16b` | 16B | Strong coding | `ollama pull deepseek-coder-v2:16b` |
| `codellama:13b` | 13B | Meta's coding model | `ollama pull codellama:13b` |
| `codellama:34b` | 34B | Larger codellama | `ollama pull codellama:34b` |
| `starcoder2:15b` | 15B | Code completion | `ollama pull starcoder2:15b` |

**Tip:** Use quantized versions (`:q4_K_M`) to fit larger models in less VRAM:
```bash
ollama pull qwen2.5-coder:32b-q4_K_M  # ~18GB instead of ~24GB
```

---

## 5. Builtin + vLLM (Best Local Quality)

**Best for:** Local inference with proper tool support, production local deployments

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: openai-compatible
  model: Qwen/Qwen2.5-Coder-32B-Instruct
  api_key: null
  local_mode: true
  base_url: http://localhost:8000/v1
```

**Setup:**
```bash
# Install vLLM
pip install vllm

# Start vLLM server (adjust GPU memory as needed)
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct \
  --port 8000 \
  --gpu-memory-utilization 0.9 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes

# Initialize
sapiens init
# Select: builtin → vllm
```

**Why vLLM over Ollama?**
- Better tool/function calling support
- Higher throughput
- More consistent outputs
- Production-ready

---

## 6. GitHub Copilot (Simplest)

**Best for:** Simple tasks, existing Copilot subscribers, GitHub ecosystem

```yaml
# .sapiens/config.yaml
agent_provider:
  provider_type: copilot-local
  model: gpt-4
  api_key: null
  local_mode: true
```

**Setup:**
```bash
# Install GitHub CLI
brew install gh  # or apt install gh

# Login and install extension
gh auth login
gh extension install github/gh-copilot

# Initialize
sapiens init
# Select: copilot
```

**Note:** Copilot has limited capabilities. See [COPILOT_SETUP.md](./COPILOT_SETUP.md) for details.

---

## Quick Decision Matrix

```
What's your priority?

Code Quality     → Claude Code (claude-sonnet-4)
Flexibility      → Goose + OpenRouter (claude-3.5-sonnet or llama-3.1-70b)
Speed            → Goose + Groq (llama-3.1-70b-versatile)
Privacy          → Builtin + Ollama (qwen2.5-coder:14b)
Local + Quality  → Builtin + vLLM (Qwen2.5-Coder-32B)
Budget           → Groq free tier or Ollama (free)
Simple           → Copilot (if you have subscription)
```

---

## Cost Comparison (per 1000 automation tasks)

| Setup | Estimated Cost |
|-------|----------------|
| Ollama / vLLM (local) | $0 (electricity only) |
| Groq (free tier) | $0 |
| Groq (paid) | ~$0.02 |
| OpenRouter (open-weight) | ~$0.05-0.15 |
| OpenRouter (proprietary) | ~$0.10-0.30 |
| Claude Code | ~$0.15-0.50 |
| GitHub Copilot | $10-39/month flat |

---

## Environment Variables Reference

For CI/CD or environment-based configuration:

```bash
# Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI (direct or via Goose)
export OPENAI_API_KEY="sk-..."

# OpenRouter
export OPENROUTER_API_KEY="sk-or-..."

# Groq
export GROQ_API_KEY="gsk_..."

# Gitea/GitHub token
export SAPIENS_GITEA_TOKEN="..."
export SAPIENS_GITHUB_TOKEN="..."
```

---

## See Also

- [AGENT_COMPARISON.md](./AGENT_COMPARISON.md) - Detailed agent comparison
- [GOOSE_SETUP.md](./GOOSE_SETUP.md) - Full Goose configuration guide
- [COPILOT_SETUP.md](./COPILOT_SETUP.md) - GitHub Copilot setup
- [CREDENTIALS.md](./CREDENTIALS.md) - Credential management
