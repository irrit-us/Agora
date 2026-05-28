"""
System prompts for Baseline ReAct Agent.

This module contains the prompts used to guide the baseline agent
in analyzing consensus protocol implementations for bugs.

The prompts are designed to be:
- Direct: Focus on reading code and finding bugs
- Structured: Clear output format for bug reports
- Protocol-aware: Include hints for specific repositories
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# System Prompt
# =============================================================================

BASELINE_SYSTEM_PROMPT: Final[str] = """\
You are a consensus protocol bug hunter. Your task is to read and analyze \
consensus protocol source code to find potential bugs.

## Your Role

You are a **code reader and analyzer**, not a developer.

- DO read code thoroughly and reason about its correctness
- DO search for suspicious patterns and trace data flows
- DO report potential bugs with detailed analysis
- DO NOT suggest fixes (just identify the problem)
- DO NOT write test code or attempt to verify bugs by running tests

## Autonomous Discovery

You are expected to **independently discover** potential bugs through your own analysis.

- **No hints given**: You will NOT be told what types of bugs to look for
- **Read and understand**: Your primary job is to deeply understand the code
- **Form your own hypotheses**: Based on your reading, develop theories about what might be wrong
- **Creative thinking**: Look for issues that others might miss - be original
- **Trust your reasoning**: If something looks suspicious to you, investigate it

The goal is for YOU to find bugs through careful code reading and logical reasoning, not to match against a checklist of known patterns. Approach this like a security researcher discovering novel vulnerabilities.

## Available Tools

You have 3 tools for code analysis:

1. **list_files(path)**: Explore repository structure. Start here to understand the codebase layout.
2. **read_file(path, start_line, max_lines)**: Read source code with line numbers. This is your primary tool.
3. **search_code(pattern, file_glob)**: Search for code patterns using regex. Use to find specific functions, variables, or suspicious patterns.

Use these tools systematically: explore -> read -> search -> analyze.

## Your Approach

Use the ReAct (Reasoning + Acting) pattern:
1. **Thought**: Analyze what you know and what you need to investigate
2. **Action**: Use a tool to gather information
3. **Observation**: Analyze the tool's output
4. Repeat until you find bugs or conclude the code is safe

## Analysis Workflow

### Phase 1: Reconnaissance
- Use list_files to understand the directory structure
- Identify where the core logic lives by exploring the codebase

### Phase 2: Deep Reading
- Read source files thoroughly and completely
- Understand the data structures, state transitions, and control flow
- Identify the invariants the code is trying to maintain

### Phase 3: Independent Analysis
- Based on YOUR reading, identify what could go wrong
- Think critically about the code - what assumptions does it make?
- Trace data flows and reason about correctness yourself

### Phase 4: Hypothesis Testing
- When you suspect something, read more code to verify
- Follow function calls, check all callers and callees
- Build your own mental model of how the system works

## Output Format

When you find a potential bug, report it as:

<bug_report>
File: [filename:line_number]
Type: [your own categorization based on your analysis]
Severity: [your assessment]
Description: [Clear description of the bug]
Root Cause: [Why this bug exists]
Trigger Condition: [How to trigger this bug]
Impact: [What happens if triggered]
</bug_report>

When you finish analyzing without finding bugs:

<analysis_complete>
Files Analyzed: [list of files]
Areas Checked: [what you looked for]
Conclusion: [why you believe the code is safe, or areas that need more investigation]
</analysis_complete>

## Important Guidelines

- **Read first, judge later**: Thoroughly read the code before forming opinions
- **Think independently**: Develop your own understanding of what could go wrong
- **Be creative**: Don't limit yourself to known bug patterns - discover new ones
- **Question everything**: Challenge the code's assumptions through your own reasoning
- **Follow the evidence**: Let the code guide your investigation, not preconceptions

You are an expert code auditor. Trust your own analysis and judgment.

Now, analyze the code and find bugs.
"""


# =============================================================================
# Repository Core Files
# =============================================================================

# Pre-defined core files for each repository
# These are the most important files to analyze for consensus bugs
REPO_CORE_FILES: Final[dict[str, list[str]]] = {
    # ==========================================================================
    # CFT Protocols
    # ==========================================================================
    "raft": [
        # Core Raft state machine - leader election, log replication, commit
        "raft.go",
        # Log management - entries, compaction, snapshots
        "log.go",
        # Persistent storage interface
        "storage.go",
        # Node lifecycle and message handling
        "node.go",
        # Follower progress tracking
        "tracker/progress.go",
    ],
    "raft-rs": [
        # Core Raft state machine implementation
        "src/raft.rs",
        # Log management
        "src/raft_log.rs",
        # Storage trait and MemStorage
        "src/storage.rs",
        # RawNode wrapper for Raft
        "src/raw_node.rs",
    ],
    "hashicorp-raft": [
        # Core Raft implementation
        "raft.go",
        # Log entry definitions
        "log.go",
        # FSM interface
        "fsm.go",
        # Snapshot interface
        "snapshot.go",
        # Node state management
        "state.go",
    ],
    "dragonboat": [
        # Raft protocol interface
        "internal/raft/peer.go",
        # Log entry management
        "internal/raft/logentry.go",
        # Raft state machine core
        "internal/raft/raft.go",
        # NodeHost main interface
        "nodehost.go",
    ],
    "efficient-epaxos": [
        # Core EPaxos - PreAccept, Accept, Commit, Recovery all in one file
        "src/epaxos/epaxos.go",
        # Execution and dependency resolution
        "src/epaxos/epaxos-exec.go",
    ],
    "ratis": [
        # Server state management
        "ratis-server/src/main/java/org/apache/ratis/server/impl/ServerState.java",
        # Leader state implementation
        "ratis-server/src/main/java/org/apache/ratis/server/impl/LeaderStateImpl.java",
        # Segmented Raft log
        "ratis-server/src/main/java/org/apache/ratis/server/raftlog/segmented/SegmentedRaftLog.java",
    ],
    "zookeeper": [
        # Leader role implementation
        "zookeeper-server/src/main/java/org/apache/zookeeper/server/quorum/Leader.java",
        # Follower role implementation
        "zookeeper-server/src/main/java/org/apache/zookeeper/server/quorum/Follower.java",
        # Fast leader election
        "zookeeper-server/src/main/java/org/apache/zookeeper/server/quorum/FastLeaderElection.java",
        # Quorum peer coordination
        "zookeeper-server/src/main/java/org/apache/zookeeper/server/quorum/QuorumPeer.java",
    ],
    "fabric": [
        # Consensus chain management
        "orderer/consensus/etcdraft/chain.go",
        # Raft node wrapper
        "orderer/consensus/etcdraft/node.go",
        # WAL and snapshot storage
        "orderer/consensus/etcdraft/storage.go",
    ],
    # ==========================================================================
    # BFT Protocols
    # ==========================================================================
    "library": [
        # Service replica main class
        "src/main/java/bftsmart/tom/ServiceReplica.java",
        # Core consensus algorithm
        "src/main/java/bftsmart/consensus/Consensus.java",
        # TOM layer core logic
        "src/main/java/bftsmart/tom/core/TOMLayer.java",
    ],
    "cometbft": [
        # Core state machine
        "consensus/state.go",
        # Consensus reactor
        "consensus/reactor.go",
        # Vote structure
        "types/vote.go",
        # Block structure
        "types/block.go",
    ],
    "hotstuff": [
        # Chained HotStuff protocol rules
        "protocol/rules/chainedhotstuff.go",
        # Fast HotStuff variant
        "protocol/rules/fasthotstuff.go",
        # View synchronization
        "protocol/synchronizer/synchronizer.go",
        # Vote handling
        "protocol/consensus/voter.go",
        # Block proposal
        "protocol/consensus/proposer.go",
        # Commit logic
        "protocol/consensus/committer.go",
    ],
    "AlephBFT": [
        # DAG main module
        "consensus/src/dag/mod.rs",
        # Unit module
        "consensus/src/units/mod.rs",
        # Unit creator
        "consensus/src/creation/creator.rs",
        # Consensus main module
        "consensus/src/consensus/mod.rs",
    ],
    "aptos-core": [
        # Round manager
        "consensus/src/round_manager.rs",
        # Safety rules
        "consensus/safety-rules/src/safety_rules.rs",
    ],
    "sui": [
        # DAG state management - block acceptance, ancestors
        "consensus/core/src/dag_state.rs",
        # Commit ordering - linearization of DAG
        "consensus/core/src/linearizer.rs",
        # Commit synchronization
        "consensus/core/src/commit_syncer.rs",
        # Block handling and validation
        "consensus/core/src/block_manager.rs",
    ],
}


def get_core_files(repo_name: str) -> list[str]:
    """
    Get the pre-defined core files for a repository.

    Args:
        repo_name: Name of the repository.

    Returns:
        List of core file paths, or empty list if unknown repo.
    """
    return REPO_CORE_FILES.get(repo_name, [])


# =============================================================================
# Repository-Specific Hints
# =============================================================================

_REPO_HINTS: Final[dict[str, str]] = {
    # ==========================================================================
    # CFT Protocols
    # ==========================================================================
    "raft": """\
## Repository: etcd/raft (Go)

This is the Raft consensus implementation used by etcd.

### Suggested Starting Points
- `raft.go`: Core Raft state machine logic
- `log.go`: Log management and compaction
- `storage.go`: Persistent storage interface
- `node.go`: Node lifecycle and message handling

Explore the codebase and discover potential issues through your own analysis.
""",
    "raft-rs": """\
## Repository: raft-rs (Rust)

This is TiKV's Raft implementation in Rust.

### Suggested Starting Points
- `src/raft.rs`: Core Raft state machine implementation
- `src/raft_log.rs`: Log management
- `src/storage.rs`: Storage trait and MemStorage
- `src/raw_node.rs`: RawNode wrapper for Raft

Explore the codebase and discover potential issues through your own analysis.

### Build Notes
- Tests are in `harness/tests/` directory
- Use `cargo test -p harness <test_name>` to run tests
""",
    "hashicorp-raft": """\
## Repository: HashiCorp Raft (Go)

This is HashiCorp's Raft implementation used by Consul, Nomad, and Vault.

### Suggested Starting Points
- `raft.go`: Core Raft implementation
- `log.go`: Log entry definitions
- `fsm.go`: FSM interface
- `snapshot.go`: Snapshot interface
- `state.go`: Node state management

Explore the codebase and discover potential issues through your own analysis.
""",
    "dragonboat": """\
## Repository: Dragonboat (Go)

This is a high-performance multi-group Raft implementation.

### Suggested Starting Points
- `internal/raft/peer.go`: Raft protocol interface
- `internal/raft/logentry.go`: Log entry management
- `internal/raft/raft.go`: Raft state machine core
- `nodehost.go`: NodeHost main interface

Explore the codebase and discover potential issues through your own analysis.

### Notes
- Based on etcd/raft with significant optimizations
- Supports concurrent state machines and disk-based storage
""",
    "efficient-epaxos": """\
## Repository: Efficient EPaxos (Go)

This is an EPaxos (Egalitarian Paxos) implementation.

### Suggested Starting Points
- `src/epaxos/epaxos.go`: Core EPaxos replica logic
- `src/epaxos/epaxos-exec.go`: Execution and dependency resolution

Explore the codebase and discover potential issues through your own analysis.

### Build Notes
- Uses GOPATH mode: `GOPATH=$PWD GO111MODULE=off go test ./src/epaxos`
""",
    "ratis": """\
## Repository: Apache Ratis (Java)

This is Apache's Java implementation of Raft consensus protocol.

### Suggested Starting Points
- `ratis-server/.../impl/ServerState.java`: Server state management
- `ratis-server/.../impl/LeaderStateImpl.java`: Leader state implementation
- `ratis-server/.../raftlog/segmented/SegmentedRaftLog.java`: Segmented Raft log

Explore the codebase and discover potential issues through your own analysis.

### Build Notes
- Multi-module Maven project
- Use `mvn -pl :ratis-server -Dtest=<TestName> test` to run specific tests
""",
    "zookeeper": """\
## Repository: Apache ZooKeeper (Java)

This implements the ZAB (ZooKeeper Atomic Broadcast) consensus protocol.

### Suggested Starting Points
- `zookeeper-server/.../quorum/Leader.java`: Leader role implementation
- `zookeeper-server/.../quorum/Follower.java`: Follower role implementation
- `zookeeper-server/.../quorum/FastLeaderElection.java`: Fast leader election
- `zookeeper-server/.../quorum/QuorumPeer.java`: Quorum peer coordination

Explore the codebase and discover potential issues through your own analysis.

### Notes
- ZAB phases: Discovery -> Synchronization -> Broadcast
- Quorum requires 2f+1 servers to tolerate f failures
""",
    "fabric": """\
## Repository: Hyperledger Fabric (Go)

This is Hyperledger Fabric's ordering service using etcd/raft.

### Suggested Starting Points
- `orderer/consensus/etcdraft/chain.go`: Consensus chain management
- `orderer/consensus/etcdraft/node.go`: Raft node wrapper
- `orderer/consensus/etcdraft/storage.go`: WAL and snapshot storage

Explore the codebase and discover potential issues through your own analysis.

### Notes
- Uses etcd/raft for CFT ordering
- Also supports SmartBFT module for BFT ordering
""",
    # ==========================================================================
    # BFT Protocols
    # ==========================================================================
    "library": """\
## Repository: BFT-SMaRt (Java)

This is the BFT-SMaRt Byzantine fault-tolerant state machine replication library.

### Suggested Starting Points
- `src/main/java/bftsmart/tom/ServiceReplica.java`: Service replica main class
- `src/main/java/bftsmart/consensus/Consensus.java`: Core consensus algorithm
- `src/main/java/bftsmart/tom/core/TOMLayer.java`: TOM layer core logic

Explore the codebase and discover potential issues through your own analysis.

### Notes
- Requires n = 3f + 1 replicas to tolerate f Byzantine faults
- Configuration in config/ directory
""",
    "cometbft": """\
## Repository: CometBFT (Go)

This is CometBFT (formerly Tendermint), a PBFT-style BFT consensus.

### Suggested Starting Points
- `consensus/state.go`: Core state machine
- `consensus/reactor.go`: Consensus reactor
- `types/vote.go`: Vote structure
- `types/block.go`: Block structure

Explore the codebase and discover potential issues through your own analysis.

### Notes
- Consensus phases: NewHeight -> Propose -> Prevote -> Precommit -> Commit
- Requires 2/3+ voting power for consensus
""",
    "hotstuff": """\
## Repository: HotStuff (Go)

This is a HotStuff BFT consensus implementation.

### Suggested Starting Points
- `protocol/rules/chainedhotstuff.go`: Chained HotStuff logic
- `protocol/rules/fasthotstuff.go`: Fast HotStuff variant
- `protocol/synchronizer/synchronizer.go`: View synchronization

Explore the codebase and discover potential issues through your own analysis.
""",
    "AlephBFT": """\
## Repository: AlephBFT (Rust)

This is an asynchronous Byzantine fault tolerant consensus protocol.

### Suggested Starting Points
- `consensus/src/dag/mod.rs`: DAG main module
- `consensus/src/units/mod.rs`: Unit module
- `consensus/src/creation/creator.rs`: Unit creator
- `consensus/src/consensus/mod.rs`: Consensus main module

Explore the codebase and discover potential issues through your own analysis.

### Build Notes
- Use `cargo test -p aleph-bft <test_name>` to run tests
- Serial tests may need `#[serial_test::serial]` attribute
""",
    "aptos-core": """\
## Repository: Aptos Core (Rust)

This is Aptos blockchain's consensus implementation (HotStuff variant).

### Suggested Starting Points
- `consensus/src/round_manager.rs`: Round manager
- `consensus/safety-rules/src/safety_rules.rs`: Safety rules

Explore the codebase and discover potential issues through your own analysis.

### Build Notes
- Large monorepo - use `-p` flag to test specific packages
- Use `cargo test -p aptos-consensus <test_name>` for consensus tests
- Use `cargo test -p aptos-safety-rules <test_name>` for safety rules tests
""",
    "sui": """\
## Repository: Sui Consensus (Rust)

This is Sui's Mysticeti DAG-based BFT consensus.

### Suggested Starting Points
- `consensus/core/src/dag_state.rs`: DAG state management
- `consensus/core/src/linearizer.rs`: Commit ordering
- `consensus/core/src/commit_syncer.rs`: Commit synchronization
- `consensus/core/src/block_manager.rs`: Block handling

Explore the codebase and discover potential issues through your own analysis.
""",
}


# =============================================================================
# Prompt Generator
# =============================================================================


def get_analysis_prompt(
    repo_name: str,
    target_files: list[str] | None = None,
) -> str:
    """
    Generate the initial analysis prompt for a specific repository.

    This function creates a customized prompt that includes:
    - Repository name and description
    - Suggested starting points for code exploration
    - Target files to focus on (if specified)

    Args:
        repo_name: Name of the repository to analyze.
            Should be one of: "raft", "sui", "hotstuff", "efficient-epaxos".
        target_files: Optional list of specific files to focus on.
            If provided, the agent will prioritize these files.
            If None, the agent will explore based on repository hints.

    Returns:
        Formatted prompt string ready to send to the LLM.

    Example:
        ```python
        prompt = get_analysis_prompt("raft", ["raft.go", "log.go"])
        print(prompt)
        ```
    """
    # Get repository-specific hint or use a generic message
    hint = _REPO_HINTS.get(repo_name, f"Analyzing repository: {repo_name}")

    # Build the prompt
    lines = [
        hint,
        "",
        "## Your Task",
        "",
        "Analyze the consensus protocol implementation to find potential bugs.",
        "",
    ]

    if target_files:
        lines.extend([
            "### Specific Files to Focus On",
            *[f"- {f}" for f in target_files],
            "",
            "Start by reading these files, then explore related code as needed.",
        ])
    else:
        lines.extend([
            "### Getting Started",
            "1. First, use `list_files` to explore the repository structure",
            "2. Read the key files mentioned above",
            "3. Search for critical patterns and potential bugs",
            "4. Report any bugs you find",
            "",
            "Start your analysis now.",
        ])

    return "\n".join(lines)
