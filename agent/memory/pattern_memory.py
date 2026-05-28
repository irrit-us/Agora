"""
Pattern Memory - stores known bug patterns for CFT and BFT protocols.

This module provides persistent storage for bug patterns that can be tested
across different consensus protocol implementations.

Design Note:
    This module uses synchronous file I/O within async functions. This is
    intentional because:
    1. File operations are fast (small JSON files) and don't block significantly
    2. Using aiofiles would add an external dependency
    3. The bottleneck is LLM API calls, not file I/O
    If file I/O becomes a bottleneck, consider using aiofiles or thread pools.
"""

import json
import re
import uuid
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel, Field


# ============================================================
# Constants
# ============================================================

# Maximum number of words to include in pattern file slugs
MAX_PATTERN_SLUG_WORDS = 8


class BugPattern(BaseModel):
    """A known bug pattern that can be tested across protocols

    The pattern_id serves as a human-readable summary of the bug pattern.
    It should be a concise description that helps the agent understand
    what this pattern is about without reading the full description.

    Example pattern_id:
        "Byzantine DoS via insufficient QC validation - single malicious node can stall consensus"
        "Unbuffered channel notification loss causing deadlock in producer-consumer patterns"

    Note: The file name is automatically generated as a slug from pattern_id.
    """

    pattern_id: str  # Summary of the bug pattern (required, no default)
    protocol_type: str  # "cft" or "bft"
    description: str  # Detailed explanation (primary content)

    # Optional structured fields (may be extracted from description)
    fault_type: str | None = None  # e.g., "network_partition", "node_crash"
    bug_category: str | None = None  # "safety", "liveness", "agreement"
    trigger_condition: str | None = None  # Description of what triggers the bug
    test_template: str | None = None  # Code template or description for the test

    # Discovery info
    discovered_in_repo: str | None = None
    discovery_date: str | None = None
    discovery_process: str | None = None

    # Metadata (optional)
    tags: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)

    # Tracking
    tested_repos: list[str] = Field(default_factory=list)
    confirmed_in_repos: list[str] = Field(default_factory=list)


class PatternMemory:
    """
    Manages bug patterns stored in JSON files.
    Patterns are separated by protocol type (CFT/BFT).
    Thread-safe with file locking for cross-process access.
    """

    def __init__(self, base_path: Path | None = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "pattern_memory"
        self.base_path = Path(base_path)
        self.cft_path = self.base_path / "cft"
        self.bft_path = self.base_path / "bft"

        # Ensure directories exist
        self.cft_path.mkdir(parents=True, exist_ok=True)
        self.bft_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, protocol_type: str) -> Path:
        """Get the directory path for a protocol type"""
        if protocol_type.lower() == "cft":
            return self.cft_path
        elif protocol_type.lower() == "bft":
            return self.bft_path
        else:
            raise ValueError(f"Unknown protocol type: {protocol_type}")

    def _get_lock(self, file_path: Path) -> FileLock:
        """Get a file lock for thread-safe access"""
        lock_path = file_path.with_suffix(".lock")
        return FileLock(str(lock_path))

    def _generate_file_slug(
        self, pattern_id: str, max_words: int = MAX_PATTERN_SLUG_WORDS
    ) -> str:
        """
        Generate a file-safe slug from pattern_id (which is now a summary).

        Args:
            pattern_id: The pattern identifier/summary string.
            max_words: Maximum number of words to include in the slug (default: 8).

        Returns:
            A file-safe slug string.

        Examples:
            "Byzantine DoS via insufficient QC validation - single malicious node..."
            -> "byzantine_dos_via_insufficient_qc_validation_single_malicious"

            "Unbuffered channel notification loss causing deadlock..."
            -> "unbuffered_channel_notification_loss_causing_deadlock"
        """
        # Remove special characters, keep only alphanumeric and spaces
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", pattern_id)
        # Split into words and take first N
        words = cleaned.lower().split()[:max_words]
        # Join with underscore
        slug = "_".join(words)
        # Ensure it's not empty
        if not slug:
            slug = str(uuid.uuid4())[:8]
        return slug

    async def add_pattern(self, pattern: BugPattern) -> str:
        """Add a new bug pattern"""
        dir_path = self._get_path(pattern.protocol_type)

        # Generate file-safe slug from pattern_id (which is now a summary)
        file_slug = self._generate_file_slug(pattern.pattern_id)
        file_path = dir_path / f"{file_slug}.json"

        # If file already exists, append a short uuid to avoid collision
        if file_path.exists():
            file_slug = f"{file_slug}_{str(uuid.uuid4())[:6]}"
            file_path = dir_path / f"{file_slug}.json"

        with self._get_lock(file_path):
            with open(file_path, "w") as f:
                json.dump(pattern.model_dump(), f, indent=2)

        return pattern.pattern_id

    async def get_pattern(
        self, pattern_id: str, protocol_type: str
    ) -> BugPattern | None:
        """
        Get a specific pattern by pattern_id.

        Since pattern_id is now a summary and file names are slugs,
        we search through all files to find the matching pattern.
        """
        dir_path = self._get_path(protocol_type)

        # Search through all pattern files
        for file_path in dir_path.glob("*.json"):
            with self._get_lock(file_path):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    if data.get("pattern_id") == pattern_id:
                        return BugPattern(**data)
                except json.JSONDecodeError:
                    # Skip corrupted JSON files
                    continue
                except (OSError, IOError):
                    # Skip files with IO errors
                    continue
                except (KeyError, TypeError, ValueError):
                    # Skip files with invalid data structure
                    continue

        return None

    async def get_all_patterns(
        self, protocol_type: str | None = None
    ) -> list[BugPattern]:
        """Get all patterns, optionally filtered by protocol type"""
        patterns = []

        dirs_to_search = []
        if protocol_type is None:
            dirs_to_search = [self.cft_path, self.bft_path]
        else:
            dirs_to_search = [self._get_path(protocol_type)]

        for dir_path in dirs_to_search:
            for file_path in dir_path.glob("*.json"):
                with self._get_lock(file_path):
                    try:
                        with open(file_path, "r") as f:
                            data = json.load(f)
                        patterns.append(BugPattern(**data))
                    except json.JSONDecodeError:
                        # Skip corrupted JSON files
                        continue
                    except (OSError, IOError):
                        # Skip files with IO errors
                        continue
                    except (KeyError, TypeError, ValueError):
                        # Skip files with invalid data structure
                        continue

        return patterns

    async def _find_pattern_file(
        self, pattern_id: str, protocol_type: str
    ) -> Path | None:
        """Find the file path for a pattern by its pattern_id"""
        dir_path = self._get_path(protocol_type)

        for file_path in dir_path.glob("*.json"):
            with self._get_lock(file_path):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    if data.get("pattern_id") == pattern_id:
                        return file_path
                except json.JSONDecodeError:
                    # Skip corrupted JSON files
                    continue
                except (OSError, IOError):
                    # Skip files with IO errors
                    continue

        return None

    async def get_patterns_for_protocol(
        self,
        protocol_type: str,
        not_tested_in: str | None = None,
        bug_category: str | None = None,
    ) -> list[BugPattern]:
        """
        Get patterns applicable to a protocol type.

        Args:
            protocol_type: "cft" or "bft"
            not_tested_in: Exclude patterns already tested in this repo
            bug_category: Filter by bug category
        """
        patterns = await self.get_all_patterns(protocol_type)

        # BFT can use both BFT and CFT patterns
        if protocol_type.lower() == "bft":
            cft_patterns = await self.get_all_patterns("cft")
            patterns.extend(cft_patterns)

        # Filter
        if not_tested_in:
            patterns = [p for p in patterns if not_tested_in not in p.tested_repos]

        if bug_category:
            patterns = [p for p in patterns if p.bug_category == bug_category]

        return patterns

    async def update_pattern(self, pattern: BugPattern) -> None:
        """Update an existing pattern in place"""
        # Find existing file
        file_path = await self._find_pattern_file(
            pattern.pattern_id, pattern.protocol_type
        )

        if file_path is None:
            # Pattern doesn't exist, create new one
            await self.add_pattern(pattern)
            return

        # Update existing file
        with self._get_lock(file_path):
            with open(file_path, "w") as f:
                json.dump(pattern.model_dump(), f, indent=2)

    async def mark_tested(
        self, pattern_id: str, protocol_type: str, repo: str, found_bug: bool = False
    ) -> None:
        """Mark a pattern as tested in a repo"""
        pattern = await self.get_pattern(pattern_id, protocol_type)
        if pattern:
            if repo not in pattern.tested_repos:
                pattern.tested_repos.append(repo)
            if found_bug and repo not in pattern.confirmed_in_repos:
                pattern.confirmed_in_repos.append(repo)
            await self.update_pattern(pattern)
