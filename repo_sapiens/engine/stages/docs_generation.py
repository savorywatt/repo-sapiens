"""Documentation generation stage - auto-generates documentation for code changes."""

from typing import Any

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue

log = structlog.get_logger(__name__)


class DocsGenerationStage(WorkflowStage):
    """Generate documentation when 'docs-generation' label is present.

    This stage:
    1. Detects issues/PRs with 'docs-generation' or 'sapiens/docs-generation' label
    2. Analyzes the code changes or issue description
    3. Generates appropriate documentation (API docs, README updates, docstrings)
    4. Posts documentation suggestions as a comment
    5. Updates label to 'docs-ready' or 'docs-generated'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute documentation generation.

        Args:
            issue: Issue with 'docs-generation' label
        """
        log.info("docs_generation_stage_start", issue=issue.number)

        # Check if already processed
        if "docs-ready" in issue.labels or "docs-generated" in issue.labels:
            log.debug("already_docs_generated", issue=issue.number)
            return

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"📚 **Starting Documentation Generation**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll analyze the code and generate documentation suggestions.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Try to get PR for this issue
            pr = await self._get_pr_for_issue(issue)

            if pr:
                # Generate docs based on PR changes
                await self._generate_docs_for_pr(issue, pr)
            else:
                # Generate docs based on issue description
                await self._generate_docs_for_issue(issue)

            log.info("docs_generation_stage_complete", issue=issue.number)

        except Exception as e:
            log.error("docs_generation_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Documentation Generation Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _get_pr_for_issue(self, issue: Issue) -> Any:
        """Try to find a PR associated with this issue."""
        try:
            pr = await self.git.get_pull_request(issue.number)
            return pr
        except Exception as e:
            log.debug("pr_lookup_failed", issue=issue.number, error=str(e))
            return None

    async def _generate_docs_for_pr(self, issue: Issue, pr: Any) -> None:
        """Generate documentation based on PR changes."""
        log.info("generating_docs_for_pr", pr=pr.number)

        # Get PR diff
        diff = await self.git.get_diff(pr.base, pr.head, pr_number=pr.number)

        if not diff:
            log.warning("empty_diff_for_docs", pr=pr.number)
            await self.git.add_comment(
                issue.number,
                "📝 **No Changes Found**\n\n"
                "The PR has no detectable changes to document.\n\n"
                "◆ Posted by Sapiens Automation",
            )
            return

        # Build context for agent
        context = {
            "pr_number": pr.number,
            "pr_title": pr.title,
            "pr_body": pr.body,
            "diff": diff,
        }

        prompt = f"""You are generating documentation for a pull request.

**PR Title**: {pr.title}
**PR Description**:
{pr.body or "(No description)"}

**Code Diff**:
```diff
{diff[:8000]}
```

**Instructions**:
Analyze the code changes and generate appropriate documentation:

1. **API Documentation**:
   - Document any new or modified public functions/methods
   - Include parameter descriptions, return types, and examples
   - Use docstring format appropriate for the language

2. **README Updates** (if applicable):
   - New features that should be documented
   - Configuration changes
   - New dependencies

3. **Code Comments**:
   - Complex logic that needs explanation
   - Non-obvious design decisions

4. **Changelog Entry**:
   - Suggested changelog entry for this change

Format your response with clear sections:

## API Documentation
[Generated docstrings or API docs]

## README Updates
[Suggested README changes, if any]

## Code Comments
[Suggested inline comments]

## Changelog Entry
[Suggested changelog text]

Be specific and provide ready-to-use documentation text.
"""

        result = await self.agent.execute_prompt(prompt, context, f"docs-gen-{pr.number}")

        if not result.get("success"):
            raise Exception(f"Documentation generation failed: {result.get('error')}")

        output = result.get("output", "No documentation generated.")

        # Post documentation suggestions
        await self.git.add_comment(
            issue.number,
            f"📚 **Documentation Generated**\n\n"
            f"Here are the suggested documentation updates for PR #{pr.number}:\n\n"
            f"{output}\n\n"
            f"---\n"
            f"Please review and apply the relevant documentation updates.\n\n"
            f"◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["docs-generation", "sapiens/docs-generation"]
        ]
        updated_labels.append("docs-ready")
        await self.git.update_issue(issue.number, labels=updated_labels)

    async def _generate_docs_for_issue(self, issue: Issue) -> None:
        """Generate documentation based on issue description."""
        log.info("generating_docs_for_issue", issue=issue.number)

        context = {
            "issue_number": issue.number,
            "issue_title": issue.title,
            "issue_body": issue.body,
        }

        prompt = f"""You are generating documentation based on an issue description.

**Issue Title**: {issue.title}

**Issue Description**:
{issue.body or "(No description provided)"}

**Instructions**:
Based on the issue, suggest what documentation should be created or updated:

1. **Feature Documentation**:
   - How should this feature be documented?
   - User-facing documentation needs

2. **Technical Documentation**:
   - Architecture documentation needs
   - API documentation if applicable

3. **Example Code**:
   - Code examples that should be included in docs

4. **Documentation Structure**:
   - Suggested location in the docs
   - Related documentation to update

Format your response with clear sections and actionable suggestions.
"""

        result = await self.agent.execute_prompt(prompt, context, f"docs-gen-issue-{issue.number}")

        if not result.get("success"):
            raise Exception(f"Documentation generation failed: {result.get('error')}")

        output = result.get("output", "No documentation suggestions generated.")

        # Post documentation plan
        await self.git.add_comment(
            issue.number,
            f"📚 **Documentation Plan Generated**\n\n"
            f"{output}\n\n"
            f"---\n"
            f"Use this plan when implementing the feature to ensure proper documentation.\n\n"
            f"◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["docs-generation", "sapiens/docs-generation"]
        ]
        updated_labels.append("docs-ready")
        await self.git.update_issue(issue.number, labels=updated_labels)
