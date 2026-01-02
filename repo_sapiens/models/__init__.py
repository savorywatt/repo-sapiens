"""Core domain models for the automation system.

This package defines all data models representing the core business entities
of the automation platform, including issues, tasks, plans, and reviews.

Key Models:
    - Issue: Git repository issue/task
    - Task: Individual development task from a plan
    - Plan: Complete development plan
    - PullRequest: Git pull request
    - Review: Code review result
    - Comment: Issue/PR comment
    - Branch: Git branch

Enums:
    - IssueState: Issue state (open, closed)
    - TaskStatus: Task execution status (pending, in progress, completed, etc.)

Example:
    >>> from repo_sapiens.models import Issue, Plan, Task
    >>> issue = Issue(number=42, title="Add feature X", ...)
    >>> plan = Plan(id="plan-42", title="Implementation Plan", tasks=[...])
    >>> task = Task(id="task-1", title="Implement API", ...)
"""
