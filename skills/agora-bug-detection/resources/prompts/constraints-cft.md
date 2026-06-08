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
- Malicious messages (sending forged/tampered messages)
- Double voting (voting two different ways in the same round)
- Selective broadcast (sending messages only to some nodes)
- Signature forgery (impersonating other nodes)
- Any behavior requiring a node to "intentionally act maliciously"

Remember: CFT protocols assume all nodes either work normally or stop completely — no "half-dead" or "malicious behavior".
