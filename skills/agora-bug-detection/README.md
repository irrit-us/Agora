# Agora Bug Detection Skill

An AI-powered skill for Agents (Codex, Claude Code, Gemini, Antigravity, Cursor etc.) that automatically discovers bugs in distributed consensus protocol implementations.

## Installation

```bash
SKILL_BASE_URL=https://github.com/lebronlambert/Agora/tree/main npx skill skills/agora-bug-detection
```

## How It Works

The skill runs a 2-agent pipeline per iteration:

```
┌──────────────────────────────────────┐
│  Discovery (auto)                    │
│  Scans repo → determines CFT/BFT    │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│  Strategy Agent (reasoning)          │
│  Generates attack scenarios          │
└──────────────────┬───────────────────┘
                   │ <attack_scenario>
                   ▼
┌──────────────────────────────────────┐
│  TestGen Agent (execution)           │
│  Implements & runs tests             │
└──────────────────────────────────────┘
```

1. **Discovery** — a subagent scans the repository (README, build files, source) to determine protocol type (CFT/BFT), language, and key components
2. **Strategy Agent** — uses knowledge of distributed systems to devise creative, realistic attack scenarios targeting safety/liveness/agreement violations
3. **TestGen Agent** — reads the target codebase, writes test code, executes it, self-heals on errors, and reports results

## Supported Languages

- Go (Raft, etcd, etc.)
- Rust (AlephBFT, etc.)
- Java (BFT-SMaRt, etc.)
- C++ (Bitcoin Core, etc.)

## Supported Protocol Types

- **CFT** (Crash Fault Tolerant) — Raft, Paxos, ZAB, etc.
- **BFT** (Byzantine Fault Tolerant) — PBFT, HotStuff, Tendermint, AlephBFT, etc.

## Usage

Navigate to the target protocol repository and invoke the skill. No configuration file needed — the skill auto-discovers everything.

## Bug Patterns

The `resources/patterns/` directory contains 141 known bug patterns extracted from real vulnerabilities found in consensus protocols. The Strategy Agent draws inspiration from these patterns while ensuring each generated scenario is original and adapted to the target.

## Skill Structure

```
SKILL.md                          — Skill definition and orchestration logic
resources/
  prompts/
    strategy-system.md            — Strategy agent system prompt
    testgen-system.md             — TestGen agent system prompt
    constraints-cft.md            — CFT-specific attack constraints
    constraints-bft.md            — BFT-specific attack constraints
    exploitation.md               — Bug exploitation mode prompt
  patterns/
    index.yaml                    — Pattern index (one-line summaries)
    cft/                          — CFT bug patterns (JSON)
    bft/                          — BFT bug patterns (JSON)
```

## License

MIT
