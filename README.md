# repo-sapiens

> *The evolved, intelligent way to manage repositories*

A production-ready AI-driven automation system for Git workflows with advanced error recovery, parallel execution, multi-repository support, comprehensive monitoring, and intelligent cost optimization.

## 🚀 Quick Start for CI/CD

**Want to run this in CI/CD? It's easy!**

```bash
# Docker (recommended)
docker-compose up -d

# Or pip install
pip install -e .
automation daemon --interval 60
```

📚 **See [Getting Started](docs/GETTING_STARTED.md)** for setup guide
📦 **See [CI/CD Usage](docs/ci-cd-usage.md)** for platform-specific guides

---

## Overview

This automation system transforms Git issues into fully implemented features through an AI-powered workflow that includes planning, implementation, code review, and deployment.

**Supports both GitHub and Gitea** - Works seamlessly with GitHub repositories and GitHub Actions, or Gitea repositories with Gitea Actions.

### Phase 4 Enhancements

Phase 4 adds enterprise-grade features for production readiness:

- **Advanced Error Recovery**: Checkpoint-based recovery with multiple strategies
- **Parallel Execution**: Intelligent task scheduling with dependency management
- **Multi-Repository Support**: Coordinate workflows across multiple repositories
- **Performance Optimizations**: Caching, connection pooling, and batch operations
- **Monitoring & Analytics**: Prometheus metrics and interactive dashboard
- **Cost Optimization**: Intelligent AI model selection based on task complexity
- **Learning System**: Continuous improvement through feedback analysis

## Features

- **Multi-Platform Git Support**: Works with both **GitHub** and **Gitea**
  - Auto-detects provider from repository
  - GitHub Actions or Gitea Actions workflows
  - Platform-specific API integration
- **Automated Planning**: Generate development plans from issue descriptions
- **Task Decomposition**: Break plans into manageable, executable tasks
- **Multi-Agent AI**: Execute tasks using **Claude Code** or **Goose AI** with multiple LLM backends
  - **Claude Code**: Best-in-class coding with Anthropic models
  - **Goose AI**: Flexible provider choice (OpenAI, Anthropic, Ollama, OpenRouter, Groq, Databricks)
  - Switch between agents or use different providers per repository
- **Code Review**: Automated code review before merging
- **CI/CD Integration**: Full GitHub Actions or Gitea Actions workflows
- **State Management**: Track workflow progress with atomic state updates
- **Webhook Support**: Real-time event processing via webhooks
- **Health Monitoring**: Automated health checks and failure detection

## Quick Start

### Installation

```bash
# Install from PyPI
pip install repo-sapiens

# Or install from source
git clone https://github.com/savorywatt/repo-sapiens.git
cd repo-sapiens

# Install dependencies
pip install -e .

# Install development dependencies (optional)
pip install -e ".[dev]"
```

### Configuration

**Recommended: One-Command Setup**

```bash
# Initialize in your Git repository (interactive)
automation init
```

This will:
- Auto-discover your Git repository configuration (GitHub or Gitea)
- **Detect and select AI agent** (Claude Code or Goose AI)
- **Choose LLM provider** (for Goose: OpenAI, Anthropic, Ollama, OpenRouter, Groq)
- Prompt for credentials and store them securely
- Generate configuration file
- Help set up GitHub Actions or Gitea Actions secrets

📚 **Agent Selection Help**:
- See [AGENT_COMPARISON.md](docs/AGENT_COMPARISON.md) to choose between Claude and Goose
- See [GOOSE_SETUP.md](docs/GOOSE_SETUP.md) for Goose-specific configuration

**Manual Setup (Alternative)**

1. Copy and edit configuration:
   ```bash
   cp repo_sapiens/config/automation_config.yaml repo_sapiens/config/my_config.yaml
   ```

2. Set environment variables:
   ```bash
   export GITEA_TOKEN="your-gitea-token"
   export CLAUDE_API_KEY="your-claude-api-key"
   ```

3. Test configuration:
   ```bash
   automation --config repo_sapiens/config/my_config.yaml list-plans
   ```

### Basic Usage

```bash
# List active plans
automation list-active-plans

# Process a specific issue
automation process-issue --issue 42 --stage planning

# Generate prompts from plan
automation generate-prompts --plan-file plans/42-feature.md --plan-id 42

# Check system health
automation health-check

# Check for stale workflows
automation check-stale --max-age-hours 24
```

## Architecture

### Components

```
repo_sapiens/
├── config/           # Configuration management
├── models/           # Domain models (Issue, Task, Plan, etc.)
├── providers/        # Git and AI provider implementations
├── engine/           # Workflow orchestration and state management
├── processors/       # Task processing and dependency tracking
├── utils/            # Utilities (logging, status reporting)
└── main.py           # CLI entry point
```

### Workflow Stages

1. **Planning**: Generate development plan from issue
2. **Plan Review**: Review and approve plan
3. **Prompts**: Generate prompt issues for tasks
4. **Implementation**: Execute tasks with AI agents
5. **Code Review**: Automated code review
6. **Merge**: Create pull request for completed work

## CI/CD Integration

### GitHub Actions / Gitea Actions Workflows

The system includes workflow templates that work with both GitHub Actions and Gitea Actions:

1. **automation-trigger.yaml**: Processes issues based on labels
2. **plan-merged.yaml**: Generates prompts when plans merge
3. **automation-daemon.yaml**: Periodically processes pending issues
4. **monitor.yaml**: Health monitoring and failure detection
5. **test.yaml**: Runs tests on PRs and pushes

### Setup

1. Configure secrets in your repository settings:
   - **For GitHub**: `GITHUB_TOKEN` (automatically provided) or personal access token
   - **For Gitea**: `GITEA_TOKEN` (Gitea API token with repo access)
   - **For Claude Code**: `CLAUDE_API_KEY` (Anthropic Claude API key)
   - **For Goose**: Provider-specific key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.)

2. Workflows trigger automatically on:
   - Issue events (opened, labeled, etc.)
   - Plan file merges to main
   - Scheduled intervals (cron)

3. Workflow files location:
   - **GitHub**: `.github/workflows/`
   - **Gitea**: `.gitea/workflows/`

See [CI/CD Usage Guide](docs/ci-cd-usage.md) for detailed instructions.

## Webhook Server

Optional webhook server for real-time event processing:

```bash
# Run webhook server
uvicorn automation.webhook_server:app --host 0.0.0.0 --port 8000

# Or with gunicorn for production
gunicorn automation.webhook_server:app -w 4 -k uvicorn.workers.UvicornWorker
```

Configure webhook in Gitea:
- URL: `https://your-server.com/webhook/gitea`
- Content Type: `application/json`
- Events: Issues, Push

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=automation --cov-report=html

# Run specific test file
pytest tests/unit/test_state_manager.py -v
```

### Code Quality

```bash
# Format code
black repo_sapiens/ tests/

# Lint code
ruff check repo_sapiens/ tests/

# Type check
mypy repo_sapiens/
```

### Project Structure

```
.
├── .gitea/workflows/      # Gitea Actions workflows
├── repo_sapiens/          # Main package
│   ├── config/           # Configuration
│   ├── engine/           # Workflow engine
│   ├── models/           # Domain models
│   ├── providers/        # Provider implementations
│   ├── processors/       # Task processors
│   └── utils/            # Utilities
├── docs/                 # Documentation
├── plans/                # Development plans
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── fixtures/        # Test fixtures
└── .automation/state/    # Workflow state files
```

## Configuration

### Configuration File

The system uses YAML configuration with environment variable interpolation:

```yaml
git_provider:
  type: gitea
  base_url: ${GITEA_BASE_URL:-https://gitea.example.com}
  api_token: ${GITEA_TOKEN}

agent_provider:
  type: claude
  model: claude-sonnet-4.5
  api_key: ${CLAUDE_API_KEY}

workflow:
  branching_strategy: per-agent
  max_concurrent_tasks: 3
  parallel_execution: true
```

### Environment Variables

All settings can be overridden via environment variables with `AUTOMATION__` prefix:

```bash
export AUTOMATION__GIT_PROVIDER__API_TOKEN="token"
export AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS="5"
export AUTOMATION__CICD__TIMEOUT_MINUTES="60"
```

## State Management

Workflow state is stored in `.automation/state/` as JSON files:

```json
{
  "plan_id": "42",
  "status": "in_progress",
  "created_at": "2025-12-20T10:00:00",
  "updated_at": "2025-12-20T10:30:00",
  "stages": {
    "planning": {"status": "completed", "data": {}},
    "implementation": {"status": "in_progress", "data": {}}
  },
  "tasks": {},
  "metadata": {}
}
```

State updates are atomic using file locking and temporary files.

## Monitoring

### Health Checks

```bash
# Generate health report
automation health-check

# Check for failures
automation check-failures --since-hours 24

# Check for stale workflows
automation check-stale --max-age-hours 24
```

### Viewing State

```bash
# List active plans
automation list-active-plans

# View state file directly
cat .automation/state/42.json | jq .
```

## Documentation

### Getting Started
- [Quick Start Guide](QUICK_START.md) - 5-minute setup walkthrough
- [Credential Quick Start](docs/CREDENTIAL_QUICK_START.md) - Secure credential management

### AI Agent Selection
- [Agent Comparison](docs/AGENT_COMPARISON.md) - **Choose between Claude Code and Goose AI**
- [Goose Setup Guide](docs/GOOSE_SETUP.md) - Complete Goose AI configuration guide
- [INIT Command Guide](docs/INIT_COMMAND_GUIDE.md) - Using `automation init`

### Advanced Configuration
- [Secrets Setup Guide](docs/secrets-setup.md) - Configure CI/CD secrets
- [CI/CD Usage Guide](docs/ci-cd-usage.md) - Using workflows and CLI
- [Phase 3 Implementation Plan](plans/automation/phase-3-gitea-actions.md) - Detailed implementation guide

## Troubleshooting

### Common Issues

**Workflow doesn't trigger:**
- Check Gitea Actions is enabled
- Verify webhook configuration
- Check runner availability

**Permission errors:**
- Verify GITEA_TOKEN has correct scopes
- Check repository permissions
- Ensure secrets are configured

**State conflicts:**
- Only one process should access state at a time
- Use file locking in state manager
- Check for stale lock files

### Debug Mode

Enable detailed logging:

```bash
automation --log-level DEBUG process-issue --issue 42 --stage planning
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

This system is designed to be extended with:

- Additional workflow stages
- Additional git providers (GitLab, Bitbucket, etc.)
- Alternative AI agents (OpenAI, local models)
- Enhanced error recovery
- Performance optimizations

**Note**: GitHub and Gitea are fully supported. GitLab and other providers can be added following the provider pattern in `repo_sapiens/providers/`.

For bugs, feature requests, or questions, please [open an issue](https://github.com/savorywatt/repo-sapiens/issues) on GitHub.

## Links

- **GitHub Repository**: [https://github.com/savorywatt/repo-sapiens](https://github.com/savorywatt/repo-sapiens)
- **Issue Tracker**: [https://github.com/savorywatt/repo-sapiens/issues](https://github.com/savorywatt/repo-sapiens/issues)
- **PyPI Package**: [https://pypi.org/project/repo-sapiens/](https://pypi.org/project/repo-sapiens/)

## Author

Maintained by [@savorywatt](https://github.com/savorywatt)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on [GitHub Issues](https://github.com/savorywatt/repo-sapiens/issues)
- Check the documentation in `docs/`
- Review workflow logs in Actions
