"""
Simplified tools for Baseline ReAct Agent.

This module provides a minimal set of tools for code analysis:
- read_file: Read file content with line numbers
- search_code: Search code using ripgrep with context
- run_command: Execute shell commands
- list_files: Explore repository structure

These tools are intentionally simple to serve as a baseline
for comparing with more sophisticated tool implementations.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from ..core.tool_agent import Tool, tool

# =============================================================================
# Constants
# =============================================================================

# File reading limits
DEFAULT_MAX_LINES = 500
LINE_NUMBER_WIDTH = 6

# Search limits
DEFAULT_CONTEXT_LINES = 2
DEFAULT_MAX_SEARCH_RESULTS = 50
SEARCH_TIMEOUT_SECONDS = 30.0
MAX_SEARCH_OUTPUT_LENGTH = 10000

# Command execution limits
DEFAULT_COMMAND_TIMEOUT = 60.0
MAX_COMMAND_OUTPUT_LENGTH = 8000

# Allowed commands whitelist (read-only, non-destructive commands)
ALLOWED_COMMANDS: tuple[str, ...] = (
    "ls",
    "tree",
    "cat",
    "head",
    "tail",
    "find",
    "du",
    "wc",
    "file",
    "stat",
    "grep",
    "rg",
    "awk",
    "sed",  # read-only usage for viewing
    "less",
    "more",
)

# Directory listing limits
MAX_DIR_LISTING_ITEMS = 100


# =============================================================================
# Tool Factory
# =============================================================================


def create_baseline_tools(repo_root: Path) -> list[Tool]:
    """
    Create the minimal tool set for baseline agent.

    This factory function creates tools that are bound to a specific
    repository path. All file operations are relative to this root.

    Args:
        repo_root: Absolute path to the repository root directory.
            All file paths in tool calls will be resolved relative to this.

    Returns:
        List of Tool objects ready to be used by BaselineReActAgent.
        Currently returns 4 tools: read_file, search_code, run_command, list_files.

    Example:
        ```python
        from pathlib import Path
        from agent.baseline.tools import create_baseline_tools

        tools = create_baseline_tools(Path("/path/to/repo"))
        for tool in tools:
            print(f"Tool: {tool.name} - {tool.description}")
        ```
    """

    @tool(description="Read file content from the repository. Path is relative to repo root.")
    async def read_file(
        path: str,
        start_line: int = 0,
        max_lines: int = DEFAULT_MAX_LINES,
    ) -> str:
        """
        Read file content from the repository with line numbers.

        Args:
            path: File path relative to repository root.
                Leading slashes are automatically stripped.
            start_line: Starting line number (0-indexed, default 0).
            max_lines: Maximum number of lines to read (default 500).
                Use this to read large files in chunks.

        Returns:
            File content with line numbers in the format:
            "File: path (lines X-Y of Z)\\n     1| content..."

            Returns an error message string if the file cannot be read.
        """
        try:
            # Ensure numeric parameters are integers (LLM may pass strings)
            start_line = int(start_line) if start_line is not None else 0
            max_lines = int(max_lines) if max_lines is not None else DEFAULT_MAX_LINES

            path_clean = path.lstrip("/")
            file_path = repo_root / path_clean

            if not file_path.exists():
                return f"Error: File not found: {path}"

            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            # Read file with line numbers
            lines = file_path.read_text(errors="replace").splitlines()

            # Apply line range
            end_line = min(start_line + max_lines, len(lines))
            selected_lines = lines[start_line:end_line]

            # Format with line numbers
            result = []
            for i, line in enumerate(selected_lines, start=start_line + 1):
                result.append(f"{i:{LINE_NUMBER_WIDTH}}| {line}")

            header = f"File: {path} (lines {start_line + 1}-{end_line} of {len(lines)})\n"
            return header + "\n".join(result)

        except PermissionError:
            return f"Error: Permission denied reading file: {path}"
        except UnicodeDecodeError as e:
            return f"Error: Unable to decode file {path}: {e}"
        except OSError as e:
            return f"Error reading file: {e}"

    @tool(
        description="Search for a pattern in code files using ripgrep. "
        "Returns matching lines with context."
    )
    async def search_code(
        pattern: str,
        file_glob: str = "**/*",
        context_lines: int = DEFAULT_CONTEXT_LINES,
        max_results: int = DEFAULT_MAX_SEARCH_RESULTS,
    ) -> str:
        """
        Search for a regex pattern in code files.

        Uses ripgrep (rg) for fast searching, with automatic fallback
        to grep if ripgrep is not available.

        Args:
            pattern: Regular expression pattern to search for.
                Supports Rust regex syntax (similar to PCRE).
            file_glob: Glob pattern to filter files (default "**/*").
                Examples: "**/*.go", "**/*.rs", "src/**/*.py"
            context_lines: Number of context lines before/after match (default 2).
            max_results: Maximum number of matches per file (default 50).

        Returns:
            Matching lines with file paths and line numbers.
            Results are truncated if they exceed 10,000 characters.
        """
        try:
            # Ensure numeric parameters are integers (LLM may pass strings)
            context_lines = int(context_lines) if context_lines is not None else DEFAULT_CONTEXT_LINES
            max_results = int(max_results) if max_results is not None else DEFAULT_MAX_SEARCH_RESULTS

            # Use ripgrep for fast searching
            cmd = [
                "rg",
                "--line-number",
                f"--context={context_lines}",
                f"--max-count={max_results}",
                "--glob",
                file_glob,
                pattern,
                str(repo_root),
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_root,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=SEARCH_TIMEOUT_SECONDS,
            )

            output = stdout.decode("utf-8", errors="replace")

            if not output.strip():
                return f"No matches found for pattern: {pattern}"

            # Truncate if too long
            if len(output) > MAX_SEARCH_OUTPUT_LENGTH:
                output = output[:MAX_SEARCH_OUTPUT_LENGTH] + "\n...(truncated)"

            return f"Search results for '{pattern}':\n{output}"

        except asyncio.TimeoutError:
            return f"Error: Search timed out after {SEARCH_TIMEOUT_SECONDS}s"

        except FileNotFoundError:
            # Fallback to grep if rg not available
            return await _search_with_grep(
                pattern, repo_root, context_lines, max_results
            )

        except OSError as e:
            return f"Error searching: {e}"


    async def _search_with_grep(
        pattern: str,
        repo_root: Path,
        context_lines: int,
        max_results: int,  # noqa: ARG001 - kept for API consistency
    ) -> str:
        """Fallback search using grep when ripgrep is not available."""
        try:
            cmd = [
                "grep",
                "-rn",
                f"-C{context_lines}",
                pattern,
                str(repo_root),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SEARCH_TIMEOUT_SECONDS,
                cwd=repo_root,
                check=False,
            )
            output = result.stdout

            if not output.strip():
                return f"No matches found for pattern: {pattern}"

            if len(output) > MAX_SEARCH_OUTPUT_LENGTH:
                output = output[:MAX_SEARCH_OUTPUT_LENGTH] + "\n...(truncated)"

            return f"Search results for '{pattern}':\n{output}"

        except subprocess.TimeoutExpired:
            return f"Error: Search timed out after {SEARCH_TIMEOUT_SECONDS}s"
        except FileNotFoundError:
            return "Error: Neither ripgrep (rg) nor grep is available"
        except OSError as e:
            return f"Error in grep fallback: {e}"

    @tool(
        description="Execute a read-only shell command in the repository. "
        "Only allows: ls, tree, cat, head, tail, find, du, wc, file, stat, grep, rg, awk, sed."
    )
    async def run_command(
        command: str,
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> str:
        """
        Execute a read-only shell command in the repository directory.

        Commands are executed with the repository root as the working directory.
        Both stdout and stderr are captured and returned.

        Only non-destructive commands are allowed for security.

        Args:
            command: Shell command to execute.
                Must start with an allowed command: ls, tree, cat, head, tail,
                find, du, wc, file, stat, grep, rg, awk, sed.
            timeout: Command timeout in seconds (default 60).
                Long-running commands will be terminated.

        Returns:
            Combined output containing stdout, stderr, and exit code.
            Output is truncated if it exceeds 8,000 characters.
        """
        # Check if command starts with an allowed command
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return "Error: Empty command"

        try:
            timeout_seconds = float(timeout)
        except (TypeError, ValueError):
            return f"Error: Invalid timeout '{timeout}'; must be a number"

        if timeout_seconds <= 0:
            return f"Error: Invalid timeout '{timeout_seconds}'; must be positive"

        base_cmd = cmd_parts[0]
        if base_cmd not in ALLOWED_COMMANDS:
            allowed = ", ".join(ALLOWED_COMMANDS)
            return (
                f"Error: Command '{base_cmd}' is not allowed. "
                f"Only read-only commands are permitted: {allowed}"
            )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_root,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            combined = ""
            if output:
                combined += f"stdout:\n{output}\n"
            if errors:
                combined += f"stderr:\n{errors}\n"
            if process.returncode != 0:
                combined += f"exit code: {process.returncode}\n"

            if not combined.strip():
                combined = "(no output)"

            # Truncate if too long
            if len(combined) > MAX_COMMAND_OUTPUT_LENGTH:
                combined = combined[:MAX_COMMAND_OUTPUT_LENGTH] + "\n...(truncated)"

            return combined

        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout_seconds}s"
        except OSError as e:
            return f"Error executing command: {e}"

    @tool(description="List files and directories. Use to explore repository structure.")
    async def list_files(
        path: str = ".",
        pattern: str = "*",
    ) -> str:
        """
        List files and directories in a path.

        Args:
            path: Directory path relative to repo root (default ".").
                Leading slashes are automatically stripped.
            pattern: Glob pattern to filter files (default "*").
                Only applies to the immediate directory, not recursive.

        Returns:
            Formatted list of files and directories.
            Directories are marked with a trailing slash.
            Results are limited to 100 items.
        """
        try:
            target = repo_root / path.lstrip("/")

            if not target.exists():
                return f"Error: Path not found: {path}"

            if target.is_file():
                size = target.stat().st_size
                return f"{path} (file, {size:,} bytes)"

            # List directory contents
            items = []
            for item in sorted(target.glob(pattern)):
                try:
                    rel_path = item.relative_to(repo_root)
                    if item.is_dir():
                        items.append(f"  {rel_path}/")
                    else:
                        items.append(f"  {rel_path}")
                except ValueError:
                    # Item is outside repo_root, skip it
                    continue

                # Limit output
                if len(items) >= MAX_DIR_LISTING_ITEMS:
                    items.append(f"  ...(more than {MAX_DIR_LISTING_ITEMS} items)")
                    break

            if not items:
                return f"Directory {path} is empty or no files match pattern '{pattern}'"

            return f"Contents of {path}:\n" + "\n".join(items)

        except PermissionError:
            return f"Error: Permission denied accessing: {path}"
        except OSError as e:
            return f"Error listing files: {e}"

    return [read_file, search_code, run_command, list_files]
