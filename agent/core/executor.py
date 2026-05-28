"""
Code Executor - Executes code/commands and returns results with full traceback
Supports self-healing reflection loops by providing detailed error information
"""

import asyncio
import logging
import os
import re
import signal
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

# Default timeout for command execution (in seconds)
DEFAULT_COMMAND_TIMEOUT = 300  # 5 minutes

# Timeout for graceful process termination before force kill (in seconds)
GRACEFUL_TERMINATION_TIMEOUT = 5


@dataclass
class ExecutionResult:
    """Result of code/command execution"""

    success: bool
    output: str
    error: str
    exit_code: int
    duration_ms: int


class Executor:
    """
    Code and command executor with robust error handling.
    Provides detailed traceback information for self-healing loops.

    Features:
    - Enforces working directory to prevent accidental execution in wrong directory
    - Strips dangerous 'cd /' patterns from commands
    - Logs actual working directory for debugging
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        timeout: int = DEFAULT_COMMAND_TIMEOUT,
        env: dict | None = None,
        enforce_working_dir: bool = True,  # New: enforce working directory
    ):
        self.working_dir = Path(working_dir).resolve() if working_dir else Path.cwd()
        self.timeout = timeout
        self.env = env or {}
        self.enforce_working_dir = enforce_working_dir

        # Validate working directory exists
        if not self.working_dir.exists():
            raise ValueError(f"Working directory does not exist: {self.working_dir}")

        logger.info(f"Executor initialized with working_dir: {self.working_dir}")

    async def execute_python(self, code: str) -> ExecutionResult:
        """
        Execute Python code string.
        Returns (success, output) with full traceback on failure.
        """
        start_time = time.time()

        try:
            # Write code to temp file for better error messages
            temp_file = self.working_dir / "_temp_exec.py"
            try:
                temp_file.write_text(code)

                result = await self._run_command(
                    [sys.executable, str(temp_file)], cwd=self.working_dir
                )
            finally:
                if temp_file.exists():
                    temp_file.unlink()

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=result[0] == 0,
                output=result[1],
                error=result[2],
                exit_code=result[0],
                duration_ms=duration_ms,
            )

        except (OSError, IOError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"IO error during Python execution: {e}",
                exit_code=-1,
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Catch-all for unexpected subprocess errors
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unexpected execution error:\n{traceback.format_exc()}",
                exit_code=-1,
                duration_ms=duration_ms,
            )

    async def execute_command(
        self, command: str | list[str], cwd: Path | None = None
    ) -> ExecutionResult:
        """
        Execute shell command.
        Returns result with full output/error.

        If enforce_working_dir is True, dangerous 'cd /' patterns are stripped
        and the command is always executed in the configured working directory.
        """
        start_time = time.time()

        # Determine working directory
        working_dir = cwd or self.working_dir
        if working_dir:
            working_dir = Path(working_dir).resolve()

        # Process command
        if isinstance(command, str):
            # Strip dangerous cd patterns that would change to wrong directory
            if self.enforce_working_dir:
                original_cmd = command
                command = self._sanitize_command(command)
                if command != original_cmd:
                    logger.warning(
                        f"Sanitized command: '{original_cmd[:100]}...' -> '{command[:100]}...'"
                    )
            cmd = command
            use_shell = True
        else:
            cmd = command
            use_shell = False

        logger.debug(
            f"Executing command in {working_dir}: {cmd[:200] if isinstance(cmd, str) else cmd}"
        )

        try:
            if use_shell:
                exit_code, stdout, stderr = await self._run_shell_command(
                    cmd, cwd=working_dir
                )
            else:
                exit_code, stdout, stderr = await self._run_command(
                    cmd, cwd=working_dir
                )
            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=exit_code == 0,
                output=stdout,
                error=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except (OSError, IOError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"IO error during command execution: {e}",
                exit_code=-1,
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Catch-all for unexpected subprocess errors
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unexpected command error:\n{traceback.format_exc()}",
                exit_code=-1,
                duration_ms=duration_ms,
            )

    def _sanitize_command(self, command: str) -> str:
        """
        Sanitize command to prevent accidental directory changes.

        Removes patterns like:
        - 'cd / &&' or 'cd / ;'
        - 'cd /some/absolute/path &&' (outside working dir)
        """
        # Pattern: cd <absolute-path-outside-working-dir> && or ;
        # We want to strip 'cd /' but keep 'cd ./subdir' or 'cd subdir'

        # Remove 'cd / &&' or 'cd / ;' patterns
        command = re.sub(r"\bcd\s+/\s*[;&]+\s*", "", command)

        # Remove 'cd /absolute/path &&' patterns (but keep relative paths)
        # Only strip if it's changing to a directory outside working_dir
        def check_cd_target(match):
            target = match.group(1).strip()
            # Keep relative paths and paths starting with .
            if not target.startswith("/") or target.startswith("./"):
                return match.group(0)
            # Strip absolute paths that go elsewhere
            return ""

        command = re.sub(r"\bcd\s+(/[^\s;&#|]+)\s*[;&]+\s*", check_cd_target, command)

        return command.strip()

    async def execute_go_test(
        self, test_name: str, package: str = "./...", cwd: Path | None = None
    ) -> ExecutionResult:
        """Execute Go test"""
        cmd = ["go", "test", "-v", "-run", test_name, package]
        return await self.execute_command(cmd, cwd=cwd)

    async def execute_rust_test(
        self, test_name: str, cwd: Path | None = None, package: str | None = None
    ) -> ExecutionResult:
        """
        Execute Rust test with workspace package support.

        Args:
            test_name: Name of the test to run
            cwd: Working directory (defaults to self.working_dir)
            package: Optional package name for workspace projects (e.g., "aleph-bft", "harness")

        Returns:
            ExecutionResult with test output
        """
        if package:
            cmd = f"cargo test -p {package} {test_name} -- --nocapture"
        else:
            cmd = f"cargo test {test_name} -- --nocapture"
        return await self.execute_command(cmd, cwd=cwd)

    async def execute_java_test(
        self,
        test_name: str,
        cwd: Path | None = None,
        build_system: str = "auto",
        module: str | None = None,
    ) -> ExecutionResult:
        """
        Execute Java test with auto-detection of build system.

        Args:
            test_name: Name of the test class or method
            cwd: Working directory (defaults to self.working_dir)
            build_system: "maven", "gradle", or "auto" (default)
            module: Optional module/subproject for multi-module builds

        Returns:
            ExecutionResult with test output
        """
        working_dir = Path(cwd) if cwd else self.working_dir

        # Auto-detect build system if needed
        if build_system == "auto":
            if (working_dir / "build.gradle").exists() or (
                working_dir / "build.gradle.kts"
            ).exists():
                build_system = "gradle"
            elif (working_dir / "pom.xml").exists():
                build_system = "maven"
            else:
                build_system = "maven"  # Default to maven

        if build_system == "gradle":
            # Use gradle wrapper if available
            if (working_dir / "gradlew").exists():
                gradle_cmd = "./gradlew"
            else:
                gradle_cmd = "gradle"

            if module:
                cmd = f"{gradle_cmd} :{module}:test --tests {test_name} --info"
            else:
                cmd = f"{gradle_cmd} test --tests {test_name} --info"
        else:
            # Maven
            if module:
                cmd = f"mvn test -pl {module} -am -Dtest={test_name} -DfailIfNoTests=false"
            else:
                cmd = f"mvn test -Dtest={test_name} -DfailIfNoTests=false"

        return await self.execute_command(cmd, cwd=working_dir)

    async def _run_command(
        self, cmd: list[str], cwd: Path | None = None
    ) -> tuple[int, str, str]:
        """
        Run command (as list) and return (exit_code, stdout, stderr).
        Includes robust timeout handling and process cleanup.
        """
        working_dir = cwd or self.working_dir

        # Build environment
        full_env = os.environ.copy()
        full_env.update(self.env)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=full_env,
                start_new_session=True,  # Create new process group for clean kill
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )

            return (
                proc.returncode or 0,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )

        except asyncio.TimeoutError:
            logger.warning(f"Command timed out after {self.timeout}s: {' '.join(cmd)}")
            await self._kill_process_tree(proc)
            return (-1, "", f"Command timed out after {self.timeout}s")

        except asyncio.CancelledError:
            logger.warning(f"Command cancelled: {' '.join(cmd)}")
            await self._kill_process_tree(proc)
            raise

        except (OSError, IOError) as e:
            logger.error(f"Command IO error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"IO error: {str(e)}")

        except ValueError as e:
            logger.error(f"Command value error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"Invalid command or arguments: {str(e)}")

        except Exception as e:
            # Catch-all for unexpected errors - preserve for debugging
            logger.error(f"Unexpected command error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"Unexpected error: {str(e)}\n{traceback.format_exc()}")

    async def _run_shell_command(
        self, cmd: str, cwd: Path | None = None
    ) -> tuple[int, str, str]:
        """
        Run shell command (as string, supports pipes, redirects, etc.).
        Returns (exit_code, stdout, stderr).
        """
        working_dir = cwd or self.working_dir

        # Build environment
        full_env = os.environ.copy()
        full_env.update(self.env)

        proc = None
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=full_env,
                start_new_session=True,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )

            return (
                proc.returncode or 0,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )

        except asyncio.TimeoutError:
            logger.warning(
                f"Shell command timed out after {self.timeout}s: {cmd[:100]}"
            )
            await self._kill_process_tree(proc)
            return (-1, "", f"Command timed out after {self.timeout}s")

        except asyncio.CancelledError:
            logger.warning(f"Shell command cancelled: {cmd[:100]}")
            await self._kill_process_tree(proc)
            raise

        except (OSError, IOError) as e:
            logger.error(f"Shell command IO error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"IO error: {str(e)}")

        except ValueError as e:
            logger.error(f"Shell command value error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"Invalid command: {str(e)}")

        except Exception as e:
            # Catch-all for unexpected errors - preserve for debugging
            logger.error(f"Unexpected shell command error: {e}")
            await self._kill_process_tree(proc)
            return (-2, "", f"Unexpected error: {str(e)}\n{traceback.format_exc()}")

    async def _kill_process_tree(self, proc: asyncio.subprocess.Process | None):
        """Kill process and all its children safely"""
        if proc is None:
            return

        try:
            # Try graceful termination first
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=GRACEFUL_TERMINATION_TIMEOUT)
                except asyncio.TimeoutError:
                    pass

            # Force kill if still running
            if proc.returncode is None:
                proc.kill()
                try:
                    # Kill process group on Unix
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

        except Exception as e:
            logger.debug(f"Process cleanup error (usually harmless): {e}")


def format_error_for_reflection(result: ExecutionResult) -> str:
    """
    Format execution error for reflection loop.
    Provides raw error information - the agent will analyze and fix autonomously.
    """
    if result.success:
        return ""

    error_info = []
    error_info.append(f"Exit Code: {result.exit_code}")
    error_info.append(f"Duration: {result.duration_ms}ms")

    if result.output:
        error_info.append(f"\n=== STDOUT ===\n{result.output}")

    if result.error:
        error_info.append(f"\n=== STDERR ===\n{result.error}")

    return "\n".join(error_info)
