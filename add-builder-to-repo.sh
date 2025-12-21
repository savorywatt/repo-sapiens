#!/bin/bash
# add-builder-to-repo.sh - Automated script to add builder automation to another repository

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BUILDER_PATH="/home/ross/Workspace/builder"
TARGET_REPO="$1"

# Help message
show_help() {
    cat << EOF
${BLUE}Builder Automation Setup Script${NC}

Usage: $0 /path/to/target/repo [options]

Options:
    --minimal       Copy only essential workflows
    --all           Copy all workflows including examples (default)
    --help          Show this help message

Examples:
    $0 /home/ross/Workspace/my-project
    $0 /home/ross/Workspace/my-project --minimal
    $0 ../another-repo

This script will:
    1. Create .gitea/workflows directory
    2. Copy workflow files
    3. Copy configuration examples
    4. Copy label creation script
    5. Set up playground directory
    6. Commit changes

After running this script:
    1. Configure secrets in Gitea (Settings → Secrets)
       - GITEA_URL
       - GITEA_TOKEN
       - CLAUDE_API_KEY
    2. Run: python create_labels.py
    3. Test by creating an issue with 'needs-planning' label

EOF
}

# Check arguments
if [ -z "$TARGET_REPO" ] || [ "$TARGET_REPO" = "--help" ]; then
    show_help
    exit 0
fi

MODE="${2:-all}"

echo -e "${BLUE}🚀 Builder Automation Setup${NC}"
echo "=========================================="
echo ""

# Validate target repo
if [ ! -d "$TARGET_REPO" ]; then
    echo -e "${RED}❌ Error: Target repository not found: $TARGET_REPO${NC}"
    exit 1
fi

if [ ! -d "$TARGET_REPO/.git" ]; then
    echo -e "${RED}❌ Error: Not a git repository: $TARGET_REPO${NC}"
    exit 1
fi

# Validate builder path
if [ ! -d "$BUILDER_PATH" ]; then
    echo -e "${RED}❌ Error: Builder repository not found: $BUILDER_PATH${NC}"
    exit 1
fi

cd "$TARGET_REPO"
echo -e "${GREEN}✓${NC} Target repository: $(pwd)"
echo ""

# 1. Create workflows directory
echo -e "${YELLOW}📁 Creating .gitea/workflows directory...${NC}"
mkdir -p .gitea/workflows
echo -e "${GREEN}✓${NC} Directory created"
echo ""

# 2. Copy workflow files
echo -e "${YELLOW}📋 Copying workflow files...${NC}"

if [ "$MODE" = "minimal" ]; then
    # Copy only essential workflows
    WORKFLOWS=(
        "build-artifacts.yaml"
        "needs-planning.yaml"
        "approved.yaml"
        "execute-task.yaml"
        "needs-review.yaml"
        "requires-qa.yaml"
        "needs-fix.yaml"
    )

    for workflow in "${WORKFLOWS[@]}"; do
        if [ -f "$BUILDER_PATH/.gitea/workflows/$workflow" ]; then
            cp "$BUILDER_PATH/.gitea/workflows/$workflow" .gitea/workflows/
            echo -e "  ${GREEN}✓${NC} Copied $workflow"
        fi
    done
else
    # Copy all workflows
    cp "$BUILDER_PATH/.gitea/workflows"/*.yaml .gitea/workflows/
    echo -e "${GREEN}✓${NC} Copied all workflow files"
fi

# Copy documentation
if [ -f "$BUILDER_PATH/.gitea/workflows/label-routing-guide.md" ]; then
    cp "$BUILDER_PATH/.gitea/workflows/label-routing-guide.md" .gitea/workflows/
    echo -e "${GREEN}✓${NC} Copied label-routing-guide.md"
fi

if [ -f "$BUILDER_PATH/.gitea/workflows/ARTIFACT_SYSTEM.md" ]; then
    cp "$BUILDER_PATH/.gitea/workflows/ARTIFACT_SYSTEM.md" .gitea/workflows/
    echo -e "${GREEN}✓${NC} Copied ARTIFACT_SYSTEM.md"
fi

echo ""

# 3. Copy configuration examples
echo -e "${YELLOW}⚙️  Copying configuration files...${NC}"

if [ ! -f ".env.example" ]; then
    cp "$BUILDER_PATH/.env.example" .env.example
    echo -e "${GREEN}✓${NC} Copied .env.example"
else
    echo -e "${YELLOW}⚠${NC}  .env.example already exists, skipping"
fi

echo ""

# 4. Copy label creation script
echo -e "${YELLOW}🏷️  Copying label creation script...${NC}"

if [ ! -f "create_labels.py" ]; then
    cp "$BUILDER_PATH/create_labels.py" .
    echo -e "${GREEN}✓${NC} Copied create_labels.py"
else
    echo -e "${YELLOW}⚠${NC}  create_labels.py already exists, skipping"
fi

echo ""

# 5. Set up playground directory
echo -e "${YELLOW}🎮 Setting up playground directory...${NC}"

REPO_NAME=$(basename "$(pwd)")
PLAYGROUND_DIR="$(dirname "$(pwd)")/playground-${REPO_NAME}"

if [ ! -d "$PLAYGROUND_DIR" ]; then
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

    if [ -n "$REMOTE_URL" ]; then
        echo "  Cloning repository to playground..."
        git clone "$REMOTE_URL" "$PLAYGROUND_DIR"
        echo -e "${GREEN}✓${NC} Created playground directory: $PLAYGROUND_DIR"
    else
        echo -e "${YELLOW}⚠${NC}  No remote URL found, skipping playground setup"
        echo -e "${YELLOW}⚠${NC}  You may need to create it manually for QA to work"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Playground directory already exists: $PLAYGROUND_DIR"
fi

echo ""

# 6. Check git status
echo -e "${YELLOW}📊 Git status:${NC}"
git status --short
echo ""

# 7. Offer to commit
echo -e "${BLUE}Ready to commit changes?${NC}"
read -p "Commit and push? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    git add .gitea/workflows .env.example create_labels.py 2>/dev/null || true

    git commit -m "feat: Add builder automation workflows

- Add label-triggered automation workflows
- Add QA build and test automation
- Add code review automation
- Add task execution automation

🤖 Installed via builder setup script
" || true

    echo ""
    read -p "Push to remote? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin main || git push origin master
        echo -e "${GREEN}✓${NC} Pushed to remote"
    fi
fi

echo ""
echo -e "${GREEN}✅ Builder automation setup complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "1. Configure secrets in Gitea:"
echo -e "   ${YELLOW}Repository → Settings → Secrets → Actions${NC}"
echo "   Add these secrets:"
echo "   - GITEA_URL (e.g., http://100.89.157.127:3000)"
echo "   - GITEA_TOKEN (your Gitea API token)"
echo "   - CLAUDE_API_KEY (your Claude API key)"
echo ""
echo "2. Create labels:"
echo -e "   ${YELLOW}python create_labels.py${NC}"
echo ""
echo "3. Test the automation:"
echo -e "   ${YELLOW}gh issue create --title \"Test\" --body \"Test automation\"${NC}"
echo -e "   ${YELLOW}gh issue edit 1 --add-label \"needs-planning\"${NC}"
echo ""
echo "4. Watch the workflow run:"
echo -e "   ${YELLOW}gh run watch${NC}"
echo ""
echo "📚 Documentation:"
echo "   - Workflow guide: .gitea/workflows/label-routing-guide.md"
echo "   - Artifact system: .gitea/workflows/ARTIFACT_SYSTEM.md"
echo ""
echo -e "${GREEN}Happy automating! 🚀${NC}"
