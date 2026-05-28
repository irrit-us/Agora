"""
Prompts for Orchestrator Agent.

The Orchestrator Agent coordinates the bug hunting workflow and directly
calls LLM to generate bug reports and save bug patterns to Pattern Memory.
"""


# System prompt for the Orchestrator Agent
ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator Agent, the central coordinator of a multi-agent system for discovering vulnerabilities in distributed consensus protocols.

Your responsibilities:
1. Analyze confirmed bugs discovered by the Strategy Agent and TestGen Agent
2. Generate comprehensive bug reports with root cause analysis
3. Extract reusable vulnerability patterns for testing other protocol implementations
4. Track resource usage (tokens, cost) for each bug discovery

Be technical, precise, and actionable. Focus on providing insights that help developers understand and fix the vulnerabilities."""


def get_orchestrator_prompt(
    protocol_name: str,
    protocol_type: str,
    scenario_name: str,
    target_component: str,
    attack_category: str,
    vulnerability_hypothesis: str,
    preconditions: list[str],
    attack_steps: list[str],
    expected_bug_behavior: str,
    correct_behavior: str,
    test_file: str,
    test_output: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    api_cost: float,
) -> str:
    """
    Generate the Orchestrator Agent's prompt for bug report and pattern extraction.

    The Orchestrator Agent uses this prompt to analyze confirmed bugs and generate:
    1. A detailed bug report with root cause analysis
    2. A reusable bug pattern for testing other implementations

    Args:
        protocol_name: Name of the protocol (e.g., "raft", "hotstuff").
        protocol_type: Type of the protocol ("cft" or "bft").
        scenario_name: Name of the attack scenario.
        target_component: Target component of the attack.
        attack_category: Category of the attack (safety/liveness/agreement).
        vulnerability_hypothesis: The vulnerability being tested.
        preconditions: List of preconditions for the attack.
        attack_steps: List of attack steps.
        expected_bug_behavior: Expected behavior if bug exists.
        correct_behavior: What should happen if no bug.
        test_file: Path to the test file.
        test_output: Test execution output (truncated to 2000 chars).
        prompt_tokens: Number of prompt tokens used to discover this bug.
        completion_tokens: Number of completion tokens used.
        total_tokens: Total tokens used.
        api_cost: API cost in dollars.

    Returns:
        Complete prompt string for the Orchestrator Agent.
    """
    preconditions_text = "\n".join(f"- {p}" for p in preconditions) if preconditions else "N/A"
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(attack_steps)) if attack_steps else "N/A"

    return f"""As the Orchestrator Agent, analyze the following confirmed vulnerability and generate a comprehensive report.

## Confirmed Bug Details

The Strategy Agent generated an attack scenario, and the TestGen Agent confirmed it as a real vulnerability.

**Protocol**: {protocol_name}
**Protocol Type**: {protocol_type.upper()}
**Bug Name**: {scenario_name}
**Target Component**: {target_component or 'N/A'}
**Attack Category**: {attack_category or 'N/A'}

**Vulnerability Hypothesis**:
{vulnerability_hypothesis or 'N/A'}

**Preconditions**:
{preconditions_text}

**Attack Steps**:
{steps_text}

**Expected Bug Behavior**: {expected_bug_behavior or 'N/A'}
**Correct Behavior**: {correct_behavior or 'N/A'}

**Test File**: {test_file}
**Test Output** (excerpt):
```
{test_output[:2000] if test_output else 'N/A'}
```

## Resource Usage for This Bug Discovery

- **Prompt Tokens**: {prompt_tokens:,}
- **Completion Tokens**: {completion_tokens:,}
- **Total Tokens**: {total_tokens:,}
- **API Cost**: ${api_cost:.4f}

---

## Your Task

As the Orchestrator Agent, generate:

1. **Bug Report**: A comprehensive analysis including:
   - Root cause of the vulnerability
   - Potential security impact
   - Recommended fixes

2. **Bug Pattern**: A reusable pattern for testing similar vulnerabilities in other consensus protocol implementations.

## Output Format

<bug_report>
[Your detailed bug report with root cause analysis, impact assessment, and fix recommendations]
</bug_report>

<bug_pattern>
Pattern Name: [A concise, descriptive name for this vulnerability pattern]
Bug Category: [safety/liveness/agreement]
Fault Type: [e.g., byzantine_leader, network_partition, crash_recovery]
Trigger Condition: [Specific conditions that trigger this vulnerability]
Description: [Detailed description of the vulnerability pattern and why it occurs]
Test Template: [How to test for this pattern in other protocol implementations]
</bug_pattern>
"""
