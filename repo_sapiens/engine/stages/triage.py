"""Triage stage - categorizes and prioritizes incoming issues."""

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue

log = structlog.get_logger(__name__)


class TriageStage(WorkflowStage):
    """Triage issues when 'triage' or 'sapiens/triage' label is present.

    This stage:
    1. Detects issues with triage label
    2. Analyzes issue title and body
    3. Suggests appropriate labels (bug, feature, enhancement, etc.)
    4. Estimates priority/severity
    5. Posts triage summary as comment
    6. Updates labels to include suggested categories
    """

    async def execute(self, issue: Issue) -> None:
        """Execute issue triage.

        Args:
            issue: Issue with 'triage' label
        """
        log.info("triage_stage_start", issue=issue.number)

        # Check if already triaged
        if "triaged" in issue.labels:
            log.debug("already_triaged", issue=issue.number)
            return

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🏷️ **Starting Issue Triage**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll analyze this issue and suggest appropriate labels and priority.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Perform triage analysis
            triage_result = await self._analyze_issue(issue)

            # Post triage results
            await self._post_triage_results(issue, triage_result)

            log.info("triage_stage_complete", issue=issue.number)

        except Exception as e:
            log.error("triage_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Triage Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please triage this issue manually.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _analyze_issue(self, issue: Issue) -> dict:
        """Analyze issue and determine categorization."""
        log.info("analyzing_issue_for_triage", issue=issue.number)

        context = {
            "issue_number": issue.number,
            "issue_title": issue.title,
            "issue_body": issue.body,
            "existing_labels": issue.labels,
        }

        prompt = f"""Analyze this issue and perform triage.

**Issue Title**: {issue.title}

**Issue Body**:
{issue.body or "(No description provided)"}

**Existing Labels**: {', '.join(issue.labels) if issue.labels else 'None'}

**Instructions**:
Analyze this issue and determine:

1. **Issue Type** (choose one):
   - `bug` - Something isn't working as expected
   - `feature` - New functionality request
   - `enhancement` - Improvement to existing functionality
   - `documentation` - Documentation-related
   - `question` - Needs clarification or discussion
   - `chore` - Maintenance task

2. **Priority** (choose one):
   - `priority:critical` - Blocks critical functionality, needs immediate attention
   - `priority:high` - Important but not blocking
   - `priority:medium` - Normal priority
   - `priority:low` - Nice to have, not urgent

3. **Complexity** (choose one):
   - `complexity:small` - Quick fix, few hours
   - `complexity:medium` - Several days of work
   - `complexity:large` - Week or more of work
   - `complexity:epic` - Needs to be broken down

4. **Area/Component** (if identifiable):
   - `area:frontend`
   - `area:backend`
   - `area:api`
   - `area:infrastructure`
   - `area:testing`
   - `area:security`
   (or other relevant areas)

5. **Additional Context**:
   - Is this a duplicate? If so, of what?
   - Are there missing details needed?
   - Who might be best suited to work on this?

**Response Format**:
Provide your analysis in the following JSON format:
```json
{{
  "type": "bug|feature|enhancement|documentation|question|chore",
  "priority": "critical|high|medium|low",
  "complexity": "small|medium|large|epic",
  "areas": ["area:backend"],
  "suggested_labels": ["bug", "priority:high", "area:backend"],
  "needs_more_info": false,
  "possible_duplicate_of": null,
  "summary": "Brief one-line summary of the issue",
  "recommended_action": "What should happen next"
}}
```

Be accurate and conservative in your assessment. When uncertain, prefer lower priority.
"""

        result = await self.agent.execute_prompt(prompt, context, f"triage-{issue.number}")

        if not result.get("success"):
            raise Exception(f"Triage analysis failed: {result.get('error')}")

        # Parse the response
        output = result.get("output", "")
        triage_data = self._parse_triage_response(output)

        return triage_data

    def _parse_triage_response(self, output: str) -> dict:
        """Parse the triage response from the agent."""
        import json
        import re

        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        try:
            # Find JSON-like structure
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(output[json_start:json_end])
        except json.JSONDecodeError:
            pass

        # Fallback: create basic triage from text
        return {
            "type": "question",
            "priority": "medium",
            "complexity": "medium",
            "areas": [],
            "suggested_labels": [],
            "needs_more_info": True,
            "possible_duplicate_of": None,
            "summary": "Unable to parse triage automatically",
            "recommended_action": "Manual review recommended",
            "raw_analysis": output,
        }

    async def _post_triage_results(self, issue: Issue, triage_result: dict) -> None:
        """Post triage results and update labels."""
        # Build the summary comment
        summary_parts = [
            "🏷️ **Triage Complete**\n",
            f"**Summary**: {triage_result.get('summary', 'Issue analyzed')}\n",
            "",
            "## Classification",
            "",
            "| Category | Value |",
            "|----------|-------|",
            f"| Type | `{triage_result.get('type', 'unknown')}` |",
            f"| Priority | `{triage_result.get('priority', 'medium')}` |",
            f"| Complexity | `{triage_result.get('complexity', 'medium')}` |",
        ]

        if triage_result.get("areas"):
            summary_parts.append(f"| Areas | {', '.join(triage_result['areas'])} |")

        summary_parts.extend(["", "## Suggested Labels", ""])

        suggested = triage_result.get("suggested_labels", [])
        if suggested:
            for label in suggested:
                summary_parts.append(f"- `{label}`")
        else:
            summary_parts.append("- No additional labels suggested")

        summary_parts.extend(["", "## Recommended Action", ""])
        summary_parts.append(triage_result.get("recommended_action", "Ready for planning"))

        if triage_result.get("needs_more_info"):
            summary_parts.extend(
                [
                    "",
                    "⚠️ **Note**: This issue may need more information before work can begin.",
                ]
            )

        if triage_result.get("possible_duplicate_of"):
            summary_parts.extend(
                [
                    "",
                    f"🔍 **Possible Duplicate**: #{triage_result['possible_duplicate_of']}",
                ]
            )

        if triage_result.get("raw_analysis"):
            summary_parts.extend(
                [
                    "",
                    "<details>",
                    "<summary>Raw Analysis</summary>",
                    "",
                    triage_result["raw_analysis"],
                    "",
                    "</details>",
                ]
            )

        summary_parts.extend(["", "---", "", "◆ Posted by Sapiens Automation"])

        await self.git.add_comment(issue.number, "\n".join(summary_parts))

        # Update labels
        updated_labels = [label for label in issue.labels if label not in ["triage", "sapiens/triage"]]

        # Add suggested labels
        for label in triage_result.get("suggested_labels", []):
            if label not in updated_labels:
                updated_labels.append(label)

        # Add triaged marker
        updated_labels.append("triaged")

        # Add needs-more-info if flagged
        if triage_result.get("needs_more_info"):
            updated_labels.append("needs-more-info")

        await self.git.update_issue(issue.number, labels=updated_labels)

        log.info(
            "triage_labels_updated",
            issue=issue.number,
            labels=updated_labels,
            type=triage_result.get("type"),
            priority=triage_result.get("priority"),
        )
