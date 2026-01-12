"""Review and comment analysis models."""

from enum import Enum

from pydantic import BaseModel, Field


class CommentCategory(str, Enum):
    """Categories for review comments."""

    SIMPLE_FIX = "simple_fix"  # Straightforward code change, execute immediately
    CONTROVERSIAL_FIX = "controversial_fix"  # Requires approval before executing
    QUESTION = "question"  # Needs an answer, no code change
    INFO = "info"  # Informational comment, acknowledge only
    ALREADY_DONE = "already_done"  # Already addressed in code
    WONT_FIX = "wont_fix"  # Valid comment but won't implement


class CommentAnalysis(BaseModel):
    """AI analysis of a single review comment."""

    comment_id: int = Field(..., description="Comment ID in the issue tracker")
    comment_author: str = Field(..., description="Username of comment author")
    comment_body: str = Field(..., description="Full text of the comment")
    comment_created_at: str | None = Field(default=None, description="When comment was created")

    category: CommentCategory = Field(..., description="How to handle this comment")
    reasoning: str = Field(..., description="Why AI categorized it this way")
    proposed_action: str = Field(..., description="What AI plans to do")

    # For fixes
    file_path: str | None = Field(default=None, description="File to modify (if applicable)")
    line_number: int | None = Field(default=None, description="Line number to fix (if applicable)")
    code_snippet: str | None = Field(default=None, description="Current code at location (if applicable)")

    # For questions
    answer: str | None = Field(default=None, description="Answer to question (if applicable)")

    # Execution tracking
    executed: bool = Field(default=False, description="Whether action has been executed")
    execution_result: str | None = Field(default=None, description="Result of executing the action")
    reply_posted: bool = Field(default=False, description="Whether reply comment has been posted")


class ReviewAnalysisResult(BaseModel):
    """Complete analysis of all review comments."""

    pr_number: int = Field(..., description="Pull request number")
    total_comments: int = Field(..., description="Total comments analyzed")
    reviewer_comments: int = Field(..., description="Comments from reviewers/maintainers")

    simple_fixes: list[CommentAnalysis] = Field(default_factory=list, description="Fixes to execute immediately")
    controversial_fixes: list[CommentAnalysis] = Field(default_factory=list, description="Fixes requiring approval")
    questions: list[CommentAnalysis] = Field(default_factory=list, description="Questions to answer")
    info_comments: list[CommentAnalysis] = Field(default_factory=list, description="Informational comments")
    already_done: list[CommentAnalysis] = Field(default_factory=list, description="Already addressed in code")
    wont_fix: list[CommentAnalysis] = Field(default_factory=list, description="Valid but won't implement")

    def get_all_analyses(self) -> list[CommentAnalysis]:
        """Get all comment analyses in one flat list."""
        return (
            self.simple_fixes
            + self.controversial_fixes
            + self.questions
            + self.info_comments
            + self.already_done
            + self.wont_fix
        )

    def has_executable_fixes(self) -> bool:
        """Check if there are any fixes to execute."""
        return len(self.simple_fixes) > 0

    def has_controversial_fixes(self) -> bool:
        """Check if there are fixes needing approval."""
        return len(self.controversial_fixes) > 0
