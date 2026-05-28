"""
Unit tests for Executor and TestRunner modules.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.core.executor import ExecutionResult, Executor, format_error_for_reflection
from agent.tools.test_runner import Language, TestResult, TestRunner, get_runner

# ============================================================
# Executor Tests
# ============================================================


class TestExecutor:
    """Tests for the Executor class."""

    @pytest.fixture
    def executor(self, temp_repo_dir):
        """Create an Executor with temp directory."""
        return Executor(
            working_dir=temp_repo_dir, timeout=10  # Short timeout for tests
        )

    @pytest.mark.asyncio
    async def test_execute_command_success(self, executor):
        """Test executing a simple successful command."""
        result = await executor.execute_command(["echo", "hello"])

        assert result.success
        assert result.exit_code == 0
        assert "hello" in result.output
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_command_failure(self, executor):
        """Test executing a failing command."""
        result = await executor.execute_command(["false"])  # Returns exit code 1

        assert not result.success
        assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, executor):
        """Test executing a non-existent command."""
        result = await executor.execute_command(["nonexistent_command_xyz"])

        assert not result.success

    @pytest.mark.asyncio
    async def test_execute_command_with_stderr(self, executor):
        """Test command that writes to stderr."""
        # Use a command that writes to stderr
        result = await executor.execute_command(["sh", "-c", "echo error >&2; exit 1"])

        assert not result.success
        assert "error" in result.error

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, temp_repo_dir):
        """Test command timeout handling."""
        executor = Executor(working_dir=temp_repo_dir, timeout=1)

        result = await executor.execute_command(["sleep", "10"])

        assert not result.success
        assert result.exit_code == -1
        assert "timed out" in result.error.lower() or "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_command_with_cwd(self, executor, temp_repo_dir):
        """Test executing command with specific working directory."""
        result = await executor.execute_command(["pwd"], cwd=temp_repo_dir)

        assert result.success
        assert str(temp_repo_dir) in result.output

    @pytest.mark.asyncio
    async def test_execute_command_string_input(self, executor):
        """Test that string commands are split correctly."""
        result = await executor.execute_command("echo hello world")

        assert result.success
        # Note: "world" may be treated as separate arg
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_execute_python(self, executor, temp_repo_dir):
        """Test executing Python code."""
        code = "print('hello from python')"
        result = await executor.execute_python(code)

        assert result.success
        assert "hello from python" in result.output

    @pytest.mark.asyncio
    async def test_execute_python_with_error(self, executor):
        """Test Python code with syntax error."""
        code = "print('unclosed"
        result = await executor.execute_python(code)

        assert not result.success
        assert "SyntaxError" in result.error or "syntax" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_python_with_exception(self, executor):
        """Test Python code that raises exception."""
        code = "raise ValueError('test error')"
        result = await executor.execute_python(code)

        assert not result.success
        assert "ValueError" in result.error
        assert "test error" in result.error

    @pytest.mark.asyncio
    async def test_execute_go_test(self, executor, temp_repo_dir):
        """Test Go test execution (mocked for environments without Go)."""
        # This test verifies the command is constructed correctly
        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "PASS", "")

            result = await executor.execute_go_test("TestExample", cwd=temp_repo_dir)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "go" in call_args
            assert "test" in call_args
            assert "TestExample" in call_args

    @pytest.mark.asyncio
    async def test_execute_rust_test(self, executor, temp_repo_dir):
        """Test Rust test execution (mocked)."""
        # execute_rust_test passes a string command, so use_shell=True and _run_shell_command is called
        with patch.object(executor, "_run_shell_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "test result: ok", "")

            result = await executor.execute_rust_test("test_example", cwd=temp_repo_dir)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "cargo" in call_args
            assert "test" in call_args
            assert "test_example" in call_args

    @pytest.mark.asyncio
    async def test_execution_result_fields(self, executor):
        """Test that ExecutionResult has all expected fields."""
        result = await executor.execute_command(["echo", "test"])

        assert hasattr(result, "success")
        assert hasattr(result, "output")
        assert hasattr(result, "error")
        assert hasattr(result, "exit_code")
        assert hasattr(result, "duration_ms")


# ============================================================
# Error Analysis Tests
# ============================================================


class TestErrorAnalysis:
    """Tests for error analysis functions."""

    def test_format_error_for_reflection_success(self):
        """Test formatting a successful result."""
        result = ExecutionResult(
            success=True, output="PASS", error="", exit_code=0, duration_ms=100
        )

        formatted = format_error_for_reflection(result)
        assert formatted == ""

    def test_format_error_for_reflection_failure(self):
        """Test formatting a failed result."""
        result = ExecutionResult(
            success=False,
            output="some output",
            error="syntax error: unexpected }",
            exit_code=1,
            duration_ms=50,
        )

        formatted = format_error_for_reflection(result)

        assert "Exit Code: 1" in formatted
        assert "Duration: 50ms" in formatted
        assert "STDOUT" in formatted
        assert "some output" in formatted
        assert "STDERR" in formatted
        assert "syntax error" in formatted


# ============================================================
# Test Runner Tests
# ============================================================


class TestTestRunner:
    """Tests for the TestRunner class."""

    @pytest.fixture
    def go_runner(self, temp_repo_dir):
        """Create a Go TestRunner."""
        return TestRunner(temp_repo_dir, Language.GO)

    @pytest.fixture
    def rust_runner(self, temp_repo_dir):
        """Create a Rust TestRunner."""
        return TestRunner(temp_repo_dir, Language.RUST)

    @pytest.fixture
    def java_runner(self, temp_repo_dir):
        """Create a Java TestRunner."""
        return TestRunner(temp_repo_dir, Language.JAVA)

    def test_get_runner_go(self, temp_repo_dir):
        """Test getting a Go runner."""
        runner = get_runner(temp_repo_dir, "go")
        assert runner.language == Language.GO

    def test_get_runner_rust(self, temp_repo_dir):
        """Test getting a Rust runner."""
        runner = get_runner(temp_repo_dir, "rust")
        assert runner.language == Language.RUST

    def test_get_runner_java(self, temp_repo_dir):
        """Test getting a Java runner."""
        runner = get_runner(temp_repo_dir, "java")
        assert runner.language == Language.JAVA

    def test_get_runner_cpp(self, temp_repo_dir):
        """Test getting a C++ runner."""
        runner = get_runner(temp_repo_dir, "cpp")
        assert runner.language == Language.CPP

        runner2 = get_runner(temp_repo_dir, "c++")
        assert runner2.language == Language.CPP

    def test_get_runner_invalid(self, temp_repo_dir):
        """Test getting a runner with invalid language."""
        with pytest.raises(ValueError):
            get_runner(temp_repo_dir, "invalid_language")

    @pytest.mark.asyncio
    async def test_run_go_test(self, go_runner):
        """Test running a Go test (mocked)."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (
                0,
                "=== RUN   TestExample\n--- PASS: TestExample",
                "",
            )

            result = await go_runner.run_test("TestExample")

            assert result.success
            assert result.passed
            assert "PASS" in result.output

    @pytest.mark.asyncio
    async def test_run_go_test_fail(self, go_runner):
        """Test Go test failure detection."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (
                1,
                "=== RUN   TestExample\n--- FAIL: TestExample",
                "",
            )

            result = await go_runner.run_test("TestExample")

            assert result.success  # Ran successfully
            assert not result.passed  # But test failed
            assert "FAIL" in result.output

    @pytest.mark.asyncio
    async def test_run_rust_test(self, rust_runner):
        """Test running a Rust test (mocked)."""
        with patch.object(
            rust_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "test test_example ... ok\ntest result: ok", "")

            result = await rust_runner.run_test("test_example")

            assert result.success
            assert result.passed

    @pytest.mark.asyncio
    async def test_run_java_test(self, java_runner):
        """Test running a Java test (mocked)."""
        with patch.object(
            java_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "BUILD SUCCESS", "")

            result = await java_runner.run_test("TestExample")

            assert result.success
            assert result.passed

    @pytest.mark.asyncio
    async def test_run_test_with_file(self, go_runner):
        """Test running test with specific file."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "PASS", "")

            await go_runner.run_test("TestExample", test_file="raft/raft_test.go")

            call_args = mock_run.call_args[0][0]
            assert "./raft/..." in str(call_args) or "raft" in str(call_args)

    @pytest.mark.asyncio
    async def test_run_test_timeout(self, temp_repo_dir):
        """Test test runner timeout."""
        runner = TestRunner(temp_repo_dir, Language.GO)
        runner.timeout = 1

        with patch.object(runner, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (-1, "", "Test timed out after 1s")

            result = await runner.run_test("TestSlow")

            assert not result.success
            assert (
                "timed out" in result.error.lower() or "timeout" in result.error.lower()
            )

    @pytest.mark.asyncio
    async def test_run_all_tests(self, go_runner):
        """Test running all tests."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "PASS\nok package 1.234s", "")

            results = await go_runner.run_all_tests()

            assert len(results) == 1
            assert results[0].passed

    @pytest.mark.asyncio
    async def test_run_all_tests_with_pattern(self, go_runner):
        """Test running all tests with pattern filter."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "PASS", "")

            await go_runner.run_all_tests(pattern="TestSafety")

            call_args = mock_run.call_args[0][0]
            assert "TestSafety" in str(call_args)

    @pytest.mark.asyncio
    async def test_check_test_exists_go(self, go_runner):
        """Test checking if a Go test exists."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "TestExample\n", "")

            exists = await go_runner.check_test_exists("TestExample")
            assert exists

    @pytest.mark.asyncio
    async def test_check_test_not_exists_go(self, go_runner):
        """Test checking if a Go test doesn't exist."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "", "")  # Empty output

            exists = await go_runner.check_test_exists("TestNonexistent")
            assert not exists

    @pytest.mark.asyncio
    async def test_test_result_fields(self, go_runner):
        """Test TestResult has all expected fields."""
        with patch.object(
            go_runner, "_run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (0, "PASS", "")

            result = await go_runner.run_test("TestExample")

            assert hasattr(result, "success")
            assert hasattr(result, "passed")
            assert hasattr(result, "output")
            assert hasattr(result, "error")
            assert hasattr(result, "duration_ms")
            assert hasattr(result, "test_name")


# ============================================================
# Process Cleanup Tests
# ============================================================


class TestProcessCleanup:
    """Tests for process cleanup and timeout handling."""

    @pytest.mark.asyncio
    async def test_kill_process_tree_none(self, temp_repo_dir):
        """Test _kill_process_tree with None process."""
        executor = Executor(working_dir=temp_repo_dir)

        # Should not raise
        await executor._kill_process_tree(None)

    @pytest.mark.asyncio
    async def test_cleanup_on_timeout(self, temp_repo_dir):
        """Test that process is cleaned up on timeout."""
        executor = Executor(working_dir=temp_repo_dir, timeout=1)

        # Start a long-running command
        result = await executor.execute_command(["sleep", "100"])

        assert not result.success
        assert result.exit_code == -1

        # Give a moment for cleanup
        await asyncio.sleep(0.1)

        # The process should be terminated (can't easily verify, but command should complete)

    @pytest.mark.asyncio
    async def test_concurrent_commands(self, temp_repo_dir):
        """Test running multiple commands concurrently."""
        executor = Executor(working_dir=temp_repo_dir, timeout=10)

        async def run_echo(msg):
            return await executor.execute_command(["echo", msg])

        results = await asyncio.gather(
            run_echo("one"), run_echo("two"), run_echo("three")
        )

        assert all(r.success for r in results)
        outputs = [r.output.strip() for r in results]
        assert "one" in outputs
        assert "two" in outputs
        assert "three" in outputs
