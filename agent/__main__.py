"""
Consensus Bug Hunter - Claude Agent SDK Edition

Usage:
    python -m agent --repo raft
    python -m agent --repo raft --forever
    python -m agent --all
    python -m agent --list
    python -m agent --stats
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging level"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger("agent").setLevel(level)


async def run_single_protocol(repo: str, iterations: int = 10, forever: bool = False):
    """Run bug hunting for a single protocol"""
    import signal

    from .config.settings import get_settings
    from .core.orchestrator import create_orchestrator

    settings = get_settings()

    # Verify protocol exists
    if repo not in settings.protocols:
        available = ", ".join(settings.protocols.keys())
        logger.error(f"Protocol '{repo}' not found. Available: {available}")
        return

    logger.info(f"Starting bug hunting for {repo}")

    orchestrator = None
    try:
        orchestrator = await create_orchestrator(repo, settings)

        # Register signal handlers to ensure metrics are saved on interrupt
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: _handle_signal(s, orchestrator),
            )

        await orchestrator.run(max_iterations=iterations, forever=forever)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        if orchestrator:
            orchestrator.metrics.finalize(status="interrupted")
    except Exception as e:
        logger.error(f"Error running orchestrator: {e}")
        if orchestrator:
            orchestrator.metrics.finalize(status="error")
        raise


def _handle_signal(sig, orchestrator):
    """Handle OS signal by finalizing metrics before exit."""
    logger.info(f"Received signal {sig}, saving metrics...")
    if orchestrator and hasattr(orchestrator, "metrics"):
        orchestrator.metrics.finalize(status="interrupted")
    raise KeyboardInterrupt


async def run_all_protocols(
    iterations: int = 10, forever: bool = False, parallel: int = 4
):
    """Run bug hunting for all protocols in parallel"""
    from .config.settings import get_settings
    from .core.orchestrator import create_orchestrator

    settings = get_settings()
    protocols = list(settings.protocols.keys())

    if not protocols:
        logger.error("No protocols configured")
        return

    logger.info(f"Running bug hunting for {len(protocols)} protocols")
    logger.info(f"Protocols: {', '.join(protocols)}")

    # Create tasks for each protocol
    semaphore = asyncio.Semaphore(parallel)

    async def run_with_semaphore(proto: str):
        async with semaphore:
            try:
                orchestrator = await create_orchestrator(proto, settings)
                await orchestrator.run(max_iterations=iterations, forever=forever)
            except Exception as e:
                logger.error(f"Error in {proto}: {e}")

    tasks = [run_with_semaphore(proto) for proto in protocols]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


def list_protocols():
    """List all available protocols"""
    from .config.settings import get_settings

    settings = get_settings()
    project_root = Path(__file__).parent.parent.resolve()

    if not settings.protocols:
        print("No protocols configured.")
        print("Add protocols to agent/config/protocols.yaml")
        return

    print("\nAvailable protocols:")
    print("-" * 60)

    for name, config in settings.protocols.items():
        print(f"\n  {name}")
        print(f"    Type: {config.type.upper()}")
        print(f"    Language: {config.language}")
        print(f"    Config Path: {config.path}")

        # Resolve and show repo root
        repo_path = config.path
        if repo_path.startswith("./"):
            repo_path = repo_path[2:]
        resolved = project_root / repo_path

        if resolved.exists():
            print(f"    Repo Root: {resolved} ✓")
        else:
            print(f"    Repo Root: {resolved} ❌ Not found")

        if config.description:
            print(f"    Description: {config.description}")


async def show_stats(protocol: str = None):
    """Show test history statistics"""
    from .memory.test_history import TestHistory

    history = TestHistory(Path(__file__).parent / "data" / "test_history")

    # Test stats
    stats = await history.get_stats(protocol)

    print("\n" + "=" * 50)
    if protocol:
        print(f"Test History Statistics for {protocol}")
    else:
        print("Test History Statistics (All Protocols)")
    print("=" * 50)

    print(f"\nTotal Tests: {stats['total_tests']}")
    print(f"Bugs Found: {stats['bugs_found']}")
    print(f"False Positives: {stats['false_positives']}")
    print(f"Unrealistic Scenarios: {stats['unrealistic_scenarios']}")
    print(f"Issues Created: {stats['issues_created']}")
    print(f"PRs Created: {stats['prs_created']}")

    # Bug summary
    bug_summary = await history.get_bug_summary()

    print("\n" + "-" * 50)
    print("Bug Summary")
    print("-" * 50)
    print(f"\nTotal Bugs: {bug_summary['total_bugs']}")

    if bug_summary["by_category"]:
        print("\nBy Category:")
        for cat, count in bug_summary["by_category"].items():
            if count > 0:
                print(f"  - {cat}: {count}")

    if bug_summary["by_status"]:
        print("\nBy Status:")
        for status, count in bug_summary["by_status"].items():
            if count > 0:
                print(f"  - {status}: {count}")

    if bug_summary["by_protocol"]:
        print("\nBy Protocol:")
        for proto, info in bug_summary["by_protocol"].items():
            print(f"  {proto}: {info['count']} bugs")
            for cat, cnt in info["categories"].items():
                if cnt > 0:
                    print(f"    - {cat}: {cnt}")


def main():
    parser = argparse.ArgumentParser(
        description="Consensus Bug Hunter - Claude Agent SDK Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent --list                    # List available protocols
  python -m agent --repo raft               # Run 10 iterations on raft
  python -m agent --repo raft --forever     # Run indefinitely
  python -m agent --repo raft -i 50         # Run 50 iterations
  python -m agent --all --parallel 4        # Run all protocols, 4 at a time
  python -m agent --stats                   # Show statistics
  python -m agent --stats --repo raft       # Show stats for raft only
        """,
    )

    parser.add_argument("--repo", "-r", help="Run for a single protocol repository")
    parser.add_argument(
        "--all", "-a", action="store_true", help="Run for all configured protocols"
    )
    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=10,
        help="Maximum iterations (default: 10, ignored if --forever)",
    )
    parser.add_argument(
        "--forever", "-f", action="store_true", help="Run indefinitely until Ctrl+C"
    )
    parser.add_argument(
        "--parallel",
        "-j",
        type=int,
        default=4,
        help="Max parallel processes for --all (default: 4)",
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List available protocols"
    )
    parser.add_argument(
        "--stats", "-s", action="store_true", help="Show test history statistics"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Handle commands
    if args.list:
        list_protocols()
        return

    if args.stats:
        asyncio.run(show_stats(args.repo))
        return

    if args.all:
        asyncio.run(
            run_all_protocols(
                iterations=args.iterations, forever=args.forever, parallel=args.parallel
            )
        )
    elif args.repo:
        asyncio.run(
            run_single_protocol(
                repo=args.repo, iterations=args.iterations, forever=args.forever
            )
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
