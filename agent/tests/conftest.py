"""
Pytest configuration and fixtures for the Consensus Bug Hunter test suite.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path for imports (consensus-test directory)
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

# Import using agent package
from agent.config.settings import ProtocolConfig, Settings
from agent.mcp_servers.memory_server import (
    MemoryServer,
    MemoryTools,
    create_memory_server,
)
from agent.memory.pattern_memory import BugPattern, PatternMemory
from agent.memory.repo_knowledge import RepoKnowledge
from agent.memory.test_history import BugRecord, TestHistory, TestRecord

# ============================================================
# Event Loop Configuration
# ============================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Directory Fixtures
# ============================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def temp_memory_dir(tmp_path):
    """Create a temporary directory structure for memory storage."""
    memory_dir = tmp_path / "memory"
    (memory_dir / "data" / "pattern_memory" / "cft").mkdir(parents=True)
    (memory_dir / "data" / "pattern_memory" / "bft").mkdir(parents=True)
    (memory_dir / "data" / "repo_knowledge").mkdir(parents=True)
    (memory_dir / "data" / "test_history").mkdir(parents=True)
    return memory_dir


@pytest.fixture
def temp_repo_dir(tmp_path):
    """Create a temporary directory mimicking a protocol repository."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Create some mock test files
    (repo_dir / "raft.go").write_text("package raft\n\nfunc main() {}\n")
    (repo_dir / "raft_test.go").write_text(
        'package raft\n\nimport "testing"\n\nfunc TestExample(t *testing.T) {}\n'
    )

    return repo_dir


# ============================================================
# Settings Fixtures
# ============================================================


@pytest.fixture
def mock_settings(temp_memory_dir):
    """Create mock settings for testing."""
    return Settings(
        openrouter_api_key="test-api-key-not-real",
        openrouter_base_url="https://openrouter.ai/api/v1",
        llm_model="anthropic/claude-sonnet-4",
        max_thinking_tokens=16000,
        enable_prompt_caching=True,
        max_reflection_retries=3,
        max_turns=5,
        max_budget_usd=1.0,
        test_timeout=60,
        embedding_model="openai/text-embedding-3-small",
        protocols={},
    )


@pytest.fixture
def mock_protocol_config(temp_repo_dir):
    """Create a mock protocol configuration."""
    return ProtocolConfig(
        name="test-raft",
        path=str(temp_repo_dir),
        type="cft",
        language="go",
        fault_tolerance="(n-1)/2",
        description="Test Raft implementation",
        test_pattern="*_test.go",
        test_command="go test -v -run {test_name} ./...",
    )


# ============================================================
# Memory Module Fixtures
# ============================================================


@pytest.fixture
def pattern_memory(temp_memory_dir):
    """Create a PatternMemory instance with temp directory."""
    return PatternMemory(temp_memory_dir / "pattern_memory")


@pytest.fixture
def test_history(temp_memory_dir):
    """Create a TestHistory instance with temp directory."""
    return TestHistory(temp_memory_dir / "test_history")


@pytest.fixture
def repo_knowledge(temp_memory_dir):
    """Create a RepoKnowledge instance with temp directory."""
    return RepoKnowledge(temp_memory_dir / "repo_knowledge")


@pytest.fixture
def memory_server(temp_memory_dir):
    """Create a MemoryServer with all components initialized."""
    return create_memory_server(
        base_path=temp_memory_dir,
        api_key=None,  # No API key - skip embedding
        embedding_model="openai/text-embedding-3-small",
    )


@pytest.fixture
def memory_tools(memory_server):
    """Create MemoryTools instance."""
    return MemoryTools(memory_server)


# ============================================================
# Sample Data Fixtures
# ============================================================


@pytest.fixture
def sample_bug_pattern():
    """Create a sample BugPattern for testing."""
    return BugPattern(
        pattern_id="Leader partition during commit causes data loss",
        protocol_type="cft",
        fault_type="network_partition",
        bug_category="safety",
        trigger_condition="Leader isolation during commit",
        description="When a leader is partitioned after sending AppendEntries but before receiving acknowledgments, committed entries may be lost.",
        test_template="Create 5-node cluster, partition leader, verify no data loss",
        discovered_in_repo="etcd-raft",
    )


@pytest.fixture
def sample_bug_pattern_bft():
    """Create a sample BFT BugPattern for testing."""
    return BugPattern(
        pattern_id="Byzantine leader equivocation causes consensus failure",
        protocol_type="bft",
        fault_type="byzantine_equivocation",
        bug_category="safety",
        trigger_condition="Byzantine leader sends conflicting messages",
        description="Byzantine leader can send different pre-prepare messages to different replicas.",
        test_template="Create 4-node cluster with Byzantine leader",
        discovered_in_repo="tendermint",
    )


@pytest.fixture
def sample_test_record():
    """Create a sample TestRecord for testing."""
    return TestRecord(
        id="test-001",
        protocol="test-raft",
        protocol_type="cft",
        language="go",
        scenario_name="StaleLeaderTest",
        scenario_description="Test stale leader cannot become leader",
        fault_type="network_partition",
        bug_category="safety",
        steps=["Partition node", "Crash majority", "Heal partition"],
        strategy_source="pattern_memory",
        test_name="TestStaleLeader",
        test_file="stale_leader_test.go",
        test_code="func TestStaleLeader(t *testing.T) {}",
        test_passed=False,
        test_output="--- FAIL: TestStaleLeader",
    )


@pytest.fixture
def sample_bug_record():
    """Create a sample BugRecord for testing."""
    return BugRecord(
        id="bug-001",
        protocol="test-raft",
        protocol_type="cft",
        language="go",
        bug_category="safety",
        fault_type="network_partition",
        scenario_name="StaleLeaderViolation",
        scenario_description="Stale node can become leader",
        root_cause="Missing log up-to-dateness check",
        code_location="vote_handler.go:145",
        test_name="TestStaleLeader",
        test_file="stale_leader_test.go",
        status="open",
    )


# ============================================================
# Baseline Agent Fixtures
# ============================================================


@pytest.fixture
def baseline_repo(tmp_path):
    """
    Create a temporary repository for baseline agent testing.

    This creates a realistic repo structure with:
    - Main source files (raft.go, log.go, storage.go)
    - Test files
    - Subdirectories
    - Code with various patterns to search
    """
    # Main implementation file
    (tmp_path / "raft.go").write_text(
        '''package raft

import "sync"

type Raft struct {
    mu          sync.Mutex
    currentTerm int
    votedFor    int
    log         []LogEntry
}

func (r *Raft) RequestVote(args *RequestVoteArgs, reply *RequestVoteReply) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if args.Term < r.currentTerm {
        reply.VoteGranted = false
        return
    }
    
    if r.votedFor == -1 || r.votedFor == args.CandidateId {
        r.votedFor = args.CandidateId
        reply.VoteGranted = true
    }
}
'''
    )

    # Log management
    (tmp_path / "log.go").write_text(
        '''package raft

type LogEntry struct {
    Term    int
    Command interface{}
}

func (r *Raft) appendLog(entries []LogEntry) {
    r.log = append(r.log, entries...)
}
'''
    )

    # Storage interface
    (tmp_path / "storage.go").write_text(
        '''package raft

type Storage interface {
    SaveState(term int, votedFor int) error
    LoadState() (term int, votedFor int, err error)
}
'''
    )

    # Test file
    (tmp_path / "raft_test.go").write_text(
        '''package raft

import "testing"

func TestRequestVote(t *testing.T) {
    r := &Raft{currentTerm: 1, votedFor: -1}
    // Test implementation
}
'''
    )

    # Subdirectory
    (tmp_path / "internal").mkdir()
    (tmp_path / "internal" / "util.go").write_text(
        '''package internal

func min(a, b int) int {
    if a < b {
        return a
    }
    return b
}
'''
    )

    return tmp_path


@pytest.fixture
def baseline_agent(baseline_repo):
    """Create a BaselineReActAgent for testing."""
    from agent.baseline.react_agent import BaselineReActAgent

    return BaselineReActAgent(
        model="anthropic/claude-sonnet-4",
        api_key="test-api-key-not-real",
        base_url="https://openrouter.ai/api/v1",
        repo_path=baseline_repo,
        max_iterations=10,
        max_tokens=16000,
        timeout=30.0,
    )


@pytest.fixture
def baseline_tools(baseline_repo):
    """Create baseline tools for testing."""
    from agent.baseline.tools import create_baseline_tools

    return create_baseline_tools(baseline_repo)


@pytest.fixture
def mock_llm_response():
    """
    Factory fixture for creating mock LLM responses.

    Usage:
        def test_something(mock_llm_response):
            response = mock_llm_response(content="Hello", tool_calls=[...])
    """
    from .mocks.baseline_responses import make_llm_response

    return make_llm_response


# ============================================================
# Pytest Markers
# ============================================================


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line(
        "markers", "api: marks tests that require real API access (costs money)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )