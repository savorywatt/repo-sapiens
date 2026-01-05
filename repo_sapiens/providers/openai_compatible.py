"""OpenAI-compatible provider for local AI inference (vLLM, LMStudio, etc.)."""

import re
from typing import Any

import httpx
import structlog

from repo_sapiens.models.domain import Issue, Plan, Review, Task, TaskResult
from repo_sapiens.providers.base import AgentProvider

log = structlog.get_logger(__name__)


class OpenAICompatibleProvider(AgentProvider):
    """Agent provider for OpenAI-compatible API servers.

    Supports vLLM, LMStudio, text-generation-webui, and other servers
    that implement the OpenAI API specification.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "default",
        api_key: str | None = None,
        working_dir: str | None = None,
        qa_handler: Any | None = None,
        timeout: float = 300.0,
    ):
        """Initialize OpenAI-compatible provider.

        Args:
            base_url: API base URL (e.g., http://localhost:8000/v1)
            model: Model identifier to use
            api_key: Optional API key for authentication
            working_dir: Working directory for operations
            qa_handler: Interactive Q&A handler
            timeout: Request timeout in seconds (default: 300)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.working_dir = working_dir or "."
        self.qa_handler = qa_handler
        self.timeout = timeout
        self.current_issue_number: int | None = None

        # Build headers
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def connect(self) -> None:
        """Verify server connection and model availability."""
        try:
            # Check if server is running by listing models
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()

            data = response.json()
            models = data.get("data", [])
            model_ids = [m.get("id", "") for m in models]

            log.info("openai_compatible_connected", available_models=model_ids)

            # Check if our model is available (if not using 'default')
            if self.model != "default" and model_ids:
                if not any(self.model in mid for mid in model_ids):
                    log.warning(
                        "model_not_found",
                        model=self.model,
                        available=model_ids,
                        message=f"Model {self.model} not found in available models",
                    )
                else:
                    log.info("openai_compatible_model_ready", model=self.model)
            else:
                log.info("openai_compatible_ready", model=self.model)

        except httpx.ConnectError as e:
            log.error("openai_compatible_not_running", url=self.base_url)
            raise RuntimeError(
                f"OpenAI-compatible server not running at {self.base_url}. "
                "Ensure your server (vLLM, LMStudio, etc.) is started."
            ) from e
        except httpx.HTTPStatusError as e:
            # Some servers may not implement /models endpoint
            if e.response.status_code == 404:
                log.warning(
                    "models_endpoint_not_available",
                    message="Server does not support /models endpoint, proceeding anyway",
                )
            else:
                log.error("openai_compatible_connection_failed", error=str(e))
                raise
        except Exception as e:
            log.error("openai_compatible_connection_failed", error=str(e))
            raise

    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt using the OpenAI-compatible API.

        Args:
            prompt: The prompt to execute
            context: Additional context
            task_id: Unique task identifier

        Returns:
            Dict with execution results
        """
        log.info("executing_prompt", model=self.model, task_id=task_id)

        try:
            # Call chat completions API
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()

            result = response.json()
            choices = result.get("choices", [])

            if not choices:
                log.error("no_choices_in_response", task_id=task_id)
                return {
                    "success": False,
                    "output": "",
                    "files_changed": [],
                    "error": "No choices returned from API",
                }

            output = choices[0].get("message", {}).get("content", "")

            # Extract usage statistics if available
            usage = result.get("usage", {})
            tokens = usage.get("total_tokens", usage.get("completion_tokens", 0))

            log.info(
                "prompt_executed",
                task_id=task_id,
                output_length=len(output),
                tokens=tokens,
            )

            return {
                "success": True,
                "output": output,
                "files_changed": self._detect_changed_files(output),
                "error": None,
            }

        except httpx.HTTPStatusError as e:
            error_detail = str(e)
            try:
                error_body = e.response.json()
                error_detail = error_body.get("error", {}).get("message", str(e))
            except Exception:  # nosec B110
                pass  # Parsing error body failed, keep original error

            log.error(
                "prompt_execution_failed",
                task_id=task_id,
                status_code=e.response.status_code,
                error=error_detail,
            )
            return {
                "success": False,
                "output": "",
                "files_changed": [],
                "error": f"API error ({e.response.status_code}): {error_detail}",
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

        This is a heuristic - looks for common patterns in LLM output.
        """
        files: list[str] = []

        # Look for file operation indicators
        patterns = [
            "Created file:",
            "Modified file:",
            "Updated file:",
            "Writing to:",
            "Saved:",
            "File:",
            "FILE:",
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

    def _parse_tasks_from_markdown(self, markdown: str) -> list:
        """Parse tasks from markdown output."""
        tasks = []
        lines = markdown.split("\n")

        # Pattern: ## 1. Task Title or ## Task 1: Title
        task_pattern = re.compile(r"^##\s+(\d+)[\.\:]\s+(.+?)$")

        current_task: dict[str, Any] | None = None
        current_desc: list[str] = []

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
            """Dict subclass that allows attribute access."""

            def __getattr__(self, key: str) -> Any:
                try:
                    return self[key]
                except KeyError as e:
                    raise AttributeError(
                        f"'{type(self).__name__}' object has no attribute '{key}'"
                    ) from e

            def __setattr__(self, key: str, value: Any) -> None:
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

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Break plan into executable tasks.

        For this provider, we use the tasks already parsed from the plan.

        Args:
            plan: Plan to break down

        Returns:
            List of Task objects
        """
        return plan.tasks if hasattr(plan, "tasks") else []

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
        # Limit diff size to avoid token limits
        truncated_diff = diff[:5000]

        prompt = f"""You are a senior code reviewer. Review this code change.

**Context**: {context.get("description", "Code review")}

**Changes**:
```diff
{truncated_diff}
```

Provide a code review with:
1. Overall assessment (approve or request changes)
2. Specific issues found (bugs, style, security, performance)
3. Suggestions for improvement

Be concise and constructive. Focus on important issues.

Start your response with either "APPROVE" or "REQUEST_CHANGES".
Then list specific comments, one per line starting with "- ".
"""

        result = await self.execute_prompt(prompt)
        output = result.get("output", "")

        # Check if approved (look at first line)
        first_line = output.split("\n")[0] if output else ""
        approved = "APPROVE" in first_line.upper()

        # Parse comments from output
        comments: list[str] = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                comments.append(line[2:])

        # If no bullet points found, use the whole output as a single comment
        if not comments and output:
            comments = [output]

        return Review(
            approved=approved,
            comments=comments,
            confidence_score=0.7,  # Conservative score for local models
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
Output ONLY the resolved file content, no explanations.
"""

        result = await self.execute_prompt(prompt)
        return result.get("output", "")

    async def __aenter__(self) -> "OpenAICompatibleProvider":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.client.aclose()
