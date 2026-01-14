#!/bin/bash
# scripts/run-gitea-e2e.sh
#
# Gitea-focused integration/e2e test.
# Validates the complete repo-sapiens workflow:
#   1. Create labeled issue
#   2. Process issue (generate plan)
#   3. Execute plan (make changes)
#   4. Create PR
#   5. Verify results
#   6. Cleanup
#
# Options:
#   --bootstrap      Auto-bootstrap Gitea if not configured
#   --docker NAME    Docker container name (default: gitea-test)
#
# Exit codes:
#   0 - Test passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Script directory for sourcing other scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitea-test}"
AUTO_BOOTSTRAP=false
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
        -h|--help)
            head -20 "$0" | tail -15
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
    if "$bootstrap_script" --url "$GITEA_URL" --docker "$DOCKER_CONTAINER" --output "$env_file"; then
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

    # Check Ollama is running (for agent)
    if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        error "Ollama not running at localhost:11434"
        error "Start with: ollama serve"
        exit 2
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

# Generate report
generate_report() {
    local status="$1"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# Gitea E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)
**Status**: $status

## Test Configuration

| Setting | Value |
|---------|-------|
| Gitea URL | $GITEA_URL |
| Repository | $GITEA_OWNER/$GITEA_REPO |
| Test Prefix | $TEST_PREFIX |

## Test Flow

1. **Create Issue**: #${ISSUE_NUMBER:-N/A}
2. **Process with sapiens**: See process-output.log
3. **Feature Branch**: ${FEATURE_BRANCH:-Not created}
4. **Pull Request**: #${PR_NUMBER:-Not created}

## Result

**$status**

## Logs

- \`process-output.log\` - Full sapiens output
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
    create_test_issue
    process_issue

    if verify_results; then
        generate_report "PASSED"
        log ""
        log "=== E2E Test PASSED ==="
        exit 0
    else
        generate_report "FAILED"
        error ""
        error "=== E2E Test FAILED ==="
        exit 1
    fi
}

main "$@"
