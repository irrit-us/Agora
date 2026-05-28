"""
Unit tests for memory modules: PatternMemory, TestHistory, RepoKnowledge.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.memory.pattern_memory import BugPattern, PatternMemory
from agent.memory.repo_knowledge import (
    CodingStyle,
    FaultInjectionMethod,
    HelperFunction,
    RepoKnowledge,
    RepoKnowledgeData,
    TestStructure,
)
from agent.memory.test_history import BugRecord, TestHistory, TestRecord

# ============================================================
# Pattern Memory Tests
# ============================================================


class TestPatternMemory:
    """Tests for PatternMemory module."""

    @pytest.mark.asyncio
    async def test_add_and_get_pattern(self, pattern_memory, sample_bug_pattern):
        """Test adding and retrieving a pattern."""
        pattern_id = await pattern_memory.add_pattern(sample_bug_pattern)

        assert pattern_id is not None
        # pattern_id is now the user-provided summary string
        assert pattern_id == sample_bug_pattern.pattern_id

        # Retrieve the pattern using pattern_id
        retrieved = await pattern_memory.get_pattern(pattern_id, "cft")
        assert retrieved is not None
        assert retrieved.fault_type == "network_partition"
        assert retrieved.bug_category == "safety"
        assert retrieved.discovered_in_repo == "etcd-raft"

    @pytest.mark.asyncio
    async def test_get_nonexistent_pattern(self, pattern_memory):
        """Test getting a pattern that doesn't exist."""
        result = await pattern_memory.get_pattern("nonexistent", "cft")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_patterns(
        self, pattern_memory, sample_bug_pattern, sample_bug_pattern_bft
    ):
        """Test getting all patterns."""
        await pattern_memory.add_pattern(sample_bug_pattern)
        await pattern_memory.add_pattern(sample_bug_pattern_bft)

        # Get all patterns
        all_patterns = await pattern_memory.get_all_patterns()
        assert len(all_patterns) == 2

        # Get CFT patterns only
        cft_patterns = await pattern_memory.get_all_patterns("cft")
        assert len(cft_patterns) == 1
        assert cft_patterns[0].protocol_type == "cft"

        # Get BFT patterns only
        bft_patterns = await pattern_memory.get_all_patterns("bft")
        assert len(bft_patterns) == 1
        assert bft_patterns[0].protocol_type == "bft"

    @pytest.mark.asyncio
    async def test_get_patterns_for_protocol(
        self, pattern_memory, sample_bug_pattern, sample_bug_pattern_bft
    ):
        """Test getting patterns for a specific protocol type."""
        await pattern_memory.add_pattern(sample_bug_pattern)
        await pattern_memory.add_pattern(sample_bug_pattern_bft)

        # CFT should only get CFT patterns
        cft_patterns = await pattern_memory.get_patterns_for_protocol("cft")
        assert len(cft_patterns) == 1

        # BFT should get both BFT and CFT patterns
        bft_patterns = await pattern_memory.get_patterns_for_protocol("bft")
        assert len(bft_patterns) == 2

    @pytest.mark.asyncio
    async def test_filter_not_tested_in(self, pattern_memory, sample_bug_pattern):
        """Test filtering patterns not tested in a specific repo."""
        sample_bug_pattern.tested_repos = ["repo-a", "repo-b"]
        await pattern_memory.add_pattern(sample_bug_pattern)

        # Should not return pattern tested in repo-a
        patterns = await pattern_memory.get_patterns_for_protocol(
            "cft", not_tested_in="repo-a"
        )
        assert len(patterns) == 0

        # Should return pattern not tested in repo-c
        patterns = await pattern_memory.get_patterns_for_protocol(
            "cft", not_tested_in="repo-c"
        )
        assert len(patterns) == 1

    @pytest.mark.asyncio
    async def test_filter_by_bug_category(self, pattern_memory):
        """Test filtering patterns by bug category."""
        safety_pattern = BugPattern(
            pattern_id="Crash fault causes safety violation",
            protocol_type="cft",
            fault_type="crash",
            bug_category="safety",
            trigger_condition="test",
            description="test",
            test_template="",
        )
        liveness_pattern = BugPattern(
            pattern_id="Network fault causes liveness violation",
            protocol_type="cft",
            fault_type="network",
            bug_category="liveness",
            trigger_condition="test",
            description="test",
            test_template="",
        )

        await pattern_memory.add_pattern(safety_pattern)
        await pattern_memory.add_pattern(liveness_pattern)

        safety_patterns = await pattern_memory.get_patterns_for_protocol(
            "cft", bug_category="safety"
        )
        assert len(safety_patterns) == 1
        assert safety_patterns[0].bug_category == "safety"

    @pytest.mark.asyncio
    async def test_mark_tested(self, pattern_memory, sample_bug_pattern):
        """Test marking a pattern as tested."""
        pattern_id = await pattern_memory.add_pattern(sample_bug_pattern)

        await pattern_memory.mark_tested(pattern_id, "cft", "new-repo", found_bug=True)

        pattern = await pattern_memory.get_pattern(pattern_id, "cft")
        assert "new-repo" in pattern.tested_repos
        assert "new-repo" in pattern.confirmed_in_repos

    @pytest.mark.asyncio
    async def test_update_pattern(self, pattern_memory, sample_bug_pattern):
        """Test updating a pattern."""
        pattern_id = await pattern_memory.add_pattern(sample_bug_pattern)

        # Modify and update
        sample_bug_pattern.description = "Updated description"
        await pattern_memory.update_pattern(sample_bug_pattern)

        pattern = await pattern_memory.get_pattern(pattern_id, "cft")
        assert pattern.description == "Updated description"

    @pytest.mark.asyncio
    async def test_file_persistence(self, pattern_memory, sample_bug_pattern):
        """Test that patterns are persisted to files."""
        pattern_id = await pattern_memory.add_pattern(sample_bug_pattern)

        # Check file exists (file name is a slug from pattern_id)
        # Find the persisted file by checking what files exist
        files = list(pattern_memory.cft_path.glob("*.json"))
        assert len(files) == 1
        file_path = files[0]

        # Check content
        with open(file_path) as f:
            data = json.load(f)
        assert data["fault_type"] == "network_partition"
        assert data["pattern_id"] == pattern_id


# ============================================================
# Test History Tests
# ============================================================


class TestTestHistory:
    """Tests for TestHistory module."""

    @pytest.mark.asyncio
    async def test_add_record(self, test_history, sample_test_record):
        """Test adding a test record."""
        record_id = await test_history.add_record(sample_test_record)

        assert record_id == "test-001"

    @pytest.mark.asyncio
    async def test_get_records(self, test_history, sample_test_record):
        """Test getting records for a protocol."""
        await test_history.add_record(sample_test_record)

        records = await test_history.get_records("test-raft")
        assert len(records) == 1
        assert records[0].scenario_name == "StaleLeaderTest"

    @pytest.mark.asyncio
    async def test_get_records_with_limit(self, test_history):
        """Test getting records with limit."""
        for i in range(5):
            record = TestRecord(
                id=f"test-{i:03d}",
                protocol="test-raft",
                protocol_type="cft",
                language="go",
                scenario_name=f"Test{i}",
                scenario_description="test",
                fault_type="crash",
                bug_category="safety",
                steps=["step1"],
                strategy_source="test",
                test_name=f"Test{i}",
                test_file="test.go",
                test_code="",
                test_passed=True,
                test_output="",
            )
            await test_history.add_record(record)

        records = await test_history.get_records("test-raft", limit=3)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, test_history):
        """Test getting statistics."""
        # Add some records
        passed = TestRecord(
            id="pass-001",
            protocol="test-raft",
            protocol_type="cft",
            language="go",
            scenario_name="PassingTest",
            scenario_description="test",
            fault_type="crash",
            bug_category="safety",
            steps=["step1"],
            strategy_source="test",
            test_name="TestPass",
            test_file="test.go",
            test_code="",
            test_passed=True,
            test_output="",
        )
        bug_found = TestRecord(
            id="bug-001",
            protocol="test-raft",
            protocol_type="cft",
            language="go",
            scenario_name="BugTest",
            scenario_description="test",
            fault_type="crash",
            bug_category="safety",
            steps=["step1"],
            strategy_source="test",
            test_name="TestBug",
            test_file="test.go",
            test_code="",
            test_passed=False,
            test_output="FAIL",
            validated=True,
            is_real_bug=True,
        )
        false_positive = TestRecord(
            id="fp-001",
            protocol="test-raft",
            protocol_type="cft",
            language="go",
            scenario_name="FPTest",
            scenario_description="test",
            fault_type="crash",
            bug_category="safety",
            steps=["step1"],
            strategy_source="test",
            test_name="TestFP",
            test_file="test.go",
            test_code="",
            test_passed=False,
            test_output="FAIL",
            validated=True,
            is_real_bug=False,
        )

        await test_history.add_record(passed)
        await test_history.add_record(bug_found)
        await test_history.add_record(false_positive)

        stats = await test_history.get_stats("test-raft")
        assert stats["total_tests"] == 3
        assert stats["bugs_found"] == 1
        assert stats["false_positives"] == 1

    @pytest.mark.asyncio
    async def test_add_bug(self, test_history, sample_bug_record):
        """Test adding a bug record."""
        bug_id = await test_history.add_bug(sample_bug_record)

        assert bug_id == "bug-001"

    @pytest.mark.asyncio
    async def test_get_bugs(self, test_history, sample_bug_record):
        """Test getting bugs for a protocol."""
        await test_history.add_bug(sample_bug_record)

        bugs = await test_history.get_bugs("test-raft")
        assert len(bugs) == 1
        assert bugs[0].scenario_name == "StaleLeaderViolation"

    @pytest.mark.asyncio
    async def test_get_all_bugs(self, test_history):
        """Test getting all bugs across protocols."""
        bug1 = BugRecord(
            id="bug-001",
            protocol="proto-a",
            protocol_type="cft",
            language="go",
            bug_category="safety",
            fault_type="crash",
            scenario_name="Bug1",
            scenario_description="test",
            test_name="Test1",
            test_file="test.go",
        )
        bug2 = BugRecord(
            id="bug-002",
            protocol="proto-b",
            protocol_type="bft",
            language="rust",
            bug_category="liveness",
            fault_type="network",
            scenario_name="Bug2",
            scenario_description="test",
            test_name="Test2",
            test_file="test.rs",
        )

        await test_history.add_bug(bug1)
        await test_history.add_bug(bug2)

        all_bugs = await test_history.get_all_bugs()
        assert len(all_bugs) == 2

    @pytest.mark.asyncio
    async def test_update_bug_status(self, test_history, sample_bug_record):
        """Test updating bug status."""
        await test_history.add_bug(sample_bug_record)

        success = await test_history.update_bug_status("test-raft", "bug-001", "fixed")
        assert success

        bugs = await test_history.get_bugs("test-raft")
        assert bugs[0].status == "fixed"

    @pytest.mark.asyncio
    async def test_get_bug_summary(self, test_history):
        """Test getting bug summary."""
        safety_bug = BugRecord(
            id="bug-001",
            protocol="raft",
            protocol_type="cft",
            language="go",
            bug_category="safety",
            fault_type="crash",
            scenario_name="SafetyBug",
            scenario_description="test",
            test_name="Test1",
            test_file="test.go",
            status="open",
        )
        liveness_bug = BugRecord(
            id="bug-002",
            protocol="raft",
            protocol_type="cft",
            language="go",
            bug_category="liveness",
            fault_type="network",
            scenario_name="LivenessBug",
            scenario_description="test",
            test_name="Test2",
            test_file="test.go",
            status="confirmed",
        )

        await test_history.add_bug(safety_bug)
        await test_history.add_bug(liveness_bug)

        summary = await test_history.get_bug_summary()
        assert summary["total_bugs"] == 2
        assert summary["by_category"]["safety"] == 1
        assert summary["by_category"]["liveness"] == 1
        assert summary["by_status"]["open"] == 1
        assert summary["by_status"]["confirmed"] == 1

    @pytest.mark.asyncio
    async def test_export_csv(self, test_history, sample_test_record, temp_dir):
        """Test exporting to CSV."""
        await test_history.add_record(sample_test_record)

        output_path = temp_dir / "export.csv"
        await test_history.export_csv(output_path, "test-raft")

        assert output_path.exists()
        content = output_path.read_text()
        assert "test-raft" in content
        assert "StaleLeaderTest" in content


# ============================================================
# Repo Knowledge Tests
# ============================================================


class TestRepoKnowledge:
    """Tests for RepoKnowledge module."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, repo_knowledge):
        """Test saving and retrieving repo knowledge."""
        knowledge = RepoKnowledgeData(
            repo="test-raft",
            language="go",
            package_name="raft",
            module_path="github.com/test/raft",
            test_structure=TestStructure(
                test_dirs=["raft", "transport"],
                test_pattern="*_test.go",
                main_test_files=["raft_test.go"],
            ),
            coding_style=CodingStyle(
                naming_convention="TestXxx", assertion_style="t.Fatalf"
            ),
        )

        await repo_knowledge.save(knowledge)

        retrieved = await repo_knowledge.get("test-raft")
        assert retrieved is not None
        assert retrieved.language == "go"
        assert retrieved.package_name == "raft"
        assert "raft" in retrieved.test_structure.test_dirs

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repo_knowledge):
        """Test getting knowledge for non-existent repo."""
        result = await repo_knowledge.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_helpers(self, repo_knowledge):
        """Test updating helper functions."""
        knowledge = RepoKnowledgeData(repo="test-raft", language="go")
        await repo_knowledge.save(knowledge)

        helpers = [
            HelperFunction(
                name="newTestCluster",
                file="test_util.go",
                purpose="Create test cluster",
            ),
            HelperFunction(
                name="waitForLeader",
                file="test_util.go",
                purpose="Wait for leader election",
            ),
        ]

        await repo_knowledge.update_helpers("test-raft", helpers)

        updated = await repo_knowledge.get("test-raft")
        assert len(updated.helper_functions) == 2
        assert updated.helper_functions[0].name == "newTestCluster"

    @pytest.mark.asyncio
    async def test_update_fault_injection(self, repo_knowledge):
        """Test updating fault injection methods."""
        knowledge = RepoKnowledgeData(repo="test-raft", language="go")
        await repo_knowledge.save(knowledge)

        methods = [
            FaultInjectionMethod(
                fault_type="network_partition",
                location="transport.go:partitionNode",
                usage="transport.Partition(nodeID)",
            )
        ]

        await repo_knowledge.update_fault_injection("test-raft", methods)

        updated = await repo_knowledge.get("test-raft")
        assert len(updated.fault_injection) == 1
        assert updated.fault_injection[0].fault_type == "network_partition"

    @pytest.mark.asyncio
    async def test_add_note(self, repo_knowledge):
        """Test adding notes."""
        knowledge = RepoKnowledgeData(repo="test-raft", language="go")
        await repo_knowledge.save(knowledge)

        await repo_knowledge.add_note("test-raft", "Found useful test patterns")

        updated = await repo_knowledge.get("test-raft")
        assert len(updated.notes) == 1
        assert "useful test patterns" in updated.notes[0]

    @pytest.mark.asyncio
    async def test_needs_update(self, repo_knowledge):
        """Test checking if update is needed."""
        # Non-existent repo needs update
        needs = await repo_knowledge.needs_update("nonexistent", {})
        assert needs

        # Existing repo with same hashes doesn't need update
        knowledge = RepoKnowledgeData(
            repo="test-raft",
            language="go",
            file_hashes={"file1.go": "hash1", "file2.go": "hash2"},
        )
        await repo_knowledge.save(knowledge)

        needs = await repo_knowledge.needs_update(
            "test-raft", {"file1.go": "hash1", "file2.go": "hash2"}
        )
        assert not needs

        # Changed file needs update
        needs = await repo_knowledge.needs_update(
            "test-raft", {"file1.go": "hash1", "file2.go": "new_hash"}
        )
        assert needs

    @pytest.mark.asyncio
    async def test_file_path_sanitization(self, repo_knowledge):
        """Test that repo names with special chars are handled."""
        knowledge = RepoKnowledgeData(repo="github.com/org/repo", language="go")
        await repo_knowledge.save(knowledge)

        # Should create file with sanitized name
        file_path = repo_knowledge._get_file_path("github.com/org/repo")
        assert "/" not in file_path.name
        assert "\\" not in file_path.name


# ============================================================
# Concurrency Tests
# ============================================================


class TestConcurrency:
    """Tests for concurrent access to memory modules."""

    @pytest.mark.asyncio
    async def test_concurrent_pattern_writes(self, pattern_memory):
        """Test concurrent writes to pattern memory."""

        async def add_pattern(i):
            pattern = BugPattern(
                pattern_id=f"Concurrent test pattern {i}",
                protocol_type="cft",
                fault_type=f"fault_{i}",
                bug_category="safety",
                trigger_condition=f"trigger_{i}",
                description=f"description_{i}",
                test_template="",
            )
            return await pattern_memory.add_pattern(pattern)

        # Add patterns concurrently
        tasks = [add_pattern(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed with unique IDs
        assert len(set(results)) == 10

        # All patterns should be retrievable
        all_patterns = await pattern_memory.get_all_patterns("cft")
        assert len(all_patterns) == 10
