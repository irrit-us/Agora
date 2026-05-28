"""
Command-line runner for Baseline ReAct Agent.

This module provides a CLI interface for running the baseline agent
against consensus protocol repositories.

Usage:
    python -m agent.baseline.runner --repo raft --target raft.go
    python -m agent.baseline.runner --repo sui --target consensus/core/src/dag_state.rs
    python -m agent.baseline.runner --repo hotstuff --verbose
    python -m agent.baseline.runner --repo efficient-epaxos --max-iterations 50

Examples:
    # Analyze etcd raft with specific files
    $ python -m agent.baseline.runner --repo raft --target raft.go log.go

    # Analyze entire hotstuff repo with verbose logging
    $ python -m agent.baseline.runner --repo hotstuff -v

    # Use a specific model
    $ python -m agent.baseline.runner --repo sui --model openai/gpt-4o
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .react_agent import AnalysisResult, ReActStep

# =============================================================================
# Constants
# =============================================================================

# Supported repositories and their relative paths
REPO_PATHS: dict[str, str] = {
    # CFT Protocols
    "raft": "raft",
    "raft-rs": "raft-rs",
    "hashicorp-raft": "hashicorp-raft",
    "dragonboat": "dragonboat",
    "efficient-epaxos": "efficient-epaxos",
    "ratis": "ratis",
    "zookeeper": "zookeeper",
    "fabric": "fabric",
    # BFT Protocols
    "library": "library",
    "cometbft": "cometbft",
    "hotstuff": "hotstuff",
    "AlephBFT": "AlephBFT",
    "aptos-core": "aptos-core",
    "sui": "sui",
}

# Default configuration
DEFAULT_MAX_ITERATIONS = 30
DEFAULT_OUTPUT_DIR = "agent/data/baseline_results"

# Exit codes
EXIT_SUCCESS = 0
EXIT_NO_BUGS = 1
EXIT_ERROR = 2
EXIT_INTERRUPTED = 130


# =============================================================================
# Logging Setup
# =============================================================================


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for the runner.

    Args:
        verbose: If True, enable DEBUG level logging.
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# =============================================================================
# Path Resolution
# =============================================================================


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.resolve()


def get_repo_path(repo_name: str) -> Path:
    """
    Get the absolute path to a repository.

    Args:
        repo_name: Name of the repository.

    Returns:
        Absolute path to the repository.

    Raises:
        ValueError: If repository is unknown or not found.
    """
    repo_dir = REPO_PATHS.get(repo_name)
    if not repo_dir:
        available = ", ".join(REPO_PATHS.keys())
        raise ValueError(f"Unknown repository: {repo_name}. Available: {available}")

    repo_path = get_project_root() / repo_dir
    if not repo_path.exists():
        raise ValueError(f"Repository not found at: {repo_path}")

    return repo_path


# =============================================================================
# Result Handling
# =============================================================================


def save_result(result: "AnalysisResult", output_dir: Path) -> Path:
    """
    Save analysis result to a JSON file.

    The filename includes the model name for easy identification of
    which model was used for the analysis.

    Args:
        result: Analysis result to save.
        output_dir: Directory to save the result in.

    Returns:
        Path to the saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = result.model_safe_name
    filename = f"baseline_{result.repo_name}_{model_safe}_{timestamp}.json"
    output_path = output_dir / filename

    data = {
        **result.to_dict(),
        "timestamp": timestamp,
        "version": "0.1.0",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


def print_result(result: "AnalysisResult") -> None:
    """
    Print analysis result to console.

    Args:
        result: Analysis result to print.
    """
    separator = "=" * 60

    print(f"\n{separator}")
    print(f"BASELINE ANALYSIS RESULT: {result.repo_name}")
    print(separator)

    print("\nStatistics:")
    print(f"  Iterations:     {result.iterations}")
    print(f"  Tool calls:     {result.tool_calls}")
    print(f"  Duration:       {result.duration_ms / 1000:.1f}s")
    print(f"  Files analyzed: {len(result.files_analyzed)}")

    # Token usage statistics
    token_usage = result.token_usage
    if token_usage:
        print("\nToken Usage:")
        print(f"  Prompt:         {token_usage.get('prompt_tokens', 0):,}")
        print(f"  Completion:     {token_usage.get('completion_tokens', 0):,}")
        print(f"  Total:          {token_usage.get('total_tokens', 0):,}")
        cached = token_usage.get("cached_tokens", 0)
        if cached > 0:
            print(f"  Cached:         {cached:,}")
        reasoning = token_usage.get("reasoning_tokens", 0)
        if reasoning > 0:
            print(f"  Reasoning:      {reasoning:,}")
        cost = token_usage.get("cost", 0.0)
        if cost > 0:
            print(f"  Cost:           ${cost:.6f}")

    if result.error:
        print(f"\nError: {result.error}")

    print(f"\nBugs Found: {len(result.bugs_found)}")

    for i, bug in enumerate(result.bugs_found, 1):
        print(f"\n--- Bug #{i} ---")
        location = bug.file
        if bug.line:
            location += f":{bug.line}"
        print(f"  Location:    {location}")
        print(f"  Type:        {bug.bug_type}")
        print(f"  Severity:    {bug.severity}")

        desc = bug.description
        if len(desc) > 200:
            desc = desc[:200] + "..."
        print(f"  Description: {desc}")

    if result.final_response and not result.bugs_found:
        print("\nFinal Analysis:")
        response = result.final_response
        if len(response) > 1000:
            response = response[:1000] + "..."
        print(response)

    print(f"\n{separator}")


def load_trace_from_jsonl(trace_path: Path) -> list[dict]:
    """
    Load execution trace steps from a JSONL file.

    Args:
        trace_path: Path to the JSONL trace file.

    Returns:
        List of step dictionaries (excludes header/footer).
    """
    steps = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "step":
                    steps.append(data)
            except json.JSONDecodeError:
                continue
    return steps


def generate_markdown_report_from_jsonl(
    trace_path: Path,
    result: "AnalysisResult",
) -> Path:
    """
    Generate a Markdown report from a JSONL trace file.

    This is used when streaming mode is enabled - the trace is read
    from the JSONL file instead of from memory.

    Args:
        trace_path: Path to the JSONL trace file.
        result: Analysis result (for summary and bug info).

    Returns:
        Path to the generated markdown file.
    """
    md_path = trace_path.with_suffix(".md")

    # Load steps from JSONL
    steps = load_trace_from_jsonl(trace_path)

    # Extract token usage
    token_usage = result.token_usage or {}
    total_tokens = token_usage.get("total_tokens", 0)
    cost = token_usage.get("cost", 0.0)

    lines = [
        f"# Baseline Analysis Report: {result.repo_name}",
        "",
        f"**Model:** {result.model}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Duration | {result.duration_ms / 1000:.1f}s |",
        f"| Iterations | {result.iterations} |",
        f"| Tool Calls | {result.tool_calls} |",
        f"| Files Analyzed | {len(result.files_analyzed)} |",
        f"| Bugs Found | {len(result.bugs_found)} |",
        f"| Total Tokens | {total_tokens:,} |",
        f"| Cost | ${cost:.6f} |",
        "",
    ]

    if result.error:
        lines.extend([
            "## Error",
            "",
            f"```",
            result.error,
            "```",
            "",
        ])

    # Execution Trace from JSONL
    lines.extend([
        "## Execution Trace",
        "",
    ])

    for step in steps:
        iteration = step.get("iteration", 0)
        thought = step.get("thought", "")
        tool_calls = step.get("tool_calls", [])
        timestamp = step.get("timestamp", "")

        lines.extend([
            f"### Iteration {iteration}",
            "",
            f"*Timestamp: {timestamp}*",
            "",
        ])

        # Thought section
        if thought:
            lines.extend([
                "**Thought:**",
                "",
            ])
            thought_lines = thought.strip().split("\n")
            for tl in thought_lines[:50]:
                lines.append(f"> {tl}")
            if len(thought_lines) > 50:
                lines.append(f"> ... ({len(thought_lines) - 50} more lines)")
            lines.append("")

        # Tool calls section
        if tool_calls:
            lines.extend([
                "**Actions:**",
                "",
                "| Tool | Arguments | Duration |",
                "|------|-----------|----------|",
            ])

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                duration = tc.get("duration_ms", 0)
                args_str = json.dumps(args, ensure_ascii=False)
                if len(args_str) > 60:
                    args_str = args_str[:57] + "..."
                lines.append(f"| `{name}` | `{args_str}` | {duration}ms |")

            lines.append("")
            lines.append("**Observations:**")
            lines.append("")

            for tc in tool_calls:
                name = tc.get("name", "")
                result_text = tc.get("result", "")
                lines.append(f"*{name}:*")
                lines.append("")
                lines.append("```")
                result_lines = result_text.split("\n")
                if len(result_lines) > 30:
                    lines.extend(result_lines[:30])
                    lines.append(f"... ({len(result_lines) - 30} more lines)")
                else:
                    lines.append(result_text)
                lines.append("```")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Bug Reports
    if result.bugs_found:
        lines.extend([
            "## Bug Reports",
            "",
        ])

        for i, bug in enumerate(result.bugs_found, 1):
            location = bug.file
            if bug.line:
                location += f":{bug.line}"

            lines.extend([
                f"### Bug #{i}: {bug.bug_type}",
                "",
                f"**Location:** `{location}`",
                f"**Severity:** {bug.severity}",
                "",
                "**Description:**",
                "",
                bug.description,
                "",
                "**Root Cause:**",
                "",
                bug.root_cause,
                "",
                "**Trigger Condition:**",
                "",
                bug.trigger_condition,
                "",
                "**Impact:**",
                "",
                bug.impact,
                "",
                "---",
                "",
            ])

    # Files Analyzed
    if result.files_analyzed:
        lines.extend([
            "## Files Analyzed",
            "",
        ])
        for f in result.files_analyzed:
            lines.append(f"- `{f}`")
        lines.append("")

    # Write the file
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return md_path


# =============================================================================
# Analysis Runner
# =============================================================================


def create_progress_callback(verbose: bool = False) -> "Callable[[ReActStep], None]":
    """
    Create a callback function for displaying real-time progress.

    Args:
        verbose: If True, show detailed tool call info.

    Returns:
        Callback function that prints progress for each step.
    """
    from agent.baseline.react_agent import ReActStep

    def on_step(step: ReActStep) -> None:
        # Summary line
        tool_names = [tc.name for tc in step.tool_calls]
        tools_str = ", ".join(tool_names) if tool_names else "final response"
        print(f"  [{step.iteration:2d}] {tools_str}")

        if verbose and step.thought:
            # Show first line of thought
            first_line = step.thought.split("\n")[0][:80]
            if len(step.thought) > 80:
                first_line += "..."
            print(f"       > {first_line}")

    return on_step


async def run_analysis(
    repo_name: str,
    target_files: list[str] | None = None,
    model: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    trace_file: Path | None = None,
    on_step: "Callable[[ReActStep], None] | None" = None,
) -> "AnalysisResult":
    """
    Run baseline analysis on a repository.

    Args:
        repo_name: Name of the repository to analyze.
        target_files: Optional list of specific files to focus on.
            If None, uses pre-defined core files for the repository.
        model: LLM model to use (default: from settings).
        max_iterations: Maximum ReAct iterations.
        trace_file: Optional path to JSONL file for streaming trace output.
        on_step: Optional callback for real-time progress display.

    Returns:
        Analysis result with bugs found.

    Raises:
        ValueError: If settings are invalid.
    """
    # Import here to avoid circular imports and allow settings loading
    from agent.baseline.prompts import get_core_files
    from agent.baseline.react_agent import BaselineReActAgent
    from agent.config.settings import load_settings

    # If no target files specified, use pre-defined core files
    if target_files is None:
        target_files = get_core_files(repo_name)

    settings = load_settings()

    # Validate API key
    api_key = settings.openrouter_api_key
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not set. "
            "Please set it in your .env file or environment."
        )

    # Get model
    if not model:
        model = getattr(settings, "llm_model", None) or "anthropic/claude-sonnet-4"

    # Get repo path
    repo_path = get_repo_path(repo_name)

    # Create and run agent
    agent = BaselineReActAgent(
        model=model,
        api_key=api_key,
        base_url=settings.openrouter_base_url,
        repo_path=repo_path,
        max_iterations=max_iterations,
    )

    return await agent.analyze(
        repo_name,
        target_files,
        trace_file=trace_file,
        on_step=on_step,
    )


# =============================================================================
# CLI Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Baseline ReAct Agent for Consensus Protocol Bug Hunting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --repo raft                    # Uses pre-defined core files
  %(prog)s --repo sui -v                  # Verbose mode
  %(prog)s --repo raft --target raft.go   # Override with specific files
        """,
    )

    parser.add_argument(
        "--repo",
        required=True,
        choices=list(REPO_PATHS.keys()),
        help="Repository to analyze",
    )

    parser.add_argument(
        "--target",
        nargs="*",
        metavar="FILE",
        help="Specific files to focus on. If not specified, uses pre-defined core files for the repo.",
    )

    parser.add_argument(
        "--model",
        metavar="NAME",
        help="LLM model to use (default: from settings)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        metavar="N",
        help=f"Maximum ReAct iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=get_project_root() / DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help="Directory to save results",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code (0 for success with bugs, 1 for no bugs, 2 for error).
    """
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Show what core files will be used
    from agent.baseline.prompts import get_core_files
    from agent.baseline.react_agent import sanitize_model_name

    target_display = args.target if args.target else get_core_files(args.repo)

    # Determine model for trace file naming
    if args.model:
        model_name = args.model
    else:
        from agent.config.settings import load_settings
        settings = load_settings()
        model_name = getattr(settings, "llm_model", None) or "anthropic/claude-sonnet-4"

    # Generate trace file path
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = sanitize_model_name(model_name)
    trace_file = args.output_dir / f"baseline_{args.repo}_{model_safe}_{timestamp}.jsonl"

    print("\nBaseline ReAct Agent")
    print(f"  Repository:      {args.repo}")
    print(f"  Target files:    {target_display}")
    print(f"  Max iterations:  {args.max_iterations}")
    print(f"  Trace file:      {trace_file}")
    print("\nProgress:")

    try:
        # Create progress callback
        on_step = create_progress_callback(verbose=args.verbose)

        result = asyncio.run(
            run_analysis(
                repo_name=args.repo,
                target_files=args.target,
                model=args.model,
                max_iterations=args.max_iterations,
                trace_file=trace_file,
                on_step=on_step,
            )
        )

        print_result(result)

        # Save result (JSON) - note: execution_trace will be empty since we streamed
        output_path = save_result(result, args.output_dir)
        print(f"\nResult saved to: {output_path}")
        print(f"Trace file:      {trace_file}")

        # Generate markdown report from JSONL trace
        md_path = generate_markdown_report_from_jsonl(trace_file, result)
        print(f"Markdown report: {md_path}")

        # Return appropriate exit code
        if result.error:
            return EXIT_ERROR
        return EXIT_SUCCESS if result.bugs_found else EXIT_NO_BUGS

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        return EXIT_INTERRUPTED

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return EXIT_ERROR

    except Exception as e:
        logger.exception("Analysis failed: %s", e)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
