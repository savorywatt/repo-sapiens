# Quick Start Guide

Get the builder automation running in 5 minutes!

## Option 1: One-Command Setup (Recommended)

```bash
# 1. Install
pip install repo-agent

# 2. Navigate to your Git repository
cd /path/to/your/repo

# 3. Initialize (interactive setup)
repo-agent init

# 4. Done! Now run the daemon
repo-agent daemon --interval 60
```

**That's it!** The init command will:
- Auto-discover your repository configuration
- **Detect and let you choose your AI agent** (Claude Code or Goose AI)
- **Select LLM provider** (for Goose: OpenAI, Anthropic, Ollama, OpenRouter, Groq)
- Prompt for credentials
- Store them securely
- Generate config file
- Guide you through Gitea Actions secrets setup

💡 **New to agent selection?** See [AGENT_COMPARISON.md](docs/AGENT_COMPARISON.md) to choose between Claude and Goose!

---

## Option 2: Docker (Easiest for CI/CD)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit with your credentials
nano .env  # Set GITEA_TOKEN, CLAUDE_API_KEY (or OPENAI_API_KEY for Goose), etc.

# 3. Run!
docker-compose up -d

# 4. Check logs
docker-compose logs -f builder
```

**That's it!** The automation is now running and will poll every 60 seconds.

---

## Option 3: Local Installation

```bash
# 1. Run setup script
./setup.sh

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Configure environment
cp .env.example .env
nano .env

# 4. Load environment and run
set -a; source .env; set +a
automation process-all
```

---

## Option 4: Direct Docker Run

```bash
docker run -it \
  -e AUTOMATION__GIT_PROVIDER__BASE_URL="http://gitea:3000" \
  -e AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token" \
  -e AUTOMATION__REPOSITORY__OWNER="myorg" \
  -e AUTOMATION__REPOSITORY__NAME="myrepo" \
  -e AUTOMATION__AGENT_PROVIDER__API_KEY="sk-ant-xxx" \
  -v $(pwd)/workspace:/workspace \
  gitea-automation:latest \
  process-all
```

---

## CLI Commands Cheat Sheet

```bash
# Process all issues
automation process-all

# Process issues with specific label
automation process-all --tag needs-planning

# Process single issue
automation process-issue --issue 42

# Run in daemon mode (poll every 60s)
automation daemon --interval 60

# List active plans
automation list-plans

# Show plan status
automation show-plan --plan-id 42

# Health check
automation health-check
```

---

## Environment Variables

**Required:**
```bash
AUTOMATION__GIT_PROVIDER__BASE_URL=http://gitea:3000
AUTOMATION__GIT_PROVIDER__API_TOKEN=your-token
AUTOMATION__REPOSITORY__OWNER=myorg
AUTOMATION__REPOSITORY__NAME=myrepo
```

**Optional:**
```bash
# For Claude API
AUTOMATION__AGENT_PROVIDER__API_KEY=sk-ant-xxx
# Or for Goose with OpenAI
AUTOMATION__AGENT_PROVIDER__API_KEY=sk-proj-xxx

AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS=3
```

---

## CI/CD Integration

For detailed CI/CD platform-specific guides, see [CI_CD_GUIDE.md](CI_CD_GUIDE.md)

**GitHub Actions:**
```yaml
- name: Run automation
  env:
    AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
  run: automation process-all
```

**GitLab CI:**
```yaml
automation:
  script:
    - pip install -e .
    - automation process-all
```

**Jenkins:**
```groovy
sh 'automation process-all'
```

---

## Troubleshooting

**Permission denied:**
```bash
chmod +x setup.sh
```

**Python not found:**
```bash
# Install Python 3.11+
sudo apt install python3.11 python3.11-venv
```

**Docker permission denied:**
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

**Environment variables not working:**
```bash
# Load .env file
set -a; source .env; set +a
```

---

## What It Does

The builder automation:

1. **Monitors** Gitea for issues with specific labels
2. **Creates** development plans using AI
3. **Breaks down** plans into executable tasks
4. **Implements** tasks using your chosen AI agent (Claude Code or Goose AI)
5. **Reviews** code changes automatically
6. **Runs** QA (builds and tests)
7. **Merges** completed work

All automatically, with minimal human intervention!

---

## Next Steps

1. ✅ Install (done!)
2. 📝 Configure your Gitea URL and token
3. 🏷️ Add `needs-planning` label to an issue
4. 🚀 Watch the magic happen!

For more details, see the full [README.md](README.md)
