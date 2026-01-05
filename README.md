# repo-sapiens

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/repo-sapiens.svg)](https://pypi.org/project/repo-sapiens/)
[![Documentation Status](https://readthedocs.org/projects/repo-sapiens/badge/?version=latest)](https://repo-sapiens.readthedocs.io/en/latest/?badge=latest)

> *The evolved, intelligent way to manage repositories*

An AI-driven automation system for Git workflows with support for multiple AI agents, Git providers, and deployment modes.

## Features

### Implemented

- **Multi-Platform Git Support**: Works with both **GitHub** and **Gitea**
  - Auto-detects provider from repository remote URL
  - GitHub Actions or Gitea Actions workflow templates
  - Platform-specific API integration

- **Multiple AI Agent Support**
  - **Claude Code**: Anthropic's coding assistant
  - **Goose AI**: Block's flexible agent with multiple LLM backends (OpenAI, Anthropic, Ollama, OpenRouter, Groq)
  - **ReAct Agent**: Local AI agent using Ollama for autonomous coding tasks
    - Interactive REPL mode with 9 built-in tools
    - Remote Ollama support for GPU servers
    - Path sandboxing for security

- **Workflow Automation**
  - Label-triggered workflows for issue processing
  - Development plan generation from issues
  - Task decomposition and execution
  - Automated code review
  - PR creation and management

- **CLI Commands**
  - `sapiens init` - Interactive repository setup with agent selection
  - `sapiens react --repl` - Interactive ReAct agent REPL
  - `sapiens daemon` - Run automation daemon
  - `sapiens credentials` - Manage credentials securely
  - `sapiens process-issue` - Process a specific issue
  - `sapiens health-check` - System health monitoring

- **Developer Experience**
  - 63% test coverage with 936+ unit tests
  - Type hints throughout (mypy strict mode)
  - Pre-commit hooks for code quality
  - Comprehensive documentation

## Quick Start

### Installation

```bash
# Install from PyPI
pip install repo-sapiens

# Or install from source
git clone https://github.com/savorywatt/repo-sapiens.git
cd repo-sapiens
pip install -e ".[dev]"
```

### Interactive Setup

```bash
# Initialize in your Git repository
sapiens init
```

This will:
- Auto-discover your Git repository configuration (GitHub or Gitea)
- Detect and select AI agent (Claude Code, Goose AI, or ReAct)
- Configure LLM provider settings
- Store credentials securely
- Generate configuration file
- Set up CI/CD workflow secrets

### ReAct Agent REPL

Try the local AI agent with Ollama:

```bash
# Start interactive REPL (uses qwen3:latest by default)
sapiens react --repl

# Use a remote Ollama server
sapiens react --repl --ollama-url http://192.168.1.100:11434

# Use a specific model
sapiens react --repl --model codellama:13b
```

REPL commands:
- `/help` - Show available commands
- `/models` - List available Ollama models
- `/model <name>` - Switch to a different model
- `/pwd` - Show current working directory
- `/verbose` - Toggle verbose output
- `/quit` - Exit REPL

### Basic CLI Usage

```bash
# List active plans
sapiens list-active-plans

# Process a specific issue
sapiens process-issue --issue 42 --stage planning

# Check system health
sapiens health-check

# Check for stale workflows
sapiens check-stale --max-age-hours 24

# Run as daemon
sapiens daemon --interval 60
```

## Configuration

### Configuration File

Located at `repo_sapiens/config/automation_config.yaml`:

```yaml
git_provider:
  type: gitea  # or 'github'
  base_url: ${GITEA_BASE_URL:-https://gitea.example.com}
  api_token: ${GITEA_TOKEN}

agent_provider:
  type: claude  # or 'goose', 'ollama'
  model: claude-sonnet-4.5
  api_key: ${CLAUDE_API_KEY}

workflow:
  branching_strategy: per-agent
  max_concurrent_tasks: 3
  state_directory: .automation/state
```

### Environment Variables

Override settings with `AUTOMATION__` prefix (legacy) or `SAPIENS__` prefix:

```bash
export AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token"
export AUTOMATION__AGENT_PROVIDER__API_KEY="your-api-key"
export AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS="5"
```

## CI/CD Integration

### Workflow Templates

The system includes workflow templates in `.gitea/workflows/`:

| Workflow | Description |
|----------|-------------|
| `test.yaml` | Run tests on PRs and pushes |
| `needs-planning.yaml` | Process issues labeled `needs-planning` |
| `approved.yaml` | Create tasks from approved plans |
| `execute-task.yaml` | Execute task implementations |
| `needs-review.yaml` | Automated code review |
| `requires-qa.yaml` | Run QA build and tests |
| `automation-daemon.yaml` | Periodic issue processing |
| `monitor.yaml` | Health monitoring |

### Required Secrets

Configure in your repository settings:

| Secret | Description |
|--------|-------------|
| `SAPIENS_GITEA_TOKEN` | Gitea API token with repo access |
| `SAPIENS_GITEA_URL` | Gitea instance URL |
| `SAPIENS_CLAUDE_API_KEY` | Anthropic Claude API key |

## Architecture

```
repo_sapiens/
├── agents/           # ReAct agent implementation
│   ├── react.py      # ReAct loop and REPL
│   └── tools.py      # Agent tool definitions
├── cli/              # CLI commands
│   ├── init.py       # Interactive setup
│   └── credentials.py # Credential management
├── config/           # Configuration management
├── credentials/      # Credential backends (keyring, env, encrypted)
├── engine/           # Workflow orchestration
│   ├── orchestrator.py
│   ├── state_manager.py
│   └── stages/       # Workflow stages
├── git/              # Git operations and discovery
├── models/           # Domain models (Issue, Task, Plan)
├── providers/        # Git and AI providers
│   ├── gitea_rest.py
│   ├── github_rest.py
│   ├── ollama.py
│   └── external_agent.py
├── rendering/        # Template rendering
├── templates/        # Jinja2 workflow templates
└── utils/            # Utilities
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=repo_sapiens --cov-report=html

# Run specific test file
pytest tests/unit/test_react_agent.py -v
```

### Code Quality

```bash
# Format code
black repo_sapiens/ tests/

# Lint code
ruff check repo_sapiens/ tests/

# Type check
mypy repo_sapiens/

# Run pre-commit hooks
pre-commit run --all-files
```

### Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t repo-sapiens .
docker run -it repo-sapiens --help
```

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Initial setup guide |
| [Init Command Guide](docs/INIT_COMMAND_GUIDE.md) | Using `sapiens init` |
| [Goose Setup](docs/GOOSE_SETUP.md) | Goose AI configuration |
| [Secrets Setup](docs/secrets-setup.md) | CI/CD secrets configuration |
| [CI/CD Usage](docs/ci-cd-usage.md) | Workflow usage guide |
| [Local Execution](docs/LOCAL_EXECUTION_WORKFLOW.md) | Running locally |
| [Gitea Tutorial](docs/GITEA_NEW_REPO_TUTORIAL.md) | New Gitea repo setup |
| [Architecture](docs/ARCHITECTURE.md) | System architecture |
| [Error Handling](docs/ERROR_HANDLING.md) | Error handling patterns |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Production deployment |
| [Developer Setup](docs/DEVELOPER_SETUP.md) | Development environment setup |
| [Contributing](docs/CONTRIBUTING.md) | Contribution guidelines |
| [Changelog](CHANGELOG.md) | Version history |

## Troubleshooting

### Common Issues

**Workflow doesn't trigger:**
- Check Actions is enabled in repository settings
- Verify labels match workflow triggers
- Check runner is online

**Permission errors:**
- Verify API token has correct scopes
- Check repository permissions
- Ensure secrets are configured correctly

**ReAct agent model not found:**
- Pull the model: `ollama pull qwen3:latest`
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Verify `--ollama-url` is correct

### Debug Mode

```bash
sapiens --log-level DEBUG process-issue --issue 42
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

Before contributing, please:
1. Read the [Contributor License Agreement](docs/CONTRIBUTOR_LICENSE_AGREEMENT.md)
2. Sign off your commits with `git commit -s`
3. Ensure tests pass and code quality checks succeed

## Links

- **GitHub Repository**: [https://github.com/savorywatt/repo-sapiens](https://github.com/savorywatt/repo-sapiens)
- **Issue Tracker**: [https://github.com/savorywatt/repo-sapiens/issues](https://github.com/savorywatt/repo-sapiens/issues)
- **PyPI Package**: [https://pypi.org/project/repo-sapiens/](https://pypi.org/project/repo-sapiens/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Maintained by [@savorywatt](https://github.com/savorywatt)
