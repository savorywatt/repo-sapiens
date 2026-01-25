# Manual Testing Checklist

Quick reference for manually testing Sapiens label-driven workflows on GitLab.

## Prerequisites

- GitLab instance with Sapiens CI components installed
- Repository with `.sapiens/config.yaml` configured
- AI provider accessible (Ollama at 192.168.1.241:11434 or OpenRouter)

## Core Label Workflows

### 1. Issue Triage
**Trigger**: Add `sapiens/triage` label to an issue

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue with title and description | Issue created |
| 2 | Add label `sapiens/triage` | Pipeline triggers |
| 3 | Wait for processing | Comment posted with classification |
| 4 | Verify labels updated | `triage` removed, type/priority/area labels added |

**Example issue:**
```
Title: Login button not working on mobile
Body: When I tap the login button on iOS Safari, nothing happens.
```

---

### 2. Proposal (Needs Work)
**Trigger**: Add `sapiens/needs-work` label to an issue

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue describing a feature/fix | Issue created |
| 2 | Add label `sapiens/needs-work` | Pipeline triggers |
| 3 | Wait for processing | AI posts implementation proposal |
| 4 | Review proposal comment | Contains approach, files to modify, considerations |

---

### 3. Approval & Execution
**Trigger**: Add `sapiens/approved` label after proposal

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | After proposal, add `sapiens/approved` | Pipeline triggers |
| 2 | Wait for processing | AI creates branch and MR |
| 3 | Check MR | Contains code changes implementing proposal |
| 4 | Verify labels | `approved` removed, `in-progress` or similar added |

---

### 4. Code Review
**Trigger**: Add `sapiens/needs-review` or `needs-review` label to MR

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create or find MR with changes | MR exists |
| 2 | Add label `sapiens/needs-review` | Pipeline triggers |
| 3 | Wait for processing | AI posts code review comment |
| 4 | Verify review | Contains findings, suggestions, approval status |
| 5 | Check labels | `needs-review` removed, `reviewed` added |

---

### 5. Fix Request
**Trigger**: Add `sapiens/needs-fix` label to MR

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Find MR with review comments | MR with feedback |
| 2 | Add label `sapiens/needs-fix` | Pipeline triggers |
| 3 | Wait for processing | AI analyzes what needs fixing |
| 4 | Verify comment | Lists fixes to be made |

---

### 6. QA Request
**Trigger**: Add `sapiens/requires-qa` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Find MR or issue | Target exists |
| 2 | Add label `sapiens/requires-qa` | Pipeline triggers |
| 3 | Wait for processing | AI posts QA checklist |
| 4 | Verify QA plan | Contains test scenarios, edge cases |

---

### 7. Security Review
**Trigger**: Add `sapiens/security-review` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create MR with code changes | MR with diff |
| 2 | Add label `sapiens/security-review` | Pipeline triggers |
| 3 | Wait for processing | Security analysis posted |
| 4 | Verify findings | OWASP categories, severity levels |
| 5 | Check labels | `security-review` removed, `security-reviewed` added |

**Security checks performed:**
- Injection flaws (SQL, XSS, command)
- Hardcoded secrets/credentials
- Authentication/authorization issues
- Insecure deserialization
- Known vulnerable dependencies

---

### 8. Dependency Audit
**Trigger**: Add `sapiens/dependency-audit` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue requesting audit | Issue created |
| 2 | Add label `sapiens/dependency-audit` | Pipeline triggers |
| 3 | Wait for processing | Audit results posted |
| 4 | Verify results | Vulnerability counts, outdated packages |
| 5 | Check labels | `dependency-audit` removed, `audit-complete` added |

---

### 9. Docs Generation
**Trigger**: Add `sapiens/docs-generation` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue about documentation | Issue created |
| 2 | Add label `sapiens/docs-generation` | Pipeline triggers |
| 3 | Wait for processing | Documentation generated/updated |
| 4 | Verify output | Docs or MR with doc changes |

---

### 10. Test Coverage
**Trigger**: Add `sapiens/test-coverage` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue about test coverage | Issue created |
| 2 | Add label `sapiens/test-coverage` | Pipeline triggers |
| 3 | Wait for processing | Coverage analysis posted |
| 4 | Verify analysis | Coverage gaps identified, test suggestions |

---

### 11. Plan Review
**Trigger**: Add `sapiens/plan-review` or `needs-plan-review` label

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Create issue with implementation plan | Issue with plan |
| 2 | Add label `sapiens/plan-review` | Pipeline triggers |
| 3 | Wait for processing | Plan feedback posted |
| 4 | Verify review | Suggestions, risks, improvements |

---

### 12. Merge
**Trigger**: MR approved and ready

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Have approved MR | MR with approvals |
| 2 | Sapiens detects approved state | Auto-merge triggered |
| 3 | Verify merge | MR merged, branch cleaned |

---

## Quick Smoke Test

Fastest way to verify Sapiens is working:

```bash
# 1. Create test issue via API (use SAPIENS_GITLAB_TOKEN - GITLAB_ prefix is reserved)
curl -X POST -H "PRIVATE-TOKEN: $SAPIENS_GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$PROJECT_ID/issues" \
  -d "title=Test: Button alignment broken" \
  -d "description=The submit button is misaligned on the checkout page." \
  -d "labels=sapiens/triage"

# 2. Watch for pipeline
# 3. Check issue for triage comment (should appear within 1-2 minutes)
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Pipeline doesn't trigger | Verify CI components installed, check `.gitlab-ci.yml` |
| "No handler for label" | Label not in config's `label_triggers` |
| AI returns empty response | Check Ollama/OpenRouter connectivity |
| Timeout errors | Increase `timeout` in agent config |
| "Rate limited" | OpenRouter quota exceeded |

### View Logs

```bash
# GitLab pipeline logs
# Navigate to: CI/CD > Pipelines > [job] > View log

# Local testing
uv run sapiens --config .sapiens/config.yaml process-label --label sapiens/triage --number 123
```

---

## Label Reference

| Label | Action |
|-------|--------|
| `sapiens/triage` | Classify and label issue |
| `sapiens/needs-work` | Generate implementation proposal |
| `sapiens/approved` | Execute approved proposal |
| `sapiens/needs-review` | Perform code review |
| `sapiens/needs-fix` | Identify fixes needed |
| `sapiens/requires-qa` | Generate QA test plan |
| `sapiens/security-review` | Security vulnerability scan |
| `sapiens/dependency-audit` | Audit dependencies |
| `sapiens/docs-generation` | Generate documentation |
| `sapiens/test-coverage` | Analyze test coverage |
| `sapiens/plan-review` | Review implementation plan |

Legacy labels (without `sapiens/` prefix) are also supported for backwards compatibility.
