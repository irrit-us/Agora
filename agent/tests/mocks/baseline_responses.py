"""
Mock LLM responses for Baseline ReAct Agent testing.

These responses mimic the expected format from OpenRouter API
for the BaselineReActAgent's ReAct loop.
"""

import json
from typing import Any

# ============================================================
# Tool Call Response Structures
# ============================================================


def make_tool_call(
    tool_id: str, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Create a tool call structure in OpenAI format."""
    return {
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def make_llm_response(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a mock LLM API response."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "anthropic/claude-sonnet-4",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


# ============================================================
# Tool Call Responses - Exploration Phase
# ============================================================

# First iteration: List files to understand structure
MOCK_LIST_FILES_CALL = make_llm_response(
    content="I'll start by exploring the repository structure to understand what files are available.",
    tool_calls=[
        make_tool_call("call_001", "list_files", {"path": ".", "pattern": "*"}),
    ],
)

# Second iteration: Read a specific file
MOCK_READ_FILE_CALL = make_llm_response(
    content="Now I'll read the main source file to analyze the code.",
    tool_calls=[
        make_tool_call(
            "call_002", "read_file", {"path": "raft.go", "start_line": 0, "max_lines": 500}
        ),
    ],
)

# Third iteration: Search for patterns
MOCK_SEARCH_CODE_CALL = make_llm_response(
    content="I'll search for vote handling logic to check for potential issues.",
    tool_calls=[
        make_tool_call(
            "call_003",
            "search_code",
            {"pattern": "RequestVote", "file_glob": "**/*.go", "context_lines": 3},
        ),
    ],
)

# Multiple tool calls in one response
MOCK_MULTIPLE_TOOL_CALLS = make_llm_response(
    content="I'll read multiple related files to understand the full picture.",
    tool_calls=[
        make_tool_call("call_004", "read_file", {"path": "raft.go"}),
        make_tool_call("call_005", "read_file", {"path": "log.go"}),
        make_tool_call("call_006", "list_files", {"path": "internal"}),
    ],
)

# Run command tool call
MOCK_RUN_COMMAND_CALL = make_llm_response(
    content="I'll check the file structure with tree command.",
    tool_calls=[
        make_tool_call("call_007", "run_command", {"command": "tree -L 2"}),
    ],
)


# ============================================================
# Bug Report Responses
# ============================================================

MOCK_BUG_REPORT_RESPONSE = make_llm_response(
    content="""After thorough analysis, I found a potential bug:

<bug_report>
File: vote_handler.go:145
Type: safety
Severity: critical
Description: The RequestVote handler does not verify that the candidate's log is at least as up-to-date as the voter's log before granting a vote. This violates the Raft safety property.
Root Cause: Missing log comparison check in vote granting logic. The code only compares terms but ignores log length and last log term.
Trigger Condition: A node with a stale log but higher term (due to network partition) can win an election and overwrite committed entries.
Impact: Committed entries can be lost when a stale node becomes leader, causing data loss and consistency violations.
</bug_report>

This is a serious safety violation that should be fixed immediately.
""",
)

MOCK_MULTIPLE_BUGS_RESPONSE = make_llm_response(
    content="""I found two potential bugs in the codebase:

<bug_report>
File: raft.go:234
Type: race_condition
Severity: high
Description: Concurrent access to the votedFor field without proper synchronization.
Root Cause: Missing mutex lock when updating votedFor during leader election.
Trigger Condition: Multiple RequestVote RPCs arriving simultaneously.
Impact: Node might grant votes to multiple candidates in the same term.
</bug_report>

<bug_report>
File: log.go:89
Type: liveness
Severity: medium
Description: Log compaction can block indefinitely if snapshot transfer fails.
Root Cause: No timeout on snapshot transfer during log compaction.
Trigger Condition: Network partition during snapshot transfer.
Impact: Node becomes unresponsive and cannot participate in consensus.
</bug_report>

Both issues should be addressed to ensure protocol correctness.
""",
)


# ============================================================
# Analysis Complete Response (No Bugs)
# ============================================================

MOCK_ANALYSIS_COMPLETE_RESPONSE = make_llm_response(
    content="""<analysis_complete>
Files Analyzed: raft.go, log.go, storage.go, node.go
Areas Checked: 
- Leader election and vote handling
- Log replication and commit logic
- Snapshot and compaction
- Term and index management

Conclusion: The implementation appears to follow the Raft specification correctly. 
Key safety invariants are properly maintained:
1. At most one leader per term
2. Log matching property is enforced
3. Leader completeness is ensured through proper vote checking
4. State machine safety is maintained

No bugs were found during this analysis. The code quality is high with proper 
error handling and synchronization.
</analysis_complete>
""",
)


# ============================================================
# Error Case Responses
# ============================================================

# Empty response (no content, no tool calls)
MOCK_EMPTY_RESPONSE = make_llm_response(content="")

# Malformed tool call (invalid JSON in arguments)
MOCK_MALFORMED_TOOL_CALL: dict[str, Any] = {
    "id": "chatcmpl-mock",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "anthropic/claude-sonnet-4",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": "{invalid json}",  # Invalid JSON
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
}

# Unknown tool call
MOCK_UNKNOWN_TOOL_CALL = make_llm_response(
    content="",
    tool_calls=[
        make_tool_call("call_unknown", "nonexistent_tool", {"arg": "value"}),
    ],
)


# ============================================================
# Sequence for Complete Analysis Flow
# ============================================================

# A typical analysis sequence: explore -> read -> search -> report
MOCK_ANALYSIS_SEQUENCE = [
    MOCK_LIST_FILES_CALL,
    MOCK_READ_FILE_CALL,
    MOCK_SEARCH_CODE_CALL,
    MOCK_BUG_REPORT_RESPONSE,
]

# Sequence that ends with no bugs found
MOCK_CLEAN_ANALYSIS_SEQUENCE = [
    MOCK_LIST_FILES_CALL,
    MOCK_READ_FILE_CALL,
    MOCK_ANALYSIS_COMPLETE_RESPONSE,
]

# Sequence with multiple iterations
MOCK_EXTENDED_ANALYSIS_SEQUENCE = [
    MOCK_LIST_FILES_CALL,
    MOCK_READ_FILE_CALL,
    MOCK_SEARCH_CODE_CALL,
    MOCK_READ_FILE_CALL,  # Read another file
    MOCK_SEARCH_CODE_CALL,  # Search again
    MOCK_MULTIPLE_BUGS_RESPONSE,
]


# ============================================================
# HTTP Error Responses
# ============================================================

MOCK_HTTP_401_RESPONSE = {
    "error": {
        "message": "Invalid API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}

MOCK_HTTP_429_RESPONSE = {
    "error": {
        "message": "Rate limit exceeded",
        "type": "rate_limit_error",
        "code": "rate_limit_exceeded",
    }
}

MOCK_HTTP_500_RESPONSE = {
    "error": {
        "message": "Internal server error",
        "type": "server_error",
        "code": "internal_error",
    }
}


# ============================================================
# Response Dictionary for Easy Access
# ============================================================

BASELINE_MOCK_RESPONSES = {
    # Tool calls
    "list_files": MOCK_LIST_FILES_CALL,
    "read_file": MOCK_READ_FILE_CALL,
    "search_code": MOCK_SEARCH_CODE_CALL,
    "run_command": MOCK_RUN_COMMAND_CALL,
    "multiple_tools": MOCK_MULTIPLE_TOOL_CALLS,
    # Analysis results
    "bug_report": MOCK_BUG_REPORT_RESPONSE,
    "multiple_bugs": MOCK_MULTIPLE_BUGS_RESPONSE,
    "analysis_complete": MOCK_ANALYSIS_COMPLETE_RESPONSE,
    # Error cases
    "empty": MOCK_EMPTY_RESPONSE,
    "malformed": MOCK_MALFORMED_TOOL_CALL,
    "unknown_tool": MOCK_UNKNOWN_TOOL_CALL,
    # Sequences
    "sequence_with_bug": MOCK_ANALYSIS_SEQUENCE,
    "sequence_clean": MOCK_CLEAN_ANALYSIS_SEQUENCE,
    "sequence_extended": MOCK_EXTENDED_ANALYSIS_SEQUENCE,
}
