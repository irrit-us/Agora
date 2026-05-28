#!/usr/bin/env python3
"""
Test runner script for Consensus Bug Hunter.
Provides convenient commands for running different test suites.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> int:
    """Run a command and return exit code."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


def main():
    parser = argparse.ArgumentParser(description="Run Consensus Bug Hunter tests")
    parser.add_argument(
        "--suite",
        choices=[
            "all",
            "unit",
            "integration",
            "e2e",
            "api",
            "memory",
            "executor",
            "tools",
            "orchestrator",
        ],
        default="all",
        help="Test suite to run",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")

    args = parser.parse_args()

    # Base command
    tests_dir = Path(__file__).parent
    agent_dir = tests_dir.parent

    cmd = [sys.executable, "-m", "pytest"]

    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term"])

    # Add verbose if requested
    if args.verbose:
        cmd.append("-v")

    # Skip slow tests if --fast
    if args.fast:
        cmd.extend(["-m", "not slow"])

    # Determine which tests to run
    suite = args.suite

    if suite == "all":
        cmd.append(str(tests_dir))
    elif suite == "unit":
        cmd.extend(
            [
                str(tests_dir / "test_memory_modules.py"),
                str(tests_dir / "test_executor.py"),
            ]
        )
    elif suite == "integration":
        cmd.extend(["-m", "integration", str(tests_dir)])
    elif suite == "e2e":
        cmd.extend(["-m", "e2e", str(tests_dir)])
    elif suite == "api":
        cmd.extend(["-m", "api", str(tests_dir / "test_api_connectivity.py")])
    elif suite == "memory":
        cmd.append(str(tests_dir / "test_memory_modules.py"))
    elif suite == "executor":
        cmd.append(str(tests_dir / "test_executor.py"))
    elif suite == "tools":
        cmd.append(str(tests_dir / "test_tools.py"))
    elif suite == "orchestrator":
        cmd.append(str(tests_dir / "test_orchestrator.py"))

    # Run tests from agent directory
    return run_command(cmd)


if __name__ == "__main__":
    sys.exit(main())
