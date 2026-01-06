"""Workflow orchestration and execution engine.

This package provides the core automation engine for managing multi-stage
workflows, including task orchestration, state management, recovery strategies,
and parallel execution capabilities.

Key Components:
    - Orchestrator: Main workflow orchestration engine
    - StateManager: Persistent state management with atomic transactions
    - WorkflowStage: Base class for workflow stages
    - BranchingStrategy: Git branching strategy implementations
    - AdvancedRecovery: Error recovery and retry mechanisms
    - ParallelExecutor: Optimized parallel task execution

Type Definitions:
    - WorkflowState: TypedDict for complete workflow state
    - StageState: TypedDict for individual stage state
    - TaskState: TypedDict for task state within workflows
    - StagesDict: TypedDict for stage collection

Workflow Stages:
    - Planning: Generate development plan from issue
    - Proposal: Create review issue for plan approval
    - Approval: Monitor for approval comments
    - PlanReview: Generate prompts from approved plan
    - Implementation: Execute development tasks
    - Execution: Run individual tasks
    - CodeReview: AI-powered code review
    - PRReview: Pull request review
    - PRFix: Create fix proposals from review
    - FixExecution: Implement approved fixes
    - QA: Build and test
    - Merge: Create and merge pull requests

Example:
    >>> from repo_sapiens.engine import WorkflowOrchestrator
    >>> orchestrator = WorkflowOrchestrator(settings, git, agent, state)
    >>> await orchestrator.process_issue(issue)

    >>> from repo_sapiens.engine.types import WorkflowState
    >>> state: WorkflowState = await state_manager.load_state("plan-123")
"""

from repo_sapiens.engine.types import (
    StagesDict,
    StageState,
    TaskState,
    WorkflowState,
)

__all__ = [
    "StageState",
    "StagesDict",
    "TaskState",
    "WorkflowState",
]
