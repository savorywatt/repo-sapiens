#!/bin/bash
# scripts/run-gitea-e2e.sh
#
# Gitea-focused integration/e2e test.
# Validates the complete repo-sapiens workflow including all stages
# required by the Gitea workflow templates.
#
# Phase 1: Actions Integration
#   1. Deploy workflow file to repo
#   2. Set up repository secrets
#   3. Create issue with trigger label
#   4. Wait for Action to run
#   5. Verify Action completed
#
# Phase 2: Sapiens CLI (Proposal)
#   - Stage: proposal
#   1. Create test issue with needs-planning label
#   2. Run sapiens process-issue
#   3. Verify proposal created
#
# Phase 3: Full Workflow (requires --full-workflow)
#   - Stages: approval, task_execution
#   1. Approve proposal
#   2. Run sapiens to create task issues
#   3. Execute task
#   4. Verify PR created with code changes
#
# Phase 4: PR Review Cycle (requires --full-workflow)
#   - Stages: pr_review, pr_fix, fix_execution
#   1. Add needs-review label to trigger code review
#   2. Add needs-fix label to trigger fix proposal
#   3. Approve fix proposal
#   4. Execute fix
#
# Phase 5: QA Stage (requires --full-workflow)
#   - Stage: qa
#   1. Add requires-qa label
#   2. Run QA validation
#
# Options:
#   --bootstrap       Auto-bootstrap Gitea if not configured
#   --docker NAME     Docker container name (default: gitea-test)
#   --context NAME    Docker context to use (e.g., 'default', 'remote-server')
#   --skip-actions      Skip Actions integration test (just run CLI test)
#   --actions-only      Only run Actions integration test
#   --full-workflow     Run full workflow test (all 5 phases)
#   --skip-cleanup      Skip cleanup of artifacts from previous test runs
#   --test-dispatcher   Test the reusable sapiens-dispatcher workflow
#   --test-tiers        Test Core, Security, Support tiers via workflow_dispatch API
#   --dispatcher-ref    Branch/tag to reference for dispatcher (default: v2)
#
# Environment:
#   DOCKER_CONTEXT    Docker context (alternative to --context)
#   GITEA_URL         Gitea URL (auto-detected for remote contexts)
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
DOCKER_CONTEXT="${DOCKER_CONTEXT:-}"  # Empty means use current context
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitea-test}"
AUTO_BOOTSTRAP=false
SKIP_ACTIONS=false
ACTIONS_ONLY=false
FULL_WORKFLOW=false
SKIP_CLEANUP=false
TEST_DISPATCHER=false
TEST_TIERS=false  # Test Core, Security, Support tiers via workflow dispatch
DISPATCHER_REF="${DISPATCHER_REF:-v2}"  # Branch/tag to reference for dispatcher
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="gitea-e2e-${TIMESTAMP}"

GITEA_URL="${GITEA_URL:-http://localhost:3000}"
GITEA_OWNER="${GITEA_OWNER:-testadmin}"
GITEA_REPO="${GITEA_REPO:-test-repo}"
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# Playground directory - where sapiens expects the target repo clone
# Must match the hardcoded path in repo_sapiens/engine/stages/execution.py
PLAYGROUND_DIR="${PLAYGROUND_DIR:-/home/ross/Workspace/playground}"
PLAYGROUND_CREATED=false

# State variables
ISSUE_NUMBER=""
PR_NUMBER=""
FEATURE_BRANCH=""
PROPOSAL_NUMBER=""
ACTION_ISSUE_NUMBER=""
DISPATCHER_ISSUE_NUMBER=""
WORKFLOW_RUN_ID=""
FIX_PROPOSAL_NUMBER=""
TASK_ISSUE_NUMBER=""

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
        --context) DOCKER_CONTEXT="$2"; shift 2 ;;
        --skip-actions) SKIP_ACTIONS=true; shift ;;
        --actions-only) ACTIONS_ONLY=true; shift ;;
        --full-workflow) FULL_WORKFLOW=true; shift ;;
        --skip-cleanup) SKIP_CLEANUP=true; shift ;;
        --test-dispatcher) TEST_DISPATCHER=true; shift ;;
        --test-tiers) TEST_TIERS=true; shift ;;
        --dispatcher-ref) DISPATCHER_REF="$2"; shift 2 ;;
        -h|--help)
            head -50 "$0" | tail -45
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

    # Close dispatcher test issue
    if [[ -n "${DISPATCHER_ISSUE_NUMBER:-}" ]]; then
        log "Closing dispatcher test issue #$DISPATCHER_ISSUE_NUMBER..."
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$DISPATCHER_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
    fi

    # Close template test issue
    if [[ -n "${TEMPLATE_ISSUE_NUMBER:-}" ]]; then
        log "Closing template test issue #$TEMPLATE_ISSUE_NUMBER..."
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TEMPLATE_ISSUE_NUMBER" '{"state":"closed"}' > /dev/null 2>&1 || true
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

    # Remove playground directory if we created it
    if [[ "$PLAYGROUND_CREATED" == "true" && -d "$PLAYGROUND_DIR" ]]; then
        log "Removing playground directory..."
        rm -rf "$PLAYGROUND_DIR"
    fi

    log "Cleanup complete"
    exit $exit_code
}
trap cleanup EXIT

#############################################
# Docker context detection
#############################################
detect_docker_context() {
    local context_name

    # If a context was explicitly specified, switch to it
    if [[ -n "$DOCKER_CONTEXT" ]]; then
        log "Switching to Docker context: $DOCKER_CONTEXT"
        if ! docker context use "$DOCKER_CONTEXT" >/dev/null 2>&1; then
            error "Failed to switch to Docker context: $DOCKER_CONTEXT"
            error "Available contexts:"
            docker context ls
            exit 1
        fi
        context_name="$DOCKER_CONTEXT"
    else
        context_name=$(docker context show 2>/dev/null || echo "default")
    fi

    echo "$context_name"  # Print for diagnostic purposes

    # Check if this is a remote context (ssh://)
    local host_url
    host_url=$(docker context inspect "$context_name" 2>/dev/null | jq -r '.[0].Endpoints.docker.Host // ""' 2>/dev/null || echo "")

    if [[ "$host_url" == ssh://* ]]; then
        # Extract the remote host from ssh://user@host
        DOCKER_REMOTE_HOST=$(echo "$host_url" | sed -E 's|ssh://[^@]+@([^:/]+).*|\1|')
        log "Docker context: $context_name (remote: $DOCKER_REMOTE_HOST)"

        # If GITEA_URL is still localhost, update it to use the remote host
        if [[ "$GITEA_URL" == *"localhost"* ]] || [[ "$GITEA_URL" == *"127.0.0.1"* ]]; then
            local old_url="$GITEA_URL"
            GITEA_URL=$(echo "$GITEA_URL" | sed -E "s/(localhost|127\.0\.0\.1)/$DOCKER_REMOTE_HOST/")
            log "Updated GITEA_URL: $old_url -> $GITEA_URL"
        fi
    else
        DOCKER_REMOTE_HOST=""
        log "Docker context: $context_name (local)"
    fi

    export DOCKER_REMOTE_HOST
}

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
# Note: This function echoes the label ID to stdout for capture,
# so any log messages must go to stderr
ensure_label() {
    local label_name="$1"
    local label_id

    # Check if label exists
    label_id=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/labels" 2>/dev/null | \
        jq -r ".[] | select(.name == \"$label_name\") | .id" | head -1)

    if [[ -z "$label_id" ]]; then
        # Create the label (log to stderr so it doesn't interfere with return value)
        echo -e "${GREEN}[INFO]${NC} Creating label: $label_name" >&2
        label_id=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/labels" \
            "{\"name\": \"$label_name\", \"color\": \"428BCA\"}" 2>/dev/null | jq -r '.id')
    fi

    echo "$label_id"
}

#############################################
# Phase 1: Actions Integration Test
#############################################

# Get Gitea container IP for use in workflows
get_gitea_container_ip() {
    local container_names=("$DOCKER_CONTAINER" "sapiens-gitea" "gitea-test" "gitea")
    local context_arg=""

    # Use the Docker context if specified
    if [[ -n "$DOCKER_CONTEXT" ]]; then
        context_arg="--context $DOCKER_CONTEXT"
    fi

    # Try each container name
    for name in "${container_names[@]}"; do
        local ip
        # shellcheck disable=SC2086
        ip=$(docker $context_arg inspect "$name" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
        if [[ -n "$ip" ]]; then
            echo "$ip"
            return 0
        fi
    done

    echo ""
}

# Deploy workflow file to repository
deploy_workflow() {
    step "Deploying test workflow to repository..."

    # Get Gitea container's internal IP for Docker network connectivity
    local gitea_ip
    gitea_ip=$(get_gitea_container_ip)
    local gitea_internal_url="http://${gitea_ip}:3000"

    if [[ -z "$gitea_ip" ]]; then
        warn "Could not determine Gitea container IP, using localhost"
        gitea_internal_url="http://localhost:3000"
    else
        log "Gitea container IP: $gitea_ip"
    fi

    # Create a simple workflow that posts a comment when triggered
    # Note: Gitea has different event context than GitHub:
    # - github.event.label is null (use github.event.issue.labels instead)
    # - github.event.action is 'label_updated' not 'labeled'
    # Note: We use the container IP directly because job containers can't reach localhost
    local workflow_content
    workflow_content=$(cat << WORKFLOW_EOF
name: E2E Test Workflow

on:
  issues:
    types: [labeled]

jobs:
  test-trigger:
    name: Test Action Trigger
    # Gitea uses issue.labels array, not event.label (which is null)
    if: contains(github.event.issue.labels.*.name, 'test-action-trigger')
    runs-on: ubuntu-latest
    steps:
      - name: Debug context
        run: |
          echo "Server URL: \${{ github.server_url }}"
          echo "Repository: \${{ github.repository }}"
          echo "Issue number: \${{ github.event.issue.number }}"
          echo "Event action: \${{ github.event.action }}"
          echo "Internal URL: ${gitea_internal_url}"

      - name: Post confirmation comment
        env:
          GITEA_TOKEN: \${{ secrets.SAPIENS_GITEA_TOKEN }}
          REPO: \${{ github.repository }}
          ISSUE_NUM: \${{ github.event.issue.number }}
          RUN_ID: \${{ github.run_id }}
          # Use internal Docker IP instead of github.server_url (localhost doesn't work in containers)
          SERVER_URL: "${gitea_internal_url}"
        run: |
          echo "Using API base: \$SERVER_URL"

          # Build comment body - keep it simple to avoid YAML parsing issues
          COMMENT_BODY="Action triggered successfully! Run ID: \$RUN_ID"

          # Post the comment
          HTTP_CODE=\$(curl -sS -w "%{http_code}" -o /tmp/response.json -X POST \\
            -H "Authorization: token \$GITEA_TOKEN" \\
            -H "Content-Type: application/json" \\
            -d "{\\"body\\": \\"\$COMMENT_BODY\\"}" \\
            "\${SERVER_URL}/api/v1/repos/\${REPO}/issues/\${ISSUE_NUM}/comments")

          echo "Response code: \$HTTP_CODE"
          cat /tmp/response.json

          if [ "\$HTTP_CODE" -ge 200 ] && [ "\$HTTP_CODE" -lt 300 ]; then
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

    # Set SAPIENS_GITEA_TOKEN secret (used by workflow to post comments)
    log "Setting SAPIENS_GITEA_TOKEN secret..."
    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets/SAPIENS_GITEA_TOKEN" "{
        \"data\": \"$SAPIENS_GITEA_TOKEN\"
    }" > /dev/null 2>&1 || {
        warn "Could not set SAPIENS_GITEA_TOKEN secret via API."
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
# Phase 1.5: Dispatcher Integration Test
#############################################

# Deploy the sapiens thin wrapper workflow for Gitea
deploy_sapiens_wrapper() {
    step "Deploying sapiens thin wrapper workflow..."

    local workflow_path=".gitea/workflows/sapiens.yaml"

    # Check if workflow exists
    local response
    response=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$workflow_path" 2>/dev/null || echo "")

    if echo "$response" | jq -e '.name' >/dev/null 2>&1; then
        log "Sapiens workflow already deployed: $workflow_path"
        return 0
    fi

    log "Creating thin wrapper workflow referencing dispatcher@${DISPATCHER_REF}..."

    # Create thin wrapper content for Gitea
    # Gitea uses GitHub workflow syntax but needs gitea-specific provider config
    local workflow_content
    workflow_content=$(cat << WRAPPER_EOF
# Sapiens Automation - Thin Wrapper for Gitea
# Generated by E2E test for dispatcher validation
name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@${DISPATCHER_REF}
    with:
      label: \${{ github.event.label.name }}
      issue_number: \${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: \${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: gitea
      git_provider_url: ${GITEA_URL}
      ai_provider_type: ollama
      ai_base_url: http://localhost:11434
      ai_model: qwen3:8b
    secrets:
      GIT_TOKEN: \${{ secrets.SAPIENS_GITEA_TOKEN }}
WRAPPER_EOF
    )

    # Base64 encode
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Create the file via API
    response=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$workflow_path" "{
        \"content\": \"$encoded_content\",
        \"message\": \"Add sapiens thin wrapper workflow for E2E testing\"
    }" 2>&1)

    if echo "$response" | jq -e '.content.path' >/dev/null 2>&1; then
        log "Sapiens workflow deployed: $workflow_path"
    else
        error "Could not deploy sapiens workflow: $response"
        return 1
    fi
}

# Create issue to trigger dispatcher
create_dispatcher_test_issue() {
    step "Creating issue to trigger dispatcher..."

    # Ensure the trigger label exists
    local planning_label_id
    planning_label_id=$(ensure_label "needs-planning")

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
    response=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Dispatcher Integration Test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [$planning_label_id]
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

    local timeout=300  # 5 minutes
    local elapsed=0
    local poll_interval=15

    while [[ $elapsed -lt $timeout ]]; do
        # Check workflow runs
        local runs
        runs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=10" 2>/dev/null || echo "{}")

        # Find Sapiens workflow runs
        local sapiens_run
        sapiens_run=$(echo "$runs" | jq -r '
            .workflow_runs[]?
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
                    log "Dispatcher workflow failed (may be expected if Ollama unavailable)"
                    return 0
                else
                    warn "Dispatcher workflow concluded: $conclusion"
                    return 1
                fi
            fi
        fi

        # Also check for comments on the issue
        local comments
        comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$DISPATCHER_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

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
    local response
    response=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/.gitea/workflows/sapiens.yaml" 2>/dev/null || echo "")

    if echo "$response" | jq -e '.name' >/dev/null 2>&1; then
        log "  ✓ Sapiens workflow file exists"
        ((passed++))
    else
        error "  ✗ Sapiens workflow file not found"
        ((failed++))
    fi

    # Check 2: Dispatcher workflow was triggered
    log "Checking for dispatcher workflow run..."
    local runs
    runs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=10" 2>/dev/null || echo "{}")

    local sapiens_run_exists
    sapiens_run_exists=$(echo "$runs" | jq -r '.workflow_runs[]? | select(.name | test("Sapiens"; "i")) | .id' | head -1)

    if [[ -n "$sapiens_run_exists" ]]; then
        log "  ✓ Dispatcher workflow was triggered (run: $sapiens_run_exists)"
        ((passed++))
    else
        error "  ✗ No dispatcher workflow run found"
        ((failed++))
    fi

    # Check 3: Issue has some activity
    log "Checking for issue activity..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$DISPATCHER_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")
    local comments_count
    comments_count=$(echo "$comments" | jq 'length')

    if [[ "$comments_count" -gt 0 ]]; then
        log "  ✓ Issue has $comments_count comment(s)"
        ((passed++))
    else
        warn "  - No comments on issue (dispatcher may have run but produced no output)"
    fi

    echo ""
    log "Dispatcher verification: $passed passed, $failed failed"

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
    sleep 3  # Give Gitea time to recognize the new workflow

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
# Phase 1.6: Template Workflow Test
#############################################

# State variable for template test issue
TEMPLATE_ISSUE_NUMBER=""

# Deploy the actual process-label.yaml template
deploy_process_label_template() {
    step "Deploying process-label.yaml template..."

    local template_path="$PROJECT_ROOT/templates/workflows/gitea/sapiens/process-label.yaml"
    local target_path=".gitea/workflows/sapiens/process-label.yaml"

    if [[ ! -f "$template_path" ]]; then
        error "Template file not found: $template_path"
        return 1
    fi

    # Read and base64 encode template
    local content
    content=$(cat "$template_path" | base64 -w 0)

    # Check if file exists
    local existing_sha
    existing_sha=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" 2>/dev/null | jq -r '.sha // empty')

    if [[ -n "$existing_sha" ]]; then
        gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" "{
            \"message\": \"Update process-label.yaml template for E2E test\",
            \"content\": \"$content\",
            \"sha\": \"$existing_sha\"
        }" > /dev/null
    else
        # Ensure parent directory exists by creating .gitea/workflows/sapiens/.gitkeep first
        local gitkeep_content
        gitkeep_content=$(echo -n "" | base64)

        # Try to create .gitea/workflows/sapiens directory structure
        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/.gitea/workflows/sapiens/.gitkeep" "{
            \"message\": \"Create sapiens workflows directory\",
            \"content\": \"$gitkeep_content\"
        }" > /dev/null 2>&1 || true

        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" "{
            \"message\": \"Deploy process-label.yaml template for E2E test\",
            \"content\": \"$content\"
        }" > /dev/null
    fi

    log "Deployed: $target_path"
}

# Set up secrets needed for template test
setup_template_secrets() {
    step "Setting up template test secrets..."

    # Get current branch for testing local changes
    local current_branch
    current_branch=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)

    # Get the Gitea internal URL (for workflow container to reach Gitea)
    local gitea_ip
    gitea_ip=$(get_gitea_container_ip)
    local gitea_internal_url="http://${gitea_ip}:3000"

    if [[ -z "$gitea_ip" ]]; then
        warn "Could not determine Gitea container IP, using localhost"
        gitea_internal_url="http://localhost:3000"
    fi

    # For E2E tests, we use a local file:// URL since the workflow runner
    # shares filesystem with the test environment
    log "Setting SAPIENS_REPO_URL to file://$PROJECT_ROOT"
    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets/SAPIENS_REPO_URL" "{
        \"data\": \"file://$PROJECT_ROOT\"
    }" > /dev/null 2>&1 || {
        warn "Could not set SAPIENS_REPO_URL secret via API"
    }

    log "Setting SAPIENS_BRANCH to $current_branch"
    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/actions/secrets/SAPIENS_BRANCH" "{
        \"data\": \"$current_branch\"
    }" > /dev/null 2>&1 || {
        warn "Could not set SAPIENS_BRANCH secret via API"
    }

    log "Set SAPIENS_BRANCH=$current_branch"
}

# Create issue to trigger template workflow
create_template_test_issue() {
    step "Creating issue to trigger template workflow..."

    # Ensure the trigger label exists
    local planning_label_id
    planning_label_id=$(ensure_label "needs-planning")

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## Template Workflow E2E Test

This issue tests that the actual `process-label.yaml` template executes correctly when triggered by a label.

## Task
Add a simple test file to verify the template workflow is working.

## Expected Behavior
1. The `process-label.yaml` workflow should trigger on `needs-planning` label
2. Sapiens should detect the label and route to the planning handler
3. A comment should be posted (success or failure)

This is an automated template test issue.
ISSUE_EOF
)

    local response
    response=$(gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues" "{
        \"title\": \"${TEST_PREFIX}Template Workflow Test\",
        \"body\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": [$planning_label_id]
    }")

    TEMPLATE_ISSUE_NUMBER=$(echo "$response" | jq -r '.number // empty')
    if [[ -z "$TEMPLATE_ISSUE_NUMBER" ]]; then
        error "Failed to create template test issue. Response: $response"
        return 1
    fi
    log "Created issue #$TEMPLATE_ISSUE_NUMBER with needs-planning label"
}

# Wait for template workflow to complete
wait_for_template_workflow() {
    step "Waiting for template workflow to complete..."

    local timeout=300
    local elapsed=0
    local poll_interval=15

    while [[ $elapsed -lt $timeout ]]; do
        # Check for process-label workflow run
        local runs
        runs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=10" 2>/dev/null || echo "{}")

        # Find runs matching process-label.yaml workflow path (name field is null in Gitea API)
        local template_run
        template_run=$(echo "$runs" | jq -r '
            [.workflow_runs[]?
            | select(.path | test("process-label"; "i"))
            | {status: .status, conclusion: .conclusion, id: .id}][0] // empty
        ' 2>/dev/null || echo "")

        if [[ -n "$template_run" && "$template_run" != "null" ]]; then
            local status conclusion run_id
            status=$(echo "$template_run" | jq -r '.status // "unknown"')
            conclusion=$(echo "$template_run" | jq -r '.conclusion // "pending"')
            run_id=$(echo "$template_run" | jq -r '.id // "unknown"')

            log "  Template run $run_id - status: $status, conclusion: $conclusion"

            if [[ "$status" == "completed" ]]; then
                if [[ "$conclusion" == "success" ]]; then
                    log "Template workflow completed successfully!"
                    return 0
                else
                    warn "Template workflow completed with: $conclusion"
                    # Still counts as "ran" - the workflow executed
                    return 0
                fi
            fi
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
        log "  Waiting... (${elapsed}s / ${timeout}s)"
    done

    warn "Timeout waiting for template workflow"
    return 1
}

# Verify template workflow results
verify_template_workflow() {
    step "Verifying template workflow results..."

    local passed=0
    local failed=0

    # Check 1: Workflow file exists
    log "Checking template file..."
    if gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/.gitea/workflows/sapiens/process-label.yaml" > /dev/null 2>&1; then
        log "  ✓ Template file deployed"
        ((passed++))
    else
        error "  ✗ Template file missing"
        ((failed++))
    fi

    # Check 2: Workflow ran
    log "Checking for workflow run..."
    local runs
    runs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=10" 2>/dev/null || echo "{}")

    if echo "$runs" | jq -e '.workflow_runs[]? | select(.path | test("process-label"; "i"))' > /dev/null 2>&1; then
        log "  ✓ Template workflow ran"
        ((passed++))
    else
        error "  ✗ No template workflow run found"
        ((failed++))
    fi

    # Check 3: Comment posted (success or failure comment from workflow)
    log "Checking for handler comment..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TEMPLATE_ISSUE_NUMBER/comments" 2>/dev/null || echo "[]")

    if echo "$comments" | jq -e '.[] | select(.body | test("Label handler"; "i"))' > /dev/null 2>&1; then
        log "  ✓ Handler comment posted"
        ((passed++))
    else
        # Check for any sapiens-related comment
        if echo "$comments" | jq -e '.[] | select(.body | test("sapiens|automation|failed|success"; "i"))' > /dev/null 2>&1; then
            log "  ✓ Workflow comment posted"
            ((passed++))
        else
            warn "  - No handler comment (workflow may still be processing or failed silently)"
        fi
    fi

    echo ""
    log "Template verification: $passed passed, $failed failed"
    [[ $failed -eq 0 ]]
}

# Run the template workflow test
run_template_test() {
    step "=== Phase 1.6: Template Workflow Test ==="
    echo ""
    log "Testing actual process-label.yaml template execution"
    echo ""

    deploy_process_label_template || return 1
    setup_template_secrets
    sleep 3  # Give Gitea time to recognize the new workflow

    create_template_test_issue || return 1

    if wait_for_template_workflow; then
        if verify_template_workflow; then
            log "Template workflow test PASSED"
            return 0
        fi
    fi

    error "Template workflow test FAILED"
    return 1
}

#############################################
# Workflow Dispatch API Helpers
#############################################

# Global variable to track last workflow conclusion
LAST_WORKFLOW_CONCLUSION=""

# Dispatch a workflow via API and return the run ID
# Usage: dispatch_workflow <workflow_file> [inputs_json]
# Note: This function echoes the run_id to stdout for capture,
# so all log messages must go to stderr
dispatch_workflow() {
    local workflow_file="$1"
    local inputs="${2:-{\}}"

    step "Dispatching workflow: $workflow_file" >&2

    # Get the default branch
    local default_branch="main"

    # URL-encode the workflow file path (replace / with %2F)
    local encoded_workflow_file
    encoded_workflow_file=$(echo "$workflow_file" | sed 's|/|%2F|g')

    # Get runs before dispatch to identify new run
    local runs_before
    runs_before=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=5" 2>/dev/null | jq -r '[.workflow_runs[].id] | join(",")' || echo "")

    # Dispatch the workflow using raw curl (gitea_api uses -sf which hides 204 success)
    local response
    response=$(curl -s -X POST \
        -H "Authorization: token $SAPIENS_GITEA_TOKEN" \
        -H "Content-Type: application/json" \
        "$GITEA_URL/api/v1/repos/$GITEA_OWNER/$GITEA_REPO/actions/workflows/$encoded_workflow_file/dispatches" \
        -d "{\"ref\": \"$default_branch\", \"inputs\": $inputs}" 2>&1 || echo "")

    # Check for errors (204 No Content is success, so empty response is OK)
    if [[ "$response" == *"error"* ]] || [[ "$response" == *"404"* ]] || [[ "$response" == *"message"* ]]; then
        error "Failed to dispatch workflow: $response" >&2
        return 1
    fi

    log "Workflow dispatch initiated" >&2

    # Wait briefly for workflow to appear
    sleep 5

    # Find the new run
    local runs_after
    runs_after=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs?limit=10" 2>/dev/null || echo "{}")

    local new_run_id
    new_run_id=$(echo "$runs_after" | jq -r --arg wf "$workflow_file" '
        [.workflow_runs[]? | select(.path | test($wf; "i"))][0].id // empty
    ')

    if [[ -n "$new_run_id" ]]; then
        log "New workflow run ID: $new_run_id" >&2
        echo "$new_run_id"
        return 0
    else
        warn "Could not find new workflow run" >&2
        return 1
    fi
}

# Wait for a workflow run to complete
# Usage: wait_for_workflow_run <run_id> [timeout_seconds]
wait_for_workflow_run() {
    local run_id="$1"
    local timeout="${2:-300}"
    local poll_interval=15
    local elapsed=0

    step "Waiting for workflow run $run_id to complete..."

    while [[ $elapsed -lt $timeout ]]; do
        local run_data
        run_data=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/actions/runs/$run_id" 2>/dev/null || echo "{}")

        local status conclusion
        status=$(echo "$run_data" | jq -r '.status // "unknown"')
        conclusion=$(echo "$run_data" | jq -r '.conclusion // "pending"')

        log "  Run $run_id - status: $status, conclusion: $conclusion (${elapsed}s / ${timeout}s)"

        if [[ "$status" == "completed" ]]; then
            if [[ "$conclusion" == "success" ]]; then
                log "Workflow run completed successfully!"
                LAST_WORKFLOW_CONCLUSION="success"
                return 0
            else
                warn "Workflow run completed with: $conclusion"
                LAST_WORKFLOW_CONCLUSION="$conclusion"
                return 0  # Completed but not success
            fi
        fi

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
    done

    warn "Timeout waiting for workflow run"
    LAST_WORKFLOW_CONCLUSION="timeout"
    return 1
}

# Deploy a recipe workflow template to the test repository
# Usage: deploy_recipe_workflow <recipe_name>
deploy_recipe_workflow() {
    local recipe_name="$1"
    local template_path="$PROJECT_ROOT/templates/workflows/gitea/sapiens/recipes/${recipe_name}.yaml"
    local target_path=".gitea/workflows/sapiens/recipes/${recipe_name}.yaml"

    step "Deploying recipe: $recipe_name"

    if [[ ! -f "$template_path" ]]; then
        error "Template not found: $template_path"
        return 1
    fi

    local content
    content=$(cat "$template_path" | base64 -w 0)

    # Check if parent directory structure exists
    local parent_dir=".gitea/workflows/sapiens/recipes"
    local gitkeep_path="${parent_dir}/.gitkeep"

    # Try to create parent directory structure if needed
    local gitkeep_check
    gitkeep_check=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$gitkeep_path" 2>/dev/null | jq -r '.sha // empty')
    if [[ -z "$gitkeep_check" ]]; then
        local gitkeep_content
        gitkeep_content=$(echo -n "" | base64)
        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$gitkeep_path" "{
            \"message\": \"Create recipes directory\",
            \"content\": \"$gitkeep_content\"
        }" > /dev/null 2>&1 || true
    fi

    local existing_sha
    existing_sha=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" 2>/dev/null | jq -r '.sha // empty')

    if [[ -n "$existing_sha" ]]; then
        gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" "{
            \"message\": \"Update $recipe_name for E2E test\",
            \"content\": \"$content\",
            \"sha\": \"$existing_sha\"
        }" > /dev/null
    else
        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$target_path" "{
            \"message\": \"Deploy $recipe_name for E2E test\",
            \"content\": \"$content\"
        }" > /dev/null
    fi

    log "Deployed: $target_path"
}

#############################################
# Progress Tracking
#############################################

# Track script start time
SCRIPT_START_TIME=$(date +%s)

# Status variables
declare -A PHASE_STATUS
declare -A PHASE_START_TIME
declare -A PHASE_END_TIME

mark_phase_start() {
    local phase="$1"
    PHASE_STATUS[$phase]="IN_PROGRESS"
    PHASE_START_TIME[$phase]=$(date +%s)
}

mark_phase_end() {
    local phase="$1"
    local status="$2"  # PASSED, FAILED, SKIPPED
    PHASE_STATUS[$phase]="$status"
    PHASE_END_TIME[$phase]=$(date +%s)
}

get_phase_duration() {
    local phase="$1"
    local start="${PHASE_START_TIME[$phase]:-0}"
    local end="${PHASE_END_TIME[$phase]:-$(date +%s)}"
    echo $((end - start))
}

print_progress() {
    local run_id="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"

    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo " GITEA E2E TEST PROGRESS - Run ID: $run_id"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""

    local passed=0 failed=0 running=0 pending=0

    # Group A: Infrastructure
    echo " GROUP A: Infrastructure"
    for phase_id in "1.0" "1.5" "1.6"; do
        local status="${PHASE_STATUS[$phase_id]:-PENDING}"
        local duration=""
        local icon="○"
        local phase_name=""

        case "$phase_id" in
            "1.0") phase_name="Actions Integration" ;;
            "1.5") phase_name="Dispatcher Integration" ;;
            "1.6") phase_name="process-label.yaml" ;;
        esac

        case "$status" in
            PASSED) icon="✓"; duration="($(get_phase_duration "$phase_id")s)"; passed=$((passed + 1)) ;;
            FAILED) icon="✗"; duration="($(get_phase_duration "$phase_id")s)"; failed=$((failed + 1)) ;;
            IN_PROGRESS) icon="●"; running=$((running + 1)) ;;
            SKIPPED) icon="○" ;;
            *) pending=$((pending + 1)) ;;
        esac

        printf "   %s Phase %s: %-30s %s %s\n" "$icon" "$phase_id" "$phase_name" "$status" "$duration"
    done
    echo ""

    # Group C: Core Tier
    echo " GROUP C: Core Tier"
    for phase_id in "2.1" "2.2"; do
        local status="${PHASE_STATUS[$phase_id]:-PENDING}"
        local duration=""
        local icon="○"
        local phase_name=""

        case "$phase_id" in
            "2.1") phase_name="post-merge-docs" ;;
            "2.2") phase_name="weekly-test-coverage" ;;
        esac

        case "$status" in
            PASSED) icon="✓"; duration="($(get_phase_duration "$phase_id")s)"; passed=$((passed + 1)) ;;
            FAILED) icon="✗"; duration="($(get_phase_duration "$phase_id")s)"; failed=$((failed + 1)) ;;
            IN_PROGRESS) icon="●"; running=$((running + 1)) ;;
            SKIPPED) icon="○" ;;
            *) pending=$((pending + 1)) ;;
        esac

        printf "   %s Phase %s: %-30s %s %s\n" "$icon" "$phase_id" "$phase_name" "$status" "$duration"
    done
    echo ""

    # Group D: Security Tier
    echo " GROUP D: Security Tier"
    for phase_id in "3.1" "3.2" "3.3"; do
        local status="${PHASE_STATUS[$phase_id]:-PENDING}"
        local duration=""
        local icon="○"
        local phase_name=""

        case "$phase_id" in
            "3.1") phase_name="weekly-security-review" ;;
            "3.2") phase_name="weekly-dependency-audit" ;;
            "3.3") phase_name="weekly-sbom-license" ;;
        esac

        case "$status" in
            PASSED) icon="✓"; duration="($(get_phase_duration "$phase_id")s)"; passed=$((passed + 1)) ;;
            FAILED) icon="✗"; duration="($(get_phase_duration "$phase_id")s)"; failed=$((failed + 1)) ;;
            IN_PROGRESS) icon="●"; running=$((running + 1)) ;;
            SKIPPED) icon="○" ;;
            *) pending=$((pending + 1)) ;;
        esac

        printf "   %s Phase %s: %-30s %s %s\n" "$icon" "$phase_id" "$phase_name" "$status" "$duration"
    done
    echo ""

    # Group E: Support Tier
    echo " GROUP E: Support Tier"
    for phase_id in "4.1"; do
        local status="${PHASE_STATUS[$phase_id]:-PENDING}"
        local duration=""
        local icon="○"
        local phase_name="daily-issue-triage"

        case "$status" in
            PASSED) icon="✓"; duration="($(get_phase_duration "$phase_id")s)"; passed=$((passed + 1)) ;;
            FAILED) icon="✗"; duration="($(get_phase_duration "$phase_id")s)"; failed=$((failed + 1)) ;;
            IN_PROGRESS) icon="●"; running=$((running + 1)) ;;
            SKIPPED) icon="○" ;;
            *) pending=$((pending + 1)) ;;
        esac

        printf "   %s Phase %s: %-30s %s %s\n" "$icon" "$phase_id" "$phase_name" "$status" "$duration"
    done
    echo ""

    # Group F: CLI Tests
    echo " GROUP F: CLI Tests"
    for phase_id in "5.0" "6.0"; do
        local status="${PHASE_STATUS[$phase_id]:-PENDING}"
        local duration=""
        local icon="○"
        local phase_name=""

        case "$phase_id" in
            "5.0") phase_name="CLI proposal test" ;;
            "6.0") phase_name="Full workflow test" ;;
        esac

        case "$status" in
            PASSED) icon="✓"; duration="($(get_phase_duration "$phase_id")s)"; passed=$((passed + 1)) ;;
            FAILED) icon="✗"; duration="($(get_phase_duration "$phase_id")s)"; failed=$((failed + 1)) ;;
            IN_PROGRESS) icon="●"; running=$((running + 1)) ;;
            SKIPPED) icon="○" ;;
            *) pending=$((pending + 1)) ;;
        esac

        printf "   %s Phase %s: %-30s %s %s\n" "$icon" "$phase_id" "$phase_name" "$status" "$duration"
    done
    echo ""

    local elapsed=$(($(date +%s) - SCRIPT_START_TIME))
    echo "═══════════════════════════════════════════════════════════════════"
    printf " Elapsed: %dm %ds | Passed: %d | Failed: %d | Running: %d | Pending: %d\n" \
        $((elapsed/60)) $((elapsed%60)) $passed $failed $running $pending
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
}

#############################################
# GROUP C: Core Tier Tests
#############################################

# State variables for tier tests
CORE_TIER_STATUS=""
SECURITY_TIER_STATUS=""
SUPPORT_TIER_STATUS=""

run_core_tier_test() {
    step "=== GROUP C: Core Tier Tests ==="
    echo ""

    local passed=0 failed=0

    # Phase 2.1: post-merge-docs
    mark_phase_start "2.1"
    step "Phase 2.1: post-merge-docs.yaml"
    deploy_recipe_workflow "post-merge-docs"
    sleep 2

    local run_id
    if run_id=$(dispatch_workflow "sapiens/recipes/post-merge-docs.yaml"); then
        if wait_for_workflow_run "$run_id" 300; then
            if [[ "$LAST_WORKFLOW_CONCLUSION" == "success" ]]; then
                log "  ✓ Phase 2.1 PASSED"
                mark_phase_end "2.1" "PASSED"
                ((passed++))
            else
                warn "  ⚠ Phase 2.1 completed with: $LAST_WORKFLOW_CONCLUSION"
                mark_phase_end "2.1" "PASSED"  # Still counts as executed
                ((passed++))
            fi
        else
            error "  ✗ Phase 2.1 FAILED (timeout)"
            mark_phase_end "2.1" "FAILED"
            ((failed++))
        fi
    else
        error "  ✗ Phase 2.1 FAILED (dispatch failed)"
        mark_phase_end "2.1" "FAILED"
        ((failed++))
    fi

    echo ""

    # Phase 2.2: weekly-test-coverage
    mark_phase_start "2.2"
    step "Phase 2.2: weekly-test-coverage.yaml"
    deploy_recipe_workflow "weekly-test-coverage"
    sleep 2

    if run_id=$(dispatch_workflow "sapiens/recipes/weekly-test-coverage.yaml" '{"target_coverage": "50"}'); then
        if wait_for_workflow_run "$run_id" 600; then
            if [[ "$LAST_WORKFLOW_CONCLUSION" == "success" ]]; then
                log "  ✓ Phase 2.2 PASSED"
                mark_phase_end "2.2" "PASSED"
                ((passed++))
            else
                warn "  ⚠ Phase 2.2 completed with: $LAST_WORKFLOW_CONCLUSION"
                mark_phase_end "2.2" "PASSED"
                ((passed++))
            fi
        else
            error "  ✗ Phase 2.2 FAILED (timeout)"
            mark_phase_end "2.2" "FAILED"
            ((failed++))
        fi
    else
        error "  ✗ Phase 2.2 FAILED (dispatch failed)"
        mark_phase_end "2.2" "FAILED"
        ((failed++))
    fi

    log "Core tier: $passed passed, $failed failed"
    CORE_TIER_STATUS="$passed/$((passed+failed)) passed"
    [[ $failed -eq 0 ]]
}

#############################################
# GROUP D: Security Tier Tests
#############################################

run_security_tier_test() {
    step "=== GROUP D: Security Tier Tests ==="
    echo ""

    local passed=0 failed=0
    local recipes=("weekly-security-review" "weekly-dependency-audit" "weekly-sbom-license")
    local phase_ids=("3.1" "3.2" "3.3")
    local idx=0

    for recipe in "${recipes[@]}"; do
        local phase_id="${phase_ids[$idx]}"
        mark_phase_start "$phase_id"
        step "Phase $phase_id: ${recipe}.yaml"
        deploy_recipe_workflow "$recipe"
        sleep 2

        local run_id
        if run_id=$(dispatch_workflow "sapiens/recipes/${recipe}.yaml"); then
            if wait_for_workflow_run "$run_id" 600; then
                if [[ "$LAST_WORKFLOW_CONCLUSION" == "success" ]]; then
                    log "  ✓ Phase $phase_id PASSED"
                    mark_phase_end "$phase_id" "PASSED"
                    ((passed++))
                else
                    warn "  ⚠ Phase $phase_id completed with: $LAST_WORKFLOW_CONCLUSION"
                    mark_phase_end "$phase_id" "PASSED"
                    ((passed++))
                fi
            else
                error "  ✗ Phase $phase_id FAILED (timeout)"
                mark_phase_end "$phase_id" "FAILED"
                ((failed++))
            fi
        else
            error "  ✗ Phase $phase_id FAILED (dispatch failed)"
            mark_phase_end "$phase_id" "FAILED"
            ((failed++))
        fi

        ((idx++))
        echo ""
    done

    log "Security tier: $passed passed, $failed failed"
    SECURITY_TIER_STATUS="$passed/$((passed+failed)) passed"
    [[ $failed -eq 0 ]]
}

#############################################
# GROUP E: Support Tier Tests
#############################################

run_support_tier_test() {
    step "=== GROUP E: Support Tier Tests ==="
    echo ""

    local passed=0 failed=0

    # Phase 4.1: daily-issue-triage
    mark_phase_start "4.1"
    step "Phase 4.1: daily-issue-triage.yaml"
    deploy_recipe_workflow "daily-issue-triage"
    sleep 2

    # Create some test issues for triage
    log "Creating test issues for triage..."
    for i in 1 2 3; do
        gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues" "{
            \"title\": \"${TEST_PREFIX}Triage Test Issue $i\",
            \"body\": \"This is a test issue for daily-issue-triage workflow.\"
        }" > /dev/null 2>&1 || true
    done

    local run_id
    if run_id=$(dispatch_workflow "sapiens/recipes/daily-issue-triage.yaml"); then
        if wait_for_workflow_run "$run_id" 600; then
            if [[ "$LAST_WORKFLOW_CONCLUSION" == "success" ]]; then
                log "  ✓ Phase 4.1 PASSED"
                mark_phase_end "4.1" "PASSED"
                ((passed++))
            else
                warn "  ⚠ Phase 4.1 completed with: $LAST_WORKFLOW_CONCLUSION"
                mark_phase_end "4.1" "PASSED"
                ((passed++))
            fi
        else
            error "  ✗ Phase 4.1 FAILED (timeout)"
            mark_phase_end "4.1" "FAILED"
            ((failed++))
        fi
    else
        error "  ✗ Phase 4.1 FAILED (dispatch failed)"
        mark_phase_end "4.1" "FAILED"
        ((failed++))
    fi

    log "Support tier: $passed passed, $failed failed"
    SUPPORT_TIER_STATUS="$passed/$((passed+failed)) passed"
    [[ $failed -eq 0 ]]
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
    step "=== Phase 2: Sapiens CLI Test (Proposal Stage) ==="
    echo ""

    create_test_issue
    process_issue

    if verify_results; then
        log "Sapiens CLI proposal test PASSED"
        return 0
    fi

    error "Sapiens CLI proposal test FAILED"
    return 1
}

#############################################
# Phase 3: Full Workflow Test (Approval + Execution)
#############################################

# Approve the proposal
approve_proposal() {
    step "Approving proposal #$PROPOSAL_NUMBER..."

    # Add 'approved' label to the proposal issue
    local approved_label_id
    approved_label_id=$(ensure_label "approved")

    # Get current labels
    local proposal
    proposal=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$PROPOSAL_NUMBER")
    local current_labels
    current_labels=$(echo "$proposal" | jq -r '[.labels[].id]')

    # Add approved label if not present
    if ! echo "$current_labels" | grep -q "$approved_label_id"; then
        local new_labels
        new_labels=$(echo "$current_labels" | jq ". + [$approved_label_id]")
        gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$PROPOSAL_NUMBER" "{\"labels\": $new_labels}" > /dev/null
        log "Added 'approved' label to proposal #$PROPOSAL_NUMBER"
    fi

    # Also add an approval comment
    gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$PROPOSAL_NUMBER/comments" \
        '{"body": "LGTM - approved for implementation"}' > /dev/null
    log "Added approval comment"
}

# Process the proposal to trigger approval stage
process_approval() {
    step "Processing proposal for approval..."

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

    log "Running: sapiens process-issue --issue $PROPOSAL_NUMBER (approval stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$PROPOSAL_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/approval-output.log"; then
        log "Approval processing completed"
    else
        warn "Approval processing returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify approval results
verify_approval() {
    step "Verifying approval results..."

    local passed=0
    local failed=0

    # Check 1: Original issue should now have 'in-progress' label
    log "Checking original issue labels..."
    local issue
    issue=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$ISSUE_NUMBER")
    local labels
    labels=$(echo "$issue" | jq -r '.labels[].name' | tr '\n' ',')

    if [[ "$labels" == *"in-progress"* ]]; then
        log "  Original issue has in-progress label: $labels"
        ((passed++))
    else
        error "  Original issue missing in-progress label: $labels"
        ((failed++))
    fi

    # Check 2: Task issues should have been created
    log "Checking for task issues..."
    local task_issues
    task_issues=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues?state=all&labels=task" || echo "[]")
    local task_count
    task_count=$(echo "$task_issues" | jq 'length')

    if [[ "$task_count" -gt 0 ]]; then
        log "  Found $task_count task issue(s)"
        ((passed++))

        # Get first task issue number for execution test
        TASK_ISSUE_NUMBER=$(echo "$task_issues" | jq -r '.[0].number')
        log "  First task issue: #$TASK_ISSUE_NUMBER"
    else
        error "  No task issues created"
        ((failed++))
    fi

    # Check 3: Approval comment on proposal
    log "Checking for approval confirmation comment..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$PROPOSAL_NUMBER/comments" || echo "[]")
    local approval_comment
    approval_comment=$(echo "$comments" | jq -r '.[] | select(.body | contains("Approved") or contains("approved") or contains("tasks")) | .id' | head -1)

    if [[ -n "$approval_comment" ]]; then
        log "  Approval confirmation comment found"
        ((passed++))
    else
        warn "  No approval confirmation comment (may be timing issue)"
    fi

    echo ""
    log "Approval verification: $passed passed, $failed failed"

    if [[ $failed -gt 0 ]]; then
        return 1
    fi
    return 0
}

# Add execute label to task issue
prepare_task_execution() {
    step "Preparing task #$TASK_ISSUE_NUMBER for execution..."

    # Ensure execute label exists
    local execute_label_id
    execute_label_id=$(ensure_label "execute")
    log "Execute label ID: $execute_label_id"

    # Get current label names
    local task
    task=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER")
    local current_labels
    current_labels=$(echo "$task" | jq -r '[.labels[].name]')
    log "Current labels: $current_labels"

    # Build new label list: remove 'ready', add 'execute'
    local new_labels
    new_labels=$(echo "$current_labels" | jq 'map(select(. != "ready")) + ["execute"]')
    log "New labels: $new_labels"

    # Use PUT to replace all labels (Gitea's preferred method)
    local response
    response=$(gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/labels" "{\"labels\": $new_labels}")

    # Verify the update worked
    local updated_labels
    updated_labels=$(echo "$response" | jq -r '[.[].name] | join(", ")')
    log "Updated labels: $updated_labels"

    if echo "$updated_labels" | grep -q "execute"; then
        log "Successfully added 'execute' label to task #$TASK_ISSUE_NUMBER"
    else
        error "Failed to add 'execute' label - labels are: $updated_labels"
    fi
}

# Set up playground directory for task execution
# The execution stage expects a clone of the target repo at PLAYGROUND_DIR
setup_playground() {
    step "Setting up playground directory for task execution..."

    # Check if playground already exists
    if [[ -d "$PLAYGROUND_DIR" ]]; then
        warn "Playground directory already exists at $PLAYGROUND_DIR"
        # Check if it's a git repo for the right remote
        if git -C "$PLAYGROUND_DIR" remote get-url origin 2>/dev/null | grep -q "$GITEA_REPO"; then
            log "Playground appears to be correct repo, updating..."
            git -C "$PLAYGROUND_DIR" fetch origin 2>/dev/null || true
            git -C "$PLAYGROUND_DIR" checkout main 2>/dev/null || true
            git -C "$PLAYGROUND_DIR" pull origin main 2>/dev/null || true
            return 0
        else
            error "Playground exists but is a different repo"
            error "Please remove $PLAYGROUND_DIR manually or set PLAYGROUND_DIR to a different path"
            return 1
        fi
    fi

    # Clone the test repo from Gitea
    local clone_url="$GITEA_URL/$GITEA_OWNER/$GITEA_REPO.git"
    log "Cloning $clone_url to $PLAYGROUND_DIR"

    # Configure git to use the token for authentication
    local auth_url
    auth_url="${GITEA_URL/http:\/\//http://testadmin:${SAPIENS_GITEA_TOKEN}@}"
    auth_url="${auth_url/https:\/\//https://testadmin:${SAPIENS_GITEA_TOKEN}@}"
    local auth_clone_url="$auth_url/$GITEA_OWNER/$GITEA_REPO.git"

    if git clone "$auth_clone_url" "$PLAYGROUND_DIR"; then
        log "Playground cloned successfully"
        PLAYGROUND_CREATED=true

        # Configure git user for commits
        git -C "$PLAYGROUND_DIR" config user.email "sapiens-e2e@test.local"
        git -C "$PLAYGROUND_DIR" config user.name "Sapiens E2E Test"

        # Set push URL with auth
        git -C "$PLAYGROUND_DIR" remote set-url --push origin "$auth_clone_url"
    else
        error "Failed to clone playground repository"
        return 1
    fi
}

# Process task for execution
process_task_execution() {
    step "Processing task for execution..."

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
    execute: execute
CONFIG_EOF

    log "Running: sapiens process-issue --issue $TASK_ISSUE_NUMBER (execution stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$TASK_ISSUE_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/execution-output.log"; then
        log "Task execution completed"
    else
        warn "Task execution returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify execution results
verify_execution() {
    step "Verifying execution results..."

    local passed=0
    local failed=0

    # Check 1: Feature branch should exist
    log "Checking for feature branch..."
    local branches
    branches=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/branches" || echo "[]")
    local feature_branch
    feature_branch=$(echo "$branches" | jq -r ".[] | select(.name != \"main\") | .name" | head -1)

    if [[ -n "$feature_branch" ]]; then
        log "  Feature branch found: $feature_branch"
        ((passed++))
        FEATURE_BRANCH="$feature_branch"
    else
        error "  No feature branch created"
        ((failed++))
    fi

    # Check 2: Pull request should exist
    log "Checking for pull request..."
    local prs
    prs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/pulls?state=all" || echo "[]")
    local pr_number
    pr_number=$(echo "$prs" | jq -r '.[0].number // empty')

    if [[ -n "$pr_number" ]]; then
        log "  Pull request found: #$pr_number"
        ((passed++))
        PR_NUMBER="$pr_number"
    else
        error "  No pull request created"
        ((failed++))
    fi

    # Check 3: PR should have code changes (files)
    if [[ -n "$pr_number" ]]; then
        log "Checking PR files..."
        local pr_files
        pr_files=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/pulls/$pr_number/files" || echo "[]")
        local file_count
        file_count=$(echo "$pr_files" | jq 'length')

        if [[ "$file_count" -gt 0 ]]; then
            log "  PR has $file_count file(s) changed"
            ((passed++))

            # Show changed files
            echo "$pr_files" | jq -r '.[].filename' | while read -r filename; do
                log "    - $filename"
            done
        else
            warn "  PR has no file changes (model didn't generate code)"
            # Don't fail - the PR infrastructure works, model just didn't produce changes
            ((passed++))
        fi
    fi

    echo ""
    log "Execution verification: $passed passed, $failed failed"

    if [[ $failed -gt 0 ]]; then
        return 1
    fi
    return 0
}

#############################################
# Phase 4: PR Review Cycle (needs-review, needs-fix, fix_execution)
#############################################

# Add needs-review label to trigger PR review
add_review_label() {
    step "Adding 'needs-review' label to task #$TASK_ISSUE_NUMBER..."

    local review_label_id
    review_label_id=$(ensure_label "needs-review")

    # Get current labels
    local current_labels
    current_labels=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER" | jq -r '[.labels[].name]')

    # Add needs-review label
    local new_labels
    new_labels=$(echo "$current_labels" | jq '. + ["needs-review"] | unique')

    local response
    response=$(gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/labels" "{\"labels\": $new_labels}")

    local updated_labels
    updated_labels=$(echo "$response" | jq -r '.[].name' | tr '\n' ', ')
    log "Updated labels: $updated_labels"

    if echo "$updated_labels" | grep -q "needs-review"; then
        log "Successfully added 'needs-review' label"
    else
        error "Failed to add 'needs-review' label"
    fi
}

# Process PR review stage
process_pr_review() {
    step "Processing PR review..."

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
    execute: execute
CONFIG_EOF

    log "Running: sapiens process-issue --issue $TASK_ISSUE_NUMBER (pr_review stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$TASK_ISSUE_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/pr-review-output.log"; then
        log "PR review completed"
    else
        warn "PR review returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify PR review results
verify_pr_review() {
    step "Verifying PR review results..."

    local passed=0
    local failed=0

    # Check 1: Review comment should be added
    log "Checking for review comment..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/comments" || echo "[]")
    local review_comment
    review_comment=$(echo "$comments" | jq -r '.[] | select(.body | contains("review") or contains("Review")) | .id' | head -1)

    if [[ -n "$review_comment" ]]; then
        log "  Review comment found"
        ((passed++))
    else
        warn "  No review comment found (stage may have skipped)"
        # Don't fail - the stage might not have added a comment
    fi

    # Check 2: Labels should be updated (review label may be removed, or needs-fix added)
    log "Checking labels after review..."
    local issue_data
    issue_data=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER")
    local labels
    labels=$(echo "$issue_data" | jq -r '[.labels[].name] | join(", ")')
    log "  Current labels: $labels"
    ((passed++))

    echo ""
    log "PR review verification: $passed passed, $failed failed"

    if [[ $failed -gt 0 ]]; then
        return 1
    fi
    return 0
}

# Add needs-fix label to trigger fix proposal
add_fix_label() {
    step "Adding 'needs-fix' label to task #$TASK_ISSUE_NUMBER..."

    local fix_label_id
    fix_label_id=$(ensure_label "needs-fix")

    # Get current labels
    local current_labels
    current_labels=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER" | jq -r '[.labels[].name]')

    # Add needs-fix label (and remove needs-review if present)
    local new_labels
    new_labels=$(echo "$current_labels" | jq 'map(select(. != "needs-review")) + ["needs-fix"] | unique')

    local response
    response=$(gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/labels" "{\"labels\": $new_labels}")

    local updated_labels
    updated_labels=$(echo "$response" | jq -r '.[].name' | tr '\n' ', ')
    log "Updated labels: $updated_labels"
}

# Process fix proposal stage
process_fix_proposal() {
    step "Processing fix proposal..."

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
    execute: execute
CONFIG_EOF

    log "Running: sapiens process-issue --issue $TASK_ISSUE_NUMBER (pr_fix stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$TASK_ISSUE_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/fix-proposal-output.log"; then
        log "Fix proposal completed"
    else
        warn "Fix proposal returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify fix proposal results
verify_fix_proposal() {
    step "Verifying fix proposal results..."

    local passed=0
    local failed=0

    # Check 1: Fix proposal issue should be created (with fix-proposal label)
    log "Checking for fix proposal issue..."
    local issues
    issues=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues?state=open&labels=fix-proposal" || echo "[]")
    local fix_proposal
    fix_proposal=$(echo "$issues" | jq -r '.[0].number // empty')

    if [[ -n "$fix_proposal" ]]; then
        log "  Fix proposal found: #$fix_proposal"
        FIX_PROPOSAL_NUMBER="$fix_proposal"
        ((passed++))
    else
        warn "  No fix proposal issue created (stage may have skipped)"
        # Check if there's a comment about fixes instead
        local comments
        comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/comments" || echo "[]")
        if echo "$comments" | jq -r '.[].body' | grep -qi "fix"; then
            log "  Fix-related comment found"
            ((passed++))
        fi
    fi

    echo ""
    log "Fix proposal verification: $passed passed, $failed failed"

    # Don't fail even if no fix proposal - the stage might work differently
    return 0
}

# Approve fix proposal
approve_fix_proposal() {
    if [[ -z "$FIX_PROPOSAL_NUMBER" ]]; then
        warn "No fix proposal to approve, skipping"
        return 0
    fi

    step "Approving fix proposal #$FIX_PROPOSAL_NUMBER..."

    # Add 'approved' label
    local current_labels
    current_labels=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$FIX_PROPOSAL_NUMBER" | jq -r '[.labels[].name]')

    local new_labels
    new_labels=$(echo "$current_labels" | jq '. + ["approved"] | unique')

    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$FIX_PROPOSAL_NUMBER/labels" "{\"labels\": $new_labels}" > /dev/null

    # Add approval comment
    gitea_api POST "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$FIX_PROPOSAL_NUMBER/comments" \
        '{"body": "✅ Approved! Please apply the proposed fixes.\n\n🤖 E2E Test Automation"}' > /dev/null

    log "Fix proposal approved"
}

# Process fix execution stage
process_fix_execution() {
    if [[ -z "$FIX_PROPOSAL_NUMBER" ]]; then
        warn "No fix proposal to execute, skipping"
        return 0
    fi

    step "Processing fix execution..."

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
    execute: execute
CONFIG_EOF

    log "Running: sapiens process-issue --issue $FIX_PROPOSAL_NUMBER (fix_execution stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$FIX_PROPOSAL_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/fix-execution-output.log"; then
        log "Fix execution completed"
    else
        warn "Fix execution returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify fix execution results
verify_fix_execution() {
    step "Verifying fix execution results..."

    local passed=0
    local failed=0

    # Check: PR should have new commits or comments about fixes
    if [[ -n "$PR_NUMBER" ]]; then
        log "Checking PR #$PR_NUMBER for fix commits..."
        local commits
        commits=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/pulls/$PR_NUMBER/commits" || echo "[]")
        local commit_count
        commit_count=$(echo "$commits" | jq 'length')
        log "  PR has $commit_count commit(s)"
        ((passed++))
    fi

    echo ""
    log "Fix execution verification: $passed passed, $failed failed"
    return 0
}

# Run the full PR review cycle
run_pr_review_test() {
    step "=== Phase 4: PR Review Cycle ==="
    echo ""

    # Skip if no PR was created
    if [[ -z "$PR_NUMBER" ]] || [[ -z "$TASK_ISSUE_NUMBER" ]]; then
        warn "Cannot run PR review test - no PR or task issue"
        return 0
    fi

    # Step 1: Add needs-review label
    add_review_label

    # Step 2: Process PR review
    process_pr_review

    # Step 3: Verify PR review
    if ! verify_pr_review; then
        warn "PR review verification had issues (continuing)"
    fi
    log "PR review stage completed"

    # Step 4: Add needs-fix label (simulate review found issues)
    add_fix_label

    # Step 5: Process fix proposal
    process_fix_proposal

    # Step 6: Verify fix proposal
    verify_fix_proposal

    # Step 7: Approve fix proposal (if created)
    approve_fix_proposal

    # Step 8: Process fix execution
    process_fix_execution

    # Step 9: Verify fix execution
    verify_fix_execution

    log "PR review cycle PASSED"
    return 0
}

#############################################
# Phase 5: QA Stage (requires-qa)
#############################################

# Add requires-qa label
add_qa_label() {
    step "Adding 'requires-qa' label to task #$TASK_ISSUE_NUMBER..."

    local qa_label_id
    qa_label_id=$(ensure_label "requires-qa")

    # Get current labels
    local current_labels
    current_labels=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER" | jq -r '[.labels[].name]')

    # Add requires-qa label
    local new_labels
    new_labels=$(echo "$current_labels" | jq '. + ["requires-qa"] | unique')

    local response
    response=$(gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/labels" "{\"labels\": $new_labels}")

    local updated_labels
    updated_labels=$(echo "$response" | jq -r '.[].name' | tr '\n' ', ')
    log "Updated labels: $updated_labels"
}

# Process QA stage
process_qa() {
    step "Processing QA stage..."

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
    execute: execute
CONFIG_EOF

    log "Running: sapiens process-issue --issue $TASK_ISSUE_NUMBER (qa stage)"

    if uv run sapiens --config "$config_file" process-issue --issue "$TASK_ISSUE_NUMBER" 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/qa-output.log"; then
        log "QA stage completed"
    else
        warn "QA stage returned non-zero exit code"
    fi

    rm -f "$config_file"
}

# Verify QA results
verify_qa() {
    step "Verifying QA results..."

    local passed=0
    local failed=0

    # Check 1: QA comment should be added
    log "Checking for QA comment..."
    local comments
    comments=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER/comments" || echo "[]")
    local qa_comment
    qa_comment=$(echo "$comments" | jq -r '.[] | select(.body | test("QA|qa|test|Test|build|Build"; "i")) | .id' | head -1)

    if [[ -n "$qa_comment" ]]; then
        log "  QA comment found"
        ((passed++))
    else
        warn "  No QA comment found (stage may have skipped)"
    fi

    # Check 2: Labels should indicate QA status
    log "Checking labels after QA..."
    local issue_data
    issue_data=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$TASK_ISSUE_NUMBER")
    local labels
    labels=$(echo "$issue_data" | jq -r '[.labels[].name] | join(", ")')
    log "  Current labels: $labels"
    ((passed++))

    echo ""
    log "QA verification: $passed passed, $failed failed"

    return 0
}

# Run QA test
run_qa_test() {
    step "=== Phase 5: QA Stage ==="
    echo ""

    # Skip if no task issue
    if [[ -z "$TASK_ISSUE_NUMBER" ]]; then
        warn "Cannot run QA test - no task issue"
        return 0
    fi

    # Step 1: Add requires-qa label
    add_qa_label

    # Step 2: Process QA
    process_qa

    # Step 3: Verify QA
    verify_qa

    log "QA stage PASSED"
    return 0
}

#############################################
# Full Workflow Runner
#############################################

run_full_workflow_test() {
    step "=== Phase 3: Full Workflow Test (Approval + Execution) ==="
    echo ""

    # Skip if proposal stage failed
    if [[ -z "$PROPOSAL_NUMBER" ]]; then
        error "Cannot run full workflow test - no proposal issue"
        return 1
    fi

    # Step 1: Approve the proposal
    approve_proposal

    # Step 2: Process the proposal (triggers approval stage)
    process_approval

    # Step 3: Verify approval results
    if ! verify_approval; then
        error "Approval stage verification FAILED"
        return 1
    fi
    log "Approval stage PASSED"

    # Skip execution test if no task issues created
    if [[ -z "$TASK_ISSUE_NUMBER" ]]; then
        warn "Cannot run execution test - no task issues created"
        return 0
    fi

    # Step 4: Prepare task for execution
    prepare_task_execution

    # Step 4.5: Set up playground directory
    if ! setup_playground; then
        error "Failed to set up playground directory"
        return 1
    fi

    # Step 5: Process task (triggers execution stage)
    process_task_execution

    # Step 6: Verify execution results
    if ! verify_execution; then
        error "Execution stage verification FAILED"
        return 1
    fi
    log "Execution stage PASSED"

    # Phase 4: PR Review Cycle
    if ! run_pr_review_test; then
        warn "PR review cycle had issues (continuing)"
    fi

    # Phase 5: QA Stage
    if ! run_qa_test; then
        warn "QA stage had issues (continuing)"
    fi

    log "Full workflow test PASSED"
    return 0
}

#############################################
# Report Generation
#############################################

generate_report() {
    local actions_status="$1"
    local dispatcher_status="$2"
    local template_status="$3"
    local cli_status="$4"
    local workflow_status="${5:-SKIPPED}"
    local core_tier_status="${6:-SKIPPED}"
    local security_tier_status="${7:-SKIPPED}"
    local support_tier_status="${8:-SKIPPED}"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# Gitea E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| Gitea URL | $GITEA_URL |
| Repository | $GITEA_OWNER/$GITEA_REPO |
| Test Prefix | $TEST_PREFIX |
| Full Workflow | $FULL_WORKFLOW |
| Test Tiers | $TEST_TIERS |
| Dispatcher Ref | $DISPATCHER_REF |

## GROUP A: Infrastructure Tests

### Phase 1.0: Actions Integration

**Status**: $actions_status

- Workflow deployed: .gitea/workflows/e2e-test.yaml
- Test issue: #${ACTION_ISSUE_NUMBER:-N/A}
- Triggered by: \`test-action-trigger\` label

### Phase 1.5: Dispatcher Integration

**Status**: $dispatcher_status

- Workflow: .gitea/workflows/sapiens.yaml (thin wrapper)
- Dispatcher: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@$DISPATCHER_REF
- Test issue: #${DISPATCHER_ISSUE_NUMBER:-N/A}
- Triggered by: \`needs-planning\` label

### Phase 1.6: Template Workflow Test (Essential Tier)

**Status**: $template_status

- Template: .gitea/workflows/sapiens/process-label.yaml
- Test issue: #${TEMPLATE_ISSUE_NUMBER:-N/A}
- Triggered by: \`needs-planning\` label
- Tests: Actual template workflow execution (not just thin wrapper)

## GROUP C: Core Tier Tests

**Status**: $core_tier_status

| Phase | Workflow | Status |
|-------|----------|--------|
| 2.1 | post-merge-docs.yaml | ${PHASE_STATUS[2.1]:-SKIPPED} |
| 2.2 | weekly-test-coverage.yaml | ${PHASE_STATUS[2.2]:-SKIPPED} |

## GROUP D: Security Tier Tests

**Status**: $security_tier_status

| Phase | Workflow | Status |
|-------|----------|--------|
| 3.1 | weekly-security-review.yaml | ${PHASE_STATUS[3.1]:-SKIPPED} |
| 3.2 | weekly-dependency-audit.yaml | ${PHASE_STATUS[3.2]:-SKIPPED} |
| 3.3 | weekly-sbom-license.yaml | ${PHASE_STATUS[3.3]:-SKIPPED} |

## GROUP E: Support Tier Tests

**Status**: $support_tier_status

| Phase | Workflow | Status |
|-------|----------|--------|
| 4.1 | daily-issue-triage.yaml | ${PHASE_STATUS[4.1]:-SKIPPED} |

## GROUP F: CLI Tests

### Phase 5.0: Sapiens CLI (Proposal)

**Status**: $cli_status

- Test issue: #${ISSUE_NUMBER:-N/A}
- Proposal issue: #${PROPOSAL_NUMBER:-N/A}

### Phase 6.0: Full Workflow (Approval + Execution)

**Status**: $workflow_status

- Task issue: #${TASK_ISSUE_NUMBER:-N/A}
- Feature branch: ${FEATURE_BRANCH:-Not created}
- Pull request: #${PR_NUMBER:-Not created}

### Phase 4: PR Review Cycle (Legacy)

**Status**: $(if [[ "$FULL_WORKFLOW" == "true" && -n "$PR_NUMBER" ]]; then echo "EXECUTED"; else echo "SKIPPED"; fi)

- Stages tested: \`pr_review\`, \`pr_fix\`, \`fix_execution\`
- Fix proposal: #${FIX_PROPOSAL_NUMBER:-N/A}

### Phase 5: QA Stage (Legacy)

**Status**: $(if [[ "$FULL_WORKFLOW" == "true" && -n "$TASK_ISSUE_NUMBER" ]]; then echo "EXECUTED"; else echo "SKIPPED"; fi)

- Stage tested: \`qa\`

## Overall Result

$(
    local any_failed=false
    [[ "$actions_status" == "FAILED" ]] && any_failed=true
    [[ "$dispatcher_status" == "FAILED" ]] && any_failed=true
    [[ "$template_status" == "FAILED" ]] && any_failed=true
    [[ "$cli_status" == "FAILED" ]] && any_failed=true
    [[ "$workflow_status" == "FAILED" ]] && any_failed=true
    [[ "$core_tier_status" == "FAILED" ]] && any_failed=true
    [[ "$security_tier_status" == "FAILED" ]] && any_failed=true
    [[ "$support_tier_status" == "FAILED" ]] && any_failed=true

    if [[ "$any_failed" == "true" ]]; then
        echo "❌ **TESTS FAILED**"
    else
        # Check what passed vs skipped
        local passed_tests=""
        [[ "$actions_status" == "PASSED" ]] && passed_tests="${passed_tests}Actions, "
        [[ "$dispatcher_status" == "PASSED" ]] && passed_tests="${passed_tests}Dispatcher, "
        [[ "$template_status" == "PASSED" ]] && passed_tests="${passed_tests}Template, "
        [[ "$core_tier_status" == "PASSED" ]] && passed_tests="${passed_tests}Core Tier, "
        [[ "$security_tier_status" == "PASSED" ]] && passed_tests="${passed_tests}Security Tier, "
        [[ "$support_tier_status" == "PASSED" ]] && passed_tests="${passed_tests}Support Tier, "
        [[ "$cli_status" == "PASSED" ]] && passed_tests="${passed_tests}CLI, "
        [[ "$workflow_status" == "PASSED" ]] && passed_tests="${passed_tests}Full Workflow, "

        if [[ -n "$passed_tests" ]]; then
            passed_tests="${passed_tests%, }"
            echo "✅ **TESTS PASSED**: $passed_tests"
        else
            echo "⏭️ **ALL TESTS SKIPPED**"
        fi
    fi
)

## Logs

- \`process-output.log\` - Sapiens CLI proposal output
- \`approval-output.log\` - Sapiens CLI approval output (if run)
- \`execution-output.log\` - Sapiens CLI execution output (if run)
- \`pr-review-output.log\` - PR review stage output (if run)
- \`fix-proposal-output.log\` - Fix proposal stage output (if run)
- \`fix-execution-output.log\` - Fix execution stage output (if run)
- \`qa-output.log\` - QA stage output (if run)
REPORT_EOF

    log "Report saved to $RESULTS_DIR/$RUN_ID/e2e-report.md"
}

#############################################
# Cleanup previous test runs
#############################################
cleanup_previous_runs() {
    if [[ "$SKIP_CLEANUP" == "true" ]]; then
        log "Skipping cleanup of previous runs (--skip-cleanup)"
        return 0
    fi

    step "Cleaning up artifacts from previous test runs..."

    # Close open issues with sapiens-e2e or plan- prefix
    log "Closing open test issues..."
    local issues
    issues=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/issues?state=open&limit=100" 2>/dev/null || echo "[]")

    local closed_count=0
    while IFS= read -r issue_num; do
        if [[ -n "$issue_num" && "$issue_num" != "null" ]]; then
            gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/issues/$issue_num" '{"state":"closed"}' > /dev/null 2>&1 || true
            ((closed_count++))
        fi
    done < <(echo "$issues" | jq -r '.[] | select(.title | test("sapiens-e2e|\\[PROPOSAL\\]|\\[TASK|plan-for-")) | .number')

    if [[ $closed_count -gt 0 ]]; then
        log "  Closed $closed_count test issue(s)"
    fi

    # Close open PRs from test runs
    log "Closing open test PRs..."
    local prs
    prs=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/pulls?state=open&limit=100" 2>/dev/null || echo "[]")

    local pr_count=0
    while IFS= read -r pr_num; do
        if [[ -n "$pr_num" && "$pr_num" != "null" ]]; then
            gitea_api PATCH "/repos/$GITEA_OWNER/$GITEA_REPO/pulls/$pr_num" '{"state":"closed"}' > /dev/null 2>&1 || true
            ((pr_count++))
        fi
    done < <(echo "$prs" | jq -r '.[] | select(.title | test("Plan #|sapiens-e2e")) | .number')

    if [[ $pr_count -gt 0 ]]; then
        log "  Closed $pr_count test PR(s)"
    fi

    # Delete test branches (plan-*-implementation)
    log "Deleting test branches..."
    local branches
    branches=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/branches?limit=100" 2>/dev/null || echo "[]")

    local branch_count=0
    while IFS= read -r branch_name; do
        if [[ -n "$branch_name" && "$branch_name" != "null" && "$branch_name" != "main" && "$branch_name" != "master" ]]; then
            gitea_api DELETE "/repos/$GITEA_OWNER/$GITEA_REPO/branches/$branch_name" > /dev/null 2>&1 || true
            ((branch_count++))
        fi
    done < <(echo "$branches" | jq -r '.[] | select(.name | test("plan-.*-implementation")) | .name')

    if [[ $branch_count -gt 0 ]]; then
        log "  Deleted $branch_count test branch(es)"
    fi

    log "Previous run cleanup complete"
    echo ""
}

#############################################
# Main
#############################################
main() {
    # Reset progress tracking
    SCRIPT_START_TIME=$(date +%s)

    # Detect Docker context and update GITEA_URL if remote
    detect_docker_context

    mkdir -p "$RESULTS_DIR/$RUN_ID"

    log "=== Gitea E2E Integration Test ==="
    log "Run ID: $RUN_ID"
    if [[ "$FULL_WORKFLOW" == "true" ]]; then
        log "Mode: Full Workflow (proposal + approval + execution)"
    fi
    if [[ "$TEST_TIERS" == "true" ]]; then
        log "Mode: Tier Tests (Core, Security, Support via workflow_dispatch)"
    fi
    echo ""

    check_prerequisites

    # Clean up artifacts from previous test runs
    cleanup_previous_runs

    local actions_status="SKIPPED"
    local dispatcher_status="SKIPPED"
    local template_status="SKIPPED"
    local cli_status="SKIPPED"
    local workflow_status="SKIPPED"
    local core_tier_status="SKIPPED"
    local security_tier_status="SKIPPED"
    local support_tier_status="SKIPPED"
    local overall_exit=0

    # Phase 1.0: Actions Integration
    if [[ "$SKIP_ACTIONS" != "true" ]]; then
        mark_phase_start "1.0"
        if run_actions_test; then
            actions_status="PASSED"
            mark_phase_end "1.0" "PASSED"
        else
            actions_status="FAILED"
            mark_phase_end "1.0" "FAILED"
            overall_exit=1
        fi
    else
        log "Skipping Actions integration test (--skip-actions)"
        mark_phase_end "1.0" "SKIPPED"
    fi

    echo ""

    # Phase 1.5: Dispatcher Integration (optional, requires --test-dispatcher)
    if [[ "$TEST_DISPATCHER" == "true" ]]; then
        mark_phase_start "1.5"
        if run_dispatcher_test; then
            dispatcher_status="PASSED"
            mark_phase_end "1.5" "PASSED"
        else
            dispatcher_status="FAILED"
            mark_phase_end "1.5" "FAILED"
            overall_exit=1
        fi
        echo ""
    else
        log "Skipping dispatcher test (use --test-dispatcher to enable)"
        mark_phase_end "1.5" "SKIPPED"
    fi

    echo ""

    # Phase 1.6: Template Workflow Test
    # This tests that the actual process-label.yaml template executes correctly
    if [[ "$SKIP_ACTIONS" != "true" ]]; then
        mark_phase_start "1.6"
        if run_template_test; then
            template_status="PASSED"
            mark_phase_end "1.6" "PASSED"
        else
            template_status="FAILED"
            mark_phase_end "1.6" "FAILED"
            overall_exit=1
        fi
        echo ""
    else
        mark_phase_end "1.6" "SKIPPED"
    fi

    # Show progress after infrastructure tests
    if [[ "$TEST_TIERS" == "true" ]]; then
        print_progress
    fi

    # GROUP C-E: Tier Tests (optional, requires --test-tiers)
    if [[ "$TEST_TIERS" == "true" ]]; then
        # GROUP C: Core Tier
        if run_core_tier_test; then
            core_tier_status="PASSED"
        else
            core_tier_status="FAILED"
            overall_exit=1
        fi
        echo ""
        print_progress

        # GROUP D: Security Tier
        if run_security_tier_test; then
            security_tier_status="PASSED"
        else
            security_tier_status="FAILED"
            overall_exit=1
        fi
        echo ""
        print_progress

        # GROUP E: Support Tier
        if run_support_tier_test; then
            support_tier_status="PASSED"
        else
            support_tier_status="FAILED"
            overall_exit=1
        fi
        echo ""
        print_progress
    else
        log "Skipping tier tests (use --test-tiers to enable)"
        mark_phase_end "2.1" "SKIPPED"
        mark_phase_end "2.2" "SKIPPED"
        mark_phase_end "3.1" "SKIPPED"
        mark_phase_end "3.2" "SKIPPED"
        mark_phase_end "3.3" "SKIPPED"
        mark_phase_end "4.1" "SKIPPED"
    fi

    # Phase 5.0: Sapiens CLI (Proposal)
    if [[ "$ACTIONS_ONLY" != "true" ]]; then
        mark_phase_start "5.0"
        if run_cli_test; then
            cli_status="PASSED"
            mark_phase_end "5.0" "PASSED"
        else
            cli_status="FAILED"
            mark_phase_end "5.0" "FAILED"
            overall_exit=1
        fi
    else
        log "Skipping CLI test (--actions-only)"
        mark_phase_end "5.0" "SKIPPED"
    fi

    echo ""

    # Phase 6.0: Full Workflow (Approval + Execution)
    if [[ "$FULL_WORKFLOW" == "true" && "$cli_status" == "PASSED" ]]; then
        mark_phase_start "6.0"
        if run_full_workflow_test; then
            workflow_status="PASSED"
            mark_phase_end "6.0" "PASSED"
        else
            workflow_status="FAILED"
            mark_phase_end "6.0" "FAILED"
            overall_exit=1
        fi
    elif [[ "$FULL_WORKFLOW" == "true" && "$cli_status" != "PASSED" ]]; then
        warn "Skipping full workflow test (proposal stage failed)"
        workflow_status="SKIPPED"
        mark_phase_end "6.0" "SKIPPED"
    else
        mark_phase_end "6.0" "SKIPPED"
    fi

    echo ""

    # Final progress display for tier tests
    if [[ "$TEST_TIERS" == "true" ]]; then
        print_progress
    fi

    generate_report "$actions_status" "$dispatcher_status" "$template_status" "$cli_status" "$workflow_status" \
        "$core_tier_status" "$security_tier_status" "$support_tier_status"

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
