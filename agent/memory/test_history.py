"""
Test History - records all test cases and their results.

This module provides persistent storage for test execution records and bug reports.

Directory structure:
    test_history/
    ├── <protocol>/
    │   ├── history.json        # Test records
    │   ├── bugs.json           # Confirmed bugs (summary)
    │   └── llm_logs/           # LLM interaction logs
    │       ├── session_<timestamp>.json
    │       └── archive/
    └── bugs/                   # Individual bug reports (detailed)
        └── <protocol>/
            ├── bug_001_<name>.json
            └── bug_002_<name>.json
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


# ============================================================
# Constants
# ============================================================

# Maximum length for scenario name in bug filenames
MAX_SCENARIO_NAME_LENGTH = 40

# Default model name when not specified
DEFAULT_MODEL_NAME = "unknown"


def sanitize_model_name(model: str) -> str:
    """
    Convert model name to a safe filename/directory format.

    Replaces special characters that are not allowed in filenames.

    Args:
        model: Model name (e.g., "anthropic/claude-sonnet-4").

    Returns:
        Safe filename string (e.g., "anthropic_claude-sonnet-4").
    """
    if not model:
        return DEFAULT_MODEL_NAME
    return model.replace("/", "_").replace(":", "_").replace(" ", "_")


class BugRecord(BaseModel):
    """A confirmed bug found in a repository"""

    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Protocol info
    protocol: str
    protocol_type: str  # cft or bft
    language: str

    # Model info
    model: str = ""  # LLM model used for bug discovery

    # Bug details
    bug_category: str  # safety, liveness, agreement
    fault_type: str
    scenario_name: str
    scenario_description: str

    # Root cause
    root_cause: str = ""
    code_location: str = ""  # file:line

    # Test info
    test_name: str
    test_file: str
    test_code: str = ""  # Full test code
    test_output: str = ""  # Test execution output

    # Attack scenario details
    vulnerability_hypothesis: str = ""
    target_component: str = ""
    preconditions: list[str] = []
    attack_steps: list[str] = []
    expected_bug_behavior: str = ""
    correct_behavior: str = ""

    # Validation info
    validation_reason: str = ""
    bug_report: str = ""  # Full bug report content

    # GitHub links
    issue_number: int | None = None
    issue_url: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None

    # Status
    status: str = "open"  # open, confirmed, fixed, wontfix


class TestRecord(BaseModel):
    """A record of a single test execution"""

    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Protocol info
    protocol: str
    protocol_type: str  # cft or bft
    language: str

    # Model info
    model: str = ""  # LLM model used for test generation

    # Test scenario
    scenario_name: str
    scenario_description: str
    fault_type: str
    bug_category: str
    steps: list[str]

    # Strategy source
    strategy_source: str  # pattern_memory, history_analysis, protocol_analysis

    # Generated test
    test_name: str
    test_file: str
    test_code: str

    # Execution result
    test_passed: bool
    test_output: str
    test_error: str = ""
    duration_ms: int = 0

    # Validation result (if applicable)
    validated: bool | None = None
    is_real_bug: bool | None = None
    is_realistic_scenario: bool | None = None
    validation_reason: str | None = None

    # Submission (if bug confirmed)
    issue_number: int | None = None
    pr_number: int | None = None


class TestHistory:
    """
    Records all test cases and results.
    Stored as JSON files per protocol and model in separate folders.

    Directory structure:
        test_history/
        ├── raft/
        │   ├── anthropic_claude-sonnet-4/
        │   │   ├── history.json    # Test records for this model
        │   │   └── bugs.json       # Confirmed bugs for this model
        │   ├── openai_gpt-4o/
        │   │   ├── history.json
        │   │   └── bugs.json
        │   └── ...
        ├── cometbft/
        │   └── ...
        └── ...
    """

    def __init__(self, base_path: Path | None = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "test_history"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_protocol_dir(self, protocol: str, model: str = "") -> Path:
        """Get directory for a protocol and model combination"""
        model_safe = sanitize_model_name(model)
        proto_dir = self.base_path / protocol / model_safe
        proto_dir.mkdir(parents=True, exist_ok=True)
        return proto_dir

    def _get_file_path(self, protocol: str, model: str = "") -> Path:
        """Get history file for a protocol and model"""
        return self._get_protocol_dir(protocol, model) / "history.json"

    def _get_bugs_file_path(self, protocol: str, model: str = "") -> Path:
        """Get bugs file for a protocol and model"""
        return self._get_protocol_dir(protocol, model) / "bugs.json"

    def _load_history(self, protocol: str, model: str = "") -> list[dict]:
        """Load history for a protocol and model"""
        file_path = self._get_file_path(protocol, model)
        if not file_path.exists():
            return []

        with open(file_path, "r") as f:
            return json.load(f)

    def _save_history(self, protocol: str, model: str, history: list[dict]):
        """Save history for a protocol and model"""
        file_path = self._get_file_path(protocol, model)
        with open(file_path, "w") as f:
            json.dump(history, f, indent=2)

    def _load_bugs(self, protocol: str, model: str = "") -> list[dict]:
        """Load bugs for a protocol and model"""
        file_path = self._get_bugs_file_path(protocol, model)
        if not file_path.exists():
            return []

        with open(file_path, "r") as f:
            return json.load(f)

    def _save_bugs(self, protocol: str, model: str, bugs: list[dict]):
        """Save bugs for a protocol and model"""
        file_path = self._get_bugs_file_path(protocol, model)
        with open(file_path, "w") as f:
            json.dump(bugs, f, indent=2)

    async def add_record(self, record: TestRecord) -> str:
        """Add a test record"""
        history = self._load_history(record.protocol, record.model)
        history.append(record.model_dump())
        self._save_history(record.protocol, record.model, history)
        return record.id

    async def get_records(
        self,
        protocol: str,
        model: str = "",
        limit: int | None = None,
        bug_only: bool = False,
    ) -> list[TestRecord]:
        """Get test records for a protocol and model"""
        history = self._load_history(protocol, model)

        if bug_only:
            history = [h for h in history if h.get("is_real_bug")]

        # Sort by timestamp descending
        history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if limit:
            history = history[:limit]

        return [TestRecord(**h) for h in history]

    async def get_all_records(self, limit: int | None = None) -> list[TestRecord]:
        """Get all test records across all protocols and models"""
        all_records = []

        # Iterate through protocol subdirectories
        for proto_dir in self.base_path.iterdir():
            if proto_dir.is_dir():
                # Iterate through model subdirectories
                for model_dir in proto_dir.iterdir():
                    if model_dir.is_dir():
                        history_file = model_dir / "history.json"
                        if history_file.exists():
                            with open(history_file, "r") as f:
                                records = json.load(f)
                                all_records.extend(records)

        # Sort by timestamp descending
        all_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if limit:
            all_records = all_records[:limit]

        return [TestRecord(**r) for r in all_records]

    async def get_stats(
        self, protocol: str | None = None, model: str = ""
    ) -> dict:
        """Get statistics"""
        if protocol:
            records = await self.get_records(protocol, model)
        else:
            records = await self.get_all_records()

        total = len(records)
        bugs_found = len([r for r in records if r.is_real_bug])
        false_positives = len([r for r in records if r.validated and not r.is_real_bug])
        unrealistic = len(
            [r for r in records if r.validated and not r.is_realistic_scenario]
        )

        return {
            "total_tests": total,
            "bugs_found": bugs_found,
            "false_positives": false_positives,
            "unrealistic_scenarios": unrealistic,
            "issues_created": len([r for r in records if r.issue_number]),
            "prs_created": len([r for r in records if r.pr_number]),
        }

    async def export_csv(
        self, output_path: Path, protocol: str | None = None, model: str = ""
    ):
        """Export history to CSV"""
        if protocol:
            records = await self.get_records(protocol, model)
        else:
            records = await self.get_all_records()

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "protocol",
                    "model",
                    "scenario_name",
                    "fault_type",
                    "bug_category",
                    "test_passed",
                    "is_real_bug",
                    "is_realistic_scenario",
                    "issue_number",
                    "pr_number",
                ]
            )

            for r in records:
                writer.writerow(
                    [
                        r.timestamp,
                        r.protocol,
                        r.model,
                        r.scenario_name,
                        r.fault_type,
                        r.bug_category,
                        r.test_passed,
                        r.is_real_bug,
                        r.is_realistic_scenario,
                        r.issue_number,
                        r.pr_number,
                    ]
                )

    # === Bug Management ===

    def _get_bugs_dir(self, protocol: str, model: str = "") -> Path:
        """Get bugs directory for a protocol and model.

        Structure: test_history/bugs/<protocol>/<model_safe_name>/
        """
        model_safe = sanitize_model_name(model)
        bugs_dir = self.base_path / "bugs" / protocol / model_safe
        bugs_dir.mkdir(parents=True, exist_ok=True)
        return bugs_dir

    def _generate_bug_filename(self, bug: BugRecord) -> str:
        """Generate a filename for a bug report"""
        # Extract bug number from ID or use timestamp
        bug_num = bug.id.split("_")[0] if "_" in bug.id else bug.id[:8]
        # Clean scenario name for filename
        safe_name = bug.scenario_name.lower()
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in safe_name)
        safe_name = safe_name[:MAX_SCENARIO_NAME_LENGTH]
        return f"bug_{bug_num}_{safe_name}.json"

    async def add_bug(self, bug: BugRecord) -> str:
        """Add a confirmed bug record"""
        # Add to summary bugs.json (in protocol/model directory)
        bugs = self._load_bugs(bug.protocol, bug.model)
        bugs.append(bug.model_dump())
        self._save_bugs(bug.protocol, bug.model, bugs)

        # Save detailed bug to individual file in bugs/ folder
        await self._save_bug_file(bug)

        return bug.id

    async def _save_bug_file(self, bug: BugRecord) -> Path:
        """Save bug to individual file in bugs/ folder"""
        bugs_dir = self._get_bugs_dir(bug.protocol, bug.model)
        filename = self._generate_bug_filename(bug)
        file_path = bugs_dir / filename

        # Create detailed bug report
        bug_data = bug.model_dump()
        bug_data["_meta"] = {
            "saved_at": datetime.now().isoformat(),
            "file_path": str(file_path),
        }

        with open(file_path, "w") as f:
            json.dump(bug_data, f, indent=2, ensure_ascii=False)

        return file_path

    def get_bug_files(self, protocol: str, model: str = "") -> list[Path]:
        """Get all bug files for a protocol and model"""
        bugs_dir = self._get_bugs_dir(protocol, model)
        return sorted(bugs_dir.glob("bug_*.json"))

    async def get_bug_from_file(
        self, protocol: str, bug_id: str, model: str = ""
    ) -> BugRecord | None:
        """Load a bug from its individual file"""
        bugs_dir = self._get_bugs_dir(protocol, model)

        # Try to find file by ID
        for file_path in bugs_dir.glob("bug_*.json"):
            if bug_id in file_path.name:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    data.pop("_meta", None)
                    return BugRecord(**data)

        return None

    async def get_bugs(self, protocol: str, model: str = "") -> list[BugRecord]:
        """Get all bugs for a protocol and model"""
        bugs = self._load_bugs(protocol, model)
        return [BugRecord(**b) for b in bugs]

    async def get_all_bugs(self) -> list[BugRecord]:
        """Get all bugs across all protocols and models"""
        all_bugs = []

        # Iterate through protocol subdirectories
        for proto_dir in self.base_path.iterdir():
            if proto_dir.is_dir():
                # Iterate through model subdirectories
                for model_dir in proto_dir.iterdir():
                    if model_dir.is_dir():
                        bugs_file = model_dir / "bugs.json"
                        if bugs_file.exists():
                            with open(bugs_file, "r") as f:
                                bugs = json.load(f)
                                all_bugs.extend(bugs)

        # Sort by timestamp descending
        all_bugs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return [BugRecord(**b) for b in all_bugs]

    async def get_bugs_by_category(self, category: str) -> list[BugRecord]:
        """Get bugs by category (safety/liveness/agreement)"""
        all_bugs = await self.get_all_bugs()
        return [b for b in all_bugs if b.bug_category == category]

    async def update_bug_status(
        self, protocol: str, bug_id: str, status: str, model: str = ""
    ) -> bool:
        """Update bug status (open/confirmed/fixed/wontfix)"""
        bugs = self._load_bugs(protocol, model)

        for bug in bugs:
            if bug.get("id") == bug_id:
                bug["status"] = status
                self._save_bugs(protocol, model, bugs)
                return True

        return False

    async def get_bug_summary(self) -> dict:
        """Get summary of bugs across all protocols"""
        all_bugs = await self.get_all_bugs()

        # Group by protocol
        by_protocol = {}
        for bug in all_bugs:
            proto = bug.protocol
            if proto not in by_protocol:
                by_protocol[proto] = []
            by_protocol[proto].append(bug)

        # Build summary
        summary = {
            "total_bugs": len(all_bugs),
            "by_category": {
                "safety": len([b for b in all_bugs if b.bug_category == "safety"]),
                "liveness": len([b for b in all_bugs if b.bug_category == "liveness"]),
                "agreement": len(
                    [b for b in all_bugs if b.bug_category == "agreement"]
                ),
            },
            "by_status": {
                "open": len([b for b in all_bugs if b.status == "open"]),
                "confirmed": len([b for b in all_bugs if b.status == "confirmed"]),
                "fixed": len([b for b in all_bugs if b.status == "fixed"]),
                "wontfix": len([b for b in all_bugs if b.status == "wontfix"]),
            },
            "by_protocol": {
                proto: {
                    "count": len(bugs),
                    "categories": {
                        "safety": len([b for b in bugs if b.bug_category == "safety"]),
                        "liveness": len(
                            [b for b in bugs if b.bug_category == "liveness"]
                        ),
                        "agreement": len(
                            [b for b in bugs if b.bug_category == "agreement"]
                        ),
                    },
                }
                for proto, bugs in by_protocol.items()
            },
        }

        return summary
