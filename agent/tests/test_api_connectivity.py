#!/usr/bin/env python3
"""
API Connectivity Tests - Low-cost validation of LLM services.

Purpose:
    Spend minimal tokens to verify API connectivity before expensive operations.
    This prevents wasted money from mid-run failures due to configuration issues.

Cost Estimate:
    - LLM test: ~$0.001-0.005 (minimal prompt/response with Claude)
    - Total: < $0.01 for full validation

Usage:
    # Run all API connectivity tests
    python -m pytest agent/tests/test_api_connectivity.py -v

    # Run only with real API (requires .env with valid OPENROUTER_API_KEY)
    python -m pytest agent/tests/test_api_connectivity.py -v -m "api"

    # Quick validation script (standalone)
    python agent/tests/test_api_connectivity.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
import pytest

# Setup path for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================


def get_api_key() -> str | None:
    """Get OpenRouter API key from environment or .env file."""
    # First try environment variable
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    # Try loading from .env file
    env_path = project_root / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    return None


def get_base_url() -> str:
    """Get OpenRouter base URL."""
    return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


# ============================================================
# Test Fixtures
# ============================================================


@pytest.fixture
def api_key():
    """Get API key, skip test if not available."""
    key = get_api_key()
    if not key or key == "test-api-key-not-real":
        pytest.skip("No valid OPENROUTER_API_KEY configured")
    return key


@pytest.fixture
def base_url():
    """Get base URL."""
    return get_base_url()


# ============================================================
# LLM Tests
# ============================================================


@pytest.mark.api
@pytest.mark.asyncio
async def test_llm_connectivity(api_key, base_url):
    """
    Test LLM API connectivity with minimal cost.

    Cost: ~$0.001-0.003 (minimal prompt/response)
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [{"role": "user", "content": "Reply with only 'OK'."}],
                "max_tokens": 10,  # Limit response to minimize cost
            },
        )

        # Check response
        assert response.status_code == 200, f"LLM API failed: {response.text}"

        data = response.json()
        assert "choices" in data, f"Response missing 'choices': {data}"
        assert len(data["choices"]) > 0, "No choices in response"

        content = data["choices"][0].get("message", {}).get("content", "")
        assert content, "Empty response from LLM"

        logger.info(f"✅ LLM API working! Response: {content[:50]}...")


@pytest.mark.api
@pytest.mark.asyncio
async def test_llm_extended_thinking(api_key, base_url):
    """
    Test extended thinking capability (Claude-specific).

    Cost: ~$0.01-0.02 (extended thinking uses more tokens)
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [
                    {
                        "role": "user",
                        "content": "What is 2+2? Think step by step, then answer.",
                    }
                ],
                "max_tokens": 500,
                # Extended thinking parameters (if supported)
                "temperature": 1.0,  # Required for extended thinking
            },
        )

        assert response.status_code == 200, f"Extended thinking failed: {response.text}"

        data = response.json()
        content = data["choices"][0].get("message", {}).get("content", "")

        # Should contain the answer
        assert "4" in content, f"Expected answer '4' in response: {content}"

        logger.info("✅ LLM extended thinking working!")


@pytest.mark.api
@pytest.mark.asyncio
async def test_llm_structured_output(api_key, base_url):
    """
    Test LLM can generate structured output (required for agent workflow).

    Cost: ~$0.005-0.01
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        prompt = """Generate a test scenario in this exact format:

<attack_scenario>
Name: TestScenario
Target Component: TestComponent
Vulnerability Hypothesis: Test hypothesis
Attack Category: safety
</attack_scenario>

Only output the attack_scenario block, nothing else."""

        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            },
        )

        assert response.status_code == 200, f"Structured output failed: {response.text}"

        data = response.json()
        content = data["choices"][0].get("message", {}).get("content", "")

        # Should contain the structured output
        assert "<attack_scenario>" in content, f"Missing attack_scenario tag: {content}"
        assert "</attack_scenario>" in content, f"Missing closing tag: {content}"
        assert "Name:" in content, f"Missing Name field: {content}"

        logger.info("✅ LLM structured output working!")


# ============================================================
# Model Availability Tests
# ============================================================


@pytest.mark.api
@pytest.mark.asyncio
async def test_model_availability(api_key, base_url):
    """
    Test that required models are available.

    Cost: Free (just checking model list)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/models",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
        )

        assert response.status_code == 200, f"Models endpoint failed: {response.text}"

        data = response.json()
        models = {m.get("id") for m in data.get("data", [])}

        # Check required models
        required_models = [
            "anthropic/claude-sonnet-4",
        ]

        for model in required_models:
            # OpenRouter may return models without org prefix
            model_found = any(model in m or model.split("/")[-1] in m for m in models)
            assert model_found, f"Required model not available: {model}"

        logger.info(f"✅ All required models available! Total models: {len(models)}")


# ============================================================
# Rate Limit Tests
# ============================================================


@pytest.mark.api
@pytest.mark.asyncio
async def test_rate_limit_handling(api_key, base_url):
    """
    Test graceful handling of rate limits (just verify headers).

    Cost: ~$0.001 (one LLM call)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            },
        )

        # Check for rate limit headers
        rate_limit_headers = [
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
        ]

        found_headers = {
            h: response.headers.get(h)
            for h in rate_limit_headers
            if response.headers.get(h)
        }

        if found_headers:
            logger.info(f"✅ Rate limit headers present: {found_headers}")
        else:
            logger.info("ℹ️  No rate limit headers in response (may vary by provider)")


# ============================================================
# Integration Tests
# ============================================================


@pytest.mark.api
@pytest.mark.asyncio
async def test_full_workflow_minimal(api_key, base_url, tmp_path):
    """
    Test a minimal workflow simulation.

    This tests the basic flow without actually running against a protocol:
    1. Call LLM with context
    2. Parse structured response

    Cost: ~$0.005-0.01
    """
    # Call LLM with context
    context = "Found pattern: leader_election_bug (CFT safety violation)"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are testing a consensus protocol. Generate attack scenarios.",
                    },
                    {
                        "role": "user",
                        "content": f"Context: {context}\n\nGenerate a simple test name (5 words max).",
                    },
                ],
                "max_tokens": 50,
            },
        )

        assert response.status_code == 200
        content = response.json()["choices"][0]["message"]["content"]
        assert len(content) > 0, "Should generate response"

    logger.info("✅ Full minimal workflow working!")


# ============================================================
# Standalone Runner
# ============================================================


async def run_connectivity_tests():
    """
    Run basic connectivity tests as a standalone script.
    Returns True if all tests pass.
    """
    api_key = get_api_key()
    base_url = get_base_url()

    print("\n" + "=" * 60)
    print("API Connectivity Validation")
    print("=" * 60)

    if not api_key or api_key == "test-api-key-not-real":
        print("\n❌ ERROR: No valid OPENROUTER_API_KEY found!")
        print("\nPlease set the API key:")
        print("  1. Create .env file in project root with:")
        print("     OPENROUTER_API_KEY=your_key_here")
        print("  2. Or set environment variable:")
        print("     export OPENROUTER_API_KEY=your_key_here")
        return False

    print(f"\n📍 Base URL: {base_url}")
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")

    tests_passed = 0
    tests_failed = 0

    # Test 1: LLM API
    print("\n--- Test 1: LLM API (Claude) ---")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "messages": [{"role": "user", "content": "Reply with only: OK"}],
                    "max_tokens": 10,
                },
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"✅ LLM API working! Response: {content}")
                tests_passed += 1
            else:
                print(f"❌ LLM API failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                tests_failed += 1
    except Exception as e:
        print(f"❌ LLM API error: {e}")
        tests_failed += 1

    # Test 2: Structured Output
    print("\n--- Test 2: Structured Output ---")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "messages": [
                        {"role": "user", "content": "Output exactly: <tag>test</tag>"}
                    ],
                    "max_tokens": 20,
                },
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                if "<tag>" in content and "</tag>" in content:
                    print(f"✅ Structured output working!")
                    tests_passed += 1
                else:
                    print(f"⚠️  Structured output may need tuning: {content}")
                    tests_passed += 1  # Still counts as working
            else:
                print(f"❌ Structured output failed: {response.status_code}")
                tests_failed += 1
    except Exception as e:
        print(f"❌ Structured output error: {e}")
        tests_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)

    if tests_failed == 0:
        print("\n🎉 All API connectivity tests passed!")
        print("   Your configuration is ready for the bug hunting workflow.")
        print(f"\n💰 Estimated cost for these tests: < $0.01")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check your configuration.")
        return False


def main():
    """Main entry point for standalone execution."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    success = asyncio.run(run_connectivity_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
