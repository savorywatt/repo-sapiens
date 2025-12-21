# CI/CD Integration Guide

This guide shows how to integrate the Builder Automation system into various CI/CD platforms.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Docker Deployment](#docker-deployment)
3. [GitHub Actions](#github-actions)
4. [GitLab CI](#gitlab-ci)
5. [Jenkins](#jenkins)
6. [Gitea Actions](#gitea-actions)
7. [Environment Variables](#environment-variables)

---

## Quick Start

### Installation via pip

```bash
# Install from source
git clone <your-repo-url>
cd builder
pip install -e .

# Or install from PyPI (if published)
pip install gitea-automation
```

### Docker Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your credentials
nano .env

# 3. Run with docker-compose
docker-compose up -d

# 4. Check logs
docker-compose logs -f builder
```

---

## Docker Deployment

### Build Docker Image

```bash
docker build -t gitea-automation:latest .
```

### Run Container

```bash
docker run -d \
  --name builder-automation \
  -e AUTOMATION__GIT_PROVIDER__BASE_URL="http://gitea:3000" \
  -e AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token" \
  -e AUTOMATION__REPOSITORY__OWNER="myorg" \
  -e AUTOMATION__REPOSITORY__NAME="myrepo" \
  -v $(pwd)/workspace:/workspace \
  gitea-automation:latest daemon --interval 60
```

### Process Single Issue

```bash
docker run --rm \
  -e AUTOMATION__GIT_PROVIDER__API_TOKEN="your-token" \
  -v $(pwd)/workspace:/workspace \
  gitea-automation:latest process-issue --issue 42
```

---

## GitHub Actions

Create `.github/workflows/builder-automation.yml`:

```yaml
name: Builder Automation

on:
  issues:
    types: [opened, labeled]
  schedule:
    # Run every hour
    - cron: '0 * * * *'

jobs:
  automation:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install builder automation
        run: |
          pip install -e .

      - name: Run automation
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.GITEA_URL }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ github.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ github.event.repository.name }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          automation process-all
```

### Using Docker in GitHub Actions

```yaml
name: Builder Automation (Docker)

on:
  issues:
    types: [opened, labeled]

jobs:
  automation:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t gitea-automation:latest .

      - name: Run automation
        env:
          GITEA_TOKEN: ${{ secrets.GITEA_TOKEN }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          docker run --rm \
            -e AUTOMATION__GIT_PROVIDER__API_TOKEN="$GITEA_TOKEN" \
            -e AUTOMATION__AGENT_PROVIDER__API_KEY="$CLAUDE_API_KEY" \
            -v ${{ github.workspace }}:/workspace \
            gitea-automation:latest process-all
```

---

## GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - automation

variables:
  AUTOMATION__GIT_PROVIDER__BASE_URL: "https://gitea.example.com"
  AUTOMATION__REPOSITORY__OWNER: "$CI_PROJECT_NAMESPACE"
  AUTOMATION__REPOSITORY__NAME: "$CI_PROJECT_NAME"

automation:
  stage: automation
  image: python:3.11-slim
  before_script:
    - apt-get update && apt-get install -y git
    - pip install -e .
  script:
    - automation process-all
  only:
    - schedules
    - issues
  variables:
    AUTOMATION__GIT_PROVIDER__API_TOKEN: "$GITEA_TOKEN"
    AUTOMATION__AGENT_PROVIDER__API_KEY: "$CLAUDE_API_KEY"
```

### Using Docker in GitLab CI

```yaml
stages:
  - build
  - automation

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t gitea-automation:latest .
    - docker save gitea-automation:latest | gzip > automation-image.tar.gz
  artifacts:
    paths:
      - automation-image.tar.gz
    expire_in: 1 day

automation:
  stage: automation
  image: docker:latest
  services:
    - docker:dind
  dependencies:
    - build
  script:
    - docker load < automation-image.tar.gz
    - |
      docker run --rm \
        -e AUTOMATION__GIT_PROVIDER__API_TOKEN="$GITEA_TOKEN" \
        -e AUTOMATION__AGENT_PROVIDER__API_KEY="$CLAUDE_API_KEY" \
        -v $CI_PROJECT_DIR:/workspace \
        gitea-automation:latest process-all
  only:
    - schedules
```

---

## Jenkins

Create `Jenkinsfile`:

```groovy
pipeline {
    agent {
        docker {
            image 'python:3.11-slim'
            args '-v $WORKSPACE:/workspace'
        }
    }

    environment {
        AUTOMATION__GIT_PROVIDER__BASE_URL = 'https://gitea.example.com'
        AUTOMATION__GIT_PROVIDER__API_TOKEN = credentials('gitea-token')
        AUTOMATION__AGENT_PROVIDER__API_KEY = credentials('claude-api-key')
        AUTOMATION__REPOSITORY__OWNER = 'myorg'
        AUTOMATION__REPOSITORY__NAME = 'myrepo'
    }

    triggers {
        cron('H * * * *')  // Run every hour
    }

    stages {
        stage('Install') {
            steps {
                sh '''
                    apt-get update && apt-get install -y git
                    pip install -e .
                '''
            }
        }

        stage('Run Automation') {
            steps {
                sh 'automation process-all'
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
```

### Using Docker Build in Jenkins

```groovy
pipeline {
    agent any

    environment {
        GITEA_TOKEN = credentials('gitea-token')
        CLAUDE_API_KEY = credentials('claude-api-key')
    }

    stages {
        stage('Build Docker Image') {
            steps {
                script {
                    docker.build('gitea-automation:latest')
                }
            }
        }

        stage('Run Automation') {
            steps {
                script {
                    docker.image('gitea-automation:latest').inside('-v $WORKSPACE:/workspace') {
                        sh '''
                            automation process-all
                        '''
                    }
                }
            }
        }
    }
}
```

---

## Gitea Actions

Create `.gitea/workflows/automation.yaml`:

```yaml
name: Builder Automation

on:
  issues:
    types: [opened, labeled]
  schedule:
    # Run every hour
    - cron: '0 * * * *'

jobs:
  automation:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .

      - name: Run automation
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.GITEA_URL }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ gitea.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ gitea.repository }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          automation process-all --tag needs-planning
```

### Process Specific Issue (Webhook Triggered)

```yaml
name: Process Issue

on:
  issues:
    types: [labeled]

jobs:
  process-issue:
    if: contains(github.event.issue.labels.*.name, 'needs-planning')
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install automation
        run: pip install -e .

      - name: Process issue
        env:
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
        run: |
          automation process-issue --issue ${{ github.event.issue.number }}
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTOMATION__GIT_PROVIDER__BASE_URL` | Gitea base URL | `https://gitea.example.com` |
| `AUTOMATION__GIT_PROVIDER__API_TOKEN` | Gitea API token | `ghp_xxxxxxxxxxxx` |
| `AUTOMATION__REPOSITORY__OWNER` | Repository owner | `myorg` |
| `AUTOMATION__REPOSITORY__NAME` | Repository name | `myrepo` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE` | Agent type | `claude-local` |
| `AUTOMATION__AGENT_PROVIDER__MODEL` | Model name | `claude-sonnet-4.5` |
| `AUTOMATION__AGENT_PROVIDER__API_KEY` | Claude API key | None |
| `AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS` | Max parallel tasks | `3` |
| `AUTOMATION__WORKFLOW__BRANCHING_STRATEGY` | Branch strategy | `per-agent` |

### CI/CD Secrets Setup

#### GitHub Actions
```bash
# Add secrets in: Settings → Secrets and variables → Actions
GITEA_URL=https://gitea.example.com
GITEA_TOKEN=your-token-here
CLAUDE_API_KEY=your-claude-key
```

#### GitLab CI
```bash
# Add variables in: Settings → CI/CD → Variables
GITEA_TOKEN=your-token-here
CLAUDE_API_KEY=your-claude-key
```

#### Jenkins
```bash
# Add credentials in: Manage Jenkins → Credentials
# ID: gitea-token (Secret text)
# ID: claude-api-key (Secret text)
```

---

## CLI Commands for CI/CD

### Process All Issues
```bash
automation process-all
```

### Process Issues with Tag
```bash
automation process-all --tag needs-planning
```

### Process Single Issue
```bash
automation process-issue --issue 42
```

### Run in Daemon Mode
```bash
automation daemon --interval 60
```

### Health Check
```bash
automation health-check
```

### List Active Plans
```bash
automation list-plans
```

---

## Troubleshooting

### Permission Errors
Ensure your Gitea token has the following scopes:
- `repo` (full repository access)
- `write:issue` (create/update issues)
- `write:pull_request` (create/update PRs)

### Docker Volume Permissions
If you encounter permission issues with mounted volumes:
```bash
# Fix ownership
sudo chown -R 1000:1000 ./workspace

# Or run container as root (not recommended)
docker run --user root ...
```

### Missing Dependencies
If Claude Code CLI is needed but not available in container:
```bash
# Install in running container
docker exec -it builder-automation bash
curl -fsSL https://claude.ai/download/linux | sh
```

---

## Best Practices

1. **Use Secret Management**: Never commit tokens/keys to version control
2. **Resource Limits**: Set appropriate `MAX_CONCURRENT_TASKS` for your CI/CD resources
3. **Monitoring**: Enable health checks and logs collection
4. **Caching**: Cache Python dependencies in CI/CD for faster builds
5. **Timeouts**: Set appropriate timeouts for long-running operations
6. **Workspace Cleanup**: Clean up workspace between runs to avoid conflicts

---

## Example: Complete GitHub Actions Setup

```yaml
name: Complete Builder Automation

on:
  issues:
    types: [opened, labeled, edited]
  pull_request:
    types: [opened, synchronize]
  schedule:
    - cron: '0 */2 * * *'  # Every 2 hours

jobs:
  automation:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}

      - name: Install automation
        run: |
          pip install --upgrade pip
          pip install -e .

      - name: Run automation
        env:
          AUTOMATION__GIT_PROVIDER__BASE_URL: ${{ secrets.GITEA_URL }}
          AUTOMATION__GIT_PROVIDER__API_TOKEN: ${{ secrets.GITEA_TOKEN }}
          AUTOMATION__REPOSITORY__OWNER: ${{ github.repository_owner }}
          AUTOMATION__REPOSITORY__NAME: ${{ github.event.repository.name }}
          AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          AUTOMATION__WORKFLOW__MAX_CONCURRENT_TASKS: 3
        run: |
          automation process-all

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: automation-logs
          path: .automation/logs/
```
