#!/bin/bash
# scripts/bootstrap-gitea.sh
#
# Bootstraps a fresh Gitea instance for integration testing.
# Creates config, admin user, API token, test repository, and an Actions runner.
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
#   --no-runner      Skip Gitea Actions runner setup
#   --runner-name    Runner container name (default: gitea-act-runner)
#   --cleanup        Remove all Gitea containers and reset environment
#   --output FILE    Output file for credentials (default: .env.gitea-test)
#
# Outputs:
#   Exports SAPIENS_GITEA_TOKEN, GITEA_URL, GITEA_OWNER, GITEA_REPO
#   Also writes to output file for sourcing

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
WITH_RUNNER=true
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitea-act-runner}"
RUNNER_TOKEN=""
CLEANUP_ONLY=false

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
        --no-runner) WITH_RUNNER=false; shift ;;
        --runner-name) RUNNER_CONTAINER="$2"; shift 2 ;;
        --cleanup) CLEANUP_ONLY=true; shift ;;
        -h|--help)
            head -28 "$0" | tail -23
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

#############################################
# Docker context detection
#############################################
detect_docker_context() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        return 0
    fi

    local context_name
    context_name=$(docker context show 2>/dev/null || echo "default")
    DOCKER_CONTEXT="$context_name"

    log "Docker context: $context_name"

    # Check if this is a remote context (ssh://)
    local host_url
    host_url=$(docker context inspect "$context_name" 2>/dev/null | jq -r '.[0].Endpoints.docker.Host // ""' 2>/dev/null || echo "")

    if [[ "$host_url" == ssh://* ]]; then
        # Extract the remote host from ssh://user@host
        DOCKER_REMOTE_HOST=$(echo "$host_url" | sed -E 's|ssh://[^@]+@([^:/]+).*|\1|')
        log "Docker running on remote host: $DOCKER_REMOTE_HOST"

        # If GITEA_URL is still localhost, update it to use the remote host
        if [[ "$GITEA_URL" == *"localhost"* ]] || [[ "$GITEA_URL" == *"127.0.0.1"* ]]; then
            local old_url="$GITEA_URL"
            GITEA_URL=$(echo "$GITEA_URL" | sed -E "s/(localhost|127\.0\.0\.1)/$DOCKER_REMOTE_HOST/")
            log "Updated GITEA_URL: $old_url -> $GITEA_URL"
        fi
    else
        DOCKER_REMOTE_HOST=""
        log "Docker running locally"
    fi

    export DOCKER_CONTEXT DOCKER_REMOTE_HOST
}

# Extract host from URL for config (done after context detection)
extract_url_components() {
    GITEA_HOST=$(echo "$GITEA_URL" | sed -E 's|https?://([^:/]+).*|\1|')
    GITEA_PORT=$(echo "$GITEA_URL" | sed -E 's|.*:([0-9]+).*|\1|')
    # If port extraction failed (no port in URL), use default
    if [[ "$GITEA_PORT" == "$GITEA_URL" ]]; then
        GITEA_PORT=3000
    fi
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

    # docker is required unless --no-docker
    if [[ "$SKIP_DOCKER" != "true" ]] && ! command -v docker >/dev/null 2>&1; then
        die "docker is required but not installed (use --no-docker to skip Docker operations)"
    fi

    log "Prerequisites OK"
}

#############################################
# Step 0b: Clean up conflicting containers
#############################################
cleanup_conflicting_containers() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        return 0
    fi

    log "Checking for conflicting containers on port $GITEA_PORT..."

    # Find containers using the target port (even if stopped)
    local conflicting
    conflicting=$(docker ps -a --format '{{.Names}}' --filter "publish=$GITEA_PORT" 2>/dev/null || echo "")

    # Also check for common old container names that might conflict
    local old_containers="gitea-test gitea"
    for old_name in $old_containers; do
        # Skip if it's our target container
        [[ "$old_name" == "$DOCKER_CONTAINER" ]] && continue

        if docker ps -a --format '{{.Names}}' | grep -q "^${old_name}$"; then
            # Check if this container is using our port
            local ports
            ports=$(docker inspect "$old_name" --format '{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} {{end}}' 2>/dev/null || echo "")
            if [[ "$ports" == *"$GITEA_PORT"* ]] || [[ "$ports" == *"3000"* ]]; then
                conflicting="$conflicting $old_name"
            fi
        fi
    done

    # Remove duplicates and trim
    conflicting=$(echo "$conflicting" | tr ' ' '\n' | sort -u | tr '\n' ' ' | xargs)

    if [[ -n "$conflicting" ]]; then
        warn "Found containers that may conflict: $conflicting"
        for container in $conflicting; do
            # Don't remove our target container
            [[ "$container" == "$DOCKER_CONTAINER" ]] && continue

            log "Removing conflicting container: $container"
            docker rm -f "$container" > /dev/null 2>&1 || {
                warn "Could not remove $container (may need manual cleanup)"
            }
        done
    fi
}

#############################################
# Full cleanup (--cleanup flag)
#############################################
do_full_cleanup() {
    log "=== Full Cleanup ==="

    # Remove runner container
    if docker ps -a --format '{{.Names}}' | grep -q "^${RUNNER_CONTAINER}$"; then
        log "Removing runner container: $RUNNER_CONTAINER"
        docker rm -f "$RUNNER_CONTAINER" > /dev/null 2>&1 || true
    fi

    # Remove Gitea container
    if docker ps -a --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
        log "Removing Gitea container: $DOCKER_CONTAINER"
        docker rm -f "$DOCKER_CONTAINER" > /dev/null 2>&1 || true
    fi

    # Remove common old containers
    for old_name in gitea-test gitea sapiens-gitea; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${old_name}$"; then
            log "Removing old container: $old_name"
            docker rm -f "$old_name" > /dev/null 2>&1 || true
        fi
    done

    # Clean up volumes (optional - preserves data by default)
    # Uncomment to also remove volumes:
    # docker volume rm docker_gitea-data gitea-data 2>/dev/null || true

    # Clean up output file
    if [[ -f "$OUTPUT_FILE" ]]; then
        log "Removing output file: $OUTPUT_FILE"
        rm -f "$OUTPUT_FILE"
    fi

    log "Cleanup complete"
}

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

    if [[ -n "$response" ]] && echo "$response" | jq -e '.version' > /dev/null 2>&1; then
        log "Gitea already installed (version: $(echo "$response" | jq -r '.version'))"
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

    if echo "$response" | jq -e '.sha1' > /dev/null 2>&1; then
        GITEA_TOKEN=$(echo "$response" | jq -r '.sha1')
        log "Token generated: ${GITEA_TOKEN:0:8}..."
        return 0
    fi

    # Try to list existing tokens and use one if available
    response=$(curl -s -u "$ADMIN_USER:$ADMIN_PASS" \
        "$GITEA_URL/api/v1/users/$ADMIN_USER/tokens" 2>&1)

    if echo "$response" | jq -e '.[].sha1' > /dev/null 2>&1; then
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

    if echo "$response" | jq -e ".name == \"$TEST_REPO\"" > /dev/null 2>&1; then
        log "Repository created successfully"
        return 0
    fi

    die "Failed to create repository: $response"
}

#############################################
# Step 6b: Deploy sapiens wrapper workflow
#############################################
deploy_sapiens_workflow() {
    log "Deploying sapiens wrapper workflow..."

    # Thin wrapper workflow that calls the reusable sapiens-dispatcher
    # Includes Gitea-specific inputs (git_provider_type, git_provider_url)
    local workflow_content
    workflow_content=$(cat << 'WORKFLOW_EOF'
# Generated by repo-sapiens bootstrap
# Thin wrapper that calls the reusable sapiens-dispatcher workflow
# See: https://github.com/savorywatt/repo-sapiens

name: Sapiens Automation

on:
  issues:
    types: [labeled]
  pull_request:
    types: [labeled]

jobs:
  sapiens:
    uses: https://github.com/savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v2
    with:
      label: ${{ github.event.label.name }}
      issue_number: ${{ github.event.issue.number || github.event.pull_request.number }}
      event_type: ${{ github.event_name == 'pull_request' && 'pull_request.labeled' || 'issues.labeled' }}
      git_provider_type: gitea
      git_provider_url: ${{ github.server_url }}
      # Uncomment and configure AI provider as needed:
      # ai_provider_type: openai-compatible
      # ai_base_url: https://openrouter.ai/api/v1
      # ai_model: anthropic/claude-3.5-sonnet
    secrets:
      GIT_TOKEN: ${{ secrets.SAPIENS_GITEA_TOKEN }}
      AI_API_KEY: ${{ secrets.SAPIENS_AI_API_KEY }}
WORKFLOW_EOF
    )

    local workflow_path=".gitea/workflows/sapiens.yaml"
    local encoded_content
    encoded_content=$(echo -n "$workflow_content" | base64 -w 0)

    # Check if file exists
    local existing
    existing=$(curl -sf -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO/contents/$workflow_path" 2>/dev/null || echo "")

    if echo "$existing" | jq -e '.sha' > /dev/null 2>&1; then
        local sha
        sha=$(echo "$existing" | jq -r '.sha')
        log "Updating existing workflow file..."
        curl -sf -X PUT "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO/contents/$workflow_path" \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"Update sapiens wrapper workflow\",\"content\":\"$encoded_content\",\"sha\":\"$sha\"}" \
            > /dev/null 2>&1 && log "Workflow updated: $workflow_path" || warn "Could not update workflow"
    else
        log "Creating workflow file..."
        curl -sf -X POST "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO/contents/$workflow_path" \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"Add sapiens wrapper workflow\",\"content\":\"$encoded_content\"}" \
            > /dev/null 2>&1 && log "Workflow created: $workflow_path" || warn "Could not create workflow"
    fi
}

#############################################
# Step 6c: Configure repository secrets for Actions
#############################################
configure_repo_secrets() {
    log "Configuring repository secrets for Actions..."

    # Gitea Actions secrets API: PUT /repos/{owner}/{repo}/actions/secrets/{secretname}
    # The secret value needs to be in the request body as {"data": "base64_encoded_value"}

    # Set SAPIENS_GITEA_TOKEN (use the same token we generated)
    local token_b64
    token_b64=$(echo -n "$GITEA_TOKEN" | base64 -w 0)

    local response
    response=$(curl -s -X PUT "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO/actions/secrets/SAPIENS_GITEA_TOKEN" \
        -H "Authorization: token $GITEA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"data\":\"$token_b64\"}" 2>&1)

    if [[ $? -eq 0 ]]; then
        log "Secret SAPIENS_GITEA_TOKEN configured"
    else
        warn "Could not configure SAPIENS_GITEA_TOKEN: $response"
    fi

    # Set SAPIENS_AI_API_KEY (use environment variable if available, otherwise placeholder)
    local ai_key="${SAPIENS_AI_API_KEY:-${AI_API_KEY:-test-api-key-placeholder}}"
    local ai_key_b64
    ai_key_b64=$(echo -n "$ai_key" | base64 -w 0)

    response=$(curl -s -X PUT "$GITEA_URL/api/v1/repos/$ADMIN_USER/$TEST_REPO/actions/secrets/SAPIENS_AI_API_KEY" \
        -H "Authorization: token $GITEA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"data\":\"$ai_key_b64\"}" 2>&1)

    if [[ $? -eq 0 ]]; then
        log "Secret SAPIENS_AI_API_KEY configured"
    else
        warn "Could not configure SAPIENS_AI_API_KEY: $response"
    fi
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

    if echo "$response" | jq -e '.token' > /dev/null 2>&1; then
        RUNNER_TOKEN=$(echo "$response" | jq -r '.token')
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

    # Get the Docker network that Gitea is on so job containers can reach it
    local gitea_network
    gitea_network=$(docker inspect "$DOCKER_CONTAINER" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null | head -1)

    if [[ -z "$gitea_network" ]]; then
        gitea_network="bridge"
        warn "Could not determine Gitea's network, using default bridge"
    else
        log "Gitea is on network: $gitea_network"
    fi

    # Get Gitea's IP on this network for job containers to use
    local gitea_ip
    gitea_ip=$(docker inspect "$DOCKER_CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
    log "Gitea container IP: $gitea_ip"

    log "Starting Actions runner container..."
    # Use the same network as Gitea so job containers can reach it
    # Note: We don't mount a config file as it doesn't work with remote Docker contexts
    # The runner will use environment variables for configuration
    docker run -d \
        --name "$RUNNER_CONTAINER" \
        --restart unless-stopped \
        --network "$gitea_network" \
        -e GITEA_INSTANCE_URL="http://${gitea_ip}:3000" \
        -e GITEA_RUNNER_REGISTRATION_TOKEN="$RUNNER_TOKEN" \
        -e GITEA_RUNNER_NAME="test-runner" \
        -e GITEA_RUNNER_LABELS="ubuntu-latest:docker://catthehacker/ubuntu:act-latest" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        gitea/act_runner:latest > /dev/null 2>&1 || {
            warn "Failed to start runner with same network, trying bridge..."

            # Fallback: use default bridge network
            docker run -d \
                --name "$RUNNER_CONTAINER" \
                --restart unless-stopped \
                -e GITEA_INSTANCE_URL="$GITEA_URL" \
                -e GITEA_RUNNER_REGISTRATION_TOKEN="$RUNNER_TOKEN" \
                -e GITEA_RUNNER_NAME="test-runner" \
                -e GITEA_RUNNER_LABELS="ubuntu-latest:docker://catthehacker/ubuntu:act-latest" \
                -v /var/run/docker.sock:/var/run/docker.sock \
                gitea/act_runner:latest > /dev/null 2>&1 || {
                    warn "Failed to start runner container"
                    return 1
                }
        }

    # Install Docker CLI in the runner (required for Docker-based jobs)
    log "Installing Docker CLI in runner..."
    sleep 2
    docker exec "$RUNNER_CONTAINER" apk add --no-cache docker-cli > /dev/null 2>&1 || {
        warn "Could not install Docker CLI in runner (job execution may fail)"
    }

    # Wait for runner to register
    log "Waiting for runner to register..."
    sleep 5

    # Verify runner is registered
    local runners
    runners=$(curl -sf "$GITEA_URL/api/v1/admin/runners" \
        -H "Authorization: token $GITEA_TOKEN" 2>/dev/null || echo "[]")

    if echo "$runners" | jq -e '.[].name' > /dev/null 2>&1; then
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

    check_prerequisites
    detect_docker_context
    extract_url_components

    # Handle cleanup-only mode
    if [[ "$CLEANUP_ONLY" == "true" ]]; then
        do_full_cleanup
        exit 0
    fi

    cleanup_conflicting_containers
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
    deploy_sapiens_workflow
    configure_repo_secrets
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
