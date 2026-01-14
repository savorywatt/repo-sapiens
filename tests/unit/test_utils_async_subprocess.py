"""Tests for repo_sapiens.utils.async_subprocess module."""

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.utils.async_subprocess import run_command, run_shell_command


# =============================================================================
# Tests for run_command
# =============================================================================


class TestRunCommandBasic:
    """Test basic functionality of run_command."""

    @pytest.mark.asyncio
    async def test_run_simple_command(self):
        """Test running a simple command that succeeds."""
        stdout, stderr, returncode = await run_command("echo", "hello")

        assert stdout.strip() == "hello"
        assert stderr == ""
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_with_multiple_args(self):
        """Test running command with multiple arguments."""
        stdout, stderr, returncode = await run_command("echo", "hello", "world")

        assert stdout.strip() == "hello world"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_returns_tuple(self):
        """Test run_command returns a tuple of (stdout, stderr, returncode)."""
        result = await run_command("true")

        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_run_command_captures_stderr(self):
        """Test run_command captures stderr output."""
        stdout, stderr, returncode = await run_command(
            "bash", "-c", "echo error >&2"
        )

        assert stderr.strip() == "error"

    @pytest.mark.asyncio
    async def test_run_command_with_non_zero_exit_check_false(self):
        """Test run_command with non-zero exit code when check=False."""
        stdout, stderr, returncode = await run_command("false", check=False)

        assert returncode != 0


class TestRunCommandWorkingDirectory:
    """Test run_command with working directory option."""

    @pytest.mark.asyncio
    async def test_run_command_with_cwd_as_path(self):
        """Test run_command with cwd as Path object."""
        stdout, stderr, returncode = await run_command(
            "pwd", cwd=Path("/tmp")
        )

        assert stdout.strip() == "/tmp"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_with_cwd_as_string(self):
        """Test run_command with cwd as string."""
        stdout, stderr, returncode = await run_command("pwd", cwd="/tmp")

        assert stdout.strip() == "/tmp"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_with_none_cwd(self):
        """Test run_command with cwd=None uses current directory."""
        stdout, stderr, returncode = await run_command("pwd", cwd=None)

        # Should succeed and return some path
        assert returncode == 0
        assert len(stdout.strip()) > 0


class TestRunCommandCheckOption:
    """Test run_command check parameter behavior."""

    @pytest.mark.asyncio
    async def test_run_command_check_true_raises_on_failure(self):
        """Test run_command raises CalledProcessError when check=True."""
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            await run_command("false", check=True)

        assert exc_info.value.returncode != 0

    @pytest.mark.asyncio
    async def test_run_command_check_false_does_not_raise(self):
        """Test run_command does not raise when check=False."""
        stdout, stderr, returncode = await run_command("false", check=False)

        # Should not raise, just return non-zero
        assert returncode != 0

    @pytest.mark.asyncio
    async def test_run_command_check_default_is_true(self):
        """Test run_command defaults to check=True."""
        with pytest.raises(subprocess.CalledProcessError):
            await run_command("false")

    @pytest.mark.asyncio
    async def test_called_process_error_contains_output(self):
        """Test CalledProcessError contains stdout and stderr."""
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            await run_command(
                "bash", "-c", "echo stdout_msg; echo stderr_msg >&2; exit 1",
                check=True
            )

        assert "stdout_msg" in exc_info.value.stdout
        assert "stderr_msg" in exc_info.value.stderr


class TestRunCommandTimeout:
    """Test run_command timeout behavior."""

    @pytest.mark.asyncio
    async def test_run_command_with_timeout_completes(self):
        """Test run_command with timeout that completes in time."""
        stdout, stderr, returncode = await run_command(
            "echo", "fast", timeout=5.0
        )

        assert stdout.strip() == "fast"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_timeout_raises_timeout_error(self):
        """Test run_command raises TimeoutError when timeout exceeded."""
        with pytest.raises(TimeoutError):
            await run_command("sleep", "10", timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_command_timeout_kills_process(self):
        """Test run_command kills process on timeout."""
        # Use a command that would hang
        with pytest.raises(TimeoutError):
            await run_command("sleep", "60", timeout=0.1)

        # If we reach here without hanging, the process was killed

    @pytest.mark.asyncio
    async def test_run_command_none_timeout(self):
        """Test run_command with timeout=None (no timeout)."""
        stdout, stderr, returncode = await run_command(
            "echo", "test", timeout=None
        )

        assert stdout.strip() == "test"


class TestRunCommandCaptureOutput:
    """Test run_command capture_output parameter."""

    @pytest.mark.asyncio
    async def test_run_command_capture_output_true(self):
        """Test run_command captures output by default."""
        stdout, stderr, returncode = await run_command(
            "echo", "captured", capture_output=True
        )

        assert stdout.strip() == "captured"

    @pytest.mark.asyncio
    async def test_run_command_capture_output_false(self):
        """Test run_command with capture_output=False returns empty strings."""
        stdout, stderr, returncode = await run_command(
            "echo", "not captured", capture_output=False
        )

        assert stdout == ""
        assert stderr == ""
        assert returncode == 0


class TestRunCommandEncoding:
    """Test run_command output encoding."""

    @pytest.mark.asyncio
    async def test_run_command_utf8_output(self):
        """Test run_command handles UTF-8 output."""
        stdout, stderr, returncode = await run_command(
            "echo", "hello"
        )

        # Basic ASCII should work fine
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_run_command_binary_output_replacement(self):
        """Test run_command handles invalid UTF-8 with replacement."""
        # Create a command that outputs invalid UTF-8
        stdout, stderr, returncode = await run_command(
            "bash", "-c", "printf '\\xff\\xfe'"
        )

        # Should not raise, should use replacement characters
        assert returncode == 0


# =============================================================================
# Tests for run_shell_command
# =============================================================================


class TestRunShellCommandBasic:
    """Test basic functionality of run_shell_command."""

    @pytest.mark.asyncio
    async def test_run_shell_command_simple(self):
        """Test running a simple shell command."""
        stdout, stderr, returncode = await run_shell_command("echo hello")

        assert stdout.strip() == "hello"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_pipe(self):
        """Test run_shell_command supports shell pipes."""
        stdout, stderr, returncode = await run_shell_command(
            "echo 'hello world' | tr 'h' 'j'"
        )

        assert stdout.strip() == "jello world"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_redirect(self):
        """Test run_shell_command supports shell redirects."""
        stdout, stderr, returncode = await run_shell_command(
            "echo error_msg >&2"
        )

        assert stderr.strip() == "error_msg"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_variable_expansion(self):
        """Test run_shell_command supports variable expansion."""
        stdout, stderr, returncode = await run_shell_command(
            "VAR=test; echo $VAR"
        )

        assert stdout.strip() == "test"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_command_substitution(self):
        """Test run_shell_command supports command substitution."""
        stdout, stderr, returncode = await run_shell_command(
            "echo $(echo nested)"
        )

        assert stdout.strip() == "nested"
        assert returncode == 0


class TestRunShellCommandWorkingDirectory:
    """Test run_shell_command with working directory option."""

    @pytest.mark.asyncio
    async def test_run_shell_command_with_cwd(self):
        """Test run_shell_command with cwd parameter."""
        stdout, stderr, returncode = await run_shell_command("pwd", cwd="/tmp")

        assert stdout.strip() == "/tmp"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_cwd_as_path(self):
        """Test run_shell_command with cwd as Path object."""
        stdout, stderr, returncode = await run_shell_command(
            "pwd", cwd=Path("/tmp")
        )

        assert stdout.strip() == "/tmp"


class TestRunShellCommandCheckOption:
    """Test run_shell_command check parameter behavior."""

    @pytest.mark.asyncio
    async def test_run_shell_command_check_true_raises_on_failure(self):
        """Test run_shell_command raises CalledProcessError when check=True."""
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            await run_shell_command("exit 1", check=True)

        assert exc_info.value.returncode == 1

    @pytest.mark.asyncio
    async def test_run_shell_command_check_false_does_not_raise(self):
        """Test run_shell_command does not raise when check=False."""
        stdout, stderr, returncode = await run_shell_command(
            "exit 42", check=False
        )

        assert returncode == 42

    @pytest.mark.asyncio
    async def test_run_shell_command_check_default_is_true(self):
        """Test run_shell_command defaults to check=True."""
        with pytest.raises(subprocess.CalledProcessError):
            await run_shell_command("false")

    @pytest.mark.asyncio
    async def test_run_shell_called_process_error_contains_command(self):
        """Test CalledProcessError contains the original command string."""
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            await run_shell_command("echo fail; exit 1", check=True)

        assert exc_info.value.cmd == "echo fail; exit 1"


class TestRunShellCommandTimeout:
    """Test run_shell_command timeout behavior."""

    @pytest.mark.asyncio
    async def test_run_shell_command_with_timeout_completes(self):
        """Test run_shell_command with timeout that completes in time."""
        stdout, stderr, returncode = await run_shell_command(
            "echo fast", timeout=5.0
        )

        assert stdout.strip() == "fast"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_timeout_raises_timeout_error(self):
        """Test run_shell_command raises TimeoutError when timeout exceeded."""
        with pytest.raises(TimeoutError):
            await run_shell_command("sleep 10", timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_shell_command_timeout_kills_process(self):
        """Test run_shell_command kills process on timeout."""
        with pytest.raises(TimeoutError):
            await run_shell_command("sleep 60", timeout=0.1)

        # If we reach here without hanging, the process was killed


class TestRunShellCommandCaptureOutput:
    """Test run_shell_command capture_output parameter."""

    @pytest.mark.asyncio
    async def test_run_shell_command_capture_output_true(self):
        """Test run_shell_command captures output by default."""
        stdout, stderr, returncode = await run_shell_command(
            "echo captured", capture_output=True
        )

        assert stdout.strip() == "captured"

    @pytest.mark.asyncio
    async def test_run_shell_command_capture_output_false(self):
        """Test run_shell_command with capture_output=False."""
        stdout, stderr, returncode = await run_shell_command(
            "echo not_captured", capture_output=False
        )

        assert stdout == ""
        assert stderr == ""
        assert returncode == 0


class TestRunShellCommandComplexCommands:
    """Test run_shell_command with complex shell commands."""

    @pytest.mark.asyncio
    async def test_run_shell_command_with_multiple_commands(self):
        """Test run_shell_command with semicolon-separated commands."""
        stdout, stderr, returncode = await run_shell_command(
            "echo first; echo second"
        )

        assert "first" in stdout
        assert "second" in stdout

    @pytest.mark.asyncio
    async def test_run_shell_command_with_and_operator(self):
        """Test run_shell_command with && operator."""
        stdout, stderr, returncode = await run_shell_command(
            "echo first && echo second"
        )

        assert "first" in stdout
        assert "second" in stdout

    @pytest.mark.asyncio
    async def test_run_shell_command_with_or_operator(self):
        """Test run_shell_command with || operator."""
        stdout, stderr, returncode = await run_shell_command(
            "false || echo fallback"
        )

        assert stdout.strip() == "fallback"
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_with_subshell(self):
        """Test run_shell_command with subshell."""
        stdout, stderr, returncode = await run_shell_command(
            "(cd /tmp && pwd)"
        )

        assert stdout.strip() == "/tmp"


# =============================================================================
# Tests with mocked subprocess
# =============================================================================


class TestRunCommandMocked:
    """Test run_command with mocked subprocess for edge cases."""

    @pytest.mark.asyncio
    async def test_run_command_handles_none_returncode(self):
        """Test run_command handles None returncode (converts to 0)."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.communicate = AsyncMock(return_value=(b"out", b"err"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            stdout, stderr, returncode = await run_command(
                "test", check=False
            )

            assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_decodes_with_replace(self):
        """Test run_command uses 'replace' error handling for decoding."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        # Simulate binary output that's not valid UTF-8
        mock_process.communicate = AsyncMock(
            return_value=(b"valid\xff\xfeinvalid", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            stdout, stderr, returncode = await run_command("test")

            # Should not raise, uses replacement character
            assert "valid" in stdout

    @pytest.mark.asyncio
    async def test_run_command_handles_none_output(self):
        """Test run_command handles None stdout/stderr."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(None, None))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            stdout, stderr, returncode = await run_command("test")

            assert stdout == ""
            assert stderr == ""


class TestRunShellCommandMocked:
    """Test run_shell_command with mocked subprocess for edge cases."""

    @pytest.mark.asyncio
    async def test_run_shell_command_handles_none_returncode(self):
        """Test run_shell_command handles None returncode."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.communicate = AsyncMock(return_value=(b"out", b"err"))

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            stdout, stderr, returncode = await run_shell_command(
                "test", check=False
            )

            assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_shell_command_handles_none_output(self):
        """Test run_shell_command handles None stdout/stderr."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(None, None))

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            stdout, stderr, returncode = await run_shell_command("test")

            assert stdout == ""
            assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_shell_command_decodes_with_replace(self):
        """Test run_shell_command uses 'replace' error handling for decoding."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        # Simulate binary output that's not valid UTF-8
        mock_process.communicate = AsyncMock(
            return_value=(b"valid\xff\xfeinvalid", b"")
        )

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            stdout, stderr, returncode = await run_shell_command("test")

            # Should not raise, uses replacement character
            assert "valid" in stdout
