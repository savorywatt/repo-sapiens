"""External agent provider that runs Claude Code or Goose as CLI tools."""

import asyncio
import os
from typing import Any

import structlog

from repo_sapiens.models.domain import Issue, Plan, Review, Task, TaskResult
from repo_sapiens.providers.base import AgentProvider

log = structlog.get_logger(__name__)


class ExternalAgentProvider(AgentProvider):
    """Agent provider that executes prompts using external CLI tools (Claude Code or Goose)."""

    def __init__(
        self,
        agent_type: str = "claude",
        model: str = "claude-sonnet-4.5",
        working_dir: str | None = None,
        qa_handler: Any | None = None,
        goose_config: dict[str, Any] | None = None,
    ):
        """Initialize external agent provider.

        Args:
            agent_type: Type of agent CLI ("claude" or "goose")
            model: Model to use
            working_dir: Working directory for agent execution
            qa_handler: Interactive Q&A handler for agent questions
            goose_config: Goose-specific configuration (toolkit, temperature, etc.)
        """
        self.agent_type = agent_type
        self.model = model
        self.working_dir = working_dir or os.getcwd()
        self.qa_handler = qa_handler
        self.goose_config = goose_config or {}
        self.current_issue_number: int | None = None

    async def connect(self) -> None:
        """Check if the agent CLI is available."""
        cmd = "claude" if self.agent_type == "claude" else "goose"

        try:
            result = await asyncio.create_subprocess_exec(
                cmd,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            if result.returncode == 0:
                log.info("agent_cli_available", agent=self.agent_type)
            else:
                log.warning("agent_cli_check_failed", agent=self.agent_type, code=result.returncode)
        except FileNotFoundError as e:
            log.error("agent_cli_not_found", agent=self.agent_type)
            raise RuntimeError(f"{cmd} CLI not found in PATH") from e

    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt using the external agent CLI.

        Args:
            prompt: The prompt to execute
            context: Additional context (files, dependencies, etc.)
            task_id: Unique task identifier

        Returns:
            Dict with execution results:
                - success: bool
                - output: str (agent output)
                - files_changed: List[str]
                - error: Optional[str]
        """
        log.info("executing_prompt", agent=self.agent_type, task_id=task_id)

        try:
            if self.agent_type == "claude":
                result = await self._execute_claude(prompt, context, task_id)
            else:
                result = await self._execute_goose(prompt, context, task_id)

            log.info("prompt_executed", task_id=task_id, success=result["success"])
            return result

        except Exception as e:
            log.error("prompt_execution_failed", task_id=task_id, error=str(e))
            return {
                "success": False,
                "output": "",
                "files_changed": [],
                "error": str(e),
            }

    async def _execute_claude(
        self,
        prompt: str,
        context: dict[str, Any] | None,
        task_id: str | None,
    ) -> dict[str, Any]:
        """Execute prompt using Claude Code CLI.

        Claude Code runs in the current directory and modifies files directly.
        """
        # Execute Claude Code with the prompt in non-interactive mode
        # Using --print for non-interactive output
        # Using --dangerously-skip-permissions to skip permission dialogs
        # For large prompts, pass via stdin to avoid "Argument list too long" error
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]

        log.debug("running_claude", cwd=self.working_dir, prompt_length=len(prompt))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.working_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=prompt.encode("utf-8"))

        success = process.returncode == 0
        output = stdout.decode("utf-8") if stdout else ""
        error_output = stderr.decode("utf-8") if stderr else ""

        # Try to detect which files were changed
        # This is a simple heuristic - in practice you might use git diff
        files_changed = self._detect_changed_files(output)

        log.info(
            "claude_execution_complete",
            success=success,
            output_length=len(output),
            error_length=len(error_output),
        )

        return {
            "success": success,
            "output": output,
            "files_changed": files_changed,
            "error": error_output if not success else None,
        }

    async def _execute_goose(
        self,
        prompt: str,
        context: dict[str, Any] | None,
        task_id: str | None,
    ) -> dict[str, Any]:
        """Execute prompt using Goose CLI.

        Goose runs in the current directory and modifies files directly.
        Uses 'goose session start' to run a one-shot session.
        """
        # Build Goose command with configuration options
        cmd = ["goose", "session", "start"]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        # Add toolkit
        toolkit = self.goose_config.get("toolkit", "default")
        cmd.extend(["--toolkit", toolkit])

        # Add temperature if specified
        if "temperature" in self.goose_config:
            temp = self.goose_config["temperature"]
            cmd.extend(["--temperature", str(temp)])

        # Add LLM provider if specified
        if "llm_provider" in self.goose_config:
            provider = self.goose_config["llm_provider"]
            cmd.extend(["--provider", provider])

        # Pass prompt via stdin for large prompts
        log.debug(
            "running_goose",
            cmd=" ".join(cmd),
            cwd=self.working_dir,
            prompt_length=len(prompt),
            config=self.goose_config,
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.working_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=prompt.encode("utf-8"))

        success = process.returncode == 0
        output = stdout.decode("utf-8") if stdout else ""
        error_output = stderr.decode("utf-8") if stderr else ""

        files_changed = self._detect_changed_files(output)

        log.info(
            "goose_execution_complete",
            success=success,
            output_length=len(output),
            error_length=len(error_output),
        )

        return {
            "success": success,
            "output": output,
            "files_changed": files_changed,
            "error": error_output if not success else None,
        }

    def _detect_changed_files(self, output: str) -> list[str]:
        """Detect which files were changed from agent output.

        This is a heuristic - looks for common patterns in output.
        Better approach: use git diff before/after.
        """
        files = []

        # Look for common file operation indicators in output
        patterns = [
            "Created file:",
            "Modified file:",
            "Updated file:",
            "Writing to:",
            "Saved:",
        ]

        for line in output.split("\n"):
            for pattern in patterns:
                if pattern in line:
                    # Extract filename after the pattern
                    parts = line.split(pattern)
                    if len(parts) > 1:
                        filename = parts[1].strip().split()[0]
                        if filename:
                            files.append(filename)

        return files

    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate development plan from issue."""
        prompt = f"""Generate a development plan for the following issue:

Title: {issue.title}
Description:
{issue.body}

Please create a detailed plan with specific, actionable tasks.

IMPORTANT: Format your response EXACTLY like this:

# Overview
[Brief overview of the solution]

# Tasks

## 1. Task Title Here
[Detailed description of what needs to be done for this task]

## 2. Another Task Title
[Description of this task]

## 3. Final Task Title
[Description]

Make each task specific and actionable. Include 3-10 tasks that break down the work.
"""

        result = await self.execute_prompt(prompt)
        output = result.get("output", "")

        # Parse tasks from markdown output
        tasks = self._parse_tasks_from_markdown(output)

        plan = Plan(
            id=str(issue.number),
            title=f"Plan: {issue.title}",
            description=output,  # Full markdown output
            tasks=tasks,
            file_path=f"plans/{issue.number}-{issue.title.lower().replace(' ', '-')}.md",
        )

        return plan

    def _parse_tasks_from_markdown(self, markdown: str) -> list:
        """Parse tasks from markdown output.

        Looks for pattern: ## N. Task Title
        followed by description text.
        """
        import re

        tasks = []
        lines = markdown.split("\n")

        # Pattern: ## 1. Task Title or ## Task 1: Title
        task_pattern = re.compile(r"^##\s+(\d+)[\.\:]\s+(.+?)$")

        current_task = None
        current_desc = []

        for line in lines:
            match = task_pattern.match(line.strip())
            if match:
                # Save previous task
                if current_task:
                    current_task["description"] = "\n".join(current_desc).strip()
                    tasks.append(current_task)

                # Start new task
                task_num = int(match.group(1))
                title = match.group(2).strip()
                current_task = {
                    "id": f"task-{task_num}",
                    "title": title,
                    "number": task_num,
                    "dependencies": [],
                }
                current_desc = []
            elif current_task and line.strip() and not line.strip().startswith("#"):
                # Accumulate description
                current_desc.append(line)

        # Don't forget the last task
        if current_task:
            current_task["description"] = "\n".join(current_desc).strip()
            tasks.append(current_task)

        # Return tasks as simple dicts with consistent structure
        # Convert to proper objects that support attribute access
        class TaskDict(dict):
            """Dict that also supports attribute access."""

            def __getattr__(self, key):
                try:
                    return self[key]
                except KeyError as e:
                    raise AttributeError(
                        f"'{type(self).__name__}' object has no attribute '{key}'"
                    ) from e

            def __setattr__(self, key, value):
                self[key] = value

        task_objects = []
        for t in tasks:
            task_obj = TaskDict(
                id=t["id"],
                title=t["title"],
                description=t.get("description", ""),
                dependencies=t.get("dependencies", []),
            )
            task_objects.append(task_obj)

        return task_objects

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks."""
        prompt = f"""Break down this plan into executable tasks:

{plan.description}

For each task, provide:
1. Task ID
2. Description
3. Dependencies (task IDs)
4. Estimated complexity

Format as JSON list.
"""

        await self.execute_prompt(prompt)

        # Would parse JSON and create Task objects
        # Simplified for now
        return []

    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        """Execute a development task."""
        # Store current issue for Q&A
        self.current_issue_number = context.get("issue_number")

        # Get original issue context
        original_issue = context.get("original_issue", {})

        task_num = context.get("task_number")
        total_tasks = context.get("total_tasks")
        prompt = f"""You are implementing Task {task_num} of {total_tasks} """
        prompt += """for a development project.

**Original Project**: """
        prompt += f"""{original_issue.get("title", "Unknown")}
{original_issue.get("body", "")}

**Your Task ({context.get("task_number")}/{context.get("total_tasks")})**: {task.title}

**Task Description**:
{task.description}

**Context**:
- Branch: {context.get("branch", "main")}
- Working directory: {context.get("workspace", ".")}

**CRITICAL Instructions**:
1. You MUST create or modify actual files for this task
2. Use the Write or Edit tools to create/modify files
3. DO NOT just describe what should be done - actually implement it
4. Create complete, working code files
5. The files will be automatically committed and pushed after you finish

**What to do**:
- Read the task description carefully
- Identify which files need to be created or modified
- Use Write tool to create new files
- Use Edit tool to modify existing files
- Make sure all code is complete and functional

NOTE: If you have questions during implementation, you can ask by outputting:
BUILDER_QUESTION: Your question here

The system will post your question to the issue and wait for a response.
"""

        result = await self.execute_prompt(prompt, context, task.id)

        # Check if agent asked any questions
        output = result.get("output", "")
        if "BUILDER_QUESTION:" in output:
            question = self._extract_question(output)
            if question and self.qa_handler and self.current_issue_number:
                # Ask user via issue comment
                answer = await self.qa_handler.ask_user_question(
                    self.current_issue_number,
                    question,
                    context=f"Task: {task.title}",
                    timeout_minutes=30,
                )

                if answer:
                    # Re-run with the answer
                    followup_prompt = f"""Previous task: {task.title}

You asked: {question}
User answered: {answer}

Please continue with the task using this information.
"""
                    result = await self.execute_prompt(followup_prompt, context, task.id)

        return TaskResult(
            success=result["success"],
            branch=context.get("branch"),
            commits=[],  # Would parse from git
            files_changed=result.get("files_changed", []),
            error=result.get("error"),
        )

    def _extract_question(self, output: str) -> str | None:
        """Extract question from agent output."""
        if "BUILDER_QUESTION:" not in output:
            return None

        lines = output.split("\n")
        for line in lines:
            if "BUILDER_QUESTION:" in line:
                return line.split("BUILDER_QUESTION:", 1)[1].strip()

        return None

    async def review_code(self, diff: str, context: dict) -> Review:
        """Review code changes."""
        prompt = f"""Review the following code changes:

{diff}

Context:
{context.get("description", "")}

Please provide:
1. Overall assessment (approve/request changes)
2. Specific issues or concerns
3. Suggestions for improvement

Be concise and focus on critical issues.
"""

        result = await self.execute_prompt(prompt)

        output = result.get("output", "")
        approved = any(word in output.lower() for word in ["approve", "looks good", "lgtm"])

        return Review(
            approved=approved,
            comments=output,
            confidence=0.8 if approved else 0.5,
        )

    async def resolve_conflict(self, conflict_info: dict) -> str:
        """Resolve merge conflict."""
        prompt = f"""Resolve the following merge conflict:

File: {conflict_info.get("file", "unknown")}

Conflict markers:
{conflict_info.get("content", "")}

Please provide the resolved content without conflict markers.
"""

        result = await self.execute_prompt(prompt)

        return result.get("output", "")
