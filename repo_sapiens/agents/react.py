"""ReAct (Reasoning + Acting) agent using LLM backends and local tools.

Supports multiple LLM backends:
- Ollama (local inference)
- OpenAI-compatible APIs (OpenAI, vLLM, llama.cpp, etc.)

Can use native function calling when available, with text-based parsing as fallback.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import structlog

from repo_sapiens.agents.backends import ChatResponse, LLMBackend, create_backend
from repo_sapiens.agents.tools import ToolRegistry
from repo_sapiens.models.domain import Issue, Plan, Review, Task, TaskResult
from repo_sapiens.providers.base import AgentProvider

log = structlog.get_logger()


@dataclass
class TrajectoryStep:
    """A single step in the ReAct trajectory."""

    iteration: int
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str


@dataclass
class ReActConfig:
    """Configuration for the ReAct agent.

    Attributes:
        model: Model name/identifier to use
        backend_type: LLM backend type ("ollama" or "openai")
        base_url: Backend API base URL (None uses backend default)
        api_key: API key for authentication (OpenAI backend)
        max_iterations: Maximum ReAct loop iterations
        temperature: Sampling temperature (0.0 to 1.0)
        timeout: Request timeout in seconds
        use_native_tools: Use native function calling when available
    """

    model: str = "qwen3:latest"
    backend_type: Literal["ollama", "openai"] = "ollama"
    base_url: str | None = None
    api_key: str | None = None
    max_iterations: int = 10
    temperature: float = 0.7
    timeout: int = 300
    use_native_tools: bool = True

    @property
    def ollama_url(self) -> str:
        """Legacy property for backwards compatibility."""
        return self.base_url or "http://localhost:11434"

    @ollama_url.setter
    def ollama_url(self, value: str) -> None:
        """Legacy setter for backwards compatibility."""
        self.base_url = value


class ReActAgentProvider(AgentProvider):
    """ReAct agent using LLM backends for reasoning and local tools for acting.

    This agent implements the ReAct (Reasoning + Acting) pattern:
    1. Think about what to do next
    2. Choose an action and execute it
    3. Observe the result
    4. Repeat until task is complete

    Supports multiple backends:
    - Ollama (default): Local inference with models like qwen3, llama3, etc.
    - OpenAI: OpenAI API or compatible servers (vLLM, llama.cpp, etc.)

    When use_native_tools=True (default), uses native function calling for
    backends that support it, falling back to text-based parsing otherwise.

    Example usage:
        # Ollama backend (default)
        agent = ReActAgentProvider(working_dir="/path/to/project")

        # OpenAI-compatible backend
        config = ReActConfig(
            backend_type="openai",
            base_url="http://localhost:8000/v1",
            model="gpt-4",
        )
        agent = ReActAgentProvider(working_dir="/path/to/project", config=config)

        result = await agent.execute_task(task, context={})
    """

    SYSTEM_PROMPT = """You are a ReAct agent that solves tasks by thinking step-by-step and using tools.

For each step, you MUST output in this EXACT format:
THOUGHT: [Your reasoning about what to do next]
ACTION: [Tool name]
ACTION_INPUT: [JSON object with the tool parameters]

{tool_descriptions}

Rules:
- Always start with THOUGHT to reason about the current situation
- Choose exactly ONE action per step
- ACTION_INPUT must be valid JSON
- Use 'finish' when the task is complete
- Be concise in your thoughts

CRITICAL: When using 'finish', the 'answer' field must contain the ACTUAL DATA the user asked for. Copy the real data into the answer string - do NOT use code, variables, or expressions. The user only sees what's in the 'answer' field.

Example:
THOUGHT: I need to read the README to understand the project structure.
ACTION: read_file
ACTION_INPUT: {{"path": "README.md"}}

Example finish with proper answer (copy the actual data into answer):
THOUGHT: The find_files tool returned: main.py, utils.py, test.py. I'll put this in the answer.
ACTION: finish
ACTION_INPUT: {{"answer": "Found 3 Python files:\\n- main.py\\n- utils.py\\n- test.py", "summary": "Listed Python files"}}

WRONG (do not do this):
ACTION_INPUT: {{"answer": files_variable}}  <- NO! Don't use variables
ACTION_INPUT: {{"answer": "\\n".join(files)}}  <- NO! Don't use code
"""

    def __init__(
        self,
        working_dir: str | Path | None = None,
        config: ReActConfig | None = None,
        allowed_commands: list[str] | None = None,
        system_prompt: str | None = None,
    ):
        """Initialize the ReAct agent.

        Args:
            working_dir: Base directory for file operations
            config: Agent configuration
            allowed_commands: Optional whitelist for shell commands
            system_prompt: Custom system prompt (uses default if None)
        """
        self.config = config or ReActConfig()
        self.working_dir = str(Path(working_dir or os.getcwd()).resolve())
        self.tools = ToolRegistry(
            self.working_dir,
            allowed_commands=allowed_commands,
        )

        # Create the LLM backend
        self.backend: LLMBackend = create_backend(
            backend_type=self.config.backend_type,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
        )

        self._trajectory: list[TrajectoryStep] = []
        self.system_prompt = system_prompt or self.SYSTEM_PROMPT

    async def __aenter__(self) -> ReActAgentProvider:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.backend.close()

    async def list_models(self, raise_on_error: bool = False) -> list[str]:
        """Get list of available models from the backend."""
        return await self.backend.list_models(raise_on_error=raise_on_error)

    async def connect(self) -> None:
        """Verify the backend is running and model is available."""
        await self.backend.connect()

        # Check if our model is available
        model_names = await self.backend.list_models()
        if model_names and not any(self.config.model in name for name in model_names):
            log.warning(
                "model_not_found",
                model=self.config.model,
                available=model_names[:5],
                hint=f"Pull or download model: {self.config.model}",
            )

    def set_model(self, model: str) -> None:
        """Change the model to use."""
        self.config.model = model

    async def execute_task(self, task: Task, context: dict[str, Any]) -> TaskResult:
        """Execute a task using the ReAct loop.

        Args:
            task: Task to execute
            context: Additional context (ignored for now)

        Returns:
            TaskResult with execution details
        """
        self._trajectory = []
        self.tools.reset()

        log.info(
            "react_starting",
            task_id=task.id,
            title=task.title,
            max_iterations=self.config.max_iterations,
            backend=self.config.backend_type,
            native_tools=self.config.use_native_tools,
        )

        task_prompt = f"Task: {task.title}\n\nDescription: {task.description}"

        for iteration in range(self.config.max_iterations):
            log.debug("react_iteration", iteration=iteration + 1)

            # Generate next step from LLM
            response = await self._generate_step(task_prompt)

            # Handle native tool calls vs text-based parsing
            if isinstance(response, ChatResponse) and response.has_tool_calls:
                # Native function calling - extract tool call directly
                tool_call = response.tool_calls[0]
                thought = response.content or ""
                action = tool_call.name
                action_input = tool_call.arguments
            else:
                # Text-based parsing fallback
                text_response = response.content if isinstance(response, ChatResponse) else response
                thought, action, action_input = self._parse_response(text_response)

            if not action:
                response_preview = response.content[:200] if isinstance(response, ChatResponse) else str(response)[:200]
                log.warning("react_no_action", response=response_preview)
                continue

            # Check for completion
            if action == "finish":
                answer = action_input.get("answer", action_input.get("summary", ""))
                # If finish was called but with empty/invalid action_input, retry
                if not answer and not action_input:
                    log.warning("finish_without_answer", hint="JSON parsing likely failed")
                    observation = "Error: Your ACTION_INPUT was not valid JSON. Please provide a valid JSON object with an 'answer' field containing the actual data. Do NOT use variables or code - copy the data as a literal string."
                    step = TrajectoryStep(
                        iteration=iteration + 1,
                        thought=thought,
                        action=action,
                        action_input={},
                        observation=observation,
                    )
                    self._trajectory.append(step)
                    continue  # Retry - trajectory will be included in next call

                log.info(
                    "react_finished",
                    iterations=iteration + 1,
                    summary=action_input.get("summary", ""),
                )
                return TaskResult(
                    success=True,
                    files_changed=self.tools.get_files_written(),
                    execution_time=0.0,
                    output=answer,
                )

            # Execute the tool
            observation = await self.tools.execute(action, action_input)

            # Record trajectory
            step = TrajectoryStep(
                iteration=iteration + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
            self._trajectory.append(step)

            log.debug(
                "react_step",
                iteration=iteration + 1,
                action=action,
                observation_len=len(observation),
            )

        log.warning("react_max_iterations", max=self.config.max_iterations)
        return TaskResult(
            success=False,
            error=f"Max iterations ({self.config.max_iterations}) reached",
            files_changed=self.tools.get_files_written(),
        )

    async def _generate_step(self, task_prompt: str) -> ChatResponse | str:
        """Generate the next ReAct step from the LLM backend.

        Args:
            task_prompt: The task description

        Returns:
            ChatResponse with tool_calls (native mode) or raw string (text mode)
        """
        # Build the full prompt
        # If custom system prompt contains {tool_descriptions}, replace it
        # Otherwise, use it as-is
        try:
            system = self.system_prompt.format(tool_descriptions=self.tools.get_tool_descriptions())
        except KeyError:
            # System prompt doesn't use {tool_descriptions} placeholder
            system = self.system_prompt

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task_prompt},
        ]

        # Add trajectory as conversation history
        for step in self._trajectory:
            # Assistant's previous response
            assistant_msg = (
                f"THOUGHT: {step.thought}\n" f"ACTION: {step.action}\n" f"ACTION_INPUT: {json.dumps(step.action_input)}"
            )
            messages.append({"role": "assistant", "content": assistant_msg})

            # Observation as user message
            messages.append(
                {
                    "role": "user",
                    "content": f"OBSERVATION: {step.observation}\n\nContinue with the next step.",
                }
            )

        # Determine if we should use native tool calling
        tools = None
        if self.config.use_native_tools:
            tools = self.tools.to_openai_format()

        try:
            response = await self.backend.chat(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature,
                tools=tools,
            )

            # If we got tool calls back, return the full response for native handling
            if response.has_tool_calls:
                log.debug(
                    "native_tool_call",
                    tool=response.tool_calls[0].name,
                    args=response.tool_calls[0].arguments,
                )
                return response

            # Otherwise, return the text content for text-based parsing
            return response.content

        except Exception as e:
            log.error("backend_request_failed", error=str(e))
            raise

    def _parse_response(self, response: str) -> tuple[str, str, dict[str, Any]]:
        """Parse the ReAct response into thought, action, and input.

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (thought, action, action_input)
        """
        thought = ""
        action = ""
        action_input: dict[str, Any] = {}

        # Extract THOUGHT
        thought_match = re.search(
            r"THOUGHT:\s*(.+?)(?=ACTION:|$)",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract ACTION
        action_match = re.search(
            r"ACTION:\s*(\w+)",
            response,
            re.IGNORECASE,
        )
        if action_match:
            action = action_match.group(1).strip().lower()

        # Extract ACTION_INPUT
        input_match = re.search(
            r"ACTION_INPUT:\s*(\{.+?\})",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                log.warning("invalid_action_input", raw=input_match.group(1))
                action_input = {}

        return thought, action, action_input

    def get_trajectory(self) -> list[TrajectoryStep]:
        """Get the execution trajectory."""
        return self._trajectory.copy()

    # --- AgentProvider interface implementation ---

    async def execute_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt and return the result.

        Uses the LLM backend directly without the ReAct loop. This is useful for
        simple prompt-response interactions like analyzing comments or generating
        quick responses.

        Args:
            prompt: The prompt text to execute.
            context: Optional context dict (not used, for interface compatibility).
            task_id: Optional task identifier for logging.

        Returns:
            Dict with 'success', 'output', and optionally 'error' keys.
        """
        log.info("execute_prompt", task_id=task_id, prompt_len=len(prompt))

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.backend.chat(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature,
            )

            return {
                "success": True,
                "output": response.content,
                "error": None,
            }
        except Exception as e:
            log.error("execute_prompt_failed", task_id=task_id, error=str(e))
            return {
                "success": False,
                "output": "",
                "error": str(e),
            }

    async def generate_plan(self, issue: Issue) -> Plan:
        """Generate a plan from an issue using ReAct reasoning.

        For simple ReAct usage, this creates a single-task plan.
        """
        task = Task(
            id=f"react-{issue.number}",
            prompt_issue_id=issue.number,
            title=issue.title,
            description=issue.body,
        )
        return Plan(
            id=f"plan-{issue.number}",
            title=f"Plan for: {issue.title}",
            description=issue.body,
            tasks=[task],
        )

    async def generate_prompts(self, plan: Plan) -> list[Task]:
        """Return tasks from the plan."""
        return plan.tasks

    async def review_code(self, diff: str, context: dict[str, Any]) -> Review:
        """Review code changes using ReAct reasoning."""
        # Create a review task
        task = Task(
            id="review",
            prompt_issue_id=0,
            title="Review code changes",
            description=f"Review the following code diff and provide feedback:\n\n```diff\n{diff[:5000]}\n```",
        )

        result = await self.execute_task(task, context)

        # Parse approval from trajectory
        approved = False
        comments: list[str] = []

        for step in self._trajectory:
            if "approve" in step.thought.lower():
                approved = True
            if step.action == "finish":
                comments.append(step.action_input.get("summary", ""))

        return Review(
            approved=approved,
            comments=comments,
            confidence_score=0.7 if result.success else 0.3,
        )

    async def resolve_conflict(self, conflict_info: dict[str, Any]) -> str:
        """Resolve a merge conflict using ReAct reasoning."""
        file_path = conflict_info.get("file", "unknown")
        content = conflict_info.get("content", "")

        task = Task(
            id="resolve-conflict",
            prompt_issue_id=0,
            title=f"Resolve merge conflict in {file_path}",
            description=(
                f"Resolve the merge conflict in {file_path}. "
                f"The conflicted content is:\n\n```\n{content}\n```\n\n"
                "Use write_file to save the resolved version."
            ),
        )

        await self.execute_task(task, {})

        # Read the resolved file
        resolved = await self.tools.execute("read_file", {"path": file_path})
        return resolved


async def run_react_task(
    task_description: str,
    working_dir: str | None = None,
    model: str = "qwen3:latest",
    max_iterations: int = 10,
    verbose: bool = False,
) -> TaskResult:
    """Convenience function to run a task with the ReAct agent.

    Args:
        task_description: What to do
        working_dir: Directory to work in
        model: Ollama model to use
        max_iterations: Maximum ReAct iterations
        verbose: Print trajectory steps

    Returns:
        TaskResult with execution details
    """
    config = ReActConfig(model=model, max_iterations=max_iterations)
    agent = ReActAgentProvider(working_dir=working_dir, config=config)

    task = Task(
        id="cli-task",
        prompt_issue_id=0,
        title=task_description,
        description=task_description,
    )

    async with agent:
        await agent.connect()
        result = await agent.execute_task(task, {})

        if verbose:
            for step in agent.get_trajectory():
                print(f"\n--- Step {step.iteration} ---")
                print(f"THOUGHT: {step.thought}")
                print(f"ACTION: {step.action}")
                print(f"INPUT: {step.action_input}")
                print(f"OBSERVATION: {step.observation[:200]}...")

        return result
