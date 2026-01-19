"""Review and comment analysis models.

This module defines Pydantic models for analyzing and categorizing pull request
review comments. The AI system uses these models to determine how to respond
to reviewer feedback - whether to make immediate fixes, ask for clarification,
or flag items for human approval.

Example:
    Analyzing a PR's review comments::

        analysis = ReviewAnalysisResult(
            pr_number=42,
            total_comments=5,
            reviewer_comments=3,
            simple_fixes=[
                CommentAnalysis(
                    comment_id=123,
                    comment_author="reviewer",
                    comment_body="Fix the typo on line 15",
                    category=CommentCategory.SIMPLE_FIX,
                    reasoning="Clear, non-controversial change",
                    proposed_action="Replace 'recieve' with 'receive'",
                    file_path="src/utils.py",
                    line_number=15
                )
            ]
        )
"""

from enum import Enum

from pydantic import BaseModel, Field


class CommentCategory(str, Enum):
    """Categories for review comments determining how to handle them.

    The AI analyzes each review comment and assigns it to one of these
    categories, which determines the automated response:

    - SIMPLE_FIX: Execute immediately without approval
    - CONTROVERSIAL_FIX: Requires human approval before execution
    - QUESTION: Generate and post an answer
    - INFO: Acknowledge without action
    - ALREADY_DONE: Note that it's already addressed
    - WONT_FIX: Explain why the suggestion won't be implemented

    Example:
        Routing comments by category::

            for analysis in result.get_all_analyses():
                if analysis.category == CommentCategory.SIMPLE_FIX:
                    await execute_fix(analysis)
                elif analysis.category == CommentCategory.QUESTION:
                    await post_answer(analysis)
    """

    SIMPLE_FIX = "simple_fix"
    """Straightforward code change that can be executed immediately.

    Examples: typo fixes, formatting changes, adding a missing docstring.
    These changes are non-controversial and unlikely to break anything.
    """

    CONTROVERSIAL_FIX = "controversial_fix"
    """Change that requires human approval before executing.

    Examples: architectural changes, API modifications, security-related changes.
    The AI will describe the proposed change and wait for approval.
    """

    QUESTION = "question"
    """Reviewer is asking a question that needs an answer.

    The AI will generate an answer explaining the code, design decision,
    or providing requested clarification. No code changes are made.
    """

    INFO = "info"
    """Informational comment that only needs acknowledgment.

    Examples: "Nice work!", "FYI this is similar to what we did in PR #30".
    The AI acknowledges the comment without taking action.
    """

    ALREADY_DONE = "already_done"
    """The requested change is already addressed in the code.

    The AI will reply pointing to where the change was already made,
    possibly with a code snippet or line reference.
    """

    WONT_FIX = "wont_fix"
    """Valid suggestion that won't be implemented.

    The AI will explain why the suggestion isn't being implemented,
    such as performance tradeoffs, scope limitations, or design constraints.
    """


class CommentAnalysis(BaseModel):
    """AI analysis of a single review comment.

    Captures the original comment, the AI's categorization and reasoning,
    and the proposed response. Also tracks execution state for fixes.

    Example:
        Analyzing a review comment::

            analysis = CommentAnalysis(
                comment_id=456,
                comment_author="senior_dev",
                comment_body="This function is too long, consider splitting it",
                category=CommentCategory.CONTROVERSIAL_FIX,
                reasoning="Refactoring requires architectural decision",
                proposed_action="Split into parse_input() and validate_input()",
                file_path="src/parser.py",
                line_number=42,
                code_snippet="def process_input(data):\\n    # 200 lines..."
            )
    """

    # Original comment data
    comment_id: int = Field(
        ...,
        description="Unique identifier for the comment in the git provider. "
        "Used for posting reply comments and tracking state.",
    )

    comment_author: str = Field(
        ...,
        description="Username of the reviewer who posted the comment. "
        "Used to identify maintainers vs. regular contributors.",
    )

    comment_body: str = Field(
        ...,
        description="Full text of the review comment in markdown format. "
        "This is what the AI analyzes to determine the category and response.",
    )

    comment_created_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when the comment was posted. " "Used for ordering comments chronologically.",
    )

    # AI analysis results
    category: CommentCategory = Field(
        ...,
        description="How the AI categorized this comment. "
        "Determines the automated response (fix, answer, acknowledge, etc.).",
    )

    reasoning: str = Field(
        ...,
        description="AI's explanation of why it chose this category. "
        "Helps humans understand and audit the AI's decision-making.",
    )

    proposed_action: str = Field(
        ...,
        description="Description of what the AI plans to do in response. "
        "For fixes: describes the code change. For questions: summarizes the answer.",
    )

    # Location information (for fixes)
    file_path: str | None = Field(
        default=None,
        description="Path to the file to modify, relative to repo root. "
        "Only populated for SIMPLE_FIX and CONTROVERSIAL_FIX categories.",
    )

    line_number: int | None = Field(
        default=None,
        description="Line number where the change should be made. "
        "May be None if the fix spans multiple lines or is at file level.",
    )

    code_snippet: str | None = Field(
        default=None,
        description="Current code at the location for context. " "Helps verify the fix is applied to the right place.",
    )

    # Response content (for questions)
    answer: str | None = Field(
        default=None,
        description="Generated answer for QUESTION category comments. "
        "This text will be posted as a reply to the reviewer.",
    )

    # Execution tracking
    executed: bool = Field(
        default=False,
        description="Whether the proposed action has been executed. "
        "For fixes: code was modified. For questions: answer was posted.",
    )

    execution_result: str | None = Field(
        default=None,
        description="Result message from executing the action. " "Contains success confirmation or error details.",
    )

    reply_posted: bool = Field(
        default=False,
        description="Whether a reply comment has been posted to the reviewer. " "Prevents duplicate replies on retry.",
    )


class ReviewAnalysisResult(BaseModel):
    """Complete analysis of all review comments on a pull request.

    Organizes analyzed comments by category for easy processing.
    Provides helper methods to check for pending work.

    Example:
        Processing review analysis::

            result = await analyze_pr_comments(pr_number=42)

            # Execute simple fixes immediately
            for fix in result.simple_fixes:
                await execute_fix(fix)

            # Queue controversial fixes for approval
            if result.has_controversial_fixes():
                await request_approval(result.controversial_fixes)

            # Post answers to questions
            for question in result.questions:
                await post_reply(question.comment_id, question.answer)
    """

    pr_number: int = Field(
        ...,
        description="Pull request number being analyzed. " "Used for API calls and logging.",
    )

    total_comments: int = Field(
        ...,
        description="Total number of comments analyzed, including bot comments " "and the PR author's own comments.",
    )

    reviewer_comments: int = Field(
        ...,
        description="Number of comments from reviewers and maintainers. "
        "Excludes bot comments and the PR author's responses.",
    )

    # Comments grouped by category
    simple_fixes: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Fixes that can be executed immediately without approval. "
        "Typically typos, formatting, and other non-controversial changes.",
    )

    controversial_fixes: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Fixes that require human approval before execution. "
        "Includes architectural changes, API modifications, etc.",
    )

    questions: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Questions from reviewers that need answers. "
        "The AI generates answers to be posted as reply comments.",
    )

    info_comments: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Informational comments requiring only acknowledgment. "
        "Examples: praise, FYI notes, general observations.",
    )

    already_done: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Comments requesting changes that are already implemented. "
        "The AI will point to where the change exists.",
    )

    wont_fix: list[CommentAnalysis] = Field(
        default_factory=list,
        description="Valid suggestions that won't be implemented. "
        "The AI will explain the reasoning for not making the change.",
    )

    def get_all_analyses(self) -> list[CommentAnalysis]:
        """Get all comment analyses in a single flat list.

        Returns:
            List of all CommentAnalysis objects across all categories.
            Order: simple_fixes, controversial_fixes, questions, info_comments,
            already_done, wont_fix.

        Example:
            Iterating over all comments::

                for analysis in result.get_all_analyses():
                    print(f"{analysis.comment_author}: {analysis.category.value}")
        """
        return (
            self.simple_fixes
            + self.controversial_fixes
            + self.questions
            + self.info_comments
            + self.already_done
            + self.wont_fix
        )

    def has_executable_fixes(self) -> bool:
        """Check if there are simple fixes ready to execute.

        Returns:
            True if simple_fixes list is non-empty.

        Example:
            Conditional execution::

                if result.has_executable_fixes():
                    for fix in result.simple_fixes:
                        await apply_fix(fix)
        """
        return len(self.simple_fixes) > 0

    def has_controversial_fixes(self) -> bool:
        """Check if there are fixes needing human approval.

        Returns:
            True if controversial_fixes list is non-empty.

        Example:
            Requesting approval::

                if result.has_controversial_fixes():
                    await post_approval_request(result.controversial_fixes)
        """
        return len(self.controversial_fixes) > 0
