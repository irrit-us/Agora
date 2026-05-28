"""
Prompt Builder - Centralized prompt construction for agents.

This module consolidates all prompt building logic that was previously
scattered throughout the Orchestrator class.
"""

import logging

from .strategies import AttackScenario, StrategyContext, TestResult

logger = logging.getLogger(__name__)

ATTACK_SCENARIO_FORMAT = """\
<attack_scenario>
Name: [Descriptive name for this attack - be specific]
Target Component: [Which module/function to target]
Vulnerability Hypothesis: [What specific vulnerability you're testing]
Attack Category: [safety/liveness/agreement]
Inspiration Source: [pattern_memory::<pattern_id> | original]

Preconditions:
- [Required conditions for the attack]

Attack Steps:
1. [Specific step 1]
2. [Specific step 2]
...

Expected Bug Behavior: [What happens if bug exists]
Correct Behavior: [What should happen]

Assertions:
- [What to check in test]
</attack_scenario>"""


class PromptBuilder:
    """
    Centralized prompt builder for all agent interactions.
    
    Provides clean, testable methods for constructing prompts.
    """
    
    @staticmethod
    def build_strategy_prompt(context: StrategyContext) -> str:
        """
        Build prompt for Strategy Agent to generate an attack scenario.
        
        Args:
            context: Strategy generation context.
            
        Returns:
            Complete prompt string.
        """
        rejection_context = PromptBuilder.build_rejection_context(
            context.rejected_strategies,
            context.rejected_pattern_ids,
        )
        
        return f"""Generate an ORIGINAL attack strategy for {context.protocol_name} protocol.

Protocol Info:
- Name: {context.protocol_name}
- Description: {context.protocol_description or 'N/A'}
- Type: {context.protocol_type.upper()}
- Language: {context.protocol_language}

Constraints:
{context.constraint}
{rejection_context}

Repository Context:
{context.repo_context or 'N/A'}

{context.pattern_context}

Think creatively about potential vulnerabilities in distributed consensus protocols:
- Safety violations (double commits, conflicting decisions)
- Liveness issues (deadlocks, stalls, infinite loops)
- Agreement violations (nodes diverging)
- Edge cases in view changes, leader elections, or timeout handling
- Race conditions in message processing
- State corruption through malformed or out-of-order messages

Output your strategy in this format (include Inspiration Source):

{ATTACK_SCENARIO_FORMAT}
"""

    @staticmethod
    def build_similarity_check_prompt(
        scenario: AttackScenario,
        test_globs: list[str],
    ) -> str:
        """
        Build prompt for checking if similar test exists.
        
        Args:
            scenario: Attack scenario to check.
            test_globs: Glob patterns for finding test files.
            
        Returns:
            Prompt string.
        """
        globs_text = (
            "\n".join(f"- {g}" for g in test_globs)
            if test_globs
            else "- **/*_test.*"
        )
        scenario_text = PromptBuilder.format_scenario_for_testgen(scenario)
        
        return f"""Before implementing the test, first check if a similar test already exists.

Attack Scenario to implement:
{scenario_text}

Instructions:
1. Use glob_files to find all test files using these patterns (run each pattern):
{globs_text}
2. Read the test file names and any existing test that might test similar scenarios
3. Check if there's already a test that covers the SAME or VERY SIMILAR attack vector

If a similar test EXISTS, output:
<similar_test_found>
Existing Test: [path to existing test file]
Test Function: [name of the specific test function, e.g., TestLeaderElection or test_leader_election]
Similarity Reason: [why it's similar]
</similar_test_found>

If NO similar test exists, output:
<no_similar_test>
Checked files: [list of test files checked]
Reason: [why this is a new attack vector]
</no_similar_test>
"""

    @staticmethod
    def build_run_existing_test_prompt(
        test_file: str,
        test_name: str | None,
        scenario: AttackScenario,
    ) -> str:
        """
        Build prompt for running and validating an existing test.
        
        Args:
            test_file: Path to existing test file.
            test_name: Optional test function name.
            scenario: Attack scenario context.
            
        Returns:
            Prompt string.
        """
        scenario_text = PromptBuilder.format_scenario_for_testgen(scenario)
        
        return f"""Run and validate an existing test that covers a similar attack scenario.

Existing Test:
- File: {test_file}
- Test Function: {test_name or "all tests in file"}

Attack Scenario Context:
{scenario_text}

Instructions:
1. First, read the test file to understand what it tests
2. Run the test using run_command
3. If compilation fails:
   - Use repo_knowledge_find_lessons to find similar fixes
   - Fix the errors and re-run
   - After fixing, use repo_knowledge_add_lesson to record what you learned
4. Keep running until test passes OR you confirm it's a real bug

Understanding Test Results:
- Test PASSES: The attack vector is already covered, protocol handles it correctly
- Test FAILS with compilation error: Fix your test code and re-run
- Test FAILS with assertion error AND test code is correct: POTENTIAL BUG FOUND!

Output format when done:
<test_result>
Test File: {test_file}
Test Name: {test_name or "N/A"}
Result: [PASS/FAIL/ERROR]
Output: [test output summary]
Analysis: [Your analysis - is the test correct? is this a real bug?]
</test_result>

If you CONFIRMED a real bug (test code is correct AND assertion failure indicates vulnerability):
<confirmed_bug>{scenario.name}</confirmed_bug>
"""

    @staticmethod
    def build_testgen_prompt(scenario: AttackScenario) -> str:
        """
        Build prompt for TestGen Agent to implement a test.
        
        Args:
            scenario: Attack scenario to implement.
            
        Returns:
            Prompt string.
        """
        if scenario is None:
            logger.error("[PROMPT] build_testgen_prompt called with None scenario!")
            return ""
        
        logger.debug(f"[PROMPT] Building testgen prompt for scenario: {scenario.name}")
        scenario_text = PromptBuilder.format_scenario_for_testgen(scenario)
        
        if not scenario_text or len(scenario_text) < 50:
            logger.warning(f"[PROMPT] Scenario text is too short: len={len(scenario_text)}")
            logger.warning(f"[PROMPT] Scenario fields: name={scenario.name}, target={scenario.target_component}, steps={len(scenario.steps or [])}")
        
        return f"""Implement a test for the following attack scenario:

{scenario_text}

Instructions:
1. First, use repo_knowledge to understand the test structure
2. Read relevant source files to understand the implementation
3. Write a test file that:
   - Sets up the required preconditions
   - Executes the attack steps
   - Checks assertions
4. Run the test and observe the result
5. If compilation fails, use repo_knowledge_find_lessons to find solutions
6. After fixing issues, use repo_knowledge_add_lesson to record what you learned

Understanding Test Results:
- Test PASSES (assertion holds): Protocol handled attack correctly - NOT A BUG
- Test FAILS - there are MULTIPLE possible reasons:
  1. Compilation error / missing imports → Fix your test code
  2. Runtime error / wrong API usage → Fix your test code  
  3. Assertion fails but test logic is wrong → Fix your test code
  4. Assertion fails AND test code is correct → POTENTIAL BUG FOUND!

IMPORTANT: Only report a bug when you are CONFIDENT that:
- Your test code compiles and runs correctly
- The test logic correctly implements the attack scenario
- The assertion accurately checks for the expected behavior
- The assertion failure indicates a real protocol vulnerability

Output format when done:
<test_result>
Test File: [path]
Test Name: [name]
Result: [PASS/FAIL/ERROR]
Output: [test output summary]
Analysis: [Your analysis of the result - is the test correct? is this a real bug?]
</test_result>

If you CONFIRMED a real bug (test code is correct AND assertion failure indicates vulnerability):
Output: <confirmed_bug>{scenario.name}</confirmed_bug>

The Orchestrator will automatically generate a bug report and save the bug pattern.

If test fails but it's your test code that's wrong, just fix it and re-run. Do NOT report as a bug.
"""

    @staticmethod
    def format_scenario_for_testgen(scenario: AttackScenario) -> str:
        """
        Format attack scenario for TestGen prompt.
        
        Args:
            scenario: The scenario to format.
            
        Returns:
            Formatted string.
        """
        if scenario is None:
            logger.error("[PROMPT] format_scenario_for_testgen called with None scenario!")
            return ""
        
        preconditions = scenario.preconditions or []
        steps = scenario.steps or []
        assertions = scenario.assertions or []
        
        # Validate scenario fields
        missing_fields = []
        if not scenario.name:
            missing_fields.append("name")
        if not scenario.target_component:
            missing_fields.append("target_component")
        if not scenario.vulnerability_hypothesis:
            missing_fields.append("vulnerability_hypothesis")
        if not steps:
            missing_fields.append("steps")
        
        if missing_fields:
            logger.warning(f"[PROMPT] Scenario missing fields: {missing_fields}")
        
        logger.debug(f"[PROMPT] Formatting scenario: name={scenario.name}, preconditions={len(preconditions)}, steps={len(steps)}, assertions={len(assertions)}")
        
        return f"""Name: {scenario.name}
Target Component: {scenario.target_component}
Vulnerability Hypothesis: {scenario.vulnerability_hypothesis}
Attack Category: {scenario.attack_category}

Preconditions:
{chr(10).join(f'- {p}' for p in preconditions)}

Attack Steps:
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(steps))}

Expected Bug Behavior: {scenario.expected_bug_behavior}
Correct Behavior: {scenario.correct_behavior}

Assertions:
{chr(10).join(f'- {a}' for a in assertions)}
"""

    @staticmethod
    def format_bug_context(
        scenario: AttackScenario,
        result: TestResult,
    ) -> str:
        """
        Format bug context for exploitation.
        
        Args:
            scenario: Attack scenario that triggered the bug.
            result: Test result from the bug.
            
        Returns:
            Formatted bug context string.
        """
        preconditions = scenario.preconditions or []
        steps = scenario.steps or []
        assertions = scenario.assertions or []
        
        # Truncate for context efficiency
        test_code_excerpt = result.test_code[:2000] if result.test_code else "N/A"
        if result.test_code and len(result.test_code) > 2000:
            test_code_excerpt += "\n... (truncated)"
        
        test_output_excerpt = result.test_output[:1000] if result.test_output else "N/A"
        if result.test_output and len(result.test_output) > 1000:
            test_output_excerpt += "\n... (truncated)"
        
        return f"""### Bug Summary
- **Name**: {scenario.name}
- **Target Component**: {scenario.target_component}
- **Category**: {scenario.attack_category}

### Vulnerability Hypothesis
{scenario.vulnerability_hypothesis}

### Preconditions
{chr(10).join(f'- {p}' for p in preconditions) if preconditions else 'N/A'}

### Attack Steps That Triggered the Bug
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(steps)) if steps else 'N/A'}

### Expected Bug Behavior (Confirmed)
{scenario.expected_bug_behavior}

### Correct Behavior (What Should Have Happened)
{scenario.correct_behavior}

### Assertions Used
{chr(10).join(f'- {a}' for a in assertions) if assertions else 'N/A'}

### Test Code (Excerpt)
```
{test_code_excerpt}
```

### Test Output (Excerpt)
```
{test_output_excerpt}
```
"""

    @staticmethod
    def build_rejection_context(
        rejected_strategies: list[str],
        rejected_pattern_ids: list[str],
    ) -> str:
        """
        Build context about previously rejected strategies.
        
        Args:
            rejected_strategies: Previously rejected strategy descriptions.
            rejected_pattern_ids: Pattern IDs that must not be reused.
            
        Returns:
            Context string or empty string.
        """
        if not rejected_strategies and not rejected_pattern_ids:
            return ""
        
        parts: list[str] = []
        
        if rejected_strategies:
            parts.append(f"""
IMPORTANT: The following attack strategies have ALREADY been implemented as tests in this repository.
You MUST generate a DIFFERENT and ORIGINAL attack strategy.

Already existing strategies (DO NOT repeat these):
{chr(10).join(f"- {s}" for s in rejected_strategies)}
""")
        
        if rejected_pattern_ids:
            parts.append(f"""
Disallowed pattern_ids (already used or invalid):
{chr(10).join(f"- {p}" for p in rejected_pattern_ids)}
Only use pattern_ids from the provided pattern list.
""")
        
        parts.append("""
Think about:
- Different attack vectors not covered above
- Different Byzantine behaviors
- Edge cases in timing, ordering, or state transitions
- Combinations of faults that haven't been tested
""")
        
        return "\n".join(parts)

    @staticmethod
    def build_free_exploration_prompt(
        protocol_name: str,
        protocol_type: str,
        protocol_language: str,
        protocol_description: str,
        test_globs: list[str],
    ) -> str:
        """
        Build prompt for TestGen Agent to freely explore and generate tests.
        
        This is used in "no strategy" ablation mode where TestGen explores
        the codebase on its own without any guided attack scenario.
        
        Args:
            protocol_name: Name of the protocol.
            protocol_type: Type of protocol (cft/bft).
            protocol_language: Programming language.
            protocol_description: Protocol description.
            test_globs: Glob patterns for finding test files.
            
        Returns:
            Prompt string.
        """
        globs_text = (
            "\n".join(f"- {g}" for g in test_globs)
            if test_globs
            else "- **/*_test.*"
        )
        
        return f"""You are testing the {protocol_name} consensus protocol implementation.

Protocol Info:
- Name: {protocol_name}
- Type: {protocol_type.upper()}
- Language: {protocol_language}
- Description: {protocol_description or 'Distributed consensus protocol'}

Your Task:
Explore the codebase, identify a potential vulnerability or edge case, and write a test to verify it.

Instructions:
1. Use repo_knowledge to understand the codebase structure and key components
2. Use glob_files to find source files and existing tests:
{globs_text}
3. Read relevant source code to identify potential issues:
   - Race conditions in message handling
   - Edge cases in leader election or view changes
   - State corruption scenarios
   - Safety or liveness violations
4. Write a test that targets a specific vulnerability hypothesis
5. Run the test and analyze the result
6. If compilation fails, fix the errors and re-run
7. Keep iterating until the test passes OR you confirm a real bug

Understanding Test Results:
- Test PASSES (assertion holds): Protocol handled the scenario correctly - NOT A BUG
- Test FAILS - there are MULTIPLE possible reasons:
  1. Compilation error / missing imports → Fix your test code
  2. Runtime error / wrong API usage → Fix your test code  
  3. Assertion fails but test logic is wrong → Fix your test code
  4. Assertion fails AND test code is correct → POTENTIAL BUG FOUND!

IMPORTANT: Only report a bug when you are CONFIDENT that:
- Your test code compiles and runs correctly
- The test logic correctly implements the attack scenario
- The assertion accurately checks for the expected behavior
- The assertion failure indicates a real protocol vulnerability

Output format when done:
<test_result>
Test File: [path]
Test Name: [name]
Target Component: [what component you tested]
Vulnerability Hypothesis: [what issue you were testing for]
Result: [PASS/FAIL/ERROR]
Output: [test output summary]
Analysis: [Your analysis of the result - is the test correct? is this a real bug?]
</test_result>

If you CONFIRMED a real bug (test code is correct AND assertion failure indicates vulnerability):
Output: <confirmed_bug>[Brief description of the bug]</confirmed_bug>
"""
