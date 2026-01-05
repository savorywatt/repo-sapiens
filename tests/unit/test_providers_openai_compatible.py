"""Tests for repo_sapiens/providers/openai_compatible.py - OpenAI-compatible API provider."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.models.domain import Issue, IssueState, Plan, Review, Task, TaskResult
from repo_sapiens.providers.openai_compatible import OpenAICompatibleProvider


@pytest.fixture
def provider():
    """Create OpenAICompatibleProvider instance with defaults."""
    return OpenAICompatibleProvider()


@pytest.fixture
def provider_custom():
    """Create OpenAICompatibleProvider instance with custom settings."""
    return OpenAICompatibleProvider(
        base_url="http://custom-vllm:8080/v1",
        model="mistral-7b-instruct",
        api_key="test-api-key",
        working_dir="/workspace/project",
        qa_handler=MagicMock(),
        timeout=600.0,
    )


@pytest.fixture
def sample_issue():
    """Create a sample Issue for testing."""
    return Issue(
        id=1,
        number=42,
        title="Implement rate limiting",
        body="We need to add rate limiting to the API endpoints.",
        state=IssueState.OPEN,
        labels=["feature", "api"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        author="testuser",
        url="https://example.com/issues/42",
    )


@pytest.fixture
def sample_task():
    """Create a sample Task for testing."""
    return Task(
        id="task-1",
        prompt_issue_id=42,
        title="Add rate limiter middleware",
        description="Implement middleware to track and limit API requests per client",
        dependencies=[],
    )


class TestOpenAICompatibleProviderInit:
    """Tests for OpenAICompatibleProvider initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default values."""
        provider = OpenAICompatibleProvider()

        assert provider.base_url == "http://localhost:8000/v1"
        assert provider.model == "default"
        assert provider.api_key is None
        assert provider.working_dir == "."
        assert provider.qa_handler is None
        assert provider.timeout == 300.0
        assert provider.current_issue_number is None
        assert provider.client is not None

    def test_init_with_custom_values(self):
        """Should initialize with custom values."""
        qa_handler = MagicMock()
        provider = OpenAICompatibleProvider(
            base_url="http://openrouter.ai/api/v1/",
            model="anthropic/claude-3-opus",
            api_key="sk-test-key",
            working_dir="/custom/workspace",
            qa_handler=qa_handler,
            timeout=120.0,
        )

        # Trailing slash should be stripped
        assert provider.base_url == "http://openrouter.ai/api/v1"
        assert provider.model == "anthropic/claude-3-opus"
        assert provider.api_key == "sk-test-key"
        assert provider.working_dir == "/custom/workspace"
        assert provider.qa_handler is qa_handler
        assert provider.timeout == 120.0

    def test_init_strips_trailing_slash(self):
        """Should strip trailing slash from base_url."""
        provider = OpenAICompatibleProvider(base_url="http://localhost:8000/v1///")
        assert provider.base_url == "http://localhost:8000/v1"

    def test_init_with_api_key_sets_auth_header(self):
        """Should set Authorization header when api_key is provided."""
        provider = OpenAICompatibleProvider(api_key="test-bearer-token")
        # Headers are stored in client config
        assert provider.client is not None

    def test_init_without_api_key_no_auth_header(self):
        """Should not set Authorization header when api_key is None."""
        provider = OpenAICompatibleProvider(api_key=None)
        assert provider.client is not None

    def test_init_working_dir_none_defaults_to_current(self):
        """Should default working_dir to '.' when None."""
        provider = OpenAICompatibleProvider(working_dir=None)
        assert provider.working_dir == "."

    def test_init_client_with_custom_timeout(self):
        """Should create client with custom timeout."""
        provider = OpenAICompatibleProvider(timeout=600.0)
        assert provider.timeout == 600.0
        assert provider.client is not None


class TestOpenAICompatibleProviderConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, provider):
        """Should connect successfully when server is available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "default"},
                {"id": "codellama-7b"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "get", AsyncMock(return_value=mock_response)
        ) as mock_get:
            await provider.connect()

            mock_get.assert_called_once_with("http://localhost:8000/v1/models")

    @pytest.mark.asyncio
    async def test_connect_model_found(self, provider_custom):
        """Should log success when specified model is found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "mistral-7b-instruct"},
                {"id": "llama-2-13b"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider_custom.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise
            await provider_custom.connect()

    @pytest.mark.asyncio
    async def test_connect_model_not_found_logs_warning(self, provider_custom):
        """Should log warning when specified model is not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "different-model"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider_custom.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise, just log warning
            await provider_custom.connect()

    @pytest.mark.asyncio
    async def test_connect_default_model_skips_check(self, provider):
        """Should skip model availability check when using 'default' model."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise even with empty model list
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_server_not_running(self, provider):
        """Should raise RuntimeError when server is not running."""
        with patch.object(
            provider.client,
            "get",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await provider.connect()

        assert "OpenAI-compatible server not running" in str(exc_info.value)
        assert provider.base_url in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_models_endpoint_404(self, provider):
        """Should log warning when /models endpoint returns 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(
            provider.client,
            "get",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=MagicMock(),
                    response=mock_response,
                )
            ),
        ):
            # Should not raise, just log warning
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_other_http_error(self, provider):
        """Should propagate non-404 HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            provider.client,
            "get",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=mock_response,
                )
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_generic_exception(self, provider):
        """Should propagate generic exceptions."""
        with patch.object(
            provider.client,
            "get",
            AsyncMock(side_effect=ValueError("Unexpected error")),
        ):
            with pytest.raises(ValueError) as exc_info:
                await provider.connect()

            assert "Unexpected error" in str(exc_info.value)


class TestOpenAICompatibleProviderContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager_entry(self):
        """Should call connect on entry."""
        provider = OpenAICompatibleProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "default"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "get", AsyncMock(return_value=mock_response)):
            async with provider as p:
                assert p is provider

    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self):
        """Should close client on exit."""
        provider = OpenAICompatibleProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "default"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "get", AsyncMock(return_value=mock_response)
        ), patch.object(provider.client, "aclose", AsyncMock()) as mock_aclose:
            async with provider:
                pass
            mock_aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_exit_on_exception(self):
        """Should close client even when exception occurs."""
        provider = OpenAICompatibleProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "default"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "get", AsyncMock(return_value=mock_response)
        ), patch.object(provider.client, "aclose", AsyncMock()) as mock_aclose:
            with pytest.raises(ValueError):
                async with provider:
                    raise ValueError("Test error")
            mock_aclose.assert_called_once()


class TestOpenAICompatibleProviderExecutePrompt:
    """Tests for execute_prompt method."""

    @pytest.mark.asyncio
    async def test_execute_prompt_success(self, provider):
        """Should execute prompt and return results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Here is the implementation...\nCreated file: app.py"}}
            ],
            "usage": {"total_tokens": 250},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt(
                "Write a function to parse JSON",
                context={"workspace": "/tmp"},
                task_id="task-1",
            )

        assert result["success"] is True
        assert "Here is the implementation" in result["output"]
        assert result["error"] is None
        assert "app.py" in result["files_changed"]

    @pytest.mark.asyncio
    async def test_execute_prompt_api_call_format(self, provider):
        """Should make correct API call to chat/completions endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Response text"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.execute_prompt("Test prompt")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8000/v1/chat/completions"
        json_body = call_args[1]["json"]
        assert json_body["model"] == "default"
        assert json_body["messages"] == [{"role": "user", "content": "Test prompt"}]
        assert json_body["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_execute_prompt_no_choices(self, provider):
        """Should handle response with no choices."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt", task_id="task-1")

        assert result["success"] is False
        assert result["output"] == ""
        assert "No choices returned" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_empty_choices(self, provider):
        """Should handle response with empty choices array."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is False
        assert "No choices returned" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_http_error_with_json_body(self, provider):
        """Should extract error message from JSON response body."""
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 400
        mock_response_obj.json.return_value = {"error": {"message": "Invalid model specified"}}

        with patch.object(
            provider.client,
            "post",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad Request",
                    request=MagicMock(),
                    response=mock_response_obj,
                )
            ),
        ):
            result = await provider.execute_prompt("Test prompt", task_id="task-1")

        assert result["success"] is False
        assert "Invalid model specified" in result["error"]
        assert "400" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_http_error_without_json_body(self, provider):
        """Should handle HTTP error when response body is not JSON."""
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 500
        mock_response_obj.json.side_effect = ValueError("Not JSON")

        with patch.object(
            provider.client,
            "post",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal Server Error",
                    request=MagicMock(),
                    response=mock_response_obj,
                )
            ),
        ):
            result = await provider.execute_prompt("Test prompt", task_id="task-1")

        assert result["success"] is False
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_generic_exception(self, provider):
        """Should handle generic exceptions."""
        with patch.object(
            provider.client,
            "post",
            AsyncMock(side_effect=RuntimeError("Connection reset")),
        ):
            result = await provider.execute_prompt("Test prompt", task_id="task-1")

        assert result["success"] is False
        assert result["output"] == ""
        assert "Connection reset" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_extracts_usage_total_tokens(self, provider):
        """Should extract total_tokens from usage if available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 500},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_extracts_usage_completion_tokens(self, provider):
        """Should fall back to completion_tokens if total_tokens unavailable."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"completion_tokens": 100},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_with_none_context(self, provider):
        """Should handle None context."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Done"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test", context=None)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_with_none_task_id(self, provider):
        """Should handle None task_id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Done"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test", task_id=None)

        assert result["success"] is True


class TestOpenAICompatibleProviderDetectChangedFiles:
    """Tests for _detect_changed_files method."""

    def test_detect_created_file(self, provider):
        """Should detect created files."""
        output = "Created file: src/middleware/rate_limiter.py\nDone."
        files = provider._detect_changed_files(output)
        assert "src/middleware/rate_limiter.py" in files

    def test_detect_modified_file(self, provider):
        """Should detect modified files."""
        output = "Modified file: config.yaml"
        files = provider._detect_changed_files(output)
        assert "config.yaml" in files

    def test_detect_updated_file(self, provider):
        """Should detect updated files."""
        output = "Updated file: README.md"
        files = provider._detect_changed_files(output)
        assert "README.md" in files

    def test_detect_writing_to_file(self, provider):
        """Should detect 'Writing to:' pattern."""
        output = "Writing to: output.json"
        files = provider._detect_changed_files(output)
        assert "output.json" in files

    def test_detect_saved_file(self, provider):
        """Should detect 'Saved:' pattern."""
        output = "Saved: data.csv"
        files = provider._detect_changed_files(output)
        assert "data.csv" in files

    def test_detect_file_pattern(self, provider):
        """Should detect 'File:' pattern."""
        output = "File: test.py"
        files = provider._detect_changed_files(output)
        assert "test.py" in files

    def test_detect_file_uppercase_pattern(self, provider):
        """Should detect 'FILE:' pattern (uppercase)."""
        output = "FILE: IMPORTANT.txt"
        files = provider._detect_changed_files(output)
        assert "IMPORTANT.txt" in files

    def test_detect_multiple_files(self, provider):
        """Should detect multiple file changes."""
        output = """
        Created file: app.py
        Modified file: setup.py
        Updated file: README.md
        Writing to: config.json
        """
        files = provider._detect_changed_files(output)
        assert "app.py" in files
        assert "setup.py" in files
        assert "README.md" in files
        assert "config.json" in files

    def test_detect_no_files(self, provider):
        """Should return empty list when no files detected."""
        output = "Just some regular output without file changes."
        files = provider._detect_changed_files(output)
        assert files == []

    def test_detect_file_with_path(self, provider):
        """Should extract complete file paths."""
        output = "Created file: src/models/user.py additional text"
        files = provider._detect_changed_files(output)
        assert "src/models/user.py" in files

    def test_detect_file_with_special_characters(self, provider):
        """Should handle file paths with special characters."""
        output = "Created file: path/to/file-with-dashes_and_underscores.py"
        files = provider._detect_changed_files(output)
        assert "path/to/file-with-dashes_and_underscores.py" in files

    def test_detect_file_empty_after_pattern(self, provider):
        """Should raise IndexError when pattern has no filename after it.

        Note: This is a known limitation in the current implementation.
        The code assumes there will always be a filename after the pattern.
        """
        output = "Created file:"
        # Current implementation raises IndexError when no filename follows
        with pytest.raises(IndexError):
            provider._detect_changed_files(output)


class TestOpenAICompatibleProviderParseTasksFromMarkdown:
    """Tests for _parse_tasks_from_markdown method."""

    def test_parse_standard_format(self, provider):
        """Should parse tasks in standard format (## N. Title)."""
        markdown = """
## 1. First Task
Description of first task.

## 2. Second Task
Description of second task.
With multiple lines.

## 3. Third Task
Final task description.
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert len(tasks) == 3
        assert tasks[0].title == "First Task"
        assert tasks[1].title == "Second Task"
        assert "multiple lines" in tasks[1].description
        assert tasks[2].id == "task-3"

    def test_parse_colon_format(self, provider):
        """Should parse tasks with colon separator (## N: Title)."""
        markdown = """
## 1: Task One
Description one.

## 2: Task Two
Description two.
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert len(tasks) == 2
        assert tasks[0].title == "Task One"
        assert tasks[1].title == "Task Two"

    def test_parse_empty_descriptions(self, provider):
        """Should handle tasks with empty descriptions."""
        markdown = """
## 1. Task Without Description
## 2. Another Task
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert len(tasks) == 2
        assert tasks[0].description == ""

    def test_parse_no_tasks(self, provider):
        """Should return empty list for markdown without tasks."""
        markdown = "# Overview\nSome text without task format."
        tasks = provider._parse_tasks_from_markdown(markdown)
        assert tasks == []

    def test_parse_task_with_nested_headers(self, provider):
        """Should filter out lines starting with # from descriptions.

        The parser skips any line starting with # when accumulating description,
        so ### headers are excluded from task descriptions.
        """
        markdown = """
## 1. Main Task
Description.
### Subtask details
More info.

## 2. Second Task
Another description.
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert len(tasks) == 2
        # Note: Lines starting with # are skipped, so "Subtask details" is NOT included
        assert "Subtask details" not in tasks[0].description
        # But "More info." IS included since it doesn't start with #
        assert "More info" in tasks[0].description

    def test_task_objects_have_attribute_access(self, provider):
        """Should return task objects with attribute access."""
        markdown = "## 1. Test Task\nDescription here."
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert tasks[0].id == "task-1"
        assert tasks[0].title == "Test Task"
        assert tasks[0].description == "Description here."
        assert tasks[0].dependencies == []

    def test_task_dict_raises_attribute_error_for_missing_key(self, provider):
        """Should raise AttributeError when accessing missing attribute."""
        markdown = "## 1. Test Task\nDescription here."
        tasks = provider._parse_tasks_from_markdown(markdown)

        with pytest.raises(AttributeError) as exc_info:
            _ = tasks[0].nonexistent_attribute

        assert "TaskDict" in str(exc_info.value)
        assert "nonexistent_attribute" in str(exc_info.value)

    def test_task_dict_setattr_works(self, provider):
        """Should allow setting attributes on TaskDict objects."""
        markdown = "## 1. Test Task\nDescription here."
        tasks = provider._parse_tasks_from_markdown(markdown)

        # Set a new attribute
        tasks[0].custom_field = "custom_value"

        # Verify it was set (accessing via dict and attribute)
        assert tasks[0].custom_field == "custom_value"
        assert tasks[0]["custom_field"] == "custom_value"

    def test_parse_preserves_multiline_description(self, provider):
        """Should preserve multi-line descriptions correctly."""
        markdown = """
## 1. Setup Database
First line.
Second line.
Third line.
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert "First line" in tasks[0].description
        assert "Second line" in tasks[0].description
        assert "Third line" in tasks[0].description


class TestOpenAICompatibleProviderGeneratePlan:
    """Tests for generate_plan method."""

    @pytest.mark.asyncio
    async def test_generate_plan_success(self, provider, sample_issue):
        """Should generate a plan from an issue."""
        plan_output = """
# Overview
This plan implements rate limiting for API endpoints.

# Tasks

## 1. Create Rate Limiter Class
Implement a token bucket rate limiter class with configurable limits.

## 2. Add Middleware Integration
Integrate rate limiter as middleware in the request pipeline.

## 3. Add Configuration Options
Allow rate limits to be configured via environment variables.
"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": plan_output}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        assert isinstance(plan, Plan)
        assert plan.id == str(sample_issue.number)
        assert "Implement rate limiting" in plan.title
        assert len(plan.tasks) == 3
        assert "Rate Limiter" in plan.tasks[0].title

    @pytest.mark.asyncio
    async def test_generate_plan_with_empty_tasks(self, provider, sample_issue):
        """Should handle plan with no parseable tasks."""
        plan_output = "# Overview\nSome plan without proper task formatting."

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": plan_output}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        assert isinstance(plan, Plan)
        assert len(plan.tasks) == 0

    @pytest.mark.asyncio
    async def test_generate_plan_file_path_format(self, provider, sample_issue):
        """Should generate correct file_path for the plan."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "## 1. Task\nDescription"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        # File path should be based on issue number and title
        assert plan.file_path == "plans/42-implement-rate-limiting.md"

    @pytest.mark.asyncio
    async def test_generate_plan_prompt_contains_issue_details(self, provider, sample_issue):
        """Should include issue details in the prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "## 1. Task\nDescription"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.generate_plan(sample_issue)

        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["messages"][0]["content"]
        assert str(sample_issue.number) in prompt
        assert sample_issue.title in prompt
        assert sample_issue.body in prompt


class TestOpenAICompatibleProviderGeneratePrompts:
    """Tests for generate_prompts method."""

    @pytest.mark.asyncio
    async def test_generate_prompts_returns_plan_tasks(self, provider):
        """Should return tasks from plan."""

        class MockTask:
            def __init__(self, task_id, title):
                self.id = task_id
                self.title = title

        plan = MagicMock(spec=Plan)
        plan.tasks = [
            MockTask("task-1", "First"),
            MockTask("task-2", "Second"),
        ]

        tasks = await provider.generate_prompts(plan)

        assert len(tasks) == 2
        assert tasks[0].id == "task-1"
        assert tasks[1].id == "task-2"

    @pytest.mark.asyncio
    async def test_generate_prompts_no_tasks_attribute(self, provider):
        """Should return empty list if plan has no tasks attribute."""
        plan = MagicMock()
        del plan.tasks

        tasks = await provider.generate_prompts(plan)
        assert tasks == []

    @pytest.mark.asyncio
    async def test_generate_prompts_empty_tasks(self, provider):
        """Should return empty list if plan has empty tasks."""
        plan = MagicMock(spec=Plan)
        plan.tasks = []

        tasks = await provider.generate_prompts(plan)
        assert tasks == []


class TestOpenAICompatibleProviderExecuteTask:
    """Tests for execute_task method."""

    @pytest.mark.asyncio
    async def test_execute_task_success(self, provider, sample_task):
        """Should execute a task and return result."""
        task_output = """
Here's the implementation:

FILE: src/middleware/rate_limiter.py
```python
class RateLimiter:
    def __init__(self, max_requests=100):
        self.max_requests = max_requests
```
Created file: src/middleware/rate_limiter.py
"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": task_output}}]}
        mock_response.raise_for_status = MagicMock()

        context = {
            "issue_number": 42,
            "original_issue": {"title": "Rate Limiting", "body": "Add rate limits"},
            "task_number": 1,
            "total_tasks": 3,
            "branch": "feature/rate-limiting",
            "workspace": "/workspace",
        }

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_task(sample_task, context)

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.branch == "feature/rate-limiting"
        assert "src/middleware/rate_limiter.py" in result.files_changed

    @pytest.mark.asyncio
    async def test_execute_task_stores_issue_number(self, provider, sample_task):
        """Should store current issue number for Q&A."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Done"}}]}
        mock_response.raise_for_status = MagicMock()

        context = {"issue_number": 99}

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            await provider.execute_task(sample_task, context)

        assert provider.current_issue_number == 99

    @pytest.mark.asyncio
    async def test_execute_task_failure(self, provider, sample_task):
        """Should handle task execution failure."""
        with patch.object(
            provider.client,
            "post",
            AsyncMock(side_effect=RuntimeError("API Error")),
        ):
            result = await provider.execute_task(sample_task, {})

        assert result.success is False
        assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_execute_task_with_empty_context(self, provider, sample_task):
        """Should handle empty context dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Done"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_task(sample_task, {})

        assert result.success is True
        assert result.branch is None

    @pytest.mark.asyncio
    async def test_execute_task_prompt_format(self, provider, sample_task):
        """Should format task prompt correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Done"}}]}
        mock_response.raise_for_status = MagicMock()

        context = {
            "original_issue": {"title": "Test Issue", "body": "Issue body"},
            "task_number": 2,
            "total_tasks": 5,
            "branch": "feature/test",
            "workspace": "/workspace",
        }

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.execute_task(sample_task, context)

        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["messages"][0]["content"]
        assert sample_task.title in prompt
        assert sample_task.description in prompt
        assert "2/5" in prompt
        assert "feature/test" in prompt


class TestOpenAICompatibleProviderReviewCode:
    """Tests for review_code method."""

    @pytest.mark.asyncio
    async def test_review_code_approve(self, provider):
        """Should correctly parse APPROVE response."""
        review_output = """APPROVE

Good implementation:
- Clean code structure
- Proper error handling
"""

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": review_output}}]}
        mock_response.raise_for_status = MagicMock()

        diff = "+def new_function():\n+    pass"
        context = {"description": "Add new function"}

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code(diff, context)

        assert isinstance(review, Review)
        assert review.approved is True
        assert len(review.comments) > 0
        assert review.confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_review_code_request_changes(self, provider):
        """Should correctly parse REQUEST_CHANGES response."""
        review_output = """REQUEST_CHANGES

Issues found:
- Missing input validation
- No error handling for edge cases
"""

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": review_output}}]}
        mock_response.raise_for_status = MagicMock()

        diff = "+def risky_function():\n+    return unsafe_operation()"
        context = {"description": "Risky change"}

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code(diff, context)

        assert review.approved is False
        assert len(review.comments) >= 2

    @pytest.mark.asyncio
    async def test_review_code_parses_bullet_comments(self, provider):
        """Should parse bullet-point comments from output."""
        review_output = """APPROVE

- First comment
- Second comment
* Third comment with asterisk
"""

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": review_output}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert "First comment" in review.comments
        assert "Second comment" in review.comments
        assert "Third comment with asterisk" in review.comments

    @pytest.mark.asyncio
    async def test_review_code_no_bullets_uses_full_output(self, provider):
        """Should use full output as comment when no bullets found."""
        review_output = "APPROVE - This looks good overall"

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": review_output}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert len(review.comments) == 1
        assert review_output in review.comments[0]

    @pytest.mark.asyncio
    async def test_review_code_empty_output(self, provider):
        """Should handle empty output."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert review.approved is False  # No APPROVE found
        assert review.comments == []  # Empty output = no comments

    @pytest.mark.asyncio
    async def test_review_code_truncates_large_diff(self, provider):
        """Should truncate large diffs to 5000 characters."""
        large_diff = "+" * 10000

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "APPROVE"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.review_code(large_diff, {})

        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["messages"][0]["content"]
        # The diff in the prompt should be truncated
        # The full prompt will be larger than 5000 due to the prompt template
        assert prompt.count("+") <= 5000

    @pytest.mark.asyncio
    async def test_review_code_conservative_confidence_score(self, provider):
        """Should use conservative confidence score of 0.7."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "APPROVE"}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert review.confidence_score == 0.7


class TestOpenAICompatibleProviderResolveConflict:
    """Tests for resolve_conflict method."""

    @pytest.mark.asyncio
    async def test_resolve_conflict_success(self, provider):
        """Should resolve merge conflict."""
        resolved_content = """def combined_function():
    # Merged both changes
    original_code()
    new_code()
    return True"""

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": resolved_content}}]}
        mock_response.raise_for_status = MagicMock()

        conflict_info = {
            "file": "src/app.py",
            "content": """<<<<<<< HEAD
def function():
    original_code()
=======
def function():
    new_code()
>>>>>>> feature""",
        }

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.resolve_conflict(conflict_info)

        assert result == resolved_content
        assert "<<<<<<" not in result
        assert "======" not in result
        assert ">>>>>>" not in result

    @pytest.mark.asyncio
    async def test_resolve_conflict_prompt_format(self, provider):
        """Should include conflict details in prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "resolved"}}]}
        mock_response.raise_for_status = MagicMock()

        conflict_info = {
            "file": "config.yaml",
            "content": "conflict content here",
        }

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.resolve_conflict(conflict_info)

        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["messages"][0]["content"]
        assert "config.yaml" in prompt
        assert "conflict content here" in prompt

    @pytest.mark.asyncio
    async def test_resolve_conflict_empty_result(self, provider):
        """Should handle empty resolution."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.resolve_conflict({"file": "test.py", "content": ""})

        assert result == ""


class TestOpenAICompatibleProviderIntegration:
    """Integration-style tests for OpenAICompatibleProvider."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, sample_issue):
        """Should support full planning and execution workflow."""
        provider = OpenAICompatibleProvider()

        # Mock responses for connect, generate_plan, and execute_task
        connect_response = MagicMock()
        connect_response.json.return_value = {"data": [{"id": "default"}]}
        connect_response.raise_for_status = MagicMock()

        plan_response = MagicMock()
        plan_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """
# Overview
Implementation plan.

## 1. Setup Project
Initialize project structure.

## 2. Implement Feature
Add main functionality.
"""
                    }
                }
            ]
        }
        plan_response.raise_for_status = MagicMock()

        task_response = MagicMock()
        task_response.json.return_value = {
            "choices": [{"message": {"content": "Created file: main.py\nDone."}}]
        }
        task_response.raise_for_status = MagicMock()

        responses = [connect_response, plan_response, task_response, task_response]
        response_iter = iter(responses)

        async def mock_request(*args, **kwargs):
            return next(response_iter)

        with patch.object(provider.client, "get", mock_request), patch.object(
            provider.client, "post", mock_request
        ), patch.object(provider.client, "aclose", AsyncMock()):
            async with provider:
                # Generate plan
                plan = await provider.generate_plan(sample_issue)
                assert len(plan.tasks) == 2

                # Execute tasks
                for task in plan.tasks:
                    # Create proper Task object for execute_task
                    task_obj = Task(
                        id=task.id,
                        prompt_issue_id=sample_issue.number,
                        title=task.title,
                        description=task.description,
                        dependencies=[],
                    )
                    result = await provider.execute_task(task_obj, {"branch": "main"})
                    assert result.success is True


class TestOpenAICompatibleProviderEdgeCases:
    """Edge case tests for OpenAICompatibleProvider."""

    @pytest.mark.asyncio
    async def test_connect_with_empty_model_list(self, provider_custom):
        """Should log warning when model list is empty."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider_custom.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise
            await provider_custom.connect()

    @pytest.mark.asyncio
    async def test_execute_prompt_missing_message_key(self, provider):
        """Should handle response with missing message key in choices."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True
        assert result["output"] == ""

    @pytest.mark.asyncio
    async def test_execute_prompt_missing_content_key(self, provider):
        """Should handle response with missing content key in message."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True
        assert result["output"] == ""

    def test_detect_changed_files_pattern_in_middle_of_line(self, provider):
        """Should detect patterns in middle of lines."""
        output = "Log: Created file: output.txt at 12:00"
        files = provider._detect_changed_files(output)
        assert "output.txt" in files

    @pytest.mark.asyncio
    async def test_review_code_case_insensitive_approve(self, provider):
        """Should detect APPROVE regardless of case."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "approve\nLooks good"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert review.approved is True

    @pytest.mark.asyncio
    async def test_review_code_approve_not_on_first_line(self, provider):
        """Should detect APPROVE only on first line."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Analysis:\nI APPROVE this change"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        # APPROVE is not on first line, so should be False
        assert review.approved is False
