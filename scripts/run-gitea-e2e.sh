#!/bin/bash
# scripts/run-gitea-e2e.sh
#
# Gitea-focused integration/e2e test.
# Validates the complete repo-sapiens workflow:
#
# Phase 1: Actions Integration
#   1. Deploy workflow file to repo
#   2. Set up repository secrets
#   3. Create issue with trigger label
#   4. Wait for Action to run
#   5. Verify Action completed
#
# Phase 2: Sapiens CLI
#   1. Create test issue
#   2. Run sapiens process-issue
#   3. Verify proposal created
#
# Options:
#   --bootstrap       Auto-bootstrap Gitea if not configured
#   --docker NAME     Docker container name (default: gitea-test)
#   --skip-actions    Skip Actions integration test (just run CLI test)
#   --actions-only    Only run Actions integration test
#
# Exit codes:
#   0 - Test passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Script directory for sourcing other scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitea-test}"
AUTO_BOOTSTRAP=false
SKIP_ACTIONS=false
ACTIONS_ONLY=false
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="gitea-e2e-${TIMESTAMP}"

GITEA_URL="${GITEA_URL:-http://localhost:3000}"
GITEA_OWNER="${GITEA_OWNER:-admin}"
GITEA_REPO="${GITEA_REPO:-test-repo}"
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# State variables
ISSUE_NUMBER=""
PR_NUMBER=""
FEATURE_BRANCH=""
PROPOSAL_NUMBER=""
ACTION_ISSUE_NUMBER=""
WORKFLOW_RUN_ID=""

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
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --url) GITEA_URL="$2"; shift 2 ;;
        --skip-actions) SKIP_ACTIONS=true; shift ;;
        --actions-only) ACTIONS_ONLY=true; shift ;;
        -h|--help)
            head -30 "$0" | tail -25
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
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close Actions test issue
    if [[ -n "${ACTION_ISSUE_NUMBER:-}" ]]; then
        log "Closing Actions test issue #$ACTION_ISSUE_NUMBER..."
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ACTION_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close proposal issue
    if [[ -n "${PROPOSAL_NUMBER:-}" ]]; then
        log "Closing proposal #$PROPOSAL_NUMBER..."
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$PROPOSAL_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close PR
    if [[ -n "${PR_NUMBER:-}" ]]; then
        log "Closing PR #$PR_NUMBER..."
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/pulls/$PR_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Delete feature branch
    if [[ -n "${FEATURE_BRANCH:-}" ]]; then
        log "Deleting branch $FEATURE_BRANCH..."
        gitea_api DELETE "/repos/$GITEA_OWNER/$GITEA_REPO/branches/$FEATURE_BRANCH" > /dev/null 2>&1 || true
    fi

    log "Cleanup complete"
    exit $exit_code
}
trap cleanup EXIT

# Bootstrap Gitea if needed
maybe_bootstrap_gitea() {
    if [[ "$AUTO_BOOTSTRAP" != "true" ]]; then
        return 1
    fi

    log "Auto-bootstrapping Gitea..."

    local bootstrap_script="$SCRIPT_DIR/bootstrap-gitea.sh"
    if [[ ! -x "$bootstrap_script" ]]; then
        error "Bootstrap script not found: $bootstrap_script"
        return 1
    fi

    local env_file="/tmp/.env.gitea-test-$$"
    if "$bootstrap_script" --url "$GITEA_URL" --docker "$DOCKER_CONTAINER" --with-runner --output "$env_file"; then
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

    # Check Gitea is accessible (may need bootstrap)
    if ! curl -sf "$GITEA_URL/api/v1/version" > /dev/null 2>&1; then
        if curl -sf "$GITEA_URL/api/healthz" > /dev/null 2>&1; then
            # Gitea running but not installed
            if maybe_bootstrap_gitea; then
                log "Gitea bootstrapped successfully"
            else
                error "Gitea needs installation at $GITEA_URL"
                error "Run with --bootstrap or complete setup manually"
                exit 2
            fi
        else
            error "Gitea not accessible at $GITEA_URL"
            error "Start with: docker compose -f plans/validation/docker/gitea.yaml up -d"
            exit 2
        fi
    fi

    # Check for token (may have been set by bootstrap)
    if [[ -z "${SAPIENS_GITEA_TOKEN:-}" ]]; then
        if [[ "$AUTO_BOOTSTRAP" == "true" ]]; then
            maybe_bootstrap_gitea || {
                error "SAPIENS_GITEA_TOKEN is required (bootstrap failed)"
                exit 2
            }
        else
            error "SAPIENS_GITEA_TOKEN is required"
            error "Run with --bootstrap to auto-configure, or set manually"
            exit 2
        fi
    fi

    # Update GITEA_OWNER and GITEA_REPO from environment if set by bootstrap
    GITEA_OWNER="${GITEA_OWNER:-testadmin}"
    GITEA_REPO="${GITEA_REPO:-test-repo}"

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

    log "Prerequisites OK"
}

# API helper
gitea_api() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local curl_args=(
        -sf
        -X "$method"
        -H "Authorization: token $SAPIENS_GITEA_TOKEN"
    )

    if [[ -n "$data" ]]; then
        curl_args+=(-H "Content-Type: application/json" -d "$data")
    fi

    curl "${curl_args[@]}" "$GITEA_URL/api/v1$endpoint"
}

# Ensure label exists and get its ID
ensure_label() {
    local label_name="$1"
    local label_id

    # Check if label exists
    label_id=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/labels" 2>/dev/null | \
        jq -r ".[] | select(.name == \"$label_name\") | .id" | head -1)

    if [[ -z "$label_id" ]]; then
        # Create the label
        log "Creating label: $label_name"
        label_id=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/labels" \
            "{\"name\": \"$label_name\", \"color\": \"428BCA\"}" 2>/dev/null | jq -r '.id')
    fi

    echo "$label_id"
}

#############################################
# Phase 1: Actions Integration Test
#############################################

# Deploy workflow file to repository
deploy_workflow() {
    step "Deploying test workflow to repository..."

    # Create a simple workflow that posts a comment when triggered
    # Note: We use GITEA_URL secret instead of github.server_url because
    # Docker environments may have URL resolution issues (internal vs external URLs)
    local workflow_content
    workflow_content=$(cat << 'WORKFLOW_EOF'
name: E2E Test Workflow

on:
  issues:
    types: [labeled]

jobs:
  test-trigger:
    name: Test Action Trigger
    if: github.event.label.name == 'test-action-trigger'
    runs-on: ubuntu-latest
    steps:
      - name: Debug context
        run: |
          echo "Server URL: ${{ github.server_url }}"
          echo "Repository: ${{ github.repository }}"
          echo "Issue number: ${{ github.event.issue.number }}"
          echo "Label name: ${{ github.event.label.name }}"
          echo "GITEA_URL secret available: ${{ secrets.GITEA_URL != '' }}"

      - name: Post confirmation comment
        env:
          GITEA_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
          GITEA_URL: ${{ secrets.GITEA_URL }}
          REPO: ${{ github.repository }}
          ISSUE_NUM: ${{ github.event.issue.number }}
          RUN_ID: ${{ github.run_id }}
        run: |
          # Use GITEA_URL secret if available, otherwise fall back to github.server_url
          API_BASE="${GITEA_URL:-${{ github.server_url }}}"
          echo "Using API base: $API_BASE"

          COMMENT_BODY=$(cat << 'COMMENT'
          ✅ **Action triggered successfully!**

          This comment confirms that Gitea Actions are working correctly.

          - Workflow: E2E Test Workflow
          - Trigger: Issue labeled with test-action-trigger
          - Run ID: RUN_ID_PLACEHOLDER
          COMMENT
          )
          COMMENT_BODY="${COMMENT_BODY//RUN_ID_PLACEHOLDER/$RUN_ID}"

          # Post the comment
          HTTP_CODE=$(curl -sS -w "%{http_code}" -o /tmp/response.json -X POST \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"body\": $(echo "$COMMENT_BODY" | jq -Rs .)}" \
            "${API_BASE}/api/v1/repos/${REPO}/issues/${ISSUE_NUM}/comments")

          echo "Response code: $HTTP_CODE"
          cat /tmp/response.json

          if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
            echo "Comment posted successfully!"
          else
            echo "Failed to post comment"
            exit 1
          fi
WORKFLOW_EOF
)

    # Base64 encode the content
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Check if file exists
    local file_path=".gitea/workflows/e2e-test.yaml"
    local existing_sha=""

    existing_sha=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" 2>/dev/null | jq -r '.sha // empty' || echo "")

    if [[ -n "$existing_sha" ]]; then
        # Update existing file
        log "Updating existing workflow file..."
        gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" "{
            \"message\": \"Update E2E test workflow\",
            \"content\": \"$encoded_content\",
            \"sha\": \"$existing_sha\"
        }" > /dev/null
    else
        # Create new file
        log "Creating workflow file..."
        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" "{
            \"message\": \"Add E2E test workflow\",
            \"content\": \"$encoded_content\"
        }" > /dev/null
    fi

    log "Workflow deployed: $file_path"
}

# Set up repository secrets
setup_secrets() {
    step "Setting up repository secrets..."

    # Gitea Actions secrets API
    # Note: This requires the token to have admin access

    # Set SAPIENS_GITEA_TOKEN secret
    log "Setting SAPIENS_GITEA_TOKEN secret..."
    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets/SAPIENS_GITEA_TOKEN" "{
        \"data\": \"$SAPIENS_GITEA_TOKEN\"
    }" > /dev/null 2>&1 || {
        warn "Could not set SAPIENS_GITEA_TOKEN secret via API."
    }

    # Set GITEA_URL secret for the workflow to use
    # This is needed because github.server_url may not work correctly in Docker
    log "Setting GITEA_URL secret..."
    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets/GITEA_URL" "{
        \"data\": \"$GITEA_URL\"
    }" > /dev/null 2>&1 || {
        warn "Could not set GITEA_URL secret via API."
    }

    # Verify secrets were set
    local secrets_response
    secrets_response=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets" 2>/dev/null || echo "[]")
    local secret_count
    secret_count=$(echo "$secrets_response" | jq 'length' 2>/dev/null || echo "0")

    if [[ "$secret_count" -gt 0 ]]; then
        log "Secrets configured ($secret_count secrets set)"
    else
        warn "Could not verify secrets. May need manual setup:"
        warn "  $GITEA_URL/$GITEA_OWNER/$GITEA_REPO/settings/actions/secrets"
    fi
}

# Create issue to trigger Action
create_action_test_issue() {
    step "Creating issue to trigger Action..."

    # Ensure the trigger label exists
    local label_id
    label_id=$(ensure_label "test-action-trigger")
    log "Using label 'test-action-trigger' (id: $label_id)"

    # Create issue
    local response
    response=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Actions Integration Test\",
        \"body\": \"This issue tests that Gitea Actions are properly configured.\\n\\nWhen the \`test-action-trigger\` label is added, the workflow should post a comment.\",
        \"labels\": [$label_id]
    }")

    ACTION_ISSUE_NUMBER=$(echo "$response" | jq -r '.number')
    log "Created issue #$ACTION_ISSUE_NUMBER with trigger label"
}

# Wait for Action to complete
wait_for_action() {
    step "Waiting for Action to complete..."

    local timeout=180
    local elapsed=0
    local poll_interval=10

    while [[ $elapsed -lt $timeout ]]; do
        # Check for the confirmation comment
        local comments
        comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ACTION_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

        if echo "$comments" | jq -e '.[] | select(.body | contains("Action triggered successfully"))' > /dev/null 2>&1; then
            log "Action completed successfully!"
            return 0
        fi

        # Check workflow runs API
        local runs
        runs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs" 2>/dev/null || echo "{}")

        # Try both possible JSON structures (Gitea may vary)
        local latest_run
        latest_run=$(echo "$runs" | jq -r '.workflow_runs[0] // .runs[0] // empty' 2>/dev/null)

        if [[ -n "$latest_run" && "$latest_run" != "null" ]]; then
            local status conclusion run_id
            status=$(echo "$latest_run" | jq -r '.status // "unknown"')
            conclusion=$(echo "$latest_run" | jq -r '.conclusion // "pending"')
            run_id=$(echo "$latest_run" | jq -r '.id // "unknown"')

            log "  Run #$run_id - status: $status, conclusion: $conclusion"

            if [[ "$conclusion" == "success" ]]; then
                log "Action completed with success!"
                # Give a moment for the comment to be posted
                sleep 3
                return 0
            elif [[ "$conclusion" == "failure" || "$conclusion" == "cancelled" ]]; then
                error "Action $conclusion!"
                # Try to get logs
                local logs
                logs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs/$run_id/logs" 2>/dev/null || echo "")
                if [[ -n "$logs" ]]; then
                    log "Run logs:"
                    echo "$logs" | head -50
                fi
                return 1
            fi
        else
            # No runs found - check if workflow was triggered at all
            local run_count
            run_count=$(echo "$runs" | jq '.total_count // (.workflow_runs | length) // 0' 2>/dev/null || echo "0")
            log "  No workflow runs found yet (count: $run_count)"
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
        log "  Waiting... (${elapsed}s / ${timeout}s)"
    done

    # On timeout, dump debugging info
    warn "Timeout waiting for Action to complete"
    warn "Dumping debug info..."

    # Check if workflow file exists
    log "Checking workflow file..."
    gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/.gitea/workflows/e2e-test.yaml" 2>/dev/null | jq -r '.name // "not found"'

    # List all workflow runs
    log "All workflow runs:"
    gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs" 2>/dev/null | jq '.' || echo "Could not fetch runs"

    # Check secrets
    log "Repository secrets:"
    gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets" 2>/dev/null | jq '.[].name // .' || echo "Could not fetch secrets"

    return 1
}

# Verify Actions integration
verify_actions() {
    step "Verifying Actions integration..."

    local passed=0
    local failed=0

    # Check 1: Workflow file exists
    log "Checking workflow file..."
    if gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/.gitea/workflows/e2e-test.yaml" > /dev/null 2>&1; then
        log "  Workflow file exists"
        ((passed++))
    else
        error "  Workflow file not found"
        ((failed++))
    fi

    # Check 2: Action posted comment
    log "Checking for Action comment..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ACTION_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

    if echo "$comments" | jq -e '.[] | select(.body | contains("Action triggered successfully"))' > /dev/null 2>&1; then
        log "  Action comment found"
        ((passed++))
    else
        error "  Action comment not found"
        ((failed++))
    fi

    echo ""
    log "Actions verification: $passed passed, $failed failed"

    if [[ $failed -gt 0 ]]; then
        return 1
    fi
    return 0
}

run_actions_test() {
    step "=== Phase 1: Actions Integration Test ==="
    echo ""

    deploy_workflow
    setup_secrets

    # Give Gitea a moment to recognize the new workflow
    sleep 2

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

    # Ensure required labels exist and get their IDs
    local planning_label_id
    planning_label_id=$(ensure_label "needs-planning")
    log "Using label 'needs-planning' (id: $planning_label_id)"

    # Also ensure other labels exist for later stages
    ensure_label "approved" > /dev/null
    ensure_label "in-progress" > /dev/null
    ensure_label "done" > /dev/null

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
    response=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Add greeting function\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [$planning_label_id]
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
  provider_type: gitea
  base_url: "$GITEA_URL"
  api_token: "\${SAPIENS_GITEA_TOKEN}"

repository:
  owner: $GITEA_OWNER
  name: $GITEA_REPO
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
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ISSUE_NUMBER/comments" || echo "[]")
    local proposal_comment
    proposal_comment=$(echo "$comments" | jq -r '.[] | select(.body | (contains("proposal") or contains("PROPOSAL") or contains("#"))) | .id' | head -1)

    if [[ -n "$proposal_comment" ]]; then
        log "  Proposal comment found"
        ((passed++))
    else
        error "  No proposal comment found"
        ((failed++))
    fi

    # Check 2: Issue labels should have changed to awaiting-approval
    log "Checking issue labels..."
    local issue
    issue=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ISSUE_NUMBER")
    local labels
    labels=$(echo "$issue" | jq -r '.labels[].name' | tr '\n' ',')

    if [[ "$labels" == *"awaiting-approval"* ]]; then
        log "  Issue has awaiting-approval label: $labels"
        ((passed++))
    elif [[ "$labels" == *"approved"* ]] || [[ "$labels" == *"in-progress"* ]] || [[ "$labels" == *"done"* ]]; then
        log "  Issue labels updated: $labels"
        ((passed++))
    else
        error "  Issue labels not updated: $labels"
        ((failed++))
    fi

    # Check 3: Look for proposal issue
    log "Checking for proposal issue..."
    local issues
    issues=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues?state=all&labels=proposed" || echo "[]")
    local proposal_issue
    proposal_issue=$(echo "$issues" | jq -r ".[] | select(.title | contains(\"$ISSUE_NUMBER\") or contains(\"PROPOSAL\")) | .number" | head -1)

    if [[ -n "$proposal_issue" ]]; then
        log "  Proposal issue found: #$proposal_issue"
        ((passed++))
        PROPOSAL_NUMBER="$proposal_issue"
    else
        error "  No proposal issue found"
        ((failed++))
    fi

    # Check 4: Look for created branch (optional - only if plan approved)
    log "Checking for feature branch..."
    local branches
    branches=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/branches" || echo "[]")
    local feature_branch
    feature_branch=$(echo "$branches" | jq -r ".[] | select(.name | contains(\"$ISSUE_NUMBER\") or contains(\"greeting\")) | .name" | head -1)

    if [[ -n "$feature_branch" ]]; then
        log "  Feature branch found: $feature_branch"
        ((passed++))
        FEATURE_BRANCH="$feature_branch"
    else
        log "  No feature branch (expected - plan needs approval)"
    fi

    # Check 5: Look for PR (optional - only after implementation)
    log "Checking for pull request..."
    local prs
    prs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/pulls?state=all" || echo "[]")
    local test_pr
    test_pr=$(echo "$prs" | jq -r ".[] | select(.title | contains(\"$TEST_PREFIX\") or contains(\"greeting\")) | .number" | head -1)

    if [[ -n "$test_pr" ]]; then
        log "  Pull request found: #$test_pr"
        ((passed++))
        PR_NUMBER="$test_pr"
    else
        log "  No pull request (expected - plan needs approval)"
    fi

    # Summary
    echo ""
    log "Verification: $passed passed, $failed failed"

    # Pass if core checks pass (comment, label, proposal)
    if [[ $failed -gt 0 ]]; then
        return 1
    fi
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
# Gitea E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| Gitea URL | $GITEA_URL |
| Repository | $GITEA_OWNER/$GITEA_REPO |
| Test Prefix | $TEST_PREFIX |

## Phase 1: Actions Integration

**Status**: $actions_status

- Workflow deployed: .gitea/workflows/e2e-test.yaml
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
    docker context use "$DOCKER_CONTEXT" 2>/dev/null || true

    mkdir -p "$RESULTS_DIR/$RUN_ID"

    log "=== Gitea E2E Integration Test ==="
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
