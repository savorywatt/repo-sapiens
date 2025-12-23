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
    >>> from automation.engine import WorkflowOrchestrator
    >>> orchestrator = WorkflowOrchestrator(settings, git, agent, state)
    >>> await orchestrator.process_issue(issue)
"""
