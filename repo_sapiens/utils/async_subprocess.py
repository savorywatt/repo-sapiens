"""Async subprocess utilities.

Provides non-blocking subprocess execution for use in async contexts,
replacing blocking subprocess.run calls that would stall the event loop.

This module offers two main functions:
    - run_command: Execute commands with list arguments (safer, no shell)
    - run_shell_command: Execute shell command strings (supports pipes, etc.)

Key Features:
    - Non-blocking execution compatible with asyncio
    - Configurable timeout with automatic process cleanup
    - Optional check mode that raises on non-zero exit codes
    - Proper handling of stdout/stderr capture and decoding

Example:
    >>> from repo_sapiens.utils.async_subprocess import run_command
    >>> stdout, stderr, code = await run_command("git", "status", cwd="/repo")
    >>> if code == 0:
    ...     print(stdout)

Thread Safety:
    These functions are safe to call concurrently from multiple async tasks.
    Each call creates an independent subprocess with no shared state.

See Also:
    - asyncio.create_subprocess_exec: Underlying async subprocess API
    - subprocess.CalledProcessError: Exception raised on check failures
"""

import asyncio
import subprocess
from pathlib import Path


async def run_command(
    *args: str,
    cwd: Path | str | None = None,
    check: bool = True,
    timeout: float | None = None,
    capture_output: bool = True,
) -> tuple[str, str, int]:
    """Run a command asynchronously without shell interpolation.

    Executes the command in a subprocess, capturing stdout and stderr.
    This is the safer option when you have discrete command arguments,
    as it avoids shell injection risks.

    Args:
        *args: Command and arguments as separate strings. The first argument
            is the executable, subsequent arguments are passed to it.
            Example: "git", "commit", "-m", "message"
        cwd: Working directory for command execution. If None, uses the
            current working directory of the parent process.
        check: If True (default), raise CalledProcessError when the command
            returns a non-zero exit code. If False, return the exit code
            without raising.
        timeout: Maximum seconds to wait for command completion. If exceeded,
            the process is killed and TimeoutError is raised. None means
            wait indefinitely.
        capture_output: If True (default), capture stdout and stderr as
            strings. If False, output goes to the parent's stdout/stderr
            and returned strings will be empty.

    Returns:
        Tuple of (stdout, stderr, return_code) where stdout and stderr are
        decoded UTF-8 strings (with replacement for invalid bytes), and
        return_code is the process exit code.

    Raises:
        subprocess.CalledProcessError: If check=True and command returns
            non-zero. The exception includes stdout, stderr, and return code.
        asyncio.TimeoutError: If timeout is exceeded. The process is killed
            before this exception is raised.
        FileNotFoundError: If the command executable is not found.
        PermissionError: If the executable cannot be executed.

    Example:
        >>> # Simple command
        >>> stdout, stderr, code = await run_command("ls", "-la")

        >>> # Git command with working directory
        >>> stdout, stderr, code = await run_command(
        ...     "git", "status", "--porcelain",
        ...     cwd="/path/to/repo",
        ...     check=True,
        ... )

        >>> # Command with timeout
        >>> try:
        ...     stdout, _, _ = await run_command(
        ...         "long-running-process",
        ...         timeout=30.0,
        ...     )
        ... except asyncio.TimeoutError:
        ...     print("Process took too long")

        >>> # Don't raise on non-zero exit
        >>> stdout, stderr, code = await run_command(
        ...     "grep", "pattern", "file.txt",
        ...     check=False,  # grep returns 1 if no match
        ... )
        >>> if code == 0:
        ...     print("Found matches")

    Note:
        Unlike run_shell_command, this function does NOT support shell
        features like pipes, redirects, or variable expansion. Use
        run_shell_command if you need those capabilities.
    """
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise

    stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
    stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

    if check and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            args,
            stdout,
            stderr,
        )

    return stdout, stderr, process.returncode or 0


async def run_shell_command(
    command: str,
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    timeout: float | None = None,
    capture_output: bool = True,
) -> tuple[str, str, int]:
    """Run a shell command asynchronously.

    Similar to run_command but uses shell=True semantics, allowing
    shell features like pipes, redirects, variable expansion, and
    command chaining.

    Args:
        command: Complete shell command string to execute. This is passed
            to /bin/sh -c on Unix or cmd.exe on Windows.
        cwd: Working directory for command execution. If None, uses the
            current working directory.
        check: If True (default), raise CalledProcessError on non-zero
            exit code. If False, return exit code without raising.
        timeout: Maximum seconds to wait. Process is killed if exceeded.
            None means wait indefinitely.
        capture_output: If True (default), capture stdout/stderr as strings.
            If False, output goes to parent's stdout/stderr.

    Returns:
        Tuple of (stdout, stderr, return_code) where stdout and stderr are
        decoded UTF-8 strings, and return_code is the process exit code.

    Raises:
        subprocess.CalledProcessError: If check=True and command returns
            non-zero exit code.
        asyncio.TimeoutError: If timeout is exceeded.

    Example:
        >>> # Piped commands
        >>> stdout, _, _ = await run_shell_command(
        ...     "grep -r pattern . | head -10",
        ...     cwd="/path/to/search",
        ... )

        >>> # Command with shell variables
        >>> stdout, _, _ = await run_shell_command(
        ...     "echo $HOME && ls $HOME",
        ... )

        >>> # Complex shell one-liner
        >>> stdout, _, _ = await run_shell_command(
        ...     "for f in *.py; do wc -l $f; done | sort -n",
        ...     cwd="/project",
        ... )

    Warning:
        Be careful with user-provided input in shell commands to avoid
        command injection vulnerabilities. Prefer run_command when possible,
        or carefully sanitize any interpolated values.

    Note:
        The command is executed via the system shell (/bin/sh on Unix),
        so shell-specific syntax will work. However, this also means the
        command string is subject to shell parsing and escaping rules.
    """
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise

    stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
    stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

    if check and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            command,
            stdout,
            stderr,
        )

    return stdout, stderr, process.returncode or 0
