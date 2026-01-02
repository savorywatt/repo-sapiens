"""Workflow stage implementations for the automation engine.

This package provides all workflow stages that compose the automation pipeline.
Each stage handles a specific phase of the development workflow, from planning
through merge.

Available Stages:
    - ApprovalStage: Monitor for plan approval comments
    - CodeReviewStage: Perform AI-powered code review
    - ExecutionStage: Execute individual development tasks
    - FixExecutionStage: Implement approved fixes from review
    - ImplementationStage: Execute development tasks from plan
    - MergeStage: Create and merge pull requests
    - PlanReviewStage: Generate prompts from approved plan
    - PlanningStage: Generate development plan from issue
    - ProposalStage: Create review issue for plan approval
    - QAStage: Build and test implementation
    - PRFixStage: Create fix proposals from review comments
    - PRReviewStage: Review pull requests

Each stage inherits from WorkflowStage and implements the stage-specific logic.

Example:
    >>> from repo_sapiens.engine.stages import PlanningStage
    >>> stage = PlanningStage(agent, git, settings)
    >>> result = await stage.execute(issue, context)
"""
