#!/bin/bash
# scripts/run-gitlab-tests.sh
#
# Master test runner for GitLab integration and E2E tests.
# Handles the complete lifecycle: cleanup → bootstrap → e2e → integration → cleanup
#
# Environment Variables:
#   DOCKER_CONTEXT   Docker context to use (default: "default" for local docker)
#   SKIP_CLEANUP     Set to "true" to skip cleanup at end (for debugging)
#   SKIP_BOOTSTRAP   Set to "true" to skip bootstrap (use existing GitLab)
#   SKIP_E2E         Set to "true" to skip E2E tests
#   SKIP_INTEGRATION Set to "true" to skip integration tests
#
# Usage:
#   ./scripts/run-gitlab-tests.sh
#   DOCKER_CONTEXT=remote-server ./scripts/run-gitlab-tests.sh
#
# Options:
#   --context NAME      Docker context to use (overrides DOCKER_CONTEXT env var)
#   --skip-cleanup      Skip cleanup at end (for debugging)
#   --skip-bootstrap    Skip bootstrap (use existing GitLab instance)
#   --skip-e2e          Skip E2E tests
#   --skip-integration  Skip integration tests
#   --cleanup-only      Only run cleanup (no tests)
#   -h, --help          Show this help
#
# Examples:
#   # Run full test suite on local docker
#   ./scripts/run-gitlab-tests.sh
#
#   # Run on remote docker context
#   DOCKER_CONTEXT=remote-server ./scripts/run-gitlab-tests.sh
#
#   # Skip bootstrap (GitLab already running)
#   ./scripts/run-gitlab-tests.sh --skip-bootstrap
#
#   # Just cleanup
#   ./scripts/run-gitlab-tests.sh --cleanup-only

set -euo pipefail

# Configuration
DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
SKIP_CLEANUP="${SKIP_CLEANUP:-false}"
SKIP_BOOTSTRAP="${SKIP_BOOTSTRAP:-false}"
SKIP_E2E="${SKIP_E2E:-false}"
SKIP_INTEGRATION="${SKIP_INTEGRATION:-false}"
CLEANUP_ONLY=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
step() { echo -e "${CYAN}[STEP]${NC} $1"; }
header() { echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}\n"; }

# Track test results
E2E_RESULT=0
INTEGRATION_RESULT=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --context) DOCKER_CONTEXT="$2"; shift 2 ;;
        --skip-cleanup) SKIP_CLEANUP=true; shift ;;
        --skip-bootstrap) SKIP_BOOTSTRAP=true; shift ;;
        --skip-e2e) SKIP_E2E=true; shift ;;
        --skip-integration) SKIP_INTEGRATION=true; shift ;;
        --cleanup-only) CLEANUP_ONLY=true; shift ;;
        -h|--help)
            head -40 "$0" | tail -35
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Export for child scripts
export DOCKER_CONTEXT

#############################################
# Cleanup function (runs on exit)
#############################################
final_cleanup() {
    local exit_code=$?

    if [[ "$SKIP_CLEANUP" == "true" ]]; then
        warn "Skipping final cleanup (SKIP_CLEANUP=true)"
        warn "Run manually: DOCKER_CONTEXT=$DOCKER_CONTEXT ./scripts/gitlab-cleanup.sh"
    else
        header "Final Cleanup"
        "$SCRIPT_DIR/gitlab-cleanup.sh" --context "$DOCKER_CONTEXT" || true
    fi

    return $exit_code
}

#############################################
# Initial cleanup
#############################################
run_initial_cleanup() {
    header "Initial Cleanup"
    log "Cleaning up any existing GitLab resources..."
    "$SCRIPT_DIR/gitlab-cleanup.sh" --context "$DOCKER_CONTEXT" || true
}

#############################################
# Bootstrap GitLab
#############################################
run_bootstrap() {
    if [[ "$SKIP_BOOTSTRAP" == "true" ]]; then
        log "Skipping bootstrap (--skip-bootstrap)"

        # Load existing env file if available
        if [[ -f "$PROJECT_ROOT/.env.gitlab-test" ]]; then
            log "Loading existing .env.gitlab-test"
            source "$PROJECT_ROOT/.env.gitlab-test"
        else
            error "No .env.gitlab-test found. Cannot skip bootstrap."
            exit 1
        fi
        return 0
    fi

    header "Bootstrap GitLab"
    "$SCRIPT_DIR/bootstrap-gitlab.sh" --context "$DOCKER_CONTEXT"

    # Source the generated env file
    if [[ -f "$PROJECT_ROOT/.env.gitlab-test" ]]; then
        source "$PROJECT_ROOT/.env.gitlab-test"
    fi
}

#############################################
# Run E2E tests
#############################################
run_e2e_tests() {
    if [[ "$SKIP_E2E" == "true" ]]; then
        log "Skipping E2E tests (--skip-e2e)"
        return 0
    fi

    header "E2E Tests"

    if "$SCRIPT_DIR/run-gitlab-e2e.sh"; then
        log "E2E tests PASSED"
        E2E_RESULT=0
    else
        error "E2E tests FAILED"
        E2E_RESULT=1
    fi
}

#############################################
# Run integration tests
#############################################
run_integration_tests() {
    if [[ "$SKIP_INTEGRATION" == "true" ]]; then
        log "Skipping integration tests (--skip-integration)"
        return 0
    fi

    header "Integration Tests"

    cd "$PROJECT_ROOT"

    if uv run pytest tests/integration/test_gitlab_provider.py -v -m "integration and gitlab"; then
        log "Integration tests PASSED"
        INTEGRATION_RESULT=0
    else
        error "Integration tests FAILED"
        INTEGRATION_RESULT=1
    fi
}

#############################################
# Print summary
#############################################
print_summary() {
    header "Test Summary"

    echo "Docker Context: $DOCKER_CONTEXT"
    echo ""

    if [[ "$SKIP_E2E" != "true" ]]; then
        if [[ $E2E_RESULT -eq 0 ]]; then
            echo -e "E2E Tests:         ${GREEN}PASSED${NC}"
        else
            echo -e "E2E Tests:         ${RED}FAILED${NC}"
        fi
    else
        echo -e "E2E Tests:         ${YELLOW}SKIPPED${NC}"
    fi

    if [[ "$SKIP_INTEGRATION" != "true" ]]; then
        if [[ $INTEGRATION_RESULT -eq 0 ]]; then
            echo -e "Integration Tests: ${GREEN}PASSED${NC}"
        else
            echo -e "Integration Tests: ${RED}FAILED${NC}"
        fi
    else
        echo -e "Integration Tests: ${YELLOW}SKIPPED${NC}"
    fi

    echo ""

    # Return overall result
    if [[ $E2E_RESULT -ne 0 ]] || [[ $INTEGRATION_RESULT -ne 0 ]]; then
        return 1
    fi
    return 0
}

#############################################
# Main
#############################################
main() {
    cd "$PROJECT_ROOT"

    echo ""
    log "=== GitLab Test Runner ==="
    log "Docker Context: $DOCKER_CONTEXT"
    echo ""

    # Cleanup only mode
    if [[ "$CLEANUP_ONLY" == "true" ]]; then
        run_initial_cleanup
        log "Cleanup complete"
        exit 0
    fi

    # Set up cleanup trap (only if not skipping)
    if [[ "$SKIP_CLEANUP" != "true" ]]; then
        trap final_cleanup EXIT
    fi

    # Run test lifecycle
    run_initial_cleanup
    run_bootstrap
    run_e2e_tests
    run_integration_tests

    # Print summary and exit with appropriate code
    if print_summary; then
        log "=== All Tests PASSED ==="
        exit 0
    else
        error "=== Some Tests FAILED ==="
        exit 1
    fi
}

main "$@"
