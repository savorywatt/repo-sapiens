"""
Domain models for the automation system.

This module contains all data classes and enums representing the core business
entities of the automation system, including issues, tasks, plans, and reviews.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueState(str, Enum):
    """Issue state."""

    OPEN = "open"
    CLOSED = "closed"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CODE_REVIEW = "code_review"
    MERGE_READY = "merge_ready"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Issue:
    """Represents a Git issue."""

    id: int
    number: int
    title: str
    body: str
    state: IssueState
    labels: List[str]
    created_at: datetime
    updated_at: datetime
    author: str
    url: str


@dataclass
class Comment:
    """Represents an issue comment."""

    id: int
    body: str
    author: str
    created_at: datetime


@dataclass
class Branch:
    """Represents a Git branch."""

    name: str
    sha: str
    protected: bool = False


@dataclass
class PullRequest:
    """Represents a pull request."""

    id: int
    number: int
    title: str
    body: str
    head: str
    base: str
    state: str
    url: str
    created_at: datetime
    mergeable: bool = True
    merged: bool = False


@dataclass
class Task:
    """Represents a single development task from a plan."""

    id: str
    prompt_issue_id: int
    title: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of executing a task."""

    success: bool
    branch: Optional[str] = None
    commits: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class Plan:
    """Represents a development plan generated from an issue."""

    id: str
    title: str
    description: str
    tasks: List[Task]
    file_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Review:
    """Code review result."""

    approved: bool
    comments: List[str] = field(default_factory=list)
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
