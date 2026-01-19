#!/bin/bash
# scripts/gitea-cleanup.sh
#
# Tears down Gitea test environment completely.
# Removes containers, volumes, networks, and temporary files.
#
# Usage:
#   ./scripts/gitea-cleanup.sh [options]
#
# Options:
#   --docker NAME    Docker container name (default: sapiens-gitea)
#   --runner NAME    Runner container name (default: gitea-act-runner)
#   --keep-volumes   Don't remove Docker volumes (preserve data)
#   --all-contexts   Clean up on all Docker contexts
#   -h, --help       Show this help message
#
# Examples:
#   ./scripts/gitea-cleanup.sh                    # Clean local context
#   ./scripts/gitea-cleanup.sh --all-contexts     # Clean all contexts
#   ./scripts/gitea-cleanup.sh --keep-volumes     # Keep data volumes

set -euo pipefail

# Defaults
DOCKER_CONTAINER="${DOCKER_CONTAINER:-sapiens-gitea}"
RUNNER_CONTAINER="${RUNNER_CONTAINER:-gitea-act-runner}"
KEEP_VOLUMES=false
ALL_CONTEXTS=false

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
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --runner) RUNNER_CONTAINER="$2"; shift 2 ;;
        --keep-volumes) KEEP_VOLUMES=true; shift ;;
        --all-contexts) ALL_CONTEXTS=true; shift ;;
        -h|--help)
            head -22 "$0" | tail -18
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Remove containers for a specific context
cleanup_containers() {
    local context_name="${1:-current}"

    log "Cleaning up containers ($context_name context)..."

    # Stop and remove runner container
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${RUNNER_CONTAINER}$"; then
        log "  Removing runner: $RUNNER_CONTAINER"
        docker rm -f "$RUNNER_CONTAINER" > /dev/null 2>&1 || true
    fi

    # Stop and remove Gitea container
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${DOCKER_CONTAINER}$"; then
        log "  Removing Gitea: $DOCKER_CONTAINER"
        docker rm -f "$DOCKER_CONTAINER" > /dev/null 2>&1 || true
    fi

    # Also remove common old container names
    for old_name in gitea-test gitea; do
        if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${old_name}$"; then
            log "  Removing old container: $old_name"
            docker rm -f "$old_name" > /dev/null 2>&1 || true
        fi
    done
}

# Remove volumes
cleanup_volumes() {
    local context_name="${1:-current}"

    if [[ "$KEEP_VOLUMES" == "true" ]]; then
        log "Keeping volumes ($context_name context)"
        return 0
    fi

    log "Cleaning up volumes ($context_name context)..."

    # Remove Gitea data volumes
    for vol in docker_gitea-data gitea-data gitea_data; do
        if docker volume ls -q 2>/dev/null | grep -q "^${vol}$"; then
            log "  Removing volume: $vol"
            docker volume rm "$vol" > /dev/null 2>&1 || true
        fi
    done
}

# Remove networks (only if empty)
cleanup_networks() {
    local context_name="${1:-current}"

    log "Cleaning up networks ($context_name context)..."

    # Only remove docker_default if it has no containers
    if docker network ls --format '{{.Name}}' 2>/dev/null | grep -q "^docker_default$"; then
        local containers
        containers=$(docker network inspect docker_default --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "")
        if [[ -z "$containers" ]]; then
            log "  Removing network: docker_default"
            docker network rm docker_default > /dev/null 2>&1 || true
        else
            log "  Keeping network docker_default (has containers: $containers)"
        fi
    fi
}

# Clean up temporary files
cleanup_temp_files() {
    log "Cleaning up temporary files..."

    # Remove env files
    rm -f /tmp/.env.gitea* 2>/dev/null || true
    rm -f .env.gitea-test 2>/dev/null || true

    # Remove runner config directories
    rm -rf /tmp/gitea-runner-config-* 2>/dev/null || true

    # Remove sapiens e2e config files
    rm -f /tmp/sapiens-e2e-config-*.yaml 2>/dev/null || true
}

# Cleanup for current context
cleanup_current_context() {
    cleanup_containers "local"
    cleanup_volumes "local"
    cleanup_networks "local"
}

# Cleanup all Docker contexts
cleanup_all_contexts() {
    local original_context
    original_context=$(docker context show 2>/dev/null || echo "default")

    # Get list of contexts
    local contexts
    contexts=$(docker context ls --format '{{.Name}}' 2>/dev/null || echo "default")

    for ctx in $contexts; do
        log "Switching to context: $ctx"
        if docker context use "$ctx" > /dev/null 2>&1; then
            cleanup_containers "$ctx"
            cleanup_volumes "$ctx"
            cleanup_networks "$ctx"
        else
            warn "Could not switch to context: $ctx"
        fi
    done

    # Restore original context
    log "Restoring context: $original_context"
    docker context use "$original_context" > /dev/null 2>&1 || true
}

# Main
main() {
    log "=== Gitea Cleanup ==="
    echo ""

    if [[ "$ALL_CONTEXTS" == "true" ]]; then
        cleanup_all_contexts
    else
        cleanup_current_context
    fi

    cleanup_temp_files

    echo ""
    log "=== Cleanup Complete ==="

    # Show remaining containers
    local remaining
    remaining=$(docker ps -a --filter "name=gitea" --format '{{.Names}}' 2>/dev/null | tr '\n' ' ')
    if [[ -n "$remaining" ]]; then
        warn "Remaining Gitea containers: $remaining"
    else
        log "No Gitea containers remaining"
    fi
}

main "$@"
