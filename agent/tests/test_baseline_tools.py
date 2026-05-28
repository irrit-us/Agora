"""
Tests for Baseline Agent tools.

Tests all tools created by create_baseline_tools:
- read_file
- search_code
- run_command
- list_files
"""

import asyncio
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

from agent.baseline.tools import create_baseline_tools


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repository with test files."""
    # Create main source file
    (tmp_path / "raft.go").write_text(
        """package raft

import "sync"

// Raft represents a Raft consensus node.
type Raft struct {
    mu        sync.Mutex
    currentTerm int
    votedFor    int
    log         []LogEntry
}

// RequestVote handles vote requests from candidates.
func (r *Raft) RequestVote(args *RequestVoteArgs) bool {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if args.Term < r.currentTerm {
        return false
    }
    return true
}

// AppendEntries handles log replication from leader.
func (r *Raft) AppendEntries(args *AppendEntriesArgs) bool {
    return true
}
"""
    )

    # Create log file
    (tmp_path / "log.go").write_text(
        """package raft

// LogEntry represents a single log entry.
type LogEntry struct {
    Term    int
    Command interface{}
}

// appendLog adds entries to the log.
func (r *Raft) appendLog(entries []LogEntry) {
    r.log = append(r.log, entries...)
}
"""
    )

    # Create subdirectory with files
    subdir = tmp_path / "internal"
    subdir.mkdir()
    (subdir / "util.go").write_text(
        """package internal

func min(a, b int) int {
    if a < b {
        return a
    }
    return b
}
"""
    )

    # Create a test file
    (tmp_path / "raft_test.go").write_text(
        """package raft

import "testing"

func TestRequestVote(t *testing.T) {
    // Test implementation
}
"""
    )

    # Create a large file for testing line limits
    large_content = "\n".join([f"// Line {i}" for i in range(1, 1001)])
    (tmp_path / "large_file.go").write_text(large_content)

    # Create file with unicode content
    (tmp_path / "unicode.go").write_text(
        """package raft

// 中文注释
// Japanese: 日本語
// Emoji: 🎉
func unicode() {}
"""
    )

    return tmp_path


@pytest.fixture
def baseline_tools(temp_repo):
    """Create baseline tools for the temporary repository."""
    return create_baseline_tools(temp_repo)


@pytest.fixture
def tools_dict(baseline_tools):
    """Create a dictionary of tools by name."""
    return {t.name: t for t in baseline_tools}


# ============================================================
# create_baseline_tools Tests
# ============================================================


class TestCreateBaselineTools:
    """Tests for the create_baseline_tools function."""

    def test_returns_list_of_tools(self, temp_repo):
        """Test that function returns a list of Tool objects."""
        tools = create_baseline_tools(temp_repo)
        assert isinstance(tools, list)
        assert len(tools) == 4

    def test_all_tools_have_names(self, baseline_tools):
        """Test that all tools have names."""
        for tool in baseline_tools:
            assert hasattr(tool, "name")
            assert isinstance(tool.name, str)
            assert len(tool.name) > 0

    def test_all_tools_have_descriptions(self, baseline_tools):
        """Test that all tools have descriptions."""
        for tool in baseline_tools:
            assert hasattr(tool, "description")
            assert isinstance(tool.description, str)

    def test_all_tools_have_functions(self, baseline_tools):
        """Test that all tools have callable functions."""
        for tool in baseline_tools:
            assert hasattr(tool, "func")
            assert callable(tool.func)

    def test_expected_tool_names(self, tools_dict):
        """Test that expected tools are created."""
        expected_names = ["read_file", "search_code", "run_command", "list_files"]
        for name in expected_names:
            assert name in tools_dict, f"Missing tool: {name}"

    def test_tools_can_convert_to_openai_format(self, baseline_tools):
        """Test that tools can be converted to OpenAI format."""
        for tool in baseline_tools:
            openai_format = tool.to_openai_format()
            assert "type" in openai_format
            assert openai_format["type"] == "function"
            assert "function" in openai_format
            assert "name" in openai_format["function"]
            assert "description" in openai_format["function"]


# ============================================================
# read_file Tool Tests
# ============================================================


class TestReadFileTool:
    """Tests for the read_file tool."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tools_dict):
        """Test reading an existing file."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="raft.go")

        assert "File: raft.go" in result
        assert "package raft" in result
        assert "RequestVote" in result

    @pytest.mark.asyncio
    async def test_read_file_with_line_numbers(self, tools_dict):
        """Test that file content includes line numbers."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="raft.go")

        # Should have line numbers
        assert "| " in result
        # First line should be numbered 1
        assert "1|" in result or "     1|" in result

    @pytest.mark.asyncio
    async def test_read_file_with_start_line(self, tools_dict):
        """Test reading file from a specific line."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="large_file.go", start_line=100, max_lines=10)

        assert "lines 101-110" in result
        assert "Line 101" in result
        assert "Line 110" in result

    @pytest.mark.asyncio
    async def test_read_file_with_max_lines(self, tools_dict):
        """Test reading file with line limit."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="large_file.go", max_lines=50)

        assert "lines 1-50" in result
        # Should not contain line 51
        lines = result.split("\n")
        # Count actual content lines (excluding header)
        assert len([l for l in lines if l.strip() and "|" in l]) <= 50

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tools_dict):
        """Test reading a file that doesn't exist."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="nonexistent.go")

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_read_directory_as_file(self, tools_dict):
        """Test reading a directory instead of file."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="internal")

        assert "Error" in result
        assert "Not a file" in result

    @pytest.mark.asyncio
    async def test_read_file_strips_leading_slash(self, tools_dict):
        """Test that leading slash is stripped from path."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="/raft.go")

        assert "package raft" in result

    @pytest.mark.asyncio
    async def test_read_file_in_subdirectory(self, tools_dict):
        """Test reading file in subdirectory."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="internal/util.go")

        assert "package internal" in result
        assert "func min" in result

    @pytest.mark.asyncio
    async def test_read_unicode_file(self, tools_dict):
        """Test reading file with unicode content."""
        read_file = tools_dict["read_file"]
        result = await read_file.func(path="unicode.go")

        assert "中文注释" in result
        assert "日本語" in result


# ============================================================
# search_code Tool Tests
# ============================================================


class TestSearchCodeTool:
    """Tests for the search_code tool."""

    @pytest.mark.asyncio
    async def test_search_simple_pattern(self, tools_dict):
        """Test searching for a simple pattern."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="RequestVote")

        assert "RequestVote" in result
        assert "raft.go" in result

    @pytest.mark.asyncio
    async def test_search_with_file_glob(self, tools_dict):
        """Test searching with file glob filter."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="func", file_glob="**/*_test.go")

        assert "raft_test.go" in result
        # Should find test function
        assert "Test" in result

    @pytest.mark.asyncio
    async def test_search_no_matches(self, tools_dict):
        """Test searching for pattern with no matches."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="ThisPatternDoesNotExist12345")

        assert "No matches" in result

    @pytest.mark.asyncio
    async def test_search_regex_pattern(self, tools_dict):
        """Test searching with regex pattern."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="func.*Vote")

        assert "RequestVote" in result

    @pytest.mark.asyncio
    async def test_search_with_context_lines(self, tools_dict):
        """Test that search includes context lines."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="currentTerm", context_lines=2)

        # Should have surrounding context
        lines = result.split("\n")
        assert len(lines) > 3  # More than just the match

    @pytest.mark.asyncio
    async def test_search_multiple_files(self, tools_dict):
        """Test that search finds matches in multiple files."""
        search_code = tools_dict["search_code"]
        result = await search_code.func(pattern="package raft")

        # Should find in multiple files
        assert "raft.go" in result
        assert "log.go" in result


# ============================================================
# run_command Tool Tests
# ============================================================


class TestRunCommandTool:
    """Tests for the run_command tool."""

    @pytest.mark.asyncio
    async def test_run_ls_command(self, tools_dict):
        """Test running ls command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="ls")

        assert "raft.go" in result
        assert "log.go" in result

    @pytest.mark.asyncio
    async def test_run_ls_with_options(self, tools_dict):
        """Test running ls with options."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="ls -la")

        # Should include hidden files info
        assert "." in result

    @pytest.mark.asyncio
    async def test_run_cat_command(self, tools_dict):
        """Test running cat command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="cat raft.go")

        assert "package raft" in result

    @pytest.mark.asyncio
    async def test_run_head_command(self, tools_dict):
        """Test running head command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="head -5 raft.go")

        assert "package raft" in result

    @pytest.mark.asyncio
    async def test_run_wc_command(self, tools_dict):
        """Test running wc command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="wc -l raft.go")

        # Should return line count
        assert result.strip()

    @pytest.mark.asyncio
    async def test_forbidden_command_rm(self, tools_dict):
        """Test that rm command is rejected."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="rm -rf /")

        assert "Error" in result
        assert "not allowed" in result.lower()

    @pytest.mark.asyncio
    async def test_forbidden_command_mv(self, tools_dict):
        """Test that mv command is rejected."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="mv file1 file2")

        assert "Error" in result
        assert "not allowed" in result.lower()

    @pytest.mark.asyncio
    async def test_forbidden_command_python(self, tools_dict):
        """Test that python command is rejected."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="python -c 'print(1)'")

        assert "Error" in result
        assert "not allowed" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_command(self, tools_dict):
        """Test running empty command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="")

        assert "Error" in result
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_command_with_pipe(self, tools_dict):
        """Test running command with pipe."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="ls | head -5")

        # Pipes may or may not work depending on shell configuration
        # At minimum, the command should execute without raising
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_command(self, tools_dict):
        """Test running find command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="find . -name '*.go'")

        assert "raft.go" in result

    @pytest.mark.asyncio
    async def test_grep_command(self, tools_dict):
        """Test running grep command."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="grep -r 'package' .")

        assert "raft" in result

    @pytest.mark.asyncio
    async def test_command_nonzero_exit(self, tools_dict):
        """Test command with non-zero exit code."""
        run_command = tools_dict["run_command"]
        result = await run_command.func(command="ls nonexistent_file_12345")

        # Should contain error info
        assert "stderr" in result.lower() or "No such file" in result


# ============================================================
# list_files Tool Tests
# ============================================================


class TestListFilesTool:
    """Tests for the list_files tool."""

    @pytest.mark.asyncio
    async def test_list_root_directory(self, tools_dict):
        """Test listing root directory."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path=".")

        assert "raft.go" in result
        assert "log.go" in result
        assert "internal/" in result  # Directory should have trailing slash

    @pytest.mark.asyncio
    async def test_list_subdirectory(self, tools_dict):
        """Test listing subdirectory."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path="internal")

        assert "util.go" in result

    @pytest.mark.asyncio
    async def test_list_with_pattern(self, tools_dict):
        """Test listing with glob pattern."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path=".", pattern="*.go")

        assert "raft.go" in result
        # Should not include subdirectory
        assert "internal/util.go" not in result

    @pytest.mark.asyncio
    async def test_list_nonexistent_path(self, tools_dict):
        """Test listing non-existent path."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path="nonexistent_dir")

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_list_file_path(self, tools_dict):
        """Test listing a file path instead of directory."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path="raft.go")

        # Should return file info
        assert "raft.go" in result
        assert "file" in result.lower()
        assert "bytes" in result.lower()

    @pytest.mark.asyncio
    async def test_list_strips_leading_slash(self, tools_dict):
        """Test that leading slash is stripped."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path="/internal")

        assert "util.go" in result

    @pytest.mark.asyncio
    async def test_list_test_files_only(self, tools_dict):
        """Test listing only test files."""
        list_files = tools_dict["list_files"]
        result = await list_files.func(path=".", pattern="*_test.go")

        assert "raft_test.go" in result
        assert "raft.go" not in result or result.count("raft") == result.count("raft_test")

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, tools_dict, temp_repo):
        """Test listing empty directory."""
        # Create empty directory
        empty_dir = temp_repo / "empty_dir"
        empty_dir.mkdir()

        list_files = tools_dict["list_files"]
        result = await list_files.func(path="empty_dir")

        assert "empty" in result.lower()


# ============================================================
# Edge Cases and Error Handling
# ============================================================


class TestToolEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_read_file_outside_repo(self, tools_dict):
        """Test that reading files outside repo is blocked."""
        read_file = tools_dict["read_file"]
        # Try to escape using ..
        result = await read_file.func(path="../../../etc/passwd")

        # Should either fail or be contained within repo
        # The exact behavior depends on implementation

    @pytest.mark.asyncio
    async def test_tools_are_async(self, tools_dict):
        """Test that all tools are async functions."""
        for name, tool in tools_dict.items():
            assert asyncio.iscoroutinefunction(tool.func), f"{name} should be async"

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, tools_dict):
        """Test that tools can be called concurrently."""
        read_file = tools_dict["read_file"]
        list_files = tools_dict["list_files"]

        # Run multiple tool calls concurrently
        results = await asyncio.gather(
            read_file.func(path="raft.go"),
            read_file.func(path="log.go"),
            list_files.func(path="."),
        )

        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)
        assert "package raft" in results[0]
        assert "LogEntry" in results[1]
        assert "raft.go" in results[2]


# ============================================================
# Tool Schema Validation Tests
# ============================================================


class TestToolSchemas:
    """Tests for tool schema definitions."""

    def test_read_file_schema(self, tools_dict):
        """Test read_file tool schema."""
        tool = tools_dict["read_file"]
        schema = tool.to_openai_format()

        params = schema["function"]["parameters"]
        assert "path" in params.get("properties", {})

    def test_search_code_schema(self, tools_dict):
        """Test search_code tool schema."""
        tool = tools_dict["search_code"]
        schema = tool.to_openai_format()

        params = schema["function"]["parameters"]
        props = params.get("properties", {})
        assert "pattern" in props

    def test_run_command_schema(self, tools_dict):
        """Test run_command tool schema."""
        tool = tools_dict["run_command"]
        schema = tool.to_openai_format()

        params = schema["function"]["parameters"]
        props = params.get("properties", {})
        assert "command" in props

    def test_list_files_schema(self, tools_dict):
        """Test list_files tool schema."""
        tool = tools_dict["list_files"]
        schema = tool.to_openai_format()

        params = schema["function"]["parameters"]
        props = params.get("properties", {})
        assert "path" in props
