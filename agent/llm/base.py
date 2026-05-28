"""
Base module for LLM clients.

Provides common logging utilities shared between OpenRouter and DeepSeek clients.

Uses contextvars for thread-safe, asyncio-safe callback isolation, enabling
parallel execution of experiments with independent logging contexts.
"""

import contextvars
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for log callback
LogCallback = Callable[[dict], None] | None

# Context variable for LLM logging callback - enables parallel execution isolation
# Each asyncio task can have its own callback without affecting others
_llm_log_callback: contextvars.ContextVar[LogCallback] = contextvars.ContextVar(
    "_llm_log_callback", default=None
)


def set_llm_log_callback(callback: LogCallback) -> contextvars.Token:
    """
    Set callback for LLM request/response logging in current context.

    This function is context-aware: when called within an asyncio task,
    the callback is only visible within that task's context, enabling
    parallel execution with isolated logging.

    Args:
        callback: Function that receives log entry dicts, or None to disable

    Returns:
        Token that can be used with reset_llm_log_callback() to restore
        the previous callback value.
    """
    return _llm_log_callback.set(callback)


def reset_llm_log_callback(token: contextvars.Token) -> None:
    """
    Reset the LLM log callback to its previous value.

    Args:
        token: Token returned by set_llm_log_callback()
    """
    try:
        _llm_log_callback.reset(token)
    except ValueError:
        # Token was already reset or context changed
        pass


def get_llm_log_callback() -> LogCallback:
    """
    Get the current LLM log callback for this context.

    Returns:
        The callback function, or None if not set.
    """
    return _llm_log_callback.get()


def log_llm_interaction(
    event_type: str,
    model: str,
    messages: list[dict[str, Any]] | None = None,
    response: str | None = None,
    reasoning_content: str | None = None,
    error: str | None = None,
    duration_ms: int = 0,
    tokens_used: int = 0,
) -> None:
    """
    Log LLM interaction details.

    This function:
    1. Logs to the standard Python logger
    2. Calls the global callback (if set) with structured log data

    Args:
        event_type: Type of event ("llm_request" or "llm_response")
        model: Model name being used
        messages: Request messages (for requests)
        response: Response content (for responses)
        reasoning_content: Reasoning/thinking content (for DeepSeek Reasoner)
        error: Error message (for failed responses)
        duration_ms: Request duration in milliseconds
        tokens_used: Total tokens consumed
    """
    log_entry: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "model": model,
        "duration_ms": duration_ms,
    }

    if messages:
        log_entry["messages"] = messages
        log_entry["message_count"] = len(messages)

    if response:
        log_entry["response"] = response
        log_entry["response_length"] = len(response)

    if reasoning_content:
        log_entry["reasoning_content"] = reasoning_content
        log_entry["reasoning_length"] = len(reasoning_content)

    if error:
        log_entry["error"] = error

    if tokens_used:
        log_entry["tokens_used"] = tokens_used

    # Log to standard logger
    if event_type == "llm_request":
        msg_count = len(messages) if messages else 0
        logger.info(f"[LLM Request] [{model}]: {msg_count} messages")
    elif event_type == "llm_response":
        if error:
            logger.error(f"[LLM Error] [{model}]: {error}")
        else:
            resp_len = len(response) if response else 0
            logger.info(f"[LLM Response] [{model}]: {duration_ms}ms, {resp_len} chars")
            if reasoning_content:
                logger.info(f"[Reasoning]: {len(reasoning_content)} chars")
            if response:
                resp_preview = response[:200] + "..." if len(response) > 200 else response
                logger.debug(f"LLM Response preview: {resp_preview}")

    # Call context-aware callback if set
    callback = _llm_log_callback.get()
    if callback:
        try:
            callback(log_entry)
        except Exception as e:
            logger.warning(f"LLM log callback error: {e}")
