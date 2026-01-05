# Getting Started with repo-sapiens

Welcome to repo-sapiens, an intelligent repository automation and management system powered by AI. This guide will help you get up and running in minutes.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start (5 minutes)](#quick-start-5-minutes)
4. [Configuration](#configuration)
5. [Basic Workflows](#basic-workflows)
6. [Common Tasks](#common-tasks)
7. [Troubleshooting](#troubleshooting)
8. [Next Steps](#next-steps)

---

## Introduction

### What is repo-sapiens?

repo-sapiens is an AI-driven automation system that transforms repository management from manual processes to intelligent, automated workflows. It helps you:

- **Automate issue processing** - Convert GitHub/Gitea issues into complete, tested implementations
- **Manage complex workflows** - Coordinate multi-step processes across repositories
- **Maintain code quality** - Automated planning, implementation, and code review
- **Scale efficiently** - Handle multiple repositories and concurrent tasks
- **Monitor everything** - Real-time health checks and comprehensive logging

### Key Features

- **Intelligent Planning**: Automatically generate development plans from issue descriptions
- **AI Implementation**: Execute tasks using Claude or other AI agents
- **Automated Code Review**: Review and test implementations before merge
- **State Management**: Track workflow progress with atomic, reliable state updates
- **Webhook Support**: Real-time event processing from your Git provider
- **Health Monitoring**: Built-in health checks and failure detection
- **Cost Optimization**: Intelligent AI model selection based on task complexity
- **Multi-Repository Support**: Coordinate workflows across multiple repositories
- **Parallel Execution**: Execute independent tasks concurrently
- **CI/CD Integration**: Native support for GitHub Actions, Gitea Actions, and more

### Use Cases

- **Feature Development**: Automate feature implementation from issue to deployment
- **Bug Triage**: Automatically classify, analyze, and attempt fixes for bug reports
- **Code Maintenance**: Keep dependencies updated, refactor code, optimize performance
- **Documentation**: Generate and maintain API documentation automatically
- **Quality Assurance**: Continuous testing and code quality improvements
- **DevOps Automation**: Manage infrastructure and deployment workflows

---

## Installation

### Prerequisites

Before installing repo-sapiens, ensure you have:

- **Python 3.11 or higher** - Check with: `python --version` or `python3 --version`
- **Git** - Check with: `git --version`
- **Access to a Git provider** - GitHub, Gitea, or GitLab
- **API tokens** - From your Git provider (and optionally from Claude API or other AI providers)

### Installing from PyPI

The easiest way to install repo-sapiens is from PyPI:

```bash
# Install the base package
pip install repo-sapiens

# Verify installation
sapiens --help
```

### Installing from Source

For development or to use the latest features:

**Option A: Using uv (Recommended)**

```bash
# Clone the repository
git clone https://github.com/savorywatt/repo-sapiens.git
cd repo-sapiens

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Verify installation
uv run sapiens --help
```

**Option B: Using pip**

```bash
# Clone the repository
git clone https://github.com/savorywatt/repo-sapiens.git
cd repo-sapiens

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Verify installation
sapiens --help
```

### Optional Dependencies

repo-sapiens supports optional feature groups:

```bash
# Install with monitoring support (Prometheus, health checks)
pip install repo-sapiens[monitoring]

# Install with analytics features (Plotly dashboards)
pip install repo-sapiens[analytics]

# Install development tools (pytest, black, mypy)
pip install repo-sapiens[dev]

# Install everything
pip install repo-sapiens[all]
```

### Checking Your Installation

```bash
# Display help and available commands
sapiens --help

# Expected output:
# Usage: sapiens [OPTIONS] COMMAND [ARGS]...
#
#   repo-sapiens: Intelligent repository automation CLI.
#
# Options:
#   --config TEXT     Path to configuration file
#   --log-level TEXT  Logging level
#   --help            Show this message and exit.
#
# Commands:
#   credentials      Manage credentials for the automation system
#   daemon           Run in daemon mode, polling for new issues
#   init             Initialize repo-sapiens in your Git repository
#   list-plans       List all active plans
#   process-all      Process all issues with optional tag filter
#   process-issue    Process a single issue manually
#   process-plan     Process entire plan end-to-end
#   react            Run a task using the ReAct agent
#   show-plan        Show detailed plan status
```

---

## Quick Start (5 minutes)

This section gets you from zero to running your first automation in 5 minutes.

### Step 1: Initialize Your Repository (Recommended)

The easiest way to set up repo-sapiens is with the interactive init command:

```bash
# Navigate to your Git repository
cd /path/to/your/repo

# Run interactive setup
sapiens init

# The wizard will:
# 1. Detect your Git remote (Gitea/GitHub)
# 2. Prompt for credentials
# 3. Let you choose an AI agent (Claude, Goose, or local Ollama)
# 4. Generate a configuration file
# 5. Optionally set up Gitea Actions secrets
```

See [INIT_COMMAND_GUIDE.md](./INIT_COMMAND_GUIDE.md) for detailed options.

### Alternative: Manual Configuration

If you prefer manual setup, create a configuration file:

```bash
# Create a new configuration file:
cat > sapiens_config.yaml << 'EOF'
git_provider:
  provider_type: gitea
  base_url: https://your-gitea-instance.com
  api_token: "${GITEA_API_TOKEN}"

repository:
  owner: your-org
  name: your-repo
  default_branch: main

agent_provider:
  provider_type: claude-api
  model: claude-sonnet-4-20250514
  api_key: "${CLAUDE_API_KEY}"

workflow:
  plans_directory: plans
  state_directory: .automation/state
  branching_strategy: per-agent
  max_concurrent_tasks: 3

tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
EOF
```

### Step 2: Set Up Credentials

You have three options for managing credentials. Choose the one that fits your environment:

#### Option A: Environment Variables (Simplest)

```bash
# For the current session (recommended for testing)
export GITEA_API_TOKEN="your-gitea-token-here"
export CLAUDE_API_KEY="your-claude-api-key-here"

# Verify configuration loads correctly
sapiens --config my_config.yaml list-plans
```

#### Option B: Keyring (Recommended for Desktop)

```bash
# Store credentials securely (encrypted by OS)
sapiens credentials set gitea/api_token --backend keyring
# Enter your Gitea token when prompted

sapiens credentials set claude/api_key --backend keyring
# Enter your Claude API key when prompted

# Update your config to use keyring references
cat > my_config.yaml << 'EOF'
git_provider:
  api_token: "@keyring:gitea/api_token"

agent_provider:
  api_key: "@keyring:claude/api_key"
# ... rest of config
EOF
```

#### Option C: Encrypted File (For Headless Servers)

```bash
# Set a master password (use a strong password!)
export SAPIENS_MASTER_PASSWORD="your-secure-password"

# Store credentials
sapiens credentials set gitea/api_token --backend encrypted
sapiens credentials set claude/api_key --backend encrypted

# Update config to use encrypted references
# api_token: "@encrypted:gitea/api_token"
```

### Step 3: Run Your First Command

List active automation plans:

```bash
sapiens --config my_config.yaml list-plans
```

Expected output:

```
Active Plans (0):

(No active plans found yet - this is normal for a fresh setup!)
```

### Step 4: Process Your First Issue

Create or find an issue in your repository, then process it:

```bash
# Process a specific issue (replace 1 with your issue number)
sapiens --config my_config.yaml process-issue --issue 1

# Watch the output:
# ✓ Loading issue #1...
# ✓ Generating development plan...
# ✓ Creating plan file (plans/1-feature.md)...
# ✓ Generating prompt issues...
# ✓ Processing tasks...
# ✓ Creating pull request...
# ✅ Issue #1 processed successfully
```

### Step 5: Check the Results

View the generated plan and track progress:

```bash
# List all active plans
sapiens --config my_config.yaml list-plans

# View status of a specific plan
sapiens --config my_config.yaml show-plan --plan-id 1

# Expected output:
# 📋 Plan 1 Status
#
# Overall Status: in_progress
# Created: 2025-12-23T10:15:30
# Updated: 2025-12-23T10:30:45
#
# Stages:
#   ✅ planning: completed
#   ⏳ implementation: in_progress
#   ⏳ code_review: pending
#   ⏳ merge: pending
#
# Tasks (8):
#   ✅ task-1: completed
#   🔄 task-2: in_progress
#   ⏳ task-3: pending
#   ...
```

---

## Configuration

### Configuration File Structure

The `automation_config.yaml` file controls all aspects of repo-sapiens behavior. Here's the complete structure:

```yaml
# Git Provider Configuration
# Supports: gitea, github
git_provider:
  provider_type: gitea
  mcp_server: null  # Optional: Name of MCP server for git ops
  base_url: https://your-gitea-instance.com
  api_token: "${GITEA_API_TOKEN}"  # See credential options below

# Repository Configuration
repository:
  owner: your-organization
  name: your-repository
  default_branch: main  # Default: main

# AI Agent Configuration
# Supports: claude-api, claude-local, openai, ollama
agent_provider:
  provider_type: claude-api
  model: claude-sonnet-4-20250514
  api_key: "${CLAUDE_API_KEY}"  # Optional: required for API providers
  local_mode: false  # Set to true to use local Claude Code CLI
  base_url: null  # Optional: for Ollama or custom endpoints

# Workflow Behavior
workflow:
  plans_directory: plans  # Where to store generated plans
  state_directory: .automation/state  # Where to track progress
  branching_strategy: per-agent  # or: shared
  max_concurrent_tasks: 3  # 1-10 recommended
  review_approval_threshold: 0.8  # 0.0-1.0 confidence for auto-approval

# Issue Labels for Workflow Stages
tags:
  needs_planning: needs-planning
  plan_review: plan-review
  ready_to_implement: ready-to-implement
  in_progress: in-progress
  review_ready: review-ready
  deployed: deployed
```

### Environment Variables

All configuration values can be overridden using environment variables with the `SAPIENS__` prefix. Use double underscores to indicate nesting:

```bash
# Git provider settings
export SAPIENS__GIT_PROVIDER__BASE_URL="https://your-gitea.com"
export SAPIENS__GIT_PROVIDER__API_TOKEN="your-token"

# Repository settings
export SAPIENS__REPOSITORY__OWNER="myorg"
export SAPIENS__REPOSITORY__NAME="myrepo"

# Agent settings
export SAPIENS__AGENT_PROVIDER__MODEL="claude-sonnet-4.5"
export SAPIENS__AGENT_PROVIDER__API_KEY="your-api-key"

# Workflow settings
export SAPIENS__WORKFLOW__MAX_CONCURRENT_TASKS="5"
export SAPIENS__WORKFLOW__PLANS_DIRECTORY="./my_plans"

# Logging level
export SAPIENS__LOG_LEVEL="DEBUG"
```

Use environment variables to:
- Override config file values
- Keep secrets out of version control
- Support different environments (dev, staging, production)

### Credential Management Options

repo-sapiens supports three secure credential storage methods:

#### 1. Keyring (Recommended for Desktop)

**Best for**: Local development on macOS, Linux, or Windows

Uses your operating system's native credential storage:
- macOS: Keychain
- Linux: Secret Service (GNOME/KDE)
- Windows: Credential Manager

**Setup**:

```bash
# Store a credential
sapiens credentials set gitea/api_token --backend keyring
# Enter your token at the interactive prompt

# Reference in config
git_provider:
  api_token: "@keyring:gitea/api_token"

# Verify it works
sapiens --config my_config.yaml list-plans
```

**Pros**:
- Secure OS-level encryption
- Biometric support (Touch ID, Windows Hello)
- Persists across reboots
- No password management needed

**Cons**:
- Only works on machines with graphical environments
- Not suitable for CI/CD (unless running on desktop)

#### 2. Environment Variables (Recommended for CI/CD)

**Best for**: GitHub Actions, GitLab CI, Gitea Actions, Jenkins

**Setup**:

```bash
# For current session (testing)
export GITEA_API_TOKEN="your-token"
export CLAUDE_API_KEY="your-api-key"

# Reference in config
git_provider:
  api_token: "${GITEA_API_TOKEN}"

agent_provider:
  api_key: "${CLAUDE_API_KEY}"
```

**In CI/CD platforms** (example: Gitea Actions):

```yaml
name: Automation Workflow
on:
  issues:
    types: [opened, labeled]

jobs:
  automate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install repo-sapiens
        run: pip install repo-sapiens

      - name: Run automation
        env:
          GITEA_API_TOKEN: ${{ secrets.GITEA_API_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: sapiens --config my_config.yaml process-all
```

**Pros**:
- Native CI/CD support
- No additional setup
- Simple and reliable
- Standard across all platforms

**Cons**:
- Not persisted locally
- Less secure than keyring for unattended access
- Requires CI/CD secret management

#### 3. Encrypted File (For Headless Servers)

**Best for**: Self-hosted servers, Docker containers

**Setup**:

```bash
# Set a master password (use a strong password!)
export SAPIENS_MASTER_PASSWORD="your-very-secure-password-here"

# Store credentials
sapiens credentials set gitea/api_token --backend encrypted
sapiens credentials set claude/api_key --backend encrypted

# Reference in config
git_provider:
  api_token: "@encrypted:gitea/api_token"

agent_provider:
  api_key: "@encrypted:claude/api_key"
```

**For Docker**:

```dockerfile
FROM python:3.11-slim

# ... install repo-sapiens ...

# Store encrypted credentials during build
ARG SAPIENS_MASTER_PASSWORD
RUN SAPIENS_MASTER_PASSWORD=$SAPIENS_MASTER_PASSWORD \
    sapiens credentials set gitea/api_token --backend encrypted \
    && sapiens credentials set claude/api_key --backend encrypted

# Master password provided at runtime
ENV SAPIENS_MASTER_PASSWORD=<runtime-secret>

CMD ["sapiens", "--config", "my_config.yaml", "daemon", "--interval", "60"]
```

**Pros**:
- Works on any system (no graphical UI needed)
- File-based persistence
- Container-friendly

**Cons**:
- Requires master password management
- Less secure if master password is compromised
- Requires storing encrypted files in version control

### Choosing a Credential Method

Use this decision tree:

```
Are you running on a personal/development machine?
├─ Yes → Use Keyring (most secure, easiest)
└─ No
    ├─ Is this CI/CD? → Use Environment Variables
    └─ Is this a headless server? → Use Encrypted File
```

---

## Basic Workflows

### Workflow 1: Automating Issue Processing

Process a single issue from creation to implementation:

```bash
# Step 1: Identify an issue you want to automate
# (Look in your repository for issues labeled "needs-planning")

# Step 2: Process the issue
sapiens --config my_config.yaml process-issue --issue 42

# Step 3: Monitor progress
sapiens --config my_config.yaml show-plan --plan-id 42

# Step 4: The automation will:
#   ✅ Generate a development plan
#   ✅ Create a plan document (plans/42-*.md)
#   ✅ Generate prompt issues for each task
#   ✅ Execute tasks with AI agents
#   ✅ Run code review
#   ✅ Create a pull request
```

**Configuration for Issue Processing**:

```yaml
# In my_config.yaml
workflow:
  plans_directory: plans  # Plans stored here
  state_directory: .automation/state  # Progress tracked here
  branching_strategy: per-agent  # One branch per AI agent
  max_concurrent_tasks: 3  # How many tasks to run in parallel

tags:
  needs_planning: needs-planning
  ready_to_implement: ready-to-implement
```

### Workflow 2: Using Daemon Mode

Run continuous automation that processes new issues automatically:

```bash
# Start the daemon (runs indefinitely)
sapiens --config my_config.yaml daemon --interval 60

# Output:
# 🤖 Starting daemon mode (polling every 60s)
# 🔄 Polling for issues...
# ✅ Poll complete. Waiting 60s...
# 🔄 Polling for issues...
# (processes any new issues automatically)

# Stop with Ctrl+C
# 👋 Shutting down daemon...
```

**Daemon Configuration**:

```yaml
# In my_config.yaml
workflow:
  # Issues will be automatically discovered and processed
  # based on their labels
  tags:
    needs_planning: needs-planning  # Issues with this label are processed
```

**Running in the Background** (Linux/macOS):

```bash
# Using nohup
nohup sapiens --config my_config.yaml daemon --interval 60 > sapiens.log 2>&1 &

# Using systemd (create /etc/systemd/system/sapiens.service)
[Unit]
Description=repo-sapiens Automation Daemon
After=network.target

[Service]
Type=simple
User=sapiens
ExecStart=/usr/local/bin/sapiens --config /etc/sapiens/config.yaml daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable sapiens
sudo systemctl start sapiens
sudo systemctl status sapiens
```

### Workflow 3: Using the ReAct Agent

Run local AI-powered tasks without external API costs using the built-in ReAct agent:

```bash
# Start Ollama (if not already running)
ollama serve &
ollama pull qwen3:latest

# Run a single task
sapiens react "Create a Python function that calculates fibonacci numbers"

# Start interactive REPL mode
sapiens react --repl

# Use with verbose output to see reasoning
sapiens react -v "List all Python files and summarize their purpose"
```

**ReAct Agent Features**:

- **Local inference**: Uses Ollama or vLLM for free, private execution
- **Built-in tools**: File operations, shell commands, code search
- **Transparent reasoning**: See step-by-step thinking with `-v` flag
- **Interactive mode**: Explore tasks in REPL mode

See [AGENT_COMPARISON.md](./AGENT_COMPARISON.md) for more agent options.

---

## Common Tasks

### Task 1: List Active Plans

View all automation plans currently in progress:

```bash
sapiens --config my_config.yaml list-plans

# Output:
# Active Plans (3):
#
#   • Plan 42: in_progress
#   • Plan 43: completed
#   • Plan 44: failed
```

### Task 2: Process a Specific Issue

Manually trigger automation for a single issue:

```bash
sapiens --config my_config.yaml process-issue --issue 42

# Or with custom configuration
sapiens --config my_config.yaml \
  --log-level DEBUG \
  process-issue --issue 42

# Output:
# ✓ Loading configuration...
# ✓ Connecting to Gitea...
# ✓ Fetching issue #42...
# ✓ Generating development plan...
# ✓ Creating plan file (plans/42-feature.md)
# ✓ Processing tasks...
# ✓ Creating pull request...
# ✅ Issue #42 processed successfully
```

### Task 3: Test Credentials

Verify your credentials are properly configured:

```bash
sapiens credentials test

# Output:
# Testing credential backends...
# ✅ Keyring: Available
# ✅ Environment: Available
# ✅ Encrypted: Available
#
# All credential systems operational
```

### Task 4: View Detailed Plan Status

Get complete status of a plan including all stages and tasks:

```bash
sapiens --config my_config.yaml show-plan --plan-id 42

# Output:
# 📋 Plan 42 Status
#
# Overall Status: in_progress
# Created: 2025-12-23T10:15:30
# Updated: 2025-12-23T10:30:45
#
# Stages:
#   ✅ planning: completed
#   🔄 implementation: in_progress
#   ⏳ code_review: pending
#   ⏳ merge: pending
#
# Tasks (8):
#   ✅ task-1: completed (duration: 45s)
#   🔄 task-2: in_progress (elapsed: 23s)
#   ⏳ task-3: pending
#   ⏳ task-4: pending
```

### Task 5: View Logs

Enable debug logging to troubleshoot issues:

```bash
# Enable debug logging for a single command
sapiens --log-level DEBUG \
  --config my_config.yaml \
  process-issue --issue 42

# Logs show:
# 2025-12-23 10:15:30 INFO Loading configuration: my_config.yaml
# 2025-12-23 10:15:31 DEBUG Connecting to Git provider: https://gitea.com
# 2025-12-23 10:15:32 DEBUG Git provider connected successfully
# 2025-12-23 10:15:33 DEBUG Fetching issue #42 from repository
# 2025-12-23 10:15:34 DEBUG Issue #42: "Add dark mode support"
# ...
```

**Available Log Levels**:
- `DEBUG` - Detailed diagnostic information
- `INFO` - General informational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages

### Task 6: Process All Issues with a Tag

Batch process multiple issues at once:

```bash
# Process all issues with a specific label
sapiens --config my_config.yaml process-all --tag needs-planning

# Process all issues (ignores tags)
sapiens --config my_config.yaml process-all

# Monitor multi-issue processing
# (Each issue processed sequentially or in parallel based on settings)
```

---

## Troubleshooting

### Common Errors and Solutions

#### Error: "Configuration file not found"

**Problem**: `Error: Configuration file not found: my_config.yaml`

**Solutions**:

```bash
# Check file exists
ls -la my_config.yaml

# Use absolute path
sapiens --config /full/path/to/my_config.yaml list-plans

# Use default location
cp my_config.yaml repo_sapiens/config/automation_config.yaml
sapiens list-plans  # Uses default config
```

#### Error: "API token not found"

**Problem**: `Error: API token not found or invalid`

**Solutions**:

```bash
# Check environment variable
echo $GITEA_API_TOKEN
# Should output your token

# Or set it
export GITEA_API_TOKEN="your-token-here"

# Or use keyring
sapiens credentials set gitea/api_token --backend keyring
# And reference it: api_token: "@keyring:gitea/api_token"

# Verify credentials are set up
sapiens credentials test
```

#### Error: "Connection refused"

**Problem**: `Connection refused` when connecting to Git provider

**Solutions**:

```bash
# Check URL in config
grep base_url my_config.yaml

# Test connectivity
curl https://your-gitea-instance.com/api/v1/user

# Verify network access
ping your-gitea-instance.com

# Check if VPN/proxy is required
# (Configure in environment or config as needed)
```

#### Error: "Plan file not found"

**Problem**: `FileNotFoundError: plan file not found`

**Solutions**:

```bash
# Check plans directory exists
ls -la plans/

# Create it if missing
mkdir -p plans

# Or change in config
workflow:
  plans_directory: ./my_plans  # Your custom directory
```

#### Error: "State file conflict"

**Problem**: `Error: State file is locked (another process is running)`

**Solutions**:

```bash
# Wait for the other process to complete
# (Check process list)
ps aux | grep sapiens

# Or remove stale lock file
rm -f .automation/state/*.lock

# Check permissions on state directory
ls -la .automation/state/
chmod 755 .automation/state
```

### Debug Logging

Enable detailed logging to diagnose issues:

```bash
# Enable debug logging with file output
sapiens --log-level DEBUG \
  --config my_config.yaml \
  process-issue --issue 42 \
  > sapiens-debug.log 2>&1

# View the log
tail -f sapiens-debug.log

# Search for errors
grep ERROR sapiens-debug.log

# View timing information
grep -E "(Started|Completed)" sapiens-debug.log
```

### Enable Structured Logging

The system uses structured logging (JSON format) for easier analysis:

```bash
# Logs are automatically formatted as JSON
# View with jq for pretty printing
tail -f sapiens.log | jq '.'

# Filter by log level
tail -f sapiens.log | jq 'select(.level=="ERROR")'

# Filter by module
tail -f sapiens.log | jq 'select(.module=="orchestrator")'
```

### Getting Help

When you need assistance:

1. **Review logs** - Enable debug logging and check error messages
2. **Test credentials** - Run `sapiens credentials test`
3. **Check configuration** - Verify your config file syntax with `sapiens --config my_config.yaml list-plans`
4. **Open an issue** - https://github.com/savorywatt/repo-sapiens/issues
5. **Check documentation** - https://github.com/savorywatt/repo-sapiens#readme

---

## Next Steps

### Advanced Configuration

Once you're comfortable with the basics, explore:

- **Custom Templates**: Modify plan and prompt templates in `repo_sapiens/templates/`
- **Workflow Customization**: Adjust stages and workflow behavior in configuration
- **Multiple Repositories**: Configure automation for multiple repos simultaneously
- **Cost Optimization**: Fine-tune AI model selection for cost/quality tradeoff
- **Monitoring**: Enable Prometheus metrics for production deployments

See: [ARCHITECTURE.md](./ARCHITECTURE.md) for system design details.

### CI/CD Integration

Set up automated workflows:

- **GitHub Actions**: Trigger automation on issue events
- **Gitea Actions**: Native integration with Gitea workflows
- **GitLab CI**: Schedule automation jobs
- **Jenkins**: Integrate with Jenkins pipelines

**Multi-Environment Setup**: Use different agents for local vs CI/CD:

```bash
# Create local config (free, private with Ollama)
sapiens init --config-path sapiens_config.yaml
# Choose: Ollama

# Create CI/CD config (better quality with Goose/Claude)
sapiens init --config-path sapiens_config.ci.yaml
# Choose: Goose → OpenAI
```

Then in your workflow: `sapiens --config sapiens_config.ci.yaml process-all`

See: [ci-cd-usage.md](./ci-cd-usage.md) for complete CI/CD setup

### Template Customization

Customize how plans and prompts are generated:

- **Plan Templates**: Modify `repo_sapiens/templates/plan.j2`
- **Prompt Templates**: Modify `repo_sapiens/templates/prompt.j2`
- **Custom Stages**: Add custom workflow stages
- **Custom Tags**: Define custom issue labels and their meaning

See: The `repo_sapiens/templates/` directory for Jinja2 templates.

### Monitoring and Observability

Monitor production deployments:

- **Prometheus Metrics**: Expose metrics for Prometheus scraping
- **Health Checks**: Automated monitoring endpoints
- **Alerting**: Set up alerts for failures
- **Dashboards**: Create dashboards from metrics

See: Install with `pip install repo-sapiens[monitoring]` for Prometheus support.

### Production Deployment

Deploy to production safely:

- **Docker**: Use Docker for containerized deployments
- **Kubernetes**: Deploy to Kubernetes clusters
- **Security**: Hardening and security best practices
- **High Availability**: Multi-instance setup with shared state
- **Backup & Recovery**: State backup and disaster recovery

See: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

### API Reference

Integrate with other systems:

- **REST API**: HTTP API for integrations
- **Event Webhooks**: Custom event processing
- **Python SDK**: Use repo-sapiens as a library
- **Plugin System**: Extend functionality with plugins

See: [ARCHITECTURE.md](./ARCHITECTURE.md) for module structure.

---

## Key Resources

- **Homepage**: https://github.com/savorywatt/repo-sapiens
- **Documentation**: https://github.com/savorywatt/repo-sapiens#readme
- **Issue Tracker**: https://github.com/savorywatt/repo-sapiens/issues
- **PyPI Package**: https://pypi.org/project/repo-sapiens/
- **Discussions**: https://github.com/savorywatt/repo-sapiens/discussions

## Quick Command Reference

```bash
# Installation
pip install repo-sapiens

# Setup
sapiens init                                 # Interactive setup wizard
sapiens init --non-interactive               # CI/CD setup (uses env vars)

# Basic commands
sapiens --help                               # Show all commands
sapiens list-plans                           # List active plans
sapiens show-plan --plan-id 42               # View plan status
sapiens process-issue --issue 42             # Process one issue
sapiens process-all                          # Process all issues
sapiens daemon --interval 60                 # Run continuous automation

# ReAct agent (local execution with Ollama)
sapiens react --repl                         # Interactive REPL mode
sapiens react "task description"             # Run single task
sapiens react -v "task"                      # Verbose mode (show reasoning)
sapiens react --backend openai --base-url http://localhost:8000/v1 "task"  # Use vLLM

# Credentials management
sapiens credentials test                     # Test credential backends
sapiens credentials set gitea/api_token      # Store a credential
sapiens credentials get gitea/api_token      # Retrieve a credential

# Configuration
sapiens --config custom_config.yaml list-plans  # Use custom config
sapiens --log-level DEBUG process-issue --issue 42  # Debug logging
```

## Support

Having trouble? Here's how to get help:

1. **Check the docs** - Most questions are answered in the documentation
2. **Review logs** - Enable debug logging to see what's happening
3. **Test credentials** - Run `sapiens credentials test`
4. **Open an issue** - Include logs and your configuration (without secrets!)

---

**Ready to go?** Start with [Quick Start (5 minutes)](#quick-start-5-minutes) above, or see the [Configuration](#configuration) section for detailed setup instructions.

**Have questions?** Check [Troubleshooting](#troubleshooting) or [Getting Help](#getting-help).

**Want advanced features?** Explore [Next Steps](#next-steps) for CI/CD, monitoring, and more.
