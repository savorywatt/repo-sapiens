"""ReAct (Reasoning + Acting) agent using Ollama and local tools."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import structlog

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
    """Configuration for the ReAct agent."""

    model: str = "llama3.1:8b"
    ollama_url: str = "http://localhost:11434"
    max_iterations: int = 10
    temperature: float = 0.7
    timeout: int = 300


class ReActAgentProvider(AgentProvider):
    """ReAct agent using Ollama for reasoning and local tools for acting.

    This agent implements the ReAct (Reasoning + Acting) pattern:
    1. Think about what to do next
    2. Choose an action and execute it
    3. Observe the result
    4. Repeat until task is complete

    Example usage:
        agent = ReActAgentProvider(working_dir="/path/to/project")
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
    ):
        """Initialize the ReAct agent.

        Args:
            working_dir: Base directory for file operations
            config: Agent configuration
            allowed_commands: Optional whitelist for shell commands
        """
        self.config = config or ReActConfig()
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self.tools = ToolRegistry(
            self.working_dir,
            allowed_commands=allowed_commands,
        )
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        self._trajectory: list[TrajectoryStep] = []

    async def __aenter__(self) -> "ReActAgentProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.client.aclose()

    async def list_models(self, raise_on_error: bool = False) -> list[str]:
        """Get list of available models from Ollama server."""
        try:
            response = await self.client.get(f"{self.config.ollama_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m.get("name", "") for m in models]
        except httpx.ConnectError:
            if raise_on_error:
                raise
            return []

    async def connect(self) -> None:
        """Verify Ollama is running and model is available."""
        try:
            model_names = await self.list_models(raise_on_error=True)

            if not any(self.config.model in name for name in model_names):
                log.warning(
                    "model_not_found",
                    model=self.config.model,
                    available=model_names[:5],
                    hint=f"Run: ollama pull {self.config.model}",
                )
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Ollama not running at {self.config.ollama_url}. "
                "Start it with: ollama serve"
            ) from e

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
        )

        task_prompt = f"Task: {task.title}\n\nDescription: {task.description}"

        for iteration in range(self.config.max_iterations):
            log.debug("react_iteration", iteration=iteration + 1)

            # Generate next step from LLM
            response = await self._generate_step(task_prompt)

            # Parse the response
            thought, action, action_input = self._parse_response(response)

            if not action:
                log.warning("react_no_action", response=response[:200])
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

    async def _generate_step(self, task_prompt: str) -> str:
        """Generate the next ReAct step from Ollama.

        Args:
            task_prompt: The task description

        Returns:
            Raw LLM response
        """
        # Build the full prompt
        system = self.SYSTEM_PROMPT.format(
            tool_descriptions=self.tools.get_tool_descriptions()
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task_prompt},
        ]

        # Add trajectory as conversation history
        for step in self._trajectory:
            # Assistant's previous response
            assistant_msg = (
                f"THOUGHT: {step.thought}\n"
                f"ACTION: {step.action}\n"
                f"ACTION_INPUT: {json.dumps(step.action_input)}"
            )
            messages.append({"role": "assistant", "content": assistant_msg})

            # Observation as user message
            messages.append({
                "role": "user",
                "content": f"OBSERVATION: {step.observation}\n\nContinue with the next step.",
            })

        try:
            response = await self.client.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except Exception as e:
            log.error("ollama_request_failed", error=str(e))
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
    model: str = "llama3.1:8b",
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
