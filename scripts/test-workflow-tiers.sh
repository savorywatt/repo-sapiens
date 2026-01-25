#!/bin/bash
# scripts/test-workflow-tiers.sh
#
# E2E tests for tiered workflow deployment on Gitea.
# Tests install, update, and remove operations for each workflow tier.
#
# Usage:
#   ./scripts/test-workflow-tiers.sh [OPTIONS]
#
# Options:
#   --bootstrap       Auto-bootstrap Gitea if not configured
#   --url URL         Gitea URL (default: http://localhost:3000)
#   --docker NAME     Docker container name (default: gitea-test)
#   --skip-remove     Skip removal tests (keep workflows deployed)
#   -h, --help        Show this help message
#
# Environment:
#   SAPIENS_GITEA_TOKEN   Gitea API token (required)
#   GITEA_OWNER           Repository owner (default: testadmin)
#   GITEA_REPO            Repository name (default: test-repo)
#
# Exit codes:
#   0 - All tests passed
#   1 - Test failed
#   2 - Prerequisites not met

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
GITEA_URL="${GITEA_URL:-http://localhost:3000}"
GITEA_OWNER="${GITEA_OWNER:-testadmin}"
GITEA_REPO="${GITEA_REPO:-test-repo}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-gitea-test}"
AUTO_BOOTSTRAP=false
SKIP_REMOVE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Test state
TESTS_PASSED=0
TESTS_FAILED=0

# Logging functions
log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
step() { echo -e "${CYAN}[STEP]${NC} $1"; }
header() { echo -e "\n${BOLD}=== $1 ===${NC}\n"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bootstrap) AUTO_BOOTSTRAP=true; shift ;;
        --url) GITEA_URL="$2"; shift 2 ;;
        --docker) DOCKER_CONTAINER="$2"; shift 2 ;;
        --skip-remove) SKIP_REMOVE=true; shift ;;
        -h|--help)
            head -25 "$0" | tail -20
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 2 ;;
    esac
done

#############################################
# API Helpers
#############################################

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

# Check if file exists in repo via API
file_exists() {
    local file_path="$1"
    gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" > /dev/null 2>&1
}

# Get file content from repo via API
get_file_content() {
    local file_path="$1"
    gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" 2>/dev/null | \
        jq -r '.content // empty' | base64 -d 2>/dev/null || echo ""
}

# Corrupt a file by replacing content
corrupt_file() {
    local file_path="$1"
    local response
    response=$(gitea_api GET "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" 2>/dev/null)
    local sha
    sha=$(echo "$response" | jq -r '.sha // empty')

    if [[ -z "$sha" ]]; then
        return 1
    fi

    local corrupt_content
    corrupt_content=$(echo "# CORRUPTED FILE - E2E TEST" | base64 -w 0)

    gitea_api PUT "/repos/$GITEA_OWNER/$GITEA_REPO/contents/$file_path" "{
        \"message\": \"E2E test: corrupt file for update test\",
        \"content\": \"$corrupt_content\",
        \"sha\": \"$sha\"
    }" > /dev/null 2>&1
}

#############################################
# Prerequisites
#############################################

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
    if "$bootstrap_script" --url "$GITEA_URL" --docker "$DOCKER_CONTAINER" --output "$env_file"; then
        # shellcheck source=/dev/null
        source "$env_file"
        rm -f "$env_file"
        log "Bootstrap complete, credentials loaded"
        return 0
    fi

    return 1
}

check_prerequisites() {
    log "Checking prerequisites..."

    # Check Gitea is accessible
    if ! curl -sf "$GITEA_URL/api/v1/version" > /dev/null 2>&1; then
        if maybe_bootstrap_gitea; then
            log "Gitea bootstrapped successfully"
        else
            error "Gitea not accessible at $GITEA_URL"
            error "Run with --bootstrap or start Gitea manually"
            exit 2
        fi
    fi

    # Check for token
    if [[ -z "${SAPIENS_GITEA_TOKEN:-}" ]]; then
        if maybe_bootstrap_gitea; then
            log "Token obtained from bootstrap"
        else
            error "SAPIENS_GITEA_TOKEN is required"
            exit 2
        fi
    fi

    # Check uv is available
    if ! command -v uv >/dev/null 2>&1; then
        error "uv not found"
        exit 2
    fi

    # Update owner/repo from environment if set by bootstrap
    GITEA_OWNER="${GITEA_OWNER:-testadmin}"
    GITEA_REPO="${GITEA_REPO:-test-repo}"

    log "Prerequisites OK"
    log "  Gitea: $GITEA_URL"
    log "  Repo: $GITEA_OWNER/$GITEA_REPO"
}

#############################################
# Test Helpers
#############################################

# Record test result
test_pass() {
    local test_name="$1"
    echo -e "  ${GREEN}✓${NC} $test_name"
    ((TESTS_PASSED++))
}

test_fail() {
    local test_name="$1"
    local reason="${2:-}"
    echo -e "  ${RED}✗${NC} $test_name"
    if [[ -n "$reason" ]]; then
        echo -e "    ${RED}Reason: $reason${NC}"
    fi
    ((TESTS_FAILED++))
}

# Create temporary config file for sapiens
create_test_config() {
    local config_file="/tmp/sapiens-tier-test-$$.yaml"
    cat > "$config_file" << EOF
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
EOF
    echo "$config_file"
}

# Run sapiens init with given options
run_sapiens_init() {
    local config_file="$1"
    shift
    uv run sapiens --config "$config_file" init \
        --non-interactive \
        --no-setup-secrets \
        --no-deploy-actions \
        "$@" 2>&1
}

#############################################
# Tier Test Functions
#############################################

# Get expected files for a tier
get_tier_files() {
    local tier="$1"
    case "$tier" in
        essential)
            echo ".github/workflows/sapiens/process-label.yaml"
            ;;
        core)
            echo ".github/workflows/sapiens/recipes/post-merge-docs.yaml"
            echo ".github/workflows/sapiens/recipes/weekly-test-coverage.yaml"
            ;;
        security)
            echo ".github/workflows/sapiens/recipes/weekly-security-review.yaml"
            echo ".github/workflows/sapiens/recipes/weekly-dependency-audit.yaml"
            echo ".github/workflows/sapiens/recipes/weekly-sbom-license.yaml"
            ;;
        support)
            echo ".github/workflows/sapiens/recipes/daily-issue-triage.yaml"
            ;;
    esac
}

# Test: Install tier
test_install_tier() {
    local tier="$1"
    local config_file="$2"

    step "Testing install for tier: $tier"

    # Deploy the tier
    local output
    output=$(run_sapiens_init "$config_file" --deploy-workflows "$tier" 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Install $tier" "sapiens init failed"
        return 1
    fi

    # Verify files exist
    local files
    files=$(get_tier_files "$tier")
    local all_exist=true

    for file in $files; do
        if file_exists "$file"; then
            log "    Found: $file"
        else
            error "    Missing: $file"
            all_exist=false
        fi
    done

    if $all_exist; then
        test_pass "Install $tier"
        return 0
    else
        test_fail "Install $tier" "Some files missing"
        return 1
    fi
}

# Test: Idempotent re-deploy
test_idempotent() {
    local tier="$1"
    local config_file="$2"

    step "Testing idempotent re-deploy for tier: $tier"

    # Re-deploy the same tier
    local output
    output=$(run_sapiens_init "$config_file" --deploy-workflows "$tier" 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Idempotent $tier" "sapiens init failed on re-deploy"
        return 1
    fi

    # Verify files still exist
    local files
    files=$(get_tier_files "$tier")

    for file in $files; do
        if ! file_exists "$file"; then
            test_fail "Idempotent $tier" "File disappeared: $file"
            return 1
        fi
    done

    test_pass "Idempotent $tier"
    return 0
}

# Test: Update corrupted file
test_update() {
    local tier="$1"
    local config_file="$2"

    step "Testing update (corrupt + re-deploy) for tier: $tier"

    # Get first file of tier to corrupt
    local files
    files=$(get_tier_files "$tier")
    local first_file
    first_file=$(echo "$files" | head -1)

    # Corrupt the file
    if ! corrupt_file "$first_file"; then
        test_fail "Update $tier" "Could not corrupt file: $first_file"
        return 1
    fi
    log "    Corrupted: $first_file"

    # Verify it's corrupted
    local content
    content=$(get_file_content "$first_file")
    if [[ "$content" != *"CORRUPTED"* ]]; then
        test_fail "Update $tier" "File corruption not detected"
        return 1
    fi

    # Re-deploy to restore
    local output
    output=$(run_sapiens_init "$config_file" --deploy-workflows "$tier" 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Update $tier" "sapiens init failed on update"
        return 1
    fi

    # Verify file is restored (contains template marker)
    content=$(get_file_content "$first_file")
    if [[ "$content" == *"@repo-sapiens-template"* ]] || [[ "$content" == *"Sapiens"* ]]; then
        test_pass "Update $tier"
        return 0
    else
        test_fail "Update $tier" "File not properly restored"
        return 1
    fi
}

# Test: Remove tier
test_remove_tier() {
    local tier="$1"
    local config_file="$2"

    step "Testing remove for tier: $tier"

    # Remove the tier
    local output
    output=$(run_sapiens_init "$config_file" --remove-workflows "$tier" 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Remove $tier" "sapiens init failed"
        return 1
    fi

    # Verify files are gone
    local files
    files=$(get_tier_files "$tier")
    local all_gone=true

    for file in $files; do
        if file_exists "$file"; then
            error "    Still exists: $file"
            all_gone=false
        else
            log "    Removed: $file"
        fi
    done

    if $all_gone; then
        test_pass "Remove $tier"
        return 0
    else
        test_fail "Remove $tier" "Some files still exist"
        return 1
    fi
}

# Test: Install all tiers
test_install_all() {
    local config_file="$1"

    step "Testing install all tiers"

    local output
    output=$(run_sapiens_init "$config_file" --deploy-workflows all 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Install all" "sapiens init failed"
        return 1
    fi

    # Count all expected files
    local total_files=0
    local found_files=0

    for tier in essential core security support; do
        local files
        files=$(get_tier_files "$tier")
        for file in $files; do
            ((total_files++))
            if file_exists "$file"; then
                ((found_files++))
            fi
        done
    done

    if [[ $found_files -eq $total_files ]]; then
        test_pass "Install all ($found_files workflows deployed)"
        return 0
    else
        test_fail "Install all" "Only $found_files of $total_files files found"
        return 1
    fi
}

# Test: Remove all tiers
test_remove_all() {
    local config_file="$1"

    step "Testing remove all tiers"

    local output
    output=$(run_sapiens_init "$config_file" --remove-workflows all 2>&1)

    if [[ $? -ne 0 ]]; then
        test_fail "Remove all" "sapiens init failed"
        return 1
    fi

    # Verify all files are gone
    local remaining=0

    for tier in essential core security support; do
        local files
        files=$(get_tier_files "$tier")
        for file in $files; do
            if file_exists "$file"; then
                ((remaining++))
                error "    Still exists: $file"
            fi
        done
    done

    if [[ $remaining -eq 0 ]]; then
        test_pass "Remove all (all files cleaned up)"
        return 0
    else
        test_fail "Remove all" "$remaining files still remain"
        return 1
    fi
}

#############################################
# Main Test Runner
#############################################

run_tier_tests() {
    local tier="$1"
    local config_file="$2"

    header "[$tier]"

    test_install_tier "$tier" "$config_file" || true
    test_idempotent "$tier" "$config_file" || true
    test_update "$tier" "$config_file" || true

    if [[ "$SKIP_REMOVE" != "true" ]]; then
        test_remove_tier "$tier" "$config_file" || true
    else
        log "Skipping remove test (--skip-remove)"
    fi
}

main() {
    header "Workflow Tier E2E Tests"

    check_prerequisites

    local config_file
    config_file=$(create_test_config)
    log "Using config: $config_file"

    # Test each tier individually
    for tier in essential core security support; do
        run_tier_tests "$tier" "$config_file"
    done

    # Test all tiers together
    header "[all]"
    test_install_all "$config_file" || true

    if [[ "$SKIP_REMOVE" != "true" ]]; then
        test_remove_all "$config_file" || true
    fi

    # Cleanup
    rm -f "$config_file"

    # Summary
    header "Test Summary"
    echo -e "  ${GREEN}Passed${NC}: $TESTS_PASSED"
    echo -e "  ${RED}Failed${NC}: $TESTS_FAILED"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}=== All tests passed ===${NC}"
        exit 0
    else
        echo -e "${RED}${BOLD}=== Some tests failed ===${NC}"
        exit 1
    fi
}

main "$@"
