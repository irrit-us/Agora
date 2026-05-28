"""
Token Usage Tracking for OpenRouter API.

This module provides a shared TokenUsage class for tracking token consumption
across multiple LLM calls. Used by both the baseline ReAct agent and the
multi-agent orchestrator system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TokenUsage:
    """
    Token usage statistics from OpenRouter API.

    Tracks cumulative token consumption across multiple LLM calls,
    including detailed breakdowns for caching and reasoning tokens.

    Attributes:
        prompt_tokens: Total input/prompt tokens consumed.
        completion_tokens: Total output/completion tokens generated.
        total_tokens: Sum of prompt and completion tokens.
        cached_tokens: Tokens read from cache (reduces cost).
        reasoning_tokens: Tokens used for reasoning (e.g., o1, DeepSeek Reasoner).
        cost: Total API cost in credits.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0

    def add(self, usage: dict[str, Any]) -> None:
        """
        Accumulate token usage from a single API response.

        Args:
            usage: The 'usage' dict from OpenRouter API response.
        """
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)
        self.cost += usage.get("cost", 0.0) or 0.0

        # Parse nested details
        prompt_details = usage.get("prompt_tokens_details") or {}
        self.cached_tokens += prompt_details.get("cached_tokens", 0)

        completion_details = usage.get("completion_tokens_details") or {}
        self.reasoning_tokens += completion_details.get("reasoning_tokens", 0)

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """
        Add two TokenUsage instances together.

        Args:
            other: Another TokenUsage instance to add.

        Returns:
            A new TokenUsage instance with combined totals.
        """
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cost=self.cost + other.cost,
        )

    def __iadd__(self, other: TokenUsage) -> TokenUsage:
        """
        In-place addition of another TokenUsage instance.

        Args:
            other: Another TokenUsage instance to add.

        Returns:
            Self with updated totals.
        """
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cached_tokens += other.cached_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cost += other.cost
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cost": self.cost,
        }

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.cached_tokens = 0
        self.reasoning_tokens = 0
        self.cost = 0.0

    def copy(self) -> TokenUsage:
        """Create a copy of this TokenUsage instance."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            cached_tokens=self.cached_tokens,
            reasoning_tokens=self.reasoning_tokens,
            cost=self.cost,
        )

    def format_summary(self) -> str:
        """
        Format a concise summary string for logging.

        Returns:
            A formatted string like "prompt=1000 completion=500 total=1500 cost=$0.0150"
        """
        return (
            f"prompt={self.prompt_tokens:,} completion={self.completion_tokens:,} "
            f"total={self.total_tokens:,} cost=${self.cost:.4f}"
        )
