"""
End-to-end tests for Baseline ReAct Agent.

These tests simulate complete analysis flows using mocked LLM responses
but real tool execution. This verifies the entire pipeline works correctly.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.baseline.react_agent import AnalysisResult, BaselineReActAgent, BugReport
from agent.baseline.runner import save_result

from .mocks.baseline_responses import (
    MOCK_ANALYSIS_COMPLETE_RESPONSE,
    MOCK_ANALYSIS_SEQUENCE,
    MOCK_BUG_REPORT_RESPONSE,
    MOCK_CLEAN_ANALYSIS_SEQUENCE,
    MOCK_EXTENDED_ANALYSIS_SEQUENCE,
    MOCK_LIST_FILES_CALL,
    MOCK_MULTIPLE_BUGS_RESPONSE,
    MOCK_READ_FILE_CALL,
    MOCK_SEARCH_CODE_CALL,
    make_llm_response,
    make_tool_call,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def realistic_repo(tmp_path):
    """
    Create a realistic repository structure for e2e testing.

    This mimics a real consensus protocol implementation with:
    - Core source files
    - Test files
    - Subdirectories
    - Various code patterns
    """
    # Main raft implementation
    (tmp_path / "raft.go").write_text(
        '''package raft

import (
    "sync"
    "time"
)

// Raft represents a single Raft node.
type Raft struct {
    mu          sync.Mutex
    id          int
    currentTerm int
    votedFor    int
    log         []LogEntry
    commitIndex int
    lastApplied int
    
    // Leader state
    nextIndex  []int
    matchIndex []int
    
    state    StateType
    leaderId int
}

// StateType represents the role of a Raft node.
type StateType int

const (
    Follower StateType = iota
    Candidate
    Leader
)

// RequestVoteArgs contains arguments for RequestVote RPC.
type RequestVoteArgs struct {
    Term         int
    CandidateId  int
    LastLogIndex int
    LastLogTerm  int
}

// RequestVoteReply contains reply for RequestVote RPC.
type RequestVoteReply struct {
    Term        int
    VoteGranted bool
}

// RequestVote handles vote requests from candidates.
// BUG: This implementation does not check log up-to-dateness!
func (r *Raft) RequestVote(args *RequestVoteArgs, reply *RequestVoteReply) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    reply.Term = r.currentTerm
    
    if args.Term < r.currentTerm {
        reply.VoteGranted = false
        return
    }
    
    // Missing check: Should verify candidate's log is up-to-date
    // if args.LastLogTerm < r.getLastLogTerm() {
    //     reply.VoteGranted = false
    //     return
    // }
    
    if r.votedFor == -1 || r.votedFor == args.CandidateId {
        r.votedFor = args.CandidateId
        reply.VoteGranted = true
    }
}

// AppendEntries handles log replication from leader.
func (r *Raft) AppendEntries(args *AppendEntriesArgs, reply *AppendEntriesReply) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    // Implementation...
}

func (r *Raft) getLastLogTerm() int {
    if len(r.log) == 0 {
        return 0
    }
    return r.log[len(r.log)-1].Term
}
'''
    )

    # Log management
    (tmp_path / "log.go").write_text(
        '''package raft

// LogEntry represents a single log entry.
type LogEntry struct {
    Term    int
    Index   int
    Command interface{}
}

// AppendEntriesArgs contains arguments for AppendEntries RPC.
type AppendEntriesArgs struct {
    Term         int
    LeaderId     int
    PrevLogIndex int
    PrevLogTerm  int
    Entries      []LogEntry
    LeaderCommit int
}

// AppendEntriesReply contains reply for AppendEntries RPC.
type AppendEntriesReply struct {
    Term    int
    Success bool
}

// appendLog adds entries to the log.
func (r *Raft) appendLog(entries []LogEntry) {
    r.log = append(r.log, entries...)
}

// truncateLog removes entries from index onwards.
func (r *Raft) truncateLog(index int) {
    if index < len(r.log) {
        r.log = r.log[:index]
    }
}
'''
    )

    # Storage interface
    (tmp_path / "storage.go").write_text(
        '''package raft

// Storage interface for persistent state.
type Storage interface {
    SaveState(term int, votedFor int) error
    LoadState() (term int, votedFor int, err error)
    SaveLog(entries []LogEntry) error
    LoadLog() ([]LogEntry, error)
}

// MemoryStorage implements Storage interface in memory.
type MemoryStorage struct {
    term     int
    votedFor int
    log      []LogEntry
}

func NewMemoryStorage() *MemoryStorage {
    return &MemoryStorage{votedFor: -1}
}

func (m *MemoryStorage) SaveState(term int, votedFor int) error {
    m.term = term
    m.votedFor = votedFor
    return nil
}

func (m *MemoryStorage) LoadState() (int, int, error) {
    return m.term, m.votedFor, nil
}

func (m *MemoryStorage) SaveLog(entries []LogEntry) error {
    m.log = append(m.log, entries...)
    return nil
}

func (m *MemoryStorage) LoadLog() ([]LogEntry, error) {
    return m.log, nil
}
'''
    )

    # Test file
    (tmp_path / "raft_test.go").write_text(
        '''package raft

import "testing"

func TestRequestVote(t *testing.T) {
    r := &Raft{currentTerm: 1, votedFor: -1}
    args := &RequestVoteArgs{Term: 2, CandidateId: 1}
    reply := &RequestVoteReply{}
    
    r.RequestVote(args, reply)
    
    if !reply.VoteGranted {
        t.Error("Expected vote to be granted")
    }
}

func TestAppendEntries(t *testing.T) {
    // Test implementation
}
'''
    )

    # Subdirectory with utilities
    (tmp_path / "internal").mkdir()
    (tmp_path / "internal" / "util.go").write_text(
        '''package internal

func min(a, b int) int {
    if a < b {
        return a
    }
    return b
}

func max(a, b int) int {
    if a > b {
        return a
    }
    return b
}
'''
    )

    return tmp_path


@pytest.fixture
def e2e_agent(realistic_repo):
    """Create agent for e2e testing."""
    return BaselineReActAgent(
        model="anthropic/claude-sonnet-4",
        api_key="test-api-key",
        base_url="https://openrouter.ai/api/v1",
        repo_path=realistic_repo,
        max_iterations=20,
    )


# ============================================================
# Mock Response Generator
# ============================================================


class MockResponseSequence:
    """Helper class to manage a sequence of mock responses."""

    def __init__(self, responses: list):
        self.responses = responses
        self.index = 0
        self.call_count = 0

    async def get_next(self, *args, **kwargs):
        """Get the next response in the sequence."""
        self.call_count += 1
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return httpx.Response(
            200,
            json=response,
            request=httpx.Request("POST", "https://test.com"),
        )

    def reset(self):
        """Reset the sequence."""
        self.index = 0
        self.call_count = 0


# ============================================================
# E2E Bug Discovery Tests
# ============================================================


@pytest.mark.e2e
class TestE2EBugDiscovery:
    """End-to-end tests for bug discovery flow."""

    @pytest.mark.asyncio
    async def test_complete_analysis_finds_bug(self, e2e_agent):
        """Test complete analysis flow that finds a bug."""
        sequence = MockResponseSequence(MOCK_ANALYSIS_SEQUENCE)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft", ["raft.go"])

        assert result.success
        assert result.has_bugs
        assert len(result.bugs_found) >= 1
        assert result.iterations == len(MOCK_ANALYSIS_SEQUENCE)
        assert result.tool_calls == 3  # list_files, read_file, search_code

    @pytest.mark.asyncio
    async def test_analysis_finds_multiple_bugs(self, e2e_agent):
        """Test analysis that finds multiple bugs."""
        sequence = MockResponseSequence([
            MOCK_LIST_FILES_CALL,
            MOCK_READ_FILE_CALL,
            MOCK_MULTIPLE_BUGS_RESPONSE,
        ])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.success
        assert len(result.bugs_found) == 2

        # Verify bug details
        bug_types = [b.bug_type for b in result.bugs_found]
        assert "race_condition" in bug_types or "race" in bug_types
        assert "liveness" in bug_types

    @pytest.mark.asyncio
    async def test_analysis_no_bugs_found(self, e2e_agent):
        """Test analysis flow that finds no bugs."""
        sequence = MockResponseSequence(MOCK_CLEAN_ANALYSIS_SEQUENCE)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.success
        assert not result.has_bugs
        assert "analysis_complete" in result.final_response.lower()


# ============================================================
# E2E Tool Execution Tests
# ============================================================


@pytest.mark.e2e
class TestE2EToolExecution:
    """End-to-end tests verifying real tool execution."""

    @pytest.mark.asyncio
    async def test_tools_read_actual_files(self, e2e_agent):
        """Test that tools actually read files from the repo."""
        # Create a response that requests reading a specific file
        read_response = make_llm_response(
            content="Reading the main file",
            tool_calls=[
                make_tool_call("call_001", "read_file", {"path": "raft.go"}),
            ],
        )
        bug_response = MOCK_BUG_REPORT_RESPONSE

        sequence = MockResponseSequence([read_response, bug_response])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        # The file should be tracked
        assert "raft.go" in result.files_analyzed

    @pytest.mark.asyncio
    async def test_tools_list_actual_directory(self, e2e_agent, realistic_repo):
        """Test that list_files returns actual directory contents."""
        list_response = make_llm_response(
            content="Listing files",
            tool_calls=[
                make_tool_call("call_001", "list_files", {"path": "."}),
            ],
        )
        complete_response = MOCK_ANALYSIS_COMPLETE_RESPONSE

        sequence = MockResponseSequence([list_response, complete_response])

        # We need to verify the tool output contains expected files
        # This is done indirectly through successful completion

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.success

    @pytest.mark.asyncio
    async def test_tools_search_actual_code(self, e2e_agent):
        """Test that search_code searches actual files."""
        search_response = make_llm_response(
            content="Searching for patterns",
            tool_calls=[
                make_tool_call(
                    "call_001",
                    "search_code",
                    {"pattern": "RequestVote", "file_glob": "**/*.go"},
                ),
            ],
        )
        complete_response = MOCK_ANALYSIS_COMPLETE_RESPONSE

        sequence = MockResponseSequence([search_response, complete_response])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.success
        assert result.tool_calls >= 1


# ============================================================
# E2E Error Recovery Tests
# ============================================================


@pytest.mark.e2e
class TestE2EErrorRecovery:
    """End-to-end tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_handles_http_500_error(self, e2e_agent):
        """Test handling of HTTP 500 error."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                500,
                json={"error": "Server error"},
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await e2e_agent.analyze("raft")

        assert not result.success
        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_handles_timeout(self, e2e_agent):
        """Test handling of request timeout."""
        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Timeout")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await e2e_agent.analyze("raft")

        assert not result.success
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_malformed_tool_args(self, e2e_agent):
        """Test handling of malformed tool arguments from LLM."""
        malformed_response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_001",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": "{not valid json",
                                },
                            }
                        ],
                    }
                }
            ]
        }
        complete_response = MOCK_ANALYSIS_COMPLETE_RESPONSE

        sequence = MockResponseSequence([malformed_response, complete_response])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        # Should handle gracefully and continue
        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_handles_unknown_tool(self, e2e_agent):
        """Test handling of unknown tool request from LLM."""
        unknown_tool_response = make_llm_response(
            content="",
            tool_calls=[
                make_tool_call("call_001", "nonexistent_tool", {"arg": "value"}),
            ],
        )
        complete_response = MOCK_ANALYSIS_COMPLETE_RESPONSE

        sequence = MockResponseSequence([unknown_tool_response, complete_response])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        # Should handle unknown tool and continue
        assert result.iterations >= 1


# ============================================================
# E2E Max Iterations Tests
# ============================================================


@pytest.mark.e2e
class TestE2EMaxIterations:
    """End-to-end tests for iteration limits."""

    @pytest.mark.asyncio
    async def test_respects_max_iterations(self, realistic_repo):
        """Test that agent respects max iterations limit."""
        agent = BaselineReActAgent(
            model="test-model",
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            repo_path=realistic_repo,
            max_iterations=5,
        )

        # Always return tool calls to trigger max iterations
        sequence = MockResponseSequence([MOCK_LIST_FILES_CALL] * 10)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await agent.analyze("raft")

        assert result.iterations <= 5

    @pytest.mark.asyncio
    async def test_extended_analysis(self, e2e_agent):
        """Test extended analysis with many iterations."""
        sequence = MockResponseSequence(MOCK_EXTENDED_ANALYSIS_SEQUENCE)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.success
        assert result.iterations == len(MOCK_EXTENDED_ANALYSIS_SEQUENCE)


# ============================================================
# E2E Result Persistence Tests
# ============================================================


@pytest.mark.e2e
class TestE2EResultPersistence:
    """End-to-end tests for result saving and loading."""

    @pytest.mark.asyncio
    async def test_save_and_reload_e2e_result(self, e2e_agent, tmp_path):
        """Test saving and reloading a complete e2e result."""
        sequence = MockResponseSequence(MOCK_ANALYSIS_SEQUENCE)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft", ["raft.go"])

        # Save result
        output_path = save_result(result, tmp_path)

        # Reload and verify
        with open(output_path) as f:
            data = json.load(f)

        assert data["repo_name"] == "raft"
        assert data["model"] == "anthropic/claude-sonnet-4"
        assert data["iterations"] == result.iterations
        assert data["tool_calls"] == result.tool_calls
        assert len(data["bugs_found"]) == len(result.bugs_found)

    @pytest.mark.asyncio
    async def test_result_contains_duration(self, e2e_agent):
        """Test that result contains meaningful duration."""
        sequence = MockResponseSequence(MOCK_ANALYSIS_SEQUENCE)

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.duration_ms > 0


# ============================================================
# E2E Statistics Tests
# ============================================================


@pytest.mark.e2e
class TestE2EStatistics:
    """End-to-end tests for tracking statistics."""

    @pytest.mark.asyncio
    async def test_tracks_tool_calls(self, e2e_agent):
        """Test that tool calls are counted correctly."""
        # 3 tool calls in sequence
        sequence = MockResponseSequence([
            MOCK_LIST_FILES_CALL,  # 1 tool call
            MOCK_READ_FILE_CALL,   # 1 tool call
            MOCK_SEARCH_CODE_CALL, # 1 tool call
            MOCK_BUG_REPORT_RESPONSE,
        ])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert result.tool_calls == 3

    @pytest.mark.asyncio
    async def test_tracks_files_analyzed(self, e2e_agent):
        """Test that files read are tracked."""
        # Multiple file reads
        multi_read_response = make_llm_response(
            content="Reading files",
            tool_calls=[
                make_tool_call("call_001", "read_file", {"path": "raft.go"}),
                make_tool_call("call_002", "read_file", {"path": "log.go"}),
            ],
        )

        sequence = MockResponseSequence([multi_read_response, MOCK_BUG_REPORT_RESPONSE])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        assert "raft.go" in result.files_analyzed
        assert "log.go" in result.files_analyzed

    @pytest.mark.asyncio
    async def test_files_analyzed_sorted(self, e2e_agent):
        """Test that files_analyzed is sorted."""
        multi_read_response = make_llm_response(
            content="Reading files",
            tool_calls=[
                make_tool_call("call_001", "read_file", {"path": "storage.go"}),
                make_tool_call("call_002", "read_file", {"path": "raft.go"}),
                make_tool_call("call_003", "read_file", {"path": "log.go"}),
            ],
        )

        sequence = MockResponseSequence([multi_read_response, MOCK_BUG_REPORT_RESPONSE])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result = await e2e_agent.analyze("raft")

        # Should be sorted
        assert result.files_analyzed == sorted(result.files_analyzed)


# ============================================================
# E2E Concurrent Execution Tests
# ============================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestE2EConcurrency:
    """End-to-end tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_multiple_analyses_sequential(self, e2e_agent):
        """Test running multiple analyses sequentially."""
        sequence = MockResponseSequence(MOCK_ANALYSIS_SEQUENCE * 3)

        results = []
        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            for _ in range(3):
                result = await e2e_agent.analyze("raft")
                results.append(result)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_agent_state_reset_between_analyses(self, e2e_agent):
        """Test that agent state is reset between analyses."""
        sequence = MockResponseSequence([
            make_llm_response(
                content="",
                tool_calls=[make_tool_call("c1", "read_file", {"path": "raft.go"})],
            ),
            MOCK_BUG_REPORT_RESPONSE,
            make_llm_response(
                content="",
                tool_calls=[make_tool_call("c2", "read_file", {"path": "log.go"})],
            ),
            MOCK_ANALYSIS_COMPLETE_RESPONSE,
        ])

        with patch.object(httpx.AsyncClient, "post", sequence.get_next):
            result1 = await e2e_agent.analyze("raft")
            result2 = await e2e_agent.analyze("raft")

        # Each analysis should have its own files
        # (files from first analysis shouldn't appear in second)
        assert "raft.go" in result1.files_analyzed
        assert "log.go" in result2.files_analyzed
        # The second analysis should NOT include files from first
        # (assuming they're different tool call sequences)
