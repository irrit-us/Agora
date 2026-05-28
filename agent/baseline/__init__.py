"""
Baseline ReAct Agent for Consensus Protocol Bug Hunting.

This module provides a simplified single-agent approach for finding bugs
in consensus protocol implementations. It uses the ReAct (Reasoning + Acting)
pattern with minimal tools, serving as a baseline for comparison with
more sophisticated multi-agent architectures.

Example Usage:
    ```python
    from agent.baseline import BaselineReActAgent
    from agent.config.settings import load_settings

    # Load LLM configuration from .env file
    settings = load_settings()

    agent = BaselineReActAgent(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        repo_path="/path/to/consensus/repo",
    )

    result = await agent.analyze(
        repo_name="raft",
        target_files=["raft.go", "log.go"],
    )

    for bug in result.bugs_found:
        print(f"Found bug in {bug.file}: {bug.description}")
    ```

Command-line Usage:
    ```bash
    python -m agent.baseline.runner --repo raft --target raft.go
    python -m agent.baseline.runner --repo sui --verbose
    ```
"""

__version__ = "0.1.0"
__author__ = "Consensus Bug Hunter Authors"

from .prompts import REPO_CORE_FILES, get_core_files
from .react_agent import (
    AnalysisResult,
    BaselineReActAgent,
    BugReport,
    ReActStep,
    ToolCallRecord,
)
from .tools import create_baseline_tools


# Lazy imports for runner functions to avoid RuntimeWarning when running
# `python -m agent.baseline.runner`. The warning occurs because __init__.py
# imports runner before runpy can execute it as __main__.
def __getattr__(name: str):
    """Lazy import runner functions to avoid circular import issues."""
    if name in ("generate_markdown_report_from_jsonl", "load_trace_from_jsonl"):
        from . import runner
        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Main classes
    "BaselineReActAgent",
    # Data classes
    "AnalysisResult",
    "BugReport",
    "ReActStep",
    "ToolCallRecord",
    # Tool factory
    "create_baseline_tools",
    # Report generation
    "generate_markdown_report_from_jsonl",
    "load_trace_from_jsonl",
    # Core files mapping
    "REPO_CORE_FILES",
    "get_core_files",
    # Metadata
    "__version__",
    "__author__",
]
