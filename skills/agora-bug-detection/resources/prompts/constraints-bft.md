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
