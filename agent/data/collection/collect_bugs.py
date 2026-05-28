#!/usr/bin/env python3
"""
Bug Pattern Collection Script

Collects issues and PRs from CFT/BFT protocol repositories using GitHub CLI (gh).
Filters valuable bug patterns and stores them in learning memory.
"""

import json
import os
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Repository configurations
REPOSITORIES = {
    # CFT Protocols
    "raft": {"owner": "etcd-io", "repo": "raft", "type": "cft"},
    "raft-rs": {"owner": "tikv", "repo": "raft-rs", "type": "cft"},
    "hashicorp-raft": {"owner": "hashicorp", "repo": "raft", "type": "cft"},
    "efficient-epaxos": {"owner": "efficient", "repo": "epaxos", "type": "cft"},
    "phxpaxos": {"owner": "Tencent", "repo": "phxpaxos", "type": "cft"},
    "zookeeper": {"owner": "apache", "repo": "zookeeper", "type": "cft"},
    "fabric": {"owner": "hyperledger", "repo": "fabric", "type": "cft"},
    # BFT Protocols
    "library": {"owner": "bft-smart", "repo": "library", "type": "bft"},
    "cometbft": {"owner": "cometbft", "repo": "cometbft", "type": "bft"},
    "hotstuff": {"owner": "relab", "repo": "hotstuff", "type": "bft"},
    "sui": {"owner": "MystenLabs", "repo": "sui", "type": "bft"},
    "bitcoin": {"owner": "bitcoin", "repo": "bitcoin", "type": "bft"},
}

# Search keywords for bug-related issues/PRs
BUG_KEYWORDS = [
    "bug",
    "fix",
    "race condition",
    "deadlock",
    "safety",
    "liveness",
    "split-brain",
    "partition",
    "quorum",
    "data loss",
    "inconsistency",
    "corruption",
    "divergence",
    "election",
    "leader",
    "term",
    "epoch",
    "consensus",
]

# Bug categories for classification
BUG_CATEGORIES = {
    "safety": [
        "safety",
        "split-brain",
        "divergence",
        "inconsistent",
        "data loss",
        "corruption",
        "wrong",
    ],
    "liveness": [
        "liveness",
        "deadlock",
        "hang",
        "stuck",
        "timeout",
        "stall",
        "block",
        "progress",
    ],
    "race_condition": ["race", "concurrent", "atomic", "lock", "mutex", "synchron"],
    "state_inconsistency": ["state", "inconsisten", "mismatch", "out of sync", "stale"],
}

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "raw"
FILTERED_DIR = BASE_DIR / "filtered"
# Note: Learning memory is stored in pattern_memory now
LEARNING_MEMORY_DIR = BASE_DIR.parent / "pattern_memory"


@dataclass
class BugPattern:
    """Represents a bug pattern extracted from GitHub issues/PRs"""

    id: str
    timestamp: str
    source_agent: str
    protocol: str
    repo: str
    content: str
    tags: list
    context: dict
    reference_count: int = 0
    led_to_bug: bool = False
    usefulness_score: float = 0.0
    promoted_to_long_term: bool = True
    promoted_at: str | None = None
    embedded: bool = False


def run_gh_command(args: list[str]) -> str | None:
    """Run a gh CLI command and return output"""
    try:
        result = subprocess.run(
            ["gh"] + args, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  Warning: gh command failed: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"  Warning: gh command timed out")
        return None
    except Exception as e:
        print(f"  Error running gh: {e}")
        return None


def collect_issues(owner: str, repo: str, limit: int = 200) -> list[dict]:
    """Collect bug-related issues from a repository"""
    issues = []
    repo_full = f"{owner}/{repo}"

    # Search for bug-related issues
    for keyword in [
        "bug",
        "fix",
        "race",
        "deadlock",
        "safety",
        "liveness",
        "consensus",
    ]:
        print(f"    Searching issues with keyword: {keyword}")
        output = run_gh_command(
            [
                "search",
                "issues",
                f"{keyword} repo:{repo_full}",
                "--state",
                "closed",
                "--limit",
                str(min(limit, 50)),
                "--json",
                "number,title,body,labels,url,state,closedAt",
            ]
        )

        if output:
            try:
                results = json.loads(output)
                for item in results:
                    # Avoid duplicates
                    if not any(i["number"] == item["number"] for i in issues):
                        issues.append(item)
            except json.JSONDecodeError:
                continue

    # Also get issues with bug label
    print(f"    Getting issues with 'bug' label")
    output = run_gh_command(
        [
            "issue",
            "list",
            "-R",
            repo_full,
            "--state",
            "closed",
            "--label",
            "bug",
            "--limit",
            str(limit),
            "--json",
            "number,title,body,labels,url,state,closedAt",
        ]
    )

    if output:
        try:
            results = json.loads(output)
            for item in results:
                if not any(i["number"] == item["number"] for i in issues):
                    issues.append(item)
        except json.JSONDecodeError:
            pass

    return issues


def collect_prs(owner: str, repo: str, limit: int = 200) -> list[dict]:
    """Collect bug-fix PRs from a repository"""
    prs = []
    repo_full = f"{owner}/{repo}"

    # Search for merged bugfix PRs using is:merged in query
    for keyword in ["fix", "bug", "race", "deadlock", "safety"]:
        print(f"    Searching PRs with keyword: {keyword}")
        output = run_gh_command(
            [
                "search",
                "prs",
                f"{keyword} repo:{repo_full} is:merged",
                "--limit",
                str(min(limit, 50)),
                "--json",
                "number,title,body,labels,url,state,mergedAt",
            ]
        )

        if output:
            try:
                results = json.loads(output)
                for item in results:
                    if not any(p["number"] == item["number"] for p in prs):
                        prs.append(item)
            except json.JSONDecodeError:
                continue

    # Also get merged PRs from pr list
    print(f"    Getting merged PRs from list...")
    output = run_gh_command(
        [
            "pr",
            "list",
            "-R",
            repo_full,
            "--state",
            "merged",
            "--limit",
            str(limit),
            "--json",
            "number,title,body,labels,url,state,mergedAt",
        ]
    )

    if output:
        try:
            results = json.loads(output)
            for item in results:
                if not any(p["number"] == item["number"] for p in prs):
                    prs.append(item)
        except json.JSONDecodeError:
            pass

    return prs


def classify_bug(title: str, body: str) -> str | None:
    """Classify a bug into a category based on content"""
    text = f"{title} {body}".lower()

    for category, keywords in BUG_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return category

    return None


def is_confirmed_bug(item: dict) -> tuple[bool, float]:
    """
    Check if this is a confirmed bug and return confidence score.
    Returns (is_confirmed, confidence_score)

    IMPORTANT:
    1. Only bugs with official "bug" label are considered as candidates.
    2. MUST manually verify reviewer/maintainer comments before adding to learning memory!
       - Look for: "confirmed", "I can reproduce", "fixed in PR #xxx", "merged"
       - Reject if: "misconfiguration", "not a bug", "expected behavior", "user error"
    3. This script only pre-filters candidates; human verification is required.
    """
    title = item.get("title", "").lower()
    body = (item.get("body", "") or "").lower()
    labels = [
        l.get("name", "").lower() if isinstance(l, dict) else str(l).lower()
        for l in item.get("labels", [])
    ]
    state = item.get("state", "").lower()

    confidence = 0.0

    # REQUIRED: Must have official bug label to be considered confirmed
    bug_labels = ["bug", "type:bug", "kind/bug", "type: bug", "kind: bug"]
    has_bug_label = any(bl in labels for bl in bug_labels)

    if not has_bug_label:
        return False, 0.0  # Reject if no bug label

    confidence += 0.5  # Base confidence for having bug label

    # Closed state indicates resolution
    if state == "closed":
        confidence += 0.1

    # Fix indicators in title/body
    fix_indicators = [
        "fixed",
        "resolved",
        "fix:",
        "bugfix",
        "root cause",
        "the issue was",
        "the bug was",
        "caused by",
        "the problem was",
        "this was due to",
    ]
    if any(fi in body for fi in fix_indicators):
        confidence += 0.2

    # PR/commit reference indicates fix was made
    pr_indicators = ["pr #", "pull request", "commit", "merged", "fixed in", "fixed by"]
    if any(pi in body for pi in pr_indicators):
        confidence += 0.1

    # Technical details indicate real analysis
    technical_indicators = [
        "stack trace",
        "panic",
        "assertion",
        "error:",
        "exception",
        "crash",
        "race condition",
        "deadlock",
        "data loss",
    ]
    if any(ti in body for ti in technical_indicators):
        confidence += 0.1

    # Negative indicators reduce confidence but don't disqualify
    negative_labels = [
        "question",
        "invalid",
        "wontfix",
        "not a bug",
        "expected behavior",
    ]
    if any(nl in labels for nl in negative_labels):
        confidence -= 0.2

    return True, confidence


def extract_bug_pattern(
    item: dict, repo_name: str, repo_config: dict, is_pr: bool = False
) -> dict | None:
    """Extract bug pattern information from an issue or PR"""
    title = item.get("title", "")
    body = item.get("body", "") or ""
    url = item.get("url", "")
    number = item.get("number", 0)
    labels = [
        l.get("name", "") if isinstance(l, dict) else str(l)
        for l in item.get("labels", [])
    ]

    # Skip if too short or not descriptive
    if len(body) < 100:
        return None

    # Check if this is a confirmed bug
    is_confirmed, confidence = is_confirmed_bug(item)
    if not is_confirmed:
        return None

    # Classify the bug
    category = classify_bug(title, body)
    if not category:
        return None

    # Check if it's consensus/distributed system related
    consensus_keywords = [
        "consensus",
        "raft",
        "paxos",
        "bft",
        "leader",
        "election",
        "term",
        "epoch",
        "quorum",
        "commit",
        "replicate",
        "log",
        "state machine",
        "snapshot",
        "partition",
        "node",
        "cluster",
        "voter",
        "follower",
        "candidate",
        "view",
        "propose",
    ]

    text_lower = f"{title} {body}".lower()
    if not any(kw in text_lower for kw in consensus_keywords):
        return None

    return {
        "number": number,
        "title": title,
        "body": body[:3000],  # Truncate very long bodies
        "url": url,
        "labels": labels,
        "category": category,
        "repo": repo_name,
        "protocol_type": repo_config["type"],
        "is_pr": is_pr,
        "confidence": confidence,
        "timestamp": item.get("closedAt")
        or item.get("mergedAt")
        or datetime.now().isoformat(),
    }


def collect_all_repositories():
    """Collect issues and PRs from all repositories"""
    print("=" * 60)
    print("Starting Bug Pattern Collection")
    print("=" * 60)

    # Ensure directories exist
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    FILTERED_DIR.mkdir(parents=True, exist_ok=True)

    all_patterns = []

    for repo_name, config in REPOSITORIES.items():
        print(f"\n[{repo_name}] Collecting from {config['owner']}/{config['repo']}...")

        repo_dir = RAW_DIR / repo_name
        repo_dir.mkdir(exist_ok=True)

        # Collect issues
        print(f"  Collecting issues...")
        issues = collect_issues(config["owner"], config["repo"])
        print(f"    Found {len(issues)} issues")

        with open(repo_dir / "issues.json", "w") as f:
            json.dump(issues, f, indent=2)

        # Collect PRs
        print(f"  Collecting PRs...")
        prs = collect_prs(config["owner"], config["repo"])
        print(f"    Found {len(prs)} PRs")

        with open(repo_dir / "prs.json", "w") as f:
            json.dump(prs, f, indent=2)

        # Extract patterns
        print(f"  Extracting bug patterns...")
        patterns = []

        for issue in issues:
            pattern = extract_bug_pattern(issue, repo_name, config, is_pr=False)
            if pattern:
                patterns.append(pattern)

        for pr in prs:
            pattern = extract_bug_pattern(pr, repo_name, config, is_pr=True)
            if pattern:
                patterns.append(pattern)

        print(f"    Extracted {len(patterns)} relevant patterns")
        all_patterns.extend(patterns)

    # Save all filtered patterns
    with open(FILTERED_DIR / "bug_patterns.json", "w") as f:
        json.dump(all_patterns, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Collection Complete!")
    print(f"Total patterns extracted: {len(all_patterns)}")
    print(f"Raw data saved to: {RAW_DIR}")
    print(f"Filtered patterns saved to: {FILTERED_DIR / 'bug_patterns.json'}")
    print("=" * 60)

    return all_patterns


def extract_root_cause(body: str) -> str:
    """Try to extract root cause from bug description"""
    body_lower = body.lower()

    # Look for root cause patterns
    patterns = [
        ("caused by", 200),
        ("root cause", 200),
        ("the issue was", 200),
        ("the bug was", 200),
        ("the problem was", 200),
        ("this was due to", 200),
        ("because", 150),
        ("due to", 150),
    ]

    for pattern, max_len in patterns:
        idx = body_lower.find(pattern)
        if idx != -1:
            # Extract text after the pattern
            start = idx
            end = min(idx + max_len, len(body))
            # Find sentence end
            for char in ".!?\n":
                sent_end = body.find(char, idx + len(pattern))
                if sent_end != -1 and sent_end < end:
                    end = sent_end + 1
                    break
            return body[start:end].strip()

    return ""


def create_learning_memory_entry(pattern: dict) -> BugPattern:
    """Create a learning memory entry from a filtered pattern"""
    short_id = str(uuid.uuid4())[:8]
    repo = pattern["repo"]
    category = pattern["category"]
    title = pattern["title"]
    body = pattern["body"]

    # Extract root cause if possible
    root_cause = extract_root_cause(body)

    # Build content string following the format:
    # BUG PATTERN: [name]. DESCRIPTION: ... ROOT CAUSE: ... LESSON: ...
    content_parts = [f"BUG PATTERN: {title}."]

    # Add description (first 400 chars of body, cleaned)
    desc = body[:400].replace("\r\n", " ").replace("\n", " ")
    desc = " ".join(desc.split())  # Normalize whitespace
    content_parts.append(f"DESCRIPTION: {desc}")

    # Add category
    content_parts.append(f"CATEGORY: {category}.")

    # Add root cause if found
    if root_cause:
        root_cause_clean = root_cause.replace("\r\n", " ").replace("\n", " ")
        root_cause_clean = " ".join(root_cause_clean.split())
        content_parts.append(f"ROOT CAUSE: {root_cause_clean}")

    # Add source reference
    content_parts.append(f"SOURCE: {pattern['url']}")

    # Add lesson based on category
    lessons = {
        "safety": f"LESSON: This safety violation in {repo} shows how {pattern['protocol_type'].upper()} implementations can diverge or lose data. Always verify state consistency across nodes.",
        "liveness": f"LESSON: This liveness bug in {repo} demonstrates how {pattern['protocol_type'].upper()} systems can get stuck. Check for timeout handling and progress guarantees.",
        "race_condition": f"LESSON: This race condition in {repo} shows concurrency pitfalls in {pattern['protocol_type'].upper()} implementations. Ensure atomic operations for state transitions.",
        "state_inconsistency": f"LESSON: This state inconsistency in {repo} highlights synchronization issues. Verify state machine determinism and message ordering.",
    }
    content_parts.append(
        lessons.get(
            category,
            f"LESSON: Review this {category} pattern for potential issues in other implementations.",
        )
    )

    content = " ".join(content_parts)

    # Build tags
    tags = ["bug_pattern", category, pattern["protocol_type"], repo]
    # Add clean labels
    for label in pattern.get("labels", [])[:3]:
        if label and label not in tags:
            tags.append(label.lower().replace(" ", "_"))

    # Build context
    context = {
        "issue_url": pattern["url"],
        "bug_category": category,
        "pattern_type": category,
        "source_number": pattern["number"],
        "is_pr": pattern["is_pr"],
        "confidence": pattern.get("confidence", 0.0),
    }

    return BugPattern(
        id=f"bug_pattern_{repo}_{short_id}",
        timestamp=datetime.now().isoformat(),
        source_agent="github_collector",
        protocol=pattern["protocol_type"],
        repo=repo,
        content=content,
        tags=tags,
        context=context,
        promoted_at=datetime.now().isoformat(),
    )


def store_to_learning_memory(patterns: list[dict], max_per_repo: int = 10):
    """Store filtered patterns to learning memory"""
    print(f"\nStoring top patterns to learning memory...")

    LEARNING_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # Group by repo and take top N per repo
    by_repo = {}
    for p in patterns:
        repo = p["repo"]
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(p)

    stored_count = 0
    for repo, repo_patterns in by_repo.items():
        # Sort by body length (more detailed = potentially more valuable)
        repo_patterns.sort(key=lambda x: len(x.get("body", "")), reverse=True)

        for pattern in repo_patterns[:max_per_repo]:
            entry = create_learning_memory_entry(pattern)

            # Save to learning memory
            file_path = LEARNING_MEMORY_DIR / f"{entry.id}.json"
            with open(file_path, "w") as f:
                json.dump(asdict(entry), f, indent=2)

            stored_count += 1
            print(f"  Stored: {entry.id}")

    print(f"\nStored {stored_count} patterns to learning memory")
    return stored_count


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect bug patterns from GitHub repositories"
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Collect issues and PRs from repositories",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Store filtered patterns to learning memory",
    )
    parser.add_argument(
        "--all", action="store_true", help="Run full pipeline (collect + store)"
    )
    parser.add_argument(
        "--max-per-repo", type=int, default=10, help="Max patterns to store per repo"
    )

    args = parser.parse_args()

    if args.all or args.collect:
        patterns = collect_all_repositories()
    else:
        # Load existing patterns
        patterns_file = FILTERED_DIR / "bug_patterns.json"
        if patterns_file.exists():
            with open(patterns_file) as f:
                patterns = json.load(f)
        else:
            print("No patterns file found. Run with --collect first.")
            return

    if args.all or args.store:
        store_to_learning_memory(patterns, max_per_repo=args.max_per_repo)


if __name__ == "__main__":
    main()
