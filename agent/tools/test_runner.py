"""
Test Runner - executes tests in different languages
With robust error handling for long-running processes.

Supports:
- Go: go test
- Rust: cargo test
- Java: Maven (pom.xml) or Gradle (build.gradle)
- C++: make test / CMake (Bitcoin Core)
- Python: Bitcoin Core functional tests (test/functional/)
"""

import asyncio
import logging
import os
import re
import signal
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

# Default timeout for test execution (in seconds)
DEFAULT_TEST_TIMEOUT = 300  # 5 minutes

# Timeout for graceful process termination before force kill (in seconds)
GRACEFUL_TERMINATION_TIMEOUT = 5


class Language(Enum):
    """Supported programming languages for test execution."""

    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"


class JavaBuildSystem(Enum):
    """Java build system types"""

    MAVEN = "maven"
    GRADLE = "gradle"
    UNKNOWN = "unknown"


@dataclass
class TestResult:
    """Result of a test execution"""

    success: bool
    passed: bool
    output: str
    error: str
    duration_ms: int
    test_name: str
    test_file: str | None = None


class TestRunner:
    """
    Multi-language test runner.
    Supports Go, Rust, Java (Maven/Gradle), and C++.
    """

    def __init__(self, repo_path: Path, language: Language):
        self.repo_path = Path(repo_path)
        self.language = language
        self.timeout = DEFAULT_TEST_TIMEOUT

        # Detect Java build system if needed
        self._java_build_system: JavaBuildSystem | None = None
        self._java_module: str | None = None  # For multi-module projects

    def _detect_java_build_system(self) -> JavaBuildSystem:
        """Detect whether the Java project uses Maven or Gradle"""
        if self._java_build_system is not None:
            return self._java_build_system

        # Check for Gradle first (some projects have both, prefer Gradle)
        gradle_files = [
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        ]
        for gf in gradle_files:
            if (self.repo_path / gf).exists():
                self._java_build_system = JavaBuildSystem.GRADLE
                logger.info(f"Detected Gradle build system in {self.repo_path}")
                return JavaBuildSystem.GRADLE

        # Check for Maven
        if (self.repo_path / "pom.xml").exists():
            self._java_build_system = JavaBuildSystem.MAVEN
            logger.info(f"Detected Maven build system in {self.repo_path}")
            return JavaBuildSystem.MAVEN

        self._java_build_system = JavaBuildSystem.UNKNOWN
        logger.warning(f"Could not detect Java build system in {self.repo_path}")
        return JavaBuildSystem.UNKNOWN

    def _find_maven_module_for_test(self, test_file: str | None) -> str | None:
        """
        Find the Maven module containing a test file.
        For multi-module projects like ZooKeeper, this helps run tests in the correct module.
        """
        if not test_file:
            return None

        test_path = Path(test_file)

        # Walk up the directory tree looking for pom.xml
        current = (
            self.repo_path / test_path.parent
            if not test_path.is_absolute()
            else test_path.parent
        )

        while current != self.repo_path and current != current.parent:
            if (current / "pom.xml").exists():
                # Found a module - return relative path from repo root
                try:
                    rel_path = current.relative_to(self.repo_path)
                    return str(rel_path)
                except ValueError:
                    return None
            current = current.parent

        return None

    def _find_gradle_module_for_test(self, test_file: str | None) -> str | None:
        """
        Find the Gradle module/subproject containing a test file.
        """
        if not test_file:
            return None

        test_path = Path(test_file)
        current = (
            self.repo_path / test_path.parent
            if not test_path.is_absolute()
            else test_path.parent
        )

        while current != self.repo_path and current != current.parent:
            # Check for Gradle build file
            if (current / "build.gradle").exists() or (
                current / "build.gradle.kts"
            ).exists():
                try:
                    rel_path = current.relative_to(self.repo_path)
                    # Convert path to Gradle project notation (e.g., "subproject:subsubproject")
                    return str(rel_path).replace(os.sep, ":")
                except ValueError:
                    return None
            current = current.parent

        return None

    async def _run_command(
        self, cmd: list[str], cwd: Path | None = None, env: dict | None = None
    ) -> tuple[int, str, str]:
        """
        Run a command and return exit code, stdout, stderr.
        Includes robust timeout handling and process cleanup.
        """
        if cwd is None:
            cwd = self.repo_path

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=full_env,
                # Create new process group for clean kill
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
            logger.warning(f"Command timed out after {self.timeout}s: {' '.join(cmd)}")
            await self._kill_process_tree(proc)
            return -1, "", f"Test timed out after {self.timeout}s"

        except asyncio.CancelledError:
            logger.warning(f"Command cancelled: {' '.join(cmd)}")
            await self._kill_process_tree(proc)
            raise

        except (OSError, IOError) as e:
            logger.error(f"Command IO error: {e}")
            await self._kill_process_tree(proc)
            return -2, "", f"IO error: {str(e)}"

        except ValueError as e:
            logger.error(f"Command value error: {e}")
            await self._kill_process_tree(proc)
            return -2, "", f"Invalid command: {str(e)}"

        except Exception as e:
            # Catch-all for unexpected subprocess errors
            logger.error(f"Unexpected command error: {e}")
            await self._kill_process_tree(proc)
            return -2, "", f"Unexpected error: {str(e)}"

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

        except (ProcessLookupError, PermissionError, OSError) as e:
            # Process already gone or we don't have permission - this is expected
            logger.debug(f"Process cleanup: {e}")
        except Exception as e:
            # Unexpected error during cleanup - log but don't crash
            logger.debug(f"Process cleanup unexpected error (usually harmless): {e}")

    async def run_test(
        self,
        test_name: str,
        test_file: str | None = None,
        extra_args: list[str] | None = None,
    ) -> TestResult:
        """
        Run a specific test.

        Args:
            test_name: Name of the test to run
            test_file: Optional specific test file
            extra_args: Additional arguments for the test command

        Returns:
            TestResult with execution details
        """
        start_time = time.time()

        if self.language == Language.GO:
            result = await self._run_go_test(test_name, test_file, extra_args)
        elif self.language == Language.RUST:
            result = await self._run_rust_test(test_name, test_file, extra_args)
        elif self.language == Language.JAVA:
            result = await self._run_java_test(test_name, test_file, extra_args)
        elif self.language == Language.CPP:
            result = await self._run_cpp_test(test_name, test_file, extra_args)
        else:
            raise ValueError(f"Unsupported language: {self.language}")

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    async def _run_go_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """Run Go test"""
        cmd = ["go", "test", "-v", "-run", test_name]

        if test_file:
            # Get the package from the file path
            test_dir = Path(test_file).parent
            cmd.append(f"./{test_dir}/...")
        else:
            cmd.append("./...")

        if extra_args:
            cmd.extend(extra_args)

        exit_code, stdout, stderr = await self._run_command(cmd)

        # Go test passes if exit code is 0
        passed = exit_code == 0
        # Check for specific pass/fail patterns
        if "PASS" in stdout:
            passed = True
        elif "FAIL" in stdout:
            passed = False

        return TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    def _find_rust_package_for_test(self, test_file: str | None) -> str | None:
        """
        Find the Cargo package containing a test file.
        For workspace projects like raft-rs, AlephBFT, aptos-core, sui.
        """
        if not test_file:
            return None

        test_path = Path(test_file)
        current = (
            self.repo_path / test_path.parent
            if not test_path.is_absolute()
            else test_path.parent
        )

        while current != self.repo_path and current != current.parent:
            cargo_toml = current / "Cargo.toml"
            if cargo_toml.exists():
                # Read package name from Cargo.toml
                try:
                    with open(cargo_toml, "r") as f:
                        content = f.read()
                        # Simple parsing - look for name = "package_name"
                        match = re.search(
                            r'\[package\].*?name\s*=\s*["\']([^"\']+)["\']',
                            content,
                            re.DOTALL,
                        )
                        if match:
                            return match.group(1)
                except Exception:
                    pass
            current = current.parent

        return None

    async def _run_rust_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """
        Run Rust test with workspace package support.

        Supports:
        - Single crate projects
        - Workspace projects (uses -p flag to target specific package)
        """
        cmd = ["cargo", "test"]

        # Find package for workspace projects
        package = self._find_rust_package_for_test(test_file)
        if package:
            cmd.extend(["-p", package])
            logger.info(f"Running Rust test in package: {package}")

        # Add test name filter
        cmd.append(test_name)
        cmd.extend(["--", "--nocapture"])

        if extra_args:
            # Insert extra args before "--"
            dash_idx = cmd.index("--")
            for arg in reversed(extra_args):
                cmd.insert(dash_idx, arg)

        exit_code, stdout, stderr = await self._run_command(cmd)

        # Check for success patterns
        passed = exit_code == 0
        if "test result: ok" in stdout:
            passed = True
        elif "test result: FAILED" in stdout or "error" in stderr.lower():
            passed = False

        return TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    async def _run_java_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """
        Run Java test using detected build system (Maven or Gradle).

        Supports:
        - Maven: mvn test -Dtest=TestName
        - Maven multi-module: mvn test -pl module -Dtest=TestName
        - Gradle: gradle test --tests TestName
        - Gradle multi-project: gradle :module:test --tests TestName
        """
        build_system = self._detect_java_build_system()

        if build_system == JavaBuildSystem.GRADLE:
            return await self._run_gradle_test(test_name, test_file, extra_args)
        elif build_system == JavaBuildSystem.MAVEN:
            return await self._run_maven_test(test_name, test_file, extra_args)
        else:
            # Fallback: try Maven first, then Gradle
            result = await self._run_maven_test(test_name, test_file, extra_args)
            if not result.success or "BUILD FAILURE" in result.output:
                result = await self._run_gradle_test(test_name, test_file, extra_args)
            return result

    async def _run_maven_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """
        Run Java test using Maven.

        Handles multi-module projects by detecting the correct module.
        """
        cmd = ["mvn", "test"]

        # Find the module for multi-module projects
        module = self._find_maven_module_for_test(test_file)
        if module:
            cmd.extend(["-pl", module, "-am"])  # -am = also make dependencies
            logger.info(f"Running test in Maven module: {module}")

        # Add test specification
        cmd.append(f"-Dtest={test_name}")

        # Skip compiling other modules' tests for faster execution
        cmd.append("-DfailIfNoTests=false")

        if extra_args:
            cmd.extend(extra_args)

        exit_code, stdout, stderr = await self._run_command(cmd)

        # Check for success patterns
        passed = exit_code == 0 and "BUILD SUCCESS" in stdout
        # Also check for test-specific patterns
        if "Tests run:" in stdout:
            # Parse "Tests run: X, Failures: Y, Errors: Z"
            if "Failures: 0" in stdout and "Errors: 0" in stdout:
                passed = True
            elif "Failures:" in stdout or "Errors:" in stdout:
                passed = False

        return TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    async def _run_gradle_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """
        Run Java test using Gradle.

        Handles multi-project builds by detecting the correct subproject.
        """
        # Detect if gradle wrapper exists
        if (self.repo_path / "gradlew").exists():
            gradle_cmd = "./gradlew"
        else:
            gradle_cmd = "gradle"

        cmd = [gradle_cmd]

        # Find the subproject for multi-project builds
        subproject = self._find_gradle_module_for_test(test_file)
        if subproject:
            # Use Gradle's project path notation
            cmd.append(f":{subproject}:test")
            logger.info(f"Running test in Gradle subproject: {subproject}")
        else:
            cmd.append("test")

        # Add test filter
        cmd.extend(["--tests", test_name])

        # Show test output
        cmd.append("--info")

        if extra_args:
            cmd.extend(extra_args)

        exit_code, stdout, stderr = await self._run_command(cmd)

        # Check for success patterns
        passed = exit_code == 0 and "BUILD SUCCESSFUL" in stdout
        # Also check for test failure patterns
        if "BUILD FAILED" in stdout or "BUILD FAILED" in stderr:
            passed = False

        return TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    def _cpp_test_binary_path(self) -> Path:
        """Bitcoin Core (CMake): build/bin/test_bitcoin[.exe]."""
        name = "test_bitcoin.exe" if os.name == "nt" else "test_bitcoin"
        candidate = self.repo_path / "build" / "bin" / name
        if candidate.exists():
            return candidate
        return self.repo_path / "build" / "src" / "test" / name

    def _is_functional_test(self, test_file: str | None) -> bool:
        """Check if the test file is a Bitcoin Core Python functional test."""
        if not test_file:
            return False
        return test_file.endswith(".py") and "test/functional" in test_file

    def _bitcoind_binary_path(self) -> Path:
        """Locate the bitcoind binary."""
        name = "bitcoind.exe" if os.name == "nt" else "bitcoind"
        candidate = self.repo_path / "build" / "bin" / name
        if candidate.exists():
            return candidate
        return self.repo_path / "build" / "src" / name

    async def _run_functional_test(
        self, test_name: str, test_file: str, extra_args: list[str] | None
    ) -> TestResult:
        """Run a Bitcoin Core Python functional test (test/functional/*.py)."""
        test_path = self.repo_path / test_file
        if not test_path.exists():
            return TestResult(
                success=False,
                passed=False,
                output="",
                error=f"Functional test file not found: {test_path}",
                duration_ms=0,
                test_name=test_name,
                test_file=test_file,
            )

        bitcoind = self._bitcoind_binary_path()
        if not bitcoind.exists():
            return TestResult(
                success=False,
                passed=False,
                output="",
                error=(
                    f"bitcoind not found at {bitcoind}. "
                    "Run agent/scripts/build_bitcoin.sh to compile it."
                ),
                duration_ms=0,
                test_name=test_name,
                test_file=test_file,
            )

        cmd = ["python3", str(test_path)]
        if extra_args:
            cmd.extend(extra_args)

        exit_code, stdout, stderr = await self._run_command(cmd)

        passed = exit_code == 0
        combined = stdout + stderr
        if "Tests successful" in combined or "Passed" in combined:
            passed = True
        elif "Test failed" in combined or "FAILED" in combined:
            passed = False

        return TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    async def _run_cpp_test(
        self, test_name: str, test_file: str | None, extra_args: list[str] | None
    ) -> TestResult:
        """Run C++ unit tests or Python functional tests (Bitcoin Core)."""

        if self._is_functional_test(test_file):
            return await self._run_functional_test(test_name, test_file, extra_args)

        binary = self._cpp_test_binary_path()
        cmake_build_dir = self.repo_path / "build"

        # Bitcoin-style CMake layout
        if (self.repo_path / "CMakeLists.txt").exists() and cmake_build_dir.exists():
            if not binary.exists():
                build_code, build_out, build_err = await self._run_command(
                    ["cmake", "--build", "build", "--target", "test_bitcoin"]
                )
                if build_code != 0:
                    return TestResult(
                        success=False,
                        passed=False,
                        output=build_out,
                        error=f"Build failed: {build_err}",
                        duration_ms=0,
                        test_name=test_name,
                        test_file=test_file,
                    )

            if not binary.exists():
                return TestResult(
                    success=False,
                    passed=False,
                    output="",
                    error=f"test binary not found after build: {binary}",
                    duration_ms=0,
                    test_name=test_name,
                    test_file=test_file,
                )

            cmd = [str(binary), f"--run_test={test_name}"]
            if extra_args:
                cmd.extend(extra_args)
            exit_code, stdout, stderr = await self._run_command(cmd)
            passed = exit_code == 0

            return TestResult(
                success=exit_code >= 0,
                passed=passed,
                output=stdout,
                error=stderr,
                duration_ms=0,
                test_name=test_name,
                test_file=test_file,
            )

        # Legacy: Makefile projects
        build_code, build_out, build_err = await self._run_command(["make", "test"])
        if build_code != 0:
            return TestResult(
                success=False,
                passed=False,
                output=build_out,
                error=f"Build failed: {build_err}",
                duration_ms=0,
                test_name=test_name,
                test_file=test_file,
            )
        test_binary = self.repo_path / "test" / test_name
        if test_binary.exists():
            cmd = [str(test_binary)]
            if extra_args:
                cmd.extend(extra_args)
            exit_code, stdout, stderr = await self._run_command(cmd)
        else:
            exit_code, stdout, stderr = build_code, build_out, build_err
        return TestResult(
            success=exit_code >= 0,
            passed=exit_code == 0,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=test_name,
            test_file=test_file,
        )

    async def run_all_tests(self, pattern: str | None = None) -> list[TestResult]:
        """Run all tests matching a pattern"""
        results = []

        if self.language == Language.GO:
            cmd = ["go", "test", "-v", "./..."]
            if pattern:
                cmd.extend(["-run", pattern])
            exit_code, stdout, stderr = await self._run_command(cmd)
            passed = exit_code == 0

        elif self.language == Language.RUST:
            cmd = ["cargo", "test"]
            if pattern:
                cmd.append(pattern)
            cmd.extend(["--", "--nocapture"])
            exit_code, stdout, stderr = await self._run_command(cmd)
            passed = exit_code == 0 and "test result: ok" in stdout

        elif self.language == Language.JAVA:
            build_system = self._detect_java_build_system()

            if build_system == JavaBuildSystem.GRADLE:
                gradle_cmd = (
                    "./gradlew" if (self.repo_path / "gradlew").exists() else "gradle"
                )
                cmd = [gradle_cmd, "test"]
                if pattern:
                    cmd.extend(["--tests", f"*{pattern}*"])
                exit_code, stdout, stderr = await self._run_command(cmd)
                passed = exit_code == 0 and "BUILD SUCCESSFUL" in stdout

            else:  # Maven or unknown
                cmd = ["mvn", "test"]
                if pattern:
                    cmd.append(f"-Dtest={pattern}")
                exit_code, stdout, stderr = await self._run_command(cmd)
                passed = exit_code == 0 and "BUILD SUCCESS" in stdout
        elif self.language == Language.CPP:
            bin_path = self._cpp_test_binary_path()
            if bin_path.exists():
                cmd = [str(bin_path)]
                if pattern:
                    cmd.append(f"--run_test={pattern}")
                exit_code, stdout, stderr = await self._run_command(cmd)
            else:
                exit_code, stdout, stderr = await self._run_command(
                    ["cmake", "--build", "build", "--target", "test_bitcoin"]
                )
                passed_build = exit_code == 0
                if passed_build and bin_path.exists():
                    cmd = [str(bin_path)]
                    if pattern:
                        cmd.append(f"--run_test={pattern}")
                    exit_code, stdout, stderr = await self._run_command(cmd)
                else:
                    passed = False
                    result = TestResult(
                        success=exit_code >= 0,
                        passed=False,
                        output=stdout,
                        error=stderr,
                        duration_ms=0,
                        test_name=pattern or "all",
                    )
                    results.append(result)
                    return results
            passed = exit_code == 0

        else:
            cmd = ["make", "test"]
            exit_code, stdout, stderr = await self._run_command(cmd)
            passed = exit_code == 0

        result = TestResult(
            success=exit_code >= 0,
            passed=passed,
            output=stdout,
            error=stderr,
            duration_ms=0,
            test_name=pattern or "all",
        )
        results.append(result)

        return results

    async def check_test_exists(self, test_name: str) -> bool:
        """Check if a test exists"""
        if self.language == Language.GO:
            # List tests matching the name
            cmd = ["go", "test", "-list", test_name, "./..."]
            exit_code, stdout, _ = await self._run_command(cmd)
            return exit_code == 0 and test_name in stdout
        elif self.language == Language.RUST:
            cmd = ["cargo", "test", test_name, "--", "--list"]
            exit_code, stdout, _ = await self._run_command(cmd)
            return exit_code == 0 and test_name in stdout

        return True  # Assume exists for other languages


def get_runner(repo_path: Path, language: str) -> TestRunner:
    """
    Create a test runner for the specified language.

    Args:
        repo_path: Path to the repository root.
        language: Programming language (go, rust, java, cpp, c++).

    Returns:
        Configured TestRunner instance.

    Raises:
        ValueError: If the language is not supported.
    """
    lang_map = {
        "go": Language.GO,
        "rust": Language.RUST,
        "java": Language.JAVA,
        "cpp": Language.CPP,
        "c++": Language.CPP,
    }

    lang = lang_map.get(language.lower())
    if lang is None:
        raise ValueError(f"Unsupported language: {language}")

    return TestRunner(repo_path, lang)
