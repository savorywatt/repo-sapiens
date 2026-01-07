"""Async subprocess utilities.

Provides non-blocking subprocess execution for use in async contexts,
replacing blocking subprocess.run calls that would stall the event loop.
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
    """Run a command asynchronously.

    This is a drop-in async replacement for subprocess.run() that doesn't
    block the event loop during command execution.

    Args:
        *args: Command and arguments (e.g., "git", "fetch", "origin")
        cwd: Working directory for command execution
        check: If True, raise CalledProcessError on non-zero return code
        timeout: Timeout in seconds (None for no timeout)
        capture_output: If True, capture stdout/stderr (default True)

    Returns:
        Tuple of (stdout, stderr, return_code)

    Raises:
        subprocess.CalledProcessError: If check=True and return code is non-zero
        asyncio.TimeoutError: If timeout exceeded

    Example:
        >>> stdout, stderr, code = await run_command(
        ...     "git", "status",
        ...     cwd="/path/to/repo",
        ...     check=True,
        ... )
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
    shell features like pipes, redirects, and variable expansion.

    Args:
        command: Shell command string to execute
        cwd: Working directory for command execution
        check: If True, raise CalledProcessError on non-zero return code
        timeout: Timeout in seconds (None for no timeout)
        capture_output: If True, capture stdout/stderr (default True)

    Returns:
        Tuple of (stdout, stderr, return_code)

    Raises:
        subprocess.CalledProcessError: If check=True and return code is non-zero
        asyncio.TimeoutError: If timeout exceeded

    Example:
        >>> stdout, stderr, code = await run_shell_command(
        ...     "grep -r pattern . | head -10",
        ...     cwd="/path/to/search",
        ... )
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
