#!/bin/bash
# scripts/bootstrap-gitlab.sh
#
# Bootstraps a fresh GitLab instance for integration testing.
# Starts container, waits for healthy, creates API token, test project, and optionally a Runner.
#
# WARNING: GitLab is resource-intensive!
#   - Requires 4GB+ RAM (6GB recommended)
#   - Requires 2+ CPU cores
#   - Initial startup takes 5-10 minutes
#
# Usage:
#   ./scripts/bootstrap-gitlab.sh [options]
#
# Options:
#   --url URL           GitLab URL (default: http://localhost:8080)
#   --docker NAME       Docker container name (default: gitlab-test)
#   --project NAME      Test project name (default: test-repo)
#   --compose FILE      Docker compose file (default: plans/validation/docker/gitlab.yaml)
#   --no-start          Skip starting container (already running)
#   --with-runner       Set up GitLab Runner for CI/CD testing
#   --timeout SECONDS   Max wait time for GitLab to start (default: 600)
#
# Outputs:
#   Exports SAPIENS_GITLAB_TOKEN, GITLAB_URL, GITLAB_PROJECT
#   Also writes to .env.gitlab-test for sourcing

set -euo pipefail

# Defaults
GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitlab-test}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitlab-runner}"
TEST_PROJECT="${TEST_PROJECT:-test-repo}"
COMPOSE_FILE="${COMPOSE_FILE:-plans/validation/docker/gitlab.yaml}"
OUTPUT_FILE="${OUTPUT_FILE:-.env.gitlab-test}"
SKIP_START=false
WITH_RUNNER=false
TIMEOUT=600

# State
GITLAB_TOKEN=""
ROOT_PASSWORD=""

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
die() { error "$1"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url) GITLAB_URL="$2"; shift 2 ;;
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --project) TEST_PROJECT="$2"; shift 2 ;;
        --compose) COMPOSE_FILE="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        --no-start) SKIP_START=true; shift ;;
        --with-runner) WITH_RUNNER=true; shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        -h|--help)
            head -30 "$0" | tail -25
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

#############################################
# Step 1: Start GitLab container
#############################################
start_gitlab() {
    if [[ "$SKIP_START" == "true" ]]; then
        log "Skipping container start (--no-start)"
        return 0
    fi

    step "Starting GitLab container..."

    if ! [[ -f "$COMPOSE_FILE" ]]; then
        die "Compose file not found: $COMPOSE_FILE"
    fi

    # Check if already running
    if docker ps --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
        log "Container $DOCKER_CONTAINER already running"
        return 0
    fi

    # Start with docker compose
    log "Starting GitLab via docker compose..."
    docker compose -f "$COMPOSE_FILE" up -d gitlab

    log "Container started. GitLab takes 5-10 minutes to initialize..."
}

#############################################
# Step 2: Wait for GitLab to be healthy
#############################################
wait_for_gitlab() {
    step "Waiting for GitLab to become healthy..."
    log "This typically takes 5-10 minutes on first start."
    log "Timeout set to ${TIMEOUT}s"

    local elapsed=0
    local interval=10

    while true; do
        # Check health endpoint
        local health
        health=$(curl -sf "$GITLAB_URL/-/health" 2>/dev/null || echo "")

        if [[ "$health" == "GitLab OK" ]]; then
            echo ""
            log "GitLab is healthy!"
            return 0
        fi

        # Check readiness (more detailed)
        local ready
        ready=$(curl -sf "$GITLAB_URL/-/readiness" 2>/dev/null || echo "")

        if echo "$ready" | grep -q '"status":"ok"'; then
            echo ""
            log "GitLab is ready!"
            return 0
        fi

        # Progress indicator
        if (( elapsed % 60 == 0 )) && (( elapsed > 0 )); then
            echo ""
            log "Still waiting... (${elapsed}s elapsed)"

            # Show container logs hint
            if (( elapsed == 60 )); then
                log "Monitor progress: docker logs -f $DOCKER_CONTAINER"
            fi
        else
            echo -n "."
        fi

        sleep $interval
        elapsed=$((elapsed + interval))

        if (( elapsed >= TIMEOUT )); then
            echo ""
            die "GitLab not healthy after ${TIMEOUT}s. Check: docker logs $DOCKER_CONTAINER"
        fi
    done
}

#############################################
# Step 3: Get root password
#############################################
get_root_password() {
    step "Getting root password..."

    # GitLab stores initial root password in a file
    ROOT_PASSWORD=$(docker exec "$DOCKER_CONTAINER" \
        cat /etc/gitlab/initial_root_password 2>/dev/null | \
        grep -oP 'Password: \K.*' | tr -d '\n' || echo "")

    if [[ -z "$ROOT_PASSWORD" ]]; then
        # Password file might be deleted after first login
        # Try to check if we already have a token
        warn "Initial password file not found (may have been deleted)"
        warn "If you've already set up GitLab, use --no-start and set GITLAB_TOKEN"
        return 1
    fi

    log "Root password obtained: ${ROOT_PASSWORD:0:4}..."
}

#############################################
# Step 4: Create API token via Rails console
#############################################
create_api_token() {
    step "Creating API token via Rails console..."

    # GitLab requires Rails console to create tokens programmatically
    # (API token creation requires existing authentication)

    local token_name="sapiens-test-$(date +%s)"

    log "Running Rails command to create personal access token..."

    # Create token via gitlab-rails runner
    local result
    result=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "
        user = User.find_by_username('root')
        if user.nil?
          puts 'ERROR: Root user not found'
          exit 1
        end

        # Delete existing sapiens tokens to avoid duplicates
        user.personal_access_tokens.where('name LIKE ?', 'sapiens-test-%').destroy_all

        # Create new token with all necessary scopes
        token = user.personal_access_tokens.create!(
          name: '$token_name',
          scopes: ['api', 'read_api', 'read_repository', 'write_repository', 'read_user'],
          expires_at: 365.days.from_now
        )

        puts token.token
    " 2>&1)

    # Extract token (starts with glpat-)
    GITLAB_TOKEN=$(echo "$result" | grep -oP 'glpat-[A-Za-z0-9_-]+' | head -1 || echo "")

    if [[ -z "$GITLAB_TOKEN" ]]; then
        error "Failed to create token via Rails console."
        error ""
        error "Rails output:"
        echo "$result" | sed 's/^/    /'
        error ""

        # Provide specific troubleshooting hints
        if echo "$result" | grep -qi "root user not found"; then
            error "Hint: GitLab may not have finished initializing. Wait a few minutes and retry."
        elif echo "$result" | grep -qi "validation failed"; then
            error "Hint: Token with same name may already exist. Try again."
        elif echo "$result" | grep -qi "connection refused\|cannot connect"; then
            error "Hint: GitLab services may not be fully started. Check: docker logs $DOCKER_CONTAINER"
        else
            error "Hint: Check GitLab container status: docker logs $DOCKER_CONTAINER | tail -50"
        fi

        die "Token creation failed"
    fi

    log "Token created: ${GITLAB_TOKEN:0:12}..."
}

#############################################
# Step 5: Verify API access
#############################################
verify_api_access() {
    step "Verifying API access..."

    local response
    response=$(curl -sf -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        "$GITLAB_URL/api/v4/user" 2>&1 || echo "")

    if echo "$response" | grep -q '"username":"root"'; then
        log "API access verified (authenticated as root)"
        return 0
    fi

    error "API verification failed: $response"
    die "Cannot access GitLab API with generated token"
}

#############################################
# Step 6: Create test project
#############################################
create_test_project() {
    step "Creating test project: $TEST_PROJECT"

    # Check if project exists
    local existing
    existing=$(curl -sf -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        "$GITLAB_URL/api/v4/projects?search=$TEST_PROJECT" 2>/dev/null || echo "[]")

    if echo "$existing" | grep -q "\"path\":\"$TEST_PROJECT\""; then
        log "Project $TEST_PROJECT already exists"
        return 0
    fi

    # Create project
    local response
    response=$(curl -sf -X POST \
        -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        -H "Content-Type: application/json" \
        "$GITLAB_URL/api/v4/projects" \
        -d "{
            \"name\": \"$TEST_PROJECT\",
            \"path\": \"$TEST_PROJECT\",
            \"initialize_with_readme\": true,
            \"visibility\": \"public\"
        }" 2>&1 || echo "")

    if echo "$response" | grep -q "\"path\":\"$TEST_PROJECT\""; then
        log "Project created successfully"
        return 0
    fi

    # Check for "already exists" error
    if echo "$response" | grep -q "has already been taken"; then
        log "Project already exists"
        return 0
    fi

    error "Failed to create project: $response"
    return 1
}

#############################################
# Step 7: Create automation labels
#############################################
create_automation_labels() {
    step "Creating automation labels..."

    local project_encoded="root%2F$TEST_PROJECT"

    local labels=(
        "needs-planning:#5319e7"
        "awaiting-approval:#fbca04"
        "approved:#0e8a16"
        "in-progress:#1d76db"
        "done:#0e8a16"
    )

    for label_def in "${labels[@]}"; do
        local name="${label_def%%:*}"
        local color="${label_def##*:}"

        local response
        response=$(curl -sf -X POST \
            -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
            -H "Content-Type: application/json" \
            "$GITLAB_URL/api/v4/projects/$project_encoded/labels" \
            -d "{\"name\": \"$name\", \"color\": \"$color\"}" 2>&1 || echo "")

        if echo "$response" | grep -q "\"name\":\"$name\""; then
            log "  Created label: $name"
        elif echo "$response" | grep -q "already exists"; then
            log "  Label exists: $name"
        else
            warn "  Failed to create label $name: $response"
        fi
    done
}

#############################################
# Step 8: Set up GitLab Runner (optional)
#############################################
setup_runner() {
    if [[ "$WITH_RUNNER" != "true" ]]; then
        return 0
    fi

    step "Setting up GitLab Runner..."

    # Start runner container
    log "Starting runner container..."
    docker compose -f "$COMPOSE_FILE" --profile runner up -d gitlab-runner || {
        warn "Failed to start runner container"
        return 1
    }

    # Wait for runner to be ready
    sleep 5

    # Get runner registration token via Rails
    log "Getting runner registration token..."
    local runner_token
    runner_token=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "
        token = Ci::Runner.generate_registration_token
        puts token
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
        warn "Register manually: Admin → CI/CD → Runners → New instance runner"
        return 1
    fi

    log "Registration token: ${runner_token:0:8}..."

    # Register the runner
    log "Registering runner..."
    docker exec "$RUNNER_CONTAINER" gitlab-runner register \
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

#############################################
# Step 9: Write output file
#############################################
write_output() {
    step "Writing configuration to $OUTPUT_FILE"

    cat > "$OUTPUT_FILE" << ENVFILE
# GitLab test configuration
# Generated by bootstrap-gitlab.sh at $(date -Iseconds)
# Source this file: source $OUTPUT_FILE

export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"
export GITLAB_TOKEN="$GITLAB_TOKEN"
export GITLAB_URL="$GITLAB_URL"
export GITLAB_PROJECT="root/$TEST_PROJECT"
ENVFILE

    log "Configuration written to $OUTPUT_FILE"
}

#############################################
# Main
#############################################
main() {
    echo ""
    log "=== GitLab Bootstrap Script ==="
    log "This will set up a GitLab instance for repo-sapiens testing."
    echo ""

    start_gitlab
    wait_for_gitlab

    if ! get_root_password; then
        # If no password, check for existing token
        if [[ -n "${GITLAB_TOKEN:-}" ]]; then
            log "Using existing GITLAB_TOKEN from environment"
        else
            die "Cannot bootstrap: no root password and no existing token"
        fi
    else
        create_api_token
    fi

    verify_api_access
    create_test_project
    create_automation_labels
    setup_runner
    write_output

    echo ""
    log "=== Bootstrap Complete ==="
    echo ""
    log "GitLab URL:  $GITLAB_URL"
    log "Project:     root/$TEST_PROJECT"
    log "Token:       ${GITLAB_TOKEN:0:12}..."
    if [[ "$WITH_RUNNER" == "true" ]]; then
        log "Runner:      $RUNNER_CONTAINER"
    fi
    echo ""
    log "To use: source $OUTPUT_FILE"
    log "To run E2E tests: ./scripts/run-gitlab-e2e.sh"
    echo ""

    # Export for current shell
    export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"
    export GITLAB_TOKEN="$GITLAB_TOKEN"
    export GITLAB_URL="$GITLAB_URL"
    export GITLAB_PROJECT="root/$TEST_PROJECT"
}

main "$@"
