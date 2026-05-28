#!/usr/bin/env python3
"""
Generate repo_context.json for each consensus protocol repository.

This script analyzes each protocol repository and extracts:
1. Test Infrastructure - how to start clusters, simulate networks, crypto operations
2. Valid Entry Points - public functions for message handling
3. Data Constructors - how to create Blocks, Proposals, QCs, etc.
4. Forbidden Patterns - things test code should NOT do

Output: {repo_name}.json in agent/repo_knowledge/
"""

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ValidAPI:
    """Represents a valid API that tests can use"""

    name: str
    signature: str
    usage: str
    category: str  # infrastructure, entry_point, constructor, helper
    file: str = ""
    example: str = ""


@dataclass
class ForbiddenPattern:
    """Represents a pattern that tests should NOT use"""

    pattern: str
    reason: str
    suggestion: str = ""


@dataclass
class RepoContext:
    """Complete context for a repository"""

    repo_name: str
    language: str
    commit_hash: str
    analyzed_at: str
    valid_apis: list = field(default_factory=list)
    forbidden_patterns: list = field(default_factory=list)
    test_infrastructure: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def get_commit_hash(repo_path: Path) -> str:
    """Get the current git commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True
        )
        return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def analyze_hotstuff(repo_path: Path) -> RepoContext:
    """Analyze the hotstuff repository"""
    ctx = RepoContext(
        repo_name="hotstuff",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    # Test Infrastructure
    ctx.test_infrastructure = {
        "cluster_setup": {
            "method": "testutil.NewEssentialsSet",
            "description": "Creates a set of Essentials for multiple replicas with proper wiring",
            "file": "internal/testutil/wiring.go",
        },
        "network_simulation": {
            "method": "twins.ExecuteScenario",
            "description": "Simulates network partitions and message delivery using Twins framework",
            "file": "twins/executor.go",
        },
        "crypto": {
            "method": "testutil.CreateQC / testutil.CreatePC / testutil.CreateTC",
            "description": "Use testutil helpers to create properly signed certificates",
            "file": "internal/testutil/testutil.go",
        },
    }

    # Valid APIs - Infrastructure
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="testutil.NewEssentialsSet",
                    signature="func NewEssentialsSet(t testing.TB, count uint, cryptoName string, opts ...core.RuntimeOption) EssentialsSet",
                    usage="Initialize a cluster of n replicas with proper crypto and wiring. REQUIRED for any test involving multiple nodes.",
                    category="infrastructure",
                    file="internal/testutil/wiring.go",
                    example="""essentials := testutil.NewEssentialsSet(t, 4, crypto.NameECDSA)
signers := essentials.Signers()""",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.WireUpEssentials",
                    signature="func WireUpEssentials(t testing.TB, id hotstuff.ID, cryptoName string, opts ...core.RuntimeOption) *Essentials",
                    usage="Wire up essentials for a single replica. Use NewEssentialsSet for multiple replicas.",
                    category="infrastructure",
                    file="internal/testutil/wiring.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="twins.ExecuteScenario",
                    signature="func ExecuteScenario(s Scenario, numNodes, numTwins, maxMessages int, ruleName string) (*Result, error)",
                    usage="Execute a network scenario with partitions and twins. Returns safety/liveness results.",
                    category="infrastructure",
                    file="twins/executor.go",
                    example="""s := twins.Scenario{}
allNodes := twins.NewNodeSet(twins.Replica(1), twins.Replica(2), twins.Replica(3), twins.Replica(4))
s = append(s, twins.View{Leader: 1, Partitions: []twins.NodeSet{allNodes}})
result, err := twins.ExecuteScenario(s, 4, 0, 100, rules.NameChainedHotStuff)""",
                )
            ),
            asdict(
                ValidAPI(
                    name="twins.NewGenerator",
                    signature="func NewGenerator(logger logging.Logger, settings Settings) *Generator",
                    usage="Create a scenario generator for fuzzing network partitions.",
                    category="infrastructure",
                    file="twins/generator.go",
                )
            ),
        ]
    )

    # Valid APIs - Data Constructors
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="hotstuff.NewBlock",
                    signature="func NewBlock(parent Hash, cert QuorumCert, batch *clientpb.Batch, view View, proposer ID) *Block",
                    usage="Create a new block with proper parent, QC, and view. Hash is computed automatically.",
                    category="constructor",
                    file="block.go",
                    example="""block := hotstuff.NewBlock(
    parent.Hash(),
    qc,
    &clientpb.Batch{Commands: []*clientpb.Command{}},
    view,
    proposerID,
)""",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateBlock",
                    signature="func CreateBlock(t testing.TB, signer *cert.Authority) *hotstuff.Block",
                    usage="Create a simple block extending genesis. For basic tests only.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateParentedBlock",
                    signature="func CreateParentedBlock(t testing.TB, proposer hotstuff.ID, validParent *hotstuff.Block) *hotstuff.Block",
                    usage="Create a block that properly extends a given parent block.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateQC",
                    signature="func CreateQC(t testing.TB, block *hotstuff.Block, signers ...*cert.Authority) hotstuff.QuorumCert",
                    usage="Create a properly signed QuorumCert for a block. ALWAYS use this instead of manual QC creation.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                    example="""qc := testutil.CreateQC(t, block, signers...)""",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreatePC",
                    signature="func CreatePC(t testing.TB, block *hotstuff.Block, signer *cert.Authority) hotstuff.PartialCert",
                    usage="Create a single partial certificate (vote) for a block.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreatePCs",
                    signature="func CreatePCs(t testing.TB, block *hotstuff.Block, signers []*cert.Authority) []hotstuff.PartialCert",
                    usage="Create partial certificates from multiple signers.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateTC",
                    signature="func CreateTC(t testing.TB, view hotstuff.View, signers []*cert.Authority) hotstuff.TimeoutCert",
                    usage="Create a TimeoutCert signed by the given signers.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateAC",
                    signature="func CreateAC(t testing.TB, view hotstuff.View, signers []*cert.Authority) hotstuff.AggregateQC",
                    usage="Create an AggregateQC (used in Fast-HotStuff variant).",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateTimeouts",
                    signature="func CreateTimeouts[T crypto.Base](t testing.TB, view hotstuff.View, signers []T, qcs ...hotstuff.QuorumCert) []hotstuff.TimeoutMsg",
                    usage="Create timeout messages signed by multiple signers.",
                    category="constructor",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="hotstuff.NewQuorumCert",
                    signature="func NewQuorumCert(sig QuorumSignature, view View, hash Hash) QuorumCert",
                    usage="Low-level QC constructor. Prefer testutil.CreateQC for tests.",
                    category="constructor",
                    file="quorum.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="hotstuff.NewSyncInfo",
                    signature="func NewSyncInfo() SyncInfo",
                    usage="Create empty SyncInfo. Use NewSyncInfoWith* variants for initialized versions.",
                    category="constructor",
                    file="syncinfo.go",
                )
            ),
        ]
    )

    # Valid APIs - Entry Points (message handlers)
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="Blockchain.Store",
                    signature="func (bc *Blockchain) Store(block *Block)",
                    usage="Store a block in the blockchain. Usually called internally by protocol.",
                    category="entry_point",
                    file="protocol/blockchain.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="VotingMachine.OnVote",
                    signature="func (vm *VotingMachine) OnVote(vote VoteMsg)",
                    usage="Handle incoming vote message.",
                    category="entry_point",
                    file="protocol/votingmachine/votingmachine.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Synchronizer.OnRemoteTimeout",
                    signature="func (s *Synchronizer) OnRemoteTimeout(timeout TimeoutMsg)",
                    usage="Handle incoming timeout message from remote replica.",
                    category="entry_point",
                    file="protocol/synchronizer/synchronizer.go",
                )
            ),
        ]
    )

    # Valid APIs - Crypto helpers
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="testutil.GenerateECDSAKey",
                    signature="func GenerateECDSAKey(t testing.TB) hotstuff.PrivateKey",
                    usage="Generate an ECDSA private key for testing.",
                    category="helper",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.GenerateBLS12Key",
                    signature="func GenerateBLS12Key(t testing.TB) hotstuff.PrivateKey",
                    usage="Generate a BLS12-381 private key for testing.",
                    category="helper",
                    file="internal/testutil/testutil.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="testutil.CreateSigners",
                    signature="func CreateSigners[T crypto.Base](t testing.TB, numReplicas int) []T",
                    usage="Create multiple signers of a specific crypto type.",
                    category="helper",
                    file="internal/testutil/testutil.go",
                )
            ),
        ]
    )

    # Valid APIs - Twins framework
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="twins.NewNodeSet",
                    signature="func NewNodeSet(nodes ...NodeID) NodeSet",
                    usage="Create a set of nodes for defining network partitions.",
                    category="helper",
                    file="twins/scenario.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="twins.Replica",
                    signature="func Replica(id hotstuff.ID) NodeID",
                    usage="Create a NodeID for a replica. Use .Twin(n) to reference twin instances.",
                    category="helper",
                    file="twins/scenario.go",
                    example="""// Replica 1 with two twins
twins.Replica(1).Twin(1)  // First twin of replica 1
twins.Replica(1).Twin(2)  // Second twin of replica 1""",
                )
            ),
        ]
    )

    # Forbidden Patterns
    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="hotstuff.NewQuorumCert(nil, ...) without proper signature",
                    reason="QCs without proper signatures will fail verification. Tests may appear to work but are invalid.",
                    suggestion="Use testutil.CreateQC(t, block, signers...) to create properly signed QCs.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Directly manipulating Blockchain internals",
                    reason="Bypasses protocol logic and creates unrealistic test scenarios.",
                    suggestion="Use the twins framework or proper message injection.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Creating blocks without proper parent chain",
                    reason="Orphan blocks violate protocol invariants.",
                    suggestion="Use testutil.CreateParentedBlock or ensure parent exists in blockchain.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Manually computing block hashes",
                    reason="hotstuff.NewBlock computes hash automatically. Manual hashing may cause mismatches.",
                    suggestion="Let NewBlock compute the hash, or use block.Hash() to get the correct value.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Using private/lowercase functions from protocol packages",
                    reason="Internal functions may change without notice and bypass safety checks.",
                    suggestion="Use only exported (uppercase) functions and testutil helpers.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Skipping signature verification in tests",
                    reason="Tests must verify signatures to catch real bugs. Use core.WithSyncVerification() option.",
                    suggestion="NewEssentialsSet already enables sync verification by default.",
                )
            ),
        ]
    )

    ctx.notes = [
        "HotStuff uses the 'twins' framework for network partition testing",
        "crypto.NameECDSA, crypto.NameEDDSA, crypto.NameBLS12 are valid crypto implementations",
        "View numbers are 1-indexed, hotstuff.View(0) is genesis",
        "hotstuff.GetGenesis() returns the genesis block",
        "EssentialsSet.Signers() returns []*cert.Authority for creating signatures",
        "Use rules.NameChainedHotStuff or rules.NameFastHotStuff for protocol variants",
    ]

    return ctx


def analyze_efficient_epaxos(repo_path: Path) -> RepoContext:
    """Analyze the efficient-epaxos repository"""
    ctx = RepoContext(
        repo_name="efficient-epaxos",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "cluster_setup": {
            "method": "epaxos.NewReplica",
            "description": "Creates a new EPaxos replica with given peer list",
            "file": "src/epaxos/epaxos.go",
        },
        "network_simulation": {
            "method": "Manual channel injection via Replica channels",
            "description": "Messages are injected via prepareChan, preAcceptChan, commitChan, etc.",
            "file": "src/epaxos/epaxos.go",
        },
        "state_machine": {
            "method": "state.Command",
            "description": "Commands are the basic unit of replication",
            "file": "src/state/state.go",
        },
    }

    # Valid APIs
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="epaxos.NewReplica",
                    signature="func NewReplica(id int, peerAddrList []string, thrifty bool, exec bool, dreply bool, beacon bool, durable bool) *Replica",
                    usage="Create a new EPaxos replica. Set durable=false for in-memory testing.",
                    category="infrastructure",
                    file="src/epaxos/epaxos.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Replica.InstanceSpace",
                    signature="InstanceSpace [][]*Instance",
                    usage="Access to the 2D instance space [replica][instance]. READ-ONLY in tests.",
                    category="entry_point",
                    file="src/epaxos/epaxos.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="epaxosproto.PreAccept",
                    signature="type PreAccept struct { LeaderId, Replica, Instance int32; Ballot int32; Cmds []state.Command; Seq int32; Deps [DS]int32 }",
                    usage="PreAccept message structure for the fast path.",
                    category="constructor",
                    file="src/epaxosproto/epaxosproto.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="epaxosproto.Accept",
                    signature="type Accept struct { LeaderId, Replica, Instance int32; Ballot int32; Seq int32; Deps [DS]int32 }",
                    usage="Accept message structure for the slow path.",
                    category="constructor",
                    file="src/epaxosproto/epaxosproto.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="epaxosproto.Commit",
                    signature="type Commit struct { LeaderId, Replica, Instance int32; Cmds []state.Command; Seq int32; Deps [DS]int32 }",
                    usage="Commit message to finalize an instance.",
                    category="constructor",
                    file="src/epaxosproto/epaxosproto.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="epaxosproto.Prepare",
                    signature="type Prepare struct { LeaderId, Replica, Instance int32; Ballot int32 }",
                    usage="Prepare message for recovery.",
                    category="constructor",
                    file="src/epaxosproto/epaxosproto.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="state.Command",
                    signature="type Command struct { Op Operation; K Key; V Value }",
                    usage="A state machine command with operation, key, value.",
                    category="constructor",
                    file="src/state/state.go",
                )
            ),
        ]
    )

    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Directly modifying Instance.Status without proper state machine transitions",
                    reason="Instance status must follow the protocol state machine: PREACCEPTED -> ACCEPTED -> COMMITTED -> EXECUTED",
                    suggestion="Inject proper protocol messages to trigger status changes.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Setting instance.Deps without conflict analysis",
                    reason="Dependencies must be computed based on actual command conflicts.",
                    suggestion="Use the protocol's updateAttributes/mergeAttributes logic.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Skipping ballot checks",
                    reason="Ballot numbers enforce leader election correctness.",
                    suggestion="Always include proper ballot numbers in messages.",
                )
            ),
        ]
    )

    ctx.notes = [
        "EPaxos uses 2D instance space: InstanceSpace[replica][instance]",
        "DS=5 is the default dependency set size",
        "Instance statuses: PREACCEPTED=1, ACCEPTED=2, COMMITTED=3, EXECUTED=4",
        "Recovery uses Prepare/PrepareReply messages",
        "Fast path completes if f+1 replicas agree on dependencies",
    ]

    return ctx


def analyze_raft(repo_path: Path) -> RepoContext:
    """Analyze the etcd raft repository"""
    ctx = RepoContext(
        repo_name="raft",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "cluster_setup": {
            "method": "rafttest.Network / newNetwork",
            "description": "Creates a simulated network of raft nodes",
            "file": "rafttest/network.go",
        },
        "node_creation": {
            "method": "raft.NewRawNode / newTestRaft",
            "description": "Creates individual raft state machines",
            "file": "rawnode.go",
        },
        "storage": {
            "method": "MemoryStorage",
            "description": "In-memory storage for testing",
            "file": "storage.go",
        },
    }

    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="raft.NewRawNode",
                    signature="func NewRawNode(config *Config) (*RawNode, error)",
                    usage="Create a new RawNode which is the core raft state machine.",
                    category="infrastructure",
                    file="rawnode.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="MemoryStorage",
                    signature="type MemoryStorage struct",
                    usage="In-memory storage implementation for testing. Use NewMemoryStorage().",
                    category="infrastructure",
                    file="storage.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="raft.Config",
                    signature="type Config struct { ID uint64; ElectionTick int; HeartbeatTick int; Storage Storage; ... }",
                    usage="Configuration for raft node. ID must be non-zero.",
                    category="constructor",
                    file="raft.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="pb.Message",
                    signature="type Message struct { Type MessageType; To, From uint64; Term uint64; LogTerm uint64; Index uint64; Entries []Entry; ... }",
                    usage="Protocol message structure. See raftpb/raft.proto for all fields.",
                    category="constructor",
                    file="raftpb/raft.pb.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="RawNode.Step",
                    signature="func (rn *RawNode) Step(m pb.Message) error",
                    usage="THE MAIN ENTRY POINT: Process a message. This is how messages are delivered to a node.",
                    category="entry_point",
                    file="rawnode.go",
                    example="""err := node.Step(pb.Message{
    Type: pb.MsgVote,
    From: 2,
    To: 1,
    Term: 2,
})""",
                )
            ),
            asdict(
                ValidAPI(
                    name="RawNode.Tick",
                    signature="func (rn *RawNode) Tick()",
                    usage="Advance the internal logical clock. Call this to trigger timeouts.",
                    category="entry_point",
                    file="rawnode.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="RawNode.Ready",
                    signature="func (rn *RawNode) Ready() Ready",
                    usage="Get messages to send, entries to apply, etc.",
                    category="entry_point",
                    file="rawnode.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="RawNode.Advance",
                    signature="func (rn *RawNode) Advance(rd Ready)",
                    usage="Acknowledge that Ready has been processed. Must call after Ready().",
                    category="entry_point",
                    file="rawnode.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="RawNode.Propose",
                    signature="func (rn *RawNode) Propose(data []byte) error",
                    usage="Propose a new entry to be appended to the log.",
                    category="entry_point",
                    file="rawnode.go",
                )
            ),
        ]
    )

    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Directly setting raft.state or raft.Term",
                    reason="Internal state must change via protocol messages.",
                    suggestion="Use Step() with appropriate messages to change state.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Calling raft.becomeLeader/becomeFollower directly",
                    reason="These are internal methods, not test APIs.",
                    suggestion="Trigger state changes via election: send MsgHup or wait for election timeout.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Using pb.Message with invalid term/index combinations",
                    reason="Invalid log indices cause panics or undefined behavior.",
                    suggestion="Ensure Index <= LastIndex+1 and Term is consistent.",
                )
            ),
        ]
    )

    ctx.notes = [
        "MessageTypes: MsgHup (trigger election), MsgBeat (trigger heartbeat), MsgProp (propose), MsgApp (append entries), MsgVote, etc.",
        "States: StateFollower, StateCandidate, StateLeader, StatePreCandidate",
        "Use node.Step(pb.Message{Type: pb.MsgHup}) to trigger an election",
        "ElectionTick ticks must pass before election timeout",
        "Ready.Messages contains messages to send to other nodes",
    ]

    return ctx


def analyze_hashicorp_raft(repo_path: Path) -> RepoContext:
    """Analyze the hashicorp-raft repository"""
    ctx = RepoContext(
        repo_name="hashicorp-raft",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "cluster_setup": {
            "method": "MakeCluster / MakeClusterNoBootstrap",
            "description": "Creates a test cluster with in-memory transport",
            "file": "raft_test.go",
        },
        "transport": {
            "method": "InmemTransport",
            "description": "In-memory transport for testing without network",
            "file": "inmem_transport.go",
        },
        "storage": {
            "method": "InmemStore",
            "description": "In-memory log/stable store for testing",
            "file": "inmem_store.go",
        },
        "fsm": {
            "method": "MockFSM",
            "description": "Mock FSM implementation for testing",
            "file": "raft_test.go",
        },
    }

    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="raft.NewRaft",
                    signature="func NewRaft(conf *Config, fsm FSM, logs LogStore, stable StableStore, snaps SnapshotStore, trans Transport) (*Raft, error)",
                    usage="Create a new Raft node. For testing, use in-memory implementations.",
                    category="infrastructure",
                    file="raft.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="InmemTransport",
                    signature="func NewInmemTransport(addr ServerAddress) (ServerAddress, *InmemTransport)",
                    usage="Create in-memory transport for testing.",
                    category="infrastructure",
                    file="inmem_transport.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="InmemStore",
                    signature="func NewInmemStore() *InmemStore",
                    usage="Create in-memory log/stable store.",
                    category="infrastructure",
                    file="inmem_store.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Raft.Apply",
                    signature="func (r *Raft) Apply(cmd []byte, timeout time.Duration) ApplyFuture",
                    usage="Apply a command (leader only). Returns a future.",
                    category="entry_point",
                    file="api.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Raft.AddVoter",
                    signature="func (r *Raft) AddVoter(id ServerID, addr ServerAddress, prevIndex uint64, timeout time.Duration) IndexFuture",
                    usage="Add a voter to the cluster configuration.",
                    category="entry_point",
                    file="api.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Raft.RemoveServer",
                    signature="func (r *Raft) RemoveServer(id ServerID, prevIndex uint64, timeout time.Duration) IndexFuture",
                    usage="Remove a server from the cluster.",
                    category="entry_point",
                    file="api.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Raft.LeaderCh",
                    signature="func (r *Raft) LeaderCh() <-chan bool",
                    usage="Channel that notifies of leadership changes.",
                    category="entry_point",
                    file="api.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="Raft.State",
                    signature="func (r *Raft) State() RaftState",
                    usage="Get current state (Follower, Candidate, Leader).",
                    category="entry_point",
                    file="api.go",
                )
            ),
        ]
    )

    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Accessing internal raft.* fields directly",
                    reason="Internal state is not thread-safe for external access.",
                    suggestion="Use the public API methods like State(), Leader(), etc.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Creating Raft without proper FSM",
                    reason="FSM is required for state machine replication.",
                    suggestion="Use MockFSM for testing or implement FSM interface.",
                )
            ),
        ]
    )

    ctx.notes = [
        "RaftState: Follower=0, Candidate=1, Leader=2, Shutdown=3",
        "Use Bootstrap() for initial cluster formation",
        "Futures have Error() method to check for errors",
        "LeaderCh() is buffered(1), may not capture all transitions",
        "Configuration changes require leader",
    ]

    return ctx


def analyze_cometbft(repo_path: Path) -> RepoContext:
    """Analyze the cometbft repository"""
    ctx = RepoContext(
        repo_name="cometbft",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "cluster_setup": {
            "method": "Various test helpers in test/ directory",
            "description": "CometBFT has complex test infrastructure",
            "file": "test/",
        },
        "consensus_state": {
            "method": "consensus.NewState",
            "description": "Creates consensus state machine",
            "file": "consensus/state.go",
        },
        "mempool": {
            "method": "mempool.NewCListMempool",
            "description": "Creates mempool for transaction handling",
            "file": "mempool/clist_mempool.go",
        },
    }

    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="consensus.NewState",
                    signature="func NewState(config *cfg.ConsensusConfig, state sm.State, blockExec *sm.BlockExecutor, blockStore sm.BlockStore, mempool mempool.Mempool, evpool evidencePool, options ...StateOption) *State",
                    usage="Create a new consensus state machine.",
                    category="infrastructure",
                    file="consensus/state.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.NewBlock",
                    signature="func NewBlock(height int64, txs Txs, commit *Commit, evidence []Evidence) *Block",
                    usage="Create a new block.",
                    category="constructor",
                    file="types/block.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.MakeCommit",
                    signature="func MakeCommit(blockID BlockID, height int64, round int32, voteSet *VoteSet, validators []PrivValidator, now time.Time) (*Commit, error)",
                    usage="Create a commit with signatures from validators.",
                    category="constructor",
                    file="types/vote.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.NewVote",
                    signature="func NewVote(vType SignedMsgType, height int64, round int32, blockID BlockID, timestamp time.Time) *Vote",
                    usage="Create a new vote message.",
                    category="constructor",
                    file="types/vote.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="State.SetProposal",
                    signature="func (cs *State) SetProposal(proposal *types.Proposal, peerID p2p.ID) error",
                    usage="Set a proposal for the current round.",
                    category="entry_point",
                    file="consensus/state.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="State.AddVote",
                    signature="func (cs *State) AddVote(vote *types.Vote, peerID p2p.ID) (added bool, err error)",
                    usage="Add a vote to the current consensus round.",
                    category="entry_point",
                    file="consensus/state.go",
                )
            ),
        ]
    )

    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Directly modifying consensus state Height/Round",
                    reason="State transitions must follow the state machine.",
                    suggestion="Use proper message flow: Proposal -> Prevote -> Precommit -> Commit",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Creating votes without valid validator signatures",
                    reason="Signature verification is enforced.",
                    suggestion="Use test validators with proper keys.",
                )
            ),
        ]
    )

    ctx.notes = [
        "CometBFT (formerly Tendermint) uses PBFT-style consensus",
        "Consensus phases: NewHeight -> Propose -> Prevote -> Precommit -> Commit",
        "Vote types: PrevoteType, PrecommitType",
        "Evidence is for detecting byzantine behavior",
        "BlockID uniquely identifies a block (hash + parts)",
    ]

    return ctx


def analyze_bitcoin(repo_path: Path) -> RepoContext:
    """Analyze the Bitcoin Core repository"""
    ctx = RepoContext(
        repo_name="bitcoin",
        language="cpp",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "test_framework": {
            "method": "Boost.Test",
            "description": "Unit tests use Boost.Test with BOOST_AUTO_TEST_CASE / BOOST_FIXTURE_TEST_SUITE macros",
            "file": "src/test/main.cpp",
        },
        "fixtures": {
            "method": "BasicTestingSetup / ChainTestingSetup / TestingSetup / TestChain100Setup",
            "description": "Hierarchical test fixtures: Basic (args/ECC) -> Chain (chainstate/mempool) -> Testing (full node) -> TestChain100 (pre-mined 100 blocks)",
            "file": "src/test/util/setup_common.h",
        },
        "block_creation": {
            "method": "TestChain100Setup::CreateAndProcessBlock / CreateBlock",
            "description": "Create blocks with transactions and optionally process them into the chain",
            "file": "src/test/util/setup_common.h",
        },
        "transaction_creation": {
            "method": "TestChain100Setup::CreateValidTransaction / CreateValidMempoolTransaction",
            "description": "Create valid transactions spending from coinbase outputs",
            "file": "src/test/util/setup_common.h",
        },
    }

    # Valid APIs - Test Infrastructure
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="BasicTestingSetup",
                    signature="struct BasicTestingSetup",
                    usage="Minimal test fixture: args manager, logging, ECC context, random seeding. Use for tests that don't need blockchain state.",
                    category="infrastructure",
                    file="src/test/util/setup_common.h",
                    example="""BOOST_FIXTURE_TEST_SUITE(my_tests, BasicTestingSetup)
BOOST_AUTO_TEST_CASE(basic_test) { /* ... */ }
BOOST_AUTO_TEST_SUITE_END()""",
                )
            ),
            asdict(
                ValidAPI(
                    name="TestingSetup",
                    signature="struct TestingSetup : ChainTestingSetup",
                    usage="Full node test fixture with chainstate, mempool, and validation. Use for consensus/validation tests.",
                    category="infrastructure",
                    file="src/test/util/setup_common.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="TestChain100Setup",
                    signature="struct TestChain100Setup : TestingSetup",
                    usage="Pre-mines 100 blocks with spendable coinbase. Use for tests that need existing chain state and UTXOs.",
                    category="infrastructure",
                    file="src/test/util/setup_common.h",
                    example="""BOOST_FIXTURE_TEST_SUITE(my_tests, TestChain100Setup)
BOOST_AUTO_TEST_CASE(spend_test) {
    auto tx = CreateValidTransaction(/* ... */);
    auto block = CreateAndProcessBlock({tx}, scriptPubKey);
}
BOOST_AUTO_TEST_SUITE_END()""",
                )
            ),
        ]
    )

    # Valid APIs - Consensus Entry Points
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="CheckBlock",
                    signature="bool CheckBlock(const CBlock& block, BlockValidationState& state, const Consensus::Params& consensusParams, bool fCheckPOW = true, bool fCheckMerkleRoot = true)",
                    usage="Context-independent block validation: checks PoW, merkle root, tx validity, size limits.",
                    category="entry_point",
                    file="src/validation.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CheckProofOfWork",
                    signature="bool CheckProofOfWork(uint256 hash, unsigned int nBits, const Consensus::Params& params)",
                    usage="Verify that a block hash meets the required PoW target encoded in nBits.",
                    category="entry_point",
                    file="src/pow.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="GetNextWorkRequired",
                    signature="unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader* pblock, const Consensus::Params& params)",
                    usage="Calculate the required difficulty target for the next block.",
                    category="entry_point",
                    file="src/pow.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CalculateNextWorkRequired",
                    signature="unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params& params)",
                    usage="Core difficulty adjustment calculation based on actual vs target timespan.",
                    category="entry_point",
                    file="src/pow.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CheckTransaction",
                    signature="bool CheckTransaction(const CTransaction& tx, TxValidationState& state)",
                    usage="Context-independent transaction validation: checks for empty inputs/outputs, duplicate inputs, value ranges.",
                    category="entry_point",
                    file="src/consensus/tx_check.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="PermittedDifficultyTransition",
                    signature="bool PermittedDifficultyTransition(const Consensus::Params& params, int64_t height, uint32_t old_nbits, uint32_t new_nbits)",
                    usage="Check whether a difficulty transition between two consecutive blocks is permitted.",
                    category="entry_point",
                    file="src/pow.h",
                )
            ),
        ]
    )

    # Valid APIs - Data Constructors
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="CBlock",
                    signature="class CBlock : public CBlockHeader { std::vector<CTransactionRef> vtx; }",
                    usage="Block containing header and vector of transactions.",
                    category="constructor",
                    file="src/primitives/block.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CBlockHeader",
                    signature="class CBlockHeader { int32_t nVersion; uint256 hashPrevBlock; uint256 hashMerkleRoot; uint32_t nTime; uint32_t nBits; uint32_t nNonce; }",
                    usage="Block header with all fields needed for PoW validation.",
                    category="constructor",
                    file="src/primitives/block.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CTransaction",
                    signature="class CTransaction { const std::vector<CTxIn> vin; const std::vector<CTxOut> vout; const int32_t nVersion; const uint32_t nLockTime; }",
                    usage="Immutable transaction. Use CMutableTransaction for construction, then convert.",
                    category="constructor",
                    file="src/primitives/transaction.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CMutableTransaction",
                    signature="struct CMutableTransaction { std::vector<CTxIn> vin; std::vector<CTxOut> vout; int32_t nVersion; uint32_t nLockTime; }",
                    usage="Mutable transaction for building transactions in tests. Convert to CTransaction via MakeTransactionRef().",
                    category="constructor",
                    file="src/primitives/transaction.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="Consensus::Params",
                    signature="struct Params { uint256 hashGenesisBlock; int nSubsidyHalvingInterval; uint256 powLimit; ... }",
                    usage="Consensus parameters including PoW limits, deployment heights, and target timing.",
                    category="constructor",
                    file="src/consensus/params.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="CreateChainParams",
                    signature="std::unique_ptr<const CChainParams> CreateChainParams(const ArgsManager& args, ChainType chain)",
                    usage="Create chain parameters for mainnet/testnet/regtest. Use ChainType::REGTEST for testing.",
                    category="constructor",
                    file="src/chainparams.h",
                )
            ),
        ]
    )

    # Valid APIs - Helpers
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="GetBlockSubsidy",
                    signature="CAmount GetBlockSubsidy(int nHeight, const Consensus::Params& consensusParams)",
                    usage="Calculate the block reward (subsidy) at a given height.",
                    category="helper",
                    file="src/validation.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockMerkleRoot",
                    signature="uint256 BlockMerkleRoot(const CBlock& block, bool* mutated = nullptr)",
                    usage="Compute the Merkle root of a block's transactions.",
                    category="helper",
                    file="src/consensus/merkle.h",
                )
            ),
            asdict(
                ValidAPI(
                    name="HasReason",
                    signature="class HasReason { explicit HasReason(std::string_view reason); }",
                    usage="Test predicate for BOOST_CHECK_EXCEPTION to match validation error reasons.",
                    category="helper",
                    file="src/test/util/common.h",
                    example='BOOST_CHECK_EXCEPTION(/* code */, std::runtime_error, HasReason("bad-txns-vin-empty"));',
                )
            ),
        ]
    )

    # Forbidden Patterns
    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Directly modifying CTransaction fields after construction",
                    reason="CTransaction is immutable. All fields are const.",
                    suggestion="Use CMutableTransaction to build, then convert via MakeTransactionRef().",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Hardcoding difficulty targets or nBits values",
                    reason="Target encoding is compact (nBits) and chain-dependent.",
                    suggestion="Use Consensus::Params::powLimit or GetNextWorkRequired() for correct targets.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Skipping merkle root computation for test blocks",
                    reason="CheckBlock verifies merkle root by default; invalid roots cause rejection.",
                    suggestion="Use BlockMerkleRoot() to compute correct merkle root, or use CreateAndProcessBlock() which handles this.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Using mainnet consensus params in tests",
                    reason="Mainnet has high difficulty and long target spacing, making tests slow or impossible.",
                    suggestion="Use ChainType::REGTEST which has minimal difficulty and instant mining.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Manually computing block hashes instead of using GetHash()",
                    reason="Block hash computation includes all header fields; manual hashing may miss fields.",
                    suggestion="Use CBlockHeader::GetHash() for correct block hash.",
                )
            ),
        ]
    )

    ctx.notes = [
        "Bitcoin uses Nakamoto consensus (PoW-based probabilistic BFT)",
        "Fault tolerance: < 50% of total hashpower can be adversarial",
        "Consensus-critical code: src/consensus/ (rules), src/pow.cpp (PoW), src/validation.cpp (block/tx validation), src/script/ (script interpreter)",
        "Test fixtures: BasicTestingSetup -> ChainTestingSetup -> TestingSetup -> TestChain100Setup",
        "TestChain100Setup provides 100 pre-mined blocks with spendable coinbase via m_coinbase_txns",
        "Block validation pipeline: CheckBlock() -> AcceptBlock() -> ConnectBlock()",
        "Difficulty adjustment occurs every 2016 blocks (params.DifficultyAdjustmentInterval())",
        "UTXO model: transactions consume UTXOs (inputs) and create new UTXOs (outputs)",
        "Script validation uses a stack-based interpreter in src/script/interpreter.cpp",
        "Use regtest (ChainType::REGTEST) for testing: allows instant mining with minimal difficulty",
    ]

    return ctx


def analyze_geth(repo_path: Path) -> RepoContext:
    """Analyze the go-ethereum (Geth) repository"""
    ctx = RepoContext(
        repo_name="go-ethereum",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "consensus_engine": {
            "method": "ethash.NewFaker()",
            "description": "Creates a fake ethash engine that skips PoW verification. Standard for unit tests.",
            "file": "consensus/ethash/ethash.go",
        },
        "chain_setup": {
            "method": "core.NewBlockChain / core.GenerateChainWithGenesis",
            "description": "NewBlockChain creates a full blockchain instance; GenerateChainWithGenesis produces test chains from a Genesis spec",
            "file": "core/blockchain.go / core/chain_makers.go",
        },
        "block_generation": {
            "method": "core.GenerateChain / BlockGen",
            "description": "GenerateChain creates N blocks; the callback receives a BlockGen to add txs, set coinbase, add uncles, etc.",
            "file": "core/chain_makers.go",
        },
        "state_database": {
            "method": "rawdb.NewMemoryDatabase()",
            "description": "In-memory database backend for testing (no disk I/O)",
            "file": "core/rawdb/database.go",
        },
        "evm": {
            "method": "vm.NewEVM(blockCtx, statedb, chainConfig, vmConfig)",
            "description": "Creates a new EVM instance for transaction execution",
            "file": "core/vm/evm.go",
        },
    }

    # Valid APIs - Infrastructure
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="ethash.NewFaker",
                    signature="func NewFaker() *Ethash",
                    usage="Creates a fake ethash engine that accepts all blocks without PoW verification. REQUIRED for most tests.",
                    category="infrastructure",
                    file="consensus/ethash/ethash.go",
                    example="""engine := ethash.NewFaker()
// Use with NewBlockChain or GenerateChain""",
                )
            ),
            asdict(
                ValidAPI(
                    name="ethash.NewFakeFailer",
                    signature="func NewFakeFailer(fail uint64) *Ethash",
                    usage="Like NewFaker but rejects the block at the specified height. Useful for testing block validation failures.",
                    category="infrastructure",
                    file="consensus/ethash/ethash.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.NewBlockChain",
                    signature="func NewBlockChain(db ethdb.Database, genesis *Genesis, engine consensus.Engine, cfg *BlockChainConfig) (*BlockChain, error)",
                    usage="Create a full blockchain instance with state, validator, and processor. Pass nil cfg for defaults.",
                    category="infrastructure",
                    file="core/blockchain.go",
                    example="""blockchain, _ := core.NewBlockChain(rawdb.NewMemoryDatabase(), genesis, engine, nil)
defer blockchain.Stop()""",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.GenerateChain",
                    signature="func GenerateChain(config *params.ChainConfig, parent *types.Block, engine consensus.Engine, db ethdb.Database, n int, gen func(int, *BlockGen)) ([]*types.Block, []types.Receipts)",
                    usage="Generate a chain of N blocks starting from parent. The gen callback customizes each block (add txs, set coinbase, etc.).",
                    category="infrastructure",
                    file="core/chain_makers.go",
                    example="""blocks, _ := core.GenerateChain(params.TestChainConfig, genesis, engine, db, 10, func(i int, gen *core.BlockGen) {
    gen.SetCoinbase(common.Address{1})
    // gen.AddTx(tx)
})""",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.GenerateChainWithGenesis",
                    signature="func GenerateChainWithGenesis(genesis *Genesis, engine consensus.Engine, n int, gen func(int, *BlockGen)) (ethdb.Database, []*types.Block, []types.Receipts)",
                    usage="Like GenerateChain but also creates the database and commits the genesis block. Returns db, blocks, receipts.",
                    category="infrastructure",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="rawdb.NewMemoryDatabase",
                    signature="func NewMemoryDatabase() ethdb.Database",
                    usage="Create an in-memory database for testing. No persistence.",
                    category="infrastructure",
                    file="core/rawdb/database.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="vm.NewEVM",
                    signature="func NewEVM(blockCtx BlockContext, statedb StateDB, chainConfig *params.ChainConfig, config Config) *EVM",
                    usage="Create a new EVM instance. BlockContext contains block number, timestamp, difficulty, etc.",
                    category="infrastructure",
                    file="core/vm/evm.go",
                )
            ),
        ]
    )

    # Valid APIs - Consensus Entry Points
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="consensus.Engine.VerifyHeader",
                    signature="VerifyHeader(chain ChainHeaderReader, header *types.Header) error",
                    usage="Verify a block header conforms to consensus rules (difficulty, gas limit, timestamp, etc.).",
                    category="entry_point",
                    file="consensus/consensus.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="consensus.Engine.VerifyUncles",
                    signature="VerifyUncles(chain ChainReader, block *types.Block) error",
                    usage="Verify that a block's uncles conform to consensus rules.",
                    category="entry_point",
                    file="consensus/consensus.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="consensus.Engine.CalcDifficulty",
                    signature="CalcDifficulty(chain ChainHeaderReader, time uint64, parent *types.Header) *big.Int",
                    usage="Calculate the required difficulty for the next block given timestamp and parent header.",
                    category="entry_point",
                    file="consensus/consensus.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="consensus.Engine.Finalize",
                    signature="Finalize(chain ChainHeaderReader, header *types.Header, state vm.StateDB, body *types.Body)",
                    usage="Run post-transaction state modifications (block rewards, withdrawals). Does not assemble the block.",
                    category="entry_point",
                    file="consensus/consensus.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockValidator.ValidateBody",
                    signature="func (v *BlockValidator) ValidateBody(block *types.Block) error",
                    usage="Validate block body: uncle hash, tx root, withdrawals hash, blob gas, ancestor existence.",
                    category="entry_point",
                    file="core/block_validator.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockValidator.ValidateState",
                    signature="func (v *BlockValidator) ValidateState(block *types.Block, statedb *state.StateDB, res *ProcessResult, stateless bool) error",
                    usage="Validate post-execution state: gas used, bloom, receipt root, state root.",
                    category="entry_point",
                    file="core/block_validator.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.ApplyTransaction",
                    signature="func ApplyTransaction(evm *vm.EVM, gp *GasPool, statedb *state.StateDB, header *types.Header, tx *types.Transaction) (*types.Receipt, error)",
                    usage="Apply a single transaction to the state using the EVM. Returns receipt.",
                    category="entry_point",
                    file="core/state_processor.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="ethash.CalcDifficulty",
                    signature="func CalcDifficulty(config *params.ChainConfig, time uint64, parent *types.Header) *big.Int",
                    usage="Calculate PoW difficulty for the next block. Dispatches to the correct EIP-based algorithm.",
                    category="entry_point",
                    file="consensus/ethash/consensus.go",
                )
            ),
        ]
    )

    # Valid APIs - Data Constructors
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="types.NewBlock",
                    signature="func NewBlock(header *Header, body *Body, receipts []*Receipt, hasher TrieHasher) *Block",
                    usage="Create a new block from header, body (txs + uncles + withdrawals), and receipts.",
                    category="constructor",
                    file="core/types/block.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.NewTransaction",
                    signature="func NewTransaction(nonce uint64, to common.Address, amount *big.Int, gasLimit uint64, gasPrice *big.Int, data []byte) *Transaction",
                    usage="Create a legacy transaction. For EIP-1559 use NewTx with DynamicFeeTx inner.",
                    category="constructor",
                    file="core/types/transaction.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.NewTx",
                    signature="func NewTx(inner TxData) *Transaction",
                    usage="Create a transaction from typed inner data (LegacyTx, AccessListTx, DynamicFeeTx, BlobTx).",
                    category="constructor",
                    file="core/types/transaction.go",
                    example="""tx := types.NewTx(&types.DynamicFeeTx{
    ChainID:   chainID,
    Nonce:     nonce,
    GasTipCap: big.NewInt(1),
    GasFeeCap: big.NewInt(1000000000),
    Gas:       21000,
    To:        &to,
    Value:     big.NewInt(1),
})""",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.Genesis",
                    signature="type Genesis struct { Config *params.ChainConfig; Nonce uint64; Timestamp uint64; ExtraData []byte; GasLimit uint64; Difficulty *big.Int; Alloc types.GenesisAlloc; ... }",
                    usage="Genesis specification for creating test chains. Set Config, BaseFee, Difficulty, Alloc for test accounts.",
                    category="constructor",
                    file="core/genesis.go",
                    example="""genesis := &core.Genesis{
    Config:     params.AllEthashProtocolChanges,
    BaseFee:    big.NewInt(params.InitialBaseFee),
    Difficulty: big.NewInt(1),
    Alloc: types.GenesisAlloc{
        addr: {Balance: big.NewInt(1000000000000000000)},
    },
}""",
                )
            ),
            asdict(
                ValidAPI(
                    name="params.AllEthashProtocolChanges",
                    signature="var AllEthashProtocolChanges *ChainConfig",
                    usage="ChainConfig with all Ethereum hard forks enabled (ethash PoW). Standard for tests.",
                    category="constructor",
                    file="params/config.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="params.TestChainConfig",
                    signature="var TestChainConfig *ChainConfig",
                    usage="Alias for AllEthashProtocolChanges. Common in test code.",
                    category="constructor",
                    file="params/config.go",
                )
            ),
        ]
    )

    # Valid APIs - Helpers
    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="BlockGen.SetCoinbase",
                    signature="func (b *BlockGen) SetCoinbase(addr common.Address)",
                    usage="Set the coinbase (miner) of the generated block. Must be called before adding transactions.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.AddTx",
                    signature="func (b *BlockGen) AddTx(tx *types.Transaction)",
                    usage="Add a signed transaction to the generated block.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.AddTxWithChain",
                    signature="func (b *BlockGen) AddTxWithChain(bc *BlockChain, tx *types.Transaction)",
                    usage="Add a signed transaction with full chain context (needed for cross-references).",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.AddUncle",
                    signature="func (b *BlockGen) AddUncle(h *types.Header)",
                    usage="Add an uncle header to the generated block. Difficulty is auto-calculated.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.PrevBlock",
                    signature="func (b *BlockGen) PrevBlock(index int) *types.Block",
                    usage="Get a previously generated block by index. Index -1 returns the parent block.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.TxNonce",
                    signature="func (b *BlockGen) TxNonce(addr common.Address) uint64",
                    usage="Get the next valid nonce for an account. Panics if account does not exist.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="BlockGen.OffsetTime",
                    signature="func (b *BlockGen) OffsetTime(seconds int64)",
                    usage="Modify block timestamp, implicitly changing difficulty. Useful for testing fork choice and difficulty.",
                    category="helper",
                    file="core/chain_makers.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.SignTx",
                    signature="func SignTx(tx *Transaction, s Signer, prv *ecdsa.PrivateKey) (*Transaction, error)",
                    usage="Sign a transaction with a private key using the given signer.",
                    category="helper",
                    file="core/types/transaction_signing.go",
                    example="""signedTx, err := types.SignTx(tx, types.NewEIP155Signer(chainID), privateKey)""",
                )
            ),
            asdict(
                ValidAPI(
                    name="types.MakeSigner",
                    signature="func MakeSigner(config *params.ChainConfig, blockNumber *big.Int, blockTime uint64) Signer",
                    usage="Create the appropriate transaction signer for a given block context.",
                    category="helper",
                    file="core/types/transaction_signing.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="core.CalcGasLimit",
                    signature="func CalcGasLimit(parentGasLimit, desiredLimit uint64) uint64",
                    usage="Compute the gas limit for the next block given parent gas limit and desired target.",
                    category="helper",
                    file="core/block_validator.go",
                )
            ),
            asdict(
                ValidAPI(
                    name="crypto.GenerateKey",
                    signature="func GenerateKey() (*ecdsa.PrivateKey, error)",
                    usage="Generate a new ECDSA private key for test accounts.",
                    category="helper",
                    file="crypto/crypto.go",
                    example="""key, _ := crypto.GenerateKey()
addr := crypto.PubkeyToAddress(key.PublicKey)""",
                )
            ),
            asdict(
                ValidAPI(
                    name="newCanonical",
                    signature="func newCanonical(engine consensus.Engine, n int, full bool, scheme string) (ethdb.Database, *Genesis, *BlockChain, error)",
                    usage="Test-local helper: creates a chain database with a deterministic canonical chain of n blocks.",
                    category="helper",
                    file="core/blockchain_test.go",
                    example="""db, gspec, chain, err := newCanonical(ethash.NewFaker(), 10, true, rawdb.HashScheme)
defer chain.Stop()""",
                )
            ),
        ]
    )

    # Forbidden Patterns
    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Using real PoW mining in tests",
                    reason="Real ethash mining is extremely slow and non-deterministic.",
                    suggestion="Use ethash.NewFaker() for all tests. Use ethash.NewFakeFailer(n) to test block rejection at height n.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Directly modifying state.StateDB trie nodes",
                    reason="Internal trie manipulation bypasses state accounting and will cause root mismatches.",
                    suggestion="Use StateDB's public API: SetBalance, SetNonce, SetCode, SetState, AddBalance.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Hardcoding gas prices or limits without checking chain config",
                    reason="Gas mechanics change across forks (EIP-1559 base fee, EIP-4844 blob gas). Hardcoded values break on fork boundaries.",
                    suggestion="Use params.InitialBaseFee, header.BaseFee, and types.MakeSigner for fork-aware values.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Creating transactions without proper signing",
                    reason="Unsigned or incorrectly signed transactions are rejected by the EVM and state processor.",
                    suggestion="Always use types.SignTx with the correct Signer for the fork. Use types.MakeSigner(config, blockNum, blockTime).",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Forgetting defer blockchain.Stop() after NewBlockChain",
                    reason="BlockChain starts background goroutines that leak if not stopped.",
                    suggestion="Always call defer blockchain.Stop() immediately after creation.",
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern="Using mainnet ChainConfig in tests",
                    reason="Mainnet config has specific fork block numbers that complicate test logic.",
                    suggestion="Use params.AllEthashProtocolChanges or params.TestChainConfig for tests.",
                )
            ),
        ]
    )

    ctx.notes = [
        "go-ethereum uses ethash.NewFaker() as the standard consensus engine for tests (skips PoW)",
        "Core test pattern: Genesis -> GenerateChain (with BlockGen callback) -> NewBlockChain -> InsertChain",
        "Package core/types contains: Block, Header, Transaction, Receipt, Log, Withdrawal",
        "Consensus engines implement consensus.Engine interface: VerifyHeader, CalcDifficulty, Finalize, Seal",
        "Three consensus engines: ethash (PoW), beacon (PoS post-Merge), clique (PoA for testnets)",
        "State transitions: StateProcessor.Process executes txs -> StateDB modified -> BlockValidator.ValidateState checks roots",
        "Key forks affecting consensus: Homestead, Byzantium, Constantinople, Istanbul, London (EIP-1559), Paris (Merge), Shanghai, Cancun (EIP-4844)",
        "EVM test helpers: vm.NewEVM creates an EVM instance, core.ApplyTransaction applies a single tx",
        "Test accounts: use crypto.GenerateKey() and crypto.PubkeyToAddress(key.PublicKey) for deterministic test addresses",
        "BlockGen callback methods: SetCoinbase, AddTx, AddUncle, AddWithdrawal, OffsetTime, TxNonce, PrevBlock",
        "rawdb.NewMemoryDatabase() is the standard in-memory DB for tests (no disk persistence)",
        "params.AllEthashProtocolChanges enables all forks with ethash consensus for testing",
    ]

    return ctx


def analyze_avalanchego(repo_path: Path) -> RepoContext:
    """Analyze the AvalancheGo repository"""
    ctx = RepoContext(
        repo_name="avalanchego",
        language="go",
        commit_hash=get_commit_hash(repo_path),
        analyzed_at=datetime.now().isoformat(),
    )

    ctx.test_infrastructure = {
        "consensus_parameters": {
            "method": "snowball.Parameters{}",
            "description": (
                "Snowball consensus parameters: K (sample size), AlphaPreference, "
                "AlphaConfidence (vote thresholds), Beta (consecutive confidence rounds "
                "for finalization), ConcurrentRepolls, OptimalProcessing, "
                "MaxOutstandingItems, MaxItemProcessingTime."
            ),
            "file": "snow/consensus/snowball/parameters.go",
        },
        "default_parameters": {
            "method": "snowball.DefaultParameters",
            "description": (
                "Default production parameters: K=20, AlphaPreference=15, "
                "AlphaConfidence=15, Beta=20, ConcurrentRepolls=4, OptimalProcessing=10, "
                "MaxOutstandingItems=256, MaxItemProcessingTime=30s."
            ),
            "file": "snow/consensus/snowball/parameters.go",
        },
        "test_context": {
            "method": "snowtest.Context(tb, chainID) / snowtest.ConsensusContext(ctx)",
            "description": (
                "Creates a full snow.Context with BLS keys, shared memory, validators, "
                "logging, etc. ConsensusContext wraps it with Prometheus registry and "
                "noOp acceptors. Standard for all consensus unit tests."
            ),
            "file": "snow/snowtest/context.go",
        },
        "test_blocks": {
            "method": "snowmantest.BuildChild(parent) / snowmantest.BuildChain(length)",
            "description": (
                "Creates test blocks for Snowman consensus tests. BuildChild creates a "
                "single child block. BuildChain creates a genesis + descendants chain. "
                "snowmantest.Genesis is the pre-built genesis block."
            ),
            "file": "snow/consensus/snowman/snowmantest/block.go",
        },
        "consensus_factory": {
            "method": "Factory interface / factory.New()",
            "description": (
                "Snowman consensus implementations use the Factory pattern. factory.New() "
                "returns a Consensus instance. runConsensusTests(t, factory) runs the "
                "full test suite against any implementation."
            ),
            "file": "snow/consensus/snowman/factory.go",
        },
        "memory_database": {
            "method": "memdb.New()",
            "description": "In-memory database for testing (no disk I/O).",
            "file": "database/memdb/memdb.go",
        },
    }

    ctx.valid_apis.extend(
        [
            asdict(
                ValidAPI(
                    name="snowball.Parameters",
                    signature=(
                        "type Parameters struct { K int; AlphaPreference int; "
                        "AlphaConfidence int; Beta int; ConcurrentRepolls int; "
                        "OptimalProcessing int; MaxOutstandingItems int; "
                        "MaxItemProcessingTime time.Duration }"
                    ),
                    usage=(
                        "Configure consensus parameters. Must satisfy: "
                        "K/2 < AlphaPreference <= AlphaConfidence <= K, "
                        "0 < ConcurrentRepolls <= Beta."
                    ),
                    category="infrastructure",
                    file="snow/consensus/snowball/parameters.go",
                    example=(
                        "params := snowball.Parameters{\n"
                        "    K: 1, AlphaPreference: 1, AlphaConfidence: 1,\n"
                        "    Beta: 3, ConcurrentRepolls: 1, OptimalProcessing: 1,\n"
                        "    MaxOutstandingItems: 1, MaxItemProcessingTime: 1,\n"
                        "}"
                    ),
                )
            ),
            asdict(
                ValidAPI(
                    name="snowman.Consensus.Initialize",
                    signature=(
                        "Initialize(ctx *snow.ConsensusContext, params snowball.Parameters, "
                        "lastAcceptedID ids.ID, lastAcceptedHeight uint64, "
                        "lastAcceptedTime time.Time) error"
                    ),
                    usage=(
                        "Initialize a Snowman consensus instance with context, parameters, "
                        "and last accepted block info."
                    ),
                    category="entry_point",
                    file="snow/consensus/snowman/consensus.go",
                    example=(
                        "sm := factory.New()\n"
                        "require.NoError(sm.Initialize(ctx, params, "
                        "snowmantest.GenesisID, snowmantest.GenesisHeight, "
                        "snowmantest.GenesisTimestamp))"
                    ),
                )
            ),
            asdict(
                ValidAPI(
                    name="snowman.Consensus.Add",
                    signature="Add(Block) error",
                    usage=(
                        "Add a new block to the consensus instance. Parent must be "
                        "last accepted or currently processing."
                    ),
                    category="entry_point",
                    file="snow/consensus/snowman/consensus.go",
                    example=(
                        "block := snowmantest.BuildChild(snowmantest.Genesis)\n"
                        "require.NoError(sm.Add(block))"
                    ),
                )
            ),
            asdict(
                ValidAPI(
                    name="snowman.Consensus.RecordPoll",
                    signature="RecordPoll(context.Context, bag.Bag[ids.ID]) error",
                    usage=(
                        "Record the results of a network poll. The bag contains voted "
                        "block IDs with counts. Drives voting toward finalization."
                    ),
                    category="entry_point",
                    file="snow/consensus/snowman/consensus.go",
                    example=(
                        "votes := bag.Of(blockID)\n"
                        "require.NoError(sm.RecordPoll(context.Background(), votes))"
                    ),
                )
            ),
            asdict(
                ValidAPI(
                    name="snowmantest.BuildChild",
                    signature="func BuildChild(parent *Block) *Block",
                    usage=(
                        "Create a test block that is a child of the given parent. "
                        "Generates a random ID and inherits parent's timestamp."
                    ),
                    category="helper",
                    file="snow/consensus/snowman/snowmantest/block.go",
                    example="child := snowmantest.BuildChild(snowmantest.Genesis)",
                )
            ),
            asdict(
                ValidAPI(
                    name="snowmantest.BuildChain",
                    signature="func BuildChain(length int) []*Block",
                    usage=(
                        "Build a linear chain of test blocks starting from genesis. "
                        "chain[0] is genesis (Accepted), chain[1..] are undecided."
                    ),
                    category="helper",
                    file="snow/consensus/snowman/snowmantest/block.go",
                    example="chain := snowmantest.BuildChain(5)",
                )
            ),
            asdict(
                ValidAPI(
                    name="snowtest.Context",
                    signature="func Context(tb testing.TB, chainID ids.ID) *snow.Context",
                    usage=(
                        "Create a full test snow.Context with BLS keys, shared memory, "
                        "validator state, logging, etc."
                    ),
                    category="helper",
                    file="snow/snowtest/context.go",
                    example="snowCtx := snowtest.Context(t, snowtest.CChainID)",
                )
            ),
            asdict(
                ValidAPI(
                    name="snowtest.ConsensusContext",
                    signature=(
                        "func ConsensusContext(ctx *snow.Context) *snow.ConsensusContext"
                    ),
                    usage=(
                        "Wrap a snow.Context into a ConsensusContext with Prometheus "
                        "registry and noOp acceptors."
                    ),
                    category="helper",
                    file="snow/snowtest/context.go",
                    example=(
                        "ctx := snowtest.ConsensusContext("
                        "snowtest.Context(t, snowtest.CChainID))"
                    ),
                )
            ),
            asdict(
                ValidAPI(
                    name="bag.Of",
                    signature="func Of[T comparable](elts ...T) Bag[T]",
                    usage=(
                        "Create a Bag from elements. Used to construct poll results "
                        "for RecordPoll."
                    ),
                    category="helper",
                    file="utils/bag/bag.go",
                    example="votes := bag.Of(blockA.ID(), blockA.ID(), blockB.ID())",
                )
            ),
            asdict(
                ValidAPI(
                    name="ids.GenerateTestID",
                    signature="func GenerateTestID() ID",
                    usage=(
                        "Generate a unique random test ID. Used extensively in tests."
                    ),
                    category="helper",
                    file="ids/test_generator.go",
                )
            ),
        ]
    )

    ctx.forbidden_patterns.extend(
        [
            asdict(
                ForbiddenPattern(
                    pattern="Using real networking or P2P connections in unit tests",
                    reason=(
                        "Real networking introduces non-determinism and flakiness."
                    ),
                    suggestion=(
                        "Use enginetest.Sender, sendermock, or direct function calls "
                        "for message passing in tests."
                    ),
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern=(
                        "Using snowball.DefaultParameters directly in tests"
                    ),
                    reason=(
                        "Default parameters (K=20) require 20 validators. "
                        "Test parameters should be minimal."
                    ),
                    suggestion=(
                        "Use minimal parameters: K=1, AlphaPreference=1, "
                        "AlphaConfidence=1, Beta=1-3, ConcurrentRepolls=1."
                    ),
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern=(
                        "Violating parameter constraints: "
                        "K/2 < AlphaPreference <= AlphaConfidence <= K"
                    ),
                    reason=(
                        "Parameters.Verify() will fail and consensus initialization "
                        "will return an error."
                    ),
                    suggestion=(
                        "Always ensure K/2 < AlphaPreference <= AlphaConfidence <= K "
                        "and 0 < ConcurrentRepolls <= Beta."
                    ),
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern=(
                        "Calling Add() with a block whose parent is not accepted "
                        "or processing"
                    ),
                    reason=(
                        "The consensus instance will return an error for orphan blocks."
                    ),
                    suggestion=(
                        "Always add blocks in topological order: parent must be "
                        "accepted or processing."
                    ),
                )
            ),
            asdict(
                ForbiddenPattern(
                    pattern=(
                        "Forgetting to call Initialize() before using Consensus"
                    ),
                    reason=(
                        "Uninitialized consensus will panic or return incorrect results."
                    ),
                    suggestion=(
                        "Always call sm.Initialize(ctx, params, genesisID, "
                        "genesisHeight, genesisTimestamp) first."
                    ),
                )
            ),
        ]
    )

    ctx.notes = [
        (
            "AvalancheGo implements three consensus protocols: Snowball "
            "(binary/multi-choice voting), Snowman (linear chain), and Simplex "
            "(BFT block proposal)"
        ),
        (
            "Snowball is the fundamental voting primitive; Snowman builds on it "
            "for linear blockchain consensus"
        ),
        (
            "Key consensus flow: Add block -> validators sample peers -> "
            "RecordPoll with votes -> repeat until Beta consecutive successful "
            "polls -> block is Accepted"
        ),
        (
            "Consensus parameters: K=sample size, AlphaPreference/AlphaConfidence"
            "=vote thresholds, Beta=consecutive confidence rounds for finalization"
        ),
        (
            "Parameter constraints: K/2 < AlphaPreference <= AlphaConfidence <= K, "
            "0 < ConcurrentRepolls <= Beta"
        ),
        (
            "Test pattern: factory.New() -> Initialize -> Add blocks -> "
            "RecordPoll with vote bags -> check Preference/Finalized"
        ),
        (
            "snowmantest.Genesis is the standard genesis block (height=0, Accepted)"
        ),
        (
            "snowmantest.BuildChild(parent) creates a child block; "
            "snowmantest.BuildChain(n) creates genesis + n-1 descendants"
        ),
        (
            "snowtest.Context(t, chainID) creates a full test context; "
            "snowtest.ConsensusContext(ctx) wraps it for consensus use"
        ),
        (
            "Topological (snow/consensus/snowman/topological.go) is the main "
            "Snowman consensus implementation"
        ),
        "Tests use require (testify) assertions extensively",
        "Module path: github.com/ava-labs/avalanchego",
        (
            "Simplex consensus (simplex/) is a newer BFT protocol for block "
            "proposal and agreement"
        ),
        (
            "snow/engine/snowman/ contains the Snowman engine connecting "
            "consensus to the VM and P2P layer"
        ),
        (
            "Mock implementations: snowmanmock.Block, enginetest.Sender, "
            "blocktest.VM"
        ),
    ]

    return ctx


def save_context(ctx: RepoContext, output_dir: Path) -> None:
    """Save repo context to JSON file"""
    output_file = output_dir / f"{ctx.repo_name}.json"

    data = {
        "repo_name": ctx.repo_name,
        "language": ctx.language,
        "commit_hash": ctx.commit_hash,
        "analyzed_at": ctx.analyzed_at,
        "test_infrastructure": ctx.test_infrastructure,
        "valid_apis": ctx.valid_apis,
        "forbidden_patterns": ctx.forbidden_patterns,
        "notes": ctx.notes,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✓ Generated {output_file}")


def main():
    """Main entry point"""
    # Determine paths
    script_dir = Path(__file__).parent
    agent_dir = script_dir.parent
    project_root = agent_dir.parent
    output_dir = agent_dir / "data" / "repo_knowledge"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Project root: {project_root}")
    print(f"Output directory: {output_dir}")
    print()

    # Repositories to analyze
    repos = {
        "hotstuff": project_root / "hotstuff",
        "efficient-epaxos": project_root / "efficient-epaxos",
        "raft": project_root / "raft",
        "hashicorp-raft": project_root / "hashicorp-raft",
        "cometbft": project_root / "cometbft",
        "bitcoin": project_root / "bitcoin",
        "go-ethereum": project_root / "go-ethereum",
        "avalanchego": project_root / "avalanchego",
    }

    analyzers = {
        "hotstuff": analyze_hotstuff,
        "efficient-epaxos": analyze_efficient_epaxos,
        "raft": analyze_raft,
        "hashicorp-raft": analyze_hashicorp_raft,
        "cometbft": analyze_cometbft,
        "bitcoin": analyze_bitcoin,
        "go-ethereum": analyze_geth,
        "avalanchego": analyze_avalanchego,
    }

    # Analyze each repository
    for name, path in repos.items():
        if not path.exists():
            print(f"⚠ Skipping {name}: directory not found at {path}")
            continue

        print(f"Analyzing {name}...")
        try:
            analyzer = analyzers.get(name)
            if analyzer:
                ctx = analyzer(path)
                save_context(ctx, output_dir)
            else:
                print(f"  No analyzer defined for {name}")
        except Exception as e:
            print(f"  Error analyzing {name}: {e}")

    print()
    print("Done! Generated context files:")
    for f in sorted(output_dir.glob("*.json")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
