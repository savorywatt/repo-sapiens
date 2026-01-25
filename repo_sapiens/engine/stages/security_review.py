"""Security review stage - performs security-focused code review."""


import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue, PullRequest

log = structlog.get_logger(__name__)


class SecurityReviewStage(WorkflowStage):
    """Perform security review when 'security-review' label is present.

    This stage:
    1. Detects issues/PRs with 'security-review' or 'sapiens/security-review' label
    2. Analyzes code for security vulnerabilities (OWASP Top 10)
    3. Checks for hardcoded secrets
    4. Reviews authentication/authorization code
    5. Posts security findings as a comment
    6. Updates label to 'security-reviewed'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute security review.

        Args:
            issue: Issue with 'security-review' label
        """
        log.info("security_review_stage_start", issue=issue.number)

        # Check if already reviewed
        if "security-reviewed" in issue.labels:
            log.debug("already_security_reviewed", issue=issue.number)
            return

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔒 **Starting Security Review**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll analyze the code for security vulnerabilities.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Try to get PR for this issue
            pr = await self._get_pr_for_issue(issue)

            if pr:
                await self._review_pr_security(issue, pr)
            else:
                await self._review_issue_security(issue)

            log.info("security_review_stage_complete", issue=issue.number)

        except Exception as e:
            log.error("security_review_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Security Review Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _get_pr_for_issue(self, issue: Issue) -> PullRequest | None:
        """Try to find a PR associated with this issue."""
        try:
            pr = await self.git.get_pull_request(issue.number)
            return pr
        except Exception as e:
            log.debug("pr_lookup_failed", issue=issue.number, error=str(e))
            return None

    async def _review_pr_security(self, issue: Issue, pr: PullRequest) -> None:
        """Perform security review on PR changes."""
        log.info("reviewing_pr_security", pr=pr.number)

        # Get PR diff
        diff = await self.git.get_diff(pr.base, pr.head, pr_number=pr.number)

        if not diff:
            log.warning("empty_diff_for_security", pr=pr.number)
            await self.git.add_comment(
                issue.number,
                "📝 **No Changes to Review**\n\n"
                "The PR has no detectable changes for security review.\n\n"
                "◆ Posted by Sapiens Automation",
            )
            return

        context = {
            "pr_number": pr.number,
            "pr_title": pr.title,
            "pr_body": pr.body,
            "diff": diff,
        }

        prompt = f"""You are performing a security-focused code review on a pull request.

**PR Title**: {pr.title}
**PR Description**:
{pr.body or "(No description)"}

**Code Diff**:
```diff
{diff[:10000]}
```

**Security Review Checklist** (OWASP Top 10 & Best Practices):

1. **Injection Flaws**:
   - SQL injection
   - Command injection
   - XSS (Cross-Site Scripting)
   - LDAP injection
   - Path traversal

2. **Broken Authentication**:
   - Weak password requirements
   - Missing rate limiting
   - Insecure session management
   - Missing MFA considerations

3. **Sensitive Data Exposure**:
   - Hardcoded secrets/credentials
   - API keys in code
   - Sensitive data in logs
   - Unencrypted sensitive data

4. **XML External Entities (XXE)**:
   - Unsafe XML parsing
   - External entity references

5. **Broken Access Control**:
   - Missing authorization checks
   - IDOR vulnerabilities
   - Privilege escalation risks

6. **Security Misconfiguration**:
   - Debug mode enabled
   - Default credentials
   - Unnecessary features enabled

7. **Cross-Site Scripting (XSS)**:
   - Unescaped user input
   - Unsafe innerHTML usage
   - Missing Content Security Policy

8. **Insecure Deserialization**:
   - Unsafe pickle/marshal usage
   - JSON parsing of untrusted data

9. **Known Vulnerabilities**:
   - Outdated libraries with CVEs
   - Deprecated security functions

10. **Insufficient Logging**:
    - Missing security event logging
    - Sensitive data in logs

**Response Format**:
For each finding, provide:

## Security Findings

### Finding 1: [Title]
- **Severity**: Critical/High/Medium/Low/Info
- **Category**: [OWASP category]
- **Location**: [file:line if identifiable]
- **Description**: [What the issue is]
- **Risk**: [What could happen if exploited]
- **Recommendation**: [How to fix it]

If no issues found, state:
## Security Review Passed
No security issues identified in this code review.

Be thorough but avoid false positives. Focus on actual security risks, not style issues.
"""

        result = await self.agent.execute_prompt(prompt, context, f"security-review-{pr.number}")

        if not result.get("success"):
            raise Exception(f"Security review failed: {result.get('error')}")

        output = result.get("output", "Unable to complete security review.")

        # Determine severity for labels
        has_critical = "Critical" in output or "critical" in output
        has_high = "High" in output or "high" in output
        passed = "Security Review Passed" in output or "No security issues" in output

        # Post review
        severity_indicator = "🔴" if has_critical else ("🟠" if has_high else ("🟢" if passed else "🟡"))

        await self.git.add_comment(
            issue.number,
            f"{severity_indicator} **Security Review Complete**\n\n"
            f"PR: #{pr.number}\n\n"
            f"{output}\n\n"
            f"---\n"
            f"⚠️ This is an automated security scan. Manual review by a security expert "
            f"is recommended for sensitive changes.\n\n"
            f"◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["security-review", "sapiens/security-review"]
        ]
        updated_labels.append("security-reviewed")

        if has_critical:
            updated_labels.append("security-critical")
        elif has_high:
            updated_labels.append("security-warning")

        await self.git.update_issue(issue.number, labels=updated_labels)

    async def _review_issue_security(self, issue: Issue) -> None:
        """Provide security considerations for an issue without a PR."""
        log.info("reviewing_issue_security", issue=issue.number)

        context = {
            "issue_number": issue.number,
            "issue_title": issue.title,
            "issue_body": issue.body,
        }

        prompt = f"""Analyze this issue from a security perspective.

**Issue Title**: {issue.title}

**Issue Description**:
{issue.body or "(No description provided)"}

**Instructions**:
Review this feature/bug request and identify:

1. **Security Implications**:
   - What security concerns might arise during implementation?
   - What security requirements should be considered?

2. **Threat Model**:
   - What are potential attack vectors?
   - What assets are at risk?
   - Who are potential threat actors?

3. **Security Requirements**:
   - Authentication/authorization needs
   - Data protection requirements
   - Input validation requirements
   - Logging/auditing needs

4. **Implementation Guidance**:
   - Security patterns to follow
   - Common pitfalls to avoid
   - Libraries/frameworks to use for security

5. **Testing Recommendations**:
   - Security tests to implement
   - Penetration testing considerations
   - Edge cases to cover

Format your response with clear sections. Be specific and actionable.
"""

        result = await self.agent.execute_prompt(prompt, context, f"security-analysis-{issue.number}")

        if not result.get("success"):
            raise Exception(f"Security analysis failed: {result.get('error')}")

        output = result.get("output", "Unable to complete security analysis.")

        # Post analysis
        await self.git.add_comment(
            issue.number,
            f"🔒 **Security Analysis Complete**\n\n"
            f"{output}\n\n"
            f"---\n"
            f"Consider these security aspects during implementation.\n\n"
            f"◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["security-review", "sapiens/security-review"]
        ]
        updated_labels.append("security-reviewed")
        await self.git.update_issue(issue.number, labels=updated_labels)
