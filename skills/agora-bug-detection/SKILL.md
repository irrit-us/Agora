---
name: agora-bug-detection
description: Hunt for bugs in distributed consensus protocol implementations using a 2-agent strategy+testgen pipeline. Use when targeting consensus protocols (Raft, PBFT, HotStuff, Tendermint, etc.) for automated vulnerability discovery.
license: MIT
metadata:
  author: SherlockShemol
  version: "1.0.0"
---

# Agora Bug Detection

You are orchestrating a consensus protocol bug hunting session. Your job is to coordinate two subagents in a loop to discover real vulnerabilities.

## Setup (Auto-Discovery)

You are running inside the target protocol repository. No configuration file is needed.

1. **Discover the protocol** — spawn a lightweight subagent to quickly scan the repository:
   - Read `README.md` or equivalent
   - Check top-level files for language indicators (go.mod, Cargo.toml, pom.xml, CMakeLists.txt)
   - Determine protocol type: look for keywords like "byzantine", "BFT", "f < n/3" → BFT; otherwise assume CFT
   - Identify key source directories and test file locations
   - Produce a summary: name, type (cft/bft), language, description, key components

2. **Load constraint** — based on the discovered type, read the appropriate constraint from `resources/prompts/constraints-cft.md` or `resources/prompts/constraints-bft.md`

3. **Load bug patterns** — read `resources/patterns/index.yaml` to get a one-line summary of all known patterns. Filter by the discovered protocol type (cft/bft). Select 5-10 patterns that seem most relevant to the target protocol's architecture. Then read the full JSON files only for those selected patterns (e.g., `resources/patterns/cft/<id>.json`).

## Per-Iteration Workflow

Run 5 iterations by default (or more if the user specifies).

### Step 1: Build Strategy Context

Gather:
- Protocol summary from discovery phase
- Repository context (key components, test structure)
- Selected bug patterns (full JSON content of the 5-10 patterns chosen during setup)
- Previously rejected strategies (to avoid repeats within this session)

### Step 2: Call Strategy Agent (Subagent 1)

Spawn a subagent with:
- System prompt from `resources/prompts/strategy-system.md`
- The built context as user message
- Constraint text (CFT or BFT) included in the prompt
- No tools needed — this is pure reasoning

Parse the response for an `<attack_scenario>` block. If parsing fails, retry once with a repair prompt asking to reformat.

### Step 3: Similarity Check

Before implementing, grep existing test files to check if a similar test already exists:
- Use glob patterns appropriate for the language (e.g., `**/*_test.go`, `**/*_test.rs`)
- If a similar test covers the same attack vector, reject this strategy and loop back to Step 1

### Step 4: Call TestGen Agent (Subagent 2)

Spawn a subagent with:
- System prompt from `resources/prompts/testgen-system.md`
- The attack scenario as the task
- Working directory set to the protocol repository root
- Full tool access: file read/write, shell execution

The TestGen agent will:
1. Read the codebase to understand test structure
2. Write a test file implementing the attack scenario
3. Run the test and iterate on compilation errors
4. Report results in `<test_result>` format
5. Output `<confirmed_bug>` if a real vulnerability is found

### Step 5: Record Results

If `<confirmed_bug>` is found:
- Save bug details to `results/bugs/` in the working directory
- Include: scenario name, test file, test output, vulnerability description
- Log the pattern for future reference
- **Proceed to Step 6 (Bug Exploitation)**

If test passes (no bug): record as "protocol handles correctly" and continue to next iteration.

### Step 6: Bug Exploitation (triggered when a bug is confirmed)

When a bug is confirmed, exploit it to uncover more vulnerabilities by exploring related attack vectors.

1. **Read exploitation prompt** — load `resources/prompts/exploitation.md` as supplementary context for Strategy Agent
2. **Build exploitation context** — include the full confirmed bug info:
   - Attack scenario that triggered it
   - Test code and output
   - The vulnerability hypothesis that was proven correct
3. **Call Strategy Agent** with exploitation prompt — instruct it to:
   - Analyze the root cause and find where else the same assumption is violated
   - Generate variant attacks through different entry points or timing
   - Check if similar components have the same bug
   - Escalate severity (liveness → safety) or combine with other faults
4. **Call TestGen Agent** to implement the new exploitation scenario
5. **Repeat 2-3 times** — each attempt should explore a genuinely different angle of the same underlying weakness

If exploitation finds additional bugs, record them and optionally trigger further exploitation on those as well.

## Output

After all iterations, summarize:
- Total iterations completed
- Bugs found (with brief descriptions)
- Strategies that were rejected as duplicates
- Any errors encountered

## Important Rules

1. **Realism**: Only report bugs where the test code is correct AND the assertion failure indicates a real vulnerability
2. **No false positives**: If the test code itself is wrong, that's NOT a bug in the protocol
3. **Diversity**: Each iteration must target a different attack vector
4. **Respect protocol type**: CFT protocols cannot have Byzantine attacks; BFT protocols can have both
