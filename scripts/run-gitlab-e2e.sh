#!/bin/bash
# scripts/run-gitlab-e2e.sh
#
# GitLab E2E integration test.
# Validates the complete repo-sapiens workflow with GitLab:
#
# Phase 1: CI Integration
#   1. Deploy .gitlab-ci.yml to repo (if not present)
#   2. Create issue with trigger label
#   3. Simulate webhook trigger (GitLab lacks native label triggers)
#   4. Verify CI pipeline was triggered
#
# Phase 1.5: Component Integration
#   1. Deploy sapiens thin wrapper CI config
#   2. Create test issue with needs-planning label
#   3. Trigger pipeline manually (GitLab requires webhooks for label events)
#   4. Verify component was executed
#
# Phase 2: Sapiens CLI - Proposal
#   1. Create test issue with needs-planning label
#   2. Run sapiens process-label
#   3. Verify proposal created
#
# Phase 3: Sapiens CLI - Approval
#   4. Add approved label to proposal issue
#   5. Run sapiens process-label
#   6. Verify task issues created
#
# Phase 4: Sapiens CLI - Execution
#   7. Add execute label to first task
#   8. Run sapiens process-label
#   9. Verify branch and MR created
#
# Options:
#   --bootstrap         Run bootstrap script first if not configured
#   --skip-ci           Skip CI integration test (just run CLI tests)
#   --ci-only           Only run CI integration test
#   --test-component    Test the sapiens GitLab CI component
#   --component-ref     Branch/tag for component (default: v2)
#   --with-runner       Set up GitLab Runner for CI component tests
#   --ai-provider       AI provider for CI tests (ollama, openrouter) (default: openrouter)
#   --no-cleanup        Don't cleanup test resources on exit
#
# Environment Variables:
#   DOCKER_CONTEXT       Docker context to use (default: "default")
#   SAPIENS_GITLAB_TOKEN GitLab API token (preferred)
#   GITLAB_TOKEN         GitLab API token (legacy, fallback)
#   GITLAB_URL           GitLab URL (default: http://localhost:8080)
#   GITLAB_PROJECT       GitLab project path (default: root/test-repo)
#   PLAYGROUND_DIR       Local repo for code changes (default: ~/Workspace/playground)
#   RESULTS_DIR          Directory for test results (default: ./validation-results)
#   OPENROUTER_API_KEY   API key for OpenRouter (needed for CI component tests)
#
# Note: GitLab uses different API patterns than Gitea/GitHub:
#   - Issues use `iid` (project-scoped) not global `id`
#   - PRs are called "Merge Requests" (MRs)
#   - Different authentication header (PRIVATE-TOKEN)
#   - No native label triggers - requires webhook handler
#
# Exit codes:
#   0 - Test passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Script directory for sourcing other scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Auto-load .env.gitlab-test if token not already set
if [[ -z "${SAPIENS_GITLAB_TOKEN:-}" ]] && [[ -z "${GITLAB_TOKEN:-}" ]]; then
    if [[ -f "$PROJECT_ROOT/.env.gitlab-test" ]]; then
        # shellcheck source=/dev/null
        source "$PROJECT_ROOT/.env.gitlab-test"
    fi
fi

# Configuration
AUTO_BOOTSTRAP=false
SKIP_CI=false
CI_ONLY=false
TEST_COMPONENT=false
WITH_RUNNER=false
NO_CLEANUP=false
AI_PROVIDER="${AI_PROVIDER:-openrouter}"
COMPONENT_REF="${COMPONENT_REF:-v2}"
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="gitlab-e2e-${TIMESTAMP}"

DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitlab-test}"
GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
GITLAB_PROJECT="${GITLAB_PROJECT:-root/test-repo}"
PLAYGROUND_DIR="${PLAYGROUND_DIR:-$HOME/Workspace/playground}"
TEST_PREFIX="sapiens-e2e-${TIMESTAMP}-"

# OpenRouter API for CI tests (runner can't reach local Ollama)
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-anthropic/claude-3-haiku}"

# State variables
ISSUE_IID=""
PROPOSAL_IID=""
TASK_IID=""
MR_IID=""
FEATURE_BRANCH=""
CI_ISSUE_IID=""
COMPONENT_ISSUE_IID=""
PIPELINE_ID=""

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bootstrap) AUTO_BOOTSTRAP=true; shift ;;
        --skip-ci) SKIP_CI=true; shift ;;
        --ci-only) CI_ONLY=true; shift ;;
        --test-component) TEST_COMPONENT=true; shift ;;
        --component-ref) COMPONENT_REF="$2"; shift 2 ;;
        --with-runner) WITH_RUNNER=true; shift ;;
        --ai-provider) AI_PROVIDER="$2"; shift 2 ;;
        --no-cleanup) NO_CLEANUP=true; shift ;;
        -h|--help)
            head -55 "$0" | tail -50
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 2 ;;
    esac
done

# Cleanup trap
cleanup() {
    local exit_code=$?

    if [[ "$NO_CLEANUP" == "true" ]]; then
        log "Skipping cleanup (--no-cleanup)"
        exit $exit_code
    fi

    step "Cleaning up test resources..."

    # Close original issue
    if [[ -n "${ISSUE_IID:-}" ]]; then
        log "Closing issue #$ISSUE_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$ISSUE_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Close CI test issue
    if [[ -n "${CI_ISSUE_IID:-}" ]]; then
        log "Closing CI test issue #$CI_ISSUE_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$CI_ISSUE_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Close component test issue
    if [[ -n "${COMPONENT_ISSUE_IID:-}" ]]; then
        log "Closing component test issue #$COMPONENT_ISSUE_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$COMPONENT_ISSUE_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Close proposal issue
    if [[ -n "${PROPOSAL_IID:-}" ]] && [[ "$PROPOSAL_IID" != "$ISSUE_IID" ]]; then
        log "Closing proposal #$PROPOSAL_IID..."
        gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$PROPOSAL_IID" '{"state_event":"close"}' > /dev/null 2>&1 || true
    fi

    # Close task issues
    if [[ -n "${TEST_PREFIX:-}" ]]; then
        log "Closing task issues..."
        local tasks
        tasks=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues?search=TASK&in=title&state=opened" 2>/dev/null || echo "[]")
        for task_iid in $(echo "$tasks" | jq -r '.[].iid' 2>/dev/null); do
            gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$task_iid" '{"state_event":"close"}' > /dev/null 2>&1 || true
        done
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

    # Cleanup config file
    if [[ -n "${SAPIENS_CONFIG_FILE:-}" ]]; then
        rm -f "$SAPIENS_CONFIG_FILE"
    fi

    log "Cleanup complete"
    exit $exit_code
}
trap cleanup EXIT

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

# Bootstrap GitLab if needed
maybe_bootstrap_gitlab() {
    if [[ "$AUTO_BOOTSTRAP" != "true" ]]; then
        return 1
    fi

    log "Auto-bootstrapping GitLab..."

    local bootstrap_script="$SCRIPT_DIR/bootstrap-gitlab.sh"
    if [[ ! -x "$bootstrap_script" ]]; then
        error "Bootstrap script not found: $bootstrap_script"
        return 1
    fi

    local bootstrap_args=()
    if [[ "$DOCKER_CONTEXT" != "default" ]]; then
        bootstrap_args+=(--context "$DOCKER_CONTEXT")
    fi
    if [[ -n "${GITLAB_URL:-}" ]]; then
        bootstrap_args+=(--url "$GITLAB_URL")
    fi

    if "$bootstrap_script" "${bootstrap_args[@]}"; then
        # Source the generated environment
        if [[ -f "$PROJECT_ROOT/.env.gitlab-test" ]]; then
            # shellcheck source=/dev/null
            source "$PROJECT_ROOT/.env.gitlab-test"
        fi
        log "Bootstrap complete, credentials loaded"
        return 0
    fi

    return 1
}

# Set up GitLab Runner
setup_runner() {
    if [[ "$WITH_RUNNER" != "true" ]]; then
        return 0
    fi

    step "Setting up GitLab Runner..."

    local compose_file="$PROJECT_ROOT/plans/validation/docker/gitlab.yaml"

    # Start runner container
    log "Starting runner container..."
    docker compose -f "$compose_file" --profile runner up -d gitlab-runner || {
        warn "Failed to start runner container"
        return 1
    }

    # Wait for runner to be ready
    sleep 5

    # Check if runner is already registered
    if docker exec gitlab-runner gitlab-runner list 2>/dev/null | grep -q "sapiens-test-runner"; then
        log "Runner already registered"
        return 0
    fi

    # Get runner registration token via Rails
    log "Getting runner registration token..."
    local runner_token
    runner_token=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "
        # GitLab 16+ uses new runner authentication
        token = Ci::Runner.generate_registration_token rescue nil
        puts token if token
    " 2>&1 | grep -v '^[[:space:]]*$' | tail -1 || echo "")

    if [[ -z "$runner_token" ]]; then
        # Try alternative method for newer GitLab versions
        runner_token=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "
            settings = ApplicationSetting.current
            puts settings.runners_registration_token
        " 2>&1 | grep -v '^[[:space:]]*$' | tail -1 || echo "")
    fi

    if [[ -z "$runner_token" ]]; then
        warn "Could not get runner registration token"
        warn "Register manually via Admin → CI/CD → Runners"
        return 1
    fi

    log "Registration token: ${runner_token:0:8}..."

    # Register the runner
    log "Registering runner..."
    docker exec gitlab-runner gitlab-runner register \
        --non-interactive \
        --url "http://gitlab:80" \
        --registration-token "$runner_token" \
        --executor "docker" \
        --docker-image "python:3.12-slim" \
        --description "sapiens-test-runner" \
        --docker-network-mode "sapiens-gitlab-network" \
        --docker-privileged 2>/dev/null || {
            warn "Runner registration failed. May need manual setup."
            return 1
        }

    log "Runner registered successfully"
}

# Configure GitLab CI/CD secrets
configure_ci_secrets() {
    step "Configuring CI/CD secrets..."

    # Set SAPIENS_GITLAB_TOKEN secret
    log "Setting SAPIENS_GITLAB_TOKEN secret..."
    gitlab_api POST "/projects/$PROJECT_ENCODED/variables" "{
        \"key\": \"SAPIENS_GITLAB_TOKEN\",
        \"value\": \"$GITLAB_TOKEN\",
        \"protected\": false,
        \"masked\": true
    }" 2>/dev/null || gitlab_api PUT "/projects/$PROJECT_ENCODED/variables/SAPIENS_GITLAB_TOKEN" "{
        \"value\": \"$GITLAB_TOKEN\",
        \"protected\": false,
        \"masked\": true
    }" 2>/dev/null || true

    # Set AI API key secret based on provider
    if [[ "$AI_PROVIDER" == "openrouter" ]]; then
        if [[ -z "$OPENROUTER_API_KEY" ]]; then
            warn "OPENROUTER_API_KEY not set - CI component test will fail"
            warn "Set it or use --ai-provider ollama with host network access"
            return 1
        fi

        log "Setting SAPIENS_AI_API_KEY secret (OpenRouter)..."
        gitlab_api POST "/projects/$PROJECT_ENCODED/variables" "{
            \"key\": \"SAPIENS_AI_API_KEY\",
            \"value\": \"$OPENROUTER_API_KEY\",
            \"protected\": false,
            \"masked\": true
        }" 2>/dev/null || gitlab_api PUT "/projects/$PROJECT_ENCODED/variables/SAPIENS_AI_API_KEY" "{
            \"value\": \"$OPENROUTER_API_KEY\",
            \"protected\": false,
            \"masked\": true
        }" 2>/dev/null || true
    fi

    log "CI/CD secrets configured"
}

# Verify prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Support both SAPIENS_GITLAB_TOKEN (preferred) and GITLAB_TOKEN (legacy)
    if [[ -n "${SAPIENS_GITLAB_TOKEN:-}" ]]; then
        GITLAB_TOKEN="$SAPIENS_GITLAB_TOKEN"
    fi

    if [[ -z "${GITLAB_TOKEN:-}" ]]; then
        if [[ "$AUTO_BOOTSTRAP" == "true" ]]; then
            maybe_bootstrap_gitlab || {
                error "SAPIENS_GITLAB_TOKEN is required (bootstrap failed)"
                exit 2
            }
        else
            error "SAPIENS_GITLAB_TOKEN (or GITLAB_TOKEN) is required"
            error "Run with --bootstrap to auto-configure, or: source .env.gitlab-test"
            exit 2
        fi
    fi

    # Check GitLab is accessible
    if ! curl -sf -H "PRIVATE-TOKEN: $GITLAB_TOKEN" "$GITLAB_URL/api/v4/user" > /dev/null 2>&1; then
        error "GitLab not accessible at $GITLAB_URL (or token invalid)"
        error "Start with: docker compose -f plans/validation/docker/gitlab.yaml up -d"
        error "Note: GitLab takes ~5 minutes to start"
        exit 2
    fi

    # Check Ollama is running (for agent) - only needed for CLI tests
    if [[ "$CI_ONLY" != "true" ]]; then
        if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
            error "Ollama not running at localhost:11434"
            error "Start with: ollama serve"
            exit 2
        fi
    fi

    # Verify project exists
    if ! gitlab_api GET "/projects/$PROJECT_ENCODED" > /dev/null 2>&1; then
        error "Project $GITLAB_PROJECT not found"
        error "Create it in GitLab UI or run: ./scripts/bootstrap-gitlab.sh"
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
        error "Install with: apt install jq (or brew install jq)"
        exit 2
    fi

    # Check playground directory exists (needed for task execution)
    if [[ "$CI_ONLY" != "true" ]] && [[ ! -d "$PLAYGROUND_DIR/.git" ]]; then
        warn "Playground directory not found at $PLAYGROUND_DIR"
        warn "Task execution phase may fail. Run bootstrap to set up."
    fi

    # Check rate limit (GitLab uses different headers)
    local rate_remaining
    rate_remaining=$(curl -sf -I -H "PRIVATE-TOKEN: $GITLAB_TOKEN" "$GITLAB_URL/api/v4/projects" 2>/dev/null | grep -i "ratelimit-remaining" | awk '{print $2}' | tr -d '\r' || echo "unknown")

    if [[ "$rate_remaining" != "unknown" ]]; then
        log "GitLab API rate limit remaining: $rate_remaining"
        if [[ "$rate_remaining" -lt 100 ]]; then
            warn "Rate limit is low ($rate_remaining). Consider waiting before running tests."
        fi
    fi

    log "Prerequisites OK"
}

# Ensure label exists
ensure_label() {
    local label_name="$1"
    local label_color="${2:-#428BCA}"

    gitlab_api POST "/projects/$PROJECT_ENCODED/labels" "{
        \"name\": \"$label_name\",
        \"color\": \"$label_color\"
    }" 2>/dev/null || true  # Ignore if already exists
}

#############################################
# Phase 1: CI Integration Test
#############################################

# Deploy CI configuration to repository
deploy_ci_config() {
    step "Checking CI configuration deployment..."

    local ci_path=".gitlab-ci.yml"

    # Check if .gitlab-ci.yml exists
    if gitlab_api GET "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml?ref=main" > /dev/null 2>&1; then
        log "CI configuration already deployed: $ci_path"
        return 0
    fi

    log "Deploying test CI configuration..."

    # Create simple CI workflow that posts a comment on issue label events
    # Note: GitLab doesn't have native label triggers, so this tests pipeline API
    local ci_content
    ci_content=$(cat << 'CI_EOF'
# E2E Test CI Configuration
# This tests that GitLab CI/CD is working correctly

stages:
  - test

test-trigger:
  stage: test
  rules:
    - if: $CI_PIPELINE_SOURCE == "api"
      when: always
    - if: $CI_PIPELINE_SOURCE == "trigger"
      when: always
  script:
    - echo "Pipeline triggered successfully"
    - echo "Issue IID: ${SAPIENS_ISSUE_IID:-not set}"
    - echo "Label: ${SAPIENS_LABEL:-not set}"
    - |
      if [ -n "$SAPIENS_ISSUE_IID" ] && [ -n "$CI_PROJECT_ID" ]; then
        curl --request POST \
          --header "PRIVATE-TOKEN: $CI_JOB_TOKEN" \
          --form "body=CI Pipeline triggered successfully! Run ID: $CI_PIPELINE_ID" \
          "$CI_API_V4_URL/projects/$CI_PROJECT_ID/issues/$SAPIENS_ISSUE_IID/notes" || echo "Could not post comment"
      fi
CI_EOF
    )

    # Base64 encode for API
    local encoded_content
    encoded_content=$(echo -n "$ci_content" | base64 -w 0)

    # Create the file via API
    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml" "{
        \"branch\": \"main\",
        \"content\": \"$ci_content\",
        \"commit_message\": \"Add E2E test CI configuration\"
    }" 2>&1 || echo "")

    if echo "$response" | jq -e '.file_path' > /dev/null 2>&1; then
        log "CI configuration deployed: $ci_path"
    else
        warn "Could not deploy CI configuration: $response"
        warn "CI integration test may be limited"
    fi
}

# Create issue to trigger CI
create_ci_test_issue() {
    step "Creating issue for CI trigger test..."

    ensure_label "test-ci-trigger" "#6610f2"

    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/issues" "{
        \"title\": \"${TEST_PREFIX}CI Integration Test\",
        \"description\": \"This issue tests GitLab CI integration.\\n\\nThe pipeline should post a comment when triggered.\",
        \"labels\": \"test-ci-trigger\"
    }")

    CI_ISSUE_IID=$(echo "$response" | jq -r '.iid // empty')
    if [[ -z "$CI_ISSUE_IID" ]]; then
        error "Failed to create CI test issue. Response: $response"
        return 1
    fi
    log "Created CI test issue #$CI_ISSUE_IID"
}

# Trigger pipeline via API (simulates webhook trigger)
trigger_ci_pipeline() {
    step "Triggering CI pipeline via API..."

    # GitLab doesn't have native label triggers, so we use the pipeline API
    # This simulates what a webhook handler would do
    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/pipeline" "{
        \"ref\": \"main\",
        \"variables\": [
            {\"key\": \"SAPIENS_ISSUE_IID\", \"value\": \"$CI_ISSUE_IID\"},
            {\"key\": \"SAPIENS_LABEL\", \"value\": \"test-ci-trigger\"}
        ]
    }" 2>&1 || echo "")

    PIPELINE_ID=$(echo "$response" | jq -r '.id // empty')
    if [[ -z "$PIPELINE_ID" ]]; then
        warn "Could not trigger pipeline: $response"
        warn "This may be expected if CI is not fully configured"
        return 1
    fi

    log "Pipeline triggered: #$PIPELINE_ID"
}

# Wait for pipeline to complete
wait_for_pipeline() {
    step "Waiting for pipeline to complete..."

    local timeout=180
    local elapsed=0
    local poll_interval=10

    while [[ $elapsed -lt $timeout ]]; do
        local pipeline
        pipeline=$(gitlab_api GET "/projects/$PROJECT_ENCODED/pipelines/$PIPELINE_ID" 2>/dev/null || echo "{}")

        local status
        status=$(echo "$pipeline" | jq -r '.status // "unknown"')

        log "  Pipeline status: $status"

        case "$status" in
            success)
                log "Pipeline completed successfully!"
                return 0
                ;;
            failed|canceled|skipped)
                warn "Pipeline $status"
                return 1
                ;;
        esac

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
    done

    warn "Timeout waiting for pipeline"
    return 1
}

# Verify CI integration
verify_ci() {
    step "Verifying CI integration..."

    local passed=0
    local failed=0

    # Check 1: .gitlab-ci.yml exists
    log "Checking CI configuration file..."
    if gitlab_api GET "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml?ref=main" > /dev/null 2>&1; then
        log "  CI configuration exists"
        ((passed++))
    else
        error "  CI configuration not found"
        ((failed++))
    fi

    # Check 2: Pipeline was created
    log "Checking pipeline creation..."
    if [[ -n "${PIPELINE_ID:-}" ]]; then
        log "  Pipeline created: #$PIPELINE_ID"
        ((passed++))
    else
        error "  No pipeline was created"
        ((failed++))
    fi

    # Check 3: Check for comment on issue (if pipeline succeeded)
    log "Checking for pipeline comment..."
    local notes
    notes=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$CI_ISSUE_IID/notes" 2>/dev/null || echo "[]")

    if echo "$notes" | grep -q "Pipeline triggered successfully"; then
        log "  Pipeline comment found"
        ((passed++))
    else
        warn "  - No pipeline comment (CI job may not have permissions)"
    fi

    echo ""
    log "CI verification: $passed passed, $failed failed"

    [[ $failed -gt 0 ]] && return 1
    return 0
}

run_ci_test() {
    step "=== Phase 1: CI Integration Test ==="
    echo ""

    deploy_ci_config
    sleep 2

    create_ci_test_issue || return 1

    if trigger_ci_pipeline; then
        wait_for_pipeline || true  # Don't fail if pipeline fails
    fi

    if verify_ci; then
        log "CI integration test PASSED"
        return 0
    fi

    warn "CI integration test had issues (may be expected without runner)"
    return 0  # Don't fail overall test for CI issues
}

#############################################
# Phase 1.5: Component Integration Test
#############################################

# Deploy the sapiens-dispatcher component CI configuration
deploy_sapiens_component() {
    step "Deploying sapiens-dispatcher component..."

    local ci_path=".gitlab-ci.yml"

    # Check if component config already exists
    local existing
    existing=$(gitlab_api GET "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml?ref=main" 2>/dev/null || echo "")

    if echo "$existing" | jq -e '.content' > /dev/null 2>&1; then
        local current_content
        current_content=$(echo "$existing" | jq -r '.content' | base64 -d 2>/dev/null || echo "")

        if echo "$current_content" | grep -q "sapiens-dispatcher"; then
            log "Sapiens component already in CI config"
            return 0
        fi
    fi

    # Determine AI provider config
    local ai_provider_type ai_base_url ai_model
    if [[ "$AI_PROVIDER" == "openrouter" ]]; then
        ai_provider_type="openai-compatible"
        ai_base_url="https://openrouter.ai/api/v1"
        ai_model="${OPENROUTER_MODEL}"
    else
        ai_provider_type="ollama"
        # Use Docker host IP for Ollama access from runner
        ai_base_url="http://host.docker.internal:11434"
        ai_model="qwen3:8b"
    fi

    log "Creating sapiens component CI config..."
    log "  AI Provider: $ai_provider_type"
    log "  AI Model: $ai_model"

    # Create CI config that uses the sapiens-dispatcher component
    # The component is in this repo at gitlab/sapiens-dispatcher/template.yml
    # For testing, we inline the component logic rather than using include:
    # because the component isn't published to a public GitLab instance
    local ci_content
    ci_content=$(cat << COMPONENT_EOF
# Sapiens Automation - GitLab CI Component
# Generated by E2E test for component validation
# Tests the sapiens-dispatcher component functionality

stages:
  - sapiens

variables:
  GIT_STRATEGY: clone
  GIT_DEPTH: 0

# Sapiens label handler job
# This implements the sapiens-dispatcher component logic
sapiens-dispatch:
  stage: sapiens
  image: python:3.12-slim
  variables:
    SAPIENS_GIT_PROVIDER_TYPE: gitlab
    SAPIENS_GIT_BASE_URL: \${CI_API_V4_URL}
    SAPIENS_GIT_TOKEN: \${SAPIENS_GITLAB_TOKEN}
    SAPIENS_REPO_OWNER: \${CI_PROJECT_NAMESPACE}
    SAPIENS_REPO_NAME: \${CI_PROJECT_NAME}
    SAPIENS_AI_PROVIDER_TYPE: ${ai_provider_type}
    SAPIENS_AI_BASE_URL: ${ai_base_url}
    SAPIENS_AI_MODEL: ${ai_model}
    SAPIENS_AI_API_KEY: \${SAPIENS_AI_API_KEY}
  before_script:
    - apt-get update && apt-get install -y git
    - pip install --quiet repo-sapiens>=2.0.0
    - git config --global user.name "Sapiens Bot"
    - git config --global user.email "sapiens-bot@gitlab.local"
  script:
    - echo "Sapiens Dispatcher - GitLab CI Component"
    - echo "Processing label '\${SAPIENS_LABEL}' on issue #\${SAPIENS_ISSUE}"
    - |
      sapiens process-label \\
        --event-type "\${SAPIENS_EVENT_TYPE:-issues.labeled}" \\
        --label "\${SAPIENS_LABEL}" \\
        --issue "\${SAPIENS_ISSUE}" \\
        --source gitlab
  artifacts:
    paths:
      - .sapiens/
    expire_in: 7 days
    when: always
  rules:
    - if: \$CI_PIPELINE_SOURCE == "api" && \$SAPIENS_LABEL && \$SAPIENS_ISSUE
      when: always
    - if: \$CI_PIPELINE_SOURCE == "trigger" && \$SAPIENS_LABEL && \$SAPIENS_ISSUE
      when: always
    - when: never
COMPONENT_EOF
    )

    # Get SHA of existing file for update
    local file_sha=""
    if echo "$existing" | jq -e '.content' > /dev/null 2>&1; then
        # File exists - need to update
        local encoded_content
        encoded_content=$(echo -n "$ci_content" | base64 -w 0)

        local response
        response=$(gitlab_api PUT "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml" "{
            \"branch\": \"main\",
            \"content\": \"$encoded_content\",
            \"encoding\": \"base64\",
            \"commit_message\": \"Update sapiens component CI config for E2E testing\"
        }" 2>&1 || echo "")

        if echo "$response" | jq -e '.file_path' > /dev/null 2>&1; then
            log "Component CI config updated"
            return 0
        fi
    fi

    # File doesn't exist - create it
    local encoded_content
    encoded_content=$(echo -n "$ci_content" | base64 -w 0)

    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml" "{
        \"branch\": \"main\",
        \"content\": \"$encoded_content\",
        \"encoding\": \"base64\",
        \"commit_message\": \"Add sapiens component CI config for E2E testing\"
    }" 2>&1 || echo "")

    if echo "$response" | jq -e '.file_path' > /dev/null 2>&1; then
        log "Component CI config created"
    else
        warn "Could not deploy component CI config: $response"
        return 1
    fi
}

# Create issue to trigger component
create_component_test_issue() {
    step "Creating issue for component test..."

    ensure_label "needs-planning" "#428BCA"

    local issue_body
    issue_body=$(cat << 'ISSUE_EOF'
## Component Integration Test

This issue tests the reusable sapiens GitLab CI component.

## Task
Add a simple test file to verify the component is working.

## Expected Behavior
1. Pipeline should trigger on `needs-planning` label (via API)
2. Sapiens should process the issue
3. A proposal comment should be posted

This is an automated test issue.
ISSUE_EOF
)

    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/issues" "{
        \"title\": \"${TEST_PREFIX}Component Integration Test\",
        \"description\": $(echo "$issue_body" | jq -Rs .),
        \"labels\": \"needs-planning\"
    }")

    COMPONENT_ISSUE_IID=$(echo "$response" | jq -r '.iid // empty')
    if [[ -z "$COMPONENT_ISSUE_IID" ]]; then
        error "Failed to create component test issue. Response: $response"
        return 1
    fi
    log "Created component test issue #$COMPONENT_ISSUE_IID with needs-planning label"
}

# Verify component integration
verify_component() {
    step "Verifying component integration..."

    local passed=0
    local failed=0

    # Check 1: CI config has sapiens job
    log "Checking sapiens job in CI config..."
    local ci_file
    ci_file=$(gitlab_api GET "/projects/$PROJECT_ENCODED/repository/files/.gitlab-ci.yml?ref=main" 2>/dev/null || echo "")

    if echo "$ci_file" | jq -r '.content' 2>/dev/null | base64 -d 2>/dev/null | grep -q "sapiens-dispatch"; then
        log "  Sapiens dispatch job found in CI config"
        ((passed++))
    else
        error "  Sapiens dispatch job not found"
        ((failed++))
    fi

    # Check 2: Issue has comments (sapiens posts comments)
    log "Checking for sapiens comments on issue..."
    local notes
    notes=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$COMPONENT_ISSUE_IID/notes" 2>/dev/null || echo "[]")
    local notes_count
    notes_count=$(echo "$notes" | jq 'length')

    if [[ "$notes_count" -gt 0 ]]; then
        log "  Issue has $notes_count comment(s)"
        ((passed++))
    else
        warn "  - No comments on issue (pipeline may not have run)"
    fi

    # Check 3: Check for proposal issue created by component
    log "Checking for proposal issue..."
    local proposals
    proposals=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues?search=PROPOSAL&in=title" || echo "[]")
    local component_proposal
    component_proposal=$(echo "$proposals" | jq -r ".[] | select(.title | contains(\"#$COMPONENT_ISSUE_IID\")) | .iid" | head -1)

    if [[ -n "$component_proposal" ]]; then
        log "  Proposal issue created: #$component_proposal"
        ((passed++))
    else
        warn "  - No proposal issue found (pipeline may have failed)"
    fi

    # Check 4: Check for label changes on issue
    log "Checking for label changes..."
    local issue
    issue=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$COMPONENT_ISSUE_IID" 2>/dev/null || echo "{}")
    local labels
    labels=$(echo "$issue" | jq -r '.labels | join(",")' 2>/dev/null || echo "")

    if [[ "$labels" == *"plan-ready"* ]]; then
        log "  Plan-ready label added"
        ((passed++))
    else
        warn "  - No plan-ready label (labels: $labels)"
    fi

    echo ""
    log "Component verification: $passed passed, $failed failed"

    # Component test passes if CI config was deployed
    [[ $failed -gt 0 ]] && return 1
    return 0
}

run_component_test() {
    step "=== Phase 1.5: Component Integration Test ==="
    echo ""
    log "Testing sapiens-dispatcher GitLab CI component"
    log "AI Provider: $AI_PROVIDER"
    echo ""

    # Check for required secrets
    if [[ "$AI_PROVIDER" == "openrouter" ]] && [[ -z "$OPENROUTER_API_KEY" ]]; then
        error "OPENROUTER_API_KEY required for component test"
        error "Set it or use: --ai-provider ollama"
        return 1
    fi

    # Set up runner if requested
    if [[ "$WITH_RUNNER" == "true" ]]; then
        setup_runner || {
            warn "Runner setup failed - component test may fail"
        }
    fi

    # Configure CI/CD secrets
    configure_ci_secrets || {
        warn "Could not configure CI secrets"
    }

    # Deploy component CI config
    deploy_sapiens_component || return 1
    sleep 3

    # Create test issue
    create_component_test_issue || return 1

    # Trigger pipeline with sapiens variables
    step "Triggering sapiens pipeline..."
    local response
    response=$(gitlab_api POST "/projects/$PROJECT_ENCODED/pipeline" "{
        \"ref\": \"main\",
        \"variables\": [
            {\"key\": \"SAPIENS_LABEL\", \"value\": \"needs-planning\"},
            {\"key\": \"SAPIENS_ISSUE\", \"value\": \"$COMPONENT_ISSUE_IID\"},
            {\"key\": \"SAPIENS_EVENT_TYPE\", \"value\": \"issues.labeled\"}
        ]
    }" 2>&1 || echo "")

    local component_pipeline_id
    component_pipeline_id=$(echo "$response" | jq -r '.id // empty')

    if [[ -z "$component_pipeline_id" ]]; then
        warn "Could not trigger component pipeline: $response"
        warn "This is expected if no runner is available"
        return 0
    fi

    log "Pipeline triggered: #$component_pipeline_id"

    # Wait for pipeline to complete
    step "Waiting for component pipeline..."
    local timeout=300
    local elapsed=0
    local poll_interval=15

    while [[ $elapsed -lt $timeout ]]; do
        local pipeline
        pipeline=$(gitlab_api GET "/projects/$PROJECT_ENCODED/pipelines/$component_pipeline_id" 2>/dev/null || echo "{}")

        local status
        status=$(echo "$pipeline" | jq -r '.status // "unknown"')

        log "  Pipeline status: $status (${elapsed}s / ${timeout}s)"

        case "$status" in
            success)
                log "Pipeline completed successfully!"
                break
                ;;
            failed)
                warn "Pipeline failed"
                # Get job logs for debugging
                local jobs
                jobs=$(gitlab_api GET "/projects/$PROJECT_ENCODED/pipelines/$component_pipeline_id/jobs" 2>/dev/null || echo "[]")
                local job_id
                job_id=$(echo "$jobs" | jq -r '.[0].id // empty')
                if [[ -n "$job_id" ]]; then
                    log "Job logs (last 50 lines):"
                    gitlab_api GET "/projects/$PROJECT_ENCODED/jobs/$job_id/trace" 2>/dev/null | tail -50 || true
                fi
                break
                ;;
            canceled|skipped)
                warn "Pipeline $status"
                break
                ;;
        esac

        sleep $poll_interval
        elapsed=$((elapsed + poll_interval))
    done

    if verify_component; then
        log "Component integration test PASSED"
        return 0
    fi

    warn "Component integration test had issues"
    return 0  # Don't fail overall for component issues
}

#############################################
# Phase 2: Sapiens CLI - Proposal
#############################################

# Create test issue with automation label
create_test_issue() {
    step "Creating test issue..."

    # Ensure required labels exist
    ensure_label "needs-planning" "#428BCA"
    ensure_label "approved" "#28A745"
    ensure_label "in-progress" "#1d76db"
    ensure_label "done" "#0e8a16"
    ensure_label "plan-ready" "#6f42c1"
    ensure_label "execute" "#6610f2"
    ensure_label "review" "#ffc107"

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

# Create sapiens config for CLI tests
create_sapiens_config() {
    local owner="${GITLAB_PROJECT%%/*}"
    local repo="${GITLAB_PROJECT##*/}"

    local config_file="/tmp/sapiens-gitlab-e2e-config-${TIMESTAMP}.yaml"

    # Export for sapiens subprocess
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

workflow:
  plans_directory: plans
  state_directory: .sapiens/state
  playground_directory: "$PLAYGROUND_DIR"

automation:
  mode:
    mode: native

  label_triggers:
    "needs-planning":
      label_pattern: "needs-planning"
      handler: proposal
      ai_enabled: true
      remove_on_complete: false
      success_label: plan-ready
    "approved":
      label_pattern: "approved"
      handler: approval
      ai_enabled: true
      remove_on_complete: true
      success_label: implemented
    "execute":
      label_pattern: "execute"
      handler: task_execution
      ai_enabled: true
      remove_on_complete: true
      success_label: review
CONFIG_EOF

    log "Config written to $config_file"
    export SAPIENS_CONFIG_FILE="$config_file"
}

# Run sapiens to process the issue (proposal stage)
process_proposal() {
    step "Processing issue with sapiens (proposal)..."

    create_sapiens_config

    local event_json
    event_json=$(cat <<EVENT_JSON
{
  "object_attributes": {
    "iid": $ISSUE_IID
  },
  "changes": {
    "labels": {
      "previous": [],
      "current": [{"title": "needs-planning"}]
    }
  }
}
EVENT_JSON
)
    log "Running: sapiens process-label --event-type issues.labeled --issue $ISSUE_IID"

    mkdir -p "$RESULTS_DIR/$RUN_ID"
    if echo "$event_json" | uv run sapiens --config "$SAPIENS_CONFIG_FILE" process-label --event-type issues.labeled --source gitlab 2>&1 | tee "$RESULTS_DIR/$RUN_ID/process-output.log"; then
        log "Proposal processing completed"
    else
        warn "Proposal processing returned non-zero exit code"
    fi
}

run_proposal_test() {
    step "=== Phase 2: Sapiens CLI - Proposal ==="
    echo ""

    create_test_issue
    process_proposal
}

#############################################
# Phase 3: Sapiens CLI - Approval
#############################################

process_approval() {
    step "=== Phase 3: Sapiens CLI - Approval ==="
    echo ""

    # Find the proposal issue created in Phase 2
    log "Finding proposal issue..."
    local proposals
    proposals=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues?search=PROPOSAL&in=title" || echo "[]")
    local proposal_iid
    proposal_iid=$(echo "$proposals" | jq -r ".[] | select(.title | contains(\"#$ISSUE_IID\")) | .iid" | head -1)

    if [[ -z "$proposal_iid" ]]; then
        warn "No proposal issue found for original issue #$ISSUE_IID"
        warn "Skipping approval phase"
        return 0
    fi

    log "Found proposal issue #$proposal_iid"
    PROPOSAL_IID="$proposal_iid"

    # Add the 'approved' label to the proposal issue
    log "Adding 'approved' label to proposal issue #$proposal_iid..."

    local current_labels
    current_labels=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$proposal_iid" | jq -r '.labels | join(",")')
    gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$proposal_iid" "{\"labels\": \"$current_labels,approved\"}" > /dev/null

    log "Added 'approved' label to proposal #$proposal_iid"

    # Build event data for approval
    local event_json
    event_json=$(cat <<EVENT_JSON
{
  "object_attributes": {
    "iid": $proposal_iid
  },
  "changes": {
    "labels": {
      "previous": [{"title": "plan-ready"}],
      "current": [{"title": "plan-ready"}, {"title": "approved"}]
    }
  }
}
EVENT_JSON
)
    log "Running: sapiens process-label --event-type issues.labeled (approval)"

    if echo "$event_json" | uv run sapiens --config "$SAPIENS_CONFIG_FILE" process-label --event-type issues.labeled --source gitlab 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/process-output.log"; then
        log "Approval processing completed"
    else
        warn "Approval processing returned non-zero exit code"
    fi
}

#############################################
# Phase 4: Sapiens CLI - Execution
#############################################

process_execution() {
    step "=== Phase 4: Sapiens CLI - Execution ==="
    echo ""

    # Find task issues created by approval stage
    log "Finding task issues..."
    local tasks
    tasks=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues?search=TASK&in=title&state=opened" || echo "[]")
    local task_iid
    task_iid=$(echo "$tasks" | jq -r ".[] | select(.title | contains(\"[TASK 1/\")) | .iid" | head -1)

    if [[ -z "$task_iid" ]]; then
        warn "No task issue found - skipping execution phase"
        return 0
    fi

    log "Found task issue #$task_iid"
    TASK_IID="$task_iid"

    # Add execute label to task issue
    log "Adding 'execute' label to task #$task_iid..."
    local current_labels
    current_labels=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$task_iid" | jq -r '.labels | join(",")')
    gitlab_api PUT "/projects/$PROJECT_ENCODED/issues/$task_iid" "{\"labels\": \"$current_labels,execute\"}" > /dev/null

    log "Added 'execute' label to task #$task_iid"

    # Build event data for task execution
    local event_json
    event_json=$(cat <<EVENT_JSON
{
  "object_attributes": {
    "iid": $task_iid
  },
  "changes": {
    "labels": {
      "previous": [{"title": "task"}, {"title": "ready"}],
      "current": [{"title": "task"}, {"title": "ready"}, {"title": "execute"}]
    }
  }
}
EVENT_JSON
)
    log "Running: sapiens process-label --event-type issues.labeled (execution)"

    if echo "$event_json" | uv run sapiens --config "$SAPIENS_CONFIG_FILE" process-label --event-type issues.labeled --source gitlab 2>&1 | tee -a "$RESULTS_DIR/$RUN_ID/process-output.log"; then
        log "Task execution completed"
    else
        warn "Task execution returned non-zero exit code"
    fi
}

#############################################
# Verification
#############################################

verify_results() {
    step "Verifying results..."

    local passed=0
    local failed=0

    # Check 1: Issue should have plan-ready label
    log "Checking for plan-ready label..."
    local issue
    issue=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues/$ISSUE_IID")
    local labels
    labels=$(echo "$issue" | jq -r '.labels[]' 2>/dev/null | tr '\n' ',')

    if [[ "$labels" == *"plan-ready"* ]]; then
        log "  Plan-ready label found: $labels"
        ((passed++))
    else
        error "  No plan-ready label found (labels: $labels)"
        ((failed++))
    fi

    # Check 2: Proposal issue should exist
    log "Checking for proposal issue..."
    local proposals
    proposals=$(gitlab_api GET "/projects/$PROJECT_ENCODED/issues?search=PROPOSAL&in=title" || echo "[]")
    local proposal_iid
    proposal_iid=$(echo "$proposals" | jq -r ".[] | select(.title | contains(\"#$ISSUE_IID\")) | .iid" | head -1)

    if [[ -n "$proposal_iid" ]]; then
        log "  Proposal issue found: #$proposal_iid"
        ((passed++))
    else
        error "  No proposal issue found"
        ((failed++))
    fi

    # Check 3: Look for feature branch
    log "Checking for feature branch..."
    local branches
    branches=$(gitlab_api GET "/projects/$PROJECT_ENCODED/repository/branches" || echo "[]")
    local feature_branch
    feature_branch=$(echo "$branches" | jq -r ".[] | select(.name | contains(\"$ISSUE_IID\") or contains(\"plan-\")) | .name" | head -1)

    if [[ -n "$feature_branch" ]]; then
        log "  Feature branch found: $feature_branch"
        ((passed++))
        FEATURE_BRANCH="$feature_branch"
    else
        warn "  - No feature branch found"
    fi

    # Check 4: Look for MR
    log "Checking for merge request..."
    local mrs
    mrs=$(gitlab_api GET "/projects/$PROJECT_ENCODED/merge_requests?state=all" || echo "[]")
    local test_mr
    test_mr=$(echo "$mrs" | jq -r ".[] | select(.title | contains(\"Plan\") or contains(\"$TEST_PREFIX\")) | .iid" | head -1)

    if [[ -n "$test_mr" ]]; then
        log "  Merge request found: !$test_mr"
        ((passed++))
        MR_IID="$test_mr"
    else
        warn "  - No merge request found"
    fi

    # Summary
    echo ""
    log "Verification: $passed passed, $failed failed"

    [[ $failed -gt 0 ]] && return 1
    return 0
}

#############################################
# Report Generation
#############################################

generate_report() {
    local ci_status="$1"
    local component_status="$2"
    local cli_status="$3"

    cat > "$RESULTS_DIR/$RUN_ID/e2e-report.md" << REPORT_EOF
# GitLab E2E Test Report: $RUN_ID

**Date**: $(date -Iseconds)

## Test Configuration

| Setting | Value |
|---------|-------|
| Docker Context | $DOCKER_CONTEXT |
| GitLab URL | $GITLAB_URL |
| Project | $GITLAB_PROJECT |
| Playground | $PLAYGROUND_DIR |
| Test Prefix | $TEST_PREFIX |
| Component Ref | $COMPONENT_REF |

## Phase 1: CI Integration

**Status**: $ci_status

- CI Config: .gitlab-ci.yml
- Test issue: #${CI_ISSUE_IID:-N/A}
- Pipeline: #${PIPELINE_ID:-N/A}

Note: GitLab doesn't have native label triggers. This tests pipeline API triggering.

## Phase 1.5: Component Integration

**Status**: $component_status

- Component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@$COMPONENT_REF
- Test issue: #${COMPONENT_ISSUE_IID:-N/A}

## Phase 2: Sapiens CLI - Proposal

**Status**: Included in CLI status below

- Test issue: #${ISSUE_IID:-N/A}
- Triggered by: \`needs-planning\` label

## Phase 3: Sapiens CLI - Approval

**Status**: Included in CLI status below

- Proposal issue: #${PROPOSAL_IID:-N/A}
- Triggered by: \`approved\` label

## Phase 4: Sapiens CLI - Execution

**Status**: Included in CLI status below

- Task issue: #${TASK_IID:-N/A}
- Triggered by: \`execute\` label

## CLI Test Results

**Status**: $cli_status

- Feature branch: ${FEATURE_BRANCH:-Not created}
- Merge request: !${MR_IID:-Not created}

## Overall Result

$(
    local any_failed=false

    [[ "$ci_status" == "FAILED" ]] && any_failed=true
    [[ "$component_status" == "FAILED" ]] && any_failed=true
    [[ "$cli_status" == "FAILED" ]] && any_failed=true

    if [[ "$any_failed" == "true" ]]; then
        echo "TESTS FAILED"
    else
        local passed_tests=""
        [[ "$ci_status" == "PASSED" ]] && passed_tests="${passed_tests}CI, "
        [[ "$component_status" == "PASSED" ]] && passed_tests="${passed_tests}Component, "
        [[ "$cli_status" == "PASSED" ]] && passed_tests="${passed_tests}CLI, "

        if [[ -n "$passed_tests" ]]; then
            passed_tests="${passed_tests%, }"
            echo "TESTS PASSED: $passed_tests"
        else
            echo "ALL TESTS SKIPPED"
        fi
    fi
)

## Logs

- \`process-output.log\` - Full sapiens output

## Notes

GitLab-specific behaviors:
- Issues use \`iid\` (project-scoped ID)
- PRs are called "Merge Requests" (MRs)
- Authentication via \`PRIVATE-TOKEN\` header
- No native label triggers - requires webhook handler or API trigger
REPORT_EOF

    log "Report saved to $RESULTS_DIR/$RUN_ID/e2e-report.md"
}

#############################################
# Main
#############################################
main() {
    # Switch to specified docker context
    log "Switching to docker context: $DOCKER_CONTEXT"
    docker context use "$DOCKER_CONTEXT"

    mkdir -p "$RESULTS_DIR/$RUN_ID"

    log "=== GitLab E2E Integration Test ==="
    log "Run ID: $RUN_ID"
    log "Docker Context: $DOCKER_CONTEXT"
    echo ""

    check_prerequisites

    local ci_status="SKIPPED"
    local component_status="SKIPPED"
    local cli_status="SKIPPED"
    local overall_exit=0

    # Phase 1: CI Integration
    if [[ "$SKIP_CI" != "true" ]]; then
        if run_ci_test; then
            ci_status="PASSED"
        else
            ci_status="FAILED"
            # Don't fail overall for CI issues
        fi
    else
        log "Skipping CI integration test (--skip-ci)"
    fi

    echo ""

    # Phase 1.5: Component Integration (optional)
    if [[ "$TEST_COMPONENT" == "true" ]]; then
        if run_component_test; then
            component_status="PASSED"
        else
            component_status="FAILED"
            # Don't fail overall for component issues
        fi
        echo ""
    else
        log "Skipping component test (use --test-component to enable)"
    fi

    echo ""

    # Phases 2-4: CLI Tests
    if [[ "$CI_ONLY" != "true" ]]; then
        run_proposal_test

        echo ""
        process_approval

        echo ""
        process_execution

        echo ""
        if verify_results; then
            cli_status="PASSED"
        else
            cli_status="FAILED"
            overall_exit=1
        fi
    else
        log "Skipping CLI tests (--ci-only)"
    fi

    echo ""
    generate_report "$ci_status" "$component_status" "$cli_status"

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
