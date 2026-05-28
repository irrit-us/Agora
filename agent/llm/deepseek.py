"""
DeepSeek Reasoner (Thinking Mode) Client

Handles DeepSeek Reasoner's special requirements:
- Response includes both `reasoning_content` (CoT) and `content` (final answer)
- Parameters `temperature`, `top_p`, `presence_penalty`, `frequency_penalty` are IGNORED
- Tool calls require passing `reasoning_content` back to API (400 error otherwise)

Note: LangChain integration removed - ToolAgent uses direct httpx calls.
Reference: https://api-docs.deepseek.com/guides/thinking_mode
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from .base import log_llm_interaction, set_llm_log_callback

logger = logging.getLogger(__name__)

# Re-export set_llm_log_callback for backward compatibility
__all__ = ["DeepSeekReasonerResponse", "deepseek_chat_completion", "set_llm_log_callback", "simple_chat", "simple_chat_with_reasoning"]


class DeepSeekReasonerResponse:
    """Response from DeepSeek Reasoner, containing both reasoning and content."""

    def __init__(
        self,
        content: str,
        reasoning_content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        usage: dict[str, int] | None = None,
    ):
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls or []
        self.usage = usage or {}

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def full_response(self) -> str:
        """Get full response including reasoning (for logging/debugging)."""
        parts = []
        if self.reasoning_content:
            parts.append(f"<reasoning>\n{self.reasoning_content}\n</reasoning>")
        if self.content:
            parts.append(self.content)
        return "\n\n".join(parts)

    def to_assistant_message(self, include_reasoning: bool = False) -> dict[str, Any]:
        """
        Convert to assistant message for multi-turn conversation.

        Args:
            include_reasoning: If True, include reasoning_content (needed during tool call loop).
        """
        message = {
            "role": "assistant",
            "content": self.content,
        }
        if include_reasoning and self.reasoning_content:
            message["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return message


# Known base URLs for DeepSeek
OPENROUTER_URLS = [
    "https://openrouter.ai/api/v1",
    "openrouter.ai",
]


def is_openrouter_url(base_url: str) -> bool:
    """Check if the base URL is OpenRouter."""
    return any(ou in base_url for ou in OPENROUTER_URLS)


async def deepseek_chat_completion(
    messages: list[dict[str, Any]],
    *,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-reasoner",
    max_tokens: int = 32000,
    tools: list[dict[str, Any]] | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 120.0,
    max_retries: int = 2,
) -> DeepSeekReasonerResponse:
    """
    Call DeepSeek Reasoner API and return structured response.

    IMPORTANT for Thinking Mode:
    - Do NOT pass temperature, top_p, presence_penalty, frequency_penalty (ignored)
    - Response includes reasoning_content and content
    - For tool calls, must pass reasoning_content back in subsequent turns
    """
    start_time = time.time()

    # Log request
    log_llm_interaction(
        event_type="llm_request",
        model=model,
        messages=messages,
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    # Determine if using OpenRouter
    using_openrouter = is_openrouter_url(base_url)

    # Normalize model name for OpenRouter
    actual_model = model
    if using_openrouter and not model.startswith("deepseek/"):
        if "reasoner" in model.lower():
            actual_model = "deepseek/deepseek-reasoner"
            logger.info(f"Using OpenRouter, normalized model name to: {actual_model}")

    # Build request body - NO temperature/top_p for reasoner!
    request_body = {
        "model": actual_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if tools:
        request_body["tools"] = tools

    last_error: Exception | None = None
    last_status: int | None = None
    last_body: str | None = None

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                )
                resp.raise_for_status()
                data = resp.json()

                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError("DeepSeek response missing choices")

                message = choices[0].get("message") or {}

                # Extract content
                content = message.get("content")
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, str):
                            parts.append(block)
                        elif isinstance(block, dict):
                            text = block.get("text")
                            if text:
                                parts.append(text)
                    content = "".join(parts)
                content = content or ""

                # Extract reasoning_content (DeepSeek Reasoner specific)
                reasoning_content = message.get("reasoning_content")

                # Extract tool_calls
                tool_calls = message.get("tool_calls") or []

                # Extract usage
                usage = data.get("usage", {})

                # Create response object
                response = DeepSeekReasonerResponse(
                    content=content,
                    reasoning_content=reasoning_content,
                    tool_calls=tool_calls,
                    usage=usage,
                )

                # Log successful response
                duration_ms = int((time.time() - start_time) * 1000)
                log_llm_interaction(
                    event_type="llm_response",
                    model=model,
                    response=content,
                    reasoning_content=reasoning_content,
                    duration_ms=duration_ms,
                    tokens_used=usage.get("total_tokens", 0),
                )

                return response

        except httpx.TimeoutException as e:
            last_error = e
            last_status = None
            last_body = "timeout"
            wait = 2**attempt
            logger.warning(
                f"DeepSeek timeout attempt {attempt+1}/{max_retries+1}, wait {wait}s"
            )
            await asyncio.sleep(wait)

        except httpx.HTTPStatusError as e:
            last_error = e
            last_status = e.response.status_code
            last_body = e.response.text[:500] if e.response.text else "empty"
            status = e.response.status_code

            if status == 400:
                logger.error(
                    f"DeepSeek 400 error - check if reasoning_content is passed for tool calls: {last_body}"
                )

            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    f"DeepSeek HTTP {status} attempt {attempt+1}/{max_retries+1}, wait {wait}s"
                )
                await asyncio.sleep(wait)
                continue

            duration_ms = int((time.time() - start_time) * 1000)
            log_llm_interaction(
                event_type="llm_response",
                model=model,
                error=f"HTTP {status}: {last_body}",
                duration_ms=duration_ms,
            )
            logger.error(f"DeepSeek HTTP error {status}: {last_body}")
            raise

        except Exception as e:
            last_error = e
            last_status = None
            last_body = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue

            duration_ms = int((time.time() - start_time) * 1000)
            log_llm_interaction(
                event_type="llm_response",
                model=model,
                error=str(e),
                duration_ms=duration_ms,
            )
            logger.error(f"DeepSeek error: {e}")
            raise

    duration_ms = int((time.time() - start_time) * 1000)
    log_llm_interaction(
        event_type="llm_response",
        model=model,
        error=f"Failed after retries: status={last_status}, body={last_body}",
        duration_ms=duration_ms,
    )
    raise RuntimeError(
        f"DeepSeek call failed after retries: status={last_status}, body={last_body}, err={last_error}"
    )


# ============================================================
# Convenience Functions
# ============================================================


async def simple_chat(
    prompt: str,
    *,
    api_key: str,
    system_prompt: str | None = None,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-reasoner",
) -> str:
    """
    Simple single-turn chat with DeepSeek Reasoner.
    Returns just the content (final answer), not the reasoning.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await deepseek_chat_completion(
        messages=messages,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    return response.content


async def simple_chat_with_reasoning(
    prompt: str,
    *,
    api_key: str,
    system_prompt: str | None = None,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-reasoner",
) -> tuple[str, str | None]:
    """
    Simple single-turn chat returning both content and reasoning.

    Returns:
        Tuple of (content, reasoning_content)
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await deepseek_chat_completion(
        messages=messages,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    return response.content, response.reasoning_content
