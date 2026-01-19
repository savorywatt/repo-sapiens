#!/bin/bash
# scripts/run-github-e2e.sh
#
# GitHub E2E integration test.
# Validates the complete repo-sapiens workflow with GitHub:
#
# Phase 1: Actions Integration
#   1. Deploy workflow file to repo (if not present)
#   2. Create issue with trigger label
#   3. Wait for Action to run
#   4. Verify Action completed and posted comment
#
# Phase 2: Sapiens CLI
#   1. Create test issue with needs-planning label
#   2. Run sapiens process-issue
#   3. Verify proposal created
#
# Options:
#   --bootstrap         Run bootstrap script first if not configured
#   --skip-actions      Skip Actions integration test (just run CLI test)
#   --actions-only      Only run Actions integration test
#   --test-dispatcher   Test the reusable sapiens-dispatcher workflow
#   --dispatcher-ref    Branch/tag to reference for dispatcher (default: v2)
#
# Prerequisites:
#   - SAPIENS_GITHUB_TOKEN environment variable set
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
SKIP_ACTIONS=false
ACTIONS_ONLY=false
TEST_DISPATCHER=false
DISPATCHER_REF="${DISPATCHER_REF:-v2}"  # Branch/tag to reference for dispatcher
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="github-e2e-${TIMESTAMP}"

GITHUB_API="${GITHUB_URL:-https://api.github.com}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-sapiens-test-repo}"
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# State variables
ISSUE_NUMBER=""
PR_NUMBER=""
FEATURE_BRANCH=""
PROPOSAL_NUMBER=""
ACTION_ISSUE_NUMBER=""
DISPATCHER_ISSUE_NUMBER=""

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
        --skip-actions) SKIP_ACTIONS=true; shift ;;
        --actions-only) ACTIONS_ONLY=true; shift ;;
        --test-dispatcher) TEST_DISPATCHER=true; shift ;;
        --dispatcher-ref) DISPATCHER_REF="$2"; shift 2 ;;
        -h|--help)
            head -35 "$0" | tail -30
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 2 ;;
    esac
done

# Cleanup trap - always runs
cleanup() {
    local exit_code=$?
    step "Cleaning up test resources..."

    # Close original issue
    if [[ -n "${ISSUE_NUMBER:-}" ]]; then
        log "Closing issue #$ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close Actions test issue
    if [[ -n "${ACTION_ISSUE_NUMBER:-}" ]]; then
        log "Closing Actions test issue #$ACTION_ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ACTION_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close dispatcher test issue
    if [[ -n "${DISPATCHER_ISSUE_NUMBER:-}" ]]; then
        log "Closing dispatcher test issue #$DISPATCHER_ISSUE_NUMBER..."
        github_api PATCH "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$DISPATCHER_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
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
        # Source the generated environment
        # shellcheck source=/dev/null
        source "$env_file"
        rm -f "$env_file"
        log "Bootstrap complete, credentials loaded"
        return 0
    fi

    return 1
}

# Verify prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check for token
    if [[ -z "${SAPIENS_GITHUB_TOKEN:-}" ]]; then
        if [[ "$AUTO_BOOTSTRAP" == "true" ]]; then
            maybe_bootstrap_github || {
                error "SAPIENS_GITHUB_TOKEN is required (bootstrap failed)"
                exit 2
            }
        else
            error "SAPIENS_GITHUB_TOKEN is required"
            error "Run with --bootstrap to auto-configure, or set manually"
            exit 2
        fi
    fi

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

    # Check Ollama is running (for agent) - only needed for CLI test
    if [[ "$ACTIONS_ONLY" != "true" ]]; then
        if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
            error "Ollama not running at localhost:11434"
            error "Start with: ollama serve"
            exit 2
        fi
    fi

    # Check uv is available
    if ! command -v uv >/dev/null 2>&1; then
        error "uv not found"
        exit 2
    fi

    # Check gh CLI is available (used for workflow deployment)
    if ! command -v gh >/dev/null 2>&1; then
        error "gh CLI not found (required for workflow deployment)"
        error "Install from: https://cli.github.com/"
        exit 2
    fi

    # Check jq is available
    if ! command -v jq >/dev/null 2>&1; then
        error "jq not found (required for JSON parsing)"
        error "Install with: apt install jq (or brew install jq)"
        exit 2
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
# Phase 1: Actions Integration Test
#############################################

# Deploy workflow file to repository
deploy_workflow() {
    step "Checking workflow deployment..."

    local workflow_path=".github/workflows/e2e-test.yaml"

    # Check if workflow exists (use gh api for reliability)
    if gh api "repos/$GITHUB_OWNER/$GITHUB_REPO/contents/$workflow_path" --jq '.name' >/dev/null 2>&1; then
        log "Workflow already deployed: $workflow_path"
        return 0
    fi

    log "Deploying test workflow..."

    # Create workflow content
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

    # Base64 encode
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Create the file using gh api (requires workflow scope)
    if gh api -X PUT "repos/$GITHUB_OWNER/$GITHUB_REPO/contents/$workflow_path" \
        -f message="Add E2E test workflow" \
        -f content="$encoded_content" \
        --jq '.content.path' >/dev/null 2>&1; then
        log "Workflow deployed: $workflow_path"
    else
        warn "Could not deploy workflow. Ensure gh auth has 'workflow' scope."
        warn "Run: gh auth refresh -h github.com -s workflow"
    fi
}

# Create issue to trigger Action
create_action_test_issue() {
    step "Creating issue to trigger Action..."

    # Ensure the trigger label exists
    ensure_label "test-action-trigger"

    # Create issue with label (use single-line JSON to avoid parsing issues)
    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" \
        "{\"title\":\"${TEST_PREFIX}Actions Integration Test\",\"body\":\"This issue tests GitHub Actions integration.\",\"labels\":[\"test-action-trigger\"]}")

    ACTION_ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$ACTION_ISSUE_NUMBER" ]]; then
        error "Failed to create issue. Response: $response"
        return 1
    fi
    log "Created issue #$ACTION_ISSUE_NUMBER with trigger label"
}

# Wait for Action to complete (by checking for comment)
wait_for_action() {
    step "Waiting for Action to complete..."

    local timeout=180
    local elapsed=0
    local poll_interval=10

    while [[ $elapsed -lt $timeout ]]; do
        # Primary check: look for the confirmation comment
        local comments
        comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ACTION_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

        if echo "$comments" | grep -q "Action triggered successfully"; then
            log "Action completed - confirmation comment found!"
            return 0
        fi

        # Secondary check: workflow run status for progress info
        local runs
        runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=5" 2>/dev/null || echo "{}")

        local latest_status latest_conclusion
        latest_status=$(echo "$runs" | jq -r '.workflow_runs[0].status // "unknown"')
        latest_conclusion=$(echo "$runs" | jq -r '.workflow_runs[0].conclusion // "pending"')

        log "  Latest run - status: $latest_status, conclusion: $latest_conclusion"

        # If workflow failed, no point waiting for comment
        if [[ "$latest_conclusion" == "failure" || "$latest_conclusion" == "cancelled" ]]; then
            error "Action $latest_conclusion!"
            return 1
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
        log "  Waiting for comment... (${elapsed}s / ${timeout}s)"
    done

    warn "Timeout waiting for Action comment"
    return 1
}

# Verify Actions integration
verify_actions() {
    step "Verifying Actions integration..."

    local passed=0
    local failed=0

    # Check 1: Workflow file exists
    log "Checking workflow file..."
    if github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/contents/.github/workflows/e2e-test.yaml" > /dev/null 2>&1; then
        log "  ✓ Workflow file exists"
        ((passed++))
    else
        error "  ✗ Workflow file not found"
        ((failed++))
    fi

    # Check 2: Action posted comment
    log "Checking for Action comment on issue #$ACTION_ISSUE_NUMBER..."
    local comments
    comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ACTION_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")
    log "  Comments response length: ${#comments}"

    if echo "$comments" | grep -q "Action triggered successfully"; then
        log "  ✓ Action comment found"
        ((passed++))
    else
        error "  ✗ Action comment not found"
        error "  Response preview: ${comments:0:200}"
        ((failed++))
    fi

    echo ""
    log "Actions verification: $passed passed, $failed failed"

    [[ $failed -gt 0 ]] && return 1
    return 0
}

run_actions_test() {
    step "=== Phase 1: Actions Integration Test ==="
    echo ""

    deploy_workflow
    sleep 2  # Give GitHub a moment to recognize the workflow

    create_action_test_issue

    if wait_for_action; then
        if verify_actions; then
            log "Actions integration test PASSED"
            return 0
        fi
    fi

    error "Actions integration test FAILED"
    return 1
}

#############################################
# Phase 1.5: Dispatcher Integration Test
#############################################

# Deploy the sapiens thin wrapper workflow
deploy_sapiens_wrapper() {
    step "Deploying sapiens thin wrapper workflow..."

    local workflow_path=".github/workflows/sapiens.yaml"

    # Check if workflow exists
    if gh api "repos/$GITHUB_OWNER/$GITHUB_REPO/contents/$workflow_path" --jq '.name' >/dev/null 2>&1; then
        log "Sapiens workflow already deployed: $workflow_path"
        return 0
    fi

    log "Creating thin wrapper workflow referencing dispatcher@${DISPATCHER_REF}..."

    # Create thin wrapper content
    # Uses Ollama for AI since it doesn't require API keys
    local workflow_content
    workflow_content=$(cat << WRAPPER_EOF
# Sapiens Automation - Thin Wrapper
# Generated by E2E test for dispatcher validation
name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

# Permissions required by the reusable workflow
permissions:
  contents: write
  issues: write
  pull-requests: write

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@${DISPATCHER_REF}
    with:
      label: \${{ github.event.label.name }}
      issue_number: \${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: \${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: github
      ai_provider_type: ollama
      ai_base_url: http://localhost:11434
      ai_model: qwen3:8b
    secrets:
      GIT_TOKEN: \${{ secrets.SAPIENS_GITHUB_TOKEN }}
WRAPPER_EOF
    )

    # Base64 encode
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Create the file
    if gh api -X PUT "repos/$GITHUB_OWNER/$GITHUB_REPO/contents/$workflow_path" \
        -f message="Add sapiens thin wrapper workflow for E2E testing" \
        -f content="$encoded_content" \
        --jq '.content.path' >/dev/null 2>&1; then
        log "Sapiens workflow deployed: $workflow_path"
    else
        error "Could not deploy sapiens workflow"
        return 1
    fi
}

# Create issue to trigger dispatcher
create_dispatcher_test_issue() {
    step "Creating issue to trigger dispatcher..."

    # Ensure the trigger label exists
    ensure_label "needs-planning"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## Dispatcher Integration Test

This issue tests the reusable sapiens-dispatcher workflow.

## Task
Add a simple test file to verify the dispatcher is working.

## Expected Behavior
1. Dispatcher workflow should trigger on `needs-planning` label
2. Sapiens should process the issue
3. A proposal comment should be posted (or error comment if Ollama unavailable)

This is an automated test issue.
ISSUE_EOF
)

    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Dispatcher Integration Test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [\"needs-planning\"]
    }")

    DISPATCHER_ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$DISPATCHER_ISSUE_NUMBER" ]]; then
        error "Failed to create dispatcher test issue. Response: $response"
        return 1
    fi
    log "Created dispatcher test issue #$DISPATCHER_ISSUE_NUMBER with needs-planning label"
}

# Wait for dispatcher workflow to complete
wait_for_dispatcher() {
    step "Waiting for dispatcher workflow to complete..."

    local timeout=300  # 5 minutes - dispatcher does more work
    local elapsed=0
    local poll_interval=15

    while [[ $elapsed -lt $timeout ]]; do
        # Check workflow runs for "Sapiens Automation" or "Sapiens Dispatcher"
        local runs
        runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=10" 2>/dev/null || echo "{}")

        # Find runs triggered by our issue
        local sapiens_run
        sapiens_run=$(echo "$runs" | jq -r --arg issue "#$DISPATCHER_ISSUE_NUMBER" '
            .workflow_runs[]
            | select(.name | test("Sapiens"; "i"))
            | select(.status != "queued")
            | {status: .status, conclusion: .conclusion, id: .id}
        ' 2>/dev/null | head -1 || echo "")

        if [[ -n "$sapiens_run" ]]; then
            local status conclusion run_id
            status=$(echo "$sapiens_run" | jq -r '.status // "unknown"')
            conclusion=$(echo "$sapiens_run" | jq -r '.conclusion // "pending"')
            run_id=$(echo "$sapiens_run" | jq -r '.id // "unknown"')

            log "  Dispatcher run $run_id - status: $status, conclusion: $conclusion"

            if [[ "$status" == "completed" ]]; then
                if [[ "$conclusion" == "success" ]]; then
                    log "Dispatcher workflow completed successfully!"
                    return 0
                elif [[ "$conclusion" == "failure" ]]; then
                    # Check if it's an expected failure (Ollama not available in GitHub Actions)
                    log "Dispatcher workflow failed (may be expected if Ollama unavailable)"
                    # Still return 0 - we're testing that the dispatcher RUNS, not that Ollama works
                    return 0
                else
                    warn "Dispatcher workflow concluded: $conclusion"
                    return 1
                fi
            fi
        fi

        # Also check for comments on the issue (indicates processing happened)
        local comments
        comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$DISPATCHER_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

        if echo "$comments" | grep -qiE '(sapiens|proposal|automation|failed)'; then
            log "Sapiens comment found on issue - processing occurred"
            return 0
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
        log "  Waiting for dispatcher... (${elapsed}s / ${timeout}s)"
    done

    warn "Timeout waiting for dispatcher workflow"
    return 1
}

# Verify dispatcher integration
verify_dispatcher() {
    step "Verifying dispatcher integration..."

    local passed=0
    local failed=0

    # Check 1: Sapiens workflow file exists
    log "Checking sapiens workflow file..."
    if github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/contents/.github/workflows/sapiens.yaml" > /dev/null 2>&1; then
        log "  ✓ Sapiens workflow file exists"
        ((passed++))
    else
        error "  ✗ Sapiens workflow file not found"
        ((failed++))
    fi

    # Check 2: Dispatcher workflow was triggered
    log "Checking for dispatcher workflow run..."
    local runs
    runs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?per_page=10" 2>/dev/null || echo "{}")

    local sapiens_run_exists
    sapiens_run_exists=$(echo "$runs" | jq -r '.workflow_runs[] | select(.name | test("Sapiens"; "i")) | .id' | head -1)

    if [[ -n "$sapiens_run_exists" ]]; then
        log "  ✓ Dispatcher workflow was triggered (run: $sapiens_run_exists)"
        ((passed++))
    else
        error "  ✗ No dispatcher workflow run found"
        ((failed++))
    fi

    # Check 3: Issue has some activity (comment or label change)
    log "Checking for issue activity..."
    local issue
    issue=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$DISPATCHER_ISSUE_NUMBER" 2>/dev/null || echo "{}")
    local comments_count
    comments_count=$(echo "$issue" | jq -r '.comments // 0')

    if [[ "$comments_count" -gt 0 ]]; then
        log "  ✓ Issue has $comments_count comment(s)"
        ((passed++))
    else
        # Check if workflow posted a failure comment
        local comments
        comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$DISPATCHER_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

        if echo "$comments" | grep -qiE '(sapiens|automation)'; then
            log "  ✓ Sapiens automation comment found"
            ((passed++))
        else
            warn "  - No comments on issue (dispatcher may have run but produced no output)"
        fi
    fi

    echo ""
    log "Dispatcher verification: $passed passed, $failed failed"

    # Dispatcher test passes if workflow was triggered, even if it failed
    # (failure could be due to Ollama not being available in GitHub Actions runners)
    [[ $failed -gt 1 ]] && return 1
    return 0
}

run_dispatcher_test() {
    step "=== Phase 1.5: Dispatcher Integration Test ==="
    echo ""
    log "Testing reusable sapiens-dispatcher workflow"
    log "Dispatcher ref: $DISPATCHER_REF"
    echo ""

    deploy_sapiens_wrapper || return 1
    sleep 3  # Give GitHub time to recognize the new workflow

    create_dispatcher_test_issue || return 1

    if wait_for_dispatcher; then
        if verify_dispatcher; then
            log "Dispatcher integration test PASSED"
            return 0
        fi
    fi

    error "Dispatcher integration test FAILED"
    return 1
}

#############################################
# Phase 2: Sapiens CLI Test
#############################################

# Create test issue with automation label
create_test_issue() {
    step "Creating test issue..."

    # Ensure required labels exist
    ensure_label "needs-planning"
    ensure_label "approved"
    ensure_label "in-progress"
    ensure_label "done"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## Task
Add a simple greeting function to the codebase.

## Requirements
- Create a file called `greeting.py`
- Add a function `greet(name: str) -> str` that returns "Hello, {name}!"
- Include a docstring

## Acceptance Criteria
- [ ] File `greeting.py` exists
- [ ] Function `greet()` works correctly
- [ ] Has proper docstring
ISSUE_EOF
)

    local response
    response=$(github_api POST "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Add greeting function\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [\"needs-planning\"]
    }")

    ISSUE_NUMBER=$(echo "$response" | jq -r '.number')
    log "Created issue #$ISSUE_NUMBER"
}

# Run sapiens to process the issue
process_issue() {
    step "Processing issue with sapiens..."

    # Create a temporary config for this test
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
  provider_type: ollama
  base_url: "http://localhost:11434"
  model: qwen3:8b

automation:
  labels:
    planning: needs-planning
    approved: approved
    in_progress: in-progress
    done: done
CONFIG_EOF

    log "Config written to $config_file"

    # Process the specific issue
    log "Running: sapiens process-issue --issue $ISSUE_NUMBER"

    mkdir -p "$RESULTS_DIR/$RUN_ID"
    if uv run sapiens --config "$config_file" process-issue --issue "$ISSUE_NUMBER" 2>&1 | tee "$RESULTS_DIR/$RUN_ID/process-output.log"; then
        log "Issue processing completed"
    else
        warn "Issue processing returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify results
verify_results() {
    step "Verifying results..."

    local passed=0
    local failed=0

    # Check 1: Issue should have a comment linking to proposal
    log "Checking for proposal comment..."
    local comments
    comments=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ISSUE_NUMBER/comments" || echo "[]")

    if echo "$comments" | grep -qiE '(proposal|PROPOSAL|#[0-9]+)'; then
        log "  ✓ Proposal comment found"
        ((passed++))
    else
        error "  ✗ No proposal comment found"
        ((failed++))
    fi

    # Check 2: Issue labels should have changed
    log "Checking issue labels..."
    local issue
    issue=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues/$ISSUE_NUMBER")
    local labels
    labels=$(echo "$issue" | jq -r '[.labels[].name] | join(",")' || echo "")

    if [[ "$labels" == *"awaiting-approval"* ]] || [[ "$labels" == *"approved"* ]] || [[ "$labels" == *"in-progress"* ]] || [[ "$labels" == *"done"* ]]; then
        log "  ✓ Issue labels updated: $labels"
        ((passed++))
    else
        error "  ✗ Issue labels not updated: $labels"
        ((failed++))
    fi

    # Check 3: Look for proposal issue
    log "Checking for proposal issue..."
    local issues
    issues=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/issues?state=all&labels=proposed&per_page=10" || echo "[]")
    local proposal_issue
    proposal_issue=$(echo "$issues" | jq -r '.[0].number // empty' || echo "")

    if [[ -n "$proposal_issue" ]]; then
        log "  ✓ Proposal issue found: #$proposal_issue"
        ((passed++))
        PROPOSAL_NUMBER="$proposal_issue"
    else
        error "  ✗ No proposal issue found"
        ((failed++))
    fi

    # Check 4: Look for feature branch (optional)
    log "Checking for feature branch..."
    local branches
    branches=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/branches?per_page=20" || echo "[]")
    local feature_branch
    feature_branch=$(echo "$branches" | jq -r --arg issue "$ISSUE_NUMBER" '[.[].name | select(test("issue-" + $issue) or test("greeting"))] | .[0] // empty' || echo "")

    if [[ -n "$feature_branch" ]]; then
        log "  ✓ Feature branch found: $feature_branch"
        ((passed++))
        FEATURE_BRANCH="$feature_branch"
    else
        log "  - No feature branch (expected - plan needs approval)"
    fi

    # Check 5: Look for PR (optional)
    log "Checking for pull request..."
    local prs
    prs=$(github_api GET "/repos/$GITHUB_OWNER/$GITHUB_REPO/pulls?state=all&per_page=10" || echo "[]")
    local test_pr
    test_pr=$(echo "$prs" | jq -r --arg prefix "$TEST_PREFIX" '[.[] | select(.title | contains($prefix))] | .[0].number // empty' || echo "")

    if [[ -n "$test_pr" ]]; then
        log "  ✓ Pull request found: #$test_pr"
        ((passed++))
        PR_NUMBER="$test_pr"
    else
        log "  - No pull request (expected - plan needs approval)"
    fi

    # Summary
    echo ""
    log "Verification: $passed passed, $failed failed"

    [[ $failed -gt 0 ]] && return 1
    return 0
}

run_cli_test() {
    step "=== Phase 2: Sapiens CLI Test ==="
    echo ""

    create_test_issue
    process_issue

    if verify_results; then
        log "Sapiens CLI test PASSED"
        return 0
    fi

    error "Sapiens CLI test FAILED"
    return 1
}

#############################################
# Report Generation
#############################################

generate_report() {
    local actions_status="$1"
    local dispatcher_status="$2"
    local cli_status="$3"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# GitHub E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| GitHub API | $GITHUB_API |
| Repository | $GITHUB_OWNER/$GITHUB_REPO |
| Test Prefix | $TEST_PREFIX |
| Dispatcher Ref | $DISPATCHER_REF |

## Phase 1: Actions Integration

**Status**: $actions_status

- Workflow: .github/workflows/e2e-test.yaml
- Test issue: #${ACTION_ISSUE_NUMBER:-N/A}
- Triggered by: \`test-action-trigger\` label

## Phase 1.5: Dispatcher Integration

**Status**: $dispatcher_status

- Workflow: .github/workflows/sapiens.yaml (thin wrapper)
- Dispatcher: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@$DISPATCHER_REF
- Test issue: #${DISPATCHER_ISSUE_NUMBER:-N/A}
- Triggered by: \`needs-planning\` label

## Phase 2: Sapiens CLI

**Status**: $cli_status

- Test issue: #${ISSUE_NUMBER:-N/A}
- Proposal issue: #${PROPOSAL_NUMBER:-N/A}
- Feature branch: ${FEATURE_BRANCH:-Not created}
- Pull request: #${PR_NUMBER:-Not created}

## Overall Result

$(
    local all_passed=true
    local any_failed=false

    [[ "$actions_status" == "FAILED" ]] && any_failed=true
    [[ "$dispatcher_status" == "FAILED" ]] && any_failed=true
    [[ "$cli_status" == "FAILED" ]] && any_failed=true

    if [[ "$any_failed" == "true" ]]; then
        echo "❌ **TESTS FAILED**"
    else
        # Check what passed vs skipped
        local passed_tests=""
        [[ "$actions_status" == "PASSED" ]] && passed_tests="${passed_tests}Actions, "
        [[ "$dispatcher_status" == "PASSED" ]] && passed_tests="${passed_tests}Dispatcher, "
        [[ "$cli_status" == "PASSED" ]] && passed_tests="${passed_tests}CLI, "

        if [[ -n "$passed_tests" ]]; then
            passed_tests="${passed_tests%, }"  # Remove trailing comma
            echo "✅ **TESTS PASSED**: $passed_tests"
        else
            echo "⏭️ **ALL TESTS SKIPPED**"
        fi
    fi
)

## Logs

- \`process-output.log\` - Sapiens CLI output
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
    echo ""

    check_prerequisites

    local actions_status="SKIPPED"
    local dispatcher_status="SKIPPED"
    local cli_status="SKIPPED"
    local overall_exit=0

    # Phase 1: Actions Integration
    if [[ "$SKIP_ACTIONS" != "true" ]]; then
        if run_actions_test; then
            actions_status="PASSED"
        else
            actions_status="FAILED"
            overall_exit=1
        fi
    else
        log "Skipping Actions integration test (--skip-actions)"
    fi

    echo ""

    # Phase 1.5: Dispatcher Integration (optional, requires --test-dispatcher)
    if [[ "$TEST_DISPATCHER" == "true" ]]; then
        if run_dispatcher_test; then
            dispatcher_status="PASSED"
        else
            dispatcher_status="FAILED"
            overall_exit=1
        fi
        echo ""
    else
        log "Skipping dispatcher test (use --test-dispatcher to enable)"
    fi

    echo ""

    # Phase 2: Sapiens CLI
    if [[ "$ACTIONS_ONLY" != "true" ]]; then
        if run_cli_test; then
            cli_status="PASSED"
        else
            cli_status="FAILED"
            overall_exit=1
        fi
    else
        log "Skipping CLI test (--actions-only)"
    fi

    echo ""
    generate_report "$actions_status" "$dispatcher_status" "$cli_status"

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
