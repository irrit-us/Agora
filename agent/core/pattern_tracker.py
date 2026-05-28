"""
Pattern Tracker - Tracks bug pattern usage per protocol.

This module manages which bug patterns have been viewed and used
when generating attack strategies for each protocol.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..mcp_servers.memory_server import MemoryServer

logger = logging.getLogger(__name__)

# Bug pattern context limits
MAX_PATTERN_CONTEXT = 6


class PatternTracker:
    """
    Tracks bug pattern usage per protocol.
    
    Manages:
    - Which patterns have been viewed (queried for details)
    - Which patterns have been used (strategy generated from them)
    - Pattern context generation for Strategy Agent prompts
    """
    
    def __init__(self, base_path: Path | None = None):
        """
        Initialize the pattern tracker.
        
        Args:
            base_path: Base path for test history data.
                       Defaults to agent/data/test_history.
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "test_history"
        self.base_path = Path(base_path)
    
    def _get_usage_path(self, protocol: str) -> Path:
        """Get the path to pattern_usage.json for a protocol."""
        return self.base_path / protocol / "pattern_usage.json"

    def load_usage(self, protocol: str) -> dict:
        """Load pattern usage data for a protocol."""
        file_path = self._get_usage_path(protocol)
        if not file_path.exists():
            return {"used_patterns": [], "viewed_patterns": []}
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"used_patterns": [], "viewed_patterns": []}

    def save_usage(self, protocol: str, data: dict) -> None:
        """Save pattern usage data for a protocol."""
        file_path = self._get_usage_path(protocol)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data["last_updated"] = datetime.now().isoformat()
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def mark_viewed(self, protocol: str, pattern_id: str) -> None:
        """Mark a pattern as viewed (queried for details)."""
        usage = self.load_usage(protocol)
        if pattern_id not in usage["viewed_patterns"]:
            usage["viewed_patterns"].append(pattern_id)
            self.save_usage(protocol, usage)

    def mark_used(self, protocol: str, pattern_id: str) -> None:
        """Mark a pattern as used (strategy generated from it)."""
        usage = self.load_usage(protocol)
        if pattern_id not in usage["used_patterns"]:
            usage["used_patterns"].append(pattern_id)
            self.save_usage(protocol, usage)

    def is_used(self, protocol: str, pattern_id: str) -> bool:
        """Check if a pattern has been used to generate a strategy."""
        usage = self.load_usage(protocol)
        return pattern_id in usage.get("used_patterns", [])
    
    async def get_pattern_context(
        self,
        memory: "MemoryServer",
        protocol_type: str,
        repo_key: str,
        rejected_pattern_ids: list[str],
    ) -> tuple[str, dict[str, str]]:
        """
        Get lightweight bug pattern context for Strategy Agent.

        Returns only pattern_id + category (no full details).
        Agent can use get_pattern_details tool to fetch full info.
        
        Args:
            memory: Memory server for accessing pattern memory.
            protocol_type: Protocol type (cft/bft).
            repo_key: Repository key for filtering tested patterns.
            rejected_pattern_ids: Pattern IDs to exclude.
            
        Returns:
            Tuple of (context_string, pattern_map).
            pattern_map maps pattern_id to protocol_type.
        """
        try:
            patterns = await memory.pattern_memory.get_patterns_for_protocol(
                protocol_type=protocol_type, not_tested_in=repo_key
            )
        except Exception as e:
            logger.warning(f"Failed to load bug patterns: {e}")
            return "## Confirmed Bug Patterns\n- (Failed to load patterns)", {}

        if rejected_pattern_ids:
            patterns = [p for p in patterns if p.pattern_id not in rejected_pattern_ids]

        if not patterns:
            return "## Confirmed Bug Patterns\n- None available for this repository.", {}

        pattern_map: dict[str, str] = {}
        lines = [
            "## Confirmed Bug Patterns (select at most one)",
            "",
            "Below are pattern IDs (which summarize the bug). Use `get_pattern_details(pattern_id)` to learn more about any pattern before deciding.",
            "",
        ]

        for idx, pattern in enumerate(patterns[:MAX_PATTERN_CONTEXT], start=1):
            pattern_map[pattern.pattern_id] = pattern.protocol_type
            # Lightweight format: just pattern_id + category tag
            category_tag = f"[{pattern.bug_category}]" if pattern.bug_category else ""
            lines.append(f"{idx}. {pattern.pattern_id} {category_tag}")

        lines.append("")
        lines.append("Use the pattern_id EXACTLY as shown when calling get_pattern_details or referencing in Inspiration Source.")

        return "\n".join(lines), pattern_map
    
    async def mark_tested(
        self,
        memory: "MemoryServer",
        pattern_id: str,
        pattern_protocol_type: str,
        repo_key: str,
        found_bug: bool,
    ) -> None:
        """Persist that a bug pattern has been tested in this repo."""
        try:
            await memory.pattern_memory.mark_tested(
                pattern_id, pattern_protocol_type, repo_key, found_bug=found_bug
            )
        except Exception as e:
            logger.warning(
                f"Failed to mark pattern tested ({pattern_id}, {pattern_protocol_type}): {e}"
            )
