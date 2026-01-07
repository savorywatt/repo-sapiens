# Documentation Accuracy Review Report

**Date:** 2026-01-06
**Reviewed by:** 7 parallel review agents
**Files Reviewed:** 21 documentation files

---

## Executive Summary

The documentation suite contains **significant accuracy issues** that could mislead users and cause setup failures. The most critical problems are:

1. **Phantom features** - Webhook server, multiple CLI commands, and workflow files documented but don't exist
2. **Wrong paths** - `.repo-sapiens` vs `.sapiens`, config file locations inconsistent
3. **Outdated tooling** - Black formatter references (now Ruff), pip instead of uv
4. **Incorrect secrets** - `AUTOMATION__*` env vars documented but actual secrets are `SAPIENS_*`

**Overall Health:** 42% of documents have critical issues requiring immediate attention.

---

## Summary by Document Group

| Group | Files | Avg Score | Critical Issues |
|-------|-------|-----------|-----------------|
| Credentials | 3 | 8.3/10 | 2 (wrong paths, wrong encryption algo) |
| Setup/Getting Started | 3 | 6.7/10 | 4 (phantom webhook, missing docs, wrong paths) |
| Architecture | 3 | 8.0/10 | 2 (wrong class names, phantom workflows) |
| Deployment/CI | 3 | 4.0/10 | 12 (phantom workflows, wrong secrets, phantom commands) |
| Agent/Execution | 3 | 7.2/10 | 4 (phantom CLI options, invalid provider type) |
| Contributor/Maintainer | 4 | 7.3/10 | 3 (wrong package manager, wrong formatter) |
| API/Index | 2 | 5.5/10 | 4 (10 phantom doc files, missing api/modules.rst) |

---

## Critical Issues (Must Fix Immediately)

### 1. Phantom Webhook Server
**Files:** `GETTING_STARTED.md`, `DEPLOYMENT_GUIDE.md`
**Issue:** Documentation describes `sapiens webhook-server` command and webhook configuration that don't exist.
**Impact:** Users will attempt to run non-existent commands.
**Fix:** Remove lines 633-664 in GETTING_STARTED.md and lines 194-221 in DEPLOYMENT_GUIDE.md.

### 2. Wrong Directory Paths
**Files:** `CREDENTIALS.md`, `api/credentials.md`, `GITEA_NEW_REPO_TUTORIAL.md`
**Issue:** Documentation uses `.repo-sapiens/` but actual code uses `.sapiens/`.
**Impact:** Credentials stored in wrong location, config files not found.
**Fix:** Replace all `.repo-sapiens` with `.sapiens`.

### 3. Wrong Secret Names
**Files:** `DEPLOYMENT_GUIDE.md`, `ci-cd-usage.md`, `actions-configuration.md`
**Issue:** Documents `AUTOMATION__GIT_PROVIDER__API_TOKEN` but actual secrets are `SAPIENS_GITEA_TOKEN` and `SAPIENS_CLAUDE_API_KEY`.
**Impact:** CI/CD workflows fail with authentication errors.
**Fix:** Update all secret references to use `SAPIENS_*` naming.

### 4. Phantom Workflow Files
**Files:** `DEPLOYMENT_GUIDE.md`, `ci-cd-usage.md`, `workflow-diagram.md`
**Issue:** References `automation-trigger.yaml`, `plan-merged.yaml`, `monitor.yaml` which don't exist.
**Actual workflows:** `needs-planning.yaml`, `approved.yaml`, `execute-task.yaml`, etc.
**Fix:** Replace with actual workflow file names.

### 5. Phantom CLI Commands
**Files:** `ci-cd-usage.md`, `AGENT_COMPARISON.md`, `LOCAL_EXECUTION_WORKFLOW.md`
**Issue:** Documents these non-existent commands:
- `sapiens generate-prompts`
- `sapiens list-active-plans` (actual: `list-plans`)
- `sapiens check-stale`
- `sapiens check-failures`
- `react --backend` option
- `react --api-key` option
**Fix:** Remove phantom commands; update `list-active-plans` to `list-plans`.

### 6. Phantom API Documentation Files
**File:** `docs/api/README.md`
**Issue:** References 10 non-existent API documentation files.
**Missing:** `configuration.md`, `git-discovery.md`, `git-providers.md`, `agent-providers.md`, `template-engine.md`, `template-filters.md`, `security.md`, `orchestrator.md`, `workflow-stages.md`, `state-management.md`
**Fix:** Either create these files or remove the references.

### 7. Wrong Encryption Algorithm
**Files:** `CREDENTIALS.md`, `api/credentials.md`
**Issue:** States "AES-256-GCM encryption" but actual implementation uses Fernet (AES-128-CBC + HMAC).
**Fix:** Update to "Fernet (AES-128-CBC + HMAC)".

---

## High Priority Issues

### Package Manager (pip vs uv)
**Files:** `CONTRIBUTING.md`, `DEVELOPER_SETUP.md`, `GITEA_NEW_REPO_TUTORIAL.md`
**Issue:** Documentation recommends `pip install` but project uses `uv`.
**Fix:** Replace `pip install -e ".[dev]"` with `uv sync --group dev`.

### Formatter (Black vs Ruff)
**Files:** `CONTRIBUTING.md`
**Issue:** Multiple references to Black formatter, but project uses Ruff.
**Fix:** Replace Black references with Ruff format documentation.

### State Directory Inconsistency
**Issue:** Some docs use `.automation/state`, others use `.sapiens/state`.
**Reality:** `init.py` generates `.sapiens/state` but settings model defaults to `.automation/state`.
**Fix:** Standardize on `.sapiens/state` throughout.

### Invalid Provider Type
**Files:** `AGENT_COMPARISON.md`
**Issue:** Mentions `openai-compatible` as a provider type.
**Reality:** Valid types are only: `claude-local`, `claude-api`, `goose-local`, `goose-api`, `openai`, `ollama`.
**Fix:** Remove `openai-compatible` references or clarify it should use `openai` type with custom `base_url`.

### GitHub vs Gitea URLs
**Files:** Multiple (12 occurrences)
**Issue:** Primary remote is Gitea but docs reference GitHub URLs.
**Fix:** Update to Gitea URLs or add note about primary remote.

### Missing api/modules.rst
**File:** `docs/source/index.rst`
**Issue:** References `api/modules` which doesn't exist.
**Fix:** Run `sphinx-apidoc -o docs/source/api/ repo_sapiens/` or remove reference.

---

## Medium Priority Issues

| File | Issue | Fix |
|------|-------|-----|
| `ARCHITECTURE.md` | Class name `TemplateEngine` should be `SecureTemplateEngine` | Update example code |
| `ARCHITECTURE.md` | Class name `CheckpointingManager` should be `CheckpointManager` | Update reference |
| `AGENT_COMPARISON.md` | Default model `qwen3:latest` should be `qwen3:8b` | Update default |
| `LOCAL_EXECUTION_WORKFLOW.md` | Config path `repo_sapiens/config/automation_config.yaml` wrong | Use `.sapiens/config.yaml` |
| `DEVELOPER_SETUP.md` | References missing `.pre-commit-quick-reference.md` | Remove reference |
| `CREDENTIALS.md` | Duplicate file `docs/api/credentials.md` | Consolidate |
| `actions-configuration.md` | Action version `setup-python@v4` should be `@v5` | Update version |
| `INIT_COMMAND_GUIDE.md` | Line 198 wrong default path | Fix to `.sapiens/config.yaml` |

---

## Document-by-Document Scores

| Document | Score | Status |
|----------|-------|--------|
| `CREDENTIALS.md` | 8/10 | Needs path fix |
| `api/credentials.md` | 8/10 | Duplicate, needs consolidation |
| `secrets-setup.md` | 9/10 | Good |
| `GETTING_STARTED.md` | 5/10 | Critical issues |
| `DEVELOPER_SETUP.md` | 7/10 | Missing file refs |
| `INIT_COMMAND_GUIDE.md` | 8/10 | Minor path issue |
| `ARCHITECTURE.md` | 8/10 | Class name fixes |
| `workflow-diagram.md` | 7/10 | Phantom workflows |
| `ERROR_HANDLING.md` | 9/10 | Good |
| `DEPLOYMENT_GUIDE.md` | 4/10 | Critical issues |
| `ci-cd-usage.md` | 3/10 | Major rewrite needed |
| `actions-configuration.md` | 5/10 | Multiple issues |
| `AGENT_COMPARISON.md` | 6.5/10 | Phantom CLI options |
| `GOOSE_SETUP.md` | 8/10 | Good |
| `LOCAL_EXECUTION_WORKFLOW.md` | 7/10 | Path issues |
| `CONTRIBUTING.md` | 6/10 | Tooling outdated |
| `CONTRIBUTOR_LICENSE_AGREEMENT.md` | 9/10 | Good |
| `MAINTAINERS.md` | 9/10 | Good |
| `GITEA_NEW_REPO_TUTORIAL.md` | 5/10 | Path issues |
| `api/README.md` | 4/10 | Phantom files |
| `source/index.rst` | 7/10 | Missing module |

---

## Recommended Fix Priority

### Week 1 - Critical
1. Remove all phantom webhook documentation
2. Fix secret names (`SAPIENS_*` convention)
3. Fix directory paths (`.sapiens/` convention)
4. Remove phantom CLI commands

### Week 2 - High
1. Update package manager references (uv)
2. Update formatter references (Ruff)
3. Fix workflow file references
4. Generate or remove api/modules.rst

### Week 3 - Medium
1. Fix class name references
2. Update action versions
3. Consolidate duplicate credentials docs
4. Update GitHub URLs to Gitea

---

## Files Requiring Complete Rewrite

1. **`ci-cd-usage.md`** - Score 3/10, majority of content references non-existent features
2. **`DEPLOYMENT_GUIDE.md`** - Score 4/10, webhook and workflow sections entirely phantom

---

## Verification Commands

After fixes, verify with:

```bash
# Check CLI commands exist
uv run sapiens --help

# Check config path
uv run sapiens health-check

# Check secrets used in workflows
grep -h "secrets\\." .gitea/workflows/*.yaml | sort | uniq

# Check actual workflow files
ls -la .gitea/workflows/

# Build docs to verify rst/md references
cd docs && make html
```

---

## Report Generated By

7 parallel Explore agents conducting independent codebase verification:
- Credentials docs agent
- Setup/getting started docs agent
- Architecture docs agent
- Deployment/CI docs agent
- Agent/execution docs agent
- Contributor/maintainer docs agent
- API/index docs agent

Each agent read documentation files, then verified claims against actual code using grep, glob, bash commands, and file reads.
