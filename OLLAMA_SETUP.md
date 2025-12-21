# Using Builder with Ollama

This guide shows how to run the Builder Automation system with Ollama for completely local, offline AI inference.

## Why Ollama?

- ✅ **Free** - No API costs
- ✅ **Local** - Runs on your machine, no cloud needed
- ✅ **Private** - Your code never leaves your system
- ✅ **Offline** - Works without internet
- ✅ **Fast** - No network latency
- ✅ **Open Source** - Use any open model

## Prerequisites

### 1. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Or download from https://ollama.com/download
```

### 2. Start Ollama Server

```bash
ollama serve
```

Keep this running in a terminal.

### 3. Pull a Model

Recommended models for code/automation:

```bash
# Best for code (recommended)
ollama pull codellama:7b          # 4GB, fast
ollama pull codellama:13b         # 8GB, better quality
ollama pull codellama:34b         # 20GB, best quality

# General purpose models (also work well)
ollama pull llama3.1:8b           # 5GB, good balance
ollama pull llama3.1:70b          # 40GB, highest quality
ollama pull mistral:7b            # 4GB, fast and capable

# Specialized for following instructions
ollama pull qwen2.5-coder:7b      # 5GB, excellent for code
```

**Recommended for most users:**
```bash
ollama pull llama3.1:8b
```

## Configuration

### Option 1: Environment Variables

```bash
# Set Ollama as provider
export AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE=ollama
export AUTOMATION__AGENT_PROVIDER__MODEL=llama3.1:8b
export AUTOMATION__AGENT_PROVIDER__BASE_URL=http://localhost:11434

# Gitea config (as before)
export AUTOMATION__GIT_PROVIDER__BASE_URL=http://localhost:3000
export AUTOMATION__GIT_PROVIDER__API_TOKEN=your-token
export AUTOMATION__REPOSITORY__OWNER=myorg
export AUTOMATION__REPOSITORY__NAME=myrepo

# Run automation
automation process-all
```

### Option 2: Config File

Create `automation/config/ollama_config.yaml`:

```yaml
agent_provider:
  provider_type: ollama
  model: llama3.1:8b
  base_url: http://localhost:11434

git_provider:
  base_url: http://localhost:3000
  api_token: your-token

repository:
  owner: myorg
  name: myrepo
```

Then run:
```bash
automation --config automation/config/ollama_config.yaml process-all
```

### Option 3: Update .env File

```bash
# Edit .env
AGENT_TYPE=ollama
AGENT_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434

# Load and run
set -a; source .env; set +a
automation process-all
```

## Docker Setup with Ollama

### docker-compose.yml

```yaml
version: '3.8'

services:
  # Ollama service
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped

  # Builder automation
  builder:
    image: gitea-automation:latest
    depends_on:
      - ollama
    environment:
      - AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE=ollama
      - AUTOMATION__AGENT_PROVIDER__MODEL=llama3.1:8b
      - AUTOMATION__AGENT_PROVIDER__BASE_URL=http://ollama:11434
      - AUTOMATION__GIT_PROVIDER__BASE_URL=${GITEA_URL}
      - AUTOMATION__GIT_PROVIDER__API_TOKEN=${GITEA_TOKEN}
      - AUTOMATION__REPOSITORY__OWNER=${REPO_OWNER}
      - AUTOMATION__REPOSITORY__NAME=${REPO_NAME}
    volumes:
      - ./workspace:/workspace
    command: daemon --interval 60
    restart: unless-stopped

volumes:
  ollama-data:
```

### Setup and Run

```bash
# Start services
docker-compose up -d

# Pull model inside Ollama container
docker exec ollama ollama pull llama3.1:8b

# Check logs
docker-compose logs -f builder
```

## Gitea Actions Workflows with Ollama

Update workflow environment variables to use Ollama:

```yaml
# .gitea/workflows/needs-planning.yaml
- name: Start Ollama
  run: |
    ollama serve &
    sleep 5
    ollama pull llama3.1:8b

- name: Run automation
  env:
    AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: ollama
    AUTOMATION__AGENT_PROVIDER__MODEL: llama3.1:8b
    AUTOMATION__AGENT_PROVIDER__BASE_URL: http://localhost:11434
    AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.GITEA_URL }}
    AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
  run: |
    automation process-issue --issue ${{ gitea.event.issue.number }}
```

Or use Ollama as a service in Gitea Actions:

```yaml
jobs:
  automation:
    runs-on: ubuntu-latest

    services:
      ollama:
        image: ollama/ollama:latest
        ports:
          - 11434:11434

    steps:
      - uses: actions/checkout@v4

      - name: Pull Ollama model
        run: |
          curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3.1:8b"}'

      - name: Install automation
        run: pip install -e .

      - name: Run automation
        env:
          AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: ollama
          AUTOMATION__AGENT_PROVIDER__MODEL: llama3.1:8b
          AUTOMATION__AGENT_PROVIDER__BASE_URL: http://localhost:11434
        run: automation process-all
```

## Testing Your Setup

```bash
# 1. Check Ollama is running
curl http://localhost:11434/api/tags

# 2. Test model
ollama run llama3.1:8b "Write a hello world function in Python"

# 3. Test automation
automation --help

# 4. Process an issue
automation process-issue --issue 1
```

## Model Selection Guide

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| `codellama:7b` | 4GB | Fast | Good | Quick tasks, simple code |
| `codellama:13b` | 8GB | Medium | Better | General development |
| `codellama:34b` | 20GB | Slow | Best | Complex refactoring |
| `llama3.1:8b` | 5GB | Fast | Good | General purpose |
| `llama3.1:70b` | 40GB | Slow | Excellent | Maximum quality |
| `qwen2.5-coder:7b` | 5GB | Fast | Great | Code generation |
| `mistral:7b` | 4GB | Fast | Good | Balanced |

**Recommendations:**
- **8GB RAM**: Use `codellama:7b` or `mistral:7b`
- **16GB RAM**: Use `llama3.1:8b` or `codellama:13b`
- **32GB+ RAM**: Use `codellama:34b` or `llama3.1:70b`

## Performance Tips

### 1. Use GPU Acceleration

If you have an NVIDIA GPU:

```bash
# Ollama automatically uses GPU if available
nvidia-smi  # Check GPU is detected
ollama run llama3.1:8b  # Will use GPU
```

### 2. Adjust Context Length

For larger code files:

```bash
# Set in environment
export OLLAMA_NUM_CTX=8192  # Default is 2048
```

Or in API call:
```python
# In ollama.py, update the generate call
"options": {
    "num_ctx": 8192,
    "temperature": 0.7,
}
```

### 3. Pre-load Models

```bash
# Keep model in memory
ollama run llama3.1:8b --keepalive 24h
```

## Secrets Configuration

With Ollama, you **don't need** CLAUDE_API_KEY!

**Required secrets:**
- `GITEA_URL` - Your Gitea instance URL
- `GITEA_TOKEN` - Gitea API token

**NOT required:**
- ~~CLAUDE_API_KEY~~ (not needed with Ollama)

## Troubleshooting

### Ollama Not Running

**Error:** `Ollama not running at http://localhost:11434`

**Solution:**
```bash
ollama serve
# Or start as service
sudo systemctl start ollama  # Linux with systemd
```

### Model Not Found

**Error:** `Model llama3.1:8b not found`

**Solution:**
```bash
ollama pull llama3.1:8b
ollama list  # Check installed models
```

### Out of Memory

**Error:** Model fails to load

**Solutions:**
1. Use smaller model: `ollama pull codellama:7b`
2. Close other applications
3. Use quantized models (automatic with Ollama)

### Slow Response

**Solutions:**
1. Use GPU if available
2. Use smaller model
3. Reduce context length
4. Pre-load model: `ollama run model --keepalive 1h`

### Connection Refused in Docker

**Error:** Can't connect to Ollama from container

**Solution:**
```yaml
# Use service name in docker-compose
AUTOMATION__AGENT_PROVIDER__BASE_URL: http://ollama:11434
```

## Comparing Ollama vs Claude

| Feature | Ollama | Claude API |
|---------|--------|------------|
| **Cost** | Free | $0.003-0.015/1K tokens |
| **Privacy** | Local | Cloud |
| **Internet** | Not needed | Required |
| **Setup** | Install + download | API key only |
| **Speed** | Depends on hardware | Fast (cloud) |
| **Quality** | Good | Excellent |
| **Models** | Any open model | Claude only |

## Next Steps

1. ✅ Install Ollama
2. ✅ Pull a model
3. ✅ Configure builder to use Ollama
4. ✅ Remove CLAUDE_API_KEY requirement
5. ✅ Test with an issue

```bash
# Complete setup
ollama serve &
ollama pull llama3.1:8b

# Configure
export AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE=ollama
export AUTOMATION__AGENT_PROVIDER__MODEL=llama3.1:8b

# Test
automation process-issue --issue 1
```

That's it! You're now running builder completely locally with Ollama! 🚀
