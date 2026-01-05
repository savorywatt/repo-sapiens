"""Tests for repo_sapiens/providers/openai_compatible.py - OpenAI-compatible provider."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from repo_sapiens.models.domain import Issue, IssueState, Plan, Task, TaskResult
from repo_sapiens.providers.openai_compatible import OpenAICompatibleProvider


@pytest.fixture
def provider():
    """Create OpenAICompatibleProvider instance with defaults."""
    return OpenAICompatibleProvider()


@pytest.fixture
def provider_with_auth():
    """Create OpenAICompatibleProvider with API key authentication."""
    return OpenAICompatibleProvider(
        base_url="http://localhost:8000/v1",
        model="gpt-4",
        api_key="sk-test-api-key-12345",  # pragma: allowlist secret
    )


@pytest.fixture
def provider_custom():
    """Create OpenAICompatibleProvider instance with custom settings."""
    return OpenAICompatibleProvider(
        base_url="http://custom-server:9000/v1",
        model="codellama:13b",
        api_key="test-key",  # pragma: allowlist secret
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
        title="Add user authentication",
        body="We need to implement login and signup functionality.",
        state=IssueState.OPEN,
        labels=["feature", "high-priority"],
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
        title="Create User model",
        description="Implement User model with authentication fields",
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
            base_url="http://custom-host:9000/v1/",
            model="mistral:7b",
            api_key="secret-key",  # pragma: allowlist secret
            working_dir="/custom/path",
            qa_handler=qa_handler,
            timeout=600.0,
        )

        # Trailing slash should be stripped
        assert provider.base_url == "http://custom-host:9000/v1"
        assert provider.model == "mistral:7b"
        assert provider.api_key == "secret-key"  # pragma: allowlist secret
        assert provider.working_dir == "/custom/path"
        assert provider.qa_handler is qa_handler
        assert provider.timeout == 600.0

    def test_init_strips_trailing_slash(self):
        """Should strip trailing slash from base_url."""
        provider = OpenAICompatibleProvider(base_url="http://localhost:8000/v1///")
        assert provider.base_url == "http://localhost:8000/v1"

    def test_init_strips_single_trailing_slash(self):
        """Should strip single trailing slash from base_url."""
        provider = OpenAICompatibleProvider(base_url="http://localhost:8000/v1/")
        assert provider.base_url == "http://localhost:8000/v1"

    def test_init_with_api_key_sets_auth_header(self, provider_with_auth):
        """Should set Authorization header when api_key is provided."""
        # Headers are stored in the client - verify client was created
        assert provider_with_auth.client is not None
        assert provider_with_auth.api_key == "sk-test-api-key-12345"  # pragma: allowlist secret

    def test_init_without_api_key_no_auth_header(self, provider):
        """Should not set Authorization header when no api_key."""
        assert provider.api_key is None
        assert provider.client is not None

    def test_init_working_dir_none_defaults_to_current(self):
        """Should default working_dir to '.' when None."""
        provider = OpenAICompatibleProvider(working_dir=None)
        assert provider.working_dir == "."

    def test_init_client_timeout(self):
        """Should create client with specified timeout."""
        provider = OpenAICompatibleProvider(timeout=120.0)
        assert provider.timeout == 120.0
        assert provider.client is not None


class TestOpenAICompatibleProviderConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, provider):
        """Should connect successfully when server is available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "get", AsyncMock(return_value=mock_response)
        ) as mock_get:
            await provider.connect()

            mock_get.assert_called_once_with("http://localhost:8000/v1/models")

    @pytest.mark.asyncio
    async def test_connect_model_not_found(self):
        """Should log warning when model is not available."""
        provider = OpenAICompatibleProvider(model="nonexistent-model")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "different-model"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise, just log warning
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_model_found_by_substring(self):
        """Should find model by substring match."""
        provider = OpenAICompatibleProvider(model="gpt-4")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4-turbo-preview"},
                {"id": "gpt-3.5-turbo"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "get", AsyncMock(return_value=mock_response)):
            # Should not raise - "gpt-4" is in "gpt-4-turbo-preview"
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_with_default_model_skips_check(self, provider):
        """Should skip model check when using 'default' model."""
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
        assert "http://localhost:8000/v1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_401_unauthorized(self, provider_with_auth):
        """Should raise HTTPStatusError for 401 unauthorized."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"message": "Invalid API key", "type": "invalid_request_error"}
        }

        with patch.object(
            provider_with_auth.client,
            "get",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Unauthorized",
                    request=MagicMock(),
                    response=mock_response,
                )
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await provider_with_auth.connect()

    @pytest.mark.asyncio
    async def test_connect_404_models_endpoint_not_supported(self, provider):
        """Should proceed when /models endpoint returns 404."""
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
            # Should not raise - 404 on /models is acceptable
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_500_server_error(self, provider):
        """Should raise HTTPStatusError for 500 server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            provider.client,
            "get",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal Server Error",
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
            AsyncMock(side_effect=Exception("Unexpected error")),
        ):
            with pytest.raises(Exception) as exc_info:
                await provider.connect()

        assert "Unexpected error" in str(exc_info.value)


class TestOpenAICompatibleProviderContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager_entry(self):
        """Should call connect on entry."""
        provider = OpenAICompatibleProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "model-1"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "get", AsyncMock(return_value=mock_response)):
            async with provider as p:
                assert p is provider

    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self):
        """Should close client on exit."""
        provider = OpenAICompatibleProvider()

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "model-1"}]}
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
        mock_response.json.return_value = {"data": [{"id": "model-1"}]}
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
                {"message": {"role": "assistant", "content": "Here is the implementation code..."}}
            ],
            "usage": {"total_tokens": 150},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt(
                "Write a function",
                context={"test": "value"},
                task_id="task-1",
            )

        assert result["success"] is True
        assert result["output"] == "Here is the implementation code..."
        assert result["error"] is None
        assert isinstance(result["files_changed"], list)

    @pytest.mark.asyncio
    async def test_execute_prompt_correct_api_call(self, provider):
        """Should make correct API call to chat completions endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Response"}}]
        }
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
    async def test_execute_prompt_with_custom_model(self, provider_with_auth):
        """Should use custom model in API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider_with_auth.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider_with_auth.execute_prompt("Test prompt")

        json_body = mock_post.call_args[1]["json"]
        assert json_body["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_execute_prompt_no_choices(self, provider):
        """Should handle response with no choices."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is False
        assert result["output"] == ""
        assert result["error"] == "No choices returned from API"

    @pytest.mark.asyncio
    async def test_execute_prompt_empty_message_content(self, provider):
        """Should handle empty message content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {}}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True
        assert result["output"] == ""

    @pytest.mark.asyncio
    async def test_execute_prompt_api_error(self, provider):
        """Should handle API errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal server error"}}

        with patch.object(
            provider.client,
            "post",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "API Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            ),
        ):
            result = await provider.execute_prompt("Test prompt", task_id="task-1")

        assert result["success"] is False
        assert result["output"] == ""
        assert "500" in result["error"]
        assert "Internal server error" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_api_error_no_json_body(self, provider):
        """Should handle API errors when response body is not JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Not JSON")

        with patch.object(
            provider.client,
            "post",
            AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            ),
        ):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is False
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_execute_prompt_connection_error(self, provider):
        """Should handle connection errors."""
        with patch.object(
            provider.client,
            "post",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is False
        assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_prompt_with_usage_stats(self, provider):
        """Should extract token usage from response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Test"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test prompt")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_with_completion_tokens_only(self, provider):
        """Should handle usage with only completion_tokens."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Test"}}],
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
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Test"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test", context=None)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_with_none_task_id(self, provider):
        """Should handle None task_id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Test"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test", task_id=None)

        assert result["success"] is True


class TestOpenAICompatibleProviderDetectChangedFiles:
    """Tests for _detect_changed_files method."""

    def test_detect_created_file(self, provider):
        """Should detect created files."""
        output = "Created file: src/models/user.py\nDone."
        files = provider._detect_changed_files(output)
        assert "src/models/user.py" in files

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
        """Should detect files being written to."""
        output = "Writing to: output.txt"
        files = provider._detect_changed_files(output)
        assert "output.txt" in files

    def test_detect_saved_file(self, provider):
        """Should detect saved files."""
        output = "Saved: data.json"
        files = provider._detect_changed_files(output)
        assert "data.json" in files

    def test_detect_file_pattern(self, provider):
        """Should detect File: pattern."""
        output = "File: test.py"
        files = provider._detect_changed_files(output)
        assert "test.py" in files

    def test_detect_file_uppercase(self, provider):
        """Should detect FILE: uppercase pattern."""
        output = "FILE: main.py"
        files = provider._detect_changed_files(output)
        assert "main.py" in files

    def test_detect_multiple_files(self, provider):
        """Should detect multiple file changes."""
        output = """
        Created file: app.py
        Modified file: setup.py
        Updated file: README.md
        """
        files = provider._detect_changed_files(output)
        assert "app.py" in files
        assert "setup.py" in files
        assert "README.md" in files

    def test_detect_no_files(self, provider):
        """Should return empty list when no files detected."""
        output = "Just some regular output without file changes."
        files = provider._detect_changed_files(output)
        assert files == []

    def test_detect_file_with_special_characters(self, provider):
        """Should handle file paths with special characters."""
        output = "Created file: path/to/file-with-dashes_and_underscores.py"
        files = provider._detect_changed_files(output)
        assert "path/to/file-with-dashes_and_underscores.py" in files


class TestOpenAICompatibleProviderParseTasksFromMarkdown:
    """Tests for _parse_tasks_from_markdown method."""

    def test_parse_standard_format(self, provider):
        """Should parse tasks in standard format."""
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
        """Should parse tasks with colon separator."""
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

    def test_parse_ignores_overview_headers(self, provider):
        """Should not parse overview headers as tasks."""
        markdown = """
# Overview
This is the overview.

## 1. Actual Task
Task description.
"""
        tasks = provider._parse_tasks_from_markdown(markdown)

        assert len(tasks) == 1
        assert tasks[0].title == "Actual Task"


class TestOpenAICompatibleProviderGeneratePlan:
    """Tests for generate_plan method."""

    @pytest.mark.asyncio
    async def test_generate_plan_success(self, provider, sample_issue):
        """Should generate a plan from an issue."""
        plan_output = """
# Overview
This plan implements user authentication with login and signup.

# Tasks

## 1. Create User Model
Implement the User model with fields for email, password hash, etc.

## 2. Add Authentication Routes
Create login and signup endpoints.

## 3. Implement JWT Tokens
Add token generation and validation.
"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": plan_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        assert isinstance(plan, Plan)
        assert plan.id == str(sample_issue.number)
        assert "Add user authentication" in plan.title
        assert len(plan.tasks) == 3
        assert "Create User Model" in plan.tasks[0].title

    @pytest.mark.asyncio
    async def test_generate_plan_with_empty_tasks(self, provider, sample_issue):
        """Should handle plan with no parseable tasks."""
        plan_output = "# Overview\nSome plan without proper task formatting."

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": plan_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        assert isinstance(plan, Plan)
        assert len(plan.tasks) == 0

    @pytest.mark.asyncio
    async def test_generate_plan_sets_file_path(self, provider, sample_issue):
        """Should set appropriate file_path for the plan."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "## 1. Task\nDesc"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            plan = await provider.generate_plan(sample_issue)

        assert plan.file_path is not None
        assert "42" in plan.file_path
        assert "add-user-authentication" in plan.file_path

    @pytest.mark.asyncio
    async def test_generate_plan_prompt_contains_issue_info(self, provider, sample_issue):
        """Should include issue info in the prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "## 1. Task\nDesc"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.generate_plan(sample_issue)

        # Verify prompt contains issue information
        call_args = mock_post.call_args[1]["json"]
        prompt = call_args["messages"][0]["content"]
        assert str(sample_issue.number) in prompt
        assert sample_issue.title in prompt
        assert sample_issue.body in prompt


class TestOpenAICompatibleProviderExecuteTask:
    """Tests for execute_task method."""

    @pytest.mark.asyncio
    async def test_execute_task_success(self, provider, sample_task):
        """Should execute a task and return result."""
        task_output = """
FILE: src/models/user.py
```python
class User:
    def __init__(self, email):
        self.email = email
```
Created file: src/models/user.py
"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": task_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        context = {
            "issue_number": 42,
            "original_issue": {"title": "Test Issue", "body": "Test body"},
            "task_number": 1,
            "total_tasks": 3,
            "branch": "feature/user-auth",
            "workspace": "/workspace",
        }

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_task(sample_task, context)

        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.branch == "feature/user-auth"
        assert "src/models/user.py" in result.files_changed

    @pytest.mark.asyncio
    async def test_execute_task_stores_issue_number(self, provider, sample_task):
        """Should store current issue number for Q&A."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Done"}}]
        }
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
            AsyncMock(side_effect=Exception("API Error")),
        ):
            result = await provider.execute_task(sample_task, {})

        assert result.success is False
        assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_execute_task_with_empty_context(self, provider, sample_task):
        """Should handle empty context dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Done"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_task(sample_task, {})

        assert result.success is True
        assert result.branch is None

    @pytest.mark.asyncio
    async def test_execute_task_prompt_contains_task_info(self, provider, sample_task):
        """Should include task info in the prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Done"}}]
        }
        mock_response.raise_for_status = MagicMock()

        context = {
            "original_issue": {"title": "Issue Title", "body": "Issue body"},
            "task_number": 2,
            "total_tasks": 5,
            "branch": "feature-branch",
            "workspace": "/workspace",
        }

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.execute_task(sample_task, context)

        call_args = mock_post.call_args[1]["json"]
        prompt = call_args["messages"][0]["content"]
        assert sample_task.title in prompt
        assert sample_task.description in prompt
        assert "2/5" in prompt
        assert "feature-branch" in prompt


class TestOpenAICompatibleProviderReviewCode:
    """Tests for review_code method."""

    @pytest.mark.asyncio
    async def test_review_code_approve(self, provider):
        """Should correctly parse APPROVE response."""
        review_output = """APPROVE

Good implementation. Code follows best practices.
- Clean code structure
- Proper error handling
"""

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": review_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        diff = "+def new_function():\n+    pass"
        context = {"description": "Add new function"}

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code(diff, context)

        assert review.approved is True
        assert len(review.comments) >= 1
        assert review.confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_review_code_request_changes(self, provider):
        """Should correctly parse REQUEST_CHANGES response."""
        review_output = """REQUEST_CHANGES

This code needs improvements:
- Missing error handling
- No input validation
* Security vulnerability detected
"""

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": review_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        diff = "+def vulnerable_function():\n+    pass"

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code(diff, {})

        assert review.approved is False
        assert "Missing error handling" in review.comments
        assert "No input validation" in review.comments
        assert "Security vulnerability detected" in review.comments

    @pytest.mark.asyncio
    async def test_review_code_correct_api_call(self, provider):
        """Should make correct API call for code review."""
        diff = "+def test_function():\n+    pass"
        context = {"description": "Test function"}

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "APPROVE\nLooks good"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.review_code(diff, context)

        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]["json"]
        prompt = call_args["messages"][0]["content"]
        assert "code reviewer" in prompt.lower()
        assert diff in prompt

    @pytest.mark.asyncio
    async def test_review_code_truncates_large_diff(self, provider):
        """Should truncate large diffs to 5000 characters."""
        large_diff = "+" * 10000

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "APPROVE\nLooks good"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.review_code(large_diff, {})

        call_args = mock_post.call_args[1]["json"]
        prompt = call_args["messages"][0]["content"]
        # The diff in the prompt should be truncated to 5000 chars
        assert len(prompt) < len(large_diff) + 1000  # Allow for prompt overhead

    @pytest.mark.asyncio
    async def test_review_code_returns_review_with_correct_kwargs(self, provider):
        """Should return Review with correct field types."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "APPROVE\n- Good code"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        # Verify Review object has correct types
        assert isinstance(review.approved, bool)
        assert isinstance(review.comments, list)
        assert isinstance(review.confidence_score, float)
        assert review.confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_review_code_no_bullet_points_uses_full_output(self, provider):
        """Should use full output as comment when no bullet points found."""
        review_output = "APPROVE\nThis is a general comment without bullet points."

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": review_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert len(review.comments) == 1
        assert review_output in review.comments[0]

    @pytest.mark.asyncio
    async def test_review_code_empty_response(self, provider):
        """Should handle empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": ""}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert review.approved is False
        assert len(review.comments) == 0


class TestOpenAICompatibleProviderResolveConflict:
    """Tests for resolve_conflict method."""

    @pytest.mark.asyncio
    async def test_resolve_conflict_success(self, provider):
        """Should resolve merge conflict."""
        resolved_content = """def function():
    combined_changes()
    return True"""

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": resolved_content}}]
        }
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
    async def test_resolve_conflict_prompt_contains_conflict_info(self, provider):
        """Should include conflict info in prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "resolved"}}]
        }
        mock_response.raise_for_status = MagicMock()

        conflict_info = {
            "file": "test.py",
            "content": "<<<<<<< HEAD\noriginal\n=======\nnew\n>>>>>>> branch",
        }

        with patch.object(
            provider.client, "post", AsyncMock(return_value=mock_response)
        ) as mock_post:
            await provider.resolve_conflict(conflict_info)

        call_args = mock_post.call_args[1]["json"]
        prompt = call_args["messages"][0]["content"]
        assert "test.py" in prompt
        assert conflict_info["content"] in prompt


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


class TestOpenAICompatibleProviderIntegration:
    """Integration-style tests for OpenAICompatibleProvider."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, sample_issue):
        """Should support full planning and execution workflow."""
        provider = OpenAICompatibleProvider()

        # Mock responses for connect, generate_plan, and execute_task
        connect_response = MagicMock()
        connect_response.json.return_value = {"data": [{"id": "gpt-4"}]}
        connect_response.raise_for_status = MagicMock()

        plan_response = MagicMock()
        plan_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": """
# Overview
Implementation plan.

## 1. Setup Project
Initialize project structure.

## 2. Implement Feature
Add main functionality.
""",
                    }
                }
            ]
        }
        plan_response.raise_for_status = MagicMock()

        task_response = MagicMock()
        task_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Created file: main.py\nDone."}}
            ]
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

    def test_base_url_without_trailing_slash(self):
        """Should work with base_url that has no trailing slash."""
        provider = OpenAICompatibleProvider(base_url="http://example.com/v1")
        assert provider.base_url == "http://example.com/v1"

    def test_model_with_special_characters(self):
        """Should handle model names with special characters."""
        provider = OpenAICompatibleProvider(model="org/model-name:7b-v2.0")
        assert provider.model == "org/model-name:7b-v2.0"

    @pytest.mark.asyncio
    async def test_execute_prompt_with_unicode_content(self, provider):
        """Should handle unicode content in prompts."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Response: Hello, World!"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            result = await provider.execute_prompt("Test with unicode: cafe")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_review_code_with_asterisk_bullets(self, provider):
        """Should parse comments with asterisk bullets."""
        review_output = """APPROVE
* First comment with asterisk
* Second comment with asterisk
"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": review_output}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.client, "post", AsyncMock(return_value=mock_response)):
            review = await provider.review_code("+code", {})

        assert "First comment with asterisk" in review.comments
        assert "Second comment with asterisk" in review.comments

    @pytest.mark.asyncio
    async def test_generate_plan_with_api_failure(self, provider, sample_issue):
        """Should handle API failure during plan generation."""
        with patch.object(
            provider.client,
            "post",
            AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
        ):
            plan = await provider.generate_plan(sample_issue)

        # Should still return a plan, but with no tasks due to empty output
        assert isinstance(plan, Plan)
        assert len(plan.tasks) == 0
