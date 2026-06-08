# Consensus Bug Hunter (Agora)

[![ICML 2026](https://img.shields.io/badge/ICML-2026-blue)](https://icml.cc/)

**[Agora: Toward Autonomous Bug Detection in Production-Level Consensus Protocols with LLM Agents](https://openreview.net/forum?id=IU9dsf2LZA)**  
*Forty-third International Conference on Machine Learning (ICML), 2026*

A multi-agent system for automatically discovering bugs in distributed consensus protocol implementations, powered by Claude Agent SDK.

## Overview

This system uses Claude-powered agents to:
- Generate creative attack scenarios targeting safety, liveness, and agreement violations
- Analyze repository test structures and generate compliant test code
- Learn from bug patterns through persistent memory
- Support both CFT and BFT protocols with appropriate constraints

## Architecture

### Claude Agent SDK Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Orchestrator (Main Controller)               │
│  - Coordinates the entire bug hunting workflow                      │
│  - Manages automated iteration loop (runs forever until Ctrl+C)     │
│  - Implements Self-Healing reflection loop (up to 5 retries)        │
│  - OpenRouter API + Prompt Caching + Extended Thinking              │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Auto-invokes
              ┌──────────────┴──────────────┐
              ▼                             ▼
       ┌───────────────┐           ┌───────────────┐
       │strategy-agent │           │testgen-agent  │
       │Extended Think │           │Extended Think │
       │ Self-Healing  │           │ Self-Healing  │
       │Creative Attack│           │Code Generation│
       └───────────────┘           └───────────────┘
              │                             │
              └──────────────┬──────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 MCP Memory Server (Cross-Session Persistence)       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │PatternMemory│    │RepoKnowledge│    │ TestHistory │              │
│  │(Bug Patterns)    │(Repo Structure)   │(Test Records)│             │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Features

#### Extended Thinking
Claude's native `max_thinking_tokens` enables deeper reasoning for complex attack scenarios.

#### Prompt Caching
OpenRouter's `cache_control` caches system prompts and memory context (5-minute TTL, max 4 breakpoints).

#### Self-Healing Reflection Loop
Automatic error detection and code regeneration (up to 5 retries per task).

#### PostToolUse Hooks
Smart error detection that injects helpful suggestions for common issues.

#### Autonomous Problem Solving
Agents can independently investigate and fix issues using available tools (Bash, Read, Grep, Glob) without waiting for external suggestions.

#### Bug Exploitation Mode
When a bug is confirmed, the system automatically enters **Bug Exploitation Mode** to discover related vulnerabilities:
- Strategy Agent analyzes the confirmed bug's root cause and attack pattern
- Generates creative variations and related attack scenarios
- Explores similar vulnerabilities in related components
- Up to 5 exploitation attempts per confirmed bug (configurable via `MAX_BUG_EXPLOITATION_ATTEMPTS`)

### Agent Responsibilities

| Agent | Input | Output | Responsibility |
|-------|-------|--------|----------------|
| **Strategy Agent** | Pattern Memory, Protocol Code | Attack Scenario | Generate creative attack scenarios using CFT/BFT constraints |
| **TestGen Agent** | Attack Scenario, Repo Knowledge | Test Code + Results | Generate and execute tests matching repo style |

## Supported Protocols

| Protocol | Type | Language | Description |
|----------|------|----------|-------------|
| raft | CFT | Go | etcd's Raft implementation |
| raft-rs | CFT | Rust | TiKV's Raft implementation |
| hashicorp-raft | CFT | Go | HashiCorp's Raft |
| efficient-epaxos | CFT | Go | Efficient EPaxos |
| phxpaxos | CFT | C++ | Tencent's Paxos |
| zookeeper | CFT | Java | Apache ZooKeeper (ZAB) |
| fabric | CFT | Go | Hyperledger Fabric |
| cometbft | BFT | Go | CometBFT (Tendermint) |
| hotstuff | BFT | Go | HotStuff BFT |
| sui | BFT | Rust | Sui blockchain consensus |
| library | BFT | Java | BFT-SMaRt library |

## Skill (Agent-Native Interface)

Besides the Python framework, this project also provides a self-contained agent skill that works with any coding agent (Codex, Claude Code, Gemini, Cursor, etc.).

### Install

```bash
SKILL_BASE_URL=https://github.com/lebronlambert/Agora/tree/main npx skill skills/agora-bug-detection
```

The skill auto-discovers the protocol type (CFT/BFT), language, and structure — no configuration needed. See [`skill/README.md`](skill/README.md) for details.

## Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r agent/requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=your_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4

# Extended Thinking (Claude's native reasoning)
MAX_THINKING_TOKENS=16000

# Prompt Caching
ENABLE_PROMPT_CACHING=true

# Agent Settings
MAX_REFLECTION_RETRIES=5
MAX_TURNS=10
MAX_BUDGET_USD=10.0

# Bug Exploitation Mode
MAX_BUG_EXPLOITATION_ATTEMPTS=5

# Test Settings
TEST_TIMEOUT=300
```

## Usage

### Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Validate API configuration before running (recommended)
python agent/validate_api.py

# List available protocols
python -m agent --list

# Run for a single protocol (10 iterations by default)
python -m agent --repo raft

# Run with specific number of iterations
python -m agent --repo raft --iterations 20

# Run indefinitely until Ctrl+C
python -m agent --repo raft --forever
```

### Advanced Usage

```bash
# Run for all protocols in parallel (4 processes by default)
python -m agent --all --parallel 4

# Run ALL protocols FOREVER (until Ctrl+C)
python -m agent --all --forever --parallel 9

# Show test history statistics
python -m agent --stats

# Show stats for specific protocol
python -m agent --stats --repo raft

# Verbose logging
python -m agent --repo raft --verbose
```

### Maintenance Commands

```bash
# Validate API configuration (cost: < $0.01)
python agent/validate_api.py

# Clean up pattern memory files
python agent/scripts/cleanup_memory.py --execute

# Run the test suite
python agent/tests/run_tests.py
# Or using pytest directly
pytest agent/tests/ -v
```

## How It Works

### 1. Strategy Agent - Creative Attack Generation

The Strategy Agent generates attack scenarios through creative thinking, not fixed patterns:

```
<thinking>
[Understanding the Protocol]
...I observe that the key mechanism of this protocol is...
...It assumes...

[Analyzing Known Patterns]
...A pattern in Pattern Memory describes...
...This approach might manifest in the current protocol as...

[Identifying Suspicious Points]
...I notice that at some point...
...There seems to be no check for...

[Creative Reasoning]
...If I construct a scenario where...
...This might lead to...
</thinking>

<attack_scenario>
Name: DuplicateParentCertificateStakeAmplification
Target Component: Header Validator
Attack Steps:
1. Create a valid Certificate C
2. Construct Header H, placing C's Digest repeatedly in the parents list
3. Validator computes: stake += committee.stake(parent.author) * repetition_count
4. Result: 1 vote is counted as multiple votes, forging a majority
</attack_scenario>
```

**CFT vs BFT Constraints:**

- **CFT Protocols**: Only crash/network faults allowed
  - Node crashes, restarts
  - Network partitions, delays, message drops
  - NO malicious behavior

- **BFT Protocols**: All fault types allowed
  - All CFT faults
  - Plus: equivocation, byzantine messages, selective broadcast, etc.

### 2. TestGen Agent - Code Generation with Self-Healing

```
Generate Test ──▶ Run Test ──▶ Pass? ──Yes──▶ Report Result
                               │
                               │ No (Compile/Runtime Error)
                               ▼
                        Analyze Error
                               │
                               ▼
                        Auto-Fix (up to 5 retries)
                               │
                               ▼
                        Re-run Test
```

### 3. Bug Exploitation Mode - Maximizing Bug Discovery

When a bug is confirmed, the system automatically enters **Bug Exploitation Mode** to find related vulnerabilities:

```
                    ┌─────────────────────────────────────────┐
                    │         Bug Confirmed!                  │
                    └──────────────────┬──────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │     Enter Bug Exploitation Mode         │
                    │     (max 5 attempts by default)         │
                    └──────────────────┬──────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │  Root Cause     │    │   Variant       │    │   Pattern       │
     │  Analysis       │    │   Generation    │    │   Propagation   │
     │                 │    │                 │    │                 │
     │  Where else     │    │  Different      │    │  Similar bugs   │
     │  might this     │    │  entry points,  │    │  in related     │
     │  assumption     │    │  timing, edge   │    │  components?    │
     │  be violated?   │    │  cases          │    │                 │
     └─────────────────┘    └─────────────────┘    └─────────────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │   Strategy Agent generates new scenario │
                    │   based on confirmed bug context        │
                    └──────────────────┬──────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │   TestGen Agent implements & executes   │
                    └──────────────────┬──────────────────────┘
                                       │
                           ┌───────────┴───────────┐
                           │                       │
                           ▼                       ▼
                  ┌─────────────────┐    ┌─────────────────┐
                  │  New Bug Found  │    │   No Bug        │
                  │  Record & Log   │    │   Try Again     │
                  └─────────────────┘    └─────────────────┘
```

**Key Exploitation Strategies:**

- **Root Cause Analysis**: Identify fundamental assumptions being violated
- **Variant Generation**: Test different entry points, timing, message orders
- **Pattern Propagation**: Look for similar bugs in related protocol components
- **Deeper Exploration**: Escalate from liveness to safety violations

### 4. Memory Systems

**Pattern Memory** (`agent/pattern memory/`):
- Stores confirmed bug patterns (CFT/BFT separated)
- Enables cross-protocol learning
- Used as inspiration, not rigid templates

**Repo Knowledge** (`agent/repo_knowledge/`):
- Cached repository analysis
- Test structure, coding style, helper functions
- Updated as agent learns

**Test History** (`agent/test_history/`):
- Complete test execution records
- Bug confirmations and false positives
- Per-protocol folders

## Project Structure

```
agent/
├── __init__.py
├── __main__.py              # CLI entry point
├── validate_api.py          # API validation script
├── core/                    # Core agent framework
│   ├── orchestrator.py      # Main controller + reflection loop
│   ├── tool_agent.py        # Tool-calling agent framework
│   ├── executor.py          # Code executor for self-healing
│   ├── prompt_builder.py    # Centralized prompt construction
│   ├── result_parser.py     # LLM response parsing logic
│   ├── report_generator.py  # Bug report generation
│   ├── strategies.py        # Strategy interfaces & data types
│   └── strategy_impl.py     # Strategy implementations
├── ablation/                # Ablation experiment framework
│   ├── base.py              # Base experiment class
│   ├── runner.py            # CLI runner for experiments
│   ├── config.py            # Experiment configuration
│   └── experiments/         # 7 experiment implementations
│       ├── no_ablation.py   # Control group (full system)
│       ├── no_pattern.py    # Disable pattern memory
│       ├── no_exploitation.py   # Disable bug exploitation
│       ├── stateless.py     # Disable state management
│       ├── no_strategy.py   # Random strategy (no LLM)
│       ├── no_type_distinction.py  # No BFT/CFT distinction
│       └── no_testgen_loop.py      # No test fix loop
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuration loading
│   └── protocols.yaml       # Protocol definitions
├── prompts/
│   ├── __init__.py
│   ├── strategy.py          # Strategy Agent prompt
│   ├── testgen.py           # TestGen Agent prompt
│   └── constraints.py       # CFT/BFT constraints
├── mcp_servers/
│   ├── __init__.py
│   └── memory_server.py     # Memory MCP Server
├── memory/
│   ├── __init__.py
│   ├── pattern_memory.py    # Bug pattern storage
│   ├── repo_knowledge.py    # Repo structure cache
│   └── test_history.py      # Test case records
├── tools/
│   ├── __init__.py
│   ├── test_runner.py       # Multi-language test execution
│   └── mcp_server.py        # MCP server tools
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── pytest.ini           # Pytest configuration
│   ├── test_*.py            # Unit and integration tests
│   └── mocks/               # Mock LLM responses
├── data/
│   ├── pattern_memory/      # Bug patterns (CFT/BFT)
│   ├── repo_knowledge/      # Cached repo analysis (JSON)
│   └── test_history/        # Test records per protocol (JSON)
└── scripts/                 # Utility scripts
```

## Testing

The project includes a comprehensive test suite:

```bash
# Run all tests
pytest agent/tests/ -v

# Run specific test file
pytest agent/tests/test_orchestrator.py -v

# Run with coverage
pytest agent/tests/ --cov=agent --cov-report=html

# Run only unit tests (skip E2E)
pytest agent/tests/ -v --ignore=agent/tests/test_e2e.py

# Run API connectivity tests
pytest agent/tests/test_api_connectivity.py -v
```

**Test Categories:**
- `test_executor.py` - Code execution and process management
- `test_memory_modules.py` - Pattern, Learning, Repo Knowledge, Test History
- `test_orchestrator.py` - Workflow coordination and agent invocation
- `test_parsers.py` - Attack scenario and validation result parsing
- `test_tools.py` - Tool functionality tests
- `test_api_connectivity.py` - OpenRouter API validation
- `test_e2e.py` - End-to-end integration tests

## Adding New Protocols

Edit `agent/config/protocols.yaml`:

```yaml
protocols:
  new-protocol:
    path: ./new-protocol
    type: cft  # or bft
    language: go  # go, rust, java, cpp
    fault_tolerance: "(n-1)/2"  # or "(n-1)/3" for BFT
    description: "Description here"
    test_pattern: "*_test.go"
    test_command: "go test -v -run {test_name}"
    # Optional: issue tracker configuration
    issue_tracker:
      type: github  # or jira
      url: "https://github.com/org/repo/issues"
```

## Bug Categories

| Category | Description |
|----------|-------------|
| **Safety** | Different nodes commit different values for the same slot |
| **Liveness** | Cluster cannot make progress (blocked indefinitely) |
| **Agreement** | Nodes disagree on the committed state |

## Fault Types

**CFT Protocols:**
- `node_crash` / `node_restart`
- `network_partition` / `network_delay`
- `message_drop` / `message_reorder`
- `disk_failure`

**BFT Protocols (additional):**
- `byzantine_message`
- `equivocation`
- `invalid_signature`
- `selective_send`

## Bug Reports

When a bug is discovered, the system generates a markdown report in:
```
bug_reports/{protocol_name}/{timestamp}_{bug_name}.md
```

The report includes:
- Summary and vulnerability hypothesis
- Target component
- Attack scenario (preconditions, steps, expected behavior)
- Test code and output
- Impact assessment

## Error Handling

The system is designed for continuous operation:

| Component | Potential Issue | Recovery Strategy |
|-----------|-----------------|-------------------|
| **Embedding Store** | API timeout | Exponential backoff, fallback to zero embedding |
| **Test Execution** | Process hang | Timeout kill, skip iteration |
| **Code Generation** | Compile error | Self-healing reflection loop (5 retries) |
| **Memory Files** | Corruption | Atomic writes, file locking |
| **LLM Calls** | Parse errors | Retry with adjusted prompts |
| **Process Tree** | Zombie processes | Process group kill with SIGKILL |

## Troubleshooting

### Common Issues

**API Key Issues:**
```bash
# Validate your API configuration
python agent/validate_api.py
```

**Memory Cleanup:**
```bash
# Remove empty or corrupted pattern memory entries
python agent/scripts/cleanup_memory.py --execute
```

**Test Failures:**
```bash
# Run with verbose output
python -m agent --repo raft --verbose
```

**Process Stuck:**
- The system uses `start_new_session=True` for subprocess isolation
- Processes are killed with `SIGKILL` on timeout
- Use Ctrl+C to gracefully stop the workflow

## Citation

If you use this work, please cite:

```bibtex
@inproceedings{
liu2026agora,
title={Agora: Toward Autonomous Bug Detection in Production-Level Consensus Protocols with {LLM} Agents},
author={Xiang Liu, Sa Song, Zhaowei Zhang, Huiying Lan, Jason Zeng, Ming Wu, Michael Heinrich, Yong Sun, Ceyao Zhang},
booktitle={Forty-third International Conference on Machine Learning},
year={2026},
url={https://openreview.net/forum?id=IU9dsf2LZA}
}
```

## License

MIT
