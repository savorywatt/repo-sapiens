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
#   --bootstrap       Run bootstrap script first if not configured
#   --skip-actions    Skip Actions integration test (just run CLI test)
#   --actions-only    Only run Actions integration test
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
    local cli_status="$2"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# GitHub E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| GitHub API | $GITHUB_API |
| Repository | $GITHUB_OWNER/$GITHUB_REPO |
| Test Prefix | $TEST_PREFIX |

## Phase 1: Actions Integration

**Status**: $actions_status

- Workflow: .github/workflows/e2e-test.yaml
- Test issue: #${ACTION_ISSUE_NUMBER:-N/A}
- Triggered by: \`test-action-trigger\` label

## Phase 2: Sapiens CLI

**Status**: $cli_status

- Test issue: #${ISSUE_NUMBER:-N/A}
- Proposal issue: #${PROPOSAL_NUMBER:-N/A}
- Feature branch: ${FEATURE_BRANCH:-Not created}
- Pull request: #${PR_NUMBER:-Not created}

## Overall Result

$(if [[ "$actions_status" == "PASSED" && "$cli_status" == "PASSED" ]]; then
    echo "✅ **ALL TESTS PASSED**"
elif [[ "$actions_status" == "SKIPPED" && "$cli_status" == "PASSED" ]]; then
    echo "✅ **CLI TESTS PASSED** (Actions skipped)"
elif [[ "$actions_status" == "PASSED" && "$cli_status" == "SKIPPED" ]]; then
    echo "✅ **ACTIONS TESTS PASSED** (CLI skipped)"
else
    echo "❌ **TESTS FAILED**"
fi)

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
    generate_report "$actions_status" "$cli_status"

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
