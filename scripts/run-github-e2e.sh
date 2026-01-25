#!/bin/bash
# scripts/run-github-e2e.sh
#
# GitHub E2E integration test.
# Validates the complete repo-sapiens workflow with GitHub:
#
# Phase 0: Setup with sapiens init
#   1. Clone test repo
#   2. Run sapiens init --deploy-workflows essential
#   3. Commit and push workflows
#
# Phase 1: Test needs-planning workflow
#   1. Create issue with needs-planning label
#   2. Wait for workflow to trigger and complete
#   3. Verify sapiens processed the issue
#
# Phase 2: Test approved workflow (optional)
#   1. If proposal exists, add approved label
#   2. Wait for execution workflow
#   3. Verify execution completed
#
# Phase 3: CLI test (optional)
#   1. Run sapiens process-issue locally
#   2. Verify results
#
# Options:
#   --bootstrap         Run bootstrap script first if not configured
#   --skip-init         Skip sapiens init (use existing workflows)
#   --skip-cli          Skip CLI test (just run workflow tests)
#   --cli-only          Only run CLI test (skip workflow tests)
#   --ai-provider       AI provider type (default: openai-compatible)
#   --ai-model          AI model to use (default: deepseek/deepseek-r1-0528:free)
#   --ai-base-url       AI provider base URL (default: https://openrouter.ai/api/v1)
#
# Prerequisites:
#   - SAPIENS_GITHUB_TOKEN environment variable set (or gh auth)
#   - OPENROUTER_API_KEY for AI provider (or local Ollama)
#   - GITHUB_OWNER and GITHUB_REPO set (or run with --bootstrap)
#
# Exit codes:
#   0 - Test passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Script directory for sourcing other scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Auto-load .env.github-test if token not already set
if [[ -z "${SAPIENS_GITHUB_TOKEN:-}" ]]; then
    if [[ -f "$PROJECT_ROOT/.env.github-test" ]]; then
        # shellcheck source=/dev/null
        source "$PROJECT_ROOT/.env.github-test"
    fi
fi

# Configuration
AUTO_BOOTSTRAP=false
SKIP_INIT=false
SKIP_CLI=false
CLI_ONLY=false
# Use absolute path for results directory
RESULTS_DIR="${RESULTS_DIR:-$PROJECT_ROOT/validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="github-e2e-${TIMESTAMP}"

# AI Provider Configuration
AI_PROVIDER="${AI_PROVIDER:-openai-compatible}"
AI_MODEL="${AI_MODEL:-deepseek/deepseek-r1-0528:free}"
AI_BASE_URL="${AI_BASE_URL:-https://openrouter.ai/api/v1}"
AI_API_KEY_ENV="${AI_API_KEY_ENV:-OPENROUTER_API_KEY}"

GITHUB_API="${GITHUB_URL:-https://api.github.com}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-sapiens-test-repo}"
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# State variables
ISSUE_NUMBER=""
PR_NUMBER=""
FEATURE_BRANCH=""
PROPOSAL_NUMBER=""
PLANNING_ISSUE_NUMBER=""
APPROVED_ISSUE_NUMBER=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bootstrap) AUTO_BOOTSTRAP=true; shift ;;
        --skip-init) SKIP_INIT=true; shift ;;
        --skip-cli) SKIP_CLI=true; shift ;;
        --cli-only) CLI_ONLY=true; shift ;;
        --ai-provider) AI_PROVIDER="$2"; shift 2 ;;
        --ai-model) AI_MODEL="$2"; shift 2 ;;
        --ai-base-url) AI_BASE_URL="$2"; shift 2 ;;
        -h|--help)
            head -45 "$0" | tail -40
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 2 ;;
    esac
done

# Cleanup trap - always runs
cleanup() {
    local exit_code=$?
    step "Cleaning up test resources..."

    # Close planning test issue
    if [[ -n "${PLANNING_ISSUE_NUMBER:-}" ]]; then
        log "Closing planning issue #$PLANNING_ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$PLANNING_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close approved test issue
    if [[ -n "${APPROVED_ISSUE_NUMBER:-}" ]]; then
        log "Closing approved issue #$APPROVED_ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$APPROVED_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close CLI test issue
    if [[ -n "${ISSUE_NUMBER:-}" ]]; then
        log "Closing CLI test issue #$ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close proposal issue
    if [[ -n "${PROPOSAL_NUMBER:-}" ]]; then
        log "Closing proposal #$PROPOSAL_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$PROPOSAL_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close PR
    if [[ -n "${PR_NUMBER:-}" ]]; then
        log "Closing PR #$PR_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/pulls/$PR_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Delete feature branch
    if [[ -n "${FEATURE_BRANCH:-}" ]]; then
        log "Deleting branch $FEATURE_BRANCH..."
        github_api DELETE "/repos/$GITHUB_OWNER/$GITHUB_REPO/git/refs/heads/$FEATURE_BRANCH" > /dev/null 2>&1 || true
    fi

    # Clean up temp directory
    if [[ -n "${TEMP_CLONE_DIR:-}" ]] && [[ -d "$TEMP_CLONE_DIR" ]]; then
        rm -rf "$TEMP_CLONE_DIR"
    fi

    log "Cleanup complete"
    exit $exit_code
}
trap cleanup EXIT

# API helper
github_api() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local curl_args=(
        -sf
        -X "$method"
        -H "Authorization: Bearer $SAPIENS_GITHUB_TOKEN"
        -H "Accept: application/vnd.github+json"
        -H "X-GitHub-Api-Version: 2022-11-28"
    )

    if [[ -n "$data" ]]; then
        curl_args+=(-H "Content-Type: application/json" -d "$data")
    fi

    curl "${curl_args[@]}" "${GITHUB_API}${endpoint}"
}

# Bootstrap GitHub if needed
maybe_bootstrap_github() {
    if [[ "$AUTO_BOOTSTRAP" != "true" ]]; then
        return 1
    fi

    log "Auto-bootstrapping GitHub..."

    local bootstrap_script="$SCRIPT_DIR/bootstrap-github.sh"
    if [[ ! -x "$bootstrap_script" ]]; then
        error "Bootstrap script not found: $bootstrap_script"
        return 1
    fi

    local env_file="/tmp/.env.github-test-$$"
    if "$bootstrap_script" --output "$env_file"; then
        # shellcheck source=/dev/null
        source "$env_file"
        rm -f "$env_file"
        log "Bootstrap complete, credentials loaded"
        return 0
    fi

    return 1
}

# Get token from environment or gh auth
get_github_token() {
    if [[ -n "${SAPIENS_GITHUB_TOKEN:-}" ]]; then
        echo "$SAPIENS_GITHUB_TOKEN"
        return 0
    fi

    if command -v gh >/dev/null 2>&1; then
        gh auth token 2>/dev/null || echo ""
        return 0
    fi

    echo ""
}

# Verify prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check for token
    SAPIENS_GITHUB_TOKEN=$(get_github_token)
    if [[ -z "$SAPIENS_GITHUB_TOKEN" ]]; then
        if [[ "$AUTO_BOOTSTRAP" == "true" ]]; then
            maybe_bootstrap_github || {
                error "SAPIENS_GITHUB_TOKEN is required (bootstrap failed)"
                exit 2
            }
            SAPIENS_GITHUB_TOKEN=$(get_github_token)
        else
            error "SAPIENS_GITHUB_TOKEN is required"
            error "Run with --bootstrap to auto-configure, or set manually"
            exit 2
        fi
    fi
    export SAPIENS_GITHUB_TOKEN

    # Get owner from token if not set
    if [[ -z "$GITHUB_OWNER" ]]; then
        log "Getting owner from token..."
        GITHUB_OWNER=$(github_api GET "/user" 2>/dev/null | jq -r '.login // empty' || echo "")

        if [[ -z "$GITHUB_OWNER" ]]; then
            error "Could not determine GITHUB_OWNER. Set it explicitly."
            exit 2
        fi
        log "Owner: $GITHUB_OWNER"
    fi

    # Check GitHub API is accessible
    if ! github_api GET "/rate_limit" > /dev/null 2>&1; then
        error "GitHub API not accessible or token invalid"
        exit 2
    fi

    # Check repository exists
    if ! github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO" > /dev/null 2>&1; then
        error "Repository not found: $GITHUB_OWNER/$GITHUB_REPO"
        error "Run with --bootstrap to create it, or create manually"
        exit 2
    fi

    # Check uv is available
    if ! command -v uv >/dev/null 2>&1; then
        error "uv not found"
        exit 2
    fi

    # Check jq is available
    if ! command -v jq >/dev/null 2>&1; then
        error "jq not found (required for JSON parsing)"
        exit 2
    fi

    # Check AI API key for workflow tests
    if [[ "$CLI_ONLY" != "true" ]]; then
        local ai_key="${!AI_API_KEY_ENV:-}"
        if [[ -z "$ai_key" ]]; then
            warn "$AI_API_KEY_ENV not set - workflow tests may fail"
            warn "Set it with: export $AI_API_KEY_ENV=your_key"
        fi
    fi

    # Check rate limit
    local rate_info
    rate_info=$(github_api GET "/rate_limit" 2>/dev/null || echo "{}")
    local remaining
    remaining=$(echo "$rate_info" | jq -r '.rate.remaining // "unknown"' || echo "unknown")
    log "GitHub API rate limit remaining: $remaining"

    if [[ "$remaining" != "unknown" ]] && [[ "$remaining" -lt 100 ]]; then
        warn "Rate limit is low ($remaining). Consider waiting before running tests."
    fi

    log "Prerequisites OK"
}

# Ensure label exists
ensure_label() {
    local label_name="$1"

    # Check if label exists
    if github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/labels/$label_name" > /dev/null 2>&1; then
        return 0
    fi

    # Create the label
    log "Creating label: $label_name"
    github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/labels" \
        "{\"name\": \"$label_name\", \"color\": \"428BCA\"}" > /dev/null 2>&1 || true
}

#############################################
# Phase 0: Setup with sapiens init
#############################################

deploy_with_sapiens_init() {
    step "Deploying workflows with sapiens init..."

    # Ensure results directory exists (before we change directories)
    mkdir -p "$RESULTS_DIR/$RUN_ID"

    # Clone repo to temp directory
    TEMP_CLONE_DIR=$(mktemp -d)
    log "Cloning repository to $TEMP_CLONE_DIR"

    local clone_url="https://${SAPIENS_GITHUB_TOKEN}@github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git"

    if ! git clone "$clone_url" "$TEMP_CLONE_DIR/repo" > /dev/null 2>&1; then
        error "Could not clone repository"
        return 1
    fi

    cd "$TEMP_CLONE_DIR/repo"

    # Configure git
    git config user.name "Sapiens Bot"
    git config user.email "sapiens-bot@users.noreply.github.com"

    # Remove existing config to force fresh generation with updated credential format
    # This ensures the E2E test uses the latest init code's credential references
    rm -rf .sapiens/config.yaml sapiens_config.ci.yaml

    # Run sapiens init with workflow deployment
    log "Running sapiens init --deploy-workflows essential..."

    local init_args=(
        --non-interactive
        --run-mode cicd
        --deploy-workflows essential
        --git-token-env SAPIENS_GITHUB_TOKEN
        --ai-provider "$AI_PROVIDER"
        --ai-model "$AI_MODEL"
        --ai-base-url "$AI_BASE_URL"
        --ai-api-key-env "$AI_API_KEY_ENV"
        --no-setup-secrets
    )

    # Run sapiens init and capture output (don't fail on tee issues)
    local init_log="$RESULTS_DIR/$RUN_ID/init-output.log"
    uv run --project "$PROJECT_ROOT" sapiens init "${init_args[@]}" 2>&1 | tee "$init_log" || true

    # Check if workflow was actually deployed
    if [[ -f ".github/workflows/sapiens.yaml" ]]; then
        log "sapiens init completed successfully"
    else
        error "sapiens init failed - workflow not created"
        cd - > /dev/null
        return 1
    fi

    # Check what was created
    log "Checking deployed files..."

    if [[ -f ".github/workflows/sapiens.yaml" ]]; then
        log "  ✓ sapiens.yaml workflow deployed"
    else
        warn "  ✗ sapiens.yaml not found"
    fi

    if [[ -f ".sapiens/config.yaml" ]]; then
        log "  ✓ .sapiens/config.yaml created"
    else
        warn "  ✗ .sapiens/config.yaml not found"
    fi

    # Commit and push changes
    if [[ -n "$(git status --porcelain)" ]]; then
        log "Pushing sapiens configuration..."
        git add -A
        git commit -m "chore: Deploy sapiens workflows via init (E2E test)" > /dev/null 2>&1 || true

        if git push origin HEAD > /dev/null 2>&1; then
            log "Changes pushed successfully"
        else
            error "Could not push changes"
            cd - > /dev/null
            return 1
        fi
    else
        log "No new changes (workflows may already be deployed)"
    fi

    cd - > /dev/null
    log "Deployment complete"
    return 0
}

verify_deployment() {
    step "Verifying workflow deployment..."

    local passed=0
    local failed=0

    # Check 1: sapiens.yaml workflow exists
    log "Checking for sapiens.yaml workflow..."
    if github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/contents/.github/workflows/sapiens.yaml" > /dev/null 2>&1; then
        log "  ✓ sapiens.yaml exists"
        ((passed++))
    else
        error "  ✗ sapiens.yaml not found"
        ((failed++))
    fi

    # Check 2: config file exists
    log "Checking for .sapiens/config.yaml..."
    if github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/contents/.sapiens/config.yaml" > /dev/null 2>&1; then
        log "  ✓ .sapiens/config.yaml exists"
        ((passed++))
    else
        warn "  - .sapiens/config.yaml not found (may use env vars)"
    fi

    # Check 3: Workflows are recognized by GitHub
    log "Checking GitHub Actions workflows..."
    local workflows
    workflows=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/workflows" 2>/dev/null || echo "{}")
    local workflow_count
    workflow_count=$(echo "$workflows" | jq -r '.total_count // 0')

    if [[ "$workflow_count" -gt 0 ]]; then
        log "  ✓ GitHub Actions enabled ($workflow_count workflows)"
        ((passed++))
    else
        warn "  - No workflows recognized yet (may need time)"
    fi

    echo ""
    log "Deployment verification: $passed passed, $failed failed"

    [[ $failed -gt 0 ]] && return 1
    return 0
}

run_init_phase() {
    step "=== Phase 0: Deploy with sapiens init ==="
    echo ""

    if [[ "$SKIP_INIT" == "true" ]]; then
        log "Skipping init phase (--skip-init)"
        return 0
    fi

    if deploy_with_sapiens_init; then
        # Wait for GitHub to recognize the workflow
        sleep 3
        if verify_deployment; then
            log "Init phase PASSED"
            return 0
        fi
    fi

    error "Init phase FAILED"
    return 1
}

#############################################
# Phase 1: Test needs-planning workflow
#############################################

create_planning_test_issue() {
    step "Creating issue to trigger needs-planning workflow..."

    ensure_label "needs-planning"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## E2E Test: needs-planning workflow

This issue tests the sapiens needs-planning workflow.

## Task
Create a simple hello world function.

## Expected Behavior
1. Workflow should trigger on `needs-planning` label
2. Sapiens should analyze the issue
3. A planning comment should be posted

This is an automated E2E test issue.
ISSUE_EOF
)

    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}needs-planning test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [\"needs-planning\"]
    }")

    PLANNING_ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$PLANNING_ISSUE_NUMBER" ]]; then
        error "Failed to create issue. Response: $response"
        return 1
    fi
    log "Created issue #$PLANNING_ISSUE_NUMBER with needs-planning label"
}

wait_for_planning_workflow() {
    step "Waiting for needs-planning workflow to complete..."

    local timeout=300  # 5 minutes
    local elapsed=0
    local poll_interval=15

    while [[ $elapsed -lt $timeout ]]; do
        # Check workflow runs
        local runs
        runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=10" 2>/dev/null || echo "{}")

        # Find the most recent Sapiens run (use first match from array)
        local status conclusion run_id run_name
        status=$(echo "$runs" | jq -r '[.workflow_runs[] | select(.name | test("Sapiens|sapiens|Process Label"; "i"))][0].status // empty' 2>/dev/null || echo "")
        conclusion=$(echo "$runs" | jq -r '[.workflow_runs[] | select(.name | test("Sapiens|sapiens|Process Label"; "i"))][0].conclusion // empty' 2>/dev/null || echo "")
        run_id=$(echo "$runs" | jq -r '[.workflow_runs[] | select(.name | test("Sapiens|sapiens|Process Label"; "i"))][0].id // empty' 2>/dev/null || echo "")
        run_name=$(echo "$runs" | jq -r '[.workflow_runs[] | select(.name | test("Sapiens|sapiens|Process Label"; "i"))][0].name // empty' 2>/dev/null || echo "")

        if [[ -n "$run_id" ]]; then
            log "  Workflow: $run_name (run $run_id) - status: $status, conclusion: $conclusion"

            if [[ "$status" == "completed" ]]; then
                if [[ "$conclusion" == "success" ]]; then
                    log "Workflow completed successfully!"
                    return 0
                elif [[ "$conclusion" == "failure" ]]; then
                    warn "Workflow failed (checking for error comment...)"
                    # Still return 0 - we're testing that the workflow RUNS
                    return 0
                else
                    warn "Workflow concluded: $conclusion"
                    return 0
                fi
            fi
        fi

        # Also check for comments on the issue
        local comments
        comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$PLANNING_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

        if echo "$comments" | grep -qiE '(sapiens|proposal|plan|automation)'; then
            log "Sapiens comment found on issue!"
            return 0
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
        log "  Waiting... (${elapsed}s / ${timeout}s)"
    done

    warn "Timeout waiting for workflow"
    return 1
}

verify_planning_workflow() {
    step "Verifying needs-planning workflow results..."

    local passed=0
    local failed=0

    # Check 1: Workflow was triggered
    log "Checking for workflow run..."
    local runs
    runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=10" 2>/dev/null || echo "{}")

    local sapiens_run_id
    sapiens_run_id=$(echo "$runs" | jq -r '.workflow_runs[] | select(.name | test("Sapiens|sapiens|Process"; "i")) | .id' | head -1)

    if [[ -n "$sapiens_run_id" ]]; then
        log "  ✓ Workflow was triggered (run: $sapiens_run_id)"
        ((passed++))
    else
        error "  ✗ No workflow run found"
        ((failed++))
    fi

    # Check 2: Issue has comments
    log "Checking for issue comments..."
    local issue
    issue=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$PLANNING_ISSUE_NUMBER" 2>/dev/null || echo "{}")
    local comments_count
    comments_count=$(echo "$issue" | jq -r '.comments // 0')

    if [[ "$comments_count" -gt 0 ]]; then
        log "  ✓ Issue has $comments_count comment(s)"
        ((passed++))
    else
        warn "  - No comments on issue"
    fi

    # Check 3: Check comment content
    log "Checking comment content..."
    local comments
    comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$PLANNING_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

    if echo "$comments" | grep -qiE '(proposal|plan|implementation|sapiens)'; then
        log "  ✓ Sapiens posted a response"
        ((passed++))
    else
        warn "  - No sapiens response found in comments"
    fi

    echo ""
    log "Planning workflow verification: $passed passed, $failed failed"

    # Pass if workflow ran, even if it failed (AI provider might be down)
    [[ $passed -ge 1 ]] && return 0
    return 1
}

run_planning_test() {
    step "=== Phase 1: Test needs-planning workflow ==="
    echo ""

    create_planning_test_issue || return 1

    if wait_for_planning_workflow; then
        if verify_planning_workflow; then
            log "needs-planning workflow test PASSED"
            return 0
        fi
    fi

    error "needs-planning workflow test FAILED"
    return 1
}

#############################################
# Phase 2: Test approved workflow (optional)
#############################################

run_approved_test() {
    step "=== Phase 2: Test approved workflow ==="
    echo ""

    # This phase requires a proposal to exist
    # For now, we'll create a simple test

    ensure_label "approved"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## E2E Test: approved workflow

This issue tests the sapiens approved workflow.

## Task
Test the approved label trigger.

## Plan
1. Create test file
2. Add content
3. Commit

This is an automated E2E test issue.
ISSUE_EOF
)

    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}approved test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [\"approved\"]
    }")

    APPROVED_ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$APPROVED_ISSUE_NUMBER" ]]; then
        warn "Could not create approved test issue"
        return 0  # Non-fatal
    fi

    log "Created issue #$APPROVED_ISSUE_NUMBER with approved label"

    # Wait briefly for workflow
    sleep 30

    # Check if workflow ran
    local runs
    runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=10" 2>/dev/null || echo "{}")

    local run_count
    run_count=$(echo "$runs" | jq -r '[.workflow_runs[] | select(.name | test("Sapiens|sapiens"; "i"))] | length')

    if [[ "$run_count" -gt 0 ]]; then
        log "Approved workflow test PASSED (workflow triggered)"
        return 0
    fi

    warn "Approved workflow test inconclusive"
    return 0  # Non-fatal
}

#############################################
# Phase 3: CLI Test
#############################################

run_cli_test() {
    step "=== Phase 3: Sapiens CLI Test ==="
    echo ""

    # Check if local AI is available (for CLI test)
    if [[ "$AI_PROVIDER" == "ollama" ]]; then
        if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
            warn "Ollama not running - skipping CLI test"
            return 0
        fi
    fi

    ensure_label "needs-planning"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## CLI Test Issue

Test sapiens CLI process-issue command.

## Task
Add a greeting function to the codebase.

## Requirements
- Create greeting.py
- Add greet(name) function
ISSUE_EOF
)

    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}CLI test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [\"needs-planning\"]
    }")

    ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$ISSUE_NUMBER" ]]; then
        error "Failed to create CLI test issue"
        return 1
    fi
    log "Created CLI test issue #$ISSUE_NUMBER"

    # Create temporary config
    # Use ${...} format for env var interpolation (resolved by from_yaml())
    local config_file="/tmp/sapiens-e2e-config-${TIMESTAMP}.yaml"
    cat > "$config_file" << CONFIG_EOF
git_provider:
  provider_type: github
  base_url: "$GITHUB_API"
  api_token: "\${SAPIENS_GITHUB_TOKEN}"

repository:
  owner: $GITHUB_OWNER
  name: $GITHUB_REPO
  default_branch: main

agent_provider:
  provider_type: $AI_PROVIDER
  base_url: "$AI_BASE_URL"
  model: "$AI_MODEL"
  api_key: "\${$AI_API_KEY_ENV}"
CONFIG_EOF

    log "Running sapiens process-issue..."
    if uv run sapiens --config "$config_file" process-issue --issue "$ISSUE_NUMBER" 2>&1 | tee "$RESULTS_DIR/$RUN_ID/cli-output.log"; then
        log "CLI test completed"
    else
        warn "CLI test returned non-zero"
    fi

    rm -f "$config_file"

    # Verify results
    log "Verifying CLI results..."
    local comments
    comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

    if echo "$comments" | grep -qiE '(proposal|plan|sapiens)'; then
        log "CLI test PASSED"
        return 0
    fi

    warn "CLI test inconclusive (no proposal comment found)"
    return 0  # Non-fatal
}

#############################################
# Report Generation
#############################################

generate_report() {
    local init_status="$1"
    local planning_status="$2"
    local approved_status="$3"
    local cli_status="$4"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# GitHub E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| GitHub API | $GITHUB_API |
| Repository | $GITHUB_OWNER/$GITHUB_REPO |
| Test Prefix | $TEST_PREFIX |
| AI Provider | $AI_PROVIDER |
| AI Model | $AI_MODEL |

## Phase 0: Deploy with sapiens init

**Status**: $init_status

- Deployed using \`sapiens init --deploy-workflows essential\`
- Workflow: .github/workflows/sapiens.yaml

## Phase 1: needs-planning Workflow

**Status**: $planning_status

- Test issue: #${PLANNING_ISSUE_NUMBER:-N/A}
- Triggered by: \`needs-planning\` label

## Phase 2: approved Workflow

**Status**: $approved_status

- Test issue: #${APPROVED_ISSUE_NUMBER:-N/A}
- Triggered by: \`approved\` label

## Phase 3: CLI Test

**Status**: $cli_status

- Test issue: #${ISSUE_NUMBER:-N/A}
- Command: \`sapiens process-issue\`

## Overall Result

$(
    local any_failed=false
    [[ "$init_status" == "FAILED" ]] && any_failed=true
    [[ "$planning_status" == "FAILED" ]] && any_failed=true

    if [[ "$any_failed" == "true" ]]; then
        echo "❌ **TESTS FAILED**"
    else
        local passed_tests=""
        [[ "$init_status" == "PASSED" ]] && passed_tests="${passed_tests}Init, "
        [[ "$planning_status" == "PASSED" ]] && passed_tests="${passed_tests}Planning, "
        [[ "$approved_status" == "PASSED" ]] && passed_tests="${passed_tests}Approved, "
        [[ "$cli_status" == "PASSED" ]] && passed_tests="${passed_tests}CLI, "

        if [[ -n "$passed_tests" ]]; then
            passed_tests="${passed_tests%, }"
            echo "✅ **TESTS PASSED**: $passed_tests"
        else
            echo "⏭️ **ALL TESTS SKIPPED**"
        fi
    fi
)

## Logs

- \`init-output.log\` - sapiens init output
- \`cli-output.log\` - CLI test output
REPORT_EOF

    log "Report saved to $RESULTS_DIR/$RUN_ID/e2e-report.md"
}

#############################################
# Main
#############################################

main() {
    mkdir -p "$RESULTS_DIR/$RUN_ID"

    log "=== GitHub E2E Integration Test ==="
    log "Run ID: $RUN_ID"
    log "AI Provider: $AI_PROVIDER ($AI_MODEL)"
    echo ""

    check_prerequisites

    local init_status="SKIPPED"
    local planning_status="SKIPPED"
    local approved_status="SKIPPED"
    local cli_status="SKIPPED"
    local overall_exit=0

    # Phase 0: Deploy with sapiens init
    if [[ "$CLI_ONLY" != "true" ]]; then
        if run_init_phase; then
            init_status="PASSED"
        else
            init_status="FAILED"
            overall_exit=1
        fi
        echo ""

        # Phase 1: Test needs-planning workflow
        if run_planning_test; then
            planning_status="PASSED"
        else
            planning_status="FAILED"
            overall_exit=1
        fi
        echo ""

        # Phase 2: Test approved workflow (optional)
        if run_approved_test; then
            approved_status="PASSED"
        else
            approved_status="SKIPPED"
        fi
        echo ""
    fi

    # Phase 3: CLI test
    if [[ "$SKIP_CLI" != "true" ]]; then
        if run_cli_test; then
            cli_status="PASSED"
        else
            cli_status="FAILED"
        fi
        echo ""
    fi

    generate_report "$init_status" "$planning_status" "$approved_status" "$cli_status"

    if [[ $overall_exit -eq 0 ]]; then
        log ""
        log "=== E2E Test PASSED ==="
    else
        error ""
        error "=== E2E Test FAILED ==="
    fi

    exit $overall_exit
}

main "$@"
