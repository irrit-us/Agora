"""
Async OpenRouter client for chat completions.
Uses httpx with simple retry and error logging.

Note: LangChain integration removed - ToolAgent uses direct httpx calls.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from .base import log_llm_interaction, set_llm_log_callback

logger = logging.getLogger(__name__)

# Re-export set_llm_log_callback for backward compatibility
__all__ = ["chat_completion", "set_llm_log_callback"]


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    temperature: float = 0.2,
    max_tokens: int = 16000,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    max_retries: int = 2,
) -> str:
    """
    Call OpenRouter chat/completions and return text content.
    Retries on timeouts/5xx/429 with backoff.
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

    last_error: Exception | None = None
    last_status: int | None = None
    last_body: str | None = None

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError("OpenRouter response missing choices")
                message = choices[0].get("message") or {}
                content = message.get("content")

                # Extract token usage if available
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens", 0)

                result_content = None
                if isinstance(content, str):
                    result_content = content
                elif isinstance(content, list):
                    # Content can be list of blocks; concatenate text-like parts.
                    parts = []
                    for block in content:
                        if isinstance(block, str):
                            parts.append(block)
                        elif isinstance(block, dict):
                            text = block.get("text")
                            if text:
                                parts.append(text)
                    result_content = "".join(parts)
                else:
                    raise RuntimeError("Unsupported content format from OpenRouter")

                # Log successful response
                duration_ms = int((time.time() - start_time) * 1000)
                log_llm_interaction(
                    event_type="llm_response",
                    model=model,
                    response=result_content,
                    duration_ms=duration_ms,
                    tokens_used=tokens_used,
                )

                return result_content

        except httpx.TimeoutException as e:
            last_error = e
            last_status = None
            last_body = "timeout"
            wait = 2**attempt
            logger.warning(
                f"OpenRouter timeout attempt {attempt+1}/{max_retries+1}, wait {wait}s"
            )
            await asyncio.sleep(wait)
        except httpx.HTTPStatusError as e:
            last_error = e
            last_status = e.response.status_code
            last_body = e.response.text[:500] if e.response.text else "empty"
            status = e.response.status_code
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    f"OpenRouter HTTP {status} attempt {attempt+1}/{max_retries+1}, wait {wait}s, body={last_body}"
                )
                await asyncio.sleep(wait)
                continue
            # Log error response
            duration_ms = int((time.time() - start_time) * 1000)
            log_llm_interaction(
                event_type="llm_response",
                model=model,
                error=f"HTTP {status}: {last_body}",
                duration_ms=duration_ms,
            )
            logger.error(f"OpenRouter HTTP error {status}: {last_body}")
            raise
        except Exception as e:
            last_error = e
            last_status = None
            last_body = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            # Log error response
            duration_ms = int((time.time() - start_time) * 1000)
            log_llm_interaction(
                event_type="llm_response",
                model=model,
                error=str(e),
                duration_ms=duration_ms,
            )
            logger.error(f"OpenRouter error: {e}")
            raise

    # Log final failure
    duration_ms = int((time.time() - start_time) * 1000)
    log_llm_interaction(
        event_type="llm_response",
        model=model,
        error=f"Failed after retries: status={last_status}, body={last_body}",
        duration_ms=duration_ms,
    )
    raise RuntimeError(
        f"OpenRouter call failed after retries: status={last_status}, body={last_body}, err={last_error}"
    )
