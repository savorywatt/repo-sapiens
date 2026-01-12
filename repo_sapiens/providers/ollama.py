"""Ollama provider for local AI inference."""

from typing import Any

import httpx
import structlog

from repo_sapiens.models.domain import Issue, Plan, Review, Task, TaskResult
from repo_sapiens.providers.base import AgentProvider

log = structlog.get_logger(__name__)


class OllamaProvider(AgentProvider):
    """Agent provider that uses Ollama for local AI inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        working_dir: str | None = None,
        qa_handler: Any | None = None,
    ):
        """Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL
            model: Model to use (e.g., llama3.1:8b, codellama, mistral)
            working_dir: Working directory for operations
            qa_handler: Interactive Q&A handler
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.working_dir = working_dir or "."
        self.qa_handler = qa_handler
        self.current_issue_number: int | None = None
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout

    async def connect(self) -> None:
        """Check if Ollama is available and the model is downloaded."""
        try:
            # Check if Ollama is running
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            log.info("ollama_connected", available_models=model_names)

            # Check if our model is available
            if not any(self.model in name for name in model_names):
                log.warning(
                    "model_not_found",
                    model=self.model,
                    available=model_names,
                    message=f"Model {self.model} not found. Run: ollama pull {self.model}",
                )
            else:
                log.info("ollama_model_ready", model=self.model)

        except httpx.ConnectError as e:
            log.error("ollama_not_running", url=self.base_url)
            raise RuntimeError(f"Ollama not running at {self.base_url}. Start it with: ollama serve") from e
        except Exception as e:
            log.error("ollama_connection_failed", error=str(e))
            raise

    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt using Ollama.

        Args:
            prompt: The prompt to execute
            context: Additional context
            task_id: Unique task identifier

        Returns:
            Dict with execution results
        """
        log.info("executing_prompt", model=self.model, task_id=task_id)

        try:
            # Call Ollama generate API
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                    },
                },
            )
            response.raise_for_status()

            result = response.json()
            output = result.get("response", "")

            log.info(
                "prompt_executed",
                task_id=task_id,
                output_length=len(output),
                tokens=result.get("eval_count", 0),
            )

            return {
                "success": True,
                "output": output,
                "files_changed": self._detect_changed_files(output),
                "error": None,
            }

        except Exception as e:
            log.error("prompt_execution_failed", task_id=task_id, error=str(e))
            return {
                "success": False,
                "output": "",
                "files_changed": [],
                "error": str(e),
            }

    def _detect_changed_files(self, output: str) -> list[str]:
        """Detect which files were changed from output.

        This is a heuristic - looks for common patterns.
        """
        files = []

        # Look for file operation indicators
        patterns = [
            "Created file:",
            "Modified file:",
            "Updated file:",
            "Writing to:",
            "Saved:",
            "File:",
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
        """Generate development plan from issue.

        Args:
            issue: Issue to plan for

        Returns:
            Plan object with tasks
        """
        prompt = f"""You are a software architect creating a development plan.

**Issue #{issue.number}: {issue.title}**

{issue.body}

Create a detailed, actionable development plan following this EXACT format:

# Overview
[Brief 2-3 sentence overview of the solution approach]

# Tasks

## 1. [First Task Title]
[Detailed description of what needs to be done for this task. Be specific
about files, components, and implementation details.]

## 2. [Second Task Title]
[Detailed description]

## 3. [Third Task Title]
[Detailed description]

IMPORTANT:
- Break down the work into 3-7 concrete, actionable tasks
- Each task should be implementable independently
- Include specific technical details (which files, functions, APIs)
- Order tasks logically (dependencies first)
- Use the exact format shown above (## N. Title)
"""

        result = await self.execute_prompt(prompt)
        output = result.get("output", "")

        # Parse tasks from markdown output
        tasks = self._parse_tasks_from_markdown(output)

        plan = Plan(
            id=str(issue.number),
            title=f"Plan: {issue.title}",
            description=output,
            tasks=tasks,
            file_path=f"plans/{issue.number}-{issue.title.lower().replace(' ', '-')}.md",
        )

        return plan

    def _parse_tasks_from_markdown(self, markdown: str) -> list:
        """Parse tasks from markdown output."""
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

        # Convert to task objects with attribute access
        class TaskDict(dict):
            def __getattr__(self, key):
                try:
                    return self[key]
                except KeyError as e:
                    raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'") from e

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

    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        """Execute a development task.

        Args:
            task: Task to execute
            context: Execution context

        Returns:
            TaskResult with outcome
        """
        # Store current issue for Q&A
        self.current_issue_number = context.get("issue_number")

        # Get original issue context
        original_issue = context.get("original_issue", {})

        prompt = f"""You are implementing a software development task.

**Project**: {original_issue.get("title", "Unknown")}
{original_issue.get("body", "")}

**Your Task ({context.get("task_number")}/{context.get("total_tasks")})**: {task.title}

{task.description}

**Context**:
- Branch: {context.get("branch", "main")}
- Working directory: {context.get("workspace", ".")}

**Instructions**:
Describe the EXACT implementation steps and code changes needed for this task.

For each file that needs to be created or modified, use this format:

FILE: path/to/file.ext
```language
[complete file contents or specific changes]
```

Be specific and thorough. Include all necessary:
- File paths and names
- Complete code (not pseudocode)
- Import statements
- Configuration changes
- Tests if applicable

Focus on making this task complete and working.
"""

        result = await self.execute_prompt(prompt, context, task.id)

        # Note: With Ollama, we're getting guidance/instructions rather than
        # executing the changes directly. The user or another system would
        # apply the changes based on the output.

        return TaskResult(
            success=result["success"],
            branch=context.get("branch"),
            commits=[],
            files_changed=result.get("files_changed", []),
            error=result.get("error"),
        )

    async def review_code(self, diff: str, context: dict) -> Review:
        """Review code changes.

        Args:
            diff: Git diff to review
            context: Review context

        Returns:
            Review object with feedback
        """
        prompt = f"""You are a senior code reviewer. Review this code change.

**Context**: {context.get("description", "Code review")}

**Changes**:
```diff
{diff[:5000]}  # Limit diff size
```

Provide a code review with:
1. Overall assessment (approve or request changes)
2. Specific issues found (bugs, style, security, performance)
3. Suggestions for improvement

Be concise and constructive. Focus on important issues.

Start your response with either "APPROVE" or "REQUEST_CHANGES".
"""

        result = await self.execute_prompt(prompt)
        output = result.get("output", "")

        # Check if approved
        approved = "APPROVE" in output.upper().split("\n")[0]

        return Review(
            approved=approved,
            comments=output,
            confidence=0.7,  # Ollama tends to be more conservative
        )

    async def resolve_conflict(self, conflict_info: dict) -> str:
        """Resolve merge conflict.

        Args:
            conflict_info: Conflict details

        Returns:
            Resolved content
        """
        prompt = f"""Resolve this merge conflict.

**File**: {conflict_info.get("file", "unknown")}

**Conflict**:
```
{conflict_info.get("content", "")}
```

Provide the resolved content without conflict markers (<<<<<<, ======, >>>>>>).
"""

        result = await self.execute_prompt(prompt)
        return result.get("output", "")

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        For Ollama, we can use the tasks already parsed from the plan.
        """
        return plan.tasks if hasattr(plan, "tasks") else []

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
