"""
Strategy Implementations - Concrete implementations of strategy interfaces.

This module provides various strategy implementations for ablation experiments:
- DefaultStrategyGenerator: Full LLM-based strategy generation
- DefaultExploitationHandler: Full LLM-based bug exploitation
"""

import asyncio
import logging
from typing import Any

from ..memory.llm_logs import get_action_logger
from ..prompts import get_bug_exploitation_prompt, get_constraint_for_protocol
from ..utils.token_usage import TokenUsage
from .prompt_builder import ATTACK_SCENARIO_FORMAT, PromptBuilder
from .result_parser import ResultParser
from .strategies import (
    AttackScenario,
    ExploitationHandler,
    StrategyContext,
    StrategyGenerator,
    TestResult,
)
from .tool_agent import ToolAgent

logger = logging.getLogger(__name__)


async def _self_repair_attack_scenario(
    agent: ToolAgent,
    original_response: str,
    token_accumulator: TokenUsage | None = None,
) -> AttackScenario | None:
    """
    Attempt to salvage a strategy response that failed format parsing.

    Sends the original response back to the LLM with the expected format
    template, asking it to restructure (not regenerate) the content.
    """
    action_logger = get_action_logger()

    truncated = original_response[-3000:]
    if len(original_response) > 3000:
        truncated = "...(truncated)\n" + truncated

    repair_prompt = (
        "Your previous response contained valuable analysis but was not "
        "formatted correctly. The response MUST include an <attack_scenario> block.\n\n"
        "Here is your original response (may be truncated):\n"
        "---\n"
        f"{truncated}\n"
        "---\n\n"
        "Reformat your analysis into this exact format:\n\n"
        f"{ATTACK_SCENARIO_FORMAT}\n\n"
        "Output ONLY the <attack_scenario> block based on your original analysis. "
        "Do not add any other text."
    )

    try:
        repair_response = await agent.run(repair_prompt, max_iterations=1)
        if token_accumulator is not None:
            token_accumulator.add(repair_response.token_usage)

        if repair_response.error:
            logger.warning(f"[SELF-REPAIR] LLM error: {repair_response.error}")
            return None

        scenario = ResultParser.parse_attack_scenario(repair_response.content)
        if scenario:
            logger.info(f"[SELF-REPAIR] Successfully recovered scenario: {scenario.name}")
            action_logger.info(f"[SELF-REPAIR] Recovered scenario: {scenario.name}")
        else:
            logger.warning("[SELF-REPAIR] Repaired response still failed parsing")
            action_logger.warning("[SELF-REPAIR] Repaired response still failed parsing")
        return scenario
    except Exception as e:
        logger.warning(f"[SELF-REPAIR] Unexpected error: {e}")
        return None


class DefaultStrategyGenerator(StrategyGenerator):
    """
    Default LLM-based strategy generator.
    
    Uses the Strategy Agent to generate intelligent attack scenarios.
    """
    
    def __init__(
        self,
        strategy_agent: ToolAgent,
        max_iterations: int = 3,
    ):
        self.strategy_agent = strategy_agent
        self.max_iterations = max_iterations
        self._last_token_usage: dict[str, Any] = {}
    
    async def generate(self, context: StrategyContext) -> AttackScenario | None:
        """Generate attack scenario using Strategy Agent."""
        prompt = PromptBuilder.build_strategy_prompt(context)
        
        response = await self.strategy_agent.run(
            prompt, max_iterations=self.max_iterations
        )
        
        self._last_token_usage = response.token_usage
        
        if response.error:
            logger.error(f"Strategy agent error: {response.error}")
            return None
        
        scenario = ResultParser.parse_attack_scenario(response.content)
        if not scenario:
            scenario = await _self_repair_attack_scenario(
                self.strategy_agent, response.content
            )
        return scenario
    
    def get_token_usage(self) -> dict[str, Any]:
        """Get token usage from last generation."""
        return self._last_token_usage


class DefaultExploitationHandler(ExploitationHandler):
    """
    Default LLM-based bug exploitation handler.
    
    When a bug is confirmed, generates creative variations and related
    attack scenarios to find more bugs of similar nature.
    """
    
    def __init__(
        self,
        strategy_agent: ToolAgent,
        testgen_agent: ToolAgent,
        protocol_name: str,
        protocol_type: str,
        max_testgen_iterations: int = 100,
    ):
        """
        Initialize the exploitation handler.
        
        Args:
            strategy_agent: Agent for generating exploitation scenarios.
            testgen_agent: Agent for implementing and running tests.
            protocol_name: Name of the protocol.
            protocol_type: Type of protocol (cft/bft).
            max_testgen_iterations: Max iterations for TestGen agent.
        """
        self.strategy_agent = strategy_agent
        self.testgen_agent = testgen_agent
        self.protocol_name = protocol_name
        self.protocol_type = protocol_type
        self.max_testgen_iterations = max_testgen_iterations
        self._cumulative_token_usage = TokenUsage()
    
    async def exploit(
        self,
        original_scenario: AttackScenario,
        original_result: TestResult,
        context: StrategyContext,
        max_attempts: int,
    ) -> list[tuple[AttackScenario, TestResult | None]]:
        """
        Exploit a confirmed bug to find related vulnerabilities.
        
        Args:
            original_scenario: The scenario that triggered the bug.
            original_result: Test result from the bug.
            context: Strategy context (unused, kept for interface compatibility).
            max_attempts: Maximum exploitation attempts.
            
        Returns:
            List of (scenario, test_result) tuples for each exploitation attempt.
        """
        results: list[tuple[AttackScenario, TestResult | None]] = []
        previous_scenarios: list[str] = []
        
        action_logger = get_action_logger()
        original_bug_name = original_scenario.name
        
        logger.info(
            f"[BUG EXPLOITATION] Starting exploitation mode for bug: {original_bug_name}"
        )
        action_logger.info(
            f"[BUG EXPLOITATION] Starting exploitation for confirmed bug: {original_bug_name} "
            f"(max {max_attempts} attempts)"
        )
        
        # Format bug context once for all attempts
        bug_context = PromptBuilder.format_bug_context(original_scenario, original_result)
        constraint = get_constraint_for_protocol(self.protocol_type)
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"[BUG EXPLOITATION] Attempt {attempt}/{max_attempts}")
            action_logger.info(
                f"[BUG EXPLOITATION] Attempt {attempt}/{max_attempts}: "
                f"Generating related attack scenario..."
            )
            
            try:
                # Step 1: Generate exploitation prompt
                exploitation_prompt = get_bug_exploitation_prompt(
                    bug_context=bug_context,
                    protocol_name=self.protocol_name,
                    protocol_type=self.protocol_type,
                    constraint=constraint,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    previous_scenarios=previous_scenarios if previous_scenarios else None,
                )
                
                # Step 2: Strategy Agent generates related scenario
                strategy_response = await self.strategy_agent.run(
                    exploitation_prompt, max_iterations=50
                )
                
                # Accumulate token usage
                self._cumulative_token_usage.add(strategy_response.token_usage)
                
                if strategy_response.error:
                    action_logger.error(
                        f"[BUG EXPLOITATION] Strategy error: {strategy_response.error}"
                    )
                    continue
                
                # Log strategy response
                action_logger.thinking(
                    f"[BUG EXPLOITATION] Strategy Output (Attempt {attempt})",
                    strategy_response.content,
                )
                
                # Step 3: Parse the new scenario
                new_scenario = ResultParser.parse_attack_scenario(strategy_response.content)
                if not new_scenario:
                    action_logger.info(
                        f"[BUG EXPLOITATION] Parse failed in attempt {attempt}, attempting self-repair..."
                    )
                    new_scenario = await _self_repair_attack_scenario(
                        self.strategy_agent,
                        strategy_response.content,
                        self._cumulative_token_usage,
                    )
                    if not new_scenario:
                        action_logger.error(
                            f"[BUG EXPLOITATION] Self-repair failed in attempt {attempt}"
                        )
                        continue
                
                previous_scenarios.append(new_scenario.name)
                
                logger.info(f"[BUG EXPLOITATION] Generated scenario: {new_scenario.name}")
                action_logger.info(
                    f"[BUG EXPLOITATION] New scenario: {new_scenario.name} | "
                    f"Target: {new_scenario.target_component or 'N/A'}"
                )
                
                # Step 4: TestGen implements and executes the test
                testgen_prompt = PromptBuilder.build_testgen_prompt(new_scenario)
                testgen_response = await self.testgen_agent.run(
                    testgen_prompt,
                    max_iterations=self.max_testgen_iterations,
                )
                
                # Accumulate token usage
                self._cumulative_token_usage.add(testgen_response.token_usage)
                
                if testgen_response.error:
                    action_logger.error(
                        f"[BUG EXPLOITATION] TestGen error: {testgen_response.error}"
                    )
                    results.append((new_scenario, None))
                    continue
                
                # Log testgen response
                action_logger.thinking(
                    f"[BUG EXPLOITATION] TestGen Output (Attempt {attempt})",
                    testgen_response.content,
                )
                
                # Step 5: Parse test result
                test_result = ResultParser.parse_test_result(testgen_response.content)
                if test_result:
                    action_logger.info(
                        f"[BUG EXPLOITATION] Test result: {test_result.result} | "
                        f"File: {test_result.test_file}"
                    )
                
                # Step 6: Check for new confirmed bug
                if ResultParser.has_confirmed_bug(testgen_response.content):
                    logger.info(
                        f"[BUG EXPLOITATION] ADDITIONAL BUG FOUND: {new_scenario.name}"
                    )
                    action_logger.info(
                        f"[BUG EXPLOITATION] SUCCESS! Additional bug found: {new_scenario.name}"
                    )
                else:
                    action_logger.info(
                        f"[BUG EXPLOITATION] Attempt {attempt}: No additional bug found"
                    )
                
                results.append((new_scenario, test_result))
                
            except asyncio.CancelledError:
                logger.info("[BUG EXPLOITATION] Cancelled by user")
                raise
            except Exception as e:
                logger.error(f"[BUG EXPLOITATION] Error in attempt {attempt}: {e}")
                action_logger.error(
                    f"[BUG EXPLOITATION] Error in attempt {attempt}: {str(e)}"
                )
        
        # Summary logging
        bugs_found = sum(
            1 for _, r in results 
            if r and ResultParser.has_confirmed_bug(f"<confirmed_bug>{r.result}</confirmed_bug>")
        )
        logger.info(
            f"[BUG EXPLOITATION] Completed {max_attempts} attempts, "
            f"found {bugs_found} additional bugs"
        )
        action_logger.info(
            f"[BUG EXPLOITATION] Exploitation complete: {max_attempts} attempts, "
            f"{bugs_found} additional bugs found"
        )
        
        return results
    
    def get_token_usage(self) -> dict[str, Any]:
        """Get cumulative token usage from exploitation."""
        return self._cumulative_token_usage.to_dict()
