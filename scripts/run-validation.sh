#!/bin/bash
# scripts/run-validation.sh
#
# Runs the complete validation suite against all providers.
# Idempotent - safe to run multiple times.
#
# Exit codes:
#   0 - All validations passed
#   1 - One or more validations failed
#   2 - Script error (missing dependencies, invalid config)

set -euo pipefail

# Configuration
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
RESULTS_DIR="${RESULTS_DIR:-./validation-results}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RUN_ID="validation-${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging functions
log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
die() { error "$1"; exit 2; }

# Cleanup trap
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 && "${CLEANUP_AFTER:-true}" == "true" ]]; then
        log "Cleaning up after failure..."
        cleanup_gitea_test_resources 2>/dev/null || true
    fi
    exit $exit_code
}
trap cleanup EXIT

# Verify dependencies
check_dependencies() {
    log "Checking dependencies..."

    command -v docker >/dev/null 2>&1 || die "docker not found"
    command -v curl >/dev/null 2>&1 || die "curl not found"
    command -v jq >/dev/null 2>&1 || die "jq not found"
    command -v uv >/dev/null 2>&1 || die "uv not found"

    # Verify Docker context
    if ! docker context inspect "$DOCKER_CONTEXT" >/dev/null 2>&1; then
        warn "Docker context '$DOCKER_CONTEXT' not found, using current context"
    else
        docker context use "$DOCKER_CONTEXT" 2>/dev/null || true
    fi

    log "Dependencies OK"
}

# Use remote Docker context
setup_docker_context() {
    if docker context inspect "$DOCKER_CONTEXT" >/dev/null 2>&1; then
        docker context use "$DOCKER_CONTEXT"
        log "Using Docker context: $DOCKER_CONTEXT"
    fi
}

#############################################
# Phase 1: Infrastructure Setup
#############################################
setup_infrastructure() {
    log "Phase 1: Setting up test infrastructure..."

    # Start Gitea (idempotent - docker compose handles existing containers)
    if [[ -f "plans/validation/docker/gitea.yaml" ]]; then
        log "Starting Gitea..."
        docker compose -f plans/validation/docker/gitea.yaml up -d gitea 2>/dev/null || {
            warn "Gitea compose file not found or failed to start"
        }

        # Wait for Gitea to be healthy
        log "Waiting for Gitea to be ready..."
        local timeout=120
        local elapsed=0
        while ! curl -sf http://localhost:3000/api/v1/version > /dev/null 2>&1; do
            sleep 2
            elapsed=$((elapsed + 2))
            if [[ $elapsed -ge $timeout ]]; then
                warn "Gitea did not become ready within ${timeout}s"
                break
            fi
        done
    fi

    # Start GitLab if requested
    if [[ "${INCLUDE_GITLAB:-false}" == "true" ]]; then
        if [[ -f "plans/validation/docker/gitlab.yaml" ]]; then
            log "Starting GitLab (this takes 5+ minutes)..."
            docker compose -f plans/validation/docker/gitlab.yaml up -d gitlab 2>/dev/null || {
                warn "GitLab compose file not found or failed to start"
            }

            # Wait for GitLab health
            local timeout=600
            local elapsed=0
            while ! curl -sf http://localhost:8080/-/health > /dev/null 2>&1; do
                sleep 10
                elapsed=$((elapsed + 10))
                if [[ $elapsed -ge $timeout ]]; then
                    warn "GitLab did not become ready within ${timeout}s"
                    break
                fi
            done
        fi
    fi

    # Start Ollama if not running
    if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        log "Starting Ollama..."
        if command -v ollama >/dev/null 2>&1; then
            ollama serve &
            sleep 5
        else
            warn "Ollama not installed, skipping"
        fi
    fi

    # Ensure test model is available
    if command -v ollama >/dev/null 2>&1; then
        log "Pulling test model..."
        ollama pull qwen3:8b 2>/dev/null || true
    fi
}

#############################################
# Phase 2: Reset Test State
#############################################
cleanup_gitea_test_resources() {
    local token="${SAPIENS_GITEA_TOKEN:-}"
    local base_url="http://localhost:3000"
    local owner="${GITEA_OWNER:-admin}"
    local repo="${GITEA_REPO:-test-repo}"

    if [[ -z "$token" ]]; then
        warn "No SAPIENS_GITEA_TOKEN - skipping Gitea cleanup"
        return 0
    fi

    # Delete test issues (those with "sapiens-test-" prefix)
    log "Cleaning up Gitea test issues..."
    local issues
    issues=$(curl -sf -H "Authorization: token $token" \
        "$base_url/api/v1/repos/$owner/$repo/issues?state=all" 2>/dev/null || echo "[]")

    echo "$issues" | jq -r '.[] | select(.title | startswith("sapiens-test-")) | .number' 2>/dev/null | \
    while read -r issue_num; do
        [[ -z "$issue_num" ]] && continue
        curl -sf -X PATCH -H "Authorization: token $token" \
            -H "Content-Type: application/json" \
            -d '{"state":"closed"}' \
            "$base_url/api/v1/repos/$owner/$repo/issues/$issue_num" > /dev/null 2>&1 || true
    done

    # Delete test branches
    log "Cleaning up Gitea test branches..."
    local branches
    branches=$(curl -sf -H "Authorization: token $token" \
        "$base_url/api/v1/repos/$owner/$repo/branches" 2>/dev/null || echo "[]")

    echo "$branches" | jq -r '.[] | select(.name | startswith("sapiens-test-")) | .name' 2>/dev/null | \
    while read -r branch; do
        [[ -z "$branch" ]] && continue
        curl -sf -X DELETE -H "Authorization: token $token" \
            "$base_url/api/v1/repos/$owner/$repo/branches/$branch" > /dev/null 2>&1 || true
    done
}

reset_test_state() {
    log "Phase 2: Resetting test state..."
    cleanup_gitea_test_resources
}

#############################################
# Phase 3: Run Validation Tests
#############################################
run_validations() {
    log "Phase 3: Running validation tests..."

    mkdir -p "$RESULTS_DIR/$RUN_ID"

    # Test configurations
    declare -A CONFIGS=(
        ["gitea-ollama"]=".sapiens/config-gitea-ollama.yaml"
        ["gitea-claude"]=".sapiens/config-gitea-claude.yaml"
    )

    if [[ "${INCLUDE_GITLAB:-false}" == "true" ]]; then
        CONFIGS["gitlab-ollama"]=".sapiens/config-gitlab-ollama.yaml"
    fi

    if [[ -n "${SAPIENS_GITHUB_TOKEN:-}" ]]; then
        CONFIGS["github-ollama"]=".sapiens/config-github-ollama.yaml"
    fi

    declare -a FAILED=()
    declare -a PASSED=()

    for name in "${!CONFIGS[@]}"; do
        config="${CONFIGS[$name]}"
        result_file="$RESULTS_DIR/$RUN_ID/${name}.json"

        log "Testing: $name"

        if [[ ! -f "$config" ]]; then
            warn "Config not found: $config - skipping"
            continue
        fi

        if uv run sapiens health-check --config "$config" --full --json > "$result_file" 2>&1; then
            PASSED+=("$name")
            log "  PASSED"
        else
            FAILED+=("$name")
            error "  FAILED (see $result_file)"
        fi
    done

    # Store results for report
    echo "${PASSED[*]}" > "$RESULTS_DIR/$RUN_ID/.passed"
    echo "${FAILED[*]}" > "$RESULTS_DIR/$RUN_ID/.failed"
}

#############################################
# Phase 4: Cleanup (optional)
#############################################
cleanup_resources() {
    if [[ "${CLEANUP_AFTER:-true}" == "true" ]]; then
        log "Phase 4: Cleaning up test resources..."
        cleanup_gitea_test_resources
    fi
}

#############################################
# Phase 5: Report Results
#############################################
generate_report() {
    log "Phase 5: Generating report..."

    local passed
    local failed
    read -ra passed < "$RESULTS_DIR/$RUN_ID/.passed" 2>/dev/null || passed=()
    read -ra failed < "$RESULTS_DIR/$RUN_ID/.failed" 2>/dev/null || failed=()

    REPORT_FILE="$RESULTS_DIR/$RUN_ID/summary.md"

    cat > "$REPORT_FILE" << REPORT_EOF
# Validation Report: $RUN_ID

**Date**: $(date -Iseconds)
**Docker Context**: $DOCKER_CONTEXT

## Results

| Configuration | Status |
|---------------|--------|
REPORT_EOF

    for name in "${passed[@]}"; do
        [[ -n "$name" ]] && echo "| $name | PASSED |" >> "$REPORT_FILE"
    done

    for name in "${failed[@]}"; do
        [[ -n "$name" ]] && echo "| $name | FAILED |" >> "$REPORT_FILE"
    done

    cat >> "$REPORT_FILE" << REPORT_EOF

## Summary

- **Passed**: ${#passed[@]}
- **Failed**: ${#failed[@]}
- **Total**: $((${#passed[@]} + ${#failed[@]}))

## Detailed Results

See individual JSON files in \`$RESULTS_DIR/$RUN_ID/\`
REPORT_EOF

    log "Report saved to: $REPORT_FILE"

    # Return exit code based on results
    if [[ ${#failed[@]} -gt 0 ]]; then
        error "Validation FAILED: ${#failed[@]} configuration(s) failed"
        return 1
    else
        log "Validation PASSED: All ${#passed[@]} configuration(s) succeeded"
        return 0
    fi
}

#############################################
# Main
#############################################
main() {
    log "=== Validation Suite ==="
    log "Run ID: $RUN_ID"
    echo ""

    check_dependencies
    setup_docker_context
    setup_infrastructure
    reset_test_state
    run_validations
    cleanup_resources
    generate_report
}

main "$@"
