"""Unit tests for the ReAct agent."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from automation.agents.react import ReActAgentProvider, ReActConfig, TrajectoryStep
from automation.agents.tools import ToolExecutionError, ToolRegistry
from automation.models.domain import Task


class TestToolRegistry:
    """Tests for the ToolRegistry class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def registry(self, temp_dir):
        """Create a ToolRegistry instance."""
        return ToolRegistry(temp_dir)

    def test_get_tool_descriptions(self, registry):
        """Test that tool descriptions are formatted correctly."""
        desc = registry.get_tool_descriptions()
        assert "read_file" in desc
        assert "write_file" in desc
        assert "list_directory" in desc
        assert "run_command" in desc
        assert "finish" in desc
        assert "search_files" in desc
        assert "find_files" in desc
        assert "edit_file" in desc
        assert "tree" in desc

    @pytest.mark.asyncio
    async def test_read_file_success(self, registry, temp_dir):
        """Test reading an existing file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = await registry.execute("read_file", {"path": "test.txt"})
        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, registry):
        """Test reading a non-existent file."""
        result = await registry.execute("read_file", {"path": "nonexistent.txt"})
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_read_file_missing_path(self, registry):
        """Test reading without path parameter."""
        result = await registry.execute("read_file", {})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_write_file_success(self, registry, temp_dir):
        """Test writing a file."""
        result = await registry.execute(
            "write_file",
            {"path": "new_file.txt", "content": "Test content"},
        )
        assert "Successfully wrote" in result

        # Verify file was written
        written = (temp_dir / "new_file.txt").read_text()
        assert written == "Test content"

        # Verify tracking
        assert "new_file.txt" in registry.get_files_written()

    @pytest.mark.asyncio
    async def test_write_file_creates_directories(self, registry, temp_dir):
        """Test that write_file creates parent directories."""
        result = await registry.execute(
            "write_file",
            {"path": "subdir/nested/file.txt", "content": "Nested content"},
        )
        assert "Successfully wrote" in result
        assert (temp_dir / "subdir" / "nested" / "file.txt").exists()

    @pytest.mark.asyncio
    async def test_list_directory_success(self, registry, temp_dir):
        """Test listing directory contents."""
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "subdir").mkdir()

        result = await registry.execute("list_directory", {"path": "."})
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "subdir" in result

    @pytest.mark.asyncio
    async def test_list_directory_empty(self, registry, temp_dir):
        """Test listing empty directory."""
        (temp_dir / "empty").mkdir()
        result = await registry.execute("list_directory", {"path": "empty"})
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_success(self, registry):
        """Test running a simple command."""
        result = await registry.execute("run_command", {"command": "echo hello"})
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_run_command_with_error(self, registry):
        """Test running a command that fails."""
        result = await registry.execute(
            "run_command",
            {"command": "ls /nonexistent_directory_12345"},
        )
        assert "Exit code" in result or "error" in result.lower() or "stderr" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_allowed_list(self, temp_dir):
        """Test command allowlist enforcement."""
        registry = ToolRegistry(temp_dir, allowed_commands=["echo", "ls"])

        # Allowed command
        result = await registry.execute("run_command", {"command": "echo test"})
        assert "test" in result

        # Disallowed command
        result = await registry.execute("run_command", {"command": "rm -rf /"})
        assert "not allowed" in result.lower()

    @pytest.mark.asyncio
    async def test_finish_tool(self, registry):
        """Test the finish tool."""
        result = await registry.execute("finish", {"summary": "Task complete"})
        assert "Task complete" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self, registry):
        """Test calling an unknown tool."""
        result = await registry.execute("unknown_tool", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_path_security(self, temp_dir):
        """Test that paths outside working directory are rejected."""
        registry = ToolRegistry(temp_dir)

        result = await registry.execute("read_file", {"path": "../../../etc/passwd"})
        assert "outside working directory" in result.lower() or "error" in result.lower()

    def test_reset(self, registry, temp_dir):
        """Test resetting the registry state."""
        registry.files_written = ["file1.txt", "file2.txt"]
        registry.reset()
        assert registry.files_written == []

    # ==================== search_files tests ====================

    @pytest.mark.asyncio
    async def test_search_files_success(self, registry, temp_dir):
        """Test searching for a pattern in files."""
        # Create test files
        (temp_dir / "file1.py").write_text("def hello():\n    print('hello world')\n")
        (temp_dir / "file2.py").write_text("def goodbye():\n    print('goodbye')\n")

        result = await registry.execute("search_files", {"pattern": "hello"})
        assert "file1.py" in result
        assert "hello" in result
        # Should include line numbers
        assert ":" in result

    @pytest.mark.asyncio
    async def test_search_files_no_matches(self, registry, temp_dir):
        """Test searching when no matches exist."""
        (temp_dir / "test.txt").write_text("nothing special here")

        result = await registry.execute(
            "search_files", {"pattern": "nonexistent_pattern_xyz"}
        )
        assert "No matches found" in result

    @pytest.mark.asyncio
    async def test_search_files_with_file_pattern(self, registry, temp_dir):
        """Test searching with file pattern filter."""
        (temp_dir / "code.py").write_text("target_string in python")
        (temp_dir / "data.txt").write_text("target_string in text")

        result = await registry.execute(
            "search_files",
            {"pattern": "target_string", "path": ".", "file_pattern": "*.py"},
        )
        assert "code.py" in result
        # The txt file should not be in results when filtering by *.py
        # (grep --include handles this)

    @pytest.mark.asyncio
    async def test_search_files_missing_pattern(self, registry):
        """Test search_files without pattern parameter."""
        result = await registry.execute("search_files", {})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_search_files_invalid_path(self, registry):
        """Test search_files with non-existent path."""
        result = await registry.execute(
            "search_files", {"pattern": "test", "path": "nonexistent_dir"}
        )
        assert "does not exist" in result

    # ==================== find_files tests ====================

    @pytest.mark.asyncio
    async def test_find_files_success(self, registry, temp_dir):
        """Test finding files by glob pattern."""
        (temp_dir / "file1.py").touch()
        (temp_dir / "file2.py").touch()
        (temp_dir / "data.txt").touch()

        result = await registry.execute("find_files", {"pattern": "*.py"})
        assert "file1.py" in result
        assert "file2.py" in result
        assert "data.txt" not in result

    @pytest.mark.asyncio
    async def test_find_files_recursive(self, registry, temp_dir):
        """Test finding files recursively."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "root.py").touch()
        (subdir / "nested.py").touch()

        result = await registry.execute("find_files", {"pattern": "**/*.py"})
        assert "root.py" in result
        assert "nested.py" in result

    @pytest.mark.asyncio
    async def test_find_files_no_matches(self, registry, temp_dir):
        """Test find_files when no files match."""
        (temp_dir / "file.txt").touch()

        result = await registry.execute("find_files", {"pattern": "*.xyz"})
        assert "No files found" in result

    @pytest.mark.asyncio
    async def test_find_files_missing_pattern(self, registry):
        """Test find_files without pattern parameter."""
        result = await registry.execute("find_files", {})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_find_files_skips_hidden(self, registry, temp_dir):
        """Test that find_files skips hidden files."""
        (temp_dir / ".hidden_file.py").touch()
        (temp_dir / "visible.py").touch()

        result = await registry.execute("find_files", {"pattern": "*.py"})
        assert "visible.py" in result
        assert ".hidden_file.py" not in result

    # ==================== edit_file tests ====================

    @pytest.mark.asyncio
    async def test_edit_file_success(self, registry, temp_dir):
        """Test successful file edit."""
        test_file = temp_dir / "edit_me.txt"
        test_file.write_text("Hello World! This is a test.")

        result = await registry.execute(
            "edit_file",
            {"path": "edit_me.txt", "old_text": "World", "new_text": "Universe"},
        )
        assert "Successfully edited" in result

        # Verify the change
        content = test_file.read_text()
        assert "Hello Universe! This is a test." == content

        # Verify tracking
        assert "edit_me.txt" in registry.get_files_written()

    @pytest.mark.asyncio
    async def test_edit_file_text_not_found(self, registry, temp_dir):
        """Test edit_file when old_text is not in file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Original content")

        result = await registry.execute(
            "edit_file",
            {"path": "test.txt", "old_text": "nonexistent", "new_text": "new"},
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_not_unique(self, registry, temp_dir):
        """Test edit_file when old_text appears multiple times."""
        test_file = temp_dir / "duplicate.txt"
        test_file.write_text("word word word")

        result = await registry.execute(
            "edit_file",
            {"path": "duplicate.txt", "old_text": "word", "new_text": "term"},
        )
        assert "3 times" in result or "multiple" in result.lower() or "unique" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_file_not_found(self, registry):
        """Test edit_file with non-existent file."""
        result = await registry.execute(
            "edit_file",
            {"path": "nonexistent.txt", "old_text": "old", "new_text": "new"},
        )
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_edit_file_missing_parameters(self, registry, temp_dir):
        """Test edit_file with missing parameters."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        # Missing old_text
        result = await registry.execute(
            "edit_file", {"path": "test.txt", "new_text": "new"}
        )
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_path_security(self, temp_dir):
        """Test that edit_file rejects paths outside working directory."""
        registry = ToolRegistry(temp_dir)

        result = await registry.execute(
            "edit_file",
            {"path": "../../../etc/passwd", "old_text": "old", "new_text": "new"},
        )
        assert "outside working directory" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_empty_replacement(self, registry, temp_dir):
        """Test edit_file can replace text with empty string (deletion)."""
        test_file = temp_dir / "delete_text.txt"
        test_file.write_text("Keep this. Remove this part. Keep this too.")

        result = await registry.execute(
            "edit_file",
            {"path": "delete_text.txt", "old_text": " Remove this part.", "new_text": ""},
        )
        assert "Successfully edited" in result

        content = test_file.read_text()
        assert content == "Keep this. Keep this too."

    # ==================== tree tests ====================

    @pytest.mark.asyncio
    async def test_tree_success(self, registry, temp_dir):
        """Test tree display of directory structure."""
        # Create directory structure
        (temp_dir / "file1.txt").touch()
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file2.txt").touch()

        result = await registry.execute("tree", {"path": "."})
        assert "file1.txt" in result
        assert "subdir" in result
        assert "file2.txt" in result
        # Should show tree characters
        assert "├" in result or "└" in result

    @pytest.mark.asyncio
    async def test_tree_with_depth_limit(self, registry, temp_dir):
        """Test tree with max_depth parameter."""
        # Create nested structure
        (temp_dir / "level1").mkdir()
        (temp_dir / "level1" / "level2").mkdir()
        (temp_dir / "level1" / "level2" / "level3").mkdir()
        (temp_dir / "level1" / "level2" / "level3" / "deep.txt").touch()

        result = await registry.execute("tree", {"path": ".", "max_depth": 1})
        assert "level1" in result
        # level2 should not appear because max_depth=1
        assert "level2" not in result

    @pytest.mark.asyncio
    async def test_tree_skips_hidden(self, registry, temp_dir):
        """Test that tree skips hidden files and directories."""
        (temp_dir / ".hidden_dir").mkdir()
        (temp_dir / ".hidden_file").touch()
        (temp_dir / "visible.txt").touch()

        result = await registry.execute("tree", {"path": "."})
        assert "visible.txt" in result
        assert ".hidden" not in result

    @pytest.mark.asyncio
    async def test_tree_invalid_path(self, registry):
        """Test tree with non-existent path."""
        result = await registry.execute("tree", {"path": "nonexistent_dir"})
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_tree_on_file(self, registry, temp_dir):
        """Test tree when path is a file, not directory."""
        (temp_dir / "file.txt").touch()

        result = await registry.execute("tree", {"path": "file.txt"})
        assert "not a directory" in result

    @pytest.mark.asyncio
    async def test_tree_shows_type_indicators(self, registry, temp_dir):
        """Test that tree shows [dir] and [file] indicators."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "file.txt").touch()

        result = await registry.execute("tree", {"path": "."})
        assert "[dir]" in result
        assert "[file]" in result

    @pytest.mark.asyncio
    async def test_tree_default_depth(self, registry, temp_dir):
        """Test tree with default max_depth of 3."""
        # Create 4 levels deep
        current = temp_dir
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file{i}.txt").touch()

        result = await registry.execute("tree", {"path": "."})
        # Should show level0, level1, level2 (depth 0, 1, 2, 3)
        assert "level0" in result
        assert "level1" in result
        assert "level2" in result
        # level4 should not appear (beyond default max_depth=3)
        assert "level4" not in result


class TestReActAgentProvider:
    """Tests for the ReActAgentProvider class."""

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
            max_iterations=3,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir, config=config)

    def test_init(self, agent, temp_dir):
        """Test agent initialization."""
        assert agent.working_dir == temp_dir.resolve()
        assert agent.config.model == "test-model"
        assert agent.config.max_iterations == 3

    def test_parse_response_complete(self, agent):
        """Test parsing a complete ReAct response."""
        response = """
THOUGHT: I need to read the file to understand its contents.
ACTION: read_file
ACTION_INPUT: {"path": "README.md"}
"""
        thought, action, action_input = agent._parse_response(response)
        assert "read the file" in thought
        assert action == "read_file"
        assert action_input == {"path": "README.md"}

    def test_parse_response_finish(self, agent):
        """Test parsing a finish action."""
        response = """
THOUGHT: The task is complete.
ACTION: finish
ACTION_INPUT: {"summary": "Created the file successfully"}
"""
        thought, action, action_input = agent._parse_response(response)
        assert action == "finish"
        assert action_input["summary"] == "Created the file successfully"

    def test_parse_response_invalid_json(self, agent):
        """Test parsing with invalid JSON in ACTION_INPUT."""
        response = """
THOUGHT: Doing something.
ACTION: read_file
ACTION_INPUT: {invalid json}
"""
        thought, action, action_input = agent._parse_response(response)
        assert action == "read_file"
        assert action_input == {}  # Falls back to empty dict

    def test_parse_response_missing_parts(self, agent):
        """Test parsing with missing parts."""
        response = "Just some random text without proper formatting"
        thought, action, action_input = agent._parse_response(response)
        assert thought == ""
        assert action == ""
        assert action_input == {}

    @pytest.mark.asyncio
    async def test_execute_task_immediate_finish(self, agent, temp_dir):
        """Test task execution that finishes immediately."""
        task = Task(
            id="test-1",
            prompt_issue_id=0,
            title="Test task",
            description="A simple test",
        )

        # Mock the LLM to return finish immediately
        async def mock_generate(*args, **kwargs):
            return """
THOUGHT: This is a simple task, I'll complete it immediately.
ACTION: finish
ACTION_INPUT: {"summary": "Done"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_task_with_file_operations(self, agent, temp_dir):
        """Test task execution with file write then finish."""
        task = Task(
            id="test-2",
            prompt_issue_id=0,
            title="Create a file",
            description="Create hello.txt with 'Hello'",
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return """
THOUGHT: I need to create the file.
ACTION: write_file
ACTION_INPUT: {"path": "hello.txt", "content": "Hello"}
"""
            else:
                return """
THOUGHT: File created, task complete.
ACTION: finish
ACTION_INPUT: {"summary": "Created hello.txt"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is True
        assert "hello.txt" in result.files_changed
        assert (temp_dir / "hello.txt").read_text() == "Hello"

    @pytest.mark.asyncio
    async def test_execute_task_max_iterations(self, agent):
        """Test that max iterations is respected."""
        task = Task(
            id="test-3",
            prompt_issue_id=0,
            title="Endless task",
            description="This task never finishes",
        )

        async def mock_generate(*args, **kwargs):
            return """
THOUGHT: I'll just keep reading files forever.
ACTION: list_directory
ACTION_INPUT: {"path": "."}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is False
        assert "Max iterations" in result.error
        assert len(agent.get_trajectory()) == agent.config.max_iterations

    @pytest.mark.asyncio
    async def test_connect_success(self, agent):
        """Test successful connection to Ollama."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "test-model:latest"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.client, "get", AsyncMock(return_value=mock_response)):
            await agent.connect()  # Should not raise

    @pytest.mark.asyncio
    async def test_connect_ollama_not_running(self, agent):
        """Test connection failure when Ollama is not running."""
        import httpx

        with patch.object(
            agent.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(RuntimeError, match="Ollama not running"):
                await agent.connect()

    def test_trajectory_tracking(self, agent):
        """Test that trajectory is properly tracked."""
        step = TrajectoryStep(
            iteration=1,
            thought="Test thought",
            action="read_file",
            action_input={"path": "test.txt"},
            observation="File contents",
        )
        agent._trajectory = [step]

        trajectory = agent.get_trajectory()
        assert len(trajectory) == 1
        assert trajectory[0].thought == "Test thought"

        # Verify it's a copy
        trajectory.append(step)
        assert len(agent._trajectory) == 1


class TestReActConfig:
    """Tests for ReActConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = ReActConfig()
        assert config.model == "llama3.1:8b"
        assert config.ollama_url == "http://localhost:11434"
        assert config.max_iterations == 10
        assert config.temperature == 0.7
        assert config.timeout == 300

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ReActConfig(
            model="custom-model",
            max_iterations=5,
            temperature=0.5,
        )
        assert config.model == "custom-model"
        assert config.max_iterations == 5
        assert config.temperature == 0.5
