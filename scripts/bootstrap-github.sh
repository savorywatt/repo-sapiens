#!/bin/bash
# scripts/bootstrap-github.sh
#
# Bootstraps a GitHub test repository for integration testing.
# Uses the GitHub CLI (gh) for all API operations to handle auth properly.
#
# Usage:
#   ./scripts/bootstrap-github.sh [options]
#
# Options:
#   --owner OWNER    GitHub username or org (default: from gh auth)
#   --repo NAME      Test repository name (default: sapiens-test-repo)
#   --private        Make repository private (default)
#   --public         Make repository public
#   --output FILE    Output env file (default: .env.github-test)
#
# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated
#   - gh auth must have 'repo' and 'workflow' scopes
#
# Outputs:
#   Exports SAPIENS_GITHUB_TOKEN, GITHUB_URL, GITHUB_OWNER, GITHUB_REPO
#   Also writes to .env.github-test for sourcing

set -euo pipefail

# Defaults
GITHUB_OWNER=""
TEST_REPO="${GITHUB_REPO:-sapiens-test-repo}"
REPO_VISIBILITY="private"
OUTPUT_FILE="${OUTPUT_FILE:-.env.github-test}"
GITHUB_API="https://api.github.com"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
die() { error "$1"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --owner) GITHUB_OWNER="$2"; shift 2 ;;
        --repo) TEST_REPO="$2"; shift 2 ;;
        --private) REPO_VISIBILITY="private"; shift ;;
        --public) REPO_VISIBILITY="public"; shift ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        -h|--help)
            head -28 "$0" | tail -23
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

#############################################
# Step 1: Check prerequisites
#############################################
check_prerequisites() {
    log "Checking prerequisites..."

    # gh CLI is required
    if ! command -v gh >/dev/null 2>&1; then
        die "GitHub CLI (gh) is required but not installed.
Install from: https://cli.github.com/"
    fi

    # Check if authenticated
    if ! gh auth status >/dev/null 2>&1; then
        die "GitHub CLI not authenticated.
Run: gh auth login"
    fi

    # Get owner from gh if not provided
    if [[ -z "$GITHUB_OWNER" ]]; then
        GITHUB_OWNER=$(gh api user --jq '.login' 2>/dev/null || echo "")
        if [[ -z "$GITHUB_OWNER" ]]; then
            die "Could not determine GitHub owner. Set explicitly: --owner YOUR_USERNAME"
        fi
    fi

    # Check for required scopes
    local scopes
    scopes=$(gh auth status 2>&1 | grep "Token scopes" || echo "")

    if [[ -n "$scopes" ]]; then
        if ! echo "$scopes" | grep -q "'repo'"; then
            warn "Token may be missing 'repo' scope"
        fi
        if ! echo "$scopes" | grep -q "'workflow'"; then
            warn "Token missing 'workflow' scope - required for deploying workflows"
            warn "Run: gh auth refresh -h github.com -s workflow"
            die "Please add workflow scope and re-run"
        fi
    fi

    log "Authenticated as: $GITHUB_OWNER"
    log "Prerequisites OK"
}

#############################################
# Step 2: Create or verify repository
#############################################
create_test_repo() {
    log "Checking for repository: $GITHUB_OWNER/$TEST_REPO"

    # Check if repo exists
    if gh api "repos/$GITHUB_OWNER/$TEST_REPO" --jq '.name' >/dev/null 2>&1; then
        log "Repository already exists"
        return 0
    fi

    log "Creating repository: $TEST_REPO"

    local visibility_flag="--private"
    [[ "$REPO_VISIBILITY" == "public" ]] && visibility_flag="--public"

    if gh repo create "$GITHUB_OWNER/$TEST_REPO" \
        $visibility_flag \
        --description "Test repository for repo-sapiens integration testing" \
        --add-readme \
        --clone=false 2>/dev/null; then
        log "Repository created successfully"
        # Wait for GitHub to initialize the repo
        sleep 2
    else
        die "Failed to create repository"
    fi
}

#############################################
# Step 3: Set up automation labels
#############################################
setup_labels() {
    log "Setting up automation labels..."

    # Define labels with colors
    declare -A LABELS=(
        ["needs-planning"]="5319e7"
        ["awaiting-approval"]="fbca04"
        ["approved"]="0e8a16"
        ["in-progress"]="1d76db"
        ["done"]="0e8a16"
        ["proposed"]="c5def5"
        ["test-action-trigger"]="428BCA"
    )

    for label_name in "${!LABELS[@]}"; do
        local color="${LABELS[$label_name]}"

        # Check if label exists
        if gh api "repos/$GITHUB_OWNER/$TEST_REPO/labels/$label_name" --jq '.name' >/dev/null 2>&1; then
            log "  Label exists: $label_name"
            continue
        fi

        # Create label
        if gh api -X POST "repos/$GITHUB_OWNER/$TEST_REPO/labels" \
            -f name="$label_name" \
            -f color="$color" \
            -f description="Automation label for sapiens" \
            --jq '.name' >/dev/null 2>&1; then
            log "  Created label: $label_name"
        else
            warn "  Could not create label: $label_name"
        fi
    done
}

#############################################
# Step 4: Set up repository secrets
#############################################
setup_secrets() {
    log "Setting up repository secrets..."

    # Get the token to store as a secret
    local token
    token=$(gh auth token 2>/dev/null || echo "")

    if [[ -z "$token" ]]; then
        warn "Could not get token for secret. Set manually at:"
        warn "  https://github.com/$GITHUB_OWNER/$TEST_REPO/settings/secrets/actions"
        return 0
    fi

    # Use gh secret set which handles encryption automatically
    if echo "$token" | gh secret set SAPIENS_GITHUB_TOKEN \
        --repo "$GITHUB_OWNER/$TEST_REPO" 2>/dev/null; then
        log "Secret SAPIENS_GITHUB_TOKEN configured"
    else
        warn "Could not set secret. Set manually at:"
        warn "  https://github.com/$GITHUB_OWNER/$TEST_REPO/settings/secrets/actions"
    fi
}

#############################################
# Step 5: Deploy workflow files
#############################################
deploy_workflows() {
    log "Deploying workflow files..."

    # Deploy the sapiens wrapper workflow (references reusable dispatcher)
    deploy_sapiens_workflow

    # Deploy the E2E test workflow for testing Actions functionality
    deploy_e2e_test_workflow
}

deploy_sapiens_workflow() {
    log "Deploying sapiens wrapper workflow..."

    local workflow_path=".github/workflows/sapiens.yaml"

    # Thin wrapper workflow that calls the reusable sapiens-dispatcher
    # This is the new pattern - minimal boilerplate, all logic in the dispatcher
    local workflow_content
    workflow_content=$(cat << 'WORKFLOW_EOF'
# Generated by repo-sapiens bootstrap
# Thin wrapper that calls the reusable sapiens-dispatcher workflow
# See: https://github.com/savorywatt/repo-sapiens

name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v2
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      # Uncomment and configure AI provider as needed:
      # ai_provider_type: openai-compatible
      # ai_base_url: https://openrouter.ai/api/v1
      # ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITHUB_TOKEN }}
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
WORKFLOW_EOF
    )

    deploy_workflow_file "$workflow_path" "$workflow_content" "Add sapiens wrapper workflow"
}

deploy_e2e_test_workflow() {
    log "Deploying E2E test workflow..."

    local workflow_path=".github/workflows/e2e-test.yaml"

    # E2E test workflow for verifying Actions functionality
    local workflow_content
    workflow_content=$(cat << 'WORKFLOW_EOF'
name: E2E Test Trigger

on:
  issues:
    types: [labeled]

permissions:
  issues: write

jobs:
  test-trigger:
    if: github.event.label.name == 'test-action-trigger'
    runs-on: ubuntu-latest
    steps:
      - name: Post confirmation comment
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: '✅ **Action triggered successfully!**\n\nThis comment confirms that GitHub Actions are working correctly.\n\n- Workflow: E2E Test Trigger\n- Trigger: Issue labeled with `test-action-trigger`\n- Run ID: ' + context.runId
            });
WORKFLOW_EOF
    )

    deploy_workflow_file "$workflow_path" "$workflow_content" "Add E2E test workflow"
}

deploy_workflow_file() {
    local workflow_path="$1"
    local workflow_content="$2"
    local commit_message="$3"

    # Base64 encode the content
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Check if file exists and get SHA if so
    local existing_sha=""
    existing_sha=$(gh api "repos/$GITHUB_OWNER/$TEST_REPO/contents/$workflow_path" --jq '.sha' 2>/dev/null || echo "")

    if [[ -n "$existing_sha" ]]; then
        # Update existing file
        log "Updating existing workflow file: $workflow_path"
        if gh api -X PUT "repos/$GITHUB_OWNER/$TEST_REPO/contents/$workflow_path" \
            -f message="Update: $commit_message" \
            -f content="$encoded_content" \
            -f sha="$existing_sha" \
            --jq '.content.path' >/dev/null 2>&1; then
            log "Workflow updated: $workflow_path"
        else
            warn "Could not update workflow file: $workflow_path"
        fi
    else
        # Create new file
        log "Creating workflow file: $workflow_path"
        if gh api -X PUT "repos/$GITHUB_OWNER/$TEST_REPO/contents/$workflow_path" \
            -f message="$commit_message" \
            -f content="$encoded_content" \
            --jq '.content.path' >/dev/null 2>&1; then
            log "Workflow created: $workflow_path"
        else
            warn "Could not create workflow file: $workflow_path"
        fi
    fi
}

#############################################
# Step 6: Verify Actions is enabled
#############################################
verify_actions() {
    log "Verifying GitHub Actions..."

    local count
    count=$(gh api "repos/$GITHUB_OWNER/$TEST_REPO/actions/workflows" --jq '.total_count' 2>/dev/null || echo "0")

    if [[ "$count" -gt 0 ]]; then
        log "GitHub Actions enabled ($count workflows found)"
    else
        # Might just be that the workflow hasn't been picked up yet
        log "GitHub Actions enabled (workflow pending recognition)"
    fi
}

#############################################
# Step 7: Write output file
#############################################
write_output() {
    log "Writing configuration to $OUTPUT_FILE"

    # Get the current token for the env file
    local token
    token=$(gh auth token 2>/dev/null || echo "")

    cat > "$OUTPUT_FILE" << ENVFILE
# GitHub test configuration
# Generated by bootstrap-github.sh at $(date -Iseconds)
# Source this file: source $OUTPUT_FILE

export SAPIENS_GITHUB_TOKEN="$token"
export GITHUB_URL="$GITHUB_API"
export GITHUB_OWNER="$GITHUB_OWNER"
export GITHUB_REPO="$TEST_REPO"
ENVFILE

    log "Configuration written to $OUTPUT_FILE"
}

#############################################
# Main
#############################################
main() {
    log "=== GitHub Bootstrap Script ==="
    echo ""

    check_prerequisites
    create_test_repo
    setup_labels
    setup_secrets
    deploy_workflows
    verify_actions
    write_output

    echo ""
    log "=== Bootstrap Complete ==="
    log "GitHub API:   $GITHUB_API"
    log "Owner:        $GITHUB_OWNER"
    log "Repository:   $TEST_REPO"
    log "Visibility:   $REPO_VISIBILITY"
    echo ""
    log "Repository URL: https://github.com/$GITHUB_OWNER/$TEST_REPO"
    log "To use: source $OUTPUT_FILE"
}

main "$@"
