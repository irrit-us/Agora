"""
ToolAgent - Self-built Tool Calling Agent.

A simpler, more controllable agent implementation as an alternative to LangGraph/DeepAgents.
Supports multi-turn tool calling with independent context window management.
"""

import asyncio
import inspect
import json
import logging
import re
import time
import traceback
import types
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, get_args, get_origin

import httpcore
import httpx

from ..memory.llm_logs import get_action_logger
from ..utils.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Constants
MAX_EMPTY_RESPONSES = 3  # Max retries for empty LLM responses
MAX_TOOL_RESULT_LENGTH = 8000  # Maximum characters per tool result
MAX_CONTEXT_CHARS = 400000  # Approximate max context size (chars, ~100k tokens)
RATE_LIMIT_RETRY_DELAYS = [5, 15, 30, 60]  # Exponential backoff for rate limits (seconds)

# Repetition detection thresholds (identical call signature)
STUCK_LOOP_WARN_THRESHOLD = 3  # Inject correction message after this many identical calls
STUCK_LOOP_ABORT_THRESHOLD = 5  # Force-terminate after this many identical calls

# Identical-call detection (catches loops where the exact same call repeats)
IDENTICAL_CALL_WARN_THRESHOLD = 10  # Inject correction after N identical call rounds
IDENTICAL_CALL_ABORT_THRESHOLD = 20  # Force-terminate after N identical call rounds


def _truncate_tool_result(result: str, max_length: int = MAX_TOOL_RESULT_LENGTH) -> str:
    """Truncate tool result if too long, keeping beginning and end."""
    if len(result) <= max_length:
        return result
    # Keep first 60% and last 30%, with truncation notice in middle
    head_len = int(max_length * 0.6)
    tail_len = int(max_length * 0.3)
    return (
        result[:head_len]
        + f"\n\n... [TRUNCATED {len(result) - head_len - tail_len} chars] ...\n\n"
        + result[-tail_len:]
    )


def _count_consecutive_identical(items: list[str]) -> int:
    """Count how many times the last element repeats consecutively from the end."""
    if not items:
        return 0
    last = items[-1]
    count = 0
    for item in reversed(items):
        if item == last:
            count += 1
        else:
            break
    return count


def _format_call_summary(tool_calls: list[dict], max_len: int = 200) -> str:
    """Build a human-readable summary of tool calls for loop-detection logs."""
    parts = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "?")
        try:
            args = json.loads(fn.get("arguments", "{}"))
            if "command" in args:
                parts.append(f'{name}("{args["command"]}")')
            elif "path" in args:
                parts.append(f'{name}("{args["path"]}")')
            else:
                parts.append(f"{name}({fn.get('arguments', '{}')})")
        except (json.JSONDecodeError, TypeError):
            parts.append(f"{name}({fn.get('arguments', '{}')})")
    summary = " | ".join(parts)
    if len(summary) > max_len:
        summary = summary[:max_len] + "..."
    return summary


# ============================================================
# Type to JSON Schema Mapping
# ============================================================

# Mapping from Python types to JSON Schema types
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _python_type_to_json_schema(py_type: type) -> dict[str, Any]:
    """
    Convert a Python type annotation to JSON Schema.

    Supports:
    - Basic types: str, int, float, bool
    - Optional types: X | None, Optional[X]
    - List types: list[X]
    - Dict types: dict[str, X]

    Args:
        py_type: Python type annotation

    Returns:
        JSON Schema dict
    """
    # Handle None type
    if py_type is type(None):
        return {"type": "null"}

    # Handle basic types
    if py_type in _TYPE_MAP:
        return {"type": _TYPE_MAP[py_type]}

    # Handle generic types (list[X], dict[K, V], X | None, etc.)
    origin = get_origin(py_type)
    args = get_args(py_type)

    # Handle Union types (X | None or Optional[X])
    if origin is type(None):
        return {"type": "null"}

    # Check for Union (including X | None in Python 3.10+)
    # In Python 3.10+, X | None has origin types.UnionType
    if origin is types.UnionType or str(origin) == "typing.Union":
        # Filter out NoneType to get the actual type
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            # Optional type - just use the inner type
            return _python_type_to_json_schema(non_none_args[0])
        else:
            # Union of multiple types - use anyOf
            return {"anyOf": [_python_type_to_json_schema(a) for a in args]}

    # Handle list[X]
    if origin is list:
        if args:
            return {"type": "array", "items": _python_type_to_json_schema(args[0])}
        return {"type": "array"}

    # Handle dict[K, V]
    if origin is dict:
        schema: dict[str, Any] = {"type": "object"}
        if len(args) >= 2:
            schema["additionalProperties"] = _python_type_to_json_schema(args[1])
        return schema

    # Default to string for unknown types
    return {"type": "string"}


def _parse_docstring_params(docstring: str | None) -> dict[str, str]:
    """
    Parse parameter descriptions from a docstring.

    Supports Google-style and reStructuredText-style docstrings:
    - Args:
        param_name: Description
    - :param param_name: Description

    Args:
        docstring: The function's docstring

    Returns:
        Dict mapping parameter names to their descriptions
    """
    if not docstring:
        return {}

    params: dict[str, str] = {}

    # Pattern for Google-style: "param_name: Description" or "param_name (type): Description"
    google_pattern = re.compile(r"^\s*(\w+)(?:\s*\([^)]*\))?\s*:\s*(.+?)(?=\n\s*\w+\s*(?:\([^)]*\))?\s*:|$)", re.MULTILINE | re.DOTALL)

    # Pattern for reStructuredText-style: ":param param_name: Description"
    rst_pattern = re.compile(r":param\s+(\w+):\s*(.+?)(?=\n\s*:|$)", re.MULTILINE | re.DOTALL)

    # Try Google-style first (look for "Args:" section)
    args_match = re.search(r"Args?:\s*\n(.*?)(?=\n\s*(?:Returns?|Raises?|Examples?|Note):|$)", docstring, re.IGNORECASE | re.DOTALL)
    if args_match:
        args_section = args_match.group(1)
        for match in google_pattern.finditer(args_section):
            param_name = match.group(1).strip()
            param_desc = match.group(2).strip()
            # Clean up multiline descriptions
            param_desc = re.sub(r"\s+", " ", param_desc)
            params[param_name] = param_desc

    # Try reStructuredText-style
    for match in rst_pattern.finditer(docstring):
        param_name = match.group(1).strip()
        param_desc = match.group(2).strip()
        param_desc = re.sub(r"\s+", " ", param_desc)
        if param_name not in params:  # Don't override Google-style
            params[param_name] = param_desc

    return params


def _generate_json_schema(func: Callable) -> dict[str, Any]:
    """
    Generate JSON Schema for a function's parameters.

    Args:
        func: The function to generate schema for

    Returns:
        JSON Schema dict with 'type', 'properties', and 'required' fields
    """
    sig = inspect.signature(func)
    docstring = func.__doc__
    param_docs = _parse_docstring_params(docstring)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Skip self, cls, *args, **kwargs
        if param_name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        # Get type annotation
        if param.annotation != inspect.Parameter.empty:
            prop_schema = _python_type_to_json_schema(param.annotation)
        else:
            prop_schema = {"type": "string"}  # Default to string

        # Add description from docstring
        if param_name in param_docs:
            prop_schema["description"] = param_docs[param_name]

        properties[param_name] = prop_schema

        # Check if required (no default value and not Optional)
        if param.default == inspect.Parameter.empty:
            # Check if it's an Optional type
            origin = get_origin(param.annotation)
            args = get_args(param.annotation)
            is_optional = type(None) in args if args else False
            if not is_optional:
                required.append(param_name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    return schema


# ============================================================
# Tool Definition
# ============================================================


@dataclass
class Tool:
    """Tool definition for the agent."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    func: Callable  # Async function to execute

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }




# ============================================================
# Agent Response
# ============================================================


@dataclass
class AgentResponse:
    """Response from the agent."""

    content: str
    reasoning: str | None = None
    tool_calls_made: int = 0
    api_calls_made: int = 0
    iterations: int = 0
    duration_ms: int = 0
    error: str | None = None
    token_usage: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Tool Agent
# ============================================================


class ToolAgent:
    """
    Self-built Tool Calling Agent.

    Features:
    - Supports OpenRouter and DeepSeek API
    - Automatic tool calling loop handling
    - Independent context window
    - Detailed logging

    Usage:
        agent = ToolAgent(
            model="openai/gpt-4o",
            api_key="...",
            system_prompt="You are a helpful assistant.",
            tools=[read_file_tool, write_file_tool],
        )

        response = await agent.run("Help me analyze this code...")
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        system_prompt: str = "",
        tools: list[Tool] | None = None,
        max_tokens: int = 16000,
        timeout: float = 120.0,
        log_callback: Callable[[dict], None] | None = None,
        metrics_callback: Callable[[dict], None] | None = None,
    ):
        """
        Initialize the ToolAgent.

        Args:
            model: Model name (e.g., "openai/gpt-4o", "deepseek/deepseek-reasoner")
            api_key: API key
            base_url: API base URL
            system_prompt: System prompt for the agent
            tools: List of Tool objects
            max_tokens: Maximum output tokens
            timeout: Request timeout in seconds
            log_callback: Optional callback for logging LLM interactions
            metrics_callback: Optional callback invoked after each LLM API call
                with a dict containing usage, duration_ms, success, error, generation_id.
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.system_prompt = system_prompt
        self.tools = {t.name: t for t in (tools or [])}
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.log_callback = log_callback
        self.metrics_callback = metrics_callback

        # Detect if this is a DeepSeek Reasoner model
        self.is_reasoner = "reasoner" in model.lower()

        # Reusable HTTP client with connection pooling
        self._http_client: httpx.AsyncClient | None = None

        logger.info(
            f"[ToolAgent] Initialized with model={model}, tools={list(self.tools.keys())}"
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create a reusable HTTP client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            # Configure connection pool limits
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            )
            # Configure transport with retries for connection issues
            transport = httpx.AsyncHTTPTransport(
                retries=2,  # Retry connection-level failures
            )
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=30.0),
                limits=limits,
                transport=transport,
            )
        return self._http_client

    async def close(self):
        """Close the HTTP client. Call this when done with the agent."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def add_tool(self, tool: Tool):
        """Add a tool to the agent."""
        self.tools[tool.name] = tool

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """Get tools in OpenAI format."""
        return [t.to_openai_format() for t in self.tools.values()]

    async def run(
        self,
        prompt: str,
        *,
        max_iterations: int = 20,
        additional_context: str | None = None,
    ) -> AgentResponse:
        """
        Run the agent with the given prompt.

        Args:
            prompt: User prompt
            max_iterations: Maximum tool calling iterations
            additional_context: Optional additional context to prepend to prompt

        Returns:
            AgentResponse with the final result
        """
        start_time = time.time()

        # Build initial messages
        messages: list[dict[str, Any]] = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        user_content = prompt
        if additional_context:
            user_content = f"{additional_context}\n\n{prompt}"
        messages.append({"role": "user", "content": user_content})

        tool_calls_made = 0
        api_calls_made = 0
        iteration = 0
        last_reasoning = None
        empty_response_count = 0  # Track consecutive empty responses
        max_empty_responses = MAX_EMPTY_RESPONSES

        # Repetition detection: list of recent tool call signatures
        recent_call_signatures: list[str] = []

        # Identical-call detection
        last_call_signature: str | None = None
        consecutive_identical_calls: int = 0

        # Token usage accumulator
        total_token_usage = TokenUsage()

        action_logger = get_action_logger()

        for iteration in range(max_iterations):
            logger.debug(f"[ToolAgent] Iteration {iteration + 1}/{max_iterations}")

            try:
                # Call LLM
                response = await self._call_llm(messages)
                api_calls_made += 1

                content = response.get("content", "")
                reasoning = response.get("reasoning")
                tool_calls = response.get("tool_calls", [])
                usage = response.get("usage", {})

                # Accumulate token usage
                total_token_usage.add(usage)

                # Log reasoning/thinking (full content, no truncation)
                if reasoning:
                    last_reasoning = reasoning
                    action_logger.thinking("[LLM REASONING]", reasoning)
                elif content and not tool_calls:
                    # Log final response (full content)
                    action_logger.thinking("[LLM RESPONSE]", content)

                # If no tool calls, check if response is valid
                if not tool_calls:
                    # Check for empty/abnormal response - likely LLM interruption
                    # Also retry on first iteration empty response (model may have failed to start)
                    if not content.strip():
                        empty_response_count += 1
                        logger.warning(
                            f"[ToolAgent] Empty response without tool calls (attempt {empty_response_count}/{max_empty_responses}) - possible LLM interruption"
                        )
                        action_logger.error(
                            f"[WARNING] LLM returned empty response, retrying ({empty_response_count}/{max_empty_responses})"
                        )

                        if empty_response_count < max_empty_responses:
                            # Add exponential backoff delay before retry
                            backoff_delay = 2 ** empty_response_count  # 2s, 4s, 8s...
                            logger.info(f"[ToolAgent] Waiting {backoff_delay}s before retry...")
                            await asyncio.sleep(backoff_delay)
                            
                            # Add a nudge message to encourage continuation
                            messages.append(
                                {
                                    "role": "user",
                                    "content": "Your response was empty. Please continue with your analysis and complete the task. If you need to use tools, please do so. If you have a final answer, please provide it.",
                                }
                            )
                            continue  # Retry
                        else:
                            # Give up after max retries
                            logger.error(
                                f"[ToolAgent] Max empty response retries ({max_empty_responses}) reached"
                            )
                            duration_ms = int((time.time() - start_time) * 1000)
                            return AgentResponse(
                                content="",
                                reasoning=last_reasoning,
                                tool_calls_made=tool_calls_made,
                                api_calls_made=api_calls_made,
                                iterations=iteration + 1,
                                duration_ms=duration_ms,
                                error="empty_response_after_retries",
                                token_usage=total_token_usage.to_dict(),
                            )

                    # Valid completion - reset counter and return
                    duration_ms = int((time.time() - start_time) * 1000)
                    return AgentResponse(
                        content=content,
                        reasoning=last_reasoning,
                        tool_calls_made=tool_calls_made,
                        api_calls_made=api_calls_made,
                        iterations=iteration + 1,
                        duration_ms=duration_ms,
                        token_usage=total_token_usage.to_dict(),
                    )

                # Reset empty response counter on successful tool call
                empty_response_count = 0

                # Add assistant message with tool calls
                assistant_msg = {"role": "assistant", "content": content or ""}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                if reasoning and self.is_reasoner:
                    # For DeepSeek Reasoner, include reasoning in tool call continuation
                    assistant_msg["reasoning_content"] = reasoning
                messages.append(assistant_msg)

                # Execute tools
                for tool_call in tool_calls:
                    tool_id = tool_call.get("id", "")
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")

                    try:
                        args = json.loads(function.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    # Log tool call
                    action_logger.tool_call(tool_name, args)
                    logger.info(f"[ToolAgent] Executing tool: {tool_name}")

                    # Execute tool
                    result = await self._execute_tool(tool_name, args)
                    tool_calls_made += 1

                    # Log tool result (only errors)
                    if result.startswith("Error"):
                        action_logger.tool_result(tool_name, False, result)

                    # Truncate large tool results to prevent context overflow
                    truncated_result = _truncate_tool_result(str(result))
                    if len(truncated_result) < len(result):
                        reduction_pct = 100 - (len(truncated_result) * 100 // len(result))
                        logger.debug(
                            f"[ToolAgent] Truncated tool result from {len(result)} to {len(truncated_result)} chars"
                        )
                        action_logger.info(
                            f"[TRUNCATE] iter={iteration + 1} | {tool_name}: {len(result)} -> {len(truncated_result)} chars (-{reduction_pct}%)"
                        )

                    # Add tool result
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": truncated_result,
                        }
                    )

                # --- Repetition detection ---
                # Build a signature for ALL tool calls in this iteration
                iter_signatures = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    sig = f"{fn.get('name', '')}:{fn.get('arguments', '')}"
                    iter_signatures.append(sig)
                combined_sig = "|".join(iter_signatures)
                recent_call_signatures.append(combined_sig)

                consecutive = _count_consecutive_identical(recent_call_signatures)

                if consecutive >= STUCK_LOOP_ABORT_THRESHOLD:
                    logger.error(
                        f"[ToolAgent] Stuck in loop: {consecutive} identical tool call rounds detected, aborting"
                    )
                    action_logger.error(
                        f"[STUCK LOOP] Aborting after {consecutive} identical rounds"
                    )
                    duration_ms = int((time.time() - start_time) * 1000)
                    return AgentResponse(
                        content="",
                        reasoning=last_reasoning,
                        tool_calls_made=tool_calls_made,
                        api_calls_made=api_calls_made,
                        iterations=iteration + 1,
                        duration_ms=duration_ms,
                        error="stuck_in_loop",
                        token_usage=total_token_usage.to_dict(),
                    )
                elif consecutive >= STUCK_LOOP_WARN_THRESHOLD:
                    logger.warning(
                        f"[ToolAgent] Possible stuck loop: {consecutive} identical tool call rounds"
                    )
                    action_logger.warning(
                        f"[STUCK LOOP WARNING] {consecutive} identical rounds, injecting correction"
                    )
                    messages = self._compress_repeated_messages(messages)
                    correction = self._build_loop_correction(tool_calls)
                    messages.append({"role": "user", "content": correction})

                # --- Identical-call detection ---
                # Higher-threshold complement to stuck-loop detection above.
                # Both compare the full combined_sig (tool names + args).
                # Stuck-loop fires early (warn=3, abort=5) with message compression;
                # this fires later (warn=10, abort=20) as a backstop.
                if combined_sig == last_call_signature:
                    consecutive_identical_calls += 1
                else:
                    last_call_signature = combined_sig
                    consecutive_identical_calls = 1

                if consecutive_identical_calls >= IDENTICAL_CALL_ABORT_THRESHOLD:
                    call_summary = _format_call_summary(tool_calls)
                    logger.error(
                        f"[ToolAgent] Identical-call loop: {consecutive_identical_calls} "
                        f"identical rounds, aborting. Call: {call_summary}"
                    )
                    action_logger.error(
                        f"[IDENTICAL CALL LOOP] Aborting after {consecutive_identical_calls}/{IDENTICAL_CALL_ABORT_THRESHOLD} "
                        f"identical rounds: {call_summary}"
                    )
                    duration_ms = int((time.time() - start_time) * 1000)
                    return AgentResponse(
                        content="",
                        reasoning=last_reasoning,
                        tool_calls_made=tool_calls_made,
                        api_calls_made=api_calls_made,
                        iterations=iteration + 1,
                        duration_ms=duration_ms,
                        error=f"stuck_in_identical_call_loop:{call_summary}",
                        token_usage=total_token_usage.to_dict(),
                    )
                elif consecutive_identical_calls >= IDENTICAL_CALL_WARN_THRESHOLD:
                    call_summary = _format_call_summary(tool_calls)
                    logger.warning(
                        f"[ToolAgent] Possible identical-call loop: {consecutive_identical_calls} "
                        f"identical rounds. Call: {call_summary}"
                    )
                    action_logger.warning(
                        f"[IDENTICAL CALL LOOP WARNING] {consecutive_identical_calls}/{IDENTICAL_CALL_ABORT_THRESHOLD} "
                        f"identical rounds: {call_summary}"
                    )
                    messages.append({
                        "role": "user",
                        "content": (
                            f"STOP: You have executed the exact same call {consecutive_identical_calls} "
                            f"times in a row: {call_summary}\n"
                            f"You appear to be stuck repeating the same action without making progress. Please:\n"
                            f"1. Read the error output carefully and try a different approach\n"
                            f"2. If a command keeps failing, investigate why instead of retrying\n"
                            f"3. If you cannot make progress, provide your final answer as text"
                        ),
                    })

            except asyncio.CancelledError:
                raise
            except httpx.ConnectError as e:
                # Network connection error - retry with backoff
                connect_retries = getattr(self, '_connect_retries', 0) + 1
                self._connect_retries = connect_retries
                max_connect_retries = 3
                if connect_retries <= max_connect_retries:
                    wait_time = 2 ** connect_retries  # Exponential backoff: 2, 4, 8 seconds
                    logger.warning(
                        f"[ToolAgent] Connection error (attempt {connect_retries}/{max_connect_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    logger.warning(f"[ToolAgent] Connection target: {self.base_url}, model: {self.model}")
                    action_logger.error(f"[ERROR] Connection failed to {self.base_url}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue  # Retry the iteration
                else:
                    logger.error(f"[ToolAgent] Connection failed after {max_connect_retries} retries: {e}")
                    logger.error(f"[ToolAgent] Connection target: {self.base_url}, model: {self.model}")
                    action_logger.error(f"[ERROR] Connection failed to {self.base_url} after {max_connect_retries} retries")
                    duration_ms = int((time.time() - start_time) * 1000)
                    self._connect_retries = 0  # Reset for next run
                    return AgentResponse(
                        content="",
                        reasoning=last_reasoning,
                        tool_calls_made=tool_calls_made,
                        api_calls_made=api_calls_made,
                        iterations=iteration + 1,
                        duration_ms=duration_ms,
                        error=f"Connection failed to {self.base_url} after {max_connect_retries} retries: {e}",
                        token_usage=total_token_usage.to_dict(),
                    )
            except httpcore.ProtocolError as e:
                # Transient protocol error (e.g. peer closed connection mid-stream) - retry with backoff
                protocol_retries = getattr(self, '_protocol_retries', 0) + 1
                self._protocol_retries = protocol_retries
                max_protocol_retries = 3
                if protocol_retries <= max_protocol_retries:
                    wait_time = 2 ** protocol_retries
                    logger.warning(
                        f"[ToolAgent] Protocol error (attempt {protocol_retries}/{max_protocol_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    action_logger.error(f"[ERROR] Protocol error, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"[ToolAgent] Protocol error persisted after {max_protocol_retries} retries: {e}")
                    action_logger.error(f"[ERROR] Protocol error after {max_protocol_retries} retries: {e}")
                    duration_ms = int((time.time() - start_time) * 1000)
                    self._protocol_retries = 0
                    return AgentResponse(
                        content="",
                        reasoning=last_reasoning,
                        tool_calls_made=tool_calls_made,
                        api_calls_made=api_calls_made,
                        iterations=iteration + 1,
                        duration_ms=duration_ms,
                        error=f"Protocol error after {max_protocol_retries} retries: {e}",
                        token_usage=total_token_usage.to_dict(),
                    )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_body = ""
                try:
                    error_body = e.response.text
                except Exception:
                    pass

                # Handle rate limiting (429) with exponential backoff
                if status_code == 429:
                    rate_limit_retries = getattr(self, '_rate_limit_retries', 0)
                    if rate_limit_retries < len(RATE_LIMIT_RETRY_DELAYS):
                        wait_time = RATE_LIMIT_RETRY_DELAYS[rate_limit_retries]
                        self._rate_limit_retries = rate_limit_retries + 1
                        logger.warning(
                            f"[ToolAgent] Rate limited (attempt {rate_limit_retries + 1}/{len(RATE_LIMIT_RETRY_DELAYS)}), "
                            f"waiting {wait_time}s before retry"
                        )
                        action_logger.info(
                            f"[RATE LIMIT] iter={iteration + 1} | Attempt {rate_limit_retries + 1}/{len(RATE_LIMIT_RETRY_DELAYS)}, "
                            f"waiting {wait_time}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        continue  # Retry the iteration
                    else:
                        logger.error(f"[ToolAgent] Rate limit exceeded after all retries")
                        action_logger.error(
                            f"[RATE LIMIT] iter={iteration + 1} | Failed after {len(RATE_LIMIT_RETRY_DELAYS)} retries, giving up"
                        )
                        self._rate_limit_retries = 0
                        duration_ms = int((time.time() - start_time) * 1000)
                        return AgentResponse(
                            content="",
                            reasoning=last_reasoning,
                            tool_calls_made=tool_calls_made,
                            api_calls_made=api_calls_made,
                            iterations=iteration + 1,
                            duration_ms=duration_ms,
                            error="Rate limit exceeded after all retries",
                            token_usage=total_token_usage.to_dict(),
                        )

                # Handle context length exceeded (400 with specific error)
                if status_code == 400 and "context_length" in error_body.lower():
                    context_compress_retries = getattr(self, '_context_compress_retries', 0)
                    if context_compress_retries < 2:  # Max 2 compression attempts
                        self._context_compress_retries = context_compress_retries + 1
                        logger.warning(
                            f"[ToolAgent] Context length exceeded, attempting to compress messages "
                            f"(attempt {context_compress_retries + 1}/2)"
                        )
                        action_logger.info(
                            f"[CONTEXT OVERFLOW] iter={iteration + 1} | Detected! Compressing messages (attempt {context_compress_retries + 1}/2)..."
                        )
                        # Try to compress by removing older tool results
                        messages = self._compress_messages(messages)
                        continue  # Retry with compressed context
                    else:
                        logger.error("[ToolAgent] Context overflow persists after compression attempts")
                        action_logger.error(f"[CONTEXT OVERFLOW] iter={iteration + 1} | Failed after 2 compression attempts")
                        self._context_compress_retries = 0

                # Log detailed HTTP error information
                logger.error(f"[ToolAgent] HTTP {status_code} error in iteration {iteration + 1}")
                logger.error(f"[ToolAgent] HTTP error details: {e}")
                if error_body:
                    # Truncate very long error bodies but keep useful info
                    body_preview = error_body[:500] if len(error_body) > 500 else error_body
                    logger.error(f"[ToolAgent] HTTP error body: {body_preview}")
                logger.error(f"[ToolAgent] Model: {self.model}, API: {self.base_url}")
                action_logger.error(f"[ERROR] HTTP {status_code}: {error_body[:200] if error_body else str(e)}")
                duration_ms = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    content="",
                    reasoning=last_reasoning,
                    tool_calls_made=tool_calls_made,
                    api_calls_made=api_calls_made,
                    iterations=iteration + 1,
                    duration_ms=duration_ms,
                    error=f"HTTP {status_code}: {error_body[:300] if error_body else str(e)}",
                    token_usage=total_token_usage.to_dict(),
                )
            except httpx.TimeoutException as e:
                logger.error(f"[ToolAgent] Timeout in iteration {iteration + 1}: {e}")
                logger.error(f"[ToolAgent] Timeout details: model={self.model}, timeout={self.timeout}s")
                action_logger.error(f"[ERROR] Request timeout after {self.timeout}s")
                duration_ms = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    content="",
                    reasoning=last_reasoning,
                    tool_calls_made=tool_calls_made,
                    api_calls_made=api_calls_made,
                    iterations=iteration + 1,
                    duration_ms=duration_ms,
                    error=f"Request timeout ({self.timeout}s): {str(e)}",
                    token_usage=total_token_usage.to_dict(),
                )
            except json.JSONDecodeError as e:
                logger.error(f"[ToolAgent] JSON error in iteration {iteration + 1}: {e}")
                action_logger.error(f"[ERROR] JSON decode error")
                duration_ms = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    content="",
                    reasoning=last_reasoning,
                    tool_calls_made=tool_calls_made,
                    api_calls_made=api_calls_made,
                    iterations=iteration + 1,
                    duration_ms=duration_ms,
                    error=f"JSON decode error: {str(e)}",
                    token_usage=total_token_usage.to_dict(),
                )
            except RuntimeError as e:
                logger.error(f"[ToolAgent] Runtime error in iteration {iteration + 1}: {e}")
                logger.error(f"[ToolAgent] Runtime error context: model={self.model}")
                logger.debug(f"[ToolAgent] Runtime error traceback:\n{traceback.format_exc()}")
                action_logger.error(f"[ERROR] Runtime error: {str(e)}")
                duration_ms = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    content="",
                    reasoning=last_reasoning,
                    tool_calls_made=tool_calls_made,
                    api_calls_made=api_calls_made,
                    iterations=iteration + 1,
                    duration_ms=duration_ms,
                    error=f"Runtime error: {str(e)}",
                    token_usage=total_token_usage.to_dict(),
                )
            except Exception as e:
                # Catch-all for unexpected errors - include exception type for debugging
                error_type = type(e).__name__
                error_msg = str(e) or "(no message)"
                full_error = f"{error_type}: {error_msg}"
                logger.error(f"[ToolAgent] Unexpected error in iteration {iteration + 1}: {full_error}")
                logger.debug(f"[ToolAgent] Traceback:\n{traceback.format_exc()}")
                action_logger.error(f"[ERROR] Unexpected: {full_error}")
                duration_ms = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    content="",
                    reasoning=last_reasoning,
                    tool_calls_made=tool_calls_made,
                    api_calls_made=api_calls_made,
                    iterations=iteration + 1,
                    duration_ms=duration_ms,
                    error=f"Unexpected error ({error_type}): {error_msg}",
                    token_usage=total_token_usage.to_dict(),
                )

        # Max iterations reached
        logger.warning(f"[ToolAgent] Max iterations ({max_iterations}) reached")
        duration_ms = int((time.time() - start_time) * 1000)
        return AgentResponse(
            content="Max iterations reached without completing the task.",
            reasoning=last_reasoning,
            tool_calls_made=tool_calls_made,
            api_calls_made=api_calls_made,
            iterations=max_iterations,
            duration_ms=duration_ms,
            error="max_iterations_reached",
            token_usage=total_token_usage.to_dict(),
        )

    def _compress_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Compress messages to reduce context size when approaching limits.

        Strategy:
        1. Keep system message intact
        2. Keep first user message intact
        3. Aggressively truncate older tool results
        4. Keep recent messages intact
        """
        action_logger = get_action_logger()

        if len(messages) <= 4:
            return messages  # Too few messages to compress

        compressed = []
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        target_chars = MAX_CONTEXT_CHARS * 0.7  # Target 70% of max

        logger.info(
            f"[ToolAgent] Compressing messages: {len(messages)} messages, "
            f"{total_chars} chars -> target {int(target_chars)} chars"
        )
        action_logger.info(
            f"[CONTEXT COMPRESS] Starting: {len(messages)} messages, {total_chars} chars"
        )

        # Always keep first 2 messages (system + user) and last 4 messages
        keep_start = 2
        keep_end = 4
        middle_messages = messages[keep_start:-keep_end] if len(messages) > keep_start + keep_end else []

        compressed.extend(messages[:keep_start])

        # Aggressively truncate middle messages (mostly tool results)
        compressed_count = 0
        for msg in middle_messages:
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                # Reduce to just first 500 chars for old tool results
                if len(content) > 500:
                    msg = msg.copy()
                    msg["content"] = content[:500] + "\n... [COMPRESSED - old result] ..."
                    compressed_count += 1
            compressed.append(msg)

        compressed.extend(messages[-keep_end:])

        new_total = sum(len(str(m.get("content", ""))) for m in compressed)
        reduction_pct = 100 - (new_total * 100 // total_chars) if total_chars > 0 else 0
        logger.info(
            f"[ToolAgent] Compression complete: {total_chars} -> {new_total} chars "
            f"({reduction_pct}% reduction)"
        )
        action_logger.info(
            f"[CONTEXT COMPRESS] Complete: {total_chars} -> {new_total} chars (-{reduction_pct}%), "
            f"compressed {compressed_count} tool results"
        )

        return compressed

    def _compress_repeated_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate assistant+tool message pairs caused by stuck loops.

        Keeps the system prompt, initial user message, and the *last* copy of
        the repeated assistant+tool pair so the LLM still sees the error once.
        """
        if len(messages) <= 6:
            return messages

        def _msg_key(m: dict) -> str:
            return f"{m.get('role')}:{m.get('content', '')}"

        # Find repeating (assistant, tool*) blocks at the end, working backwards.
        blocks: list[tuple[int, int]] = []  # (start, end) of each block
        i = len(messages) - 1
        while i >= 2:
            if messages[i].get("role") == "tool":
                # Find the start of this tool group
                tool_start = i
                while tool_start > 0 and messages[tool_start - 1].get("role") == "tool":
                    tool_start -= 1
                # The message before the tool group should be assistant
                if tool_start > 0 and messages[tool_start - 1].get("role") == "assistant":
                    blocks.append((tool_start - 1, i + 1))
                    i = tool_start - 2
                else:
                    break
            else:
                break

        if len(blocks) < 2:
            return messages  # Nothing to compress

        # Check which blocks are identical
        blocks.reverse()  # chronological order
        ref_block = blocks[-1]  # keep the last one
        ref_content = [_msg_key(messages[j]) for j in range(ref_block[0], ref_block[1])]
        identical_blocks = []
        for b in blocks[:-1]:
            b_content = [_msg_key(messages[j]) for j in range(b[0], b[1])]
            if b_content == ref_content:
                identical_blocks.append(b)

        if not identical_blocks:
            return messages

        # Remove all identical blocks except the last
        remove_indices: set[int] = set()
        for b in identical_blocks:
            remove_indices.update(range(b[0], b[1]))

        compressed = [m for idx, m in enumerate(messages) if idx not in remove_indices]

        removed_count = len(messages) - len(compressed)
        if removed_count > 0:
            action_logger = get_action_logger()
            logger.info(
                f"[ToolAgent] Compressed {removed_count} repeated messages "
                f"({len(messages)} -> {len(compressed)})"
            )
            action_logger.info(
                f"[STUCK LOOP COMPRESS] Removed {removed_count} repeated messages"
            )

        return compressed

    def _build_loop_correction(self, tool_calls: list[dict]) -> str:
        """Build a correction message when a stuck loop is detected."""
        parts = [
            "STOP: You are stuck in a loop, repeatedly making the same tool call "
            "with incorrect arguments. Each attempt has returned an error.\n"
        ]
        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            tool_obj = self.tools.get(tool_name)
            if tool_obj:
                expected = list(tool_obj.parameters.get("properties", {}).keys())
                parts.append(
                    f"Tool '{tool_name}' expects these parameters: {expected}\n"
                    f"Tool description: {tool_obj.description}"
                )
            else:
                parts.append(f"Tool '{tool_name}' is not a valid tool.")
        parts.append(
            "\nPlease fix your tool call arguments, or if you cannot complete "
            "the task, provide your final answer as text."
        )
        return "\n".join(parts)

    async def _call_llm(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Call the LLM API.

        Returns dict with keys: content, reasoning (optional), tool_calls (optional),
        usage, generation_id.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        request_body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }

        # Add tools if available
        tools_schema = self.get_tools_schema()
        if tools_schema:
            request_body["tools"] = tools_schema

        # Don't add temperature for reasoner models
        if not self.is_reasoner:
            request_body["temperature"] = 0.2

        # Use reusable HTTP client with connection pooling
        call_start = time.time()
        client = await self._get_http_client()
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=request_body,
        )
        resp.raise_for_status()
        data = resp.json()
        call_duration_ms = int((time.time() - call_start) * 1000)

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices")

        message = choices[0].get("message") or {}

        # Extract usage information from OpenRouter API response
        usage = data.get("usage", {})
        generation_id = data.get("id", "")

        result = {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "usage": usage,
            "generation_id": generation_id,
            "call_duration_ms": call_duration_ms,
        }

        # Extract reasoning if available (DeepSeek Reasoner)
        if "reasoning_content" in message:
            result["reasoning"] = message["reasoning_content"]
        elif "reasoning" in message:
            result["reasoning"] = message["reasoning"]

        # Notify metrics callback
        if self.metrics_callback:
            try:
                self.metrics_callback({
                    "model": self.model,
                    "usage": usage,
                    "duration_ms": call_duration_ms,
                    "success": True,
                    "error": None,
                    "generation_id": generation_id,
                })
            except Exception:
                pass  # never let metrics crash the agent

        return result

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool and return the result as string."""
        tool = self.tools.get(tool_name)

        if not tool:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.func(**args)
            else:
                result = tool.func(**args)

            # Convert result to string
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result, indent=2, ensure_ascii=False, default=str)

        except TypeError as e:
            expected_params = list(inspect.signature(tool.func).parameters.keys())
            return (
                f"Error calling {tool_name}: Invalid arguments - {e}. "
                f"Expected parameters: {expected_params}"
            )
        except ValueError as e:
            # Value validation error
            return f"Error calling {tool_name}: Invalid value - {e}"
        except (OSError, IOError) as e:
            # File/IO operation errors
            logger.error(f"[ToolAgent] Tool {tool_name} IO error: {e}")
            return f"IO error in {tool_name}: {e}"
        except json.JSONDecodeError as e:
            # JSON parsing errors
            return f"JSON error in {tool_name}: {e}"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Catch-all for unexpected tool errors - include exception type
            error_type = type(e).__name__
            error_msg = str(e) or "(no message)"
            logger.error(f"[ToolAgent] Tool {tool_name} unexpected error: {error_type}: {error_msg}")
            return f"Unexpected error in {tool_name} ({error_type}): {error_msg}"


# ============================================================
# Tool Decorator and Factory Functions
# ============================================================


def tool(
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], Tool]:
    """
    Decorator to convert a function into a Tool with auto-generated JSON Schema.

    The decorator extracts:
    - Function name (or uses provided name)
    - Description from docstring's first line (or uses provided description)
    - Parameters schema from function signature and type annotations
    - Parameter descriptions from docstring's Args section

    Usage:
        @tool()
        async def read_file(path: str, encoding: str = "utf-8") -> str:
            '''Read a file from disk.

            Args:
                path: The file path to read
                encoding: File encoding (default: utf-8)

            Returns:
                File contents as string
            '''
            ...

        # Or with explicit name/description:
        @tool(name="read", description="Read file contents")
        async def read_file(path: str) -> str:
            ...

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring's first line)

    Returns:
        Decorator that returns a Tool object
    """
    def decorator(func: Callable) -> Tool:
        # Get tool name
        tool_name = name or func.__name__

        # Get description from docstring
        tool_description = description
        if not tool_description:
            docstring = func.__doc__
            if docstring:
                # Use first non-empty line
                first_line = docstring.strip().split("\n")[0].strip()
                tool_description = first_line
            else:
                tool_description = f"Execute {tool_name}"

        # Generate parameters schema
        parameters = _generate_json_schema(func)

        return Tool(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            func=func,
        )

    return decorator


def create_tool(
    func: Callable,
    name: str | None = None,
    description: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Tool:
    """
    Create a Tool from a function.

    This is a convenience function that either:
    - Uses provided parameters schema directly, or
    - Auto-generates schema from function signature using the @tool decorator

    Args:
        func: The function to wrap
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring's first line)
        parameters: JSON Schema for parameters (auto-generated if not provided)

    Returns:
        Tool object

    Example:
        # With explicit parameters:
        tool = create_tool(
            my_func,
            name="my_tool",
            description="Does something",
            parameters={"type": "object", "properties": {...}}
        )

        # With auto-generated parameters:
        tool = create_tool(my_func)  # Uses @tool decorator internally
    """
    if parameters is None:
        # Use the tool decorator to auto-generate schema
        return tool(name=name, description=description)(func)

    # Use provided parameters
    tool_name = name or func.__name__
    tool_description = description
    if not tool_description:
        docstring = func.__doc__
        if docstring:
            tool_description = docstring.strip().split("\n")[0].strip()
        else:
            tool_description = f"Execute {tool_name}"

    return Tool(
        name=tool_name,
        description=tool_description,
        parameters=parameters,
        func=func,
    )
