"""
LLM client modules for API communication.

Modules:
    - base: Common logging utilities for all LLM clients
    - openrouter: OpenRouter API client for various LLM models
    - deepseek: DeepSeek Reasoner (Thinking Mode) client

Public API:
    Core functions used internally by ToolAgent:
    - chat_completion: OpenRouter chat completion
    - deepseek_chat_completion: DeepSeek chat completion with reasoning

    Convenience functions for external use:
    - simple_chat: Single-turn chat with DeepSeek Reasoner
    - simple_chat_with_reasoning: Single-turn chat returning both content and reasoning

    Logging utilities (context-aware for parallel execution):
    - set_llm_log_callback: Set callback for LLM logging (returns token for reset)
    - reset_llm_log_callback: Reset callback using token
    - get_llm_log_callback: Get current callback
    - log_llm_interaction: Log LLM request/response details
"""

from .base import (
    log_llm_interaction,
    set_llm_log_callback,
    reset_llm_log_callback,
    get_llm_log_callback,
)
from .deepseek import DeepSeekReasonerResponse, deepseek_chat_completion
from .deepseek import simple_chat, simple_chat_with_reasoning
from .openrouter import chat_completion

__all__ = [
    # Common logging utilities (context-aware)
    "set_llm_log_callback",
    "reset_llm_log_callback",
    "get_llm_log_callback",
    "log_llm_interaction",
    # OpenRouter - core chat completion
    "chat_completion",
    # DeepSeek - core chat completion with reasoning support
    "deepseek_chat_completion",
    "DeepSeekReasonerResponse",
    # DeepSeek - convenience functions for external use
    "simple_chat",
    "simple_chat_with_reasoning",
]
