"""
Integration test for token usage tracking.

Uses real API call with minimal token consumption (~10-20 tokens)
to verify OpenRouter returns the expected usage format.

Run:
    python -m pytest agent/tests/test_token_usage_integration.py -v -s

Skip in CI:
    python -m pytest agent/tests/ -v --ignore=agent/tests/test_token_usage_integration.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import httpx
import pytest

logger = logging.getLogger(__name__)

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.baseline.react_agent import TokenUsage


@pytest.fixture
def settings():
    """Load settings with API key."""
    from agent.config.settings import load_settings

    return load_settings()


@pytest.mark.integration
class TestTokenUsageIntegration:
    """
    Real API tests for token usage tracking.

    Requires OPENROUTER_API_KEY environment variable.
    """

    @pytest.mark.asyncio
    async def test_openrouter_usage_format(self, settings):
        """
        Verify OpenRouter returns expected usage structure.

        This test makes a single, minimal API call to verify the
        actual response format from OpenRouter.
        """
        api_key = settings.openrouter_api_key
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Minimal request to consume very few tokens
        request_body = {
            "model": "openai/gpt-4o-mini",  # Cheap model
            "messages": [{"role": "user", "content": "Say 'ok'"}],
            "max_tokens": 5,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()

        # Verify response has usage field
        assert "usage" in data, f"Response missing 'usage' field. Keys: {data.keys()}"
        usage = data["usage"]

        logger.info("OpenRouter Usage Response: %s", usage)

        # Required fields
        assert "prompt_tokens" in usage, "Missing prompt_tokens"
        assert "completion_tokens" in usage, "Missing completion_tokens"
        assert "total_tokens" in usage, "Missing total_tokens"

        # Verify total calculation
        expected_total = usage["prompt_tokens"] + usage["completion_tokens"]
        assert usage["total_tokens"] == expected_total, (
            f"total_tokens ({usage['total_tokens']}) != "
            f"prompt_tokens ({usage['prompt_tokens']}) + "
            f"completion_tokens ({usage['completion_tokens']})"
        )

        # Log optional fields presence
        has_cost = "cost" in usage
        has_prompt_details = "prompt_tokens_details" in usage
        has_completion_details = "completion_tokens_details" in usage

        logger.debug(
            "Optional fields - has_cost: %s, has_prompt_details: %s, has_completion_details: %s",
            has_cost, has_prompt_details, has_completion_details
        )

        # Verify TokenUsage class can parse it
        token_usage = TokenUsage()
        token_usage.add(usage)

        assert token_usage.prompt_tokens == usage["prompt_tokens"]
        assert token_usage.completion_tokens == usage["completion_tokens"]
        assert token_usage.total_tokens == usage["total_tokens"]

        logger.info("TokenUsage parsed: %s", token_usage.to_dict())

    @pytest.mark.asyncio
    async def test_token_usage_accumulation(self, settings):
        """
        Test that TokenUsage correctly accumulates multiple API calls.
        """
        api_key = settings.openrouter_api_key
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        token_usage = TokenUsage()

        # Make two minimal API calls
        for i in range(2):
            request_body = {
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": f"Say '{i}'"}],
                "max_tokens": 3,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                )
                resp.raise_for_status()
                data = resp.json()

            usage = data.get("usage", {})
            token_usage.add(usage)
            logger.debug("Call %d: %d tokens", i + 1, usage.get("total_tokens", 0))

        logger.info("Accumulated tokens: %s", token_usage.to_dict())

        # Should have accumulated tokens from both calls
        assert token_usage.total_tokens > 0
        assert token_usage.prompt_tokens > 0
        assert token_usage.completion_tokens > 0


class TestTokenUsageUnit:
    """Unit tests for TokenUsage dataclass (no API calls)."""

    def test_token_usage_creation(self):
        """Test creating TokenUsage with defaults."""
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.reasoning_tokens == 0
        assert usage.cost == 0.0

    def test_token_usage_add_basic(self):
        """Test adding basic usage without details."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        })
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_token_usage_add_with_cost(self):
        """Test adding usage with cost."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.05,
        })
        assert usage.cost == pytest.approx(0.05)

    def test_token_usage_add_with_details(self):
        """Test adding usage with nested details."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.05,
            "prompt_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 10},
            "completion_tokens_details": {"reasoning_tokens": 15},
        })
        assert usage.cached_tokens == 20
        assert usage.reasoning_tokens == 15
        assert usage.cost == pytest.approx(0.05)

    def test_token_usage_accumulation(self):
        """Test multiple adds accumulate correctly."""
        usage = TokenUsage()
        usage.add({"prompt_tokens": 100, "total_tokens": 100, "cost": 0.1})
        usage.add({"prompt_tokens": 200, "total_tokens": 200, "cost": 0.2})
        assert usage.prompt_tokens == 300
        assert usage.total_tokens == 300
        assert usage.cost == pytest.approx(0.3)

    def test_token_usage_to_dict(self):
        """Test serialization to dict."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.05,
            "prompt_tokens_details": {"cached_tokens": 10},
            "completion_tokens_details": {"reasoning_tokens": 5},
        })
        d = usage.to_dict()

        assert d["prompt_tokens"] == 100
        assert d["completion_tokens"] == 50
        assert d["total_tokens"] == 150
        assert d["cached_tokens"] == 10
        assert d["reasoning_tokens"] == 5
        assert d["cost"] == pytest.approx(0.05)

    def test_token_usage_handles_none_details(self):
        """Test handling of None or missing details."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": None,
            "completion_tokens_details": None,
        })
        assert usage.cached_tokens == 0
        assert usage.reasoning_tokens == 0

    def test_token_usage_handles_none_cost(self):
        """Test handling of None cost value."""
        usage = TokenUsage()
        usage.add({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": None,
        })
        assert usage.cost == 0.0
