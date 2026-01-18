#!/bin/bash
# scripts/run-gitlab-e2e.sh
#
# GitLab-focused integration/e2e test.
# Validates the complete repo-sapiens workflow against GitLab:
#   1. Create labeled issue
#   2. Process issue (generate plan)
#   3. Execute plan (make changes)
#   4. Create MR (merge request)
#   5. Verify results
#   6. Cleanup
#
# Note: GitLab uses different API patterns than Gitea/GitHub:
#   - Issues use `iid` (project-scoped) not global `id`
#   - PRs are called "Merge Requests" (MRs)
#   - Different authentication header (PRIVATE-TOKEN)
#
# Exit codes:
#   0 - Test passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Configuration
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="gitlab-e2e-${TIMESTAMP}"

GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
GITLAB_PROJECT="${GITLAB_PROJECT:-root/test-repo}"  # owner/repo format
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# State variables
ISSUE_IID=""
MR_IID=""
FEATURE_BRANCH=""

# URL-encode project path for GitLab API
PROJECT_ENCODED="${GITLAB_PROJECT//\//%2F}"

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

# Cleanup trap
cleanup() {
    local exit_code=$?
    step "Cleaning up test resources..."

    # Close issue
    if [[ -n "${ISSUE_IID:-}" ]]; then
        log "Closing issue #$ISSUE_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$ISSUE_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Close MR
    if [[ -n "${MR_IID:-}" ]]; then
        log "Closing MR !$MR_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/merge_requests/$MR_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Delete feature branch
    if [[ -n "${FEATURE_BRANCH:-}" ]]; then
        log "Deleting branch $FEATURE_BRANCH..."
        local branch_encoded
        branch_encoded=$(echo "$FEATURE_BRANCH" | jq -Rr @uri)
        gitlab_api DELETE "/projects/$PROJECT_ENCODED/repository/branches/$branch_encoded" > /dev/null 2>&1 || true
    fi

    log "Cleanup complete"
    exit $exit_code
}
trap cleanup EXIT

# Verify prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Support both SAPIENS_GITLAB_TOKEN (preferred) and GITLAB_TOKEN (legacy)
    if [[ -n "${SAPIENS_GITLAB_TOKEN:-}" ]]; then
        GITLAB_TOKEN="$SAPIENS_GITLAB_TOKEN"
    fi

    if [[ -z "${GITLAB_TOKEN:-}" ]]; then
        error "SAPIENS_GITLAB_TOKEN (or GITLAB_TOKEN) is required"
        error "Run: source .env.gitlab-test  (after bootstrap)"
        exit 2
    fi

    # Check GitLab is accessible
    if ! curl -sf "$GITLAB_URL/-/health" > /dev/null 2>&1; then
        error "GitLab not accessible at $GITLAB_URL"
        error "Start with: docker compose -f plans/validation/docker/gitlab.yaml up -d"
        error "Note: GitLab takes ~5 minutes to start"
        exit 2
    fi

    # Check Ollama is running (for agent)
    if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        error "Ollama not running at localhost:11434"
        error "Start with: ollama serve"
        exit 2
    fi

    # Verify project exists
    if ! gitlab_api GET "/projects/$PROJECT_ENCODED" > /dev/null 2>&1; then
        error "Project $GITLAB_PROJECT not found"
        error "Create it in GitLab UI first"
        exit 2
    fi

    # Check uv is available
    if ! command -v uv >/dev/null 2>&1; then
        error "uv not found"
        exit 2
    fi

    log "Prerequisites OK"
}

# API helper for GitLab
gitlab_api() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local curl_args=(
        -sf
        -X "$method"
        -H "PRIVATE-TOKEN: $GITLAB_TOKEN"
    )

    if [[ -n "$data" ]]; then
        curl_args+=(-H "Content-Type: application/json" -d "$data")
    fi

    curl "${curl_args[@]}" "$GITLAB_URL/api/v4$endpoint"
}

# Create test issue with automation label
create_test_issue() {
    step "Creating test issue..."

    # First, ensure the label exists
    log "Ensuring 'needs-planning' label exists..."
    gitlab_api POST "/projects/$PROJECT_ENCODED/labels" '{
        "name": "needs-planning",
        "color": "#428BCA"
    }' 2>/dev/null || true  # Ignore if already exists

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
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/issues" "{
        \"title\": \"${TEST_PREFIX}Add greeting function\",
        \"description\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": \"needs-planning\"
    }")

    ISSUE_IID=$(echo "$response" | jq -r '.iid')
    log "Created issue #$ISSUE_IID"
}

# Run sapiens to process the issue
process_issue() {
    step "Processing issue with sapiens..."

    # Extract owner and repo from project path
    local owner="${GITLAB_PROJECT%%/*}"
    local repo="${GITLAB_PROJECT##*/}"

    # Create a temporary config for this test
    local config_file="/tmp/sapiens-gitlab-e2e-config-${TIMESTAMP}.yaml"

    # Export for sapiens subprocess (use standard name)
    export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"

    cat > "$config_file" << CONFIG_EOF
git_provider:
  provider_type: gitlab
  base_url: "$GITLAB_URL"
  api_token: "\${SAPIENS_GITLAB_TOKEN}"

repository:
  owner: $owner
  name: $repo
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
    log "Running: sapiens process-label --issue $ISSUE_IID"

    mkdir -p "$RESULTS_DIR/$RUN_ID"
    if uv run sapiens --config "$config_file" process-label --issue "$ISSUE_IID" --verbose 2>&1 | tee "$RESULTS_DIR/$RUN_ID/process-output.log"; then
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

    # Check 1: Issue should have a plan comment (GitLab calls them "notes")
    log "Checking for plan comment..."
    local notes
    notes=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$ISSUE_IID/notes" || echo "[]")
    local plan_note
    plan_note=$(echo "$notes" | jq -r '.[] | select(.body | contains("## Plan")) | .id' | head -1)

    if [[ -n "$plan_note" ]]; then
        log "  Plan comment found"
        ((passed++))
    else
        error "  No plan comment found"
        ((failed++))
    fi

    # Check 2: Issue labels should have changed
    log "Checking issue labels..."
    local issue
    issue=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$ISSUE_IID")
    local labels
    labels=$(echo "$issue" | jq -r '.labels[]' 2>/dev/null | tr '\n' ',')

    if [[ "$labels" == *"approved"* ]] || [[ "$labels" == *"in-progress"* ]] || [[ "$labels" == *"done"* ]]; then
        log "  Issue labels updated: $labels"
        ((passed++))
    else
        warn "  Issue labels unchanged: $labels (may need manual approval)"
    fi

    # Check 3: Look for created branch
    log "Checking for feature branch..."
    local branches
    branches=$(gitlab_api GET "/projects/$PROJECT_ENCODED/repository/branches" || echo "[]")
    local feature_branch
    feature_branch=$(echo "$branches" | jq -r ".[] | select(.name | contains(\"$ISSUE_IID\") or contains(\"greeting\")) | .name" | head -1)

    if [[ -n "$feature_branch" ]]; then
        log "  Feature branch found: $feature_branch"
        ((passed++))
        FEATURE_BRANCH="$feature_branch"
    else
        warn "  No feature branch found (may need approved label)"
    fi

    # Check 4: Look for MR (merge request)
    log "Checking for merge request..."
    local mrs
    mrs=$(gitlab_api GET "/projects/$PROJECT_ENCODED/merge_requests?state=all" || echo "[]")
    local test_mr
    test_mr=$(echo "$mrs" | jq -r ".[] | select(.title | contains(\"$TEST_PREFIX\") or contains(\"greeting\")) | .iid" | head -1)

    if [[ -n "$test_mr" ]]; then
        log "  Merge request found: !$test_mr"
        ((passed++))
        MR_IID="$test_mr"
    else
        warn "  No merge request found (workflow may not have completed)"
    fi

    # Summary
    echo ""
    log "Verification: $passed passed, $failed failed"

    if [[ $failed -gt 0 ]]; then
        return 1
    fi
    return 0
}

# Generate report
generate_report() {
    local status="$1"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# GitLab E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)
**Status**: $status

## Test Configuration

| Setting | Value |
|---------|-------|
| GitLab URL | $GITLAB_URL |
| Project | $GITLAB_PROJECT |
| Test Prefix | $TEST_PREFIX |

## Test Flow

1. **Create Issue**: #${ISSUE_IID:-N/A}
2. **Process with sapiens**: See process-output.log
3. **Feature Branch**: ${FEATURE_BRANCH:-Not created}
4. **Merge Request**: !${MR_IID:-Not created}

## Result

**$status**

## Logs

- \`process-output.log\` - Full sapiens output

## Notes

GitLab-specific behaviors:
- Issues use \`iid\` (project-scoped ID)
- PRs are called "Merge Requests" (MRs)
- Authentication via \`PRIVATE-TOKEN\` header
REPORT_EOF

    log "Report saved to $RESULTS_DIR/$RUN_ID/e2e-report.md"
}

#############################################
# Main
#############################################
main() {
    docker context use "$DOCKER_CONTEXT" 2>/dev/null || true

    mkdir -p "$RESULTS_DIR/$RUN_ID"

    log "=== GitLab E2E Integration Test ==="
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
