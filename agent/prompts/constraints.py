"""
Protocol type constraints for attack scenarios
"""

CFT_CONSTRAINT = """
## Protocol Type Constraint: CFT (Crash Fault Tolerant)

This is a CFT protocol that can only tolerate **crash faults**, not Byzantine behavior.

### Allowed Attack Methods:
- Node crash (stop running at any moment)
- Node restart (recover after crash, may lose in-memory state)
- Network partition (communication between nodes interrupted)
- Network delay (messages arrive late)
- Message loss (messages not delivered)
- Message reordering (messages arrive in different order than sent)
- Boundary conditions (extreme values, null values, overflow, etc.)
- Duplicate utilization (same resource referenced/computed multiple times)

### Prohibited Attack Methods:
- ❌ Malicious messages (sending forged/tampered messages)
- ❌ Double voting (voting two different ways in the same round)
- ❌ Selective broadcast (sending messages only to some nodes)
- ❌ Signature forgery (impersonating other nodes)
- ❌ Any behavior requiring a node to "intentionally act maliciously"

Remember: CFT protocols assume all nodes either work normally or stop completely - no "half-dead" or "malicious behavior".
"""

BFT_CONSTRAINT = """
## Protocol Type Constraint: BFT (Byzantine Fault Tolerant)

This is a BFT protocol that can tolerate **Byzantine faults** (malicious nodes).

### All Allowed Attack Methods:

**CFT-type attacks (all available):**
- Node crash/restart
- Network partition/delay/loss/reordering
- Boundary conditions, duplicate utilization

**BFT-type attacks (additionally available):**
- Equivocation: Send two different votes for the same round/height
- Malicious messages: Send invalid, tampered, or malformed messages
- Selective broadcast: Send messages only to some nodes, causing state inconsistency
- Delay/withholding: Malicious leader intentionally delays or withholds proposals
- State forgery: Forge certificates, votes, signatures, etc.
- Timing attacks: Exploit vulnerabilities in timing assumptions

### Attack Mindset:
Imagine you control up to f malicious nodes (f < n/3). How would you maximize damage?
- Can you make honest nodes accept invalid state?
- Can you prevent the system from reaching consensus (liveness attack)?
- Can you make different honest nodes see different "truths"?

Be creative! Imagine how a clever attacker would exploit the protocol's weaknesses!
"""


def get_constraint_for_protocol(protocol_type: str) -> str:
    """Get the appropriate constraint text for a protocol type"""
    if protocol_type.lower() == "bft":
        return BFT_CONSTRAINT
    else:
        return CFT_CONSTRAINT
