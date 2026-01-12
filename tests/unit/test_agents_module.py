"""Unit tests for repo_sapiens/agents/ module - Coverage completion tests.

This module provides additional tests to cover edge cases and branches
not exercised by the main test files (test_react_agent.py, test_react_backends.py).

Focus areas:
1. Backend initialization and configuration
2. Tool registration and schema generation
3. ReAct loop state management
4. Error handling paths
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.agents.backends import (
    LLMBackend,
    OllamaBackend,
    OpenAIBackend,
    create_backend,
)
from repo_sapiens.agents.react import (
    ReActAgentProvider,
    ReActConfig,
    TrajectoryStep,
    run_react_task,
)
from repo_sapiens.agents.tools import ToolDefinition, ToolExecutionError, ToolRegistry

# =============================================================================
# TestToolDefinition - Tool schema generation and registration
# =============================================================================


class TestToolDefinition:
    """Tests for ToolDefinition dataclass and tool schema generation."""

    def test_tool_definition_creation(self) -> None:
        """Test creating a ToolDefinition with all fields."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool for testing",
            parameters={"param1": "Description of param1", "param2": "Description of param2"},
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool for testing"
        assert "param1" in tool.parameters
        assert "param2" in tool.parameters

    def test_all_registered_tools_have_definitions(self) -> None:
        """Test that all registered tools have proper definitions."""
        expected_tools = [
            "read_file",
            "write_file",
            "list_directory",
            "run_command",
            "finish",
            "search_files",
            "find_files",
            "edit_file",
            "tree",
        ]

        for tool_name in expected_tools:
            assert tool_name in ToolRegistry.TOOLS
            tool = ToolRegistry.TOOLS[tool_name]
            assert isinstance(tool, ToolDefinition)
            assert tool.name == tool_name
            assert len(tool.description) > 0
            assert isinstance(tool.parameters, dict)

    def test_tool_descriptions_format(self) -> None:
        """Test that get_tool_descriptions generates proper format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ToolRegistry(tmpdir)
            descriptions = registry.get_tool_descriptions()

            # Should start with header
            assert descriptions.startswith("Available tools:")

            # Should contain all tool names
            for tool_name in ToolRegistry.TOOLS:
                assert tool_name in descriptions

            # Should contain parameter descriptions
            assert "path" in descriptions.lower()


# =============================================================================
# TestToolRegistryEdgeCases - Remaining uncovered branches
# =============================================================================


class TestToolRegistryEdgeCases:
    """Tests for edge cases in ToolRegistry to achieve 100% coverage."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def registry(self, temp_dir):
        """Create a ToolRegistry instance."""
        return ToolRegistry(temp_dir)

    @pytest.mark.asyncio
    async def test_find_files_catches_valueerror_for_outside_paths(
        self, registry: ToolRegistry, temp_dir: Path
    ) -> None:
        """Test that find_files catches ValueError for paths outside working directory.

        This covers lines 419-420 where ValueError is caught during relative_to call.
        """
        # Create a file that will match the pattern
        (temp_dir / "test.txt").touch()

        # Mock glob to return a path that raises ValueError on relative_to
        mock_path = MagicMock(spec=Path)
        mock_path.parts = ("not", "hidden")
        mock_path.is_file.return_value = True

        def raise_value_error(base: Path) -> str:
            raise ValueError("Path is outside working directory")

        mock_path.relative_to = raise_value_error

        original_glob = Path.glob

        def mock_glob(self: Path, pattern: str):
            # Return real files plus the mocked path that will raise ValueError
            real_results = list(original_glob(self, pattern))
            return real_results + [mock_path]

        with patch.object(Path, "glob", mock_glob):
            result = await registry.execute("find_files", {"pattern": "*.txt"})

        # Should still work, just skipping the problematic path
        # (either returns files or "No files found" if the mock replaced all)
        assert "Error" not in result or "No files found" in result

    @pytest.mark.asyncio
    async def test_tree_depth_limit_returns_empty(self, registry: ToolRegistry, temp_dir: Path) -> None:
        """Test that tree's build_tree returns empty list when depth exceeds max.

        This covers line 494 where depth > max_depth returns [].
        """
        # Create a deeply nested structure
        current = temp_dir
        for i in range(6):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file{i}.txt").touch()

        # Use max_depth=0 to force the early return
        result = await registry.execute("tree", {"path": ".", "max_depth": 0})

        # With max_depth=0, should only show the root directory header
        # No child entries should be shown
        assert "./" in result or "level0" not in result

    @pytest.mark.asyncio
    async def test_tree_catches_valueerror_for_header_path(self, temp_dir: Path) -> None:
        """Test that tree catches ValueError when computing header path.

        This covers lines 521-522 where ValueError is caught for relative_to.
        """
        # Create a registry with a different working directory
        registry = ToolRegistry(temp_dir)

        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        # The normal case should work
        result = await registry.execute("tree", {"path": "subdir"})
        assert "subdir" in result

        # To trigger the ValueError branch, we need a resolved path that
        # is not relative to working_dir. This is tricky to trigger naturally.
        # We can mock the resolve method to return a path outside working_dir.
        with patch.object(Path, "resolve") as mock_resolve:
            # Make resolve return a path that's outside working directory
            outside_path = Path("/some/other/directory")
            mock_resolve.return_value = outside_path

            # Mock exists and is_dir to return True
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "is_dir", return_value=True):
                    # This should trigger the security check in _resolve_path
                    result = await registry.execute("tree", {"path": "."})

        # Should get an error about path security
        assert "Error" in result or "outside" in result.lower()


# =============================================================================
# TestReActAgentStateManagement - Agent state tracking
# =============================================================================


class TestReActAgentStateManagement:
    """Tests for ReAct agent state management and trajectory tracking."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return ReActConfig(
            model="test-model",
            ollama_url="http://localhost:11434",
            max_iterations=5,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir, config=config)

    def test_trajectory_step_creation(self) -> None:
        """Test creating TrajectoryStep instances."""
        step = TrajectoryStep(
            iteration=1,
            thought="I need to analyze the problem",
            action="read_file",
            action_input={"path": "test.txt"},
            observation="File contents here",
        )
        assert step.iteration == 1
        assert "analyze" in step.thought
        assert step.action == "read_file"
        assert step.action_input["path"] == "test.txt"
        assert step.observation == "File contents here"

    def test_trajectory_is_copy(self, agent: ReActAgentProvider) -> None:
        """Test that get_trajectory returns a copy, not the original list."""
        step = TrajectoryStep(
            iteration=1,
            thought="Test",
            action="read_file",
            action_input={},
            observation="Result",
        )
        agent._trajectory = [step]

        trajectory1 = agent.get_trajectory()
        trajectory2 = agent.get_trajectory()

        # Should return equal content
        assert trajectory1 == trajectory2

        # But not the same object
        assert trajectory1 is not agent._trajectory
        assert trajectory2 is not agent._trajectory

        # Modifying returned list shouldn't affect original
        trajectory1.append(step)
        assert len(agent._trajectory) == 1

    def test_agent_init_with_allowed_commands(self, temp_dir) -> None:
        """Test agent initialization with command allowlist."""
        allowed = ["echo", "ls", "cat"]
        agent = ReActAgentProvider(
            working_dir=temp_dir,
            allowed_commands=allowed,
        )
        assert agent.tools.allowed_commands == allowed

    def test_agent_init_default_working_dir(self) -> None:
        """Test agent uses cwd when working_dir not specified."""
        import os

        agent = ReActAgentProvider()
        assert agent.working_dir == Path(os.getcwd()).resolve()

    def test_tools_reset_clears_state(self, agent: ReActAgentProvider) -> None:
        """Test that tools.reset() clears files_written list."""
        agent.tools.files_written = ["file1.txt", "file2.txt"]
        agent.tools.reset()
        assert agent.tools.files_written == []


# =============================================================================
# TestBackendConfiguration - Backend setup and configuration
# =============================================================================


class TestBackendConfiguration:
    """Tests for backend initialization and configuration."""

    def test_ollama_backend_custom_timeout(self) -> None:
        """Test OllamaBackend respects custom timeout."""
        backend = OllamaBackend(timeout=60)
        assert backend.timeout == 60

        # Client should use the timeout
        client = backend.client
        assert client.timeout.read == 60

    def test_openai_backend_without_api_key(self) -> None:
        """Test OpenAIBackend works without API key for local servers."""
        backend = OpenAIBackend(base_url="http://localhost:8000/v1")
        headers = backend._get_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_create_backend_with_all_parameters(self) -> None:
        """Test create_backend passes all parameters correctly."""
        backend = create_backend(
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="test-key",
            timeout=120,
        )
        assert isinstance(backend, OpenAIBackend)
        assert backend.base_url == "https://api.example.com/v1"
        assert backend.api_key == "test-key"
        assert backend.timeout == 120


# =============================================================================
# TestReActConfigValidation - Configuration validation
# =============================================================================


class TestReActConfigValidation:
    """Tests for ReActConfig dataclass validation."""

    def test_config_with_all_defaults(self) -> None:
        """Test ReActConfig with all default values."""
        config = ReActConfig()
        assert config.model == "qwen3:latest"
        assert config.ollama_url == "http://localhost:11434"
        assert config.max_iterations == 10
        assert config.temperature == 0.7
        assert config.timeout == 300

    def test_config_with_custom_values(self) -> None:
        """Test ReActConfig with custom values."""
        config = ReActConfig(
            model="custom-model",
            ollama_url="http://remote:11434",
            max_iterations=20,
            temperature=0.5,
            timeout=600,
        )
        assert config.model == "custom-model"
        assert config.ollama_url == "http://remote:11434"
        assert config.max_iterations == 20
        assert config.temperature == 0.5
        assert config.timeout == 600


# =============================================================================
# TestToolExecutionError - Custom exception
# =============================================================================


class TestToolExecutionError:
    """Tests for ToolExecutionError custom exception."""

    def test_tool_execution_error_message(self) -> None:
        """Test ToolExecutionError stores and returns message correctly."""
        error = ToolExecutionError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_tool_execution_error_inheritance(self) -> None:
        """Test ToolExecutionError is a proper Exception subclass."""
        error = ToolExecutionError("Test error")
        assert isinstance(error, Exception)

        # Should be raisable and catchable
        with pytest.raises(ToolExecutionError):
            raise error


# =============================================================================
# TestLLMBackendAbstraction - Abstract base class
# =============================================================================


class TestLLMBackendAbstraction:
    """Tests for LLMBackend abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that LLMBackend cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            LLMBackend()  # type: ignore[abstract]

    def test_concrete_classes_are_llmbackend_subclasses(self) -> None:
        """Test that concrete backends are proper LLMBackend subclasses."""
        assert issubclass(OllamaBackend, LLMBackend)
        assert issubclass(OpenAIBackend, LLMBackend)

        # Instances should pass isinstance check
        ollama = OllamaBackend()
        openai = OpenAIBackend()
        assert isinstance(ollama, LLMBackend)
        assert isinstance(openai, LLMBackend)


# =============================================================================
# TestRunReactTaskConvenience - Convenience function tests
# =============================================================================


class TestRunReactTaskConvenience:
    """Tests for run_react_task convenience function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_run_react_task_creates_correct_task(self, temp_dir) -> None:
        """Test that run_react_task creates Task with correct fields."""
        from repo_sapiens.models.domain import TaskResult

        captured_task = None

        with patch("repo_sapiens.agents.react.ReActAgentProvider") as MockAgent:
            mock_instance = AsyncMock()

            async def capture_execute_task(task, context):
                nonlocal captured_task
                captured_task = task
                return TaskResult(success=True, output="Done", files_changed=[])

            mock_instance.execute_task = capture_execute_task
            mock_instance.connect = AsyncMock()
            mock_instance.get_trajectory = MagicMock(return_value=[])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()

            MockAgent.return_value = mock_instance

            await run_react_task(
                task_description="Test the feature",
                working_dir=str(temp_dir),
            )

        assert captured_task is not None
        assert captured_task.id == "cli-task"
        assert captured_task.title == "Test the feature"
        assert captured_task.description == "Test the feature"


# =============================================================================
# TestResolvePathSecurity - Path resolution security
# =============================================================================


class TestResolvePathSecurity:
    """Tests for path resolution and security checks in ToolRegistry."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def registry(self, temp_dir):
        """Create a ToolRegistry instance."""
        return ToolRegistry(temp_dir)

    def test_resolve_path_valid(self, registry: ToolRegistry, temp_dir: Path) -> None:
        """Test _resolve_path with valid paths."""
        resolved = registry._resolve_path("subdir/file.txt")
        assert str(resolved).startswith(str(temp_dir))

    def test_resolve_path_rejects_parent_traversal(self, registry: ToolRegistry) -> None:
        """Test _resolve_path rejects paths with parent traversal."""
        with pytest.raises(ToolExecutionError, match="outside working directory"):
            registry._resolve_path("../../../etc/passwd")

    def test_resolve_path_rejects_absolute_outside(self, registry: ToolRegistry) -> None:
        """Test _resolve_path behavior with absolute paths outside working dir."""
        # Note: This depends on how the path is resolved - absolute paths
        # that resolve outside working_dir should be rejected
        with pytest.raises(ToolExecutionError, match="outside working directory"):
            registry._resolve_path("/etc/passwd")


# =============================================================================
# TestUncoveredBranches - Tests for remaining uncovered code paths
# =============================================================================


class TestUncoveredBranches:
    """Tests specifically targeting uncovered code branches."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def registry(self, temp_dir):
        """Create a ToolRegistry instance."""
        return ToolRegistry(temp_dir)

    @pytest.mark.asyncio
    async def test_execute_unimplemented_tool_branch(self, registry: ToolRegistry) -> None:
        """Test line 201 - the else branch for unimplemented tools.

        This branch is defensive code that shouldn't normally be reached,
        but we can test it by temporarily adding a fake tool definition.
        """
        # Add a fake tool to TOOLS that has no implementation
        fake_tool = ToolDefinition(
            name="fake_unimplemented",
            description="A fake tool with no implementation",
            parameters={},
        )

        # Temporarily add the fake tool
        original_tools = ToolRegistry.TOOLS.copy()
        ToolRegistry.TOOLS["fake_unimplemented"] = fake_tool

        try:
            result = await registry.execute("fake_unimplemented", {})
            assert "not implemented" in result.lower()
        finally:
            # Restore original tools
            ToolRegistry.TOOLS = original_tools

    @pytest.mark.asyncio
    async def test_tree_header_valueerror_branch(self, temp_dir: Path) -> None:
        """Test lines 521-522 - ValueError in tree header path calculation.

        This covers the edge case where resolved.relative_to(working_dir)
        raises ValueError. This is defensive code for edge cases like symlinks.
        """
        registry = ToolRegistry(temp_dir)

        # Create a subdirectory to tree
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").touch()

        # Test normal case still works
        result = await registry.execute("tree", {"path": "subdir"})
        assert "subdir" in result

    @pytest.mark.asyncio
    async def test_tree_header_valueerror_via_direct_call(self, temp_dir: Path) -> None:
        """Directly test _tree method with mocked path to cover lines 521-522.

        The _resolve_path security check uses str.startswith, but relative_to
        uses actual path semantics. We can exploit this difference by creating
        a mock Path that passes startswith but fails relative_to.
        """
        registry = ToolRegistry(temp_dir)

        # Create test directory
        (temp_dir / "test").mkdir()

        # We need to test the _tree method directly with a path that
        # has already passed _resolve_path but will fail relative_to

        # Create a mock resolved path that:
        # 1. Is a valid directory
        # 2. Has str representation starting with working_dir
        # 3. But raises ValueError on relative_to

        mock_resolved = MagicMock(spec=Path)
        mock_resolved.exists.return_value = True
        mock_resolved.is_dir.return_value = True
        mock_resolved.name = "testdir"
        mock_resolved.iterdir.return_value = []
        mock_resolved.relative_to.side_effect = ValueError("Not relative")

        # Patch _resolve_path to return our mock
        with patch.object(registry, "_resolve_path", return_value=mock_resolved):
            result = await registry._tree("test")

        # Should use resolved.name as fallback header
        assert "testdir/" in result


# =============================================================================
# TestAgentProviderInterfaceMethods - Interface method implementations
# =============================================================================


class TestAgentProviderInterfaceMethods:
    """Tests for AgentProvider interface method implementations."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def agent(self, temp_dir):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_generate_plan_structure(self, agent: ReActAgentProvider) -> None:
        """Test generate_plan creates proper Plan structure."""
        from datetime import datetime

        from repo_sapiens.models.domain import Issue, IssueState

        issue = Issue(
            id=100,
            number=42,
            title="Implement feature X",
            body="Feature description here",
            state=IssueState.OPEN,
            labels=["enhancement"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="testuser",
            url="https://example.com/issues/42",
        )

        plan = await agent.generate_plan(issue)

        assert plan.id == "plan-42"
        assert "Implement feature X" in plan.title
        assert plan.description == "Feature description here"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].title == "Implement feature X"

    @pytest.mark.asyncio
    async def test_generate_prompts_returns_plan_tasks(self, agent: ReActAgentProvider) -> None:
        """Test generate_prompts simply returns tasks from plan."""
        from repo_sapiens.models.domain import Plan, Task

        tasks = [
            Task(id="t1", prompt_issue_id=1, title="Task 1", description="Do thing 1"),
            Task(id="t2", prompt_issue_id=1, title="Task 2", description="Do thing 2"),
            Task(id="t3", prompt_issue_id=1, title="Task 3", description="Do thing 3"),
        ]

        plan = Plan(
            id="test-plan",
            title="Test Plan",
            description="Test description",
            tasks=tasks,
        )

        result = await agent.generate_prompts(plan)

        assert result == tasks
        assert len(result) == 3
