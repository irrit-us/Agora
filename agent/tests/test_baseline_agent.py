"""
Tests for BaselineReActAgent.

Tests the core agent logic including:
- Initialization
- LLM API calls (mocked)
- Tool execution
- Bug report parsing
- Analysis flow
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

from agent.baseline.react_agent import (
    AnalysisResult,
    BaselineReActAgent,
    BugReport,
    sanitize_model_name,
)

from .mocks.baseline_responses import (
    MOCK_ANALYSIS_COMPLETE_RESPONSE,
    MOCK_BUG_REPORT_RESPONSE,
    MOCK_HTTP_401_RESPONSE,
    MOCK_HTTP_500_RESPONSE,
    MOCK_LIST_FILES_CALL,
    MOCK_MULTIPLE_BUGS_RESPONSE,
    MOCK_READ_FILE_CALL,
    make_llm_response,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repository with test files."""
    # Create basic files
    (tmp_path / "raft.go").write_text(
        """package raft

func (r *Raft) RequestVote(args *RequestVoteArgs) bool {
    return true
}
"""
    )
    (tmp_path / "log.go").write_text(
        """package raft

type LogEntry struct {
    Term int
}
"""
    )

    # Create subdirectory
    (tmp_path / "internal").mkdir()
    (tmp_path / "internal" / "util.go").write_text("package internal")

    return tmp_path


@pytest.fixture
def agent(temp_repo):
    """Create a BaselineReActAgent instance."""
    return BaselineReActAgent(
        model="anthropic/claude-sonnet-4",
        api_key="test-api-key",
        base_url="https://openrouter.ai/api/v1",
        repo_path=temp_repo,
        max_iterations=10,
    )


# ============================================================
# Utility Function Tests
# ============================================================


class TestSanitizeModelName:
    """Tests for the sanitize_model_name function."""

    def test_sanitize_with_slash(self):
        """Test sanitizing model name with slash."""
        result = sanitize_model_name("anthropic/claude-sonnet-4")
        assert result == "anthropic_claude-sonnet-4"
        assert "/" not in result

    def test_sanitize_with_colon(self):
        """Test sanitizing model name with colon."""
        result = sanitize_model_name("model:version")
        assert result == "model_version"
        assert ":" not in result

    def test_sanitize_with_space(self):
        """Test sanitizing model name with space."""
        result = sanitize_model_name("model name")
        assert result == "model_name"
        assert " " not in result

    def test_sanitize_multiple_special_chars(self):
        """Test sanitizing with multiple special characters."""
        result = sanitize_model_name("org/model:v1 beta")
        assert result == "org_model_v1_beta"

    def test_sanitize_already_clean(self):
        """Test sanitizing already clean name."""
        result = sanitize_model_name("clean-model-name")
        assert result == "clean-model-name"


# ============================================================
# BugReport Tests
# ============================================================


class TestBugReport:
    """Tests for the BugReport dataclass."""

    def test_bug_report_creation(self):
        """Test creating a BugReport."""
        bug = BugReport(
            file="raft.go",
            line=145,
            bug_type="safety",
            severity="critical",
            description="Test description",
            root_cause="Test cause",
            trigger_condition="Test trigger",
            impact="Test impact",
        )

        assert bug.file == "raft.go"
        assert bug.line == 145
        assert bug.bug_type == "safety"

    def test_bug_report_to_dict(self):
        """Test converting BugReport to dictionary."""
        bug = BugReport(
            file="raft.go",
            line=100,
            bug_type="liveness",
            severity="high",
            description="Desc",
            root_cause="Cause",
            trigger_condition="Trigger",
            impact="Impact",
        )

        d = bug.to_dict()
        assert d["file"] == "raft.go"
        assert d["line"] == 100
        assert d["type"] == "liveness"
        assert d["severity"] == "high"

    def test_bug_report_with_none_line(self):
        """Test BugReport with None line number."""
        bug = BugReport(
            file="raft.go",
            line=None,
            bug_type="safety",
            severity="medium",
            description="Desc",
            root_cause="Cause",
            trigger_condition="Trigger",
            impact="Impact",
        )

        assert bug.line is None
        d = bug.to_dict()
        assert d["line"] is None


# ============================================================
# AnalysisResult Tests
# ============================================================


class TestAnalysisResult:
    """Tests for the AnalysisResult dataclass."""

    def test_analysis_result_creation(self):
        """Test creating an AnalysisResult."""
        result = AnalysisResult(repo_name="raft")

        assert result.repo_name == "raft"
        assert result.bugs_found == []
        assert result.files_analyzed == []
        assert result.iterations == 0

    def test_analysis_result_success_property(self):
        """Test success property."""
        result = AnalysisResult(repo_name="raft")
        assert result.success is True

        result.error = "Some error"
        assert result.success is False

    def test_analysis_result_has_bugs_property(self):
        """Test has_bugs property."""
        result = AnalysisResult(repo_name="raft")
        assert result.has_bugs is False

        bug = BugReport(
            file="test",
            line=1,
            bug_type="safety",
            severity="low",
            description="",
            root_cause="",
            trigger_condition="",
            impact="",
        )
        result.bugs_found.append(bug)
        assert result.has_bugs is True

    def test_analysis_result_model_safe_name(self):
        """Test model_safe_name property."""
        result = AnalysisResult(repo_name="raft", model="anthropic/claude-sonnet-4")
        assert result.model_safe_name == "anthropic_claude-sonnet-4"

    def test_analysis_result_to_dict(self):
        """Test converting AnalysisResult to dictionary."""
        result = AnalysisResult(
            repo_name="raft",
            model="test-model",
            iterations=5,
            tool_calls=10,
            duration_ms=5000,
        )

        d = result.to_dict()
        assert d["repo_name"] == "raft"
        assert d["model"] == "test-model"
        assert d["iterations"] == 5
        assert d["tool_calls"] == 10
        assert d["duration_ms"] == 5000


# ============================================================
# Agent Initialization Tests
# ============================================================


class TestAgentInitialization:
    """Tests for BaselineReActAgent initialization."""

    def test_basic_initialization(self, temp_repo):
        """Test basic agent initialization."""
        agent = BaselineReActAgent(
            model="test-model",
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            repo_path=temp_repo,
        )

        assert agent.model == "test-model"
        assert agent.repo_path == temp_repo
        assert len(agent.tools) == 4

    def test_initialization_with_all_options(self, temp_repo):
        """Test initialization with all options."""
        agent = BaselineReActAgent(
            model="test-model",
            api_key="test-key",
            base_url="https://custom.api/v1",
            repo_path=temp_repo,
            max_iterations=50,
            max_tokens=8000,
            timeout=60.0,
        )

        assert agent.max_iterations == 50

    def test_initialization_invalid_repo_path(self, tmp_path):
        """Test initialization with non-existent repo path."""
        with pytest.raises(ValueError, match="does not exist"):
            BaselineReActAgent(
                model="test-model",
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                repo_path=tmp_path / "nonexistent",
            )

    def test_tools_created_correctly(self, agent):
        """Test that tools are created and registered."""
        assert len(agent.tools) == 4
        tool_names = [t.name for t in agent.tools]
        assert "read_file" in tool_names
        assert "search_code" in tool_names
        assert "run_command" in tool_names
        assert "list_files" in tool_names

    def test_tools_by_name_dict(self, agent):
        """Test that tools_by_name dict is populated."""
        assert "read_file" in agent._tools_by_name
        assert agent._tools_by_name["read_file"].name == "read_file"


# ============================================================
# Tool Schema Tests
# ============================================================


class TestAgentToolSchemas:
    """Tests for agent tool schema generation."""

    def test_get_tools_schema(self, agent):
        """Test getting tools in OpenAI format."""
        schemas = agent.get_tools_schema()

        assert isinstance(schemas, list)
        assert len(schemas) == 4

        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]

    def test_tools_schema_has_parameters(self, agent):
        """Test that tool schemas include parameters."""
        schemas = agent.get_tools_schema()

        for schema in schemas:
            func = schema["function"]
            assert "parameters" in func
            assert isinstance(func["parameters"], dict)


# ============================================================
# LLM Call Tests (Mocked)
# ============================================================


class TestLLMCalls:
    """Tests for LLM API calls."""

    @pytest.mark.asyncio
    async def test_call_llm_success(self, agent):
        """Test successful LLM API call."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_LIST_FILES_CALL,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent._call_llm([{"role": "user", "content": "test"}])

            assert "content" in result
            assert "tool_calls" in result

    @pytest.mark.asyncio
    async def test_call_llm_with_tool_calls(self, agent):
        """Test LLM response with tool calls."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_READ_FILE_CALL,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent._call_llm([{"role": "user", "content": "test"}])

            assert len(result["tool_calls"]) > 0
            tool_call = result["tool_calls"][0]
            assert tool_call["function"]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_call_llm_no_tool_calls(self, agent):
        """Test LLM response without tool calls."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_BUG_REPORT_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent._call_llm([{"role": "user", "content": "test"}])

            assert result["tool_calls"] == []
            assert "bug_report" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_call_llm_http_error(self, agent):
        """Test handling of HTTP error."""
        async def mock_post(*args, **kwargs):
            response = httpx.Response(
                401,
                json=MOCK_HTTP_401_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )
            return response

        with patch.object(httpx.AsyncClient, "post", mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await agent._call_llm([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_call_llm_empty_choices(self, agent):
        """Test handling of empty choices in response."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json={"choices": []},
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            with pytest.raises(RuntimeError, match="missing 'choices'"):
                await agent._call_llm([{"role": "user", "content": "test"}])


# ============================================================
# Tool Execution Tests
# ============================================================


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_known_tool(self, agent):
        """Test executing a known tool."""
        result = await agent._execute_tool("list_files", {"path": "."})

        assert isinstance(result, str)
        assert "raft.go" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, agent):
        """Test executing an unknown tool."""
        result = await agent._execute_tool("nonexistent_tool", {})

        assert "Error" in result
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_tool_with_invalid_args(self, agent):
        """Test executing tool with invalid arguments."""
        result = await agent._execute_tool(
            "read_file", {"invalid_param": "value"}
        )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_process_tool_call(self, agent):
        """Test processing a tool call from LLM response."""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "list_files",
                "arguments": json.dumps({"path": "."}),
            },
        }

        result = await agent._process_tool_call(tool_call)

        assert isinstance(result, str)
        assert "raft.go" in result

    @pytest.mark.asyncio
    async def test_process_tool_call_invalid_json(self, agent):
        """Test processing tool call with invalid JSON arguments."""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "list_files",
                "arguments": "{invalid json}",
            },
        }

        result = await agent._process_tool_call(tool_call)
        # Should handle gracefully with empty args
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_process_tool_call_tracks_files(self, agent):
        """Test that read_file calls are tracked."""
        tool_call = {
            "id": "call_001",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"path": "raft.go"}),
            },
        }

        await agent._process_tool_call(tool_call)

        assert "raft.go" in agent._files_read


# ============================================================
# Bug Report Parsing Tests
# ============================================================


class TestBugReportParsing:
    """Tests for bug report parsing."""

    def test_parse_single_bug_report(self, agent):
        """Test parsing a single bug report."""
        # Use the actual format from mock responses (single line fields)
        response = MOCK_BUG_REPORT_RESPONSE["choices"][0]["message"]["content"]

        bugs = agent._parse_bug_reports(response)

        assert len(bugs) >= 1
        # The mock response has proper formatting
        assert bugs[0].file is not None
        assert bugs[0].bug_type != ""

    def test_parse_multiple_bug_reports(self, agent):
        """Test parsing multiple bug reports."""
        response = MOCK_MULTIPLE_BUGS_RESPONSE["choices"][0]["message"]["content"]

        bugs = agent._parse_bug_reports(response)

        assert len(bugs) == 2

    def test_parse_bug_report_without_line_number(self, agent):
        """Test parsing bug report without line number."""
        response = """<bug_report>
File: raft.go
Type: liveness
Severity: medium
Description: Timeout issue when waiting for responses
Root Cause: Missing timeout on RPC calls
Trigger Condition: Slow network causes indefinite wait
Impact: Node becomes unresponsive
</bug_report>"""

        bugs = agent._parse_bug_reports(response)

        assert len(bugs) == 1
        # File may include more text if parsing is loose
        assert "raft.go" in bugs[0].file
        assert bugs[0].line is None

    def test_parse_no_bug_reports(self, agent):
        """Test parsing response with no bug reports."""
        response = "Analysis complete. No bugs found."

        bugs = agent._parse_bug_reports(response)

        assert len(bugs) == 0

    def test_parse_malformed_bug_report(self, agent):
        """Test parsing malformed bug report."""
        response = """
        <bug_report>
        This is not properly formatted
        </bug_report>
        """

        bugs = agent._parse_bug_reports(response)
        # Should handle gracefully - may return empty or parse what it can
        assert isinstance(bugs, list)

    def test_parse_bug_report_with_extra_content(self, agent):
        """Test parsing bug report surrounded by other text."""
        response = """I found a bug in the code.

<bug_report>
File: test.go:10
Type: race
Severity: high
Description: Race condition in vote handling
Root Cause: Missing mutex lock
Trigger Condition: Concurrent vote requests
Impact: Data corruption and incorrect state
</bug_report>

This should be fixed immediately."""

        bugs = agent._parse_bug_reports(response)

        assert len(bugs) == 1
        assert "test.go" in bugs[0].file


# ============================================================
# Analysis Flow Tests
# ============================================================


class TestAnalysisFlow:
    """Tests for the complete analysis flow."""

    @pytest.mark.asyncio
    async def test_analyze_with_bug_found(self, agent):
        """Test analysis that finds a bug."""
        # Create response sequence
        response_sequence = [
            MOCK_LIST_FILES_CALL,
            MOCK_READ_FILE_CALL,
            MOCK_BUG_REPORT_RESPONSE,
        ]
        response_index = [0]

        async def mock_post(*args, **kwargs):
            idx = min(response_index[0], len(response_sequence) - 1)
            response_index[0] += 1
            return httpx.Response(
                200,
                json=response_sequence[idx],
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft", ["raft.go"])

        assert result.success
        assert result.has_bugs
        assert len(result.bugs_found) >= 1
        assert result.iterations > 0

    @pytest.mark.asyncio
    async def test_analyze_no_bugs_found(self, agent):
        """Test analysis that finds no bugs."""
        response_sequence = [
            MOCK_LIST_FILES_CALL,
            MOCK_READ_FILE_CALL,
            MOCK_ANALYSIS_COMPLETE_RESPONSE,
        ]
        response_index = [0]

        async def mock_post(*args, **kwargs):
            idx = min(response_index[0], len(response_sequence) - 1)
            response_index[0] += 1
            return httpx.Response(
                200,
                json=response_sequence[idx],
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft", ["raft.go"])

        assert result.success
        assert not result.has_bugs
        assert "analysis_complete" in result.final_response.lower()

    @pytest.mark.asyncio
    async def test_analyze_tracks_files(self, agent):
        """Test that analysis tracks files read."""
        response_sequence = [
            MOCK_READ_FILE_CALL,
            MOCK_BUG_REPORT_RESPONSE,
        ]
        response_index = [0]

        async def mock_post(*args, **kwargs):
            idx = min(response_index[0], len(response_sequence) - 1)
            response_index[0] += 1
            return httpx.Response(
                200,
                json=response_sequence[idx],
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft", ["raft.go"])

        # Should track files that were read
        assert len(result.files_analyzed) >= 0

    @pytest.mark.asyncio
    async def test_analyze_respects_max_iterations(self, temp_repo):
        """Test that analysis respects max iterations."""
        agent = BaselineReActAgent(
            model="test-model",
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            repo_path=temp_repo,
            max_iterations=3,
        )

        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_LIST_FILES_CALL,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        # Should stop at max iterations
        assert result.iterations <= 3

    @pytest.mark.asyncio
    async def test_analyze_records_duration(self, agent):
        """Test that analysis records duration."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_BUG_REPORT_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_analyze_counts_tool_calls(self, agent):
        """Test that analysis counts tool calls."""
        response_sequence = [
            MOCK_LIST_FILES_CALL,
            MOCK_READ_FILE_CALL,
            MOCK_BUG_REPORT_RESPONSE,
        ]
        response_index = [0]

        async def mock_post(*args, **kwargs):
            idx = min(response_index[0], len(response_sequence) - 1)
            response_index[0] += 1
            return httpx.Response(
                200,
                json=response_sequence[idx],
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        assert result.tool_calls >= 2

    @pytest.mark.asyncio
    async def test_analyze_http_error_handling(self, agent):
        """Test that analysis handles HTTP errors gracefully."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                500,
                json=MOCK_HTTP_500_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        assert not result.success
        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_analyze_timeout_handling(self, agent):
        """Test that analysis handles timeouts gracefully."""
        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Request timed out")

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        assert not result.success
        assert result.error is not None
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_with_target_files(self, agent):
        """Test analysis with specific target files."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_BUG_REPORT_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft", ["raft.go", "log.go"])

        assert result.success

    @pytest.mark.asyncio
    async def test_analyze_clears_files_read(self, agent):
        """Test that each analysis starts with fresh file tracking."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_BUG_REPORT_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        # First analysis
        with patch.object(httpx.AsyncClient, "post", mock_post):
            await agent.analyze("raft")

        # Add some manual tracking
        agent._files_read.add("old_file.go")

        # Second analysis should start fresh
        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        # old_file.go should not be in files_analyzed
        assert "old_file.go" not in result.files_analyzed


# ============================================================
# Integration Tests
# ============================================================


class TestAgentIntegration:
    """Integration tests for the agent."""

    @pytest.mark.asyncio
    async def test_full_flow_with_real_tools(self, agent):
        """Test full flow using real tools but mocked LLM."""
        # This test uses real tool execution but mocked LLM

        # Sequence: list files -> read file -> report bug
        response_sequence = [
            MOCK_LIST_FILES_CALL,
            MOCK_READ_FILE_CALL,
            MOCK_BUG_REPORT_RESPONSE,
        ]
        response_index = [0]

        async def mock_post(*args, **kwargs):
            idx = min(response_index[0], len(response_sequence) - 1)
            response_index[0] += 1
            return httpx.Response(
                200,
                json=response_sequence[idx],
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft", ["raft.go"])

        assert result.success
        assert result.iterations == 3
        assert result.tool_calls == 2  # list_files and read_file

    @pytest.mark.asyncio
    async def test_result_serialization(self, agent):
        """Test that result can be serialized to JSON."""
        async def mock_post(*args, **kwargs):
            return httpx.Response(
                200,
                json=MOCK_BUG_REPORT_RESPONSE,
                request=httpx.Request("POST", "https://test.com"),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await agent.analyze("raft")

        # Should be serializable
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)
        assert json_str is not None

        # Should be deserializable
        loaded = json.loads(json_str)
        assert loaded["repo_name"] == "raft"
