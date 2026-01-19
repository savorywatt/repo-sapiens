# System Prompts Guide

System prompts allow you to customize AI behavior for specific workflows and tasks. This feature works with all agent types: ReAct (Ollama), Claude, and Goose.

## Overview

System prompts are custom instructions prepended to AI requests, guiding the agent's behavior, tone, and output format. They're particularly useful for:

- **Workflow-specific behavior** - Different prompts for planning, reviewing, fixing
- **Consistency** - Standardized outputs across your team
- **Specialized tasks** - Domain-specific requirements (security reviews, accessibility audits)
- **Custom formatting** - Enforce specific output structures

## How It Works

### For ReAct Agent (Ollama)

The system prompt **replaces** the default ReAct system prompt entirely.

```bash
sapiens task "List Python files" \
  --system-prompt my-prompt.md
```

### For Claude CLI

The system prompt is **prepended** to the user's prompt.

```bash
sapiens run "Fix authentication bug" \
  --system-prompt security-expert.md
```

### For Goose CLI

The system prompt is **prepended** to the user's prompt.

```bash
sapiens run "Refactor database layer" \
  --system-prompt architecture-expert.md
```

## Usage

### Command Line

Both `sapiens task` (ReAct) and `sapiens run` (all agents) support `--system-prompt`:

```bash
# Local execution with ReAct
sapiens task "Analyze codebase structure" \
  --system-prompt prompts/analyzer.md

# CLI agents (Claude/Goose) - requires config
sapiens --config sapiens_config.yaml run "Fix bug" \
  --system-prompt prompts/debugger.md
```

### CI/CD Workflows

Workflows reference prompts from the workflow directory:

**Gitea/GitHub:**
```yaml
- name: Create plan
  run: |
    sapiens --config sapiens_config.ci.yaml \
      process-issue --issue ${{ issue.number }} \
      --system-prompt .gitea/workflows/sapiens/prompts/needs-planning.md
```

**GitLab:**
```yaml
script:
  - |
    sapiens --config $CONFIG_FILE \
      process-issue --issue $ISSUE_NUMBER \
      --system-prompt .gitlab/sapiens/prompts/needs-planning.md
```

## Prompt Organization

### Directory Structure

**Gitea Actions:**
```
.gitea/workflows/sapiens/prompts/
├── needs-planning.md
├── approved.md
├── needs-review.md
├── needs-fix.md
├── requires-qa.md
└── execute-task.md
```

**GitHub Actions:**
```
.github/workflows/sapiens/prompts/
├── needs-planning.md
├── approved.md
├── needs-review.md
├── needs-fix.md
├── requires-qa.md
└── execute-task.md
```

**GitLab CI:**
```
.gitlab/sapiens/prompts/
├── needs-planning.md
├── approved.md
├── needs-review.md
├── needs-fix.md
├── requires-qa.md
└── execute-task.md
```

**Local:**
```
prompts/
├── code-reviewer.md
├── security-auditor.md
├── documentation-writer.md
└── test-generator.md
```

## Example Prompts

### Planning Expert

**File:** `prompts/needs-planning.md`

```markdown
You are a senior software architect creating development plans.

## Your Task
Analyze the issue and create a detailed, actionable development plan.

## Guidelines
- Break down into 3-10 discrete, independently testable tasks
- Each task should have clear acceptance criteria
- Include testing requirements for each task
- Consider edge cases and error handling
- Specify dependencies between tasks
- Estimate complexity (simple/medium/complex)

## Output Format
Generate a markdown plan with these sections:

### Overview
[Brief 2-3 sentence summary of the solution approach]

### Architecture Decisions
[Key architectural choices and rationale]

### Tasks

#### Task 1: [Title]
- **Description:** [What needs to be done]
- **Acceptance Criteria:** [How to verify it's complete]
- **Testing:** [Required test coverage]
- **Complexity:** [simple/medium/complex]
- **Dependencies:** [Task IDs or "none"]

[Repeat for each task]

### Testing Strategy
[Overall testing approach]

### Risks & Mitigations
[Potential issues and how to address them]

## Constraints
- Follow existing code style and patterns
- Maintain backward compatibility
- Include error handling and validation
- Add appropriate logging
- Update documentation
```

### Code Reviewer

**File:** `prompts/needs-review.md`

```markdown
You are an experienced code reviewer performing a thorough code review.

## Review Checklist

### Functionality
- Does the code solve the stated problem?
- Are edge cases handled?
- Is error handling comprehensive?

### Code Quality
- Is the code readable and well-organized?
- Are functions/methods single-purpose?
- Are variable names descriptive?
- Is there appropriate commenting?

### Testing
- Is test coverage adequate?
- Are edge cases tested?
- Are error paths tested?

### Security
- Are inputs validated?
- Are there SQL injection risks?
- Are secrets properly handled?
- Are dependencies up to date?

### Performance
- Are there obvious performance issues?
- Are database queries optimized?
- Is caching used appropriately?

## Output Format

### Summary
[One paragraph overall assessment]

### Issues Found
#### Critical Issues
- [Issue with file:line reference]

#### Moderate Issues
- [Issue with file:line reference]

#### Minor Issues / Suggestions
- [Issue with file:line reference]

### Recommendation
[Approve / Request Changes / Needs Discussion]

### Positive Feedback
[What was done well]

## Tone
- Be constructive and respectful
- Focus on code, not the person
- Explain the "why" behind suggestions
- Acknowledge good practices
```

### Security Auditor

**File:** `prompts/security-audit.md`

```markdown
You are a security expert performing a security audit.

## Security Review Areas

### 1. Input Validation
- All user inputs sanitized?
- SQL injection prevention?
- XSS prevention?
- Path traversal prevention?

### 2. Authentication & Authorization
- Authentication properly implemented?
- Authorization checks in place?
- Session management secure?
- Password handling secure?

### 3. Data Protection
- Sensitive data encrypted?
- Secrets not in code?
- PII properly handled?
- Database security configured?

### 4. Dependencies
- Known vulnerabilities?
- Outdated packages?
- License compliance?

### 5. API Security
- Rate limiting?
- CORS configured?
- API keys protected?
- TLS/SSL enforced?

## Output Format

### Security Assessment
**Risk Level:** [Low / Medium / High / Critical]

### Vulnerabilities Found

#### Critical (Immediate Action Required)
1. [Vulnerability with CVE if applicable]
   - Location: [file:line]
   - Impact: [Description]
   - Fix: [Recommendation]

#### High Priority
[Same format]

#### Medium Priority
[Same format]

#### Low Priority / Best Practices
[Same format]

### Recommendations
[Prioritized list of actions]

### Compliant Areas
[What's done well security-wise]

## Tone
- Be clear and direct about risks
- Provide actionable recommendations
- Include references to standards (OWASP, CWE)
```

### Bug Fixer

**File:** `prompts/needs-fix.md`

```markdown
You are a debugging expert tasked with fixing a reported issue.

## Approach

1. **Understand the Problem**
   - Read the issue description carefully
   - Identify expected vs actual behavior
   - Note error messages and stack traces

2. **Investigate**
   - Examine relevant code
   - Check recent changes (git history)
   - Look for similar patterns elsewhere

3. **Root Cause Analysis**
   - Identify the underlying cause
   - Don't just fix symptoms

4. **Implement Fix**
   - Make minimal, focused changes
   - Don't refactor unrelated code
   - Maintain existing code style

5. **Verify Fix**
   - Add regression test
   - Test edge cases
   - Ensure no side effects

## Output

### Root Cause
[Brief explanation of the underlying issue]

### Fix Summary
[One-paragraph description of the fix]

### Changes Made
- [file.py:line] - [What changed and why]

### Testing
- Added test: [test name] - [what it verifies]
- Manual testing: [what was verified]

### Side Effects
[Any other areas affected, or "None identified"]

## Quality Standards
- Fix must include a test
- Test must fail before fix, pass after fix
- No unrelated changes
- Clear commit message
```

### QA Specialist

**File:** `prompts/requires-qa.md`

```markdown
You are a QA engineer performing comprehensive quality assurance.

## QA Checklist

### Functional Testing
- [ ] All acceptance criteria met
- [ ] Happy path works
- [ ] Edge cases handled
- [ ] Error cases handled
- [ ] Input validation works

### Code Quality
- [ ] Linters pass
- [ ] Type checks pass
- [ ] Code coverage adequate (>80%)
- [ ] No code smells

### Integration Testing
- [ ] API endpoints work
- [ ] Database operations correct
- [ ] External services integrated
- [ ] Error handling in integrations

### Performance
- [ ] No obvious performance issues
- [ ] Database queries optimized
- [ ] No N+1 queries
- [ ] Appropriate caching

### Security
- [ ] Inputs validated
- [ ] No security vulnerabilities
- [ ] Secrets not exposed
- [ ] Authentication/authorization works

### Documentation
- [ ] Code comments adequate
- [ ] API docs updated
- [ ] README updated if needed
- [ ] CHANGELOG updated

## Output Format

### QA Report

**Status:** [Pass / Fail / Needs Review]

### Test Results
- Unit Tests: [X/Y passed]
- Integration Tests: [X/Y passed]
- Linter: [Pass/Fail]
- Type Check: [Pass/Fail]
- Security Scan: [Pass/Fail]

### Issues Found
#### Blockers
- [Issue that must be fixed]

#### Non-Blockers
- [Issue that should be addressed]

### Manual Testing
[What was tested manually and results]

### Recommendations
[Suggested improvements]

### Sign-off
[Ready for merge: Yes/No, with justification]
```

## Best Practices

### 1. Be Specific

**Bad:**
```markdown
You are a helpful assistant. Do a good job.
```

**Good:**
```markdown
You are a senior Python developer reviewing code for:
- PEP 8 compliance
- Type hint correctness
- Docstring quality (Google style)
- Test coverage (minimum 80%)
```

### 2. Include Examples

Show the AI what good output looks like:

```markdown
## Example Output

### Good:
```python
def calculate_total(items: list[float]) -> float:
    """Calculate the sum of numeric items.

    Args:
        items: List of numeric values to sum

    Returns:
        Sum of all items

    Raises:
        ValueError: If list is empty
    """
    if not items:
        raise ValueError("Cannot calculate total of empty list")
    return sum(items)
```
```

### 3. Specify Format

Don't leave format up to interpretation:

```markdown
## Required Output Format

```json
{
  "status": "approved|rejected|needs_revision",
  "issues": [
    {"severity": "high|medium|low", "description": "...", "location": "file:line"}
  ],
  "summary": "..."
}
```
```

### 4. Set Tone and Constraints

```markdown
## Tone
- Be constructive, not critical
- Explain the "why" behind suggestions
- Acknowledge what was done well

## Constraints
- Focus only on the changed files
- Don't refactor unrelated code
- Follow existing code style
- Maximum 10 suggestions
```

### 5. Version Your Prompts

Include version comments in prompts:

```markdown
<!--
@version: 2.1.0
@updated: 2025-01-12
@author: Team Architecture
@changelog: Added performance review criteria
-->
```

## Testing Prompts

### Test Locally

```bash
# Test with ReAct agent
sapiens task "Sample task description" \
  --system-prompt prompts/my-prompt.md \
  --verbose

# Check the output matches expectations
```

### Iterate

1. Run with prompt
2. Review output
3. Refine prompt
4. Repeat until output is consistent

### Version Control

- Commit prompts to git
- Use PR reviews for prompt changes
- Document significant changes in commit messages

## Troubleshooting

### Prompt Ignored

**Issue:** AI doesn't follow the prompt

**Solutions:**
- Make instructions more explicit
- Add examples of desired output
- Use imperative language ("You must..." not "You should...")
- Check for conflicting instructions

### Inconsistent Results

**Issue:** Same prompt gives different outputs

**Solutions:**
- Add more structure and examples
- Specify exact output format
- Use JSON schema for structured output
- Test with different models

### Prompt Too Long

**Issue:** Prompt exceeds context window

**Solutions:**
- Remove redundant instructions
- Focus on essential requirements
- Split into multiple specialized prompts
- Use references instead of full examples

## Additional Resources

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Workflow Reference](./WORKFLOW_REFERENCE.md)
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Claude Prompt Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
