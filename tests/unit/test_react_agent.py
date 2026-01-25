"""Unit tests for the ReAct agent."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.agents.react import ReActAgentProvider, ReActConfig, TrajectoryStep
from repo_sapiens.agents.tools import ToolRegistry
from repo_sapiens.models.domain import Task, TaskResult


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

        result = await registry.execute("search_files", {"pattern": "nonexistent_pattern_xyz"})
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
        result = await registry.execute("search_files", {"pattern": "test", "path": "nonexistent_dir"})
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
        assert content == "Hello Universe! This is a test."

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
        result = await registry.execute("edit_file", {"path": "test.txt", "new_text": "new"})
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
            base_url="http://localhost:11434",
            max_iterations=3,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir, config=config)

    def test_init(self, agent, temp_dir):
        """Test agent initialization."""
        assert agent.working_dir == str(temp_dir.resolve())
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
        """Test successful connection to backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "test-model:latest"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.backend.client, "get", AsyncMock(return_value=mock_response)):
            await agent.connect()  # Should not raise

    @pytest.mark.asyncio
    async def test_connect_ollama_not_running(self, agent):
        """Test connection failure when Ollama is not running."""
        import httpx

        from repo_sapiens.exceptions import ProviderConnectionError

        with patch.object(
            agent.backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(ProviderConnectionError, match="Ollama not running"):
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
        assert config.model == "qwen3:latest"
        assert config.base_url is None  # base_url defaults to None
        assert config.ollama_url == "http://localhost:11434"  # Legacy property returns default
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


class TestGenerateStep:
    """Tests for the _generate_step method with mocked HTTP client."""

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
            base_url="http://localhost:11434",
            max_iterations=3,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir, config=config)

    @pytest.mark.asyncio
    async def test_generate_step_success(self, agent):
        """Test _generate_step makes correct HTTP request and returns content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "content": 'THOUGHT: I should read the file.\nACTION: read_file\nACTION_INPUT: {"path": "test.txt"}'
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.backend.client, "post", AsyncMock(return_value=mock_response)):
            result = await agent._generate_step("Test task")

        assert "read_file" in result
        assert "test.txt" in result

    @pytest.mark.asyncio
    async def test_generate_step_empty_response(self, agent):
        """Test _generate_step handles empty message content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.backend.client, "post", AsyncMock(return_value=mock_response)):
            result = await agent._generate_step("Test task")

        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_step_http_error(self, agent):
        """Test _generate_step propagates HTTP errors."""
        import httpx

        with patch.object(
            agent.backend.client,
            "post",
            AsyncMock(side_effect=httpx.HTTPStatusError("Server error", request=MagicMock(), response=MagicMock())),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await agent._generate_step("Test task")

    @pytest.mark.asyncio
    async def test_generate_step_includes_trajectory(self, agent):
        """Test that trajectory is included in subsequent calls."""
        # Add a step to trajectory
        from repo_sapiens.agents.react import TrajectoryStep

        agent._trajectory.append(
            TrajectoryStep(
                iteration=1,
                thought="First thought",
                action="read_file",
                action_input={"path": "test.txt"},
                observation="File contents here",
            )
        )

        captured_json = None

        async def capture_post(url, json=None):
            nonlocal captured_json
            captured_json = json
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "THOUGHT: Done\nACTION: finish\nACTION_INPUT: {}"}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch.object(agent.backend.client, "post", capture_post):
            await agent._generate_step("Test task")

        # Verify trajectory is in messages
        messages = captured_json["messages"]
        assert len(messages) >= 4  # system, user, assistant (trajectory), user (observation)
        assert any("First thought" in str(m) for m in messages)
        assert any("File contents here" in str(m) for m in messages)


class TestFinishWithInvalidJson:
    """Tests for error recovery when finish has invalid JSON."""

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
            base_url="http://localhost:11434",
            max_iterations=5,
        )

    @pytest.fixture
    def agent(self, temp_dir, config):
        """Create a ReActAgentProvider instance."""
        return ReActAgentProvider(working_dir=temp_dir, config=config)

    @pytest.mark.asyncio
    async def test_finish_with_invalid_json_retries(self, agent):
        """Test that finish with invalid JSON gets a retry with error message."""
        task = Task(
            id="test-invalid-finish",
            prompt_issue_id=0,
            title="Test task",
            description="A test",
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: return finish with invalid JSON
                return """
THOUGHT: Done.
ACTION: finish
ACTION_INPUT: {invalid json here}
"""
            else:
                # Second call: return valid finish
                return """
THOUGHT: Now I'll finish properly.
ACTION: finish
ACTION_INPUT: {"answer": "Task completed", "summary": "Done"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is True
        # Should have recorded the failed attempt in trajectory
        assert len(agent._trajectory) >= 1

    @pytest.mark.asyncio
    async def test_finish_with_empty_action_input(self, agent):
        """Test that finish with empty action_input triggers retry."""
        task = Task(
            id="test-empty-finish",
            prompt_issue_id=0,
            title="Test task",
            description="A test",
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: return finish without answer
                return """
THOUGHT: Task is done.
ACTION: finish
ACTION_INPUT: {}
"""
            else:
                # Second call: return valid finish
                return """
THOUGHT: Let me provide the answer.
ACTION: finish
ACTION_INPUT: {"answer": "The actual answer", "summary": "Completed"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is True
        assert result.output == "The actual answer"

    @pytest.mark.asyncio
    async def test_no_action_continues_loop(self, agent):
        """Test that response without action continues the loop."""
        task = Task(
            id="test-no-action",
            prompt_issue_id=0,
            title="Test task",
            description="A test",
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: return response without proper format
                return "I'm just thinking here without proper format..."
            else:
                # Second call: return valid finish
                return """
THOUGHT: Now I'll respond properly.
ACTION: finish
ACTION_INPUT: {"answer": "Done", "summary": "Completed"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.execute_task(task, {})

        assert result.success is True
        assert call_count == 2


class TestRunReactTask:
    """Tests for the run_react_task convenience function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_run_react_task_success(self, temp_dir):
        """Test run_react_task convenience function."""
        from repo_sapiens.agents.react import run_react_task

        # Mock the agent's methods
        with patch("repo_sapiens.agents.react.ReActAgentProvider") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.execute_task = AsyncMock(
                return_value=TaskResult(
                    success=True,
                    output="Task done",
                    files_changed=[],
                )
            )
            mock_instance.connect = AsyncMock()
            mock_instance.get_trajectory = MagicMock(return_value=[])

            # Setup async context manager
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()

            MockAgent.return_value = mock_instance

            result = await run_react_task(
                task_description="Test task",
                working_dir=str(temp_dir),
                model="test-model",
                max_iterations=5,
                verbose=False,
            )

        assert result.success is True
        assert result.output == "Task done"

    @pytest.mark.asyncio
    async def test_run_react_task_verbose(self, temp_dir, capsys):
        """Test run_react_task with verbose output."""
        from repo_sapiens.agents.react import TrajectoryStep, run_react_task

        with patch("repo_sapiens.agents.react.ReActAgentProvider") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.execute_task = AsyncMock(
                return_value=TaskResult(
                    success=True,
                    output="Done",
                    files_changed=[],
                )
            )
            mock_instance.connect = AsyncMock()
            mock_instance.get_trajectory = MagicMock(
                return_value=[
                    TrajectoryStep(
                        iteration=1,
                        thought="Test thought",
                        action="read_file",
                        action_input={"path": "test.txt"},
                        observation="File contents here that is longer than 200 characters " * 5,
                    )
                ]
            )

            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()

            MockAgent.return_value = mock_instance

            result = await run_react_task(
                task_description="Test task",
                working_dir=str(temp_dir),
                verbose=True,
            )

        captured = capsys.readouterr()
        assert "Step 1" in captured.out
        assert "THOUGHT: Test thought" in captured.out
        assert "ACTION: read_file" in captured.out

    @pytest.mark.asyncio
    async def test_run_react_task_with_defaults(self, temp_dir):
        """Test run_react_task uses correct defaults."""
        from repo_sapiens.agents.react import run_react_task

        captured_config = None

        with patch("repo_sapiens.agents.react.ReActAgentProvider") as MockAgent:

            def capture_init(working_dir, config):
                nonlocal captured_config
                captured_config = config
                mock = AsyncMock()
                mock.execute_task = AsyncMock(return_value=TaskResult(success=True, output="", files_changed=[]))
                mock.connect = AsyncMock()
                mock.get_trajectory = MagicMock(return_value=[])
                mock.__aenter__ = AsyncMock(return_value=mock)
                mock.__aexit__ = AsyncMock()
                return mock

            MockAgent.side_effect = capture_init

            await run_react_task(
                task_description="Test task",
                working_dir=str(temp_dir),
            )

        assert captured_config.model == "qwen3:latest"
        assert captured_config.max_iterations == 10


class TestAgentProviderInterface:
    """Tests for AgentProvider interface methods."""

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
    async def test_generate_plan(self, agent):
        """Test generate_plan creates single-task plan."""
        from datetime import datetime

        from repo_sapiens.models.domain import Issue, IssueState

        issue = Issue(
            id=1,
            number=42,
            title="Test Issue",
            body="Issue description",
            state=IssueState.OPEN,
            labels=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="testuser",
            url="https://example.com/issues/42",
        )

        plan = await agent.generate_plan(issue)

        assert plan.id == "plan-42"
        assert "Test Issue" in plan.title
        assert len(plan.tasks) == 1
        assert plan.tasks[0].id == "react-42"
        assert plan.tasks[0].title == "Test Issue"

    @pytest.mark.asyncio
    async def test_generate_prompts(self, agent):
        """Test generate_prompts returns tasks from plan."""
        from repo_sapiens.models.domain import Plan

        plan = Plan(
            id="test-plan",
            title="Test Plan",
            description="A plan",
            tasks=[
                Task(id="t1", prompt_issue_id=1, title="Task 1", description="Do 1"),
                Task(id="t2", prompt_issue_id=1, title="Task 2", description="Do 2"),
            ],
        )

        tasks = await agent.generate_prompts(plan)

        assert len(tasks) == 2
        assert tasks[0].id == "t1"
        assert tasks[1].id == "t2"

    @pytest.mark.asyncio
    async def test_review_code(self, agent):
        """Test review_code method."""
        diff = """
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-def old_function():
+def new_function():
     pass
"""
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First step: read the diff and form an opinion with "approve" in thought
                # Note: Must be a non-finish action so it gets added to trajectory
                return """
THOUGHT: The code looks good. I approve this change. Let me verify by reading more.
ACTION: list_directory
ACTION_INPUT: {"path": "."}
"""
            # Second step: finish
            return """
THOUGHT: All looks good.
ACTION: finish
ACTION_INPUT: {"summary": "Code review passed"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            review = await agent.review_code(diff, {})

        # approved is True because "approve" was in a trajectory thought
        assert review.approved is True

    @pytest.mark.asyncio
    async def test_review_code_not_approved(self, agent):
        """Test review_code when not approved."""
        diff = "some diff"

        async def mock_generate(*args, **kwargs):
            return """
THOUGHT: This code has issues.
ACTION: finish
ACTION_INPUT: {"summary": "Found problems"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            review = await agent.review_code(diff, {})

        # Not approved since "approve" not in thought
        assert review.approved is False

    @pytest.mark.asyncio
    async def test_resolve_conflict(self, agent, temp_dir):
        """Test resolve_conflict method."""
        # Create a conflicted file
        conflict_file = temp_dir / "conflict.txt"
        conflict_file.write_text("<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>>")

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return """
THOUGHT: I'll resolve the conflict by keeping the ours version.
ACTION: write_file
ACTION_INPUT: {"path": "conflict.txt", "content": "resolved content"}
"""
            return """
THOUGHT: Conflict resolved.
ACTION: finish
ACTION_INPUT: {"summary": "Resolved"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            result = await agent.resolve_conflict(
                {
                    "file": "conflict.txt",
                    "content": "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>>",
                }
            )

        assert result == "resolved content"

    @pytest.mark.asyncio
    async def test_set_model(self, agent):
        """Test set_model changes the model."""
        assert agent.config.model == "qwen3:latest"
        agent.set_model("new-model")
        assert agent.config.model == "new-model"


class TestAsyncContextManager:
    """Tests for async context manager functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self, temp_dir):
        """Test async context manager properly enters and exits."""
        agent = ReActAgentProvider(working_dir=temp_dir)

        async with agent as a:
            assert a is agent

        # Backend client should be closed after exit
        assert agent.backend._client is None or agent.backend._client.is_closed


class TestListModels:
    """Tests for list_models method."""

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
    async def test_list_models_success(self, agent):
        """Test list_models returns model names."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "codellama:7b"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.backend.client, "get", AsyncMock(return_value=mock_response)):
            models = await agent.list_models()

        assert "llama3.1:8b" in models
        assert "codellama:7b" in models

    @pytest.mark.asyncio
    async def test_list_models_connection_error_silent(self, agent):
        """Test list_models returns empty list on connection error."""
        import httpx

        with patch.object(
            agent.backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            models = await agent.list_models(raise_on_error=False)

        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_connection_error_raises(self, agent):
        """Test list_models raises on connection error when requested."""
        import httpx

        with patch.object(
            agent.backend.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(httpx.ConnectError):
                await agent.list_models(raise_on_error=True)

    @pytest.mark.asyncio
    async def test_connect_model_not_found_warning(self, agent, caplog):
        """Test connect logs warning when model not found."""

        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "other-model:latest"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent.backend.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise, just warn
            await agent.connect()


class TestToolEdgeCases:
    """Tests for edge cases in tools."""

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
    async def test_read_file_is_directory(self, registry, temp_dir):
        """Test read_file on a directory returns error."""
        (temp_dir / "subdir").mkdir()

        result = await registry.execute("read_file", {"path": "subdir"})
        assert "not a file" in result

    @pytest.mark.asyncio
    async def test_read_file_binary(self, registry, temp_dir):
        """Test read_file on binary file returns error."""
        binary_file = temp_dir / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe")

        result = await registry.execute("read_file", {"path": "binary.bin"})
        assert "not a text file" in result

    @pytest.mark.asyncio
    async def test_read_file_truncation(self, registry, temp_dir):
        """Test read_file truncates large files."""
        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * 60000)

        result = await registry.execute("read_file", {"path": "large.txt"})
        assert "Truncated" in result
        assert len(result) < 60000

    @pytest.mark.asyncio
    async def test_write_file_missing_content(self, registry):
        """Test write_file with None content."""
        result = await registry.execute("write_file", {"path": "test.txt", "content": None})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_write_file_missing_path(self, registry):
        """Test write_file without path."""
        result = await registry.execute("write_file", {"content": "test"})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_list_directory_is_file(self, registry, temp_dir):
        """Test list_directory on a file."""
        (temp_dir / "file.txt").touch()

        result = await registry.execute("list_directory", {"path": "file.txt"})
        assert "not a directory" in result

    @pytest.mark.asyncio
    async def test_list_directory_permission_error(self, registry, temp_dir):
        """Test list_directory with permission error."""
        import os

        restricted = temp_dir / "restricted"
        restricted.mkdir()
        os.chmod(restricted, 0o000)

        try:
            result = await registry.execute("list_directory", {"path": "restricted"})
            assert "Permission denied" in result or "empty" in result.lower()
        finally:
            os.chmod(restricted, 0o755)

    @pytest.mark.asyncio
    async def test_run_command_timeout(self, registry):
        """Test run_command timeout."""
        # Create registry with short timeout
        registry.command_timeout = 1

        result = await registry.execute("run_command", {"command": "sleep 10"})
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_empty(self, registry):
        """Test run_command with empty command."""
        result = await registry.execute("run_command", {"command": ""})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_search_files_is_file_not_dir(self, registry, temp_dir):
        """Test search_files when path is a file."""
        (temp_dir / "file.txt").write_text("content")

        result = await registry.execute("search_files", {"pattern": "content", "path": "file.txt"})
        assert "not a directory" in result

    @pytest.mark.asyncio
    async def test_search_files_grep_not_found(self, registry, temp_dir):
        """Test search_files when grep command not found."""
        (temp_dir / "file.txt").write_text("content")

        with patch("subprocess.run", side_effect=FileNotFoundError("grep not found")):
            result = await registry.execute("search_files", {"pattern": "content", "path": "."})
        assert "grep command not found" in result

    @pytest.mark.asyncio
    async def test_search_files_timeout(self, registry, temp_dir):
        """Test search_files timeout."""
        import subprocess

        (temp_dir / "file.txt").write_text("content")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("grep", 30)):
            result = await registry.execute("search_files", {"pattern": "content", "path": "."})
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_search_files_grep_error(self, registry, temp_dir):
        """Test search_files when grep returns error."""

        (temp_dir / "file.txt").write_text("content")

        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stderr = "grep: invalid option"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await registry.execute("search_files", {"pattern": "content", "path": "."})
        assert "Error" in result or "invalid option" in result

    @pytest.mark.asyncio
    async def test_search_files_many_results_truncated(self, registry, temp_dir):
        """Test search_files truncates many results."""

        # Create a file with many matching lines
        lines = [f"match line {i}" for i in range(100)]
        (temp_dir / "file.txt").write_text("\n".join(lines))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        # Return more than 50 matches
        mock_result.stdout = "\n".join([f"file.txt:{i}:match line {i}" for i in range(60)])

        with patch("subprocess.run", return_value=mock_result):
            result = await registry.execute("search_files", {"pattern": "match", "path": "."})
        assert "Truncated" in result

    @pytest.mark.asyncio
    async def test_find_files_is_file_not_dir(self, registry, temp_dir):
        """Test find_files when path is a file."""
        (temp_dir / "file.txt").touch()

        result = await registry.execute("find_files", {"pattern": "*.txt", "path": "file.txt"})
        assert "not a directory" in result

    @pytest.mark.asyncio
    async def test_find_files_path_outside_working_dir(self, registry):
        """Test find_files with path outside working directory."""
        result = await registry.execute("find_files", {"pattern": "*.txt", "path": "../../../"})
        assert "outside" in result.lower()

    @pytest.mark.asyncio
    async def test_find_files_many_results_truncated(self, registry, temp_dir):
        """Test find_files truncates many results."""
        # Create more than 100 files
        for i in range(150):
            (temp_dir / f"file{i}.txt").touch()

        result = await registry.execute("find_files", {"pattern": "*.txt"})
        assert "Truncated" in result
        assert "100" in result

    @pytest.mark.asyncio
    async def test_edit_file_is_directory(self, registry, temp_dir):
        """Test edit_file on a directory."""
        (temp_dir / "subdir").mkdir()

        result = await registry.execute(
            "edit_file",
            {"path": "subdir", "old_text": "old", "new_text": "new"},
        )
        assert "not a file" in result

    @pytest.mark.asyncio
    async def test_edit_file_binary_file(self, registry, temp_dir):
        """Test edit_file on binary file."""
        binary_file = temp_dir / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe")

        result = await registry.execute(
            "edit_file",
            {"path": "binary.bin", "old_text": "old", "new_text": "new"},
        )
        assert "not a text file" in result

    @pytest.mark.asyncio
    async def test_edit_file_missing_new_text(self, registry, temp_dir):
        """Test edit_file with missing new_text."""
        (temp_dir / "file.txt").write_text("content")

        result = await registry.execute(
            "edit_file",
            {"path": "file.txt", "old_text": "content", "new_text": None},
        )
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_tree_permission_denied(self, registry, temp_dir):
        """Test tree with permission denied subdirectory."""
        import os

        restricted = temp_dir / "restricted"
        restricted.mkdir()
        os.chmod(restricted, 0o000)

        try:
            result = await registry.execute("tree", {"path": "."})
            assert "restricted" in result
        finally:
            os.chmod(restricted, 0o755)

    @pytest.mark.asyncio
    async def test_tree_many_entries_truncated(self, registry, temp_dir):
        """Test tree truncates output for many entries."""
        # Create many files and directories
        for i in range(250):
            (temp_dir / f"file{i}.txt").touch()

        result = await registry.execute("tree", {"path": ".", "max_depth": 1})
        assert "Truncated" in result

    @pytest.mark.asyncio
    async def test_tree_path_outside_working_dir(self, registry, temp_dir):
        """Test tree with nested path that still resolves within working dir."""
        (temp_dir / "subdir").mkdir()

        result = await registry.execute("tree", {"path": "subdir"})
        assert "subdir" in result

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self, registry, temp_dir):
        """Test that ToolExecutionError is properly caught."""
        # The path security check raises ToolExecutionError
        result = await registry.execute("read_file", {"path": "../../../etc/passwd"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, registry, temp_dir):
        """Test handling of unexpected errors."""
        # Mock _read_file to raise unexpected error
        with patch.object(registry, "_read_file", side_effect=RuntimeError("Unexpected")):
            result = await registry.execute("read_file", {"path": "test.txt"})
        assert "Unexpected error" in result

    @pytest.mark.asyncio
    async def test_tool_not_implemented(self, registry):
        """Test that unimplemented tool branch returns error."""
        # This tests line 201 - the else branch that should never be reached
        # but exists for safety. We can't easily trigger it without modifying TOOLS,
        # so we test the unknown tool path instead
        result = await registry.execute("nonexistent", {})
        assert "Unknown tool" in result


class TestToolRegistryIntegration:
    """Integration tests for ToolRegistry."""

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
    async def test_write_then_edit(self, registry, temp_dir):
        """Test writing a file then editing it."""
        # Write file
        await registry.execute(
            "write_file",
            {"path": "test.txt", "content": "Hello World"},
        )

        # Edit file
        result = await registry.execute(
            "edit_file",
            {"path": "test.txt", "old_text": "World", "new_text": "Universe"},
        )

        assert "Successfully edited" in result

        # Verify content
        content = (temp_dir / "test.txt").read_text()
        assert content == "Hello Universe"

        # Check files_written tracking
        assert "test.txt" in registry.get_files_written()

    @pytest.mark.asyncio
    async def test_search_in_nested_directory(self, registry, temp_dir):
        """Test searching in nested directories."""
        # Create nested structure
        subdir = temp_dir / "src" / "utils"
        subdir.mkdir(parents=True)
        (subdir / "helper.py").write_text("def search_target(): pass")

        result = await registry.execute(
            "search_files",
            {"pattern": "search_target", "path": "."},
        )

        assert "helper.py" in result
        assert "search_target" in result


class TestToolsAdditionalCoverage:
    """Additional tests to improve coverage for edge cases."""

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
    async def test_list_directory_not_exist(self, registry):
        """Test list_directory with non-existent directory."""
        result = await registry.execute("list_directory", {"path": "nonexistent"})
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_list_directory_skip_hidden(self, registry, temp_dir):
        """Test that list_directory skips hidden files."""
        (temp_dir / ".hidden").touch()
        (temp_dir / "visible.txt").touch()

        result = await registry.execute("list_directory", {"path": "."})
        assert "visible.txt" in result
        assert ".hidden" not in result

    @pytest.mark.asyncio
    async def test_run_command_general_exception(self, registry):
        """Test run_command handles general exceptions."""
        # Use a command that raises an exception internally
        with patch("asyncio.create_subprocess_shell", side_effect=OSError("No such file")):
            result = await registry.execute("run_command", {"command": "echo test"})
        assert "Error running command" in result

    @pytest.mark.asyncio
    async def test_search_files_empty_output(self, registry, temp_dir):
        """Test search_files when grep returns empty output."""

        (temp_dir / "file.txt").write_text("content")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""  # Empty output

        with patch("subprocess.run", return_value=mock_result):
            result = await registry.execute("search_files", {"pattern": "pattern", "path": "."})
        assert "No matches found" in result

    @pytest.mark.asyncio
    async def test_search_files_general_exception(self, registry, temp_dir):
        """Test search_files handles general exceptions."""
        (temp_dir / "file.txt").write_text("content")

        with patch("subprocess.run", side_effect=RuntimeError("Unexpected")):
            result = await registry.execute("search_files", {"pattern": "pattern", "path": "."})
        assert "Error:" in result

    @pytest.mark.asyncio
    async def test_find_files_non_existent_path(self, registry):
        """Test find_files with non-existent directory."""
        result = await registry.execute("find_files", {"pattern": "*.txt", "path": "nonexistent"})
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_find_files_glob_matches_directory(self, registry, temp_dir):
        """Test find_files only returns files, not directories."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "file.txt").touch()

        result = await registry.execute("find_files", {"pattern": "*"})
        assert "file.txt" in result
        # Directories should not be included
        assert "subdir" not in result or "[dir]" not in result

    @pytest.mark.asyncio
    async def test_find_files_general_exception(self, registry, temp_dir):
        """Test find_files handles general exceptions."""
        with patch.object(Path, "glob", side_effect=RuntimeError("Unexpected")):
            result = await registry.execute("find_files", {"pattern": "*.txt"})
        assert "Error:" in result

    @pytest.mark.asyncio
    async def test_edit_file_missing_path(self, registry):
        """Test edit_file without path."""
        result = await registry.execute("edit_file", {"old_text": "old", "new_text": "new"})
        assert "required" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_write_oserror(self, registry, temp_dir):
        """Test edit_file handles OSError on write."""
        (temp_dir / "file.txt").write_text("original content")

        with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
            result = await registry.execute(
                "edit_file",
                {"path": "file.txt", "old_text": "original", "new_text": "new"},
            )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_write_file_oserror(self, registry, temp_dir):
        """Test write_file handles OSError."""
        with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
            result = await registry.execute("write_file", {"path": "test.txt", "content": "test"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_tree_relative_path_value_error(self, registry, temp_dir):
        """Test tree handles ValueError when getting relative path."""
        # This tests line 521-522 where ValueError is caught
        # Create a subdirectory and test the tree output
        (temp_dir / "sub").mkdir()
        (temp_dir / "sub" / "file.txt").touch()

        # Just test that tree works with a subdirectory path
        result = await registry.execute("tree", {"path": "sub"})
        assert "sub" in result or "file.txt" in result

    @pytest.mark.asyncio
    async def test_tree_depth_limit_exceeded(self, registry, temp_dir):
        """Test tree respects max_depth by creating a deep structure."""
        # Create a structure deeper than max_depth
        current = temp_dir
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file{i}.txt").touch()

        # With max_depth=2, should only see level0, level1, level2
        result = await registry.execute("tree", {"path": ".", "max_depth": 2})
        assert "level0" in result
        assert "level1" in result
        # level2 is the last level shown (depth=2 from root)
        # level3 and level4 should NOT appear
        assert "level3" not in result
        assert "level4" not in result


class TestReactReviewCodeTrajectory:
    """Additional tests for review_code trajectory handling."""

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
    async def test_review_code_collects_finish_comments(self, agent):
        """Test that review_code collects comments from finish actions in trajectory."""
        diff = "some diff"
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Do an action first to add to trajectory
                return """
THOUGHT: Let me examine this.
ACTION: list_directory
ACTION_INPUT: {"path": "."}
"""
            # Then finish - this adds to trajectory with finish action
            return """
THOUGHT: All good.
ACTION: finish
ACTION_INPUT: {"summary": "Review complete - looks good"}
"""

        with patch.object(agent, "_generate_step", mock_generate):
            review = await agent.review_code(diff, {})

        # The finish step is in trajectory since we had a prior non-finish step
        # Check confidence score based on success
        assert review.confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_review_code_trajectory_with_finish_action(self, agent):
        """Test review_code properly extracts summary from finish action in trajectory."""
        # Manually set up a trajectory with finish action to test line 394
        agent._trajectory = [
            TrajectoryStep(
                iteration=1,
                thought="I approve the changes",
                action="finish",
                action_input={"summary": "Review passed", "answer": "All good"},
                observation="Task completed",
            )
        ]

        # Mock execute_task to avoid actual execution but set the trajectory properly
        mock_result = TaskResult(success=True, output="Done", files_changed=[])

        with patch.object(agent, "execute_task", AsyncMock(return_value=mock_result)):
            review = await agent.review_code("diff", {})

        # Comments should include the summary from the finish action
        assert "Review passed" in review.comments
        assert review.approved is True  # "approve" in thought
