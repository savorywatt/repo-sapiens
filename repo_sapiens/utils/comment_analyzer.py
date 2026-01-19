"""Comment analyzer for dynamic PR review response.

This module provides AI-powered analysis of pull request review comments,
categorizing them by type (simple fix, controversial change, question, etc.)
to enable automated or semi-automated response workflows.

The analyzer uses an AI agent to classify comments and determine appropriate
actions, which can then be used to drive automated fix applications or
human-in-the-loop review processes.

Key Exports:
    CommentAnalyzer: Main class for analyzing PR review comments.

Example:
    >>> from repo_sapiens.utils.comment_analyzer import CommentAnalyzer
    >>> analyzer = CommentAnalyzer(git_provider, agent_provider)
    >>> result = await analyzer.analyze_comments(pr_number=42, comments=comments)
    >>> for fix in result.simple_fixes:
    ...     print(f"Simple fix needed: {fix.proposed_action}")

Note:
    This module is not thread-safe. Each instance should be used within
    a single async context. The analyzer makes API calls to both the git
    provider (for PR details) and the AI agent (for comment classification).
"""

import json
from typing import Any

import structlog

from repo_sapiens.models.review import CommentAnalysis, CommentCategory, ReviewAnalysisResult
from repo_sapiens.providers.base import AgentProvider, GitProvider

log = structlog.get_logger(__name__)


class CommentAnalyzer:
    """Analyzes PR review comments and categorizes them for action.

    This class coordinates between a git provider (for accessing PR data)
    and an AI agent (for intelligent comment classification) to produce
    structured analysis results that can drive automated workflows.

    The analyzer categorizes comments into:
        - simple_fix: Straightforward code changes (typos, formatting)
        - controversial_fix: Complex changes with trade-offs
        - question: Reviewer questions requiring answers
        - info: Informational comments, no action needed
        - already_done: Concerns already addressed in current code
        - wont_fix: Valid but intentionally not implemented

    Attributes:
        git: Git provider instance for accessing repository data.
        agent: AI agent provider for comment analysis.

    Example:
        >>> analyzer = CommentAnalyzer(git_provider, agent_provider)
        >>> result = await analyzer.analyze_comments(pr_number=42, comments=comments)
        >>> print(f"Found {len(result.simple_fixes)} simple fixes")
        >>> print(f"Found {len(result.questions)} questions to answer")
    """

    def __init__(self, git: GitProvider, agent: AgentProvider) -> None:
        """Initialize the comment analyzer.

        Args:
            git: Git provider for accessing repository data (PRs, comments).
            agent: AI agent provider for analyzing and categorizing comments.

        Example:
            >>> from repo_sapiens.providers.gitea import GiteaProvider
            >>> from repo_sapiens.providers.claude import ClaudeProvider
            >>> git = GiteaProvider(base_url="https://gitea.example.com", token="...")
            >>> agent = ClaudeProvider(api_key="...")
            >>> analyzer = CommentAnalyzer(git, agent)
        """
        self.git = git
        self.agent = agent

    async def is_reviewer_or_maintainer(self, username: str, pr_number: int) -> bool:
        """Check if a user has reviewer or maintainer privileges.

        Determines whether a comment author should be treated as an
        authoritative reviewer whose feedback requires action.

        Args:
            username: The username to check for privileges.
            pr_number: The PR number to check against.

        Returns:
            True if the user has reviewer/maintainer privileges, False otherwise.
            Currently returns True for all users as a permissive default.

        Note:
            The current implementation is permissive and returns True for all
            users. TODO: Implement proper permission checking per provider
            (check write access, maintainer lists, CODEOWNERS, etc.).

        Example:
            >>> is_reviewer = await analyzer.is_reviewer_or_maintainer("alice", 42)
            >>> if is_reviewer:
            ...     print("Alice's feedback should be addressed")
        """
        try:
            # Get PR details
            pr = await self.git.get_pull_request(pr_number)

            # Check if user is PR author (they can review their own PR)
            if pr.author == username:
                return True

            # Check if user is repository owner/maintainer
            # This is provider-specific, but generally:
            # - Check if user has write access to repo
            # - Check if user is in maintainers list
            # For now, we'll be permissive and allow any comment
            # TODO: Implement proper permission checking per provider

            return True  # Allow all for now

        except Exception as e:
            log.warning("reviewer_check_failed", username=username, error=str(e))
            return False

    async def analyze_comments(
        self,
        pr_number: int,
        comments: list[Any],
    ) -> ReviewAnalysisResult:
        """Analyze all comments on a PR and categorize them.

        Processes a list of comments, filters for reviewer/maintainer comments,
        and uses AI to categorize each comment into actionable categories.

        Args:
            pr_number: The PR number being analyzed.
            comments: List of comment objects from the git provider. Each comment
                should have 'author', 'body', 'id', and optionally 'created_at'
                attributes or dict keys.

        Returns:
            A ReviewAnalysisResult containing categorized comments:
                - simple_fixes: Comments requesting straightforward changes
                - controversial_fixes: Comments requesting complex changes
                - questions: Questions from reviewers
                - info_comments: Informational/praise comments
                - already_done: Issues already addressed
                - wont_fix: Intentionally declined suggestions

        Raises:
            No exceptions are raised; individual comment analysis failures
            are logged and skipped.

        Example:
            >>> comments = await git.get_review_comments(pr_number=42)
            >>> result = await analyzer.analyze_comments(42, comments)
            >>> print(f"Total: {result.total_comments}")
            >>> print(f"From reviewers: {result.reviewer_comments}")
            >>> for fix in result.simple_fixes:
            ...     print(f"Fix: {fix.proposed_action} in {fix.file_path}")
        """
        log.info("analyzing_comments", pr_number=pr_number, total=len(comments))

        # Filter for reviewer/maintainer comments
        reviewer_comments = []
        for comment in comments:
            author = comment.author if hasattr(comment, "author") else comment.get("author", "unknown")
            if await self.is_reviewer_or_maintainer(author, pr_number):
                reviewer_comments.append(comment)

        log.info(
            "filtered_comments",
            pr_number=pr_number,
            total=len(comments),
            reviewers=len(reviewer_comments),
        )

        # Analyze each comment with AI
        analyses = []
        for comment in reviewer_comments:
            analysis = await self._analyze_single_comment(comment, pr_number)
            if analysis:
                analyses.append(analysis)

        # Organize by category
        result = ReviewAnalysisResult(
            pr_number=pr_number,
            total_comments=len(comments),
            reviewer_comments=len(reviewer_comments),
        )

        for analysis in analyses:
            if analysis.category == CommentCategory.SIMPLE_FIX:
                result.simple_fixes.append(analysis)
            elif analysis.category == CommentCategory.CONTROVERSIAL_FIX:
                result.controversial_fixes.append(analysis)
            elif analysis.category == CommentCategory.QUESTION:
                result.questions.append(analysis)
            elif analysis.category == CommentCategory.INFO:
                result.info_comments.append(analysis)
            elif analysis.category == CommentCategory.ALREADY_DONE:
                result.already_done.append(analysis)
            elif analysis.category == CommentCategory.WONT_FIX:
                result.wont_fix.append(analysis)

        log.info(
            "analysis_complete",
            pr_number=pr_number,
            simple_fixes=len(result.simple_fixes),
            controversial=len(result.controversial_fixes),
            questions=len(result.questions),
        )

        return result

    async def _analyze_single_comment(
        self,
        comment: Any,
        pr_number: int,
    ) -> CommentAnalysis | None:
        """Analyze a single comment using AI classification.

        Sends the comment to the AI agent with a structured prompt to determine
        the comment category and appropriate action.

        Args:
            comment: A comment object with 'id', 'author', 'body', and optionally
                'created_at' attributes or dict keys.
            pr_number: The PR number this comment belongs to.

        Returns:
            A CommentAnalysis object containing the categorization and proposed
            action, or None if analysis failed (e.g., API error, parse failure).

        Note:
            This is a private method. Use analyze_comments() for the public API.
            Failures are logged but not raised to allow batch processing to
            continue despite individual failures.
        """
        comment_id = comment.id if hasattr(comment, "id") else comment.get("id")
        comment_author = comment.author if hasattr(comment, "author") else comment.get("author", "unknown")
        comment_body = comment.body if hasattr(comment, "body") else comment.get("body", "")
        comment_created = comment.created_at if hasattr(comment, "created_at") else comment.get("created_at", None)

        log.debug("analyzing_comment", comment_id=comment_id, author=comment_author)

        # Build AI prompt for analysis
        prompt = f"""You are analyzing a code review comment to determine how to respond.

**PR Number**: #{pr_number}
**Comment Author**: {comment_author}
**Comment**:
{comment_body}

**Your Task**:
Analyze this comment and determine:
1. What category does it fall into?
2. What action should be taken?
3. If it's a fix, is it simple or controversial?

**Categories**:
- **simple_fix**: A straightforward code change (typo, formatting, simple refactor, adding comments, etc.)
- **controversial_fix**: A complex change that affects logic, architecture, or has trade-offs
- **question**: The reviewer is asking a question about the code
- **info**: Just an informational comment, no action needed
- **already_done**: The concern is already addressed in the current code
- **wont_fix**: Valid comment but we choose not to implement (explain why)

**Guidelines for categorization**:
- Simple fixes: typos, formatting, add/remove comments, rename variables, add logging, simple refactors
- Controversial fixes: algorithm changes, architecture changes, security implications, performance trade-offs

**Response Format** (JSON):
{{
    "category": "simple_fix|controversial_fix|question|info|already_done|wont_fix",
    "reasoning": "Why you categorized it this way (1-2 sentences)",
    "proposed_action": "What you plan to do (be specific)",
    "file_path": "path/to/file.py (if fixing code, otherwise null)",
    "line_number": 123 (if specific line mentioned, otherwise null),
    "answer": "Answer to question (if category is question, otherwise null)"
}}

Respond ONLY with the JSON, no other text.
"""

        try:
            # Execute AI analysis
            result = await self.agent.execute_prompt(
                prompt,
                context={"pr_number": pr_number, "comment_id": comment_id},
                task_id=f"analyze-comment-{comment_id}",
            )

            if not result.get("success"):
                log.error("comment_analysis_failed", comment_id=comment_id, error=result.get("error"))
                return None

            # Parse AI response as JSON
            ai_output = result.get("output", "")
            analysis_data = self._parse_ai_response(ai_output)

            if not analysis_data:
                log.error("failed_to_parse_ai_response", comment_id=comment_id)
                return None

            # Create CommentAnalysis object
            analysis = CommentAnalysis(
                comment_id=comment_id,
                comment_author=comment_author,
                comment_body=comment_body,
                comment_created_at=comment_created,
                category=CommentCategory(analysis_data["category"]),
                reasoning=analysis_data["reasoning"],
                proposed_action=analysis_data["proposed_action"],
                file_path=analysis_data.get("file_path"),
                line_number=analysis_data.get("line_number"),
                answer=analysis_data.get("answer"),
            )

            return analysis

        except Exception as e:
            log.error("comment_analysis_exception", comment_id=comment_id, error=str(e), exc_info=True)
            return None

    def _parse_ai_response(self, output: str) -> dict[str, Any] | None:
        """Parse JSON response from AI agent.

        Extracts JSON from the AI output, handling cases where the AI may
        include explanatory text before or after the JSON object.

        Args:
            output: Raw text output from the AI agent.

        Returns:
            Parsed dictionary containing the analysis fields, or None if
            parsing failed.

        Note:
            This method uses regex to find JSON objects within the text,
            allowing for some flexibility in AI output formatting.
        """
        try:
            # Try to find JSON in output (AI might add text before/after)
            import re

            json_match = re.search(r"\{.*\}", output, re.DOTALL)
            parsed: dict[str, Any]
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
            else:
                # Try parsing entire output as JSON
                parsed = json.loads(output)
            return parsed

        except json.JSONDecodeError as e:
            log.error("json_parse_failed", error=str(e), output=output[:200])
            return None
