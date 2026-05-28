#!/usr/bin/env python3
"""
API Validation Script - Quick check before running expensive operations.

This script validates your OpenRouter API configuration with minimal cost (~$0.01).
Run this before starting long bug-hunting sessions to catch configuration issues early.

Usage:
    python agent/validate_api.py

Environment:
    OPENROUTER_API_KEY: Your OpenRouter API key (or set in .env file)
"""
import asyncio
import sys
from pathlib import Path

# Ensure we can import from agent package
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tests.test_api_connectivity import run_connectivity_tests

if __name__ == "__main__":
    print(
        """
╔═══════════════════════════════════════════════════════════════╗
║         Consensus Bug Hunter - API Validation                 ║
║                                                               ║
║  This quick check verifies your API configuration before      ║
║  running expensive operations. Cost: < $0.01                  ║
╚═══════════════════════════════════════════════════════════════╝
"""
    )

    success = asyncio.run(run_connectivity_tests())

    if success:
        print(
            """
╔═══════════════════════════════════════════════════════════════╗
║  ✅ Ready to run bug hunting!                                 ║
║                                                               ║
║  Example commands:                                            ║
║    python -m agent --list              # List protocols       ║
║    python -m agent --repo raft -i 5    # Run 5 iterations     ║
║    python -m agent --stats             # View statistics      ║
╚═══════════════════════════════════════════════════════════════╝
"""
        )
    else:
        print(
            """
╔═══════════════════════════════════════════════════════════════╗
║  ❌ Configuration issues detected!                            ║
║                                                               ║
║  Please check:                                                ║
║    1. Your .env file has valid OPENROUTER_API_KEY            ║
║    2. You have credits in your OpenRouter account            ║
║    3. The API endpoint is accessible                         ║
╚═══════════════════════════════════════════════════════════════╝
"""
        )

    sys.exit(0 if success else 1)
