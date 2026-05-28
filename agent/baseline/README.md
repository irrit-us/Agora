# Baseline ReAct Agent

A simplified single-agent approach for finding bugs in consensus protocol implementations using the ReAct (Reasoning + Acting) pattern.

## Overview

The Baseline ReAct Agent provides a minimal, straightforward implementation for consensus protocol bug hunting. It serves as a **baseline for comparison** with more sophisticated multi-agent architectures (such as the Strategy + TestGen orchestrator).

### Key Characteristics

- **Single Agent**: One agent handles all analysis tasks
- **ReAct Pattern**: Iterative loop of Thought → Action → Observation
- **Minimal Tools**: Only 4 essential tools for code analysis
- **No Memory System**: Fresh analysis each run, no pattern learning
- **Direct Code Reading**: Focuses on reading and understanding source code

### ReAct Loop

```
┌─────────────────────────────────────────────────┐
│                  ReAct Loop                     │
├─────────────────────────────────────────────────┤
│  1. Thought   → Analyze what's known            │
│  2. Action    → Use a tool to gather info       │
│  3. Observation → Process tool output           │
│  4. Repeat until bugs found or complete         │
└─────────────────────────────────────────────────┘
```

## Architecture

### Module Structure

```
agent/baseline/
├── __init__.py       # Public API exports
├── react_agent.py    # Main agent class (BaselineReActAgent)
├── prompts.py        # System prompts and repository configs
├── tools.py          # Tool implementations (4 tools)
├── runner.py         # CLI interface
└── README.md         # This file
```

### Core Components

| File | Description |
|------|-------------|
| `react_agent.py` | Main `BaselineReActAgent` class with ReAct loop implementation |
| `prompts.py` | System prompts, repository hints, and core file definitions |
| `tools.py` | Tool factory `create_baseline_tools()` with 4 tools |
| `runner.py` | CLI entry point and result handling |

### Data Classes

**ToolCallRecord** - Record of a single tool invocation:
```python
@dataclass
class ToolCallRecord:
    name: str           # Tool name
    arguments: dict     # Arguments passed
    result: str         # Tool output
    duration_ms: int    # Execution time
```

**ReActStep** - Record of one ReAct iteration:
```python
@dataclass
class ReActStep:
    iteration: int              # Iteration number (1-indexed)
    thought: str                # LLM's reasoning
    tool_calls: list[ToolCallRecord]  # Tools invoked
    timestamp: str              # ISO format timestamp
```

**BugReport** - Represents a discovered bug:
```python
@dataclass
class BugReport:
    file: str           # File path
    line: int | None    # Line number
    bug_type: str       # Bug category
    severity: str       # critical/high/medium/low
    description: str    # What the bug is
    root_cause: str     # Why it exists
    trigger_condition: str  # How to trigger
    impact: str         # Consequences
```

**AnalysisResult** - Complete analysis output:
```python
@dataclass
class AnalysisResult:
    repo_name: str
    model: str
    bugs_found: list[BugReport]
    files_analyzed: list[str]
    iterations: int
    tool_calls: int
    duration_ms: int
    tokens_used: int
    final_response: str
    error: str | None
    execution_trace: list[ReActStep]  # Full ReAct execution trace
```

## Supported Repositories

| Repository | Language | Description | Core Files |
|------------|----------|-------------|------------|
| `raft` | Go | etcd/raft consensus | `raft.go`, `log.go`, `storage.go`, `node.go`, `tracker/progress.go` |
| `sui` | Rust | Mysticeti DAG-based BFT | `dag_state.rs`, `linearizer.rs`, `commit_syncer.rs`, `block_manager.rs` |
| `hotstuff` | Go | HotStuff BFT protocol | `chainedhotstuff.go`, `fasthotstuff.go`, `synchronizer.go`, `voter.go` |
| `efficient-epaxos` | Go | Egalitarian Paxos | `epaxos.go`, `epaxos-exec.go` |

## Tools

The agent has access to 4 read-only tools:

### 1. `read_file`
Read file content with line numbers.

```python
read_file(
    path: str,              # Relative to repo root
    start_line: int = 0,    # Starting line (0-indexed)
    max_lines: int = 500    # Max lines to read
) -> str
```

### 2. `search_code`
Search for patterns using ripgrep.

```python
search_code(
    pattern: str,                    # Regex pattern
    file_glob: str = "**/*",         # File filter
    context_lines: int = 2,          # Context before/after
    max_results: int = 50            # Max matches per file
) -> str
```

### 3. `run_command`
Execute read-only shell commands.

```python
run_command(
    command: str,           # Shell command
    timeout: float = 60.0   # Timeout in seconds
) -> str
```

**Allowed commands**: `ls`, `tree`, `cat`, `head`, `tail`, `find`, `du`, `wc`, `file`, `stat`, `grep`, `rg`, `awk`, `sed`

### 4. `list_files`
List directory contents.

```python
list_files(
    path: str = ".",     # Directory path
    pattern: str = "*"   # Glob pattern
) -> str
```

## Usage

### Programmatic API

```python
from agent.baseline import BaselineReActAgent
from agent.config.settings import load_settings

# Load configuration from .env
settings = load_settings()

# Create agent
agent = BaselineReActAgent(
    model=settings.llm_model,
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
    repo_path="/path/to/raft",
    max_iterations=30,
)

# Run analysis
result = await agent.analyze(
    repo_name="raft",
    target_files=["raft.go", "log.go"],
)

# Process results
print(f"Found {len(result.bugs_found)} bugs")
for bug in result.bugs_found:
    print(f"  [{bug.severity}] {bug.file}:{bug.line} - {bug.description}")
```

### Command Line Interface

```bash
# Analyze with pre-defined core files
python -m agent.baseline.runner --repo raft

# Specify target files
python -m agent.baseline.runner --repo raft --target raft.go log.go

# Verbose logging
python -m agent.baseline.runner --repo sui --verbose

# Custom model and iterations
python -m agent.baseline.runner --repo hotstuff --model openai/gpt-4o --max-iterations 50

# Show help
python -m agent.baseline.runner --help
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--repo` | Repository to analyze (required) | - |
| `--target` | Specific files to focus on | Core files |
| `--model` | LLM model to use | From settings |
| `--max-iterations` | Maximum ReAct iterations | 30 |
| `--output-dir` | Directory for results | `agent/data/baseline_results` |
| `--verbose`, `-v` | Enable debug logging | False |

## Output Format

### Bug Reports

The agent outputs bugs in XML format:

```xml
<bug_report>
File: raft.go:234
Type: race condition
Severity: high
Description: Concurrent access to leader state without proper synchronization
Root Cause: Missing lock acquisition before reading volatileState
Trigger Condition: Network partition during leader election
Impact: Split brain scenario with two leaders
</bug_report>
```

### JSON Results

Results are automatically saved to `agent/data/baseline_results/` with filenames like:
```
baseline_{repo}_{model}_{timestamp}.json
```

Example JSON structure:
```json
{
  "repo_name": "raft",
  "model": "anthropic/claude-sonnet-4",
  "bugs_found": [
    {
      "file": "raft.go",
      "line": 234,
      "type": "race condition",
      "severity": "high",
      "description": "...",
      "root_cause": "...",
      "trigger_condition": "...",
      "impact": "..."
    }
  ],
  "files_analyzed": ["raft.go", "log.go"],
  "iterations": 15,
  "tool_calls": 42,
  "duration_ms": 180000,
  "tokens_used": 0,
  "error": null,
  "execution_trace": [
    {
      "iteration": 1,
      "thought": "Let me start by exploring the repository structure...",
      "tool_calls": [
        {
          "name": "list_files",
          "arguments": {"path": "."},
          "result": "raft.go\nlog.go\n...",
          "duration_ms": 12
        }
      ],
      "timestamp": "2026-01-15T10:30:45.123456+00:00"
    }
  ],
  "timestamp": "20250115_143022",
  "version": "0.1.0"
}
```

### Markdown Report

A human-readable Markdown report is also generated alongside the JSON file:
```
baseline_{repo}_{model}_{timestamp}.md
```

The Markdown report includes:
- Summary statistics (duration, iterations, tool calls, bugs found)
- Full execution trace with agent thoughts and tool observations
- Detailed bug reports with all fields
- List of files analyzed

### JSONL Streaming Trace

For memory-efficient analysis and crash recovery, the CLI uses streaming JSONL output:
```
baseline_{repo}_{model}_{timestamp}.jsonl
```

Each line is a valid JSON object:
```jsonl
{"type": "header", "repo_name": "raft", "model": "...", "started_at": "..."}
{"type": "step", "iteration": 1, "thought": "...", "tool_calls": [...], "timestamp": "..."}
{"type": "step", "iteration": 2, "thought": "...", "tool_calls": [...], "timestamp": "..."}
{"type": "footer", "iterations": 15, "tool_calls": 42, "bugs_found": 2, "duration_ms": 180000}
```

Benefits:
- **Memory efficient**: Steps are written immediately, not accumulated in memory
- **Crash recovery**: Partial traces are preserved if analysis is interrupted
- **Real-time monitoring**: Watch progress by tailing the file (`tail -f *.jsonl`)
- **Tool result truncation**: Long tool outputs are truncated (default: 8000 chars)

To load a trace programmatically:
```python
from agent.baseline import load_trace_from_jsonl

steps = load_trace_from_jsonl("path/to/trace.jsonl")
for step in steps:
    print(f"Iteration {step['iteration']}: {len(step['tool_calls'])} tools")
```

## Configuration

### Agent Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | str | - | LLM model identifier (e.g., `anthropic/claude-sonnet-4`) |
| `api_key` | str | - | OpenRouter API key |
| `base_url` | str | - | API base URL |
| `repo_path` | Path | - | Repository to analyze |
| `max_iterations` | int | 30 | Maximum ReAct loop iterations |
| `max_tokens` | int | 16000 | Max tokens per LLM response |
| `timeout` | float | 120.0 | Request timeout in seconds |

### Environment Variables

Set in `.env` file:
```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4
```

## Analysis Workflow

The agent follows a structured 4-phase workflow:

### Phase 1: Reconnaissance
- Explore directory structure with `list_files`
- Identify where core logic lives

### Phase 2: Deep Reading
- Read source files thoroughly with `read_file`
- Understand data structures and control flow
- Identify invariants the code maintains

### Phase 3: Independent Analysis
- Form hypotheses about potential bugs
- Question code assumptions
- Trace data flows

### Phase 4: Hypothesis Testing
- Verify suspicions by reading more code
- Follow function calls across files
- Build complete mental model

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - bugs found |
| 1 | Success - no bugs found |
| 2 | Error during analysis |
| 130 | Interrupted by user (Ctrl+C) |

## Comparison with Multi-Agent Orchestrator

| Feature | Baseline Agent | Multi-Agent Orchestrator |
|---------|----------------|--------------------------|
| Agents | 1 | Multiple (Strategy, TestGen, etc.) |
| Memory | None | Persistent pattern memory |
| Strategy | Ad-hoc | Generated and refined |
| Tools | 4 basic tools | Extended tool set |
| Learning | None | Cross-session learning |
| Complexity | Low | High |
| Use Case | Quick analysis, baseline metrics | Production bug hunting |

## Development

### Running Tests

```bash
# Run baseline agent tests
pytest agent/tests/test_baseline_*.py -v

# Run with coverage
pytest agent/tests/test_baseline_*.py --cov=agent.baseline
```

### Adding a New Repository

1. Add repository path to `REPO_PATHS` in `runner.py`
2. Add core files to `REPO_CORE_FILES` in `prompts.py`
3. Add repository hints to `_REPO_HINTS` in `prompts.py`

## Version

- **Version**: 0.1.0
- **Author**: Consensus Bug Hunter Authors
