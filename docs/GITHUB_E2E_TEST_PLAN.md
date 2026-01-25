# GitHub E2E Comprehensive Test Plan

## Overview

This plan tests **all workflow tiers** deployed via `sapiens init --deploy-workflows all` to verify every workflow functions correctly on GitHub.

## Workflow Architecture

```
Tier: Essential
├── sapiens.yaml (thin wrapper)
│   └── calls: savorywatt/repo-sapiens/.github/workflows/sapiens-dispatcher.yaml@v0.5.1
│       └── handles labels: needs-planning, approved, execute, needs-review, needs-fix, requires-qa

Tier: Core
├── post-merge-docs.yaml (thin wrapper)
│   └── calls: sapiens-post-merge-docs.yaml@v0.5.1
└── weekly-test-coverage.yaml (thin wrapper)
    └── calls: sapiens-test-coverage.yaml@v0.5.1

Tier: Security
├── weekly-security-review.yaml
│   └── calls: sapiens-security-review.yaml@v0.5.1
├── weekly-dependency-audit.yaml
│   └── calls: sapiens-dependency-audit.yaml@v0.5.1
└── weekly-sbom-license.yaml
    └── calls: sapiens-sbom-license.yaml@v0.5.1

Tier: Support
└── daily-issue-triage.yaml
    └── calls: sapiens-issue-triage.yaml@v0.5.1
```

## Prerequisites

### Secrets Required
| Secret | Used By | Purpose |
|--------|---------|---------|
| `SAPIENS_GITHUB_TOKEN` | All workflows | GitHub API access |
| `OPENROUTER_API_KEY` | Essential tier (via dispatcher) | AI provider |
| `ANTHROPIC_API_KEY` | Recipe workflows | AI for code analysis |

### Test Repository Requirements
- Python project with `tests/` directory (for coverage)
- Some source code files (for security review)
- Open issues (for triage)

---

## Phase 0: Setup

### 0.1 Clean Test Repository
```bash
# Remove existing workflows and config
rm -rf .github/workflows/sapiens*.yaml
rm -rf .github/workflows/*-docs.yaml
rm -rf .github/workflows/*-coverage.yaml
rm -rf .github/workflows/*-security*.yaml
rm -rf .github/workflows/*-triage.yaml
rm -rf .sapiens/
git add -A && git commit -m "chore: Clean up for E2E test"
```

### 0.2 Deploy All Tiers
```bash
sapiens init \
  --non-interactive \
  --run-mode cicd \
  --deploy-workflows all \
  --git-token-env SAPIENS_GITHUB_TOKEN \
  --ai-provider openai-compatible \
  --ai-model deepseek/deepseek-r1-0528:free \
  --ai-base-url https://openrouter.ai/api/v1 \
  --ai-api-key-env OPENROUTER_API_KEY \
  --no-setup-secrets
```

### 0.3 Verify Deployment
Expected files:
- `.github/workflows/sapiens.yaml` (essential - dispatcher wrapper)
- `.github/workflows/post-merge-docs.yaml` (core)
- `.github/workflows/weekly-test-coverage.yaml` (core)
- `.github/workflows/weekly-security-review.yaml` (security)
- `.github/workflows/weekly-dependency-audit.yaml` (security)
- `.github/workflows/weekly-sbom-license.yaml` (security)
- `.github/workflows/daily-issue-triage.yaml` (support)
- `.sapiens/config.yaml`

---

## Phase 1: Essential Tier - Issue Labels

### Test 1.1: needs-planning Label
**Trigger:** Create issue with `needs-planning` label
**Expected:**
- Workflow `Sapiens Automation` triggers
- sapiens CLI processes label
- Comment with implementation plan posted to issue

### Test 1.2: approved/execute Label
**Trigger:** Add `approved` or `execute` label to issue with existing plan
**Expected:**
- Workflow triggers
- sapiens CLI attempts to execute the plan
- Progress/results posted to issue

---

## Phase 2: Essential Tier - PR Labels

### Test 2.1: Create Test PR
```bash
git checkout -b test/e2e-pr-labels
echo "# Test file" > test_file.md
git add test_file.md
git commit -m "test: Add test file for E2E"
git push -u origin test/e2e-pr-labels
gh pr create --title "E2E Test PR" --body "Testing PR label workflows"
```

### Test 2.2: needs-review Label
**Trigger:** Add `needs-review` label to PR
**Expected:**
- Workflow triggers
- Code review comments posted to PR

### Test 2.3: needs-fix Label
**Trigger:** Add `needs-fix` label to PR (after review finds issues)
**Expected:**
- Workflow triggers
- Fix commits pushed OR comment explaining what needs fixing

### Test 2.4: requires-qa Label
**Trigger:** Add `requires-qa` label to PR
**Expected:**
- Workflow triggers
- QA results posted to PR

---

## Phase 3: Core Tier

### Test 3.1: post-merge-docs
**Trigger:** `workflow_dispatch` via GitHub UI or:
```bash
gh workflow run "Update Documentation" --repo owner/repo
```
**Expected:**
- Workflow runs successfully
- Documentation updates committed (if changes detected)

### Test 3.2: weekly-test-coverage
**Trigger:** `workflow_dispatch` via:
```bash
gh workflow run "Improve Test Coverage" --repo owner/repo
```
**Expected:**
- Workflow runs
- Coverage analyzed
- PR created with new tests (if coverage below threshold)

---

## Phase 4: Security Tier

### Test 4.1: weekly-security-review
**Trigger:** `workflow_dispatch`
```bash
gh workflow run "Weekly Security Review" --repo owner/repo
```
**Expected:**
- Security scan runs
- Issues/PRs created for vulnerabilities found

### Test 4.2: weekly-dependency-audit
**Trigger:** `workflow_dispatch`
```bash
gh workflow run "Weekly Dependency Audit" --repo owner/repo
```
**Expected:**
- Dependency vulnerabilities checked
- Report generated

### Test 4.3: weekly-sbom-license
**Trigger:** `workflow_dispatch`
```bash
gh workflow run "SBOM & License Compliance" --repo owner/repo
```
**Expected:**
- SBOM generated
- License compliance checked

---

## Phase 5: Support Tier

### Test 5.1: daily-issue-triage
**Trigger:** `workflow_dispatch` or create new issue
```bash
gh workflow run "Daily Issue Triage" --repo owner/repo
```
**Expected:**
- Untriaged issues reviewed
- Labels applied automatically
- Comments added with classification

---

## Success Criteria

| Phase | Workflow | Success Criteria |
|-------|----------|------------------|
| 1.1 | needs-planning | Plan comment posted |
| 1.2 | approved/execute | Execution attempted |
| 2.2 | needs-review | Review comments posted |
| 2.3 | needs-fix | Fix attempted |
| 2.4 | requires-qa | QA results posted |
| 3.1 | post-merge-docs | Workflow completes |
| 3.2 | test-coverage | Coverage analyzed |
| 4.1 | security-review | Security scan completes |
| 4.2 | dependency-audit | Audit completes |
| 4.3 | sbom-license | SBOM generated |
| 5.1 | issue-triage | Issues labeled |

---

## Known Limitations

1. **AI API Keys**: Recipe workflows expect `ANTHROPIC_API_KEY`, essential tier uses `OPENROUTER_API_KEY`
2. **Template Placeholders**: `{{SECURITY_LANGUAGES}}` needs to be filled in during deployment
3. **Reusable Workflows**: Must be available at `@v0.5.1` tag in savorywatt/repo-sapiens
4. **Test Repo Content**: Some workflows need actual code/tests to analyze
