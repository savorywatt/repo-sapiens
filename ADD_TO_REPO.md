# Adding Builder to Another Repository

This guide shows you how to add the Builder Automation system to any other Gitea repository.

## Quick Start (5 minutes)

### Method 1: Copy Workflows (Recommended)

This is the fastest way to add builder to another repo.

```bash
# 1. Navigate to your target repository
cd /path/to/your/other/repo

# 2. Create workflows directory
mkdir -p .gitea/workflows

# 3. Copy the workflow files
cp /home/ross/Workspace/builder/.gitea/workflows/*.yaml .gitea/workflows/

# 4. Copy the environment example
cp /home/ross/Workspace/builder/.env.example .env.example

# 5. Commit and push
git add .gitea/workflows .env.example
git commit -m "feat: Add builder automation workflows"
git push origin main
```

### Method 2: Install as Package

Install builder as a Python package in your repo.

```bash
# In your target repository
cd /path/to/your/other/repo

# Option A: Install from source
pip install git+https://gitea.example.com/savorywatt/builder.git

# Option B: Add to requirements.txt
echo "gitea-automation @ git+https://gitea.example.com/savorywatt/builder.git" >> requirements.txt
pip install -r requirements.txt

# Option C: Add to pyproject.toml
# Add this to your pyproject.toml dependencies:
# "gitea-automation @ git+https://gitea.example.com/savorywatt/builder.git"
```

---

## Detailed Setup Guide

### Step 1: Copy Workflow Files

```bash
cd /path/to/target/repo

# Create workflows directory
mkdir -p .gitea/workflows

# Copy all workflow files
cp /home/ross/Workspace/builder/.gitea/workflows/*.yaml .gitea/workflows/

# Or copy only specific workflows you need:
cp /home/ross/Workspace/builder/.gitea/workflows/needs-planning.yaml .gitea/workflows/
cp /home/ross/Workspace/builder/.gitea/workflows/approved.yaml .gitea/workflows/
cp /home/ross/Workspace/builder/.gitea/workflows/execute-task.yaml .gitea/workflows/
cp /home/ross/Workspace/builder/.gitea/workflows/needs-review.yaml .gitea/workflows/
cp /home/ross/Workspace/builder/.gitea/workflows/requires-qa.yaml .gitea/workflows/
cp /home/ross/Workspace/builder/.gitea/workflows/build-artifacts.yaml .gitea/workflows/
```

### Step 2: Configure Secrets

Go to your target repository in Gitea:

**Settings → Secrets → Actions**

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `GITEA_URL` | `http://100.89.157.127:3000` | Your Gitea instance URL |
| `GITEA_TOKEN` | `your-gitea-token` | API token with repo permissions |
| `CLAUDE_API_KEY` | `sk-ant-xxx` | Claude API key (if using API mode) |

**How to create a Gitea token:**
```bash
# Via web UI:
# User Settings → Applications → Generate New Token
# Scopes needed: repo (all), write:issue, write:pull_request

# Or via CLI:
gitea admin user token create --username yourusername --scopes repo,write:issue,write:pull_request
```

### Step 3: Create Required Labels

```bash
# In your target repository
cd /path/to/target/repo

# Copy the label creation script
cp /home/ross/Workspace/builder/create_labels.py .

# Install dependencies
pip install httpx

# Create labels
python create_labels.py
```

Or manually create these labels in Gitea:

| Label | Color | Description |
|-------|-------|-------------|
| `needs-planning` | `#1E90FF` | Needs development plan |
| `proposed` | `#FFD700` | Plan proposed, awaiting approval |
| `approved` | `#32CD32` | Approved for execution |
| `task` | `#87CEEB` | Individual task |
| `execute` | `#FF8C00` | Ready for implementation |
| `needs-review` | `#9370DB` | Needs code review |
| `needs-fix` | `#DC143C` | Needs fixes after review |
| `fix-proposal` | `#FF69B4` | Fix proposal created |
| `requires-qa` | `#FFA500` | Requires QA build and test |
| `qa-passed` | `#00FF00` | QA passed |
| `qa-failed` | `#FF0000` | QA failed |

### Step 4: Update Workflow Repository References

If your workflows reference the builder package, update them:

```yaml
# In .gitea/workflows/needs-planning.yaml (and others)

# Option A: Install from builder repo
- name: Install automation
  run: |
    pip install git+https://gitea.example.com/savorywatt/builder.git
    automation --help

# Option B: If builder is installed globally/in container
- name: Run automation
  run: automation process-issue --issue ${{ gitea.event.issue.number }}
```

### Step 5: Test the Setup

```bash
# 1. Commit workflows
git add .gitea/workflows
git commit -m "feat: Add builder automation"
git push origin main

# 2. Create a test issue
gh issue create --title "Test builder automation" --body "This is a test"

# 3. Add the needs-planning label
gh issue edit 1 --add-label "needs-planning"

# 4. Check workflow runs
gh run list
gh run watch
```

---

## Configuration Options

### Option A: Standalone Repository (Each repo has its own automation)

**Structure:**
```
your-repo/
├── .gitea/
│   └── workflows/
│       ├── needs-planning.yaml
│       ├── execute-task.yaml
│       └── requires-qa.yaml
├── .env.example
└── (your project files)
```

**Pros:**
- Self-contained
- Independent configuration
- No external dependencies

**Cons:**
- Duplicate workflow files across repos
- Must update each repo separately

### Option B: Shared Builder Service (One builder instance for multiple repos)

**Structure:**
```
builder/  (automation repository)
├── automation/
├── .gitea/workflows/
└── (builder code)

your-repo/  (target repository)
├── .gitea/
│   └── workflows/
│       └── trigger-builder.yaml  (minimal trigger)
└── (your project files)
```

**Minimal trigger workflow:**
```yaml
# your-repo/.gitea/workflows/trigger-builder.yaml
name: Trigger Builder

on:
  issues:
    types: [labeled]

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger builder automation
        run: |
          curl -X POST \
            -H "Authorization: token ${{ secrets.GITEA_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{"event": "issue_labeled", "repository": "${{ gitea.repository }}", "issue": ${{ gitea.event.issue.number }}}' \
            https://your-builder-service.com/webhook
```

**Pros:**
- Single builder instance
- Easy updates (update once)
- Centralized configuration

**Cons:**
- Requires builder service running
- Cross-repo coordination needed

---

## Customization for Your Repository

### Customize Workflow Triggers

Edit workflows to match your repo's needs:

```yaml
# .gitea/workflows/needs-planning.yaml

# Original: Triggers on 'needs-planning' label
on:
  issues:
    types: [labeled]

jobs:
  create-plan:
    if: gitea.event.label.name == 'needs-planning'

# Customize: Use different label
jobs:
  create-plan:
    if: gitea.event.label.name == 'plan-me'  # Your custom label
```

### Customize Agent Settings

Configure which AI agent to use:

```yaml
# In workflows, set environment:
env:
  # Use Claude API
  AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: claude-api
  AUTOMATION__AGENT_PROVIDER__API_KEY: ${{ secrets.CLAUDE_API_KEY }}

  # Or use local Claude Code CLI
  AUTOMATION__AGENT_PROVIDER__PROVIDER_TYPE: claude-local
  AUTOMATION__AGENT_PROVIDER__LOCAL_MODE: true
```

### Customize Build/Test Commands

For the QA workflow, customize for your project type:

```yaml
# .gitea/workflows/requires-qa.yaml

# Add your specific build tools
- name: Set up dependencies
  run: |
    # For Python projects
    pip install -r requirements.txt

    # For Node projects
    npm install

    # For Go projects
    go mod download

    # For Rust projects
    cargo build
```

---

## Using Builder as a Service

### Run Builder in Daemon Mode

Run builder continuously to monitor multiple repos:

```bash
# On a server
docker-compose up -d

# Or with systemd
sudo systemctl enable builder-automation
sudo systemctl start builder-automation
```

**docker-compose.yml for multi-repo:**
```yaml
version: '3.8'

services:
  builder:
    image: gitea-automation:latest
    environment:
      - AUTOMATION__GIT_PROVIDER__BASE_URL=http://gitea:3000
      - AUTOMATION__GIT_PROVIDER__API_TOKEN=${GITEA_TOKEN}
      # Process issues from multiple repos
    command: daemon --interval 60
    restart: unless-stopped
```

### Configure Multiple Repositories

**Option 1: Environment Variables**
```bash
# Process specific repo
AUTOMATION__REPOSITORY__OWNER=myorg \
AUTOMATION__REPOSITORY__NAME=repo1 \
automation daemon --interval 60
```

**Option 2: Config File**
```yaml
# automation/config/multi-repo.yaml
repositories:
  - owner: myorg
    name: repo1
  - owner: myorg
    name: repo2
  - owner: anotherog
    name: repo3

# Run with config
automation --config multi-repo.yaml daemon
```

---

## Repository-Specific Playground Directory

The QA system needs a playground directory for each repository:

```bash
# Structure for multiple repos
/home/ross/Workspace/
├── builder/              # Builder automation repo
├── playground-repo1/     # Playground for repo1
├── playground-repo2/     # Playground for repo2
└── playground-repo3/     # Playground for repo3
```

**Configure in workflows:**
```yaml
# .gitea/workflows/requires-qa.yaml

# Set playground directory for this repo
env:
  PLAYGROUND_DIR: /home/ross/Workspace/playground-${{ gitea.repository }}

- name: Setup playground
  run: |
    if [ ! -d "$PLAYGROUND_DIR" ]; then
      git clone ${{ gitea.server_url }}/${{ gitea.repository }} $PLAYGROUND_DIR
    fi
```

---

## Troubleshooting

### Workflows Don't Trigger

**Check:**
1. Actions enabled in repo settings
2. Runner is available and connected
3. Workflow files in `.gitea/workflows/` (not `.github/workflows/`)
4. Labels exist in the repository
5. Secrets are configured

```bash
# Check Actions status
gh api repos/owner/repo/actions/permissions

# List runners
gitea admin runner list

# Check workflows
ls -la .gitea/workflows/
```

### Permission Errors

**Ensure Gitea token has scopes:**
- `repo` (all repository permissions)
- `write:issue`
- `write:pull_request`

```bash
# Test token
curl -H "Authorization: token YOUR_TOKEN" \
  http://gitea:3000/api/v1/user
```

### Builder Not Found

**Install builder in workflow:**
```yaml
- name: Install builder
  run: |
    pip install git+https://gitea.example.com/savorywatt/builder.git
    automation --help
```

Or use pre-built artifact:
```yaml
- uses: actions/download-artifact@v3
  with:
    name: automation-wheel
    repository: savorywatt/builder  # Cross-repo artifact
```

---

## Complete Example: Adding to New Repository

```bash
#!/bin/bash
# add-builder-to-repo.sh - Complete setup script

REPO_PATH="/path/to/your/repo"
BUILDER_PATH="/home/ross/Workspace/builder"

cd "$REPO_PATH"

# 1. Create workflows directory
mkdir -p .gitea/workflows

# 2. Copy workflows
cp "$BUILDER_PATH/.gitea/workflows"/*.yaml .gitea/workflows/

# 3. Copy config example
cp "$BUILDER_PATH/.env.example" .env.example

# 4. Copy label creation script
cp "$BUILDER_PATH/create_labels.py" .

# 5. Create playground directory
PLAYGROUND_DIR="${REPO_PATH}-playground"
if [ ! -d "$PLAYGROUND_DIR" ]; then
  git clone "$(git remote get-url origin)" "$PLAYGROUND_DIR"
fi

# 6. Commit
git add .gitea/workflows .env.example create_labels.py
git commit -m "feat: Add builder automation

- Add label-triggered workflows
- Add QA automation
- Add code review automation
"

# 7. Push
git push origin main

echo "✅ Builder automation added!"
echo ""
echo "Next steps:"
echo "1. Go to Settings → Secrets in Gitea"
echo "2. Add secrets: GITEA_URL, GITEA_TOKEN, CLAUDE_API_KEY"
echo "3. Run: python create_labels.py"
echo "4. Test by creating an issue and adding 'needs-planning' label"
```

---

## Summary

To add builder to another repo:

1. **Copy workflows** → `.gitea/workflows/`
2. **Configure secrets** → Gitea Settings → Secrets
3. **Create labels** → Run `create_labels.py`
4. **Test** → Create issue, add label, watch it work!

That's it! The automation is now running in your other repository. 🚀
