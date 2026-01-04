"""Tool registry and execution for ReAct agent."""
# ruff: noqa: E501  # Tool descriptions contain long lines by design

from __future__ import annotations

import asyncio
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, str]


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""

    pass


class ToolRegistry:
    """Registry of available tools for the ReAct agent.

    Provides file operations and shell command execution within
    a sandboxed working directory.
    """

    TOOLS: dict[str, ToolDefinition] = {
        "read_file": ToolDefinition(
            name="read_file",
            description="Read the contents of a file. Returns the file content as a string.",
            parameters={"path": "Path to the file to read (relative to working directory)"},
        ),
        "write_file": ToolDefinition(
            name="write_file",
            description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
            parameters={
                "path": "Path to the file to write (relative to working directory)",
                "content": "Content to write to the file",
            },
        ),
        "list_directory": ToolDefinition(
            name="list_directory",
            description="List files and directories in a path. Returns a formatted listing.",
            parameters={"path": "Path to the directory to list (relative to working directory)"},
        ),
        "run_command": ToolDefinition(
            name="run_command",
            description="Run a shell command and return its output. Use for git, npm, python, etc.",
            parameters={"command": "The shell command to execute"},
        ),
        "finish": ToolDefinition(
            name="finish",
            description="Mark the task as complete. IMPORTANT: Include the full answer with actual data/results in the 'answer' field, not just a summary statement.",
            parameters={
                "answer": "The complete answer to the user's question, including all relevant data, file lists, code, etc. This is what the user will see.",
                "summary": "A brief one-line summary of what was accomplished (optional)",
            },
        ),
        "search_files": ToolDefinition(
            name="search_files",
            description="Search for a pattern in file contents (like grep). Returns matching lines with file:line:content format.",
            parameters={
                "pattern": "The text or regex pattern to search for (required)",
                "path": "Directory to search in (default: current directory)",
                "file_pattern": "Glob pattern to filter files, e.g., '*.py' (default: '*')",
            },
        ),
        "find_files": ToolDefinition(
            name="find_files",
            description="Find files matching a glob pattern. Returns list of matching file paths.",
            parameters={
                "pattern": "Glob pattern to match files, e.g., '**/*.py' or '*.txt'",
                "path": "Directory to search in (default: current directory). Use 'repo_sapiens/' to search only in that folder.",
            },
        ),
        "edit_file": ToolDefinition(
            name="edit_file",
            description="Replace specific text in a file. The old_text must appear exactly once in the file.",
            parameters={
                "path": "Path to the file to edit (relative to working directory)",
                "old_text": "The exact text to find and replace (must be unique in file)",
                "new_text": "The text to replace it with",
            },
        ),
        "tree": ToolDefinition(
            name="tree",
            description="Display directory structure as a tree. Skips hidden files/directories.",
            parameters={
                "path": "Directory to display (default: current directory)",
                "max_depth": "Maximum depth to traverse (default: 3)",
            },
        ),
    }

    def __init__(
        self,
        working_dir: str | Path,
        allowed_commands: list[str] | None = None,
        command_timeout: int = 60,
    ):
        """Initialize the tool registry.

        Args:
            working_dir: Base directory for file operations
            allowed_commands: Optional whitelist of allowed command prefixes
            command_timeout: Timeout for shell commands in seconds
        """
        self.working_dir = Path(working_dir).resolve()
        self.allowed_commands = allowed_commands
        self.command_timeout = command_timeout
        self.files_written: list[str] = []

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the prompt."""
        lines = ["Available tools:"]
        for tool in self.TOOLS.values():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
            lines.append(f"- {tool.name}({params})")
            lines.append(f"  {tool.description}")
        return "\n".join(lines)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory, with security checks."""
        resolved = (self.working_dir / path).resolve()

        # Security: ensure path is within working directory
        if not str(resolved).startswith(str(self.working_dir)):
            raise ToolExecutionError(
                f"Path '{path}' resolves outside working directory. "
                "Only paths within the working directory are allowed."
            )
        return resolved

    async def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return the observation.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool

        Returns:
            String observation from tool execution

        Raises:
            ToolExecutionError: If tool execution fails
        """
        if tool_name not in self.TOOLS:
            return f"Error: Unknown tool '{tool_name}'. Available: {list(self.TOOLS.keys())}"

        log.info("executing_tool", tool=tool_name, args=args)

        try:
            if tool_name == "read_file":
                return await self._read_file(args.get("path", ""))
            elif tool_name == "write_file":
                return await self._write_file(
                    args.get("path", ""),
                    args.get("content", ""),
                )
            elif tool_name == "list_directory":
                return await self._list_directory(args.get("path", "."))
            elif tool_name == "run_command":
                return await self._run_command(args.get("command", ""))
            elif tool_name == "finish":
                return f"Task completed: {args.get('summary', 'No summary provided')}"
            elif tool_name == "search_files":
                return await self._search_files(
                    args.get("pattern", ""),
                    args.get("path", "."),
                    args.get("file_pattern", "*"),
                )
            elif tool_name == "find_files":
                return await self._find_files(
                    args.get("pattern", ""),
                    args.get("path", "."),
                )
            elif tool_name == "edit_file":
                return await self._edit_file(
                    args.get("path", ""),
                    args.get("old_text", ""),
                    args.get("new_text", ""),
                )
            elif tool_name == "tree":
                return await self._tree(
                    args.get("path", "."),
                    args.get("max_depth", 3),
                )
            else:
                return f"Error: Tool '{tool_name}' not implemented"
        except ToolExecutionError as e:
            log.warning("tool_execution_failed", tool=tool_name, error=str(e))
            return f"Error: {e}"
        except Exception as e:
            log.error("tool_unexpected_error", tool=tool_name, error=str(e))
            return f"Error: Unexpected error - {e}"

    async def _read_file(self, path: str) -> str:
        """Read contents of a file."""
        if not path:
            return "Error: 'path' parameter is required"

        resolved = self._resolve_path(path)

        if not resolved.exists():
            return f"Error: File '{path}' does not exist"

        if not resolved.is_file():
            return f"Error: '{path}' is not a file"

        try:
            content = resolved.read_text(encoding="utf-8")
            # Truncate very large files
            max_size = 50000
            if len(content) > max_size:
                content = content[:max_size] + f"\n\n[Truncated - file exceeds {max_size} chars]"
            return content
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not a text file"

    async def _write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        if not path:
            return "Error: 'path' parameter is required"
        if content is None:
            return "Error: 'content' parameter is required"

        resolved = self._resolve_path(path)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            resolved.write_text(content, encoding="utf-8")
            self.files_written.append(str(resolved.relative_to(self.working_dir)))
            return f"Successfully wrote {len(content)} bytes to '{path}'"
        except OSError as e:
            raise ToolExecutionError(f"Failed to write file: {e}") from e

    async def _list_directory(self, path: str) -> str:
        """List contents of a directory."""
        resolved = self._resolve_path(path)

        if not resolved.exists():
            return f"Error: Directory '{path}' does not exist"

        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory"

        try:
            entries = []
            for entry in sorted(resolved.iterdir()):
                if entry.name.startswith("."):
                    continue  # Skip hidden files
                prefix = "d " if entry.is_dir() else "f "
                entries.append(f"{prefix}{entry.name}")

            if not entries:
                return f"Directory '{path}' is empty"

            return f"Contents of '{path}':\n" + "\n".join(entries)
        except PermissionError:
            return f"Error: Permission denied for '{path}'"

    async def _run_command(self, command: str) -> str:
        """Run a shell command."""
        if not command:
            return "Error: 'command' parameter is required"

        # Security: check allowed commands if configured
        if self.allowed_commands:
            allowed = any(command.strip().startswith(cmd) for cmd in self.allowed_commands)
            if not allowed:
                return f"Error: Command not allowed. Permitted prefixes: {self.allowed_commands}"

        log.info("running_command", command=command, cwd=str(self.working_dir))

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.command_timeout,
                )
            except TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.command_timeout}s"

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = []
            if output:
                result.append(f"stdout:\n{output}")
            if errors:
                result.append(f"stderr:\n{errors}")
            if process.returncode != 0:
                result.append(f"Exit code: {process.returncode}")

            return "\n".join(result) if result else "Command completed with no output"

        except Exception as e:
            return f"Error running command: {e}"

    async def _search_files(self, pattern: str, path: str = ".", file_pattern: str = "*") -> str:
        """Search for a pattern in file contents using grep."""
        if not pattern:
            return "Error: 'pattern' parameter is required"

        resolved = self._resolve_path(path)

        if not resolved.exists():
            return f"Error: Path '{path}' does not exist"

        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory"

        try:
            # Build grep command with line numbers
            # Use --include for file pattern filtering
            cmd = [
                "grep",
                "-rn",  # recursive with line numbers
                "--include",
                file_pattern,
                pattern,
                str(resolved),
            ]

            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.working_dir),
            )

            if result.returncode == 1:
                # grep returns 1 when no matches found
                return f"No matches found for pattern '{pattern}'"

            if result.returncode != 0 and result.stderr:
                return f"Error: {result.stderr.strip()}"

            output = result.stdout.strip()
            if not output:
                return f"No matches found for pattern '{pattern}'"

            # Limit results to prevent token explosion
            lines = output.split("\n")
            max_matches = 50
            if len(lines) > max_matches:
                lines = lines[:max_matches]
                lines.append(
                    f"\n[Truncated - showing first {max_matches} of {len(output.split(chr(10)))} matches]"
                )

            # Convert absolute paths to relative paths
            formatted_lines = []
            for line in lines:
                if line.startswith(str(resolved)):
                    line = line[len(str(resolved)) + 1 :]  # +1 for the slash
                formatted_lines.append(line)

            return "\n".join(formatted_lines)

        except subprocess.TimeoutExpired:
            return "Error: Search timed out after 30 seconds"
        except FileNotFoundError:
            return "Error: grep command not found on this system"
        except Exception as e:
            return f"Error: {e}"

    async def _find_files(self, pattern: str, path: str = ".") -> str:
        """Find files matching a glob pattern within a directory."""
        if not pattern:
            return "Error: 'pattern' parameter is required"

        try:
            # Resolve and validate search path
            search_dir = (self.working_dir / path).resolve()
            if not search_dir.is_relative_to(self.working_dir):
                return f"Error: Path '{path}' is outside the working directory"
            if not search_dir.exists():
                return f"Error: Directory '{path}' does not exist"
            if not search_dir.is_dir():
                return f"Error: '{path}' is not a directory"

            matches = []
            for match in search_dir.glob(pattern):
                # Skip hidden files and directories
                if any(part.startswith(".") for part in match.parts):
                    continue

                # Security check: ensure match is within working directory
                try:
                    relative = match.relative_to(self.working_dir)
                    if match.is_file():
                        matches.append(str(relative))
                except ValueError:
                    continue  # Path is outside working directory

            if not matches:
                return f"No files found matching pattern '{pattern}' in '{path}'"

            # Limit results
            max_files = 100
            matches.sort()
            if len(matches) > max_files:
                total = len(matches)
                matches = matches[:max_files]
                matches.append(f"\n[Truncated - showing first {max_files} of {total} files]")

            return "\n".join(matches)

        except Exception as e:
            return f"Error: {e}"

    async def _edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """Replace specific text in a file."""
        if not path:
            return "Error: 'path' parameter is required"
        if old_text is None or old_text == "":
            return "Error: 'old_text' parameter is required"
        if new_text is None:
            return "Error: 'new_text' parameter is required"

        resolved = self._resolve_path(path)

        if not resolved.exists():
            return f"Error: File '{path}' does not exist"

        if not resolved.is_file():
            return f"Error: '{path}' is not a file"

        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not a text file"

        # Count occurrences of old_text
        count = content.count(old_text)

        if count == 0:
            return f"Error: Text not found in '{path}'. The old_text does not exist in the file."

        if count > 1:
            return f"Error: Text appears {count} times in '{path}'. The old_text must be unique. Please provide more context to make it unique."

        # Perform the replacement
        new_content = content.replace(old_text, new_text, 1)

        try:
            resolved.write_text(new_content, encoding="utf-8")
            rel_path = str(resolved.relative_to(self.working_dir))
            if rel_path not in self.files_written:
                self.files_written.append(rel_path)
            return f"Successfully edited '{path}': replaced {len(old_text)} chars with {len(new_text)} chars"
        except OSError as e:
            raise ToolExecutionError(f"Failed to write file: {e}") from e

    async def _tree(self, path: str = ".", max_depth: int = 3) -> str:
        """Display directory structure as a tree."""
        resolved = self._resolve_path(path)

        if not resolved.exists():
            return f"Error: Directory '{path}' does not exist"

        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory"

        def build_tree(dir_path: Path, prefix: str = "", depth: int = 1) -> list[str]:
            """Recursively build tree representation."""
            if depth > max_depth:
                return []

            lines = []
            try:
                entries = sorted(
                    [e for e in dir_path.iterdir() if not e.name.startswith(".")],
                    key=lambda x: (not x.is_dir(), x.name.lower()),
                )
            except PermissionError:
                return [f"{prefix}[Permission denied]"]

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                entry_type = "[dir]" if entry.is_dir() else "[file]"

                lines.append(f"{prefix}{connector}{entry.name} {entry_type}")

                if entry.is_dir() and depth < max_depth:
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(entry, prefix + extension, depth + 1))

            return lines

        try:
            rel_path = resolved.relative_to(self.working_dir)
            header = f"{rel_path}/" if str(rel_path) != "." else "./"
        except ValueError:
            header = f"{resolved.name}/"

        tree_lines = [header] + build_tree(resolved, "", 1)

        # Limit output size
        max_lines = 200
        if len(tree_lines) > max_lines:
            tree_lines = tree_lines[:max_lines]
            tree_lines.append(f"\n[Truncated - showing first {max_lines} lines]")

        return "\n".join(tree_lines)

    def get_files_written(self) -> list[str]:
        """Get list of files written during this session."""
        return self.files_written.copy()

    def reset(self) -> None:
        """Reset the tool registry state."""
        self.files_written = []
