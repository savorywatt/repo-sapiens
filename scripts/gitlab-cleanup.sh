#!/bin/bash
# scripts/gitlab-cleanup.sh
#
# Cleans up GitLab containers, volumes, and networks for a fresh start.
#
# Environment Variables:
#   DOCKER_CONTEXT   Docker context to use (default: "default" for local docker)
#   COMPOSE_FILE     Path to docker-compose file
#
# Usage:
#   ./scripts/gitlab-cleanup.sh [--context NAME]
#   DOCKER_CONTEXT=remote-server ./scripts/gitlab-cleanup.sh
#
# Options:
#   --context NAME   Docker context to use (overrides DOCKER_CONTEXT env var)
#
# Examples:
#   # Cleanup local docker (default)
#   ./scripts/gitlab-cleanup.sh
#
#   # Cleanup remote docker context
#   DOCKER_CONTEXT=remote-server ./scripts/gitlab-cleanup.sh
#   ./scripts/gitlab-cleanup.sh --context remote-server

set -euo pipefail

# Default to local docker context
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
COMPOSE_FILE="${COMPOSE_FILE:-plans/validation/docker/gitlab.yaml}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --context) DOCKER_CONTEXT="$2"; shift 2 ;;
        -h|--help) head -12 "$0" | tail -10; exit 0 ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Switch to specified docker context
log "Switching to docker context: $DOCKER_CONTEXT"
docker context use "$DOCKER_CONTEXT"
log "Current docker context: $(docker context show)"
log "Cleaning up GitLab resources..."

# Stop and remove containers, volumes, networks
if [[ -f "$COMPOSE_FILE" ]]; then
    log "Using compose file: $COMPOSE_FILE"
    docker compose -f "$COMPOSE_FILE" --profile runner down -v --remove-orphans 2>&1 || true
else
    warn "Compose file not found: $COMPOSE_FILE"
    warn "Attempting manual cleanup..."

    # Manual cleanup
    docker stop gitlab-test gitlab-runner 2>/dev/null || true
    docker rm gitlab-test gitlab-runner 2>/dev/null || true
    docker volume rm sapiens-gitlab-config sapiens-gitlab-logs sapiens-gitlab-data sapiens-gitlab-runner-config 2>/dev/null || true
    docker network rm sapiens-gitlab-network 2>/dev/null || true
fi

# Remove env file if exists
if [[ -f ".env.gitlab-test" ]]; then
    log "Removing .env.gitlab-test"
    rm -f .env.gitlab-test
fi

log "Cleanup complete!"
log ""
log "To start fresh: ./scripts/bootstrap-gitlab.sh"
