"""Comment response stage - AI-driven comment analysis and action execution."""

import json
import re
from dataclasses import dataclass
from typing import Any

import structlog

from repo_sapiens.config.triggers import CommentAction, CommentTriggerConfig
from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Comment, Issue

log = structlog.get_logger(__name__)


@dataclass
class CommentContext:
    """Context for processing a comment."""

    issue_number: int
    comment_id: int
    comment_author: str
    comment_body: str


@dataclass
class ActionRequest:
    """A single action requested by the AI."""

    action_type: CommentAction
    value: str


@dataclass
class AnalysisResult:
    """Result of AI comment analysis."""

    intent: str
    actions: list[ActionRequest]
    confidence: float
    reasoning: str | None = None


class CommentResponseStage(WorkflowStage):
    """Process issue comments and execute AI-suggested actions.

    This stage:
    1. Receives comment context from the CLI command
    2. Validates the comment should be processed (not bot, has keywords)
    3. Gathers full issue context (body, previous comments)
    4. Asks AI to analyze intent and suggest actions
    5. Executes allowed actions (add labels, reply, close)
    6. Posts a confirmation comment
    """

    async def execute(self, issue: Issue) -> None:
        """Execute is not used directly - use process_comment instead."""
        raise NotImplementedError(
            "CommentResponseStage.execute() should not be called directly. "
            "Use process_comment() with CommentContext instead."
        )

    async def process_comment(
        self,
        issue: Issue,
        context: CommentContext,
    ) -> dict[str, Any]:
        """Process a comment and execute suggested actions.

        Args:
            issue: The issue the comment was made on
            context: Comment context with author and body

        Returns:
            Result dictionary with success status and details
        """
        log.info(
            "comment_response_start",
            issue=issue.number,
            comment_id=context.comment_id,
            author=context.comment_author,
        )

        # Get comment trigger config
        config = self._get_config()

        # Check if this is a bot comment (prevent infinite loops)
        if config.ignore_bot_comments and self._is_bot_comment(context.comment_body, config):
            log.debug("ignoring_bot_comment", comment_id=context.comment_id)
            return {"success": True, "skipped": True, "reason": "Bot comment ignored"}

        # Check for trigger keywords
        if not self._has_trigger_keyword(context.comment_body, config):
            log.debug("no_trigger_keyword", comment_id=context.comment_id)
            return {"success": True, "skipped": True, "reason": "No trigger keyword found"}

        try:
            # Gather context for AI
            previous_comments = await self._gather_comment_context(issue, config)

            # Analyze with AI
            analysis = await self._analyze_comment(issue, context, previous_comments, config)

            if not analysis.actions:
                log.info("no_actions_suggested", issue=issue.number)
                return {"success": True, "skipped": True, "reason": "AI suggested no actions"}

            # Execute actions
            executed_actions = await self._execute_actions(issue, analysis, config)

            # Post confirmation
            await self._post_confirmation(issue, context, executed_actions, config)

            log.info(
                "comment_response_complete",
                issue=issue.number,
                actions_executed=len(executed_actions),
            )

            return {
                "success": True,
                "intent": analysis.intent,
                "actions_executed": [{"type": a.action_type.value, "value": a.value} for a in executed_actions],
            }

        except Exception as e:
            log.error(
                "comment_response_failed",
                issue=issue.number,
                error=str(e),
                exc_info=True,
            )
            # Post error comment
            await self.git.add_comment(
                issue.number,
                f"I encountered an error processing your comment:\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"{self._get_config().bot_signature}",
            )
            raise

    def _get_config(self) -> CommentTriggerConfig:
        """Get comment trigger configuration."""
        if hasattr(self.settings, "automation") and self.settings.automation:
            return self.settings.automation.comment_triggers
        return CommentTriggerConfig()

    def _is_bot_comment(self, body: str, config: CommentTriggerConfig) -> bool:
        """Check if comment was made by the bot."""
        return config.bot_signature in body

    def _has_trigger_keyword(self, body: str, config: CommentTriggerConfig) -> bool:
        """Check if comment contains a trigger keyword."""
        body_lower = body.lower()
        return any(keyword.lower() in body_lower for keyword in config.keywords)

    async def _gather_comment_context(
        self,
        issue: Issue,
        config: CommentTriggerConfig,
    ) -> list[Comment]:
        """Gather previous comments for context (excluding bot comments)."""
        all_comments = await self.git.get_comments(issue.number)

        # Filter out bot comments and limit to last 10
        filtered = [c for c in all_comments if not self._is_bot_comment(c.body, config)]

        return filtered[-10:]  # Last 10 non-bot comments

    async def _analyze_comment(
        self,
        issue: Issue,
        context: CommentContext,
        previous_comments: list[Comment],
        config: CommentTriggerConfig,
    ) -> AnalysisResult:
        """Use AI to analyze the comment and determine actions."""
        log.info("analyzing_comment", issue=issue.number, comment_id=context.comment_id)

        # Format previous comments
        formatted_comments = self._format_comments(previous_comments)

        # Build allowed actions list
        allowed_actions_str = ", ".join(a.value for a in config.allowed_actions)

        prompt = f"""Analyze this issue comment and determine what actions to take.

**Issue #{issue.number}: {issue.title}**
State: {issue.state} | Labels: {', '.join(issue.labels) if issue.labels else 'None'}

**Issue Description:**
{issue.body or "(No description provided)"}

**Previous Comments ({len(previous_comments)} shown):**
{formatted_comments if formatted_comments else "(No previous comments)"}

**New Comment by @{context.comment_author}:**
{context.comment_body}

**Instructions:**
Determine what the user wants based on their comment. You can suggest the following actions:
- `add_label`: Add a label to the issue (value = label name)
- `remove_label`: Remove a label from the issue (value = label name)
- `reply`: Post a reply comment (value = reply text)
- `close_issue`: Close the issue (value = closing reason)

**Constraints:**
- Only suggest actions from this allowed list: {allowed_actions_str}
- Maximum {config.max_actions_per_comment} actions
- Be conservative - only suggest actions the user clearly requested
- If the request is unclear, suggest a `reply` asking for clarification

**Response Format (JSON):**
```json
{{
  "intent": "Brief description of what the user wants",
  "confidence": 0.0 to 1.0,
  "reasoning": "Why you chose these actions",
  "actions": [
    {{"type": "add_label", "value": "bug"}},
    {{"type": "reply", "value": "Done! I've added the bug label."}}
  ]
}}
```

If no action is needed, return an empty actions array.
"""

        ai_context = {
            "issue_number": issue.number,
            "comment_id": context.comment_id,
            "author": context.comment_author,
        }

        result = await self.agent.execute_prompt(
            prompt,
            ai_context,
            f"comment-analysis-{issue.number}-{context.comment_id}",
        )

        if not result.get("success"):
            raise Exception(f"AI analysis failed: {result.get('error')}")

        return self._parse_analysis_response(result.get("output", ""), config)

    def _format_comments(self, comments: list[Comment]) -> str:
        """Format comments for the AI prompt."""
        if not comments:
            return ""

        lines = []
        for c in comments:
            timestamp = c.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[@{c.author} at {timestamp}]:\n{c.body}\n")

        return "\n---\n".join(lines)

    def _parse_analysis_response(
        self,
        output: str,
        config: CommentTriggerConfig,
    ) -> AnalysisResult:
        """Parse the AI response into an AnalysisResult."""
        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                data = {}
        else:
            # Try to find raw JSON
            try:
                json_start = output.find("{")
                json_end = output.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(output[json_start:json_end])
                else:
                    data = {}
            except json.JSONDecodeError:
                data = {}

        # Parse actions
        actions = []
        allowed_types = {a.value for a in config.allowed_actions}

        for action_data in data.get("actions", []):
            action_type_str = action_data.get("type", "")
            value = action_data.get("value", "")

            if action_type_str in allowed_types and value:
                try:
                    action_type = CommentAction(action_type_str)
                    actions.append(ActionRequest(action_type=action_type, value=value))
                except ValueError:
                    log.warning("invalid_action_type", action_type=action_type_str)

        # Limit actions
        actions = actions[: config.max_actions_per_comment]

        return AnalysisResult(
            intent=data.get("intent", "Unknown intent"),
            actions=actions,
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning"),
        )

    async def _execute_actions(
        self,
        issue: Issue,
        analysis: AnalysisResult,
        config: CommentTriggerConfig,
    ) -> list[ActionRequest]:
        """Execute the suggested actions."""
        executed = []
        current_labels = list(issue.labels)

        for action in analysis.actions:
            try:
                if action.action_type == CommentAction.ADD_LABEL:
                    if action.value not in current_labels:
                        current_labels.append(action.value)
                        await self.git.update_issue(issue.number, labels=current_labels)
                        log.info("label_added", issue=issue.number, label=action.value)
                    executed.append(action)

                elif action.action_type == CommentAction.REMOVE_LABEL:
                    if action.value in current_labels:
                        current_labels.remove(action.value)
                        await self.git.update_issue(issue.number, labels=current_labels)
                        log.info("label_removed", issue=issue.number, label=action.value)
                    executed.append(action)

                elif action.action_type == CommentAction.REPLY:
                    # Reply is handled in confirmation, but track it
                    executed.append(action)

                elif action.action_type == CommentAction.CLOSE_ISSUE:
                    if CommentAction.CLOSE_ISSUE in config.allowed_actions:
                        await self.git.update_issue(issue.number, state="closed")
                        log.info("issue_closed", issue=issue.number, reason=action.value)
                        executed.append(action)

            except Exception as e:
                log.error(
                    "action_execution_failed",
                    action_type=action.action_type.value,
                    error=str(e),
                )

        return executed

    async def _post_confirmation(
        self,
        issue: Issue,
        context: CommentContext,
        executed_actions: list[ActionRequest],
        config: CommentTriggerConfig,
    ) -> None:
        """Post a confirmation comment summarizing actions taken."""
        if not executed_actions:
            return

        # Build confirmation message
        lines = []

        # Check for reply actions first (they become the main message)
        reply_actions = [a for a in executed_actions if a.action_type == CommentAction.REPLY]
        other_actions = [a for a in executed_actions if a.action_type != CommentAction.REPLY]

        if reply_actions:
            # Use the reply text as the main content
            lines.append(reply_actions[0].value)

        if other_actions:
            if lines:
                lines.append("")
                lines.append("**Actions taken:**")
            else:
                lines.append("**Actions taken in response to your comment:**")

            for action in other_actions:
                if action.action_type == CommentAction.ADD_LABEL:
                    lines.append(f"- Added label `{action.value}`")
                elif action.action_type == CommentAction.REMOVE_LABEL:
                    lines.append(f"- Removed label `{action.value}`")
                elif action.action_type == CommentAction.CLOSE_ISSUE:
                    lines.append(f"- Closed issue: {action.value}")

        lines.append("")
        lines.append(f"{config.bot_signature}")

        await self.git.add_comment(issue.number, "\n".join(lines))
