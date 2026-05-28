"""
Baseline ReAct Agent for Consensus Protocol Bug Hunting.

This module implements a simplified single-agent approach that directly
reads code to find bugs. It uses the ReAct (Reasoning + Acting) pattern
with minimal tools.

The agent follows a simple loop:
1. Thought: Analyze what's known and what to investigate
2. Action: Use a tool to gather information
3. Observation: Process the tool's output
4. Repeat until bugs are found or analysis is complete

This is intentionally simple as a baseline for comparison with
the full Strategy + TestGen multi-agent orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import httpx

from ..utils.token_usage import TokenUsage
from .prompts import BASELINE_SYSTEM_PROMPT, get_analysis_prompt
from .tools import create_baseline_tools

if TYPE_CHECKING:
    from ..core.tool_agent import Tool

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default configuration values
DEFAULT_MAX_ITERATIONS = 30
DEFAULT_MAX_TOKENS = 16000
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_TEMPERATURE = 0.2

# Bug report parsing
BUG_REPORT_PATTERN = re.compile(r"<bug_report>(.*?)</bug_report>", re.DOTALL)


def sanitize_model_name(model: str) -> str:
    """
    Convert model name to a safe filename format.

    Replaces special characters that are not allowed in filenames.

    Args:
        model: Model name (e.g., "anthropic/claude-sonnet-4").

    Returns:
        Safe filename string (e.g., "anthropic_claude-sonnet-4").
    """
    return model.replace("/", "_").replace(":", "_").replace(" ", "_")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ToolCallRecord:
    """
    Record of a single tool call during analysis.

    Attributes:
        name: Name of the tool invoked.
        arguments: Arguments passed to the tool.
        result: The tool's output/result.
        duration_ms: Time taken to execute the tool in milliseconds.
    """

    name: str
    arguments: dict[str, Any]
    result: str
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ReActStep:
    """
    Record of a single ReAct iteration.

    Each step captures the agent's thought process, the actions taken,
    and serves as a complete trace of the decision-making process.

    Attributes:
        iteration: The iteration number (1-indexed).
        thought: The LLM's reasoning/thought content.
        tool_calls: List of tool calls made in this iteration.
        timestamp: ISO format timestamp when this step started.
        token_usage: Token consumption for this iteration's LLM call.
    """

    iteration: int
    thought: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    timestamp: str = ""
    token_usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "thought": self.thought,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "timestamp": self.timestamp,
            "token_usage": self.token_usage,
        }


@dataclass
class BugReport:
    """
    A potential bug found by the agent.

    Attributes:
        file: Path to the file containing the bug.
        line: Line number where the bug occurs (if known).
        bug_type: Category of bug (safety, liveness, race, agreement).
        severity: Bug severity (critical, high, medium, low).
        description: Detailed description of the bug.
        root_cause: Explanation of why the bug exists.
        trigger_condition: How to trigger the bug.
        impact: What happens when the bug is triggered.
        raw_text: Original unparsed bug report text.
    """

    file: str
    line: int | None
    bug_type: str
    severity: str
    description: str
    root_cause: str
    trigger_condition: str
    impact: str
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file": self.file,
            "line": self.line,
            "type": self.bug_type,
            "severity": self.severity,
            "description": self.description,
            "root_cause": self.root_cause,
            "trigger_condition": self.trigger_condition,
            "impact": self.impact,
        }


@dataclass
class AnalysisResult:
    """
    Result of the baseline agent's analysis.

    Attributes:
        repo_name: Name of the analyzed repository.
        model: LLM model used for analysis.
        bugs_found: List of bugs discovered during analysis.
        files_analyzed: List of files that were read.
        iterations: Number of ReAct iterations performed.
        tool_calls: Total number of tool invocations.
        duration_ms: Total analysis time in milliseconds.
        tokens_used: Total token count (for backward compatibility).
        token_usage: Detailed token usage breakdown (prompt, completion, cached, cost).
        final_response: The agent's final response text.
        error: Error message if analysis failed.
        execution_trace: Complete trace of all ReAct steps for debugging/analysis.
    """

    repo_name: str
    model: str = ""
    bugs_found: list[BugReport] = field(default_factory=list)
    files_analyzed: list[str] = field(default_factory=list)
    iterations: int = 0
    tool_calls: int = 0
    duration_ms: int = 0
    tokens_used: int = 0
    token_usage: dict[str, Any] = field(default_factory=dict)
    final_response: str = ""
    error: str | None = None
    execution_trace: list[ReActStep] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if analysis completed without errors."""
        return self.error is None

    @property
    def has_bugs(self) -> bool:
        """Check if any bugs were found."""
        return len(self.bugs_found) > 0

    @property
    def model_safe_name(self) -> str:
        """Get model name safe for use in filenames."""
        return sanitize_model_name(self.model) if self.model else "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "repo_name": self.repo_name,
            "model": self.model,
            "bugs_found": [bug.to_dict() for bug in self.bugs_found],
            "files_analyzed": self.files_analyzed,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "token_usage": self.token_usage,
            "error": self.error,
            "execution_trace": [step.to_dict() for step in self.execution_trace],
        }


# =============================================================================
# Baseline ReAct Agent
# =============================================================================


class BaselineReActAgent:
    """
    Baseline ReAct Agent for consensus protocol bug hunting.

    This agent uses a simple ReAct (Reasoning + Acting) loop to analyze
    source code and find potential bugs. It is intentionally minimal,
    using only basic tools without sophisticated memory or strategy systems.

    The agent:
    1. Reads and analyzes source code files
    2. Searches for suspicious patterns
    3. Reports potential bugs with detailed descriptions

    This serves as a baseline for comparing with more sophisticated
    multi-agent architectures that use strategy generation and
    pattern memory.

    Example:
        ```python
        from agent.config.settings import load_settings

        settings = load_settings()
        agent = BaselineReActAgent(
            model=settings.llm_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            repo_path="/path/to/raft",
        )

        result = await agent.analyze("raft", ["raft.go"])
        print(f"Found {len(result.bugs_found)} potential bugs")
        ```

    Attributes:
        model: LLM model identifier.
        repo_path: Path to the repository being analyzed.
        max_iterations: Maximum number of ReAct iterations.
        tools: List of available tools.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        repo_path: Path | str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Initialize the Baseline ReAct Agent.

        Args:
            model: LLM model name (e.g., "anthropic/claude-sonnet-4").
            api_key: API key for the LLM provider.
            base_url: API base URL. Should be loaded from .env via load_settings().
            repo_path: Path to the repository to analyze.
            max_iterations: Maximum ReAct loop iterations (default: 30).
            max_tokens: Maximum output tokens per LLM call (default: 16000).
            timeout: Request timeout in seconds (default: 120).

        Raises:
            ValueError: If repo_path does not exist.
        """
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.repo_path = Path(repo_path).resolve()
        self.max_iterations = max_iterations
        self._max_tokens = max_tokens
        self._timeout = timeout

        # Validate repo path
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        # Create tools
        self.tools: list[Tool] = create_baseline_tools(self.repo_path)
        self._tools_by_name: dict[str, Tool] = {t.name: t for t in self.tools}

        # Track files read for reporting
        self._files_read: set[str] = set()

        logger.info(
            "[BaselineReActAgent] Initialized | repo=%s | model=%s | tools=%s",
            self.repo_path,
            model,
            list(self._tools_by_name.keys()),
        )

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """
        Get tools in OpenAI function calling format.

        Returns:
            List of tool definitions in OpenAI-compatible format.
        """
        return [t.to_openai_format() for t in self.tools]

    async def analyze(
        self,
        repo_name: str,
        target_files: list[str] | None = None,
        *,
        trace_file: Path | str | None = None,
        max_result_length: int = 8000,
        on_step: "Callable[[ReActStep], None] | None" = None,
    ) -> AnalysisResult:
        """
        Run bug hunting analysis on the repository.

        This is the main entry point for analysis. The agent will:
        1. Read relevant source files
        2. Search for suspicious patterns
        3. Analyze potential vulnerabilities
        4. Report any bugs found

        Args:
            repo_name: Name of the repository for prompt context.
                Should be one of: "raft", "sui", "hotstuff", "efficient-epaxos".
            target_files: Optional list of specific files to focus on.
                If None, the agent will explore based on the prompt.
            trace_file: Optional path to JSONL file for streaming trace output.
                Each ReAct step is written immediately as a JSON line.
                This reduces memory usage and preserves progress on crashes.
            max_result_length: Maximum length for tool results in trace (default: 8000).
                Longer results are truncated to save memory. Set to 0 for no limit.
            on_step: Optional callback invoked after each iteration with the ReActStep.
                Useful for real-time console progress display.

        Returns:
            AnalysisResult containing bugs found and analysis statistics.

        Example:
            ```python
            result = await agent.analyze("raft", ["raft.go", "log.go"])
            for bug in result.bugs_found:
                print(f"{bug.severity}: {bug.description}")
            ```
        """
        start_time = time.time()
        result = AnalysisResult(repo_name=repo_name, model=self.model)
        self._files_read.clear()

        # Token usage accumulator
        total_token_usage = TokenUsage()

        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
            {"role": "user", "content": get_analysis_prompt(repo_name, target_files)},
        ]

        # Setup streaming trace file if provided
        trace_path = Path(trace_file) if trace_file else None
        if trace_path:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            # Write header line with metadata
            with open(trace_path, "w", encoding="utf-8") as f:
                header = {
                    "type": "header",
                    "repo_name": repo_name,
                    "model": self.model,
                    "target_files": target_files,
                    "max_iterations": self.max_iterations,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(header, ensure_ascii=False) + "\n")

        logger.info(
            "[BaselineReActAgent] Starting analysis | repo=%s | targets=%s | trace=%s",
            repo_name,
            target_files or "all",
            trace_path or "memory",
        )

        # ReAct loop
        for iteration in range(self.max_iterations):
            result.iterations = iteration + 1

            # Create trace step for this iteration
            step = ReActStep(
                iteration=iteration + 1,
                thought="",
                tool_calls=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            try:
                response = await self._call_llm(messages)
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])
                usage = response.get("usage", {})

                # Accumulate token usage
                total_token_usage.add(usage)
                step.token_usage = usage

                logger.debug(
                    "[BaselineReActAgent] Iteration %d | tokens: prompt=%d completion=%d total=%d",
                    iteration + 1,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                )

                # Record the LLM's thought/reasoning
                step.thought = content

                # No tool calls = analysis complete
                if not tool_calls:
                    result.final_response = content
                    result.bugs_found = self._parse_bug_reports(content)
                    # Write/store final step
                    self._record_step(
                        step, result, trace_path, max_result_length, on_step
                    )
                    logger.info(
                        "[BaselineReActAgent] Analysis complete at iteration %d",
                        iteration + 1,
                    )
                    break

                # Add assistant message with tool calls
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content or "",
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                # Execute tools and record each call
                for tool_call in tool_calls:
                    tool_start = time.time()
                    tool_result = await self._process_tool_call(tool_call)
                    tool_duration_ms = int((time.time() - tool_start) * 1000)
                    result.tool_calls += 1

                    # Extract tool call details for trace
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    try:
                        tool_args = json.loads(function.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Record tool call in trace (truncate result for memory)
                    trace_result = tool_result
                    if max_result_length > 0 and len(tool_result) > max_result_length:
                        trace_result = (
                            tool_result[:max_result_length]
                            + f"\n... [truncated {len(tool_result) - max_result_length} chars]"
                        )

                    step.tool_calls.append(ToolCallRecord(
                        name=tool_name,
                        arguments=tool_args,
                        result=trace_result,
                        duration_ms=tool_duration_ms,
                    ))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": tool_result,  # Full result for LLM context
                    })

                # Write/store completed step
                self._record_step(step, result, trace_path, max_result_length, on_step)

            except httpx.HTTPStatusError as e:
                logger.error(
                    "[BaselineReActAgent] HTTP error: %s %s",
                    e.response.status_code,
                    e.response.text[:200],
                )
                result.error = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
                step.thought = f"[ERROR] {result.error}"
                self._record_step(step, result, trace_path, max_result_length, on_step)
                break

            except httpx.TimeoutException:
                logger.error("[BaselineReActAgent] Request timeout")
                result.error = "Request timeout"
                step.thought = "[ERROR] Request timeout"
                self._record_step(step, result, trace_path, max_result_length, on_step)
                break

            except Exception as e:
                logger.exception(
                    "[BaselineReActAgent] Error in iteration %d",
                    iteration + 1,
                )
                result.error = str(e)
                step.thought = f"[ERROR] {result.error}"
                self._record_step(step, result, trace_path, max_result_length, on_step)
                break

        # Finalize result
        result.files_analyzed = sorted(self._files_read)
        result.duration_ms = int((time.time() - start_time) * 1000)
        result.tokens_used = total_token_usage.total_tokens
        result.token_usage = total_token_usage.to_dict()

        # Write footer to trace file
        if trace_path:
            with open(trace_path, "a", encoding="utf-8") as f:
                footer = {
                    "type": "footer",
                    "iterations": result.iterations,
                    "tool_calls": result.tool_calls,
                    "bugs_found": len(result.bugs_found),
                    "files_analyzed": result.files_analyzed,
                    "duration_ms": result.duration_ms,
                    "token_usage": result.token_usage,
                    "error": result.error,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(footer, ensure_ascii=False) + "\n")

        logger.info(
            "[BaselineReActAgent] Result | bugs=%d | files=%d | iterations=%d | "
            "tool_calls=%d | tokens=%d | cost=$%.6f | duration=%dms",
            len(result.bugs_found),
            len(result.files_analyzed),
            result.iterations,
            result.tool_calls,
            result.tokens_used,
            total_token_usage.cost,
            result.duration_ms,
        )

        return result

    def _record_step(
        self,
        step: ReActStep,
        result: AnalysisResult,
        trace_path: Path | None,
        max_result_length: int,
        on_step: Callable[[ReActStep], None] | None,
    ) -> None:
        """
        Record a ReAct step - either to JSONL file or memory.

        Args:
            step: The ReActStep to record.
            result: The AnalysisResult to update.
            trace_path: Path to JSONL file (if streaming).
            max_result_length: Max length for tool results (unused here, truncation done earlier).
            on_step: Optional callback to invoke.
        """
        if trace_path:
            # Stream to JSONL file - don't accumulate in memory
            with open(trace_path, "a", encoding="utf-8") as f:
                step_data = {"type": "step", **step.to_dict()}
                f.write(json.dumps(step_data, ensure_ascii=False) + "\n")
        else:
            # No streaming - keep in memory for later
            result.execution_trace.append(step)

        # Call progress callback if provided
        if on_step:
            try:
                on_step(step)
            except Exception as e:
                logger.warning("[BaselineReActAgent] on_step callback error: %s", e)

    async def _call_llm(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Call the LLM API.

        Args:
            messages: Conversation history in OpenAI format.

        Returns:
            Dict with 'content', 'tool_calls', and 'usage' keys.
            The 'usage' dict contains token consumption info from OpenRouter.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            RuntimeError: If the response is malformed.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        request_body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": DEFAULT_TEMPERATURE,
            "tools": self.get_tools_schema(),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM response missing 'choices'")

        message = choices[0].get("message", {})
        usage = data.get("usage", {})

        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "usage": usage,
        }

    async def _process_tool_call(self, tool_call: dict[str, Any]) -> str:
        """
        Process a single tool call from the LLM.

        Args:
            tool_call: Tool call object from LLM response.

        Returns:
            Tool execution result as a string.
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")

        try:
            args = json.loads(function.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        logger.debug("[BaselineReActAgent] Tool call: %s(%s)", tool_name, args)

        # Track files read
        if tool_name == "read_file" and "path" in args:
            self._files_read.add(args["path"])

        return await self._execute_tool(tool_name, args)

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool to execute.
            args: Arguments to pass to the tool.

        Returns:
            Tool result as a string, or error message.
        """
        tool = self._tools_by_name.get(tool_name)

        if not tool:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.func(**args)
            else:
                result = tool.func(**args)

            return result if isinstance(result, str) else json.dumps(result)

        except TypeError as e:
            logger.warning("[BaselineReActAgent] Tool %s arg error: %s", tool_name, e)
            return f"Error: Invalid arguments for {tool_name}: {e}"
        except Exception as e:
            logger.warning("[BaselineReActAgent] Tool %s error: %s", tool_name, e)
            return f"Error executing {tool_name}: {e}"

    def _parse_bug_reports(self, response: str) -> list[BugReport]:
        """
        Parse bug reports from the agent's final response.

        Args:
            response: The agent's response text.

        Returns:
            List of parsed BugReport objects.
        """
        bugs = []

        for match in BUG_REPORT_PATTERN.finditer(response):
            try:
                bug = self._parse_single_bug(match.group(1))
                if bug:
                    bugs.append(bug)
            except Exception as e:
                logger.warning(
                    "[BaselineReActAgent] Failed to parse bug report: %s", e
                )

        return bugs

    def _parse_single_bug(self, text: str) -> BugReport | None:
        """
        Parse a single bug report from text.

        Args:
            text: Content inside <bug_report> tags.

        Returns:
            Parsed BugReport or None if parsing fails.
        """

        def extract_field(field_name: str) -> str:
            # Match "Field Name:" followed by content until next field or end
            pattern = rf"{field_name}:\s*(.+?)(?=\n[A-Z][a-z]+ ?[A-Z]?[a-z]*:|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else ""

        file_info = extract_field("File")
        file_path = file_info
        line_num = None

        # Parse file:line format
        if ":" in file_info:
            parts = file_info.split(":", 1)
            file_path = parts[0].strip()
            try:
                line_num = int(parts[1].strip())
            except ValueError:
                pass

        return BugReport(
            file=file_path,
            line=line_num,
            bug_type=extract_field("Type").lower(),
            severity=extract_field("Severity").lower(),
            description=extract_field("Description"),
            root_cause=extract_field("Root Cause"),
            trigger_condition=extract_field("Trigger Condition"),
            impact=extract_field("Impact"),
            raw_text=text,
        )
