#!/bin/bash
# scripts/bootstrap-gitea.sh
#
# Bootstraps a fresh Gitea instance for integration testing.
# Creates config, admin user, API token, test repository, and optionally an Actions runner.
#
# Usage:
#   ./scripts/bootstrap-gitea.sh [options]
#
# Options:
#   --url URL        Gitea URL (default: http://localhost:3000)
#   --docker NAME    Docker container name (default: gitea-test)
#   --user USER      Admin username (default: testadmin)
#   --pass PASS      Admin password (default: admin123)
#   --repo NAME      Test repository name (default: test-repo)
#   --no-docker      Skip Docker operations (Gitea already configured)
#   --with-runner    Set up Gitea Actions runner for CI/CD testing
#   --runner-name    Runner container name (default: gitea-act-runner)
#
# Outputs:
#   Exports SAPIENS_GITEA_TOKEN, GITEA_URL, GITEA_OWNER, GITEA_REPO
#   Also writes to .env.gitea-test for sourcing

set -euo pipefail

# Defaults
GITEA_URL="${GITEA_URL:-http://localhost:3000}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitea-test}"
ADMIN_USER="${ADMIN_USER:-testadmin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
ADMIN_EMAIL="${ADMIN_EMAIL:-testadmin@localhost}"
TEST_REPO="${TEST_REPO:-test-repo}"
SKIP_DOCKER=false
OUTPUT_FILE="${OUTPUT_FILE:-.env.gitea-test}"
WITH_RUNNER=false
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitea-act-runner}"
RUNNER_TOKEN=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
die() { error "$1"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url) GITEA_URL="$2"; shift 2 ;;
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --user) ADMIN_USER="$2"; shift 2 ;;
        --pass) ADMIN_PASS="$2"; shift 2 ;;
        --repo) TEST_REPO="$2"; shift 2 ;;
        --no-docker) SKIP_DOCKER=true; shift ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        --with-runner) WITH_RUNNER=true; shift ;;
        --runner-name) RUNNER_CONTAINER="$2"; shift 2 ;;
        -h|--help)
            head -28 "$0" | tail -23
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

# Extract host from URL for config
GITEA_HOST=$(echo "$GITEA_URL" | sed -E 's|https?://([^:/]+).*|\1|')
GITEA_PORT=$(echo "$GITEA_URL" | sed -E 's|.*:([0-9]+).*|\1|')
[[ "$GITEA_PORT" == "$GITEA_URL" ]] && GITEA_PORT=3000

#############################################
# Step 1: Wait for Gitea to be accessible
#############################################
wait_for_gitea() {
    log "Waiting for Gitea at $GITEA_URL..."
    local timeout=60
    local elapsed=0

    while ! curl -sf "$GITEA_URL/api/healthz" > /dev/null 2>&1; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [[ $elapsed -ge $timeout ]]; then
            die "Gitea not accessible at $GITEA_URL after ${timeout}s"
        fi
        echo -n "."
    done
    echo ""
    log "Gitea is accessible"
}

#############################################
# Step 2: Check if already installed
#############################################
check_installed() {
    local response
    response=$(curl -sf "$GITEA_URL/api/v1/version" 2>/dev/null || echo "")

    if [[ -n "$response" ]] && echo "$response" | grep -q '"version"'; then
        log "Gitea already installed (version: $(echo "$response" | grep -oP '"version"\s*:\s*"\K[^"]+'))"
        return 0
    fi
    return 1
}

#############################################
# Step 3: Create config via Docker (if needed)
#############################################
create_config_via_docker() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        warn "Skipping Docker config creation (--no-docker)"
        return 1
    fi

    log "Creating Gitea config via Docker..."

    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
        warn "Container $DOCKER_CONTAINER not found"
        return 1
    fi

    # Create app.ini (with Actions enabled)
    docker exec "$DOCKER_CONTAINER" sh -c "mkdir -p /data/gitea/conf && cat > /data/gitea/conf/app.ini << 'APPINI'
APP_NAME = Gitea
RUN_MODE = prod
RUN_USER = git

[database]
DB_TYPE = sqlite3
PATH = /data/gitea/gitea.db

[repository]
ROOT = /data/git/repositories

[server]
DOMAIN = $GITEA_HOST
HTTP_PORT = $GITEA_PORT
ROOT_URL = $GITEA_URL/
SSH_PORT = 22
LFS_START_SERVER = true

[security]
INSTALL_LOCK = true
SECRET_KEY = $(openssl rand -hex 16 2>/dev/null || echo giteatestsecretkey123456)
INTERNAL_TOKEN = $(openssl rand -hex 32 2>/dev/null || echo giteainternaltoken12345678901234567890)

[service]
DISABLE_REGISTRATION = false
REQUIRE_SIGNIN_VIEW = false

[actions]
ENABLED = true
DEFAULT_ACTIONS_URL = github

[log]
MODE = console
LEVEL = info
ROOT_PATH = /data/gitea/log
APPINI
chown -R git:git /data/gitea/conf" || return 1

    log "Config created, restarting Gitea..."
    docker restart "$DOCKER_CONTAINER" > /dev/null
    sleep 5

    return 0
}

#############################################
# Step 4: Register admin user via HTTP API
#############################################
register_admin_user() {
    log "Registering admin user: $ADMIN_USER"

    local cookie_jar="/tmp/gitea_bootstrap_cookies.txt"
    rm -f "$cookie_jar"

    # Get session cookie
    curl -s -c "$cookie_jar" "$GITEA_URL/user/sign_up" > /dev/null

    # Register user (first user becomes admin automatically)
    local response
    response=$(curl -s -b "$cookie_jar" -c "$cookie_jar" \
        -X POST "$GITEA_URL/user/sign_up" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "user_name=$ADMIN_USER" \
        -d "email=$ADMIN_EMAIL" \
        -d "password=$ADMIN_PASS" \
        -d "retype=$ADMIN_PASS" \
        -w "\n%{http_code}" 2>&1)

    local http_code
    http_code=$(echo "$response" | tail -1)

    rm -f "$cookie_jar"

    # Check if user already exists by trying to get token
    if curl -sf -u "$ADMIN_USER:$ADMIN_PASS" "$GITEA_URL/api/v1/user" > /dev/null 2>&1; then
        log "User $ADMIN_USER exists and credentials valid"
        return 0
    fi

    if [[ "$http_code" == "200" ]] || [[ "$http_code" == "303" ]]; then
        log "User registered successfully"
        return 0
    fi

    warn "Registration returned HTTP $http_code (may already exist)"
    return 0
}

#############################################
# Step 5: Generate API token
#############################################
generate_api_token() {
    log "Generating API token..."

    local token_name="sapiens-test-$(date +%s)"
    local response

    response=$(curl -s -u "$ADMIN_USER:$ADMIN_PASS" \
        -X POST "$GITEA_URL/api/v1/users/$ADMIN_USER/tokens" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$token_name\",\"scopes\":[\"all\"]}" 2>&1)

    if echo "$response" | grep -q '"sha1"'; then
        GITEA_TOKEN=$(echo "$response" | grep -oP '"sha1"\s*:\s*"\K[^"]+')
        log "Token generated: ${GITEA_TOKEN:0:8}..."
        return 0
    fi

    # Try to list existing tokens and use one if available
    response=$(curl -s -u "$ADMIN_USER:$ADMIN_PASS" \
        "$GITEA_URL/api/v1/users/$ADMIN_USER/tokens" 2>&1)

    if echo "$response" | grep -q '"sha1"'; then
        warn "Could not create new token, but tokens exist. Re-create manually."
    fi

    die "Failed to generate API token: $response"
}

#############################################
# Step 6: Create test repository
#############################################
create_test_repo() {
    log "Creating test repository: $TEST_REPO"

    # Check if repo exists
    if curl -sf -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO" > /dev/null 2>&1; then
        log "Repository $TEST_REPO already exists"
        return 0
    fi

    local response
    response=$(curl -s -X POST "$GITEA_URL/api/v1/user/repos" \
        -H "Authorization: token $GITEA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$TEST_REPO\",\"auto_init\":true,\"private\":false}" 2>&1)

    if echo "$response" | grep -q "\"name\":\"$TEST_REPO\""; then
        log "Repository created successfully"
        return 0
    fi

    die "Failed to create repository: $response"
}

#############################################
# Step 7: Set up Actions runner (optional)
#############################################
setup_actions_runner() {
    if [[ "$WITH_RUNNER" != "true" ]]; then
        return 0
    fi

    if [[ "$SKIP_DOCKER" == "true" ]]; then
        warn "Cannot set up runner without Docker access (--no-docker)"
        return 1
    fi

    log "Setting up Gitea Actions runner..."

    # Get runner registration token via admin API
    log "Getting runner registration token..."
    local response
    response=$(curl -s -X POST "$GITEA_URL/api/v1/admin/runners/registration-token" \
        -H "Authorization: token $GITEA_TOKEN" \
        -H "Content-Type: application/json" 2>&1)

    if echo "$response" | grep -q '"token"'; then
        RUNNER_TOKEN=$(echo "$response" | grep -oP '"token"\s*:\s*"\K[^"]+')
        log "Registration token obtained: ${RUNNER_TOKEN:0:8}..."
    else
        # Try alternative: generate via CLI
        log "API method failed, trying CLI..."
        RUNNER_TOKEN=$(docker exec -u git "$DOCKER_CONTAINER" \
            gitea actions generate-runner-token 2>/dev/null | tr -d '\n' || echo "")

        if [[ -z "$RUNNER_TOKEN" ]]; then
            warn "Could not get runner registration token: $response"
            warn "Runner setup skipped. You can manually register later."
            return 1
        fi
        log "Registration token generated via CLI: ${RUNNER_TOKEN:0:8}..."
    fi

    # Check if runner container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${RUNNER_CONTAINER}$"; then
        log "Removing existing runner container..."
        docker rm -f "$RUNNER_CONTAINER" > /dev/null 2>&1 || true
    fi

    # Get the Docker network Gitea is on
    local gitea_network
    gitea_network=$(docker inspect "$DOCKER_CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' 2>/dev/null | head -c 12)

    # Determine internal Gitea URL for runner
    # Runner needs to connect to Gitea via Docker network
    local internal_url="http://${DOCKER_CONTAINER}:3000"

    log "Starting Actions runner container..."
    docker run -d \
        --name "$RUNNER_CONTAINER" \
        --restart unless-stopped \
        --network "container:${DOCKER_CONTAINER}" \
        -e GITEA_INSTANCE_URL="http://localhost:3000" \
        -e GITEA_RUNNER_REGISTRATION_TOKEN="$RUNNER_TOKEN" \
        -e GITEA_RUNNER_NAME="test-runner" \
        -e GITEA_RUNNER_LABELS="ubuntu-latest:docker://node:20-bookworm,ubuntu-22.04:docker://ubuntu:22.04,self-hosted:host" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        gitea/act_runner:latest > /dev/null 2>&1 || {
            warn "Failed to start runner with network mode, trying bridge..."

            # Fallback: use bridge network
            docker run -d \
                --name "$RUNNER_CONTAINER" \
                --restart unless-stopped \
                -e GITEA_INSTANCE_URL="$GITEA_URL" \
                -e GITEA_RUNNER_REGISTRATION_TOKEN="$RUNNER_TOKEN" \
                -e GITEA_RUNNER_NAME="test-runner" \
                -e GITEA_RUNNER_LABELS="ubuntu-latest:docker://node:20-bookworm,ubuntu-22.04:docker://ubuntu:22.04,self-hosted:host" \
                -v /var/run/docker.sock:/var/run/docker.sock \
                gitea/act_runner:latest > /dev/null 2>&1 || {
                    warn "Failed to start runner container"
                    return 1
                }
        }

    # Wait for runner to register
    log "Waiting for runner to register..."
    sleep 5

    # Verify runner is registered
    local runners
    runners=$(curl -sf "$GITEA_URL/api/v1/admin/runners" \
        -H "Authorization: token $GITEA_TOKEN" 2>/dev/null || echo "[]")

    if echo "$runners" | grep -q '"name"'; then
        log "Actions runner registered successfully"
        return 0
    else
        warn "Runner may not have registered yet. Check: docker logs $RUNNER_CONTAINER"
        return 0  # Non-fatal, runner might just need more time
    fi
}

#############################################
# Step 8: Write output file
#############################################
write_output() {
    log "Writing configuration to $OUTPUT_FILE"

    cat > "$OUTPUT_FILE" << ENVFILE
# Gitea test configuration
# Generated by bootstrap-gitea.sh at $(date -Iseconds)
# Source this file: source $OUTPUT_FILE

export SAPIENS_GITEA_TOKEN="$GITEA_TOKEN"
export GITEA_URL="$GITEA_URL"
export GITEA_OWNER="$ADMIN_USER"
export GITEA_REPO="$TEST_REPO"
ENVFILE

    # Add runner info if configured
    if [[ "$WITH_RUNNER" == "true" ]] && [[ -n "$RUNNER_TOKEN" ]]; then
        cat >> "$OUTPUT_FILE" << ENVFILE
export GITEA_RUNNER_TOKEN="$RUNNER_TOKEN"
export GITEA_RUNNER_CONTAINER="$RUNNER_CONTAINER"
ENVFILE
    fi

    log "Configuration written to $OUTPUT_FILE"
}

#############################################
# Main
#############################################
main() {
    log "=== Gitea Bootstrap Script ==="
    echo ""

    wait_for_gitea

    if ! check_installed; then
        log "Gitea needs installation..."
        if ! create_config_via_docker; then
            die "Cannot install Gitea. Complete setup at $GITEA_URL or provide Docker access."
        fi
        wait_for_gitea
    fi

    register_admin_user
    generate_api_token
    create_test_repo
    setup_actions_runner
    write_output

    echo ""
    log "=== Bootstrap Complete ==="
    log "Gitea URL:  $GITEA_URL"
    log "Owner:      $ADMIN_USER"
    log "Repository: $TEST_REPO"
    log "Token:      ${GITEA_TOKEN:0:8}..."
    if [[ "$WITH_RUNNER" == "true" ]]; then
        if [[ -n "$RUNNER_TOKEN" ]]; then
            log "Runner:     $RUNNER_CONTAINER (registered)"
        else
            log "Runner:     Not configured (setup failed)"
        fi
    fi
    echo ""
    log "To use: source $OUTPUT_FILE"

    # Export for current shell
    export SAPIENS_GITEA_TOKEN="$GITEA_TOKEN"
    export GITEA_URL="$GITEA_URL"
    export GITEA_OWNER="$ADMIN_USER"
    export GITEA_REPO="$TEST_REPO"
}

main "$@"
