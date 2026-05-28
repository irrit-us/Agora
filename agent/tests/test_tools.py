"""
Tests for MemoryTools MCP tool implementations.
Tests all tool methods that will be exposed to Claude Agent SDK.
"""

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

from agent.mcp_servers.memory_server import (
    MemoryTools,
    create_memory_server,
    get_memory_tools_list,
)
from agent.memory.pattern_memory import BugPattern
from agent.memory.repo_knowledge import RepoKnowledgeData
from agent.memory.test_history import TestRecord

# ============================================================
# Memory Server Creation Tests
# ============================================================


class TestMemoryServerCreation:
    """Tests for MemoryServer and create_memory_server."""

    def test_create_memory_server(self, temp_memory_dir):
        """Test creating a memory server."""
        server = create_memory_server(base_path=temp_memory_dir)

        assert server is not None
        assert server.pattern_memory is not None
        assert server.repo_knowledge is not None
        assert server.test_history is not None

    def test_memory_tools_initialization(self, memory_server):
        """Test MemoryTools initialization."""
        tools = MemoryTools(memory_server)

        assert tools.memory is memory_server

    def test_get_memory_tools_list(self, memory_tools):
        """Test getting the tools list."""
        tools_list = get_memory_tools_list(memory_tools)

        assert len(tools_list) > 0

        # Check expected tools exist
        tool_names = {t["name"] for t in tools_list}
        assert "pattern_get" in tool_names
        assert "pattern_add" in tool_names
        assert "repo_knowledge_get" in tool_names
        assert "test_history_add" in tool_names


# ============================================================
# Pattern Memory Tool Tests
# ============================================================


class TestPatternMemoryTools:
    """Tests for pattern memory tools."""

    @pytest.mark.asyncio
    async def test_pattern_get_empty(self, memory_tools):
        """Test getting patterns when none exist."""
        result = await memory_tools.pattern_get({"protocol_type": "cft"})

        assert "content" in result
        assert len(result["content"]) > 0
        assert "0 patterns" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_pattern_add(self, memory_tools):
        """Test adding a pattern."""
        result = await memory_tools.pattern_add(
            {
                "pattern_id": "Leader isolation causes safety violation",
                "protocol_type": "cft",
                "fault_type": "network_partition",
                "bug_category": "safety",
                "trigger_condition": "Leader isolation",
                "description": "Test pattern description",
                "discovered_in_repo": "test-repo",
            }
        )

        assert "content" in result
        assert "Successfully added" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_pattern_get_after_add(self, memory_tools):
        """Test getting patterns after adding one."""
        # Add a pattern
        await memory_tools.pattern_add(
            {
                "pattern_id": "Node crash during commit causes liveness issue",
                "protocol_type": "cft",
                "fault_type": "crash",
                "bug_category": "liveness",
                "trigger_condition": "Node crash during commit",
                "description": "Node crash pattern",
            }
        )

        # Get patterns
        result = await memory_tools.pattern_get({"protocol_type": "cft"})

        assert "1 pattern" in result["content"][0]["text"]
        assert "crash" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_pattern_get_with_filters(self, memory_tools):
        """Test getting patterns with filters."""
        # Add patterns
        await memory_tools.pattern_add(
            {
                "pattern_id": "Crash causes safety violation",
                "protocol_type": "cft",
                "fault_type": "crash",
                "bug_category": "safety",
                "trigger_condition": "test",
                "description": "Safety pattern",
            }
        )
        await memory_tools.pattern_add(
            {
                "pattern_id": "Network fault causes liveness issue",
                "protocol_type": "cft",
                "fault_type": "network",
                "bug_category": "liveness",
                "trigger_condition": "test",
                "description": "Liveness pattern",
            }
        )

        # Filter by category
        result = await memory_tools.pattern_get(
            {"protocol_type": "cft", "bug_category": "safety"}
        )

        assert "1 pattern" in result["content"][0]["text"]
        assert "safety" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_pattern_search(self, memory_tools):
        """Test searching patterns."""
        # Add patterns
        await memory_tools.pattern_add(
            {
                "pattern_id": "Byzantine leader causes safety attack",
                "protocol_type": "bft",
                "fault_type": "byzantine",
                "bug_category": "safety",
                "trigger_condition": "Byzantine leader",
                "description": "Byzantine attack",
            }
        )

        result = await memory_tools.pattern_search(
            {"protocol_type": "bft", "fault_type": "byzantine"}
        )

        assert "content" in result
        assert "byzantine" in result["content"][0]["text"].lower()


# ============================================================
# Repo Knowledge Tool Tests
# ============================================================


class TestRepoKnowledgeTools:
    """Tests for repo knowledge tools."""

    @pytest.mark.asyncio
    async def test_repo_knowledge_get_not_found(self, memory_tools):
        """Test getting knowledge for non-existent repo."""
        result = await memory_tools.repo_knowledge_get({"repo": "nonexistent"})

        assert "No cached knowledge" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_repo_knowledge_save_and_get(self, memory_tools):
        """Test saving and getting repo knowledge."""
        # Save knowledge
        await memory_tools.repo_knowledge_save(
            {
                "repo": "test-raft",
                "language": "go",
                "package_name": "raft",
                "test_structure": {
                    "test_dirs": ["raft", "transport"],
                    "test_pattern": "*_test.go",
                    "main_test_files": ["raft_test.go"],
                },
                "coding_style": {
                    "naming_convention": "TestXxx",
                    "assertion_style": "t.Fatalf",
                },
            }
        )

        # Get knowledge
        result = await memory_tools.repo_knowledge_get({"repo": "test-raft"})

        content = result["content"][0]["text"]
        assert "test-raft" in content or "raft" in content
        assert "go" in content.lower()

    @pytest.mark.asyncio
    async def test_repo_knowledge_update(self, memory_tools):
        """Test updating repo knowledge."""
        # Initial save
        await memory_tools.repo_knowledge_save(
            {"repo": "update-test", "language": "rust"}
        )

        # Update
        await memory_tools.repo_knowledge_save(
            {"repo": "update-test", "language": "rust", "package_name": "consensus"}
        )

        result = await memory_tools.repo_knowledge_get({"repo": "update-test"})

        assert "consensus" in result["content"][0]["text"]


# ============================================================
# Test History Tool Tests
# ============================================================


class TestTestHistoryTools:
    """Tests for test history tools."""

    @pytest.mark.asyncio
    async def test_test_history_add(self, memory_tools):
        """Test adding a test record."""
        result = await memory_tools.test_history_add(
            {
                "protocol": "test-raft",
                "protocol_type": "cft",
                "language": "go",
                "scenario_name": "TestScenario",
                "scenario_description": "Test description",
                "fault_type": "crash",
                "bug_category": "safety",
                "steps": ["step1", "step2"],
                "strategy_source": "pattern_memory",
                "test_name": "TestExample",
                "test_file": "example_test.go",
                "test_code": "func TestExample(t *testing.T) {}",
                "test_passed": True,
                "test_output": "PASS",
            }
        )

        assert "Successfully added" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_test_history_add_bug_found(self, memory_tools):
        """Test adding a test record with bug found."""
        result = await memory_tools.test_history_add(
            {
                "protocol": "test-raft",
                "protocol_type": "cft",
                "language": "go",
                "scenario_name": "BugScenario",
                "scenario_description": "Found a bug",
                "fault_type": "network",
                "bug_category": "safety",
                "steps": ["partition", "crash"],
                "strategy_source": "analysis",
                "test_name": "TestBug",
                "test_file": "bug_test.go",
                "test_code": "func TestBug(t *testing.T) {}",
                "test_passed": False,
                "test_output": "FAIL",
                "validated": True,
                "is_real_bug": True,
                "is_realistic_scenario": True,
                "validation_reason": "Confirmed safety violation",
            }
        )

        assert "Successfully added" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_test_history_get_stats(self, memory_tools):
        """Test getting test statistics."""
        # Add some records first
        await memory_tools.test_history_add(
            {
                "protocol": "stats-test",
                "protocol_type": "cft",
                "language": "go",
                "scenario_name": "Test1",
                "test_name": "Test1",
                "test_file": "test.go",
                "test_code": "",
                "test_passed": True,
                "test_output": "PASS",
            }
        )
        await memory_tools.test_history_add(
            {
                "protocol": "stats-test",
                "protocol_type": "cft",
                "language": "go",
                "scenario_name": "Test2",
                "test_name": "Test2",
                "test_file": "test.go",
                "test_code": "",
                "test_passed": False,
                "test_output": "FAIL",
                "validated": True,
                "is_real_bug": True,
            }
        )

        result = await memory_tools.test_history_get_stats({"protocol": "stats-test"})

        content = result["content"][0]["text"]
        assert "total" in content.lower()
        assert "bugs" in content.lower()

    @pytest.mark.asyncio
    async def test_test_history_get_bugs_empty(self, memory_tools):
        """Test getting bugs when none exist."""
        result = await memory_tools.test_history_get_bugs(
            {"protocol": "empty-protocol"}
        )

        assert "0 bugs" in result["content"][0]["text"]


# ============================================================
# Tool Response Format Tests
# ============================================================


class TestToolResponseFormat:
    """Tests that tool responses follow MCP format."""

    @pytest.mark.asyncio
    async def test_response_has_content_array(self, memory_tools):
        """Test that responses have content array."""
        result = await memory_tools.pattern_get({"protocol_type": "cft"})

        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_response_content_has_type(self, memory_tools):
        """Test that content items have type."""
        result = await memory_tools.pattern_get({"protocol_type": "cft"})

        for item in result["content"]:
            assert "type" in item
            assert item["type"] == "text"

    @pytest.mark.asyncio
    async def test_response_content_has_text(self, memory_tools):
        """Test that content items have text."""
        result = await memory_tools.pattern_get({"protocol_type": "cft"})

        for item in result["content"]:
            assert "text" in item
            assert isinstance(item["text"], str)


# ============================================================
# Tool Error Handling Tests
# ============================================================


class TestToolErrorHandling:
    """Tests for tool error handling."""

    @pytest.mark.asyncio
    async def test_pattern_get_invalid_type(self, memory_tools):
        """Test pattern_get with invalid protocol type."""
        # Should handle gracefully
        try:
            result = await memory_tools.pattern_get({"protocol_type": "invalid"})
            # Should either return empty or raise
        except ValueError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_repo_knowledge_save_minimal(self, memory_tools):
        """Test repo_knowledge_save with minimal args."""
        result = await memory_tools.repo_knowledge_save(
            {"repo": "minimal-repo", "language": "go"}
        )

        assert "Successfully saved" in result["content"][0]["text"]


# ============================================================
# Integration with Claude Agent SDK Format
# ============================================================


class TestClaudeAgentSDKFormat:
    """Tests for Claude Agent SDK compatibility."""

    def test_tools_list_has_required_fields(self, memory_tools):
        """Test that tools list has all required fields."""
        tools_list = get_memory_tools_list(memory_tools)

        for tool in tools_list:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "handler" in tool

    def test_tools_list_handlers_are_callable(self, memory_tools):
        """Test that tool handlers are callable."""
        tools_list = get_memory_tools_list(memory_tools)

        for tool in tools_list:
            assert callable(tool["handler"])

    def test_tools_list_parameters_are_dicts(self, memory_tools):
        """Test that tool parameters are proper dicts."""
        tools_list = get_memory_tools_list(memory_tools)

        for tool in tools_list:
            assert isinstance(tool["parameters"], dict)
            for param_name, param_def in tool["parameters"].items():
                assert "type" in param_def
                assert "description" in param_def
