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
#   - Container runs in privileged mode (required for GitLab's internal services)
#
# RECOMMENDED: Run on a remote server using docker context:
#   DOCKER_CONTEXT=remote-server ./scripts/bootstrap-gitlab.sh
#
# CLEANUP: To start fresh, run:
#   ./scripts/gitlab-cleanup.sh [--context remote-server]
#
# Environment Variables:
#   DOCKER_CONTEXT   Docker context to use (default: "default" for local docker)
#   GITLAB_URL       GitLab URL (default: http://localhost:8080)
#   COMPOSE_FILE     Path to docker-compose file
#
# Usage:
#   ./scripts/bootstrap-gitlab.sh [options]
#   DOCKER_CONTEXT=remote-server ./scripts/bootstrap-gitlab.sh
#
# Options:
#   --context NAME      Docker context to use (overrides DOCKER_CONTEXT env var)
#   --url URL           GitLab URL (default: http://localhost:8080)
#   --docker NAME       Docker container name (default: gitlab-test)
#   --project NAME      Test project name (default: test-repo)
#   --compose FILE      Docker compose file (default: plans/validation/docker/gitlab.yaml)
#   --playground DIR    Playground directory for code changes (default: ~/Workspace/playground)
#   --no-start          Skip starting container (already running)
#   --with-runner       Set up GitLab Runner for CI/CD testing
#   --timeout SECONDS   Max wait time for GitLab to start (default: 600)
#
# Outputs:
#   Exports SAPIENS_GITLAB_TOKEN, GITLAB_URL, GITLAB_PROJECT
#   Also writes to .env.gitlab-test for sourcing

set -euo pipefail

# Script directory (for finding pyproject.toml in dev mode)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitlab-test}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitlab-runner}"
TEST_PROJECT="${TEST_PROJECT:-test-repo}"
COMPOSE_FILE="${COMPOSE_FILE:-plans/validation/docker/gitlab.yaml}"
OUTPUT_FILE="${OUTPUT_FILE:-.env.gitlab-test}"
PLAYGROUND_DIR="${PLAYGROUND_DIR:-$HOME/Workspace/playground}"
SKIP_START=false
WITH_RUNNER=false
TIMEOUT=600

# Source existing env file if it exists (for existing token on re-runs)
if [[ -f ".env.gitlab-test" ]] && [[ -z "${GITLAB_TOKEN:-}" ]]; then
    # shellcheck source=/dev/null
    source ".env.gitlab-test" 2>/dev/null || true
fi

# State - preserve existing token if set
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
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
        --context) DOCKER_CONTEXT="$2"; shift 2 ;;
        --url) GITLAB_URL="$2"; shift 2 ;;
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --project) TEST_PROJECT="$2"; shift 2 ;;
        --compose) COMPOSE_FILE="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        --playground) PLAYGROUND_DIR="$2"; shift 2 ;;
        --no-start) SKIP_START=true; shift ;;
        --with-runner) WITH_RUNNER=true; shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        -h|--help)
            head -35 "$0" | tail -30
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

#############################################
# Step 0a: Switch Docker context
#############################################
switch_docker_context() {
    log "Switching to docker context: $DOCKER_CONTEXT"
    docker context use "$DOCKER_CONTEXT"
    log "Current docker context: $(docker context show)"
}

#############################################
# Step 0: Check prerequisites
#############################################
check_prerequisites() {
    log "Checking prerequisites..."

    # jq is required for JSON parsing
    if ! command -v jq >/dev/null 2>&1; then
        die "jq is required but not installed.
Install with: sudo apt install jq (Ubuntu) or brew install jq (macOS)"
    fi

    # curl is required
    if ! command -v curl >/dev/null 2>&1; then
        die "curl is required but not installed."
    fi

    # docker is required
    if ! command -v docker >/dev/null 2>&1; then
        die "docker is required but not installed."
    fi

    log "Prerequisites OK"
}

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

        # Fallback: Check via container exec (most reliable when external_url != actual URL)
        local internal_check
        internal_check=$(docker exec "$DOCKER_CONTAINER" curl -sf http://localhost/-/health 2>/dev/null || echo "")

        if [[ "$internal_check" == "GitLab OK" ]]; then
            echo ""
            log "GitLab is healthy (internal check)!"
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
# Step 2.5: Configure external_url for runner compatibility
#############################################
configure_external_url() {
    step "Checking GitLab external_url configuration..."

    # Check current external_url via Rails (most reliable)
    local current_url
    current_url=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "puts Gitlab.config.gitlab.url" 2>/dev/null | tail -1 || echo "")

    log "Current external_url: $current_url"

    # If it's localhost, we need to reconfigure for runner compatibility
    if [[ "$current_url" == "http://localhost" ]] || [[ "$current_url" == "http://localhost/"* ]]; then
        log "Reconfiguring external_url for runner compatibility..."

        # Add/update external_url in gitlab.rb
        # First remove any existing external_url line (commented or not)
        docker exec "$DOCKER_CONTAINER" sed -i "/^#*\s*external_url\s/d" /etc/gitlab/gitlab.rb

        # Add the new external_url at the top of the file
        docker exec "$DOCKER_CONTAINER" bash -c "
            echo \"external_url 'http://gitlab'\" > /tmp/gitlab_url.conf
            echo \"nginx['listen_port'] = 80\" >> /tmp/gitlab_url.conf
            echo \"nginx['listen_https'] = false\" >> /tmp/gitlab_url.conf
            cat /etc/gitlab/gitlab.rb >> /tmp/gitlab_url.conf
            mv /tmp/gitlab_url.conf /etc/gitlab/gitlab.rb
        "

        log "Reconfiguring GitLab (this may take a few minutes)..."
        docker exec "$DOCKER_CONTAINER" gitlab-ctl reconfigure > /dev/null 2>&1 || {
            warn "Reconfigure command returned non-zero (may still be successful)"
        }

        # Wait for GitLab to be ready again
        log "Waiting for GitLab to restart..."
        sleep 30

        # Verify the change
        local new_url
        new_url=$(docker exec "$DOCKER_CONTAINER" gitlab-rails runner "puts Gitlab.config.gitlab.url" 2>/dev/null | tail -1 || echo "")
        log "New external_url: $new_url"

        if [[ "$new_url" == "http://gitlab" ]]; then
            log "external_url configured for runner compatibility"
        else
            warn "external_url may not have been updated correctly: $new_url"
        fi
    elif [[ "$current_url" == "http://gitlab" ]]; then
        log "external_url already configured for runner compatibility"
    else
        log "Using existing external_url: $current_url"
    fi
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

    if echo "$response" | jq -e '.username == "root"' > /dev/null 2>&1; then
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

    if echo "$existing" | jq -e ".[] | select(.path == \"$TEST_PROJECT\")" > /dev/null 2>&1; then
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

    if echo "$response" | jq -e ".path == \"$TEST_PROJECT\"" > /dev/null 2>&1; then
        log "Project created successfully"
        return 0
    fi

    # Check for "already exists" error
    if echo "$response" | jq -e '.message | contains("has already been taken")' > /dev/null 2>&1; then
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

        if echo "$response" | jq -e ".name == \"$name\"" > /dev/null 2>&1; then
            log "  Created label: $name"
        elif echo "$response" | jq -e '.message | contains("already exists")' > /dev/null 2>&1; then
            log "  Label exists: $name"
        else
            warn "  Failed to create label $name: $response"
        fi
    done
}

#############################################
# Step 7b: Run sapiens init to configure repository
#############################################
run_sapiens_init() {
    step "Running sapiens init to configure repository..."

    # We need the playground directory to exist first
    # If it doesn't exist, we'll create a temp clone
    local work_dir="$PLAYGROUND_DIR"

    if [[ ! -d "$work_dir/.git" ]]; then
        log "Playground not ready, creating temp clone..."
        work_dir=$(mktemp -d)

        # Clone via HTTP with embedded token
        local gitlab_host
        gitlab_host=$(echo "$GITLAB_URL" | sed 's|https\?://||' | sed 's|/.*||')
        local clone_url="http://oauth2:${GITLAB_TOKEN}@${gitlab_host}/root/${TEST_PROJECT}.git"

        if ! git clone "$clone_url" "$work_dir/repo" > /dev/null 2>&1; then
            warn "Could not clone repository for sapiens init"
            rm -rf "$work_dir"
            return 1
        fi
        work_dir="$work_dir/repo"
    fi

    cd "$work_dir"

    # Configure git for commits
    git config user.name "Sapiens Bot"
    git config user.email "sapiens-bot@gitlab.local"

    # Export token for sapiens init
    export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"
    export SAPIENS_AI_API_KEY="${SAPIENS_AI_API_KEY:-${AI_API_KEY:-test-api-key}}"

    # Run sapiens init non-interactively
    # Uses claude-local by default for local testing
    log "Running: sapiens init --non-interactive --run-mode local --git-token-env SAPIENS_GITLAB_TOKEN --ai-provider claude-local"

    if command -v sapiens > /dev/null 2>&1; then
        sapiens init --non-interactive \
            --run-mode local \
            --git-token-env SAPIENS_GITLAB_TOKEN \
            --ai-provider claude-local \
            --no-setup-secrets || {
            warn "sapiens init failed"
            cd - > /dev/null
            return 1
        }
    elif command -v uv > /dev/null 2>&1 && [[ -f "$SCRIPT_DIR/../pyproject.toml" ]]; then
        # Try running from development checkout
        uv run --project "$SCRIPT_DIR/.." sapiens init --non-interactive \
            --run-mode local \
            --git-token-env SAPIENS_GITLAB_TOKEN \
            --ai-provider claude-local \
            --no-setup-secrets || {
            warn "sapiens init (via uv) failed"
            cd - > /dev/null
            return 1
        }
    else
        warn "sapiens CLI not found, skipping init (install with: pip install repo-sapiens)"
        cd - > /dev/null
        return 1
    fi

    # Push changes if any were made
    if [[ -n "$(git status --porcelain)" ]]; then
        log "Pushing sapiens configuration..."
        git add -A
        git commit -m "chore: Add sapiens configuration via init" > /dev/null 2>&1 || true
        git push origin HEAD > /dev/null 2>&1 || {
            warn "Could not push changes"
        }
    else
        log "No new changes to push (sapiens may have already been configured)"
    fi

    cd - > /dev/null
    log "sapiens init completed"
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
# Step 9: Setup playground repository
#############################################
setup_playground() {
    step "Setting up playground repository at $PLAYGROUND_DIR"

    # Create parent directory if needed
    mkdir -p "$(dirname "$PLAYGROUND_DIR")"

    # If playground exists, update it; otherwise clone fresh
    if [[ -d "$PLAYGROUND_DIR/.git" ]]; then
        log "Playground exists, updating..."
        (
            cd "$PLAYGROUND_DIR"
            git fetch origin 2>/dev/null || true
            git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
            git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
        )
    else
        # Remove if exists but not a git repo
        if [[ -d "$PLAYGROUND_DIR" ]]; then
            log "Removing non-git directory at $PLAYGROUND_DIR"
            rm -rf "$PLAYGROUND_DIR"
        fi

        # Clone via HTTP with embedded token
        log "Cloning test repository..."
        local clone_url
        # Extract host from GITLAB_URL and construct clone URL with token
        local gitlab_host
        gitlab_host=$(echo "$GITLAB_URL" | sed 's|https\?://||' | sed 's|/.*||')
        clone_url="http://oauth2:${GITLAB_TOKEN}@${gitlab_host}/root/${TEST_PROJECT}.git"

        if git clone "$clone_url" "$PLAYGROUND_DIR" 2>/dev/null; then
            log "Repository cloned successfully"
        else
            # Try without token for public repos
            clone_url="${GITLAB_URL}/root/${TEST_PROJECT}.git"
            if git clone "$clone_url" "$PLAYGROUND_DIR" 2>/dev/null; then
                log "Repository cloned (public)"
            else
                warn "Could not clone repository"
                warn "Clone manually: git clone $clone_url $PLAYGROUND_DIR"
                return 1
            fi
        fi
    fi

    # Configure git user for commits
    (
        cd "$PLAYGROUND_DIR"
        git config user.name "Sapiens Bot"
        git config user.email "sapiens-bot@gitlab.local"

        # Set up remote with token for push access
        # Must set both fetch and push URLs in case a separate pushurl was previously configured
        local gitlab_host
        gitlab_host=$(echo "$GITLAB_URL" | sed 's|https\?://||' | sed 's|/.*||')
        local remote_url="http://oauth2:${GITLAB_TOKEN}@${gitlab_host}/root/${TEST_PROJECT}.git"
        git remote set-url origin "$remote_url"
        git remote set-url --push origin "$remote_url"
    )

    log "Playground ready at $PLAYGROUND_DIR"
}

#############################################
# Step 10: Write output file
#############################################
write_output() {
    step "Writing configuration to $OUTPUT_FILE"

    cat > "$OUTPUT_FILE" << ENVFILE
# GitLab test configuration
# Generated by bootstrap-gitlab.sh at $(date -Iseconds)
# Source this file: source $OUTPUT_FILE

export DOCKER_CONTEXT="$DOCKER_CONTEXT"
export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"
export GITLAB_TOKEN="$GITLAB_TOKEN"
export GITLAB_URL="$GITLAB_URL"
export GITLAB_PROJECT="root/$TEST_PROJECT"
export PLAYGROUND_DIR="$PLAYGROUND_DIR"
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

    switch_docker_context
    check_prerequisites
    start_gitlab
    wait_for_gitlab
    configure_external_url

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
    setup_playground
    run_sapiens_init || warn "sapiens init skipped (config may need manual setup)"
    setup_runner
    write_output

    echo ""
    log "=== Bootstrap Complete ==="
    echo ""
    log "Docker ctx:  $DOCKER_CONTEXT"
    log "GitLab URL:  $GITLAB_URL"
    log "Project:     root/$TEST_PROJECT"
    log "Token:       ${GITLAB_TOKEN:0:12}..."
    log "Playground:  $PLAYGROUND_DIR"
    if [[ "$WITH_RUNNER" == "true" ]]; then
        log "Runner:      $RUNNER_CONTAINER"
    fi
    echo ""
    log "To use: source $OUTPUT_FILE"
    log "To run E2E tests: DOCKER_CONTEXT=$DOCKER_CONTEXT ./scripts/run-gitlab-e2e.sh"
    echo ""

    # Export for current shell
    export DOCKER_CONTEXT="$DOCKER_CONTEXT"
    export SAPIENS_GITLAB_TOKEN="$GITLAB_TOKEN"
    export GITLAB_TOKEN="$GITLAB_TOKEN"
    export GITLAB_URL="$GITLAB_URL"
    export GITLAB_PROJECT="root/$TEST_PROJECT"
    export PLAYGROUND_DIR="$PLAYGROUND_DIR"
}

main "$@"
