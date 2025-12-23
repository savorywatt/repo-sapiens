"""Claude AI agent provider implementation."""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from automation.models.domain import Issue, Plan, Review, Task, TaskResult
from automation.providers.base import AgentProvider
from automation.utils.helpers import slugify

log = structlog.get_logger(__name__)


class ClaudeLocalProvider(AgentProvider):
    """Claude Code local CLI implementation.

    This provider executes tasks using the Claude Code CLI tool,
    which provides local code generation and review capabilities.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4.5",
        workspace: Path = Path.cwd(),
    ):
        """Initialize Claude provider.

        Args:
            model: Claude model to use
            workspace: Workspace directory for code operations
        """
        self.model = model
        self.workspace = workspace

    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue.

        Args:
            issue: Issue to plan for

        Returns:
            Generated Plan object
        """
        log.info("generating_plan", issue_number=issue.number)

        prompt = self._build_planning_prompt(issue)

        # Execute Claude to generate plan
        output = await self._run_claude(prompt, "main")

        # Parse plan from output
        plan_content = self._extract_plan_content(output)

        # Create plan object
        plan_id = str(issue.number)
        plan = Plan(
            id=plan_id,
            title=issue.title,
            description=issue.body,
            tasks=[],  # Will be populated by generate_prompts
            file_path=f"plans/{plan_id}-{slugify(issue.title)}.md",
            created_at=datetime.now(),
            issue_number=issue.number,
        )

        log.info("plan_generated", plan_id=plan_id, length=len(plan_content))
        return plan

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        Args:
            plan: Plan to break down

        Returns:
            List of Task objects with dependencies
        """
        log.info("generating_prompts", plan_id=plan.id)

        # Read plan file to extract tasks
        if not plan.file_path:
            raise ValueError("Plan must have file_path set")

        plan_path = self.workspace / plan.file_path
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_path}")

        with open(plan_path) as f:
            plan_content = f.read()

        # Extract tasks from plan markdown
        tasks = self._extract_tasks_from_plan(plan_content, plan.id)

        log.info("prompts_generated", plan_id=plan.id, task_count=len(tasks))
        return tasks

    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        """Execute a development task.

        Args:
            task: Task to execute
            context: Execution context with workspace, branch, dependencies, etc.

        Returns:
            TaskResult with execution details
        """
        log.info("executing_task", task_id=task.id)

        start_time = time.time()

        try:
            # Build task execution prompt
            prompt = self._build_task_prompt(task, context)

            # Get branch from context
            branch = context.get("branch", "main")

            # Execute Claude Code
            output = await self._run_claude(prompt, branch)

            # Parse execution output
            commits = self._extract_commits(output)
            files_changed = self._extract_files_changed(output)

            execution_time = time.time() - start_time

            result = TaskResult(
                success=True,
                branch=branch,
                commits=commits,
                files_changed=files_changed,
                execution_time=execution_time,
                output=output,
            )

            log.info(
                "task_executed",
                task_id=task.id,
                commits=len(commits),
                files=len(files_changed),
            )

            return result

        except Exception as e:
            log.error("task_execution_failed", task_id=task.id, error=str(e))
            return TaskResult(
                success=False,
                branch=context.get("branch", ""),
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def review_code(self, diff: str, context: dict) -> Review:
        """Review code changes.

        Args:
            diff: Code diff to review
            context: Review context (plan, task, etc.)

        Returns:
            Review object with approval status and comments
        """
        log.info("reviewing_code", diff_size=len(diff))

        prompt = self._build_review_prompt(diff, context)

        # Execute Claude for review
        output = await self._run_claude(prompt, "main")

        # Parse review output (expect JSON response)
        try:
            review_data = self._parse_review_output(output)

            review = Review(
                approved=review_data.get("approved", False),
                comments=review_data.get("comments", []),
                issues_found=review_data.get("issues_found", []),
                suggestions=review_data.get("suggestions", []),
                confidence_score=review_data.get("confidence_score", 0.5),
            )

            log.info(
                "code_reviewed",
                approved=review.approved,
                confidence=review.confidence_score,
            )

            return review

        except Exception as e:
            log.error("review_parsing_failed", error=str(e))
            # Return conservative review on parse failure
            return Review(
                approved=False,
                comments=["Failed to parse review output"],
                confidence_score=0.0,
            )

    async def resolve_conflict(self, conflict_info: dict) -> str:
        """Resolve merge conflict.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolved file content
        """
        log.info("resolving_conflict", file=conflict_info.get("file"))

        prompt = self._build_conflict_resolution_prompt(conflict_info)

        # Execute Claude to resolve conflict
        output = await self._run_claude(prompt, "main")

        # Extract resolved content
        resolved_content = self._extract_resolved_content(output)

        log.info("conflict_resolved", file=conflict_info.get("file"))
        return resolved_content

    async def _run_claude(self, prompt: str, branch: str) -> str:
        """Execute Claude CLI with prompt.

        Args:
            prompt: Prompt to send to Claude
            branch: Git branch to operate on

        Returns:
            Claude's output
        """
        # Build Claude Code command
        # Note: Actual command structure depends on Claude Code CLI interface
        cmd = [
            "claude",  # Assuming 'claude' is the CLI command
            "--model",
            self.model,
            "--branch",
            branch,
        ]

        log.debug("running_claude", command=" ".join(cmd), branch=branch)

        try:
            # Run Claude Code CLI
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            stdout, stderr = await process.communicate(input=prompt.encode())

            if process.returncode != 0:
                error_msg = stderr.decode()
                log.error("claude_execution_failed", error=error_msg)
                raise RuntimeError(f"Claude execution failed: {error_msg}")

            output = stdout.decode()
            log.debug("claude_completed", output_length=len(output))

            return output

        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI not found. Please install Claude Code CLI.")

    def _build_planning_prompt(self, issue: Issue) -> str:
        """Build prompt for plan generation.

        Args:
            issue: Issue to plan for

        Returns:
            Prompt string
        """
        return f"""You are tasked with creating a detailed development plan for the following issue:

Title: {issue.title}

Description:
{issue.body}

Please create a comprehensive plan that includes:
1. Overview of the solution approach
2. Breakdown into specific implementation tasks
3. Dependencies between tasks
4. Acceptance criteria
5. Testing strategy

Format the plan as markdown with clear task sections.
Each task should have:
- Task ID (e.g., Task 1, Task 2)
- Clear title
- Detailed description
- Dependencies (if any)

Example format:
## Overview
[Solution approach]

## Tasks

### Task 1: [Title]
[Description]

### Task 2: [Title]
Dependencies: Task 1
[Description]

Begin the plan now:
"""

    def _build_task_prompt(self, task: Task, context: dict) -> str:
        """Build prompt for task execution.

        Args:
            task: Task to execute
            context: Execution context

        Returns:
            Prompt string
        """
        plan_context = context.get("plan_content", "")
        dependencies_info = context.get("dependencies_completed", [])

        prompt = f"""Execute the following development task:

Task ID: {task.id}
Title: {task.title}

Description:
{task.description}

Plan Context:
{plan_context}

"""

        if dependencies_info:
            prompt += """
Completed Dependencies:
"""
            for dep in dependencies_info:
                prompt += f"- {dep}\n"

        prompt += """
Please implement this task completely, including:
1. All necessary code changes
2. Tests (if applicable)
3. Documentation updates

Commit your changes with descriptive commit messages.
"""

        return prompt

    def _build_review_prompt(self, diff: str, context: dict) -> str:
        """Build prompt for code review.

        Args:
            diff: Code diff
            context: Review context

        Returns:
            Prompt string
        """
        task_info = context.get("task", {})

        return f"""Review the following code changes:

Task: {task_info.get('title', 'Unknown')}

Diff:
{diff}

Please review the code and provide feedback in JSON format:
{{
    "approved": true/false,
    "confidence_score": 0.0-1.0,
    "comments": ["overall assessment"],
    "issues_found": ["list of issues"],
    "suggestions": ["list of improvements"]
}}

Focus on:
1. Code quality and best practices
2. Completeness of implementation
3. Test coverage
4. Potential bugs or issues
5. Security concerns

Provide your review in JSON format:
"""

    def _build_conflict_resolution_prompt(self, conflict_info: dict) -> str:
        """Build prompt for conflict resolution.

        Args:
            conflict_info: Conflict information

        Returns:
            Prompt string
        """
        return f"""Resolve the following merge conflict:

File: {conflict_info.get('file')}

Conflict:
{conflict_info.get('conflict_content')}

Base version:
{conflict_info.get('base_content', '')}

Please provide the resolved file content, keeping the best parts from both versions
and ensuring the code remains functional.

Resolved content:
"""

    def _extract_plan_content(self, output: str) -> str:
        """Extract plan content from Claude output.

        Args:
            output: Claude output

        Returns:
            Plan content
        """
        # Simple extraction - in practice, may need more sophisticated parsing
        return output.strip()

    def _extract_tasks_from_plan(self, plan_content: str, plan_id: str) -> list[Task]:
        """Parse tasks from plan markdown content.

        Args:
            plan_content: Plan markdown content
            plan_id: Plan identifier

        Returns:
            List of Task objects
        """
        tasks = []

        # Look for task sections (e.g., ### Task 1: ...)
        task_pattern = r"###\s+Task\s+(\d+):\s+(.+?)\n(.*?)(?=###\s+Task\s+\d+:|$)"
        matches = re.finditer(task_pattern, plan_content, re.DOTALL)

        for match in matches:
            task_num = int(match.group(1))
            title = match.group(2).strip()
            description = match.group(3).strip()

            # Look for dependency markers
            deps = []
            dep_pattern = r"(?:Dependencies?|Depends on):\s*Task\s*(\d+(?:,\s*\d+)*)"
            dep_match = re.search(dep_pattern, description, re.IGNORECASE)
            if dep_match:
                dep_nums = re.findall(r"\d+", dep_match.group(1))
                deps = [f"task-{num}" for num in dep_nums]

            task = Task(
                id=f"task-{task_num}",
                title=title,
                description=description,
                dependencies=deps,
                plan_id=plan_id,
            )

            tasks.append(task)

        log.info("tasks_extracted", count=len(tasks))
        return tasks

    def _extract_commits(self, output: str) -> list[str]:
        """Extract commit SHAs from Claude output.

        Args:
            output: Claude output

        Returns:
            List of commit SHAs
        """
        # Look for commit SHA patterns (40-character hex strings)
        sha_pattern = r"\b([a-f0-9]{40})\b"
        commits = re.findall(sha_pattern, output)
        return commits

    def _extract_files_changed(self, output: str) -> list[str]:
        """Extract list of files changed from Claude output.

        Args:
            output: Claude output

        Returns:
            List of file paths
        """
        # Look for file path patterns
        # This is a simple heuristic - may need refinement
        file_pattern = r"(?:modified|created|updated):\s+([^\s]+)"
        files = re.findall(file_pattern, output, re.IGNORECASE)
        return files

    def _parse_review_output(self, output: str) -> dict[str, Any]:
        """Parse review output as JSON.

        Args:
            output: Claude output

        Returns:
            Parsed review data
        """
        # Try to find JSON in output
        json_pattern = r"\{.*\}"
        match = re.search(json_pattern, output, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: return default review structure
        return {
            "approved": False,
            "confidence_score": 0.0,
            "comments": [output[:200] if output else "No review generated"],
            "issues_found": [],
            "suggestions": [],
        }

    def _extract_resolved_content(self, output: str) -> str:
        """Extract resolved file content from output.

        Args:
            output: Claude output

        Returns:
            Resolved content
        """
        # Look for code blocks
        code_block_pattern = r"```(?:[\w]+)?\n(.*?)```"
        match = re.search(code_block_pattern, output, re.DOTALL)

        if match:
            return match.group(1).strip()

        # If no code block, return entire output
        return output.strip()
