"""
Mock LLM responses for testing without token consumption.
These responses mimic the expected format from Strategy, TestGen, and Validator agents.
"""

# ============================================================
# Strategy Agent Mock Responses
# ============================================================

MOCK_STRATEGY_RESPONSE = """
<thinking>
[Understanding the Protocol]
I observe that this Raft implementation handles leader election through term-based voting.
The key mechanism is that nodes only vote for candidates with terms higher than their own.

[Analyzing Known Patterns]
A pattern from Pattern Memory describes potential issues with split votes during network partitions.
This approach might manifest in the current protocol when nodes have stale term information.

[Identifying Suspicious Points]
I notice that the vote request handler doesn't check if the candidate's log is up-to-date.
There seems to be no check for log consistency before granting votes.

[Creative Reasoning]
If I construct a scenario where a lagging node becomes leader...
This might lead to committed entries being lost.
</thinking>

<attack_scenario>
Name: StaleLeaderElectionViolation
Target Component: VoteHandler
Vulnerability Hypothesis: A node with stale log can become leader if it has a higher term, causing committed entries to be lost
Attack Category: safety
Inspiration Source: pattern_memory

Preconditions:
1. 5-node cluster with nodes A, B, C, D, E
2. Node A is the current leader with committed entries
3. Node E is isolated and has not received recent entries

Attack Steps:
1. Partition node E from the cluster
2. Leader A commits several entries with agreement from B, C, D
3. Crash nodes A, B, C simultaneously
4. Heal partition - E can now communicate with D
5. E starts election with higher term (due to timeouts during isolation)
6. D grants vote to E (E has higher term but stale log)
7. E becomes leader with stale log

Expected Bug Behavior: Node E becomes leader and overwrites committed entries from A
Correct Behavior: D should reject E's vote request because E's log is not up-to-date

Assertions:
- After E becomes leader, committed entries from A should still be present
- No committed entry should be lost or overwritten
- Safety property: committed entries must be durable
</attack_scenario>
"""

MOCK_STRATEGY_RESPONSE_MINIMAL = """
<attack_scenario>
Name: MinimalTestScenario
Target Component: ConsensusCore
Vulnerability Hypothesis: Basic test hypothesis
Attack Category: liveness
Preconditions:
1. 3-node cluster
Attack Steps:
1. Start cluster
2. Send request
Expected Bug Behavior: Cluster hangs
Correct Behavior: Request should complete
</attack_scenario>
"""

MOCK_STRATEGY_RESPONSE_BFT = """
<thinking>
[Understanding the BFT Protocol]
This is a PBFT-style protocol with 3f+1 nodes tolerating f Byzantine faults.
The key mechanism is the three-phase commit: pre-prepare, prepare, commit.

[Analyzing Byzantine Attack Vectors]
A Byzantine leader could send conflicting pre-prepare messages to different replicas.
This equivocation attack could cause honest nodes to disagree.

[Creative Reasoning]
If the Byzantine leader sends different values to different subsets of nodes...
And carefully times the messages to exploit the 2f+1 threshold...
</thinking>

<attack_scenario>
Name: ByzantineLeaderEquivocation
Target Component: PrePrepareHandler
Vulnerability Hypothesis: Byzantine leader can cause safety violation through equivocation
Attack Category: safety
Inspiration Source: original

Preconditions:
1. 4-node cluster (f=1)
2. Node 0 is Byzantine leader
3. All other nodes are honest

Attack Steps:
1. Byzantine leader receives client request
2. Leader sends pre-prepare with value V1 to nodes 1, 2
3. Leader sends pre-prepare with value V2 to node 3
4. Nodes 1, 2 prepare V1; node 3 prepares V2
5. Leader selectively forwards prepare messages
6. Attempt to get different nodes to commit different values

Expected Bug Behavior: Nodes commit different values for the same sequence number
Correct Behavior: All honest nodes should commit the same value or none at all

Assertions:
- All honest nodes that commit must commit the same value
- Byzantine behavior should be detected and handled
</attack_scenario>
"""

# ============================================================
# TestGen Agent Mock Responses
# ============================================================

MOCK_TESTGEN_RESPONSE_GO = """
I've analyzed the repository structure and existing tests. Here's the test implementation:

File Path: consensus_stale_leader_test.go

<test_code>
package raft

import (
	"testing"
	"time"
)

// TestStaleLeaderElectionViolation tests that a node with stale log
// cannot become leader even with a higher term.
func TestStaleLeaderElectionViolation(t *testing.T) {
	// Create 5-node cluster
	cluster := newTestCluster(t, 5)
	defer cluster.cleanup()

	// Start cluster and wait for leader
	cluster.start()
	leader := cluster.waitForLeader(t, 5*time.Second)
	if leader == nil {
		t.Fatal("failed to elect initial leader")
	}

	// Commit some entries through leader
	for i := 0; i < 10; i++ {
		if err := leader.Propose([]byte("entry")); err != nil {
			t.Fatalf("failed to propose entry %d: %v", i, err)
		}
	}

	// Wait for entries to be committed
	cluster.waitForCommit(t, 10, 5*time.Second)
	committedIndex := leader.CommitIndex()

	// Partition node 4 (E)
	cluster.partition([]int{0, 1, 2, 3}, []int{4})

	// Commit more entries in majority partition
	for i := 0; i < 5; i++ {
		if err := leader.Propose([]byte("after_partition")); err != nil {
			t.Fatalf("failed to propose after partition: %v", err)
		}
	}
	cluster.waitForCommit(t, 15, 5*time.Second)

	// Crash nodes 0, 1, 2 (majority)
	cluster.crash(0)
	cluster.crash(1)
	cluster.crash(2)

	// Heal partition
	cluster.healPartition()

	// Node 4 should not become leader with stale log
	time.Sleep(3 * time.Second)

	// Check that committed entries are not lost
	for _, node := range cluster.nodes {
		if node.IsRunning() {
			if node.CommitIndex() < committedIndex {
				t.Errorf("node %d has commit index %d, expected at least %d",
					node.ID(), node.CommitIndex(), committedIndex)
			}
		}
	}
}
</test_code>

Test Command: go test -v -run TestStaleLeaderElectionViolation ./...
"""

MOCK_TESTGEN_RESPONSE_RUST = """
I've analyzed the Rust repository. Here's the test:

File Path: tests/stale_leader_test.rs

<test_code>
use raft::{Config, RawNode, Storage};
use std::time::Duration;

#[test]
fn test_stale_leader_election_violation() {
    // Create 5-node cluster configuration
    let config = Config {
        id: 1,
        peers: vec![1, 2, 3, 4, 5],
        election_tick: 10,
        heartbeat_tick: 3,
        ..Default::default()
    };

    let mut nodes: Vec<RawNode<MemStorage>> = (1..=5)
        .map(|id| {
            let storage = MemStorage::new();
            RawNode::new(&config.clone().id(id), storage).unwrap()
        })
        .collect();

    // Simulate leader election and entry commitment
    // ... (test implementation)

    // Assert safety property
    let committed_entries: Vec<_> = nodes
        .iter()
        .filter(|n| n.raft.state == StateRole::Leader || n.raft.state == StateRole::Follower)
        .map(|n| n.raft.raft_log.committed)
        .collect();

    // All running nodes should agree on committed index
    assert!(committed_entries.windows(2).all(|w| w[0] == w[1]),
        "Committed indices do not match: {:?}", committed_entries);
}
</test_code>

Test Command: cargo test test_stale_leader_election_violation -- --nocapture
"""

MOCK_TESTGEN_RESPONSE_WITH_ERROR = """
Here's my attempt at the test:

<test_code>
package raft

import (
	"testing"
)

func TestBrokenTest(t *testing.T) {
	// This has a syntax error
	cluster := newTestCluster(t, 5
	cluster.start()
}
</test_code>
"""

MOCK_TESTGEN_RESPONSE_FIXED = """
I've fixed the syntax error:

<test_code>
package raft

import (
	"testing"
)

func TestBrokenTest(t *testing.T) {
	// Fixed syntax error
	cluster := newTestCluster(t, 5)
	defer cluster.cleanup()
	cluster.start()
}
</test_code>
"""

# ============================================================
# Validator Agent Mock Responses
# ============================================================

MOCK_VALIDATOR_RESPONSE_BUG_FOUND = """
<thinking>
[Analyzing Test Results]
The test output shows that node E became leader with commit index 10, while the cluster had already committed up to index 15.
This indicates that committed entries were indeed lost.

[Checking Protocol Specification]
According to the Raft paper, a candidate should only win an election if its log is at least as up-to-date as any other log in the majority.
The "up-to-date" check compares: (1) last log term, (2) last log index.

[Verifying Bug Reality]
The code in vote_handler.go at line 145 only checks the term, not the log up-to-dateness.
This is a clear violation of the Raft specification.

[Assessing Scenario Realism]
The scenario requires:
- Network partition (common in distributed systems)
- Multiple node crashes (possible during datacenter events)
- Timing of partition healing (controllable by attacker or bad luck)

This scenario is realistic and could occur in production.
</thinking>

<validation>
Is This a Real Bug: Yes
Is Realistic Scenario: Yes
Reason: The vote handler does not implement the log up-to-dateness check required by Raft. This allows a node with stale log to become leader, violating safety.
</validation>

<bug_report>
## Summary
Safety violation in leader election: stale node can become leader

## Root Cause
The `RequestVote` RPC handler in `vote_handler.go` (line 145) only compares terms when deciding whether to grant a vote. It does not implement the log up-to-dateness check specified in the Raft paper (Section 5.4.1).

## Impact
- Committed entries can be lost when a stale node becomes leader
- Violates Raft's safety guarantee
- Could cause data loss in production

## Reproduction
1. Create 5-node cluster
2. Commit entries through leader
3. Partition one node
4. Commit more entries in majority partition
5. Crash majority nodes
6. Heal partition
7. Observe stale node becoming leader

## Suggested Fix
Add log up-to-dateness check in `handleRequestVote`:
```go
// Check if candidate's log is at least as up-to-date as receiver's
lastLogTerm := r.raftLog.lastTerm()
lastLogIndex := r.raftLog.lastIndex()
if args.LastLogTerm < lastLogTerm || 
   (args.LastLogTerm == lastLogTerm && args.LastLogIndex < lastLogIndex) {
    return &RequestVoteReply{Term: r.currentTerm, VoteGranted: false}
}
```
</bug_report>

<learning>
**Success Pattern**: Testing leader election with log divergence scenarios effectively finds safety bugs.
**Key Insight**: Always verify that vote granting logic includes log up-to-dateness check.
**Recommendation for Strategy**: Continue exploring election edge cases with different cluster sizes and partition patterns.
</learning>
"""

MOCK_VALIDATOR_RESPONSE_FALSE_POSITIVE = """
<thinking>
[Analyzing Test Results]
The test shows a timeout, but examining the code reveals that the test setup is incorrect.
The cluster never actually starts because `cluster.start()` was called before nodes were configured.

[Checking Protocol Code]
The protocol implementation correctly handles this scenario.
The timeout is due to test infrastructure issues, not a protocol bug.

[Assessing Scenario Realism]
Even if this were a real issue, the scenario requires:
- Instantaneous crash of 3 nodes (unrealistic)
- Perfect timing of partition healing (unlikely)

The scenario is not realistic for production environments.
</thinking>

<validation>
Is This a Real Bug: No
Is Realistic Scenario: No
Reason: The test failure is due to incorrect test setup, not a protocol bug. The cluster initialization order is wrong.
</validation>

<learning>
**Rejection Reason**: [test_error]
**Specific Issue**: [Test setup error - cluster.start() called before node configuration]
**Pattern to Avoid**: [Ensure cluster is fully configured before starting in tests]
**Recommendation for Strategy**: [Focus on scenarios with gradual node failures rather than instantaneous multi-node crashes]
</learning>
"""

MOCK_VALIDATOR_RESPONSE_UNREALISTIC = """
<thinking>
[Analyzing Test Results]
The test does demonstrate unexpected behavior - the leader's state becomes inconsistent.

[Checking Protocol Code]
Looking at the code, this behavior only occurs when the leader receives exactly 
simultaneous messages from all followers at the precise microsecond boundary.

[Assessing Scenario Realism]
This scenario requires:
- Microsecond-precise timing across all nodes
- Zero network latency variation
- No operating system scheduling delays

This is essentially impossible in any real deployment.
</thinking>

<validation>
Is This a Real Bug: No
Is Realistic Scenario: No
Reason: While the code has a theoretical race condition, triggering it requires impossible timing precision that cannot occur in production.
</validation>

<learning>
**Rejection Reason**: [unrealistic_scenario]
**Specific Issue**: [Requires microsecond-precise simultaneous events across distributed nodes]
**Pattern to Avoid**: [Avoid scenarios requiring precise timing synchronization across nodes]
**Recommendation for Strategy**: [Focus on scenarios with realistic timing variations and network delays]
</learning>
"""

MOCK_VALIDATOR_RESPONSE_EXPECTED_BEHAVIOR = """
<validation>
Is This a Real Bug: No
Is Realistic Scenario: Yes
Reason: The observed behavior is actually correct according to the protocol specification. The leader stepping down after losing majority is expected behavior, not a bug.
</validation>

<learning>
**Rejection Reason**: [expected_behavior]
**Specific Issue**: [Leader stepdown on majority loss is correct protocol behavior]
**Pattern to Avoid**: [Do not flag leader stepdown as liveness violation]
**Recommendation for Strategy**: [Review protocol spec before flagging normal leader transitions as bugs]
</learning>
"""

# ============================================================
# Combined Mock Response Dictionary
# ============================================================

MOCK_RESPONSES = {
    "strategy": MOCK_STRATEGY_RESPONSE,
    "strategy_minimal": MOCK_STRATEGY_RESPONSE_MINIMAL,
    "strategy_bft": MOCK_STRATEGY_RESPONSE_BFT,
    "testgen": MOCK_TESTGEN_RESPONSE_GO,
    "testgen_rust": MOCK_TESTGEN_RESPONSE_RUST,
    "testgen_error": MOCK_TESTGEN_RESPONSE_WITH_ERROR,
    "testgen_fixed": MOCK_TESTGEN_RESPONSE_FIXED,
    "validator_bug": MOCK_VALIDATOR_RESPONSE_BUG_FOUND,
    "validator_false_positive": MOCK_VALIDATOR_RESPONSE_FALSE_POSITIVE,
    "validator_unrealistic": MOCK_VALIDATOR_RESPONSE_UNREALISTIC,
    "validator_expected": MOCK_VALIDATOR_RESPONSE_EXPECTED_BEHAVIOR,
}
